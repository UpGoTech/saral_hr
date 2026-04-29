import frappe
from frappe.utils import getdate
import json


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

    permitted = frappe.get_all(
        "User Permission",
        filters={"user": user, "allow": "Company"},
        pluck="for_value"
    )

    if company:
        companies = [company] if (not permitted or company in permitted) else []
    else:
        companies = permitted

    company_filter = ""
    company_params = {}
    if companies:
        placeholders   = ", ".join([f"%(company_{i})s" for i in range(len(companies))])
        company_filter = f"AND cl.company IN ({placeholders})"
        for i, c in enumerate(companies):
            company_params[f"company_{i}"] = c

    params = {"search": search_term, **company_params}

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
    start_date = getdate(start_date)
    end_date   = getdate(end_date)

    # Fetch both the main status and the half-day fields in one query
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
            # Return structured half-day record so JS can populate both dropdown cells
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

# Full-day UI statuses that map directly to DB
VALID_FULL_STATUSES = {
    "Present", "On Tour", "Earned Comp Off",
    "Absent", "Earned Leave", "Casual Leave", "Comp Off",
    "LWP", "Holiday", "Weekly Off",
}

# Valid statuses for each half of a half-day record
VALID_HALF_STATUSES = {
    "Present", "On Tour", "Earned Comp Off",
    "Absent", "Earned Leave", "Casual Leave", "Comp Off", "LWP",
    "",  # empty / not set
}

# UI label → DB status overrides for full-day records
UI_TO_DB_STATUS = {
    # "Regular" was used in the old UI — keep mapping for safety
    "Regular": "Present",
}


def resolve_db_status(ui_status):
    return UI_TO_DB_STATUS.get(ui_status, ui_status)


# ---------------------------------------------------------------------------
# Save batch  (handles both full-day and half-day records)
# ---------------------------------------------------------------------------

@frappe.whitelist()
def save_attendance_batch(attendance_data):
    """
    Accepts a list of records.  Each record is either:

    Full-day:
        { "employee": "...", "attendance_date": "YYYY-MM-DD",
          "mode": "full", "status": "<FULL_DAY_STATUS>" }

    Half-day:
        { "employee": "...", "attendance_date": "YYYY-MM-DD",
          "mode": "half", "first_half": "<HALF_STATUS>", "second_half": "<HALF_STATUS>" }
    """
    user = frappe.session.user

    if isinstance(attendance_data, str):
        attendance_data = json.loads(attendance_data)

    companies = frappe.get_all(
        "User Permission",
        filters={"user": user, "allow": "Company"},
        pluck="for_value"
    )

    permitted_employees = None
    if companies:
        permitted_employees = set(
            frappe.get_all(
                "Company Link",
                filters={"company": ["in", companies]},
                pluck="name"
            )
        )

    saved_count = 0
    errors      = []

    try:
        for record in attendance_data:
            try:
                employee        = record.get("employee")
                attendance_date = getdate(record.get("attendance_date"))
                mode            = record.get("mode", "full")

                if permitted_employees is not None and employee not in permitted_employees:
                    errors.append(f"Not permitted for employee {employee} on {attendance_date}")
                    continue

                # ── Server-side salary slip lock check ─────────────────────
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

                else:  # mode == "full"
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

    holiday_list = frappe.db.get_value("Company", company, "default_holiday_list")
    if not holiday_list:
        return []

    holidays = frappe.db.get_all(
        "Holiday",
        filters={
            "parent":       holiday_list,
            "holiday_date": ["between", [start_date, end_date]],
        },
        pluck="holiday_date"
    )

    return [str(h) for h in holidays]


# ---------------------------------------------------------------------------
# Leave Allocation check
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_leave_allocation_for_month(employee, year, month):
    """
    Check whether an active Leave Allocation exists for the employee covering
    the given month.  Returns:
    {
        "has_allocation": True/False,
        "allocation_name": "LAL-00001" | None,
    }
    Used by the mark-attendance page to decide whether to enable leave columns.
    """
    import datetime

    try:
        year_int  = int(year)
        month_int = int(month) + 1   # JS months are 0-based
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
# Comp Off / Leave balance  (extended to include EL and CL from Leave Allocation)
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_comp_off_balance(employee, year=None, month=None):
    """
    Returns balances for Earned Leave (EL), Casual Leave (CL), and Comp Off
    for the given employee and month.

    EL / CL allocated and remaining come from the active Leave Allocation
    Detail rows.  Used / taken are computed live from Attendance records
    (supporting 0.5 for half-day leaves).

    Comp Off available/earned/used/balance are computed from Attendance directly
    (no allocation row needed — ECO earns, Comp Off uses).

    Return structure:
    {
        # EL
        "el_allocated":  int,
        "el_used":       float,   # supports 0.5 increments
        "el_remaining":  float,

        # CL
        "cl_allocated":  int,
        "cl_used":       float,
        "cl_remaining":  float,

        # Comp Off (ECO / Comp Off)
        "available":     int,    # balance carried in from before month
        "earned":        int,    # ECO earned this month
        "used":          float,  # Comp Off used this month (supports 0.5)
        "balance":       float,  # available + earned - used

        # Legacy keys (kept for backward compat)
        "el_taken":      float,  # same as el_used
        "cl_taken":      float,  # same as cl_used
    }
    """
    import datetime

    try:
        year_int  = int(year)  if year  not in (None, "", "None") else None
        month_int = int(month) if month not in (None, "", "None") else None
    except (ValueError, TypeError):
        year_int  = None
        month_int = None

    # ── Helper: count full-day + half-day attendance for a leave type ────────
    def count_leave_taken(emp, leave_type, from_dt, to_dt):
        """
        Returns float count of leave_type taken between from_dt and to_dt.
        Full-day attendance with that status = 1.0
        Half-day attendance where first_half or second_half matches = 0.5 each
        """
        total = 0.0

        # Full-day records
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

        # Half-day records — first half
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

        # Half-day records — second half
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

    # ── Helper: count full-day ECO/Comp Off (no half-day variant for ECO) ───
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

        # ── Find active Leave Allocation covering this month ─────────────────
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
            # Get allocated amounts from the Leave Allocation Detail child table
            details = frappe.get_all(
                "Leave Allocation Detail",
                filters={"parent": alloc.name},
                fields=["leave_type", "allocated_leaves"]
            )
            allocated_map = {d.leave_type: (d.allocated_leaves or 0) for d in details}

            el_allocated = allocated_map.get("Earned Leave", 0)
            cl_allocated = allocated_map.get("Casual Leave", 0)

            # Compute used from Attendance over the FULL allocation period
            # (so balance reflects the whole allocation, not just this month)
            alloc_start = alloc.from_date
            alloc_end   = alloc.to_date

            el_used = count_leave_taken(employee, "Earned Leave", alloc_start, alloc_end)
            cl_used = count_leave_taken(employee, "Casual Leave", alloc_start, alloc_end)
        else:
            el_allocated = 0
            cl_allocated = 0
            el_used      = 0.0
            cl_used      = 0.0

        el_remaining = max(0.0, float(el_allocated) - el_used)
        cl_remaining = max(0.0, float(cl_allocated) - cl_used)

        # ── Comp Off ─────────────────────────────────────────────────────────
        earned_before = count_eco_or_coff(employee, "Earned Comp Off", "2000-01-01", month_start - datetime.timedelta(days=1))
        used_before   = count_leave_taken(employee, "Comp Off", "2000-01-01", month_start - datetime.timedelta(days=1))
        available     = max(0.0, earned_before - used_before)

        earned  = count_eco_or_coff(employee, "Earned Comp Off", month_start, month_end)
        co_used = count_leave_taken(employee, "Comp Off", month_start, month_end)
        balance = max(0.0, available + earned - co_used)

    else:
        # No month specified — lifetime totals, no allocation lookup
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
        co_used = count_leave_taken(employee, "Comp Off", "2000-01-01", "2099-12-31") if False else float(
            frappe.db.count("Attendance", filters={
                "employee": employee, "status": "Comp Off", "docstatus": ["<", 2],
            })
        )
        balance = max(0.0, earned - co_used)

    return {
        # EL
        "el_allocated": el_allocated,
        "el_used":      el_used,
        "el_remaining": el_remaining,

        # CL
        "cl_allocated": cl_allocated,
        "cl_used":      cl_used,
        "cl_remaining": cl_remaining,

        # Comp Off
        "available": available,
        "earned":    earned,
        "used":      co_used,
        "balance":   balance,

        # Legacy keys
        "el_taken":  el_used,
        "cl_taken":  cl_used,
    }


# ---------------------------------------------------------------------------
# Joining / left date
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_employee_joining_date(employee):
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