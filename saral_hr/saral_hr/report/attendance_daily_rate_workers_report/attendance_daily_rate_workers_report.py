# Copyright (c) 2026, sj and contributors
# For license information, please see license.txt

import frappe
import json
from frappe import _
from frappe.utils import flt, getdate
from frappe.utils.pdf import get_pdf
from datetime import date, timedelta
import calendar


# =============================================================================
#  FRAPPE REPORT ENTRY POINT
# =============================================================================

def execute(filters=None):
    filters = filters or {}
    validate_filters(filters)
    return get_columns(), get_data(filters)


def validate_filters(filters):
    if not filters.get("company"):
        frappe.throw(_("Please select a Company."))
    if not filters.get("year"):
        frappe.throw(_("Please select a Year."))
    if not filters.get("month"):
        frappe.throw(_("Please select a Month."))


def get_columns():
    # NOTE: Gross is placed AFTER SSA Net and BEFORE Actual Runtime deductions
    return [
        {"fieldname": "employee",      "label": _("Employee"),      "fieldtype": "Link",  "options": "Employee", "width": 160},
        {"fieldname": "employee_name", "label": _("Employee Name"), "fieldtype": "Data",  "width": 160},
        {"fieldname": "total_days",    "label": _("WD"),            "fieldtype": "Int",   "width": 55},
        {"fieldname": "total_present", "label": _("Present"),       "fieldtype": "Float", "precision": 1, "width": 65},
        {"fieldname": "total_absent",  "label": _("Absent"),        "fieldtype": "Float", "precision": 1, "width": 65},
        {"fieldname": "total_halfday", "label": _("Half Day"),      "fieldtype": "Int",   "width": 65},
        {"fieldname": "total_holiday", "label": _("Holiday"),       "fieldtype": "Int",   "width": 65},
        {"fieldname": "payment_days",  "label": _("PD"),            "fieldtype": "Float", "precision": 1, "width": 65},
        {"fieldname": "total_ot_hours","label": _("OT Hrs"),        "fieldtype": "Float", "precision": 2, "width": 65},
        {"fieldname": "base_pay",      "label": _("Base Pay"),      "fieldtype": "Data",  "width": 110},
        {"fieldname": "ot_payable",    "label": _("OT Payable"),    "fieldtype": "Data",  "width": 110},
        # SSA block
        {"fieldname": "ssa_gross",           "label": _("SSA Gross"),     "fieldtype": "Data", "width": 110},
        {"fieldname": "ssa_deductions",      "label": _("SSA Ded"),       "fieldtype": "Data", "width": 280},
        {"fieldname": "ssa_total_deduction", "label": _("SSA Total"),     "fieldtype": "Data", "width": 110},
        {"fieldname": "ssa_net_payable",     "label": _("SSA Net"),       "fieldtype": "Data", "width": 110},
        # Gross comes AFTER SSA, BEFORE Actual Runtime
        {"fieldname": "gross_payable",       "label": _("Gross"),         "fieldtype": "Data", "width": 110},
        # Actual Runtime block
        {"fieldname": "runtime_deductions",      "label": _("Actual Ded"),    "fieldtype": "Data", "width": 280},
        {"fieldname": "runtime_total_deduction", "label": _("Actual Total"),  "fieldtype": "Data", "width": 110},
        {"fieldname": "runtime_net_payable",     "label": _("Net Payable"),   "fieldtype": "Data", "width": 110},
    ]


# =============================================================================
#  DATA
# =============================================================================

def get_data(filters):
    company    = filters["company"]
    year       = int(filters["year"])
    month      = int(filters["month"])
    last_day   = calendar.monthrange(year, month)[1]
    start_date = date(year, month, 1)
    end_date   = date(year, month, last_day)
    month_name = start_date.strftime("%B")

    adr_rows = frappe.db.sql("""
        SELECT adr.employee, adr.employee_name, adr.attendance_date,
               adr.status, adr.ot_hours, adr.daily_rate
        FROM `tabAttendance Daily Rate` adr
        WHERE adr.company = %(company)s
          AND adr.attendance_date BETWEEN %(start)s AND %(end)s
          AND adr.docstatus < 2
        ORDER BY adr.employee, adr.attendance_date
    """, {"company": company, "start": start_date, "end": end_date}, as_dict=True)

    if not adr_rows:
        return []

    holiday_dates   = get_holiday_dates(company, start_date, end_date)
    employees       = list({r.employee for r in adr_rows})
    ssa_map         = get_ssa_map(employees, str(start_date))
    special_amounts = get_special_monthly_amounts(ssa_map)

    from collections import defaultdict
    emp_records = defaultdict(list)
    for row in adr_rows:
        emp_records[row.employee].append(row)

    today = date.today()
    data  = []

    for emp in sorted(employees):
        rows     = emp_records[emp]
        emp_name = rows[0].employee_name or emp

        saved = {str(getdate(r.attendance_date)): r for r in rows}

        cnt = {"total": 0, "present": 0.0, "absent": 0.0,
               "halfday": 0, "holiday": 0, "payment": 0.0}
        total_ot   = 0.0
        base_pay   = 0.0
        ot_payable = 0.0

        cur = start_date
        while cur <= end_date:
            if cur > today:
                cur += timedelta(days=1)
                continue
            dk     = str(cur)
            rec    = saved.get(dk)
            status = rec.status          if rec else ""
            rate   = flt(rec.daily_rate) if rec else 0.0
            ot_dec = flt(rec.ot_hours)   if rec else 0.0

            cnt["total"] += 1
            total_ot     += ot_dec
            if rate > 0 and ot_dec > 0:
                ot_payable += (rate / 8) * ot_dec

            if not rec:
                if dk in holiday_dates:
                    cnt["holiday"] += 1
            elif status == "Half Day":
                cnt["halfday"] += 1
                cnt["present"] += 0.5
                cnt["absent"]  += 0.5
                cnt["payment"] += 0.5
                base_pay       += rate / 2
            elif status in ("Present", "On Tour"):
                cnt["present"] += 1
                cnt["payment"] += 1
                base_pay       += rate
            elif status == "Holiday":
                cnt["holiday"] += 1
                cnt["payment"] += 1
                base_pay       += rate
            elif status == "Absent":
                cnt["absent"] += 1
            cur += timedelta(days=1)

        gross = base_pay + ot_payable

        ssa           = ssa_map.get(emp, {})
        ssa_gross_val = ssa.get("gross_salary", 0.0)
        ssa_ded_list  = ssa.get("deductions", [])
        ssa_base      = ssa.get("ssa_base", 0.0)
        ssa_total_ded = sum(d["amount"] for d in ssa_ded_list)
        ssa_net       = ssa_gross_val - ssa_total_ded

        ssa_ded_str = ", ".join(
            "{}: {}".format(d["abbr"], fmt_num(d["amount"])) for d in ssa_ded_list
        ) if ssa_ded_list else "—"

        rt_ded_list  = calc_runtime_deductions(
            gross=gross, ssa_ded_list=ssa_ded_list, ssa_base=ssa_base,
            special_amounts=special_amounts, month_name=month_name,
        )
        rt_total_ded = sum(d["amount"] for d in rt_ded_list)
        rt_ded_str   = ", ".join(
            "{}: {}".format(d["abbr"], fmt_num(d["amount"])) for d in rt_ded_list
        ) if rt_ded_list else "—"

        runtime_net = gross - rt_total_ded

        data.append({
            "employee":      emp,
            "employee_name": emp_name,
            "total_days":    cnt["total"],
            "total_present": cnt["present"],
            "total_absent":  cnt["absent"],
            "total_halfday": cnt["halfday"],
            "total_holiday": cnt["holiday"],
            "payment_days":  cnt["payment"],
            "total_ot_hours": round(total_ot, 2),
            "base_pay":      fmt_num(base_pay),
            "ot_payable":    fmt_num(ot_payable),
            # SSA block
            "ssa_gross":           fmt_num(ssa_gross_val),
            "ssa_deductions":      ssa_ded_str,
            "ssa_total_deduction": fmt_num(ssa_total_ded),
            "ssa_net_payable":     fmt_num(ssa_net),
            # Gross — after SSA, before runtime
            "gross_payable": fmt_num(gross),
            # Actual runtime
            "runtime_deductions":      rt_ded_str,
            "runtime_total_deduction": fmt_num(rt_total_ded),
            "runtime_net_payable":     fmt_num(runtime_net),
            # raw for PDF totals
            "_base_pay":      base_pay,
            "_ot_payable":    ot_payable,
            "_gross":         gross,
            "_ssa_gross":     ssa_gross_val,
            "_ssa_total_ded": ssa_total_ded,
            "_ssa_net":       ssa_net,
            "_rt_total_ded":  rt_total_ded,
            "_runtime_net":   runtime_net,
            "_ssa_ded_list":  ssa_ded_list,
            "_rt_ded_list":   rt_ded_list,
        })

    return data


# =============================================================================
#  DEDUCTION ENGINE
# =============================================================================

PF_RATE      = 0.12
PF_BASIC_CAP = 15000.0

import re as _re
_PF_RE   = _re.compile(r'\bpf\b|provident.fund|emp.?pf|employee.?pf', _re.IGNORECASE)
_ESIC_RE = _re.compile(r'\besic\b|esi\b|emp.?esi|employee.?esi|emp.?esic', _re.IGNORECASE)


def _classify(salary_component, abbr=""):
    txt = (salary_component or "") + " " + (abbr or "")
    if _PF_RE.search(txt):   return "pf"
    if _ESIC_RE.search(txt): return "esic"
    return "fixed"


def calc_runtime_deductions(gross, ssa_ded_list, ssa_base, special_amounts, month_name):
    results = []
    for comp in ssa_ded_list:
        name       = comp.get("salary_component", "")
        abbr       = comp.get("abbr", "")
        ssa_amount = flt(comp.get("amount", 0))
        kind       = _classify(name, abbr)

        if kind == "pf":
            actual = flt(min(gross, PF_BASIC_CAP) * PF_RATE, 2)
        elif kind == "esic":
            base = flt(ssa_base)
            rate = (ssa_amount / base) if (base > 0 and ssa_amount > 0) else 0.0075
            actual = flt(gross * rate, 2)
        else:
            if name in special_amounts:
                actual = flt(special_amounts[name].get(month_name, ssa_amount), 2)
            else:
                actual = flt(ssa_amount, 2)

        if actual > 0:
            results.append({"abbr": abbr or name, "amount": actual})
    return results


# =============================================================================
#  SSA LOOKUP
# =============================================================================

def get_ssa_map(employees, as_of_date):
    if not employees:
        return {}
    from collections import defaultdict

    ssa_rows = frappe.db.sql("""
        SELECT ssa.employee, ssa.name AS ssa_name, ssa.salary_structure,
               ssa.from_date, ssa.gross_salary
        FROM `tabSalary Structure Assignment` ssa
        INNER JOIN (
            SELECT employee, MAX(from_date) AS max_from
            FROM `tabSalary Structure Assignment`
            WHERE employee IN %(employees)s
              AND from_date <= %(as_of)s AND docstatus = 1
            GROUP BY employee
        ) latest ON ssa.employee = latest.employee
               AND ssa.from_date = latest.max_from AND ssa.docstatus = 1
        WHERE ssa.employee IN %(employees)s
    """, {"employees": tuple(employees), "as_of": as_of_date}, as_dict=True)

    if not ssa_rows:
        return {}

    ssa_names    = [r.ssa_name for r in ssa_rows]
    ssa_base_map = {}
    for sn in ssa_names:
        try:
            ssa_base_map[sn] = flt(frappe.db.get_value("Salary Structure Assignment", sn, "base") or 0)
        except Exception:
            ssa_base_map[sn] = 0.0

    ded_rows = frappe.db.sql("""
        SELECT sd.parent AS ssa_name, sd.salary_component, sd.abbr,
               sd.amount, sd.employer_contribution
        FROM `tabSalary Details` sd
        WHERE sd.parent IN %(ssa_names)s
          AND sd.parenttype  = 'Salary Structure Assignment'
          AND sd.parentfield = 'deductions'
          AND IFNULL(sd.employer_contribution, 0) = 0
        ORDER BY sd.idx ASC
    """, {"ssa_names": tuple(ssa_names)}, as_dict=True)

    missing = list({r.salary_component for r in ded_rows if not (r.abbr or "").strip()})
    comp_abbr_map = {}
    if missing:
        for r in frappe.db.sql(
            "SELECT name, salary_component_abbr AS abbr FROM `tabSalary Component` WHERE name IN %(c)s",
            {"c": tuple(missing)}, as_dict=True
        ):
            comp_abbr_map[r.name] = r.abbr

    ded_by_ssa = defaultdict(list)
    for d in ded_rows:
        abbr = (d.abbr or "").strip() or comp_abbr_map.get(d.salary_component, d.salary_component)
        ded_by_ssa[d.ssa_name].append({
            "salary_component": d.salary_component,
            "abbr":   abbr,
            "amount": flt(d.amount),
        })

    return {
        r.employee: {
            "salary_structure": r.salary_structure,
            "gross_salary":     flt(r.gross_salary),
            "ssa_base":         ssa_base_map.get(r.ssa_name, 0.0),
            "deductions":       ded_by_ssa.get(r.ssa_name, []),
        }
        for r in ssa_rows
    }


def get_special_monthly_amounts(ssa_map):
    all_names = {
        d["salary_component"]
        for ssa in ssa_map.values()
        for d in ssa.get("deductions", [])
        if _classify(d.get("salary_component", ""), d.get("abbr", "")) == "fixed"
    }
    if not all_names:
        return {}

    special = frappe.db.sql(
        "SELECT name FROM `tabSalary Component` WHERE name IN %(n)s AND is_special_component=1",
        {"n": tuple(all_names)}, as_dict=True
    )
    if not special:
        return {}

    snames = [r.name for r in special]
    rows   = frappe.db.sql(
        "SELECT ssc.parent AS component_name, ssc.month, ssc.amount "
        "FROM `tabSpecial Salary Component` ssc WHERE ssc.parent IN %(n)s ORDER BY ssc.idx",
        {"n": tuple(snames)}, as_dict=True
    )
    result = {}
    for r in rows:
        result.setdefault(r.component_name, {})[r.month] = flt(r.amount)
    return result


def get_holiday_dates(company, start_date, end_date):
    try:
        hl = frappe.db.get_value("Company", company, "default_holiday_list")
        if not hl:
            return set()
        rows = frappe.db.sql(
            "SELECT holiday_date FROM `tabHoliday` "
            "WHERE parent=%(hl)s AND holiday_date BETWEEN %(s)s AND %(e)s",
            {"hl": hl, "s": start_date, "e": end_date}, as_dict=True
        )
        return {str(getdate(r.holiday_date)) for r in rows}
    except Exception:
        return set()


def fmt_num(amount):
    try:
        amount = flt(amount)
        return "0" if amount == 0 else "{:,.2f}".format(amount)
    except Exception:
        return str(amount)


ROWS_FIRST_PAGE = 13
ROWS_OTHER_PAGE = 15
 
# ---------------------------------------------------------------------------
# Column definitions
#
# Columns with little content (OT Hrs, OT Pay, SSA Total, etc.) get narrow
# widths. Deduction columns get wider. Text wraps inside cells.
# ---------------------------------------------------------------------------
_COLS = [
    # fn               header              align  pct
    ("sr",             "Sr",               "c",   1.6),   # tiny — just a number
    ("employee",       "Employee",         "l",   8.5),   # name + ID stacked
    ("attendance",     "Attendance",       "l",   9.0),   # WD/P/HD/PD/A/Hol grid
    ("total_ot_hours", "OT\nHrs",          "r",   3.2),   # narrow — small value
    ("base_pay",       "Base\nPay",        "r",   5.5),
    ("ot_payable",     "OT\nPay",          "r",   4.8),   # narrow
    # ── SSA (Fixed) group ──────────────────────────────────────────────────
    ("ssa_gross",      "SSA\nGross",       "r",   5.5),
    ("ssa_ded",        "SSA Deductions",   "l",   9.5),   # wide — multi-item list
    ("ssa_tot",        "SSA\nTotal",       "r",   4.8),   # narrow
    ("ssa_net",        "SSA\nNet",         "r",   5.5),
    # ── Actual (Runtime) group ────────────────────────────────────────────
    ("gross_payable",  "Gross",            "r",   5.5),
    ("rt_ded",         "Deductions",       "l",   9.5),   # wide — multi-item list
    ("rt_tot",         "Total\nDed",       "r",   4.8),   # narrow
    ("rt_net",         "Net\nPayable",     "r",   5.8),
]
 
_GROUPS = [
    ("Attendance",       "attendance",    "attendance"),
    ("Pay",              "total_ot_hours","ot_payable"),
    ("SSA (Fixed)",      "ssa_gross",     "ssa_net"),
    ("Actual (Runtime)", "gross_payable", "rt_net"),
]
 
# Thick right border after these columns (group right edges)
_GROUP_EDGE = {"employee", "attendance", "ot_payable", "ssa_net", "rt_net"}
 
# The 6 attendance fields packed into the single attendance cell
_ATT_FIELDS = [
    ("WD",  "total_days"),
    ("P",   "total_present"),
    ("HD",  "total_halfday"),
    ("PD",  "payment_days"),
    ("A",   "total_absent"),
    ("Hol", "total_holiday"),
]
 
# ---------------------------------------------------------------------------
# CSS — matches PF Register style exactly
# header font sizes, signature block, group edges, row styling
# ---------------------------------------------------------------------------
_CSS = """<style>
* { margin:0; padding:0; box-sizing:border-box; }
 
body {
    font-family: Arial, sans-serif;
    font-size: 8px;
    color: #000;
    background: #fff;
}
 
/* ── Header ── matches PF register */
.hdr {
    text-align: center;
    border-bottom: 2px solid #000;
    padding: 6px 0 5px;
    margin-bottom: 4px;
}
.hdr .co  { font-size: 17px; font-weight: 900; letter-spacing: 0.5px; text-transform: uppercase; }
.hdr .ttl { font-size: 12px; font-weight: 700; margin-top: 2px; }
.hdr .per { font-size: 10px; margin-top: 1px; color: #333; }
 
/* Continuation page header */
.cont-hdr {
    text-align: center;
    font-size: 8.5px;
    color: #555;
    border-bottom: 1px solid #000;
    padding-bottom: 2px;
    margin-bottom: 3px;
    font-weight: 700;
}
 
/* ── Table ── */
table.dt {
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
}
 
table.dt th,
table.dt td {
    border: 0.5px solid #000;
    padding: 2px;
    vertical-align: top;
    /* allow text to wrap inside narrow cells */
    white-space: normal;
    word-wrap: break-word;
    overflow: hidden;
}
 
/* Group header row */
table.dt th.grp {
    text-align: center;
    font-weight: 900;
    font-size: 8px;
    padding: 4px 3px;
    background: #f0f0f0;
}
 
/* Column sub-header row */
table.dt th.col {
    font-size: 7px;
    font-weight: 800;
    text-align: center;
    vertical-align: middle;
    line-height: 1.3;
    background: #f0f0f0;
    white-space: pre-line;   /* honour \n in header labels */
    word-wrap: break-word;
}
 
/* Alignment helpers for header cells */
.emp-hdr { text-align: left;  padding-left: 4px; }
.att-hdr { text-align: left;  padding-left: 4px; }
.ded-hdr { text-align: left;  padding-left: 4px; }
.num-hdr { text-align: right; padding-right: 4px; }
 
/* ── Group edge — thick right border ── */
.ge {
    border-right: 1.5px solid #000 !important;
}
 
/* ── Employee cell ── */
.en  { font-weight: 900; font-size: 8px; }
.eid { font-size: 6.5px; color: #222; margin-top: 1px; }
 
/* ── Attendance sub-table ── */
table.att {
    width: 100%;
    border-collapse: collapse;
}
table.att td {
    border: none;
    font-size: 7px;
    padding: 0 1px;
}
.al { font-weight: 900; padding-right: 2px; white-space: nowrap; }
.av { text-align: right; padding-right: 5px; }
 
/* ── Number cells ── */
.num    { text-align: right; font-weight: 700;  padding-right: 3px; font-size: 7.5px; }
.num-lg { text-align: right; font-weight: 900;  padding-right: 3px; font-size: 7.5px; }
.net    { text-align: right; font-weight: 900;  padding-right: 3px; font-size: 8px; }
 
/* ── Deduction sub-table ── */
table.ded {
    width: 100%;
    table-layout: fixed;
    border-collapse: collapse;
}
table.ded td {
    border: none;
    font-size: 7px;
    padding: 0 1px;
    word-wrap: break-word;
}
/* label narrower (40%), value wider (60%) for readability */
.da { width: 40%; text-align: left;  font-weight: 900; }
.dv { width: 60%; text-align: right; }
 
.dnil {
    text-align: center;
    display: block;
    width: 100%;
    font-size: 7px;
}
 
/* ── Row backgrounds ── */
.re { background: #fff; }
.ro { background: #fff; }
.tb { background: #fff; }
 
/* ── Total row label ── */
.tlbl {
    font-weight: 900;
    text-align: right;
    border-right: 1.5px solid #000 !important;
    font-size: 8px;
}
 
/* ── Page footer ── */
.pg-foot {
    display: flex;
    justify-content: space-between;
    border-top: 1px solid #000;
    margin-top: 3px;
    padding-top: 2px;
    font-size: 7.5px;
    color: #444;
}
 
/* ── Signature block — matches PF register exactly ── */
.sig {
    display: flex;
    justify-content: space-between;
    margin-top: 18px;
    padding: 0 10px;
}
.sig-b   { text-align: center; width: 160px; }
.sig-l   { border-top: 1px solid #000; margin-bottom: 3px; }
.sig-t   { font-size: 9px; font-weight: 700; }
.sig-d   { font-size: 8px; color: #555; margin-top: 3px; }
 
.nd {
    text-align: center;
    padding: 12px;
    font-style: italic;
    font-size: 8px;
}
</style>"""
 
 
# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
 
def _colgroup():
    total = sum(w for *_, w in _COLS)
    out   = "<colgroup>"
    for *_, w in _COLS:
        out += '<col style="width:{:.3f}%;">'.format(w * 100.0 / total)
    return out + "</colgroup>"
 
 
def _thead():
    col_fns = [fn for fn, *_ in _COLS]
 
    group_of  = {}
    group_fns = {}
    for label, first_fn, last_fn in _GROUPS:
        in_range = False
        group_fns[label] = []
        for fn in col_fns:
            if fn == first_fn:
                in_range = True
            if in_range:
                group_of[fn] = label
                group_fns[label].append(fn)
            if fn == last_fn:
                in_range = False
 
    # ── Row 1: group spans + standalone columns ──────────────────────────
    r1      = "<tr>"
    emitted = set()
 
    for fn, hdr, _, _ in _COLS:
        ge = " ge" if fn in _GROUP_EDGE else ""
 
        if fn in group_of:
            g = group_of[fn]
            if g not in emitted:
                last_g  = group_fns[g][-1]
                g_ge    = " ge" if last_g in _GROUP_EDGE else ""
                r1 += (
                    '<th class="grp{ge}" colspan="{span}">{label}</th>'
                ).format(ge=g_ge, span=len(group_fns[g]), label=g)
                emitted.add(g)
            # member columns emitted as group cell — skip individual
        else:
            # standalone column spans both header rows
            r1 += '<th class="col{ge}" rowspan="2">{hdr}</th>'.format(
                ge=ge, hdr=hdr)
 
    r1 += "</tr>"
 
    # ── Row 2: column labels for grouped columns only ────────────────────
    r2 = "<tr>"
    for fn, hdr, _, _ in _COLS:
        if fn not in group_of:
            continue
        ge = " ge" if fn in _GROUP_EDGE else ""
        if fn == "employee":
            cls = "col emp-hdr"
        elif fn in ("attendance", "ssa_ded", "rt_ded"):
            cls = "col att-hdr"
        elif fn == "sr":
            cls = "col"
        else:
            cls = "col num-hdr"
        r2 += '<th class="{cls}{ge}">{hdr}</th>'.format(cls=cls, ge=ge, hdr=hdr)
    r2 += "</tr>"
 
    return "<thead>{r1}{r2}</thead>".format(r1=r1, r2=r2)
 
 
def _fmt(v):
    if v is None or v == "":
        return ""
    try:
        fv = float(v)
        return "" if fv == 0 else "{:,.2f}".format(fv)
    except Exception:
        return str(v)
 
 
def _fmt_att(v):
    if v is None or v == "":
        return ""
    try:
        fv = float(v)
        return str(int(fv)) if fv == int(fv) else "{:.1f}".format(fv)
    except Exception:
        return str(v)
 
 
def _att_cell(row):
    top = _ATT_FIELDS[:3]
    bot = _ATT_FIELDS[3:]

    def _row(fields, border_top=False):
        cells = ""
        for i, (lbl, fn) in enumerate(fields):
            val = _fmt_att(row.get(fn, ""))
            # dashed right border between columns, dashed top for second row
            right_border = "border-right:1px dashed #999;" if i < len(fields)-1 else ""
            top_border   = "border-top:1px dashed #999;" if border_top else ""
            cells += (
                '<td class="al" style="padding:1px 2px;{tb}">{lbl}:</td>'
                '<td class="av" style="padding:1px 3px 1px 0;{rb}{tb}">{val}</td>'
            ).format(lbl=lbl, val=val, rb=right_border, tb=top_border)
        return "<tr>{}</tr>".format(cells)

    return (
        '<table class="att" style="border-collapse:collapse;width:100%;">'
        '{}{}'
        '</table>'
    ).format(_row(top, border_top=False), _row(bot, border_top=True))
 
def _ded_cell(ded_list):
    if not ded_list:
        return '<span class="dnil">\u2014</span>'
    rows = ""
    last = len(ded_list) - 1
    for i, d in enumerate(ded_list):
        sep = "border-bottom:1px dashed #bbb;" if i < last else ""
        rows += (
            '<tr style="{sep}">'
            '<td class="da" style="{sep}">{abbr}</td>'
            '<td class="dv" style="{sep}">{amt}</td>'
            '</tr>'
        ).format(sep=sep, abbr=d["abbr"], amt=fmt_num(d["amount"]))
    return '<table class="ded">{}</table>'.format(rows)
 
def _td(cls, content, ge=False):
    return '<td class="{cls}{ge}">{content}</td>'.format(
        cls=cls, ge=" ge" if ge else "", content=content)
 
 
def _render_row(row, row_idx, is_total=False):
    stripe = "tb" if is_total else ("re" if row_idx % 2 == 0 else "ro")
    MERGE_COLS = 3   # Sr + Employee + Attendance
 
    tr     = "<tr>"
    merged = False
 
    for fn, _, align, _ in _COLS:
        ge = fn in _GROUP_EDGE
 
        # ── Total row: merge first 3 cols ──────────────────────────────
        if is_total and fn in ("sr", "employee", "attendance"):
            if not merged:
                tr += (
                    '<td class="tlbl tb ge" colspan="{n}">Total</td>'
                ).format(n=MERGE_COLS)
                merged = True
            continue
 
        # ── Sr ──────────────────────────────────────────────────────────
        if fn == "sr":
            tr += _td("c " + stripe, row.get("sr", ""), ge)
 
        # ── Employee (Name + ID stacked) ────────────────────────────────
        elif fn == "employee":
            name  = row.get("employee_name", "") or ""
            eid   = row.get("employee", "")      or ""
            inner = '<div class="en">{}</div>'.format(name)
            if eid and not is_total:
                inner += '<div class="eid">{}</div>'.format(eid)
            tr += _td("l " + stripe, inner, ge)
 
        # ── Attendance grid ─────────────────────────────────────────────
        elif fn == "attendance":
            tr += _td(stripe, "" if is_total else _att_cell(row), ge)
 
        # ── OT Hours ────────────────────────────────────────────────────
        elif fn == "total_ot_hours":
            tr += _td("num " + stripe, _fmt_att(row.get(fn, "")), ge)
 
        # ── Base Pay / OT Pay (stored as fmt_num strings) ───────────────
        elif fn in ("base_pay", "ot_payable"):
            tr += _td("num " + stripe, row.get(fn, "") or "", ge)
 
        # ── SSA Gross ───────────────────────────────────────────────────
        elif fn == "ssa_gross":
            tr += _td("num " + stripe, _fmt(row.get("_ssa_gross", 0)), ge)
 
        # ── SSA Deductions list ─────────────────────────────────────────
        elif fn == "ssa_ded":
            tr += _td("l " + stripe, _ded_cell(row.get("_ssa_ded_list", [])), ge)
 
        # ── SSA Total ───────────────────────────────────────────────────
        elif fn == "ssa_tot":
            tr += _td("num " + stripe, _fmt(row.get("_ssa_total_ded", 0)), ge)
 
        # ── SSA Net ─────────────────────────────────────────────────────
        elif fn == "ssa_net":
            tr += _td("num-lg " + stripe, _fmt(row.get("_ssa_net", 0)), ge)
 
        # ── Gross (after SSA, before Runtime) ───────────────────────────
        elif fn == "gross_payable":
            tr += _td("num-lg " + stripe, _fmt(row.get("_gross", 0)), ge)
 
        # ── Runtime Deductions list ─────────────────────────────────────
        elif fn == "rt_ded":
            tr += _td("l " + stripe, _ded_cell(row.get("_rt_ded_list", [])), ge)
 
        # ── Runtime Total ───────────────────────────────────────────────
        elif fn == "rt_tot":
            tr += _td("num " + stripe, _fmt(row.get("_rt_total_ded", 0)), ge)
 
        # ── Net Payable ─────────────────────────────────────────────────
        elif fn == "rt_net":
            tr += _td("net " + stripe, _fmt(row.get("_runtime_net", 0)), ge)
 
        # ── Fallback ────────────────────────────────────────────────────
        else:
            tr += _td(align + " " + stripe, row.get(fn, "") or "", ge)
 
    return tr + "</tr>"
 
 
def _page_table(page_rows, start_idx):
    tbody = "<tbody>"
    for j, row in enumerate(page_rows):
        is_tot = bool(row.get("_is_total"))
        tbody += _render_row(row, 0 if is_tot else (start_idx + j), is_total=is_tot)
    tbody += "</tbody>"
    return '<table class="dt">{cg}{th}{tbody}</table>'.format(
        cg=_colgroup(), th=_thead(), tbody=tbody)
 
 
def _sig_html():
    """Signature block — matches PF Register layout (space-between, 3 blocks)."""
    labels = ["Prepared By", "Checked By", "Authorised Signatory"]
    blocks = "".join(
        '<div class="sig-b">'
        '<div class="sig-l"></div>'
        '<div class="sig-t">{l}</div>'
        '</div>'.format(l=l)
        for l in labels
    )
    return '<div class="sig">{}</div>'.format(blocks)
 
 
def _build_total_row(data):
    keys = [
        "_base_pay", "_ot_payable", "_gross",
        "_ssa_gross", "_ssa_total_ded", "_ssa_net",
        "_rt_total_ded", "_runtime_net",
    ]
    tot = {k: 0.0 for k in keys}
    for row in data:
        for k in keys:
            tot[k] += flt(row.get(k, 0))
    return {
        "sr": "", "employee": "", "employee_name": "Total",
        "total_days": "", "total_present": "", "total_halfday": "",
        "payment_days": "", "total_absent": "", "total_holiday": "",
        "total_ot_hours": "",
        "base_pay": fmt_num(tot["_base_pay"]),
        "ot_payable": fmt_num(tot["_ot_payable"]),
        "gross_payable": fmt_num(tot["_gross"]),
        **{k: tot[k] for k in keys},
        "_ssa_ded_list": [],
        "_rt_ded_list":  [],
        "_is_total": True,
    }
 
 
def _paginate(detail_rows, total_row):
    if not detail_rows:
        return [[total_row] if total_row else []]
    pages = []
    idx   = 0
    first = True
    while idx < len(detail_rows):
        lim   = max(1, (ROWS_FIRST_PAGE if first else ROWS_OTHER_PAGE) - 2)
        chunk = detail_rows[idx: idx + lim]
        pages.append(list(chunk))
        idx  += len(chunk)
        first = False
    if total_row:
        pages[-1].append(total_row)
    return pages
 
 
def _build_html(data, company, month_name, year):
    # ── Page 1 header — large company name, matches PF register ──────────
    page1_hdr = (
        '<div class="hdr">'
        '<div class="co">{co}</div>'
        '<div class="ttl">Attendance &amp; Wages Register</div>'
        '<div class="per">For the Month of {mo} {yr}</div>'
        '</div>'
    ).format(co=company, mo=month_name, yr=year)
 
    # ── Continuation header ───────────────────────────────────────────────
    cont_hdr = (
        '<div class="cont-hdr">'
        '{co} &mdash; Attendance &amp; Wages Register &mdash; {mo} {yr} (contd.)'
        '</div>'
    ).format(co=company, mo=month_name, yr=year)
 
    # Assign Sr numbers
    for i, row in enumerate(data, start=1):
        row["sr"] = i
 
    total_row   = _build_total_row(data) if data else None
    pages       = _paginate(data, total_row) if data else [[]]
    total_pages = len(pages)
    parts       = []
    row_counter = 0
 
    for pn, page_rows in enumerate(pages):
        pb       = '<div style="page-break-before:always;"></div>' if pn > 0 else ""
        is_last  = (pn == total_pages - 1)
        hdr_html = page1_hdr if pn == 0 else cont_hdr
 
        if not data:
            tbl = (
                '<table class="dt">{cg}{th}'
                '<tbody><tr><td colspan="{nc}" class="nd">'
                'No data for this period.</td></tr></tbody></table>'
            ).format(cg=_colgroup(), th=_thead(), nc=len(_COLS))
        else:
            tbl = _page_table(page_rows, row_counter)
            row_counter += sum(1 for r in page_rows if not r.get("_is_total"))
 
        pg_foot = (
            '<div class="pg-foot">'
            '<span>{co} &mdash; {mo} {yr}</span>'
            '<span>Page {pn} of {tp}</span>'
            '</div>'
        ).format(co=company, mo=month_name, yr=year, pn=pn + 1, tp=total_pages)
 
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
        "margin-right":  "5mm",
        "margin-bottom": "8mm",
        "margin-left":   "5mm",
        "encoding":      "UTF-8",
        "no-outline":    None,
    })
    ts  = frappe.utils.now_datetime().strftime("%Y%m%d_%H%M%S")
    fn  = "{}_{}.pdf".format(prefix, ts)
    with open(frappe.utils.get_files_path(fn, is_private=0), "wb") as fh:
        fh.write(pdf)
    doc = frappe.get_doc({
        "doctype":    "File",
        "file_name":  fn,
        "is_private": 0,
        "file_url":   "/files/{}".format(fn),
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return doc.file_url
 
 
@frappe.whitelist()
def print_report(filters):
    if isinstance(filters, str):
        filters = json.loads(filters)
    validate_filters(filters)
    data = get_data(filters)
 
    company    = filters.get("company", "")
    year       = int(filters["year"])
    month      = int(filters["month"])
    month_name = date(year, month, 1).strftime("%B")
 
    html = _build_html(data, company, month_name, year)
    return _save_pdf(html, "Attendance_Wages_Register")