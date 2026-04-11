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
        {"fieldname": "employee",          "label": "Employee ID",       "fieldtype": "Link",  "options": "Employee",              "width": 200},
        {"fieldname": "employee_name",     "label": "Employee Name",     "fieldtype": "Data",                                       "width": 200},
        {"fieldname": "advance_id",        "label": "Advance ID",        "fieldtype": "Link",  "options": "Employee Loan Advance",  "width": 250},
        {"fieldname": "total_advance",     "label": "Total Advance",     "fieldtype": "Float",                                      "width": 200},
        {"fieldname": "recovered_advance", "label": "Recovered Advance", "fieldtype": "Float",                                      "width": 180},
        {"fieldname": "pending_advance",   "label": "Pending Advance",   "fieldtype": "Float",                                      "width": 180},
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
            ela.name AS advance_id,
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
        GROUP BY ela.name, ela.employee, ela.full_name
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
        f'<div class="ttl">Advance Register</div>'
        f'<div class="per">{period}</div>'
        f'</div>'
    )

    # thead
    thead = "<tr>"
    for c in cols:
        is_n = c.get("fieldtype", "") in _NUMERIC_FT
        thead += f'<th class="{"r" if is_n else "l"}">{c.get("label", "")}</th>'
    thead += "</tr>"

    ncols = len(cols) or 1

    if not data:
        tbody = f'<tr><td colspan="{ncols}" class="nd">No data for this period</td></tr>'
    else:
        tbody = ""
        for row in data:
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
        total_row = {
            "employee":          "TOTAL",
            "employee_name":     "",
            "advance_id":        "",
            "total_advance":     round(sum(r.get("total_advance",     0) or 0 for r in data), 2),
            "recovered_advance": round(sum(r.get("recovered_advance", 0) or 0 for r in data), 2),
            "pending_advance":   round(sum(r.get("pending_advance",   0) or 0 for r in data), 2),
        }
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

    co = filters.get("company", "")
    mo = filters.get("month",   "")
    yr = filters.get("year",    "")

    html = _build_html(cols, data, co, mo, yr)
    return _save_pdf(html, "Advance_Register")