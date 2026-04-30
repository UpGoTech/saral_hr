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

ROWS_PER_PAGE = 13

# ---------------------------------------------------------------------------
# Day-breakdown columns grouped into pairs for stacked display
# Each tuple: (top_fieldname, top_label, bottom_fieldname, bottom_label, col_key)
# ---------------------------------------------------------------------------

DAY_PAIRS = [
    ("payment_days",        "PD",   "total_working_days",    "WD",   "pd_wd"),
    ("absent_days",         "Abs",  "total_lwp",             "LWP",  "abs_lwp"),
    ("present_days",        "Pres", "total_earned_leaves",   "EL",   "pres_el"),
    ("total_casual_leaves", "CL",   "total_comp_off",        "CO",   "cl_co"),
    ("total_earned_comp_off","ECO", "total_half_days",       "HD",   "eco_hd"),
    ("total_on_tour",       "Tour", "total_holidays",        "Hol",  "tour_hol"),
    ("weekly_offs_taken",   "WO",   None,                    "",     "wo"),
]

# All individual day fieldnames (for grand total accumulation)
ALL_DAY_FNS = [
    "payment_days","total_working_days","absent_days","total_lwp",
    "present_days","total_earned_leaves","total_casual_leaves","total_comp_off",
    "total_earned_comp_off","total_half_days","total_on_tour","total_holidays",
    "weekly_offs_taken",
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
    return (
        "{0}-{1:02d}-01".format(y, m),
        "{0}-{1:02d}-{2:02d}".format(y, m, calendar.monthrange(y, m)[1]),
    )

def _month_name(m):
    return [
        "January","February","March","April","May","June",
        "July","August","September","October","November","December"
    ][m - 1]

def _sanitize(s):
    return (
        s.strip().lower()
        .replace(" ", "_").replace("-", "_")
        .replace("(", "").replace(")", "")
        .replace("__", "_")
    )

def _company_label(f):
    c = _parse_list(f.get("company"))
    return ", ".join(c) if c else (frappe.defaults.get_global_default("company") or "")


# ---------------------------------------------------------------------------
# _get_components — called by payroll_report._register_tc_extra
# Returns (earn_comps, emp_ded_comps, empr_comps) as sorted lists.
# Transaction Checklist uses Additional Salary / Deduction doctypes rather
# than Salary Slip component tables, so earn_comps and empr_comps are empty;
# emp_ded_comps returns the distinct Additional Deduction component names
# for the filtered period so payroll_report can pass them back to _build_html.
# ---------------------------------------------------------------------------

def _get_components(where_clause, params):
    """
    Returns:
        earn_comps    : [] — not used by Transaction Checklist
        emp_ded_comps : sorted list of Additional Deduction component names
        empr_comps    : [] — not used by Transaction Checklist
    """
    try:
        rows = frappe.db.sql(
            "SELECT DISTINCT adc.{fn} AS comp"
            " FROM `tabAdditional Deduction Component` adc"
            " INNER JOIN `tabAdditional Deductions` ad ON ad.name = adc.parent"
            " WHERE ad.docstatus = 1".format(
                fn=_discover_child_fields("Additional Deduction Component")[0]
            )
        )
        emp_ded_comps = sorted(r[0] for r in rows if r[0])
    except Exception:
        emp_ded_comps = []

    return [], emp_ded_comps, []

def _fmt_num(v):
    """Format float without currency symbol."""
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
        if fv == 0: return ""
        return str(int(fv)) if fv == int(fv) else "{0:.1f}".format(fv)
    except (TypeError, ValueError): return str(v)


# ---------------------------------------------------------------------------
# Child-table field discovery
# ---------------------------------------------------------------------------

_child_field_cache = {}

def _discover_child_fields(child_doctype):
    if child_doctype in _child_field_cache:
        return _child_field_cache[child_doctype]

    comp_fn = None
    amt_fn  = None

    try:
        meta = frappe.get_meta(child_doctype)
        for df in meta.fields:
            fn  = df.fieldname
            ft  = df.fieldtype
            lbl = (df.label or "").lower()
            if not comp_fn:
                if ft == "Link" and (df.options or "").lower() in ("salary component","salary_component"):
                    comp_fn = fn
                elif ft in ("Data","Link","Select") and any(
                    kw in lbl for kw in ("component","salary component","head","particular")
                ):
                    comp_fn = fn
            if not amt_fn:
                if ft in ("Currency","Float") and any(kw in lbl for kw in ("amount","value","rate")):
                    amt_fn = fn
        if comp_fn and amt_fn:
            _child_field_cache[child_doctype] = (comp_fn, amt_fn)
            return comp_fn, amt_fn
    except Exception:
        pass

    try:
        db_cols = [r[0] for r in frappe.db.sql("DESCRIBE `tab{0}`".format(child_doctype))]
    except Exception:
        db_cols = []

    meta_cols = {
        "name","creation","modified","modified_by","owner",
        "docstatus","parent","parentfield","parenttype","idx",
    }
    comp_candidates = ["salary_component","component","salary_component_name","component_name","head","particular"]
    amt_candidates  = ["amount","value","rate","total"]

    comp_fn = next((c for c in comp_candidates if c in db_cols), None)
    amt_fn  = next((c for c in amt_candidates  if c in db_cols), None)
    if not comp_fn:
        comp_fn = next((c for c in db_cols if c not in meta_cols and c not in amt_candidates), "name")
    if not amt_fn:
        amt_fn = "amount"

    _child_field_cache[child_doctype] = (comp_fn, amt_fn)
    return comp_fn, amt_fn


# ---------------------------------------------------------------------------
# Fetch Additional Salary / Deduction data via Frappe ORM
# ---------------------------------------------------------------------------

def _fetch_additional_data(parent_doctype, child_doctype, year, month, employee_ids=None):
    comp_fn, amt_fn = _discover_child_fields(child_doctype)

    filters = {"docstatus": 1, "year": year, "month": month}
    if employee_ids:
        filters["employee"] = ["in", list(employee_ids)]

    parents = frappe.get_all(parent_doctype, filters=filters, fields=["name","employee"])
    if not parents:
        return [], {}

    parent_names  = [p["name"]     for p in parents]
    emp_by_parent = {p["name"]: p["employee"] for p in parents}

    child_rows = frappe.get_all(
        child_doctype,
        filters={"parent": ["in", parent_names], "parenttype": parent_doctype},
        fields=["parent", comp_fn, amt_fn],
    )

    emp_map    = {}
    components = set()

    for row in child_rows:
        comp_name = row.get(comp_fn) or ""
        amount    = flt(row.get(amt_fn) or 0, 2)
        if not comp_name: continue
        employee = emp_by_parent.get(row.get("parent"))
        if not employee: continue
        components.add(comp_name)
        emp_map.setdefault(employee, {})
        emp_map[employee][comp_name] = flt(emp_map[employee].get(comp_name, 0) + amount, 2)

    return sorted(components), emp_map


# ---------------------------------------------------------------------------
# Core data function
# ---------------------------------------------------------------------------

def _get_data(f):
    # Build report columns (for Frappe grid display)
    cols = [
        _col("Employee",      "employee",      w=130),
        _col("Employee Name", "employee_name", w=200),
    ]
    # Stacked pairs — expose individual day fieldnames for grid
    for fn in ALL_DAY_FNS:
        cols.append(_col(fn.replace("_"," ").title(), fn, "Float", 80, precision=2))

    cols.append(_col("Additional Salary",     "add_salary_combined",  "Data", 220))
    cols.append(_col("Additional Deductions", "add_ded_combined",     "Data", 220))

    if not f.get("company"):
        return cols, []

    s, e = _date_range(f)
    if not s:
        return cols, []

    year  = s[:4]
    month = _month_name(int(s[5:7]))

    p = {"start_date": s, "end_date": e}
    conds = [
        "ss.docstatus = 1",
        "ss.start_date >= %(start_date)s",
        "ss.end_date   <= %(end_date)s",
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
        catj = (
            "INNER JOIN `tabCompany Link` cl_cat "
            "ON cl_cat.name = ss.employee AND cl_cat.category = %(category)s"
        )

    divs = _parse_list(f.get("division"))
    if divs:
        p["divisions"] = tuple(divs)
        conds.append(
            "ss.employee IN ("
            "SELECT name FROM `tabCompany Link` "
            "WHERE division IN %(divisions)s OR department IN %(divisions)s)"
        )

    w = " AND ".join(conds)

    day_select = ", ".join("ss.{fn}".format(fn=fn) for fn in ALL_DAY_FNS)

    slips = frappe.db.sql(
        "SELECT ss.name AS slip, ss.employee, ss.employee_name, {ds}"
        " FROM `tabSalary Slip` ss {catj}"
        " WHERE {w}"
        " ORDER BY ss.employee_name".format(ds=day_select, catj=catj, w=w),
        p, as_dict=1,
    )

    employee_ids = [sl["employee"] for sl in slips] if slips else []

    as_comps, as_map = _fetch_additional_data(
        "Additional Salary", "Additional Salary Component",
        year, month, employee_ids or None,
    )
    ad_comps, ad_map = _fetch_additional_data(
        "Additional Deductions", "Additional Deduction Component",
        year, month, employee_ids or None,
    )

    if not slips:
        return cols, []

    grand = {fn: 0.0 for fn in ALL_DAY_FNS}
    grand.update({"total_add_salary": 0.0, "total_add_deductions": 0.0})

    data = []
    for sl in slips:
        row = {
            "employee":      sl["employee"],
            "employee_name": sl["employee_name"],
        }

        for fn in ALL_DAY_FNS:
            val = flt(sl.get(fn) or 0, 2)
            row[fn] = val
            grand[fn] += val

        # Additional Salary — pipe-separated detail + total
        emp_as   = as_map.get(sl["employee"], {})
        total_s  = 0.0
        as_parts = []
        for comp in as_comps:
            amt = flt(emp_as.get(comp, 0), 2)
            if amt:
                as_parts.append("{0}: {1}".format(comp, "{:,.2f}".format(amt)))
                total_s += amt
        row["add_salary_combined"] = "|".join(as_parts)  # pipe-sep for HTML splitting
        row["_total_add_salary"]   = flt(total_s, 2)
        grand["total_add_salary"] += total_s

        # Additional Deductions — pipe-separated detail + total
        emp_ad   = ad_map.get(sl["employee"], {})
        total_d  = 0.0
        ad_parts = []
        for comp in ad_comps:
            amt = flt(emp_ad.get(comp, 0), 2)
            if amt:
                ad_parts.append("{0}: {1}".format(comp, "{:,.2f}".format(amt)))
                total_d += amt
        row["add_ded_combined"]        = "|".join(ad_parts)
        row["_total_add_deductions"]   = flt(total_d, 2)
        grand["total_add_deductions"] += total_d

        data.append(row)

    if data:
        grand_row = {
            "employee":           "",
            "employee_name":      "Grand Total",
            "add_salary_combined":"",
            "add_ded_combined":   "",
            "_total_add_salary":  flt(grand["total_add_salary"], 2),
            "_total_add_deductions": flt(grand["total_add_deductions"], 2),
            "bold": 1,
        }
        grand_row.update({fn: flt(grand[fn], 2) for fn in ALL_DAY_FNS})
        data.append(grand_row)

    return cols, data


def execute(filters=None):
    return _get_data(filters or {})


# ---------------------------------------------------------------------------
# CSS  — mirrors PF Register style
# ---------------------------------------------------------------------------

_CSS = """<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Arial,sans-serif;font-size:8.5px;color:#000;background:#fff}

.hdr{text-align:center;border-bottom:2px solid #000;padding:5px 4px 4px;margin-bottom:3px;}
.hdr .co{font-size:17px;font-weight:900;letter-spacing:1px;text-transform:uppercase}
.hdr .ttl{font-size:12px;font-weight:700;margin-top:2px}
.hdr .per{font-size:10px;margin-top:1px;color:#333}

.cont-hdr{
    text-align:center;font-size:8.5px;color:#555;
    border-bottom:1px solid #000;padding-bottom:2px;margin-bottom:3px;
}

table.data-tbl{width:100%;border-collapse:collapse;table-layout:fixed;}
table.data-tbl th{
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
}
/* Section group header */
table.data-tbl th.grp-hdr{
    background:#dce6f1;
    font-size:7.5px;
    border-bottom:1px solid #999;
}
table.data-tbl th.grp-att{background:#d5e8d4;}
table.data-tbl th.grp-as{background:#d5e8d4;}
table.data-tbl th.grp-ad{background:#f8d7da;}

table.data-tbl td{
    border:1px solid #000;
    padding:2px 2px;
    font-size:7.5px;
    vertical-align:middle;
    white-space:normal;
    word-wrap:break-word;
    overflow:hidden;
    line-height:1.3;
}

/* Employee stacked */
.emp-name{font-weight:800;font-size:8.5px;word-wrap:break-word;white-space:normal;line-height:1.35;}
.emp-id{font-size:6.8px;color:#222;margin-top:1px;}

/* Stacked day pair */
.day-top{font-size:7.5px;font-weight:600;text-align:center;}
.day-bot{font-size:7.0px;color:#333;margin-top:2px;border-top:1px dashed #ccc;padding-top:2px;text-align:center;}

/* Combined salary/deduction cell */
.comb-total{font-weight:700;font-size:8px;text-align:right;}
.comb-detail{font-size:6.5px;color:#444;margin-top:2px;border-top:1px dashed #ccc;padding-top:2px;text-align:left;line-height:1.5;}

.r{text-align:right}.c{text-align:center}.l{text-align:left}
.nd{text-align:center;padding:12px;color:#888}
.pg-foot{text-align:right;font-size:7.5px;color:#555;margin-top:2px}

.sig{display:flex;justify-content:space-between;width:100%;margin-top:14px;}
.sig-b{text-align:center;width:150px}
.sig-l{border-top:1px solid #000;margin-bottom:2px}
.sig-t{font-size:9px;color:#333}
.sig-d{font-size:8px;color:#555;margin-top:4px}
</style>"""


# ---------------------------------------------------------------------------
# HTML builder
# ---------------------------------------------------------------------------

# Column spec: (key, header_top, header_bot, align, pct_width)
# For stacked pairs: header_top shown in col header row 1, header_bot in row 2
# For single cols: header_top only, rowspan=2

_HTML_COLS = [
    # key            top-label           bot-label   align  pct
    ("sr",           "Sr",               None,       "c",   2.0),
    ("employee",     "Employee",         None,       "l",   12.0),
    # Stacked attendance pairs
    ("pd_wd",        "PD",               "WD",       "c",   3.5),
    ("abs_lwp",      "Abs",              "LWP",      "c",   3.5),
    ("pres_el",      "Pres",             "EL",       "c",   3.5),
    ("cl_co",        "CL",               "CO",       "c",   3.5),
    ("eco_hd",       "ECO",              "HD",       "c",   3.5),
    ("tour_hol",     "Tour",             "Hol",      "c",   3.5),
    ("wo",           "WO",               None,       "c",   3.0),
    # Combined salary / deduction
    ("add_salary",   "Additional Salary",None,       "r",   29.0),
    ("add_ded",      "Additional Deductions", None,  "r",   29.0),
]

# Which keys are part of attendance group
_ATT_KEYS = {"pd_wd","abs_lwp","pres_el","cl_co","eco_hd","tour_hol","wo"}

# Stacked day fieldname mapping: col_key → (top_fn, bot_fn)
_PAIR_MAP = {p[4]: (p[0], p[2]) for p in DAY_PAIRS}

_SKIP_ON_TOTAL = {"sr","employee"}


def _sig_html():
    labels = ["Prepared By","Checked By","Authorised Signatory"]
    blocks = "".join(
        '<div class="sig-b"><div class="sig-l"></div>'
        '<div class="sig-t">{l}</div>'
        '<div class="sig-d">Date: ___________</div></div>'.format(l=l)
        for l in labels
    )
    return '<div class="sig">{}</div>'.format(blocks)


def _colgroup():
    total_pct = sum(c[4] for c in _HTML_COLS)
    parts = "<colgroup>"
    for c in _HTML_COLS:
        parts += '<col style="width:{0:.3f}%;">'.format(c[4] * 100.0 / total_pct)
    parts += "</colgroup>"
    return parts


def _thead_html():
    """
    Row 1: Section group headers + individual col headers (rowspan=2 for non-stacked)
    Row 2: Bottom labels for stacked attendance pairs + bottom labels for combined cols
    """
    att_span  = sum(1 for c in _HTML_COLS if c[0] in _ATT_KEYS)
    as_span   = 1
    ad_span   = 1

    # Collect keys in order
    keys = [c[0] for c in _HTML_COLS]
    first_att = next((c[0] for c in _HTML_COLS if c[0] in _ATT_KEYS), None)

    row1 = "<tr>"
    for key, top_lbl, bot_lbl, align, _ in _HTML_COLS:
        if key == "sr":
            row1 += '<th rowspan="2" class="c">Sr</th>'
        elif key == "employee":
            row1 += '<th rowspan="2" class="l">Employee</th>'
        elif key == first_att:
            row1 += (
                '<th class="grp-att" colspan="{span}" '
                'style="text-align:center;border-bottom:1px solid #999;">'
                'Attendance</th>'
            ).format(span=att_span)
        elif key in _ATT_KEYS:
            continue  # already covered by colspan
        elif key == "add_salary":
            row1 += '<th rowspan="2" class="grp-as r">Additional Salary<br><span style="font-weight:400;font-size:6.5px;">(Total + Breakup)</span></th>'
        elif key == "add_ded":
            row1 += '<th rowspan="2" class="grp-ad r">Additional Deductions<br><span style="font-weight:400;font-size:6.5px;">(Total + Breakup)</span></th>'
    row1 += "</tr>"

    # Row 2: attendance column sub-headers
    row2 = "<tr>"
    for key, top_lbl, bot_lbl, align, _ in _HTML_COLS:
        if key not in _ATT_KEYS:
            continue
        if bot_lbl:
            row2 += (
                '<th class="{a}" style="vertical-align:middle;">'
                '<div style="font-weight:700;">{t}</div>'
                '<div style="border-top:1px dashed #999;margin-top:2px;'
                'padding-top:2px;font-weight:700;">{b}</div>'
                '</th>'
            ).format(a=align, t=top_lbl, b=bot_lbl)
        else:
            row2 += '<th class="{a}">{t}</th>'.format(a=align, t=top_lbl)
    row2 += "</tr>"

    return "<thead>{r1}{r2}</thead>".format(r1=row1, r2=row2)


def _render_row(row, is_total=False, row_idx=0):
    bg = "#e0e0e0" if is_total else ("#f5f7fa" if row_idx % 2 else "#ffffff")
    fw = "font-weight:700;" if is_total else ""

    tr = "<tr>"
    for key, top_lbl, bot_lbl, align, _ in _HTML_COLS:

        if is_total and key in _SKIP_ON_TOTAL:
            if key == "sr":
                tr += '<td class="c" style="background:{bg};{fw}"></td>'.format(bg=bg, fw=fw)
            continue

        # ── Employee cell ───────────────────────────────────────────────
        if key == "employee":
            if is_total:
                tr += (
                    '<td class="l" style="background:{bg};{fw}">'
                    '<strong>Grand Total</strong>'
                    '</td>'
                ).format(bg=bg, fw=fw)
            else:
                name = row.get("employee_name","") or ""
                eid  = row.get("employee","") or ""
                tr += (
                    '<td class="l" style="background:{bg};">'
                    '<div class="emp-name">{name}</div>'
                    '{id_div}'
                    '</td>'
                ).format(
                    bg=bg, name=name,
                    id_div='<div class="emp-id">{}</div>'.format(eid) if eid else "",
                )
            continue

        # ── Sr ─────────────────────────────────────────────────────────
        if key == "sr":
            tr += '<td class="c" style="background:{bg};{fw}">{v}</td>'.format(
                bg=bg, fw=fw, v=row.get("sr","") or "")
            continue

        # ── Stacked attendance pair ─────────────────────────────────────
        if key in _ATT_KEYS:
            top_fn, bot_fn = _PAIR_MAP.get(key, (None, None))
            top_val = _fmt_days(row.get(top_fn)) if top_fn else ""
            bot_val = _fmt_days(row.get(bot_fn)) if bot_fn else ""
            if bot_fn:
                tr += (
                    '<td class="c" style="background:{bg};{fw}">'
                    '<div class="day-top">{tv}</div>'
                    '<div class="day-bot">{bv}</div>'
                    '</td>'
                ).format(bg=bg, fw=fw, tv=top_val or "&nbsp;", bv=bot_val or "&nbsp;")
            else:
                tr += (
                    '<td class="c" style="background:{bg};{fw}">'
                    '<div class="day-top">{tv}</div>'
                    '</td>'
                ).format(bg=bg, fw=fw, tv=top_val or "&nbsp;")
            continue

        # ── Combined Add. Salary ────────────────────────────────────────
        if key == "add_salary":
            total   = flt(row.get("_total_add_salary") or 0, 2)
            detail  = row.get("add_salary_combined","") or ""
            parts   = [p.strip() for p in detail.split("|") if p.strip()]
            total_s = _fmt_num(total) if total else ""
            detail_s = " &nbsp;|&nbsp; ".join(parts) if parts else ""
            cell = (
                '<td class="r" style="background:{bg};{fw}">'
                '{tot_div}'
                '{det_div}'
                '</td>'
            ).format(
                bg=bg, fw=fw,
                tot_div='<div class="comb-total">{}</div>'.format(total_s) if total_s else '<div class="comb-total">&nbsp;</div>',
                det_div='<div class="comb-detail">{}</div>'.format(detail_s) if detail_s else "",
            )
            tr += cell
            continue

        # ── Combined Add. Deductions ────────────────────────────────────
        if key == "add_ded":
            total   = flt(row.get("_total_add_deductions") or 0, 2)
            detail  = row.get("add_ded_combined","") or ""
            parts   = [p.strip() for p in detail.split("|") if p.strip()]
            total_s = _fmt_num(total) if total else ""
            detail_s = " &nbsp;|&nbsp; ".join(parts) if parts else ""
            cell = (
                '<td class="r" style="background:{bg};{fw}">'
                '{tot_div}'
                '{det_div}'
                '</td>'
            ).format(
                bg=bg, fw=fw,
                tot_div='<div class="comb-total">{}</div>'.format(total_s) if total_s else '<div class="comb-total">&nbsp;</div>',
                det_div='<div class="comb-detail">{}</div>'.format(detail_s) if detail_s else "",
            )
            tr += cell
            continue

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
    safe = max(1, ROWS_PER_PAGE - 1)
    pages = []
    idx   = 0
    while idx < len(detail_rows):
        chunk = detail_rows[idx: idx + safe]
        pages.append(list(chunk))
        idx += len(chunk)
    if not pages:
        pages = [[]]
    if total_row:
        pages[-1].append(total_row)
    return pages


def _build_html(cols, data, co, mo, yr,
                earn_comps=None, emp_ded_comps=None, empr_comps=None):
    page1_hdr = (
        '<div class="hdr">'
        '<div class="co">{co}</div>'
        '<div class="ttl">Transaction Checklist</div>'
        '<div class="per">For the Month of {mo} {yr}</div>'
        '</div>'
    ).format(co=co, mo=mo, yr=yr)

    cont_hdr = (
        '<div class="cont-hdr">'
        '{co} &mdash; Transaction Checklist &mdash; {mo} {yr} (contd.)'
        '</div>'
    ).format(co=co, mo=mo, yr=yr)

    detail_rows = [r for r in data if not r.get("bold")]
    total_row   = next((r for r in data if r.get("bold")), None)

    has_data = bool(detail_rows)
    pages    = _paginate(detail_rows, total_row) if has_data else [[]]
    total_pages = len(pages)
    parts       = []
    row_counter = 0

    for pn, page_rows in enumerate(pages):
        pb       = '<div style="page-break-before:always;"></div>' if pn > 0 else ""
        is_last  = (pn == total_pages - 1)
        hdr_html = page1_hdr if pn == 0 else cont_hdr

        if not has_data:
            nc  = len(_HTML_COLS)
            tbl = (
                '<table class="data-tbl">{cg}{thead}'
                '<tbody><tr><td colspan="{nc}" class="nd">'
                'No data for this period</td></tr></tbody></table>'
            ).format(cg=_colgroup(), thead=_thead_html(), nc=nc)
        else:
            # Inject sr numbers
            for j, row in enumerate(page_rows):
                if not row.get("bold"):
                    row["sr"] = row_counter + j + 1
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


# ---------------------------------------------------------------------------
# PDF save
# ---------------------------------------------------------------------------

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
    co_label   = _company_label(filters)
    mo         = filters.get("month", "")
    yr         = filters.get("year",  "")
    html       = _build_html(cols, data, co_label, mo, yr)
    return _save_pdf(html, "Transaction_Checklist")