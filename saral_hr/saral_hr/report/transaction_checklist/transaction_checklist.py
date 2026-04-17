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

ROWS_PER_PAGE = 8

_B  = "1px solid #000"
_BD = "1px dashed #aaa"

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
    return "{0}-{1:02d}-01".format(y, m), "{0}-{1:02d}-{2:02d}".format(y, m, calendar.monthrange(y, m)[1])

def _company_label(f):
    c = _parse_list(f.get("company"))
    return ", ".join(c) if c else (frappe.defaults.get_global_default("company") or "")

def _sanitize(s):
    return s.strip().lower().replace(" ", "_").replace("-", "_").replace("(", "").replace(")", "").replace("__","_")

def _fn(prefix, abbr):
    return "{0}_{1}".format(prefix, _sanitize(abbr))


# ---------------------------------------------------------------------------
# Fetch dynamic components
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
    earn_comps, emp_ded_comps, empr_comps = [], [], []
    seen = set()
    for r in rows:
        key = r["salary_component"]
        if key in seen: continue
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
    if not sn: return {}
    r = {}
    for x in frappe.db.sql(
        "SELECT sd.parent AS slip, sd.salary_component AS comp, sd.amount "
        "FROM `tabSalary Details` sd WHERE sd.parent IN %(sn)s",
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
        _col("Payment Days",  "payment_days",  "Float", 120, precision=2),
        _col("Absent Days",   "absent_days",   "Float", 120, precision=2),
        _col("LWP",           "total_lwp",     "Float", 120, precision=2),
    ]
    for name, abbr in earn_comps:
        cols.append(_col("{0} ({1})".format(name, abbr), _fn("e", abbr), "Float", 180, precision=2))
    cols.append(_col("Gross Earnings", "gross_earnings", "Float", 180, precision=2))
    for name, abbr in emp_ded_comps:
        cols.append(_col("{0} ({1})".format(name, abbr), _fn("d", abbr), "Float", 180, precision=2))
    cols.append(_col("Total Deductions", "total_deductions", "Float", 180, precision=2))
    for name, abbr in empr_comps:
        cols.append(_col("{0} ({1})".format(name, abbr), _fn("r", abbr), "Float", 180, precision=2))
    cols.append(_col("Employer Total", "employer_total", "Float", 180, precision=2))
    cols.append(_col("Net Salary", "net_salary", "Float", 180, precision=2))

    slips = frappe.db.sql(
        "SELECT ss.name AS slip, ss.employee, ss.employee_name,"
        "       ss.payment_days, ss.absent_days, ss.total_lwp, ss.net_salary"
        " FROM `tabSalary Slip` ss {catj}"
        " WHERE {w}"
        " ORDER BY ss.employee_name".format(catj=catj, w=w),
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
    for name, abbr in earn_comps:    grand[_fn("e", abbr)] = 0.0
    for name, abbr in emp_ded_comps: grand[_fn("d", abbr)] = 0.0
    for name, abbr in empr_comps:    grand[_fn("r", abbr)] = 0.0

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
            row[_fn("e", abbr)] = amt; ge += amt; grand[_fn("e", abbr)] += amt
        row["gross_earnings"] = flt(ge, 2); grand["gross_earnings"] += ge

        td = 0.0
        for name, abbr in emp_ded_comps:
            amt = flt(sc.get(name), 2)
            row[_fn("d", abbr)] = amt; td += amt; grand[_fn("d", abbr)] += amt
        row["total_deductions"] = flt(td, 2); grand["total_deductions"] += td

        et = 0.0
        for name, abbr in empr_comps:
            amt = flt(sc.get(name), 2)
            row[_fn("r", abbr)] = amt; et += amt; grand[_fn("r", abbr)] += amt
        row["employer_total"] = flt(et, 2); grand["employer_total"] += et

        grand["net_salary"]   += flt(sl["net_salary"], 2)
        grand["payment_days"] += flt(sl["payment_days"], 2)
        grand["absent_days"]  += flt(sl.get("absent_days") or 0, 2)
        grand["total_lwp"]    += flt(sl["total_lwp"] or 0, 2)
        data.append(row)

    if data:
        grand_row = {"employee": "", "employee_name": "Grand Total", "bold": 1}
        grand_row.update({k: flt(v, 2) for k, v in grand.items()})
        data.append(grand_row)

    return cols, data


def execute(filters=None):
    return _get_data(filters or {})


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

_CSS = """<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family: Arial, sans-serif; font-size: 10px; color: #000; background: #fff; width: 100%; }

.hdr {
    text-align: center;
    border-bottom: 1px solid #000;
    padding: 6px 4px 5px;
    margin-bottom: 6px;
}
.hdr .co  { font-size: 18px; font-weight: 900; letter-spacing: 1px; text-transform: uppercase; }
.hdr .ttl { font-size: 14px; font-weight: 700; margin-top: 3px; }
.hdr .per { font-size: 11px; margin-top: 2px; color: #333; }

.cont-hdr {
    text-align: center;
    font-size: 10px;
    color: #555;
    margin-bottom: 4px;
    border-bottom: 1px solid #000;
    padding-bottom: 3px;
}

table.main {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    table-layout: fixed;
}
table.main th, table.main td { vertical-align: middle; padding: 3px 4px; font-size: 10px; }
table.main th {
    background: #e0e0e0;
    font-weight: 700;
    text-align: center;
    border: 1px solid #000;
    white-space: normal;
    word-break: break-word;
}
th.h-sr  { width: 24px; text-align: center; }
th.h-emp { text-align: left; }
th.h-det { font-weight: 400; font-size: 9px; color: #444; text-align: left; border-left: none; }

/* ── Vertical chip layout ── */
.ck {
    display: block;
    font-weight: 700;
    font-size: 9px;
    color: #222;
    line-height: 1.3;
}
.cv {
    display: block;
    font-size: 10px;
    color: #444;
    line-height: 1.3;
}

/* Net-salary vertical chip */
.ns-hl-lbl {
    display: block;
    background: #1a1a2e;
    color: #aaa;
    border-radius: 3px 3px 0 0;
    padding: 1px 4px 0;
    font-size: 9px;
    font-weight: 700;
    text-align: center;
    white-space: normal;
    word-break: break-all;
}
.ns-hl-val {
    display: block;
    background: #1a1a2e;
    color: #fff;
    border-radius: 0 0 3px 3px;
    padding: 0 4px 1px;
    font-size: 10px;
    font-weight: 700;
    text-align: center;
    white-space: normal;
    word-break: break-all;
}

.legend {
    margin-top: 10px;
    padding: 6px 10px;
    border: 1px solid #bbb;
    background: #f9f9f9;
    font-size: 9px;
}
.legend-title { font-weight: 700; font-size: 9.5px; margin-bottom: 4px; }
.legend-body  { line-height: 1.7; }

.pg-foot { text-align: right; font-size: 9px; color: #555; margin-top: 3px; }
.sig { display: flex; justify-content: space-between; margin-top: 24px; }
.sig-box  { text-align: center; width: 160px; }
.sig-line { border-top: 1px solid #000; margin-bottom: 3px; }
.sig-lbl  { font-size: 10px; color: #333; }
</style>"""


# ---------------------------------------------------------------------------
# Cell style builders
# ---------------------------------------------------------------------------

def _sr_style(is_grand=False):
    bg = "background:#e8e8e8;" if is_grand else "background:#fff;"
    return (
        "text-align:center; vertical-align:middle; padding:4px 3px; "
        "font-size:9px; color:#444; {bg}"
        "border-top:{b}; border-bottom:{b}; border-left:{b}; border-right:{d};"
    ).format(bg=bg, b=_B, d=_BD)

def _emp_style(is_grand=False):
    bg = "background:#e8e8e8;" if is_grand else "background:#fff;"
    return (
        "vertical-align:top; padding:5px 6px; text-align:left; "
        "word-break:break-word; white-space:normal; {bg}"
        "border-top:{b}; border-bottom:{b}; border-left:none; border-right:{b};"
    ).format(bg=bg, b=_B)

def _chip_r1(is_last, is_grand=False):
    bg    = "background:#e8e8e8;" if is_grand else "background:#fff;"
    right = "border-right:{b};".format(b=_B) if is_last else "border-right:{d};".format(d=_BD)
    return (
        "white-space:normal; word-break:break-all; overflow:visible; "
        "padding:3px 4px; vertical-align:middle; {bg}"
        "border-top:{b}; border-bottom:{d}; border-left:{d}; {right}"
    ).format(bg=bg, b=_B, d=_BD, right=right)

def _chip_r2(is_last, is_grand=False):
    bg    = "background:#e8e8e8;" if is_grand else "background:#fff;"
    right = "border-right:{b};".format(b=_B) if is_last else "border-right:{d};".format(d=_BD)
    return (
        "white-space:normal; word-break:break-all; overflow:visible; "
        "padding:3px 4px; vertical-align:middle; {bg}"
        "border-top:none; border-bottom:{b}; border-left:{d}; {right}"
    ).format(bg=bg, b=_B, d=_BD, right=right)


# ---------------------------------------------------------------------------
# HTML builder
# ---------------------------------------------------------------------------

def _build_html(cols, data, co, mo, yr,
                earn_comps=None, emp_ded_comps=None, empr_comps=None):

    if earn_comps is None or emp_ded_comps is None or empr_comps is None:
        earn_comps, emp_ded_comps, empr_comps = [], [], []
        SKIP = {
            "employee","employee_name","payment_days","absent_days","total_lwp",
            "gross_earnings","total_deductions","employer_total","net_salary",
        }
        for c in cols:
            fn = c["fieldname"]
            if fn in SKIP: continue
            label = c.get("label", fn)
            if "(" in label and label.endswith(")"):
                name = label[:label.rfind("(")].strip()
                abbr = label[label.rfind("(")+1:-1].strip()
            else:
                name, abbr = label, fn
            if fn.startswith("e_"):   earn_comps.append((name, abbr))
            elif fn.startswith("d_"): emp_ded_comps.append((name, abbr))
            elif fn.startswith("r_"): empr_comps.append((name, abbr))

    first_hdr_html = (
        '<div class="hdr">'
        '<div class="co">{co}</div>'
        '<div class="ttl">Transaction Checklist</div>'
        '<div class="per">For the Month of {mo} {yr}</div>'
        '</div>'.format(co=co, mo=mo, yr=yr)
    )

    cont_hdr_html = (
        '<div class="cont-hdr">'
        '{co} &mdash; Transaction Checklist &mdash; {mo} {yr} (Contd.)'
        '</div>'.format(co=co, mo=mo, yr=yr)
    )

    if not data:
        return (
            '<!DOCTYPE html><html><head><meta charset="UTF-8">{css}</head>'
            '<body>{hdr}<p style="text-align:center;padding:20px;color:#888;">No data for this period</p>'
            '</body></html>'.format(css=_CSS, hdr=first_hdr_html)
        )

    detail_rows = [r for r in data if not r.get("bold")]
    grand_row   = next((r for r in data if r.get("bold")), {})

    all_chips = []
    all_chips.append(("payment_days",     "PD",  False, False))
    all_chips.append(("absent_days",      "AB",  False, False))
    all_chips.append(("total_lwp",        "LWP", False, False))
    for name, abbr in earn_comps:
        all_chips.append((_fn("e", abbr), abbr, True, False))
    all_chips.append(("gross_earnings",   "GE",  True,  False))
    for name, abbr in emp_ded_comps:
        all_chips.append((_fn("d", abbr), abbr, True, False))
    all_chips.append(("total_deductions", "TD",  True,  False))
    for name, abbr in empr_comps:
        all_chips.append((_fn("r", abbr), abbr, True, False))
    if empr_comps:
        all_chips.append(("employer_total", "ES", True, False))
    all_chips.append(("net_salary",       "NS",  True,  True))

    row1_chips = [c for i, c in enumerate(all_chips) if i % 2 == 0]
    row2_chips = [c for i, c in enumerate(all_chips) if i % 2 == 1]
    while len(row2_chips) < len(row1_chips):
        row2_chips.append(None)

    n_cols  = len(row1_chips)
    last_ix = n_cols - 1

    SR_PCT  = 2.0
    EMP_PCT = 14.0
    DET_PCT = 84.0
    chip_w  = DET_PCT / n_cols if n_cols else DET_PCT

    cg  = '<col style="width:{0}%;">'.format(SR_PCT)
    cg += '<col style="width:{0}%;">'.format(EMP_PCT)
    cg += "".join('<col style="width:{0:.3f}%;">'.format(chip_w) for _ in range(n_cols))

    def _v(row, key, currency=False):
        val = row.get(key)
        try:
            fv = float(val or 0)
            if currency: return "{0:,.2f}".format(fv)
            return str(int(fv)) if fv == int(fv) else "{0:,.2f}".format(fv)
        except (TypeError, ValueError):
            return "0"

    # ── CHANGED: vertical stacking of label above value ──────────────────
    def _chip_html(lbl, val, is_ns=False):
        if is_ns:
            return (
                '<span style="display:inline-flex;flex-direction:column;align-items:center;">'
                '<span class="ns-hl-lbl">{lbl}</span>'
                '<span class="ns-hl-val">{val}</span>'
                '</span>'
            ).format(lbl=lbl, val=val)
        return (
            '<span style="display:flex;flex-direction:column;align-items:flex-start;line-height:1.3;">'
            '<span class="ck">{lbl}</span>'
            '<span class="cv">{val}</span>'
            '</span>'
        ).format(lbl=lbl, val=val)
    # ─────────────────────────────────────────────────────────────────────

    def _render_chip(chip, row, is_row1, col_idx, is_grand=False):
        is_last = (col_idx == last_ix)
        style   = _chip_r1(is_last, is_grand) if is_row1 else _chip_r2(is_last, is_grand)
        if chip is None:
            return '<td style="{s}"></td>'.format(s=style)
        fk, lbl, is_cur, is_ns = chip
        val = _v(row, fk, currency=is_cur)
        return '<td style="{s}">{html}</td>'.format(s=style, html=_chip_html(lbl, val, is_ns))

    def _emp_rows(row, sr, is_grand=False):
        name = row.get("employee_name", "")
        eid  = row.get("employee", "")
        sr_s = "" if is_grand else str(sr)

        sr_td = '<td rowspan="2" style="{s}">{v}</td>'.format(
            s=_sr_style(is_grand), v=sr_s)

        if not is_grand and eid:
            emp_inner = (
                '<table style="border-collapse:collapse;width:100%;border:none;">'
                '<tr><td style="border:none;padding:0;font-size:11px;font-weight:700;'
                'line-height:1.4;word-break:break-word;white-space:normal;">{name}</td></tr>'
                '<tr><td style="border:none;padding:0;margin-top:2px;font-size:8.5px;'
                'color:#444;font-family:monospace;line-height:1.3;">{eid}</td></tr>'
                '</table>'
            ).format(name=name, eid=eid)
        else:
            emp_inner = '<span style="font-size:11px;font-weight:700;line-height:1.4;">{name}</span>'.format(name=name)

        emp_td = '<td rowspan="2" style="{s}">{inner}</td>'.format(
            s=_emp_style(is_grand), inner=emp_inner)

        chips1 = "".join(_render_chip(c, row, True,  i, is_grand) for i, c in enumerate(row1_chips))
        chips2 = "".join(_render_chip(c, row, False, i, is_grand) for i, c in enumerate(row2_chips))

        return (
            "<tr>{sr}{emp}{chips}</tr>".format(sr=sr_td, emp=emp_td, chips=chips1)
            + "<tr>{chips}</tr>".format(chips=chips2)
        )

    thead = (
        '<thead>'
        '<tr>'
        '<th class="h-sr"  rowspan="2">Sr</th>'
        '<th class="h-emp" rowspan="2">Employee</th>'
        '<th class="h-det" colspan="{n}">Details</th>'
        '</tr><tr></tr>'
        '</thead>'.format(n=n_cols)
    )

    legend_items = [
        ("PD",  "Payment Days"),
        ("AB",  "Absent Days"),
        ("LWP", "Leave Without Pay"),
        ("GE",  "Gross Earnings"),
        ("TD",  "Total Deductions"),
        ("ES",  "Employer Share"),
        ("NS",  "Net Salary"),
    ]
    for nm, ab in earn_comps:    legend_items.append((ab, nm))
    for nm, ab in emp_ded_comps: legend_items.append((ab, nm))
    for nm, ab in empr_comps:    legend_items.append((ab, nm))
    seen_lgd = set()
    legend_items_dedup = []
    for ab, nm in legend_items:
        if ab not in seen_lgd:
            seen_lgd.add(ab)
            legend_items_dedup.append((ab, nm))

    legend_html = (
        '<div class="legend">'
        '<div class="legend-title">Legend:</div>'
        '<div class="legend-body">{text}</div>'
        '</div>'.format(text=", ".join(
            "<b>{ab}</b> = {nm}".format(ab=ab, nm=nm)
            for ab, nm in legend_items_dedup
        ))
    )

    pages = []
    for i in range(0, max(len(detail_rows), 1), ROWS_PER_PAGE):
        pages.append(detail_rows[i: i + ROWS_PER_PAGE])
    if not pages:
        pages = [[]]

    total_pages = len(pages)
    parts       = []
    sr_counter  = 1

    for pn, pr in enumerate(pages):
        is_first = (pn == 0)
        is_last  = (pn == len(pages) - 1)

        pb       = '<div style="page-break-before:always;"></div>' if not is_first else ""
        page_hdr = first_hdr_html if is_first else cont_hdr_html

        tbody = "<tbody>"
        for row in pr:
            tbody += _emp_rows(row, sr_counter)
            sr_counter += 1
        if is_last and grand_row:
            tbody += _emp_rows(grand_row, "", is_grand=True)
        tbody += "</tbody>"

        parts.append(
            '{pb}{hdr}'
            '<table class="main"><colgroup>{cg}</colgroup>{thead}{tbody}</table>'
            '<div class="pg-foot">Page {pn} of {tp}</div>'
            '{legend}'.format(
                pb=pb, hdr=page_hdr, cg=cg, thead=thead, tbody=tbody,
                pn=pn + 1, tp=total_pages,
                legend=legend_html if is_last else ""
            )
        )

    sig = (
        '<div class="sig">'
        + "".join(
            '<div class="sig-box"><div class="sig-line"></div>'
            '<div class="sig-lbl">{l}</div></div>'.format(l=l)
            for l in ["Prepared By", "Checked By", "Authorised Signatory"]
        )
        + '</div>'
    )

    return (
        '<!DOCTYPE html><html><head><meta charset="UTF-8">{css}</head>'
        '<body>{body}{sig}</body></html>'.format(css=_CSS, body="".join(parts), sig=sig)
    )


# ---------------------------------------------------------------------------
# PDF save
# ---------------------------------------------------------------------------

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
    fn  = "{0}_{1}.pdf".format(prefix, ts)
    with open(frappe.utils.get_files_path(fn, is_private=0), "wb") as fh:
        fh.write(pdf)
    doc = frappe.get_doc({
        "doctype":    "File",
        "file_name":  fn,
        "is_private": 0,
        "file_url":   "/files/{0}".format(fn),
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