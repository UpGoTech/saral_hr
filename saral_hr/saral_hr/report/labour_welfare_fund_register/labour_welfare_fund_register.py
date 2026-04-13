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

# ── Rows per page (same conservative strategy as Monthly Attendance Report) ──
# Page 1 : title (~18mm) + table header (~6mm) → ~176mm usable → ~28 rows @5.5mm
# Page 2+: cont-hdr (~8mm) + table header (~6mm) → ~186mm usable → ~32 rows
ROWS_FIRST_PAGE = 28
ROWS_OTHER_PAGE = 32

_CSS = """<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Arial,sans-serif;font-size:10px;color:#000;background:#fff}

/* ── Page-1 header (matches Monthly Attendance Report) ── */
.hdr{text-align:center;border-bottom:2px solid #000;padding:6px 6px 5px;margin-bottom:4px;}
.hdr .co{font-size:18px;font-weight:900;letter-spacing:1px;text-transform:uppercase}
.hdr .ttl{font-size:13px;font-weight:700;margin-top:2px}
.hdr .per{font-size:11px;margin-top:2px}

/* ── Continuation header (matches Monthly Attendance Report) ── */
.cont-hdr{
    text-align:center;font-size:9px;color:#555;
    margin-bottom:3px;border-bottom:1px solid #000;padding-bottom:2px;
}

/* ── Data table ── */
table.data-tbl{width:100%;border-collapse:collapse;table-layout:fixed;}
table.data-tbl th{
    border:1px solid #000;padding:4px 6px;font-size:10px;font-weight:700;
    background:#f0f0f0;color:#000;white-space:nowrap;
    text-align:center;vertical-align:middle;
}
table.data-tbl td{
    border:1px solid #000;padding:4px 6px;font-size:10px;vertical-align:middle;
}
tr.tot td{background:#e8e8e8;font-weight:700;}

.nd{text-align:center;padding:14px;color:#888;font-size:10px}

/* ── Page footer ── */
.pg-foot{text-align:right;font-size:8.5px;color:#555;margin-top:2px;}

/* ── Signatures ── */
.sig{display:flex;justify-content:space-between;width:100%;margin-top:18px;padding-top:6px;}
.sig-b{text-align:center;width:170px}
.sig-l{border-top:1px solid #000;margin-bottom:3px}
.sig-t{font-size:10px;color:#333}
.sig-d{font-size:9px;color:#555;margin-top:5px}
</style>"""

_NUMERIC_FT = ("Float", "Currency", "Int", "Percent")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _sig_html():
    labels = ["Prepared By", "Checked By", "Authorised Signatory"]
    blocks = "".join(
        '<div class="sig-b">'
        '<div class="sig-l"></div>'
        '<div class="sig-t">{l}</div>'
        '<div class="sig-d">Date: ___________</div>'
        '</div>'.format(l=l)
        for l in labels
    )
    return '<div class="sig">{}</div>'.format(blocks)


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
    return "{y}-{m:02d}-01".format(y=y, m=m) if m and y else None

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
    return (" AND ss.employee IN "
            "(SELECT name FROM `tabCompany Link` "
            " WHERE division IN %(divisions)s OR department IN %(divisions)s)")

def _company_label(f):
    c = _parse_list(f.get("company"))
    return ", ".join(c) if c else (frappe.defaults.get_global_default("company") or "")

def _fmt(v):
    if v is None or v == "": return ""
    try: return "{:,.2f}".format(float(v))
    except (TypeError, ValueError): return str(v)


# ─────────────────────────────────────────────────────────────────────────────
# Data
# ─────────────────────────────────────────────────────────────────────────────

def _get_data(f):
    cols = [
        _col("Sr",            "sr_no",         "Int",   55),
        _col("Employee ID",   "employee_id",   "Data", 190),
        _col("Employee Name", "employee_name", "Data", 280),
        _col("Net Salary",    "net_salary",    "Float", 150, precision=2),
        _col("Emp LWF",       "emp_lwf",       "Float", 180, precision=2),
        _col("Empr LWF",      "empr_lwf",      "Float", 170, precision=2),
        _col("Total LWF",     "total_lwf",     "Float", 170, precision=2),
    ]

    if not f.get("company"):
        return cols, []

    p = {}
    cond = _base_cond(f, p)
    catj = _cat_join(f, p)
    divc = _div_cond(f, p)

    slips = frappe.db.sql(
        "SELECT ss.name AS slip, ss.employee, ss.employee_name,"
        "       ss.net_salary, cl.employee AS eid"
        " FROM `tabSalary Slip` ss"
        " LEFT JOIN `tabCompany Link` cl ON cl.name=ss.employee"
        " {catj}"
        " WHERE {cond}{divc}"
        " ORDER BY ss.employee_name".format(catj=catj, cond=cond, divc=divc),
        p, as_dict=1
    )
    if not slips: return cols, []

    sn = tuple(s.slip for s in slips)

    def _lm(pf):
        m = {}
        for r in frappe.db.sql(
            "SELECT sd.parent AS slip, SUM(sd.amount) AS a"
            " FROM `tabSalary Details` sd"
            " WHERE sd.parent IN %(sn)s AND sd.parentfield=%(pf)s"
            " AND LOWER(sd.salary_component) LIKE '%%welfare%%' AND sd.amount>0"
            " GROUP BY sd.parent",
            {"sn": sn, "pf": pf}, as_dict=1
        ):
            m[r.slip] = flt(r.a)
        return m

    em  = _lm("deductions")
    erm = _lm("employer_share")

    data = []
    gn = gel = grl = 0.0
    sr = 0

    for s in slips:
        el  = flt(em.get(s.slip,  0))
        erl = flt(erm.get(s.slip, 0))
        tot = el + erl
        if tot <= 0: continue
        net = flt(s.net_salary, 2)
        gn += net; gel += el; grl += erl
        sr += 1
        data.append({
            "sr_no":         sr,
            "employee_id":   s.eid or s.employee,
            "employee_name": s.employee_name or "",
            "net_salary":    net,
            "emp_lwf":       flt(el,  2),
            "empr_lwf":      flt(erl, 2),
            "total_lwf":     flt(tot, 2),
        })

    if data:
        data.append({
            "sr_no":         "",
            "employee_id":   "",
            "employee_name": "Total",
            "net_salary":    flt(gn,  2),
            "emp_lwf":       flt(gel, 2),
            "empr_lwf":      flt(grl, 2),
            "total_lwf":     flt(gel + grl, 2),
            "bold":          1,
        })

    return cols, data


def execute(filters=None):
    return _get_data(filters or {})


# ─────────────────────────────────────────────────────────────────────────────
# HTML builder — manual pagination identical strategy to Monthly Attendance
# Each page = its own <table> with a fresh <thead>.
# No employee row ever splits across pages.
# ─────────────────────────────────────────────────────────────────────────────

def _build_html(cols, data, co, mo, yr):

    # ── colgroup ──────────────────────────────────────────────────────────
    col_pct = {
        "sr_no":         "5%",
        "employee_id":   "14%",
        "employee_name": "27%",
        "net_salary":    "14%",
        "emp_lwf":       "13%",
        "empr_lwf":      "13%",
        "total_lwf":     "14%",
    }
    cg = "<colgroup>" + "".join(
        '<col style="width:{w};"/>'.format(w=col_pct.get(c["fieldname"], "13%"))
        for c in cols
    ) + "</colgroup>"

    # ── page-1 header ─────────────────────────────────────────────────────
    page1_hdr = (
        '<div class="hdr">'
        '<div class="co">{co}</div>'
        '<div class="ttl">Labour Welfare Fund Register</div>'
        '<div class="per">For the Month of {mo} {yr}</div>'
        '</div>'
    ).format(co=co, mo=mo, yr=yr)

    # ── continuation header ───────────────────────────────────────────────
    cont_hdr = (
        '<div class="cont-hdr">'
        '{co} &mdash; Labour Welfare Fund Register &mdash; {mo} {yr} (contd.)'
        '</div>'
    ).format(co=co, mo=mo, yr=yr)

    # ── column header row ─────────────────────────────────────────────────
    TH = ("border:{B};padding:4px 6px;font-size:10px;font-weight:700;"
          "background:#f0f0f0;text-align:center;vertical-align:middle;").format(B=B)
    header_tr = (
        "<tr>"
        + "".join('<th style="{th}">{lbl}</th>'.format(th=TH, lbl=c["label"]) for c in cols)
        + "</tr>"
    )

    # ── single employee row ───────────────────────────────────────────────
    def _row_html(row, idx):
        is_tot = bool(row.get("bold"))
        bg     = "#e8e8e8" if is_tot else ("#f9f9f9" if idx % 2 else "#ffffff")
        fw     = "font-weight:700;" if is_tot else ""
        html   = "<tr>"
        for c in cols:
            fn  = c["fieldname"]
            val = row.get(fn, "")
            ft  = c.get("fieldtype", "")

            if fn == "sr_no":
                html += (
                    '<td style="border:{B};text-align:center;background:{bg};'
                    'font-size:9px;color:#555;{fw}">{v}</td>'
                ).format(B=B, bg=bg, fw=fw, v="" if val == "" else val)

            elif fn in ("employee_name", "employee_id"):
                html += (
                    '<td style="border:{B};text-align:left;background:{bg};{fw}">{v}</td>'
                ).format(B=B, bg=bg, fw=fw, v=val or "")

            elif ft in _NUMERIC_FT:
                html += (
                    '<td style="border:{B};text-align:right;background:{bg};{fw}">{v}</td>'
                ).format(B=B, bg=bg, fw=fw,
                         v=_fmt(val) if val not in ("", None) else "")
            else:
                html += (
                    '<td style="border:{B};text-align:left;background:{bg};{fw}">{v}</td>'
                ).format(B=B, bg=bg, fw=fw, v=val or "")
        html += "</tr>"
        return html

    # ── page table ────────────────────────────────────────────────────────
    def _page_table(rows, start_idx):
        tbody = "<tbody>" + "".join(
            _row_html(row, start_idx + j) for j, row in enumerate(rows)
        ) + "</tbody>"
        return (
            '<table class="data-tbl">{cg}<thead>{hdr}</thead>{tbody}</table>'
        ).format(cg=cg, hdr=header_tr, tbody=tbody)

    # ── paginate — employee rows only; total row always appended to last page ──
    emp_rows = [r for r in data if not r.get("bold")]
    tot_rows = [r for r in data if r.get("bold")]

    if not emp_rows:
        pages    = [[]]
        has_data = False
    else:
        has_data = True
        pages, idx, first = [], 0, True
        while idx < len(emp_rows):
            lim = ROWS_FIRST_PAGE if first else ROWS_OTHER_PAGE
            pages.append(emp_rows[idx: idx + lim])
            idx  += lim
            first = False
        if tot_rows:
            pages[-1] = pages[-1] + tot_rows   # total row on last page only

    total_pages = len(pages)
    parts       = []
    row_counter = 0

    for pn, page_rows in enumerate(pages):
        pb      = '<div style="page-break-before:always;"></div>' if pn > 0 else ""
        is_last = (pn == total_pages - 1)
        page_hdr = page1_hdr if pn == 0 else cont_hdr

        if not has_data:
            nc  = len(cols)
            tbl = (
                '<table class="data-tbl">{cg}<thead>{hdr}</thead>'
                '<tbody><tr><td colspan="{nc}" class="nd">'
                'No data for this period</td></tr></tbody></table>'
            ).format(cg=cg, hdr=header_tr, nc=nc)
        else:
            tbl = _page_table(page_rows, row_counter)
            row_counter += len([r for r in page_rows if not r.get("bold")])

        pg_foot = '<div class="pg-foot">Page {p} of {t}</div>'.format(
            p=pn + 1, t=total_pages)
        sig = _sig_html() if is_last else ""

        parts.append(
            "{pb}{hdr}{tbl}{foot}{sig}".format(
                pb=pb, hdr=page_hdr, tbl=tbl, foot=pg_foot, sig=sig)
        )

    return (
        '<!DOCTYPE html><html><head><meta charset="UTF-8">{css}</head>'
        '<body>{body}</body></html>'
    ).format(css=_CSS, body="".join(parts))


# ─────────────────────────────────────────────────────────────────────────────
# PDF save
# ─────────────────────────────────────────────────────────────────────────────

def _save_pdf(html, prefix):
    pdf = get_pdf(html, options={
        "page-size":     "A4",
        "orientation":   "Landscape",
        "margin-top":    "7mm",
        "margin-right":  "6mm",
        "margin-bottom": "9mm",
        "margin-left":   "6mm",
        "encoding":      "UTF-8",
        "no-outline":    None,
    })
    ts = frappe.utils.now_datetime().strftime("%Y%m%d_%H%M%S")
    fn = "{prefix}_{ts}.pdf".format(prefix=prefix, ts=ts)
    with open(frappe.utils.get_files_path(fn, is_private=0), "wb") as fh:
        fh.write(pdf)
    doc = frappe.get_doc({
        "doctype":   "File",
        "file_name": fn,
        "is_private": 0,
        "file_url":  "/files/{fn}".format(fn=fn),
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return doc.file_url


@frappe.whitelist()
def print_report(filters):
    if isinstance(filters, str):
        filters = json.loads(filters)
    cols, data = _get_data(filters)
    return _save_pdf(
        _build_html(
            cols, data,
            _company_label(filters),
            filters.get("month", ""),
            filters.get("year", ""),
        ),
        "Labour_Welfare_Fund_Register",
    )