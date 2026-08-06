# Copyright (c) 2026, sj and Contributors
# See license.txt

import calendar
from datetime import date, timedelta

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import get_last_day, getdate

from saral_hr.saral_hr.page.attendance_dashboard.attendance_dashboard import (
	_past_month_nums,
	get_yearly_employee_list,
	get_yearly_summary,
)


def _uid() -> str:
	return frappe.generate_hash(length=6)


def _make_company() -> str:
	uid = _uid()
	doc = frappe.get_doc(
		{
			"doctype": "Company",
			"company": f"_Test AD Yearly {uid}",
			"abbr": f"Y{uid}"[:8],
			"country": "India",
			"default_currency": "INR",
			"salary_calculation_based_on": "Exclude Weekly Offs (Working Days)",
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _make_employee(first_name: str | None = None) -> str:
	doc = frappe.get_doc(
		{
			"doctype": "Employee",
			"naming_series": "HR-EMP-",
			"first_name": first_name or f"YrEmp{_uid()}",
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


def _ensure_department(name: str) -> str:
	if frappe.db.exists("Department", name):
		return name
	doc = frappe.get_doc({"doctype": "Department", "department": name})
	doc.insert(ignore_permissions=True)
	return doc.name


def _make_company_link(employee, company, joining, left=None, department=None):
	doc = frappe.get_doc(
		{
			"doctype": "Company Link",
			"employee": employee,
			"company": company,
			"category": _ensure_category(),
			"date_of_joining": getdate(joining),
			"left_date": getdate(left) if left else None,
			"is_active": 1,
			"department": department,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _mark_days(company, cl, start, end, status="Present"):
	"""Insert attendance for each day in [start, end] inclusive."""
	cur = getdate(start)
	end = getdate(end)
	while cur <= end:
		doc = frappe.get_doc(
			{
				"doctype": "Attendance",
				"naming_series": "HR-ATT-.YYYY.-",
				"employee": cl,
				"company": company,
				"attendance_date": cur,
				"status": status,
			}
		)
		doc.flags.ignore_validate = True
		doc.flags.ignore_mandatory = True
		doc.insert(ignore_permissions=True)
		cur += timedelta(days=1)


def _month_row(summary, month_name):
	for m in summary.get("months") or []:
		if m["month"] == month_name:
			return m
	return None


class TestAttendanceDashboardYearly(FrappeTestCase):
	def test_past_month_nums_excludes_current_and_future(self):
		today = date.today()
		self.assertEqual(_past_month_nums(today.year + 1), [])
		self.assertEqual(_past_month_nums(today.year - 1), list(range(1, 13)))
		self.assertEqual(_past_month_nums(today.year), list(range(1, today.month)))

	def test_opening_jan_uses_dec_prior_year_closing(self):
		company = _make_company()
		# On rolls through Dec 2023 → Opening Jan 2024
		cl_old = _make_company_link(_make_employee(), company, "2023-01-01")
		# Joined Jan 2024
		cl_new = _make_company_link(_make_employee(), company, "2024-01-15")
		# Left Dec 2023 (not in Jan opening)
		cl_left = _make_company_link(
			_make_employee(), company, "2023-01-01", left="2023-12-20"
		)

		summary = get_yearly_summary(company, 2024)
		jan = _month_row(summary, "January")
		self.assertIsNotNone(jan)
		self.assertEqual(jan["opening"], 1)  # only cl_old
		self.assertEqual(jan["joined"], 1)  # cl_new
		self.assertEqual(jan["left"], 0)
		self.assertEqual(jan["closing"], 2)  # opening + joined - left
		self.assertEqual(jan["total_strength"], 2)  # opening ∪ joined
		self.assertEqual(jan["marked"] + jan["not_marked"], jan["total_strength"])

	def test_one_missing_day_is_not_marked_absent_full_month_is_marked(self):
		company = _make_company()
		cl_full = _make_company_link(_make_employee(), company, "2023-01-01")
		cl_gap = _make_company_link(_make_employee(), company, "2023-01-01")

		# Full February 2024 for cl_full — all Absent still counts as marked
		_mark_days(company, cl_full, "2024-02-01", "2024-02-29", status="Absent")
		# Missing one day for cl_gap
		_mark_days(company, cl_gap, "2024-02-01", "2024-02-28", status="Present")

		summary = get_yearly_summary(company, 2024)
		feb = _month_row(summary, "February")
		self.assertEqual(feb["total_strength"], 2)
		self.assertEqual(feb["marked"], 1)
		self.assertEqual(feb["not_marked"], 1)

		not_marked = get_yearly_employee_list(
			company, 2024, "February", "not_marked"
		)["employees"]
		self.assertEqual(len(not_marked), 1)
		self.assertEqual(not_marked[0]["employee"], cl_gap)
		self.assertEqual(not_marked[0]["missing_count"], 1)
		self.assertEqual(not_marked[0]["missing_dates"], ["2024-02-29"])

		marked = get_yearly_employee_list(company, 2024, "February", "marked")[
			"employees"
		]
		self.assertEqual(len(marked), 1)
		self.assertEqual(marked[0]["employee"], cl_full)

	def test_department_filter_scopes_counts(self):
		company = _make_company()
		dept_a = _ensure_department(f"_Test Dept A {_uid()}")
		dept_b = _ensure_department(f"_Test Dept B {_uid()}")
		_make_company_link(
			_make_employee(), company, "2023-01-01", department=dept_a
		)
		_make_company_link(
			_make_employee(), company, "2023-01-01", department=dept_b
		)

		all_summary = get_yearly_summary(company, 2024)
		jan_all = _month_row(all_summary, "January")
		self.assertEqual(jan_all["opening"], 2)

		a_summary = get_yearly_summary(company, 2024, department=dept_a)
		jan_a = _month_row(a_summary, "January")
		self.assertEqual(jan_a["opening"], 1)
		self.assertEqual(jan_a["total_strength"], 1)

	def test_current_year_omits_current_and_future_months(self):
		company = _make_company()
		_make_company_link(_make_employee(), company, "2020-01-01")
		today = date.today()
		summary = get_yearly_summary(company, today.year)
		shown = {m["month_num"] for m in summary["months"]}
		self.assertNotIn(today.month, shown)
		for future in range(today.month + 1, 13):
			self.assertNotIn(future, shown)
		for past in range(1, today.month):
			self.assertIn(past, shown)
