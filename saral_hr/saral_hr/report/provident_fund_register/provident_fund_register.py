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

PF_EMP_COMP   = "Employee PF"
PF_EMPR_COMP  = "Employer PF"
PF_EPS_COMP   = "Employer EPS"
PF_EDLI_COMP  = "Employer EDLI"
PF_ADMIN_COMP = "Employer PF Admin Charges"

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

def _start_date(f):
    m = MONTH_MAP.get(f.get("month", ""))
    y = f.get("year", "")
    return f"{y}-{m:02d}-01" if m and y else None

def _base_cond(f, p):
    c  = ["ss.docstatus=1"]
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
    return (" AND ss.employee IN (SELECT name FROM `tabCompany Link` "
            "WHERE division IN %(divisions)s OR department IN %(divisions)s)")

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


# ---------------------------------------------------------------------------
# Core data function
# ---------------------------------------------------------------------------

def _get_data(f):
    # ── Column order: Employee ID → Employee Name → rest ──────────────────
    cols = [
        _col("Employee ID",   "employee_id",     w=180),   # <-- moved up
        _col("Employee Name", "employee_name",   w=200),   # <-- moved up
        _col("PF No.",        "pf_no",           w=180),
        _col("UAN No.",       "uan_no",          w=180),
        _col("Working Days",  "working_days",    "Float", 110, precision=1),
        _col("Payment Days",  "payment_days",    "Float", 110, precision=1),
        _col("Gross Salary",  "gross",           "Float", 110, precision=2),
        _col("Basic + DA",    "basic_da",        "Float", 110, precision=2),
        _col("Emp PF",        "emp_pf",          "Float", 110,  precision=2),
        _col("Empr. EPS",     "employer_eps",    "Float", 110,  precision=2),
        _col("Empr. PF",      "employer_pf",     "Float", 110,  precision=2),
        _col("Empr. EDLI",    "employer_edli",   "Float", 110,  precision=2),
        _col("PF Admin",      "employer_admin",  "Float", 110,  precision=2),
        _col("Total",         "total_amount",    "Float", 110,  precision=2),
        _col("DOJ",           "date_of_joining", "Date",  110),
        _col("DOB",           "date_of_birth",   "Date",  110),
    ]

    if not f.get("company"):
        return cols, []

    p    = {}
    cond = _base_cond(f, p)
    catj = _cat_join(f, p)
    divc = _div_cond(f, p)

    slips = frappe.db.sql(
        f"""
        SELECT ss.name AS slip_name, ss.employee AS eid, ss.employee_name,
               ss.total_working_days AS working_days, ss.payment_days,
               ss.total_earnings AS gross
        FROM `tabSalary Slip` ss {catj}
        WHERE {cond}{divc}
        ORDER BY ss.employee_name
        """,
        p, as_dict=1
    )
    if not slips:
        return cols, []

    sn   = tuple(s.slip_name for s in slips)
    eids = tuple(s.eid for s in slips)

    # Basic + DA
    bda = {
        r.slip_name: flt(r.v)
        for r in frappe.db.sql(
            """SELECT sd.parent AS slip_name, SUM(sd.amount) AS v
               FROM `tabSalary Details` sd
               WHERE sd.parent IN %(sn)s
                 AND sd.parenttype='Salary Slip'
                 AND sd.parentfield='earnings'
                 AND (LOWER(sd.salary_component) LIKE '%%basic%%'
                      OR LOWER(sd.salary_component) LIKE '%%dearness%%'
                      OR LOWER(sd.salary_component) LIKE '%% da'
                      OR sd.salary_component='DA')
               GROUP BY sd.parent""",
            {"sn": sn}, as_dict=1
        )
    }

    # Employee PF (deductions)
    ep = {
        r.slip_name: flt(r.v)
        for r in frappe.db.sql(
            """SELECT sd.parent AS slip_name, SUM(sd.amount) AS v
               FROM `tabSalary Details` sd
               WHERE sd.parent IN %(sn)s
                 AND sd.parenttype='Salary Slip'
                 AND sd.parentfield='deductions'
                 AND sd.salary_component=%(c)s
               GROUP BY sd.parent""",
            {"sn": sn, "c": PF_EMP_COMP}, as_dict=1
        )
    }

    def _fe(comp):
        return {
            r.slip_name: flt(r.v)
            for r in frappe.db.sql(
                """SELECT sd.parent AS slip_name, SUM(sd.amount) AS v
                   FROM `tabSalary Details` sd
                   WHERE sd.parent IN %(sn)s
                     AND sd.parenttype='Salary Slip'
                     AND sd.parentfield='employer_share'
                     AND sd.salary_component=%(c)s
                   GROUP BY sd.parent""",
                {"sn": sn, "c": comp}, as_dict=1
            )
        }

    erpf   = _fe(PF_EMPR_COMP)
    ereps  = _fe(PF_EPS_COMP)
    eredli = _fe(PF_EDLI_COMP)
    eradm  = _fe(PF_ADMIN_COMP)

    em = {
        r.name: r
        for r in frappe.db.sql(
            """SELECT e.name, e.employee_pf_account AS pf_no,
                      e.pf_uan_number AS uan_no, e.date_of_birth,
                      cl.date_of_joining
               FROM `tabEmployee` e
               LEFT JOIN `tabCompany Link` cl ON cl.name=e.name
               WHERE e.name IN %(ids)s""",
            {"ids": eids}, as_dict=1
        )
    }

    data       = []
    tot        = {k: 0.0 for k in [
        "gross","basic_da","emp_pf","employer_eps",
        "employer_pf","employer_edli","employer_admin","total_amount"
    ]}
    

    for s in slips:
        emp  = em.get(s.eid, frappe._dict())
        sn_  = s.slip_name
        g    = flt(s.gross,          2)
        b    = flt(bda.get(sn_, 0),  2)
        epf  = flt(ep.get(sn_,  0),  2)
        erp  = flt(erpf.get(sn_, 0), 2)
        ere  = flt(ereps.get(sn_, 0),2)
        erd  = flt(eredli.get(sn_,0),2)
        era  = flt(eradm.get(sn_,0), 2)
        tol  = flt(epf + erp + ere + erd + era, 2)

        for k, v in [("gross",g),("basic_da",b),("emp_pf",epf),
                     ("employer_eps",ere),("employer_pf",erp),
                     ("employer_edli",erd),("employer_admin",era),
                     ("total_amount",tol)]:
            tot[k] += v

        data.append({
            "employee_id":     s.eid,          # <-- kept same key, order changed via cols list
            "employee_name":   s.employee_name,
            "pf_no":           emp.get("pf_no")  or "",
            "uan_no":          emp.get("uan_no") or "",
            "working_days":    flt(s.working_days, 1),
            "payment_days":    flt(s.payment_days, 1),
            "gross":           g,
            "basic_da":        b,
            "emp_pf":          epf,
            "employer_eps":    ere,
            "employer_pf":     erp,
            "employer_edli":   erd,
            "employer_admin":  era,
            "total_amount":    tol,
            "date_of_joining": emp.get("date_of_joining") or "",
            "date_of_birth":   emp.get("date_of_birth")   or "",
            "_row_type":       "detail",
        })
    

    data.append({
        "employee_name": "Total",
        "employee_id": "",
        "pf_no": "",
        "uan_no": "",
        "working_days": None,
        "payment_days": None,
        **{k: flt(v, 2) for k, v in tot.items()},
        "date_of_joining": "",
        "date_of_birth": "",
        "bold": 1,
        "_row_type": "total",
    })

    return cols, data


# ---------------------------------------------------------------------------
# Frappe report entry-point
# ---------------------------------------------------------------------------

def execute(filters=None):
    return _get_data(filters or {})


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

_CSS = """<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Arial,sans-serif;font-size:13px;color:#000;background:#fff;width:100%;}
.hdr{text-align:center;border-bottom:2px solid #000;padding:10px 4px 8px;margin-bottom:8px}
.hdr .co{font-size:24px;font-weight:900;letter-spacing:1px;text-transform:uppercase}
.hdr .ttl{font-size:18px;font-weight:700;margin-top:5px}
.hdr .per{font-size:17px;margin-top:4px}
table{width:100%;border-collapse:collapse;table-layout:fixed;}
</style>"""

_SIG = """
<!--SIG_START-->
<div style="display:flex;justify-content:space-between;
            width:100%;margin-top:32px;padding-top:8px;
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

HDR_BG      = "#e8e8e8"
ROW_COLOURS = ["#ffffff", "#f0f0f0"]
PAD         = "padding:7px 9px;"
FS          = "font-size:13px;"


def _build_html(cols, data, co, mo, yr):
    # Company/title header
    hdr_html = (
        f'<div class="hdr">'
        f'<div class="co">{co}</div>'
        f'<div class="ttl">Provident Fund Register</div>'
        f'<div class="per">For the Month of {mo} {yr}</div>'
        f'</div>'
    )

    if not data:
        return (
            f'<!DOCTYPE html><html><head><meta charset="UTF-8">{_CSS}</head>'
            f'<body>{hdr_html}'
            f'<p style="text-align:center;{PAD}{FS}color:#888;">No data for this period</p>'
            f'{_SIG}</body></html>'
        )

    detail_rows = [r for r in data if r.get("_row_type") == "detail"]
    total_row   = next((r for r in data if r.get("bold")), None)

    TH  = (f"border:{B};{PAD}{FS}font-weight:700;background:{HDR_BG};"
           f"white-space:normal;vertical-align:middle;")
    THL = TH + "text-align:left;"
    THR = TH + "text-align:right;"

    # ── Column widths ──────────────────────────────────────────────────────
    W_EMP_ID = 100   # Employee ID
    W_NAME   = 160   # Employee Name
    W_PF     = 90    # PF No. / UAN No.
    W_DAYS   = 50
    W_GROSS  = 85
    W_BDA    = 85
    W_COMP   = 72
    W_DOJ    = 78

    # ── thead (repeats every page) ─────────────────────────────────────────
    # Column order in PDF: Sr | Emp ID | Emp Name | PF No/UAN | Days | Gross | Basic+DA | PF cols | DOJ/DOB
    def _thead():
        h  = '<thead><tr>'
        h += f'<th style="{THL}width:{W_EMP_ID}px;">Employee ID</th>'
        h += f'<th style="{THL}width:{W_NAME}px;">Employee Name</th>'
        h += f'<th style="{THL}width:{W_PF}px;">PF No.<br><span style="font-size:11px;font-weight:400;">UAN No.</span></th>'
        h += f'<th style="{THR}width:{W_DAYS}px;">Working<br>Days<br><span style="font-size:11px;font-weight:400;">Payment Days</span></th>'
        h += f'<th style="{THR}width:{W_GROSS}px;">Gross<br>Salary</th>'
        h += f'<th style="{THR}width:{W_BDA}px;">Basic<br>+ DA</th>'
        h += f'<th style="{THR}width:{W_COMP}px;">Emp<br>PF</th>'
        h += f'<th style="{THR}width:{W_COMP}px;">Empr<br>EPS</th>'
        h += f'<th style="{THR}width:{W_COMP}px;">Empr<br>PF</th>'
        h += f'<th style="{THR}width:{W_COMP}px;">Empr<br>EDLI</th>'
        h += f'<th style="{THR}width:{W_COMP}px;">PF<br>Admin</th>'
        h += f'<th style="{THR}width:{W_COMP}px;">Total</th>'
        h += f'<th style="{THL}width:{W_DOJ}px;">DOJ<br><span style="font-size:11px;font-weight:400;">DOB</span></th>'
        h += '</tr></thead>'
        return h

    # ── cell helper ────────────────────────────────────────────────────────
    def _td(val, align="right", bg="#fff", bold=False, bt=B, bb=B):
        fw = "font-weight:700;" if bold else ""
        return (
            f'<td style="border-left:{B};border-right:{B};'
            f'border-top:{bt};border-bottom:{bb};'
            f'{PAD}{FS}{fw}background:{bg};'
            f'text-align:{align};vertical-align:middle;">{val}</td>'
        )

    # ── 2 rows per employee ────────────────────────────────────────────────
    # Row 1: Employee ID | Employee Name | PF No  | Working Days | amounts... | DOJ
    # Row 2: (blank)     | (blank)       | UAN No | Payment Days | blanks...  | DOB
    def _emp_rows(row, row_idx, is_total=False):
        bg   = HDR_BG if is_total else ROW_COLOURS[row_idx % 2]
        bold = is_total
        fw   = "font-weight:700;" if bold else ""

        emp_id = row.get("employee_id",   "") or ""
        emp_nm = row.get("employee_name", "") or ""
        pf_no  = row.get("pf_no",   "") or ""
        uan_no = row.get("uan_no",  "") or ""

        wdays  = _fmt(row.get("working_days"))   or ""
        pdays  = _fmt(row.get("payment_days"))   or ""
        gross  = _fmt(row.get("gross"))          or "—"
        bda    = _fmt(row.get("basic_da"))       or "—"
        emp_pf = _fmt(row.get("emp_pf"))         or "—"
        ereps  = _fmt(row.get("employer_eps"))   or "—"
        erpf   = _fmt(row.get("employer_pf"))    or "—"
        eredli = _fmt(row.get("employer_edli"))  or "—"
        eradm  = _fmt(row.get("employer_admin")) or "—"
        total  = _fmt(row.get("total_amount"))   or "—"
        doj    = str(row.get("date_of_joining") or "")
        dob    = str(row.get("date_of_birth")   or "")

        # ── Row 1 ──────────────────────────────────────────────────────────
        r1  = '<tr>'
        # Employee ID (top)
        r1 += (
            f'<td style="border-left:{B};border-right:{B};border-top:{B};border-bottom:none;'
            f'{PAD}{FS}{fw}background:{bg};text-align:left;vertical-align:middle;">'
            f'<strong>{emp_id or "&nbsp;"}</strong></td>'
        )
        # Employee Name (top)
        r1 += (
            f'<td style="border-left:{B};border-right:{B};border-top:{B};border-bottom:none;'
            f'{PAD}{FS}{fw}background:{bg};text-align:left;vertical-align:middle;'
            f'white-space:normal;word-wrap:break-word;">'
            f'<strong>{emp_nm or "&nbsp;"}</strong></td>'
        )
        # PF No (top)
        r1 += (
            f'<td style="border-left:{B};border-right:{B};border-top:{B};border-bottom:none;'
            f'{PAD}{FS}{fw}background:{bg};text-align:left;vertical-align:middle;">'
            f'{pf_no or "&nbsp;"}</td>'
        )
        r1 += _td(wdays,  "right", bg, bold, bt=B,    bb="none")
        r1 += _td(gross,  "right", bg, bold, bt=B,    bb="none")
        r1 += _td(bda,    "right", bg, bold, bt=B,    bb="none")
        r1 += _td(emp_pf, "right", bg, bold, bt=B,    bb="none")
        r1 += _td(ereps,  "right", bg, bold, bt=B,    bb="none")
        r1 += _td(erpf,   "right", bg, bold, bt=B,    bb="none")
        r1 += _td(eredli, "right", bg, bold, bt=B,    bb="none")
        r1 += _td(eradm,  "right", bg, bold, bt=B,    bb="none")
        r1 += _td(total,  "right", bg, bold, bt=B,    bb="none")
        r1 += (
            f'<td style="border-left:{B};border-right:{B};border-top:{B};border-bottom:none;'
            f'{PAD}font-size:12px;{fw}background:{bg};text-align:left;vertical-align:middle;">'
            f'{doj or "&nbsp;"}</td>'
        )
        r1 += '</tr>'

        # ── Row 2 ──────────────────────────────────────────────────────────
        r2  = '<tr>'
        # Employee ID (bottom — blank)
        r2 += (
            f'<td style="border-left:{B};border-right:{B};border-top:none;border-bottom:{B};'
            f'{PAD}{FS}{fw}background:{bg};text-align:left;vertical-align:middle;">'
            f'&nbsp;</td>'
        )
        # Employee Name (bottom — blank)
        r2 += (
            f'<td style="border-left:{B};border-right:{B};border-top:none;border-bottom:{B};'
            f'{PAD}{FS}{fw}background:{bg};text-align:left;vertical-align:middle;">'
            f'&nbsp;</td>'
        )
        # UAN No (bottom)
        r2 += (
            f'<td style="border-left:{B};border-right:{B};border-top:none;border-bottom:{B};'
            f'{PAD}font-size:12px;{fw}background:{bg};text-align:left;vertical-align:middle;">'
            f'{uan_no or "&nbsp;"}</td>'
        )
        # Payment days (blank on total row)
        pdays_disp = pdays if not is_total else "&nbsp;"
        r2 += _td(pdays_disp, "right", bg, bold, bt="none", bb=B)
        # Blank numeric cells on row 2
        for _ in range(8):
            r2 += _td("&nbsp;", "right", bg, False, bt="none", bb=B)
        r2 += (
            f'<td style="border-left:{B};border-right:{B};border-top:none;border-bottom:{B};'
            f'{PAD}font-size:12px;{fw}background:{bg};text-align:left;vertical-align:middle;">'
            f'{dob or "&nbsp;"}</td>'
        )
        r2 += '</tr>'

        return r1 + r2

    # ── Pagination ─────────────────────────────────────────────────────────
    FIRST, OTHER = 14, 20
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

        page_hdr = hdr_html if pn == 0 else ""

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
            f'{pb}{page_hdr}'
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
    return _save_pdf(html, "Provident_Fund_Register")