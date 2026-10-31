# Copyright (c) 2026, sj and Contributors
# See license.txt

import io
import zipfile

from frappe.tests.utils import FrappeTestCase

from saral_hr.saral_hr.report.employee_salary_history.employee_salary_history import (
	_build_html,
	_build_workbook,
	_columns_for_export,
	_export_width,
	_silence_number_stored_as_text,
)


def _full_thin_border(cell):
	border = cell.border
	return all(
		getattr(border, side) is not None and getattr(border, side).style == "thin"
		for side in ("left", "right", "top", "bottom")
	)


def _excel_fixture():
	columns = [
		{
			"label": "Months",
			"fieldname": "month_year",
			"fieldtype": "Data",
			"esh_group": "Months",
		},
		{
			"label": "BASIC\nDA",
			"fieldname": "act_basic",
			"fieldtype": "Data",
			"esh_group": "Actual Earning",
			"esh_stack": [
				{"fieldname": "act_basic", "label": "BASIC"},
				{"fieldname": "act_da", "label": "DA"},
			],
		},
		{
			"label": "VAR",
			"fieldname": "act_var",
			"fieldtype": "Data",
			"esh_group": "Actual Earning",
			"esh_stack": [{"fieldname": "act_var", "label": "VAR"}],
		},
		{
			"label": "Total",
			"fieldname": "total_gross",
			"fieldtype": "Currency",
			"esh_group": "Actual Earning",
		},
		{
			"label": "",
			"fieldname": "paid_days",
			"fieldtype": "Float",
			"esh_group": "Paid Days",
		},
		{
			"label": "Net Payable",
			"fieldname": "net_payable",
			"fieldtype": "Currency",
			"esh_group": "Net Payable",
		},
	]
	rows = [
		{
			"month_year": "Jul-24",
			"act_basic": 6350.0,
			"act_da": 6000.0,
			"act_var": 0.0,
			"total_gross": 23050.0,
			"paid_days": 31,
			"net_payable": 20856.0,
		}
	]
	meta = {
		"company": "Test Co",
		"employee_name": "Ada",
		"employee": "EMP-1",
		"period": "Full History",
	}
	return columns, rows, meta


class TestEmployeeSalaryHistoryExcel(FrappeTestCase):
	def test_paired_stack_stays_two_lines_leftover_is_number(self):
		wb = _build_workbook(*_excel_fixture())
		ws = wb.active
		# Group + sub header occupy rows 5-6; first data row is 7.
		stacked = ws.cell(7, 2)
		self.assertIsInstance(stacked.value, str)
		self.assertIn("\n", stacked.value)
		self.assertIn("6,350.00", stacked.value)
		self.assertIn("6,000.00", stacked.value)

		var = ws.cell(7, 3)
		self.assertIsInstance(var.value, (int, float))
		self.assertEqual(var.value, 0.0)
		self.assertEqual(var.number_format, "#,##0.00")

		total = ws.cell(7, 4)
		self.assertIsInstance(total.value, (int, float))
		self.assertEqual(total.value, 23050.0)

		self.assertEqual(ws.cell(7, 5).value, 31)
		self.assertEqual(ws.cell(7, 1).value, "Jul-24")
		self.assertEqual(ws.cell(7, 6).value, 20856.0)

	def test_single_group_header_keeps_full_border(self):
		wb = _build_workbook(*_excel_fixture())
		ws = wb.active
		# Months col 1 and Net Payable col 6 merge header rows 5-6.
		# Excel draws the outline from every cell in the merge.
		for col in (1, 6):
			self.assertTrue(_full_thin_border(ws.cell(5, col)))
			self.assertTrue(_full_thin_border(ws.cell(6, col)))

	def test_export_pairs_deduction_and_additional_keeps_totals(self):
		cols = [
			{
				"label": "EMP-ESI",
				"fieldname": "ded_esi",
				"fieldtype": "Currency",
				"esh_group": "Deduction",
			},
			{
				"label": "EMP-PF",
				"fieldname": "ded_pf",
				"fieldtype": "Currency",
				"esh_group": "Deduction",
			},
			{
				"label": "PT",
				"fieldname": "ded_pt",
				"fieldtype": "Currency",
				"esh_group": "Deduction",
			},
			{
				"label": "LOAN",
				"fieldname": "ded_loan",
				"fieldtype": "Currency",
				"esh_group": "Deduction",
			},
			{
				"label": "Total",
				"fieldname": "total_deductions",
				"fieldtype": "Currency",
				"esh_group": "Deduction",
			},
			{
				"label": "Production Incentive",
				"fieldname": "add_earn_pi",
				"fieldtype": "Currency",
				"esh_group": "Additional Salary",
			},
			{
				"label": "Additional Salary",
				"fieldname": "add_earn_as",
				"fieldtype": "Currency",
				"esh_group": "Additional Salary",
			},
			{
				"label": "Total",
				"fieldname": "total_additional_salary",
				"fieldtype": "Currency",
				"esh_group": "Additional Salary",
			},
		]
		out = _columns_for_export(cols)
		ded = [c for c in out if c.get("esh_group") == "Deduction"]
		self.assertEqual(len(ded), 3)
		self.assertEqual([p["fieldname"] for p in ded[0]["esh_stack"]], ["ded_esi", "ded_pf"])
		self.assertEqual([p["fieldname"] for p in ded[1]["esh_stack"]], ["ded_pt", "ded_loan"])
		self.assertEqual(ded[2]["fieldname"], "total_deductions")
		self.assertFalse(ded[2].get("esh_stack"))

		add = [c for c in out if c.get("esh_group") == "Additional Salary"]
		self.assertEqual(len(add), 2)
		self.assertEqual(
			[p["fieldname"] for p in add[0]["esh_stack"]],
			["add_earn_pi", "add_earn_as"],
		)
		self.assertEqual(add[1]["fieldname"], "total_additional_salary")

	def test_pdf_headers_do_not_letter_break_paid_days_stays_wide(self):
		self.assertGreaterEqual(_export_width({"fieldname": "paid_days"}), 36)
		html = _build_html(*_excel_fixture())
		self.assertNotIn("word-wrap:break-word", html)
		self.assertIn("word-break:normal", html)
		self.assertIn("Paid<br>Days", html)

	def test_excel_amounts_stay_right_and_paid_days_wide_enough(self):
		wb = _build_workbook(*_excel_fixture())
		ws = wb.active
		self.assertEqual(ws.cell(7, 1).alignment.horizontal, "left")
		for col in range(2, 7):
			self.assertEqual(ws.cell(7, col).alignment.horizontal, "right")
		self.assertGreaterEqual(ws.column_dimensions["E"].width, 10)

	def test_xlsx_ignores_number_stored_as_text(self):
		wb = _build_workbook(*_excel_fixture())
		buf = io.BytesIO()
		wb.save(buf)
		patched = _silence_number_stored_as_text(buf.getvalue())
		with zipfile.ZipFile(io.BytesIO(patched)) as zf:
			sheet = zf.read("xl/worksheets/sheet1.xml")
		self.assertIn(b'numberStoredAsText="1"', sheet)
		self.assertIn(b'sqref="A1:ZZ9999"', sheet)
