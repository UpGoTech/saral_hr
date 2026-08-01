import frappe
from frappe.utils import getdate
import json


def _get_permitted_employees():
    """
    Returns the list of employee IDs (Company Link names) the session user
    may see, based on Frappe User Permissions.

    None  → no restriction (show all)
    []    → user has permissions set but 0 employees allowed
    [...] → restricted to this list
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


@frappe.whitelist()
def get_active_employees():
    user = frappe.session.user

    companies = frappe.get_all(
        "User Permission",
        filters={"user": user, "allow": "Company"},
        pluck="for_value"
    )

    filters = {}
    if companies:
        filters["company"] = ["in", companies]

    # ── Employee-level restriction ────────────────────────────────────────────
    permitted = _get_permitted_employees()
    if permitted is not None:
        if len(permitted) == 0:
            return []
        filters["name"] = ["in", permitted]

    employees = frappe.get_all(
        "Company Link",
        filters=filters,
        fields=["name", "employee", "full_name", "company", "weekly_off"],
        order_by="full_name asc"
    )

    for emp in employees:
        aadhaar = frappe.db.get_value("Employee", emp.employee, "aadhar_number")
        emp["aadhaar_number"] = aadhaar or ""

    return employees


@frappe.whitelist()
def search_employees(query, company=None):
    if not query or len(query.strip()) < 1:
        return []

    user        = frappe.session.user
    search_term = f"%{query.strip()}%"

    # ── Company-level restriction from User Permissions ───────────────────────
    permitted_companies = frappe.get_all(
        "User Permission",
        filters={"user": user, "allow": "Company"},
        pluck="for_value"
    )

    if company:
        companies = [company] if (not permitted_companies or company in permitted_companies) else []
    else:
        companies = permitted_companies

    company_filter = ""
    company_params = {}
    if companies:
        placeholders   = ", ".join([f"%(company_{i})s" for i in range(len(companies))])
        company_filter = f"AND cl.company IN ({placeholders})"
        for i, c in enumerate(companies):
            company_params[f"company_{i}"] = c

    # ── Employee-level restriction ────────────────────────────────────────────
    permitted_employees = _get_permitted_employees()
    emp_filter  = ""
    emp_params  = {}
    if permitted_employees is not None:
        if len(permitted_employees) == 0:
            return []
        placeholders = ", ".join([f"%(emp_{i})s" for i in range(len(permitted_employees))])
        emp_filter   = f"AND cl.name IN ({placeholders})"
        for i, e in enumerate(permitted_employees):
            emp_params[f"emp_{i}"] = e

    params = {"search": search_term, **company_params, **emp_params}

    results = frappe.db.sql(f"""
        SELECT
            cl.name,
            cl.employee,
            cl.full_name,
            cl.company,
            cl.weekly_off,
            e.aadhar_number,
            e.first_name,
            e.last_name
        FROM `tabCompany Link` cl
        LEFT JOIN `tabEmployee` e ON e.name = cl.employee
        WHERE 1=1
          {company_filter}
          {emp_filter}
          AND (
              cl.full_name LIKE %(search)s
              OR cl.employee LIKE %(search)s
              OR e.first_name LIKE %(search)s
              OR e.last_name LIKE %(search)s
              OR CONCAT(COALESCE(e.first_name, ''), ' ', COALESCE(e.last_name, '')) LIKE %(search)s
              OR e.aadhar_number LIKE %(search)s
          )
        ORDER BY cl.full_name ASC
        LIMIT 20
    """, params, as_dict=1)

    formatted = []
    for row in results:
        display_name = row.full_name or row.employee
        formatted.append({
            "name":           row.name,
            "employee":       row.employee,
            "full_name":      display_name,
            "company":        row.company,
            "weekly_off":     row.weekly_off or "",
            "aadhaar_number": row.aadhar_number or "",
            "emp_id":         row.employee or row.name,
        })

    return formatted


@frappe.whitelist()
def get_submitted_slip_months(employee):
    """
    Returns a dict of salary slip info keyed by month-start (YYYY-MM-DD) for
    the given employee. Both submitted (docstatus=1) and draft (docstatus=0)
    slips are returned so the UI can show appropriate warnings.

    Return format:
    {
        "2026-01-01": {"name": "SS-2026-01-001", "docstatus": 1},
        "2026-02-01": {"name": "SS-2026-02-003", "docstatus": 0},
        ...
    }
    """
    if not employee:
        return {}

    # ── Security: verify caller is permitted to view this employee ────────────
    permitted = _get_permitted_employees()
    if permitted is not None and employee not in permitted:
        return {}

    slips = frappe.db.get_all(
        "Salary Slip",
        filters={
            "employee": employee,
            "docstatus": ["in", [0, 1]],
        },
        fields=["name", "start_date", "docstatus"],
    )

    result = {}
    for slip in slips:
        if slip.start_date:
            key = str(slip.start_date)
            # Prefer submitted over draft if both exist for same month
            if key not in result or result[key]["docstatus"] == 0:
                result[key] = {
                    "name":      slip.name,
                    "docstatus": slip.docstatus,
                }

    return result


@frappe.whitelist()
def get_attendance_between_dates(employee, start_date, end_date):
    """
    Returns a dict  { "YYYY-MM-DD": <value> }  where <value> is either:
      - a plain string status  (for full-day records)
      - a dict { "mode": "half", "first_half": "...", "second_half": "..." }
        for half-day records that have custom_first_half / custom_second_half stored
    """
    # ── Security check ────────────────────────────────────────────────────────
    permitted = _get_permitted_employees()
    if permitted is not None and employee not in permitted:
        return {}

    start_date = getdate(start_date)
    end_date   = getdate(end_date)

    attendance_records = frappe.db.get_all(
        "Attendance",
        filters={
            "employee":        employee,
            "attendance_date": ["between", [start_date, end_date]],
            "docstatus":       ["<", 2],
        },
        fields=["attendance_date", "status", "custom_first_half", "custom_second_half"]
    )

    result = {}
    for row in attendance_records:
        date_str = str(row.attendance_date)
        if row.status == "Half Day" and (row.custom_first_half or row.custom_second_half):
            result[date_str] = {
                "mode":        "half",
                "first_half":  row.custom_first_half  or "",
                "second_half": row.custom_second_half or "",
            }
        else:
            result[date_str] = row.status

    return result


# ---------------------------------------------------------------------------
# Status constants
# ---------------------------------------------------------------------------

VALID_FULL_STATUSES = {
    "Present", "On Tour", "Earned Comp Off",
    "Absent", "Earned Leave", "Casual Leave", "Comp Off",
    "LWP", "Holiday", "Weekly Off",
}

VALID_HALF_STATUSES = {
    "Present", "On Tour", "Earned Comp Off",
    "Absent", "Earned Leave", "Casual Leave", "Comp Off", "LWP",
    "",
}

UI_TO_DB_STATUS = {
    "Regular": "Present",
}


def resolve_db_status(ui_status):
    return UI_TO_DB_STATUS.get(ui_status, ui_status)


# ---------------------------------------------------------------------------
# Save batch
# ---------------------------------------------------------------------------

@frappe.whitelist()
def save_attendance_batch(attendance_data):
    user = frappe.session.user

    if isinstance(attendance_data, str):
        attendance_data = json.loads(attendance_data)

    # ── Company-level permitted employees ─────────────────────────────────────
    companies = frappe.get_all(
        "User Permission",
        filters={"user": user, "allow": "Company"},
        pluck="for_value"
    )

    company_permitted_employees = None
    if companies:
        company_permitted_employees = set(
            frappe.get_all(
                "Company Link",
                filters={"company": ["in", companies]},
                pluck="name"
            )
        )

    # ── Employee-level permitted employees ────────────────────────────────────
    employee_level_permitted = _get_permitted_employees()

    saved_count = 0
    errors      = []

    try:
        for record in attendance_data:
            try:
                employee        = record.get("employee")
                attendance_date = getdate(record.get("attendance_date"))
                mode            = record.get("mode", "full")

                # Company-level check
                if company_permitted_employees is not None and employee not in company_permitted_employees:
                    errors.append(f"Not permitted for employee {employee} on {attendance_date}")
                    continue

                # Employee-level check
                if employee_level_permitted is not None and employee not in employee_level_permitted:
                    errors.append(f"Not permitted for employee {employee} on {attendance_date}")
                    continue

                # ── Salary slip lock check ─────────────────────────────────
                from frappe.utils import get_first_day
                month_start = str(get_first_day(attendance_date))
                submitted_slip = frappe.db.get_value(
                    "Salary Slip",
                    {
                        "employee":   employee,
                        "start_date": month_start,
                        "docstatus":  1,
                    },
                    "name"
                )
                if submitted_slip:
                    errors.append(
                        f"Cannot save attendance for {employee} on {attendance_date}: "
                        f"Salary Slip {submitted_slip} has been submitted for this month. "
                        f"Cancel the salary slip first."
                    )
                    continue

                # ── Determine DB values ────────────────────────────────────
                if mode == "half":
                    first_half  = (record.get("first_half")  or "").strip()
                    second_half = (record.get("second_half") or "").strip()

                    if first_half  not in VALID_HALF_STATUSES:
                        errors.append(f"Invalid first_half '{first_half}' for {employee} on {attendance_date}")
                        continue
                    if second_half not in VALID_HALF_STATUSES:
                        errors.append(f"Invalid second_half '{second_half}' for {employee} on {attendance_date}")
                        continue

                    db_status    = "Half Day"
                    extra_fields = {
                        "custom_first_half":  first_half,
                        "custom_second_half": second_half,
                    }

                else:
                    ui_status = record.get("status", "").strip()
                    if not ui_status or ui_status not in VALID_FULL_STATUSES:
                        continue
                    db_status    = resolve_db_status(ui_status)
                    extra_fields = {
                        "custom_first_half":  "",
                        "custom_second_half": "",
                    }

                # ── Upsert attendance record ───────────────────────────────
                existing = frappe.db.get_value(
                    "Attendance",
                    {
                        "employee":        employee,
                        "attendance_date": attendance_date,
                        "docstatus":       ["<", 2],
                    },
                    "name"
                )

                if existing:
                    update_vals = {"status": db_status, **extra_fields}
                    frappe.db.set_value(
                        "Attendance", existing, update_vals, update_modified=True
                    )
                else:
                    doc = frappe.get_doc({
                        "doctype":         "Attendance",
                        "employee":        employee,
                        "attendance_date": attendance_date,
                        "status":          db_status,
                        **extra_fields,
                    })
                    doc.flags.ignore_validate  = True
                    doc.flags.ignore_mandatory = True
                    doc.insert(ignore_permissions=True)

                saved_count += 1

            except Exception as e:
                error_msg = (
                    f"Error for {record.get('employee')} "
                    f"on {record.get('attendance_date')}: {str(e)}"
                )
                errors.append(error_msg)
                frappe.log_error(error_msg, "Mark Attendance Save Error")

        frappe.db.commit()

        return {
            "success":     True,
            "saved_count": saved_count,
            "errors":      errors if errors else None,
        }

    except Exception as e:
        frappe.db.rollback()
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Holidays
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_holidays_between_dates(company, start_date, end_date):
    if not company:
        return []

    from saral_hr.utils.holiday_utils import get_holiday_list_for_date

    # ✅ Date range mein unique holiday lists dhundho
    start = getdate(start_date)
    end   = getdate(end_date)

    # Sab dates ke liye holiday lists collect karo
    holiday_lists = set()
    current = start
    while current <= end:
        hl = get_holiday_list_for_date(str(current), company)
        if hl:
            holiday_lists.add(hl)
        # Month jump karo — har date loop karna expensive hai
        from datetime import timedelta
        current = current.replace(day=1)
        if current.month == 12:
            current = current.replace(year=current.year+1, month=1)
        else:
            current = current.replace(month=current.month+1)

    if not holiday_lists:
        return []

    # Sab lists se holidays fetch karo
    all_holidays = []
    for hl_name in holiday_lists:
        holidays = frappe.db.get_all(
            "Holiday",
            filters={
                "parent":       hl_name,
                "holiday_date": ["between", [start_date, end_date]],
            },
            pluck="holiday_date"
        )
        all_holidays.extend(holidays)

    # Duplicates remove karo
    return list(set(str(h) for h in all_holidays))

# ---------------------------------------------------------------------------
# Leave Allocation check
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_leave_allocation_for_month(employee, year, month):
    import datetime

    # ── Security check ────────────────────────────────────────────────────────
    permitted = _get_permitted_employees()
    if permitted is not None and employee not in permitted:
        return {"has_allocation": False, "allocation_name": None}

    try:
        year_int  = int(year)
        month_int = int(month) + 1
    except (ValueError, TypeError):
        return {"has_allocation": False, "allocation_name": None}

    month_start = datetime.date(year_int, month_int, 1)
    if month_int == 12:
        month_end = datetime.date(year_int + 1, 1, 1) - datetime.timedelta(days=1)
    else:
        month_end = datetime.date(year_int, month_int + 1, 1) - datetime.timedelta(days=1)

    alloc_name = frappe.db.get_value(
        "Leave Allocation",
        {
            "employee":  employee,
            "from_date": ["<=", str(month_start)],
            "to_date":   [">=", str(month_end)],
            "docstatus": ["<", 2],
        },
        "name"
    )

    return {
        "has_allocation":  bool(alloc_name),
        "allocation_name": alloc_name or None,
    }


# ---------------------------------------------------------------------------
# Comp Off / Leave balance
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_comp_off_balance(employee, year=None, month=None):
    import datetime

    # ── Security check ────────────────────────────────────────────────────────
    permitted = _get_permitted_employees()
    if permitted is not None and employee not in permitted:
        return {
            "el_allocated": 0, "el_used": 0.0, "el_remaining": 0.0,
            "cl_allocated": 0, "cl_used": 0.0, "cl_remaining": 0.0,
            "available": 0.0, "earned": 0.0, "used": 0.0, "balance": 0.0,
            "el_taken": 0.0, "cl_taken": 0.0,
        }

    try:
        year_int  = int(year)  if year  not in (None, "", "None") else None
        month_int = int(month) if month not in (None, "", "None") else None
    except (ValueError, TypeError):
        year_int  = None
        month_int = None

    def count_leave_taken(emp, leave_type, from_dt, to_dt):
        total = 0.0
        full_count = frappe.db.count(
            "Attendance",
            filters={
                "employee":        emp,
                "status":          leave_type,
                "attendance_date": ["between", [from_dt, to_dt]],
                "docstatus":       ["<", 2],
            }
        )
        total += float(full_count)
        h1_count = frappe.db.count(
            "Attendance",
            filters={
                "employee":           emp,
                "status":             "Half Day",
                "custom_first_half":  leave_type,
                "attendance_date":    ["between", [from_dt, to_dt]],
                "docstatus":          ["<", 2],
            }
        )
        total += float(h1_count) * 0.5
        h2_count = frappe.db.count(
            "Attendance",
            filters={
                "employee":            emp,
                "status":              "Half Day",
                "custom_second_half":  leave_type,
                "attendance_date":     ["between", [from_dt, to_dt]],
                "docstatus":           ["<", 2],
            }
        )
        total += float(h2_count) * 0.5
        return total

    def count_eco_or_coff(emp, status, from_dt, to_dt):
        full_count = frappe.db.count(
            "Attendance",
            filters={
                "employee":        emp,
                "status":          status,
                "attendance_date": ["between", [from_dt, to_dt]],
                "docstatus":       ["<", 2],
            }
        )
        return float(full_count)

    if year_int is not None and month_int is not None:
        month_1based = month_int + 1
        month_start  = datetime.date(year_int, month_1based, 1)
        if month_1based == 12:
            month_end = datetime.date(year_int + 1, 1, 1) - datetime.timedelta(days=1)
        else:
            month_end = datetime.date(year_int, month_1based + 1, 1) - datetime.timedelta(days=1)

        alloc = frappe.db.get_value(
            "Leave Allocation",
            {
                "employee":  employee,
                "from_date": ["<=", str(month_start)],
                "to_date":   [">=", str(month_end)],
                "docstatus": ["<", 2],
            },
            ["name", "from_date", "to_date"],
            as_dict=True
        )

        if alloc:
            details = frappe.get_all(
                "Leave Allocation Detail",
                filters={"parent": alloc.name},
                fields=["leave_type", "allocated_leaves"]
            )
            allocated_map = {d.leave_type: (d.allocated_leaves or 0) for d in details}
            el_allocated  = allocated_map.get("Earned Leave", 0)
            cl_allocated  = allocated_map.get("Casual Leave", 0)
            alloc_start   = alloc.from_date
            alloc_end     = alloc.to_date
            el_used = count_leave_taken(employee, "Earned Leave", alloc_start, alloc_end)
            cl_used = count_leave_taken(employee, "Casual Leave", alloc_start, alloc_end)
        else:
            el_allocated = 0
            cl_allocated = 0
            el_used      = 0.0
            cl_used      = 0.0

        el_remaining = max(0.0, float(el_allocated) - el_used)
        cl_remaining = max(0.0, float(cl_allocated) - cl_used)

        earned_before = count_eco_or_coff(employee, "Earned Comp Off", "2000-01-01", month_start - datetime.timedelta(days=1))
        used_before   = count_leave_taken(employee, "Comp Off", "2000-01-01", month_start - datetime.timedelta(days=1))
        available     = max(0.0, earned_before - used_before)
        earned        = count_eco_or_coff(employee, "Earned Comp Off", month_start, month_end)
        co_used       = count_leave_taken(employee, "Comp Off", month_start, month_end)
        balance       = max(0.0, available + earned - co_used)

    else:
        el_allocated = 0
        cl_allocated = 0
        el_used      = 0.0
        cl_used      = 0.0
        el_remaining = 0.0
        cl_remaining = 0.0
        available    = 0.0
        earned       = float(frappe.db.count("Attendance", filters={
            "employee": employee, "status": "Earned Comp Off", "docstatus": ["<", 2],
        }))
        co_used = float(frappe.db.count("Attendance", filters={
            "employee": employee, "status": "Comp Off", "docstatus": ["<", 2],
        }))
        balance = max(0.0, earned - co_used)

    return {
        "el_allocated": el_allocated,
        "el_used":      el_used,
        "el_remaining": el_remaining,
        "cl_allocated": cl_allocated,
        "cl_used":      cl_used,
        "cl_remaining": cl_remaining,
        "available":    available,
        "earned":       earned,
        "used":         co_used,
        "balance":      balance,
        "el_taken":     el_used,
        "cl_taken":     cl_used,
    }


# ---------------------------------------------------------------------------
# Joining / left date
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_employee_joining_date(employee):
    # ── Security check ────────────────────────────────────────────────────────
    permitted = _get_permitted_employees()
    if permitted is not None and employee not in permitted:
        return {"joining_date": None, "left_date": None}

    result = frappe.db.get_value(
        "Company Link",
        employee,
        ["date_of_joining", "left_date"],
        as_dict=True
    )
    if not result:
        return {"joining_date": None, "left_date": None}
    return {
        "joining_date": str(result.date_of_joining) if result.date_of_joining else None,
        "left_date":    str(result.left_date)        if result.left_date        else None,
    }


# ---------------------------------------------------------------------------
# Outside-tenure Absent (pre-joining / post-left)
# ---------------------------------------------------------------------------

@frappe.whitelist()
def ensure_outside_tenure_absent(employee, start_date, end_date):
    """
    Persist Absent for past days before date_of_joining or after left_date.

    Mark Attendance keeps those rows non-editable; without a stored status the
    month has blank days. Recording Absent fills them while still blocking edits.
    """
    import datetime
    from frappe.utils import get_first_day, today

    permitted = _get_permitted_employees()
    if permitted is not None and employee not in permitted:
        return {"created": 0}

    if not employee or not start_date or not end_date:
        return {"created": 0}

    cl = frappe.db.get_value(
        "Company Link",
        employee,
        ["date_of_joining", "left_date"],
        as_dict=True,
    )
    if not cl:
        return {"created": 0}

    joining = getdate(cl.date_of_joining) if cl.date_of_joining else None
    left = getdate(cl.left_date) if cl.left_date else None
    if not joining and not left:
        return {"created": 0}

    start = getdate(start_date)
    end = getdate(end_date)
    today_date = getdate(today())
    created = 0

    current = start
    while current <= end:
        if current > today_date:
            current += datetime.timedelta(days=1)
            continue

        outside = (joining and current < joining) or (left and current > left)
        if not outside:
            current += datetime.timedelta(days=1)
            continue

        month_start = str(get_first_day(current))
        if frappe.db.exists(
            "Salary Slip",
            {"employee": employee, "start_date": month_start, "docstatus": 1},
        ):
            current += datetime.timedelta(days=1)
            continue

        existing = frappe.db.get_value(
            "Attendance",
            {
                "employee": employee,
                "attendance_date": current,
                "docstatus": ["<", 2],
            },
            "name",
        )
        if existing:
            current += datetime.timedelta(days=1)
            continue

        doc = frappe.get_doc(
            {
                "doctype": "Attendance",
                "employee": employee,
                "attendance_date": current,
                "status": "Absent",
                "custom_first_half": "",
                "custom_second_half": "",
            }
        )
        doc.flags.ignore_validate = True
        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True)
        created += 1
        current += datetime.timedelta(days=1)

    if created:
        frappe.db.commit()

    return {"created": created}