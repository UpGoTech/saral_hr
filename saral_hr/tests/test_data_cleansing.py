# Copyright (c) 2026, sj and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import getdate

from saral_hr.saral_hr.page.data_cleansing import data_cleansing as dc


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
			"company": f"_Test DC {uid}",
			"abbr": f"D{uid}"[:8],
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
			"first_name": f"DCEmp{_uid()}",
			"gender": "Other",
			"date_of_birth": "1990-01-01",
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _make_company_link(employee: str, company: str, joining, left=None):
	doc = frappe.get_doc(
		{
			"doctype": "Company Link",
			"employee": employee,
			"company": company,
			"category": _ensure_category(),
			"date_of_joining": getdate(joining),
			"left_date": getdate(left) if left else None,
			"is_active": 1,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _make_attendance(cl: str, company: str, attendance_date: str, status: str = "Present"):
	doc = frappe.get_doc(
		{
			"doctype": "Attendance",
			"naming_series": "HR-ATT-.YYYY.-",
			"employee": cl,
			"company": company,
			"attendance_date": attendance_date,
			"status": status,
		}
	)
	doc.flags.ignore_validate = True
	doc.insert(ignore_permissions=True)
	return doc.name


def _stub_slip(cl: str, company: str, start_date: str, docstatus: int = 0) -> str:
	name = f"SS-DC-{_uid()}"
	end = getdate(start_date).replace(day=28)
	frappe.get_doc(
		{
			"doctype": "Salary Slip",
			"name": name,
			"naming_series": "SS-.YYYY.-",
			"employee": cl,
			"employee_name": "DC Test",
			"company": company,
			"start_date": start_date,
			"end_date": str(end),
			"docstatus": docstatus,
			"currency": "INR",
		}
	).db_insert()
	return name


class TestDataCleansing(FrappeTestCase):
	def test_matrix_includes_outside_tenure_months_with_data(self):
		company = _make_company()
		employee = _make_employee()
		cl = _make_company_link(employee, company, "2024-03-01")
		# Attendance before joining
		_make_attendance(cl, company, "2024-01-15")
		# Attendance in tenure
		_make_attendance(cl, company, "2024-03-10")

		result = dc.get_employee_month_matrix(cl, 2024, 1, 2024, 3)
		months = {r["month_label"]: r for r in result["months"]}
		self.assertIn("Jan 2024", months)
		self.assertIn("Mar 2024", months)
		self.assertIn("Outside tenure", months["Jan 2024"]["flags"])
		self.assertEqual(months["Jan 2024"]["expected_days"], 0)
		self.assertGreater(months["Mar 2024"]["expected_days"], 0)

	def test_flags_attendance_only_and_slip_only(self):
		company = _make_company()
		employee = _make_employee()
		cl = _make_company_link(employee, company, "2024-01-01")
		_make_attendance(cl, company, "2024-02-05")
		_stub_slip(cl, company, "2024-03-01", docstatus=0)

		result = dc.get_employee_month_matrix(cl, 2024, 2, 2024, 3)
		by_m = {r["month"]: r for r in result["months"]}
		self.assertIn("Attendance only", by_m[2]["flags"])
		self.assertIn("Slip only", by_m[3]["flags"])
		self.assertIn("Draft slip", by_m[3]["flags"])

	def test_partial_coverage_flag(self):
		company = _make_company()
		employee = _make_employee()
		cl = _make_company_link(employee, company, "2024-04-01")
		_make_attendance(cl, company, "2024-04-02")
		_make_attendance(cl, company, "2024-04-03")

		result = dc.get_employee_month_matrix(cl, 2024, 4, 2024, 4)
		self.assertEqual(len(result["months"]), 1)
		row = result["months"][0]
		self.assertEqual(row["attendance_days"], 2)
		self.assertEqual(row["expected_days"], 30)
		self.assertIn("Partial coverage", row["flags"])
		self.assertEqual(row["coverage"], "Partial")

	def test_attendance_delete_blocked_when_any_slip_exists(self):
		company = _make_company()
		employee = _make_employee()
		cl = _make_company_link(employee, company, "2024-05-01")
		_make_attendance(cl, company, "2024-05-10")
		_stub_slip(cl, company, "2024-05-01", docstatus=0)

		with self.assertRaises(frappe.ValidationError):
			dc.delete_attendance(cl, year=2024, month=5)

		# Cancelled also blocks
		frappe.db.set_value("Salary Slip", frappe.db.get_value("Salary Slip", {"employee": cl}, "name"), "docstatus", 2)
		with self.assertRaises(frappe.ValidationError):
			dc.delete_attendance(cl, year=2024, month=5)

	def test_attendance_delete_succeeds_after_slip_removed(self):
		company = _make_company()
		employee = _make_employee()
		cl = _make_company_link(employee, company, "2024-06-01")
		a1 = _make_attendance(cl, company, "2024-06-01")
		a2 = _make_attendance(cl, company, "2024-06-02")
		slip = _stub_slip(cl, company, "2024-06-01", docstatus=0)

		with self.assertRaises(frappe.ValidationError):
			dc.delete_attendance(cl, year=2024, month=6)

		dc.delete_salary_slip(slip)
		result = dc.delete_attendance(cl, year=2024, month=6)
		self.assertEqual(result["count"], 2)
		self.assertFalse(frappe.db.exists("Attendance", a1))
		self.assertFalse(frappe.db.exists("Attendance", a2))
		self.assertTrue(
			frappe.db.exists(
				"Data Cleansing Log",
				{"employee": cl, "action": "delete_attendance"},
			)
		)

	def test_delete_selected_attendance_days(self):
		company = _make_company()
		employee = _make_employee()
		cl = _make_company_link(employee, company, "2024-07-01")
		keep = _make_attendance(cl, company, "2024-07-01")
		gone = _make_attendance(cl, company, "2024-07-02")

		result = dc.delete_attendance(cl, names=[gone])
		self.assertEqual(result["count"], 1)
		self.assertTrue(frappe.db.exists("Attendance", keep))
		self.assertFalse(frappe.db.exists("Attendance", gone))

	def test_hr_user_cannot_mutate(self):
		company = _make_company()
		employee = _make_employee()
		cl = _make_company_link(employee, company, "2024-08-01")
		_make_attendance(cl, company, "2024-08-05")

		# Create a disposable user with only Saral HR User
		uid = _uid()
		user = f"{uid}@dc.test"
		if not frappe.db.exists("User", user):
			u = frappe.get_doc(
				{
					"doctype": "User",
					"email": user,
					"first_name": "DC User",
					"send_welcome_email": 0,
					"user_type": "System User",
				}
			)
			u.insert(ignore_permissions=True)
			u.add_roles("Saral HR User")

		frappe.set_user(user)
		try:
			# View still works
			matrix = dc.get_employee_month_matrix(cl, 2024, 8, 2024, 8)
			self.assertFalse(matrix["can_mutate"])
			with self.assertRaises(frappe.PermissionError):
				dc.delete_attendance(cl, year=2024, month=8)
		finally:
			frappe.set_user("Administrator")

	def test_delete_draft_slip_writes_log(self):
		company = _make_company()
		employee = _make_employee()
		cl = _make_company_link(employee, company, "2024-09-01")
		slip = _stub_slip(cl, company, "2024-09-01", docstatus=0)
		out = dc.delete_salary_slip(slip)
		self.assertEqual(out["deleted"], slip)
		self.assertTrue(
			frappe.db.exists(
				"Data Cleansing Log",
				{"employee": cl, "action": "delete_salary_slip"},
			)
		)

	def test_empty_months_omitted(self):
		company = _make_company()
		employee = _make_employee()
		cl = _make_company_link(employee, company, "2024-01-01")
		_make_attendance(cl, company, "2024-01-05")
		result = dc.get_employee_month_matrix(cl, 2024, 1, 2024, 3)
		labels = [r["month_label"] for r in result["months"]]
		self.assertEqual(labels, ["Jan 2024"])
