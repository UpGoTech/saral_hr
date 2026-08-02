# Copyright (c) 2026, sj and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, get_first_day, get_last_day, getdate

from saral_hr.saral_hr.doctype.salary_slip.salary_slip import get_attendance_and_days


def _uid() -> str:
	return frappe.generate_hash(length=6)


def _ensure_category(name: str = "Staff"):
	if frappe.db.exists("Category", name):
		return name
	doc = frappe.get_doc({"doctype": "Category", "category": name, "has_subtype": 0})
	doc.insert(ignore_permissions=True)
	return doc.name


def _make_company() -> str:
	uid = _uid()
	doc = frappe.get_doc(
		{
			"doctype": "Company",
			"company": f"_Test SS Days {uid}",
			"abbr": f"S{uid}"[:8],
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
			"first_name": f"SSDays{_uid()}",
			"gender": "Other",
			"date_of_birth": "1990-01-01",
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _make_company_link(employee: str, company: str, joining, weekly_off="Sunday"):
	doc = frappe.get_doc(
		{
			"doctype": "Company Link",
			"employee": employee,
			"company": company,
			"category": _ensure_category(),
			"date_of_joining": getdate(joining),
			"weekly_off": weekly_off,
			"is_active": 1,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _mark(employee: str, day, status: str):
	doc = frappe.get_doc(
		{
			"doctype": "Attendance",
			"employee": employee,
			"attendance_date": getdate(day),
			"status": status,
		}
	)
	doc.flags.ignore_validate = True
	doc.flags.ignore_mandatory = True
	doc.insert(ignore_permissions=True)


class TestSalarySlipWorkingDays(FrappeTestCase):
	def test_mid_month_join_uses_full_month_working_days(self):
		"""Working days must be the full month, not joining→month-end."""
		company = _make_company()
		employee = _make_employee()
		joining = getdate("2024-06-10")
		cl = _make_company_link(employee, company, joining, weekly_off="")
		start = get_first_day(joining)
		end = get_last_day(joining)
		month_days = (end - start).days + 1

		# Pre-join Absents + Present from joining onward
		d = start
		while d < joining:
			_mark(cl, d, "Absent")
			d = add_days(d, 1)
		d = joining
		while d <= end:
			_mark(cl, d, "Present")
			d = add_days(d, 1)

		att = get_attendance_and_days(cl, str(start), "Exclude Weekly Offs (Working Days)")

		self.assertEqual(att["total_days"], month_days)
		self.assertEqual(att["working_days"], float(month_days))
		# Must NOT equal only the post-joining slice
		post_join_days = (end - joining).days + 1
		self.assertNotEqual(att["working_days"], float(post_join_days))
		self.assertEqual(att["present_days"], float(post_join_days))
		self.assertEqual(att["absent_days"], float(month_days - post_join_days))
		self.assertEqual(att["payment_days"], float(post_join_days))
