from datetime import date

import frappe
from frappe.tests.utils import FrappeTestCase

from saral_hr.utils.period import PERIOD_YEAR_MIN, period_year_max, validate_period_year


class TestPeriodPicker(FrappeTestCase):
	def test_period_year_max_is_current_plus_one(self):
		self.assertEqual(period_year_max(), date.today().year + 1)

	def test_validate_period_year_accepts_floor(self):
		self.assertEqual(validate_period_year(PERIOD_YEAR_MIN), PERIOD_YEAR_MIN)

	def test_validate_period_year_accepts_ceiling(self):
		self.assertEqual(validate_period_year(period_year_max()), period_year_max())

	def test_validate_period_year_rejects_before_floor(self):
		with self.assertRaises(frappe.ValidationError):
			validate_period_year(PERIOD_YEAR_MIN - 1)

	def test_validate_period_year_rejects_after_ceiling(self):
		with self.assertRaises(frappe.ValidationError):
			validate_period_year(period_year_max() + 1)

	def test_additional_salary_rejects_pre_2024_year(self):
		doc = frappe.get_doc(
			{
				"doctype": "Additional Salary",
				"employee": "_test_employee_period",
				"year": "2023",
				"month": "January",
				"components": [],
			}
		)
		with self.assertRaises(frappe.ValidationError):
			doc.validate()

	def test_variable_pay_assignment_rejects_pre_2024_year(self):
		doc = frappe.get_doc(
			{
				"doctype": "Variable Pay Assignment",
				"year": 2023,
				"month": "January",
			}
		)
		with self.assertRaises(frappe.ValidationError):
			doc.validate()
