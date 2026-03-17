import frappe
import json
import calendar

from frappe import _
from frappe.utils import flt
from frappe.utils.pdf import get_pdf

MONTH_MAP = {
    "January":1,"February":2,"March":3,"April":4,"May":5,"June":6,
    "July":7,"August":8,"September":9,"October":10,"November":11,"December":12,
}

B = "1px solid #000"

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
    if not v: return []
    if isinstance(v, list): return v
    try:
        p = json.loads(v)
        if isinstance(p, list): return p
    except Exception: pass
    return [x.strip() for x in v.split(",") if x.strip()]

def _col(label, fn, ft="Data", w=120, **kw):
    return {"label": _(label), "fieldname": fn, "fieldtype": ft, "width": w, **kw}

def _company_label(f):
    c = _parse_list(f.get("company"))
    return ", ".join(c) if c else (frappe.defaults.get_global_default("company") or "")

def _fmt(v):
    if v is None or v == "" or v == 0 or v == 0.0: return ""
    return str(int(v)) if isinstance(v, float) and v == int(v) else str(v)


def _get_data(f):
    ms, ys = f.get("month", ""), f.get("year", "")
    mn = MONTH_MAP.get(ms)
    cols = [_col("Employee ID", "employee", w=110), _col("Employee Name", "employee_name", w=160)]
    if not mn or not ys: return cols, []

    yi   = int(ys)
    last = calendar.monthrange(yi, mn)[1]
    fd   = f"{yi}-{mn:02d}-01"
    td   = f"{yi}-{mn:02d}-{last:02d}"

    for d in range(1, last + 1):
        cols.append({"label": str(d), "fieldname": f"day_{d}", "fieldtype": "Data", "width": 18})

    SUMM_COLS = [
        ("P","present_days"), ("A","absent_days"), ("HD","half_days"),
        ("EL","earned_leave_days"), ("CL","casual_leave_days"),
        ("CO","comp_off_days"), ("OT","on_tour_days"),
        ("WD","working_days"), ("WO","weekly_off_days"), ("H","holiday_days"), ("LWP","lwp_days"),
    ]
    for lbl, fn in SUMM_COLS:
        cols.append(_col(lbl, fn, "Float", 25, precision=2))

    cos = _parse_list(f.get("company"))
    if not cos: return cols, []
    co  = tuple(cos) if len(cos) > 1 else (cos[0], cos[0])

    p   = {"fd": fd, "td": td, "co": co}
    cat = f.get("category")
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
        dc = "AND a.employee IN (SELECT name FROM `tabCompany Link` WHERE division IN %(divisions)s OR department IN %(divisions)s)"

    recs = frappe.db.sql(
        f"""SELECT a.employee, a.employee_name, a.attendance_date, a.status
            FROM `tabAttendance` a {catj}
            WHERE a.company IN %(co)s
              AND a.attendance_date BETWEEN %(fd)s AND %(td)s
              {ec} {dc}
            ORDER BY a.employee_name, a.attendance_date""",
        p, as_dict=1
    )
    if not recs: return cols, []

    SM = {
        "Present":      ("present_days",      1,   "P"),
        "Absent":       ("absent_days",       1,   "A"),
        "Weekly Off":   ("weekly_off_days",   1,   "WO"),
        "Holiday":      ("holiday_days",      1,   "H"),
        "LWP":          ("lwp_days",          1,   "LWP"),
        "Earned Leave": ("earned_leave_days", 1,   "EL"),
        "Casual Leave": ("casual_leave_days", 1,   "CL"),
        "Comp Off":     ("comp_off_days",     1,   "CO"),
        "On Tour":      ("on_tour_days",      1,   "OT"),
    }

    ed, eo = {}, []
    for row in recs:
        emp = row.employee
        day = row.attendance_date.day if hasattr(row.attendance_date, "day") else int(str(row.attendance_date)[8:10])
        if emp not in ed:
            eo.append(emp)
            ed[emp] = {
                "employee": emp, "employee_name": row.employee_name or "",
                "working_days": last, "present_days": 0.0, "half_days": 0.0,
                "absent_days": 0.0, "earned_leave_days": 0.0, "casual_leave_days": 0.0,
                "comp_off_days": 0.0, "on_tour_days": 0.0,
                "weekly_off_days": 0, "holiday_days": 0, "lwp_days": 0,
            }
        st = row.status
        if st == "Half Day":
            ed[emp]["half_days"]    += 1
            ed[emp]["present_days"] += 0.5
            ed[emp]["absent_days"]  += 0.5
            ed[emp][f"day_{day}"]    = "HD"
        elif st in SM:
            k, v, code = SM[st]
            ed[emp][k] += v
            ed[emp][f"day_{day}"] = code
            if st in ("Earned Leave", "Casual Leave", "Comp Off", "On Tour", "Present"):
                ed[emp]["present_days"] += 1
        else:
            ed[emp][f"day_{day}"] = "-"

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

    # ── Paired summary columns ─────────────────────────────────────────────
    SUMM_PAIRS = [
        ("P",  "present_days",      "A",   "absent_days"),
        ("EL", "earned_leave_days", "CL",  "casual_leave_days"),
        ("OT", "on_tour_days",      "WD",  "working_days"),
        ("H",  "holiday_days",      "LWP", "lwp_days"),
        ("HD", "half_days",         "CO",  "comp_off_days"),
        ("WO", "weekly_off_days",   "",    ""),
    ]

    lgd = "".join(
        f'<span style="margin-right:10px;font-size:11px;"><b>{k}</b> – {v}</span>'
        for k, v in [("P","Present"),("A","Absent"),("HD","Half Day"),("EL","Earned Leave"),
                     ("CL","Casual Leave"),("CO","Comp Off"),("OT","On Tour"),
                     ("WO","Weekly Off"),("H","Holiday"),("LWP","LWP")]
    )

    hdr = (
        f'<div class="hdr"><div class="co">{co}</div>'
        f'<div class="ttl">Monthly Attendance Report</div>'
        f'<div class="per">For the Month of {mo} {yr}</div></div>'
        f'<div class="lgd">{lgd}</div>'
    )

    nd    = len(dcols)
    ncols = 1 + nd + len(SUMM_PAIRS)

    # colgroup
    name_pct   = 17
    summ_total = 14
    day_pct    = f"{(100 - name_pct - summ_total) / nd:.3f}%" if nd else "0%"
    sc_pct     = f"{summ_total / len(SUMM_PAIRS):.2f}%"
    cg  = f'<colgroup><col style="width:{name_pct}%;"/>'
    cg += "".join(f'<col style="width:{day_pct};"/>' for _ in dcols)
    cg += "".join(f'<col style="width:{sc_pct};"/>' for _ in SUMM_PAIRS)
    cg += "</colgroup>"

    # thead
    ch = (
        f'<tr><th style="border:{B};padding:4px 6px;font-size:11px;font-weight:700;'
        f'background:#f0f0f0;text-align:left;vertical-align:top;">'
        f'Employee<br><span style="font-size:10px;font-weight:500;color:#444;">ID</span></th>'
    )
    for c in dcols:
        ch += (
            f'<th style="border:{B};padding:2px 0;font-size:10px;font-weight:700;'
            f'background:#f0f0f0;text-align:center;vertical-align:top;">{c["label"]}</th>'
        )
    for tl, _, bl, __ in SUMM_PAIRS:
        ch += (
            f'<th style="border:{B};padding:2px 1px;font-size:10px;font-weight:700;'
            f'background:#d0d8e0;text-align:center;vertical-align:top;">'
            f'{tl}'
            f'<span style="font-size:9px;display:block;margin-top:2px;">{bl}</span>'
            f'</th>'
        )
    ch += "</tr>"

    COLOR = {
        "A":"#c0392b","LWP":"#8e44ad","WO":"#2980b9","H":"#27ae60",
        "EL":"#d35400","CL":"#16a085","CO":"#7f8c8d","OT":"#2c3e50"
    }

    def _disp(v):
        if v is None or v == "" or v == 0 or v == 0.0: return ""
        return str(int(v)) if isinstance(v, float) and v == int(v) else str(v)

    def _build_rows(page_data):
        rows_html = ""
        for i, row in enumerate(page_data):
            bg = "#f9f9f9" if i % 2 else "#ffffff"
            rows_html += "<tr>"
            rows_html += (
                f'<td style="border:{B};padding:3px 6px;vertical-align:top;background:{bg};">'
                f'<div style="font-size:11px;font-weight:700;">{row.get("employee_name","")}</div>'
                f'<div style="font-size:10px;color:#555;">{row.get("employee","")}</div></td>'
            )
            for c in dcols:
                v     = row.get(c["fieldname"], "") or ""
                color = COLOR.get(v, "#000")
                rows_html += (
                    f'<td style="border:{B};font-size:10px;font-weight:700;text-align:center;'
                    f'padding:2px;background:{bg};color:{color};vertical-align:top;">{v}</td>'
                )
            for tl, tfn, bl, bfn in SUMM_PAIRS:
                tv = _disp(row.get(tfn))
                bv = _disp(row.get(bfn)) if bfn else ""
                rows_html += (
                    f'<td style="border:{B};font-size:10px;font-weight:700;text-align:center;'
                    f'padding:2px;background:#eef2f7;vertical-align:top;">'
                    f'{tv}'
                    f'<span style="font-size:9px;display:block;margin-top:2px;">{bv}</span>'
                    f'</td>'
                )
            rows_html += "</tr>"
        return rows_html

    def _make_table(page_data):
        return (
            f'<table style="width:100%;table-layout:fixed;border-collapse:collapse;margin-top:6px;">'
            f'{cg}<thead>{ch}</thead><tbody>'
            + (_build_rows(page_data) if page_data
               else f'<tr><td colspan="{ncols}" class="nd">No data for this period</td></tr>')
            + '</tbody></table>'
        )

    if not data:
        body = hdr + _make_table([])
    else:
        FIRST, OTHER = 26, 32
        pages, idx, first = [], 0, True
        while idx < len(data):
            lim = FIRST if first else OTHER
            pages.append(data[idx: idx + lim])
            idx += lim
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
    doc = frappe.get_doc({"doctype": "File", "file_name": fn, "is_private": 0, "file_url": f"/files/{fn}"})
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return doc.file_url


@frappe.whitelist()
def print_report(filters):
    if isinstance(filters, str):
        filters = json.loads(filters)
    cols, data = _get_data(filters)
    return _save_pdf(
        _build_html(cols, data, _company_label(filters), filters.get("month", ""), filters.get("year", "")),
        "Monthly_Attendance_Report"
    )