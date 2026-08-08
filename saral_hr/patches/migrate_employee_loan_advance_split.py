"""Migrate Employee Loan Advance rows into Employee Loan / Employee Advance."""

import frappe
from frappe.utils import flt


LOAN_TYPES = ("Loan", "Loan-I", "Loan-II")


def execute():
	if not frappe.db.exists("DocType", "Employee Loan Advance"):
		return
	if not frappe.db.exists("DocType", "Employee Loan"):
		return
	if not frappe.db.exists("DocType", "Employee Advance"):
		return

	_migrate_loans()
	_migrate_advances()


def _migrate_loans():
	names = frappe.get_all(
		"Employee Loan Advance",
		filters={"type": ["in", list(LOAN_TYPES)]},
		pluck="name",
		order_by="creation asc",
	)
	for name in names:
		if frappe.db.exists("Employee Loan", name):
			continue
		old = frappe.get_doc("Employee Loan Advance", name)
		doc = frappe.get_doc(
			{
				"doctype": "Employee Loan",
				"name": old.name,
				"employee": old.employee,
				"full_name": old.full_name,
				"company": old.company,
				"date": old.date,
				"amount": old.amount,
				"currency": old.currency or "INR",
				"reason": old.reason,
				"start_month": old.start_month,
				"start_year": old.start_year,
				"tenure_months": old.tenure_months,
				"installment_gap": old.installment_gap or "Monthly",
				"monthly_deduction": old.monthly_deduction,
				"total_deducted": old.total_deducted,
				"outstanding_amount": old.outstanding_amount,
				"schedule": [
					{
						"month": row.month,
						"deduction_amount": row.deduction_amount,
						"is_deducted": row.is_deducted,
						"is_deferred": row.is_deferred,
						"deferred_to": row.deferred_to,
					}
					for row in (old.schedule or [])
				],
			}
		)
		doc.flags.ignore_validate = True
		doc.flags.ignore_permissions = True
		doc.flags.ignore_mandatory = True
		doc.insert(ignore_permissions=True)
		_copy_meta(old, "Employee Loan")


def _migrate_advances():
	names = frappe.get_all(
		"Employee Loan Advance",
		filters={"type": "Advance"},
		pluck="name",
		order_by="creation asc",
	)
	for name in names:
		if frappe.db.exists("Employee Advance", name):
			continue
		old = frappe.get_doc("Employee Loan Advance", name)
		doc = frappe.get_doc(
			{
				"doctype": "Employee Advance",
				"name": old.name,
				"employee": old.employee,
				"full_name": old.full_name,
				"company": old.company,
				"date": old.date,
				"amount": old.amount,
				"currency": old.currency or "INR",
				"reason": old.reason,
				"is_deducted": old.is_deducted,
				"total_recovered": flt(old.amount) if old.is_deducted else 0,
				"outstanding_amount": 0 if old.is_deducted else flt(old.amount),
			}
		)
		doc.flags.ignore_validate = True
		doc.flags.ignore_permissions = True
		doc.flags.ignore_mandatory = True
		doc.insert(ignore_permissions=True)
		_copy_meta(old, "Employee Advance")


def _copy_meta(old, doctype):
	"""Preserve submit state and audit fields after insert."""
	frappe.db.set_value(
		doctype,
		old.name,
		{
			"docstatus": old.docstatus,
			"creation": old.creation,
			"modified": old.modified,
			"owner": old.owner,
			"modified_by": old.modified_by,
		},
		update_modified=False,
	)
