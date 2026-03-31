import frappe
import json
import calendar

from frappe import _
from frappe.utils import flt
from frappe.utils.pdf import get_pdf

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MONTH_MAP = {
    "January":1,"February":2,"March":3,"April":4,"May":5,"June":6,
    "July":7,"August":8,"September":9,"October":10,"November":11,"December":12,
}

B = "1px solid #000"

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
.hold{color:#c0392b;font-style:italic}
</style>"""

_SIG = '<div class="sig">' + "".join(
    f'<div class="sig-b"><div class="sig-l"></div><div class="sig-t">{l}</div></div>'
    for l in ["Prepared By", "Checked By", "Authorised Signatory"]
) + '</div>'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_list(v):
    if not v: return []
    if isinstance(v, list): return v
    try:
        p = json.loads(v)
        if isinstance(p, list): return p
    except Exception: pass
    return [x.strip() for x in v.split(",") if x.strip()]

def _col(label, fn, ft="Data", w=120, **kw):
    return {"label": _(label), "fieldname": fn, "fieldtype": ft, "width": w, **kw}

def _date_range(f):
    m = MONTH_MAP.get(f.get("month", ""))
    y = int(f.get("year", 0) or 0)
    if not m or not y:
        return None, None
    return f"{y}-{m:02d}-01", f"{y}-{m:02d}-{calendar.monthrange(y, m)[1]:02d}"

def _company_label(f):
    c = _parse_list(f.get("company"))
    return ", ".join(c) if c else (frappe.defaults.get_global_default("company") or "")

def _fmt(v):
    if v is None or v == "": return ""
    try: return f"{float(v):,.2f}"
    except (TypeError, ValueError): return str(v)

def _bank_map(cos):
    if not cos: return {}
    return {
        r.name: (r.bank_name or "").strip().lower()
        for r in frappe.db.get_all(
            "Company",
            filters={"name": ["in", list(cos)]},
            fields=["name", "bank_name"],
        )
    }

def _on_hold(f):
    m, y = f.get("month", ""), f.get("year", "")
    if not m or not y: return set()
    return {
        r.employee
        for r in frappe.db.sql(
            "SELECT employee FROM `tabEmployee Salary Hold` "
            "WHERE status='On Hold' AND docstatus=1 "
            "AND month=%(m)s AND year=%(y)s",
            {"m": m, "y": y}, as_dict=1
        )
    }


# ---------------------------------------------------------------------------
# Core data function
# ---------------------------------------------------------------------------

def _get_data(f):
    cols = [
        _col("Employee ID",     "employee_id",     w=150),
        _col("Employee Name",   "employee_name",   w=280),
        _col("IFSC Code",       "ifsc_code",       w=200),
        _col("Account Number",  "account_number",  w=280),
        _col("Net Salary",      "net_salary",      "Data", 120),
        _col("Bank Name",       "bank_name",       w=190),
    ]

    if not f.get("company"):
        return cols, []

    s, e = _date_range(f)
    if not s:
        return cols, []

    p    = {"sd": s, "ed": e}
    cond = (
        "ss.docstatus=1 "
        "AND ss.start_date>=%(sd)s "
        "AND ss.end_date<=%(ed)s"
    )

    co = _parse_list(f.get("company"))
    if co:
        p["companies"] = tuple(co)
        cond += " AND ss.company IN %(companies)s"

    em = _parse_list(f.get("employee"))
    if em:
        p["employees"] = tuple(em)
        cond += " AND ss.employee IN %(employees)s"

    catj = ""
    cat  = f.get("category")
    if cat:
        p["category"] = cat
        catj = "INNER JOIN `tabCompany Link` cl_cat ON cl_cat.name=ss.employee AND cl_cat.category=%(category)s"

    divc = ""
    divs = _parse_list(f.get("division"))
    if divs:
        p["divisions"] = tuple(divs)
        divc = (
            " AND ss.employee IN ("
            "SELECT name FROM `tabCompany Link` "
            "WHERE division IN %(divisions)s OR department IN %(divisions)s)"
        )

    slips = frappe.db.sql(
        f"""
        SELECT ss.employee, ss.employee_name, ss.company, ss.net_salary,
               emp.bank_name, emp.account_number, emp.ifsc_code
        FROM `tabSalary Slip` ss
        INNER JOIN `tabCompany Link` cla ON cla.name=ss.employee AND cla.is_active=1
        LEFT JOIN `tabEmployee` emp ON emp.name=ss.employee
        {catj}
        WHERE {cond}{divc}
        ORDER BY ss.employee_name
        """,
        p, as_dict=1
    )

    if not slips:
        return cols, []

    oh  = _on_hold(f)
    hm  = _bank_map(list({s.company for s in slips if s.company}))

    data = []
    tot  = 0.0

    for s in slips:
        eb = (s.bank_name or "").strip().lower()
        hb = hm.get(s.company, "")

        if not (hb and eb == hb):
            continue

        if s.employee in oh:
            data.append({
                "employee_id":    s.employee,
                "employee_name":  s.employee_name,
                "ifsc_code":      "On Hold",
                "account_number": "On Hold",
                "net_salary":     "On Hold",
                "bank_name":      s.bank_name or "-",
            })
        else:
            n = flt(s.net_salary, 2)
            tot += n
            data.append({
                "employee_id":    s.employee,
                "employee_name":  s.employee_name,
                "ifsc_code":      s.ifsc_code      or "-",
                "account_number": s.account_number or "-",
                "net_salary":     f"{n:,.2f}",
                "bank_name":      s.bank_name      or "-",
            })

    if data:
        data.append({
            "employee_id":    "",
            "employee_name":  "Total",
            "ifsc_code":      "",
            "account_number": "",
            "net_salary":     f"{flt(tot, 2):,.2f}",
            "bank_name":      "",
            "bold":           1,
        })

    return cols, data


# ---------------------------------------------------------------------------
# Frappe report entry-point
# ---------------------------------------------------------------------------

def execute(filters=None):
    return _get_data(filters or {})


# ---------------------------------------------------------------------------
# PDF helpers
# ---------------------------------------------------------------------------

def _build_html(cols, data, co, mo, yr):
    title = "Home Bank Advice"

    hdr = (
        f'<div class="hdr">'
        f'<div class="co">{co}</div>'
        f'<div class="ttl">{title}</div>'
        f'<div class="per">For the Month of {mo} {yr}</div>'
        f'</div>'
    )

    def _th():
        h = "<tr>"
        for c in cols:
            h += f'<th>{c.get("label", "")}</th>'
        return h + "</tr>"

    def _dr(row):
        h = "<tr>"
        for c in cols:
            fn  = c.get("fieldname", "")
            val = row.get(fn, "")
            if fn == "net_salary" and val == "On Hold":
                h += '<td class="hold">On Hold</td>'
            else:
                h += f'<td>{val or ""}</td>'
        return h + "</tr>"

    def _tr(row):
        h = '<tr class="tot">'
        for c in cols:
            fn = c.get("fieldname", "")
            if fn == "employee_name":
                h += '<td>Total</td>'
            elif fn == "net_salary":
                h += f'<td>{_fmt(row.get(fn, ""))}</td>'
            else:
                h += '<td></td>'
        return h + "</tr>"

    detail_rows = [r for r in data if not r.get("bold")]
    total_row   = next((r for r in data if r.get("bold")), None)
    ncols       = len(cols) or 1

    if not detail_rows:
        return (
            f'<!DOCTYPE html><html><head><meta charset="UTF-8">{_CSS}</head>'
            f'<body>{hdr}'
            f'<table><thead>{_th()}</thead>'
            f'<tbody><tr><td colspan="{ncols}" class="nd">No data for this period</td></tr></tbody>'
            f'</table>{_SIG}</body></html>'
        )

    # Fewer rows per page now due to larger font
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
    cols, data = _get_data(filters)
    co   = _company_label(filters)
    mo   = filters.get("month", "")
    yr   = filters.get("year",  "")
    html = _build_html(cols, data, co, mo, yr)
    return _save_pdf(html, "Home_Bank_Advice")