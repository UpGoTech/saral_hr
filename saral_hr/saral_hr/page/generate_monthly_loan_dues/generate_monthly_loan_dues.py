# Copyright (c) 2026, sj and contributors
# For license information, please see license.txt

import json

import frappe
from frappe.utils import flt, get_last_day, getdate

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


def _period_dates(month, year):
	month_num = MONTHS.index(month) + 1
	start = getdate(f"{int(year)}-{month_num:02d}-01")
	return start, get_last_day(start)


def _period_locked(company, month, year):
	"""True when any submitted salary slip exists for this company in the month."""
	start, end = _period_dates(month, year)
	return bool(
		frappe.db.exists(
			"Salary Slip",
			{
				"company": company,
				"docstatus": 1,
				"start_date": ["between", [start, end]],
			},
		)
	)


def _list_dues(company, month_label, employee=None):
	filters = {"company": company, "month": month_label}
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


def _create_missing_dues(company, month, year, employee=None):
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
			if "already exists" in str(e).lower():
				skipped += 1
			else:
				raise

	return created, skipped


@frappe.whitelist()
def open_period(company, month, year, employee=None):
	"""Single entry: load existing dues; create any missing when period is unlocked."""
	if not company or not month or not year:
		frappe.throw("Company, month and year are required.")
	if month not in MONTHS:
		frappe.throw(f"Invalid month: {month}")

	label = _month_label(month, year)
	locked = _period_locked(company, month, year)
	created = 0
	skipped = 0
	if not locked:
		created, skipped = _create_missing_dues(company, month, year, employee=employee)

	rows = _list_dues(company, label, employee=employee)
	if locked:
		for row in rows:
			row["locked"] = 1

	return {
		"rows": rows,
		"created": created,
		"skipped": skipped,
		"month": label,
		"period_locked": 1 if locked else 0,
	}


@frappe.whitelist()
def get_dues(company, month, year, employee=None):
	"""Backward-compatible read-only list (no create)."""
	if not company or not month or not year:
		frappe.throw("Company, month and year are required.")
	label = _month_label(month, year)
	locked = _period_locked(company, month, year)
	rows = _list_dues(company, label, employee=employee)
	if locked:
		for row in rows:
			row["locked"] = 1
	return rows


@frappe.whitelist()
def generate_dues(company, month, year, employee=None):
	"""Deprecated: use open_period. Kept for any old callers."""
	if _period_locked(company, month, year):
		return {"created": 0, "skipped": 0, "month": _month_label(month, year), "period_locked": 1}
	created, skipped = _create_missing_dues(company, month, year, employee=employee)
	return {"created": created, "skipped": skipped, "month": _month_label(month, year), "period_locked": 0}


@frappe.whitelist()
def save_dues(rows, company=None, month=None, year=None):
	if isinstance(rows, str):
		rows = json.loads(rows)

	if company and month and year and _period_locked(company, month, year):
		frappe.throw(
			f"Salary slips already exist for {_month_label(month, year)} — this period is locked."
		)

	updated = 0
	for row in rows or []:
		name = row.get("name")
		if not name:
			loan = row.get("loan")
			row_month = row.get("month")
			if not loan or not row_month:
				continue
			# Derive company/year from loan if period args missing
			if row_month and " " in row_month:
				parts = row_month.rsplit(" ", 1)
				if len(parts) == 2 and _period_locked(
					frappe.db.get_value("Employee Loan", loan, "company"),
					parts[0],
					parts[1],
				):
					frappe.throw(f"Salary slips already exist for {row_month} — this period is locked.")
			if frappe.db.exists("Employee Loan Due", {"loan": loan, "month": row_month}):
				frappe.throw(f"Due already exists for {loan} / {row_month}.")
			loan_doc = frappe.get_doc("Employee Loan", loan)
			doc = frappe.get_doc(
				{
					"doctype": "Employee Loan Due",
					"employee": loan_doc.employee,
					"loan": loan,
					"company": loan_doc.company,
					"month": row_month,
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
			if abs(flt(doc.amount) - flt(row.get("amount"))) > 0.01:
				frappe.throw(f"Cannot change locked due {doc.loan} ({doc.month}).")
			continue
		doc.amount = flt(row.get("amount"))
		doc.remarks = row.get("remarks") or ""
		doc.save(ignore_permissions=True)
		updated += 1
	return {"updated": updated}


@frappe.whitelist()
def search_loans_for_due(company, month=None, year=None, employee=None):
	"""Active loans for Add Row picker. No month/due eligibility filtering."""
	if not company:
		frappe.throw("Company is required.")
	filters = {"docstatus": 1, "status": "Active", "company": company}
	if employee:
		filters["employee"] = employee

	loans = frappe.get_all(
		"Employee Loan",
		filters=filters,
		fields=[
			"name",
			"employee",
			"full_name",
			"amount",
			"expected_emi",
			"outstanding_amount",
			"start_month",
			"start_year",
			"loan_date",
			"reason",
			"proposed_tenure_months",
		],
		order_by="employee asc, name asc",
	)
	rows = []
	for loan in loans:
		suggested = min(flt(loan.expected_emi), flt(loan.outstanding_amount)) if flt(loan.outstanding_amount) > 0 else flt(loan.expected_emi)
		reason = (loan.reason or "").strip().replace("\n", " ")
		if len(reason) > 80:
			reason = reason[:77] + "…"
		rows.append(
			{
				"name": loan.name,
				"employee": loan.employee,
				"full_name": loan.full_name,
				"amount": flt(loan.amount),
				"expected_emi": flt(loan.expected_emi),
				"outstanding_amount": flt(loan.outstanding_amount),
				"suggested_amount": suggested,
				"start": f"{loan.start_month} {loan.start_year}",
				"loan_date": loan.loan_date,
				"reason": reason,
				"proposed_tenure_months": loan.proposed_tenure_months,
				"label": (
					f"{loan.employee} · {loan.full_name or ''} · {loan.name} · "
					f"Outst {flt(loan.outstanding_amount):,.0f} · EMI {flt(loan.expected_emi):,.0f}"
				),
			}
		)
	return rows
