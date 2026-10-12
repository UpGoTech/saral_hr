# Copyright (c) 2026, sj and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today

from saral_hr.saral_hr.page.generate_monthly_loan_dues.generate_monthly_loan_dues import save_dues


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
			"company": f"_Test GLD {uid}",
			"abbr": f"G{uid}"[:8],
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
			"first_name": f"Gld{_uid()}",
			"gender": "Other",
			"date_of_birth": "1990-01-01",
		}
	)
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
			"is_active": 1,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _make_loan(cl: str, company: str, full_name: str):
	loan = frappe.get_doc(
		{
			"doctype": "Employee Loan",
			"employee": cl,
			"full_name": full_name,
			"company": company,
			"loan_date": today(),
			"amount": 50000,
			"reason": "gld zero save",
			"expected_emi": 5000,
			"start_month": "April",
			"start_year": "2024",
			"proposed_tenure_months": 10,
		}
	)
	loan.insert(ignore_permissions=True)
	loan.submit()
	return loan


class TestEmployeeLoanDue(FrappeTestCase):
	def test_save_dues_persists_zero_amount_as_skipped(self):
		"""Zero installment is valid (Skipped). Desktop save used to send the old EMI instead."""
		company = _make_company()
		employee = _make_employee()
		cl = _make_company_link(employee, company)
		full_name = frappe.db.get_value("Company Link", cl, "full_name") or employee
		loan = _make_loan(cl, company, full_name)

		due = frappe.get_doc(
			{
				"doctype": "Employee Loan Due",
				"employee": cl,
				"loan": loan.name,
				"company": company,
				"month": "April 2024",
				"year": 2024,
				"amount": 5000,
				"status": "Pending",
			}
		)
		due.insert(ignore_permissions=True)

		out = save_dues(
			rows=[{"name": due.name, "amount": 0, "remarks": "skip april"}],
			company=company,
			month="April",
			year=2024,
		)
		self.assertEqual(out.get("updated"), 1)

		saved = frappe.db.get_value(
			"Employee Loan Due", due.name, ["amount", "status", "remarks"], as_dict=True
		)
		self.assertEqual(float(saved.amount), 0)
		self.assertEqual(saved.status, "Skipped")
		self.assertEqual(saved.remarks, "skip april")
