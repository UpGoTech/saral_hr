# Copyright (c) 2026, sj and contributors
# For license information, please see license.txt

import calendar
from datetime import datetime

import frappe
from frappe.model.document import Document
from frappe.utils import flt, get_last_day, getdate


class EmployeeLoan(Document):
	def autoname(self):
		prefix = f"{self.employee}-Loan-"
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
		self.name = f"{prefix}{str(last_num + 1).zfill(4)}"

	def validate(self):
		self.validate_only_changed_rows()
		self.calculate_outstanding()
		self.validate_schedule_total()
		self.sync_tenure_from_schedule()

	def on_update_after_submit(self):
		self.validate_schedule_total()
		self.calculate_outstanding()
		self.sync_tenure_from_schedule()
		self.validate_only_changed_rows()

	def on_cancel(self):
		if not self.schedule:
			return
		blocked = []
		for row in self.schedule:
			if not row.month or not row.month.strip():
				continue
			slip = _get_submitted_slip_for_month(self.employee, row.month)
			if slip:
				blocked.append((row.month, slip))
		if blocked:
			lines = "".join(
				f"<li><b>{month}</b> &nbsp;→&nbsp; Salary Slip <b>{slip}</b></li>"
				for month, slip in blocked
			)
			frappe.throw(
				f"Cannot cancel this Loan because Salary Slips have already been "
				f"generated for the following months:<br><br>"
				f"<ul style='margin:8px 0 12px 16px;'>{lines}</ul>"
				f"Please <b>cancel the Salary Slips</b> listed above first, then cancel this loan.",
				title="Cannot Cancel — Salary Slips Exist",
			)
		for row in self.schedule:
			frappe.db.set_value(
				"Employee Loan Schedule",
				row.name,
				{"is_deducted": 0, "is_deferred": 0, "deferred_to": ""},
				update_modified=False,
			)

	def sync_tenure_from_schedule(self):
		if not self.schedule:
			return
		valid_rows = [row for row in self.schedule if row.month and row.month.strip()]
		count = len(valid_rows)
		if count and self.tenure_months != count:
			if self.name and frappe.db.exists("Employee Loan", self.name):
				frappe.db.set_value(
					"Employee Loan",
					self.name,
					"tenure_months",
					count,
					update_modified=False,
				)
			self.tenure_months = count

	def calculate_outstanding(self):
		salary_deducted = sum(
			flt(row.deduction_amount) for row in (self.schedule or []) if row.is_deducted
		)
		cash_recovered = sum(flt(row.amount) for row in (self.cash_recoveries or []))
		self.total_deducted = salary_deducted + cash_recovered
		self.outstanding_amount = flt(self.amount) - flt(self.total_deducted)

	def validate_schedule_total(self):
		if not self.schedule:
			return
		valid_rows = [row for row in self.schedule if row.month and row.month.strip()]
		if not valid_rows:
			return
		total = round(sum(flt(row.deduction_amount) for row in valid_rows), 2)
		loan_amount = round(flt(self.amount), 2)
		if total > loan_amount:
			frappe.throw(
				f"Installments total ₹{total}, but loan is only ₹{loan_amount}. "
				f"Reduce amounts so they match the loan.",
				title="Total Exceeds Loan",
			)
		elif abs(total - loan_amount) > 0.01:
			frappe.throw(
				f"Installments total ₹{total}, loan is ₹{loan_amount}. "
				f"Adjust amounts to match.",
				title="Total Mismatch",
			)

	def validate_only_changed_rows(self):
		if not self.employee:
			return
		for row in self.schedule or []:
			if not row.month or not row.is_deducted or not row.name:
				continue
			db_amount = frappe.db.get_value(
				"Employee Loan Schedule", row.name, "deduction_amount"
			)
			if db_amount is not None and abs(flt(db_amount) - flt(row.deduction_amount)) > 0.01:
				frappe.throw(
					f"Row <b>{row.idx}</b>: Cannot change deduction amount for "
					f"<b>{row.month}</b> — it is already deducted via Salary Slip. "
					f"Cancel the Salary Slip first.",
					title="Edit Not Allowed",
				)


@frappe.whitelist()
def get_submitted_slip_for_month(employee, month_name):
	return _get_submitted_slip_for_month(employee, month_name)


def _get_submitted_slip_for_month(employee, month_name):
	try:
		dt = datetime.strptime(month_name, "%B %Y")
		month_start = dt.strftime("%Y-%m-01")
		last_day = calendar.monthrange(dt.year, dt.month)[1]
		month_end = dt.strftime(f"%Y-%m-{last_day}")
	except Exception:
		return None

	return frappe.db.get_value(
		"Salary Slip",
		{
			"employee": employee,
			"docstatus": 1,
			"start_date": ["between", [month_start, month_end]],
		},
		"name",
	)
