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


class TestCompanyProfessionalTax(FrappeTestCase):
	def _make_pt_company(self, slabs=None, age_exempt_years=65):
		from saral_hr.saral_hr.doctype.company.company import maharashtra_pt_slabs_json
		import json

		uid = _uid()
		doc = frappe.get_doc(
			{
				"doctype": "Company",
				"company": f"_Test Co PT {uid}",
				"abbr": f"P{uid}"[:8],
				"country": "India",
				"default_currency": "INR",
				"salary_calculation_based_on": "Exclude Weekly Offs (Working Days)",
				"pt_periods": [
					{
						"from_date": None,
						"to_date": None,
						"age_exempt_years": age_exempt_years,
						"slabs": json.dumps(slabs) if slabs is not None else maharashtra_pt_slabs_json(),
					}
				],
			}
		)
		doc.insert(ignore_permissions=True)
		return doc

	def test_male_slab_boundaries(self):
		comp = self._make_pt_company()
		self.assertEqual(comp.calculate_pt(0, "Male", "2026-01-15"), 0.0)
		self.assertEqual(comp.calculate_pt(7500, "Male", "2026-01-15"), 0.0)
		self.assertEqual(comp.calculate_pt(7501, "Male", "2026-01-15"), 175.0)
		self.assertEqual(comp.calculate_pt(10000, "Male", "2026-01-15"), 175.0)
		self.assertEqual(comp.calculate_pt(10001, "Male", "2026-01-15"), 200.0)
		self.assertEqual(comp.calculate_pt(50000, "Male", "2026-01-15"), 200.0)

	def test_female_slab_boundaries(self):
		comp = self._make_pt_company()
		self.assertEqual(comp.calculate_pt(25000, "Female", "2026-01-15"), 0.0)
		self.assertEqual(comp.calculate_pt(25001, "Female", "2026-01-15"), 200.0)

	def test_february_male_mid_and_top_slabs(self):
		comp = self._make_pt_company()
		self.assertEqual(comp.calculate_pt(5000, "Male", "2026-02-10"), 0.0)
		self.assertEqual(comp.calculate_pt(8000, "Male", "2026-02-10"), 275.0)
		self.assertEqual(comp.calculate_pt(12000, "Male", "2026-02-10"), 300.0)
		self.assertEqual(comp.calculate_pt(8000, "Male", "2026-01-10"), 175.0)
		self.assertEqual(comp.calculate_pt(12000, "Male", "2026-01-10"), 200.0)

	def test_february_female_stays_at_tax_amount(self):
		comp = self._make_pt_company()
		self.assertEqual(comp.calculate_pt(30000, "Female", "2026-02-10"), 200.0)
		self.assertEqual(comp.calculate_pt(30000, "Female", "2026-01-10"), 200.0)
		self.assertEqual(comp.calculate_pt(20000, "Female", "2026-02-10"), 0.0)

	def test_february_amount_on_zero_tax_slab_rejected(self):
		import json

		uid = _uid()
		doc = frappe.get_doc(
			{
				"doctype": "Company",
				"company": f"_Test Co PT BadFeb {uid}",
				"abbr": f"B{uid}"[:8],
				"country": "India",
				"default_currency": "INR",
				"salary_calculation_based_on": "Exclude Weekly Offs (Working Days)",
				"pt_periods": [
					{
						"age_exempt_years": 65,
						"slabs": json.dumps(
							[
								{
									"gender": "Male",
									"from_amount": 0,
									"to_amount": 7500,
									"tax_amount": 0,
									"february_amount": 300,
								}
							]
						),
					}
				],
			}
		)
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)

	def test_age_exemption(self):
		comp = self._make_pt_company(age_exempt_years=65)
		self.assertEqual(
			comp.calculate_pt(50000, "Male", "2026-01-15", date_of_birth="1960-01-01"),
			0.0,
		)
		self.assertEqual(
			comp.calculate_pt(50000, "Male", "2026-01-15", date_of_birth="1990-01-01"),
			200.0,
		)

	def test_missing_or_other_gender_uses_male_slabs(self):
		comp = self._make_pt_company()
		self.assertEqual(comp.calculate_pt(8000, None, "2026-01-15"), 175.0)
		self.assertEqual(comp.calculate_pt(8000, "Other", "2026-01-15"), 175.0)
		self.assertEqual(comp.calculate_pt(8000, "", "2026-01-15"), 175.0)

	def test_no_period_returns_zero(self):
		uid = _uid()
		comp = frappe.get_doc(
			{
				"doctype": "Company",
				"company": f"_Test Co PT Empty {uid}",
				"abbr": f"E{uid}"[:8],
				"country": "India",
				"default_currency": "INR",
				"salary_calculation_based_on": "Exclude Weekly Offs (Working Days)",
			}
		).insert(ignore_permissions=True)
		self.assertEqual(comp.calculate_pt(50000, "Male", "2026-01-15"), 0.0)

	def test_overlapping_periods_rejected(self):
		from saral_hr.saral_hr.doctype.company.company import maharashtra_pt_slabs_json

		uid = _uid()
		doc = frappe.get_doc(
			{
				"doctype": "Company",
				"company": f"_Test Co PT Overlap {uid}",
				"abbr": f"O{uid}"[:8],
				"country": "India",
				"default_currency": "INR",
				"salary_calculation_based_on": "Exclude Weekly Offs (Working Days)",
				"pt_periods": [
					{
						"from_date": "2026-01-01",
						"to_date": "2026-06-30",
						"age_exempt_years": 65,
						"slabs": maharashtra_pt_slabs_json(),
					},
					{
						"from_date": "2026-06-01",
						"to_date": "2026-12-31",
						"age_exempt_years": 65,
						"slabs": maharashtra_pt_slabs_json(),
					},
				],
			}
		)
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)


def _stub_submitted_slip(company: str, start_date: str) -> str:
	"""Minimal submitted slip row — only fields the lock query needs."""
	name = f"SS-LOCK-{_uid()}"
	frappe.get_doc(
		{
			"doctype": "Salary Slip",
			"name": name,
			"naming_series": "SS-.YYYY.-",
			"employee": f"LOCK-EMP-{_uid()}",
			"employee_name": "Lock Test",
			"company": company,
			"start_date": start_date,
			"end_date": start_date,
			"docstatus": 1,
		}
	).db_insert()
	return name


def _stub_submitted_ssa(company: str, from_date: str) -> str:
	"""Minimal submitted SSA row — only fields the lock query needs."""
	name = f"SSA-LOCK-{_uid()}"
	frappe.get_doc(
		{
			"doctype": "Salary Structure Assignment",
			"name": name,
			"employee": f"LOCK-EMP-{_uid()}",
			"company": company,
			"from_date": from_date,
			"to_date": "9999-12-31",
			"salary_structure": "LOCK-SS",
			"docstatus": 1,
			"status": "Submitted",
		}
	).db_insert()
	return name


class TestStatutoryPeriodLock(FrappeTestCase):
	"""Period lock = submitted Salary Slip in period (SSA alone does not lock)."""

	def test_unlocked_when_no_submitted_slips(self):
		company = _make_company()
		_stub_submitted_ssa(company, "2024-04-01")
		doc = frappe.get_doc("Company", company)
		# SSA present, but no slips → both periods unlocked for correction
		self.assertFalse(doc._period_is_locked("2024-07-01", None))
		self.assertFalse(doc._period_is_locked("2024-04-01", "2024-06-30"))

	def test_submitted_slip_locks_that_period_only(self):
		company = _make_company()
		_stub_submitted_ssa(company, "2024-04-01")
		_stub_submitted_slip(company, "2024-05-01")
		doc = frappe.get_doc("Company", company)
		self.assertTrue(doc._period_is_locked("2024-04-01", "2024-06-30"))
		self.assertFalse(doc._period_is_locked("2024-07-01", None))

	def test_cancelling_slips_unlocks_period(self):
		company = _make_company()
		_stub_submitted_ssa(company, "2024-04-01")
		slip = _stub_submitted_slip(company, "2024-05-01")
		doc = frappe.get_doc("Company", company)
		self.assertTrue(doc._period_is_locked("2024-04-01", "2024-06-30"))
		# Submitted slips must be cancelled (not hard-deleted) — then period unlocks
		frappe.db.set_value("Salary Slip", slip, "docstatus", 2)
		self.assertFalse(doc._period_is_locked("2024-04-01", "2024-06-30"))

	def test_draft_slip_does_not_lock(self):
		company = _make_company()
		name = f"SS-DRAFT-{_uid()}"
		frappe.get_doc(
			{
				"doctype": "Salary Slip",
				"name": name,
				"naming_series": "SS-.YYYY.-",
				"employee": f"LOCK-EMP-{_uid()}",
				"company": company,
				"start_date": "2024-07-01",
				"end_date": "2024-07-31",
				"docstatus": 0,
			}
		).db_insert()
		doc = frappe.get_doc("Company", company)
		self.assertFalse(doc._period_is_locked("2024-07-01", None))

	def test_get_statutory_lock_dates_api(self):
		from saral_hr.saral_hr.doctype.company.company import get_statutory_lock_dates

		company = _make_company()
		_stub_submitted_ssa(company, "2024-04-01")
		_stub_submitted_slip(company, "2024-07-15")
		payload = get_statutory_lock_dates(company)
		self.assertNotIn("ssa_from_dates", payload)
		self.assertIn("2024-07-15", payload["slip_start_dates"])
