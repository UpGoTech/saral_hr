# Copyright (c) 2026, sj and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today


class TestEmployeeLoan(FrappeTestCase):
	def test_calculate_outstanding_never_nulls_months_remaining(self):
		doc = frappe.new_doc("Employee Loan")
		doc.amount = 10000
		doc.expected_emi = 0
		doc.prepayments = []
		doc.name = "TEST-LOAN-NULL-MONTHS"
		doc.calculate_outstanding()
		self.assertEqual(doc.expected_months_remaining, 0)

		doc.expected_emi = 2000
		doc.calculate_outstanding()
		self.assertEqual(doc.expected_months_remaining, 5)

	def test_recalc_after_slip_does_not_write_null_months(self):
		from saral_hr.saral_hr.doctype.salary_slip.salary_slip import _recalc_loan_outstanding

		emp = frappe.db.get_value("Company Link", {"company": ["!=", ""]}, "name")
		if not emp:
			self.skipTest("No Company Link")

		company = frappe.db.get_value("Company Link", emp, "company")
		full_name = frappe.db.get_value("Company Link", emp, "full_name") or emp
		loan = frappe.get_doc(
			{
				"doctype": "Employee Loan",
				"employee": emp,
				"full_name": full_name,
				"company": company,
				"loan_date": today(),
				"amount": 1000,
				"reason": "null months regression",
				"expected_emi": 250,
				"start_month": "August",
				"start_year": "2026",
				"proposed_tenure_months": 4,
			}
		)
		loan.insert()
		loan.submit()

		# Reproduce pre-fix path: months forced to None on the doc object
		loan.expected_months_remaining = None
		loan.expected_emi = 0
		loan.calculate_outstanding()
		self.assertEqual(loan.expected_months_remaining, 0)

		_recalc_loan_outstanding(loan.name)
		months = frappe.db.get_value("Employee Loan", loan.name, "expected_months_remaining")
		self.assertIsNotNone(months)
		self.assertGreaterEqual(int(months), 0)
