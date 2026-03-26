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
    "Present":      "P",
    "On Tour":      "T",
    "Absent":       "A",
    "Half Day":     "HD",
    "Holiday":      "H",
    "Weekly Off":   "WO",
    "LWP":          "LWP",
    "Earned Leave": "EL",
    "Casual Leave": "CL",
    "Comp Off":     "CO",
    "Earned Comp Off": "ECO",
}

# FIX 3: body width:100% so flex sig container spans full page width
_CSS = """<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Arial,sans-serif;font-size:11px;color:#000;background:#fff;width:100%;}
.hdr{text-align:center;border-bottom:2px solid #000;padding:10px 6px 6px;margin-bottom:4px}
.hdr .co{font-size:22px;font-weight:900;letter-spacing:1px;text-transform:uppercase}
.hdr .ttl{font-size:16px;font-weight:700;margin-top:2px}
.hdr .per{font-size:13px;margin-top:2px}
.lgd{padding:5px 4px;border-bottom:1px solid #000;margin-bottom:4px}
.nd{text-align:center;padding:10px;color:#888}
table{width:100%;border-collapse:collapse;table-layout:fixed}
th{border:1px solid #000;padding:3px 2px;font-size:10px;font-weight:700;background:#f0f0f0;text-align:center}
td{border:1px solid #000;padding:2px;font-size:11px;vertical-align:top}
</style>"""

# FIX 3: inline width:100% on sig container — prevents wkhtmltopdf
# collapsing the flex div to content width, which shifts sigs left
_SIG = """
<!--SIG_START-->
<div style="display:flex;justify-content:space-between;
            width:100%;margin-top:16px;padding-top:8px;
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
    fd   = f"{yi}-{mn:02d}-01"
    td   = f"{yi}-{mn:02d}-{last:02d}"

    for d in range(1, last + 1):
        cols.append({"label": str(d), "fieldname": f"day_{d}",
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

    cat  = f.get("category")
    catj = ""
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
        f"""SELECT a.employee, a.employee_name, a.attendance_date, a.status
            FROM `tabAttendance` a {catj}
            WHERE a.company IN %(co)s
              AND a.attendance_date BETWEEN %(fd)s AND %(td)s
              {ec} {dc}
            ORDER BY a.employee_name, a.attendance_date""",
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
        st  = row.status

        if st not in STATUS_CODE:
            continue

        if emp not in ed:
            eo.append(emp)
            ed[emp] = {
                "employee":             emp,
                "employee_name":        row.employee_name or "",
                "present_days":         0.0,
                "absent_days":          0.0,
                "half_days":            0.0,
                "on_tour_days":         0.0,
                "earned_leave_days":    0.0,
                "casual_leave_days":    0.0,
                "comp_off_days":        0.0,
                "earned_comp_off_days": 0.0,
                "weekly_off_days":      0.0,
                "holiday_days":         0.0,
                "lwp_days":             0.0,
            }

        code = STATUS_CODE[st]
        ed[emp][f"day_{day}"] = code

        if st == "Present":
            ed[emp]["present_days"]      += 1.0
        elif st == "On Tour":
            ed[emp]["on_tour_days"]      += 1.0
            ed[emp]["present_days"]      += 1.0
        elif st == "Absent":
            ed[emp]["absent_days"]       += 1.0
        elif st == "Half Day":
            ed[emp]["half_days"]         += 1.0
            ed[emp]["present_days"]      += 0.5
            ed[emp]["absent_days"]       += 0.5
        elif st == "Holiday":
            ed[emp]["holiday_days"]      += 1.0
        elif st == "Weekly Off":
            ed[emp]["weekly_off_days"]   += 1.0
        elif st == "LWP":
            ed[emp]["lwp_days"]          += 1.0
            ed[emp]["absent_days"]       += 1.0
        elif st == "Earned Leave":
            ed[emp]["earned_leave_days"] += 1.0
        elif st == "Casual Leave":
            ed[emp]["casual_leave_days"] += 1.0
        elif st == "Comp Off":
            ed[emp]["comp_off_days"]     += 1.0
        elif st == "Earned Comp Off":
            ed[emp]["earned_comp_off_days"] += 1.0

    for emp in ed:
        for d in range(1, last + 1):
            ed[emp].setdefault(f"day_{d}", "-")

    return cols, [ed[e] for e in eo]


def execute(filters=None):
    return _get_data(filters or {})


def _build_html(cols, data, co, mo, yr):
    mn   = MONTH_MAP.get(mo, 0)
    yi   = int(yr) if yr else 0
    last = calendar.monthrange(yi, mn)[1] if mn and yi else 31
    dcols = [c for c in cols if c["fieldname"].startswith("day_")]

    SUMM_PAIRS = [
        ("P",   "present_days",         "A",   "absent_days"),
        ("HD",  "half_days",            "T",   "on_tour_days"),
        ("EL",  "earned_leave_days",    "CL",  "casual_leave_days"),
        ("CO",  "comp_off_days",        "ECO", "earned_comp_off_days"),
        ("WO",  "weekly_off_days",      "H",   "holiday_days"),
        ("LWP", "lwp_days",             "",    ""),
    ]

    lgd = "".join(
        f'<span style="margin-right:12px;font-size:11px;"><b>{k}</b> – {v}</span>'
        for k, v in [
            ("P","Present"),("A","Absent"),("HD","Half Day"),("T","On Tour"),
            ("EL","Earned Leave"),("CL","Casual Leave"),
            ("CO","Comp Off"),("ECO","Earned Comp Off"),
            ("WO","Weekly Off"),("H","Holiday"),("LWP","Leave Without Pay"),
        ]
    )

    hdr = (
        f'<div class="hdr"><div class="co">{co}</div>'
        f'<div class="ttl">Monthly Attendance Report</div>'
        f'<div class="per">For the Month of {mo} {yr}</div></div>'
        f'<div class="lgd">{lgd}</div>'
    )

    # FIX 3: tighter column widths so WO/LWP summary cols don't clip
    nd         = len(dcols)
    name_pct   = 12                    # was 14
    summ_total = 18                    # was 21
    n_summ     = len(SUMM_PAIRS)
    day_pct    = f"{(100 - name_pct - summ_total) / nd:.3f}%" if nd else "0%"
    sc_pct     = f"{summ_total / n_summ:.3f}%"
    cg  = f'<colgroup><col style="width:{name_pct}%;"/>'
    cg += "".join(f'<col style="width:{day_pct};"/>' for _ in dcols)
    cg += "".join(f'<col style="width:{sc_pct};"/>' for _ in SUMM_PAIRS)
    cg += "</colgroup>"

    FS   = "font-size:13px;"
    FSS  = "font-size:12px;"
    PAD  = "padding:3px 2px;"
    CTR  = "text-align:center;vertical-align:middle;"
    BG1  = "background:#f0f0f0;"
    BG2  = "background:#d0d8e0;"
    BOLD = "font-weight:700;"

    def th1(extra=""):
        return f'border:{B};{PAD}{FS}{BOLD}{CTR}{extra}'
    def th2(extra=""):
        return f'border:{B};{PAD}{FSS}{BOLD}{CTR}{extra}'

    r1  = '<tr>'
    r1 += f'<th rowspan="2" style="{th1(BG1)}text-align:left;white-space:normal;word-break:break-word;">Employee<br><span style="font-size:10px;font-weight:400;color:#555;">ID</span></th>'
    for c in dcols:
        r1 += f'<th rowspan="2" style="{th1(BG1)}">{c["label"]}</th>'
    for tl, *_ in SUMM_PAIRS:
        r1 += f'<th style="{th1(BG2)}">{tl}</th>'
    r1 += "</tr>"

    r2  = '<tr>'
    for _, __, bl, ___ in SUMM_PAIRS:
        r2 += f'<th style="{th2(BG2)}">{bl}</th>'
    r2 += "</tr>"

    ch    = r1 + r2
    ncols = 1 + nd + n_summ

    COLOR = {
        "A":"#c0392b","LWP":"#8e44ad","WO":"#2980b9","H":"#27ae60",
        "EL":"#d35400","CL":"#16a085","CO":"#7f8c8d","ECO":"#c0392b","T":"#2c3e50",
        "HD":"#e67e22","P":"#1a6b1a",
    }

    def _disp(v):
        if v is None or v == "" or v == 0 or v == 0.0: return ""
        return str(int(v)) if isinstance(v, float) and v == int(v) else str(v)

    def _build_rows(page_data):
        rows_html = ""
        for i, row in enumerate(page_data):
            bg  = "#f9f9f9" if i % 2 else "#ffffff"
            SBG = "#eef2f7"

            tr1  = "<tr>"
            tr1 += (
                f'<td rowspan="2" style="border:{B};padding:3px 4px;'
                f'vertical-align:middle;background:{bg};">'
                f'<div style="font-size:13px;font-weight:700;line-height:1.3;word-break:break-word;">'
                f'{row.get("employee_name","")}</div>'
                f'<div style="font-size:11px;color:#555;line-height:1.3;">'
                f'{row.get("employee","")}</div></td>'
            )
            for c in dcols:
                v     = row.get(c["fieldname"], "") or ""
                color = COLOR.get(v, "#000")
                cell  = v if v != "-" else '<span style="color:#ddd;">–</span>'
                tr1 += (
                    f'<td rowspan="2" style="border:{B};font-size:13px;font-weight:700;'
                    f'text-align:center;padding:2px 0;background:{bg};'
                    f'color:{color};vertical-align:middle;">{cell}</td>'
                )
            for tl, tfn, bl, bfn in SUMM_PAIRS:
                tv = _disp(row.get(tfn))
                tr1 += (
                    f'<td style="border-left:{B};border-right:{B};border-top:{B};'
                    f'border-bottom:1px solid #aaa;'
                    f'font-size:13px;font-weight:700;text-align:center;'
                    f'padding:2px 1px;background:{SBG};vertical-align:middle;">{tv}</td>'
                )
            tr1 += "</tr>"

            tr2  = "<tr>"
            for tl, tfn, bl, bfn in SUMM_PAIRS:
                bv = _disp(row.get(bfn)) if bfn else ""
                tr2 += (
                    f'<td style="border-left:{B};border-right:{B};border-bottom:{B};'
                    f'border-top:none;'
                    f'font-size:13px;font-weight:700;text-align:center;'
                    f'padding:2px 1px;background:{SBG};vertical-align:middle;">{bv}</td>'
                )
            tr2 += "</tr>"

            rows_html += tr1 + tr2
        return rows_html

    def _make_table(page_data):
        body_html = (
            _build_rows(page_data) if page_data
            else f'<tr><td colspan="{ncols}" class="nd">No data for this period</td></tr>'
        )
        return (
            f'<table style="width:100%;table-layout:fixed;border-collapse:collapse;margin-top:6px;">'
            f'{cg}<thead>{ch}</thead><tbody>{body_html}</tbody></table>'
        )

    if not data:
        body = f'<div style="display:block;">{hdr}{_make_table([])}</div>'
    else:
        # FIX 2: correct per-page employee limits
        # Each employee = 2 HTML rows; page 1 has title+legend so fewer fit
        FIRST, OTHER = 11, 14    # was 13, 16
        pages, idx, first = [], 0, True
        while idx < len(data):
            lim = FIRST if first else OTHER
            pages.append(data[idx: idx + lim])
            idx  += lim
            first = False

        parts = []
        for pn, pr in enumerate(pages):
            # FIX 1 & 4: page break on outer wrapper div; hdr repeats
            # on every page so reader always sees company/month context
            pb_style = "break-before:page;page-break-before:always;" if pn > 0 else ""
            parts.append(
                f'<div style="display:block;{pb_style}">'
                f'{hdr}{_make_table(pr)}'
                f'</div>'
            )
        body = "".join(parts)

    return (
        f'<!DOCTYPE html><html><head><meta charset="UTF-8">{_CSS}</head>'
        f'<body>{body}{_SIG}</body></html>'
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
        "doctype":   "File",
        "file_name": fn,
        "is_private": 0,
        "file_url":  f"/files/{fn}",
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
        "Monthly_Attendance_Report",
    )