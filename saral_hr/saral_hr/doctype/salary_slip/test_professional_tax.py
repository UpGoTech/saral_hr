# Copyright (c) 2026, sj and Contributors
# See license.txt

"""Salary slip / SSA PT calculation uses Company slabs — no flat 200/300."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import getdate

from saral_hr.saral_hr.doctype.company.company import maharashtra_pt_slabs_json
from saral_hr.saral_hr.doctype.salary_slip.salary_slip import (
	_company_pt_amount,
	get_statutory_components_internal,
)
from saral_hr.saral_hr.doctype.salary_structure_assignment.salary_structure_assignment import (
	get_statutory_components,
)


def _uid() -> str:
	return frappe.generate_hash(length=6)


def _make_pt_company() -> str:
	uid = _uid()
	doc = frappe.get_doc(
		{
			"doctype": "Company",
			"company": f"_Test Co Slip PT {uid}",
			"abbr": f"S{uid}"[:8],
			"country": "India",
			"default_currency": "INR",
			"salary_calculation_based_on": "Exclude Weekly Offs (Working Days)",
			"pt_periods": [
				{
					"from_date": None,
					"to_date": None,
					"february_amount": 300,
					"age_exempt_years": 65,
					"slabs": maharashtra_pt_slabs_json(),
				}
			],
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _make_employee(gender="Male", dob="1990-01-01") -> str:
	doc = frappe.get_doc(
		{
			"doctype": "Employee",
			"naming_series": "HR-EMP-",
			"first_name": f"PTEmp{_uid()}",
			"gender": gender,
			"date_of_birth": dob,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


class TestProfessionalTaxCalculationPaths(FrappeTestCase):
	def test_company_pt_amount_helper(self):
		company = _make_pt_company()
		employee = _make_employee("Male")
		self.assertEqual(_company_pt_amount(company, 12000, employee, "2026-01-15"), 200.0)
		self.assertEqual(_company_pt_amount(company, 12000, employee, "2026-02-15"), 300.0)

	def test_ssa_statutory_uses_slabs_not_flat(self):
		company = _make_pt_company()
		employee = _make_employee("Female")
		result = get_statutory_components(
			company=company,
			gross_salary=30000,
			from_date="2026-01-15",
			is_pt_applicable=1,
			employee=employee,
		)
		pt_rows = [d for d in result["deductions"] if d["salary_component"] == "Professional Tax"]
		self.assertEqual(len(pt_rows), 1)
		self.assertEqual(pt_rows[0]["amount"], 200.0)

	def test_ssa_pt_off_returns_no_pt_row(self):
		company = _make_pt_company()
		employee = _make_employee("Male")
		result = get_statutory_components(
			company=company,
			gross_salary=50000,
			from_date="2026-01-15",
			is_pt_applicable=0,
			employee=employee,
		)
		pt_rows = [d for d in result["deductions"] if d["salary_component"] == "Professional Tax"]
		self.assertEqual(pt_rows, [])

	def test_slip_internal_uses_slabs(self):
		company = _make_pt_company()
		employee = _make_employee("Male")
		result = get_statutory_components_internal(
			company=company,
			gross_salary=8000,
			earnings_map={},
			from_date="2026-01-15",
			is_esic_applicable=0,
			is_pf_applicable=0,
			pf_type="",
			is_pt_applicable=1,
			is_lwf_applicable=0,
			employee=employee,
		)
		pt_rows = [d for d in result["deductions"] if d["salary_component"] == "Professional Tax"]
		self.assertEqual(len(pt_rows), 1)
		self.assertEqual(pt_rows[0]["amount"], 175.0)

	def test_no_hardcoded_pt_constants_in_ctc_modules(self):
		import inspect
		from saral_hr.saral_hr.page.ctc_calculator import ctc_calculator
		from saral_hr.saral_hr.doctype.ctc_calculator_record import ctc_calculator_record

		for mod in (ctc_calculator, ctc_calculator_record):
			src = inspect.getsource(mod)
			self.assertNotIn("PT_NORMAL", src)
			self.assertNotIn("PT_FEBRUARY", src)
