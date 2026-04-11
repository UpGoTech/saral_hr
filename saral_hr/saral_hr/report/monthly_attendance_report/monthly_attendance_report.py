import frappe
import json
import calendar

from frappe import _
from frappe.utils.pdf import get_pdf

MONTH_MAP = {
    "January":1,"February":2,"March":3,"April":4,"May":5,"June":6,
    "July":7,"August":8,"September":9,"October":10,"November":11,"December":12,
}

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

SUMM_PAIRS = [
    ("P",   "present_days",         "A",   "absent_days"),
    ("HD",  "half_days",            "T",   "on_tour_days"),
    ("EL",  "earned_leave_days",    "CL",  "casual_leave_days"),
    ("CO",  "comp_off_days",        "ECO", "earned_comp_off_days"),
    ("WO",  "weekly_off_days",      "H",   "holiday_days"),
    ("LWP", "lwp_days",             "",    ""),
]

# ─────────────────────────────────────────────────────────────────────────────
# CSS
# Key decisions for wkhtmltopdf:
#   thead { display:table-header-group }  → col-header repeats on every page
#   tbody.emp-row { page-break-inside:avoid }  → employee never split
#   Company title + legend rendered once above the table (not inside thead)
# ─────────────────────────────────────────────────────────────────────────────
_CSS = """<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Arial,sans-serif;font-size:10px;color:#000;background:#fff;width:100%}

.hdr{text-align:center;border-bottom:2px solid #000;padding:8px 6px 6px;margin-bottom:5px}
.hdr .co{font-size:20px;font-weight:900;letter-spacing:1px;text-transform:uppercase}
.hdr .ttl{font-size:15px;font-weight:700;margin-top:2px}
.hdr .per{font-size:13px;margin-top:2px}

.lgd{
    padding:5px 8px;
    border-bottom:1px solid #000;
    margin-bottom:5px;
    white-space:nowrap;
    overflow:hidden;
    line-height:1.6;
    font-size:9.5px;
}
.lgd .lbl{font-weight:700;font-size:9px;color:#555;margin-right:8px}
.lgd span{display:inline-block;margin-right:20px}

table{width:100%;border-collapse:collapse;table-layout:fixed;margin-top:4px}
thead{display:table-header-group}
th{border:1px solid #000;padding:2px 1px;font-size:9px;font-weight:700;
   background:#f0f0f0;text-align:center;word-break:break-word}
td{border:1px solid #000;padding:1px;font-size:9px;vertical-align:middle}
.nd{text-align:center;padding:10px;color:#888}

tbody.emp-row{page-break-inside:avoid;break-inside:avoid}

.sig{display:flex;justify-content:space-between;width:100%;
     margin-top:16px;padding-top:8px;box-sizing:border-box}
.sig-b{text-align:center;width:180px}
.sig-l{border-top:1px solid #000;margin-bottom:4px}
.sig-t{font-size:11px;color:#333}
</style>"""

_SIG = (
    '<div class="sig">'
    + "".join(
        '<div class="sig-b"><div class="sig-l"></div>'
        '<div class="sig-t">{l}</div></div>'.format(l=l)
        for l in ["Prepared By", "Checked By", "Authorised Signatory"]
    )
    + "</div>"
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

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
    mn = MONTH_MAP.get(ms)

    cols = [
        _col("Employee ID",   "employee",      w=150),
        _col("Employee Name", "employee_name", w=250),
    ]

    if not mn or not ys:
        return cols, []

    yi   = int(ys)
    last = calendar.monthrange(yi, mn)[1]
    fd   = "{0}-{1:02d}-01".format(yi, mn)
    td   = "{0}-{1:02d}-{2:02d}".format(yi, mn, last)

    for d in range(1, last + 1):
        cols.append({"label": str(d), "fieldname": "day_{0}".format(d),
                     "fieldtype": "Data", "width": 50})

    SUMM_COLS = [
        ("P",   "present_days"),
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
    for lbl, fn in SUMM_COLS:
        cols.append(_col(lbl, fn, "Float", 70, precision=2))

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
                "present_days": 0.0, "absent_days": 0.0, "half_days": 0.0,
                "on_tour_days": 0.0, "earned_leave_days": 0.0,
                "casual_leave_days": 0.0, "comp_off_days": 0.0,
                "earned_comp_off_days": 0.0, "weekly_off_days": 0.0,
                "holiday_days": 0.0, "lwp_days": 0.0,
            }

        ed[emp]["day_{0}".format(day)] = STATUS_CODE[st]

        if   st == "Present":         ed[emp]["present_days"]          += 1.0
        elif st == "On Tour":         ed[emp]["on_tour_days"]           += 1.0; ed[emp]["present_days"] += 1.0
        elif st == "Absent":          ed[emp]["absent_days"]            += 1.0
        elif st == "Half Day":        ed[emp]["half_days"]              += 1.0; ed[emp]["present_days"] += 0.5; ed[emp]["absent_days"] += 0.5
        elif st == "Holiday":         ed[emp]["holiday_days"]           += 1.0
        elif st == "Weekly Off":      ed[emp]["weekly_off_days"]        += 1.0
        elif st == "LWP":             ed[emp]["lwp_days"]               += 1.0; ed[emp]["absent_days"] += 1.0
        elif st == "Earned Leave":    ed[emp]["earned_leave_days"]      += 1.0
        elif st == "Casual Leave":    ed[emp]["casual_leave_days"]      += 1.0
        elif st == "Comp Off":        ed[emp]["comp_off_days"]          += 1.0
        elif st == "Earned Comp Off": ed[emp]["earned_comp_off_days"]   += 1.0

    for emp in ed:
        for d in range(1, last + 1):
            ed[emp].setdefault("day_{0}".format(d), "-")

    return cols, [ed[e] for e in eo]


def execute(filters=None):
    return _get_data(filters or {})


# ─────────────────────────────────────────────────────────────────────────────
# HTML / PDF
# ─────────────────────────────────────────────────────────────────────────────

def _build_html(cols, data, co, mo, yr):
    mn    = MONTH_MAP.get(mo, 0)
    yi    = int(yr) if yr else 0
    last  = calendar.monthrange(yi, mn)[1] if mn and yi else 31
    dcols = [c for c in cols if c["fieldname"].startswith("day_")]
    nd    = len(dcols)
    ns    = len(SUMM_PAIRS)

    # column widths
    name_pct = 13.0
    pair_pct = 3.2
    day_pct  = (100.0 - name_pct - ns * pair_pct) / nd if nd else 0
    day_s    = "{0:.3f}%".format(day_pct)

    cg  = '<colgroup><col style="width:{0}%;"/>'.format(name_pct)
    cg += "".join('<col style="width:{0};"/>'.format(day_s) for _ in dcols)
    cg += "".join('<col style="width:{0}%;"/>'.format(pair_pct) for _ in SUMM_PAIRS)
    cg += "</colgroup>"

    # legend — one line, spaced
    lgd_items = [
        ("P","Present"), ("A","Absent"), ("HD","Half Day"), ("T","On Tour"),
        ("H","Holiday"), ("WO","Weekly Off"), ("LWP","Leave Without Pay"),
        ("EL","Earned Leave"), ("CL","Casual Leave"),
        ("CO","Comp Off"), ("ECO","Earned Comp Off"),
    ]
    lgd_spans = "".join(
        '<span><b style="color:{c};">{k}</b> &ndash; {v}</span>'.format(
            c=COLOR.get(k, "#000"), k=k, v=v)
        for k, v in lgd_items
    )
    lgd_block = (
        '<div class="lgd">'
        '<span class="lbl">Legend :</span>'
        + lgd_spans
        + "</div>"
    )

    # company header (printed once, above the table)
    hdr_block = (
        '<div class="hdr">'
        '<div class="co">{co}</div>'
        '<div class="ttl">Monthly Attendance Report</div>'
        '<div class="per">For the Month of {mo} {yr}</div>'
        "</div>".format(co=co, mo=mo, yr=yr)
    )

    # column header — lives inside <thead> so wkhtmltopdf repeats it each page
    BG1 = "background:#f0f0f0;"
    BG2 = "background:#d0d8e0;"
    TH  = "border:{B};padding:2px 1px;font-size:9px;font-weight:700;text-align:center;vertical-align:middle;".format(B=B)

    r1  = "<tr>"
    r1 += (
        '<th rowspan="2" style="{th}{bg}text-align:left;">'
        "Employee<br>"
        '<span style="font-size:8px;font-weight:400;color:#555;">ID</span>'
        "</th>".format(th=TH, bg=BG1)
    )
    for c in dcols:
        r1 += '<th rowspan="2" style="{th}{bg}">{lbl}</th>'.format(
            th=TH, bg=BG1, lbl=c["label"])
    for tl, _, bl, __ in SUMM_PAIRS:
        r1 += '<th style="{th}{bg}">{tl}</th>'.format(th=TH, bg=BG2, tl=tl)
    r1 += "</tr>"

    r2  = "<tr>"
    for _, __, bl, ___ in SUMM_PAIRS:
        r2 += '<th style="{th}{bg}">{bl}</th>'.format(th=TH, bg=BG2, bl=bl)
    r2 += "</tr>"

    col_header = r1 + r2

    # row builder
    def _disp(v):
        if v is None or v == "" or v == 0 or v == 0.0:
            return ""
        return str(int(v)) if isinstance(v, float) and v == int(v) else str(v)

    def _build_rows(all_data):
        """
        Each employee = one <tbody class='emp-row'> with 2 <tr>s.
        page-break-inside:avoid on tbody prevents splitting.
        """
        SBG  = "#eef2f7"
        html = ""
        for i, row in enumerate(all_data):
            bg = "#f9f9f9" if i % 2 else "#ffffff"

            # open per-employee tbody
            html += '<tbody class="emp-row">'

            # row 1: name/id (rowspan 2) + day cells (rowspan 2) + summary top
            tr1  = "<tr>"
            tr1 += (
                '<td rowspan="2" style="border:{B};padding:2px 3px;'
                'vertical-align:middle;background:{bg};">'
                '<div style="font-size:10px;font-weight:700;line-height:1.3;'
                'word-break:break-word;">{name}</div>'
                '<div style="font-size:8.5px;color:#555;line-height:1.3;">{eid}</div>'
                "</td>".format(
                    B=B, bg=bg,
                    name=row.get("employee_name", ""),
                    eid=row.get("employee", ""))
            )
            for c in dcols:
                v     = row.get(c["fieldname"], "") or ""
                color = COLOR.get(v, "#000")
                cell  = v if v and v != "-" else '<span style="color:#ddd;">&#8211;</span>'
                tr1 += (
                    '<td rowspan="2" style="border:{B};font-size:9px;font-weight:700;'
                    'text-align:center;padding:1px 0;background:{bg};'
                    'color:{color};vertical-align:middle;">{cell}</td>'.format(
                        B=B, bg=bg, color=color, cell=cell)
                )
            for tl, tfn, bl, bfn in SUMM_PAIRS:
                tv = _disp(row.get(tfn))
                tr1 += (
                    '<td style="border-left:{B};border-right:{B};border-top:{B};'
                    'border-bottom:1px solid #aaa;font-size:10px;font-weight:700;'
                    'text-align:center;padding:2px 1px;background:{SBG};'
                    'vertical-align:middle;">{tv}</td>'.format(B=B, SBG=SBG, tv=tv)
                )
            tr1 += "</tr>"

            # row 2: summary bottom only
            tr2  = "<tr>"
            for tl, tfn, bl, bfn in SUMM_PAIRS:
                bv = _disp(row.get(bfn)) if bfn else ""
                tr2 += (
                    '<td style="border-left:{B};border-right:{B};border-bottom:{B};'
                    'border-top:none;font-size:10px;font-weight:700;'
                    'text-align:center;padding:2px 1px;background:{SBG};'
                    'vertical-align:middle;">{bv}</td>'.format(B=B, SBG=SBG, bv=bv)
                )
            tr2 += "</tr>"

            html += tr1 + tr2
            html += "</tbody>"

        return html

    # assemble
    if not data:
        ncols     = 1 + nd + ns
        body_html = (
            '<tbody><tr><td colspan="{n}" class="nd">'
            "No data for this period"
            "</td></tr></tbody>".format(n=ncols)
        )
    else:
        body_html = _build_rows(data)

    table = (
        '<table style="width:100%;table-layout:fixed;'
        'border-collapse:collapse;margin-top:4px;">'
        "{cg}<thead>{ch}</thead>{body}</table>".format(
            cg=cg, ch=col_header, body=body_html)
    )

    return (
        "<!DOCTYPE html><html><head><meta charset=\"UTF-8\">{css}</head>"
        "<body>{hdr}{lgd}{table}{sig}</body></html>".format(
            css=_CSS, hdr=hdr_block, lgd=lgd_block, table=table, sig=_SIG)
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
    fn  = "{0}_{1}.pdf".format(prefix, ts)
    with open(frappe.utils.get_files_path(fn, is_private=0), "wb") as fh:
        fh.write(pdf)
    doc = frappe.get_doc({
        "doctype":   "File",
        "file_name": fn,
        "is_private": 0,
        "file_url":  "/files/{0}".format(fn),
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
        "Monthly_Attendance_Report",
    )