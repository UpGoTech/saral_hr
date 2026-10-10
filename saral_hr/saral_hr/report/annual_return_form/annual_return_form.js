frappe.query_reports["Annual Return Form"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			reqd: 1,
		},
		saral_hr.period_picker.year_select_field(),
	],

	onload(report) {
		report.page.add_inner_button(__("Download Excel"), () => {
			const f = report.get_values();
			if (!f.company || !f.year) {
				frappe.msgprint({
					title: __("Missing Filters"),
					message: __("Please select Company and Year."),
					indicator: "orange",
				});
				return;
			}
			frappe.dom.freeze(__("Generating Excel…"));
			frappe.call({
				method: "saral_hr.saral_hr.report.annual_return_form.annual_return_form.excel_report",
				args: { filters: f },
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
				},
			});
		});
	},

	formatter(value, row, column, data, default_formatter) {
		if (!data) return default_formatter(value, row, column, data);
		const formatted = default_formatter(value, row, column, data);
		if (data._is_total) return `<strong>${formatted}</strong>`;
		return formatted;
	},
};
