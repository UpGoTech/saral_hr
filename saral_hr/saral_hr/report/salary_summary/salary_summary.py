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

B = "1px solid #000"

_CSS = """<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Arial,sans-serif;font-size:10px;color:#000;background:#fff}
.hdr{text-align:center;border-bottom:2px solid #000;padding:8px 4px 6px;margin-bottom:6px}
.hdr .co{font-size:18px;font-weight:900;letter-spacing:1px;text-transform:uppercase}
.hdr .ttl{font-size:18px;font-weight:700;margin-top:3px}
.hdr .per{font-size:16px;margin-top:2px}
.sig{display:flex;justify-content:space-between;margin-top:24px;padding-top:6px}
.sig-b{text-align:center;width:160px}
.sig-l{border-top:1px solid #000;margin-bottom:3px}
.sig-t{font-size:10px;color:#333}
</style>"""

_SIG = '<div class="sig">' + "".join(
    f'<div class="sig-b"><div class="sig-l"></div><div class="sig-t">{l}</div></div>'
    for l in ["Prepared By", "Checked By", "Authorised Signatory"]
) + '</div>'


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

def _start_date(f):
    m = MONTH_MAP.get(f.get("month", ""))
    y = f.get("year", "")
    return f"{y}-{m:02d}-01" if m and y else None

def _end_date(f):
    import calendar
    m = MONTH_MAP.get(f.get("month", ""))
    y = f.get("year", "")
    if not m or not y:
        return None
    last_day = calendar.monthrange(int(y), m)[1]
    return f"{y}-{m:02d}-{last_day:02d}"

def _company_label(f):
    c = _parse_list(f.get("company"))
    return ", ".join(c) if c else (frappe.defaults.get_global_default("company") or "")

def _fmt(v):
    if v is None or v == "": return ""
    try: return f"{float(v):,.2f}"
    except (TypeError, ValueError): return str(v)


# ---------------------------------------------------------------------------
# Attendance-based day counts — read directly from SUBMITTED Salary Slips
# ---------------------------------------------------------------------------

def _get_attendance_counts_from_slips(f, where_clause, params):
    """
    Sum attendance day fields directly from submitted Salary Slip records.

    Since tabAttendance is not submittable, we read the attendance counts
    that were already captured and stored on each Salary Slip at the time
    it was created/submitted.  This guarantees we only count employees
    whose slips are submitted (docstatus=1) and avoids any dependency on
    tabAttendance docstatus filtering.

    Fields read from tabSalary Slip:
        present_days, absent_days, total_lwp, total_on_tour,
        total_earned_leaves, total_casual_leaves, total_comp_off,
        total_earned_comp_off, weekly_offs_count (weekly offs used in calc),
        total_holidays
    """
    rows = frappe.db.sql(
        f"""
        SELECT
            SUM(ss.present_days)          AS present_days,
            SUM(ss.absent_days)           AS absent_days,
            SUM(ss.total_lwp)             AS lwp_days,
            SUM(ss.total_on_tour)         AS on_tour_days,
            SUM(ss.total_earned_leaves)   AS earned_leaves,
            SUM(ss.total_casual_leaves)   AS casual_leaves,
            SUM(ss.total_comp_off)        AS comp_off,
            SUM(ss.total_earned_comp_off) AS earned_comp_off,
            SUM(ss.weekly_offs_count)     AS weekly_off,
            SUM(ss.total_holidays)        AS total_holidays
        FROM `tabSalary Slip` ss
        WHERE {where_clause}
        """,
        params,
        as_dict=1,
    )

    r = (rows or [{}])[0]
    return {
        "present":        flt(r.get("present_days"),   2),
        "absent":         flt(r.get("absent_days"),    2),
        "lwp":            flt(r.get("lwp_days"),       2),
        "on_tour":        flt(r.get("on_tour_days"),   2),
        "earned_leave":   flt(r.get("earned_leaves"),  2),
        "casual_leave":   flt(r.get("casual_leaves"),  2),
        "comp_off":       flt(r.get("comp_off"),       2),
        "earned_comp_off":flt(r.get("earned_comp_off"),2),
        "weekly_off":     flt(r.get("weekly_off"),     2),
        "total_holidays": flt(r.get("total_holidays"), 2),
    }


# ---------------------------------------------------------------------------
# Holiday count from Holiday List  (kept for reference; now sourced from slips)
# ---------------------------------------------------------------------------

def _get_holiday_count(f):
    """
    Count distinct holidays from all Holiday Lists whose date range
    overlaps the selected month.
    """
    sd = _start_date(f)
    ed = _end_date(f)
    if not sd or not ed:
        return 0

    params = {"sd": sd, "ed": ed}
    result = frappe.db.sql(
        """
        SELECT COUNT(DISTINCT h.holiday_date) AS cnt
        FROM `tabHoliday` h
        INNER JOIN `tabHoliday List` hl ON hl.name = h.parent
        WHERE
            h.holiday_date BETWEEN %(sd)s AND %(ed)s
            AND hl.from_date <= %(ed)s
            AND hl.to_date   >= %(sd)s
        """,
        params,
    )
    return int((result or [[0]])[0][0])


# ---------------------------------------------------------------------------
# Core data function
# ---------------------------------------------------------------------------

def _get_data(f):
    cols = [
        _col("Earnings",      "description",     w=255),
        _col("Amount",        "amount",  "Float", 130, precision=2),
        {"label": " ", "fieldname": "spacer",  "fieldtype": "Data", "width": 12},
        _col("Deductions",    "ded_description", w=255),
        _col("Amount",        "ded_amount", "Float", 130, precision=2),
        {"label": " ", "fieldname": "spacer2", "fieldtype": "Data", "width": 12},
        _col("Other Details", "oth_description", w=255),
        _col("Value",         "oth_amount", "Float", 120, precision=2),
    ]

    if not f.get("company"):
        return cols, []

    # ── Build WHERE clause — only SUBMITTED slips (docstatus=1) ────────────
    p     = {}
    conds = ["ss.docstatus=1"]

    sd = _start_date(f)
    if sd:
        p["start_date"] = sd
        conds.append("ss.start_date=%(start_date)s")

    co = _parse_list(f.get("company"))
    if co:
        p["companies"] = tuple(co)
        conds.append("ss.company IN %(companies)s")

    cat = f.get("category")
    if cat:
        p["category"] = cat
        conds.append(
            "ss.employee IN (SELECT name FROM `tabCompany Link` WHERE category=%(category)s)"
        )

    divs = _parse_list(f.get("division"))
    if divs:
        p["divisions"] = tuple(divs)
        conds.append(
            "ss.employee IN (SELECT name FROM `tabCompany Link` "
            "WHERE division IN %(divisions)s OR department IN %(divisions)s)"
        )

    w = " AND ".join(conds)

    slip_count = frappe.db.sql(
        f"SELECT COUNT(*) FROM `tabSalary Slip` ss WHERE {w}", p
    )[0][0]

    if not slip_count:
        return cols, []

    # ── Salary component helpers ────────────────────────────────────────────
    def _comps(field, xj=""):
        return [
            r[0] for r in frappe.db.sql(
                f"SELECT DISTINCT sd.salary_component "
                f"FROM `tabSalary Slip` ss "
                f"INNER JOIN `tabSalary Details` sd ON sd.parent=ss.name "
                f"  AND sd.parenttype='Salary Slip' AND sd.parentfield='{field}' "
                f"{xj} WHERE {w} ORDER BY sd.salary_component",
                p, as_list=1
            )
        ]

    def _tots(field, xj=""):
        return {
            r.c: flt(r.t)
            for r in frappe.db.sql(
                f"SELECT sd.salary_component AS c, SUM(sd.amount) AS t "
                f"FROM `tabSalary Slip` ss "
                f"INNER JOIN `tabSalary Details` sd ON sd.parent=ss.name "
                f"  AND sd.parenttype='Salary Slip' AND sd.parentfield='{field}' "
                f"{xj} WHERE {w} GROUP BY sd.salary_component",
                p, as_dict=1
            )
        }

    # Exclude employer-contribution components from employee deductions panel
    dj = (
        "INNER JOIN `tabSalary Component` sc "
        "ON sc.name=sd.salary_component AND sc.employer_contribution=0"
    )

    ec = _comps("earnings")
    dc = _comps("deductions", dj)
    et = _tots("earnings")
    dt = _tots("deductions", dj)

    er = [(c, et.get(c, 0.0)) for c in ec]
    dr = [(c, dt.get(c, 0.0)) for c in dc]
    ge = sum(v for _, v in er)
    gd = sum(v for _, v in dr)

    # ── Salary Slip aggregate totals ─────────────────────────────────────────
    # net_salary on each slip is already rounded (half-up) at creation time.
    # SUM(net_salary) gives the true total net pay.
    st = (frappe.db.sql(
        f"SELECT COUNT(DISTINCT ss.employee) AS te, "
        f"SUM(ss.net_salary) AS ns, "
        f"SUM(ss.payment_days) AS tp "
        f"FROM `tabSalary Slip` ss WHERE {w}",
        p, as_dict=1
    ) or [{}])[0]

    # ── Attendance counts from submitted Salary Slips ────────────────────────
    att = _get_attendance_counts_from_slips(f, w, p)

    present_days    = att.get("present",         0.0)
    absent_days     = att.get("absent",           0.0)
    lwp_days        = att.get("lwp",              0.0)
    on_tour_days    = att.get("on_tour",          0.0)
    earned_leaves   = att.get("earned_leave",     0.0)
    casual_leaves   = att.get("casual_leave",     0.0)
    comp_off        = att.get("comp_off",         0.0)
    earned_comp_off = att.get("earned_comp_off",  0.0)
    weekly_off      = att.get("weekly_off",       0.0)
    total_holidays  = att.get("total_holidays",   0.0)

    oth_pairs = [
        ("Total Net Salary",       flt(st.get("ns"), 2)),
        ("Total Employees",        int(st.get("te") or 0)),
        ("Total Payment Days",     flt(st.get("tp"), 2)),
        ("Total Present Days",     present_days),
        ("Total Absent Days",      absent_days),
        ("Total LWP Days",         lwp_days),
        ("Total On Tour Days",     on_tour_days),
        ("Total Earned Leaves",    earned_leaves),
        ("Total Casual Leaves",    casual_leaves),
        ("Total Comp Off",         comp_off),
        ("Total Earned Comp Off",  earned_comp_off),
        ("Total Weekly Off",       weekly_off),
        ("Total Holidays",         total_holidays),
    ]

    n_rows = max(len(er), len(dr), len(oth_pairs), 1)
    data   = []

    for i in range(n_rows):
        ec2, ea = er[i]        if i < len(er)        else ("", None)
        dc2, da = dr[i]        if i < len(dr)        else ("", None)
        ol,  ov = oth_pairs[i] if i < len(oth_pairs) else ("", None)
        data.append({
            "description":     ec2,
            "amount":          flt(ea, 2) if ec2 else None,
            "spacer":          "",
            "ded_description": dc2,
            "ded_amount":      flt(da, 2) if dc2 else None,
            "spacer2":         "",
            "oth_description": ol,
            "oth_amount":      ov,
            "_row_type":       "component",
        })

    # Grand total row — net payable = gross earnings - gross employee deductions
    data.append({
        "description":     "Grand Total",
        "amount":          flt(ge, 2),
        "spacer":          "",
        "ded_description": "Grand Total",
        "ded_amount":      flt(gd, 2),
        "spacer2":         "",
        "oth_description": "Net Payable",
        "oth_amount":      flt(ge - gd, 2),
        "bold":            1,
        "_row_type":       "grand_total",
    })

    return cols, data


# ---------------------------------------------------------------------------
# Frappe report entry-point
# ---------------------------------------------------------------------------

def execute(filters=None):
    return _get_data(filters or {})


# ---------------------------------------------------------------------------
# PDF renderer — three-panel layout (Earnings | Deductions | Other Details)
# ---------------------------------------------------------------------------

def _build_html(cols, data, co, mo, yr):
    hdr = (
        f'<div class="hdr">'
        f'<div class="co">{co}</div>'
        f'<div class="ttl">Salary Summary</div>'
        f'<div class="per">For the Month of {mo} {yr}</div>'
        f'</div>'
    )

    if not data:
        return (
            f'<!DOCTYPE html><html><head><meta charset="UTF-8">{_CSS}</head>'
            f'<body>{hdr}'
            f'<p style="text-align:center;padding:30px;color:#888;font-size:10px;">'
            f'No salary slips found for this period.</p>'
            f'{_SIG}</body></html>'
        )

    earn = [r for r in data if r.get("_row_type") == "component" and r.get("description")]
    ded  = [r for r in data if r.get("_row_type") == "component" and r.get("ded_description")]
    gt   = next((r for r in data if r.get("_row_type") == "grand_total"), {})
    oth  = [r for r in data if r.get("_row_type") == "component" and r.get("oth_description")]

    ROW_COLOURS = ["#ffffff", "#f0f0f0"]

    FS  = "font-size:10px;"
    PAD = "padding:5px 7px;"

    HD  = f"border:{B};{PAD}{FS}font-weight:700;background:#e8e8e8;color:#000;text-align:center;letter-spacing:0.5px;"
    THL = f"border:{B};{PAD}{FS}font-weight:700;background:#f0f0f0;color:#000;text-align:left;"
    THR = f"border:{B};{PAD}{FS}font-weight:700;background:#f0f0f0;color:#000;text-align:right;"
    GTL = f"border:{B};border-top:2px solid #000;{PAD}{FS}font-weight:700;background:#e8e8e8;color:#000;text-align:left;"
    GTR = f"border:{B};border-top:2px solid #000;{PAD}{FS}font-weight:700;background:#e8e8e8;color:#000;text-align:right;"
    GAP = f"width:10px;border:none;padding:0;background:transparent;"

    oth_order = [
        "Total Net Salary",
        "Total Employees",
        "Total Payment Days",
        "Total Present Days",
        "Total Absent Days",
        "Total LWP Days",
        "Total On Tour Days",
        "Total Earned Leaves",
        "Total Casual Leaves",
        "Total Comp Off",
        "Total Earned Comp Off",
        "Total Weekly Off",
        "Total Holidays",
    ]
    oth_map  = {r.get("oth_description"): r for r in oth}
    oth_list = []
    for lbl in oth_order:
        r = oth_map.get(lbl, {})
        if not r:
            continue
        val  = r.get("oth_amount")
        disp = (
            str(int(val))
            if lbl in ("Total Employees",) and val is not None
            else (_fmt(val) if val is not None else "")
        )
        oth_list.append((lbl, disp))

    # Net payable = grand-total earnings minus grand-total employee deductions
    net_payable = flt(gt.get("amount", 0)) - flt(gt.get("ded_amount", 0))
    nrows       = max(len(earn), len(ded), len(oth_list))

    def _tdl(row_idx):
        bg = ROW_COLOURS[row_idx % 2]
        return f"border:{B};{PAD}{FS}color:#000;text-align:left;background:{bg};"

    def _tdr(row_idx):
        bg = ROW_COLOURS[row_idx % 2]
        return f"border:{B};{PAD}{FS}color:#000;text-align:right;background:{bg};"

    def _ec(i, row_idx):
        tdl, tdr = _tdl(row_idx), _tdr(row_idx)
        if i < len(earn):
            r = earn[i]
            return (
                f'<td style="{tdl}">{r.get("description") or ""}</td>'
                f'<td style="{tdr}">'
                f'{_fmt(r.get("amount")) if r.get("amount") is not None else ""}'
                f'</td>'
            )
        return f'<td style="{tdl}"></td><td style="{tdr}"></td>'

    def _dc(i, row_idx):
        tdl, tdr = _tdl(row_idx), _tdr(row_idx)
        if i < len(ded):
            r = ded[i]
            return (
                f'<td style="{tdl}">{r.get("ded_description") or ""}</td>'
                f'<td style="{tdr}">'
                f'{_fmt(r.get("ded_amount")) if r.get("ded_amount") is not None else ""}'
                f'</td>'
            )
        return f'<td style="{tdl}"></td><td style="{tdr}"></td>'

    def _oc(i, row_idx):
        tdl, tdr = _tdl(row_idx), _tdr(row_idx)
        if i < len(oth_list):
            lbl, disp = oth_list[i]
            return f'<td style="{tdl}">{lbl}</td><td style="{tdr}">{disp}</td>'
        return f'<td style="{tdl}"></td><td style="{tdr}"></td>'

    rows_html = ""
    for i in range(nrows):
        rows_html += (
            f"<tr>"
            f"{_ec(i, i)}"
            f"<td style='{GAP}'></td>"
            f"{_dc(i, i)}"
            f"<td style='{GAP}'></td>"
            f"{_oc(i, i)}"
            f"</tr>"
        )

    rows_html += (
        f"<tr>"
        f'<td style="{GTL}">Grand Total</td>'
        f'<td style="{GTR}">{_fmt(gt.get("amount"))}</td>'
        f'<td style="{GAP}"></td>'
        f'<td style="{GTL}">Grand Total</td>'
        f'<td style="{GTR}">{_fmt(gt.get("ded_amount"))}</td>'
        f'<td style="{GAP}"></td>'
        f'<td style="{GTL}">Net Payable</td>'
        f'<td style="{GTR}">{_fmt(net_payable)}</td>'
        f"</tr>"
    )

    table = (
        f'<table style="width:100%;border-collapse:collapse;margin-top:6px;">'
        f'<thead><tr>'
        f'<th colspan="2" style="{HD}">EARNINGS</th>'
        f'<th style="{GAP}"></th>'
        f'<th colspan="2" style="{HD}">DEDUCTIONS</th>'
        f'<th style="{GAP}"></th>'
        f'<th colspan="2" style="{HD}">OTHER DETAILS</th>'
        f'</tr><tr>'
        f'<th style="{THL}">Description</th><th style="{THR}">Amount</th>'
        f'<th style="{GAP}"></th>'
        f'<th style="{THL}">Description</th><th style="{THR}">Amount</th>'
        f'<th style="{GAP}"></th>'
        f'<th style="{THL}">Description</th><th style="{THR}">Value</th>'
        f'</tr></thead>'
        f'<tbody>{rows_html}</tbody>'
        f'</table>'
    )

    return (
        f'<!DOCTYPE html><html><head><meta charset="UTF-8">{_CSS}</head>'
        f'<body>{hdr}{table}{_SIG}</body></html>'
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
        "doctype":    "File",
        "file_name":  fn,
        "is_private": 0,
        "file_url":   f"/files/{fn}",
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
    return _save_pdf(html, "Salary_Summary")