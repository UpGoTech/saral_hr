"""Rename existing Employee Loan docs to {last4}-LN-{n} format."""

import frappe

from saral_hr.saral_hr.doctype.employee_loan.employee_loan import _employee_loan_prefix


def _is_short_loan_id(name):
	parts = (name or "").split("-")
	return (
		len(parts) == 3
		and parts[0].isdigit()
		and parts[1] == "LN"
		and parts[2].isdigit()
	)


def execute():
	loans = frappe.get_all(
		"Employee Loan",
		fields=["name", "employee"],
		order_by="employee asc, creation asc",
	)
	counters = {}

	for loan in loans:
		prefix = _employee_loan_prefix(loan.employee)
		if _is_short_loan_id(loan.name):
			counters[prefix] = max(counters.get(prefix, 0), int(loan.name.split("-")[-1]))
			continue

		next_n = counters.get(prefix, 0) + 1
		new_name = f"{prefix}-{str(next_n).zfill(2)}"
		while frappe.db.exists("Employee Loan", new_name):
			next_n += 1
			new_name = f"{prefix}-{str(next_n).zfill(2)}"
		counters[prefix] = next_n
		frappe.rename_doc("Employee Loan", loan.name, new_name, force=True, merge=False)
