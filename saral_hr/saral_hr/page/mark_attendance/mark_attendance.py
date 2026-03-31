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

                # ── Determine DB values ────────────────────────────────
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

                # ── Upsert attendance record ───────────────────────────
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
# Comp Off / Leave balance
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_comp_off_balance(employee, year=None, month=None):
    import datetime

    try:
        year_int  = int(year)  if year  not in (None, "", "None") else None
        month_int = int(month) if month not in (None, "", "None") else None
    except (ValueError, TypeError):
        year_int  = None
        month_int = None

    if year_int is not None and month_int is not None:
        month_1based = month_int + 1
        month_start  = datetime.date(year_int, month_1based, 1)
        if month_1based == 12:
            month_end = datetime.date(year_int + 1, 1, 1) - datetime.timedelta(days=1)
        else:
            month_end = datetime.date(year_int, month_1based + 1, 1) - datetime.timedelta(days=1)

        earned_before = frappe.db.count("Attendance", filters={
            "employee": employee, "status": "Earned Comp Off",
            "attendance_date": ["<", month_start], "docstatus": ["<", 2],
        })
        used_before = frappe.db.count("Attendance", filters={
            "employee": employee, "status": "Comp Off",
            "attendance_date": ["<", month_start], "docstatus": ["<", 2],
        })
        available = max(0, earned_before - used_before)

        earned = frappe.db.count("Attendance", filters={
            "employee": employee, "status": "Earned Comp Off",
            "attendance_date": ["between", [month_start, month_end]], "docstatus": ["<", 2],
        })
        used = frappe.db.count("Attendance", filters={
            "employee": employee, "status": "Comp Off",
            "attendance_date": ["between", [month_start, month_end]], "docstatus": ["<", 2],
        })
        el_taken = frappe.db.count("Attendance", filters={
            "employee": employee, "status": "Earned Leave",
            "attendance_date": ["between", [month_start, month_end]], "docstatus": ["<", 2],
        })
        cl_taken = frappe.db.count("Attendance", filters={
            "employee": employee, "status": "Casual Leave",
            "attendance_date": ["between", [month_start, month_end]], "docstatus": ["<", 2],
        })
        balance = max(0, available + earned - used)

    else:
        available = 0
        earned = frappe.db.count("Attendance", filters={
            "employee": employee, "status": "Earned Comp Off", "docstatus": ["<", 2],
        })
        used = frappe.db.count("Attendance", filters={
            "employee": employee, "status": "Comp Off", "docstatus": ["<", 2],
        })
        el_taken = frappe.db.count("Attendance", filters={
            "employee": employee, "status": "Earned Leave", "docstatus": ["<", 2],
        })
        cl_taken = frappe.db.count("Attendance", filters={
            "employee": employee, "status": "Casual Leave", "docstatus": ["<", 2],
        })
        balance = max(0, earned - used)

    return {
        "available": available,
        "earned":    earned,
        "used":      used,
        "balance":   balance,
        "el_taken":  el_taken,
        "cl_taken":  cl_taken,
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