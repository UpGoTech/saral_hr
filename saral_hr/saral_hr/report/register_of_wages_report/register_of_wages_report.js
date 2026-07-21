// Copyright (c) 2026, Saral HR
// Register of wages report — filters

frappe.query_reports["Register of wages report"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			reqd: 1,
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "year",
			label: __("Year"),
			fieldtype: "Select",
			reqd: 1,
			options: (function () {
				const cur = new Date().getFullYear();
				const years = [];
				for (let y = cur - 2; y <= cur + 1; y++) years.push(String(y));
				return years.join("\n");
			})(),
			default: String(new Date().getFullYear()),
		},
		{
			fieldname: "month",
			label: __("Month"),
			fieldtype: "Select",
			reqd: 1,
			options: [
				"January", "February", "March", "April",
				"May", "June", "July", "August",
				"September", "October", "November", "December",
			].join("\n"),
			default: ["January","February","March","April","May","June","July",
				 "August","September","October","November","December"][new Date().getMonth()],
		},
	],

	onload(report) {
		const $btn = report.page.add_inner_button(__("Export Excel"), function () {
			const values = frappe.query_report.get_filter_values(true);
			if (!values.company || !values.year || !values.month) {
				frappe.msgprint({
					title: __("Missing Filters"),
					message: __("Please select Company, Year, and Month first."),
					indicator: "orange",
				});
				return;
			}

			$btn.prop("disabled", true);
			frappe.call({
				method: "saral_hr.saral_hr.report.register_of_wages_report.register_of_wages_report.export_excel",
				args: { filters: JSON.stringify(values) },
				callback(r) {
					$btn.prop("disabled", false);
					if (r.message) {
						const a = Object.assign(document.createElement("a"), {
							href: frappe.urllib.get_full_url(r.message),
							target: "_blank",
							rel: "noopener noreferrer",
						});
						document.body.appendChild(a);
						a.click();
						document.body.removeChild(a);
					} else {
						frappe.msgprint({
							title: __("Error"),
							message: __("Failed to generate Excel file."),
							indicator: "red",
						});
					}
				},
				error() {
					$btn.prop("disabled", false);
					frappe.msgprint({
						title: __("Error"),
						message: __("Failed to generate Excel file."),
						indicator: "red",
					});
				},
			});
		});
	},
};