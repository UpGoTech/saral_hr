# Copyright (c) 2026, sj and Contributors
# See license.txt

"""Additional-only Salary Components: Link validation + ESIC wage map by name."""

import json

import frappe
from frappe.tests.utils import FrappeTestCase

from saral_hr.saral_hr.doctype.salary_slip.salary_slip import (
	_merge_additional_into_earnings_map,
	get_statutory_components_internal,
)


def _uid() -> str:
	return frappe.generate_hash(length=6)


def _ensure_component(name, abbr, type_, is_additional_only=0):
	if frappe.db.exists("Salary Component", name):
		frappe.db.set_value(
			"Salary Component",
			name,
			{
				"type": type_,
				"is_additional_only": is_additional_only,
				"is_special_component": 0,
			},
		)
		return name
	doc = frappe.get_doc(
		{
			"doctype": "Salary Component",
			"salary_component": name,
			"salary_component_abbr": abbr,
			"type": type_,
			"is_additional_only": is_additional_only,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _make_esic_company(wage_components):
	uid = _uid()
	doc = frappe.get_doc(
		{
			"doctype": "Company",
			"company": f"_Test Co Addl ESIC {uid}",
			"abbr": f"A{uid}"[:8],
			"country": "India",
			"default_currency": "INR",
			"salary_calculation_based_on": "Exclude Weekly Offs (Working Days)",
			"esic_dependent_component": [
				{
					"from_date": None,
					"to_date": None,
					"wage_components": json.dumps(wage_components),
					"employee_contribution": 0.75,
					"employer_contribution": 3.25,
				}
			],
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


class TestAdditionalOnlySalaryComponents(FrappeTestCase):
	def test_esic_includes_named_additional_earning(self):
		incentive = _ensure_component(
			f"Prod Inc {_uid()}", "PI", "Earning", is_additional_only=1
		)
		basic = _ensure_component(f"Basic {_uid()}", "B", "Earning", is_additional_only=0)
		company = _make_esic_company([basic, incentive])

		earnings_map = {basic: 10000.0}
		_merge_additional_into_earnings_map(earnings_map, {incentive: 2000.0})
		self.assertEqual(earnings_map[incentive], 2000.0)

		gross = sum(earnings_map.values())
		result = get_statutory_components_internal(
			company=company,
			gross_salary=gross,
			earnings_map=earnings_map,
			from_date="2026-01-15",
			is_esic_applicable=1,
			is_pf_applicable=0,
			pf_type="",
			is_pt_applicable=0,
			is_lwf_applicable=0,
		)
		emp = [d for d in result["deductions"] if d["salary_component"] == "Employee ESIC"]
		empr = [d for d in result["employer_share"] if d["salary_component"] == "Employer ESIC"]
		self.assertEqual(len(emp), 1)
		self.assertEqual(len(empr), 1)
		# wage = 10000 + 2000 = 12000
		self.assertEqual(emp[0]["amount"], 90.0)  # 12000 * 0.75%
		self.assertEqual(empr[0]["amount"], 390.0)  # 12000 * 3.25%

	def test_esic_excludes_additional_when_not_in_wage_list(self):
		incentive = _ensure_component(
			f"Prod Inc X {_uid()}", "PIX", "Earning", is_additional_only=1
		)
		basic = _ensure_component(f"Basic X {_uid()}", "BX", "Earning", is_additional_only=0)
		company = _make_esic_company([basic])

		earnings_map = {basic: 10000.0}
		_merge_additional_into_earnings_map(earnings_map, {incentive: 2000.0})
		result = get_statutory_components_internal(
			company=company,
			gross_salary=sum(earnings_map.values()),
			earnings_map=earnings_map,
			from_date="2026-01-15",
			is_esic_applicable=1,
			is_pf_applicable=0,
			pf_type="",
			is_pt_applicable=0,
			is_lwf_applicable=0,
		)
		emp = [d for d in result["deductions"] if d["salary_component"] == "Employee ESIC"]
		self.assertEqual(emp[0]["amount"], 75.0)  # 10000 * 0.75% only

	def test_additional_salary_rejects_non_additional_only(self):
		basic = _ensure_component(
			f"Basic AS {_uid()}", "BAS", "Earning", is_additional_only=0
		)
		# Minimal parent fields — validate should fail before needing a real employee
		doc = frappe.get_doc(
			{
				"doctype": "Additional Salary",
				"employee": "x",
				"year": "2026",
				"month": "January",
				"components": [{"component_type": basic, "amount": 100}],
			}
		)
		with self.assertRaises(frappe.ValidationError):
			doc.validate()

	def test_additional_salary_rejects_missing_component(self):
		doc = frappe.get_doc(
			{
				"doctype": "Additional Salary",
				"employee": "x",
				"year": "2026",
				"month": "January",
				"components": [{"component_type": "No Such Component XYZ", "amount": 100}],
			}
		)
		with self.assertRaises(frappe.ValidationError):
			doc.validate()

	def test_ssa_rejects_additional_only_component(self):
		incentive = _ensure_component(
			f"Prod Inc SSA {_uid()}", "PIS", "Earning", is_additional_only=1
		)
		ssa = frappe.new_doc("Salary Structure Assignment")
		ssa.append("earnings", {"salary_component": incentive, "amount": 500})
		with self.assertRaises(frappe.ValidationError):
			ssa._reject_additional_only_components()

	def test_special_and_additional_only_mutually_exclusive(self):
		name = _ensure_component(
			f"Bad Flags {_uid()}", "BF", "Earning", is_additional_only=0
		)
		doc = frappe.get_doc("Salary Component", name)
		doc.is_special_component = 1
		doc.is_additional_only = 1
		with self.assertRaises(frappe.ValidationError):
			doc.validate()
