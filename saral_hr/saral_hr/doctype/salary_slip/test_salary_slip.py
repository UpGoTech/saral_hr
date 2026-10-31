# Copyright (c) 2026, sj and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, get_first_day, get_last_day, getdate

from saral_hr.saral_hr.doctype.salary_slip.salary_slip import (
	calculate_salary_slip_amounts_exact,
	get_attendance_and_days,
	get_eligible_employees_for_salary_slip,
	get_salary_amount_rounding_digits,
	round_salary_amount,
)


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
			"company": f"_Test SS Days {uid}",
			"abbr": f"S{uid}"[:8],
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
			"first_name": f"SSDays{_uid()}",
			"gender": "Other",
			"date_of_birth": "1990-01-01",
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _make_company_link(employee: str, company: str, joining, weekly_off="Sunday"):
	doc = frappe.get_doc(
		{
			"doctype": "Company Link",
			"employee": employee,
			"company": company,
			"category": _ensure_category(),
			"date_of_joining": getdate(joining),
			"weekly_off": weekly_off,
			"is_active": 1,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _mark(employee: str, day, status: str):
	doc = frappe.get_doc(
		{
			"doctype": "Attendance",
			"employee": employee,
			"attendance_date": getdate(day),
			"status": status,
		}
	)
	doc.flags.ignore_validate = True
	doc.flags.ignore_mandatory = True
	doc.insert(ignore_permissions=True)


class TestSalarySlipWorkingDays(FrappeTestCase):
	def test_mid_month_join_uses_full_month_working_days(self):
		"""Working days must be the full month, not joining→month-end."""
		company = _make_company()
		employee = _make_employee()
		joining = getdate("2024-06-10")
		cl = _make_company_link(employee, company, joining, weekly_off="")
		start = get_first_day(joining)
		end = get_last_day(joining)
		month_days = (end - start).days + 1

		# Pre-join Absents + Present from joining onward
		d = start
		while d < joining:
			_mark(cl, d, "Absent")
			d = add_days(d, 1)
		d = joining
		while d <= end:
			_mark(cl, d, "Present")
			d = add_days(d, 1)

		att = get_attendance_and_days(cl, str(start), "Exclude Weekly Offs (Working Days)")

		self.assertEqual(att["total_days"], month_days)
		self.assertEqual(att["working_days"], float(month_days))
		# Must NOT equal only the post-joining slice
		post_join_days = (end - joining).days + 1
		self.assertNotEqual(att["working_days"], float(post_join_days))
		self.assertEqual(att["present_days"], float(post_join_days))
		self.assertEqual(att["absent_days"], float(month_days - post_join_days))
		self.assertEqual(att["payment_days"], float(post_join_days))


class TestSalaryAmountRounding(FrappeTestCase):
	def test_rounding_digits_helper(self):
		company = _make_company()
		frappe.db.set_value("Company", company, "salary_amount_rounding_digits", "0")
		self.assertEqual(get_salary_amount_rounding_digits(company), 0)
		self.assertEqual(round_salary_amount(10.6, company), 11.0)
		self.assertEqual(round_salary_amount(10.4, company), 10.0)

		frappe.db.set_value("Company", company, "salary_amount_rounding_digits", "2")
		self.assertEqual(get_salary_amount_rounding_digits(company), 2)
		self.assertEqual(round_salary_amount(10.456, company), 10.46)

		self.assertEqual(get_salary_amount_rounding_digits(None), 2)

	def test_calculate_uses_company_rounding_digits(self):
		company = _make_company()
		frappe.db.set_value("Company", company, "salary_amount_rounding_digits", "0")
		employee = _make_employee()
		cl = _make_company_link(employee, company, "2024-01-01", weekly_off="")

		ss = frappe.new_doc("Salary Slip")
		ss.employee = cl
		ss.company = company
		ss.start_date = "2024-01-01"
		ss.end_date = "2024-01-31"
		ss.total_working_days = 30
		ss.payment_days = 15
		ss.physical_working_days = 15
		row = ss.append("earnings", {})
		row.salary_component = "Basic"
		row.abbr = "BASIC"
		row.base_amount = 10000
		row.amount = 10000
		row.depends_on_payment_days = 1
		row.depends_on_physical_working_days = 0

		calculate_salary_slip_amounts_exact(ss, 0, "2024-01-01")
		# 10000 * 15/30 = 5000 exactly; use a non-integer case via payment_days
		ss.payment_days = 10
		calculate_salary_slip_amounts_exact(ss, 0, "2024-01-01")
		# 10000 * 10/30 = 3333.333... → rounds to 3333 with digits=0
		self.assertEqual(ss.earnings[0].amount, 3333.0)

		frappe.db.set_value("Company", company, "salary_amount_rounding_digits", "2")
		calculate_salary_slip_amounts_exact(ss, 0, "2024-01-01")
		self.assertEqual(ss.earnings[0].amount, 3333.33)


def _ids_from_eligible_result(result):
	ids = {row.get("name") for row in result.get("eligible") or []}
	for bucket in ("skipped", "already_generated"):
		for row in result.get(bucket) or []:
			ids.add(row.get("id"))
	return ids


class TestBulkEligibleLeftEmployees(FrappeTestCase):
	def test_left_employee_included_only_for_overlapping_months(self):
		"""Left employees must appear for months within tenure, not after left_date."""
		company = _make_company()
		employee = _make_employee()
		cl = _make_company_link(employee, company, "2024-01-01", weekly_off="")
		doc = frappe.get_doc("Company Link", cl)
		doc.left_date = getdate("2024-03-15")
		doc.save(ignore_permissions=True)
		self.assertEqual(frappe.db.get_value("Company Link", cl, "is_active"), 0)

		march = get_eligible_employees_for_salary_slip(company, "2024", "March")
		self.assertIn(cl, _ids_from_eligible_result(march))
		self.assertEqual(march["total_active"], 1)

		april = get_eligible_employees_for_salary_slip(company, "2024", "April")
		self.assertNotIn(cl, _ids_from_eligible_result(april))
		self.assertEqual(april["total_active"], 0)


def _skipped_reasons(result, employee_id):
	for row in result.get("skipped") or []:
		if row.get("id") == employee_id:
			return row.get("reasons") or []
	return None


class TestBulkEligibleLoanDues(FrappeTestCase):
	def test_missing_loan_due_marks_ineligible_until_created(self):
		from saral_hr.saral_hr.doctype.salary_slip.salary_slip import (
			_loan_dues_missing_message,
			employee_missing_loan_dues,
		)

		company = _make_company()
		employee = _make_employee()
		cl = _make_company_link(employee, company, "2024-01-01", weekly_off="")
		full_name = frappe.db.get_value("Company Link", cl, "full_name") or cl

		loan = frappe.get_doc(
			{
				"doctype": "Employee Loan",
				"employee": cl,
				"full_name": full_name,
				"company": company,
				"loan_date": "2024-05-01",
				"amount": 5000,
				"reason": "bulk eligibility loan gate",
				"expected_emi": 1000,
				"start_month": "June",
				"start_year": "2024",
				"proposed_tenure_months": 5,
			}
		)
		loan.insert(ignore_permissions=True)
		loan.submit()

		self.assertTrue(employee_missing_loan_dues(cl, "June", "2024"))
		self.assertFalse(employee_missing_loan_dues(cl, "May", "2024"))

		june = get_eligible_employees_for_salary_slip(company, "2024", "June")
		reasons = _skipped_reasons(june, cl)
		self.assertIsNotNone(reasons)
		self.assertIn(_loan_dues_missing_message("June", "2024"), reasons)

		due = frappe.get_doc(
			{
				"doctype": "Employee Loan Due",
				"employee": cl,
				"loan": loan.name,
				"company": company,
				"month": "June 2024",
				"year": 2024,
				"amount": 0,
				"status": "Skipped",
			}
		)
		due.insert(ignore_permissions=True)

		self.assertFalse(employee_missing_loan_dues(cl, "June", "2024"))
		june_after = get_eligible_employees_for_salary_slip(company, "2024", "June")
		reasons_after = _skipped_reasons(june_after, cl)
		loan_msg = _loan_dues_missing_message("June", "2024")
		if reasons_after is None:
			self.assertIn(cl, {e.name for e in june_after.get("eligible") or []})
		else:
			self.assertNotIn(loan_msg, reasons_after)


class TestBulkPrintPdf(FrappeTestCase):
	def test_offline_print_html_drops_stylesheets_keeps_inline_css(self):
		from saral_hr.utils.pdf import offline_print_html

		html = (
			"<html><head>"
			'<link type="text/css" rel="stylesheet" href="https://hrms.example.com/assets/frappe/dist/css/print.bundle.css">'
			"<style>.payslip-container { border: 1px solid #000; }</style>"
			'</head><body><div class="payslip-container">Pay</div></body></html>'
		)
		out = offline_print_html(html)
		self.assertNotIn("print.bundle.css", out)
		self.assertNotIn("<link", out.lower())
		self.assertIn(".payslip-container", out)
		self.assertIn("Pay", out)

	def test_salary_slip_pdf_strips_stylesheets_before_wkhtmltopdf(self):
		from unittest.mock import patch

		from saral_hr.saral_hr.doctype.salary_slip.salary_slip import _salary_slip_pdf

		html = (
			'<html><head><link rel="stylesheet" href="https://hrms.fabrixcel.com/assets/print.bundle.css">'
			"<style>.payslip{}</style></head><body>slip</body></html>"
		)
		with patch("frappe.get_print", return_value=html), patch(
			"saral_hr.saral_hr.doctype.salary_slip.salary_slip.get_pdf", return_value=b"%PDF-1.4"
		) as get_pdf:
			_salary_slip_pdf("SS-1")

		passed_html = get_pdf.call_args[0][0]
		self.assertNotIn("print.bundle.css", passed_html)
		self.assertNotIn("<link", passed_html.lower())
		self.assertIn(".payslip", passed_html)

	def test_download_pdf_override_is_hooked(self):
		self.assertEqual(
			frappe.override_whitelisted_method("frappe.utils.print_format.download_pdf"),
			"saral_hr.utils.pdf.download_pdf",
		)

	def test_form_download_pdf_strips_stylesheets_before_wkhtmltopdf(self):
		from unittest.mock import MagicMock, patch

		from saral_hr.utils.pdf import download_pdf

		html = (
			'<html><head><link rel="stylesheet" href="https://hrms.fabrixcel.com/assets/print.bundle.css">'
			"<style>.payslip{}</style></head><body>slip</body></html>"
		)
		with (
			patch("frappe.get_doc", return_value=MagicMock()),
			patch("saral_hr.utils.pdf.validate_print_permission"),
			patch("frappe.get_print", return_value=html),
			patch("saral_hr.utils.pdf.get_pdf", return_value=b"%PDF-1.4") as get_pdf,
		):
			download_pdf("Salary Slip", "SS-1", format="Salary Slip Custom")

		passed_html = get_pdf.call_args[0][0]
		self.assertNotIn("print.bundle.css", passed_html)
		self.assertNotIn("<link", passed_html.lower())
		self.assertIn(".payslip", passed_html)
		self.assertEqual(frappe.local.response.type, "pdf")
		self.assertEqual(frappe.local.response.filecontent, b"%PDF-1.4")
		self.assertEqual(frappe.local.response.filename, "SS-1.pdf")
		self.assertNotIn(".vert-label", passed_html)
		self.assertNotIn("width:1%!important", passed_html)
		self.assertIsNone((get_pdf.call_args[1].get("options") or {}).get("zoom"))

	def test_offline_print_html_muster_injects_layout_and_wraps_headers(self):
		from saral_hr.utils.pdf import MUSTER_CUM_WAGES_SLIP, offline_print_html

		html = (
			"<html><head>"
			'<link rel="stylesheet" href="https://example.com/print.bundle.css">'
			"</head><body>"
			'<div class="action-banner print-hide">Print Get PDF</div>'
			'<div class="print-block"><div class="card">'
			'<th class="col-vert">In time</th>'
			'<th class="col-vert col-ot">Overtime</th>'
			'</div><div class="sign-row">Signature</div></div>'
			"</body></html>"
		)
		out = offline_print_html(html, print_format=MUSTER_CUM_WAGES_SLIP)
		self.assertNotIn("print.bundle.css", out)
		self.assertNotIn("<link", out.lower())
		self.assertIn(".print-hide,.action-banner{display:none!important}", out)
		self.assertIn("display:table-cell!important", out)
		self.assertIn("width:1%!important", out)
		self.assertIn("width:99%!important", out)
		self.assertIn("margin-left:20mm", out)
		self.assertIn("margin-right:8mm", out)
		self.assertIn("padding:8px 2mm 0!important", out)
		self.assertIn("overflow:hidden!important", out)
		self.assertIn("border-collapse:collapse!important", out)
		self.assertNotIn("border-collapse:separate!important", out)
		self.assertIn("card-frame", out)
		self.assertIn("min-height:7.5mm!important", out)
		self.assertIn(".fline .fl.stack{", out)
		self.assertNotIn("white-space:normal!important", out)
		self.assertIn('class="vert-label"', out)
		self.assertIn('<span class="vert-label">In time</span>', out)
		self.assertIn('<span class="vert-label">Overtime</span>', out)

	def test_offline_print_html_custom_skips_muster_layout(self):
		from saral_hr.utils.pdf import offline_print_html

		html = (
			"<html><head><style>.payslip{}</style></head>"
			'<body><th class="col-vert">In time</th></body></html>'
		)
		out = offline_print_html(html, print_format="Salary Slip Custom")
		self.assertIn(".payslip", out)
		self.assertNotIn("vert-label", out)
		self.assertNotIn("width:1%!important", out)
		self.assertNotIn(".print-hide,.action-banner", out)

	def test_form_download_pdf_muster_injects_layout_and_zoom(self):
		from unittest.mock import MagicMock, patch

		from saral_hr.utils.pdf import MUSTER_CUM_WAGES_SLIP, download_pdf

		html = (
			'<html><head><link rel="stylesheet" href="https://hrms.fabrixcel.com/assets/print.bundle.css">'
			"</head><body>"
			'<th class="col-vert">Out time</th>'
			"</body></html>"
		)
		with (
			patch("frappe.get_doc", return_value=MagicMock()),
			patch("saral_hr.utils.pdf.validate_print_permission"),
			patch("frappe.get_print", return_value=html),
			patch("saral_hr.utils.pdf.get_pdf", return_value=b"%PDF-1.4") as get_pdf,
		):
			download_pdf("Salary Slip", "SS-1", format=MUSTER_CUM_WAGES_SLIP)

		passed_html = get_pdf.call_args[0][0]
		options = get_pdf.call_args[1]["options"]
		self.assertNotIn("print.bundle.css", passed_html)
		self.assertIn(".print-hide,.action-banner{display:none!important}", passed_html)
		self.assertIn("display:table-cell!important", passed_html)
		self.assertIn('<span class="vert-label">Out time</span>', passed_html)
		self.assertEqual(options.get("zoom"), "0.9")
		self.assertEqual(frappe.local.response.type, "pdf")


class TestAttendanceRecordPrintContext(FrappeTestCase):
	def test_pairs_split_days_and_status(self):
		company = _make_company()
		employee = _make_employee()
		cl = _make_company_link(employee, company, "2026-08-01", weekly_off="")

		present = frappe.get_doc(
			{
				"doctype": "Attendance",
				"employee": cl,
				"attendance_date": "2026-08-01",
				"status": "Present",
				"in_time": "2026-08-01 09:15:00",
				"out_time": "2026-08-01 18:00:00",
				"working_hours": 8.5,
			}
		)
		present.flags.ignore_validate = True
		present.flags.ignore_mandatory = True
		present.insert(ignore_permissions=True)
		_mark(cl, "2026-08-02", "Weekly Off")

		slip = frappe.new_doc("Salary Slip")
		slip.employee = cl
		slip.start_date = "2026-08-01"
		slip.end_date = "2026-08-31"
		rec = slip.get_attendance_record_print_context()

		self.assertEqual(len(rec.pairs), 16)
		self.assertEqual(rec.pairs[0].left.day, "1")
		self.assertEqual(rec.pairs[0].left.in_time, "09:15")
		self.assertEqual(rec.pairs[0].left.out_time, "18:00")
		self.assertEqual(rec.pairs[0].left.status, "")
		self.assertEqual(rec.pairs[0].left.total_hours, "8.5")
		self.assertEqual(rec.pairs[0].right.day, "17")
		self.assertEqual(rec.pairs[1].left.day, "2")
		self.assertEqual(rec.pairs[1].left.status, "Weekly Off")
		self.assertEqual(rec.pairs[15].left.day, "16")
		self.assertEqual(rec.pairs[15].right.day, "TOTAL")
		self.assertEqual(rec.pairs[15].right.total_hours, "8.5")
