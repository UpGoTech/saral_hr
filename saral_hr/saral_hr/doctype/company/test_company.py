# Copyright (c) 2026, sj and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import getdate

from saral_hr.saral_hr.doctype.company.company import (
	backfill_all_company_employee_counts,
	update_company_employee_counts,
)


def _ensure_category(name: str, has_subtype: int = 0):
	if frappe.db.exists("Category", name):
		return name
	doc = frappe.get_doc(
		{
			"doctype": "Category",
			"category": name,
			"has_subtype": has_subtype,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _uid() -> str:
	return frappe.generate_hash(length=6)


def _make_company() -> str:
	uid = _uid()
	doc = frappe.get_doc(
		{
			"doctype": "Company",
			"company": f"_Test Co Counts {uid}",
			"abbr": f"C{uid}"[:8],
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
			"first_name": f"CountEmp{_uid()}",
			"gender": "Other",
			"date_of_birth": "1990-01-01",
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _make_company_link(
	employee: str,
	company: str,
	category: str,
	*,
	is_active: int = 1,
	skill_type: str | None = None,
):
	doc = frappe.get_doc(
		{
			"doctype": "Company Link",
			"employee": employee,
			"company": company,
			"category": category,
			"date_of_joining": getdate(),
			"is_active": is_active,
			"skill_type": skill_type or "",
		}
	)
	doc.insert(ignore_permissions=True)
	return doc


def _counts(company: str) -> tuple[int, int, int]:
	row = frappe.db.get_value(
		"Company",
		company,
		["no_of_staff", "no_of_workers", "total_no_of_employees"],
		as_dict=True,
	)
	return (
		int(row.no_of_staff or 0),
		int(row.no_of_workers or 0),
		int(row.total_no_of_employees or 0),
	)


class TestCompanyEmployeeCounts(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_ensure_category("Staff", has_subtype=0)
		_ensure_category("Worker", has_subtype=1)
		_ensure_category("Contractor", has_subtype=0)

	def test_active_staff_and_worker_increment_counts(self):
		company = _make_company()
		_make_company_link(_make_employee(), company, "Staff")
		_make_company_link(_make_employee(), company, "Worker", skill_type="Skilled")

		self.assertEqual(_counts(company), (1, 1, 2))

	def test_inactive_links_excluded(self):
		company = _make_company()
		link = _make_company_link(_make_employee(), company, "Staff")
		self.assertEqual(_counts(company), (1, 0, 1))

		link.is_active = 0
		link.save(ignore_permissions=True)
		self.assertEqual(_counts(company), (0, 0, 0))

	def test_other_categories_do_not_affect_total(self):
		company = _make_company()
		_make_company_link(_make_employee(), company, "Staff")
		_make_company_link(_make_employee(), company, "Contractor")

		self.assertEqual(_counts(company), (1, 0, 1))

	def test_trash_decreases_counts(self):
		company = _make_company()
		link = _make_company_link(
			_make_employee(), company, "Worker", skill_type="Unskilled"
		)
		self.assertEqual(_counts(company), (0, 1, 1))

		link.delete(ignore_permissions=True)
		self.assertEqual(_counts(company), (0, 0, 0))

	def test_company_change_moves_counts(self):
		company_a = _make_company()
		company_b = _make_company()
		link = _make_company_link(_make_employee(), company_a, "Staff")
		self.assertEqual(_counts(company_a), (1, 0, 1))
		self.assertEqual(_counts(company_b), (0, 0, 0))

		link.company = company_b
		link.save(ignore_permissions=True)
		self.assertEqual(_counts(company_a), (0, 0, 0))
		self.assertEqual(_counts(company_b), (1, 0, 1))

	def test_backfill_recomputes_counts(self):
		company = _make_company()
		_make_company_link(_make_employee(), company, "Staff")

		frappe.db.set_value(
			"Company",
			company,
			{
				"no_of_staff": 99,
				"no_of_workers": 99,
				"total_no_of_employees": 99,
			},
			update_modified=False,
		)
		self.assertEqual(_counts(company), (99, 99, 99))

		backfill_all_company_employee_counts()
		self.assertEqual(_counts(company), (1, 0, 1))

	def test_helper_noop_for_missing_company(self):
		update_company_employee_counts(None)
		update_company_employee_counts("_Does Not Exist Counts Co")
