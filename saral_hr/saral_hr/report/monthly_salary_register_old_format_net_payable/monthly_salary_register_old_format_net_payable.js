frappe.query_reports["Monthly Salary Register Old Format Net Payable"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			reqd: 1,
		},
		{
			fieldname: "year",
			label: __("Year"),
			fieldtype: "Select",
			reqd: 1,
			default: String(new Date().getFullYear()),
			options: (function () {
				const y = new Date().getFullYear(),
					opts = [""];
				for (let i = y - 2; i <= y + 2; i++) opts.push(String(i));
				return opts;
			})(),
		},
		{
			fieldname: "month",
			label: __("Month"),
			fieldtype: "Select",
			reqd: 1,
			options: [
				"",
				"January",
				"February",
				"March",
				"April",
				"May",
				"June",
				"July",
				"August",
				"September",
				"October",
				"November",
				"December",
			],
		},
		{
			fieldname: "population",
			label: __("Population"),
			fieldtype: "Select",
			reqd: 1,
			default: "All",
			options: ["All", "Staff", "Worker", "Consultant"].join("\n"),
		},
		{
			fieldname: "format",
			label: __("Format"),
			fieldtype: "Select",
			reqd: 1,
			default: "Full",
			options: ["Full", "Compressed"].join("\n"),
		},
	],

	onload(report) {
		report.page.add_inner_button(__("Download PDF"), () => {
			_export(report, "print_report", __("Generating PDF…"));
		});
		report.page.add_inner_button(__("Download Excel"), () => {
			_export(report, "excel_report", __("Generating Excel…"));
		});
	},

	formatter(value, row, column, data, default_formatter) {
		if (!data) return default_formatter(value, row, column, data);
		const def = (v) => default_formatter(v, row, column, data);
		const fn = column.fieldname;
		if (data._is_total) {
			const skip = ["bank_name", "ifsc", "bank_account", "total_month_day", "sr_no"];
			if (skip.includes(fn)) {
				return "";
			}
			return `<strong>${def(value)}</strong>`;
		}
		if (["total_gross", "total_earning", "total_deductions", "net_payable"].includes(fn)) {
			return `<span style="background:#ffff99;padding:0 4px;">${def(value)}</span>`;
		}
		return def(value);
	},
};

function _export(report, method, freeze_msg) {
	const f = report.get_values();
	if (!f.company || !f.year || !f.month) {
		frappe.msgprint({
			title: __("Missing Filters"),
			message: __("Please select Company, Year and Month."),
			indicator: "orange",
		});
		return;
	}
	frappe.dom.freeze(freeze_msg);
	frappe.call({
		method: `saral_hr.saral_hr.report.monthly_salary_register_old_format_net_payable.monthly_salary_register_old_format_net_payable.${method}`,
		args: { filters: JSON.stringify(f) },
		callback(r) {
			frappe.dom.unfreeze();
			if (r.message) {
				const a = Object.assign(document.createElement("a"), {
					href: frappe.urllib.get_full_url(r.message),
					target: "_blank",
					rel: "noopener noreferrer",
				});
				document.body.appendChild(a);
				a.click();
				document.body.removeChild(a);
			}
		},
		error() {
			frappe.dom.unfreeze();
			frappe.msgprint({
				title: __("Error"),
				message: __("Export failed."),
				indicator: "red",
			});
		},
	});
}
