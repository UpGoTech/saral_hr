# Copyright (c) 2026, sj and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import get_last_day, getdate

from saral_hr.saral_hr.page.saral_hr_overview import saral_hr_overview as overview


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
			"company": f"_Test SHO {uid}",
			"abbr": f"O{uid}"[:8],
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
			"first_name": f"ShoEmp{_uid()}",
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


def _stub_slip(cl: str, company: str, start_date: str, docstatus: int = 1) -> str:
	name = f"SS-SHO-{_uid()}"
	start = getdate(start_date)
	frappe.get_doc(
		{
			"doctype": "Salary Slip",
			"name": name,
			"naming_series": "SS-.YYYY.-",
			"employee": cl,
			"employee_name": "SHO Test",
			"company": company,
			"start_date": start,
			"end_date": get_last_day(start),
			"docstatus": docstatus,
			"currency": "INR",
		}
	).db_insert()
	return name


class TestSaralHrOverviewHistorical(FrappeTestCase):
	def test_monthly_data_includes_leavers_who_were_active_in_month(self):
		"""Historical Active/Slips must use tenure, not current is_active."""
		company = _make_company()
		stayer = _make_company_link(_make_employee(), company, "2024-01-01")
		leaver = _make_company_link(
			_make_employee(), company, "2024-01-01", left="2024-06-15"
		)
		self.assertEqual(frappe.db.get_value("Company Link", leaver, "is_active"), 0)

		_stub_slip(stayer, company, "2024-05-01")
		_stub_slip(leaver, company, "2024-05-01")

		rows = overview.get_monthly_data(
			[company], "2024-05-01", "2024-05-31"
		)
		self.assertEqual(len(rows), 1)
		may = rows[0]
		self.assertEqual(may["active_count"], 2)
		self.assertEqual(may["slip_count"], 2)

		status = overview.get_salary_slip_status([company], "2024-05")
		generated = {r["employee"] for r in status["generated"]}
		self.assertEqual(generated, {stayer, leaver})
		self.assertEqual(status["not_generated"], [])

	def test_slip_count_excludes_slips_outside_tenure(self):
		company = _make_company()
		cl = _make_company_link(
			_make_employee(), company, "2024-01-01", left="2024-04-30"
		)
		_stub_slip(cl, company, "2024-05-01")  # after left_date

		rows = overview.get_monthly_data(
			[company], "2024-05-01", "2024-05-31"
		)
		self.assertEqual(rows[0]["active_count"], 0)
		self.assertEqual(rows[0]["slip_count"], 0)
