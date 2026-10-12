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
	if not filters.get("loan"):
		return columns, []

	rows, _totals = build_ledger_rows(
		loan=filters.get("loan"),
		company=filters.get("company"),
		from_date=filters.get("from_date"),
		to_date=filters.get("to_date"),
	)
	return columns, rows


@frappe.whitelist()
def print_report(filters):
	filters = parse_filters(filters)
	if not filters.get("loan"):
		frappe.throw(_("Loan is required to print the ledger."))

	rows, _totals = build_ledger_rows(
		loan=filters.get("loan"),
		company=filters.get("company"),
		from_date=filters.get("from_date"),
		to_date=filters.get("to_date"),
	)
	loan = frappe.db.get_value(
		"Employee Loan",
		filters.get("loan"),
		["employee", "full_name", "company", "amount"],
		as_dict=True,
	) or {}
	company = filters.get("company") or loan.get("company") or ""
	meta = [
		"Loan: {0}".format(filters.get("loan")),
		"Employee: {0} ({1})".format(loan.get("employee") or "", loan.get("full_name") or ""),
	]
	if filters.get("from_date") or filters.get("to_date"):
		meta.append(
			"Period: {0} to {1}".format(
				filters.get("from_date") or "…", filters.get("to_date") or "…"
			)
		)
	html = build_ledger_pdf_html("Loan Ledger", company, meta, rows)
	return save_ledger_pdf(html, "Loan_Ledger")
