// Copyright (c) 2026, sj and contributors
// For license information, please see license.txt

frappe.ui.form.on("Employee Loan", {
	refresh(frm) {
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__("Loan Ledger"), () => {
				frappe.set_route("query-report", "Loan Ledger", {
					loan: frm.doc.name,
					company: frm.doc.company,
				});
			});
			frm.add_custom_button(__("Employee Loan Ledger"), () => {
				frappe.set_route("query-report", "Employee Loan Ledger", {
					employee: frm.doc.employee,
					company: frm.doc.company,
				});
			});
		}
		if (frm.doc.docstatus === 1 && frm.doc.status === "Active") {
			frm.add_custom_button(__("Generate Monthly Loan Dues"), () => {
				frappe.set_route("generate-monthly-loan-dues");
			});
		}
	},
});
