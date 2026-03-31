# Copyright (c) 2026, sj and contributors
# For license information, please see license.txt

import frappe
import calendar
from datetime import datetime


def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data    = get_data(filters)
    return columns, data


# ------------------------------------------------------------------ #
#  Columns  — untouched                                               #
# ------------------------------------------------------------------ #

def get_columns():
    return [
        {
            "fieldname": "employee",
            "label":     "Employee ID",
            "fieldtype": "Link",
            "options":   "Employee",
            "width":     130
        },
        {
            "fieldname": "employee_name",
            "label":     "Employee Name",
            "fieldtype": "Data",
            "width":     200
        },
        {
            "fieldname": "total_advance",
            "label":     "Total Advance (₹)",
            "fieldtype": "Currency",
            "width":     160
        },
        {
            "fieldname": "recovered_advance",
            "label":     "Recovered Advance (₹)",
            "fieldtype": "Currency",
            "width":     180
        },
        {
            "fieldname": "pending_advance",
            "label":     "Pending Advance (₹)",
            "fieldtype": "Currency",
            "width":     170
        },
    ]


# ------------------------------------------------------------------ #
#  Employee dropdown — ID bold on top, Name as subtitle               #
# ------------------------------------------------------------------ #

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_employees_with_advances(doctype, txt, searchfield, start, page_len, filters):
    company = filters.get("company") if filters else None

    params = {
        "txt": f"%{txt}%",
        "start": start,
        "page_len": page_len,
    }

    company_cond = ""
    if company:
        company_cond = "AND ela.company = %(company)s"
        params["company"] = company

    results = frappe.db.sql("""
        SELECT DISTINCT
            ela.employee,
            COALESCE(e.employee_name, ela.full_name, ela.employee) AS employee_name
        FROM `tabEmployee Loan Advance` ela
        INNER JOIN `tabEmployee` e ON e.name = ela.employee
        WHERE ela.docstatus = 1
            AND ela.type = 'Advance'
            {company_cond}
            AND (ela.employee LIKE %(txt)s OR e.employee_name LIKE %(txt)s)
        ORDER BY ela.employee ASC
        LIMIT %(page_len)s OFFSET %(start)s
    """.format(company_cond=company_cond), params)

    return [[emp[0], emp[1] or emp[0]] for emp in results]


# ------------------------------------------------------------------ #
#  Data  — untouched                                                  #
# ------------------------------------------------------------------ #

def get_data(filters):
    conditions, values = build_conditions(filters)

    rows = frappe.db.sql(
        f"""
        SELECT
            ela.employee,
            ela.full_name AS employee_name,
            SUM(ela.amount) AS total_advance,
            SUM(CASE WHEN ela.is_deducted = 1 THEN ela.amount ELSE 0 END) AS recovered_advance,
            SUM(CASE WHEN ela.is_deducted = 0 THEN ela.amount ELSE 0 END) AS pending_advance
        FROM
            `tabEmployee Loan Advance` ela
        WHERE
            ela.type = 'Advance'
            AND ela.docstatus = 1
            {conditions}
        GROUP BY
            ela.employee, ela.full_name
        ORDER BY
            ela.employee ASC
        """,
        values,
        as_dict=True
    )

    return rows


# ------------------------------------------------------------------ #
#  Filter → SQL Conditions  — untouched                               #
# ------------------------------------------------------------------ #

def build_conditions(filters):
    conditions = ""
    values     = {}

    if filters.get("company"):
        conditions += " AND ela.company = %(company)s"
        values["company"] = filters["company"]

    if filters.get("employee"):
        conditions += " AND ela.employee = %(employee)s"
        values["employee"] = filters["employee"]

    if filters.get("year") or filters.get("month"):
        date_from, date_to = get_date_range(filters)
        if date_from and date_to:
            conditions += " AND ela.date BETWEEN %(date_from)s AND %(date_to)s"
            values["date_from"] = date_from
            values["date_to"]   = date_to

    return conditions, values


def get_date_range(filters):
    year  = filters.get("year")
    month = filters.get("month")

    if year and month:
        try:
            dt        = datetime.strptime(f"{month} {year}", "%B %Y")
            last_day  = calendar.monthrange(dt.year, dt.month)[1]
            date_from = dt.strftime("%Y-%m-01")
            date_to   = dt.strftime(f"%Y-%m-{last_day:02d}")
            return date_from, date_to
        except Exception:
            return None, None

    elif year:
        return f"{year}-01-01", f"{year}-12-31"

    elif month:
        return None, None

    return None, None