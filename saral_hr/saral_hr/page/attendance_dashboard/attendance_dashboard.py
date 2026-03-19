import frappe
from frappe.utils import getdate, get_last_day, get_first_day, flt, nowdate
import calendar
from datetime import timedelta, date


PRESENT_STATUSES = {"Present", "On Tour", "Earned Leave", "Casual Leave",
                    "Comp Off", "Earned Comp Off", "Half Day"}
ABSENT_STATUSES  = {"Absent", "LWP"}
LEAVE_STATUSES   = {"Earned Leave", "Casual Leave", "LWP"}


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _active_employees(company, department=None, designation=None):
    filters = {"is_active": 1, "company": company}
    if department:
        filters["department"] = department
    if designation:
        filters["designation"] = designation
    return frappe.db.get_all(
        "Company Link",
        filters=filters,
        fields=["name", "full_name", "department", "designation", "holiday_list"]
    )


def _attendance_for_date(company, att_date, department=None):
    sql = """
        SELECT a.employee, a.employee_name, a.status, a.working_hours
        FROM `tabAttendance` a
        JOIN `tabCompany Link` cl ON cl.name = a.employee
        WHERE a.company = %(company)s
          AND a.attendance_date = %(att_date)s
          AND cl.is_active = 1
          {dept}
    """.format(dept="AND cl.department = %(department)s" if department else "")
    params = {"company": company, "att_date": str(att_date)}
    if department:
        params["department"] = department
    return frappe.db.sql(sql, params, as_dict=True)


def _attendance_for_range(company, from_date, to_date, department=None):
    sql = """
        SELECT a.employee, a.employee_name, a.status,
               a.attendance_date, cl.department
        FROM `tabAttendance` a
        JOIN `tabCompany Link` cl ON cl.name = a.employee
        WHERE a.company = %(company)s
          AND a.attendance_date BETWEEN %(from_date)s AND %(to_date)s
          AND cl.is_active = 1
          {dept}
        ORDER BY a.attendance_date
    """.format(dept="AND cl.department = %(department)s" if department else "")
    params = {"company": company, "from_date": str(from_date), "to_date": str(to_date)}
    if department:
        params["department"] = department
    return frappe.db.sql(sql, params, as_dict=True)


# ─── API: Filters Meta ────────────────────────────────────────────────────────

@frappe.whitelist()
def get_filter_meta(company):
    """Return departments list for the company."""
    departments = frappe.db.sql("""
        SELECT DISTINCT department
        FROM `tabCompany Link`
        WHERE is_active = 1
          AND company = %(company)s
          AND department IS NOT NULL
          AND department != ''
        ORDER BY department
    """, {"company": company}, as_dict=True)
    return {"departments": [d.department for d in departments if d.department]}


# ─── API: Daily Summary ───────────────────────────────────────────────────────

@frappe.whitelist()
def get_daily_summary(company, att_date=None, department=None):
    """Summary cards + not-marked list for a single date."""
    if not att_date:
        att_date = nowdate()
    att_date = getdate(att_date)

    employees   = _active_employees(company, department)
    total_active = len(employees)
    emp_ids      = {e.name for e in employees}

    records = _attendance_for_date(company, att_date, department)
    rec_map  = {r.employee: r for r in records}

    marked_ids   = set(rec_map.keys())
    not_marked   = [e for e in employees if e.name not in marked_ids]

    status_counts = {}
    for r in records:
        status_counts[r.status] = status_counts.get(r.status, 0) + 1

    present_count = sum(status_counts.get(s, 0) for s in PRESENT_STATUSES)
    absent_count  = sum(status_counts.get(s, 0) for s in ABSENT_STATUSES)
    leave_count   = sum(status_counts.get(s, 0) for s in LEAVE_STATUSES)
    not_marked_count = len(not_marked)

    # Build marked list with employee details + their status
    emp_map = {e.name: e for e in employees}
    marked_list = []
    for r in records:
        emp = emp_map.get(r.employee)
        marked_list.append({
            "employee":    r.employee,
            "name":        (emp.full_name if emp else r.employee_name) or r.employee,
            "department":  (emp.department if emp else "") or "—",
            "designation": (emp.designation if emp else "") or "—",
            "status":      r.status,
        })
    # Sort marked list by name
    marked_list.sort(key=lambda x: x["name"])

    return {
        "date":              str(att_date),
        "total_active":      total_active,
        "marked":            len(marked_ids),
        "not_marked_count":  not_marked_count,
        "present":           present_count,
        "absent":            absent_count,
        "on_leave":          leave_count,
        "half_day":          status_counts.get("Half Day", 0),
        "holiday":           status_counts.get("Holiday", 0),
        "weekly_off":        status_counts.get("Weekly Off", 0),
        "status_breakdown":  status_counts,
        "marked_list":       marked_list,
        "not_marked_list":   [
            {
                "employee":    e.name,
                "name":        e.full_name or e.name,
                "department":  e.department or "—",
                "designation": e.designation or "—",
            }
            for e in not_marked
        ],
    }


# ─── API: Monthly Summary ─────────────────────────────────────────────────────

@frappe.whitelist()
def get_monthly_summary(company, year, month, department=None):
    """
    Day-wise trend + department table + overall stats for a month.
    """
    MONTHS = ["January","February","March","April","May","June",
              "July","August","September","October","November","December"]
    month_num  = MONTHS.index(month) + 1
    from_date  = date(int(year), month_num, 1)
    to_date    = get_last_day(from_date)
    total_days = calendar.monthrange(int(year), month_num)[1]

    employees    = _active_employees(company, department)
    total_active = len(employees)
    emp_ids      = {e.name for e in employees}

    records = _attendance_for_range(company, from_date, to_date, department)

    # Day-wise counts
    day_map = {}
    for r in records:
        d = str(getdate(r.attendance_date).day)
        if d not in day_map:
            day_map[d] = {"present": 0, "absent": 0, "leave": 0, "other": 0}
        if r.status in PRESENT_STATUSES:
            day_map[d]["present"] += 1
        elif r.status in ABSENT_STATUSES:
            day_map[d]["absent"] += 1
        elif r.status in LEAVE_STATUSES:
            day_map[d]["leave"] += 1
        else:
            day_map[d]["other"] += 1

    day_trend = []
    for day in range(1, total_days + 1):
        d = str(day)
        day_trend.append({
            "day":     day,
            "date":    f"{year}-{month_num:02d}-{day:02d}",
            "present": day_map.get(d, {}).get("present", 0),
            "absent":  day_map.get(d, {}).get("absent",  0),
            "leave":   day_map.get(d, {}).get("leave",   0),
        })

    # Department-wise summary
    dept_map = {}
    for emp in employees:
        dept = emp.department or "Unassigned"
        if dept not in dept_map:
            dept_map[dept] = {"total": 0, "present": 0, "absent": 0, "not_marked": 0}
        dept_map[dept]["total"] += 1

    # Count per employee for the whole month
    emp_status_count = {}
    for r in records:
        emp = r.employee
        if emp not in emp_status_count:
            emp_status_count[emp] = {"present": 0, "absent": 0}
        if r.status in PRESENT_STATUSES:
            emp_status_count[emp]["present"] += 1
        elif r.status in ABSENT_STATUSES:
            emp_status_count[emp]["absent"] += 1

    # Attendance % per employee
    emp_attendance = []
    for emp in employees:
        counts = emp_status_count.get(emp.name, {"present": 0, "absent": 0})
        pct = round((counts["present"] / total_days) * 100, 1) if total_days else 0
        emp_attendance.append({
            "employee":    emp.name,
            "name":        emp.full_name or emp.name,
            "department":  emp.department or "—",
            "designation": emp.designation or "—",
            "present":     counts["present"],
            "absent":      counts["absent"],
            "pct":         pct,
        })
    emp_attendance.sort(key=lambda x: x["pct"])

    # Overall month status counts
    overall = {}
    for r in records:
        overall[r.status] = overall.get(r.status, 0) + 1

    # Monthly attendance coverage stats
    # Count employees who have AT LEAST ONE attendance record this month
    employees_with_any_record = len(set(r.employee for r in records))
    employees_never_marked    = total_active - employees_with_any_record

    # Count working days so far in month (past + today, not future)
    from datetime import date as date_cls
    today = date_cls.today()
    if from_date.year == today.year and from_date.month == today.month:
        days_so_far = min(today.day, total_days)
    elif from_date > today:
        days_so_far = 0
    else:
        days_so_far = total_days

    # Total possible records so far = active employees x days elapsed
    total_possible = total_active * days_so_far
    total_marked_records = sum(
        emp_status_count.get(e.name, {}).get("present", 0) +
        emp_status_count.get(e.name, {}).get("absent", 0)
        for e in employees
    ) if employees else 0
    # More accurate: count all records
    total_records_this_month = len(records)

    return {
        "year":                     year,
        "month":                    month,
        "month_num":                month_num,
        "total_days":               total_days,
        "days_so_far":              days_so_far,
        "total_active":             total_active,
        "employees_with_records":   employees_with_any_record,
        "employees_never_marked":   employees_never_marked,
        "total_records_this_month": total_records_this_month,
        "total_possible":           total_possible,
        "day_trend":                day_trend,
        "emp_attendance":           emp_attendance,
        "overall":                  overall,
    }


# ─── API: Holiday List ────────────────────────────────────────────────────────

@frappe.whitelist()
def get_holidays_for_month(company, year, month):
    """Return holidays from the company's default holiday list for a month."""
    MONTHS = ["January","February","March","April","May","June",
              "July","August","September","October","November","December"]
    month_num = MONTHS.index(month) + 1
    from_date = date(int(year), month_num, 1)
    to_date   = get_last_day(from_date)

    holiday_list_name = frappe.db.get_value("Company", company, "default_holiday_list")
    if not holiday_list_name:
        return {"holidays": [], "total": 0}

    holidays = frappe.db.sql("""
        SELECT h.holiday_date, h.description
        FROM `tabHoliday` h
        JOIN `tabHoliday List` hl ON hl.name = h.parent
        WHERE hl.name = %(hl)s
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


# ─── API: Employee Monthly Detail ────────────────────────────────────────────

@frappe.whitelist()
def get_employee_monthly_detail(employee, year, month):
    """Day-wise attendance for a single employee in a month."""
    MONTHS = ["January","February","March","April","May","June",
              "July","August","September","October","November","December"]
    month_num  = MONTHS.index(month) + 1
    from_date  = date(int(year), month_num, 1)
    to_date    = get_last_day(from_date)
    total_days = calendar.monthrange(int(year), month_num)[1]

    records = frappe.db.get_all(
        "Attendance",
        filters={"employee": employee, "attendance_date": ["between", [str(from_date), str(to_date)]]},
        fields=["attendance_date", "status", "working_hours"],
        order_by="attendance_date"
    )
    rec_map = {getdate(r.attendance_date).day: r for r in records}

    days = []
    for day in range(1, total_days + 1):
        r = rec_map.get(day)
        days.append({
            "day":    day,
            "date":   f"{year}-{month_num:02d}-{day:02d}",
            "status": r.status if r else "Not Marked",
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
        "department":     emp_info.get("department") or "—",
        "designation":    emp_info.get("designation") or "—",
        "days":           days,
        "status_summary": status_summary,
        "total_days":     total_days,
        "month_num":      month_num,
        "year":           int(year),
        "month":          month,
    }