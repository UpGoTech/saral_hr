# Copyright (c) 2026, sj and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import (
	getdate,
	nowdate,
	format_date,
)


class DuplicateAttendanceError(frappe.ValidationError):
	pass


# Valid statuses for each half of a half-day record
VALID_HALF_STATUSES = {
	"Present", "On Tour", "Earned Comp Off",
	"Absent", "Earned Leave", "Casual Leave", "Comp Off", "LWP",
}

# Statuses that count as "working / present" — two of these in both halves
# means it should just be a full Present/On Tour/etc, not Half Day
PRESENT_LIKE = {"Present", "On Tour", "Earned Comp Off"}


class Attendance(Document):

	def validate(self):
		self.validate_attendance_date()
		self.validate_duplicate_record()
		self.validate_employee_active()
		self.validate_half_day_fields()
		self.clear_half_day_fields_if_not_half_day()

	def validate_attendance_date(self):
		if not self.employee or not self.attendance_date:
			return

		FUTURE_ALLOWED = {
			"On Leave",
			"Holiday",
			"Weekly Off",
			"LWP",
			"Earned Leave",
			"Casual Leave",
			"Comp Off",
			"On Tour",
			"Earned Comp Off",
		}

		date_of_joining = frappe.db.get_value(
			"Company Link",
			self.employee,
			"date_of_joining"
		)

		if (
			self.status not in FUTURE_ALLOWED
			and getdate(self.attendance_date) > getdate(nowdate())
		):
			frappe.throw(
				_("Attendance cannot be marked for future dates: {0}").format(
					frappe.bold(format_date(self.attendance_date))
				)
			)

		if date_of_joining and getdate(self.attendance_date) < getdate(date_of_joining):
			frappe.throw(
				_(
					"Attendance date {0} cannot be before employee's joining date {1}"
				).format(
					frappe.bold(format_date(self.attendance_date)),
					frappe.bold(format_date(date_of_joining)),
				)
			)

	def validate_duplicate_record(self):
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

	def validate_employee_active(self):
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

	def validate_half_day_fields(self):
		"""
		When status is Half Day:
		- At least one half must be filled
		- Both halves cannot be the same "present-like" status
		  (e.g. Present + Present should just be Present, not Half Day)
		- Both halves cannot be the same "absent-like" status
		  (e.g. Absent + Absent should just be Absent)
		- If filled, values must be valid
		"""
		if self.status != "Half Day":
			return

		fh = (self.custom_first_half or "").strip()
		sh = (self.custom_second_half or "").strip()

		if not fh and not sh:
			# Allow saving without halves — mark-attendance page may save in two steps
			return

		if fh and fh not in VALID_HALF_STATUSES:
			frappe.throw(
				_("Invalid First Half status: {0}").format(frappe.bold(fh))
			)

		if sh and sh not in VALID_HALF_STATUSES:
			frappe.throw(
				_("Invalid Second Half status: {0}").format(frappe.bold(sh))
			)

		# Warn if both halves are identical — it's technically valid (e.g., Absent + Absent
		# might happen from biometric) but flag it as a note
		if fh and sh and fh == sh:
			frappe.msgprint(
				_("Both halves are marked as <b>{0}</b>. Consider using a full-day status instead.").format(fh),
				title=_("Half Day Notice"),
				indicator="orange",
				alert=True
			)

	def clear_half_day_fields_if_not_half_day(self):
		"""Clear half-day fields when status is not Half Day."""
		if self.status != "Half Day":
			self.custom_first_half  = ""
			self.custom_second_half = ""