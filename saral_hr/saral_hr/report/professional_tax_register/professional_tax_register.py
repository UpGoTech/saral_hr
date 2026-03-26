import frappe
import json
import calendar

from frappe import _
from frappe.utils import flt
from frappe.utils.pdf import get_pdf

# ---------------------------------------------------------------------------
# Helpers
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
    cols = [
        _col("Employee ID",     "employee_id",   w=250),
        _col("Employee Name",   "employee_name", w=280),
        _col("PT Type",         "pt_type",       w=200),
        _col("Gross Salary",    "gross_salary",  "Float", 270, precision=2),
        _col("PT Amount (Rs.)", "pt_amount",     "Float", 210, precision=2),
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

    # PT amounts per slip
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

    # PT Type (pf_applicable) from the active Salary Structure Assignment
    # for each employee, valid on the slip's start_date
    sd = p.get("start_date", "")
    eids = list({s.employee for s in slips})
    pt_type_map = {}
    if eids and sd:
        for r in frappe.db.sql(
            """
            SELECT ssa.employee, ssa.pf_applicable
            FROM `tabSalary Structure Assignment` ssa
            WHERE ssa.employee IN %(eids)s
              AND ssa.docstatus = 1
              AND ssa.from_date <= %(sd)s
              AND (ssa.to_date IS NULL OR ssa.to_date >= %(sd)s)
            ORDER BY ssa.from_date DESC
            """,
            {"eids": tuple(eids), "sd": sd},
            as_dict=1
        ):
            # Keep the most recent assignment (ORDER BY from_date DESC, first wins)
            if r.employee not in pt_type_map:
                pt_type_map[r.employee] = r.pf_applicable or ""

    data = []
    gg = gp = 0.0

    for s in slips:
        pt = flt(pm.get(s.slip, 0))
        if pt <= 0:
            continue
        gross   = flt(s.gross_salary, 2)
        pt_type = pt_type_map.get(s.employee, "")
        gg += gross
        gp += pt
        data.append({
            "employee_id":   s.employee,
            "employee_name": s.employee_name,
            "pt_type":       pt_type,
            "gross_salary":  gross,
            "pt_amount":     pt,
        })

    if data:
        data.append({
            "employee_id":   "",
            "employee_name": "Total",
            "pt_type":       "",
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
    return _get_data(filters or {})


# ---------------------------------------------------------------------------
# PDF — matches Transaction Checklist style
# ---------------------------------------------------------------------------

B = "1px solid #000"

_CSS = """<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Arial,sans-serif;font-size:13px;color:#000;background:#fff}
.hdr{text-align:center;border-bottom:2px solid #000;padding:10px 4px 8px;margin-bottom:8px}
.hdr .co{font-size:24px;font-weight:900;letter-spacing:1px;text-transform:uppercase}
.hdr .ttl{font-size:17px;font-weight:700;margin-top:5px}
.hdr .per{font-size:17px;margin-top:4px}
.sig{display:flex;justify-content:space-between;margin-top:32px;padding-top:8px}
.sig-b{text-align:center;width:180px}
.sig-l{border-top:1px solid #000;margin-bottom:4px}
.sig-t{font-size:13px;color:#333}
</style>"""

_SIG = (
    '<div class="sig">'
    + "".join(
        f'<div class="sig-b"><div class="sig-l"></div><div class="sig-t">{l}</div></div>'
        for l in ["Prepared By", "Checked By", "Authorised Signatory"]
    )
    + "</div>"
)

HDR_BG      = "#e8e8e8"
ROW_COLOURS = ["#ffffff", "#f0f0f0"]
PAD         = "padding:7px 9px;"
FS          = "font-size:13px;"

# Fields that are numeric and should be right-aligned + formatted
NUM_FIELDS   = {"gross_salary", "pt_amount"}
RIGHT_FIELDS = NUM_FIELDS
# Fields to blank on total row
SKIP_ON_TOTAL = {"pt_type"}


def _build_html(cols, data, co, mo, yr):
    hdr = (
        f'<div class="hdr">'
        f'<div class="co">{co}</div>'
        f'<div class="ttl">Professional Tax Register</div>'
        f'<div class="per">For the Month of {mo} {yr}</div>'
        f'</div>'
    )

    if not data:
        return (
            f'<!DOCTYPE html><html><head><meta charset="UTF-8">{_CSS}</head>'
            f'<body>{hdr}'
            f'<p style="text-align:center;{PAD}{FS}color:#888;">No data for this period</p>'
            f'{_SIG}</body></html>'
        )

    detail_rows = [r for r in data if not r.get("bold")]
    total_row   = next((r for r in data if r.get("bold")), None)

    # ── thead ──────────────────────────────────────────────────────────
    def _thead():
        h = '<thead><tr>'
        for c in cols:
            fn    = c["fieldname"]
            align = "right" if fn in RIGHT_FIELDS else "left"
            h += (
                f'<th style="border:{B};{PAD}{FS}font-weight:700;'
                f'background:{HDR_BG};text-align:{align};'
                f'white-space:normal;vertical-align:middle;">'
                f'{c["label"]}</th>'
            )
        h += '</tr></thead>'
        return h

    # ── row builder ────────────────────────────────────────────────────
    def _row(row, row_idx, is_total=False):
        bg  = HDR_BG if is_total else ROW_COLOURS[row_idx % 2]
        fw  = "font-weight:700;" if is_total else ""
        h   = '<tr>'
        for c in cols:
            fn    = c["fieldname"]
            val   = row.get(fn, "")
            align = "right" if fn in RIGHT_FIELDS else "left"

            # Blank certain cols on total row
            if is_total and fn in SKIP_ON_TOTAL:
                disp = ""
            elif fn in NUM_FIELDS:
                disp = _fmt(val) if val not in ("", None) else ""
            else:
                disp = str(val) if val not in ("", None) else ""

            h += (
                f'<td style="border:{B};{PAD}{FS}{fw}'
                f'background:{bg};text-align:{align};vertical-align:middle;">'
                f'{disp}</td>'
            )
        h += '</tr>'
        return h

    # ── table ──────────────────────────────────────────────────────────
    body = '<tbody>'
    for ri, row in enumerate(detail_rows):
        body += _row(row, ri)
    if total_row:
        body += _row(total_row, 0, is_total=True)
    body += '</tbody>'

    pg_footer = (
        '<div style="text-align:right;font-size:12px;color:#444;'
        'margin-top:6px;padding-right:2px;">Page 1 of 1</div>'
    )

    table = f'<table style="width:100%;border-collapse:collapse;margin-top:8px;">{_thead()}{body}</table>'

    return (
        f'<!DOCTYPE html><html><head><meta charset="UTF-8">{_CSS}</head>'
        f'<body>{hdr}{table}{pg_footer}{_SIG}</body></html>'
    )


def _save_pdf(html, prefix):
    pdf = get_pdf(
        html,
        options={
            "page-size":     "A4",
            "orientation":   "Portrait",
            "margin-top":    "10mm",
            "margin-right":  "10mm",
            "margin-bottom": "10mm",
            "margin-left":   "10mm",
            "encoding":      "UTF-8",
            "no-outline":    None,
        }
    )
    ts = frappe.utils.now_datetime().strftime("%Y%m%d_%H%M%S")
    fn = f"{prefix}_{ts}.pdf"
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
    html = _build_html(
        cols, data,
        _company_label(filters),
        filters.get("month", ""),
        filters.get("year", ""),
    )
    return _save_pdf(html, "Professional_Tax_Register")