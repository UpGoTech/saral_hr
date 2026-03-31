# Copyright (c) 2026, sj and contributors
# For license information, please see license.txt

import frappe
import calendar
from frappe import _
from datetime import datetime


def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data    = get_data(filters)
    return columns, data


# ------------------------------------------------------------------ #
#  Columns                                                             #
# ------------------------------------------------------------------ #

def get_columns():
    return [
        {"label": _("Employee ID"),    "fieldname": "employee",             "fieldtype": "Link", "options": "Employee", "width": 140},
        {"label": _("Employee Name"),  "fieldname": "employee_name",        "fieldtype": "Data",                        "width": 180},
        {"label": _("Loan Type"),      "fieldname": "type",                 "fieldtype": "Data",                        "width": 100},
        {"label": _("Total Loan"),     "fieldname": "total_loan",           "fieldtype": "Float",                       "width": 140},
        {"label": _("Loan Recovered"), "fieldname": "recovered_this_month", "fieldtype": "Float",                       "width": 160},
        {"label": _("Loan Balance"),   "fieldname": "loan_balance",         "fieldtype": "Float",                       "width": 140},
    ]


# ------------------------------------------------------------------ #
#  Employee dropdown                                                   #
# ------------------------------------------------------------------ #

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_employees_with_loans(doctype, txt, searchfield, start, page_len, filters):
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
            AND ela.type IN ('Loan-I', 'Loan-II')
            {company_cond}
            AND (ela.employee LIKE %(txt)s OR e.employee_name LIKE %(txt)s)
        ORDER BY ela.employee ASC
        LIMIT %(page_len)s OFFSET %(start)s
    """.format(company_cond=company_cond), params)

    return [[emp[0], emp[1] or emp[0]] for emp in results]


# ------------------------------------------------------------------ #
#  Main data                                                           #
# ------------------------------------------------------------------ #

def get_data(filters):
    base_conditions, values = build_base_conditions(filters)

    # Build selected month label e.g. "January 2026"
    selected_month = filters.get("month")
    selected_year  = filters.get("year")
    selected_label = f"{selected_month} {selected_year}" if selected_month and selected_year else None

    # recovered_this_month: only sum schedule rows matching selected month label
    if selected_label:
        values["selected_label"] = selected_label
        recovered_condition = "AND elass.month = %(selected_label)s"
    else:
        recovered_condition = ""

    rows = frappe.db.sql(
        f"""
        SELECT
            ela.employee,
            ela.full_name                                                AS employee_name,
            ela.type,
            ela.amount                                                   AS total_loan,
            COALESCE(SUM(CASE
                WHEN elass.is_deducted = 1 {recovered_condition}
                THEN elass.deduction_amount
                ELSE 0
            END), 0)                                                     AS recovered_this_month,
            ela.amount - COALESCE(SUM(CASE
                WHEN elass.is_deducted = 1
                THEN elass.deduction_amount
                ELSE 0
            END), 0)                                                     AS loan_balance
        FROM
            `tabEmployee Loan Advance` ela
        LEFT JOIN
            `tabEmployee Loan Advance Schedule` elass ON elass.parent = ela.name
        WHERE
            ela.type IN ('Loan-I', 'Loan-II')
            AND ela.docstatus = 1
            {base_conditions}
        GROUP BY
            ela.name, ela.employee, ela.full_name, ela.type, ela.amount
        ORDER BY
            ela.employee ASC, ela.type ASC
        """,
        values,
        as_dict=True
    )

    if not rows:
        return []

    # Skip rows where nothing was recovered in selected month
    if selected_label:
        rows = [r for r in rows if (r.recovered_this_month or 0) > 0]

    if not rows:
        return []

    grand_loan      = sum(r.total_loan           or 0 for r in rows)
    grand_recovered = sum(r.recovered_this_month or 0 for r in rows)
    grand_balance   = sum(r.loan_balance         or 0 for r in rows)

    rows.append({
        "employee":             "TOTAL",
        "employee_name":        "",
        "type":                 "",
        "total_loan":           round(grand_loan,      2),
        "recovered_this_month": round(grand_recovered, 2),
        "loan_balance":         round(grand_balance,   2),
    })

    return rows


# ------------------------------------------------------------------ #
#  Filter → SQL Conditions                                             #
# ------------------------------------------------------------------ #

def build_base_conditions(filters):
    """Only company + employee conditions — NOT year/month.
    Year/month is handled via schedule month label in get_data."""
    conditions = ""
    values     = {}

    if filters.get("company"):
        conditions += " AND ela.company = %(company)s"
        values["company"] = filters["company"]

    if filters.get("employee"):
        conditions += " AND ela.employee = %(employee)s"
        values["employee"] = filters["employee"]

    return conditions, values