# Copyright (c) 2026, sj and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, get_first_day, get_last_day, getdate

from saral_hr.saral_hr.page.mark_attendance.mark_attendance import (
	ensure_outside_tenure_absent,
)


def _uid() -> str:
	return frappe.generate_hash(length=6)


def _make_company() -> str:
	uid = _uid()
	doc = frappe.get_doc(
		{
			"doctype": "Company",
			"company": f"_Test MA Tenure {uid}",
			"abbr": f"T{uid}"[:8],
			"country": "India",
			"default_currency": "INR",
			"salary_calculation_based_on": "Exclude Weekly Offs (Working Days)",
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _make_employee() -> str:
	doc = frappe.get_doc(
		{
			"doctype": "Employee",
			"naming_series": "HR-EMP-",
			"first_name": f"TenureEmp{_uid()}",
			"gender": "Other",
			"date_of_birth": "1990-01-01",
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _ensure_category(name: str = "Staff"):
	if frappe.db.exists("Category", name):
		return name
	doc = frappe.get_doc({"doctype": "Category", "category": name, "has_subtype": 0})
	doc.insert(ignore_permissions=True)
	return doc.name


def _make_company_link(employee: str, company: str, joining, left=None):
	doc = frappe.get_doc(
		{
			"doctype": "Company Link",
			"employee": employee,
			"company": company,
			"category": _ensure_category(),
			"date_of_joining": getdate(joining),
			"left_date": getdate(left) if left else None,
			"is_active": 1,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


class TestMarkAttendanceOutsideTenure(FrappeTestCase):
	def test_ensure_marks_pre_joining_days_absent(self):
		company = _make_company()
		employee = _make_employee()
		# Mid-month join: days before joining should become Absent
		joining = getdate("2024-06-10")
		cl = _make_company_link(employee, company, joining)
		start = get_first_day(joining)
		end = get_last_day(joining)

		result = ensure_outside_tenure_absent(cl, str(start), str(end))
		self.assertGreater(result["created"], 0)

		pre_join = frappe.db.get_all(
			"Attendance",
			filters={
				"employee": cl,
				"attendance_date": ["between", [str(start), str(add_days(joining, -1))]],
				"docstatus": ["<", 2],
			},
			fields=["attendance_date", "status"],
		)
		self.assertTrue(pre_join)
		self.assertTrue(all(r.status == "Absent" for r in pre_join))

		# Joining day itself must not be auto-marked
		self.assertFalse(
			frappe.db.exists(
				"Attendance",
				{"employee": cl, "attendance_date": joining, "docstatus": ["<", 2]},
			)
		)

	def test_ensure_is_idempotent_and_skips_existing(self):
		company = _make_company()
		employee = _make_employee()
		joining = getdate("2024-03-05")
		cl = _make_company_link(employee, company, joining)
		start = get_first_day(joining)
		end = get_last_day(joining)

		first = ensure_outside_tenure_absent(cl, str(start), str(end))
		second = ensure_outside_tenure_absent(cl, str(start), str(end))
		self.assertGreater(first["created"], 0)
		self.assertEqual(second["created"], 0)

	def test_ensure_marks_days_after_left_date(self):
		company = _make_company()
		employee = _make_employee()
		joining = getdate("2024-01-01")
		left = getdate("2024-04-10")
		cl = _make_company_link(employee, company, joining, left=left)
		start = get_first_day(left)
		end = get_last_day(left)

		result = ensure_outside_tenure_absent(cl, str(start), str(end))
		self.assertGreater(result["created"], 0)

		after_left = frappe.db.get_all(
			"Attendance",
			filters={
				"employee": cl,
				"attendance_date": ["between", [str(add_days(left, 1)), str(end)]],
				"docstatus": ["<", 2],
			},
			fields=["status"],
		)
		self.assertTrue(after_left)
		self.assertTrue(all(r.status == "Absent" for r in after_left))
