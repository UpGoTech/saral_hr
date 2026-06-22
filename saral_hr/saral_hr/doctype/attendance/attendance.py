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
from saral_hr.utils.holiday_utils import get_holiday_list_for_date   # ✅ ADD


class DuplicateAttendanceError(frappe.ValidationError):
	pass


VALID_HALF_STATUSES = {
	"Present", "On Tour", "Earned Comp Off",
	"Absent", "Earned Leave", "Casual Leave", "Comp Off", "LWP",
}

PRESENT_LIKE = {"Present", "On Tour", "Earned Comp Off"}

ALLOCATION_REQUIRED_STATUSES = {"Earned Leave", "Casual Leave", "Comp Off"}


class Attendance(Document):

	def validate(self):
		self.validate_attendance_date()
		self.validate_duplicate_record()
		self.validate_employee_active()
		self.check_and_set_holiday()           # ✅ ADD
		self.validate_half_day_fields()
		self.clear_half_day_fields_if_not_half_day()
		self.validate_leave_allocation()

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
		if self.status != "Half Day":
			return

		fh = (self.custom_first_half or "").strip()
		sh = (self.custom_second_half or "").strip()

		if not fh and not sh:
			return

		if fh and fh not in VALID_HALF_STATUSES:
			frappe.throw(
				_("Invalid First Half status: {0}").format(frappe.bold(fh))
			)

		if sh and sh not in VALID_HALF_STATUSES:
			frappe.throw(
				_("Invalid Second Half status: {0}").format(frappe.bold(sh))
			)

		if fh and sh and fh == sh:
			frappe.msgprint(
				_("Both halves are marked as <b>{0}</b>. Consider using a full-day status instead.").format(fh),
				title=_("Half Day Notice"),
				indicator="orange",
				alert=True
			)

	def clear_half_day_fields_if_not_half_day(self):
		if self.status != "Half Day":
			self.custom_first_half  = ""
			self.custom_second_half = ""

	def validate_leave_allocation(self):
		if not self.employee or not self.attendance_date:
			return

		statuses_used = set()

		if self.status in ALLOCATION_REQUIRED_STATUSES:
			statuses_used.add(self.status)

		if self.status == "Half Day":
			fh = (self.custom_first_half  or "").strip()
			sh = (self.custom_second_half or "").strip()
			if fh in ALLOCATION_REQUIRED_STATUSES:
				statuses_used.add(fh)
			if sh in ALLOCATION_REQUIRED_STATUSES:
				statuses_used.add(sh)

		if not statuses_used:
			return

		has_allocation = frappe.db.exists(
			"Leave Allocation",
			{
				"employee":  self.employee,
				"from_date": ["<=", self.attendance_date],
				"to_date":   [">=", self.attendance_date],
				"docstatus": ["<", 2],
			}
		)

		if not has_allocation:
			frappe.throw(
				_(
					"Cannot mark {0} for {1} on {2}: no active Leave Allocation found "
					"covering this date. Please create a Leave Allocation first."
				).format(
					frappe.bold(", ".join(sorted(statuses_used))),
					frappe.bold(self.employee),
					frappe.bold(format_date(self.attendance_date)),
				),
				title=_("No Leave Allocation")
			)

	# ✅ NAYA METHOD — class ke end mein
	def check_and_set_holiday(self):
		if not self.employee or not self.attendance_date:
			return

		company = frappe.db.get_value("Company Link", self.employee, "company")
		if not company:
			return

		holiday_list_name = get_holiday_list_for_date(self.attendance_date, company)
		if not holiday_list_name:
			return

		self.holiday = holiday_list_name

		holiday_list = frappe.get_doc("Holiday List", holiday_list_name)

		for h in holiday_list.holidays:
			if getdate(h.holiday_date) == getdate(self.attendance_date):
				self.status = "Holiday"
				frappe.msgprint(
					_("Date {0} is a Holiday: <b>{1}</b>. Status automatically set to Holiday.").format(
						frappe.bold(self.attendance_date),
						h.description or holiday_list_name
					),
					indicator="orange",
					alert=True
				)
				return