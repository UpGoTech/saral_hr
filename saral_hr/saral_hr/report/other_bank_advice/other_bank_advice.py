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

# ── Rows per page (same conservative strategy as MAR / LWF / Bank Advice) ──
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

/* ── Continuation header ── */
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
.hold{color:#c0392b;font-style:italic}

/* ── Page footer ── */
.pg-foot{text-align:right;font-size:8.5px;color:#555;margin-top:2px;}

/* ── Signatures ── */
.sig{display:flex;justify-content:space-between;width:100%;margin-top:18px;padding-top:6px;}
.sig-b{text-align:center;width:170px}
.sig-l{border-top:1px solid #000;margin-bottom:3px}
.sig-t{font-size:10px;color:#333}
.sig-d{font-size:9px;color:#555;margin-top:5px}
</style>"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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

def _date_range(f):
    m = MONTH_MAP.get(f.get("month", ""))
    y = int(f.get("year", 0) or 0)
    if not m or not y:
        return None, None
    return (
        "{y}-{m:02d}-01".format(y=y, m=m),
        "{y}-{m:02d}-{d:02d}".format(y=y, m=m, d=calendar.monthrange(y, m)[1]),
    )

def _company_label(f):
    c = _parse_list(f.get("company"))
    return ", ".join(c) if c else (frappe.defaults.get_global_default("company") or "")

def _fmt(v):
    if v is None or v == "": return ""
    try: return "{:,.2f}".format(float(v))
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
        _col("Sr",             "sr_no",          "Int",   55),
        _col("Employee ID",    "employee_id",    "Data", 140),
        _col("Employee Name",  "employee_name",  "Data", 260),
        _col("IFSC Code",      "ifsc_code",      "Data", 190),
        _col("Account Number", "account_number", "Data", 260),
        _col("Net Salary",     "net_salary",     "Data", 120),
        _col("Bank Name",      "bank_name",      "Data", 180),
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
        "SELECT ss.employee, ss.employee_name, ss.company, ss.net_salary,"
        "       emp.bank_name, emp.account_number, emp.ifsc_code"
        " FROM `tabSalary Slip` ss"
        " INNER JOIN `tabCompany Link` cla ON cla.name=ss.employee AND cla.is_active=1"
        " LEFT JOIN `tabEmployee` emp ON emp.name=ss.employee"
        " {catj}"
        " WHERE {cond}{divc}"
        " ORDER BY ss.employee_name".format(catj=catj, cond=cond, divc=divc),
        p, as_dict=1
    )

    if not slips:
        return cols, []

    oh = _on_hold(f)
    hm = _bank_map(list({sl.company for sl in slips if sl.company}))

    data = []
    tot  = 0.0
    sr   = 0

    for sl in slips:
        eb = (sl.bank_name or "").strip().lower()
        hb = hm.get(sl.company, "")

        # Other bank: employee's bank does NOT match company's home bank
        is_home = hb and eb == hb
        if is_home:
            continue

        sr += 1
        if sl.employee in oh:
            data.append({
                "sr_no":          sr,
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
                "sr_no":          sr,
                "employee_id":    sl.employee,
                "employee_name":  sl.employee_name,
                "ifsc_code":      sl.ifsc_code      or "-",
                "account_number": sl.account_number or "-",
                "net_salary":     "{:,.2f}".format(n),
                "bank_name":      sl.bank_name      or "-",
            })

    if data:
        data.append({
            "sr_no":          "",
            "employee_id":    "",
            "employee_name":  "Total",
            "ifsc_code":      "",
            "account_number": "",
            "net_salary":     "{:,.2f}".format(flt(tot, 2)),
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
# HTML builder — manual pagination (same strategy as MAR / LWF / Bank Advice)
# Each page gets its own <table> with a fresh <thead>.
# No employee row is ever split across pages.
# ---------------------------------------------------------------------------

def _build_html(cols, data, co, mo, yr):

    # ── colgroup ──────────────────────────────────────────────────────────
    col_pct = {
        "sr_no":          "4%",
        "employee_id":    "11%",
        "employee_name":  "24%",
        "ifsc_code":      "16%",
        "account_number": "22%",
        "net_salary":     "11%",
        "bank_name":      "12%",
    }
    cg = "<colgroup>" + "".join(
        '<col style="width:{w};"/>'.format(w=col_pct.get(c["fieldname"], "12%"))
        for c in cols
    ) + "</colgroup>"

    # ── page-1 header ─────────────────────────────────────────────────────
    page1_hdr = (
        '<div class="hdr">'
        '<div class="co">{co}</div>'
        '<div class="ttl">Other Bank Advice</div>'
        '<div class="per">For the Month of {mo} {yr}</div>'
        '</div>'
    ).format(co=co, mo=mo, yr=yr)

    # ── continuation header ───────────────────────────────────────────────
    cont_hdr = (
        '<div class="cont-hdr">'
        '{co} &mdash; Other Bank Advice &mdash; {mo} {yr} (contd.)'
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

    # ── single data row ───────────────────────────────────────────────────
    def _row_html(row, idx):
        is_tot = bool(row.get("bold"))
        bg     = "#e8e8e8" if is_tot else ("#f9f9f9" if idx % 2 else "#ffffff")
        fw     = "font-weight:700;" if is_tot else ""
        html   = "<tr>"
        for c in cols:
            fn  = c["fieldname"]
            val = row.get(fn, "")

            if fn == "sr_no":
                html += (
                    '<td style="border:{B};text-align:center;background:{bg};'
                    'font-size:9px;color:#555;{fw}">{v}</td>'
                ).format(B=B, bg=bg, fw=fw, v="" if val == "" else val)

            elif fn == "net_salary" and val == "On Hold":
                html += (
                    '<td style="border:{B};background:{bg};text-align:right;'
                    'color:#c0392b;font-style:italic;">On Hold</td>'
                ).format(B=B, bg=bg)

            elif fn == "net_salary":
                html += (
                    '<td style="border:{B};text-align:right;background:{bg};{fw}">{v}</td>'
                ).format(B=B, bg=bg, fw=fw, v=val or "")

            elif fn in ("ifsc_code", "account_number"):
                html += (
                    '<td style="border:{B};text-align:left;background:{bg};'
                    'font-family:monospace;font-size:9px;{fw}">{v}</td>'
                ).format(B=B, bg=bg, fw=fw, v=val or "")

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

    # ── paginate — emp rows only; total row always on last page ──────────
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
            pages[-1] = pages[-1] + tot_rows

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


# ---------------------------------------------------------------------------
# PDF save
# ---------------------------------------------------------------------------

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
    ts  = frappe.utils.now_datetime().strftime("%Y%m%d_%H%M%S")
    fn  = "{prefix}_{ts}.pdf".format(prefix=prefix, ts=ts)
    with open(frappe.utils.get_files_path(fn, is_private=0), "wb") as fh:
        fh.write(pdf)
    doc = frappe.get_doc({
        "doctype":    "File",
        "file_name":  fn,
        "is_private": 0,
        "file_url":   "/files/{fn}".format(fn=fn),
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
            filters.get("year",  ""),
        ),
        "Other_Bank_Advice",
    )