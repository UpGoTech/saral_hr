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

    # If a specific company is passed, use it (must be within permitted)
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
    start_date = getdate(start_date)
    end_date   = getdate(end_date)

    attendance_records = frappe.db.get_all(
        "Attendance",
        filters={
            "employee":        employee,
            "attendance_date": ["between", [start_date, end_date]],
            "docstatus":       ["<", 2],
        },
        fields=["attendance_date", "status"]
    )

    result = {}
    for row in attendance_records:
        result[str(row.attendance_date)] = row.status

    return result


# ---------------------------------------------------------------------------
# UI status → DB status mapping
# ---------------------------------------------------------------------------
UI_TO_DB_STATUS = {
    "Regular": "Present",
}

# "Earned Comp Off" saves directly as "Earned Comp Off" in DB
VALID_UI_STATUSES = {
    "Present",
    "Regular",
    "On Tour",
    "Earned Comp Off",
    "Absent",
    "Half Day",
    "Holiday",
    "Weekly Off",
    "LWP",
    "Earned Leave",
    "Casual Leave",
    "Comp Off",
}


def resolve_db_status(ui_status):
    return UI_TO_DB_STATUS.get(ui_status, ui_status)


@frappe.whitelist()
def save_attendance_batch(attendance_data):
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
                ui_status       = record.get("status", "").strip()

                if not ui_status or ui_status not in VALID_UI_STATUSES:
                    continue

                db_status = resolve_db_status(ui_status)

                if permitted_employees is not None and employee not in permitted_employees:
                    errors.append(f"Not permitted for employee {employee} on {attendance_date}")
                    continue

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
                    frappe.db.set_value(
                        "Attendance", existing, "status", db_status, update_modified=True
                    )
                else:
                    doc = frappe.get_doc({
                        "doctype":         "Attendance",
                        "employee":        employee,
                        "attendance_date": attendance_date,
                        "status":          db_status,
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


@frappe.whitelist()
def get_comp_off_balance(employee, year=None, month=None):
    import datetime

    # If year/month provided and valid, calculate month boundaries
    try:
        year_int  = int(year)  if year  not in (None, "", "None") else None
        month_int = int(month) if month not in (None, "", "None") else None
    except (ValueError, TypeError):
        year_int  = None
        month_int = None

    if year_int is not None and month_int is not None:
        # month_int is 0-based from JS (0=Jan … 11=Dec)
        month_1based = month_int + 1
        month_start  = datetime.date(year_int, month_1based, 1)
        if month_1based == 12:
            month_end = datetime.date(year_int + 1, 1, 1) - datetime.timedelta(days=1)
        else:
            month_end = datetime.date(year_int, month_1based + 1, 1) - datetime.timedelta(days=1)

        # Available = all earned before this month − all used before this month
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
        # Earned Leave taken this month
        el_taken = frappe.db.count("Attendance", filters={
            "employee": employee, "status": "Earned Leave",
            "attendance_date": ["between", [month_start, month_end]], "docstatus": ["<", 2],
        })
        # Casual Leave taken this month
        cl_taken = frappe.db.count("Attendance", filters={
            "employee": employee, "status": "Casual Leave",
            "attendance_date": ["between", [month_start, month_end]], "docstatus": ["<", 2],
        })

        balance = max(0, available + earned - used)

    else:
        # No month selected — show all-time totals
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


# ── fetch joining date AND left date from Company Link ─────────────────────
# joining date itself → CAN mark  (only strictly before is blocked)
# left date itself    → CAN mark  (only strictly after is blocked)
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