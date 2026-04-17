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
# Day-breakdown chips definition
# Each entry: (fieldname_on_slip, short_label, is_currency, is_net_salary)
# These map directly to Salary Slip fields fetched in the slip query.
# ---------------------------------------------------------------------------

DAY_CHIPS = [
    ("payment_days",        "PD",   False, False),
    ("total_working_days",  "WD",   False, False),
    ("absent_days",         "AB",   False, False),
    ("total_lwp",           "LWP",  False, False),
    ("present_days",        "PR",   False, False),
    ("total_earned_leaves", "EL",   False, False),
    ("total_casual_leaves", "CL",   False, False),
    ("total_comp_off",      "CO",   False, False),
    ("total_earned_comp_off","ECO", False, False),
    ("total_half_days",     "HD",   False, False),
    ("total_on_tour",       "T",    False, False),
    ("total_holidays",      "HOL",  False, False),
    ("weekly_offs_taken",   "WO",   False, False),
]

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
# Fetch dynamic salary components
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

    # ── Build report columns ──────────────────────────────────────────────
    cols = [
        _col("Employee",           "employee",           w=150),
        _col("Employee Name",      "employee_name",      w=200),
        # Day breakdown columns
        _col("Payment Days",       "payment_days",       "Float", 100, precision=2),
        _col("Working Days",       "total_working_days", "Float", 100, precision=2),
        _col("Absent Days",        "absent_days",        "Float", 100, precision=2),
        _col("LWP",                "total_lwp",          "Float", 100, precision=2),
        _col("Present Days",       "present_days",       "Float", 100, precision=2),
        _col("Earned Leave",       "total_earned_leaves","Float", 100, precision=2),
        _col("Casual Leave",       "total_casual_leaves","Float", 100, precision=2),
        _col("Comp Off Taken",     "total_comp_off",     "Float", 100, precision=2),
        _col("Earned Comp Off",    "total_earned_comp_off","Float",100, precision=2),
        _col("Half Days",          "total_half_days",    "Float", 100, precision=2),
        _col("On Tour",            "total_on_tour",      "Float", 100, precision=2),
        _col("Holidays",           "total_holidays",     "Float", 100, precision=2),
        _col("Weekly Offs Taken",  "weekly_offs_taken",  "Float", 100, precision=2),
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

    # ── All day fields to select from DB ─────────────────────────────────
    day_fields_select = ", ".join(
        "ss.{fn}".format(fn=chip[0]) for chip in DAY_CHIPS
    )

    slips = frappe.db.sql(
        "SELECT ss.name AS slip, ss.employee, ss.employee_name,"
        "       ss.net_salary,"
        "       {day_fields}"
        " FROM `tabSalary Slip` ss {catj}"
        " WHERE {w}"
        " ORDER BY ss.employee_name".format(
            day_fields=day_fields_select, catj=catj, w=w
        ),
        p, as_dict=1
    )
    if not slips:
        return cols, []

    sn       = [sl["slip"] for sl in slips]
    comp_map = _fetch_slip_comps(sn)

    data  = []

    # Initialise grand totals for all day fields + financial fields
    grand = {chip[0]: 0.0 for chip in DAY_CHIPS}
    grand.update({
        "gross_earnings": 0.0, "total_deductions": 0.0,
        "employer_total": 0.0, "net_salary": 0.0,
    })
    for name, abbr in earn_comps:    grand[_fn("e", abbr)] = 0.0
    for name, abbr in emp_ded_comps: grand[_fn("d", abbr)] = 0.0
    for name, abbr in empr_comps:    grand[_fn("r", abbr)] = 0.0

    for sl in slips:
        sc  = comp_map.get(sl["slip"], {})
        row = {
            "employee":      sl["employee"],
            "employee_name": sl["employee_name"],
            "net_salary":    flt(sl["net_salary"], 2),
        }

        # Copy all day fields from slip
        for chip in DAY_CHIPS:
            fn = chip[0]
            val = flt(sl.get(fn) or 0, 2)
            row[fn] = val
            grand[fn] += val

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

        grand["net_salary"] += flt(sl["net_salary"], 2)
        data.append(row)

    if data:
        grand_row = {"employee": "", "employee_name": "Grand Total", "bold": 1}
        grand_row.update({k: flt(v, 2) for k, v in grand.items()})
        data.append(grand_row)

    return cols, data


def execute(filters=None):
    return _get_data(filters or {})


# ---------------------------------------------------------------------------
# CSS  — print format only
# ---------------------------------------------------------------------------

_CSS = """<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family: Arial, sans-serif; font-size: 10px; color: #000; background: #fff; width: 100%; }

/* ── Page header ── */
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

/* ── Main table ── */
table.main {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    table-layout: fixed;
}
table.main th, table.main td {
    vertical-align: middle;
    padding: 2px 3px;
    font-size: 9px;
}

/* ── Section subheader row ── */
th.sect-hdr {
    background: #2c3e6b;
    color: #fff;
    font-weight: 700;
    font-size: 8px;
    text-align: center;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    padding: 2px 3px;
    border-top: 1px solid #000;
    border-bottom: 1px solid #000;
    white-space: nowrap;
    overflow: hidden;
}
th.sect-hdr.s-att  { background: #3d5a80; }
th.sect-hdr.s-earn { background: #2d6a4f; }
th.sect-hdr.s-ded  { background: #7b2d00; }
th.sect-hdr.s-empr { background: #5c4033; }
th.sect-hdr.s-net  { background: #1a1a2e; }

/* section-left border only on leftmost column of each section */
th.sect-hdr.sect-left  { border-left: 1px solid #000; }
th.sect-hdr.sect-right { border-right: 1px solid #000; }
th.sect-hdr.sect-mid   { border-left: 1px dashed rgba(255,255,255,0.3); border-right: none; }

/* ── Sr / Employee header cells ── */
th.h-sr {
    background: #e0e0e0;
    font-weight: 700;
    text-align: center;
    font-size: 9px;
    border: 1px solid #000;
    white-space: nowrap;
}
th.h-emp {
    background: #e0e0e0;
    font-weight: 700;
    text-align: left;
    font-size: 9px;
    border-top: 1px solid #000;
    border-bottom: 1px solid #000;
    border-left: none;
    border-right: 1px solid #000;
}

/* ── Chip cells ── */
/* row1 = label row (top half of zigzag), row2 = value row (bottom half) */
td.chip-r1, td.chip-r2 {
    white-space: normal;
    word-break: break-all;
    overflow: visible;
    vertical-align: middle;
    padding: 2px 3px;
}
td.chip-r1 {
    border-top: 1px solid #000;
    border-bottom: 1px dashed #aaa;
}
td.chip-r2 {
    border-top: none;
    border-bottom: 1px solid #000;
}
/* section boundary: solid left on first chip of each section */
td.sect-left  { border-left: 1px solid #000; }
td.sect-right { border-right: 1px solid #000; }
td.sect-mid   { border-left: 1px dashed #aaa; border-right: none; }

/* grand total row background */
td.grand { background: #e8e8e8 !important; }

/* ── Chip label / value typography ── */
.ck {
    display: block;
    font-weight: 700;
    font-size: 8px;
    color: #222;
    line-height: 1.25;
    white-space: nowrap;
}
.cv {
    display: block;
    font-size: 9px;
    color: #333;
    line-height: 1.25;
}

/* Net salary highlight chip */
.ns-lbl {
    display: block;
    background: #1a1a2e;
    color: #aaa;
    border-radius: 3px 3px 0 0;
    padding: 1px 3px 0;
    font-size: 8px;
    font-weight: 700;
    text-align: center;
}
.ns-val {
    display: block;
    background: #1a1a2e;
    color: #fff;
    border-radius: 0 0 3px 3px;
    padding: 0 3px 1px;
    font-size: 9px;
    font-weight: 700;
    text-align: center;
}

/* Sr / Employee cells */
td.sr-cell {
    text-align: center;
    vertical-align: middle;
    font-size: 8px;
    color: #444;
    border-top: 1px solid #000;
    border-bottom: 1px solid #000;
    border-left: 1px solid #000;
    border-right: 1px solid #000;
}
td.sr-cell.grand { background: #e8e8e8; }

td.emp-cell {
    vertical-align: top;
    padding: 4px 5px;
    text-align: left;
    word-break: break-word;
    white-space: normal;
    border-top: 1px solid #000;
    border-bottom: 1px solid #000;
    border-left: none;
    border-right: 1px solid #000;
}
td.emp-cell.grand { background: #e8e8e8; }

/* ── Legend ── */
.legend {
    margin-top: 10px;
    padding: 5px 8px;
    border: 1px solid #bbb;
    background: #f9f9f9;
    font-size: 8.5px;
}
.legend-title { font-weight: 700; font-size: 9px; margin-bottom: 3px; }
.legend-body  { line-height: 1.7; }

/* ── Footer ── */
.pg-foot { text-align: right; font-size: 8.5px; color: #555; margin-top: 3px; }
.sig { display: flex; justify-content: space-between; margin-top: 24px; }
.sig-box  { text-align: center; width: 160px; }
.sig-line { border-top: 1px solid #000; margin-bottom: 3px; }
.sig-lbl  { font-size: 10px; color: #333; }
</style>"""


# ---------------------------------------------------------------------------
# HTML builder
# ---------------------------------------------------------------------------

def _build_html(cols, data, co, mo, yr,
                earn_comps=None, emp_ded_comps=None, empr_comps=None):

    if earn_comps is None or emp_ded_comps is None or empr_comps is None:
        earn_comps, emp_ded_comps, empr_comps = [], [], []
        SKIP = {
            "employee","employee_name",
            "gross_earnings","total_deductions","employer_total","net_salary",
        }
        for chip in DAY_CHIPS:
            SKIP.add(chip[0])
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

    # ──────────────────────────────────────────────────────────────────────
    # Build section-aware chip list
    # Each chip: dict with keys:
    #   fk, lbl, is_cur, is_ns, section
    # section ∈ {"att","earn","ded","empr","net"}
    # ──────────────────────────────────────────────────────────────────────
    all_chips = []

    # Attendance section
    for fn, lbl, is_cur, is_ns in DAY_CHIPS:
        all_chips.append(dict(fk=fn, lbl=lbl, is_cur=is_cur, is_ns=is_ns, section="att"))

    # Earnings section
    for name, abbr in earn_comps:
        all_chips.append(dict(fk=_fn("e", abbr), lbl=abbr, is_cur=True,  is_ns=False, section="earn"))
    all_chips.append(dict(fk="gross_earnings",  lbl="GE",  is_cur=True,  is_ns=False, section="earn"))

    # Deductions section
    for name, abbr in emp_ded_comps:
        all_chips.append(dict(fk=_fn("d", abbr), lbl=abbr, is_cur=True,  is_ns=False, section="ded"))
    all_chips.append(dict(fk="total_deductions", lbl="TD",  is_cur=True,  is_ns=False, section="ded"))

    # Employer section (only if present)
    if empr_comps:
        for name, abbr in empr_comps:
            all_chips.append(dict(fk=_fn("r", abbr), lbl=abbr, is_cur=True, is_ns=False, section="empr"))
        all_chips.append(dict(fk="employer_total", lbl="ES", is_cur=True, is_ns=False, section="empr"))

    # Net salary (always last, its own section)
    all_chips.append(dict(fk="net_salary", lbl="NS", is_cur=True, is_ns=True, section="net"))

    n_chips = len(all_chips)

    # ── Assign border classes per chip ───────────────────────────────────
    # Determine left/right border class for each chip index
    # sect-left  → first chip in a section  → solid left border
    # sect-right → last chip in a section   → solid right border
    # sect-mid   → middle chips             → dashed left, no right

    def _border_class(i):
        cur_sec = all_chips[i]["section"]
        # is first in section?
        is_first = (i == 0) or (all_chips[i-1]["section"] != cur_sec)
        # is last in section?
        is_last  = (i == n_chips - 1) or (all_chips[i+1]["section"] != cur_sec)
        if is_first and is_last:
            return "sect-left sect-right"
        elif is_first:
            return "sect-left"
        elif is_last:
            return "sect-right"
        else:
            return "sect-mid"

    border_classes = [_border_class(i) for i in range(n_chips)]

    # ── Split into zigzag row1 / row2 ────────────────────────────────────
    # row1 = chips at even index, row2 = chips at odd index
    # We store the original index so border_classes still lines up
    row1 = [(i, c) for i, c in enumerate(all_chips) if i % 2 == 0]
    row2 = [(i, c) for i, c in enumerate(all_chips) if i % 2 == 1]
    # pad row2 to same length as row1 with None placeholders
    while len(row2) < len(row1):
        row2.append(None)

    n_cols = len(row1)   # number of td columns

    # ── Column group widths ───────────────────────────────────────────────
    # Day chips: fixed narrow (attendance numbers are small)
    # Component chips: fluid, computed from remaining space
    # NS: fixed wide

    DAY_COL_W_PCT  = 2.0   # per day chip
    NS_COL_W_PCT   = 4.0   # net salary chip
    SR_PCT         = 2.0
    EMP_PCT        = 11.0

    n_day_in_row1  = sum(1 for _, c in row1 if c and c["section"] == "att")
    n_comp_in_row1 = sum(1 for _, c in row1 if c and c["section"] in ("earn","ded","empr"))
    n_ns_in_row1   = sum(1 for _, c in row1 if c and c["section"] == "net")

    # Also count from row2
    n_day_in_row2  = sum(1 for x in row2 if x and x[1]["section"] == "att")
    n_comp_in_row2 = sum(1 for x in row2 if x and x[1]["section"] in ("earn","ded","empr"))
    n_ns_in_row2   = sum(1 for x in row2 if x and x[1]["section"] == "net")

    total_day_cols  = n_day_in_row1 + n_day_in_row2
    total_ns_cols   = n_ns_in_row1 + n_ns_in_row2
    total_comp_cols = n_comp_in_row1 + n_comp_in_row2

    day_pct_total  = total_day_cols * DAY_COL_W_PCT
    ns_pct_total   = total_ns_cols  * NS_COL_W_PCT
    det_total_pct  = 100.0 - SR_PCT - EMP_PCT
    comp_pct_avail = det_total_pct - day_pct_total - ns_pct_total
    comp_w_each    = (comp_pct_avail / total_comp_cols) if total_comp_cols else comp_pct_avail

    def _chip_w(chip):
        if chip is None: return DAY_COL_W_PCT
        sec = chip["section"]
        if sec == "att":  return DAY_COL_W_PCT
        if sec == "net":  return NS_COL_W_PCT
        return comp_w_each

    cg  = '<col style="width:{0}%;">'.format(SR_PCT)
    cg += '<col style="width:{0}%;">'.format(EMP_PCT)
    for _, c in row1:
        cg += '<col style="width:{0:.3f}%;">'.format(_chip_w(c))

    # ── Section subheader: compute colspan per section in row1 + row2 ────
    # We need to know how many *columns* (row1 slots) each section spans.
    # A column slot i covers row1[i] and row2[i].
    # A section's colspan = number of column slots that have at least one chip from it.

    sec_order = ["att", "earn", "ded"]
    if empr_comps:
        sec_order.append("empr")
    sec_order.append("net")

    sec_labels = {
        "att":  "Attendance",
        "earn": "Earnings",
        "ded":  "Deductions",
        "empr": "Employer",
        "net":  "Net Salary",
    }
    sec_colors = {
        "att":  "s-att",
        "earn": "s-earn",
        "ded":  "s-ded",
        "empr": "s-empr",
        "net":  "s-net",
    }

    # For each col slot, determine which sections appear in it
    # (one slot can have chips from different sections if zigzag splits them)
    # We treat a slot as belonging to a section if EITHER row1 or row2 chip is from it.
    # We then group consecutive slots by their "primary" section.
    # Primary = row1 chip's section if it exists, else row2 chip's section.
    col_sections = []
    for slot_i, (orig_i, c1) in enumerate(row1):
        r2_entry = row2[slot_i]
        r2_chip  = r2_entry[1] if r2_entry else None
        sec1 = c1["section"] if c1 else None
        sec2 = r2_chip["section"] if r2_chip else None
        primary = sec1 or sec2
        col_sections.append(primary)

    # Build consecutive groups for subheader colspan
    subhdr_groups = []  # list of (section, colspan)
    if col_sections:
        cur_sec   = col_sections[0]
        cur_count = 1
        for s in col_sections[1:]:
            if s == cur_sec:
                cur_count += 1
            else:
                subhdr_groups.append((cur_sec, cur_count))
                cur_sec   = s
                cur_count = 1
        subhdr_groups.append((cur_sec, cur_count))

    # ── Value helper ─────────────────────────────────────────────────────
    def _v(row, key, currency=False):
        val = row.get(key)
        try:
            fv = float(val or 0)
            if currency: return "{0:,.2f}".format(fv)
            return str(int(fv)) if fv == int(fv) else "{0:.2f}".format(fv)
        except (TypeError, ValueError):
            return "0"

    def _chip_inner(lbl, val, is_ns=False):
        if is_ns:
            return (
                '<span class="ns-lbl">{lbl}</span>'
                '<span class="ns-val">{val}</span>'
            ).format(lbl=lbl, val=val)
        return (
            '<span class="ck">{lbl}</span>'
            '<span class="cv">{val}</span>'
        ).format(lbl=lbl, val=val)

    def _chip_td(chip, orig_i, row, is_row1, is_grand=False):
        """Render a single chip <td>."""
        grand_cls = " grand" if is_grand else ""
        row_cls   = "chip-r1" if is_row1 else "chip-r2"
        brd_cls   = border_classes[orig_i]
        if chip is None:
            # placeholder cell — just blank with borders
            return '<td class="{rc} {bc}{gc}"></td>'.format(
                rc=row_cls, bc=brd_cls, gc=grand_cls)
        lbl   = chip["lbl"]
        val   = _v(row, chip["fk"], currency=chip["is_cur"])
        inner = _chip_inner(lbl, val, chip["is_ns"])
        return '<td class="{rc} {bc}{gc}">{inner}</td>'.format(
            rc=row_cls, bc=brd_cls, gc=grand_cls, inner=inner)

    def _emp_inner(row):
        name = row.get("employee_name", "")
        eid  = row.get("employee", "")
        if eid:
            return (
                '<span style="font-size:10px;font-weight:700;display:block;'
                'line-height:1.4;word-break:break-word;">{name}</span>'
                '<span style="font-size:8px;color:#555;font-family:monospace;'
                'display:block;line-height:1.3;">{eid}</span>'
            ).format(name=name, eid=eid)
        return '<span style="font-size:10px;font-weight:700;">{name}</span>'.format(name=name)

    def _render_employee_rows(row, sr_num, is_grand=False):
        grand_cls = " grand" if is_grand else ""
        sr_val    = "" if is_grand else str(sr_num)

        # Sr cell spans 2 rows; note: no dashed border here — always solid
        sr_td = (
            '<td rowspan="2" class="sr-cell{gc}">{v}</td>'
        ).format(gc=grand_cls, v=sr_val)

        # Employee cell spans 2 rows
        emp_td = (
            '<td rowspan="2" class="emp-cell{gc}">{inner}</td>'
        ).format(gc=grand_cls, inner=_emp_inner(row))

        # Row 1 chips
        chips_r1 = "".join(
            _chip_td(c, orig_i, row, True, is_grand)
            for orig_i, c in row1
        )
        # Row 2 chips
        chips_r2 = "".join(
            _chip_td(r2_entry[1] if r2_entry else None,
                     r2_entry[0] if r2_entry else 0,
                     row, False, is_grand)
            for r2_entry in row2
        )

        return (
            "<tr>{sr}{emp}{c1}</tr><tr>{c2}</tr>".format(
                sr=sr_td, emp=emp_td, c1=chips_r1, c2=chips_r2)
        )

    # ── thead: 2 rows — subheader row + blank row for rowspan targets ────
    # Row A: Sr (rowspan=2), Employee (rowspan=2), section subheaders
    # Row B: empty (rowspan targets land here — nothing else needed)

    subhdr_cells = ""
    for sec, span in subhdr_groups:
        lbl   = sec_labels.get(sec, sec)
        color = sec_colors.get(sec, "")
        # border: always solid left on first column of section, solid right on last
        subhdr_cells += (
            '<th class="sect-hdr {color}" colspan="{span}">'
            '{lbl}</th>'
        ).format(color=color, span=span, lbl=lbl)

    thead = (
        '<thead>'
        '<tr>'
        '<th class="h-sr"  rowspan="2">Sr</th>'
        '<th class="h-emp" rowspan="2">Employee</th>'
        '{subhdr}'
        '</tr>'
        '<tr></tr>'
        '</thead>'
    ).format(subhdr=subhdr_cells)

    # ── Legend ───────────────────────────────────────────────────────────
    legend_items = [
        ("PD",  "Payment Days"),
        ("WD",  "Working Days"),
        ("AB",  "Absent Days"),
        ("LWP", "Leave Without Pay"),
        ("PR",  "Present Days"),
        ("EL",  "Earned Leave"),
        ("CL",  "Casual Leave"),
        ("CO",  "Comp Off Taken"),
        ("ECO", "Earned Comp Off"),
        ("HD",  "Half Days"),
        ("T",   "On Tour"),
        ("HOL", "Holidays"),
        ("WO",  "Weekly Offs Taken"),
        ("GE",  "Gross Earnings"),
        ("TD",  "Total Deductions"),
        ("ES",  "Employer Share"),
        ("NS",  "Net Salary"),
    ]
    for nm, ab in earn_comps:    legend_items.append((ab, nm))
    for nm, ab in emp_ded_comps: legend_items.append((ab, nm))
    for nm, ab in empr_comps:    legend_items.append((ab, nm))

    seen_lgd = set()
    legend_dedup = []
    for ab, nm in legend_items:
        if ab not in seen_lgd:
            seen_lgd.add(ab)
            legend_dedup.append((ab, nm))

    legend_html = (
        '<div class="legend">'
        '<div class="legend-title">Legend:</div>'
        '<div class="legend-body">{text}</div>'
        '</div>'
    ).format(text=", ".join(
        "<b>{ab}</b>&nbsp;=&nbsp;{nm}".format(ab=ab, nm=nm)
        for ab, nm in legend_dedup
    ))

    # ── Paginate ─────────────────────────────────────────────────────────
    pages = []
    for i in range(0, max(len(detail_rows), 1), ROWS_PER_PAGE):
        pages.append(detail_rows[i: i + ROWS_PER_PAGE])
    if not pages:
        pages = [[]]

    total_pages = len(pages)
    parts       = []
    sr_counter  = 1

    for pn, pr in enumerate(pages):
        is_first  = (pn == 0)
        is_last_p = (pn == len(pages) - 1)

        pb       = '<div style="page-break-before:always;"></div>' if not is_first else ""
        page_hdr = first_hdr_html if is_first else cont_hdr_html

        tbody = "<tbody>"
        for row in pr:
            tbody += _render_employee_rows(row, sr_counter)
            sr_counter += 1
        if is_last_p and grand_row:
            tbody += _render_employee_rows(grand_row, "", is_grand=True)
        tbody += "</tbody>"

        parts.append(
            '{pb}{hdr}'
            '<table class="main"><colgroup>{cg}</colgroup>{thead}{tbody}</table>'
            '<div class="pg-foot">Page {pn} of {tp}</div>'
            '{legend}'.format(
                pb=pb, hdr=page_hdr, cg=cg,
                thead=thead, tbody=tbody,
                pn=pn + 1, tp=total_pages,
                legend=legend_html if is_last_p else ""
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
        '<body>{body}{sig}</body></html>'
    ).format(css=_CSS, body="".join(parts), sig=sig)


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