# Copyright (c) 2026, sj and contributors
# For license information, please see license.txt

import json

import frappe
from frappe.utils import flt

from saral_hr.saral_hr.doctype.employee_loan.employee_loan import month_sort_key, start_month_label

MONTHS = [
	"January",
	"February",
	"March",
	"April",
	"May",
	"June",
	"July",
	"August",
	"September",
	"October",
	"November",
	"December",
]


def _month_label(month, year):
	return f"{month} {year}"


@frappe.whitelist()
def get_dues(company, month, year, employee=None):
	if not company or not month or not year:
		frappe.throw("Company, month and year are required.")
	label = _month_label(month, year)
	filters = {"company": company, "month": label}
	if employee:
		filters["employee"] = employee
	rows = frappe.get_all(
		"Employee Loan Due",
		filters=filters,
		fields=[
			"name",
			"employee",
			"loan",
			"company",
			"month",
			"amount",
			"status",
			"salary_slip",
			"remarks",
		],
		order_by="employee asc, loan asc",
	)
	for row in rows:
		loan = frappe.db.get_value(
			"Employee Loan",
			row.loan,
			["full_name", "outstanding_amount", "expected_emi", "status"],
			as_dict=True,
		)
		row["full_name"] = loan.full_name if loan else ""
		row["outstanding_amount"] = loan.outstanding_amount if loan else 0
		row["expected_emi"] = loan.expected_emi if loan else 0
		row["loan_status"] = loan.status if loan else ""
		row["locked"] = 1 if row.salary_slip else 0
	return rows


@frappe.whitelist()
def generate_dues(company, month, year, employee=None):
	if not company or not month or not year:
		frappe.throw("Company, month and year are required.")
	label = _month_label(month, year)
	target_key = month_sort_key(label)

	filters = {"docstatus": 1, "status": "Active", "company": company}
	if employee:
		filters["employee"] = employee

	created = 0
	skipped = 0
	loans = frappe.get_all(
		"Employee Loan",
		filters=filters,
		fields=[
			"name",
			"employee",
			"company",
			"expected_emi",
			"outstanding_amount",
			"start_month",
			"start_year",
		],
	)
	for loan in loans:
		start_label = start_month_label(loan.start_month, loan.start_year)
		if month_sort_key(start_label) > target_key:
			skipped += 1
			continue
		if flt(loan.outstanding_amount) <= 0:
			skipped += 1
			continue
		if frappe.db.exists("Employee Loan Due", {"loan": loan.name, "month": label}):
			skipped += 1
			continue
		amount = min(flt(loan.expected_emi), flt(loan.outstanding_amount))
		doc = frappe.get_doc(
			{
				"doctype": "Employee Loan Due",
				"employee": loan.employee,
				"loan": loan.name,
				"company": loan.company or company,
				"month": label,
				"year": int(year),
				"amount": amount,
				"status": "Skipped" if amount == 0 else "Pending",
			}
		)
		try:
			doc.insert(ignore_permissions=True)
			created += 1
		except (frappe.UniqueValidationError, frappe.DuplicateEntryError):
			skipped += 1
		except frappe.ValidationError as e:
			# Concurrent generate can hit validate unique before commit
			if "already exists" in str(e).lower():
				skipped += 1
			else:
				raise

	return {"created": created, "skipped": skipped, "month": label}


@frappe.whitelist()
def save_dues(rows):
	if isinstance(rows, str):
		rows = json.loads(rows)
	updated = 0
	for row in rows or []:
		name = row.get("name")
		if not name:
			# new manual row
			loan = row.get("loan")
			month = row.get("month")
			if not loan or not month:
				continue
			if frappe.db.exists("Employee Loan Due", {"loan": loan, "month": month}):
				frappe.throw(f"Due already exists for {loan} / {month}.")
			loan_doc = frappe.get_doc("Employee Loan", loan)
			doc = frappe.get_doc(
				{
					"doctype": "Employee Loan Due",
					"employee": loan_doc.employee,
					"loan": loan,
					"company": loan_doc.company,
					"month": month,
					"year": row.get("year"),
					"amount": flt(row.get("amount")),
					"remarks": row.get("remarks") or "",
				}
			)
			doc.insert(ignore_permissions=True)
			updated += 1
			continue

		doc = frappe.get_doc("Employee Loan Due", name)
		if doc.salary_slip and frappe.db.get_value("Salary Slip", doc.salary_slip, "docstatus") == 1:
			# locked — skip silently or throw
			if abs(flt(doc.amount) - flt(row.get("amount"))) > 0.01:
				frappe.throw(f"Cannot change locked due {doc.loan} ({doc.month}).")
			continue
		doc.amount = flt(row.get("amount"))
		doc.remarks = row.get("remarks") or ""
		doc.save(ignore_permissions=True)
		updated += 1
	return {"updated": updated}
