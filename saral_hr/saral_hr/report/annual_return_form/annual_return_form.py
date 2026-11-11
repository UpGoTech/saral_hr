# Copyright (c) 2026, sj and Contributors
# See license.txt

"""Annual Return Form — one workbook with the five sheets from the factory return."""

from __future__ import annotations

import calendar
import io
import json
from collections import Counter
from datetime import date, datetime

import frappe
from frappe import _
from frappe.utils import cint, flt, formatdate, getdate
from frappe.utils.pdf import get_pdf
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


MONTHS = (
	"January",
	"February",
	"March",
	"April",
	"May",
	"June",
	"July",
	"August",
	"September",
	"October",
	"November",
	"December",
)
FULL_DAY = {"Present", "On Tour", "Earned Comp Off"}
LEAVE_DAY = {"Earned Leave", "Casual Leave", "Comp Off"}
CLOSED_DAY = {"Weekly Off", "Holiday"}
HOURS_PER_DAY = 8
ANNUAL_LEAVE_DAYS = 240
WEEKDAYS = {
	"Monday": 0,
	"Tuesday": 1,
	"Wednesday": 2,
	"Thursday": 3,
	"Friday": 4,
	"Saturday": 5,
	"Sunday": 6,
}
BANDS = (
	("adult", "Adult Workers"),
	("adolescent", "Worker of age (15 yrs < 18 yrs)"),
	("child", "Child Labor (14 yrs to 15 yrs)"),
)
SEXES = (("male", "Male"), ("female", "Female"))

HEADER_FILL = PatternFill("solid", fgColor="1F4E79")
SUB_FILL = PatternFill("solid", fgColor="D6DCE4")
TOTAL_FILL = PatternFill("solid", fgColor="E8E8E8")
TITLE_FONT = Font(name="Calibri", size=16, bold=True, color="1F4E79")
HEADER_FONT = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
SUB_FONT = Font(name="Calibri", size=11, bold=True)
BODY_FONT = Font(name="Calibri", size=11)
BOLD_FONT = Font(name="Calibri", size=11, bold=True)
THIN = Border(
	left=Side(style="thin", color="000000"),
	right=Side(style="thin", color="000000"),
	top=Side(style="thin", color="000000"),
	bottom=Side(style="thin", color="000000"),
)
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
MONTH = Alignment(horizontal="center", vertical="center", wrap_text=False)
LEFT = Alignment(horizontal="left", vertical="center", wrap_text=True, indent=1)
RIGHT = Alignment(horizontal="right", vertical="center", wrap_text=False, indent=1)
BODY_LEFT = Alignment(horizontal="left", vertical="center", wrap_text=False, indent=1)
DATE_RIGHT = Alignment(horizontal="right", vertical="center", wrap_text=False, indent=1)


def execute(filters=None):
	filters = _normalize_filters(filters)
	year = _year(filters)
	if not filters.get("company") or not year:
		return _working_columns(year or date.today().year), []
	pack = _load(filters.company, year)
	return _working_columns(year), _working_rows(pack)


@frappe.whitelist()
def excel_report(filters):
	filters = _normalize_filters(filters)
	year = _year(filters)
	if not filters.get("company") or not year:
		frappe.throw(_("Please select Company and Year."))
	pack = _load(filters.company, year)
	if not pack["working"]:
		frappe.throw(_("No employees found for this company and year."))
	wb = _workbook(pack, filters.company, year)
	return _save_excel(wb, "Annual_Return_Form")


@frappe.whitelist()
def print_report(filters):
	filters = _normalize_filters(filters)
	year = _year(filters)
	if not filters.get("company") or not year:
		frappe.throw(_("Please select Company and Year."))
	pack = _load(filters.company, year)
	if not pack["working"]:
		frappe.throw(_("No employees found for this company and year."))
	html = _build_print_html(pack, filters.company, year)
	return _save_pdf(html, "Annual_Return_Form")


def worked_weight(status):
	if status in FULL_DAY:
		return 1.0
	if status == "Half Day":
		return 0.5
	return 0.0


def on_rolls(joining, left, start, end):
	joining = _as_date(joining)
	left = _as_date(left)
	if not joining or joining > end:
		return False
	if left and left < start:
		return False
	return True


def age_band(dob, on):
	"""Adult is 18+, adolescent is 15 to under 18, child is under 15. Missing birth date counts as adult."""
	dob = _as_date(dob)
	if not dob:
		return "adult"
	years = on.year - dob.year - ((on.month, on.day) < (dob.month, dob.day))
	if years >= 18:
		return "adult"
	if years >= 15:
		return "adolescent"
	return "child"


def is_female(gender):
	return (gender or "").strip().lower() in {"female", "f"}


def eligible_for_annual_leave(joining, worked_days, year):
	"""Factories Act annual leave: 240 days, or two-thirds of the days after a mid-year joining."""
	joining = _as_date(joining)
	start = date(year, 1, 1)
	end = date(year, 12, 31)
	worked = flt(worked_days)
	if not joining or joining <= start:
		return worked + 1e-9 >= ANNUAL_LEAVE_DAYS
	span = (end - joining).days + 1
	return worked + 1e-9 >= (2.0 / 3.0) * span


def is_agriculture(category):
	return "agricult" in (category or "").lower()


def assemble(employees, attendance, daily_rate, year):
	start = date(year, 1, 1)
	end = date(year, 12, 31)
	people = []
	for emp in employees or []:
		if is_agriculture(emp.get("category")):
			continue
		if not on_rolls(emp.get("date_of_joining"), emp.get("left_date"), start, end):
			continue
		people.append(emp)

	by_code = {emp.get("name"): emp for emp in people}
	marks = {}
	for row in list(attendance or []) + list(daily_rate or []):
		code = row.get("employee")
		if code not in by_code:
			continue
		day = _as_date(row.get("attendance_date") or row.get("date"))
		if not day or day.year != year:
			continue
		slot = marks.setdefault(code, {}).setdefault(day, {"weight": 0.0, "status": "", "ot": 0.0, "leave": False})
		weight = worked_weight(row.get("status"))
		if weight > slot["weight"]:
			slot["weight"] = weight
			slot["status"] = row.get("status") or ""
		elif not slot["status"]:
			slot["status"] = row.get("status") or ""
		if row.get("status") in LEAVE_DAY:
			slot["leave"] = True
		slot["ot"] += flt(row.get("ot_hours"))

	weekday = _common_weekly_off(people)
	plant_open = set()
	holiday_dates = set()
	for code, days in marks.items():
		for day, slot in days.items():
			if slot["status"] and slot["status"] not in CLOSED_DAY:
				plant_open.add(day)
			if slot["status"] == "Holiday":
				holiday_dates.add(day)

	weekly_off_dates = set()
	cursor = start
	while cursor <= end:
		if cursor.weekday() == weekday and cursor not in plant_open:
			weekly_off_dates.add(cursor)
		cursor = _next_day(cursor)
	holiday_dates = {day for day in holiday_dates if day not in plant_open and day not in weekly_off_dates}
	year_days = (end - start).days + 1
	operation_days = year_days - len(weekly_off_dates) - len(holiday_dates)

	working = []
	month_mandays = {(m, sex): 0.0 for m in range(1, 13) for sex in ("male", "female")}
	month_ot = {m: 0.0 for m in range(1, 13)}
	month_head = {(m, sex): 0 for m in range(1, 13) for sex in ("male", "female")}
	groups = {
		(band, sex): {"on_duty": 0, "eligible": 0, "sanctioned": 0, "left": 0, "mandays": 0.0, "ot": 0.0}
		for band, _label in BANDS
		for sex, _sex_label in SEXES
	}

	for emp in sorted(people, key=lambda row: (row.get("name") or "")):
		code = emp.get("name")
		sex = "female" if is_female(emp.get("gender")) else "male"
		band = age_band(emp.get("date_of_birth"), end)
		months = [0.0] * 12
		leave_taken = False
		ot_total = 0.0
		for day, slot in marks.get(code, {}).items():
			months[day.month - 1] += slot["weight"] 
			month_mandays[(day.month, sex)] += slot["weight"]
			month_ot[day.month] += slot["ot"]
			ot_total += slot["ot"]
			leave_taken = leave_taken or slot["leave"]
		worked = sum(months)
		groups[(band, sex)]["on_duty"] += 1
		groups[(band, sex)]["mandays"] += worked
		groups[(band, sex)]["ot"] += ot_total
		if eligible_for_annual_leave(emp.get("date_of_joining"), worked, year):
			groups[(band, sex)]["eligible"] += 1
		if leave_taken:
			groups[(band, sex)]["sanctioned"] += 1
		left = _as_date(emp.get("left_date"))
		if left and left.year == year:
			groups[(band, sex)]["left"] += 1
		for month in range(1, 13):
			m_start = date(year, month, 1)
			m_end = date(year, month, calendar.monthrange(year, month)[1])
			if on_rolls(emp.get("date_of_joining"), emp.get("left_date"), m_start, m_end):
				month_head[(month, sex)] += 1
		working.append(
			{
				"employee": code,
				"employee_name": emp.get("full_name") or "",
				"designation": emp.get("designation") or "",
				"date_of_joining": _as_date(emp.get("date_of_joining")),
				"months": months,
				"total": worked,
			}
		)

	manpower = []
	for month in range(1, 13):
		total_days = calendar.monthrange(year, month)[1]
		m_start = date(year, month, 1)
		m_end = date(year, month, total_days)
		closing = sum(1 for day in weekly_off_dates if m_start <= day <= m_end)
		closing += sum(1 for day in holiday_dates if m_start <= day <= m_end)
		male = month_head[(month, "male")]
		female = month_head[(month, "female")]
		male_days = month_mandays[(month, "male")]
		female_days = month_mandays[(month, "female")]
		manpower.append(
			{
				"month": month,
				"month_name": MONTHS[month - 1],
				"closing_days": closing,
				"total_days": total_days,
				"working_days": total_days - closing,
				"male": male,
				"female": female,
				"employees": male + female,
				"male_mandays": male_days,
				"female_mandays": female_days,
				"mandays": male_days + female_days,
				"ot": month_ot[month],
			}
		)

	weeks = operation_days / 7.0 if operation_days else 0
	employment = []
	for band, _label in BANDS:
		for sex, _sex_label in SEXES:
			stat = groups[(band, sex)]
			mandays = stat["mandays"]
			average = round(mandays / operation_days) if operation_days else 0
			man_hours = mandays * HOURS_PER_DAY + stat["ot"]
			per_week = round((man_hours / weeks) / average) if weeks and average else 0
			employment.append(
				{
					"band": band,
					"sex": sex,
					"mandays": mandays,
					"average_workers": average,
					"ot_hours": stat["ot"],
					"man_hours": man_hours,
					"hours_per_week": per_week,
				}
			)

	left_rows = []
	for emp in people:
		left = _as_date(emp.get("left_date"))
		if not left or left.year != year:
			continue
		left_rows.append(
			{
				"employee": emp.get("name"),
				"employee_name": emp.get("full_name") or "",
				"designation": emp.get("designation") or "",
				"date_of_joining": _as_date(emp.get("date_of_joining")),
				"left_date": left,
				"month": left.month,
			}
		)
	left_rows.sort(key=lambda row: (row["left_date"], row["employee"] or ""))

	return {
		"year": year,
		"working": working,
		"groups": groups,
		"manpower": manpower,
		"employment": employment,
		"plant": {
			"operation_days": operation_days,
			"weeks": weeks,
			"hours_per_day": HOURS_PER_DAY,
			"year_days": year_days,
			"weekly_offs": len(weekly_off_dates),
			"holidays": len(holiday_dates),
		},
		"left": left_rows,
	}


def _working_columns(year):
	columns = [
		{"label": _("Sr"), "fieldname": "sr_no", "fieldtype": "Int", "width": 50},
		{"label": _("Emp. Code"), "fieldname": "employee", "fieldtype": "Link", "options": "Company Link", "width": 120},
		{"label": _("Name of Employees"), "fieldname": "employee_name", "fieldtype": "Data", "width": 145},
		{"label": _("Designation"), "fieldname": "designation", "fieldtype": "Data", "width": 140},
		{"label": _("Date of Joining"), "fieldname": "date_of_joining", "fieldtype": "Date", "width": 120},
	]
	for index, name in enumerate(MONTHS, start=1):
		columns.append(
			{
				"label": f"{name[:3]}-{year}",
				"fieldname": f"m{index}",
				"fieldtype": "Float",
				"precision": 1,
				"width": 80,
			}
		)
	columns.append(
		{"label": _("Total"), "fieldname": "total", "fieldtype": "Float", "precision": 1, "width": 90}
	)
	return columns


def _working_rows(pack):
	rows = []
	totals = [0.0] * 12
	grand = 0.0
	for index, emp in enumerate(pack["working"], start=1):
		row = {
			"sr_no": index,
			"employee": emp["employee"],
			"employee_name": emp["employee_name"],
			"designation": emp["designation"],
			"date_of_joining": emp["date_of_joining"],
			"total": _round_day(emp["total"]),
		}
		for month, value in enumerate(emp["months"], start=1):
			shown = _round_day(value)
			row[f"m{month}"] = shown
			totals[month - 1] += value
		grand += emp["total"]
		rows.append(row)
	if rows:
		total_row = {
			"sr_no": "",
			"employee": "",
			"employee_name": _("Total"),
			"designation": "",
			"date_of_joining": None,
			"total": _round_day(grand),
			"_is_total": 1,
		}
		for month, value in enumerate(totals, start=1):
			total_row[f"m{month}"] = _round_day(value)
		rows.append(total_row)
	return rows


def _load(company, year):
	start = date(year, 1, 1)
	end = date(year, 12, 31)
	employees = frappe.db.sql(
		"""
		SELECT cl.name, cl.full_name, cl.designation, cl.date_of_joining, cl.left_date,
			cl.category, cl.weekly_off, e.gender, e.date_of_birth
		FROM `tabCompany Link` cl
		LEFT JOIN `tabEmployee` e ON e.name = cl.employee
		WHERE cl.company = %s
			AND cl.date_of_joining <= %s
			AND (cl.left_date IS NULL OR cl.left_date = '' OR cl.left_date >= %s)
		""",
		(company, end, start),
		as_dict=True,
	)
	codes = [row.name for row in employees]
	attendance = []
	daily = []
	if codes:
		attendance = frappe.db.sql(
			"""
			SELECT employee, attendance_date, status
			FROM `tabAttendance`
			WHERE company = %s AND attendance_date BETWEEN %s AND %s
			""",
			(company, start, end),
			as_dict=True,
		)
		daily = frappe.db.sql(
			"""
			SELECT employee, attendance_date, status, ot_hours
			FROM `tabAttendance Daily Rate`
			WHERE attendance_date BETWEEN %s AND %s AND employee IN %s
			""",
			(start, end, tuple(codes)),
			as_dict=True,
		)
	return assemble(employees, attendance, daily, year)


def _workbook(pack, company, year):
	wb = Workbook()
	_sheet_working(wb.active, pack, company, year)
	_sheet_leave(wb.create_sheet("Leave & Wages"), pack, company, year)
	_sheet_manpower(wb.create_sheet("Total Manpower"), pack, company, year)
	_sheet_employment(wb.create_sheet("Employment Information"), pack, company, year)
	_sheet_left(wb.create_sheet("Left Workers"), pack, company, year)
	return wb


def _sheet_working(ws, pack, company, year):
	ws.title = "Working Days"
	headers = [
		"SR.\nNO.",
		"EMP.\nCODE",
		"NAME OF\nEMPLOYEES",
		"DESIGNATION",
		"DATE OF\nJOINING",
		*[f"{name[:3]}\n{year}" for name in MONTHS],
		"TOTAL",
	]
	_title(ws, 1, len(headers), f"{company} — Annual Return Form — Working Days — {year}")
	_header_row(ws, 3, headers)
	for col in range(1, len(headers) + 1):
		ws.merge_cells(start_row=3, start_column=col, end_row=4, end_column=col)
		ws.cell(4, col).fill = HEADER_FILL
		ws.cell(4, col).border = THIN
	for row_index, emp in enumerate(pack["working"], start=5):
		values = [
			row_index - 4,
			emp["employee"],
			emp["employee_name"],
			emp["designation"],
			emp["date_of_joining"],
			*[_round_day(value) for value in emp["months"]],
			_round_day(emp["total"]),
		]
		_body_row(ws, row_index, values, date_cols={5})
	total_row = 5 + len(pack["working"])
	totals = [0.0] * 12
	grand = 0.0
	for emp in pack["working"]:
		for index, value in enumerate(emp["months"]):
			totals[index] += value
		grand += emp["total"]
	_body_row(
		ws,
		total_row,
		["", "", "Total", "", "", *[_round_day(value) for value in totals], _round_day(grand)],
		bold=True,
		fill=TOTAL_FILL,
	)
	widths = [8, 16, 26, 17, 13] + [9.5] * 12 + [10]
	_widths(ws, widths)
	ws.row_dimensions[3].height = 16
	ws.row_dimensions[4].height = 16
	ws.freeze_panes = "A5"
	ws.auto_filter.ref = f"A4:{get_column_letter(len(headers))}{max(total_row, 4)}"
	ws.page_setup.orientation = "landscape"
	ws.page_setup.fitToPage = True
	ws.page_setup.fitToWidth = 1
	ws.page_setup.fitToHeight = 0
	ws.sheet_properties.pageSetUpPr.fitToPage = True
	ws.page_setup.paperSize = ws.PAPERSIZE_A4
	ws.oddHeader.left.text = f"{company} — Annual Return Form {year}"
	ws.oddFooter.center.text = "Working Days  |  Page &P of &N"


def _sheet_leave(ws, pack, company, year):
	headers = [
		"Workers'\nCategory",
		"Sex",
		"Number of\nworkers on duty\n(31 Jan Attend. +\nNew Joinees\ntill 31 Dec)",
		"Number of\nworkers eligible\nfor annual leave",
		"No of workers\nwhose leaves\nsanctioned",
		"No of\nworkers\nsuspended",
		"No of\nworkers\nTerminated",
		"No workers\nleft the job",
		"No of\nworkers\nretired",
		"No of workers\ndied while\nin service",
		"No of workers\nto whom payment\nis made instead\nof leave",
	]
	_title(ws, 1, len(headers), f"{company} — Leave & Wages Details — {year}")
	note = ws.cell(2, 1, "(Excluding Agriculture Team)")
	note.font = BOLD_FONT
	_header_row(ws, 3, headers)
	for index in range(1, len(headers) + 1):
		cell = ws.cell(4, index, f"({index})")
		cell.font = SUB_FONT
		cell.fill = SUB_FILL
		cell.alignment = CENTER
		cell.border = THIN
	row = 6
	for band, label in BANDS:
		start = row
		for sex, sex_label in SEXES:
			stat = pack["groups"][(band, sex)]
			_body_row(
				ws,
				row,
				[
					_category_label(label) if sex == "male" else "",
					sex_label,
					stat["on_duty"],
					stat["eligible"],
					stat["sanctioned"],
					0,
					0,
					stat["left"],
					0,
					0,
					0,
				],
			)
			row += 1
		ws.merge_cells(start_row=start, start_column=1, end_row=start + 1, end_column=1)
		cat = ws.cell(start, 1)
		cat.alignment = LEFT
		cat.font = BODY_FONT
	_widths(ws, [18, 11, 18, 14, 14, 12, 12, 12, 12, 14, 16])
	ws.row_dimensions[3].height = 80
	ws.row_dimensions[4].height = 16
	ws.page_setup.orientation = "landscape"
	ws.page_setup.fitToPage = True
	ws.page_setup.fitToWidth = 1
	ws.page_setup.fitToHeight = 1
	ws.sheet_properties.pageSetUpPr.fitToPage = True
	ws.page_setup.paperSize = ws.PAPERSIZE_A4
	ws.print_title_rows = "1:4"
	ws.oddFooter.center.text = "Leave & Wages  |  Page &P of &N"


def _sheet_manpower(ws, pack, company, year):
	_title(ws, 1, 12, f"{company} — Total Manpower — {year}")
	top = [
		(1, "S.N."),
		(2, "Month"),
		(3, "Closing\nDays"),
		(4, "Total\nDays"),
		(5, "Total\nWorking\nDays"),
		(6, "No. of Employees"),
		(9, "Mandays"),
		(12, "OT"),
	]
	for col, label in top:
		cell = ws.cell(3, col, label)
		cell.font = HEADER_FONT
		cell.fill = HEADER_FILL
		cell.alignment = CENTER
		cell.border = THIN
	ws.merge_cells("A3:A4")
	ws.merge_cells("B3:B4")
	ws.merge_cells("C3:C4")
	ws.merge_cells("D3:D4")
	ws.merge_cells("E3:E4")
	ws.merge_cells("F3:H3")
	ws.merge_cells("I3:K3")
	ws.merge_cells("L3:L4")
	for col, label in ((6, "Male"), (7, "Female"), (8, "Total"), (9, "Male"), (10, "Female"), (11, "Total")):
		cell = ws.cell(4, col, label)
		cell.font = HEADER_FONT
		cell.fill = HEADER_FILL
		cell.alignment = CENTER
		cell.border = THIN
	for col in (1, 2, 3, 4, 5, 12):
		ws.cell(4, col).fill = HEADER_FILL
		ws.cell(4, col).border = THIN
		ws.cell(4, col).alignment = CENTER
	totals = Counter()
	for offset, month in enumerate(pack["manpower"]):
		values = [
			offset + 1,
			f"{month['month_name'][:3]}-{year}",
			month["closing_days"],
			month["total_days"],
			month["working_days"],
			month["male"],
			month["female"],
			month["employees"],
			_round_day(month["male_mandays"]),
			_round_day(month["female_mandays"]),
			_round_day(month["mandays"]),
			_round_day(month["ot"]),
		]
		_body_row(ws, 5 + offset, values)
		for key in (
			"closing_days",
			"total_days",
			"working_days",
			"male",
			"female",
			"employees",
			"male_mandays",
			"female_mandays",
			"mandays",
			"ot",
		):
			totals[key] += month[key]
	_body_row(
		ws,
		17,
		[
			"",
			"Total",
			totals["closing_days"],
			totals["total_days"],
			totals["working_days"],
			"",
			"",
			"",
			_round_day(totals["male_mandays"]),
			_round_day(totals["female_mandays"]),
			_round_day(totals["mandays"]),
			_round_day(totals["ot"]),
		],
		bold=True,
		fill=TOTAL_FILL,
	)
	_widths(ws, [8, 14, 10, 10, 11, 8, 10, 8, 10, 10, 10, 8])
	ws.row_dimensions[3].height = 32
	ws.row_dimensions[4].height = 16
	ws.page_setup.orientation = "landscape"
	ws.page_setup.fitToPage = True
	ws.page_setup.fitToWidth = 1
	ws.page_setup.fitToHeight = 1
	ws.sheet_properties.pageSetUpPr.fitToPage = True
	ws.page_setup.paperSize = ws.PAPERSIZE_A4
	ws.print_title_rows = "1:4"
	ws.oddFooter.center.text = "Total Manpower  |  Page &P of &N"


def _sheet_employment(ws, pack, company, year):
	plant = pack["plant"]
	_title(ws, 1, 7, f"{company} — Employment Information — {year}")
	facts = [
		(3, "1", "No of days plant was in operation", plant["operation_days"], "Total days of year", plant["year_days"]),
		(4, "2", "No of weeks plant was in operation", _round_day(plant["weeks"]), "Total W. Off", plant["weekly_offs"]),
		(5, "3", "Total hours per day workers working (excluding overtime)", plant["hours_per_day"], "Total Holidays", plant["holidays"]),
		(6, "", "", "", "Total days of operation", plant["operation_days"]),
	]
	for row, serial, label, value, side_label, side_value in facts:
		ws.cell(row, 1, serial).font = BOLD_FONT
		label_cell = ws.cell(row, 2, label)
		label_cell.font = BODY_FONT
		label_cell.alignment = LEFT
		ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=4)
		num = ws.cell(row, 5, value)
		num.font = BOLD_FONT
		num.alignment = RIGHT
		side_label_cell = ws.cell(row, 6, side_label)
		side_label_cell.font = BODY_FONT
		side_label_cell.alignment = LEFT
		side = ws.cell(row, 7, side_value)
		side.font = BOLD_FONT
		side.alignment = RIGHT
		if len(label) > 40 or len(side_label) > 22:
			ws.row_dimensions[row].height = 32
	ws.cell(8, 1, "Number of labors and their details").font = TITLE_FONT
	headers = [
		"Category of\nworkers",
		"Sex",
		"No. of\nMandays during\nthe year",
		"Average number\nof Workers\nemployed\nper day",
		"Number of\nman-hours\nworked on\novertime\nin a year",
		"Number of\nmanhours worked\nincluding\novertime\nin a year",
		"Average number\nof hours\nworked\nper week",
	]
	_header_row(ws, 10, headers)
	for index in range(1, 8):
		cell = ws.cell(11, index, f"({index})")
		cell.font = SUB_FONT
		cell.fill = SUB_FILL
		cell.alignment = CENTER
		cell.border = THIN
	by_key = {(row["band"], row["sex"]): row for row in pack["employment"]}
	row_no = 12
	for band, label in BANDS:
		start = row_no
		for sex, sex_label in SEXES:
			stat = by_key[(band, sex)]
			_body_row(
				ws,
				row_no,
				[
					_category_label(label) if sex == "male" else "",
					sex_label,
					_round_day(stat["mandays"]),
					stat["average_workers"],
					_round_day(stat["ot_hours"]),
					_round_day(stat["man_hours"]),
					stat["hours_per_week"],
				],
			)
			row_no += 1
		ws.merge_cells(start_row=start, start_column=1, end_row=start + 1, end_column=1)
		cat = ws.cell(start, 1)
		cat.alignment = LEFT
		cat.font = BODY_FONT
	_widths(ws, [18, 11, 15, 16, 12, 18, 12])
	ws.row_dimensions[10].height = 90
	ws.row_dimensions[11].height = 16
	ws.page_setup.orientation = "landscape"
	ws.page_setup.fitToPage = True
	ws.page_setup.fitToWidth = 1
	ws.page_setup.fitToHeight = 1
	ws.sheet_properties.pageSetUpPr.fitToPage = True
	ws.page_setup.paperSize = ws.PAPERSIZE_A4
	ws.print_title_rows = "1:11"
	ws.oddFooter.center.text = "Employment Information  |  Page &P of &N"


def _sheet_left(ws, pack, company, year):
	headers = [
		"SR.\nNO.",
		"EMP.\nCODE",
		"NAME OF\nWORKER",
		"DESIGNATION",
		"DATE OF\nJOINING",
		"Exit\ndate",
		*[f"{name[:3]}\n{year}" for name in MONTHS],
		"Total",
	]
	_title(ws, 1, len(headers), f"{company} — Left Workers — {year}")
	_header_row(ws, 3, headers)
	for col in range(1, len(headers) + 1):
		ws.merge_cells(start_row=3, start_column=col, end_row=4, end_column=col)
		ws.cell(4, col).fill = HEADER_FILL
		ws.cell(4, col).border = THIN
	if not pack["left"]:
		ws.cell(5, 1, "No workers left in this year").font = BODY_FONT
	for index, emp in enumerate(pack["left"], start=1):
		months = [1 if month == emp["month"] else 0 for month in range(1, 13)]
		_body_row(
			ws,
			4 + index,
			[
				index,
				emp["employee"],
				emp["employee_name"],
				emp["designation"],
				emp["date_of_joining"],
				emp["left_date"],
				*months,
				1,
			],
			date_cols={5, 6},
		)
	_widths(ws, [8, 16, 26, 17, 13, 13] + [9.5] * 12 + [10])
	ws.row_dimensions[3].height = 16
	ws.row_dimensions[4].height = 16
	ws.freeze_panes = "A5"
	ws.page_setup.orientation = "landscape"
	ws.page_setup.fitToPage = True
	ws.page_setup.fitToWidth = 1
	ws.page_setup.fitToHeight = 0
	ws.sheet_properties.pageSetUpPr.fitToPage = True
	ws.page_setup.paperSize = ws.PAPERSIZE_A4
	ws.print_title_rows = "1:4"
	last = 4 + max(len(pack["left"]), 1)
	ws.auto_filter.ref = f"A4:{get_column_letter(len(headers))}{last}"
	ws.oddFooter.center.text = "Left Workers  |  Page &P of &N"


def _title(ws, row, columns, text):
	ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=columns)
	cell = ws.cell(row, 1, text)
	cell.font = TITLE_FONT
	cell.alignment = Alignment(horizontal="left", vertical="center")
	ws.row_dimensions[row].height = 22


def _category_label(label):
	return {
		"Worker of age (15 yrs < 18 yrs)": "Worker of age\n(15 yrs < 18 yrs)",
		"Child Labor (14 yrs to 15 yrs)": "Child Labor\n(14 yrs to 15 yrs)",
	}.get(label, label)


def _header_row(ws, row, headers):
	for col, label in enumerate(headers, start=1):
		cell = ws.cell(row, col, label)
		cell.font = HEADER_FONT
		cell.fill = HEADER_FILL
		# Month headers are "Jan\n2025" — keep them centered and wrapped.
		if isinstance(label, str) and "\n" in label and len(label.split("\n")[0]) == 3:
			cell.alignment = CENTER
		elif isinstance(label, str) and len(label) == 8 and label[3] == "-":
			cell.alignment = MONTH
		else:
			cell.alignment = CENTER
		cell.border = THIN


def _body_row(ws, row, values, date_cols=(), bold=False, fill=None):
	for col, value in enumerate(values, start=1):
		cell = ws.cell(row, col, value if value != "" else None)
		cell.font = BOLD_FONT if bold else BODY_FONT
		cell.border = THIN
		if col in date_cols:
			cell.alignment = DATE_RIGHT
			if isinstance(value, date):
				cell.number_format = "DD-MM-YYYY"
		elif isinstance(value, (int, float)) and not isinstance(value, bool):
			cell.alignment = RIGHT
		elif isinstance(value, str) and "\n" in value:
			cell.alignment = LEFT
		else:
			cell.alignment = BODY_LEFT
		if fill is not None:
			cell.fill = fill
		if isinstance(value, float) and col not in date_cols:
			cell.number_format = "0.0"


def _widths(ws, widths):
	for index, width in enumerate(widths, start=1):
		ws.column_dimensions[get_column_letter(index)].width = width


def _esc(value):
	return frappe.utils.escape_html("" if value is None else str(value))


def _fmt_date(value):
	if not value:
		return ""
	return formatdate(_as_date(value), "dd-mm-yyyy")


def _fmt_num(value):
	if value is None or value == "":
		return ""
	return _esc(_round_day(value))


def _build_print_html(pack, company, year):
	sections = [
		_html_working(pack, company, year),
		_html_leave(pack, company, year),
		_html_manpower(pack, company, year),
		_html_employment(pack, company, year),
		_html_left(pack, company, year),
	]
	body = "".join(f'<div class="sheet">{section}</div>' for section in sections)
	return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
body{{font-family:Arial,Helvetica,sans-serif;font-size:11px;color:#000;margin:0}}
.sheet{{page-break-after:always}}
.sheet:last-child{{page-break-after:auto}}
h2{{font-size:14px;margin:0 0 8px;color:#1F4E79}}
table{{border-collapse:collapse;width:100%;table-layout:fixed}}
th,td{{border:1px solid #000;padding:4px 5px;vertical-align:middle;word-wrap:break-word}}
th{{background:#d6e4f0;color:#111;font-size:10px;text-align:center;line-height:1.15;font-weight:700}}
th.month{{font-size:9px;padding:3px 1px}}
td.num,td.date{{text-align:right;white-space:nowrap}}
td.name{{text-align:left;padding-left:8px;font-size:11px;word-break:normal;overflow-wrap:anywhere}}
td.code{{text-align:left;padding-left:8px;white-space:nowrap;font-size:10px}}
td.left{{text-align:left;padding-left:8px}}
td.center{{text-align:center}}
td.cat{{text-align:left;padding-left:8px;vertical-align:middle}}
tr.total td{{font-weight:700;background:#e8e8e8}}
.note{{font-weight:700;margin:0 0 6px}}
.work col.c-sr{{width:3%}}
.work col.c-code{{width:8%}}
.work col.c-name{{width:12%}}
.work col.c-desig{{width:8%}}
.work col.c-date{{width:7%}}
.work col.c-m{{width:4.5%}}
.work col.c-tot{{width:5%}}
</style></head><body>{body}</body></html>"""


def _month_heads(year):
	return "".join(f'<th class="month">{name[:3]}<br>{year}</th>' for name in MONTHS)


def _html_working(pack, company, year):
	rows = []
	totals = [0.0] * 12
	grand = 0.0
	for index, emp in enumerate(pack["working"], start=1):
		cells = [
			f'<td class="center">{index}</td>',
			f'<td class="code">{_esc(emp["employee"])}</td>',
			f'<td class="name">{_esc(emp["employee_name"])}</td>',
			f'<td class="left">{_esc(emp["designation"])}</td>',
			f'<td class="date">{_esc(_fmt_date(emp["date_of_joining"]))}</td>',
		]
		for month_index, value in enumerate(emp["months"]):
			cells.append(f'<td class="num">{_fmt_num(value)}</td>')
			totals[month_index] += value
		cells.append(f'<td class="num">{_fmt_num(emp["total"])}</td>')
		grand += emp["total"]
		rows.append(f"<tr>{''.join(cells)}</tr>")
	total_cells = [
		'<td></td><td></td><td class="name">Total</td><td></td><td></td>',
		*[f'<td class="num">{_fmt_num(value)}</td>' for value in totals],
		f'<td class="num">{_fmt_num(grand)}</td>',
	]
	rows.append(f'<tr class="total">{"".join(total_cells)}</tr>')
	cols = (
		'<colgroup>'
		'<col class="c-sr"><col class="c-code"><col class="c-name">'
		'<col class="c-desig"><col class="c-date">'
		+ "".join('<col class="c-m">' for _ in MONTHS)
		+ '<col class="c-tot"></colgroup>'
	)
	return (
		f"<h2>{_esc(company)} — Annual Return Form — Working Days — {year}</h2>"
		f'<table class="work">{cols}<thead><tr>'
		"<th>SR.<br>NO.</th><th>EMP.<br>CODE</th><th>NAME OF EMPLOYEES</th>"
		"<th>DESIGNATION</th><th>DATE OF<br>JOINING</th>"
		f"{_month_heads(year)}<th>TOTAL</th></tr></thead>"
		f"<tbody>{''.join(rows)}</tbody></table>"
	)


def _html_leave(pack, company, year):
	headers = [
		"Workers' Category",
		"Sex",
		"Number of workers on duty",
		"Number of workers eligible for annual leave",
		"No of workers whose leaves sanctioned",
		"No of workers suspended",
		"No of workers Terminated",
		"No workers left the job",
		"No of workers retired",
		"No of workers died while in service",
		"No of workers to whom payment is made instead of leave",
	]
	head = "".join(f"<th>{_esc(label)}</th>" for label in headers)
	rows = []
	for band, label in BANDS:
		cat = _esc(_category_label(label)).replace("\n", "<br>")
		for index, (sex, sex_label) in enumerate(SEXES):
			stat = pack["groups"][(band, sex)]
			cat_cell = (
				f'<td class="cat" rowspan="2">{cat}</td>' if index == 0 else ""
			)
			rows.append(
				"<tr>"
				f"{cat_cell}"
				f'<td class="left">{_esc(sex_label)}</td>'
				f'<td class="num">{_fmt_num(stat["on_duty"])}</td>'
				f'<td class="num">{_fmt_num(stat["eligible"])}</td>'
				f'<td class="num">{_fmt_num(stat["sanctioned"])}</td>'
				'<td class="num">0</td><td class="num">0</td>'
				f'<td class="num">{_fmt_num(stat["left"])}</td>'
				'<td class="num">0</td><td class="num">0</td><td class="num">0</td>'
				"</tr>"
			)
	return (
		f"<h2>{_esc(company)} — Leave &amp; Wages Details — {year}</h2>"
		'<div class="note">(Excluding Agriculture Team)</div>'
		f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table>"
	)


def _html_manpower(pack, company, year):
	rows = []
	totals = Counter()
	for offset, month in enumerate(pack["manpower"]):
		rows.append(
			"<tr>"
			f'<td class="center">{offset + 1}</td>'
			f'<td class="left">{_esc(month["month_name"][:3])}-{year}</td>'
			f'<td class="num">{_fmt_num(month["closing_days"])}</td>'
			f'<td class="num">{_fmt_num(month["total_days"])}</td>'
			f'<td class="num">{_fmt_num(month["working_days"])}</td>'
			f'<td class="num">{_fmt_num(month["male"])}</td>'
			f'<td class="num">{_fmt_num(month["female"])}</td>'
			f'<td class="num">{_fmt_num(month["employees"])}</td>'
			f'<td class="num">{_fmt_num(month["male_mandays"])}</td>'
			f'<td class="num">{_fmt_num(month["female_mandays"])}</td>'
			f'<td class="num">{_fmt_num(month["mandays"])}</td>'
			f'<td class="num">{_fmt_num(month["ot"])}</td>'
			"</tr>"
		)
		for key in (
			"closing_days",
			"total_days",
			"working_days",
			"male",
			"female",
			"employees",
			"male_mandays",
			"female_mandays",
			"mandays",
			"ot",
		):
			totals[key] += month[key]
	rows.append(
		'<tr class="total"><td></td><td class="left">Total</td>'
		f'<td class="num">{_fmt_num(totals["closing_days"])}</td>'
		f'<td class="num">{_fmt_num(totals["total_days"])}</td>'
		f'<td class="num">{_fmt_num(totals["working_days"])}</td>'
		f'<td class="num">{_fmt_num(totals["male"])}</td>'
		f'<td class="num">{_fmt_num(totals["female"])}</td>'
		f'<td class="num">{_fmt_num(totals["employees"])}</td>'
		f'<td class="num">{_fmt_num(totals["male_mandays"])}</td>'
		f'<td class="num">{_fmt_num(totals["female_mandays"])}</td>'
		f'<td class="num">{_fmt_num(totals["mandays"])}</td>'
		f'<td class="num">{_fmt_num(totals["ot"])}</td></tr>'
	)
	return (
		f"<h2>{_esc(company)} — Total Manpower — {year}</h2>"
		"<table><thead>"
		"<tr>"
		'<th rowspan="2">S.N.</th><th rowspan="2">Month</th>'
		'<th rowspan="2">Closing Days</th><th rowspan="2">Total Days</th>'
		'<th rowspan="2">Total Working Days</th>'
		'<th colspan="3">No. of Employees</th><th colspan="3">Mandays</th>'
		'<th rowspan="2">OT</th></tr>'
		"<tr><th>Male</th><th>Female</th><th>Total</th>"
		"<th>Male</th><th>Female</th><th>Total</th></tr>"
		f"</thead><tbody>{''.join(rows)}</tbody></table>"
	)


def _html_employment(pack, company, year):
	plant = pack["plant"]
	facts = (
		f'<table><tbody>'
		f'<tr><td class="center">1</td><td class="left">No of days plant was in operation</td>'
		f'<td class="num">{_fmt_num(plant["operation_days"])}</td>'
		f'<td class="left">Total days of year</td><td class="num">{_fmt_num(plant["year_days"])}</td></tr>'
		f'<tr><td class="center">2</td><td class="left">No of weeks plant was in operation</td>'
		f'<td class="num">{_fmt_num(plant["weeks"])}</td>'
		f'<td class="left">Total W. Off</td><td class="num">{_fmt_num(plant["weekly_offs"])}</td></tr>'
		f'<tr><td class="center">3</td><td class="left">Total hours per day workers working (excluding overtime)</td>'
		f'<td class="num">{_fmt_num(plant["hours_per_day"])}</td>'
		f'<td class="left">Total Holidays</td><td class="num">{_fmt_num(plant["holidays"])}</td></tr>'
		f"</tbody></table>"
	)
	by_key = {(row["band"], row["sex"]): row for row in pack["employment"]}
	rows = []
	for band, label in BANDS:
		cat = _esc(_category_label(label)).replace("\n", "<br>")
		for index, (sex, sex_label) in enumerate(SEXES):
			stat = by_key[(band, sex)]
			cat_cell = f'<td class="cat" rowspan="2">{cat}</td>' if index == 0 else ""
			rows.append(
				"<tr>"
				f"{cat_cell}"
				f'<td class="left">{_esc(sex_label)}</td>'
				f'<td class="num">{_fmt_num(stat["mandays"])}</td>'
				f'<td class="num">{_fmt_num(stat["average_workers"])}</td>'
				f'<td class="num">{_fmt_num(stat["ot_hours"])}</td>'
				f'<td class="num">{_fmt_num(stat["man_hours"])}</td>'
				f'<td class="num">{_fmt_num(stat["hours_per_week"])}</td>'
				"</tr>"
			)
	return (
		f"<h2>{_esc(company)} — Employment Information — {year}</h2>{facts}"
		'<div class="note">Number of labors and their details</div>'
		"<table><thead><tr>"
		"<th>Category of workers</th><th>Sex</th><th>No. of Mandays during the year</th>"
		"<th>Average number of Workers employed per day</th>"
		"<th>Number of man-hours worked on overtime in a year</th>"
		"<th>Number of manhours worked including overtime in a year</th>"
		"<th>Average number of hours worked per week</th>"
		f"</tr></thead><tbody>{''.join(rows)}</tbody></table>"
	)


def _html_left(pack, company, year):
	if not pack["left"]:
		body = '<tr><td colspan="19" class="left">No workers left in this year</td></tr>'
	else:
		rows = []
		for index, emp in enumerate(pack["left"], start=1):
			month_cells = "".join(
				f'<td class="num">{1 if month == emp["month"] else 0}</td>' for month in range(1, 13)
			)
			rows.append(
				"<tr>"
				f'<td class="center">{index}</td>'
				f'<td class="code">{_esc(emp["employee"])}</td>'
				f'<td class="name">{_esc(emp["employee_name"])}</td>'
				f'<td class="left">{_esc(emp["designation"])}</td>'
				f'<td class="date">{_esc(_fmt_date(emp["date_of_joining"]))}</td>'
				f'<td class="date">{_esc(_fmt_date(emp["left_date"]))}</td>'
				f'{month_cells}<td class="num">1</td>'
				"</tr>"
			)
		body = "".join(rows)
	cols = (
		'<colgroup>'
		'<col class="c-sr"><col class="c-code"><col class="c-name">'
		'<col class="c-desig"><col class="c-date"><col class="c-date">'
		+ "".join('<col class="c-m">' for _ in MONTHS)
		+ '<col class="c-tot"></colgroup>'
	)
	return (
		f"<h2>{_esc(company)} — Left Workers — {year}</h2>"
		f'<table class="work">{cols}<thead><tr>'
		"<th>SR.<br>NO.</th><th>EMP.<br>CODE</th><th>NAME OF WORKER</th>"
		"<th>DESIGNATION</th><th>DATE OF<br>JOINING</th><th>Exit<br>date</th>"
		f"{_month_heads(year)}<th>Total</th></tr></thead><tbody>{body}</tbody></table>"
	)


def _save_pdf(html, prefix):
	pdf = get_pdf(
		html,
		options={
			"page-size": "A4",
			"orientation": "Landscape",
			"margin-top": "8mm",
			"margin-right": "6mm",
			"margin-bottom": "8mm",
			"margin-left": "6mm",
			"encoding": "UTF-8",
			"no-outline": None,
		},
	)
	stamp = frappe.utils.now_datetime().strftime("%Y%m%d_%H%M%S")
	fn = f"{prefix}_{stamp}.pdf"
	with open(frappe.utils.get_files_path(fn, is_private=0), "wb") as handle:
		handle.write(pdf)
	doc = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": fn,
			"is_private": 0,
			"file_url": f"/files/{fn}",
		}
	)
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return doc.file_url


def _save_excel(wb, prefix):
	buf = io.BytesIO()
	wb.save(buf)
	stamp = frappe.utils.now_datetime().strftime("%Y%m%d_%H%M%S")
	fn = f"{prefix}_{stamp}.xlsx"
	with open(frappe.utils.get_files_path(fn, is_private=0), "wb") as handle:
		handle.write(buf.getvalue())
	doc = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": fn,
			"is_private": 0,
			"file_url": f"/files/{fn}",
		}
	)
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return doc.file_url


def _normalize_filters(filters):
	if isinstance(filters, str):
		filters = json.loads(filters or "{}")
	return frappe._dict(filters or {})


def _year(filters):
	year = cint(filters.get("year"))
	if year < 1900:
		return 0
	return year


def _as_date(value):
	if not value:
		return None
	if isinstance(value, datetime):
		return value.date()
	if isinstance(value, date):
		return value
	return getdate(value)


def _round_day(value):
	number = round(flt(value), 1)
	if abs(number - round(number)) < 1e-9:
		return int(round(number))
	return number


def _common_weekly_off(employees):
	counts = Counter((emp.get("weekly_off") or "").strip() for emp in employees)
	counts.pop("", None)
	if not counts:
		return WEEKDAYS["Sunday"]
	name = counts.most_common(1)[0][0]
	return WEEKDAYS.get(name, WEEKDAYS["Sunday"])


def _next_day(day):
	return date.fromordinal(day.toordinal() + 1)
