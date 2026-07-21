# Copyright (c) 2026, Saral HR
# Register of Wages Report
#
# Source: Salary Slip (submitted, docstatus=1) for the selected Company/Year/Month,
# joined with Employee for Sex/Age/ESIC No/PF No, and Employee Loan Advance for the
# "Advance" column. PF / ESIC / Professional Tax figures are pulled from the earnings/
# deductions child table (Salary Details) on each Salary Slip.
#
# ============================================================================
# CONFIG — verify these against your actual Salary Component names before use.
# The matching is case-insensitive substring match against salary_component/abbr,
# same pattern already used in professional_tax_register.py and provident_fund_register.py.
# Edit these lists if your component names differ.
# ============================================================================
BASIC_COMPONENT_MATCH = ["basic"]
DA_COMPONENT_MATCH = ["dearness"]  # NOTE: "da" was removed — it false-matched "Daily"/"Attendance"
HRA_COMPONENT_MATCH = ["hra", "house rent"]
MEDICAL_COMPONENT_MATCH = ["medical"]
PT_COMPONENT_MATCH = ["professional tax", "professional"]
ESIC_COMPONENT_MATCH = ["esic", "state insurance", "employee state insurance"]
PF_COMPONENT_MATCH = ["provident fund", "employee pf"]  # excludes "employer pf" explicitly below
EXCLUDE_EMPLOYER_MATCH = ["employer"]

import calendar
import io
import json

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt, getdate

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def validate_filters(filters):
	if not filters.get("company"):
		frappe.throw(_("Company is required"))
	if not filters.get("year"):
		frappe.throw(_("Year is required"))
	if not filters.get("month"):
		frappe.throw(_("Month is required"))


def get_columns():
	return [
		{"fieldname": "employee", "label": _("Employee"), "fieldtype": "Link",
		 "options": "Employee", "width": 120},
		{"fieldname": "employee_name", "label": _("Full Name of Employee"),
		 "fieldtype": "Data", "width": 180},
		{"fieldname": "sex_age", "label": _("Sex/Age"), "fieldtype": "Data", "width": 90},
		{"fieldname": "working_hrs", "label": _("Working Hrs"), "fieldtype": "Data", "width": 90},
		{"fieldname": "esic_no", "label": _("ESIC No."), "fieldtype": "Data", "width": 110},
		{"fieldname": "pf_no", "label": _("PF No."), "fieldtype": "Data", "width": 110},
		{"fieldname": "total_days", "label": _("Total Days"), "fieldtype": "Float",
		 "precision": 1, "width": 80},
		{"fieldname": "min_rate_wages", "label": _("Minimum Rate of Wages Payable"),
		 "fieldtype": "Float", "precision": 2, "width": 150},
		{"fieldname": "actual_rate_wages", "label": _("Actual Rate of Wages Payable"),
		 "fieldtype": "Float", "precision": 2, "width": 150},
		{"fieldname": "total_production", "label": _("Total Production in Case"),
		 "fieldtype": "Data", "width": 130},
		{"fieldname": "total_ot_hours", "label": _("Total Overtime Hours Worked"),
		 "fieldtype": "Float", "precision": 2, "width": 130},
		{"fieldname": "normal_earning", "label": _("Normal Earning"),
		 "fieldtype": "Float", "precision": 2, "width": 110},
		{"fieldname": "da", "label": _("D.A."), "fieldtype": "Float", "precision": 2, "width": 90},
		{"fieldname": "basic_da", "label": _("Basic + DA"), "fieldtype": "Float", "precision": 2, "width": 110},
		{"fieldname": "ot_earning", "label": _("Overtime Earning"),
		 "fieldtype": "Float", "precision": 2, "width": 110},
		{"fieldname": "hra", "label": _("H.R.A."), "fieldtype": "Float", "precision": 2, "width": 90},
		{"fieldname": "medical_allowance", "label": _("Medical Allowance"),
		 "fieldtype": "Float", "precision": 2, "width": 110},
		{"fieldname": "gross_wages", "label": _("Gross Wages Payable"),
		 "fieldtype": "Float", "precision": 2, "width": 130},
		{"fieldname": "advance", "label": _("Advance"), "fieldtype": "Float", "precision": 2, "width": 90},
		{"fieldname": "professional_tax", "label": _("Professional Tax"),
		 "fieldtype": "Float", "precision": 2, "width": 110},
		{"fieldname": "state_insurance", "label": _("State Insurance"),
		 "fieldtype": "Float", "precision": 2, "width": 110},
		{"fieldname": "provident_fund", "label": _("Provident Fund"),
		 "fieldtype": "Float", "precision": 2, "width": 110},
		{"fieldname": "other_deduction", "label": _("Other Deduction of P.N."),
		 "fieldtype": "Float", "precision": 2, "width": 130},
		{"fieldname": "net_wages", "label": _("Net Wages Payable"),
		 "fieldtype": "Float", "precision": 2, "width": 130},
		{"fieldname": "prev_bal", "label": _("Previous Balance Accumulated"),
		 "fieldtype": "Float", "precision": 2, "width": 130},
		{"fieldname": "date_of_payment", "label": _("Date of Payment of Wages"),
		 "fieldtype": "Date", "width": 130},
		{"fieldname": "signature", "label": _("Signature/Thumb Impression"),
		 "fieldtype": "Data", "width": 150},
	]


def get_data(filters):
	year = cint(filters.year)
	month_name = str(filters.month).split(" - ")[-1].strip()
	month = list(calendar.month_name).index(month_name)
	month_start = getdate(f"{year}-{month:02d}-01")
	month_end = getdate(f"{year}-{month:02d}-{calendar.monthrange(year, month)[1]}")

	slips = frappe.db.sql(
		"""
		select name, employee, employee_name, start_date, end_date, payment_days,
		       total_earnings as gross_pay, total_deductions as total_deduction,
		       net_salary as net_pay
		from `tabSalary Slip`
		where company = %(company)s
		  and docstatus = 1
		  and start_date <= %(month_end)s
		  and end_date >= %(month_start)s
		order by employee_name
		""",
		{"company": filters.company, "month_start": month_start, "month_end": month_end},
		as_dict=1,
	)

	if not slips:
		return []

	slip_names = [s.name for s in slips]
	employees = list({s.employee for s in slips})

	emp_map = get_employee_map(employees)
	advance_map = get_advance_map(employees, month_start, month_end)
	earning_map = get_component_totals(slip_names, "earnings")
	deduction_map = get_component_totals(slip_names, "deductions")

	rows = []
	for s in slips:
		emp = emp_map.get(s.employee, {})
		earnings = earning_map.get(s.name, {})
		deductions = deduction_map.get(s.name, {})

		basic = sum_matching(earnings, BASIC_COMPONENT_MATCH)
		da = sum_matching(earnings, DA_COMPONENT_MATCH)
		hra = sum_matching(earnings, HRA_COMPONENT_MATCH)
		medical = sum_matching(earnings, MEDICAL_COMPONENT_MATCH)

		pt = sum_matching(deductions, PT_COMPONENT_MATCH)
		esic = sum_matching(deductions, ESIC_COMPONENT_MATCH)
		pf = sum_matching(deductions, PF_COMPONENT_MATCH, exclude=EXCLUDE_EMPLOYER_MATCH)

		gross = flt(s.gross_pay)
		total_ded = flt(s.total_deduction)
		other_ded = flt(total_ded - pt - esic - pf)
		advance = flt(advance_map.get(s.employee, 0))

		rows.append({
			"employee": s.employee,
			"employee_name": s.employee_name,
			"sex_age": emp.get("sex_age"),
			"working_hrs": emp.get("working_hrs"),
			"esic_no": emp.get("esic_no"),
			"pf_no": emp.get("pf_no"),
			"total_days": flt(s.payment_days),
			"min_rate_wages": None,  # TODO: source of statutory minimum wage not yet identified
			"actual_rate_wages": None,  # TODO: same as above
			"total_production": None,  # only relevant for piece-rate workers
			"total_ot_hours": None,  # TODO: pull from Attendance if tracked separately
			"normal_earning": flt(basic + da),
			"da": da,
			"basic_da": flt(basic + da),
			"ot_earning": None,  # TODO: OT component name not yet confirmed
			"hra": hra,
			"medical_allowance": medical,
			"gross_wages": gross,
			"advance": advance,
			"professional_tax": pt,
			"state_insurance": esic,
			"provident_fund": pf,
			"other_deduction": other_ded,
			"net_wages": flt(s.net_pay),
			"prev_bal": None,  # carried-forward balance — no existing source found
			"date_of_payment": s.end_date,  # Salary Slip has no posting_date; end_date is the closest proxy
			"signature": "",
		})

	rows.append(totals_row(rows))
	return rows


def get_employee_map(employees):
	if not employees:
		return {}
	emp_rows = frappe.db.sql(
		"""
		select name, gender, date_of_birth, esic_number, pf_uan_number, employee_pf_account
		from `tabEmployee`
		where name in %(employees)s
		""",
		{"employees": employees},
		as_dict=1,
	)
	out = {}
	for e in emp_rows:
		age = None
		if e.date_of_birth:
			today = getdate()
			dob = getdate(e.date_of_birth)
			age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
		sex = (e.gender or "")[:1].upper() if e.gender else ""
		out[e.name] = {
			"sex_age": f"{sex}/{age}" if age else sex,
			"pf_no": e.employee_pf_account or e.pf_uan_number,
			"esic_no": e.esic_number,
			"working_hrs": None,  # TODO: no per-employee shift-hours field found on Employee
		}
	return out


def get_advance_map(employees, month_start, month_end):
	"""Sum unDeducted/period Advance amounts from Employee Loan Advance (type=Advance)."""
	if not employees:
		return {}
	rows = frappe.db.sql(
		"""
		select employee, sum(amount) as total
		from `tabEmployee Loan Advance`
		where employee in %(employees)s
		  and type = 'Advance'
		  and docstatus = 1
		  and date between %(start)s and %(end)s
		group by employee
		""",
		{"employees": employees, "start": month_start, "end": month_end},
		as_dict=1,
	)
	return {r.employee: r.total for r in rows}


def get_component_totals(slip_names, parentfield):
	"""Returns {salary_slip_name: {component_name_lower: amount}}"""
	if not slip_names:
		return {}
	rows = frappe.db.sql(
		"""
		select parent, salary_component, amount
		from `tabSalary Details`
		where parent in %(slips)s
		  and parentfield = %(parentfield)s
		  and parenttype = 'Salary Slip'
		""",
		{"slips": slip_names, "parentfield": parentfield},
		as_dict=1,
	)
	out = {}
	for r in rows:
		out.setdefault(r.parent, {})
		key = (r.salary_component or "").lower()
		out[r.parent][key] = out[r.parent].get(key, 0) + flt(r.amount)
	return out


def sum_matching(component_dict, match_terms, exclude=None):
	total = 0.0
	for name, amount in component_dict.items():
		if exclude and any(term in name for term in exclude):
			continue
		if any(term in name for term in match_terms):
			total += flt(amount)
	return total


def totals_row(rows):
	total = {"employee": "", "employee_name": "TOTAL"}
	numeric_fields = [
		"total_days", "min_rate_wages", "actual_rate_wages", "total_ot_hours",
		"normal_earning", "da", "basic_da", "ot_earning", "hra", "medical_allowance",
		"gross_wages", "advance", "professional_tax", "state_insurance",
		"provident_fund", "other_deduction", "net_wages", "prev_bal",
	]
	for f in numeric_fields:
		total[f] = flt(sum(flt(r.get(f)) for r in rows if r.get(f) is not None))
	return total


# ============================================================================
# Excel export — same openpyxl styling pattern as payroll_report.py
# ============================================================================

_XL_TITLE_FG = "CC0000"
_XL_HDR_FG = "000000"
_XL_HDR_BG = "FFFF00"
_XL_ROW_BG = "FFFFFF"
_XL_ALT_BG = "F2F2F2"
_XL_TOT_BG = "D9E1F2"
_XL_TOT_FG = "1F3864"
_XL_BDR = "BFBFBF"


def _border():
	s = Side(style="thin", color=_XL_BDR)
	return Border(left=s, right=s, top=s, bottom=s)


def _xl_cell(ws, row, col, value, bold=False, fg="000000", bg=None, align="left", num_fmt=None):
	cell = ws.cell(row=row, column=col, value=value)
	cell.font = Font(name="Arial", size=9, bold=bold, color=fg)
	cell.alignment = Alignment(horizontal=align, vertical="center", wrap_text=False)
	cell.border = _border()
	if bg:
		cell.fill = PatternFill("solid", start_color=bg, fgColor=bg)
	if num_fmt:
		cell.number_format = num_fmt
	return cell


def _month_label(month_filter):
	name = str(month_filter or "").split(" - ")[-1]
	return name or ""


def _company_label(filters):
	return filters.get("company") or frappe.defaults.get_global_default("company") or ""


def _col_width(col):
	label = col.get("label", "")
	width = max(len(label) + 3, 10)
	if col.get("fieldtype") in ("Float", "Currency", "Int"):
		width = max(width, 14)
	return min(width, 40)


def _write_xl_sheet(ws, cols, data, co, mo, yr):
	nc = max(len(cols), 1)

	ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=nc)
	c1 = ws.cell(row=1, column=1, value=(co.upper() if co else ""))
	c1.font = Font(name="Arial", size=14, bold=True, color=_XL_TITLE_FG)
	c1.alignment = Alignment(horizontal="center", vertical="center")
	ws.row_dimensions[1].height = 22

	ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=nc)
	c2 = ws.cell(row=2, column=1, value="Register of Wages Report")
	c2.font = Font(name="Arial", size=11, bold=True, color="333333")
	c2.alignment = Alignment(horizontal="center", vertical="center")
	ws.row_dimensions[2].height = 18

	ws.merge_cells(start_row=3, start_column=1, end_row=3, end_column=nc)
	c3 = ws.cell(row=3, column=1, value="For the Month of {mo} {yr}".format(mo=mo, yr=yr))
	c3.font = Font(name="Arial", size=9, color="555555")
	c3.alignment = Alignment(horizontal="center", vertical="center")
	ws.row_dimensions[3].height = 14

	ws.row_dimensions[4].height = 4

	HDR_ROW = 5
	thick_bottom = Border(
		left=Side(style="thin", color=_XL_BDR),
		right=Side(style="thin", color=_XL_BDR),
		top=Side(style="thin", color=_XL_BDR),
		bottom=Side(style="medium", color="000000"),
	)
	for ci, col in enumerate(cols, 1):
		cell = ws.cell(row=HDR_ROW, column=ci, value=col.get("label", col.get("fieldname", "")))
		cell.font = Font(name="Arial", size=9, bold=True, color=_XL_HDR_FG)
		cell.fill = PatternFill("solid", start_color=_XL_HDR_BG, fgColor=_XL_HDR_BG)
		cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
		cell.border = thick_bottom
	ws.row_dimensions[HDR_ROW].height = 28

	if not data:
		ws.merge_cells(start_row=6, start_column=1, end_row=6, end_column=nc)
		c = ws.cell(row=6, column=1, value="No data for this period.")
		c.font = Font(name="Arial", size=9, italic=True, color="888888")
		c.alignment = Alignment(horizontal="center", vertical="center")
	else:
		for ri, row in enumerate(data, 6):
			is_tot = row.get("employee_name") == "TOTAL"
			row_bg = _XL_TOT_BG if is_tot else (_XL_ALT_BG if ri % 2 == 0 else _XL_ROW_BG)
			row_fg = _XL_TOT_FG if is_tot else "000000"

			for ci, col in enumerate(cols, 1):
				fn = col.get("fieldname", "")
				val = row.get(fn, "")
				ft = col.get("fieldtype", "")

				if ft in ("Float", "Currency", "Int"):
					num_fmt = "#,##0.00" if ft in ("Float", "Currency") else "#,##0"
					_xl_cell(ws, ri, ci, flt(val) if val not in ("", None) else None,
					         bold=is_tot, fg=row_fg, bg=row_bg, align="right", num_fmt=num_fmt)
				else:
					_xl_cell(ws, ri, ci, val if val is not None else "",
					         bold=is_tot, fg=row_fg, bg=row_bg, align="left")

			ws.row_dimensions[ri].height = 15

	for ci, col in enumerate(cols, 1):
		ws.column_dimensions[get_column_letter(ci)].width = _col_width(col)

	ws.freeze_panes = "A6"
	if cols:
		ws.auto_filter.ref = "{a}5:{b}5".format(a=get_column_letter(1), b=get_column_letter(nc))


def _save_excel(wb, prefix):
	buf = io.BytesIO()
	wb.save(buf)
	buf.seek(0)

	ts = frappe.utils.now_datetime().strftime("%Y%m%d_%H%M%S")
	fn = "{prefix}_{ts}.xlsx".format(prefix=prefix, ts=ts)
	with open(frappe.utils.get_files_path(fn, is_private=0), "wb") as fh:
		fh.write(buf.read())

	doc = frappe.get_doc({
		"doctype": "File",
		"file_name": fn,
		"is_private": 0,
		"file_url": "/files/{fn}".format(fn=fn),
	})
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return doc.file_url


@frappe.whitelist()
def export_excel(filters):
	if isinstance(filters, str):
		filters = json.loads(filters)

	cols, data = execute(filters)

	co = _company_label(filters)
	mo = _month_label(filters.get("month"))
	yr = filters.get("year", "")

	wb = Workbook()
	ws = wb.active
	ws.title = "Register of Wages"[:31]
	_write_xl_sheet(ws, cols, data, co, mo, yr)

	return _save_excel(wb, "Register_of_Wages_Report")