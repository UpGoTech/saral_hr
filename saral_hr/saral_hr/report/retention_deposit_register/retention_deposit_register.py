import frappe
import json

from frappe import _
from frappe.utils import flt, getdate, add_months
from frappe.utils.pdf import get_pdf

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MONTH_MAP = {
    "January":1,"February":2,"March":3,"April":4,"May":5,"June":6,
    "July":7,"August":8,"September":9,"October":10,"November":11,"December":12,
}

B    = "1px solid #000"

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
</style>"""

_SIG = '<div class="sig">' + "".join(
    f'<div class="sig-b"><div class="sig-l"></div><div class="sig-t">{l}</div></div>'
    for l in ["Prepared By", "Checked By", "Authorised Signatory"]
) + '</div>'

_NUMERIC_FT    = ("Float", "Currency", "Int", "Percent")
_SKIP_ON_TOTAL = {"date_of_joining", "ded_upto"}


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

def _start_date(f):
    m = MONTH_MAP.get(f.get("month", ""))
    y = f.get("year", "")
    return f"{y}-{m:02d}-01" if m and y else None

def _base_cond(f, p):
    c = ["ss.docstatus=1"]
    sd = _start_date(f)
    if sd: p["start_date"] = sd; c.append("ss.start_date=%(start_date)s")
    co = _parse_list(f.get("company"))
    if co: p["companies"] = tuple(co); c.append("ss.company IN %(companies)s")
    em = _parse_list(f.get("employee"))
    if em: p["employees"] = tuple(em); c.append("ss.employee IN %(employees)s")
    return " AND ".join(c)

def _cat_join(f, p):
    cat = f.get("category")
    if not cat: return ""
    p["category"] = cat
    return "INNER JOIN `tabCompany Link` cl_cat ON cl_cat.name=ss.employee AND cl_cat.category=%(category)s"

def _div_cond(f, p):
    d = _parse_list(f.get("division"))
    if not d: return ""
    p["divisions"] = tuple(d)
    return (
        " AND ss.employee IN ("
        "SELECT name FROM `tabCompany Link` "
        "WHERE division IN %(divisions)s OR department IN %(divisions)s)"
    )

def _company_label(f):
    c = _parse_list(f.get("company"))
    return ", ".join(c) if c else (frappe.defaults.get_global_default("company") or "")

def _fmt(v):
    if v is None or v == "": return ""
    try: return f"{float(v):,.2f}"
    except (TypeError, ValueError): return str(v)


# ---------------------------------------------------------------------------
# Core data function
# ---------------------------------------------------------------------------

def _get_data(f):
    cols = [
        _col("Employee ID",              "employee_id",       w=250),
        _col("Employee Name",            "employee_name",     w=280),
        _col("Date of Joining",          "date_of_joining",   "Date", 200),
        _col("Deduction Upto (3 Yrs)",   "ded_upto",          "Date", 270),
        _col("Retention Amount",         "retention_amount",  "Float", 210, precision=2),
    ]

    if not f.get("company"):
        return cols, []

    p = {"component": "Retention"}
    cond = _base_cond(f, p)
    catj = _cat_join(f, p)
    divc = _div_cond(f, p)

    rows = frappe.db.sql(
        f"""
        SELECT ss.employee AS eid, ss.employee_name,
               sd.amount AS ret
        FROM `tabSalary Slip` ss
        INNER JOIN `tabSalary Details` sd
            ON sd.parent=ss.name
            AND sd.parenttype='Salary Slip'
            AND sd.parentfield='deductions'
            AND sd.salary_component=%(component)s
            AND sd.amount > 0
        {catj}
        WHERE {cond}{divc}
        ORDER BY ss.employee_name
        """,
        p, as_dict=1
    )

    if not rows:
        return cols, []

    # Fetch date_of_joining from Company Link
    eids = tuple({r.eid for r in rows})
    cm = {
        r["name"]: r["date_of_joining"]
        for r in frappe.db.sql(
            "SELECT name, date_of_joining FROM `tabCompany Link` WHERE name IN %(ids)s",
            {"ids": eids}, as_dict=1
        )
    }

    data = []
    g    = 0.0

    for row in rows:
        doj = cm.get(row.eid)
        du  = None
        if doj:
            try:
                du = add_months(getdate(doj), 36)
            except Exception:
                pass
        ret = flt(row.ret, 2)
        g  += ret
        data.append({
            "employee_id":      row.eid,
            "employee_name":    row.employee_name,
            "date_of_joining":  doj,
            "ded_upto":         du,
            "retention_amount": ret,
        })

    if data:
        data.append({
            "employee_id":      "",
            "employee_name":    "Total",
            "date_of_joining":  None,
            "ded_upto":         None,
            "retention_amount": flt(g, 2),
            "bold":             1,
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
    hdr = (
        f'<div class="hdr">'
        f'<div class="co">{co}</div>'
        f'<div class="ttl">Retention Deposit Register</div>'
        f'<div class="per">For the Month of {mo} {yr}</div>'
        f'</div>'
    )

    # thead
    thead = "<tr>"
    for c in cols:
        is_n = c.get("fieldtype", "") in _NUMERIC_FT
        thead += f'<th class="{"r" if is_n else "l"}">{c.get("label", "")}</th>'
    thead += "</tr>"

    # tbody
    if not data:
        ncols = len(cols)
        tbody = f'<tr><td colspan="{ncols}" class="nd">No data for this period</td></tr>'
    else:
        tbody = ""
        for row in data:
            is_tot = bool(row.get("bold"))
            cls    = ' class="tot"' if is_tot else ""
            tbody += f"<tr{cls}>"
            for c in cols:
                fn   = c.get("fieldname", "")
                val  = row.get(fn, "")
                is_n = c.get("fieldtype", "") in _NUMERIC_FT
                if is_tot and fn in _SKIP_ON_TOTAL:
                    tbody += f'<td class="{"r" if is_n else "l"}"></td>'
                elif is_n:
                    tbody += f'<td class="r">{_fmt(val) if val not in ("", None) else ""}</td>'
                else:
                    # Format date objects as string
                    display = str(val) if val else ""
                    tbody += f'<td class="l">{display}</td>'
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
    co = _company_label(filters)
    mo = filters.get("month", "")
    yr = filters.get("year",  "")
    html = _build_html(cols, data, co, mo, yr)
    return _save_pdf(html, "Retention_Deposit_Register")