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


import json
from frappe.utils.pdf import get_pdf


_CSS = """<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Arial,sans-serif;font-size:16px;color:#000;background:#fff}
.hdr{text-align:center;border-bottom:2px solid #000;padding:10px 6px 6px;margin-bottom:6px}
.hdr .co{font-size:28px;font-weight:900;letter-spacing:1px;text-transform:uppercase}
.hdr .ttl{font-size:20px;font-weight:700;margin-top:2px}
.hdr .per{font-size:16px;margin-top:2px}
.sig{display:flex;justify-content:space-between;margin-top:16px;padding-top:8px}
.sig-b{text-align:center;width:180px}
.sig-l{border-top:1px solid #000;margin-bottom:4px}
.sig-t{font-size:15px;color:#333}
table{width:100%;border-collapse:collapse;margin-top:8px}
th{border:1px solid #000;padding:10px 12px;font-size:16px;font-weight:700;background:#f0f0f0;color:#000;white-space:nowrap;text-align:left}
td{border:1px solid #000;padding:10px 12px;font-size:16px;vertical-align:middle;color:#000;text-align:left}
tr.tot td{background:#e8e8e8;font-weight:700}
.nd{text-align:center;padding:10px;color:#888;font-size:16px}
</style>"""


_SIG = '<div class="sig">' + "".join(
    f'<div class="sig-b"><div class="sig-l"></div><div class="sig-t">{l}</div></div>'
    for l in ["Prepared By", "Checked By", "Authorised Signatory"]
) + '</div>'


def _fmt(v):
    if v is None or v == "":
        return ""
    try:
        return f"{float(v):,.2f}"
    except (TypeError, ValueError):
        return str(v)


def _build_html(cols, data, co, title, mo, yr):
    hdr = (
        f'<div class="hdr">'
        f'<div class="co">{co}</div>'
        f'<div class="ttl">{title}</div>'
        f'<div class="per">For the Month of {mo} {yr}</div>'
        f'</div>'
    )

    def _th():
        return "<tr>" + "".join(f'<th>{c.get("label","")}</th>' for c in cols) + "</tr>"

    def _dr(row):
        h = "<tr>"
        for c in cols:
            val = row.get(c.get("fieldname", ""), "")
            h += f'<td>{_fmt(val) if isinstance(val, (int, float)) else (val or "")}</td>'
        return h + "</tr>"

    def _tr(row):
        amount_cols = {"total_loan", "recovered_this_month", "loan_balance"}
        h = '<tr class="tot">'
        for c in cols:
            fn = c.get("fieldname", "")
            if fn == "employee":
                h += "<td>TOTAL</td>"
            elif fn in amount_cols:
                h += f'<td>{_fmt(row.get(fn, ""))}</td>'
            else:
                h += "<td></td>"
        return h + "</tr>"

    # Separate totals row (employee == "TOTAL") from detail rows
    detail_rows = [r for r in data if r.get("employee") != "TOTAL"]
    total_row   = next((r for r in data if r.get("employee") == "TOTAL"), None)
    ncols       = len(cols) or 1

    if not detail_rows:
        return (
            f'<!DOCTYPE html><html><head><meta charset="UTF-8">{_CSS}</head>'
            f'<body>{hdr}'
            f'<table><thead>{_th()}</thead>'
            f'<tbody><tr><td colspan="{ncols}" class="nd">No data for this period</td></tr></tbody>'
            f'</table>{_SIG}</body></html>'
        )

    FIRST, OTHER = 20, 25
    pages, idx, first = [], 0, True
    while idx < len(detail_rows):
        lim = FIRST if first else OTHER
        pages.append(detail_rows[idx: idx + lim])
        idx += lim
        first = False

    html = ""
    for pn, pr in enumerate(pages):
        last = (pn == len(pages) - 1)
        if pn > 0:
            html += '<div style="page-break-before:always;"></div>'
        html += hdr
        html += f'<table><thead>{_th()}</thead><tbody>'
        for row in pr:
            html += _dr(row)
        if last and total_row:
            html += _tr(total_row)
        html += '</tbody></table>'

    html += _SIG
    return f'<!DOCTYPE html><html><head><meta charset="UTF-8">{_CSS}</head><body>{html}</body></html>'


def _save_pdf(html, prefix):
    pdf = get_pdf(html, options={
        "page-size":     "A4",
        "orientation":   "Landscape",
        "margin-top":    "8mm",
        "margin-right":  "8mm",
        "margin-bottom": "8mm",
        "margin-left":   "8mm",
        "encoding":      "UTF-8",
        "no-outline":    None,
    })
    ts  = frappe.utils.now_datetime().strftime("%Y%m%d_%H%M%S")
    fn  = f"{prefix}_{ts}.pdf"
    with open(frappe.utils.get_files_path(fn, is_private=0), "wb") as fh:
        fh.write(pdf)
    doc = frappe.get_doc({
        "doctype":    "File",
        "file_name":  fn,
        "is_private": 0,
        "file_url":   f"/files/{fn}",
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return doc.file_url


@frappe.whitelist()
def print_report(filters):
    if isinstance(filters, str):
        filters = json.loads(filters)

    cols, data = execute(filters)

    co    = filters.get("company", "")
    mo    = filters.get("month",   "")
    yr    = filters.get("year",    "")
    title = "Loan Register"

    html = _build_html(cols, data, co, title, mo, yr)
    return _save_pdf(html, "Loan_Register")