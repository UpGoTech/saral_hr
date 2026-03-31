# Copyright (c) 2026, sj and contributors
# For license information, please see license.txt

import frappe
import calendar
import json
from datetime import datetime
from frappe.utils.pdf import get_pdf


def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"fieldname": "employee",          "label": "Employee ID",         "fieldtype": "Link",  "options": "Employee", "width": 130},
        {"fieldname": "employee_name",     "label": "Employee Name",       "fieldtype": "Data",                         "width": 200},
        {"fieldname": "total_advance",     "label": "Total Advance",       "fieldtype": "Float",                        "width": 160},
        {"fieldname": "recovered_advance", "label": "Recovered Advance",   "fieldtype": "Float",                        "width": 180},
        {"fieldname": "pending_advance",   "label": "Pending Advance",     "fieldtype": "Float",                        "width": 170},
    ]


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_employees_with_advances(doctype, txt, searchfield, start, page_len, filters):
    company = filters.get("company") if filters else None
    params  = {"txt": f"%{txt}%", "start": start, "page_len": page_len}

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
        FROM `tabEmployee Loan Advance` ela
        WHERE
            ela.type = 'Advance'
            AND ela.docstatus = 1
            {conditions}
        GROUP BY ela.employee, ela.full_name
        ORDER BY ela.employee ASC
        """,
        values,
        as_dict=True,
    )
    return rows


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
            dt       = datetime.strptime(f"{month} {year}", "%B %Y")
            last_day = calendar.monthrange(dt.year, dt.month)[1]
            return dt.strftime("%Y-%m-01"), dt.strftime(f"%Y-%m-{last_day:02d}")
        except Exception:
            return None, None
    elif year:
        return f"{year}-01-01", f"{year}-12-31"
    return None, None


# ------------------------------------------------------------------ #
#  Print                                                               #
# ------------------------------------------------------------------ #

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
    period = f"For the Month of {mo} {yr}" if mo and yr else (f"For the Year {yr}" if yr else "All Records")

    hdr = (
        f'<div class="hdr">'
        f'<div class="co">{co}</div>'
        f'<div class="ttl">{title}</div>'
        f'<div class="per">{period}</div>'
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
        amount_cols = {"total_advance", "recovered_advance", "pending_advance"}
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

    detail_rows = data
    ncols       = len(cols) or 1

    if not detail_rows:
        return (
            f'<!DOCTYPE html><html><head><meta charset="UTF-8">{_CSS}</head>'
            f'<body>{hdr}'
            f'<table><thead>{_th()}</thead>'
            f'<tbody><tr><td colspan="{ncols}" class="nd">No data for this period</td></tr></tbody>'
            f'</table>{_SIG}</body></html>'
        )

    total_row = {
        "employee":          "TOTAL",
        "employee_name":     "",
        "total_advance":     round(sum(r.get("total_advance",     0) or 0 for r in detail_rows), 2),
        "recovered_advance": round(sum(r.get("recovered_advance", 0) or 0 for r in detail_rows), 2),
        "pending_advance":   round(sum(r.get("pending_advance",   0) or 0 for r in detail_rows), 2),
    }

    FIRST, OTHER = 20, 25
    pages, idx, first = [], 0, True
    while idx < len(detail_rows):
        lim = FIRST if first else OTHER
        pages.append(detail_rows[idx: idx + lim])
        idx  += lim
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
        if last:
            html += _tr(total_row)
        html += '</tbody></table>'

    html += _SIG
    return f'<!DOCTYPE html><html><head><meta charset="UTF-8">{_CSS}</head><body>{html}</body></html>'


def _save_pdf(html, prefix):
    pdf = get_pdf(html, options={
        "page-size":     "A4",
        "orientation":   "Portrait",
        "margin-top":    "8mm",
        "margin-right":  "8mm",
        "margin-bottom": "8mm",
        "margin-left":   "8mm",
        "encoding":      "UTF-8",
        "no-outline":    None,
    })
    ts  = frappe.utils.now_datetime().strftime("%Y%m%d_%H%M%S")
    fn  = f"Advance_Register_{ts}.pdf"
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
    title = "Advance Register"

    html = _build_html(cols, data, co, title, mo, yr)
    return _save_pdf(html, "Advance_Register")