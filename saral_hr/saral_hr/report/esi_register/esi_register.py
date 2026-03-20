import frappe
import json

from frappe import _
from frappe.utils import flt
from frappe.utils.pdf import get_pdf

MONTH_MAP = {
    "January":1,"February":2,"March":3,"April":4,"May":5,"June":6,
    "July":7,"August":8,"September":9,"October":10,"November":11,"December":12,
}

B = "1px solid #000"

_CSS = """<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Arial,sans-serif;font-size:13px;color:#000;background:#fff}
.hdr{text-align:center;border-bottom:2px solid #000;padding:10px 4px 8px;margin-bottom:8px}
.hdr .co{font-size:24px;font-weight:900;letter-spacing:1px;text-transform:uppercase}
.hdr .ttl{font-size:17px;font-weight:700;margin-top:5px}
.hdr .per{font-size:14px;margin-top:4px}
.sig{display:flex;justify-content:space-between;margin-top:32px;padding-top:8px}
.sig-b{text-align:center;width:180px}
.sig-l{border-top:1px solid #000;margin-bottom:4px}
.sig-t{font-size:13px;color:#333}
</style>"""

_SIG = '<div class="sig">' + "".join(
    f'<div class="sig-b"><div class="sig-l"></div><div class="sig-t">{l}</div></div>'
    for l in ["Prepared By", "Checked By", "Authorised Signatory"]
) + '</div>'

_NUMERIC_FT    = ("Float", "Currency", "Int", "Percent")
_SKIP_ON_TOTAL = {"esic_number", "days_paid", "date_of_joining", "date_of_birth"}

HDR_BG      = "#e8e8e8"
ROW_COLOURS = ["#ffffff", "#f0f0f0"]
PAD         = "padding:7px 9px;"
FS          = "font-size:13px;"


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
    if sd:
        p["start_date"] = sd
        c.append("ss.start_date=%(start_date)s")
    co = _parse_list(f.get("company"))
    if co:
        p["companies"] = tuple(co)
        c.append("ss.company IN %(companies)s")
    em = _parse_list(f.get("employee"))
    if em:
        p["employees"] = tuple(em)
        c.append("ss.employee IN %(employees)s")
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


def _get_data(f):
    cols = [
        _col("Sr",              "sr",              w=40),
        _col("ESI No.",         "esic_number",     w=150),
        _col("Employee Name",   "employee_name",   w=180),
        _col("Employee ID",     "employee_id",     w=110),
        _col("Days Paid",       "days_paid",       "Float", 80,  precision=2),
        _col("Gross Salary",    "gross_salary",    "Float", 120, precision=2),
        _col("Emp ESIC",        "emp_esi",         "Float", 110, precision=2),
        _col("Empr ESIC",       "empr_esi",        "Float", 110, precision=2),
        _col("Total ESI",       "total_esi",       "Float", 110, precision=2),
        _col("DOJ",             "date_of_joining", "Date",  100),
        _col("DOB",             "date_of_birth",   "Date",  100),
    ]

    if not f.get("company"):
        return cols, []

    p    = {}
    cond = _base_cond(f, p)
    catj = _cat_join(f, p)
    divc = _div_cond(f, p)

    slips = frappe.db.sql(
        f"""
        SELECT ss.name AS slip, ss.employee, ss.employee_name,
               ss.payment_days AS days_paid,
               ss.total_earnings AS gross_salary,
               emp.name AS eid,
               cl.date_of_joining,
               emp.date_of_birth,
               emp.esic_number
        FROM `tabSalary Slip` ss
        LEFT JOIN `tabEmployee` emp ON emp.name=ss.employee
        LEFT JOIN `tabCompany Link` cl ON cl.name=ss.employee
        {catj}
        WHERE {cond}{divc}
        ORDER BY ss.employee_name
        """,
        p, as_dict=1
    )

    if not slips:
        return cols, []

    sn = tuple(s.slip for s in slips)

    def _em(like, pf):
        m = {}
        for r in frappe.db.sql(
            f"SELECT sd.parent AS slip, sd.amount "
            f"FROM `tabSalary Details` sd "
            f"WHERE sd.parent IN %(sn)s "
            f"  AND sd.parentfield=%(pf)s "
            f"  AND LOWER(sd.salary_component) LIKE %(lk)s "
            f"  AND sd.amount > 0",
            {"sn": sn, "pf": pf, "lk": like}, as_dict=1
        ):
            m[r.slip] = m.get(r.slip, 0) + flt(r.amount)
        return m

    emp_m  = _em("%%esic%%", "deductions")
    empr_m = _em("%%esic%%", "employer_share")

    data      = []
    gg = ge = gr = 0.0
    sr_counter = 1

    for s in slips:
        ei  = flt(emp_m.get(s.slip,  0))
        eri = flt(empr_m.get(s.slip, 0))
        tot = ei + eri
        if tot <= 0:
            continue
        gg += flt(s.gross_salary, 2)
        ge += ei
        gr += eri
        data.append({
            "sr":              sr_counter,
            "esic_number":     s.esic_number      or "-",
            "employee_id":     s.eid              or s.employee,
            "employee_name":   s.employee_name,
            "days_paid":       flt(s.days_paid,   2),
            "gross_salary":    flt(s.gross_salary, 2),
            "emp_esi":         flt(ei,             2),
            "empr_esi":        flt(eri,            2),
            "total_esi":       flt(tot,            2),
            "date_of_joining": s.date_of_joining,
            "date_of_birth":   s.date_of_birth,
        })
        sr_counter += 1

    if data:
        data.append({
            "sr": "", "esic_number": "", "employee_id": "",
            "employee_name":   "Total",
            "days_paid":       "",
            "gross_salary":    flt(gg, 2),
            "emp_esi":         flt(ge, 2),
            "empr_esi":        flt(gr, 2),
            "total_esi":       flt(ge + gr, 2),
            "date_of_joining": "",
            "date_of_birth":   "",
            "bold":            1,
        })

    return cols, data


def execute(filters=None):
    return _get_data(filters or {})


# ---------------------------------------------------------------------------
# PDF — Transaction Checklist style, 2-row merged employee cell
# ---------------------------------------------------------------------------

# Numeric fields (right-aligned)
_RIGHT_FIELDS = {"sr", "days_paid", "gross_salary", "emp_esi", "empr_esi", "total_esi"}


def _build_html(cols, data, co, mo, yr):
    hdr = (
        f'<div class="hdr">'
        f'<div class="co">{co}</div>'
        f'<div class="ttl">ESI Register</div>'
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

    # ── thead — employee name/id stacked, all others flat ──────────────
    TH  = f"border:{B};{PAD}{FS}font-weight:700;background:{HDR_BG};white-space:normal;vertical-align:middle;"
    THL = TH + "text-align:left;"
    THR = TH + "text-align:right;"

    def _thead():
        h = '<thead><tr>'
        for c in cols:
            fn = c["fieldname"]
            if fn == "employee_id":
                # Skip — merged into employee_name cell
                continue
            align = "right" if fn in _RIGHT_FIELDS else "left"
            ts    = THR if align == "right" else THL
            if fn == "employee_name":
                lbl = f'Employee Name<br><span style="font-size:11px;font-weight:400;">Employee ID</span>'
            elif fn == "date_of_joining":
                lbl = f'DOJ<br><span style="font-size:11px;font-weight:400;">DOB</span>'
            elif fn == "date_of_birth":
                continue   # merged into DOJ cell
            else:
                lbl = c["label"]
            h += f'<th style="{ts}width:{c["width"]}px;">{lbl}</th>'
        h += '</tr></thead>'
        return h

    # ── row builder — 2 rows per employee for name/id and doj/dob ──────
    def _td_flat(val, fn, bg, bold):
        fw    = "font-weight:700;" if bold else ""
        align = "right" if fn in _RIGHT_FIELDS else "left"
        return (
            f'<td style="border:{B};{PAD}{FS}{fw}background:{bg};'
            f'text-align:{align};vertical-align:middle;">{val}</td>'
        )

    def _emp_rows(row, row_idx, is_total=False):
        bg   = HDR_BG if is_total else ROW_COLOURS[row_idx % 2]
        bold = is_total
        fw   = "font-weight:700;" if bold else ""

        emp_nm = row.get("employee_name", "") or ""
        emp_id = row.get("employee_id",   "") or ""
        doj    = str(row.get("date_of_joining") or "")
        dob    = str(row.get("date_of_birth")   or "")

        h = '<tr>'
        for c in cols:
            fn  = c["fieldname"]
            val = row.get(fn, "")

            if fn == "employee_id" or fn == "date_of_birth":
                # Skip — handled inside employee_name / date_of_joining cells
                continue

            if fn == "employee_name":
                # 2-line cell: Name on top, ID below
                h += (
                    f'<td style="border:{B};{PAD}{FS}{fw}background:{bg};'
                    f'text-align:left;vertical-align:middle;'
                    f'white-space:normal;word-wrap:break-word;">'
                    f'<strong>{emp_nm}</strong>'
                )
                if not is_total and emp_id:
                    h += f'<br><span style="font-size:11px;color:#333;">{emp_id}</span>'
                h += '</td>'

            elif fn == "date_of_joining":
                # 2-line cell: DOJ on top, DOB below
                h += (
                    f'<td style="border:{B};{PAD}font-size:12px;{fw}background:{bg};'
                    f'text-align:left;vertical-align:middle;">'
                    f'{doj or "&nbsp;"}'
                )
                if not is_total and dob:
                    h += f'<br><span style="font-size:11px;color:#333;">{dob}</span>'
                h += '</td>'

            elif fn in _SKIP_ON_TOTAL and is_total:
                h += f'<td style="border:{B};{PAD}{FS}background:{bg};"></td>'

            else:
                if c.get("fieldtype", "") in _NUMERIC_FT:
                    disp = _fmt(val) if val not in ("", None) else ""
                else:
                    disp = str(val) if val not in ("", None) else ""
                h += _td_flat(disp, fn, bg, bold)

        h += '</tr>'
        return h

    # ── pagination ──────────────────────────────────────────────────────
    FIRST, OTHER = 20, 25
    pages, idx, first = [], 0, True
    while idx < len(detail_rows):
        lim = FIRST if first else OTHER
        pages.append(detail_rows[idx: idx + lim])
        idx  += lim
        first = False
    if not pages:
        pages = [[]]

    total_pages = len(pages)
    parts       = []

    for pn, pr in enumerate(pages):
        pb   = '<div style="page-break-before:always;"></div>' if pn > 0 else ""
        last = (pn == len(pages) - 1)

        pg_footer = (
            f'<div style="text-align:right;font-size:12px;color:#444;'
            f'margin-top:6px;padding-right:2px;">'
            f'Page {pn + 1} of {total_pages}</div>'
        )

        body = '<tbody>'
        for ri, row in enumerate(pr):
            body += _emp_rows(row, ri)
        if last and total_row:
            body += _emp_rows(total_row, 0, is_total=True)
        body += '</tbody>'

        parts.append(
            f'{pb}{hdr}'
            f'<table style="width:100%;border-collapse:collapse;margin-top:8px;">'
            f'{_thead()}{body}</table>'
            f'{pg_footer}'
        )

    return (
        f'<!DOCTYPE html><html><head><meta charset="UTF-8">{_CSS}</head>'
        f'<body>{"".join(parts)}{_SIG}</body></html>'
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
    co   = _company_label(filters)
    mo   = filters.get("month", "")
    yr   = filters.get("year",  "")
    html = _build_html(cols, data, co, mo, yr)
    return _save_pdf(html, "ESI_Register")