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

# ── Status codes exactly matching your Attendance doctype ──────────────────
# Present, On Tour, Absent, Half Day, Holiday, Weekly Off, LWP,
# Earned Leave, Casual Leave, Comp Off
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

# Which statuses contribute to each summary counter
# present_days  = Present (1) + Half Day (0.5) + On Tour (1)
# absent_days   = Absent  (1) + Half Day (0.5) + LWP     (1)
# leave_days    = Earned Leave + Casual Leave + Comp Off (each 1)
# weekly_off    = Weekly Off count
# holiday_days  = Holiday count
# lwp_days      = LWP count
# half_days     = Half Day count

_CSS = """<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Arial,sans-serif;font-size:11px;color:#000;background:#fff}
.hdr{text-align:center;border-bottom:2px solid #000;padding:10px 6px 6px;margin-bottom:4px}
.hdr .co{font-size:22px;font-weight:900;letter-spacing:1px;text-transform:uppercase}
.hdr .ttl{font-size:16px;font-weight:700;margin-top:2px}
.hdr .per{font-size:13px;margin-top:2px}
.lgd{padding:5px 4px;border-bottom:1px solid #000;margin-bottom:4px}
.sig{display:flex;justify-content:space-between;margin-top:16px;padding-top:8px}
.sig-b{text-align:center;width:180px}
.sig-l{border-top:1px solid #000;margin-bottom:4px}
.sig-t{font-size:13px;color:#333}
table{width:100%;border-collapse:collapse;table-layout:fixed}
th{border:1px solid #000;padding:3px 2px;font-size:10px;font-weight:700;background:#f0f0f0;text-align:center}
td{border:1px solid #000;padding:2px;font-size:11px;vertical-align:top}
.nd{text-align:center;padding:10px;color:#888}
</style>"""

_SIG = '<div class="sig">' + "".join(
    f'<div class="sig-b"><div class="sig-l"></div><div class="sig-t">{l}</div></div>'
    for l in ["Prepared By", "Checked By", "Authorised Signatory"]
) + '</div>'


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

    # ── Base columns ───────────────────────────────────────────────────────
    cols = [
        _col("Employee ID",   "employee",      w=110),
        _col("Employee Name", "employee_name", w=160),
    ]

    if not mn or not ys:
        return cols, []

    yi   = int(ys)
    last = calendar.monthrange(yi, mn)[1]
    fd   = f"{yi}-{mn:02d}-01"
    td   = f"{yi}-{mn:02d}-{last:02d}"

    # Day columns (1 … last)
    for d in range(1, last + 1):
        cols.append({"label": str(d), "fieldname": f"day_{d}",
                     "fieldtype": "Data", "width": 18})

    # Summary columns – exactly your 10 statuses, no WD
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
        cols.append(_col(lbl, fn, "Float", 25, precision=2))

    # ── Build filters ──────────────────────────────────────────────────────
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

    # ── Query ──────────────────────────────────────────────────────────────
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

    # ── Aggregate ──────────────────────────────────────────────────────────
    ed, eo = {}, []

    for row in recs:
        emp = row.employee
        day = (row.attendance_date.day
               if hasattr(row.attendance_date, "day")
               else int(str(row.attendance_date)[8:10]))
        st  = row.status

        # Skip unknown statuses gracefully
        if st not in STATUS_CODE:
            continue

        if emp not in ed:
            eo.append(emp)
            ed[emp] = {
                "employee":           emp,
                "employee_name":      row.employee_name or "",
                # counters – all start at 0
                "present_days":       0.0,
                "absent_days":        0.0,
                "half_days":          0.0,
                "on_tour_days":       0.0,
                "earned_leave_days":  0.0,
                "casual_leave_days":  0.0,
                "comp_off_days":      0.0,
                "earned_comp_off_days": 0.0,
                "weekly_off_days":    0.0,
                "holiday_days":       0.0,
                "lwp_days":           0.0,
            }

        code = STATUS_CODE[st]
        ed[emp][f"day_{day}"] = code

        # ── Counter logic ──────────────────────────────────────────────────
        if st == "Present":
            ed[emp]["present_days"]      += 1.0

        elif st == "On Tour":
            ed[emp]["on_tour_days"]      += 1.0
            ed[emp]["present_days"]      += 1.0   # On Tour counts as present

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
            ed[emp]["absent_days"]       += 1.0   # LWP is unpaid → absent

        elif st == "Earned Leave":
            ed[emp]["earned_leave_days"] += 1.0

        elif st == "Casual Leave":
            ed[emp]["casual_leave_days"] += 1.0

        elif st == "Comp Off":
            ed[emp]["comp_off_days"]     += 1.0

        elif st == "Earned Comp Off":
            ed[emp]["earned_comp_off_days"] += 1.0

    # Fill any days with no attendance record as "-"
    for emp in ed:
        for d in range(1, last + 1):
            ed[emp].setdefault(f"day_{d}", "-")

    return cols, [ed[e] for e in eo]


# ──────────────────────────────────────────────────────────────────────────────
# Frappe report entry-point
# ──────────────────────────────────────────────────────────────────────────────
def execute(filters=None):
    return _get_data(filters or {})


# ──────────────────────────────────────────────────────────────────────────────
# HTML / PDF helpers
# ──────────────────────────────────────────────────────────────────────────────
def _build_html(cols, data, co, mo, yr):
    mn   = MONTH_MAP.get(mo, 0)
    yi   = int(yr) if yr else 0
    last = calendar.monthrange(yi, mn)[1] if mn and yi else 31
    dcols = [c for c in cols if c["fieldname"].startswith("day_")]

    # 5 pairs — top label / bottom label / their fieldnames
    SUMM_PAIRS = [
        ("P",   "present_days",         "A",   "absent_days"),
        ("HD",  "half_days",            "T",   "on_tour_days"),
        ("EL",  "earned_leave_days",    "CL",  "casual_leave_days"),
        ("CO",  "comp_off_days",        "ECO", "earned_comp_off_days"),
        ("WO",  "weekly_off_days",      "H",   "holiday_days"),
        ("LWP", "lwp_days",             "",    ""),
    ]

    # ── Legend ────────────────────────────────────────────────────────────
    lgd = "".join(
        f'<span style="margin-right:12px;font-size:13px;"><b>{k}</b> – {v}</span>'
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

    # ── Column widths ──────────────────────────────────────────────────────
    nd         = len(dcols)
    ncols      = 1 + nd + len(SUMM_PAIRS)
    name_pct   = 14
    summ_total = 21
    day_pct    = f"{(100 - name_pct - summ_total) / nd:.3f}%" if nd else "0%"
    sc_pct     = f"{summ_total / len(SUMM_PAIRS):.2f}%"
    cg  = f'<colgroup><col style="width:{name_pct}%;"/>'
    cg += "".join(f'<col style="width:{day_pct};"/>' for _ in dcols)
    cg += "".join(f'<col style="width:{sc_pct};"/>' for _ in SUMM_PAIRS)
    cg += "</colgroup>"

    # ── Two-row thead ──────────────────────────────────────────────────────
    # Row 1: "Employee" | day numbers | top labels (P, HD, EL, CO, H)
    # Row 2: "ID"       | (empty)     | bottom labels (A, T, CL, WO, LWP)
    # The border between the two thead rows IS the separator line.
    # No inner tables. No hacks.

    FS   = "font-size:14px;"       # header font size
    FSS  = "font-size:13px;"       # slightly smaller for bottom row
    PAD  = "padding:3px 2px;"
    CTR  = "text-align:center;vertical-align:middle;"
    BG1  = "background:#f0f0f0;"   # day cols header bg
    BG2  = "background:#d0d8e0;"   # summary cols header bg
    BOLD = "font-weight:700;"

    # shared th style builders
    def th1(extra=""):
        return f'border:{B};{PAD}{FS}{BOLD}{CTR}{extra}'
    def th2(extra=""):
        # bottom header row has no bottom-border emphasis needed — just normal border
        return f'border:{B};{PAD}{FSS}{BOLD}{CTR}{extra}'

    # ── thead row 1 ───────────────────────────────────────────────────────
    r1 = f'<tr>'
    # Employee column — rowspan=2, vertically centred
    r1 += f'<th rowspan="2" style="{th1(BG1)}text-align:left;white-space:normal;word-break:break-word;">Employee<br><span style="font-size:11px;font-weight:400;color:#555;">ID</span></th>'
    # Day number columns — rowspan=2 so they span both header rows, perfectly centred
    for c in dcols:
        r1 += f'<th rowspan="2" style="{th1(BG1)}">{c["label"]}</th>'
    # Summary top labels
    for tl, *_ in SUMM_PAIRS:
        r1 += f'<th style="{th1(BG2)}">{tl}</th>'
    r1 += "</tr>"

    # ── thead row 2 ───────────────────────────────────────────────────────
    r2 = f'<tr>'
    # Employee column handled by rowspan=2 above
    # Day columns — no second row needed, handled by rowspan=2 above
    # Summary bottom labels
    for _, __, bl, ___ in SUMM_PAIRS:
        r2 += f'<th style="{th2(BG2)}">{bl}</th>'
    r2 += "</tr>"

    ch = r1 + r2

    # ── Colors ────────────────────────────────────────────────────────────
    COLOR = {
        "A":"#c0392b","LWP":"#8e44ad","WO":"#2980b9","H":"#27ae60",
        "EL":"#d35400","CL":"#16a085","CO":"#7f8c8d","ECO":"#c0392b","T":"#2c3e50",
        "HD":"#e67e22","P":"#1a6b1a",
    }

    def _disp(v):
        if v is None or v == "" or v == 0 or v == 0.0: return ""
        return str(int(v)) if isinstance(v, float) and v == int(v) else str(v)

    # ── Data rows — single <tr> per employee ──────────────────────────────
    # Summary cells: top value / bottom value stacked using a mini 2-cell div,
    # BUT now the row itself is tall enough (matches 2 header rows) via rowspan=2
    # approach — actually simplest: just two <tr> per employee.

    def _build_rows(page_data):
        rows_html = ""
        for i, row in enumerate(page_data):
            bg  = "#f9f9f9" if i % 2 else "#ffffff"
            SBG = "#eef2f7"

            # ── top data row ──────────────────────────────────────────────
            tr1 = "<tr>"
            # Employee name — rowspan=2 so it spans both sub-rows
            tr1 += (
                f'<td rowspan="2" style="border:{B};padding:3px 4px;'
                f'vertical-align:middle;background:{bg};">'
                f'<div style="font-size:14px;font-weight:700;line-height:1.3;word-break:break-word;overflow-wrap:break-word;">'
                f'{row.get("employee_name","")}</div>'
                f'<div style="font-size:13px;color:#555;line-height:1.3;word-break:break-word;overflow-wrap:break-word;">'
                f'{row.get("employee","")}</div></td>'
            )
            # Day cells — rowspan=2
            for c in dcols:
                v     = row.get(c["fieldname"], "") or ""
                color = COLOR.get(v, "#000")
                cell  = v if v != "-" else '<span style="color:#ddd;">–</span>'
                tr1 += (
                    f'<td rowspan="2" style="border:{B};font-size:14px;font-weight:700;'
                    f'text-align:center;padding:2px 0;background:{bg};'
                    f'color:{color};vertical-align:middle;">{cell}</td>'
                )
            # Summary TOP values
            for tl, tfn, bl, bfn in SUMM_PAIRS:
                tv = _disp(row.get(tfn))
                tr1 += (
                    f'<td style="border-left:{B};border-right:{B};border-top:{B};'
                    f'border-bottom:1px solid #000;'
                    f'font-size:14px;font-weight:700;text-align:center;'
                    f'padding:2px 1px;background:{SBG};vertical-align:middle;">{tv}</td>'
                )
            tr1 += "</tr>"

            # ── bottom data row ───────────────────────────────────────────
            tr2 = "<tr>"
            # Summary BOTTOM values
            for tl, tfn, bl, bfn in SUMM_PAIRS:
                bv = _disp(row.get(bfn)) if bfn else ""
                tr2 += (
                    f'<td style="border-left:{B};border-right:{B};border-bottom:{B};'
                    f'border-top:none;'
                    f'font-size:14px;font-weight:700;text-align:center;'
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
        body = hdr + _make_table([])
    else:
        FIRST, OTHER = 13, 16   # halved because each employee now takes 2 rows
        pages, idx, first = [], 0, True
        while idx < len(data):
            lim = FIRST if first else OTHER
            pages.append(data[idx: idx + lim])
            idx  += lim
            first = False
        parts = []
        for pn, pr in enumerate(pages):
            pb = '<div style="page-break-before:always;"></div>' if pn > 0 else ""
            parts.append(pb + hdr + _make_table(pr))
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