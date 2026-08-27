// Copyright (c) 2026, sj and contributors
// For license information, please see license.txt

frappe.listview_settings["Salary Structure Assignment"] = {
	onload(listview) {
		listview.page.add_inner_button(__("Import"), () => show_ssa_import_dialog(listview));
	},
};

function show_ssa_import_dialog(listview) {
	const dialog = new frappe.ui.Dialog({
		title: __("Import Salary Structure Assignments"),
		fields: [
			{
				fieldname: "salary_structure",
				fieldtype: "Link",
				label: __("Salary Structure"),
				options: "Salary Structure",
				reqd: 1,
				get_query: () => ({ filters: { is_active: "Yes" } }),
			},
			{
				fieldname: "excel_file",
				fieldtype: "Attach",
				label: __("Excel File"),
				reqd: 1,
			},
			{
				fieldname: "help",
				fieldtype: "HTML",
				options: `<p class="text-muted small">${__(
					"Excel only needs Name, Start/From Date, End/To Date, and component amounts with exact names (Basic, HRA, …). Employee ID is not required — company and other details are fetched from the name. Select Salary Structure here. For PF/ESIC/PT/LWF: 1 or any amount = on, 0 or blank = off. Excel figures are ignored; employee and employer shares come from Company settings. When PF is on, the PF Type column (Limited PF / Full PF) sets the type. For workers, Basic and V-DA come from Skill Rate Revision; daily-wage columns are per-day × the SRR multiplier."
				)}</p>`,
			},
		],
		primary_action_label: __("Import"),
		primary_action(values) {
			if (!values.salary_structure || !values.excel_file) {
				frappe.msgprint(__("Select Salary Structure and attach the Excel file."));
				return;
			}
			dialog.hide();
			frappe.call({
				method:
					"saral_hr.saral_hr.doctype.salary_structure_assignment.ssa_excel_import.import_ssa_excel",
				args: {
					salary_structure: values.salary_structure,
					file_url: values.excel_file,
				},
				freeze: true,
				freeze_message: __("Importing SSAs…"),
				callback(r) {
					const msg = r.message || {};
					const created = msg.created || [];
					const errors = msg.errors || [];
					const warnings = msg.warnings || [];
					let html = `<p>${__("Created")}: <b>${created.length}</b></p>`;
					if (warnings.length) {
						html += `<p>${frappe.utils.escape_html(warnings.join("; "))}</p>`;
					}
					if (errors.length) {
						html += `<ul>${errors
							.map((e) => `<li>${frappe.utils.escape_html(e)}</li>`)
							.join("")}</ul>`;
					}
					frappe.msgprint({
						title: __("SSA Import"),
						indicator: errors.length ? "red" : "green",
						message: html,
					});
					listview.refresh();
				},
			});
		},
	});
	dialog.show();
}
