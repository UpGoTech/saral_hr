# Copyright (c) 2026, sj and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt

from saral_hr.saral_hr.doctype.employee_loan.employee_loan import month_sort_key


class EmployeeLoanDue(Document):
	def validate(self):
		if not self.loan:
			frappe.throw("Loan is required.")
		loan = frappe.get_doc("Employee Loan", self.loan)
		if self.employee and self.employee != loan.employee:
			frappe.throw("Employee must match the loan employee.")
		self.employee = loan.employee
		self.company = loan.company
		if self.month and " " in self.month:
			try:
				self.year = int(self.month.split()[-1])
			except ValueError:
				pass

		if flt(self.amount) < 0:
			frappe.throw("Due amount cannot be negative.")

		if self.salary_slip and frappe.db.get_value("Salary Slip", self.salary_slip, "docstatus") == 1:
			if not self.is_new():
				prev = frappe.db.get_value(
					"Employee Loan Due",
					self.name,
					["amount", "employee", "loan", "month"],
					as_dict=True,
				)
				if prev and (
					abs(flt(prev.amount) - flt(self.amount)) > 0.01
					or prev.employee != self.employee
					or prev.loan != self.loan
					or prev.month != self.month
				):
					frappe.throw(
						f"Cannot edit due for {self.month} — linked to submitted Salary Slip {self.salary_slip}."
					)

		outstanding = flt(loan.outstanding_amount)
		# When editing a pending due, outstanding already excludes other dues only after salary;
		# allow amount up to outstanding (+ this due if already deducted — not the case here).
		if not self.salary_slip and flt(self.amount) - outstanding > 0.01:
			frappe.throw(
				f"Due amount ₹{flt(self.amount):,.2f} exceeds loan outstanding ₹{outstanding:,.2f}."
			)

		if flt(self.amount) == 0:
			self.status = "Skipped"
		elif self.salary_slip:
			self.status = "Deducted"
		else:
			self.status = "Pending"

		# unique loan+month
		exists = frappe.db.exists(
			"Employee Loan Due",
			{"loan": self.loan, "month": self.month, "name": ["!=", self.name or ""]},
		)
		if exists:
			frappe.throw(f"A due already exists for {self.loan} in {self.month}.")

		loan_start = f"{loan.start_month} {loan.start_year}"
		if month_sort_key(self.month) < month_sort_key(loan_start):
			frappe.throw(f"Due month {self.month} is before loan start {loan_start}.")
