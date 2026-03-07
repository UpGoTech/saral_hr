# Copyright (c) 2026, sj and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import (
	add_days,
	cint,
	getdate,
	nowdate,
	format_date,
)


class DuplicateAttendanceError(frappe.ValidationError):
	pass


class Attendance(Document):

	def validate(self):
		self.validate_attendance_date()
		self.validate_duplicate_record()
		self.validate_employee_active()

	# ------------------------------------------------------------------
	# Attendance Date Validation
	# ------------------------------------------------------------------
	def validate_attendance_date(self):
		"""
		Validate that attendance date is:
		- Not in the future (except statuses that are pre-known/leave types)
		- Not before employee joining date
		"""

		if not self.employee or not self.attendance_date:
			return

		# Statuses allowed on future dates (leaves, offs, tours planned ahead)
		FUTURE_ALLOWED = {
			"On Leave",
			"Holiday",
			"Weekly Off",
			"LWP",
			"Earned Leave",
			"Casual Leave",
			"Comp Off",
			"On Tour",
		}

		date_of_joining = frappe.db.get_value(
			"Company Link",
			self.employee,
			"date_of_joining"
		)

		# Future date check
		if (
			self.status not in FUTURE_ALLOWED
			and getdate(self.attendance_date) > getdate(nowdate())
		):
			frappe.throw(
				_("Attendance cannot be marked for future dates: {0}").format(
					frappe.bold(format_date(self.attendance_date))
				)
			)

		# Before joining date check
		if date_of_joining and getdate(self.attendance_date) < getdate(date_of_joining):
			frappe.throw(
				_(
					"Attendance date {0} cannot be before employee's joining date {1}"
				).format(
					frappe.bold(format_date(self.attendance_date)),
					frappe.bold(format_date(date_of_joining)),
				)
			)

	# ------------------------------------------------------------------
	# Duplicate Attendance Validation
	# ------------------------------------------------------------------
	def validate_duplicate_record(self):
		"""
		Ensure only one attendance record per employee per date
		"""

		if not self.employee or not self.attendance_date:
			return

		duplicate = frappe.db.exists(
			"Attendance",
			{
				"employee": self.employee,
				"attendance_date": self.attendance_date,
				"docstatus": ["<", 2],
				"name": ["!=", self.name],
			},
		)

		if duplicate:
			frappe.throw(
				_(
					"Attendance for employee {0} is already marked for {1}"
				).format(
					frappe.bold(self.employee),
					frappe.bold(format_date(self.attendance_date)),
				),
				title=_("Duplicate Attendance"),
				exc=DuplicateAttendanceError,
			)

	# ------------------------------------------------------------------
	# Active Employee Validation (Company Link)
	# ------------------------------------------------------------------
	def validate_employee_active(self):
		"""
		Ensure attendance is marked only for active Company Link records
		"""

		if not self.employee:
			return

		is_active = frappe.db.get_value(
			"Company Link",
			self.employee,
			"is_active"
		)

		if not is_active:
			frappe.throw(
				_("Cannot mark attendance for an inactive employee: {0}").format(
					frappe.bold(self.employee)
				)
			)