import frappe
import json
import calendar

from frappe import _
from frappe.utils import flt
from frappe.utils.pdf import get_pdf

MONTH_MAP = {
    "January": 1, "February": 2, "March": 3, "April": 4,
    "May": 5, "June": 6, "July": 7, "August": 8,
    "September": 9, "October": 10, "November": 11, "December": 12,
}

B = "1px solid #000"

ROWS_FIRST_PAGE = 20
ROWS_OTHER_PAGE = 24

_CSS = """<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Arial,sans-serif;font-size:10px;color:#000;background:#fff}
.hdr{text-align:center;border-bottom:2px solid #000;padding:6px 6px 5px;margin-bottom:4px;}
.hdr .co{font-size:18px;font-weight:900;letter-spacing:1px;text-transform:uppercase}
.hdr .ttl{font-size:13px;font-weight:700;margin-top:2px}
.hdr .per{font-size:11px;margin-top:2px}
.cont-hdr{text-align:center;font-size:9px;color:#555;margin-bottom:3px;border-bottom:1px solid #000;padding-bottom:2px;}
table.data-tbl{width:100%;border-collapse:collapse;table-layout:fixed;}
table.data-tbl th{border:1px solid #000;padding:4px 6px;font-size:10px;font-weight:700;background:#f0f0f0;color:#000;white-space:nowrap;text-align:center;vertical-align:middle;}
table.data-tbl td{border:1px solid #000;padding:4px 6px;font-size:10px;vertical-align:middle;}
tr.tot td{background:#e8e8e8;font-weight:700;}
.nd{text-align:center;padding:14px;color:#888;font-size:10px}
.pg-foot{text-align:right;font-size:8.5px;color:#555;margin-top:2px;}
.sig{display:flex;justify-content:space-between;width:100%;margin-top:18px;padding-top:6px;}
.sig-b{text-align:center;width:170px}
.sig-l{border-top:1px solid #000;margin-bottom:3px}
.sig-t{font-size:10px;color:#333}
.sig-d{font-size:9px;color:#555;margin-top:5px}
</style>"""

_NUMERIC_FT    = ("Float", "Currency", "Int", "Percent")
_SKIP_ON_TOTAL = {"pt_type"}


def _sig_html():
    labels = ["Prepared By", "Checked By", "Authorised Signatory"]
    blocks = "".join(
        '<div class="sig-b"><div class="sig-l"></div>'
        '<div class="sig-t">{l}</div>'
        '<div class="sig-d">Date: ___________</div></div>'.format(l=l)
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

def _base_cond(f, p, alias="ss"):
    c = ["{alias}.docstatus=1".format(alias=alias)]
    sd = _start_date(f)
    if sd: p["start_date"] = sd; c.append("{alias}.start_date=%(start_date)s".format(alias=alias))
    co = _parse_list(f.get("company"))
    if co: p["companies"] = tuple(co); c.append("{alias}.company IN %(companies)s".format(alias=alias))
    em = _parse_list(f.get("employee"))
    if em: p["employees"] = tuple(em); c.append("{alias}.employee IN %(employees)s".format(alias=alias))
    return " AND ".join(c)

def _cat_join(f, p, ec="ss.employee"):
    cat = f.get("category")
    if not cat: return ""
    p["category"] = cat
    return "INNER JOIN `tabCompany Link` cl_cat ON cl_cat.name={ec} AND cl_cat.category=%(category)s".format(ec=ec)

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
    try: return "{:,.2f}".format(float(v))
    except (TypeError, ValueError): return str(v)


def _get_data(f):
    cols = [
        _col("Sr",             "sr_no",        "Int",   55),
        _col("Employee ID",    "employee_id",  "Data", 230),
        _col("Employee Name",  "employee_name","Data", 260),
        _col("PT Type",        "pt_type",      "Data", 190),
        _col("Gross Salary",   "gross_salary", "Float", 250, precision=2),
        _col("PT Amount (Rs.)","pt_amount",    "Float", 200, precision=2),
    ]

    if not f.get("company"):
        return cols, []

    p = {}
    cond = _base_cond(f, p)
    catj = _cat_join(f, p)
    divc = _div_cond(f, p)

    slips = frappe.db.sql(
        "SELECT ss.name AS slip, ss.employee, ss.employee_name,"
        "       ss.total_earnings AS gross_salary"
        " FROM `tabSalary Slip` ss {catj}"
        " WHERE {cond}{divc}"
        " ORDER BY ss.employee_name".format(catj=catj, cond=cond, divc=divc),
        p, as_dict=1
    )

    if not slips:
        return cols, []

    sn = tuple(s.slip for s in slips)

    pm = {}
    for r in frappe.db.sql(
        "SELECT sd.parent AS slip, SUM(sd.amount) AS a"
        " FROM `tabSalary Details` sd"
        " WHERE sd.parent IN %(sn)s"
        "   AND sd.parentfield='deductions'"
        "   AND LOWER(sd.salary_component) LIKE '%%professional%%'"
        "   AND sd.amount > 0"
        " GROUP BY sd.parent",
        {"sn": sn}, as_dict=1
    ):
        pm[r.slip] = flt(r.a)

    sd_date = p.get("start_date", "")
    eids = list({s.employee for s in slips})
    pt_type_map = {}
    if eids and sd_date:
        for r in frappe.db.sql(
            "SELECT ssa.employee, ssa.pf_applicable"
            " FROM `tabSalary Structure Assignment` ssa"
            " WHERE ssa.employee IN %(eids)s"
            "   AND ssa.docstatus=1"
            "   AND ssa.from_date <= %(sd)s"
            "   AND (ssa.to_date IS NULL OR ssa.to_date >= %(sd)s)"
            " ORDER BY ssa.from_date DESC",
            {"eids": tuple(eids), "sd": sd_date}, as_dict=1
        ):
            if r.employee not in pt_type_map:
                pt_type_map[r.employee] = r.pf_applicable or ""

    data = []
    gg = gp = 0.0
    sr = 0

    for s in slips:
        pt = flt(pm.get(s.slip, 0))
        if pt <= 0:
            continue
        sr += 1
        gross   = flt(s.gross_salary, 2)
        pt_type = pt_type_map.get(s.employee, "")
        gg += gross
        gp += pt
        data.append({
            "sr_no":         sr,
            "employee_id":   s.employee,
            "employee_name": s.employee_name,
            "pt_type":       pt_type,
            "gross_salary":  gross,
            "pt_amount":     flt(pt, 2),
        })

    if data:
        data.append({
            "sr_no":         "",
            "employee_id":   "",
            "employee_name": "Total",
            "pt_type":       "",
            "gross_salary":  flt(gg, 2),
            "pt_amount":     flt(gp, 2),
            "bold":          1,
        })

    return cols, data


def execute(filters=None):
    return _get_data(filters or {})


def _build_html(cols, data, co, mo, yr):
    col_pct = {
        "sr_no":         "4%",
        "employee_id":   "17%",
        "employee_name": "25%",
        "pt_type":       "16%",
        "gross_salary":  "19%",
        "pt_amount":     "19%",
    }
    cg = "<colgroup>" + "".join(
        '<col style="width:{w};"/>'.format(w=col_pct.get(c["fieldname"], "15%"))
        for c in cols
    ) + "</colgroup>"

    page1_hdr = (
        '<div class="hdr"><div class="co">{co}</div>'
        '<div class="ttl">Professional Tax Register</div>'
        '<div class="per">For the Month of {mo} {yr}</div></div>'
    ).format(co=co, mo=mo, yr=yr)

    cont_hdr = (
        '<div class="cont-hdr">{co} &mdash; Professional Tax Register &mdash; {mo} {yr} (contd.)</div>'
    ).format(co=co, mo=mo, yr=yr)

    TH = "border:{B};padding:4px 6px;font-size:10px;font-weight:700;background:#f0f0f0;text-align:center;vertical-align:middle;".format(B=B)
    header_tr = "<tr>" + "".join(
        '<th style="{th}">{lbl}</th>'.format(th=TH, lbl=c["label"]) for c in cols
    ) + "</tr>"

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
                html += '<td style="border:{B};text-align:center;background:{bg};font-size:9px;color:#555;{fw}">{v}</td>'.format(B=B, bg=bg, fw=fw, v="" if val == "" else val)
            elif is_tot and fn in _SKIP_ON_TOTAL:
                html += '<td style="border:{B};background:{bg};"></td>'.format(B=B, bg=bg)
            elif ft in _NUMERIC_FT:
                html += '<td style="border:{B};text-align:right;background:{bg};{fw}">{v}</td>'.format(B=B, bg=bg, fw=fw, v=_fmt(val) if val not in ("", None) else "")
            else:
                html += '<td style="border:{B};text-align:left;background:{bg};{fw}">{v}</td>'.format(B=B, bg=bg, fw=fw, v=val or "")
        html += "</tr>"
        return html

    def _page_table(rows, start_idx):
        tbody = "<tbody>" + "".join(_row_html(row, start_idx + j) for j, row in enumerate(rows)) + "</tbody>"
        return '<table class="data-tbl">{cg}<thead>{hdr}</thead>{tbody}</table>'.format(cg=cg, hdr=header_tr, tbody=tbody)

    emp_rows = [r for r in data if not r.get("bold")]
    tot_rows = [r for r in data if r.get("bold")]

    if not emp_rows:
        pages, has_data = [[]], False
    else:
        has_data = True
        pages, idx, first = [], 0, True
        while idx < len(emp_rows):
            lim = ROWS_FIRST_PAGE if first else ROWS_OTHER_PAGE
            pages.append(emp_rows[idx: idx + lim])
            idx += lim; first = False
        if tot_rows:
            pages[-1] = pages[-1] + tot_rows

    total_pages = len(pages)
    parts, row_counter = [], 0

    for pn, page_rows in enumerate(pages):
        pb      = '<div style="page-break-before:always;"></div>' if pn > 0 else ""
        is_last = (pn == total_pages - 1)
        page_hdr = page1_hdr if pn == 0 else cont_hdr

        if not has_data:
            tbl = '<table class="data-tbl">{cg}<thead>{hdr}</thead><tbody><tr><td colspan="{n}" class="nd">No data for this period</td></tr></tbody></table>'.format(cg=cg, hdr=header_tr, n=len(cols))
        else:
            tbl = _page_table(page_rows, row_counter)
            row_counter += len([r for r in page_rows if not r.get("bold")])

        pg_foot = '<div class="pg-foot">Page {p} of {t}</div>'.format(p=pn + 1, t=total_pages)
        sig = _sig_html() if is_last else ""
        parts.append("{pb}{hdr}{tbl}{foot}{sig}".format(pb=pb, hdr=page_hdr, tbl=tbl, foot=pg_foot, sig=sig))

    return '<!DOCTYPE html><html><head><meta charset="UTF-8">{css}</head><body>{body}</body></html>'.format(css=_CSS, body="".join(parts))


def _save_pdf(html, prefix):
    pdf = get_pdf(html, options={"page-size":"A4","orientation":"Landscape","margin-top":"7mm","margin-right":"6mm","margin-bottom":"9mm","margin-left":"6mm","encoding":"UTF-8","no-outline":None})
    ts  = frappe.utils.now_datetime().strftime("%Y%m%d_%H%M%S")
    fn  = "{prefix}_{ts}.pdf".format(prefix=prefix, ts=ts)
    with open(frappe.utils.get_files_path(fn, is_private=0), "wb") as fh: fh.write(pdf)
    doc = frappe.get_doc({"doctype":"File","file_name":fn,"is_private":0,"file_url":"/files/{fn}".format(fn=fn)})
    doc.insert(ignore_permissions=True); frappe.db.commit()
    return doc.file_url


@frappe.whitelist()
def print_report(filters):
    if isinstance(filters, str): filters = json.loads(filters)
    cols, data = _get_data(filters)
    return _save_pdf(_build_html(cols, data, _company_label(filters), filters.get("month",""), filters.get("year","")), "Professional_Tax_Register")