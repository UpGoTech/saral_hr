import frappe
from frappe.utils import getdate, get_last_day, flt, nowdate
import calendar
from datetime import timedelta, date
from saral_hr.utils.holiday_utils import get_holiday_list_for_date


# ─── Status groupings ─────────────────────────────────────────────────────────

PHYSICALLY_PRESENT  = {"Present", "On Tour", "Earned Comp Off"}
ON_LEAVE            = {"Earned Leave", "Casual Leave", "Comp Off"}
UNPAID              = {"Absent", "LWP"}
ALL_PAID            = PHYSICALLY_PRESENT | ON_LEAVE | {"Half Day"}
PRESENT_STATUSES    = PHYSICALLY_PRESENT | {"Half Day"}
ABSENT_STATUSES     = UNPAID


# ─── Permission helper ────────────────────────────────────────────────────────

def _get_permitted_employees():
    """
    Returns:
        None  → no restriction (System Manager or no Employee permissions set)
        []    → user has permissions set but zero employees allowed
        [...] → list of permitted Company Link name IDs
    """
    user = frappe.session.user

    if "System Manager" in frappe.get_roles(user):
        return None

    user_permissions = frappe.permissions.get_user_permissions(user)

    if "Employee" in user_permissions and user_permissions["Employee"]:
        permitted = [
            p.get("doc")
            for p in user_permissions["Employee"]
            if p.get("doc")
        ]
        return permitted if permitted else None

    return None


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _active_employees(company, department=None, permitted_employees=None):
    filters = {"is_active": 1, "company": company}
    if department:
        filters["department"] = department
    if permitted_employees is not None:
        if len(permitted_employees) == 0:
            return []
        filters["name"] = ["in", permitted_employees]

    return frappe.db.get_all(
        "Company Link",
        filters=filters,
        fields=["name", "full_name", "department", "designation"]
    )


def _attendance_for_date(company, att_date, department=None, permitted_employees=None):
    emp_clause = ""
    params = {"company": company, "att_date": str(att_date)}

    if department:
        dept_clause = "AND cl.department = %(department)s"
        params["department"] = department
    else:
        dept_clause = ""

    if permitted_employees is not None:
        if len(permitted_employees) == 0:
            return []
        placeholders = ", ".join([f"%(pe_{i})s" for i in range(len(permitted_employees))])
        emp_clause   = f"AND cl.name IN ({placeholders})"
        for i, e in enumerate(permitted_employees):
            params[f"pe_{i}"] = e

    sql = f"""
        SELECT a.employee, a.employee_name, a.status
        FROM `tabAttendance` a
        JOIN `tabCompany Link` cl ON cl.name = a.employee
        WHERE a.company = %(company)s
          AND a.attendance_date = %(att_date)s
          AND cl.is_active = 1
          {dept_clause}
          {emp_clause}
    """
    return frappe.db.sql(sql, params, as_dict=True)


def _attendance_for_range(company, from_date, to_date, department=None, permitted_employees=None):
    emp_clause = ""
    params = {
        "company":   company,
        "from_date": str(from_date),
        "to_date":   str(to_date),
    }

    if department:
        dept_clause = "AND cl.department = %(department)s"
        params["department"] = department
    else:
        dept_clause = ""

    if permitted_employees is not None:
        if len(permitted_employees) == 0:
            return []
        placeholders = ", ".join([f"%(pe_{i})s" for i in range(len(permitted_employees))])
        emp_clause   = f"AND cl.name IN ({placeholders})"
        for i, e in enumerate(permitted_employees):
            params[f"pe_{i}"] = e

    sql = f"""
        SELECT a.employee, a.employee_name, a.status,
               a.attendance_date, cl.department
        FROM `tabAttendance` a
        JOIN `tabCompany Link` cl ON cl.name = a.employee
        WHERE a.company = %(company)s
          AND a.attendance_date BETWEEN %(from_date)s AND %(to_date)s
          AND cl.is_active = 1
          {dept_clause}
          {emp_clause}
        ORDER BY a.attendance_date
    """
    return frappe.db.sql(sql, params, as_dict=True)


# ─── API: Filter meta ─────────────────────────────────────────────────────────

@frappe.whitelist()
def get_filter_meta(company):
    permitted = _get_permitted_employees()

    emp_clause = ""
    params = {"company": company}

    if permitted is not None:
        if len(permitted) == 0:
            return {"departments": []}
        placeholders = ", ".join([f"%(pe_{i})s" for i in range(len(permitted))])
        emp_clause   = f"AND name IN ({placeholders})"
        for i, e in enumerate(permitted):
            params[f"pe_{i}"] = e

    departments = frappe.db.sql(f"""
        SELECT DISTINCT department
        FROM `tabCompany Link`
        WHERE is_active = 1
          AND company = %(company)s
          AND department IS NOT NULL
          AND department != ''
          {emp_clause}
        ORDER BY department
    """, params, as_dict=True)

    return {"departments": [d.department for d in departments if d.department]}


# ─── API: Daily summary ───────────────────────────────────────────────────────

@frappe.whitelist()
def get_daily_summary(company, att_date=None, department=None):
    if not att_date:
        att_date = nowdate()
    att_date = getdate(att_date)

    permitted = _get_permitted_employees()

    employees    = _active_employees(company, department, permitted)
    total_active = len(employees)
    emp_map      = {e.name: e for e in employees}

    records  = _attendance_for_date(company, att_date, department, permitted)
    rec_map  = {r.employee: r for r in records}

    marked_ids = set(rec_map.keys())
    not_marked = [e for e in employees if e.name not in marked_ids]

    status_counts = {}
    for r in records:
        status_counts[r.status] = status_counts.get(r.status, 0) + 1

    physically_present = sum(status_counts.get(s, 0) for s in PHYSICALLY_PRESENT)
    on_leave_count     = sum(status_counts.get(s, 0) for s in ON_LEAVE)
    unpaid_count       = sum(status_counts.get(s, 0) for s in UNPAID)
    half_day_count     = status_counts.get("Half Day",   0)
    holiday_count      = status_counts.get("Holiday",    0)
    weekly_off_count   = status_counts.get("Weekly Off", 0)

    marked_list = []
    for r in records:
        emp = emp_map.get(r.employee)
        marked_list.append({
            "employee":    r.employee,
            "name":        (emp.full_name if emp else r.employee_name) or r.employee,
            "department":  (emp.department  if emp else "") or "—",
            "designation": (emp.designation if emp else "") or "—",
            "status":      r.status,
        })
    marked_list.sort(key=lambda x: x["name"])

    return {
        "date":               str(att_date),
        "total_active":       total_active,
        "marked_count":       len(marked_ids),
        "not_marked_count":   len(not_marked),
        "physically_present": physically_present,
        "on_leave_count":     on_leave_count,
        "half_day_count":     half_day_count,
        "unpaid_count":       unpaid_count,
        "holiday_count":      holiday_count,
        "weekly_off_count":   weekly_off_count,
        "status_breakdown":   status_counts,
        "marked_list":        marked_list,
        "not_marked_list": [
            {
                "employee":    e.name,
                "name":        e.full_name or e.name,
                "department":  e.department  or "—",
                "designation": e.designation or "—",
            }
            for e in not_marked
        ],
    }


# ─── API: Monthly summary ─────────────────────────────────────────────────────

@frappe.whitelist()
def get_monthly_summary(company, year, month, department=None):
    MONTHS    = ["January","February","March","April","May","June",
                 "July","August","September","October","November","December"]
    month_num  = MONTHS.index(month) + 1
    from_date  = date(int(year), month_num, 1)
    to_date    = get_last_day(from_date)
    total_days = calendar.monthrange(int(year), month_num)[1]

    permitted    = _get_permitted_employees()
    employees    = _active_employees(company, department, permitted)
    total_active = len(employees)

    records = _attendance_for_range(company, from_date, to_date, department, permitted)

    day_map = {}
    for r in records:
        d = getdate(r.attendance_date).day
        if d not in day_map:
            day_map[d] = {"present": 0, "absent": 0}
        if r.status in PRESENT_STATUSES:
            day_map[d]["present"] += 1
        elif r.status in ABSENT_STATUSES:
            day_map[d]["absent"]  += 1

    day_trend = []
    for day_num in range(1, total_days + 1):
        day_trend.append({
            "day":     day_num,
            "date":    f"{year}-{month_num:02d}-{day_num:02d}",
            "present": day_map.get(day_num, {}).get("present", 0),
            "absent":  day_map.get(day_num, {}).get("absent",  0),
        })

    emp_status_count = {}
    for r in records:
        emp = r.employee
        if emp not in emp_status_count:
            emp_status_count[emp] = {"present": 0, "absent": 0}
        if r.status in PRESENT_STATUSES:
            emp_status_count[emp]["present"] += 1
        elif r.status in ABSENT_STATUSES:
            emp_status_count[emp]["absent"]  += 1

    emp_attendance = []
    for emp in employees:
        counts = emp_status_count.get(emp.name, {"present": 0, "absent": 0})
        pct    = round((counts["present"] / total_days) * 100, 1) if total_days else 0
        emp_attendance.append({
            "employee":    emp.name,
            "name":        emp.full_name  or emp.name,
            "department":  emp.department  or "—",
            "designation": emp.designation or "—",
            "present":     counts["present"],
            "absent":      counts["absent"],
            "pct":         pct,
        })
    emp_attendance.sort(key=lambda x: x["pct"])

    overall = {}
    for r in records:
        overall[r.status] = overall.get(r.status, 0) + 1

    employees_with_any_record = len(set(r.employee for r in records))
    employees_never_marked    = total_active - employees_with_any_record

    today = date.today()
    if from_date.year == today.year and from_date.month == today.month:
        days_so_far = min(today.day, total_days)
    elif from_date > today:
        days_so_far = 0
    else:
        days_so_far = total_days

    return {
        "year":                     year,
        "month":                    month,
        "month_num":                month_num,
        "total_days":               total_days,
        "days_so_far":              days_so_far,
        "total_active":             total_active,
        "employees_with_records":   employees_with_any_record,
        "employees_never_marked":   employees_never_marked,
        "total_records_this_month": len(records),
        "day_trend":                day_trend,
        "emp_attendance":           emp_attendance,
        "overall":                  overall,
    }


# ─── API: Holidays for month ──────────────────────────────────────────────────

# Top pe add karo
from saral_hr.utils.holiday_utils import get_holiday_list_for_date

@frappe.whitelist()
def get_holidays_for_month(company, year, month):
    MONTHS    = ["January","February","March","April","May","June",
                 "July","August","September","October","November","December"]
    month_num  = MONTHS.index(month) + 1
    from_date  = date(int(year), month_num, 1)
    to_date    = get_last_day(from_date)

    # ✅ Period-wise list fetch karo
    holiday_list_name = get_holiday_list_for_date(str(from_date), company)
    if not holiday_list_name:
        return {"holidays": [], "total": 0}

    holidays = frappe.db.sql("""
        SELECT h.holiday_date, h.description
        FROM `tabHoliday` h
        WHERE h.parent = %(hl)s
          AND h.holiday_date BETWEEN %(from_date)s AND %(to_date)s
        ORDER BY h.holiday_date
    """, {"hl": holiday_list_name, "from_date": str(from_date), "to_date": str(to_date)}, as_dict=True)

    return {
        "holiday_list": holiday_list_name,
        "holidays": [
            {
                "date":        str(h.holiday_date),
                "description": h.description or "Holiday",
                "day":         getdate(h.holiday_date).strftime("%A"),
            }
            for h in holidays
        ],
        "total": len(holidays),
    }

# ─── API: Employee monthly detail ─────────────────────────────────────────────

@frappe.whitelist()
def get_employee_monthly_detail(employee, year, month):
    # ── Security check ────────────────────────────────────────────────────────
    permitted = _get_permitted_employees()
    if permitted is not None and employee not in permitted:
        return {}

    MONTHS    = ["January","February","March","April","May","June",
                 "July","August","September","October","November","December"]
    month_num  = MONTHS.index(month) + 1
    from_date  = date(int(year), month_num, 1)
    to_date    = get_last_day(from_date)
    total_days = calendar.monthrange(int(year), month_num)[1]

    records = frappe.db.get_all(
        "Attendance",
        filters={
            "employee":        employee,
            "attendance_date": ["between", [str(from_date), str(to_date)]],
        },
        fields=["attendance_date", "status", "working_hours"],
        order_by="attendance_date"
    )
    rec_map = {getdate(r.attendance_date).day: r for r in records}

    days = []
    for day_num in range(1, total_days + 1):
        r = rec_map.get(day_num)
        days.append({
            "day":           day_num,
            "date":          f"{year}-{month_num:02d}-{day_num:02d}",
            "status":        r.status if r else "Not Marked",
            "working_hours": flt(r.working_hours, 2) if r else 0,
        })

    status_summary = {}
    for r in records:
        status_summary[r.status] = status_summary.get(r.status, 0) + 1

    emp_info = frappe.db.get_value(
        "Company Link", employee,
        ["full_name", "department", "designation"],
        as_dict=True
    ) or {}

    return {
        "employee":       employee,
        "employee_name":  emp_info.get("full_name") or employee,
        "department":     emp_info.get("department")  or "—",
        "designation":    emp_info.get("designation") or "—",
        "days":           days,
        "status_summary": status_summary,
        "total_days":     total_days,
        "month_num":      month_num,
        "year":           int(year),
        "month":          month,
    }


# ─── Yearly headcount & marking coverage ──────────────────────────────────────

MONTH_NAMES = [
	"January", "February", "March", "April", "May", "June",
	"July", "August", "September", "October", "November", "December",
]


def _apply_cl_scope(filters, department=None, permitted=None):
	"""Return filters, or None if permitted is empty (no access)."""
	if permitted is not None and len(permitted) == 0:
		return None
	if department:
		filters["department"] = department
	if permitted is not None:
		filters["name"] = ["in", permitted]
	return filters


def _on_rolls_at(company, as_of, department=None, permitted=None):
	"""Company Links on rolls at end of as_of date (joining set, left after as_of)."""
	as_of = getdate(as_of)
	filters = _apply_cl_scope(
		{"company": company, "date_of_joining": ["<=", as_of]},
		department,
		permitted,
	)
	if filters is None:
		return []
	rows = frappe.db.get_all(
		"Company Link",
		filters=filters,
		fields=["name", "full_name", "department", "designation", "left_date"],
	)
	return [
		r for r in rows
		if not r.left_date or getdate(r.left_date) > as_of
	]


def _joined_in_month(company, month_start, month_end, department=None, permitted=None):
	filters = _apply_cl_scope(
		{
			"company": company,
			"date_of_joining": ["between", [month_start, month_end]],
		},
		department,
		permitted,
	)
	if filters is None:
		return []
	return frappe.db.get_all(
		"Company Link",
		filters=filters,
		fields=["name", "full_name", "department", "designation"],
	)


def _left_in_month(company, month_start, month_end, department=None, permitted=None):
	filters = _apply_cl_scope(
		{
			"company": company,
			"left_date": ["between", [month_start, month_end]],
		},
		department,
		permitted,
	)
	if filters is None:
		return []
	return frappe.db.get_all(
		"Company Link",
		filters=filters,
		fields=["name", "full_name", "department", "designation"],
	)


def _past_month_nums(year):
	"""Completed past months of year (exclude current + future)."""
	today = date.today()
	year = int(year)
	if year > today.year:
		return []
	if year < today.year:
		return list(range(1, 13))
	return list(range(1, today.month))


def _prev_month_end(year, month_num):
	if month_num == 1:
		return date(year - 1, 12, 31)
	return get_last_day(date(year, month_num - 1, 1))


def _attendance_day_counts(company, employee_ids, month_start, month_end):
	"""employee -> count of distinct attendance dates in range."""
	if not employee_ids:
		return {}
	rows = frappe.db.sql(
		"""
		SELECT employee, COUNT(DISTINCT attendance_date) AS cnt
		FROM `tabAttendance`
		WHERE company = %(company)s
		  AND employee IN %(employees)s
		  AND attendance_date BETWEEN %(from_date)s AND %(to_date)s
		GROUP BY employee
		""",
		{
			"company": company,
			"employees": list(employee_ids),
			"from_date": str(month_start),
			"to_date": str(month_end),
		},
		as_dict=True,
	)
	return {r.employee: int(r.cnt) for r in rows}


def _attendance_dates_map(company, employee_ids, month_start, month_end):
	"""employee -> set of attendance dates (date objects)."""
	if not employee_ids:
		return {}
	rows = frappe.db.sql(
		"""
		SELECT employee, attendance_date
		FROM `tabAttendance`
		WHERE company = %(company)s
		  AND employee IN %(employees)s
		  AND attendance_date BETWEEN %(from_date)s AND %(to_date)s
		""",
		{
			"company": company,
			"employees": list(employee_ids),
			"from_date": str(month_start),
			"to_date": str(month_end),
		},
		as_dict=True,
	)
	out = {}
	for r in rows:
		out.setdefault(r.employee, set()).add(getdate(r.attendance_date))
	return out


def _emp_row(r):
	return {
		"employee": r.name,
		"name": r.full_name or r.name,
		"department": r.department or "—",
		"designation": r.designation or "—",
	}


def _month_headcount(company, year, month_num, department=None, permitted=None):
	month_start = date(int(year), month_num, 1)
	month_end = get_last_day(month_start)
	total_days = calendar.monthrange(int(year), month_num)[1]
	prev_end = _prev_month_end(int(year), month_num)

	opening_rows = _on_rolls_at(company, prev_end, department, permitted)
	joined_rows = _joined_in_month(company, month_start, month_end, department, permitted)
	left_rows = _left_in_month(company, month_start, month_end, department, permitted)
	closing_rows = _on_rolls_at(company, month_end, department, permitted)

	opening_ids = {r.name for r in opening_rows}
	joined_ids = {r.name for r in joined_rows}
	strength_ids = opening_ids | joined_ids

	day_counts = _attendance_day_counts(company, strength_ids, month_start, month_end)
	marked_ids = {eid for eid in strength_ids if day_counts.get(eid, 0) >= total_days}
	not_marked_ids = strength_ids - marked_ids

	opening = len(opening_ids)
	joined = len(joined_ids)
	left = len(left_rows)
	# Spec identity; tenure closing set used for drill-down
	closing = opening + joined - left

	return {
		"month": MONTH_NAMES[month_num - 1],
		"month_num": month_num,
		"year": int(year),
		"opening": opening,
		"joined": joined,
		"left": left,
		"closing": closing,
		"total_strength": len(strength_ids),
		"marked": len(marked_ids),
		"not_marked": len(not_marked_ids),
		"total_days": total_days,
		"_opening_rows": opening_rows,
		"_joined_rows": joined_rows,
		"_left_rows": left_rows,
		"_closing_rows": closing_rows,
		"_strength_ids": strength_ids,
		"_marked_ids": marked_ids,
		"_not_marked_ids": not_marked_ids,
		"_month_start": month_start,
		"_month_end": month_end,
	}


@frappe.whitelist()
def get_yearly_summary(company, year, department=None):
	if not company:
		return {"months": [], "cards": {}}

	permitted = _get_permitted_employees()
	year = int(year)
	months = []

	for month_num in _past_month_nums(year):
		m = _month_headcount(company, year, month_num, department or None, permitted)
		months.append({
			"month": m["month"],
			"month_num": m["month_num"],
			"year": m["year"],
			"opening": m["opening"],
			"joined": m["joined"],
			"left": m["left"],
			"closing": m["closing"],
			"total_strength": m["total_strength"],
			"marked": m["marked"],
			"not_marked": m["not_marked"],
		})

	total_joined = sum(m["joined"] for m in months)
	total_left = sum(m["left"] for m in months)
	avg_closing = round(sum(m["closing"] for m in months) / len(months), 1) if months else 0
	sum_strength = sum(m["total_strength"] for m in months)
	sum_marked = sum(m["marked"] for m in months)
	coverage = round((sum_marked / sum_strength) * 100, 1) if sum_strength else 0

	return {
		"year": year,
		"months": months,
		"cards": {
			"joined": total_joined,
			"left": total_left,
			"avg_closing": avg_closing,
			"marked_coverage_pct": coverage,
		},
	}


@frappe.whitelist()
def get_yearly_employee_list(company, year, month, list_type, department=None):
	"""
	list_type: opening | joined | left | closing | marked | not_marked
	"""
	if not company or month not in MONTH_NAMES:
		return {"employees": []}

	month_num = MONTH_NAMES.index(month) + 1
	if month_num not in _past_month_nums(int(year)):
		return {"employees": []}

	permitted = _get_permitted_employees()
	m = _month_headcount(company, int(year), month_num, department or None, permitted)

	if list_type == "opening":
		return {"employees": [_emp_row(r) for r in m["_opening_rows"]]}
	if list_type == "joined":
		return {"employees": [_emp_row(r) for r in m["_joined_rows"]]}
	if list_type == "left":
		return {"employees": [_emp_row(r) for r in m["_left_rows"]]}
	if list_type == "closing":
		return {"employees": [_emp_row(r) for r in m["_closing_rows"]]}

	# Build name map for strength employees
	strength = list(m["_strength_ids"])
	info = {}
	if strength:
		for r in frappe.db.get_all(
			"Company Link",
			filters={"name": ["in", strength]},
			fields=["name", "full_name", "department", "designation"],
		):
			info[r.name] = r

	if list_type == "marked":
		emps = []
		for eid in sorted(m["_marked_ids"], key=lambda x: (info.get(x) or {}).get("full_name") or x):
			r = info.get(eid)
			emps.append({
				"employee": eid,
				"name": (r.full_name if r else None) or eid,
				"department": (r.department if r else None) or "—",
				"designation": (r.designation if r else None) or "—",
			})
		return {"employees": emps}

	if list_type == "not_marked":
		dates_map = _attendance_dates_map(
			company, m["_not_marked_ids"], m["_month_start"], m["_month_end"]
		)
		all_days = [
			m["_month_start"] + timedelta(days=i)
			for i in range(m["total_days"])
		]
		emps = []
		for eid in sorted(m["_not_marked_ids"], key=lambda x: (info.get(x) or {}).get("full_name") or x):
			have = dates_map.get(eid, set())
			missing = [d for d in all_days if d not in have]
			r = info.get(eid)
			emps.append({
				"employee": eid,
				"name": (r.full_name if r else None) or eid,
				"department": (r.department if r else None) or "—",
				"designation": (r.designation if r else None) or "—",
				"missing_count": len(missing),
				"missing_dates": [str(d) for d in missing],
			})
		return {
			"employees": emps,
			"mark_attendance_url": "/app/mark-attendance",
			"month": month,
			"year": int(year),
			"company": company,
		}

	return {"employees": []}
