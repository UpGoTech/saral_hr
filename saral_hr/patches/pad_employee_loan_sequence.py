"""Pad Employee Loan sequence to at least 2 digits (0002-LN-1 → 0002-LN-01)."""

import frappe

from saral_hr.saral_hr.doctype.employee_loan.employee_loan import _employee_loan_prefix


def execute():
	loans = frappe.get_all(
		"Employee Loan",
		fields=["name", "employee"],
		order_by="name asc",
	)
	for loan in loans:
		parts = (loan.name or "").split("-")
		if not (
			len(parts) == 3
			and parts[0].isdigit()
			and parts[1] == "LN"
			and parts[2].isdigit()
		):
			continue
		padded = parts[2].zfill(2)
		if padded == parts[2]:
			continue
		new_name = f"{parts[0]}-LN-{padded}"
		if frappe.db.exists("Employee Loan", new_name):
			# Collision — allocate next free padded number under same prefix
			prefix = _employee_loan_prefix(loan.employee)
			n = int(parts[2])
			while frappe.db.exists("Employee Loan", f"{prefix}-{str(n).zfill(2)}"):
				n += 1
			new_name = f"{prefix}-{str(n).zfill(2)}"
		frappe.rename_doc("Employee Loan", loan.name, new_name, force=True, merge=False)
