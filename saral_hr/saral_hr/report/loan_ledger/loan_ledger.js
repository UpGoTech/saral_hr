// Copyright (c) 2026, sj and contributors
// For license information, please see license.txt

frappe.query_reports["Loan Ledger"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
		},
		{
			fieldname: "loan",
			label: __("Loan"),
			fieldtype: "Link",
			options: "Employee Loan",
			reqd: 1,
			get_query() {
				const company = frappe.query_report.get_filter_value("company");
				const filters = { docstatus: 1 };
				if (company) filters.company = company;
				return { filters };
			},
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
		},
	],

	onload(report) {
		report.page.set_primary_action(__("Print"), () => {
			const f = report.get_values();
			if (!f.loan) {
				frappe.msgprint({
					title: __("Missing Filters"),
					message: __("Please select Loan before printing."),
					indicator: "orange",
				});
				return;
			}
			frappe.dom.freeze(__("Generating PDF…"));
			frappe.call({
				method: "saral_hr.saral_hr.report.loan_ledger.loan_ledger.print_report",
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
						message: __("Failed to generate PDF."),
						indicator: "red",
					});
				},
			});
		}, "printer");
	},

	formatter(value, row, column, data, default_formatter) {
		if (!data) return default_formatter(value, row, column, data);
		const def = (v) => default_formatter(v, row, column, data);
		if (data.bold) {
			if (column.fieldname === "posting_date") return "";
			return `<strong>${def(value)}</strong>`;
		}
		return def(value);
	},
};
