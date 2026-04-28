// Copyright (c) 2026, sj and contributors
// For license information, please see license.txt

frappe.query_reports["Attendance Daily Rate Workers Report"] = {
	"filters": [
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"reqd": 1
		},
		{
			"fieldname": "year",
			"label": __("Year"),
			"fieldtype": "Select",
			"options": get_year_options(),
			"default": new Date().getFullYear().toString(),
			"reqd": 1
		},
		{
			"fieldname": "month",
			"label": __("Month"),
			"fieldtype": "Select",
			"options": [
				{ "value": "1",  "label": __("January") },
				{ "value": "2",  "label": __("February") },
				{ "value": "3",  "label": __("March") },
				{ "value": "4",  "label": __("April") },
				{ "value": "5",  "label": __("May") },
				{ "value": "6",  "label": __("June") },
				{ "value": "7",  "label": __("July") },
				{ "value": "8",  "label": __("August") },
				{ "value": "9",  "label": __("September") },
				{ "value": "10", "label": __("October") },
				{ "value": "11", "label": __("November") },
				{ "value": "12", "label": __("December") },
			],
			"default": (new Date().getMonth() + 1).toString(),
			"reqd": 1
		}
	],

	onload(report) {
		report.page.set_primary_action(__("Print"), function () {
			const f = report.get_values();
			if (!f.company || !f.year || !f.month) {
				frappe.msgprint({
					title: __("Missing Filters"),
					message: __("Please select Company, Year and Month before printing."),
					indicator: "orange",
				});
				return;
			}
			frappe.dom.freeze(__("Generating PDF…"));
			frappe.call({
				method: "saral_hr.saral_hr.report.attendance_daily_rate_workers_report.attendance_daily_rate_workers_report.print_report",
				args: {
					filters: JSON.stringify({
						company: f.company || "",
						year:    f.year    || "",
						month:   f.month   || "",
					}),
				},
				callback(r) {
					frappe.dom.unfreeze();
					if (r.message) {
						const a = Object.assign(document.createElement("a"), {
							href:   frappe.urllib.get_full_url(r.message),
							target: "_blank",
							rel:    "noopener noreferrer",
						});
						document.body.appendChild(a);
						a.click();
						document.body.removeChild(a);
					}
				},
				error() {
					frappe.dom.unfreeze();
					frappe.msgprint({
						title:   __("Error"),
						message: __("Failed to generate PDF."),
						indicator: "red",
					});
				},
			});
		}, "printer");
	},
};

function get_year_options() {
	var cur = new Date().getFullYear();
	var opts = [];
	for (var y = cur - 2; y <= cur + 1; y++) {
		opts.push(y.toString());
	}
	return opts.join("\n");
}