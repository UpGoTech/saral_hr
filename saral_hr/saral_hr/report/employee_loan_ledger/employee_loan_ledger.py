# Copyright (c) 2026, sj and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from saral_hr.saral_hr.report.loan_ledger_common import (
	build_ledger_pdf_html,
	build_ledger_rows,
	ledger_columns,
	parse_filters,
	save_ledger_pdf,
)


def execute(filters=None):
	filters = filters or {}
	columns = ledger_columns()
	if not filters.get("employee"):
		return columns, []

	rows, _totals = build_ledger_rows(
		employee=filters.get("employee"),
		company=filters.get("company"),
		from_date=filters.get("from_date"),
		to_date=filters.get("to_date"),
	)
	return columns, rows


@frappe.whitelist()
def print_report(filters):
	filters = parse_filters(filters)
	if not filters.get("employee"):
		frappe.throw(_("Employee is required to print the ledger."))

	rows, _totals = build_ledger_rows(
		employee=filters.get("employee"),
		company=filters.get("company"),
		from_date=filters.get("from_date"),
		to_date=filters.get("to_date"),
	)
	emp_name = frappe.db.get_value("Company Link", filters.get("employee"), "full_name") or ""
	company = filters.get("company") or frappe.db.get_value(
		"Company Link", filters.get("employee"), "company"
	) or ""
	meta = [
		"Employee: {0} ({1})".format(filters.get("employee"), emp_name),
	]
	if filters.get("from_date") or filters.get("to_date"):
		meta.append(
			"Period: {0} to {1}".format(
				filters.get("from_date") or "…", filters.get("to_date") or "…"
			)
		)
	html = build_ledger_pdf_html("Employee Loan Ledger", company, meta, rows)
	return save_ledger_pdf(html, "Employee_Loan_Ledger")
