# Copyright (c) 2026, sj and Contributors
# See license.txt

import json

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from saral_hr.saral_hr.doctype.salary_structure_assignment.salary_structure_assignment import (
	get_statutory_components,
)
from saral_hr.saral_hr.doctype.salary_structure_assignment.ssa_excel_import import (
	import_from_rows,
	parse_header_map,
	statutory_flags_from_columns,
)


def _uid():
	return frappe.generate_hash(length=6)


def _ensure_component(name, abbr, type_="Earning", **extra):
	if frappe.db.exists("Salary Component", name):
		return name
	doc = frappe.get_doc(
		{
			"doctype": "Salary Component",
			"salary_component": name,
			"salary_component_abbr": abbr,
			"type": type_,
			**extra,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _make_company(with_pf=False):
	uid = _uid()
	payload = {
		"doctype": "Company",
		"company": f"_Test SSA Imp {uid}",
		"abbr": f"I{uid}"[:8],
		"country": "India",
		"default_currency": "INR",
		"salary_calculation_based_on": "Exclude Weekly Offs (Working Days)",
		"salary_amount_rounding_digits": "2",
	}
	if with_pf:
		payload["pf_dependent_component"] = [
			{
				"from_date": None,
				"to_date": None,
				"wage_components": json.dumps(["Basic"]),
				"employee_percent": 12,
				"employer_epf": 3.67,
				"employer_eps": 8.33,
				"edli_insurance": 0.5,
				"admin_charges": 0.5,
				"pf_wage_limit": 15000,
			}
		]
	doc = frappe.get_doc(payload)
	doc.insert(ignore_permissions=True)
	return doc.name


def _make_employee():
	payload = {
		"doctype": "Employee",
		"naming_series": "HR-EMP-",
		"first_name": f"Imp{_uid()}",
		"gender": "Other",
		"date_of_birth": "1990-01-01",
	}
	if frappe.get_meta("Employee").has_field("employee_code"):
		payload["employee_code"] = f"IMP{_uid()}"
	doc = frappe.get_doc(payload)
	doc.insert(ignore_permissions=True)
	return doc.name


def _ensure_category(name="Staff"):
	if frappe.db.exists("Category", name):
		return name
	doc = frappe.get_doc({"doctype": "Category", "category": name, "has_subtype": 0})
	doc.insert(ignore_permissions=True)
	return doc.name


def _make_company_link(employee, company):
	doc = frappe.get_doc(
		{
			"doctype": "Company Link",
			"employee": employee,
			"company": company,
			"category": _ensure_category(),
			"date_of_joining": "2024-01-01",
			"weekly_off": "Sunday",
			"is_active": 1,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


class TestSSAExcelImport(FrappeTestCase):
	def test_parse_header_map_meta_and_components(self):
		mapping = parse_header_map(
			["Name", "Start Date", "End Date", "Basic", "Employee PF"]
		)
		kinds = [m[0] if m else None for m in mapping]
		self.assertEqual(kinds, ["meta", "meta", "meta", "component", "component"])
		self.assertEqual(mapping[0], ("meta", "employee_name"))
		self.assertEqual(mapping[1], ("meta", "from_date"))
		self.assertEqual(mapping[2], ("meta", "to_date"))
		self.assertEqual(mapping[3], ("component", "Basic"))

	def test_statutory_flags_follow_excel_columns(self):
		flags = statutory_flags_from_columns(
			["Employee ESIC", "Professional Tax", "Basic"], None
		)
		self.assertEqual(flags["is_esic_applicable"], 1)
		self.assertEqual(flags["is_pt_applicable"], 1)
		self.assertEqual(flags["is_pf_applicable"], 0)
		self.assertEqual(flags["is_lwf_applicable"], 0)

		off = statutory_flags_from_columns(["Basic"], None)
		self.assertEqual(off["is_esic_applicable"], 0)
		self.assertEqual(off["is_pf_applicable"], 0)

	def test_import_uses_company_pf_not_excel_amount(self):
		company = _make_company(with_pf=True)
		basic = _ensure_component("Basic", "BASIC", "Earning")
		hra = _ensure_component("House Rent Allowance", "HRA", "Earning")
		emp_pf = _ensure_component("Employee PF", "PF", "Deduction")
		_ensure_component("Employer PF", "EMPR-PF", "Deduction", employer_contribution=1)
		_ensure_component("Employer EPS", "EMPR-EPS", "Deduction", employer_contribution=1)
		_ensure_component("Employer EDLI", "EMPR-EDLI", "Deduction", employer_contribution=1)
		_ensure_component(
			"Employer PF Admin Charges", "EMPR-PFADM", "Deduction", employer_contribution=1
		)

		ss = frappe.get_doc(
			{
				"doctype": "Salary Structure",
				"salary_structure_name": f"SSA Imp {_uid()}",
				"company": company,
				"is_active": "Yes",
				"currency": "INR",
			}
		)
		ss.append("earnings", {"salary_component": basic, "amount": 0})
		ss.append("earnings", {"salary_component": hra, "amount": 0})
		ss.append("deductions", {"salary_component": emp_pf, "amount": 0})
		ss.insert(ignore_permissions=True)

		cl1 = _make_company_link(_make_employee(), company)
		cl2 = _make_company_link(_make_employee(), company)

		rows = [
			["Employee", "From Date", "To Date", "Basic", "House Rent Allowance", "Employee PF"],
			[cl1, "2026-04-01", "2027-03-31", 15000, 6000, 1],
			[cl2, "2026-04-01", "2027-03-31", 20000, 8000, 9999],
		]
		result = import_from_rows(ss.name, rows)
		self.assertEqual(len(result["created"]), 2, result)
		self.assertEqual(result["errors"], [])

		expected = get_statutory_components(
			company=company,
			gross_salary=21000,
			from_date="2026-04-01",
			is_esic_applicable=0,
			is_pf_applicable=1,
			pf_type=None,
			is_pt_applicable=0,
			is_lwf_applicable=0,
			earnings_map={"Basic": 15000, "House Rent Allowance": 6000},
			employee=cl1,
		)
		expected_pf = next(
			flt(r["amount"]) for r in expected["deductions"] if r["salary_component"] == emp_pf
		)

		ssa1 = frappe.get_doc("Salary Structure Assignment", result["created"][0])
		self.assertEqual(ssa1.employee, cl1)
		self.assertEqual(ssa1.company, company)
		self.assertTrue(ssa1.employee_name)
		self.assertEqual(ssa1.category, "Staff")
		self.assertEqual(flt(ssa1.gross_salary), 21000)
		self.assertEqual(int(ssa1.is_pf_applicable), 1)
		self.assertEqual(int(ssa1.is_esic_applicable), 0)
		pf_row = next(r for r in ssa1.deductions if r.salary_component == emp_pf)
		self.assertEqual(flt(pf_row.amount), expected_pf)
		self.assertNotEqual(flt(pf_row.amount), 1)
		self.assertTrue(ssa1.employer_share)
		empr_names = {r.salary_component for r in ssa1.employer_share}
		self.assertIn("Employer PF", empr_names)
		expected_empr = next(
			flt(r["amount"]) for r in expected["employer_share"] if r["salary_component"] == "Employer PF"
		)
		ssa_empr = next(r.amount for r in ssa1.employer_share if r.salary_component == "Employer PF")
		self.assertEqual(flt(ssa_empr), expected_empr)

		ssa2 = frappe.get_doc("Salary Structure Assignment", result["created"][1])
		self.assertEqual(flt(ssa2.gross_salary), 28000)
		expected2 = get_statutory_components(
			company=company,
			gross_salary=28000,
			from_date="2026-04-01",
			is_esic_applicable=0,
			is_pf_applicable=1,
			pf_type=None,
			is_pt_applicable=0,
			is_lwf_applicable=0,
			earnings_map={"Basic": 20000, "House Rent Allowance": 8000},
			employee=cl2,
		)
		expected_pf2 = next(
			flt(r["amount"]) for r in expected2["deductions"] if r["salary_component"] == emp_pf
		)
		pf2 = next(r for r in ssa2.deductions if r.salary_component == emp_pf)
		self.assertEqual(flt(pf2.amount), expected_pf2)
		self.assertNotEqual(flt(pf2.amount), 9999)

	def test_warns_when_excel_component_not_on_structure(self):
		company = _make_company()
		basic = _ensure_component("Basic", "BASIC", "Earning")
		extra = _ensure_component(f"Night Shift {_uid()}", "NS", "Earning")

		ss = frappe.get_doc(
			{
				"doctype": "Salary Structure",
				"salary_structure_name": f"SSA Imp {_uid()}",
				"company": company,
				"is_active": "Yes",
				"currency": "INR",
			}
		)
		ss.append("earnings", {"salary_component": basic, "amount": 0})
		ss.insert(ignore_permissions=True)

		cl = _make_company_link(_make_employee(), company)
		rows = [
			["Employee", "From Date", "To Date", "Basic", extra],
			[cl, "2026-04-01", "2027-03-31", 10000, 500],
		]
		result = import_from_rows(ss.name, rows)
		self.assertEqual(len(result["created"]), 1, result)
		self.assertTrue(any(extra in w for w in result["warnings"]))
		ssa = frappe.get_doc("Salary Structure Assignment", result["created"][0])
		self.assertEqual(flt(ssa.gross_salary), 10000)
		self.assertFalse(any(r.salary_component == extra for r in ssa.earnings))
