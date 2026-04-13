import frappe
import json
import calendar

from frappe import _
from frappe.utils.pdf import get_pdf

def _month_num(name):
    for i, m in enumerate(calendar.month_name):
        if m == name:
            return i
    return 0

B = "1px solid #000"

STATUS_CODE = {
    "Present":         "P",
    "On Tour":         "T",
    "Absent":          "A",
    "Half Day":        "HD",
    "Holiday":         "H",
    "Weekly Off":      "WO",
    "LWP":             "LWP",
    "Earned Leave":    "EL",
    "Casual Leave":    "CL",
    "Comp Off":        "CO",
    "Earned Comp Off": "ECO",
}

COLOR = {
    "P":   "#1a6b1a",
    "A":   "#c0392b",
    "HD":  "#e67e22",
    "T":   "#2c3e50",
    "H":   "#27ae60",
    "WO":  "#2980b9",
    "LWP": "#8e44ad",
    "EL":  "#d35400",
    "CL":  "#16a085",
    "CO":  "#7f8c8d",
    "ECO": "#a93226",
}

# NOTE: Eff.P (present_days) REMOVED from summary columns per requirement
SUMM_COLS = [
    ("A",   "absent_days"),
    ("HD",  "half_days"),
    ("T",   "on_tour_days"),
    ("EL",  "earned_leave_days"),
    ("CL",  "casual_leave_days"),
    ("CO",  "comp_off_days"),
    ("ECO", "earned_comp_off_days"),
    ("WO",  "weekly_off_days"),
    ("H",   "holiday_days"),
    ("LWP", "lwp_days"),
]

SUMM_COLOR = {
    "absent_days":          COLOR["A"],
    "half_days":            COLOR["HD"],
    "on_tour_days":         COLOR["T"],
    "earned_leave_days":    COLOR["EL"],
    "casual_leave_days":    COLOR["CL"],
    "comp_off_days":        COLOR["CO"],
    "earned_comp_off_days": COLOR["ECO"],
    "weekly_off_days":      COLOR["WO"],
    "holiday_days":         COLOR["H"],
    "lwp_days":             COLOR["LWP"],
}

LEGEND_ITEMS = [
    ("P",   "Present"),
    ("A",   "Absent"),
    ("HD",  "Half Day"),
    ("T",   "On Tour"),
    ("H",   "Holiday"),
    ("WO",  "Weekly Off"),
    ("LWP", "Leave Without Pay"),
    ("EL",  "Earned Leave"),
    ("CL",  "Casual Leave"),
    ("CO",  "Comp Off"),
    ("ECO", "Earned Comp Off"),
]

# ── Rows per page ─────────────────────────────────────────────────────────────
# Page 1: title (~18mm) + legend (~8mm) + table header (~6mm) leaves ~168mm
# Page 2+: cont header (~8mm) + legend (~8mm) + table header (~6mm) leaves ~178mm
# Each data row is ~5.5mm tall → page1≈30, others≈32
# Conservative values so nothing overflows:
ROWS_FIRST_PAGE = 26
ROWS_OTHER_PAGE = 30

# ─────────────────────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────────────────────
_CSS = """<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Arial,sans-serif;font-size:10px;color:#000;background:#fff}

.hdr{text-align:center;border-bottom:2px solid #000;padding:6px 6px 5px;margin-bottom:3px;}
.hdr .co{font-size:18px;font-weight:900;letter-spacing:1px;text-transform:uppercase}
.hdr .ttl{font-size:13px;font-weight:700;margin-top:2px}
.hdr .per{font-size:11px;margin-top:2px}

.cont-hdr{
    text-align:center;font-size:9px;color:#555;
    margin-bottom:3px;border-bottom:1px solid #000;padding-bottom:2px;
}

table.data-tbl{
    width:100%;
    border-collapse:collapse;
    table-layout:fixed;
}
table.data-tbl th{
    border:1px solid #000;
    padding:2px 1px;
    font-size:8.5px;
    font-weight:700;
    background:#f0f0f0;
    text-align:center;
    word-break:break-word;
    vertical-align:middle;
}
table.data-tbl td{
    border:1px solid #000;
    padding:1px;
    font-size:8.5px;
    vertical-align:middle;
}
.nd{text-align:center;padding:10px;color:#888}

.lgd-bar{
    display:flex;flex-wrap:wrap;align-items:center;
    padding:3px 5px;margin:0 0 3px 0;
    background:#f4f5f6;border:1px solid #d1d8dd;border-radius:3px;
    font-size:8px;font-family:Arial,sans-serif;line-height:1.6;
}

.pg-foot{text-align:right;font-size:8.5px;color:#555;margin-top:2px;}

.sig{
    display:flex;justify-content:space-between;
    width:100%;margin-top:14px;padding-top:6px;
}
.sig-b{text-align:center;width:170px}
.sig-l{border-top:1px solid #000;margin-bottom:3px}
.sig-t{font-size:10px;color:#333}
.sig-d{font-size:9px;color:#555;margin-top:5px}
</style>"""


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


def _legend_bar_html():
    parts = []
    for k, v in LEGEND_ITEMS:
        parts.append(
            '<span style="display:inline-flex;align-items:center;gap:2px;'
            'margin-right:8px;white-space:nowrap;">'
            '<b style="color:{c};font-size:8px;">{k}</b>'
            '<span style="font-size:8px;color:#444;">&#8211;{v}</span>'
            '</span>'.format(c=COLOR.get(k, "#000"), k=k, v=v)
        )
    return (
        '<div class="lgd-bar">'
        '<span style="font-weight:700;font-size:8px;color:#6c7680;'
        'margin-right:6px;white-space:nowrap;">Legend:</span>'
        '{items}'
        '</div>'.format(items="".join(parts))
    )


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


def _col(label, fn, ft="Data", w=120, **kw):
    return {"label": _(label), "fieldname": fn, "fieldtype": ft, "width": w, **kw}


def _company_label(f):
    c = _parse_list(f.get("company"))
    return ", ".join(c) if c else (frappe.defaults.get_global_default("company") or "")


# ─────────────────────────────────────────────────────────────────────────────
# Data
# ─────────────────────────────────────────────────────────────────────────────

def _get_data(f):
    ms = f.get("month", "")
    ys = f.get("year", "")
    mn = _month_num(ms)

    # Sr No | Employee Name | Employee ID  (Eff.P removed)
    cols = [
        _col("Sr",            "sr_no",        w=40),
        _col("Employee Name", "employee_name", w=180),
        _col("Employee ID",   "employee",      w=100),
    ]

    if not mn or not ys:
        return cols, []

    yi   = int(ys)
    last = calendar.monthrange(yi, mn)[1]
    fd   = "{0}-{1:02d}-01".format(yi, mn)
    td   = "{0}-{1:02d}-{2:02d}".format(yi, mn, last)

    for d in range(1, last + 1):
        cols.append({"label": str(d), "fieldname": "day_{0}".format(d),
                     "fieldtype": "Data", "width": 45})

    for lbl, fn in SUMM_COLS:
        cols.append(_col(lbl, fn, "Float", 65, precision=2))

    cos = _parse_list(f.get("company"))
    if not cos:
        return cols, []

    co_tuple = tuple(cos) if len(cos) > 1 else (cos[0], cos[0])
    p = {"fd": fd, "td": td, "co": co_tuple}

    catj = ""
    cat  = f.get("category")
    if cat:
        p["category"] = cat
        catj = "INNER JOIN `tabCompany Link` cl ON cl.name=a.employee AND cl.category=%(category)s"

    ec = ""
    se = _parse_list(f.get("employee"))
    if se:
        p["employees"] = tuple(se) if len(se) > 1 else (se[0], se[0])
        ec = "AND a.employee IN %(employees)s"

    dc = ""
    divs = _parse_list(f.get("division"))
    if divs:
        p["divisions"] = tuple(divs) if len(divs) > 1 else (divs[0], divs[0])
        dc = ("AND a.employee IN "
              "(SELECT name FROM `tabCompany Link` "
              " WHERE division IN %(divisions)s OR department IN %(divisions)s)")

    recs = frappe.db.sql(
        "SELECT a.employee, a.employee_name, a.attendance_date, a.status"
        " FROM `tabAttendance` a {catj}"
        " WHERE a.company IN %(co)s"
        "   AND a.attendance_date BETWEEN %(fd)s AND %(td)s"
        "   {ec} {dc}"
        " ORDER BY a.employee_name, a.attendance_date".format(catj=catj, ec=ec, dc=dc),
        p, as_dict=1,
    )

    if not recs:
        return cols, []

    ed, eo = {}, []

    for row in recs:
        emp = row.employee
        day = (row.attendance_date.day
               if hasattr(row.attendance_date, "day")
               else int(str(row.attendance_date)[8:10]))
        st = row.status
        if st not in STATUS_CODE:
            continue

        if emp not in ed:
            eo.append(emp)
            ed[emp] = {
                "employee": emp, "employee_name": row.employee_name or "",
                # present_days kept internally for Eff.P calc but NOT shown
                "present_days": 0.0,
                "absent_days": 0.0, "half_days": 0.0,
                "on_tour_days": 0.0, "earned_leave_days": 0.0,
                "casual_leave_days": 0.0, "comp_off_days": 0.0,
                "earned_comp_off_days": 0.0, "weekly_off_days": 0.0,
                "holiday_days": 0.0, "lwp_days": 0.0,
            }

        ed[emp]["day_{0}".format(day)] = STATUS_CODE[st]

        if   st == "Present":         ed[emp]["present_days"]         += 1.0
        elif st == "On Tour":         ed[emp]["on_tour_days"]          += 1.0; ed[emp]["present_days"] += 1.0
        elif st == "Absent":          ed[emp]["absent_days"]           += 1.0
        elif st == "Half Day":        ed[emp]["half_days"]             += 1.0; ed[emp]["present_days"] += 0.5; ed[emp]["absent_days"] += 0.5
        elif st == "Holiday":         ed[emp]["holiday_days"]          += 1.0
        elif st == "Weekly Off":      ed[emp]["weekly_off_days"]       += 1.0
        elif st == "LWP":             ed[emp]["lwp_days"]              += 1.0; ed[emp]["absent_days"] += 1.0
        elif st == "Earned Leave":    ed[emp]["earned_leave_days"]     += 1.0
        elif st == "Casual Leave":    ed[emp]["casual_leave_days"]     += 1.0
        elif st == "Comp Off":        ed[emp]["comp_off_days"]         += 1.0
        elif st == "Earned Comp Off": ed[emp]["earned_comp_off_days"]  += 1.0

    for emp in ed:
        for d in range(1, last + 1):
            ed[emp].setdefault("day_{0}".format(d), "-")

    # Assign serial numbers
    result = []
    for i, emp in enumerate(eo, 1):
        ed[emp]["sr_no"] = i
        result.append(ed[emp])

    return cols, result


def execute(filters=None):
    return _get_data(filters or {})


# ─────────────────────────────────────────────────────────────────────────────
# HTML builder — manual pagination (same strategy as Transaction Checklist)
# Each page gets its own <table> with a fresh header row.
# No reliance on <thead> CSS repeat or --header-html.
# ─────────────────────────────────────────────────────────────────────────────

def _build_html(cols, data, co, mo, yr):
    mn    = _month_num(mo)
    yi    = int(yr) if yr else 0
    last  = calendar.monthrange(yi, mn)[1] if mn and yi else 31
    dcols = [c for c in cols if c["fieldname"].startswith("day_")]
    nd    = len(dcols)
    ns    = len(SUMM_COLS)

    # ── colgroup ───────────────────────────────────────────────────────────
    sr_pct   = 2.0
    name_pct = 11.0
    summ_pct = 2.1
    day_pct  = (100.0 - sr_pct - name_pct - ns * summ_pct) / nd if nd else 0

    cg  = '<colgroup>'
    cg += '<col style="width:{0}%;"/>'.format(sr_pct)
    cg += '<col style="width:{0}%;"/>'.format(name_pct)
    cg += "".join('<col style="width:{0:.3f}%;"/>'.format(day_pct) for _ in dcols)
    cg += "".join('<col style="width:{0}%;"/>'.format(summ_pct) for _ in SUMM_COLS)
    cg += '</colgroup>'

    # ── page headers ───────────────────────────────────────────────────────
    page1_hdr = (
        '<div class="hdr">'
        '<div class="co">{co}</div>'
        '<div class="ttl">Monthly Attendance Report</div>'
        '<div class="per">For the Month of {mo} {yr}</div>'
        '</div>'.format(co=co, mo=mo, yr=yr)
    )
    cont_hdr = (
        '<div class="cont-hdr">'
        '{co} &mdash; Monthly Attendance Report &mdash; {mo} {yr} (contd.)'
        '</div>'.format(co=co, mo=mo, yr=yr)
    )
    lgd_bar = _legend_bar_html()

    # ── column header row ──────────────────────────────────────────────────
    BG1 = "background:#f0f0f0;"
    BG2 = "background:#d0d8e0;"
    TH  = ("border:{B};padding:2px 1px;font-size:8.5px;font-weight:700;"
           "text-align:center;vertical-align:middle;").format(B=B)

    header_tr = "<tr>"
    header_tr += '<th style="{th}{bg}">Sr</th>'.format(th=TH, bg=BG1)
    header_tr += (
        '<th style="{th}{bg}text-align:left;">'
        'Employee Name / ID'
        '</th>'.format(th=TH, bg=BG1)
    )
    for c in dcols:
        header_tr += '<th style="{th}{bg}">{lbl}</th>'.format(
            th=TH, bg=BG1, lbl=c["label"])
    for lbl, fn in SUMM_COLS:
        cc = SUMM_COLOR.get(fn, "#000")
        header_tr += (
            '<th style="{th}{bg}color:{cc};">{lbl}</th>'.format(
                th=TH, bg=BG2, cc=cc, lbl=lbl)
        )
    header_tr += "</tr>"

    # ── display helper ─────────────────────────────────────────────────────
    def _disp(v):
        if v is None or v == "" or v == 0 or v == 0.0:
            return ""
        try:
            fv = float(v)
            return str(int(fv)) if fv == int(fv) else "{:.1f}".format(fv)
        except (TypeError, ValueError):
            return str(v)

    # ── single employee row ────────────────────────────────────────────────
    def _emp_row(row, i):
        bg  = "#f9f9f9" if i % 2 else "#ffffff"
        SBG = "#eef2f7"
        html = "<tr>"
        # Sr No
        html += (
            '<td style="border:{B};text-align:center;padding:2px 1px;'
            'vertical-align:middle;background:{bg};font-size:8.5px;color:#555;">'
            '{sr}</td>'.format(B=B, bg=bg, sr=row.get("sr_no", ""))
        )
        # Name + ID stacked
        html += (
            '<td style="border:{B};padding:2px 3px;vertical-align:middle;background:{bg};">'
            '<div style="font-size:8.5px;font-weight:700;line-height:1.3;'
            'word-break:break-word;">{name}</div>'
            '<div style="font-size:7.5px;color:#555;line-height:1.3;">{eid}</div>'
            '</td>'.format(B=B, bg=bg,
                           name=row.get("employee_name", ""),
                           eid=row.get("employee", ""))
        )
        # Day cells
        for c in dcols:
            v     = row.get(c["fieldname"], "") or ""
            color = COLOR.get(v, "#000")
            cell  = (
                '<span style="font-weight:700;color:{c};font-size:8.5px;">{v}</span>'.format(
                    c=color, v=v)
                if v and v != "-"
                else '<span style="color:#ddd;">&#8211;</span>'
            )
            html += (
                '<td style="border:{B};text-align:center;padding:1px 0;'
                'background:{bg};vertical-align:middle;">{cell}</td>'.format(
                    B=B, bg=bg, cell=cell)
            )
        # Summary cells
        for lbl, fn in SUMM_COLS:
            val = _disp(row.get(fn))
            vc  = SUMM_COLOR.get(fn, "#000") if val else "#bbb"
            html += (
                '<td style="border:{B};font-size:8.5px;font-weight:700;'
                'color:{vc};text-align:center;padding:2px 0;'
                'background:{SBG};vertical-align:middle;">'
                '{val}</td>'.format(B=B, SBG=SBG, vc=vc, val=val)
            )
        html += "</tr>"
        return html

    # ── page table builder ─────────────────────────────────────────────────
    def _page_table(rows, start_i):
        tbody = "<tbody>"
        for j, row in enumerate(rows):
            tbody += _emp_row(row, start_i + j)
        tbody += "</tbody>"
        return (
            '<table class="data-tbl">{cg}<thead>{hdr}</thead>{tbody}</table>'
        ).format(cg=cg, hdr=header_tr, tbody=tbody)

    # ── paginate ───────────────────────────────────────────────────────────
    if not data:
        pages = [[]]
    else:
        pages, idx, first = [], 0, True
        while idx < len(data):
            lim = ROWS_FIRST_PAGE if first else ROWS_OTHER_PAGE
            pages.append(data[idx: idx + lim])
            idx  += lim
            first = False

    total_pages = len(pages)
    parts       = []
    row_counter = 0

    for pn, page_rows in enumerate(pages):
        pb      = '<div style="page-break-before:always;"></div>' if pn > 0 else ""
        is_last = (pn == total_pages - 1)
        page_hdr = (page1_hdr if pn == 0 else cont_hdr) + lgd_bar

        if not data:
            tbl = (
                '<table class="data-tbl">{cg}<thead>{hdr}</thead>'
                '<tbody><tr><td colspan="{n}" class="nd">'
                'No data for this period</td></tr></tbody></table>'
            ).format(cg=cg, hdr=header_tr, n=2 + nd + ns)
        else:
            tbl = _page_table(page_rows, row_counter)
            row_counter += len(page_rows)

        pg_foot = '<div class="pg-foot">Page {p} of {t}</div>'.format(
            p=pn + 1, t=total_pages)
        sig = _sig_html() if is_last else ""

        parts.append("{pb}{hdr}{tbl}{foot}{sig}".format(
            pb=pb, hdr=page_hdr, tbl=tbl, foot=pg_foot, sig=sig))

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
    co = _company_label(filters)
    mo = filters.get("month", "")
    yr = filters.get("year", "")
    return _save_pdf(
        _build_html(cols, data, co, mo, yr),
        "Monthly_Attendance_Report",
    )