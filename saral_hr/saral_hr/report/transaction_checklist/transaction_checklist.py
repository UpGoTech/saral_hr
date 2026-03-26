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
    try:
        fv = float(v)
        if fv == 0: return ""
        return f"{fv:,.2f}"
    except (TypeError, ValueError): return str(v)

def _sanitize(s):
    return s.strip().lower().replace(" ", "_").replace("-", "_").replace("(", "").replace(")", "").replace("__","_")

def _fn(prefix, abbr):
    return f"{prefix}_{_sanitize(abbr)}"


# ---------------------------------------------------------------------------
# Fetch dynamic components from actual salary slips
# ---------------------------------------------------------------------------

def _get_components(w, p):
    rows = frappe.db.sql(
        """
        SELECT DISTINCT sd.salary_component, sc.type, sc.employer_contribution,
               COALESCE(sc.salary_component_abbr, sd.salary_component) AS abbr
        FROM `tabSalary Slip` ss
        INNER JOIN `tabSalary Details` sd ON sd.parent=ss.name
            AND sd.parenttype='Salary Slip'
        INNER JOIN `tabSalary Component` sc ON sc.name=sd.salary_component
        WHERE {w}
        ORDER BY sc.type, sc.employer_contribution, sd.salary_component
        """.format(w=w),
        p, as_dict=1
    )

    earn_comps    = []
    emp_ded_comps = []
    empr_comps    = []
    seen = set()

    for r in rows:
        key = r["salary_component"]
        if key in seen:
            continue
        seen.add(key)
        entry = (r["salary_component"], r["abbr"])
        if r["type"] == "Earning":
            earn_comps.append(entry)
        elif r["employer_contribution"]:
            empr_comps.append(entry)
        else:
            emp_ded_comps.append(entry)

    return earn_comps, emp_ded_comps, empr_comps


def _fetch_slip_comps(sn):
    if not sn:
        return {}
    r = {}
    for x in frappe.db.sql(
        "SELECT sd.parent AS slip, sd.salary_component AS comp, sd.amount "
        "FROM `tabSalary Details` sd "
        "WHERE sd.parent IN %(sn)s",
        {"sn": tuple(sn)}, as_dict=1
    ):
        r.setdefault(x["slip"], {})[x["comp"]] = x["amount"]
    return r


# ---------------------------------------------------------------------------
# Core data function
# ---------------------------------------------------------------------------

def _get_data(f):
    if not f.get("company"):
        return [_col("Employee", "employee", w=110)], []

    p = {}
    s, e = _date_range(f)
    if not s:
        return [_col("Employee", "employee", w=110)], []

    p.update(start_date=s, end_date=e)
    conds = [
        "ss.docstatus=1",
        "ss.start_date>=%(start_date)s",
        "ss.end_date<=%(end_date)s",
    ]

    co = _parse_list(f.get("company"))
    if co:
        p["companies"] = tuple(co)
        conds.append("ss.company IN %(companies)s")

    em_filter = _parse_list(f.get("employee"))
    if em_filter:
        p["employees"] = tuple(em_filter)
        conds.append("ss.employee IN %(employees)s")

    cat  = f.get("category")
    catj = ""
    if cat:
        p["category"] = cat
        catj = "INNER JOIN `tabCompany Link` cl_cat ON cl_cat.name=ss.employee AND cl_cat.category=%(category)s"

    divs = _parse_list(f.get("division"))
    if divs:
        p["divisions"] = tuple(divs)
        conds.append(
            "ss.employee IN (SELECT name FROM `tabCompany Link` "
            "WHERE division IN %(divisions)s OR department IN %(divisions)s)"
        )

    w = " AND ".join(conds)

    earn_comps, emp_ded_comps, empr_comps = _get_components(w, p)

    cols = [
        _col("Employee",      "employee",      w=150),
        _col("Employee Name", "employee_name", w=200),
        _col("Payment Days",  "payment_days",  "Float", 120,  precision=2),
        _col("Absent Days",   "absent_days",   "Float", 120,  precision=2),
        _col("LWP",           "total_lwp",     "Float", 120,  precision=2),
    ]
    for name, abbr in earn_comps:
        cols.append(_col(f"{name} ({abbr})", _fn("e", abbr), "Float", 180, precision=2))
    cols.append(_col("Gross Earnings", "gross_earnings", "Float", 180, precision=2))

    for name, abbr in emp_ded_comps:
        cols.append(_col(f"{name} ({abbr})", _fn("d", abbr), "Float", 180, precision=2))
    cols.append(_col("Total Deductions", "total_deductions", "Float", 180, precision=2))

    for name, abbr in empr_comps:
        cols.append(_col(f"{name} ({abbr})", _fn("r", abbr), "Float", 180, precision=2))
    cols.append(_col("Employer Total", "employer_total", "Float", 180, precision=2))
    cols.append(_col("Net Salary", "net_salary", "Float", 180, precision=2))

    slips = frappe.db.sql(
        f"""
        SELECT ss.name AS slip, ss.employee, ss.employee_name,
               ss.payment_days, ss.absent_days, ss.total_lwp, ss.net_salary
        FROM `tabSalary Slip` ss {catj}
        WHERE {w}
        ORDER BY ss.employee_name
        """,
        p, as_dict=1
    )
    if not slips:
        return cols, []

    sn       = [sl["slip"] for sl in slips]
    comp_map = _fetch_slip_comps(sn)

    data  = []
    grand = {
        "payment_days": 0.0, "absent_days": 0.0, "total_lwp": 0.0,
        "gross_earnings": 0.0, "total_deductions": 0.0,
        "employer_total": 0.0, "net_salary": 0.0,
    }
    for name, abbr in earn_comps:
        grand[_fn("e", abbr)] = 0.0
    for name, abbr in emp_ded_comps:
        grand[_fn("d", abbr)] = 0.0
    for name, abbr in empr_comps:
        grand[_fn("r", abbr)] = 0.0

    for sl in slips:
        sc  = comp_map.get(sl["slip"], {})
        row = {
            "employee":      sl["employee"],
            "employee_name": sl["employee_name"],
            "payment_days":  flt(sl["payment_days"], 2),
            "absent_days":   flt(sl.get("absent_days") or 0, 2),
            "total_lwp":     flt(sl["total_lwp"] or 0, 2),
            "net_salary":    flt(sl["net_salary"], 2),
        }

        ge = 0.0
        for name, abbr in earn_comps:
            amt = flt(sc.get(name), 2)
            row[_fn("e", abbr)] = amt
            ge += amt
            grand[_fn("e", abbr)] += amt
        row["gross_earnings"] = flt(ge, 2)
        grand["gross_earnings"] += ge

        td = 0.0
        for name, abbr in emp_ded_comps:
            amt = flt(sc.get(name), 2)
            row[_fn("d", abbr)] = amt
            td += amt
            grand[_fn("d", abbr)] += amt
        row["total_deductions"] = flt(td, 2)
        grand["total_deductions"] += td

        et = 0.0
        for name, abbr in empr_comps:
            amt = flt(sc.get(name), 2)
            row[_fn("r", abbr)] = amt
            et += amt
            grand[_fn("r", abbr)] += amt
        row["employer_total"] = flt(et, 2)
        grand["employer_total"] += et

        grand["net_salary"]   += flt(sl["net_salary"], 2)
        grand["payment_days"] += flt(sl["payment_days"], 2)
        grand["absent_days"]  += flt(sl.get("absent_days") or 0, 2)
        grand["total_lwp"]    += flt(sl["total_lwp"] or 0, 2)

        data.append(row)

    if data:
        grand_row = {
            "employee":      "",
            "employee_name": "Grand Total",
            "bold":          1,
            **{k: flt(v, 2) for k, v in grand.items()},
        }
        data.append(grand_row)

    return cols, data


def execute(filters=None):
    return _get_data(filters or {})


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

# FIX 3: body has width:100% so flex containers span full page width
_CSS = """<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Arial,sans-serif;font-size:13px;color:#000;background:#fff;width:100%;}
.hdr{text-align:center;border-bottom:2px solid #000;padding:8px 4px 6px;margin-bottom:6px}
.hdr .co{font-size:24px;font-weight:900;letter-spacing:1px;text-transform:uppercase}
.hdr .ttl{font-size:17px;font-weight:700;margin-top:5px}
.hdr .per{font-size:14px;margin-top:4px}
table{width:100%;border-collapse:collapse;table-layout:fixed;}
</style>"""

# FIX 3: inline width:100% on the sig container so wkhtmltopdf
# doesn't collapse it to content width
_SIG = """
<!--SIG_START-->
<div style="display:flex;justify-content:space-between;
            width:100%;margin-top:30px;padding-top:10px;
            box-sizing:border-box;">
    <div style="text-align:center;width:180px;">
        <div style="border-top:1px solid #000;margin-bottom:4px;"></div>
        <div style="font-size:13px;color:#333;">Prepared By</div>
    </div>
    <div style="text-align:center;width:180px;">
        <div style="border-top:1px solid #000;margin-bottom:4px;"></div>
        <div style="font-size:13px;color:#333;">Checked By</div>
    </div>
    <div style="text-align:center;width:180px;">
        <div style="border-top:1px solid #000;margin-bottom:4px;"></div>
        <div style="font-size:13px;color:#333;">Authorised Signatory</div>
    </div>
</div>
<!--SIG_END-->
"""


def _comps_from_cols(cols):
    earn_comps, emp_ded_comps, empr_comps = [], [], []
    SKIP = {
        "employee", "employee_name", "payment_days", "absent_days", "total_lwp",
        "gross_earnings", "total_deductions", "employer_total", "net_salary",
    }
    for c in cols:
        fn = c["fieldname"]
        if fn in SKIP:
            continue
        label = c.get("label", fn)
        if "(" in label and label.endswith(")"):
            name = label[:label.rfind("(")].strip()
            abbr = label[label.rfind("(")+1:-1].strip()
        else:
            name = label
            abbr = fn
        if fn.startswith("e_"):
            earn_comps.append((name, abbr))
        elif fn.startswith("d_"):
            emp_ded_comps.append((name, abbr))
        elif fn.startswith("r_"):
            empr_comps.append((name, abbr))
    return earn_comps, emp_ded_comps, empr_comps


def _build_html(cols, data, co, mo, yr, earn_comps=None, emp_ded_comps=None, empr_comps=None):
    if earn_comps is None or emp_ded_comps is None or empr_comps is None:
        earn_comps, emp_ded_comps, empr_comps = _comps_from_cols(cols)

    # Company/title header — only used on page 1
    hdr_html = (
        f'<div class="hdr">'
        f'<div class="co">{co}</div>'
        f'<div class="ttl">Transaction Checklist</div>'
        f'<div class="per">For the Month of {mo} {yr}</div>'
        f'</div>'
    )

    if not data:
        return (
            f'<!DOCTYPE html><html><head><meta charset="UTF-8">{_CSS}</head>'
            f'<body>{hdr_html}'
            f'<p style="text-align:center;padding:20px;color:#888;">No data for this period</p>'
            f'{_SIG}</body></html>'
        )

    detail_rows = [r for r in data if not r.get("bold")]
    grand_row   = next((r for r in data if r.get("bold")), {})

    ne     = len(earn_comps)
    nd     = len(emp_ded_comps)
    nr     = len(empr_comps)
    n_cols = max(ne, nd, nr)

    W_SR   = 20
    W_EMP  = 115
    W_DAYS = 40
    W_COMP = 54
    W_TOT  = 64
    W_NET  = 68

    # ── thead (repeats on every page — correct behaviour) ──────────────
    def _thead():
        THL = (f"border:{B};padding:6px 8px;font-size:13px;font-weight:700;"
               f"background:#f0f0f0;text-align:left;white-space:normal;vertical-align:middle;")
        THR = (f"border:{B};padding:6px 8px;font-size:13px;font-weight:700;"
               f"background:#f0f0f0;text-align:right;white-space:normal;vertical-align:middle;")
        THT = (f"border:{B};padding:7px 9px;font-size:13px;font-weight:700;"
               f"background:#f0f0f0;text-align:right;white-space:normal;vertical-align:middle;")

        h  = '<thead>'

        # Row 1 — Earnings names
        h += '<tr>'
        h += f'<th rowspan="3" style="{THR}width:{W_SR}px;text-align:center;">Sr</th>'
        h += f'<th rowspan="2" style="{THL}width:{W_EMP}px;">Emp Name</th>'
        h += f'<th style="{THR}width:{W_DAYS}px;">Pay Days</th>'
        for i in range(n_cols):
            lbl = earn_comps[i][0] if i < ne else "&nbsp;"
            h += f'<th style="{THR}width:{W_COMP}px;">{lbl}</th>'
        h += f'<th style="{THT}width:{W_TOT}px;">Total Earnings</th>'
        h += f'<th rowspan="3" style="{THT}width:{W_NET}px;">Net Salary</th>'
        h += '</tr>'

        # Row 2 — Deduction names
        h += '<tr>'
        h += f'<th style="{THR}width:{W_DAYS}px;">Absent</th>'
        for i in range(n_cols):
            lbl = emp_ded_comps[i][0] if i < nd else "&nbsp;"
            h += f'<th style="{THR}width:{W_COMP}px;font-size:13px;">{lbl}</th>'
        h += f'<th style="{THT}width:{W_TOT}px;font-size:13px;">Total Deductions</th>'
        h += '</tr>'

        # Row 3 — Employer names + Emp ID
        h += '<tr>'
        h += f'<th style="{THL}width:{W_EMP}px;font-size:13px;color:#222;">Emp ID</th>'
        h += f'<th style="{THR}width:{W_DAYS}px;font-size:13px;">LWP</th>'
        for i in range(n_cols):
            lbl = empr_comps[i][0] if i < nr else "&nbsp;"
            h += f'<th style="{THR}width:{W_COMP}px;font-size:13px;">{lbl}</th>'
        h += f'<th style="{THT}width:{W_TOT}px;font-size:13px;">Total Employer Share</th>'
        h += '</tr>'

        h += '</thead>'
        return h

    # ── Row builder ─────────────────────────────────────────────────────
    ROW_COLOURS = ["#ffffff", "#f5f5f5"]
    HDR_BG      = "#f0f0f0"
    FS          = "font-size:13px;"
    FS_NET      = "font-size:15px;"
    PAD         = "padding:7px 9px;"

    def _emp_rows(row, sr, is_grand=False, row_idx=0):
        bg   = HDR_BG if is_grand else ROW_COLOURS[row_idx % 2]
        fw   = "font-weight:700;" if is_grand else ""

        name = row.get("employee_name", "")
        code = row.get("employee", "")
        pd   = _fmt(row.get("payment_days")) or "0"
        ab   = _fmt(row.get("absent_days"))  or "0"
        lwp  = _fmt(row.get("total_lwp"))    or "0"
        ge   = _fmt(row.get("gross_earnings"))   or "—"
        td2  = _fmt(row.get("total_deductions")) or "—"
        et2  = _fmt(row.get("employer_total"))   or "—"
        ns   = _fmt(row.get("net_salary"))       or "—"

        def _fixed(val, w, row_num, align="center", force_border=False):
            if force_border:
                bt, bb = B, B
            elif row_num == 1:
                bt, bb = B, "none"
            elif row_num == 2:
                bt, bb = "none", "none"
            else:
                bt, bb = "none", B
            return (
                f'<td style="border-top:{bt};border-bottom:{bb};'
                f'border-left:{B};border-right:{B};'
                f'width:{w}px;{PAD}{FS}{fw}background:{bg};'
                f'text-align:{align};vertical-align:middle;">{val}</td>'
            )

        def _comp(val, _row_num):
            return (
                f'<td style="border:{B};{PAD}{FS}{fw}background:{bg};'
                f'text-align:right;vertical-align:middle;">{val}</td>'
            )

        def _tot(val, _row_num):
            return (
                f'<td style="border:{B};width:{W_TOT}px;{PAD}{FS}{fw}background:{bg};'
                f'text-align:right;vertical-align:middle;">{val}</td>'
            )

        def _emp_cell(row_num):
            if row_num == 1:
                bt, bb  = B, "none"
                content = f'<strong style="{FS}font-weight:700;">{name}</strong>'
            elif row_num == 2:
                bt, bb  = "none", "none"
                content = "&nbsp;"
            else:
                bt, bb  = "none", B
                content = (
                    f'<span style="font-size:13px;color:#222;">{code}</span>'
                    if not is_grand else "&nbsp;"
                )
            return (
                f'<td style="border-top:{bt};border-bottom:{bb};'
                f'border-left:{B};border-right:{B};'
                f'width:{W_EMP}px;{PAD}background:{bg};'
                f'text-align:left;vertical-align:middle;'
                f'white-space:normal;word-wrap:break-word;">{content}</td>'
            )

        def _net_cell(row_num):
            if row_num == 1:
                bt, bb  = B, "none"
                content = "&nbsp;"
            elif row_num == 2:
                bt, bb  = "none", "none"
                content = f'<span style="{FS_NET}font-weight:700;">{ns}</span>'
            else:
                bt, bb  = "none", B
                content = "&nbsp;"
            return (
                f'<td style="border-top:{bt};border-bottom:{bb};'
                f'border-left:{B};border-right:{B};'
                f'width:{W_NET}px;{PAD}background:{bg};'
                f'text-align:right;vertical-align:middle;">{content}</td>'
            )

        # Row 1 — Earnings
        r1  = '<tr>'
        r1 += _fixed(sr if not is_grand else "", W_SR, 1, align="center")
        r1 += _emp_cell(1)
        r1 += _fixed(pd, W_DAYS, 1, align="right", force_border=True)
        for i in range(n_cols):
            v   = (_fmt(row.get(_fn("e", earn_comps[i][1]))) or "—") if i < ne else "&nbsp;"
            r1 += _comp(v, 1)
        r1 += _tot(ge, 1)
        r1 += _net_cell(1)
        r1 += '</tr>'

        # Row 2 — Deductions
        r2  = '<tr>'
        r2 += _fixed("", W_SR, 2, align="center")
        r2 += _emp_cell(2)
        r2 += _fixed(ab, W_DAYS, 2, align="right", force_border=True)
        for i in range(n_cols):
            v   = (_fmt(row.get(_fn("d", emp_ded_comps[i][1]))) or "—") if i < nd else "&nbsp;"
            r2 += _comp(v, 2)
        r2 += _tot(td2, 2)
        r2 += _net_cell(2)
        r2 += '</tr>'

        # Row 3 — Employer
        r3  = '<tr>'
        r3 += _fixed("", W_SR, 3, align="center")
        r3 += _emp_cell(3)
        r3 += _fixed(lwp, W_DAYS, 3, align="right", force_border=True)
        for i in range(n_cols):
            v   = (_fmt(row.get(_fn("r", empr_comps[i][1]))) or "—") if i < nr else "&nbsp;"
            r3 += _comp(v, 3)
        r3 += _tot(et2, 3)
        r3 += _net_cell(3)
        r3 += '</tr>'

        return r1 + r2 + r3

    # ── Pagination ──────────────────────────────────────────────────────
    # Each employee = 3 HTML rows.
    # FIX 2: reduced limits to prevent employee rows splitting across pages.
    # Page 1 has the title header so fewer employees fit (9).
    # Subsequent pages have more room (14).
    FIRST, OTHER = 9, 14
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
    sr_counter  = 1

    for pn, pr in enumerate(pages):
        pb   = '<div style="page-break-before:always;"></div>' if pn > 0 else ""
        last = (pn == len(pages) - 1)

        # FIX 1: company title header only on page 1;
        # column headers (_thead) still repeat on every page
        page_hdr = hdr_html if pn == 0 else ""

        pg_footer = (
            f'<div style="text-align:right;font-size:13px;color:#222;'
            f'margin-top:4px;padding-right:2px;">'
            f'Page {pn + 1} of {total_pages}</div>'
        )

        body = '<tbody>'
        for ri, row in enumerate(pr):
            body += _emp_rows(row, sr_counter, row_idx=ri)
            sr_counter += 1
        if last and grand_row:
            body += _emp_rows(grand_row, "", is_grand=True, row_idx=0)
        body += '</tbody>'

        parts.append(
            f'{pb}{page_hdr}'
            f'<table>{_thead()}{body}</table>'
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
        "margin-right":  "6mm",
        "margin-bottom": "8mm",
        "margin-left":   "6mm",
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

    p = {}
    s, e = _date_range(filters)
    if not s:
        return None

    p.update(start_date=s, end_date=e)
    conds = [
        "ss.docstatus=1",
        "ss.start_date>=%(start_date)s",
        "ss.end_date<=%(end_date)s",
    ]
    co = _parse_list(filters.get("company"))
    if co:
        p["companies"] = tuple(co)
        conds.append("ss.company IN %(companies)s")

    em_filter = _parse_list(filters.get("employee"))
    if em_filter:
        p["employees"] = tuple(em_filter)
        conds.append("ss.employee IN %(employees)s")

    cat  = filters.get("category")
    catj = ""
    if cat:
        p["category"] = cat
        catj = "INNER JOIN `tabCompany Link` cl_cat ON cl_cat.name=ss.employee AND cl_cat.category=%(category)s"

    divs = _parse_list(filters.get("division"))
    if divs:
        p["divisions"] = tuple(divs)
        conds.append(
            "ss.employee IN (SELECT name FROM `tabCompany Link` "
            "WHERE division IN %(divisions)s OR department IN %(divisions)s)"
        )

    w = " AND ".join(conds)

    earn_comps, emp_ded_comps, empr_comps = _get_components(w, p)
    cols, data = _get_data(filters)

    co_label = _company_label(filters)
    mo       = filters.get("month", "")
    yr       = filters.get("year",  "")
    html     = _build_html(cols, data, co_label, mo, yr, earn_comps, emp_ded_comps, empr_comps)
    return _save_pdf(html, "Transaction_Checklist")