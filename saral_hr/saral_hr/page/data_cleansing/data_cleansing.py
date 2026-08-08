# Copyright (c) 2026, sj and contributors
# For license information, please see license.txt

"""Data Cleansing page APIs — see specs/007-data-cleansing.md"""

from __future__ import annotations

import calendar
import json
from datetime import date

import frappe
from frappe import _
from frappe.utils import get_first_day, get_last_day, getdate

MONTH_NAMES = [
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
]

DOCSTATUS_LABEL = {0: "Draft", 1: "Submitted", 2: "Cancelled"}

MUTATE_ROLES = {"Administrator", "System Manager", "Saral HR Manager"}
VIEW_ROLES = MUTATE_ROLES | {"Saral HR User"}


def _user_roles():
	return set(frappe.get_roles(frappe.session.user))


def _assert_can_view():
	if frappe.session.user == "Administrator":
		return
	if not (_user_roles() & VIEW_ROLES):
		frappe.throw(_("Not permitted"), frappe.PermissionError)


def _assert_can_mutate():
	if frappe.session.user == "Administrator":
		return
	roles = _user_roles()
	if "System Manager" in roles or "Saral HR Manager" in roles:
		return
	frappe.throw(_("Only Saral HR Manager or Administrator can cleanse data"), frappe.PermissionError)


def _month_bounds(year: int, month: int):
	start = date(int(year), int(month), 1)
	end = date(int(year), int(month), calendar.monthrange(int(year), int(month))[1])
	return start, end


def _iter_months(from_year, from_month, to_year, to_month):
	y, m = int(from_year), int(from_month)
	ey, em = int(to_year), int(to_month)
	if (y, m) > (ey, em):
		frappe.throw(_("From month must be on or before To month"))
	while (y, m) <= (ey, em):
		yield y, m
		if m == 12:
			y, m = y + 1, 1
		else:
			m += 1


def _tenure(employee: str):
	row = frappe.db.get_value(
		"Company Link",
		employee,
		["full_name", "company", "date_of_joining", "left_date"],
		as_dict=True,
	)
	if not row:
		frappe.throw(_("Employee {0} not found").format(employee))
	return row


def _expected_days(month_start: date, month_end: date, joining, left) -> int:
	if not joining:
		return 0
	join = getdate(joining)
	leave = getdate(left) if left else None
	if join > month_end:
		return 0
	if leave and leave < month_start:
		return 0
	start = max(month_start, join)
	end = min(month_end, leave) if leave else month_end
	if start > end:
		return 0
	return (end - start).days + 1


def _outside_tenure_dates(dates, joining, left) -> bool:
	if not dates:
		return False
	join = getdate(joining) if joining else None
	leave = getdate(left) if left else None
	for d in dates:
		gd = getdate(d)
		if join and gd < join:
			return True
		if leave and gd > leave:
			return True
	return False


def _write_log(*, employee, company, month_start, action, reference_names, counts, reason=None):
	doc = frappe.get_doc(
		{
			"doctype": "Data Cleansing Log",
			"employee": employee,
			"company": company,
			"month_start": month_start,
			"action": action,
			"reference_names": (
				json.dumps(reference_names)
				if isinstance(reference_names, (list, dict))
				else (reference_names or "")
			),
			"counts": counts or 0,
			"reason": reason or "",
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _slips_for_month(employee: str, month_start: date, month_end: date):
	return frappe.db.get_all(
		"Salary Slip",
		filters={
			"employee": employee,
			"start_date": ["between", [str(month_start), str(month_end)]],
		},
		fields=["name", "docstatus", "start_date", "end_date", "net_salary"],
		order_by="docstatus asc, name asc",
	)


def _attendance_for_month(employee: str, month_start: date, month_end: date):
	return frappe.db.get_all(
		"Attendance",
		filters={
			"employee": employee,
			"attendance_date": ["between", [str(month_start), str(month_end)]],
		},
		fields=["name", "attendance_date", "status", "docstatus"],
		order_by="attendance_date asc",
	)


def _build_month_row(employee: str, tenure, year: int, month: int):
	month_start, month_end = _month_bounds(year, month)
	attendance = _attendance_for_month(employee, month_start, month_end)
	slips = _slips_for_month(employee, month_start, month_end)
	if not attendance and not slips:
		return None

	att_days = len(attendance)
	expected = _expected_days(month_start, month_end, tenure.date_of_joining, tenure.left_date)
	att_dates = [a.attendance_date for a in attendance]
	slip_dates = [s.start_date for s in slips]

	if expected == 0:
		coverage = "Outside tenure"
	elif att_days == 0:
		coverage = "None"
	elif att_days >= expected:
		coverage = "Full"
	else:
		coverage = "Partial"

	flags = []
	if att_days and not slips:
		flags.append("Attendance only")
	if slips and att_days == 0:
		flags.append("Slip only")
	if _outside_tenure_dates(att_dates + slip_dates, tenure.date_of_joining, tenure.left_date):
		flags.append("Outside tenure")
	if expected > 0 and 0 < att_days < expected:
		flags.append("Partial coverage")
	if any(s.docstatus == 0 for s in slips):
		flags.append("Draft slip")

	statuses = sorted({DOCSTATUS_LABEL.get(s.docstatus, str(s.docstatus)) for s in slips})

	return {
		"year": year,
		"month": month,
		"month_label": f"{MONTH_NAMES[month - 1][:3]} {year}",
		"month_start": str(month_start),
		"month_end": str(month_end),
		"attendance_days": att_days,
		"expected_days": expected,
		"coverage": coverage,
		"slips": [
			{
				"name": s.name,
				"docstatus": s.docstatus,
				"status": DOCSTATUS_LABEL.get(s.docstatus, str(s.docstatus)),
				"start_date": str(s.start_date) if s.start_date else None,
				"net_salary": s.net_salary,
			}
			for s in slips
		],
		"slip_names": ", ".join(s.name for s in slips) if slips else "—",
		"slip_status": ", ".join(statuses) if statuses else "—",
		"flags": flags,
		"can_delete_attendance": len(slips) == 0 and att_days > 0,
	}


@frappe.whitelist()
def can_mutate():
	_assert_can_view()
	try:
		_assert_can_mutate()
		return True
	except frappe.PermissionError:
		return False


@frappe.whitelist()
def get_employee_month_matrix(employee, from_year, from_month, to_year, to_month):
	"""Return month rows that have attendance and/or salary slips in range."""
	_assert_can_view()
	if not employee:
		frappe.throw(_("Employee is required"))

	tenure = _tenure(employee)
	rows = []
	for y, m in _iter_months(from_year, from_month, to_year, to_month):
		row = _build_month_row(employee, tenure, y, m)
		if row:
			rows.append(row)

	return {
		"employee": employee,
		"employee_name": tenure.full_name,
		"company": tenure.company,
		"date_of_joining": str(tenure.date_of_joining) if tenure.date_of_joining else None,
		"left_date": str(tenure.left_date) if tenure.left_date else None,
		"can_mutate": bool(
			frappe.session.user == "Administrator"
			or (_user_roles() & {"System Manager", "Saral HR Manager"})
		),
		"months": rows,
	}


@frappe.whitelist()
def get_month_detail(employee, year, month):
	_assert_can_view()
	tenure = _tenure(employee)
	month_start, month_end = _month_bounds(year, month)
	attendance = _attendance_for_month(employee, month_start, month_end)
	slips = _slips_for_month(employee, month_start, month_end)
	row = _build_month_row(employee, tenure, int(year), int(month))

	return {
		"employee": employee,
		"employee_name": tenure.full_name,
		"company": tenure.company,
		"month_start": str(month_start),
		"month_end": str(month_end),
		"summary": row,
		"attendance": [
			{
				"name": a.name,
				"attendance_date": str(a.attendance_date),
				"status": a.status,
			}
			for a in attendance
		],
		"slips": [
			{
				"name": s.name,
				"docstatus": s.docstatus,
				"status": DOCSTATUS_LABEL.get(s.docstatus, str(s.docstatus)),
				"start_date": str(s.start_date) if s.start_date else None,
				"net_salary": s.net_salary,
			}
			for s in slips
		],
		"can_mutate": bool(
			frappe.session.user == "Administrator"
			or (_user_roles() & {"System Manager", "Saral HR Manager"})
		),
	}


def _month_has_any_slip(employee: str, month_start: date, month_end: date) -> bool:
	return bool(
		frappe.db.exists(
			"Salary Slip",
			{
				"employee": employee,
				"start_date": ["between", [str(month_start), str(month_end)]],
			},
		)
	)


@frappe.whitelist()
def delete_attendance(employee, names=None, year=None, month=None, reason=None):
	"""Delete attendance by name list or whole month. Blocked if any slip exists."""
	_assert_can_mutate()
	if not employee:
		frappe.throw(_("Employee is required"))

	tenure = _tenure(employee)

	if names:
		if isinstance(names, str):
			names = json.loads(names)
		rows = frappe.db.get_all(
			"Attendance",
			filters={"name": ["in", names], "employee": employee},
			fields=["name", "attendance_date"],
		)
		if not rows:
			frappe.throw(_("No matching attendance found"))
		# Use earliest date's month for slip check / log
		dates = [getdate(r.attendance_date) for r in rows]
		month_start = get_first_day(min(dates))
		month_end = get_last_day(min(dates))
	elif year and month:
		month_start, month_end = _month_bounds(year, month)
		rows = _attendance_for_month(employee, month_start, month_end)
		if not rows:
			frappe.throw(_("No attendance found for this month"))
	else:
		frappe.throw(_("Provide attendance names or year/month"))

	if _month_has_any_slip(employee, month_start, month_end):
		frappe.throw(
			_(
				"Cannot delete attendance while a Salary Slip exists for {0}. "
				"Remove Draft, Submitted, and Cancelled slips for this month first."
			).format(month_start.strftime("%b %Y"))
		)

	deleted = []
	for r in rows:
		frappe.delete_doc("Attendance", r.name, ignore_permissions=True, force=1)
		deleted.append(r.name)

	log_name = _write_log(
		employee=employee,
		company=tenure.company,
		month_start=month_start,
		action="delete_attendance",
		reference_names=deleted,
		counts=len(deleted),
		reason=reason,
	)
	return {"deleted": deleted, "count": len(deleted), "log": log_name}


@frappe.whitelist()
def cancel_salary_slip(name, reason=None):
	_assert_can_mutate()
	doc = frappe.get_doc("Salary Slip", name)
	if doc.docstatus != 1:
		frappe.throw(_("Salary Slip {0} is not Submitted").format(name))
	doc.cancel()
	log_name = _write_log(
		employee=doc.employee,
		company=doc.company,
		month_start=get_first_day(getdate(doc.start_date)),
		action="cancel_salary_slip",
		reference_names=[name],
		counts=1,
		reason=reason,
	)
	return {"name": name, "docstatus": 2, "log": log_name}


@frappe.whitelist()
def delete_salary_slip(name, reason=None):
	_assert_can_mutate()
	doc = frappe.get_doc("Salary Slip", name)
	if doc.docstatus == 1:
		frappe.throw(
			_("Cancel Salary Slip {0} before deleting").format(name)
		)
	employee = doc.employee
	company = doc.company
	month_start = get_first_day(getdate(doc.start_date))
	frappe.delete_doc("Salary Slip", name, ignore_permissions=True, force=1)
	log_name = _write_log(
		employee=employee,
		company=company,
		month_start=month_start,
		action="delete_salary_slip",
		reference_names=[name],
		counts=1,
		reason=reason,
	)
	return {"deleted": name, "log": log_name}
