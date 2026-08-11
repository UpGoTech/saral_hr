# Copyright (c) 2026, sj and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from saral_hr.saral_hr.doctype.salary_component.salary_component import (
	is_percent_of_total_earning_locked,
)
from saral_hr.saral_hr.doctype.salary_slip.salary_slip import (
	calculate_salary_slip_amounts_exact,
)


def _uid() -> str:
	return frappe.generate_hash(length=6)


def _ensure_component(name, abbr, type_="Deduction", **extra):
	if frappe.db.exists("Salary Component", name):
		doc = frappe.get_doc("Salary Component", name)
		doc.update(extra)
		doc.save(ignore_permissions=True)
		return doc.name
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


def _make_company() -> str:
	uid = _uid()
	doc = frappe.get_doc(
		{
			"doctype": "Company",
			"company": f"_Test PctEarn {uid}",
			"abbr": f"P{uid}"[:8],
			"country": "India",
			"default_currency": "INR",
			"salary_calculation_based_on": "Exclude Weekly Offs (Working Days)",
			"salary_amount_rounding_digits": "2",
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _make_employee() -> str:
	doc = frappe.get_doc(
		{
			"doctype": "Employee",
			"naming_series": "HR-EMP-",
			"first_name": f"Pct{_uid()}",
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


def _make_company_link(employee: str, company: str):
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


class TestPercentOfTotalEarning(FrappeTestCase):
	def test_slip_percent_includes_additional_salary_row(self):
		"""50k earnings + 5k additional on earnings table → 10% = 5500."""
		company = _make_company()
		employee = _make_employee()
		cl = _make_company_link(employee, company)
		uid = _uid()
		basic = _ensure_component(f"Basic Pct {uid}", f"B{uid}", "Earning")
		tds = _ensure_component(
			f"94J {uid}",
			f"J{uid}",
			"Deduction",
			percent_on_total_earning=1,
			percent_of_total_earning=10,
		)
		addl = _ensure_component(f"Prod Inc {uid}", f"PI{uid}", "Earning", is_additional_only=1)

		ss = frappe.new_doc("Salary Slip")
		ss.employee = cl
		ss.company = company
		ss.start_date = "2024-01-01"
		ss.end_date = "2024-01-31"
		ss.total_working_days = 30
		ss.payment_days = 30
		ss.physical_working_days = 30

		e = ss.append("earnings", {})
		e.salary_component = basic
		e.base_amount = 50000
		e.amount = 50000

		a = ss.append("earnings", {})
		a.salary_component = addl
		a.base_amount = 5000
		a.amount = 5000

		d = ss.append("deductions", {})
		d.salary_component = tds
		d.base_amount = 0
		d.amount = 0
		d.percent_on_total_earning = 1
		d.percent_of_total_earning = 10

		calculate_salary_slip_amounts_exact(ss, 0, "2024-01-01")
		self.assertEqual(flt(ss.total_earnings), 55000)
		self.assertEqual(flt(ss.deductions[0].amount), 5500)

	def test_two_percent_components(self):
		company = _make_company()
		employee = _make_employee()
		cl = _make_company_link(employee, company)
		uid = _uid()
		basic = _ensure_component(f"Basic Two {uid}", f"BT{uid}", "Earning")
		c10 = _ensure_component(
			f"94J Two {uid}", f"J2{uid}", "Deduction",
			percent_on_total_earning=1, percent_of_total_earning=10,
		)
		c2 = _ensure_component(
			f"91Q Two {uid}", f"Q2{uid}", "Deduction",
			percent_on_total_earning=1, percent_of_total_earning=2,
		)

		ss = frappe.new_doc("Salary Slip")
		ss.employee = cl
		ss.company = company
		ss.start_date = "2024-01-01"
		ss.end_date = "2024-01-31"
		ss.total_working_days = 30
		ss.payment_days = 30
		ss.physical_working_days = 30
		e = ss.append("earnings", {})
		e.salary_component = basic
		e.base_amount = 50000
		e.amount = 50000
		for name, pct in ((c10, 10), (c2, 2)):
			d = ss.append("deductions", {})
			d.salary_component = name
			d.percent_on_total_earning = 1
			d.percent_of_total_earning = pct
			d.amount = 0
			d.base_amount = 0

		calculate_salary_slip_amounts_exact(ss, 0, "2024-01-01")
		by_name = {r.salary_component: flt(r.amount) for r in ss.deductions}
		self.assertEqual(by_name[c10], 5000)
		self.assertEqual(by_name[c2], 1000)

	def test_zero_earnings_yields_zero(self):
		company = _make_company()
		employee = _make_employee()
		cl = _make_company_link(employee, company)
		uid = _uid()
		tds = _ensure_component(
			f"94J Zero {uid}", f"JZ{uid}", "Deduction",
			percent_on_total_earning=1, percent_of_total_earning=10,
		)
		ss = frappe.new_doc("Salary Slip")
		ss.employee = cl
		ss.company = company
		ss.start_date = "2024-01-01"
		ss.end_date = "2024-01-31"
		ss.total_working_days = 30
		ss.payment_days = 0
		ss.physical_working_days = 0
		d = ss.append("deductions", {})
		d.salary_component = tds
		d.percent_on_total_earning = 1
		d.percent_of_total_earning = 10
		d.amount = 999
		d.base_amount = 999
		calculate_salary_slip_amounts_exact(ss, 0, "2024-01-01")
		self.assertEqual(flt(ss.deductions[0].amount), 0)

	def test_mutual_exclusion_with_payment_days(self):
		uid = _uid()
		doc = frappe.get_doc(
			{
				"doctype": "Salary Component",
				"salary_component": f"Bad Pct {uid}",
				"salary_component_abbr": f"BP{uid}",
				"type": "Deduction",
				"percent_on_total_earning": 1,
				"percent_of_total_earning": 10,
				"depends_on_payment_days": 1,
			}
		)
		self.assertRaises(frappe.ValidationError, doc.insert)

	def test_percent_lock_on_ssa(self):
		company = _make_company()
		employee = _make_employee()
		cl = _make_company_link(employee, company)
		uid = _uid()
		basic = _ensure_component(f"Basic Lock {uid}", f"BL{uid}", "Earning")
		tds = _ensure_component(
			f"94J Lock {uid}", f"JL{uid}", "Deduction",
			percent_on_total_earning=1, percent_of_total_earning=10,
		)
		structure = frappe.get_doc(
			{
				"doctype": "Salary Structure",
				"salary_structure_name": f"SS Pct {uid}",
				"company": company,
				"currency": "INR",
				"is_active": "Yes",
			}
		)
		structure.append("earnings", {"salary_component": basic, "amount": 50000})
		structure.append("deductions", {"salary_component": tds, "amount": 0})
		structure.insert(ignore_permissions=True)

		ssa = frappe.get_doc(
			{
				"doctype": "Salary Structure Assignment",
				"employee": cl,
				"company": company,
				"from_date": "2024-01-01",
				"to_date": "2024-12-31",
				"salary_structure": structure.name,
				"currency": "INR",
			}
		)
		ssa.append("earnings", {"salary_component": basic, "amount": 50000})
		ssa.append(
			"deductions",
			{
				"salary_component": tds,
				"amount": 5000,
				"percent_on_total_earning": 1,
				"percent_of_total_earning": 10,
			},
		)
		ssa.insert(ignore_permissions=True)

		self.assertTrue(is_percent_of_total_earning_locked(tds))
		comp = frappe.get_doc("Salary Component", tds)
		comp.percent_of_total_earning = 5
		self.assertRaises(frappe.ValidationError, comp.save)

		# Draft SSA: delete unlocks (cancel requires submit first)
		ssa.delete()
		self.assertFalse(is_percent_of_total_earning_locked(tds))
		comp.reload()
		comp.percent_of_total_earning = 5
		comp.save(ignore_permissions=True)
		self.assertEqual(flt(comp.percent_of_total_earning), 5)
