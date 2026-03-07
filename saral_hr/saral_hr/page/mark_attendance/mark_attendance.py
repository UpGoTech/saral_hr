import frappe
from frappe.utils import getdate
import json


@frappe.whitelist()
def get_active_employees():
    user = frappe.session.user

    companies = frappe.get_all(
        "User Permission",
        filters={
            "user": user,
            "allow": "Company"
        },
        pluck="for_value"
    )

    filters = {"is_active": 1}

    if companies:
        filters["company"] = ["in", companies]

    employees = frappe.get_all(
        "Company Link",
        filters=filters,
        # FIX #7: also fetch the real employee ID so the frontend can show it
        fields=["name", "employee", "full_name", "company", "weekly_off"],
        order_by="full_name asc"
    )

    for emp in employees:
        aadhaar = frappe.db.get_value("Employee", emp.employee, "aadhar_number")
        emp["aadhaar_number"] = aadhaar or ""

    return employees


@frappe.whitelist()
def search_employees(query):
    if not query or len(query.strip()) < 1:
        return []

    user = frappe.session.user
    search_term = f"%{query.strip()}%"

    companies = frappe.get_all(
        "User Permission",
        filters={
            "user": user,
            "allow": "Company"
        },
        pluck="for_value"
    )

    company_filter = ""
    company_params = {}
    if companies:
        placeholders = ", ".join([f"%(company_{i})s" for i in range(len(companies))])
        company_filter = f"AND cl.company IN ({placeholders})"
        for i, c in enumerate(companies):
            company_params[f"company_{i}"] = c

    params = {
        "search": search_term,
        **company_params
    }

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
        WHERE cl.is_active = 1
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
            "name":           row.name,          # Company Link name (used as employee key)
            "employee":       row.employee,       # real Employee ID for display
            "full_name":      display_name,
            "company":        row.company,
            "weekly_off":     row.weekly_off or "",
            "aadhaar_number": row.aadhar_number or "",
            # FIX #7: expose the real employee ID so the dropdown subtitle shows it
            "emp_id":         row.employee or row.name,
        })

    return formatted


@frappe.whitelist()
def get_attendance_between_dates(employee, start_date, end_date):
    """
    Fetch attendance records for the given Company Link employee (name)
    between the two dates.

    FIX #3: employee field in Attendance links to Company Link, so the
            filter on "employee" is correct as-is — confirmed.
    FIX #4: added docstatus filter to exclude any cancelled records.
    """
    start_date = getdate(start_date)
    end_date   = getdate(end_date)

    attendance_records = frappe.db.get_all(
        "Attendance",
        filters={
            "employee":        employee,
            "attendance_date": ["between", [start_date, end_date]],
            # FIX #4: exclude cancelled records (docstatus 2)
            "docstatus":       ["<", 2],
        },
        fields=["attendance_date", "status"]
    )

    result = {}
    for row in attendance_records:
        date_str         = str(row.attendance_date)
        result[date_str] = row.status

    return result


# ---------------------------------------------------------------------------
# Status mapping helper
# ---------------------------------------------------------------------------
VALID_STATUSES = {
    "Present",
    "Absent",
    "Half Day",
    "Holiday",
    "Weekly Off",
    "LWP",
    "Earned Leave",
    "Casual Leave",
}


@frappe.whitelist()
def save_attendance_batch(attendance_data):
    user = frappe.session.user

    if isinstance(attendance_data, str):
        attendance_data = json.loads(attendance_data)

    # FIX #10: fetch allowed companies ONCE before the loop
    companies = frappe.get_all(
        "User Permission",
        filters={
            "user": user,
            "allow": "Company"
        },
        pluck="for_value"
    )

    # FIX #10: if company restrictions exist, pre-fetch all permitted
    #          Company Link names in a single query instead of one per record
    permitted_employees = None
    if companies:
        permitted_employees = set(
            frappe.get_all(
                "Company Link",
                filters={
                    "company":   ["in", companies],
                    "is_active": 1,
                },
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
                status          = record.get("status", "").strip()

                # Skip blank or unknown statuses
                if not status or status not in VALID_STATUSES:
                    continue

                # FIX #10: in-memory permission check (no extra DB query per record)
                if permitted_employees is not None and employee not in permitted_employees:
                    errors.append(
                        f"Not permitted for employee {employee} on {attendance_date}"
                    )
                    continue

                # FIX #1 / #2: use db.get_value + db.set_value / direct insert
                #   to bypass validate() entirely (non-submittable doctype,
                #   bulk save from page; validate_attendance_date would block
                #   future Holiday/Weekly Off records otherwise).
                #   The upsert below replicates the original intent cleanly.
                existing = frappe.db.get_value(
                    "Attendance",
                    {
                        "employee":        employee,
                        "attendance_date": attendance_date,
                        # FIX #4: only consider non-cancelled records
                        "docstatus":       ["<", 2],
                    },
                    "name"
                )

                if existing:
                    frappe.db.set_value(
                        "Attendance",
                        existing,
                        "status",
                        status,
                        update_modified=True
                    )
                else:
                    doc = frappe.get_doc({
                        "doctype":         "Attendance",
                        "employee":        employee,
                        "attendance_date": attendance_date,
                        "status":          status,
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
        return {
            "success": False,
            "error":   str(e),
        }


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