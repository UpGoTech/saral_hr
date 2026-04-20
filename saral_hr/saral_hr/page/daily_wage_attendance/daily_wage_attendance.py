# Copyright (c) 2026, sj and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt, getdate
from datetime import timedelta


# ════════════════════════════════════════════════════════════════════════════
#  get_company_pf_wage_limit
# ════════════════════════════════════════════════════════════════════════════
@frappe.whitelist()
def get_company_pf_wage_limit(company):
    if not company:
        return {"wage_limit": 0}

    try:
        comp_doc = frappe.get_doc("Company", company)
        pf_cfg   = comp_doc.get_pf_config() if hasattr(comp_doc, "get_pf_config") else None
        if not pf_cfg:
            return {"wage_limit": 0}
        wage_limit = flt(pf_cfg.get("wage_limit") or 0)
        return {"wage_limit": wage_limit}
    except Exception:
        return {"wage_limit": 0}


# ════════════════════════════════════════════════════════════════════════════
#  get_daily_wage_active_employees
# ════════════════════════════════════════════════════════════════════════════
@frappe.whitelist()
def get_daily_wage_active_employees():
    try:
        rows = frappe.db.sql("""
            SELECT cl.name, cl.full_name, cl.company,
                   cl.name AS employee
            FROM   `tabCompany Link` cl
            INNER JOIN `tabCategory` cat ON cat.name = cl.category
            WHERE  cl.is_active = 1
              AND  cat.is_daily_wage = 1
            ORDER  BY cl.company, cl.full_name
        """, as_dict=True)

        if rows:
            return rows

        return frappe.db.get_all(
            "Company Link",
            filters={"is_active": 1},
            fields=["name", "full_name", "company", "name as employee"],
            order_by="company, full_name",
        )

    except Exception:
        return frappe.db.get_all(
            "Company Link",
            filters={"is_active": 1},
            fields=["name", "full_name", "company"],
            order_by="company, full_name",
        )


# ════════════════════════════════════════════════════════════════════════════
#  get_special_component_monthly_amounts
# ════════════════════════════════════════════════════════════════════════════
@frappe.whitelist()
def get_special_component_monthly_amounts(component_names):
    import json as _json

    if isinstance(component_names, str):
        component_names = _json.loads(component_names)

    if not component_names:
        return {}

    result = {}

    special_comps = frappe.db.get_all(
        "Salary Component",
        filters={
            "salary_component": ["in", component_names],
            "is_special_component": 1,
        },
        fields=["salary_component"],
    )

    for sc in special_comps:
        comp_name = sc["salary_component"]
        rows = frappe.db.get_all(
            "Special Salary Component",
            filters={"parent": comp_name, "parenttype": "Salary Component"},
            fields=["month", "amount"],
            order_by="idx asc",
        )
        if rows:
            result[comp_name] = {row["month"]: flt(row["amount"]) for row in rows}

    return result


# ════════════════════════════════════════════════════════════════════════════
#  get_daily_wage_data
# ════════════════════════════════════════════════════════════════════════════
@frappe.whitelist()
def get_daily_wage_data(employee, start_date, end_date):
    daily_rates = {}
    adr_records = {}

    # ── Daily rate lookup from Daily Rates Worker ─────────────────────────
    try:
        rate_rows = frappe.db.sql("""
            SELECT start_date, end_date, amount AS daily_rate
            FROM   `tabDaily Rates Worker`
            WHERE  employee   = %(emp)s
              AND  start_date <= %(end)s
              AND  (end_date IS NULL OR end_date >= %(start)s)
            ORDER  BY start_date DESC
        """, {"emp": employee, "start": start_date, "end": end_date}, as_dict=True)

        from datetime import date as date_type
        cur = getdate(start_date)
        eod = getdate(end_date)
        while cur <= eod:
            dk = str(cur)
            for row in rate_rows:
                eff_from = getdate(row.start_date)
                eff_to   = getdate(row.end_date) if row.end_date else date_type(9999, 12, 31)
                if eff_from <= cur <= eff_to:
                    daily_rates[dk] = flt(row.daily_rate)
                    break
            cur += timedelta(days=1)

    except Exception as e:
        frappe.log_error(f"DWA daily_rate lookup error: {e}", "Daily Wage Attendance")

    # ── Already-saved ADR records ─────────────────────────────────────────
    # ot_hours is now a Float (decimal hours: 4.5 = 4h30m)
    try:
        adr_rows = frappe.db.sql("""
            SELECT attendance_date, status, ot_hours, daily_rate, remarks
            FROM   `tabAttendance Daily Rate`
            WHERE  employee        = %(emp)s
              AND  attendance_date BETWEEN %(start)s AND %(end)s
              AND  docstatus       < 2
        """, {"emp": employee, "start": start_date, "end": end_date}, as_dict=True)

        for row in adr_rows:
            dk = str(getdate(row.attendance_date))

            # ot_hours is stored as decimal float: 4.5 → 4h 30m → 270 minutes
            ot_decimal = flt(row.ot_hours or 0)
            whole_hours = int(ot_decimal)
            frac        = ot_decimal - whole_hours
            ot_minutes  = whole_hours * 60 + round(frac * 60)

            adr_records[dk] = {
                "status":     row.status or "",
                "ot_hours":   ot_decimal,    # decimal float sent back to JS
                "ot_minutes": ot_minutes,    # integer minutes for summary bar
                "daily_rate": flt(row.daily_rate or 0),
                "remarks":    row.remarks or "",
            }
            if row.daily_rate:
                daily_rates[dk] = flt(row.daily_rate)

    except Exception as e:
        frappe.log_error(f"DWA adr_records lookup error: {e}", "Daily Wage Attendance")

    return {"daily_rates": daily_rates, "adr_records": adr_records}


# ════════════════════════════════════════════════════════════════════════════
#  save_daily_wage_attendance_batch
# ════════════════════════════════════════════════════════════════════════════
@frappe.whitelist()
def save_daily_wage_attendance_batch(attendance_data):
    import json as _json

    if isinstance(attendance_data, str):
        attendance_data = _json.loads(attendance_data)

    saved = 0
    errors = []

    for entry in attendance_data:
        try:
            employee      = entry.get("employee")
            att_date      = entry.get("attendance_date")
            mode          = entry.get("mode", "full")
            status        = entry.get("status", "")
            ot_hours_val  = flt(entry.get("ot_hours", 0))   # decimal float from JS
            daily_rate    = flt(entry.get("daily_rate", 0))
            remarks       = entry.get("remarks", "") or ""

            if not employee or not att_date:
                continue

            # Resolve effective status
            if mode == "half":
                effective_status = "Half Day"
            else:
                effective_status = status

            if not effective_status:
                continue

            # Find ALL existing records for this employee+date
            all_existing = frappe.db.get_all(
                "Attendance Daily Rate",
                filters={
                    "employee":        employee,
                    "attendance_date": att_date,
                    "docstatus":       ["<", 2],
                },
                fields=["name"],
                order_by="creation asc",
            )

            if len(all_existing) > 1:
                # Delete duplicates, keep only the oldest
                for dup in all_existing[1:]:
                    frappe.delete_doc(
                        "Attendance Daily Rate",
                        dup["name"],
                        ignore_permissions=True,
                        force=True,
                    )

            if all_existing:
                doc = frappe.get_doc("Attendance Daily Rate", all_existing[0]["name"])
                doc.status     = effective_status
                doc.ot_hours   = ot_hours_val
                doc.daily_rate = daily_rate
                doc.remarks    = remarks
                doc.save(ignore_permissions=True)
            else:
                doc = frappe.new_doc("Attendance Daily Rate")
                doc.employee        = employee
                doc.attendance_date = att_date
                doc.status          = effective_status
                doc.ot_hours        = ot_hours_val
                doc.daily_rate      = daily_rate
                doc.remarks         = remarks
                doc.insert(ignore_permissions=True)

            saved += 1

        except Exception as e:
            errors.append(str(e))
            frappe.log_error(f"DWA save error: {e}", "Daily Wage Attendance")

    frappe.db.commit()

    if errors:
        return {"success": False, "error": "; ".join(errors[:3]), "saved_count": saved}

    return {"success": True, "saved_count": saved}