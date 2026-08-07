# Copyright (c) 2026, sj and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import getdate

from saral_hr.saral_hr.report.monthly_salary_register_old_format_net_payable.monthly_salary_register_old_format_net_payable import (
	build_register,
	_act_fn,
	_earn_fn,
	_ded_fn,
)


def _uid() -> str:
	return frappe.generate_hash(length=6)


def _ensure_category(name: str):
	if frappe.db.exists("Category", name):
		return name
	doc = frappe.get_doc({"doctype": "Category", "category": name, "has_subtype": 0})
	doc.insert(ignore_permissions=True)
	return doc.name


def _ensure_component(name: str, typ: str = "Earning"):
	if frappe.db.exists("Salary Component", name):
		return name
	doc = frappe.get_doc(
		{
			"doctype": "Salary Component",
			"salary_component": name,
			"salary_component_abbr": name[:10].upper().replace(" ", ""),
			"type": typ,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _make_company() -> str:
	uid = _uid()
	doc = frappe.get_doc(
		{
			"doctype": "Company",
			"company": f"_Test MSR {uid}",
			"abbr": f"M{uid}"[:8],
			"country": "India",
			"default_currency": "INR",
			"salary_calculation_based_on": "Exclude Weekly Offs (Working Days)",
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _make_employee(bank="SBI", ifsc="SBIN0001234", acct="1234567890") -> str:
	doc = frappe.get_doc(
		{
			"doctype": "Employee",
			"naming_series": "HR-EMP-",
			"first_name": f"MSR{_uid()}",
			"gender": "Other",
			"date_of_birth": "1990-01-01",
		}
	)
	doc.insert(ignore_permissions=True)
	# bank_name is a Link; set via SQL to avoid creating Bank masters in every test
	frappe.db.sql(
		"""
		UPDATE `tabEmployee`
		SET bank_name=%s, ifsc_code=%s, account_number=%s
		WHERE name=%s
		""",
		(bank, ifsc, acct, doc.name),
	)
	return doc.name


def _make_cl(employee, company, category="Staff"):
	doc = frappe.get_doc(
		{
			"doctype": "Company Link",
			"employee": employee,
			"company": company,
			"category": _ensure_category(category),
			"date_of_joining": getdate("2024-01-01"),
			"is_active": 1,
		}
	)
	doc.flags.ignore_validate = True
	doc.flags.ignore_mandatory = True
	doc.insert(ignore_permissions=True)
	# Ensure category sticks even if validate would rewrite it
	frappe.db.set_value("Company Link", doc.name, "category", category, update_modified=False)
	return doc.name


def _make_structure(company):
	name = f"_Test MSR Struct {_uid()}"
	if frappe.db.exists("Salary Structure", name):
		return name
	doc = frappe.get_doc(
		{
			"doctype": "Salary Structure",
			"salary_structure_name": name,
			"company": company,
			"currency": "INR",
			"is_active": "Yes",
		}
	)
	doc.flags.ignore_validate = True
	doc.flags.ignore_mandatory = True
	doc.insert(ignore_permissions=True)
	frappe.db.set_value("Salary Structure", doc.name, "docstatus", 1)
	return doc.name


def _make_ssa(cl, company, structure, basic=10000, hra=2000):
	_ensure_component("Basic", "Earning")
	_ensure_component("House Rent Allowance", "Earning")
	doc = frappe.get_doc(
		{
			"doctype": "Salary Structure Assignment",
			"employee": cl,
			"company": company,
			"salary_structure": structure,
			"from_date": "2024-01-01",
			"to_date": "2025-12-31",
			"currency": "INR",
			"earnings": [
				{"salary_component": "Basic", "amount": basic},
				{"salary_component": "House Rent Allowance", "amount": hra},
			],
		}
	)
	doc.flags.ignore_validate = True
	doc.flags.ignore_mandatory = True
	doc.insert(ignore_permissions=True)
	frappe.db.set_value("Salary Structure Assignment", doc.name, "docstatus", 1)
	return doc.name


def _make_slip(
	cl,
	company,
	*,
	docstatus=1,
	basic_earn=9000,
	hra_earn=1800,
	incentive=500,
	pf=1080,
	present=26,
	absent=2,
	payment_days=28,
	employee_name="Test Emp",
):
	_ensure_component("Basic", "Earning")
	_ensure_component("House Rent Allowance", "Earning")
	_ensure_component("Incentive", "Earning")
	_ensure_component("Employee PF", "Deduction")

	ss = frappe.new_doc("Salary Slip")
	ss.employee = cl
	ss.employee_name = employee_name
	ss.company = company
	ss.start_date = "2024-06-01"
	ss.end_date = "2024-06-30"
	ss.payment_days = payment_days
	ss.present_days = present
	ss.absent_days = absent
	ss.weekly_offs_taken = 4
	ss.holidays_taken = 1
	ss.total_casual_leaves = 0
	ss.total_on_tour = 0
	ss.total_comp_off = 1
	ss.total_earned_leaves = 0
	ss.total_half_days = 2
	ss.total_earned_comp_off = 1
	ss.total_lwp = 1
	ss.total_earnings = basic_earn + hra_earn + incentive
	ss.total_deductions = pf
	ss.net_salary = ss.total_earnings - ss.total_deductions
	ss.currency = "INR"

	for comp, amt in (
		("Basic", basic_earn),
		("House Rent Allowance", hra_earn),
		("Incentive", incentive),
	):
		row = ss.append("earnings", {})
		row.salary_component = comp
		row.amount = amt

	row = ss.append("deductions", {})
	row.salary_component = "Employee PF"
	row.amount = pf

	ss.flags.ignore_validate = True
	ss.flags.ignore_mandatory = True
	ss.insert(ignore_permissions=True)
	frappe.db.set_value(
		"Salary Slip",
		ss.name,
		{
			"docstatus": docstatus,
			"employee_name": employee_name,
			"payment_days": payment_days,
			"present_days": present,
			"absent_days": absent,
			"weekly_offs_taken": 4,
			"holidays_taken": 1,
			"total_comp_off": 1,
			"total_earnings": basic_earn + hra_earn + incentive,
			"total_deductions": pf,
			"net_salary": basic_earn + hra_earn + incentive - pf,
		},
		update_modified=False,
	)
	return ss.name


class TestMonthlySalaryRegister(FrappeTestCase):
	def test_submitted_only_and_population_filter(self):
		company = _make_company()
		structure = _make_structure(company)

		staff_cl = _make_cl(_make_employee(), company, "Staff")
		worker_cl = _make_cl(_make_employee(), company, "Worker")
		_make_ssa(staff_cl, company, structure)
		_make_ssa(worker_cl, company, structure)
		_make_slip(staff_cl, company, employee_name="Alpha Staff")
		_make_slip(worker_cl, company, employee_name="Beta Worker")
		_make_slip(
			_make_cl(_make_employee(), company, "Staff"),
			company,
			docstatus=0,
			employee_name="Draft Staff",
		)

		all_rows = build_register(
			{"company": company, "year": "2024", "month": "June", "population": "All"}
		)["data"]
		people = [r["employee_name"] for r in all_rows if not r.get("_is_total")]
		self.assertEqual(sorted(people), ["Alpha Staff", "Beta Worker"])

		staff_rows = build_register(
			{"company": company, "year": "2024", "month": "June", "population": "Staff"}
		)["data"]
		staff_people = [r["employee_name"] for r in staff_rows if not r.get("_is_total")]
		self.assertEqual(staff_people, ["Alpha Staff"])

	def test_day_codes_and_actual_vs_earning_split(self):
		company = _make_company()
		structure = _make_structure(company)
		cl = _make_cl(_make_employee(bank="HDFC", ifsc="HDFC0001", acct="998877"), company)
		_make_ssa(cl, company, structure, basic=10000, hra=2000)
		_make_slip(cl, company, employee_name="Code Emp")

		payload = build_register(
			{"company": company, "year": "2024", "month": "June", "population": "All"}
		)
		rows = [r for r in payload["data"] if not r.get("_is_total")]
		self.assertEqual(len(rows), 1)
		row = rows[0]

		self.assertEqual(row["bank_name"], "HDFC")
		self.assertEqual(row["ifsc"], "HDFC0001")
		self.assertEqual(row["bank_account"], "998877")
		self.assertEqual(row["day_p"], 26)
		self.assertEqual(row["day_a"], 2)
		self.assertEqual(row["day_y"], 1)
		self.assertIsNone(row["day_od"])
		self.assertIsNone(row["day_i"])
		self.assertEqual(row["total_paid_days"], 28)
		# Half day / ECO / LWP not folded into shown codes
		self.assertNotIn("day_hd", row)

		self.assertEqual(row[_act_fn("Basic")], 10000)
		self.assertEqual(row[_act_fn("House Rent Allowance")], 2000)
		self.assertEqual(row["total_gross"], 12000)

		self.assertEqual(row[_earn_fn("Basic")], 9000)
		self.assertEqual(row[_earn_fn("Incentive")], 500)
		self.assertEqual(row["total_earning"], 11300)
		self.assertEqual(row[_ded_fn("Employee PF")], 1080)
		self.assertEqual(row["net_payable"], 10220)

		# ACTUAL should not expose Incentive column
		act_fns = {_act_fn(c) for c in payload["meta"]["actual_comps"]}
		self.assertNotIn(_act_fn("Incentive"), act_fns)
		# Earning union includes Incentive
		self.assertIn("Incentive", payload["meta"]["earn_comps"])

	def test_totals_row(self):
		company = _make_company()
		structure = _make_structure(company)
		for i, name in enumerate(("A Emp", "B Emp")):
			cl = _make_cl(_make_employee(), company)
			_make_ssa(cl, company, structure, basic=10000 + i, hra=1000)
			_make_slip(cl, company, employee_name=name, basic_earn=8000, incentive=0, pf=100)

		payload = build_register(
			{"company": company, "year": "2024", "month": "June", "population": "All"}
		)
		tot = payload["data"][-1]
		self.assertEqual(tot["_is_total"], 1)
		self.assertEqual(tot["employee_name"], "Total")
		self.assertEqual(tot["net_payable"], payload["data"][0]["net_payable"] + payload["data"][1]["net_payable"])

	def test_compressed_format_ten_columns_and_totals(self):
		company = _make_company()
		structure = _make_structure(company)
		cl = _make_cl(_make_employee(bank="HDFC", ifsc="HDFC0001", acct="998877"), company)
		_make_ssa(cl, company, structure, basic=10000, hra=2000)
		_make_slip(cl, company, employee_name="Comp Emp")

		full = build_register(
			{
				"company": company,
				"year": "2024",
				"month": "June",
				"population": "All",
				"format": "Full",
			}
		)
		compressed = build_register(
			{
				"company": company,
				"year": "2024",
				"month": "June",
				"population": "All",
				"format": "Compressed",
			}
		)

		labels = [c["label"] for c in compressed["columns"]]
		self.assertEqual(
			labels,
			[
				"Full<br>Name",
				"IFSC<br>Code",
				"Account<br>Number",
				"Days in<br>Month",
				"Paid For<br>Days",
				"Actual<br>Gross",
				"Earning<br>Gross",
				"Deductions",
				"Net<br>Payable",
			],
		)
		self.assertEqual(len(compressed["columns"]), 9)
		self.assertNotIn("sr_no", [c["fieldname"] for c in compressed["columns"]])
		self.assertEqual(compressed["meta"]["format"], "Compressed")

		from saral_hr.saral_hr.report.monthly_salary_register_old_format_net_payable.monthly_salary_register_old_format_net_payable import (
			_fmt_paid_days,
		)

		self.assertEqual(_fmt_paid_days(28.0), "28")
		self.assertEqual(_fmt_paid_days(28.5), "28.5")
		self.assertEqual(_fmt_paid_days(287.5), "287.5")

		tot = [r for r in compressed["data"] if r.get("_is_total")][0]
		self.assertEqual(tot["total_paid_days"], "")
		self.assertTrue(tot["total_gross"] > 0)

		full_row = [r for r in full["data"] if not r.get("_is_total")][0]
		row = [r for r in compressed["data"] if not r.get("_is_total")][0]
		self.assertEqual(row["ifsc"], "HDFC0001")
		self.assertEqual(row["bank_account"], "998877")
		self.assertNotIn("bank_name", row)
		self.assertNotIn("day_p", row)
		self.assertEqual(row["total_gross"], full_row["total_gross"])
		self.assertEqual(row["total_earning"], full_row["total_earning"])
		self.assertEqual(row["total_deductions"], full_row["total_deductions"])
		self.assertEqual(row["net_payable"], full_row["net_payable"])
		self.assertEqual(row["total_paid_days"], full_row["total_paid_days"])
		self.assertEqual(row["total_month_day"], 30)

	def test_default_sort_by_employee_id(self):
		company = _make_company()
		structure = _make_structure(company)
		# Create in reverse name order but assert rows follow Employee name (id)
		emps = []
		for label in ("Zed", "Amy"):
			emp = _make_employee()
			emps.append(emp)
			cl = _make_cl(emp, company)
			_make_ssa(cl, company, structure, basic=10000, hra=1000)
			_make_slip(cl, company, employee_name=f"{label} Person")

		payload = build_register(
			{"company": company, "year": "2024", "month": "June", "population": "All"}
		)
		rows = [r for r in payload["data"] if not r.get("_is_total")]
		expected_order = sorted(emps)
		name_by_emp = {}
		for emp, label in zip(emps, ("Zed", "Amy")):
			name_by_emp[emp] = f"{label} Person"
		self.assertEqual(
			[r["employee_name"] for r in rows],
			[name_by_emp[e] for e in expected_order],
		)

	def test_pdf_colgroup_uses_proportional_widths(self):
		from saral_hr.saral_hr.report.monthly_salary_register_old_format_net_payable.monthly_salary_register_old_format_net_payable import (
			_build_html,
			_colgroup_html,
			_compressed_columns,
			_columns_for_export,
		)
		import re

		cols = _columns_for_export(
			{"columns": _compressed_columns(), "meta": {"format": "Compressed"}}
		)
		html = _colgroup_html(cols)
		self.assertIn("<colgroup>", html)
		self.assertEqual(html.count("<col "), len(cols))
		pcts = [float(x) for x in re.findall(r"width:([0-9.]+)%", html)]
		ifsc_i = next(i for i, c in enumerate(cols) if c["fieldname"] == "ifsc")
		days_i = next(i for i, c in enumerate(cols) if c["fieldname"] == "total_month_day")
		self.assertGreater(pcts[ifsc_i], pcts[days_i])

		payload = {
			"columns": _compressed_columns(),
			"data": [],
			"meta": {
				"company": "X",
				"format": "Compressed",
				"month_days": 30,
			},
		}
		full_html = _build_html(payload)
		self.assertIn("<colgroup>", full_html)
		self.assertIn("table-layout:fixed", full_html)
