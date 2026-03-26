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
th{border:1px solid #000;padding:5px 7px;font-size:10px;font-weight:700;background:#f0f0f0;color:#000;white-space:nowrap}
td{border:1px solid #000;padding:5px 7px;font-size:10px;vertical-align:middle;color:#000}
tr.tot td{background:#e8e8e8;font-weight:700}
.r{text-align:right}.l{text-align:left}
.nd{text-align:center;padding:18px;color:#888;font-size:10px}
.hold{color:#c0392b;font-style:italic}
</style>"""

_SIG = '<div class="sig">' + "".join(
    f'<div class="sig-b"><div class="sig-l"></div><div class="sig-t">{l}</div></div>'
    for l in ["Prepared By", "Checked By", "Authorised Signatory"]
) + '</div>'

_NUMERIC_FN = {"net_salary"}


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
    """Map company → home bank_name (lowercase stripped)."""
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
# Core data function  (mode = "other")
# ---------------------------------------------------------------------------

def _get_data(f):
    cols = [
        _col("Employee ID",    "employee_id",    w=150),
        _col("Employee Name",  "employee_name",  w=280),
        _col("IFSC Code",      "ifsc_code",      w=200),
        _col("Account Number", "account_number", w=280),
        _col("Net Salary",     "net_salary",     "Data", 120),
        _col("Bank Name",      "bank_name",      w=190),
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
    hm  = _bank_map(list({sl.company for sl in slips if sl.company}))

    data = []
    tot  = 0.0

    for sl in slips:
        eb = (sl.bank_name or "").strip().lower()
        hb = hm.get(sl.company, "")

        # Other bank: employee's bank does NOT match company's home bank
        # (also includes employees with no bank set on company, i.e. hb is empty)
        is_home = hb and eb == hb
        if is_home:
            continue

        if sl.employee in oh:
            data.append({
                "employee_id":    sl.employee,
                "employee_name":  sl.employee_name,
                "ifsc_code":      "On Hold",
                "account_number": "On Hold",
                "net_salary":     "On Hold",
                "bank_name":      sl.bank_name or "-",
            })
        else:
            n = flt(sl.net_salary, 2)
            tot += n
            data.append({
                "employee_id":    sl.employee,
                "employee_name":  sl.employee_name,
                "ifsc_code":      sl.ifsc_code      or "-",
                "account_number": sl.account_number or "-",
                "net_salary":     f"{n:,.2f}",
                "bank_name":      sl.bank_name      or "-",
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
    title = "Other Bank Advice"

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
            is_n = c.get("fieldname") in _NUMERIC_FN or c.get("fieldtype", "") in ("Float", "Currency")
            h += f'<th class="{"r" if is_n else "l"}">{c.get("label", "")}</th>'
        return h + "</tr>"

    def _dr(row):
        h = "<tr>"
        for c in cols:
            fn  = c.get("fieldname", "")
            val = row.get(fn, "")
            if fn == "net_salary":
                if val == "On Hold":
                    h += '<td class="r hold">On Hold</td>'
                else:
                    h += f'<td class="r">{val or ""}</td>'
            else:
                h += f'<td class="l">{val or ""}</td>'
        return h + "</tr>"

    def _tr(row):
        h = '<tr class="tot">'
        for c in cols:
            fn   = c.get("fieldname", "")
            is_n = fn in _NUMERIC_FN or c.get("fieldtype", "") in ("Float", "Currency")
            if is_n:
                h += f'<td class="r">{_fmt(row.get(fn, ""))}</td>'
            elif fn == "employee_name":
                h += '<td class="l">Total</td>'
            else:
                h += '<td class="l"></td>'
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

    # Paginate: 30 rows first page, 35 on subsequent pages
    FIRST, OTHER = 30, 35
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
    return _save_pdf(html, "Other_Bank_Advice")