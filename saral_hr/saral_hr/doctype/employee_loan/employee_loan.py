# Copyright (c) 2026, sj and contributors
# For license information, please see license.txt

import math

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class EmployeeLoan(Document):
	def autoname(self):
		prefix = f"{_employee_loan_prefix(self.employee)}-"
		# prefix is like "0002-LN-"
		last = frappe.db.sql(
			"""
			SELECT name FROM `tabEmployee Loan`
			WHERE name LIKE %s
			ORDER BY CAST(SUBSTRING_INDEX(name, '-', -1) AS UNSIGNED) DESC
			LIMIT 1
			""",
			(prefix + "%",),
			as_dict=True,
		)
		last_num = 0
		if last:
			try:
				last_num = int(last[0]["name"].split("-")[-1])
			except (ValueError, IndexError):
				last_num = 0
		self.name = f"{prefix}{last_num + 1}"


def _employee_loan_prefix(employee):
	"""Last 4 digits of employee id → '{last4}-LN' (e.g. HR-EMP-00002 → 0002-LN)."""
	digits = "".join(ch for ch in (employee or "") if ch.isdigit())
	last4 = (digits[-4:] if digits else "0000").zfill(4)
	return f"{last4}-LN"

	def validate(self):
		if flt(self.amount) <= 0:
			frappe.throw("Loan amount must be greater than zero.")
		if flt(self.expected_emi) <= 0:
			frappe.throw("Expected EMI must be greater than zero.")
		if not self.proposed_tenure_months or self.proposed_tenure_months < 1:
			frappe.throw("Proposed tenure must be at least 1 month.")
		self.validate_prepayments()
		self.calculate_outstanding()

	def on_update_after_submit(self):
		self.validate_prepayments()
		self.calculate_outstanding()
		frappe.db.set_value(
			"Employee Loan",
			self.name,
			{
				"total_recovered": self.total_recovered,
				"outstanding_amount": self.outstanding_amount,
				"status": self.status,
				"expected_months_remaining": self.expected_months_remaining or 0,
			},
			update_modified=False,
		)

	def validate_prepayments(self):
		total_prepay = 0.0
		for row in self.prepayments or []:
			if flt(row.amount) <= 0:
				frappe.throw(f"Prepayment row {row.idx}: amount must be greater than zero.")
			if not row.prepayment_date:
				frappe.throw(f"Prepayment row {row.idx}: date is required.")
			total_prepay += flt(row.amount)
		salary_recovered = _salary_recovered_for_loan(self.name)
		if total_prepay + salary_recovered - flt(self.amount) > 0.01:
			frappe.throw(
				f"Prepayments + salary recoveries (₹{flt(total_prepay + salary_recovered):,.2f}) "
				f"cannot exceed loan amount (₹{flt(self.amount):,.2f})."
			)

	def calculate_outstanding(self):
		salary_recovered = _salary_recovered_for_loan(self.name)
		prepay = sum(flt(r.amount) for r in (self.prepayments or []))
		self.total_recovered = flt(salary_recovered + prepay, 2)
		self.outstanding_amount = max(flt(self.amount) - flt(self.total_recovered), 0)
		self.status = "Closed" if self.outstanding_amount <= 0.01 else "Active"
		emi = flt(self.expected_emi)
		if self.outstanding_amount <= 0.01 or emi <= 0:
			self.expected_months_remaining = 0
		else:
			self.expected_months_remaining = int(math.ceil(self.outstanding_amount / emi))


def _salary_recovered_for_loan(loan_name):
	if not loan_name or not frappe.db.exists("DocType", "Employee Loan Due"):
		return 0.0
	return flt(
		frappe.db.sql(
			"""
			SELECT COALESCE(SUM(amount), 0)
			FROM `tabEmployee Loan Due`
			WHERE loan = %s AND IFNULL(salary_slip, '') != ''
			""",
			loan_name,
		)[0][0]
	)


def start_month_label(start_month, start_year):
	return f"{start_month} {start_year}".strip()


def month_sort_key(month_label):
	"""Return (year, month_num) for comparing 'January 2026' labels."""
	try:
		parts = month_label.strip().split()
		months = [
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
		return (int(parts[1]), months.index(parts[0]) + 1)
	except Exception:
		return (0, 0)
