import frappe
from frappe.utils import getdate
import json


@frappe.whitelist()
def get_daily_wage_active_employees():
    """
    Returns only employees whose Company Link category has has_subtype = 1.
    These are the daily wage workers.
    """
    user = frappe.session.user

    companies = frappe.get_all(
        "User Permission",
        filters={"user": user, "allow": "Company"},
        pluck="for_value"
    )

    filters = {"is_active": 1}
    if companies:
        filters["company"] = ["in", companies]

    result = frappe.db.sql("""
        SELECT
            cl.name,
            cl.employee,
            cl.full_name,
            cl.company,
            cl.category
        FROM
            `tabCompany Link` cl
            INNER JOIN `tabCategory` cat ON cat.name = cl.category
        WHERE
            cl.is_active = 1
            AND cat.has_subtype = 1
            {company_filter}
        ORDER BY
            cl.full_name ASC
    """.format(
        company_filter="AND cl.company IN %(companies)s" if companies else ""
    ), {"companies": companies} if companies else {}, as_dict=True)

    return result


@frappe.whitelist()
def get_daily_wage_data(employee, start_date, end_date):
    """
    Returns:
    - daily_rates  : { "YYYY-MM-DD": 350.0, ... }  from Daily Rates Worker
    - adr_records  : { "YYYY-MM-DD": { status, ot_hours, ot_minutes, daily_rate }, ... }
                     existing Attendance Daily Rate records for this month.
    Note: first_half / second_half are no longer used. Half Day = 0.5 present + 0.5 absent.
    """
    start_date = getdate(start_date)
    end_date   = getdate(end_date)

    # ── Daily rates from Daily Rates Worker ──────────────────────────────────
    adjustments = frappe.db.get_all(
        "Daily Rates Worker",
        filters={
            "employee":   employee,
            "start_date": ["<=", end_date],
            "end_date":   [">=", start_date],
        },
        fields=["start_date", "end_date", "amount"],
        order_by="start_date asc"
    )

    daily_rates = {}
    if adjustments:
        import datetime
        current = start_date
        while current <= end_date:
            for adj in adjustments:
                adj_start = getdate(adj.start_date)
                adj_end   = getdate(adj.end_date)
                if adj_start <= current <= adj_end:
                    daily_rates[str(current)] = float(adj.amount or 0)
                    break
            current += datetime.timedelta(days=1)

    # ── Existing Attendance Daily Rate records ───────────────────────────────
    adr_rows = frappe.db.get_all(
        "Attendance Daily Rate",
        filters={
            "employee":        employee,
            "attendance_date": ["between", [str(start_date), str(end_date)]],
        },
        fields=[
            "attendance_date", "status",
            "ot_hours", "ot_minutes", "daily_rate",
        ]
    )

    adr_records = {}
    for row in adr_rows:
        dk = str(row.attendance_date)
        adr_records[dk] = {
            "status":     row.status    or "",
            "ot_hours":   row.ot_hours  or "",
            "ot_minutes": row.ot_minutes or 0,
            "daily_rate": float(row.daily_rate or 0),
        }

    return {
        "daily_rates": daily_rates,
        "adr_records": adr_records,
    }


# ---------------------------------------------------------------------------
# Valid statuses
# ---------------------------------------------------------------------------
VALID_FULL_STATUSES = {"Present", "On Tour", "Absent", "Holiday"}


@frappe.whitelist()
def save_daily_wage_attendance_batch(attendance_data):
    """
    Saves attendance + OT hours + daily rate into Attendance Daily Rate doctype.

    Each record (full-day):
        { "employee": "...", "attendance_date": "YYYY-MM-DD",
          "mode": "full", "status": "...",
          "ot_hours": "02:30", "daily_rate": 350.0 }

    Each record (half-day):
        { "employee": "...", "attendance_date": "YYYY-MM-DD",
          "mode": "half",
          "ot_hours": "01:00", "daily_rate": 350.0 }

    Half Day always means 0.5 present + 0.5 absent.
    No first_half / second_half sub-selection is used.
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
                ot_hours_raw    = (record.get("ot_hours") or "").strip()
                daily_rate_val  = record.get("daily_rate") or 0

                if permitted_employees is not None and employee not in permitted_employees:
                    errors.append(f"Not permitted for employee {employee} on {attendance_date}")
                    continue

                # Salary slip lock check
                from frappe.utils import get_first_day
                month_start = str(get_first_day(attendance_date))
                submitted_slip = frappe.db.get_value(
                    "Salary Slip",
                    {"employee": employee, "start_date": month_start, "docstatus": 1},
                    "name"
                )
                if submitted_slip:
                    errors.append(
                        f"Cannot save for {employee} on {attendance_date}: "
                        f"Salary Slip {submitted_slip} submitted. Cancel first."
                    )
                    continue

                # Build field values
                if mode == "half":
                    # Simple half day: always 0.5 present + 0.5 absent.
                    # No first_half / second_half sub-selection needed.
                    db_status    = "Half Day"
                    extra_fields = {
                        "first_half":  "",
                        "second_half": "",
                    }
                else:
                    ui_status = (record.get("status") or "").strip()
                    if not ui_status or ui_status not in VALID_FULL_STATUSES:
                        errors.append(f"Invalid status '{ui_status}' for {employee} on {attendance_date}")
                        continue
                    db_status    = ui_status
                    extra_fields = {
                        "first_half":  "",
                        "second_half": "",
                    }

                # Parse OT minutes
                ot_minutes = _parse_ot_minutes(ot_hours_raw)

                # Upsert into Attendance Daily Rate
                existing = frappe.db.get_value(
                    "Attendance Daily Rate",
                    {
                        "employee":        employee,
                        "attendance_date": attendance_date,
                    },
                    "name"
                )

                if existing:
                    update_vals = {
                        "status":     db_status,
                        "ot_hours":   ot_hours_raw,
                        "ot_minutes": ot_minutes,
                        "daily_rate": daily_rate_val,
                        **extra_fields,
                    }
                    frappe.db.set_value(
                        "Attendance Daily Rate", existing, update_vals, update_modified=True
                    )
                else:
                    doc = frappe.get_doc({
                        "doctype":         "Attendance Daily Rate",
                        "employee":        employee,
                        "attendance_date": attendance_date,
                        "status":          db_status,
                        "ot_hours":        ot_hours_raw,
                        "ot_minutes":      ot_minutes,
                        "daily_rate":      daily_rate_val,
                        **extra_fields,
                    })
                    doc.flags.ignore_validate  = True
                    doc.flags.ignore_mandatory = True
                    doc.insert(ignore_permissions=True)

                saved_count += 1

            except Exception as e:
                err = f"Error for {record.get('employee')} on {record.get('attendance_date')}: {str(e)}"
                errors.append(err)
                frappe.log_error(err, "Daily Wage Attendance Save Error")

        frappe.db.commit()
        return {
            "success":     True,
            "saved_count": saved_count,
            "errors":      errors if errors else None,
        }

    except Exception as e:
        frappe.db.rollback()
        return {"success": False, "error": str(e)}


def _parse_ot_minutes(raw):
    """Parse HH:MM or plain hours string into total minutes."""
    if not raw:
        return 0
    raw = raw.strip()
    if ":" in raw:
        parts = raw.split(":")
        h = int(parts[0]) if parts[0].isdigit() else 0
        m = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        if m > 59:
            m = 59
        return h * 60 + m
    n = int(raw) if raw.isdigit() else 0
    return n * 60


# ---------------------------------------------------------------------------
# Keep old endpoints for backward compatibility
# ---------------------------------------------------------------------------

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
        extra = frappe.db.get_value(
            "Employee", emp.employee, ["designation", "department"], as_dict=True
        ) or {}
        emp["designation"] = extra.get("designation") or ""
        emp["department"]  = extra.get("department")  or ""
    return employees