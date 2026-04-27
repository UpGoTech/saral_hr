# Copyright (c) 2026, sj and contributors
# For license information, please see license.txt

import frappe
import json
import calendar

from frappe import _
from frappe.utils import flt
from frappe.utils.pdf import get_pdf

# ════════════════════════════════════════════════════════════════════════════
#  Constants
# ════════════════════════════════════════════════════════════════════════════

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

MONTH_MAP = {m: i + 1 for i, m in enumerate(MONTH_NAMES)}

STATUS_CODE = {
    "Present":  "P",
    "On Tour":  "T",
    "Absent":   "A",
    "Half Day": "HD",
    "Holiday":  "H",
}

PF_RATE      = 0.12
PF_BASIC_CAP = 15000.0

ROWS_FIRST_PAGE = 8
ROWS_OTHER_PAGE = 9


# ════════════════════════════════════════════════════════════════════════════
#  Helpers
# ════════════════════════════════════════════════════════════════════════════

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


def _col(label, fn, ft="Data", w=80, **kw):
    return {"label": _(label), "fieldname": fn, "fieldtype": ft, "width": w, **kw}


def _fmt(v):
    if v is None or v == "" or v == 0:
        return ""
    try:
        fv = float(v)
        if fv == 0:
            return ""
        return "{0:,.2f}".format(fv)
    except (TypeError, ValueError):
        return str(v)


def _fmt_days(v):
    if v is None or v == "" or v == 0:
        return ""
    try:
        fv = float(v)
        if fv == 0:
            return ""
        return str(int(fv)) if fv == int(fv) else "{:.1f}".format(fv)
    except (TypeError, ValueError):
        return str(v)


def _company_label(f):
    c = _parse_list(f.get("company"))
    return ", ".join(c) if c else (frappe.defaults.get_global_default("company") or "")


def _ot_decimal_to_hhmm(ot_decimal):
    """
    Convert decimal OT hours (e.g. 4.5 → "04:30", 1.25 → "01:15") to HH:MM string.
    Returns "" if zero.
    """
    dec = flt(ot_decimal or 0)
    if dec <= 0:
        return ""
    whole = int(dec)
    mins  = round((dec - whole) * 60)
    return "{0:02d}:{1:02d}".format(whole, mins)


def _ot_decimal_to_minutes(ot_decimal):
    """Convert decimal OT hours to integer minutes (4.5 → 270)."""
    dec = flt(ot_decimal or 0)
    if dec <= 0:
        return 0
    whole = int(dec)
    mins  = round((dec - whole) * 60)
    return whole * 60 + mins


# ════════════════════════════════════════════════════════════════════════════
#  Classify salary component
# ════════════════════════════════════════════════════════════════════════════

def _classify_component(comp_name, abbr=""):
    name = (comp_name + " " + abbr).lower()
    if any(k in name for k in ["pf", "provident fund", "emp pf", "employee pf"]):
        return "pf"
    if any(k in name for k in ["esic", "esi", "emp esi", "employee esi", "emp esic"]):
        return "esic"
    return "fixed"


# ════════════════════════════════════════════════════════════════════════════
#  Runtime deduction engine (mirrors dashboard JS logic exactly)
#  PF: always 12% of min(gross, 15000) — no wage-limit suppression
#  ESIC: rate derived from SSA base, applied on live gross
# ════════════════════════════════════════════════════════════════════════════

def _calc_runtime_deductions(gross, ssa_deductions, pf_wage_limit, ssa_base,
                               special_monthly_amounts, month_name):
    results      = []
    total_actual = 0.0
    total_ssa    = 0.0

    for comp in ssa_deductions:
        kind       = _classify_component(comp.get("salary_component", ""), comp.get("abbr", ""))
        ssa_amount = flt(comp.get("amount", 0))
        actual     = 0.0
        applicable = True
        comp_name  = comp.get("salary_component", "")

        is_special = comp_name in (special_monthly_amounts or {})

        if kind == "pf":
            # Always calculate PF on gross — capped at ₹15,000 basic
            pf_capped = min(gross, PF_BASIC_CAP)
            actual    = pf_capped * PF_RATE
            applicable = True

        elif kind == "esic":
            base      = flt(ssa_base or 0)
            esic_rate = (ssa_amount / base) if (base > 0 and ssa_amount > 0) else 0.0075
            actual    = gross * esic_rate
            applicable = True

        else:
            if is_special and month_name and special_monthly_amounts:
                month_amts = special_monthly_amounts.get(comp_name, {})
                actual     = flt(month_amts.get(month_name, ssa_amount))
                applicable = actual > 0
            else:
                actual     = ssa_amount
                applicable = ssa_amount > 0

        if applicable:
            total_actual += actual

        total_ssa += ssa_amount

        results.append({
            "salary_component": comp_name,
            "abbr":             comp.get("abbr", "") or comp_name,
            "kind":             kind,
            "is_special":       is_special,
            "ssa_amount":       ssa_amount,
            "actual_amount":    flt(actual, 2),
            "applicable":       applicable,
        })

    return {
        "components":   results,
        "total_actual": flt(total_actual, 2),
        "total_ssa":    flt(total_ssa, 2),
        "net_actual":   flt(gross - total_actual, 2),
        "net_ssa":      flt(gross - total_ssa, 2),
    }


# ════════════════════════════════════════════════════════════════════════════
#  Fetch SSA deductions for an employee
# ════════════════════════════════════════════════════════════════════════════

def _get_ssa_data(employee, start_date):
    """Return (ssa_deductions, ssa_base, pf_wage_limit, special_monthly_amounts)."""
    ssa_rows = frappe.db.get_all(
        "Salary Structure Assignment",
        filters=[
            ["employee", "=", employee],
            ["from_date", "<=", start_date],
            ["docstatus", "=", 1],
        ],
        fields=["name", "salary_structure", "company"],
        order_by="from_date desc",
        limit=1,
    )
    if not ssa_rows:
        return [], 0.0, 0.0, {}

    doc = frappe.get_doc("Salary Structure Assignment", ssa_rows[0]["name"])

    ssa_deductions = []
    for row in (doc.deductions or []):
        if int(row.employer_contribution or 0):
            continue
        ssa_deductions.append({
            "salary_component": row.salary_component or "",
            "abbr":             row.abbr or "",
            "amount":           flt(row.amount or 0),
        })

    ssa_base = flt(doc.base or 0)

    # PF wage limit — kept for display info, PF always calculated now
    pf_wage_limit = 0.0
    try:
        company = ssa_rows[0].get("company") or getattr(doc, "company", None)
        if company:
            pf_wage_limit = flt(frappe.db.get_value("Company", company, "pf_wage_limit") or 0)
    except Exception:
        pf_wage_limit = 0.0

    fixed_comp_names = [
        c["salary_component"]
        for c in ssa_deductions
        if _classify_component(c["salary_component"], c.get("abbr", "")) == "fixed"
    ]
    special_monthly_amounts = {}
    if fixed_comp_names:
        special_comps = frappe.db.get_all(
            "Salary Component",
            filters={"salary_component": ["in", fixed_comp_names], "is_special_component": 1},
            fields=["salary_component"],
        )
        for sc in special_comps:
            cname = sc["salary_component"]
            rows  = frappe.db.get_all(
                "Special Salary Component",
                filters={"parent": cname, "parenttype": "Salary Component"},
                fields=["month", "amount"],
                order_by="idx asc",
            )
            if rows:
                special_monthly_amounts[cname] = {r["month"]: flt(r["amount"]) for r in rows}

    return ssa_deductions, ssa_base, pf_wage_limit, special_monthly_amounts


# ════════════════════════════════════════════════════════════════════════════
#  Core data function
# ════════════════════════════════════════════════════════════════════════════

def _get_data(f):
    ms  = f.get("month", "")
    ys  = f.get("year", "")
    mn  = MONTH_MAP.get(ms, 0)
    cos = _parse_list(f.get("company"))

    cols = [
        _col("Sr",            "sr_no",         "Data",    40),
        _col("Employee Name", "employee_name",  "Data",   160),
        _col("Employee ID",   "employee",       "Data",   130),
    ]

    if not mn or not ys or not cos:
        return cols, []

    yi         = int(ys)
    last       = calendar.monthrange(yi, mn)[1]
    fd         = "{0}-{1:02d}-01".format(yi, mn)
    td         = "{0}-{1:02d}-{2:02d}".format(yi, mn, last)
    month_name = MONTH_NAMES[mn - 1]

    for d in range(1, last + 1):
        cols.append(_col(str(d), "day_{0}".format(d), "Data", 38))

    cols += [
        _col("Total Days",     "total_days",    "Float",  65, precision=0),
        _col("Present",        "present_days",  "Float",  65, precision=1),
        _col("Absent",         "absent_days",   "Float",  65, precision=1),
        _col("Half Day",       "half_days",     "Float",  65, precision=0),
        _col("Holiday",        "holiday_days",  "Float",  65, precision=0),
        _col("On Tour",        "on_tour_days",  "Float",  65, precision=0),
        _col("Payment Days",   "payment_days",  "Float",  80, precision=1),
        _col("OT Hours",       "ot_hours",      "Data",   70),
        _col("Daily Rate (₹)", "daily_rate",    "Float",  90, precision=2),
        _col("Base Pay (₹)",   "base_pay",      "Float",  90, precision=2),
        _col("OT Pay (₹)",     "ot_pay",        "Float",  80, precision=2),
        _col("Gross Pay (₹)",  "gross_pay",     "Float",  95, precision=2),
    ]

    co_tuple = tuple(cos) if len(cos) > 1 else (cos[0], cos[0])

    # ── ADR records — ot_hours stored as decimal float in DB ─────────────
    adr_rows = frappe.db.sql("""
        SELECT adr.employee, adr.attendance_date, adr.status,
               adr.ot_hours, adr.daily_rate
        FROM   `tabAttendance Daily Rate` adr
        INNER  JOIN `tabCompany Link` cl ON cl.name = adr.employee
        WHERE  cl.company IN %(co)s
          AND  adr.attendance_date BETWEEN %(fd)s AND %(td)s
          AND  adr.docstatus < 2
        ORDER  BY adr.employee, adr.attendance_date
    """, {"co": co_tuple, "fd": fd, "td": td}, as_dict=True)

    if not adr_rows:
        return cols, []

    emp_filter = _parse_list(f.get("employee"))

    emp_ids = list({r.employee for r in adr_rows})
    _id_tuple = tuple(emp_ids) if len(emp_ids) > 1 else (emp_ids[0], emp_ids[0])

    emp_info = {
        r.name: r
        for r in frappe.db.sql("""
            SELECT cl.name, cl.full_name, cl.company
            FROM   `tabCompany Link` cl
            WHERE  cl.name IN %(ids)s
        """, {"ids": _id_tuple}, as_dict=True)
    }

    _hl_rows = frappe.db.sql("""
        SELECT DISTINCT cl.holiday_list
        FROM   `tabCompany Link` cl
        WHERE  cl.name IN %(ids)s
          AND  cl.holiday_list IS NOT NULL
          AND  cl.holiday_list != ''
    """, {"ids": _id_tuple}, as_dict=True)

    _hl_names = [r.holiday_list for r in _hl_rows if r.holiday_list]

    if _hl_names:
        _hl_tuple = tuple(_hl_names) if len(_hl_names) > 1 else (_hl_names[0], _hl_names[0])
        holiday_rows = frappe.db.sql("""
            SELECT hl.holiday_date
            FROM   `tabHoliday List` hll
            INNER  JOIN `tabHoliday` hl ON hl.parent = hll.name
            WHERE  hll.name IN %(hl)s
              AND  hl.holiday_date BETWEEN %(fd)s AND %(td)s
            ORDER  BY hl.holiday_date
        """, {"hl": _hl_tuple, "fd": fd, "td": td}, as_dict=True)
    else:
        holiday_rows = frappe.db.sql("""
            SELECT hl.holiday_date
            FROM   `tabHoliday List` hll
            INNER  JOIN `tabHoliday` hl ON hl.parent = hll.name
            WHERE  hll.from_date <= %(td)s
              AND  hll.to_date   >= %(fd)s
              AND  hl.holiday_date BETWEEN %(fd)s AND %(td)s
            ORDER  BY hl.holiday_date
        """, {"fd": fd, "td": td}, as_dict=True)

    holiday_set = set()
    for hr_ in holiday_rows:
        hd = hr_.holiday_date
        holiday_set.add(str(hd.date() if hasattr(hd, "date") else hd)[:10])

    emp_order = []
    emp_dict  = {}

    for row in adr_rows:
        emp = row.employee
        if emp_filter and emp not in emp_filter:
            continue

        day_str = str(row.attendance_date.date() if hasattr(row.attendance_date, "date") else row.attendance_date)[:10]
        day_num = int(day_str[8:10])
        status  = row.status or ""
        code    = STATUS_CODE.get(status, "")
        dk      = "day_{0}".format(day_num)

        # ot_hours is stored as decimal float (4.5 = 4h30m)
        ot_decimal = flt(row.ot_hours or 0)
        ot_minutes = _ot_decimal_to_minutes(ot_decimal)

        if emp not in emp_dict:
            emp_order.append(emp)
            info = emp_info.get(emp, frappe._dict())
            emp_dict[emp] = {
                "employee":        emp,
                "employee_name":   info.get("full_name") or emp,
                "present_days":    0.0,
                "absent_days":     0.0,
                "half_days":       0.0,
                "holiday_days":    0.0,
                "on_tour_days":    0.0,
                "payment_days":    0.0,
                "total_ot_dec":    0.0,   # accumulate decimal OT hours
                "daily_rate":      flt(row.daily_rate or 0),
                "base_pay":        0.0,
                "ot_pay":          0.0,
                "_adr_dates":      {},
            }
            for d2 in range(1, last + 1):
                emp_dict[emp]["day_{0}".format(d2)] = ""

        rec = emp_dict[emp]
        rec[dk] = code
        rec["_adr_dates"][day_str] = {
            "status":     status,
            "ot_decimal": ot_decimal,
            "ot_minutes": ot_minutes,
            "daily_rate": flt(row.daily_rate or 0),
        }

        rate = flt(row.daily_rate or 0)
        rec["total_ot_dec"] += ot_decimal
        rec["daily_rate"]    = rate

        if status in ("Present", "On Tour"):
            rec["present_days"]  += 1.0
            rec["payment_days"]  += 1.0
            rec["base_pay"]      += rate
            if status == "On Tour":
                rec["on_tour_days"] += 1.0
        elif status == "Absent":
            rec["absent_days"] += 1.0
        elif status == "Half Day":
            rec["half_days"]    += 1.0
            rec["present_days"] += 0.5
            rec["absent_days"]  += 0.5
            rec["payment_days"] += 0.5
            rec["base_pay"]     += rate / 2.0
        elif status == "Holiday":
            rec["holiday_days"] += 1.0

        if rate > 0 and ot_decimal > 0:
            rec["ot_pay"] += (rate / 8.0) * ot_decimal

    # ── Sandwich-eligible holiday pay ────────────────────────────────────
    for emp in emp_order:
        rec      = emp_dict[emp]
        adr_data = rec["_adr_dates"]

        for hdate in sorted(holiday_set):
            if hdate < fd or hdate > td:
                continue
            day_num = int(hdate[8:10])
            dk      = "day_{0}".format(day_num)

            hdr = adr_data.get(hdate, {})
            if not hdr:
                continue

            def _adj_status(from_date, direction):
                import datetime
                cur = datetime.date.fromisoformat(from_date)
                for _ in range(90):
                    cur += datetime.timedelta(days=direction)
                    dk2 = str(cur)
                    if dk2 < fd or dk2 > td:
                        return "outside"
                    if dk2 in holiday_set:
                        continue
                    adj = adr_data.get(dk2, {})
                    if not adj:
                        return "absent"
                    s = adj.get("status", "")
                    if s in ("Present", "On Tour"):
                        return "paid"
                    if s == "Absent":
                        return "absent"
                return "unknown"

            before = _adj_status(hdate, -1)
            after  = _adj_status(hdate, +1)

            if before == "absent" and after == "absent":
                pass  # sandwiched — no pay
            elif before == "paid" or after == "paid":
                rate = flt(hdr.get("daily_rate", 0))
                rec["payment_days"] += 1.0
                rec["base_pay"]     += rate
                rec[dk]              = "H✓"

    # ── SSA / runtime deduction data ─────────────────────────────────────
    all_ded_comps = {}   # comp_name → abbr (ordered)
    emp_ssa_data  = {}
    emp_rt_data   = {}

    for emp in emp_order:
        rec   = emp_dict[emp]
        gross = flt(rec["base_pay"]) + flt(rec["ot_pay"])

        try:
            ssa_ded, ssa_base, pf_limit, special = _get_ssa_data(emp, fd)
            emp_ssa_data[emp] = {
                "ssa_deductions": ssa_ded,
                "ssa_base":       ssa_base,
                "pf_wage_limit":  pf_limit,
                "special":        special,
            }

            rt = _calc_runtime_deductions(
                gross, ssa_ded, pf_limit, ssa_base, special, month_name
            )
            emp_rt_data[emp] = rt

            for comp in ssa_ded:
                cn = comp["salary_component"]
                if cn not in all_ded_comps:
                    all_ded_comps[cn] = comp.get("abbr") or cn

        except Exception as e:
            frappe.log_error(
                "DWR SSA load error for {0}: {1}".format(emp, e),
                "Daily Wage Calculation Report",
            )
            emp_ssa_data[emp] = {"ssa_deductions": [], "ssa_base": 0,
                                 "pf_wage_limit": 0, "special": {}}
            emp_rt_data[emp]  = {"components": [], "total_actual": 0, "total_ssa": 0,
                                 "net_actual": 0, "net_ssa": 0}

    # ── Add deduction columns (SSA + Actual paired per component) ────────
    for cn, abbr in all_ded_comps.items():
        safe = cn.replace(" ", "_").lower()
        cols.append(_col("SSA: " + abbr,    "ssa_ded_" + safe, "Float", 90, precision=2))
        cols.append(_col("Actual: " + abbr, "rt_ded_"  + safe, "Float", 90, precision=2))

    cols += [
        _col("Total SSA Ded (₹)",    "total_ssa_ded", "Float", 110, precision=2),
        _col("Total Actual Ded (₹)", "total_rt_ded",  "Float", 110, precision=2),
        _col("Net SSA (₹)",          "net_ssa",       "Float", 110, precision=2),
        _col("Net Actual (₹)",       "net_actual",    "Float", 110, precision=2),
    ]

    result = []
    for i, emp in enumerate(emp_order, 1):
        rec = emp_dict[emp]
        rt  = emp_rt_data.get(emp, {})

        # Format OT hours as HH:MM for display
        ot_str = _ot_decimal_to_hhmm(rec.get("total_ot_dec", 0))

        gross = flt(rec["base_pay"]) + flt(rec["ot_pay"])

        row_out = {
            "sr_no":         i,
            "employee":      emp,
            "employee_name": rec["employee_name"],
            "total_days":    last,
            "present_days":  rec["present_days"],
            "absent_days":   rec["absent_days"],
            "half_days":     rec["half_days"],
            "holiday_days":  rec["holiday_days"],
            "on_tour_days":  rec["on_tour_days"],
            "payment_days":  rec["payment_days"],
            "ot_hours":      ot_str,
            "daily_rate":    rec["daily_rate"],
            "base_pay":      flt(rec["base_pay"], 2),
            "ot_pay":        flt(rec["ot_pay"], 2),
            "gross_pay":     flt(gross, 2),
            "total_ssa_ded": flt(rt.get("total_ssa", 0), 2),
            "total_rt_ded":  flt(rt.get("total_actual", 0), 2),
            "net_ssa":       flt(rt.get("net_ssa", 0), 2),
            "net_actual":    flt(rt.get("net_actual", 0), 2),
        }

        for d in range(1, last + 1):
            row_out["day_{0}".format(d)] = rec.get("day_{0}".format(d), "")

        comp_map = {c["salary_component"]: c for c in rt.get("components", [])}
        for cn in all_ded_comps:
            safe = cn.replace(" ", "_").lower()
            ssa_ded_doc = next(
                (c for c in emp_ssa_data.get(emp, {}).get("ssa_deductions", [])
                 if c["salary_component"] == cn), None
            )
            ssa_val = flt(ssa_ded_doc["amount"]) if ssa_ded_doc else 0.0
            rt_val  = flt(comp_map[cn]["actual_amount"]) if cn in comp_map else 0.0
            row_out["ssa_ded_" + safe] = ssa_val
            row_out["rt_ded_"  + safe] = rt_val

        result.append(row_out)

    return cols, result


def execute(filters=None):
    return _get_data(filters or {})


# ════════════════════════════════════════════════════════════════════════════
#  CSS
# ════════════════════════════════════════════════════════════════════════════

_CSS = """<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI',Arial,sans-serif;font-size:8px;color:#111;background:#fff}

.hdr{text-align:center;border-bottom:2.5px solid #1a1a2e;padding:7px 6px 5px;margin-bottom:4px;background:linear-gradient(135deg,#f8f9ff,#eef2ff)}
.hdr .co{font-size:16px;font-weight:900;letter-spacing:1.5px;text-transform:uppercase;color:#1a1a2e}
.hdr .ttl{font-size:11.5px;font-weight:700;margin-top:2px;color:#2c3e9e}
.hdr .per{font-size:9.5px;margin-top:1px;color:#555}

.cont-hdr{text-align:center;font-size:8px;color:#666;border-bottom:1px solid #1a1a2e;padding-bottom:2px;margin-bottom:3px}

table.data-tbl{width:100%;border-collapse:collapse;table-layout:fixed}

table.data-tbl .grp-row th{font-size:7.5px;font-weight:800;text-align:center;vertical-align:middle;padding:3px 2px;border:1px solid #888;text-transform:uppercase;letter-spacing:0.05em}
.grp-identity{background:#1a1a2e;color:#fff}
.grp-days{background:#0d6efd;color:#fff}
.grp-summary{background:#6f42c1;color:#fff}
.grp-pay{background:#198754;color:#fff}
.grp-ssa{background:#ffc107;color:#1a1a2e}
.grp-actual{background:#dc3545;color:#fff}
.grp-net{background:#20c997;color:#1a1a2e}

table.data-tbl .sub-row th{font-size:7px;font-weight:700;text-align:center;vertical-align:middle;padding:2px 1px;border:1px solid #aaa;background:#f5f5f5;color:#333;word-break:break-word;line-height:1.2}

table.data-tbl td{border:1px solid #ccc;padding:1.5px 2px;font-size:7.5px;vertical-align:middle;overflow:hidden;word-break:break-word;line-height:1.25}

.emp-name{font-weight:700;font-size:8px;line-height:1.3}
.emp-id{font-size:6.5px;color:#666;margin-top:1px}

.r{text-align:right}.c{text-align:center}.l{text-align:left}
.nd{text-align:center;padding:14px;color:#888;font-size:10px}

.pg-foot{text-align:right;font-size:7.5px;color:#666;margin-top:3px}

.sig{display:flex;justify-content:space-between;width:100%;margin-top:16px}
.sig-b{text-align:center;width:160px}
.sig-l{border-top:1px solid #000;margin-bottom:2px}
.sig-t{font-size:9px;color:#333}
.sig-d{font-size:8px;color:#666;margin-top:4px}

.total-row td{background:#1a1a2e !important;color:#fff !important;font-weight:700;font-size:7.5px}
.total-row td.pay-cell{background:#198754 !important;color:#fff !important}
.total-row td.net-cell{background:#20c997 !important;color:#1a1a2e !important}

.lgd-bar{
    display:flex;flex-wrap:wrap;align-items:center;gap:6px;
    padding:3px 6px;margin:0 0 3px;
    background:#f8f9ff;border:1px solid #c7d2fe;border-radius:3px;
    font-size:7.5px;
}

/* Gross / Net highlighted cells in PDF */
.gross-cell{font-weight:700;color:#198754;}
.net-cell{font-weight:800;color:#0d6efd;}
.ded-cell{color:#c0392b;font-weight:600;}
</style>"""


# ════════════════════════════════════════════════════════════════════════════
#  HTML builder
# ════════════════════════════════════════════════════════════════════════════

DAY_COLOR = {"P": "#1a6b1a", "A": "#c0392b", "HD": "#e67e22",
             "T": "#2c3e50", "H": "#27ae60", "H✓": "#0d6efd"}


def _sig_html():
    labels = ["Prepared By", "Checked By", "Authorised Signatory"]
    blocks = "".join(
        '<div class="sig-b"><div class="sig-l"></div>'
        '<div class="sig-t">{l}</div>'
        '<div class="sig-d">Date: ___________</div></div>'.format(l=l)
        for l in labels
    )
    return '<div class="sig">{}</div>'.format(blocks)


def _legend_html():
    items = [
        ("P",  "#1a6b1a", "Present"),
        ("A",  "#c0392b", "Absent"),
        ("HD", "#e67e22", "Half Day"),
        ("T",  "#2c3e50", "On Tour"),
        ("H",  "#27ae60", "Holiday (unpaid)"),
        ("H✓", "#0d6efd", "Holiday (paid)"),
    ]
    parts = []
    for code, color, label in items:
        parts.append(
            '<span style="display:inline-flex;align-items:center;gap:2px;white-space:nowrap;">'
            '<b style="color:{c};font-size:8px;">{k}</b>'
            '<span style="color:#444;font-size:7.5px;">&#8211;{v}</span>'
            '</span>'.format(c=color, k=code, v=label)
        )
    return (
        '<div class="lgd-bar">'
        '<span style="font-weight:700;font-size:7.5px;color:#555;margin-right:4px;white-space:nowrap;">Legend:</span>'
        + " ".join(parts) +
        '<span style="margin-left:auto;font-size:7px;color:#6366f1;font-weight:500;">'
        'SSA = Fixed from Assignment &nbsp;|&nbsp; Actual = Runtime on live Gross'
        '</span>'
        '</div>'
    )


def _build_html(cols, data, co, mo, yr):
    mn   = MONTH_MAP.get(mo, 0)
    yi   = int(yr) if yr else 0
    last = calendar.monthrange(yi, mn)[1] if mn and yi else 31

    day_cols    = [c for c in cols if c["fieldname"].startswith("day_")]
    summ_fields = ["total_days", "present_days", "absent_days", "half_days",
                   "holiday_days", "on_tour_days", "payment_days", "ot_hours"]
    pay_fields  = ["daily_rate", "base_pay", "ot_pay", "gross_pay"]
    ssa_fields  = [c["fieldname"] for c in cols if c["fieldname"].startswith("ssa_ded_")]
    rt_fields   = [c["fieldname"] for c in cols if c["fieldname"].startswith("rt_ded_")]
    net_fields  = ["total_ssa_ded", "total_rt_ded", "net_ssa", "net_actual"]

    def _get_col(fn):
        for c in cols:
            if c["fieldname"] == fn:
                return c
        return None

    nd  = len(day_cols)
    ns  = len(summ_fields)
    np_ = len(pay_fields)
    nsa = len(ssa_fields)
    nr  = len(rt_fields)
    nn  = len(net_fields)

    total_pct = 100.0
    id_pct    = 12.0
    each_day  = max(1.2, (total_pct - id_pct - ns * 2.5 - np_ * 3.5 - nsa * 3.5 - nr * 3.5 - nn * 4.0) / nd) if nd else 2.0
    summ_pct  = 2.5
    pay_pct   = 3.5
    ded_pct   = 3.5
    net_pct   = 4.0

    cg  = "<colgroup>"
    cg += '<col style="width:{0}%;"/>'.format(2.0)
    cg += '<col style="width:{0}%;"/>'.format(id_pct)
    for _ in day_cols:
        cg += '<col style="width:{0:.3f}%;"/>'.format(each_day)
    for _ in summ_fields:
        cg += '<col style="width:{0}%;"/>'.format(summ_pct)
    for _ in pay_fields:
        cg += '<col style="width:{0}%;"/>'.format(pay_pct)
    for _ in ssa_fields:
        cg += '<col style="width:{0}%;"/>'.format(ded_pct)
    for _ in rt_fields:
        cg += '<col style="width:{0}%;"/>'.format(ded_pct)
    for _ in net_fields:
        cg += '<col style="width:{0}%;"/>'.format(net_pct)
    cg += "</colgroup>"

    TH = "border:1px solid #aaa;padding:2px 1px;font-size:7px;font-weight:700;text-align:center;vertical-align:middle;word-break:break-word;line-height:1.2;"

    def _grp_th(label, span, cls):
        return '<th colspan="{s}" class="grp-{c}">{l}</th>'.format(s=span, c=cls, l=label)

    grp_row  = "<tr class='grp-row'>"
    grp_row += '<th colspan="2" class="grp-identity" style="background:#1a1a2e;color:#fff;border:1px solid #888;padding:3px;">Employee</th>'
    grp_row += _grp_th("Attendance ({0} days)".format(nd), nd, "days")
    grp_row += _grp_th("Summary", ns, "summary")
    grp_row += _grp_th("Pay Calculation", np_, "pay")
    if ssa_fields:
        grp_row += _grp_th("SSA Fixed Deductions", nsa, "ssa")
        grp_row += _grp_th("Actual Runtime Deductions", nr, "actual")
    grp_row += _grp_th("Net Payable", nn, "net")
    grp_row += "</tr>"

    sub_row  = "<tr class='sub-row'>"
    sub_row += '<th style="{th}">Sr</th>'.format(th=TH)
    sub_row += '<th style="{th}text-align:left;">Employee Name / ID</th>'.format(th=TH)
    for c in day_cols:
        sub_row += '<th style="{th}">{l}</th>'.format(th=TH, l=c["label"])
    for fn in summ_fields:
        c_ = _get_col(fn)
        sub_row += '<th style="{th}">{l}</th>'.format(th=TH, l=c_["label"] if c_ else fn)
    for fn in pay_fields:
        c_ = _get_col(fn)
        sub_row += '<th style="{th}">{l}</th>'.format(th=TH, l=c_["label"] if c_ else fn)
    for fn in ssa_fields:
        c_ = _get_col(fn)
        lbl = (c_["label"] if c_ else fn).replace("SSA: ", "")
        sub_row += '<th style="{th}">{l}</th>'.format(th=TH, l=lbl)
    for fn in rt_fields:
        c_ = _get_col(fn)
        lbl = (c_["label"] if c_ else fn).replace("Actual: ", "")
        sub_row += '<th style="{th}">{l}</th>'.format(th=TH, l=lbl)
    for fn in net_fields:
        c_ = _get_col(fn)
        sub_row += '<th style="{th}">{l}</th>'.format(th=TH, l=c_["label"] if c_ else fn)
    sub_row += "</tr>"

    thead = "<thead>{g}{s}</thead>".format(g=grp_row, s=sub_row)

    def _render_row(row, i, is_total=False):
        bg  = "#f8f9ff" if i % 2 else "#ffffff"
        sbg = "#eef2ff"
        pbg = "#f0fff4"
        nbg = "#f0fdfa"

        tr = "<tr{cls}>".format(cls=' class="total-row"' if is_total else "")

        tr += '<td style="background:{bg};text-align:center;border:1px solid #ccc;font-size:7.5px;padding:2px;">{v}</td>'.format(
            bg=bg, v=row.get("sr_no", "") if not is_total else "")

        if is_total:
            tr += '<td style="background:#1a1a2e;color:#fff;font-weight:700;font-size:8px;padding:3px;border:1px solid #888;" colspan="1">TOTAL</td>'
        else:
            name = row.get("employee_name", "")
            eid  = row.get("employee", "")
            tr += (
                '<td style="background:{bg};padding:2px 3px;border:1px solid #ccc;">'
                '<div class="emp-name">{name}</div>'
                '<div class="emp-id">{eid}</div>'
                '</td>'
            ).format(bg=bg, name=name, eid=eid)

        for c in day_cols:
            v     = row.get(c["fieldname"], "") if not is_total else ""
            color = DAY_COLOR.get(v, "#111")
            if v and v not in ("", "-"):
                cell = '<b style="color:{c};font-size:7.5px;">{v}</b>'.format(c=color, v=v)
            else:
                cell = '<span style="color:#ddd;font-size:7px;">&#8211;</span>'
            tr += '<td style="background:{bg};text-align:center;border:1px solid #ddd;padding:1px 0;">{cell}</td>'.format(
                bg=bg, cell=cell)

        for fn in summ_fields:
            v = row.get(fn, "")
            if fn == "ot_hours":
                disp = str(v) if v else ""
            else:
                disp = _fmt_days(v)
            tr += '<td style="background:{bg};text-align:center;border:1px solid #ccc;font-size:7.5px;padding:1px 2px;">{v}</td>'.format(
                bg=sbg if not is_total else "inherit", v=disp)

        for fn in pay_fields:
            v      = row.get(fn, 0)
            disp   = _fmt(v) if v else ""
            if fn == "gross_pay":
                cell_style = "font-weight:700;color:#198754;"
            elif fn == "ot_pay":
                cell_style = "color:#b45309;"
            elif fn == "base_pay":
                cell_style = "color:#0d6efd;"
            elif fn == "daily_rate":
                cell_style = "color:#0ea5e9;font-weight:600;"
            else:
                cell_style = ""
            tr += '<td style="background:{bg};text-align:right;border:1px solid #ccc;font-size:7.5px;padding:1px 3px;{style}">{v}</td>'.format(
                bg=pbg if not is_total else "inherit", style=cell_style, v=disp)

        for fn in ssa_fields:
            v    = row.get(fn, 0)
            disp = _fmt(v) if v else ""
            tr += '<td style="background:#fffbeb;text-align:right;border:1px solid #ccc;font-size:7.5px;padding:1px 3px;color:#92400e;">{v}</td>'.format(v=disp)

        for fn in rt_fields:
            v    = row.get(fn, 0)
            disp = _fmt(v) if v else ""
            tr += '<td style="background:#fff5f5;text-align:right;border:1px solid #ccc;font-size:7.5px;padding:1px 3px;color:#c0392b;font-weight:600;">{v}</td>'.format(v=disp)

        for fn in net_fields:
            v    = row.get(fn, 0)
            disp = _fmt(v) if v else ""
            if fn == "net_actual":
                cell_style = "font-weight:800;color:#0d6efd;font-size:8px;"
                cell_bg    = "#dbeafe"
            elif fn == "net_ssa":
                cell_style = "font-weight:600;color:#b45309;"
                cell_bg    = nbg
            elif fn == "total_rt_ded":
                cell_style = "font-weight:700;color:#c0392b;"
                cell_bg    = "#fff5f5"
            elif fn == "total_ssa_ded":
                cell_style = "color:#92400e;"
                cell_bg    = "#fffbeb"
            else:
                cell_style = ""
                cell_bg    = nbg
            tr += '<td style="background:{bg};text-align:right;border:1px solid #ccc;font-size:7.5px;padding:1px 3px;{style}">{v}</td>'.format(
                bg=cell_bg if not is_total else "inherit", style=cell_style, v=disp)

        tr += "</tr>"
        return tr

    def _page_table(page_rows, start_i):
        tbody = "<tbody>"
        for j, row in enumerate(page_rows):
            is_tot = bool(row.get("_total"))
            tbody += _render_row(row, 0 if is_tot else (start_i + j), is_total=is_tot)
        tbody += "</tbody>"
        return '<table class="data-tbl">{cg}{thead}{tbody}</table>'.format(
            cg=cg, thead=thead, tbody=tbody)

    total_row = None
    if data:
        def _sum(fn):
            return sum(flt(r.get(fn, 0)) for r in data)

        tr = {
            "_total":        True,
            "sr_no":         "",
            "employee":      "",
            "employee_name": "TOTAL",
            "total_days":    "",
            "present_days":  _sum("present_days"),
            "absent_days":   _sum("absent_days"),
            "half_days":     _sum("half_days"),
            "holiday_days":  _sum("holiday_days"),
            "on_tour_days":  _sum("on_tour_days"),
            "payment_days":  _sum("payment_days"),
            "ot_hours":      "",
            "daily_rate":    "",
            "base_pay":      _sum("base_pay"),
            "ot_pay":        _sum("ot_pay"),
            "gross_pay":     _sum("gross_pay"),
            "total_ssa_ded": _sum("total_ssa_ded"),
            "total_rt_ded":  _sum("total_rt_ded"),
            "net_ssa":       _sum("net_ssa"),
            "net_actual":    _sum("net_actual"),
        }
        for c in day_cols:
            tr[c["fieldname"]] = ""
        for fn in ssa_fields:
            tr[fn] = _sum(fn)
        for fn in rt_fields:
            tr[fn] = _sum(fn)
        total_row = tr

    page1_hdr = (
        '<div class="hdr">'
        '<div class="co">{co}</div>'
        '<div class="ttl">Daily Wage Calculation Report</div>'
        '<div class="per">For the Month of {mo} {yr}</div>'
        '</div>'
    ).format(co=co, mo=mo, yr=yr)

    cont_hdr = (
        '<div class="cont-hdr">'
        '{co} &mdash; Daily Wage Calculation Report &mdash; {mo} {yr} (contd.)'
        '</div>'
    ).format(co=co, mo=mo, yr=yr)

    lgd = _legend_html()

    if not data:
        pages = [[]]
    else:
        pages, idx, first = [], 0, True
        while idx < len(data):
            lim = ROWS_FIRST_PAGE if first else ROWS_OTHER_PAGE
            pages.append(data[idx: idx + lim])
            idx  += lim
            first = False
        if total_row:
            pages[-1].append(total_row)

    total_pages = len(pages)
    parts       = []
    row_counter = 0

    for pn, page_rows in enumerate(pages):
        pb       = '<div style="page-break-before:always;"></div>' if pn > 0 else ""
        is_last  = (pn == total_pages - 1)
        hdr_html = (page1_hdr if pn == 0 else cont_hdr) + lgd

        if not data:
            nc  = 2 + nd + ns + np_ + nsa + nr + nn
            tbl = (
                '<table class="data-tbl">{cg}{thead}'
                '<tbody><tr><td colspan="{nc}" class="nd">'
                'No attendance data found for this period</td></tr></tbody></table>'
            ).format(cg=cg, thead=thead, nc=nc)
        else:
            tbl = _page_table(page_rows, row_counter)
            row_counter += sum(1 for r in page_rows if not r.get("_total"))

        pg_foot = '<div class="pg-foot">Page {p} of {t}</div>'.format(p=pn + 1, t=total_pages)
        sig     = _sig_html() if is_last else ""

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
    co   = _company_label(filters)
    mo   = filters.get("month", "")
    yr   = filters.get("year", "")
    html = _build_html(cols, data, co, mo, yr)
    return _save_pdf(html, "Daily_Wage_Calculation_Report")