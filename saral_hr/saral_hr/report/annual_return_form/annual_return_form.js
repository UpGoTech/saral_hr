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
		const export_file = (method, label) => {
			const f = report.get_values();
			if (!f.company || !f.year) {
				frappe.msgprint({
					title: __("Missing Filters"),
					message: __("Please select Company and Year."),
					indicator: "orange",
				});
				return;
			}
			frappe.dom.freeze(label);
			frappe.call({
				method: `saral_hr.saral_hr.report.annual_return_form.annual_return_form.${method}`,
				args: { filters: f },
				callback(r) {
					frappe.dom.unfreeze();
					if (!r.message) return;
					const a = Object.assign(document.createElement("a"), {
						href: frappe.urllib.get_full_url(r.message),
						target: "_blank",
						rel: "noopener noreferrer",
					});
					document.body.appendChild(a);
					a.click();
					document.body.removeChild(a);
				},
				error() {
					frappe.dom.unfreeze();
				},
			});
		};

		report.page.add_inner_button(__("Download Excel"), () => {
			export_file("excel_report", __("Generating Excel…"));
		});
		report.page.add_inner_button(__("Download PDF"), () => {
			export_file("print_report", __("Generating PDF…"));
		});
		report.page.set_primary_action(__("Print"), () => {
			export_file("print_report", __("Generating PDF…"));
		}, "printer");
	},

	formatter(value, row, column, data, default_formatter) {
		if (!data) return default_formatter(value, row, column, data);
		if (column.fieldname === "date_of_joining" && value) {
			const shown = frappe.datetime.str_to_user(value);
			const html = `<div style="text-align:right">${frappe.utils.escape_html(shown)}</div>`;
			return data._is_total ? `<strong>${html}</strong>` : html;
		}
		if (column.fieldname === "designation") {
			const shown = value == null ? "" : String(value);
			const html = `<div style="text-align:left;padding-left:8px">${frappe.utils.escape_html(shown)}</div>`;
			return data._is_total ? `<strong>${html}</strong>` : html;
		}
		const formatted = default_formatter(value, row, column, data);
		if (data._is_total) return `<strong>${formatted}</strong>`;
		return formatted;
	},
};
