import frappe
import json

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
# Option A column layout
# (fieldname, header, align, width-pct)
#
# Columns: Sr | Employee (ID+Name+DOJ+DOB sub-lines) | PF No. | UAN No. |
#           WD/PD | Gross | Basic+DA | Emp PF |
#           [GROUP: Employer Contribution → EPS | Empr PF | EDLI | Admin] |
#           Total
#
# 11 logical columns → fits A4 landscape comfortably at 8.5 px font
# ---------------------------------------------------------------------------

_COLS = [
    ("sr",            "Sr",          "c",  3.0),
    ("employee",      "Employee",    "l", 14.0),   # merged: name + ID sub-line + DOJ/DOB
    ("pf_no",         "PF No.",      "c",  9.0),
    ("uan_no",        "UAN No.",     "c",  9.5),
    ("wd_pd",         "WD / PD",     "c",  5.5),   # merged working/payment days
    ("gross",         "Gross Salary","r",  8.5),
    ("basic_da",      "Basic + DA",  "r",  8.5),
    ("emp_pf",        "Emp PF",      "r",  7.0),
    # ── Employer Contribution group (4 sub-columns) ──
    ("employer_eps",  "EPS",         "r",  6.5),
    ("employer_pf",   "Empr PF",     "r",  6.5),
    ("employer_edli", "EDLI",        "r",  5.5),
    ("employer_admin","PF Admin",    "r",  5.5),
    # ────────────────────────────────────────────────
    ("total_amount",  "Total",       "r",  8.0),
]

# Columns that belong to the "Employer Contribution" group header
_EMPR_GROUP = {"employer_eps", "employer_pf", "employer_edli", "employer_admin"}

_SKIP_ON_TOTAL = {
    "sr", "employee", "pf_no", "uan_no", "wd_pd",
}
_NUMERIC = {
    "gross","basic_da","emp_pf","employer_eps",
    "employer_pf","employer_edli","employer_admin","total_amount",
}

ROWS_FIRST_PAGE = 7
ROWS_OTHER_PAGE = 8

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

_CSS = """<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:Arial,sans-serif;font-size:8.5px;color:#000;background:#fff}}

.hdr{{text-align:center;border-bottom:2px solid #000;padding:5px 4px 4px;margin-bottom:3px;}}
.hdr .co{{font-size:17px;font-weight:900;letter-spacing:1px;text-transform:uppercase}}
.hdr .ttl{{font-size:12px;font-weight:700;margin-top:2px}}
.hdr .per{{font-size:10px;margin-top:1px;color:#333}}

.cont-hdr{{
    text-align:center;font-size:8.5px;color:#555;
    border-bottom:1px solid #000;padding-bottom:2px;margin-bottom:3px;
}}

table.data-tbl{{width:100%;border-collapse:collapse;table-layout:fixed;}}
table.data-tbl th{{
    border:1px solid #000;
    padding:3px 2px;
    font-size:7.5px;
    font-weight:700;
    background:#f0f0f0;
    white-space:normal;
    word-wrap:break-word;
    vertical-align:middle;
    text-align:center;
    line-height:1.25;
}}
/* Group header row */
table.data-tbl th.grp-hdr{{
    background:#dce6f1;
    font-size:7.5px;
    border-bottom:1px solid #999;
}}
/* Spacer th in group header row — no visible top/bottom border */
table.data-tbl th.grp-spacer{{
    background:#fff;
    border-top:1px solid #fff;
    border-bottom:1px solid #fff;
    border-left:1px solid #000;
    border-right:1px solid #000;
}}
table.data-tbl td{{
    border:1px solid #000;
    padding:2px 2px;
    font-size:7.5px;
    vertical-align:middle;
    white-space:normal;
    word-wrap:break-word;
    overflow:hidden;
    line-height:1.3;
}}

.emp-name{{font-weight:600;font-size:7.5px;}}
.emp-sub{{font-size:6.5px;color:#555;margin-top:1px;}}

.r{{text-align:right}}.c{{text-align:center}}.l{{text-align:left}}
.nd{{text-align:center;padding:12px;color:#888}}

.pg-foot{{text-align:right;font-size:7.5px;color:#555;margin-top:2px}}

.sig{{display:flex;justify-content:space-between;width:100%;margin-top:14px;}}
.sig-b{{text-align:center;width:150px}}
.sig-l{{border-top:1px solid #000;margin-bottom:2px}}
.sig-t{{font-size:9px;color:#333}}
.sig-d{{font-size:8px;color:#555;margin-top:4px}}
</style>"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _base_cond(f, p):
    c  = ["ss.docstatus=1"]
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
    return ("INNER JOIN `tabCompany Link` cl_cat "
            "ON cl_cat.name=ss.employee AND cl_cat.category=%(category)s")


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
        return "{0:,.2f}".format(fv)
    except (TypeError, ValueError): return str(v)


def _fmt_days(v):
    if v is None or v == "": return ""
    try:
        fv = float(v)
        return str(int(fv)) if fv == int(fv) else "{0:.1f}".format(fv)
    except (TypeError, ValueError): return str(v)


def _fmt_date(v):
    """Convert 'YYYY-MM-DD' → 'DD-MM-YYYY' for compact display."""
    if not v: return ""
    s = str(v).strip()
    if len(s) == 10 and s[4] == "-":
        return "{2}-{1}-{0}".format(*s.split("-"))
    return s


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

def _get_data(f):
    cols = [
        _col("Sr",            "sr",             w=40),
        _col("Employee",      "employee",       w=160),
        _col("PF No.",        "pf_no",          w=130),
        _col("UAN No.",       "uan_no",         w=130),
        _col("WD / PD",       "wd_pd",          w=60),
        _col("Gross Salary",  "gross",          "Float", 100, precision=2),
        _col("Basic + DA",    "basic_da",       "Float", 100, precision=2),
        _col("Emp PF",        "emp_pf",         "Float", 80,  precision=2),
        _col("EPS",           "employer_eps",   "Float", 80,  precision=2),
        _col("Empr. PF",      "employer_pf",    "Float", 80,  precision=2),
        _col("EDLI",          "employer_edli",  "Float", 70,  precision=2),
        _col("PF Admin",      "employer_admin", "Float", 70,  precision=2),
        _col("Total",         "total_amount",   "Float", 90,  precision=2),
    ]

    if not f.get("company"):
        return cols, []

    p    = {}
    cond = _base_cond(f, p)
    catj = _cat_join(f, p)
    divc = _div_cond(f, p)

    slips = frappe.db.sql(
        "SELECT ss.name AS slip_name, ss.employee AS eid, ss.employee_name,"
        "       ss.total_working_days AS working_days, ss.payment_days,"
        "       ss.total_earnings AS gross"
        " FROM `tabSalary Slip` ss {catj}"
        " WHERE {cond}{divc}"
        " ORDER BY ss.employee_name".format(catj=catj, cond=cond, divc=divc),
        p, as_dict=1
    )
    if not slips:
        return cols, []

    sn   = tuple(s.slip_name for s in slips)
    eids = tuple(s.eid for s in slips)

    bda = {
        r.slip_name: flt(r.v)
        for r in frappe.db.sql(
            "SELECT sd.parent AS slip_name, SUM(sd.amount) AS v"
            " FROM `tabSalary Details` sd"
            " WHERE sd.parent IN %(sn)s"
            "   AND sd.parenttype='Salary Slip'"
            "   AND sd.parentfield='earnings'"
            "   AND (LOWER(sd.salary_component) LIKE '%%basic%%'"
            "        OR LOWER(sd.salary_component) LIKE '%%dearness%%'"
            "        OR LOWER(sd.salary_component) LIKE '%% da'"
            "        OR sd.salary_component='DA')"
            " GROUP BY sd.parent",
            {"sn": sn}, as_dict=1
        )
    }

    ep = {
        r.slip_name: flt(r.v)
        for r in frappe.db.sql(
            "SELECT sd.parent AS slip_name, SUM(sd.amount) AS v"
            " FROM `tabSalary Details` sd"
            " WHERE sd.parent IN %(sn)s"
            "   AND sd.parenttype='Salary Slip'"
            "   AND sd.parentfield='deductions'"
            "   AND sd.salary_component=%(c)s"
            " GROUP BY sd.parent",
            {"sn": sn, "c": PF_EMP_COMP}, as_dict=1
        )
    }

    def _fe(comp):
        return {
            r.slip_name: flt(r.v)
            for r in frappe.db.sql(
                "SELECT sd.parent AS slip_name, SUM(sd.amount) AS v"
                " FROM `tabSalary Details` sd"
                " WHERE sd.parent IN %(sn)s"
                "   AND sd.parenttype='Salary Slip'"
                "   AND sd.parentfield='employer_share'"
                "   AND sd.salary_component=%(c)s"
                " GROUP BY sd.parent",
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
            "SELECT e.name, e.employee_pf_account AS pf_no,"
            "       e.pf_uan_number AS uan_no, e.date_of_birth,"
            "       cl.date_of_joining"
            " FROM `tabEmployee` e"
            " LEFT JOIN `tabCompany Link` cl ON cl.name=e.name"
            " WHERE e.name IN %(ids)s",
            {"ids": eids}, as_dict=1
        )
    }

    data = []
    tot  = {k: 0.0 for k in [
        "gross","basic_da","emp_pf","employer_eps",
        "employer_pf","employer_edli","employer_admin","total_amount"
    ]}

    for idx, s in enumerate(slips, start=1):
        emp = em.get(s.eid, frappe._dict())
        sn_ = s.slip_name
        g   = flt(s.gross,            2)
        b   = flt(bda.get(sn_,   0),  2)
        epf = flt(ep.get(sn_,    0),  2)
        erp = flt(erpf.get(sn_,  0),  2)
        ere = flt(ereps.get(sn_, 0),  2)
        erd = flt(eredli.get(sn_,0),  2)
        era = flt(eradm.get(sn_, 0),  2)
        tol = flt(epf + erp + ere + erd + era, 2)

        for k, v in [("gross",g),("basic_da",b),("emp_pf",epf),
                     ("employer_eps",ere),("employer_pf",erp),
                     ("employer_edli",erd),("employer_admin",era),
                     ("total_amount",tol)]:
            tot[k] += v

        doj = _fmt_date(emp.get("date_of_joining") or "")
        dob = _fmt_date(emp.get("date_of_birth")   or "")

        data.append({
            "sr":              str(idx),
            "employee_id":     s.eid,
            "employee_name":   s.employee_name,
            "employee_doj":    doj,
            "employee_dob":    dob,
            # merged display field used in HTML
            "employee":        s.employee_name,
            "pf_no":           emp.get("pf_no")  or "",
            "uan_no":          emp.get("uan_no") or "",
            # store raw for display in wd_pd cell
            "working_days":    flt(s.working_days, 1),
            "payment_days":    flt(s.payment_days, 1),
            "wd_pd":           "{} / {}".format(
                                   _fmt_days(flt(s.working_days, 1)),
                                   _fmt_days(flt(s.payment_days, 1))),
            "gross":           g,
            "basic_da":        b,
            "emp_pf":          epf,
            "employer_eps":    ere,
            "employer_pf":     erp,
            "employer_edli":   erd,
            "employer_admin":  era,
            "total_amount":    tol,
        })

    if data:
        data.append({
            "sr":              "",
            "employee":        "Total",
            "employee_id":     "",
            "employee_name":   "Total",
            "employee_doj":    "",
            "employee_dob":    "",
            "pf_no":           "",
            "uan_no":          "",
            "working_days":    None,
            "payment_days":    None,
            "wd_pd":           "",
            **{k: flt(v, 2) for k, v in tot.items()},
            "bold":            1,
        })

    return cols, data


def execute(filters=None):
    return _get_data(filters or {})


# ---------------------------------------------------------------------------
# HTML builder — Option A layout
# ---------------------------------------------------------------------------

def _colgroup():
    total_pct = sum(c[3] for c in _COLS)
    parts = "<colgroup>"
    for _, _, _, pct in _COLS:
        parts += '<col style="width:{0:.3f}%;">'.format(pct * 100.0 / total_pct)
    parts += "</colgroup>"
    return parts


def _thead_html():
    """
    Two header rows:
      Row 1: Sr | Employee | PF No. | UAN No. | WD/PD | Gross | Basic+DA |
             Emp PF | [Employer Contribution — colspan 4] | Total
      Row 2: (empty spacers for non-group cols) | EPS | Empr PF | EDLI | PF Admin
    """
    # How many columns are in the employer group
    empr_span = sum(1 for fn, _, _, _ in _COLS if fn in _EMPR_GROUP)
    # Indices of group columns
    empr_fns  = [fn for fn, _, _, _ in _COLS if fn in _EMPR_GROUP]

    # ── Row 1 ──────────────────────────────────────────────────────────────
    row1 = "<tr>"
    for fn, hdr, align, _ in _COLS:
        if fn == empr_fns[0]:
            # First employer col: open the group header spanning all 4
            row1 += (
                '<th class="grp-hdr" colspan="{span}" '
                'style="text-align:center;border-bottom:1px solid #999;">'
                'Employer Contribution</th>'
            ).format(span=empr_span)
        elif fn in _EMPR_GROUP:
            continue   # already covered by the colspan above
        else:
            # Non-group column: rowspan=2 so it occupies both header rows
            row1 += '<th rowspan="2" class="{a}">{h}</th>'.format(a=align, h=hdr)
    row1 += "</tr>"

    # ── Row 2 — sub-headers for the employer group only ───────────────────
    row2 = "<tr>"
    for fn, hdr, _, _ in _COLS:
        if fn in _EMPR_GROUP:
            row2 += '<th class="c">{h}</th>'.format(h=hdr)
    row2 += "</tr>"

    return "<thead>{r1}{r2}</thead>".format(r1=row1, r2=row2)


def _render_row(row, is_total=False, row_idx=0):
    bg = "#e0e0e0" if is_total else ("#f5f7fa" if row_idx % 2 else "#ffffff")
    fw = "font-weight:700;" if is_total else ""

    tr = "<tr>"
    for fn, _, align, _ in _COLS:
        val = row.get(fn, "")

        # ── Skip suppressed total columns ──────────────────────────────
        if is_total and fn in _SKIP_ON_TOTAL:
            if fn == "employee":
                # Still show "Total" label, bold
                tr += (
                    '<td class="l" style="background:{bg};font-weight:700;">'
                    'Total</td>'
                ).format(bg=bg)
            else:
                tr += '<td style="background:{bg};"></td>'.format(bg=bg)
            continue

        # ── Employee cell — name + ID + DOJ/DOB sub-lines ──────────────
        if fn == "employee":
            name  = row.get("employee_name", "") or ""
            eid   = row.get("employee_id",   "") or ""
            doj   = row.get("employee_doj",  "") or ""
            dob   = row.get("employee_dob",  "") or ""
            sub_parts = []
            if eid:  sub_parts.append(eid)
            if doj:  sub_parts.append("DOJ: " + doj)
            if dob:  sub_parts.append("DOB: " + dob)
            sub_html = ""
            if sub_parts:
                sub_html = '<div class="emp-sub">{}</div>'.format(
                    "&nbsp;&nbsp;|&nbsp;&nbsp;".join(sub_parts))
            tr += (
                '<td class="l" style="background:{bg};{fw}">'
                '<div class="emp-name">{name}</div>{sub}'
                '</td>'
            ).format(bg=bg, fw=fw, name=name or "", sub=sub_html)
            continue

        # ── WD/PD combined ─────────────────────────────────────────────
        if fn == "wd_pd":
            tr += '<td class="c" style="background:{bg};{fw}">{v}</td>'.format(
                bg=bg, fw=fw, v=val or "")
            continue

        # ── Numeric columns ─────────────────────────────────────────────
        if fn in _NUMERIC:
            tr += '<td class="r" style="background:{bg};{fw}">{v}</td>'.format(
                bg=bg, fw=fw, v=_fmt(val))
            continue

        # ── Default ─────────────────────────────────────────────────────
        tr += '<td class="{a}" style="background:{bg};{fw}">{v}</td>'.format(
            a=align, bg=bg, fw=fw, v=val or "")

    tr += "</tr>"
    return tr


def _page_table(page_rows, start_idx):
    cg    = _colgroup()
    thead = _thead_html()
    tbody = "<tbody>"
    for j, row in enumerate(page_rows):
        is_tot = bool(row.get("bold"))
        tbody += _render_row(row, is_total=is_tot,
                             row_idx=0 if is_tot else (start_idx + j))
    tbody += "</tbody>"
    return '<table class="data-tbl">{cg}{thead}{tbody}</table>'.format(
        cg=cg, thead=thead, tbody=tbody)


def _paginate(detail_rows, total_row):
    if not detail_rows:
        return [[total_row] if total_row else []]
    safe_first = max(1, ROWS_FIRST_PAGE - 2)
    safe_other = max(1, ROWS_OTHER_PAGE - 2)
    pages = []
    idx   = 0
    first = True
    while idx < len(detail_rows):
        lim   = safe_first if first else safe_other
        chunk = detail_rows[idx: idx + lim]
        pages.append(list(chunk))
        idx  += len(chunk)
        first = False
    if total_row:
        pages[-1].append(total_row)
    return pages


def _build_html(cols, data, co, mo, yr):
    page1_hdr = (
        '<div class="hdr">'
        '<div class="co">{co}</div>'
        '<div class="ttl">Provident Fund Register</div>'
        '<div class="per">For the Month of {mo} {yr}</div>'
        '</div>'
    ).format(co=co, mo=mo, yr=yr)

    cont_hdr = (
        '<div class="cont-hdr">'
        '{co} &mdash; Provident Fund Register &mdash; {mo} {yr} (contd.)'
        '</div>'
    ).format(co=co, mo=mo, yr=yr)

    detail_rows = [r for r in data if not r.get("bold")]
    total_row   = next((r for r in data if r.get("bold")), None)

    if not detail_rows:
        pages    = [[]]
        has_data = False
    else:
        has_data = True
        pages = _paginate(detail_rows, total_row)

    total_pages = len(pages)
    parts       = []
    row_counter = 0

    for pn, page_rows in enumerate(pages):
        pb      = '<div style="page-break-before:always;"></div>' if pn > 0 else ""
        is_last = (pn == total_pages - 1)
        hdr_html = page1_hdr if pn == 0 else cont_hdr

        if not has_data:
            nc  = len(_COLS)
            tbl = (
                '<table class="data-tbl">{cg}{thead}'
                '<tbody><tr><td colspan="{nc}" class="nd">'
                'No data for this period</td></tr></tbody></table>'
            ).format(cg=_colgroup(), thead=_thead_html(), nc=nc)
        else:
            tbl = _page_table(page_rows, row_counter)
            row_counter += sum(1 for r in page_rows if not r.get("bold"))

        pg_foot = '<div class="pg-foot">Page {p} of {t}</div>'.format(
            p=pn + 1, t=total_pages)
        sig = _sig_html() if is_last else ""

        parts.append("{pb}{hdr}{tbl}{foot}{sig}".format(
            pb=pb, hdr=hdr_html, tbl=tbl, foot=pg_foot, sig=sig))

    return (
        '<!DOCTYPE html><html><head><meta charset="UTF-8">{css}</head>'
        '<body>{body}</body></html>'
    ).format(css=_CSS, body="".join(parts))


def _save_pdf(html, prefix):
    pdf = get_pdf(html, options={
        "page-size":     "A4",
        "orientation":   "Landscape",
        "margin-top":    "7mm",
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
    cols, data = _get_data(filters)
    co   = _company_label(filters)
    mo   = filters.get("month", "")
    yr   = filters.get("year",  "")
    html = _build_html(cols, data, co, mo, yr)
    return _save_pdf(html, "Provident_Fund_Register")