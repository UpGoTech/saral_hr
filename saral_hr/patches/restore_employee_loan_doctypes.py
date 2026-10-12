"""Restore Employee Loan DocTypes if scrap_legacy_loan_module removed them."""

import frappe


def execute():
	# Child first, then parent, then standalone Due.
	for dn in (
		"employee_loan_prepayment",
		"employee_loan",
		"employee_loan_due",
	):
		frappe.reload_doc("saral_hr", "doctype", dn, force=True)
