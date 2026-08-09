// Copyright (c) 2026, sj and contributors
// For license information, please see license.txt

frappe.ui.form.on("Employee Loan", {
	refresh(frm) {
		if (frm.doc.docstatus === 1 && frm.doc.status === "Active") {
			frm.add_custom_button(__("Generate Monthly Loan Dues"), () => {
				frappe.set_route("generate-monthly-loan-dues");
			});
		}
	},
});
