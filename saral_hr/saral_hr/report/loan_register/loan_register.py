# Copyright (c) 2026, sj and contributors
# For license information, please see license.txt

import json
import frappe
import calendar
from frappe import _
from frappe.utils.pdf import get_pdf


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
        {"label": _("Employee ID"),    "fieldname": "employee",             "fieldtype": "Link",  "options": "Employee",              "width": 180},
        {"label": _("Employee Name"),  "fieldname": "employee_name",        "fieldtype": "Data",                                       "width": 190},
        {"label": _("Loan ID"),        "fieldname": "loan_advance_id",      "fieldtype": "Link",  "options": "Employee Loan Advance",  "width": 220},
        {"label": _("Total Loan"),     "fieldname": "total_loan",           "fieldtype": "Float",                                      "width": 180},
        {"label": _("Loan Recovered"), "fieldname": "recovered_this_month", "fieldtype": "Float",                                      "width": 220},
        {"label": _("Loan Balance"),   "fieldname": "loan_balance",         "fieldtype": "Float",                                      "width": 220},
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
            AND ela.type = 'Loan'
            {company_cond}
            AND (ela.employee LIKE %(txt)s OR e.employee_name LIKE %(txt)s)
        ORDER BY ela.employee ASC
        LIMIT %(page_len)s OFFSET %(start)s
    """.format(company_cond=company_cond), params)

    return [[emp[0], emp[1] or emp[0]] for emp in results]


# ------------------------------------------------------------------ #
#  Filter → SQL Conditions                                             #
# ------------------------------------------------------------------ #

def build_base_conditions(filters):
    conditions = ""
    values     = {}

    if filters.get("company"):
        conditions += " AND ela.company = %(company)s"
        values["company"] = filters["company"]

    if filters.get("employee"):
        conditions += " AND ela.employee = %(employee)s"
        values["employee"] = filters["employee"]

    return conditions, values


# ------------------------------------------------------------------ #
#  Main data                                                           #
# ------------------------------------------------------------------ #

def get_data(filters):
    base_conditions, values = build_base_conditions(filters)

    selected_month = filters.get("month")
    selected_year  = filters.get("year")
    selected_label = f"{selected_month} {selected_year}" if selected_month and selected_year else None

    if selected_label:
        values["selected_label"] = selected_label
        recovered_condition = "AND elass.month = %(selected_label)s"
    else:
        recovered_condition = ""

    rows = frappe.db.sql(
        f"""
        SELECT
            ela.name                                                  AS loan_advance_id,
            ela.employee,
            ela.full_name                                             AS employee_name,
            ela.amount                                                AS total_loan,
            COALESCE(SUM(CASE
                WHEN elass.is_deducted = 1 {recovered_condition}
                THEN elass.deduction_amount
                ELSE 0
            END), 0)                                                  AS recovered_this_month,
            ela.amount - COALESCE(SUM(CASE
                WHEN elass.is_deducted = 1
                THEN elass.deduction_amount
                ELSE 0
            END), 0)                                                  AS loan_balance
        FROM
            `tabEmployee Loan Advance` ela
        LEFT JOIN
            `tabEmployee Loan Advance Schedule` elass ON elass.parent = ela.name
        WHERE
            ela.type = 'Loan'
            AND ela.docstatus = 1
            {base_conditions}
        GROUP BY
            ela.name, ela.employee, ela.full_name, ela.amount
        ORDER BY
            ela.employee ASC, ela.name ASC
        """,
        values,
        as_dict=True
    )

    if not rows:
        return []

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
        "loan_advance_id":      "",
        "total_loan":           round(grand_loan,      2),
        "recovered_this_month": round(grand_recovered, 2),
        "loan_balance":         round(grand_balance,   2),
    })

    return rows


# ------------------------------------------------------------------ #
#  PDF helpers  (Variable Pay Register style)                          #
# ------------------------------------------------------------------ #

_NUMERIC_FT = ("Float", "Currency", "Int", "Percent")

_CSS = """<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Arial,sans-serif;font-size:10px;color:#000;background:#fff}
.hdr{text-align:center;border-bottom:2px solid #000;padding:8px 4px 6px;margin-bottom:6px}
.hdr .co{font-size:18px;font-weight:900;letter-spacing:1px;text-transform:uppercase}
.hdr .ttl{font-size:18px;font-weight:700;margin-top:3px}
.hdr .per{font-size:16px;margin-top:2px}
.sig{display:flex;justify-content:space-between;margin-top:24px;padding-top:6px}
.sig-b{text-align:center;width:160px}
.sig-l{border-top:1px solid #000;margin-bottom:3px}
.sig-t{font-size:10px;color:#333}
table{width:100%;border-collapse:collapse;margin-top:6px}
th{border:1px solid #000;padding:5px 7px;font-size:10px;font-weight:700;background:#f0f0f0;color:#000;white-space:nowrap}
td{border:1px solid #000;padding:5px 7px;font-size:10px;vertical-align:middle;color:#000}
tr.tot td{background:#e8e8e8;font-weight:700}
.r{text-align:right}.l{text-align:left}
.nd{text-align:center;padding:18px;color:#888;font-size:10px}
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


def _build_html(cols, data, co, mo, yr):
    period = f"For the Month of {mo} {yr}" if mo and yr else (f"For the Year {yr}" if yr else "All Records")

    hdr = (
        f'<div class="hdr">'
        f'<div class="co">{co}</div>'
        f'<div class="ttl">Loan Register</div>'
        f'<div class="per">{period}</div>'
        f'</div>'
    )

    # thead
    thead = "<tr>"
    for c in cols:
        is_n = c.get("fieldtype", "") in _NUMERIC_FT
        thead += f'<th class="{"r" if is_n else "l"}">{c.get("label", "")}</th>'
    thead += "</tr>"

    detail_rows = [r for r in data if r.get("employee") != "TOTAL"]
    total_row   = next((r for r in data if r.get("employee") == "TOTAL"), None)
    ncols       = len(cols) or 1

    if not detail_rows:
        tbody = f'<tr><td colspan="{ncols}" class="nd">No data for this period</td></tr>'
    else:
        tbody = ""
        for row in detail_rows:
            tbody += "<tr>"
            for c in cols:
                fn   = c.get("fieldname", "")
                val  = row.get(fn, "")
                is_n = c.get("fieldtype", "") in _NUMERIC_FT
                if is_n:
                    tbody += f'<td class="r">{_fmt(val) if val not in ("", None) else ""}</td>'
                else:
                    tbody += f'<td class="l">{val or ""}</td>'
            tbody += "</tr>"

        # total row
        if total_row:
            tbody += '<tr class="tot">'
            for c in cols:
                fn   = c.get("fieldname", "")
                val  = total_row.get(fn, "")
                is_n = c.get("fieldtype", "") in _NUMERIC_FT
                if fn == "employee":
                    tbody += '<td class="l">TOTAL</td>'
                elif is_n:
                    tbody += f'<td class="r">{_fmt(val)}</td>'
                else:
                    tbody += '<td class="l"></td>'
            tbody += "</tr>"

    table = f"<table><thead>{thead}</thead><tbody>{tbody}</tbody></table>"
    return (
        f'<!DOCTYPE html><html><head><meta charset="UTF-8">{_CSS}</head>'
        f'<body>{hdr}{table}{_SIG}</body></html>'
    )


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
    fn  = f"Loan_Register_{ts}.pdf"
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

    co = filters.get("company", "")
    mo = filters.get("month",   "")
    yr = filters.get("year",    "")

    html = _build_html(cols, data, co, mo, yr)
    return _save_pdf(html, "Loan_Register")