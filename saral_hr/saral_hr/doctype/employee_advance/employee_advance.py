# Copyright (c) 2026, sj and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt, get_last_day, getdate


class EmployeeAdvance(Document):
	def autoname(self):
		prefix = f"{self.employee}-Advance-"
		last = frappe.db.sql(
			"""
			SELECT name FROM `tabEmployee Advance`
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
		self.calculate_outstanding()
		self.validate_against_submitted_slip()

	def on_update_after_submit(self):
		self.calculate_outstanding()
		self.validate_against_submitted_slip()

	def on_cancel(self):
		if self.is_deducted and self.date:
			d = getdate(self.date)
			month_start = d.strftime("%Y-%m-01")
			month_end = str(get_last_day(d))
			slip = frappe.db.get_value(
				"Salary Slip",
				{
					"employee": self.employee,
					"docstatus": 1,
					"start_date": ["between", [month_start, month_end]],
				},
				"name",
			)
			if slip:
				frappe.throw(
					f"Cannot cancel this Advance — Salary Slip <b>{slip}</b> is already submitted.<br><br>"
					f"Please <b>cancel Salary Slip {slip}</b> first, then cancel this advance.",
					title="Cancel Not Allowed",
				)
		frappe.db.set_value(
			"Employee Advance",
			self.name,
			"is_deducted",
			0,
			update_modified=False,
		)

	def calculate_outstanding(self):
		cash_recovered = sum(flt(row.amount) for row in (self.cash_recoveries or []))
		if self.is_deducted:
			# One-shot salary cleared remaining principal; treat as fully recovered.
			self.total_recovered = flt(self.amount)
			self.outstanding_amount = 0
		else:
			self.total_recovered = cash_recovered
			self.outstanding_amount = max(flt(self.amount) - cash_recovered, 0)

	def validate_against_submitted_slip(self):
		pass
