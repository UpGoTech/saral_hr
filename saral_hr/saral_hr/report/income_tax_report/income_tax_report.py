import frappe
import json
from frappe import _
from frappe.utils import flt
from frappe.utils.pdf import get_pdf

MONTH_MAP = {
    "January":1,"February":2,"March":3,"April":4,"May":5,"June":6,
    "July":7,"August":8,"September":9,"October":10,"November":11,"December":12,
}

_NUMERIC_FT = ("Float", "Currency", "Int", "Percent")

# ---------------- CSS + SIGNATURE ---------------- #

_CSS = """<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Arial,sans-serif;font-size:10px;color:#000;background:#fff}
.hdr{text-align:center;border-bottom:2px solid #000;padding:8px 4px 6px;margin-bottom:6px}
.hdr .co{font-size:18px;font-weight:900;letter-spacing:1px;text-transform:uppercase}
.hdr .ttl{font-size:13px;font-weight:700;margin-top:3px}
.hdr .per{font-size:11px;margin-top:2px}
.sig{display:flex;justify-content:space-between;margin-top:24px;padding-top:6px}
.sig-b{text-align:center;width:160px}
.sig-l{border-top:1px solid #000;margin-bottom:3px}
.sig-t{font-size:10px;color:#333}
table{width:100%;border-collapse:collapse;margin-top:6px}
th{border:1px solid #000;padding:5px 7px;font-size:10px;font-weight:700;background:#f0f0f0}
td{border:1px solid #000;padding:5px 7px;font-size:10px}
tr.tot td{background:#e8e8e8;font-weight:700}
.r{text-align:right}.l{text-align:left}
.nd{text-align:center;padding:18px;color:#888}
</style>"""

_SIG = '<div class="sig">' + "".join(
    f'<div class="sig-b"><div class="sig-l"></div><div class="sig-t">{l}</div></div>'
    for l in ["Prepared By", "Checked By", "Authorised Signatory"]
) + '</div>'


# ---------------- HELPERS ---------------- #

def _parse_list(v):
    if not v: return []
    if isinstance(v, list): return v
    try: return json.loads(v)
    except: return [v]

def _start_date(f):
    m = MONTH_MAP.get(f.get("month"))
    y = f.get("year")
    return f"{y}-{m:02d}-01" if m and y else None

def _company_label(f):
    c = _parse_list(f.get("company"))
    return ", ".join(c) if c else (frappe.defaults.get_global_default("company") or "")


# ---------------- REPORT ---------------- #

def execute(filters=None):
    filters = filters or {}

    columns = [
        {"label": "Employee ID", "fieldname": "employee", "width": 140},
        {"label": "Employee Name", "fieldname": "employee_name", "width": 200},
        {"label": "Net Salary", "fieldname": "net_salary", "fieldtype": "Float", "width": 120},
        {"label": "Income Tax", "fieldname": "income_tax", "fieldtype": "Float", "width": 120},
    ]

    data = []

    companies = _parse_list(filters.get("company"))
    employees = _parse_list(filters.get("employee"))
    start_date = _start_date(filters)

    conditions = ["ss.docstatus = 1"]
    params = {}

    if start_date:
        conditions.append("ss.start_date = %(start_date)s")
        params["start_date"] = start_date

    if companies:
        conditions.append("ss.company IN %(companies)s")
        params["companies"] = tuple(companies)

    if employees:
        conditions.append("ss.employee IN %(employees)s")
        params["employees"] = tuple(employees)

    cond = " AND ".join(conditions)

    slips = frappe.db.sql(f"""
        SELECT ss.name, ss.employee, ss.employee_name, ss.net_salary
        FROM `tabSalary Slip` ss
        WHERE {cond}
    """, params, as_dict=1)

    if not slips:
        return columns, []

    slip_names = tuple(s.name for s in slips if s.name)
    if not slip_names:
        return columns, []

    tax_data = frappe.db.sql("""
        SELECT parent, SUM(amount) as tax
        FROM `tabSalary Details`
        WHERE parent IN %(slips)s
        AND parentfield = 'deductions'
        AND LOWER(salary_component) LIKE '%%income tax%%'
        GROUP BY parent
    """, {"slips": slip_names}, as_dict=1)

    tax_map = {t.parent: flt(t.tax) for t in tax_data}

    total_net = 0
    total_tax = 0

    for s in slips:
        tax = flt(tax_map.get(s.name, 0))
        if tax <= 0:
            continue

        net = flt(s.net_salary)

        total_net += net
        total_tax += tax

        data.append({
            "employee": s.employee,
            "employee_name": s.employee_name,
            "net_salary": net,
            "income_tax": tax
        })

    if data:
        data.append({
            "employee": "",
            "employee_name": "Total",
            "net_salary": total_net,
            "income_tax": total_tax,
            "bold": 1
        })

    return columns, data


# ---------------- PDF ---------------- #

def _build_html(cols, data, f):
    header = (
        f'<div class="hdr"><div class="co">{_company_label(f)}</div>'
        f'<div class="ttl">Income Tax Register</div>'
        f'<div class="per">For the Month of {f.get("month")} {f.get("year")}</div></div>'
    )

    thead = "<tr>" + "".join(
        f'<th class="{"r" if c.get("fieldtype") in _NUMERIC_FT else "l"}">{c["label"]}</th>'
        for c in cols
    ) + "</tr>"

    if not data:
        tbody = f'<tr><td colspan="{len(cols)}" class="nd">No data</td></tr>'
    else:
        tbody = ""
        for row in data:
            cls = ' class="tot"' if row.get("bold") else ""
            tbody += f"<tr{cls}>"
            for c in cols:
                val = row.get(c["fieldname"], "")
                if c.get("fieldtype") in _NUMERIC_FT:
                    val = f"{float(val):,.2f}" if val else ""
                    tbody += f'<td class="r">{val}</td>'
                else:
                    tbody += f'<td class="l">{val}</td>'
            tbody += "</tr>"

    return f"""<!DOCTYPE html><html><head>{_CSS}</head>
    <body>{header}<table><thead>{thead}</thead><tbody>{tbody}</tbody></table>{_SIG}</body></html>"""


def _save_pdf(html):
    pdf = get_pdf(html, options={"page-size":"A4","orientation":"Landscape"})
    name = "Income_Tax_Report.pdf"

    doc = frappe.get_doc({
        "doctype": "File",
        "file_name": name,
        "content": pdf,
        "is_private": 0
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return doc.file_url


@frappe.whitelist()
def print_report(filters):
    if isinstance(filters, str):
        filters = json.loads(filters)

    cols, data = execute(filters)
    html = _build_html(cols, data, filters)
    return _save_pdf(html)