# Copyright (c) 2026, sj and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import get_last_day, getdate

from saral_hr.saral_hr.page.salary_statistics.salary_statistics import (
	get_employee_month_details,
	get_employees_for_company,
)


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
			"company": f"_Test SS Left {uid}",
			"abbr": f"L{uid}"[:8],
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
			"first_name": f"SsLeft{_uid()}",
			"gender": "Other",
			"date_of_birth": "1990-01-01",
		}
	)
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


def _stub_slip(cl: str, company: str, start_date: str, net_salary: float, docstatus: int = 1) -> str:
	name = f"SS-LEFT-{_uid()}"
	start = getdate(start_date)
	frappe.get_doc(
		{
			"doctype": "Salary Slip",
			"name": name,
			"naming_series": "SS-.YYYY.-",
			"employee": cl,
			"employee_name": "Left Test",
			"company": company,
			"start_date": start,
			"end_date": get_last_day(start),
			"docstatus": docstatus,
			"currency": "INR",
			"net_salary": net_salary,
		}
	).db_insert()
	return name


class TestSalaryStatisticsLeftEmployee(FrappeTestCase):
	def test_detail_includes_inactive_leaver_slips(self):
		company = _make_company()
		stayer = _make_company_link(_make_employee(), company, "2024-01-01")
		leaver = _make_company_link(
			_make_employee(), company, "2024-01-01", left="2025-07-27"
		)
		self.assertEqual(frappe.db.get_value("Company Link", leaver, "is_active"), 0)

		slip = _stub_slip(leaver, company, "2025-07-01", 29032)
		_stub_slip(leaver, company, "2025-08-01", 999, docstatus=0)

		roster = get_employees_for_company(company, 2025, "July")
		roster_ids = {row["employee"] for row in roster}
		self.assertIn(stayer, roster_ids)
		self.assertNotIn(leaver, roster_ids)

		focused = get_employees_for_company(company, 2025, "July", employee=leaver)
		by_id = {row["employee"]: row for row in focused}
		self.assertIn(stayer, by_id)
		self.assertEqual(by_id[leaver]["monthly_net"]["July"], 29032)
		self.assertIsNone(by_id[leaver]["monthly_net"]["August"])
		self.assertNotIn("latest_slip_year", by_id[leaver])

		empty_year = get_employees_for_company(company, 2026, "September", employee=leaver)
		leaver_row = next(row for row in empty_year if row["employee"] == leaver)
		self.assertIsNone(leaver_row["monthly_net"]["July"])
		self.assertEqual(leaver_row["latest_slip_year"], 2025)

		detail = get_employee_month_details(leaver, 2025, "July")
		self.assertEqual(detail["salary"]["slip_name"], slip)
		self.assertEqual(detail["salary"]["net_salary"], 29032)
