import frappe
import json
import calendar

from frappe import _
from frappe.utils import flt
from frappe.utils.pdf import get_pdf

# ---------------------------------------------------------------------------
# Helpers shared with the main payroll report (duplicated here for standalone use)
# ---------------------------------------------------------------------------

MONTH_MAP = {
    "January": 1, "February": 2, "March": 3, "April": 4,
    "May": 5, "June": 6, "July": 7, "August": 8,
    "September": 9, "October": 10, "November": 11, "December": 12,
}


def _parse_list(v):
    if not v:
        return []
    if isinstance(v, list):
        return v
    try:
        p = json.loads(v)
        if isinstance(p, list):
            return p
    except Exception:
        pass
    return [x.strip() for x in v.split(",") if x.strip()]


def _fmt(v):
    if v is None or v == "" or v is False:
        return ""
    try:
        return f"{float(v):,.2f}"
    except (TypeError, ValueError):
        return str(v)


def _start_date(f):
    m = MONTH_MAP.get(f.get("month", ""))
    y = f.get("year", "")
    return f"{y}-{m:02d}-01" if m and y else None


def _col(label, fn, ft="Data", w=120, **kw):
    return {"label": _(label), "fieldname": fn, "fieldtype": ft, "width": w, **kw}


def _company_label(f):
    c = _parse_list(f.get("company"))
    return ", ".join(c) if c else (frappe.defaults.get_global_default("company") or "")


def _base_cond(f, p, alias="ss"):
    c = [f"{alias}.docstatus=1"]
    sd = _start_date(f)
    if sd:
        p["start_date"] = sd
        c.append(f"{alias}.start_date=%(start_date)s")
    co = _parse_list(f.get("company"))
    if co:
        p["companies"] = tuple(co)
        c.append(f"{alias}.company IN %(companies)s")
    em = _parse_list(f.get("employee"))
    if em:
        p["employees"] = tuple(em)
        c.append(f"{alias}.employee IN %(employees)s")
    return " AND ".join(c)


def _cat_join(f, p, ec="ss.employee"):
    cat = f.get("category")
    if not cat:
        return ""
    p["category"] = cat
    return f"INNER JOIN `tabCompany Link` cl_cat ON cl_cat.name={ec} AND cl_cat.category=%(category)s"


def _div_cond(f, p):
    d = _parse_list(f.get("division"))
    if not d:
        return ""
    p["divisions"] = tuple(d)
    return (
        " AND ss.employee IN ("
        "SELECT name FROM `tabCompany Link` "
        "WHERE division IN %(divisions)s OR department IN %(divisions)s)"
    )


# ---------------------------------------------------------------------------
# Core data function
# ---------------------------------------------------------------------------

def _get_data(f):
    """Return (columns, data) for the Professional Tax Register."""

    cols = [
        _col("Employee ID",      "employee_id",  w=140),
        _col("Employee Name",    "employee_name", w=220),
        _col("Gross Salary",     "gross_salary",  "Float", 150, precision=2),
        _col("PT Amount (Rs.)",  "pt_amount",     "Float", 140, precision=2),
    ]

    if not f.get("company"):
        return cols, []

    p = {}
    cond = _base_cond(f, p)
    catj = _cat_join(f, p)
    divc = _div_cond(f, p)

    slips = frappe.db.sql(
        f"""
        SELECT ss.name AS slip, ss.employee, ss.employee_name,
               ss.total_earnings AS gross_salary
        FROM `tabSalary Slip` ss
        {catj}
        WHERE {cond}{divc}
        ORDER BY ss.employee_name
        """,
        p, as_dict=1
    )

    if not slips:
        return cols, []

    sn = tuple(s.slip for s in slips)

    pm = {}
    for r in frappe.db.sql(
        """
        SELECT sd.parent AS slip, SUM(sd.amount) AS a
        FROM `tabSalary Details` sd
        WHERE sd.parent IN %(sn)s
          AND sd.parentfield = 'deductions'
          AND LOWER(sd.salary_component) LIKE '%%professional%%'
          AND sd.amount > 0
        GROUP BY sd.parent
        """,
        {"sn": sn}, as_dict=1
    ):
        pm[r.slip] = flt(r.a)

    data = []
    gg = gp = 0.0

    for s in slips:
        pt = flt(pm.get(s.slip, 0))
        if pt <= 0:
            continue
        gross = flt(s.gross_salary, 2)
        gg += gross
        gp += pt
        data.append({
            "employee_id":   s.employee,
            "employee_name": s.employee_name,
            "gross_salary":  gross,
            "pt_amount":     pt,
        })

    if data:
        data.append({
            "employee_id":   "",
            "employee_name": "Total",
            "gross_salary":  flt(gg, 2),
            "pt_amount":     flt(gp, 2),
            "bold":          1,
            "_row_type":     "total",
        })

    return cols, data


# ---------------------------------------------------------------------------
# Frappe report entry-point
# ---------------------------------------------------------------------------

def execute(filters=None):
    f = filters or {}
    return _get_data(f)


# ---------------------------------------------------------------------------
# PDF print helpers
# ---------------------------------------------------------------------------

B    = "1px solid #000"
TH_L = f"border:{B};padding:5px 7px;font-size:10px;font-weight:700;background:#f0f0f0;color:#000;text-align:left;white-space:nowrap;"
TH_R = f"border:{B};padding:5px 7px;font-size:10px;font-weight:700;background:#f0f0f0;color:#000;text-align:right;white-space:nowrap;"
TD_L = f"border:{B};padding:5px 7px;font-size:10px;vertical-align:middle;color:#000;text-align:left;"
TD_R = f"border:{B};padding:5px 7px;font-size:10px;vertical-align:middle;color:#000;text-align:right;"
TS_L = f"border:{B};padding:5px 7px;font-size:10px;font-weight:700;background:#e8e8e8;color:#000;text-align:left;"
TS_R = f"border:{B};padding:5px 7px;font-size:10px;font-weight:700;background:#e8e8e8;color:#000;text-align:right;"

_CSS = """<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: Arial, sans-serif; font-size: 10px; color: #000; background: #fff; }
.hdr { text-align: center; border-bottom: 2px solid #000; padding: 8px 4px 6px; margin-bottom: 6px; }
.hdr .co  { font-size: 18px; font-weight: 900; letter-spacing: 1px; text-transform: uppercase; }
.hdr .ttl { font-size: 13px; font-weight: 700; margin-top: 3px; }
.hdr .per { font-size: 11px; margin-top: 2px; }
table { width: 100%; border-collapse: collapse; margin-top: 6px; }
th { border: 1px solid #000; padding: 5px 7px; font-size: 10px; font-weight: 700; background: #f0f0f0; white-space: nowrap; }
td { border: 1px solid #000; padding: 5px 7px; font-size: 10px; vertical-align: middle; }
tr.tot td { background: #e8e8e8; font-weight: 700; }
.r { text-align: right; } .l { text-align: left; }
.nd { text-align: center; padding: 18px; color: #888; font-size: 10px; }
.sig { display: flex; justify-content: space-between; margin-top: 32px; padding-top: 6px; }
.sig-b { text-align: center; width: 160px; }
.sig-l { border-top: 1px solid #000; margin-bottom: 3px; }
.sig-t { font-size: 10px; color: #333; }
</style>"""

_SIG = (
    '<div class="sig">'
    + "".join(
        f'<div class="sig-b"><div class="sig-l"></div><div class="sig-t">{l}</div></div>'
        for l in ["Prepared By", "Checked By", "Authorised Signatory"]
    )
    + "</div>"
)


def _build_html(cols, data, co, mo, yr):
    """Render the full printable HTML for the Professional Tax Register."""

    hdr = (
        f'<div class="hdr">'
        f'<div class="co">{co}</div>'
        f'<div class="ttl">Professional Tax Register</div>'
        f'<div class="per">For the Month of {mo} {yr}</div>'
        f'</div>'
    )

    # Table header
    thead = "<tr>"
    for c in cols:
        is_n = c.get("fieldtype", "") in ("Float", "Currency", "Int", "Percent")
        thead += f'<th class="{"r" if is_n else "l"}">{c.get("label", "")}</th>'
    thead += "</tr>"

    # Table body
    tbody = ""
    if not data:
        tbody = f'<tr><td colspan="{len(cols)}" class="nd">No data for this period</td></tr>'
    else:
        for row in data:
            is_tot = bool(row.get("bold") or row.get("_row_type") == "total")
            cls = ' class="tot"' if is_tot else ""
            tbody += f"<tr{cls}>"
            for c in cols:
                fn  = c.get("fieldname", "")
                val = row.get(fn, "")
                is_n = c.get("fieldtype", "") in ("Float", "Currency", "Int", "Percent")
                # On total row, suppress pt_rate (not present here, but kept for safety)
                if is_tot and fn == "pt_rate":
                    tbody += f'<td class="{"r" if is_n else "l"}"></td>'
                elif is_n:
                    tbody += f'<td class="r">{_fmt(val) if val not in ("", None) else ""}</td>'
                else:
                    tbody += f'<td class="l">{val or ""}</td>'
            tbody += "</tr>"

    table = f"<table><thead>{thead}</thead><tbody>{tbody}</tbody></table>"
    return f"<!DOCTYPE html><html><head><meta charset='UTF-8'>{_CSS}</head><body>{hdr}{table}{_SIG}</body></html>"


def _save_pdf(html, prefix):
    pdf = get_pdf(
        html,
        options={
            "page-size":     "A4",
            "orientation":   "Landscape",
            "margin-top":    "8mm",
            "margin-right":  "8mm",
            "margin-bottom": "8mm",
            "margin-left":   "8mm",
            "encoding":      "UTF-8",
            "no-outline":    None,
        }
    )
    ts = frappe.utils.now_datetime().strftime("%Y%m%d_%H%M%S")
    fn = f"{prefix}_{ts}.pdf"
    with open(frappe.utils.get_files_path(fn, is_private=0), "wb") as fh:
        fh.write(pdf)
    doc = frappe.get_doc({
        "doctype":   "File",
        "file_name": fn,
        "is_private": 0,
        "file_url":  f"/files/{fn}",
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return doc.file_url


@frappe.whitelist()
def print_report(filters):
    if isinstance(filters, str):
        filters = json.loads(filters)
    cols, data = _get_data(filters)
    html = _build_html(
        cols, data,
        _company_label(filters),
        filters.get("month", ""),
        filters.get("year", ""),
    )
    return _save_pdf(html, "Professional_Tax_Register")