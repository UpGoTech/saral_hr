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

# ---------------------------------------------------------------------------
# Day-breakdown columns grouped into pairs for stacked display
# Each tuple: (top_fieldname, top_label, bottom_fieldname, bottom_label, col_key)
# ---------------------------------------------------------------------------

DAY_PAIRS = [
    ("payment_days",         "PD",   "total_working_days",    "WD",   "pd_wd"),
    ("absent_days",          "Abs",  "total_lwp",             "LWP",  "abs_lwp"),
    ("present_days",         "Pres", "total_earned_leaves",   "EL",   "pres_el"),
    ("total_casual_leaves",  "CL",   "total_comp_off",        "CO",   "cl_co"),
    ("total_earned_comp_off","ECO",  "total_half_days",       "HD",   "eco_hd"),
    ("total_on_tour",        "Tour", "total_holidays",        "Hol",  "tour_hol"),
    ("weekly_offs_taken",    "WO",   None,                    "",     "wo"),
]

ALL_DAY_FNS = [
    "payment_days","total_working_days","absent_days","total_lwp",
    "present_days","total_earned_leaves","total_casual_leaves","total_comp_off",
    "total_earned_comp_off","total_half_days","total_on_tour","total_holidays",
    "weekly_offs_taken",
]

IT_COMPONENT = "Income Tax"

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

def _fmt_num(v):
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

def _fmt_pct(v):
    if v is None or v == "": return ""
    try:
        fv = float(v)
        if fv == 0: return ""
        return "{0:.2f}%".format(fv)
    except (TypeError, ValueError): return str(v)


# ---------------------------------------------------------------------------
# _get_components
# ---------------------------------------------------------------------------

def _get_components(where_clause, params):
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
# Fetch Additional Salary / Deduction data
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
# Fetch Income Tax
# ---------------------------------------------------------------------------

def _fetch_income_tax(slip_names):
    if not slip_names:
        return {}
    result = {}
    try:
        rows = frappe.db.sql(
            "SELECT sd.parent AS slip_name, SUM(sd.amount) AS v"
            " FROM `tabSalary Details` sd"
            " WHERE sd.parent IN %(sn)s"
            "   AND sd.parenttype = 'Salary Slip'"
            "   AND sd.parentfield = 'deductions'"
            "   AND LOWER(sd.salary_component) = LOWER(%(comp)s)"
            " GROUP BY sd.parent",
            {"sn": tuple(slip_names), "comp": IT_COMPONENT},
            as_dict=1,
        )
        for r in rows:
            v = flt(r.get("v") or 0, 2)
            if v > 0:
                result[r["slip_name"]] = v
    except Exception:
        pass
    return result


# ---------------------------------------------------------------------------
# Fetch Loan & Advance Recovered
# Reads from `tabSalary Details` (deductions child table of Salary Slip).
# salary_slip.py stores components as "Loan-0001" / "Advance-0001"
# so we match by prefix: LIKE 'loan%' and LIKE 'advance%'
# Returns two dicts keyed by slip name → total amount deducted that month.
# ---------------------------------------------------------------------------

def _fetch_loan_advance(slip_names):
    if not slip_names:
        return {}, {}

    loan_map    = {}
    advance_map = {}

    try:
        rows = frappe.db.sql(
            "SELECT sd.parent AS slip_name,"
            "       sd.salary_component,"
            "       SUM(sd.amount) AS total"
            " FROM `tabSalary Details` sd"
            " WHERE sd.parent IN %(sn)s"
            "   AND sd.parenttype = 'Salary Slip'"
            "   AND sd.parentfield = 'deductions'"
            "   AND ("
            "       LOWER(sd.salary_component) LIKE 'loan%%'"
            "    OR LOWER(sd.salary_component) LIKE 'advance%%'"
            "   )"
            " GROUP BY sd.parent, sd.salary_component",
            {"sn": tuple(slip_names)},
            as_dict=1,
        )

        for r in rows:
            comp = (r.get("salary_component") or "").lower()
            slip = r["slip_name"]
            amt  = flt(r.get("total") or 0, 2)
            if amt <= 0:
                continue
            if comp.startswith("loan"):
                loan_map[slip] = flt(loan_map.get(slip, 0) + amt, 2)
            elif comp.startswith("advance"):
                advance_map[slip] = flt(advance_map.get(slip, 0) + amt, 2)

    except Exception:
        pass

    return loan_map, advance_map


# ---------------------------------------------------------------------------
# Fetch Variable Pay %
# ---------------------------------------------------------------------------

def _fetch_variable_pay_pct(year, month, employee_ids):
    if not employee_ids:
        return {}

    vp_map = {}
    try:
        emp_divisions = {}
        cl_rows = frappe.db.sql(
            "SELECT name AS employee, division"
            " FROM `tabCompany Link`"
            " WHERE name IN %(eids)s",
            {"eids": tuple(employee_ids)},
            as_dict=1,
        )
        for r in cl_rows:
            if r.get("division"):
                emp_divisions[r["employee"]] = r["division"]

        if not emp_divisions:
            return {}

        divisions = list(set(emp_divisions.values()))

        vpa_name = frappe.db.get_value(
            "Variable Pay Assignment",
            {"year": str(year), "month": month, "docstatus": ["!=", 2]},
            "name",
        )
        if not vpa_name:
            return {}

        child_rows = frappe.get_all(
            "Variable Pay Detail Table",
            filters={
                "parent": vpa_name,
                "parenttype": "Variable Pay Assignment",
                "division": ["in", divisions],
            },
            fields=["division", "percentage"],
        )
        div_pct = {r["division"]: flt(r.get("percentage") or 0, 2) for r in child_rows}

        for emp, div in emp_divisions.items():
            if div in div_pct:
                vp_map[emp] = div_pct[div]

    except Exception:
        pass

    return vp_map


# ---------------------------------------------------------------------------
# Core data function
# ---------------------------------------------------------------------------

def _get_data(f):
    cols = [
        _col("Employee",      "employee",      w=130),
        _col("Employee Name", "employee_name", w=200),
    ]
    for fn in ALL_DAY_FNS:
        cols.append(_col(fn.replace("_"," ").title(), fn, "Float", 80, precision=2))

    cols.append(_col("Additional Salary",       "add_salary_combined",  "Data",  220))
    cols.append(_col("Additional Deductions",   "add_ded_combined",     "Data",  220))
    cols.append(_col("Income Tax",              "income_tax",           "Float", 120, precision=2))
    cols.append(_col("Variable Pay %",          "variable_pay_pct",     "Data",   90))
    cols.append(_col("Loan Recovered",          "loan_recovered",       "Float", 110, precision=2))
    cols.append(_col("Advance Recovered",       "advance_recovered",    "Float", 110, precision=2))

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

    if not slips:
        return cols, []

    employee_ids = [sl["employee"] for sl in slips]
    slip_names   = [sl["slip"]     for sl in slips]

    slip_by_emp  = {sl["employee"]: sl["slip"] for sl in slips}

    as_comps, as_map = _fetch_additional_data(
        "Additional Salary", "Additional Salary Component",
        year, month, employee_ids,
    )
    ad_comps, ad_map = _fetch_additional_data(
        "Additional Deductions", "Additional Deduction Component",
        year, month, employee_ids,
    )
    it_map                = _fetch_income_tax(slip_names)
    vp_map                = _fetch_variable_pay_pct(year, month, employee_ids)
    # ── Loan & Advance: read from Salary Slip deductions child table ──────────
    loan_map, advance_map = _fetch_loan_advance(slip_names)

    grand = {fn: 0.0 for fn in ALL_DAY_FNS}
    grand.update({
        "total_add_salary":    0.0,
        "total_add_deductions":0.0,
        "income_tax":          0.0,
        "loan_recovered":      0.0,
        "advance_recovered":   0.0,
    })

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

        emp_as   = as_map.get(sl["employee"], {})
        total_s  = 0.0
        as_parts = []
        for comp in as_comps:
            amt = flt(emp_as.get(comp, 0), 2)
            if amt:
                as_parts.append("{0}: {1}".format(comp, "{:,.2f}".format(amt)))
                total_s += amt
        row["add_salary_combined"] = "|".join(as_parts)
        row["_total_add_salary"]   = flt(total_s, 2)
        grand["total_add_salary"] += total_s

        emp_ad   = ad_map.get(sl["employee"], {})
        total_d  = 0.0
        ad_parts = []
        for comp in ad_comps:
            amt = flt(emp_ad.get(comp, 0), 2)
            if amt:
                ad_parts.append("{0}: {1}".format(comp, "{:,.2f}".format(amt)))
                total_d += amt
        row["add_ded_combined"]      = "|".join(ad_parts)
        row["_total_add_deductions"] = flt(total_d, 2)
        grand["total_add_deductions"] += total_d

        it_amt = flt(it_map.get(sl["slip"], 0), 2)
        row["income_tax"] = it_amt if it_amt > 0 else None
        grand["income_tax"] += it_amt

        vp_pct = vp_map.get(sl["employee"])
        row["variable_pay_pct"] = _fmt_pct(vp_pct) if vp_pct else ""

        # ── Loan & Advance amounts for this specific slip/month ───────────────
        loan_val = flt(loan_map.get(sl["slip"], 0), 2)
        adv_val  = flt(advance_map.get(sl["slip"], 0), 2)
        row["loan_recovered"]    = loan_val if loan_val > 0 else None
        row["advance_recovered"] = adv_val  if adv_val  > 0 else None
        grand["loan_recovered"]    += loan_val
        grand["advance_recovered"] += adv_val

        data.append(row)

    if data:
        grand_row = {
            "employee":              "",
            "employee_name":         "Grand Total",
            "add_salary_combined":   "",
            "add_ded_combined":      "",
            "_total_add_salary":     flt(grand["total_add_salary"], 2),
            "_total_add_deductions": flt(grand["total_add_deductions"], 2),
            "income_tax":            flt(grand["income_tax"], 2) or None,
            "variable_pay_pct":      "",
            "loan_recovered":        flt(grand["loan_recovered"], 2) or None,
            "advance_recovered":     flt(grand["advance_recovered"], 2) or None,
            "bold": 1,
        }
        grand_row.update({fn: flt(grand[fn], 2) for fn in ALL_DAY_FNS})
        data.append(grand_row)

    return cols, data


def execute(filters=None):
    return _get_data(filters or {})


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

_CSS = """<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Arial,sans-serif;font-size:8.5px;color:#000;background:#fff}

table.data-tbl{width:100%;border-collapse:collapse;table-layout:fixed;}
table.data-tbl th{
    border:1px solid #000;
    padding:3px 2px;
    font-size:7px;
    font-weight:700;
    background:#f0f0f0;
    white-space:normal;
    word-wrap:break-word;
    vertical-align:middle;
    text-align:center;
    line-height:1.25;
}
table.data-tbl th.grp-att{background:#d5e8d4;font-size:7.5px;}
table.data-tbl th.grp-as {background:#d5e8d4;font-size:7.5px;}
table.data-tbl th.grp-ad {background:#f8d7da;font-size:7.5px;}
table.data-tbl th.grp-ex {background:#dce6f1;font-size:7.5px;}

table.data-tbl td{
    border:1px solid #000;
    padding:2px 2px;
    font-size:7px;
    vertical-align:middle;
    white-space:normal;
    word-wrap:break-word;
    overflow:hidden;
    line-height:1.3;
}
table.data-tbl tbody tr{page-break-inside:avoid;}

.emp-name{font-weight:800;font-size:8px;word-wrap:break-word;white-space:normal;line-height:1.35;}
.emp-id{font-size:6.5px;color:#222;margin-top:1px;}

.day-top{font-size:7px;font-weight:600;text-align:center;}
.day-bot{font-size:6.5px;color:#333;margin-top:1px;border-top:1px dashed #ccc;padding-top:1px;text-align:center;}

.comb-total{font-weight:700;font-size:7.5px;text-align:right;}
.comb-detail{font-size:6px;color:#444;margin-top:2px;border-top:1px dashed #ccc;
             padding-top:2px;text-align:left;line-height:1.4;word-wrap:break-word;
             white-space:normal;}

.r{text-align:right}.c{text-align:center}.l{text-align:left}
.nd{text-align:center;padding:12px;color:#888}

.sig{display:flex;justify-content:space-between;width:100%;margin-top:18px;}
.sig-b{text-align:center;width:150px}
.sig-l{border-top:1px solid #000;margin-bottom:2px}
.sig-t{font-size:9px;color:#333}
.sig-d{font-size:8px;color:#555;margin-top:4px}
</style>"""


# ---------------------------------------------------------------------------
# HTML column layout
# ---------------------------------------------------------------------------

_HTML_COLS = [
    ("sr",               "Sr",                    None,   "c",  1.8),
    ("employee",         "Employee",              None,   "l", 11.0),
    ("pd_wd",            "PD",                    "WD",   "c",  3.2),
    ("abs_lwp",          "Abs",                   "LWP",  "c",  3.2),
    ("pres_el",          "Pres",                  "EL",   "c",  3.2),
    ("cl_co",            "CL",                    "CO",   "c",  3.2),
    ("eco_hd",           "ECO",                   "HD",   "c",  3.2),
    ("tour_hol",         "Tour",                  "Hol",  "c",  3.2),
    ("wo",               "WO",                    None,   "c",  2.5),
    ("add_salary",       "Additional Salary",     None,   "r", 20.0),
    ("add_ded",          "Additional Deductions", None,   "r", 20.0),
    ("income_tax",       "Income Tax",            None,   "r",  6.5),
    ("variable_pay_pct", "Var Pay %",             None,   "c",  4.5),
    ("loan_recovered",   "Loan Rec.",             None,   "r",  5.5),
    ("advance_recovered","Adv. Rec.",             None,   "r",  5.5),
]

_ATT_KEYS   = {"pd_wd","abs_lwp","pres_el","cl_co","eco_hd","tour_hol","wo"}
_EXTRA_KEYS = {"income_tax","variable_pay_pct","loan_recovered","advance_recovered"}
_PAIR_MAP   = {p[4]: (p[0], p[2]) for p in DAY_PAIRS}

# ── FIX: Only Sr is skipped (empty cell). Employee is handled in its own block. ──
_SKIP_ON_TOTAL = {"sr"}

ROWS_FIRST_PAGE = 14
ROWS_OTHER_PAGE = 17


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


def _thead_html(co="", mo="", yr=""):
    nc = len(_HTML_COLS)

    cont_row = (
        '<tr>'
        '<th colspan="{nc}" style="'
        'text-align:center;background:#fff;border:1px solid #000;'
        'padding:3px 4px;font-size:8px;font-weight:700;line-height:1.5;">'
        '{co} &nbsp;|&nbsp; Transaction Checklist'
        ' &nbsp;&mdash;&nbsp; For the Month of {mo} {yr}'
        '</th>'
        '</tr>'
    ).format(nc=nc, co=co, mo=mo, yr=yr)

    att_keys_ordered  = [c[0] for c in _HTML_COLS if c[0] in _ATT_KEYS]
    att_span          = len(att_keys_ordered)
    first_att         = att_keys_ordered[0] if att_keys_ordered else None

    extra_keys_ordered = [c[0] for c in _HTML_COLS if c[0] in _EXTRA_KEYS]
    extra_span         = len(extra_keys_ordered)
    first_extra        = extra_keys_ordered[0] if extra_keys_ordered else None

    row1 = "<tr>"
    for key, top_lbl, bot_lbl, align, _ in _HTML_COLS:
        if key == "sr":
            row1 += '<th rowspan="2" class="c" style="vertical-align:middle;">Sr</th>'
        elif key == "employee":
            row1 += '<th rowspan="2" class="l" style="vertical-align:middle;">Employee</th>'
        elif key == first_att:
            row1 += (
                '<th class="grp-att" colspan="{span}" '
                'style="text-align:center;border-bottom:1px solid #999;">'
                'Attendance</th>'
            ).format(span=att_span)
        elif key in _ATT_KEYS:
            continue
        elif key == "add_salary":
            row1 += (
                '<th rowspan="2" class="grp-as r" style="vertical-align:middle;">'
                'Additional Salary'
                '<br><span style="font-weight:400;font-size:6px;">(Total + Breakup)</span>'
                '</th>'
            )
        elif key == "add_ded":
            row1 += (
                '<th rowspan="2" class="grp-ad r" style="vertical-align:middle;">'
                'Additional Deductions'
                '<br><span style="font-weight:400;font-size:6px;">(Total + Breakup)</span>'
                '</th>'
            )
        elif key == first_extra:
            row1 += (
                '<th class="grp-ex" colspan="{span}" '
                'style="text-align:center;border-bottom:1px solid #999;">'
                'Other Transactions</th>'
            ).format(span=extra_span)
        elif key in _EXTRA_KEYS:
            continue
    row1 += "</tr>"

    row2 = "<tr>"
    for key, top_lbl, bot_lbl, align, _ in _HTML_COLS:
        if key in _ATT_KEYS:
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
        elif key in _EXTRA_KEYS:
            row2 += '<th class="{a}">{t}</th>'.format(a=align, t=top_lbl)
    row2 += "</tr>"

    return "<thead>{cr}{r1}{r2}</thead>".format(cr=cont_row, r1=row1, r2=row2)


def _render_row(row, is_total=False, row_idx=0):
    bg = "#e0e0e0" if is_total else ("#f5f7fa" if row_idx % 2 else "#ffffff")
    fw = "font-weight:700;" if is_total else ""

    tr = "<tr>"
    for key, top_lbl, bot_lbl, align, _ in _HTML_COLS:

        if is_total and key in _SKIP_ON_TOTAL:
            tr += '<td class="c" style="background:{bg};"></td>'.format(bg=bg)
            continue

        # ── Employee ────────────────────────────────────────────────────
        if key == "employee":
            if is_total:
                tr += (
                    '<td class="l" style="background:{bg};font-weight:700;">'
                    '<strong>Grand Total</strong>'
                    '</td>'
                ).format(bg=bg)
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

        # ── Sr ──────────────────────────────────────────────────────────
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
            total    = flt(row.get("_total_add_salary") or 0, 2)
            detail   = row.get("add_salary_combined","") or ""
            parts    = [p.strip() for p in detail.split("|") if p.strip()]
            total_s  = _fmt_num(total) if total else ""
            detail_s = "<br>".join(parts) if parts else ""
            tr += (
                '<td class="r" style="background:{bg};{fw}">'
                '{tot}'
                '{det}'
                '</td>'
            ).format(
                bg=bg, fw=fw,
                tot='<div class="comb-total">{}</div>'.format(total_s) if total_s else '<div class="comb-total">&nbsp;</div>',
                det='<div class="comb-detail">{}</div>'.format(detail_s) if detail_s else "",
            )
            continue

        # ── Combined Add. Deductions ────────────────────────────────────
        if key == "add_ded":
            total    = flt(row.get("_total_add_deductions") or 0, 2)
            detail   = row.get("add_ded_combined","") or ""
            parts    = [p.strip() for p in detail.split("|") if p.strip()]
            total_s  = _fmt_num(total) if total else ""
            detail_s = "<br>".join(parts) if parts else ""
            tr += (
                '<td class="r" style="background:{bg};{fw}">'
                '{tot}'
                '{det}'
                '</td>'
            ).format(
                bg=bg, fw=fw,
                tot='<div class="comb-total">{}</div>'.format(total_s) if total_s else '<div class="comb-total">&nbsp;</div>',
                det='<div class="comb-detail">{}</div>'.format(detail_s) if detail_s else "",
            )
            continue

        # ── Income Tax ──────────────────────────────────────────────────
        if key == "income_tax":
            v = row.get("income_tax")
            tr += '<td class="r" style="background:{bg};{fw}">{v}</td>'.format(
                bg=bg, fw=fw, v=_fmt_num(v) if v else "&nbsp;")
            continue

        # ── Variable Pay % ──────────────────────────────────────────────
        if key == "variable_pay_pct":
            v = row.get("variable_pay_pct","") or ""
            tr += '<td class="c" style="background:{bg};{fw}">{v}</td>'.format(
                bg=bg, fw=fw, v=v or "&nbsp;")
            continue

        # ── Loan Recovered ──────────────────────────────────────────────
        if key == "loan_recovered":
            v = row.get("loan_recovered")
            tr += '<td class="r" style="background:{bg};{fw}">{v}</td>'.format(
                bg=bg, fw=fw, v=_fmt_num(v) if v else "&nbsp;")
            continue

        # ── Advance Recovered ───────────────────────────────────────────
        if key == "advance_recovered":
            v = row.get("advance_recovered")
            tr += '<td class="r" style="background:{bg};{fw}">{v}</td>'.format(
                bg=bg, fw=fw, v=_fmt_num(v) if v else "&nbsp;")
            continue

    tr += "</tr>"
    return tr


def _cont_header_html(co, mo, yr):
    return (
        "<!DOCTYPE html><html><head>"
        "<style>"
        "* {{margin:0;padding:0;box-sizing:border-box;}}"
        "body {{font-family:Arial,sans-serif;font-size:7.5px;color:#000;"
        "       width:100%;background:#fff;}}"
        ".cont-hdr {{text-align:center;border-bottom:1px solid #000;"
        "            padding:2px 4px 2px;line-height:1.4;}}"
        ".co  {{font-size:9px;font-weight:900;letter-spacing:0.5px;"
        "        text-transform:uppercase;display:inline;}}"
        ".sep {{margin:0 4px;color:#888;}}"
        ".ttl {{font-size:8px;font-weight:700;display:inline;}}"
        ".per {{font-size:7px;color:#444;display:inline;}}"
        "</style></head><body>"
        '<div class="cont-hdr">'
        '<span class="co">{co}</span>'
        '<span class="sep">|</span>'
        '<span class="ttl">Transaction Checklist</span>'
        '<span class="sep">—</span>'
        '<span class="per">For the Month of {mo} {yr}</span>'
        "</div>"
        "</body></html>"
    ).format(co=co, mo=mo, yr=yr)


def _build_html(cols, data, co, mo, yr,
                earn_comps=None, emp_ded_comps=None, empr_comps=None):
    detail_rows = [r for r in data if not r.get("bold")]
    total_row   = next((r for r in data if r.get("bold")), None)

    for idx, row in enumerate(detail_rows, 1):
        row["sr"] = idx

    tbody = "<tbody>"
    for idx, row in enumerate(detail_rows):
        tbody += _render_row(row, is_total=False, row_idx=idx)
    if total_row:
        tbody += _render_row(total_row, is_total=True, row_idx=0)
    tbody += "</tbody>"

    if not detail_rows:
        nc = len(_HTML_COLS)
        tbody = (
            "<tbody><tr><td colspan='{nc}' style='text-align:center;"
            "padding:12px;color:#888;'>No data for this period</td></tr></tbody>"
        ).format(nc=nc)

    tbl = '<table class="data-tbl">{cg}{thead}{tbody}</table>'.format(
        cg=_colgroup(), thead=_thead_html(co=co, mo=mo, yr=yr), tbody=tbody)

    sig = _sig_html()

    return (
        '<!DOCTYPE html><html><head><meta charset="UTF-8">{css}</head>'
        '<body>{tbl}{sig}</body></html>'
    ).format(css=_CSS, tbl=tbl, sig=sig)


def _save_pdf(html, prefix):
    pdf = get_pdf(html, options={
        "page-size":     "A4",
        "orientation":   "Landscape",
        "margin-top":    "7mm",
        "margin-right":  "5mm",
        "margin-bottom": "8mm",
        "margin-left":   "5mm",
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