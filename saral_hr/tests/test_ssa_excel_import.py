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
	apply_srr_and_daily_wage,
	import_from_rows,
	parse_header_map,
	statutory_flags_from_row,
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


def _ensure_category(name="Staff", has_subtype=0):
	if frappe.db.exists("Category", name):
		return name
	doc = frappe.get_doc({"doctype": "Category", "category": name, "has_subtype": has_subtype})
	doc.insert(ignore_permissions=True)
	return doc.name


def _make_company_link(employee, company, category=None, skill_type=None):
	payload = {
		"doctype": "Company Link",
		"employee": employee,
		"company": company,
		"category": category or _ensure_category(),
		"date_of_joining": "2024-01-01",
		"weekly_off": "Sunday",
		"is_active": 1,
	}
	if skill_type:
		payload["skill_type"] = skill_type
	doc = frappe.get_doc(payload)
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

	def test_statutory_flags_follow_excel_yes_no(self):
		flags = statutory_flags_from_row(
			{"Employee ESIC": 1, "Professional Tax": 1, "Basic": 20000}, None
		)
		self.assertEqual(flags["is_esic_applicable"], 1)
		self.assertEqual(flags["is_pt_applicable"], 1)
		self.assertEqual(flags["is_pf_applicable"], 0)
		self.assertEqual(flags["is_lwf_applicable"], 0)

		by_amount = statutory_flags_from_row(
			{"Employee PF": 999, "Professional Tax": 200}, "Limited PF"
		)
		self.assertEqual(by_amount["is_pf_applicable"], 1)
		self.assertEqual(by_amount["pf_applicable"], "Limited PF")
		self.assertEqual(by_amount["is_pt_applicable"], 1)

		off = statutory_flags_from_row(
			{"Basic": 20000, "Professional Tax": 0, "Employee PF": 0}, "Full PF"
		)
		self.assertEqual(off["is_esic_applicable"], 0)
		self.assertEqual(off["is_pf_applicable"], 0)
		self.assertEqual(off["is_pt_applicable"], 0)
		self.assertEqual(off["pf_applicable"], "")

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
		cl3 = _make_company_link(_make_employee(), company)

		rows = [
			["Employee", "From Date", "To Date", "Basic", "House Rent Allowance", "Employee PF", "PF Type"],
			[cl1, "2026-04-01", "2027-03-31", 15000, 6000, 1, "Limited PF"],
			[cl2, "2026-04-01", "2027-03-31", 20000, 8000, 9999, "Full PF"],
			[cl3, "2026-04-01", "2027-03-31", 20000, 8000, 0, "Limited PF"],
		]
		result = import_from_rows(ss.name, rows)
		self.assertEqual(len(result["created"]), 3, result)
		self.assertEqual(result["errors"], [])

		expected = get_statutory_components(
			company=company,
			gross_salary=21000,
			from_date="2026-04-01",
			is_esic_applicable=0,
			is_pf_applicable=1,
			pf_type="Limited PF",
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
		self.assertEqual(ssa1.pf_applicable, "Limited PF")
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
		self.assertEqual(ssa2.pf_applicable, "Full PF")
		expected2 = get_statutory_components(
			company=company,
			gross_salary=28000,
			from_date="2026-04-01",
			is_esic_applicable=0,
			is_pf_applicable=1,
			pf_type="Full PF",
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

		ssa3 = frappe.get_doc("Salary Structure Assignment", result["created"][2])
		self.assertEqual(int(ssa3.is_pf_applicable), 0)
		self.assertEqual(ssa3.pf_applicable or "", "")
		self.assertFalse(any(r.salary_component == emp_pf for r in ssa3.deductions))

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

	def test_import_resolves_employee_by_name_only(self):
		company = _make_company()
		basic = _ensure_component("Basic", "BASIC", "Earning")
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
		full_name = frappe.db.get_value("Company Link", cl, "full_name")
		spaced = "  ".join((full_name or "").split())
		rows = [
			["Name", "Start Date", "End Date", "Basic"],
			[spaced, "2026-04-01", "2027-03-31", 12000],
		]
		result = import_from_rows(ss.name, rows)
		self.assertEqual(len(result["created"]), 1, result)
		self.assertEqual(result["errors"], [])
		ssa = frappe.get_doc("Salary Structure Assignment", result["created"][0])
		self.assertEqual(ssa.employee, cl)
		self.assertEqual(flt(ssa.gross_salary), 12000)

	def test_errors_when_salary_component_not_created(self):
		company = _make_company()
		basic = _ensure_component("Basic", "BASIC", "Earning")
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
		missing = f"Ghost Comp {_uid()}"
		rows = [
			["Name", "Start Date", "End Date", "Basic", missing],
			["Anybody", "2026-04-01", "2027-03-31", 10000, 50],
		]
		result = import_from_rows(ss.name, rows)
		self.assertEqual(result["created"], [])
		self.assertTrue(any(missing in e for e in result["errors"]))
		self.assertTrue(any("not created" in e.lower() for e in result["errors"]))

	def test_apply_srr_overrides_excel_and_multiplies_daily_wage(self):
		earnings = [
			{"salary_component": "Basic", "abbr": "BASIC", "amount": 111, "base_amount": 111},
			{
				"salary_component": "V-Dearness Allowance",
				"abbr": "V-DA",
				"amount": 222,
				"base_amount": 222,
			},
			{
				"salary_component": "Washing Allowance-Daily",
				"abbr": "WASH",
				"amount": 10,
				"base_amount": 10,
				"daily_wage_component": 1,
			},
			{"salary_component": "House Rent Allowance", "abbr": "HRA", "amount": 500, "base_amount": 500},
		]
		apply_srr_and_daily_wage(earnings, [], [], {"vbasic": 5000, "vda": 1000}, 26)
		by_name = {r["salary_component"]: r for r in earnings}
		self.assertEqual(flt(by_name["Basic"]["amount"]), 5000)
		self.assertEqual(flt(by_name["V-Dearness Allowance"]["amount"]), 1000)
		self.assertEqual(flt(by_name["Washing Allowance-Daily"]["amount"]), 260)
		self.assertEqual(flt(by_name["Washing Allowance-Daily"]["per_day_rate"]), 10)
		self.assertEqual(flt(by_name["House Rent Allowance"]["amount"]), 500)

	def test_import_worker_uses_srr_and_daily_wage_multiplier(self):
		company = _make_company()
		worker_cat = _ensure_category(f"Worker Imp {_uid()}", has_subtype=1)
		basic = _ensure_component("Basic", "BASIC", "Earning")
		vda = _ensure_component("V-Dearness Allowance", "V-DA", "Earning")
		wash = _ensure_component(
			f"Washing Daily {_uid()}", "WASH-D", "Earning", daily_wage_component=1
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
		ss.append("earnings", {"salary_component": vda, "amount": 0})
		ss.append(
			"earnings",
			{"salary_component": wash, "amount": 0, "daily_wage_component": 1},
		)
		ss.insert(ignore_permissions=True)

		srr = frappe.get_doc(
			{
				"doctype": "Skill Rate Revision",
				"notification_number": f"IMP-{_uid()}",
				"from_month": "March",
				"from_year": "2035",
				"to_month": "March",
				"to_year": "2035",
				"daily_wage_multiplier": 26,
				"vbasic_skilled": 5000,
				"vbasic_semi_skilled": 4000,
				"vbasic_unskilled": 3000,
				"vda_skilled": 1000,
				"vda_semi_skilled": 800,
				"vda_unskilled": 600,
			}
		)
		srr.insert(ignore_permissions=True)
		srr.submit()

		cl = _make_company_link(
			_make_employee(), company, category=worker_cat, skill_type="Skilled"
		)
		rows = [
			["Name", "Start Date", "End Date", "Basic", "V-Dearness Allowance", wash],
			[cl, "2035-03-01", "2035-03-31", 111, 222, 10],
		]
		result = import_from_rows(ss.name, rows)
		self.assertEqual(len(result["created"]), 1, result)
		self.assertEqual(result["errors"], [])
		ssa = frappe.get_doc("Salary Structure Assignment", result["created"][0])
		by_name = {r.salary_component: r for r in ssa.earnings}
		self.assertEqual(flt(by_name[basic].amount), 5000)
		self.assertEqual(flt(by_name[vda].amount), 1000)
		self.assertEqual(flt(by_name[wash].amount), 260)
		self.assertEqual(flt(by_name[wash].per_day_rate), 10)
		self.assertNotEqual(flt(by_name[basic].amount), 111)

	def test_import_worker_errors_when_srr_missing(self):
		company = _make_company()
		worker_cat = _ensure_category(f"Worker Imp {_uid()}", has_subtype=1)
		basic = _ensure_component("Basic", "BASIC", "Earning")
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
		cl = _make_company_link(
			_make_employee(), company, category=worker_cat, skill_type="Skilled"
		)
		rows = [
			["Name", "Start Date", "End Date", "Basic"],
			[cl, "1980-01-01", "1980-01-31", 111],
		]
		result = import_from_rows(ss.name, rows)
		self.assertEqual(result["created"], [])
		self.assertTrue(any("Skill Rate Revision Not Found" in e for e in result["errors"]))
