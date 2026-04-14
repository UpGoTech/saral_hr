import frappe
import json
from frappe import _
from frappe.utils import flt
from frappe.utils.pdf import get_pdf

MONTH_MAP = {
    "January":1,"February":2,"March":3,"April":4,"May":5,"June":6,
    "July":7,"August":8,"September":9,"October":10,"November":11,"December":12,
}

_NUMERIC_FT = ("Float", "Currency", "Int", "Percent")

B = "1px solid #000"

ROWS_FIRST_PAGE = 21
ROWS_OTHER_PAGE = 25

_CSS = """<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Arial,sans-serif;font-size:10px;color:#000;background:#fff}

/* ── Page-1 header ── */
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

/* ── Page footer ── */
.pg-foot{text-align:right;font-size:8.5px;color:#555;margin-top:2px;}

/* ── Signatures ── */
.sig{display:flex;justify-content:space-between;width:100%;margin-top:18px;padding-top:6px;}
.sig-b{text-align:center;width:170px}
.sig-l{border-top:1px solid #000;margin-bottom:3px}
.sig-t{font-size:10px;color:#333}
.sig-d{font-size:9px;color:#555;margin-top:5px}
</style>"""


def _parse_list(v):
    if not v: return []
    if isinstance(v, list): return v
    try: return json.loads(v)
    except: return [v]

def _start_date(f):
    m = MONTH_MAP.get(f.get("month"))
    y = f.get("year")
    return "{y}-{m:02d}-01".format(y=y, m=m) if m and y else None

def _company_label(f):
    c = _parse_list(f.get("company"))
    return ", ".join(c) if c else (frappe.defaults.get_global_default("company") or "")

def _fmt(v):
    if v is None or v == "": return ""
    try: return "{:,.2f}".format(float(v))
    except (TypeError, ValueError): return str(v)

def _sig_html():
    labels = ["Prepared By", "Checked By", "Authorised Signatory"]
    blocks = "".join(
        '<div class="sig-b"><div class="sig-l"></div>'
        '<div class="sig-t">{l}</div>'
        '<div class="sig-d">Date: ___________</div></div>'.format(l=l)
        for l in labels
    )
    return '<div class="sig">{}</div>'.format(blocks)


# ---------------------------------------------------------------------------
# Columns definition (single source of truth)
# ---------------------------------------------------------------------------

def get_columns():
    return [
        {"label": _("Sr"),            "fieldname": "sr_no",        "fieldtype": "Int",   "width": 60},
        {"label": _("Employee ID"),   "fieldname": "employee",     "fieldtype": "Data",  "width": 200},
        {"label": _("Employee Name"), "fieldname": "employee_name","fieldtype": "Data",  "width": 300},
        {"label": _("Income Tax"),    "fieldname": "income_tax",   "fieldtype": "Float", "width": 200},
    ]


# ---------------------------------------------------------------------------
# execute — Frappe report entry-point
# ---------------------------------------------------------------------------

def execute(filters=None):
    filters    = filters or {}
    columns    = get_columns()
    companies  = _parse_list(filters.get("company"))
    employees  = _parse_list(filters.get("employee"))
    start_date = _start_date(filters)

    conditions = ["ss.docstatus = 1"]
    params     = {}

    if start_date:
        conditions.append("ss.start_date = %(start_date)s")
        params["start_date"] = start_date
    if companies:
        conditions.append("ss.company IN %(companies)s")
        params["companies"] = tuple(companies)
    if employees:
        conditions.append("ss.employee IN %(employees)s")
        params["employees"] = tuple(employees)

    cond  = " AND ".join(conditions)
    slips = frappe.db.sql(
        "SELECT ss.name, ss.employee, ss.employee_name, ss.net_salary"
        " FROM `tabSalary Slip` ss WHERE {cond}".format(cond=cond),
        params, as_dict=1
    )

    # Always return columns; data may be empty (blank table still prints)
    if not slips:
        return columns, []

    slip_names = tuple(s.name for s in slips if s.name)
    if not slip_names:
        return columns, []

    tax_data = frappe.db.sql(
        "SELECT parent, SUM(amount) as tax"
        " FROM `tabSalary Details`"
        " WHERE parent IN %(slips)s"
        "   AND parentfield = 'deductions'"
        "   AND LOWER(salary_component) LIKE '%%income tax%%'"
        " GROUP BY parent",
        {"slips": slip_names}, as_dict=1
    )

    tax_map   = {t.parent: flt(t.tax) for t in tax_data}
    total_tax = 0.0
    sr        = 0
    data      = []

    for s in slips:
        tax = flt(tax_map.get(s.name, 0))
        if tax <= 0:
            continue
        sr        += 1
        total_tax += tax
        data.append({
            "sr_no":         sr,
            "employee":      s.employee,
            "employee_name": s.employee_name,
            "income_tax":    tax,
        })

    if data:
        data.append({
            "sr_no":         "",
            "employee":      "",
            "employee_name": "Total",
            "income_tax":    total_tax,
            "bold":          1,
        })

    return columns, data


# ---------------------------------------------------------------------------
# _build_html — manual pagination with continuation header
# ---------------------------------------------------------------------------

def _build_html(cols, data, co, mo, yr):
    # ── colgroup ──────────────────────────────────────────────────────────
    col_pct = {
        "sr_no":         "6%",
        "employee":      "18%",
        "employee_name": "56%",
        "income_tax":    "20%",
    }
    cg = "<colgroup>" + "".join(
        '<col style="width:{w};"/>'.format(w=col_pct.get(c["fieldname"], "15%"))
        for c in cols
    ) + "</colgroup>"

    period = (
        "For the Month of {mo} {yr}".format(mo=mo, yr=yr) if mo and yr
        else ("For the Year {yr}".format(yr=yr) if yr else "All Records")
    )

    # ── page-1 header ─────────────────────────────────────────────────────
    page1_hdr = (
        '<div class="hdr">'
        '<div class="co">{co}</div>'
        '<div class="ttl">Income Tax Register</div>'
        '<div class="per">{period}</div>'
        '</div>'
    ).format(co=co, period=period)

    # ── continuation header ───────────────────────────────────────────────
    cont_hdr = (
        '<div class="cont-hdr">'
        '{co} &mdash; Income Tax Register &mdash; {period} (contd.)'
        '</div>'
    ).format(co=co, period=period)

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
            is_n = c.get("fieldtype", "") in _NUMERIC_FT

            if fn == "sr_no":
                html += (
                    '<td style="border:{B};text-align:center;background:{bg};'
                    'font-size:9px;color:#555;{fw}">{v}</td>'
                ).format(B=B, bg=bg, fw=fw, v="" if val == "" else val)
            elif is_n:
                html += (
                    '<td style="border:{B};text-align:right;background:{bg};{fw}">'
                    '{v}</td>'
                ).format(B=B, bg=bg, fw=fw, v=_fmt(val) if val not in ("", None) else "")
            else:
                html += (
                    '<td style="border:{B};text-align:left;background:{bg};{fw}">'
                    '{v}</td>'
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

    # ── paginate ──────────────────────────────────────────────────────────
    emp_rows = [r for r in data if not r.get("bold")]
    tot_rows = [r for r in data if r.get("bold")]
    has_data = bool(emp_rows)

    if not has_data:
        pages = [[]]
    else:
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
            # Show full table with headers + "No data" message — same as loan register
            tbl = (
                '<table class="data-tbl">{cg}<thead>{hdr}</thead>'
                '<tbody><tr><td colspan="{nc}" class="nd">'
                'No data for this period.</td></tr></tbody></table>'
            ).format(cg=cg, hdr=header_tr, nc=len(cols))
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

def _save_pdf(html):
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
    fn  = "Income_Tax_Report_{ts}.pdf".format(ts=ts)
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
    cols, data = execute(filters)
    co = _company_label(filters)
    mo = filters.get("month", "")
    yr = filters.get("year", "")
    html = _build_html(cols, data, co, mo, yr)
    return _save_pdf(html)