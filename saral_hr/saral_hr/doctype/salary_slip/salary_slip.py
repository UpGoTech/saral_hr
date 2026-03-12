import frappe
from frappe.model.document import Document
from frappe.utils import getdate, get_last_day, flt
import calendar
from datetime import timedelta
import json
from PyPDF2 import PdfMerger
import os
from frappe.utils.pdf import get_pdf


class SalarySlip(Document):
    def validate(self):
        if self.start_date:
            self.end_date = get_last_day(getdate(self.start_date))


# ─── Duplicate Check ──────────────────────────────────────────────────────────

@frappe.whitelist()
def check_duplicate_salary_slip(employee, start_date, current_doc=""):
    filters = {
        "employee":   employee,
        "start_date": start_date,
        "docstatus":  ["in", [0, 1]]
    }
    existing = frappe.db.get_value("Salary Slip", filters, ["name", "docstatus"], as_dict=True)

    if not existing:
        return {"status": "ok"}
    if current_doc and existing.name == current_doc:
        return {"status": "ok"}

    status_label = "Draft" if existing.docstatus == 0 else "Submitted"
    return {
        "status":  "duplicate",
        "message": (
            f"A salary slip ({existing.name}) already exists for this employee "
            f"for the selected period and is currently in {status_label} status."
        )
    }


# ─── Additional Salary wage-basis helpers ─────────────────────────────────────
#
# _ADDITIONAL_SALARY_ALIASES are the component names you add to the Company's
# ESIC / PF wage component tables to signal "include all Additional Salary here".
# When "Additional Salary" (or "Arrears") appears in the wage-component list AND
# the employee has submitted Additional Salary records for that month, the full
# total of ALL additional salary components (OT, Incentive, any free-text name)
# is included in the statutory wage basis.

# The marker key written into earnings_map for additional salary totals.
# Add "Additional Salary" to the Company's ESIC/PF wage component tables
# to include OT / incentives / any Additional Salary amounts in the wage basis.
# "Arrears" stays in _ADDITIONAL_SALARY_ALIASES only as a TRIGGER alias
# (so the recompute fires if someone named their wage component "Arrears")
# but we NEVER write additional totals under "Arrears" in the earnings_map —
# that would cause a double-count when both names appear in the component list.
_ADDITIONAL_SALARY_KEY     = "Additional Salary"
_ADDITIONAL_SALARY_ALIASES = {"Additional Salary", "Arrears"}


def _get_additional_salary_total(employee, year_str, month_str):
    """Sum all component amounts across all submitted Additional Salary docs."""
    total = 0.0
    records = frappe.db.get_all(
        "Additional Salary",
        filters={
            "employee":  employee,
            "year":      year_str,
            "month":     month_str,
            "docstatus": 1,
        },
        fields=["name"],
    )
    for rec in records:
        doc = frappe.get_doc("Additional Salary", rec.name)
        for row in doc.components or []:
            total += flt(row.amount)
    return total


def _build_earnings_map_with_additional(ssa_doc, employee, year_str, month_str):
    """
    Build a {component_name: amount} map from SSA earnings, then add the
    total of ALL Additional Salary components under a SINGLE key
    (_ADDITIONAL_SALARY_KEY = "Additional Salary") so _sum_components()
    picks it up exactly once.

    We intentionally do NOT write under "Arrears" or any other alias —
    if both "Arrears" and "Additional Salary" appear in the ESIC/PF wage
    component list, writing the total under both keys would double-count it.
    """
    earnings_map = {}
    for row in ssa_doc.earnings or []:
        comp = (row.salary_component or "").strip()
        if comp:
            earnings_map[comp] = flt(row.amount)

    additional_total = _get_additional_salary_total(employee, year_str, month_str)
    if additional_total:
        earnings_map[_ADDITIONAL_SALARY_KEY] = (
            earnings_map.get(_ADDITIONAL_SALARY_KEY, 0.0) + additional_total
        )

    return earnings_map


# ─── Salary Structure Fetch ───────────────────────────────────────────────────
#
# Returns:
#   earnings       → slip earnings table
#   deductions     → employee-share rows only (employer_contribution = 0)
#   employer_share → employer-contribution rows only (employer_contribution = 1)

@frappe.whitelist()
def get_salary_structure_for_employee(employee, start_date=None,
                                      working_days=None, payment_days=None,
                                      physical_working_days=None,
                                      variable_pay_percentage=None):
    """
    Fetch SSA rows and compute statutory deductions.

    When attendance params (working_days, payment_days, physical_working_days)
    and variable_pay_percentage are supplied, statutory contributions are
    calculated on ACTUAL earned amounts (post-proration).  This is the correct
    behaviour for ESIC / PF — contributions must be on wages actually paid.

    When called without those params (e.g. from bulk generate before attendance
    is known) the function falls back to SSA base amounts, which is then
    corrected later by calculate_salary_slip_amounts_exact.
    """
    filters = {"employee": employee, "docstatus": 1}
    if start_date:
        filters["from_date"] = ["<=", start_date]

    ssa_list = frappe.db.get_all(
        "Salary Structure Assignment",
        filters=filters,
        fields=["name", "from_date", "to_date"],
        order_by="from_date desc"
    )

    ssa_name = None
    if start_date:
        end_date = get_last_day(getdate(start_date))
        for ssa in ssa_list:
            ssa_end = getdate(ssa.to_date) if ssa.to_date else None
            if not ssa_end or ssa_end >= end_date:
                ssa_name = ssa.name
                break

    if not ssa_name:
        return None

    ssa_doc = frappe.get_doc("Salary Structure Assignment", ssa_name)

    month_names = [
        "January","February","March","April","May","June",
        "July","August","September","October","November","December"
    ]
    current_month = None
    year_str      = None
    month_str     = None
    if start_date:
        d             = getdate(start_date)
        current_month = month_names[d.month - 1]
        year_str      = str(d.year)
        month_str     = current_month

    # ── Attendance / proration params ─────────────────────────
    wd           = flt(working_days)          if working_days          is not None else None
    pd           = flt(payment_days)          if payment_days          is not None else None
    phd          = flt(physical_working_days) if physical_working_days is not None else None
    vp_pct       = flt(variable_pay_percentage) / 100.0 if variable_pay_percentage is not None else None
    has_att_data = (wd is not None and pd is not None and phd is not None and vp_pct is not None)

    def _comp_meta(comp_name):
        return frappe.db.get_value(
            "Salary Component", comp_name,
            [
                "salary_component_abbr",
                "depends_on_payment_days",
                "depends_on_physical_working_days",
                "employer_contribution",
                "type",
            ],
            as_dict=True
        ) or {}

    def _prorate(base, dep_pd, dep_phd):
        """Return actual earned amount for a component given attendance data."""
        if not has_att_data or wd == 0:
            return base
        comp_name_lower = ""  # not needed here — caller handles variable pay
        if dep_phd:
            return (base / wd) * phd
        if dep_pd:
            return (base / wd) * pd
        return base

    earnings       = []
    deductions     = []
    employer_share = []

    # ── Earnings — store both base (SSA) and actual earned amount ─────────────
    # actual_earnings_map is used for statutory wage basis calculation
    actual_earnings_map = {}

    for row in (ssa_doc.earnings or []):
        meta      = _comp_meta(row.salary_component)
        base      = flt(row.amount, 2)
        dep_pd    = int(meta.get("depends_on_payment_days") or 0)
        dep_phd   = int(meta.get("depends_on_physical_working_days") or 0)
        comp_lower = (row.salary_component or "").lower()

        # Calculate actual earned amount for earnings map
        if has_att_data and "variable" in comp_lower:
            # Variable pay: base * variable_pct (already at 100% scale in SSA)
            # prorated by payment_days if depends_on_payment_days
            if dep_pd and wd > 0:
                actual = (base / wd) * pd * vp_pct
            else:
                actual = base * vp_pct
        else:
            actual = _prorate(base, dep_pd, dep_phd)

        actual_earnings_map[row.salary_component] = flt(actual, 2)

        earnings.append({
            "salary_component":                 row.salary_component,
            "abbr":                             meta.get("salary_component_abbr") or row.abbr or "",
            "amount":                           base,   # frontend will re-prorate from base_amount
            "base_amount":                      base,
            "depends_on_payment_days":          dep_pd,
            "depends_on_physical_working_days": dep_phd,
        })

    # ── Always recompute statutory when we have enough data ───────────────────
    #
    # Statutory must always reflect ACTUAL wages paid.  We recompute whenever:
    #   a) Attendance data was passed in (most accurate — uses prorated amounts), OR
    #   b) Employee has Additional Salary this month that affects ESIC/PF basis.
    #
    # When neither condition is met (e.g. no attendance data yet) we fall back
    # to SSA stored amounts.

    additional_total_for_check = 0.0
    if employee and year_str and month_str:
        additional_total_for_check = _get_additional_salary_total(employee, year_str, month_str)

    statutory_needs_recompute = False

    if has_att_data:
        # Always recompute when attendance data is available — guarantees
        # statutory is on actual earned wages, not SSA base amounts
        statutory_needs_recompute = True
    elif additional_total_for_check > 0 and ssa_doc.company:
        comp_doc   = frappe.get_doc("Company", ssa_doc.company)
        esic_comps = set(comp_doc._get_child_components("esic_dependent_component"))
        pf_comps   = set(comp_doc._get_child_components("pf_dependent_component"))
        if (esic_comps & _ADDITIONAL_SALARY_ALIASES) or (pf_comps & _ADDITIONAL_SALARY_ALIASES):
            statutory_needs_recompute = True

    # ── Employee-share deductions ─────────────────────────────
    for row in (ssa_doc.deductions or []):
        if statutory_needs_recompute and _is_statutory_component(row.salary_component):
            continue  # will be regenerated below

        meta   = _comp_meta(row.salary_component)
        amount = flt(row.amount, 2)

        if _is_pt_component(row.salary_component):
            amount = 300.0 if current_month == "February" else 200.0

        deductions.append({
            "salary_component":                 row.salary_component,
            "abbr":                             meta.get("salary_component_abbr") or row.abbr or "",
            "amount":                           amount,
            "base_amount":                      amount,
            "employer_contribution":            0,
            "depends_on_payment_days":          int(meta.get("depends_on_payment_days") or 0),
            "depends_on_physical_working_days": int(meta.get("depends_on_physical_working_days") or 0),
        })

    # ── Employer-share rows ───────────────────────────────────
    for row in (ssa_doc.employer_share or []):
        if statutory_needs_recompute and _is_statutory_component(row.salary_component):
            continue  # will be regenerated below

        meta = _comp_meta(row.salary_component)
        employer_share.append({
            "salary_component":                 row.salary_component,
            "abbr":                             meta.get("salary_component_abbr") or row.abbr or "",
            "amount":                           flt(row.amount, 2),
            "base_amount":                      flt(row.amount, 2),
            "employer_contribution":            1,
            "depends_on_payment_days":          0,
            "depends_on_physical_working_days": 0,
        })

    # ── Recompute statutory on actual earned wages ────────────────────────────
    if statutory_needs_recompute:
        # Build earnings map: actual prorated SSA amounts + additional salary total
        earnings_map = dict(actual_earnings_map)  # already prorated above
        if additional_total_for_check > 0:
            earnings_map[_ADDITIONAL_SALARY_KEY] = (
                earnings_map.get(_ADDITIONAL_SALARY_KEY, 0.0) + additional_total_for_check
            )

        gross_salary = sum(earnings_map.values())

        recomputed = get_statutory_components_internal(
            company=ssa_doc.company,
            gross_salary=gross_salary,
            earnings_map=earnings_map,
            from_date=start_date or "",
            is_esic_applicable=int(ssa_doc.is_esic_applicable or 0),
            is_pf_applicable=int(ssa_doc.is_pf_applicable or 0),
            pf_type=ssa_doc.pf_applicable or "",
            is_pt_applicable=int(ssa_doc.is_pt_applicable or 0),
            is_lwf_applicable=int(ssa_doc.is_lwf_applicable or 0),
        )

        for d in (recomputed.get("deductions") or []):
            amount = flt(d["amount"], 2)
            if _is_pt_component(d["salary_component"]):
                amount = 300.0 if current_month == "February" else 200.0
            deductions.append({
                "salary_component":                 d["salary_component"],
                "abbr":                             d.get("abbr") or "",
                "amount":                           amount,
                "base_amount":                      amount,
                "employer_contribution":            0,
                "depends_on_payment_days":          0,
                "depends_on_physical_working_days": 0,
            })

        for d in (recomputed.get("employer_share") or []):
            employer_share.append({
                "salary_component":                 d["salary_component"],
                "abbr":                             d.get("abbr") or "",
                "amount":                           flt(d["amount"], 2),
                "base_amount":                      flt(d["amount"], 2),
                "employer_contribution":            1,
                "depends_on_payment_days":          0,
                "depends_on_physical_working_days": 0,
            })

    return {
        "salary_structure": ssa_doc.salary_structure,
        "currency":         "INR",
        "earnings":         earnings,
        "deductions":       deductions,
        "employer_share":   employer_share,
        "ssa_gross":        sum(flt(r.amount) for r in (ssa_doc.earnings or [])),
    }


# ─── Statutory component helpers ─────────────────────────────────────────────

STATUTORY_COMPONENTS = {
    "Employee ESIC", "Employer ESIC",
    "Employee PF", "Employer PF",
    "Employer EPS", "Employer EDLI", "Employer PF Admin Charges",
    "Professional Tax",
    "Employee Labour Welfare Fund", "Employer Labour Welfare Fund",
}

PT_COMPONENT_NAME = "Professional Tax"


def _is_statutory_component(comp_name):
    return (comp_name or "").strip() in STATUTORY_COMPONENTS


def _is_pt_component(comp_name):
    return (comp_name or "").strip() == PT_COMPONENT_NAME


# ─── Statutory computation (internal, non-whitelisted) ───────────────────────

MONTHS_LIST = [
    "January", "February", "March", "April",
    "May", "June", "July", "August",
    "September", "October", "November", "December"
]

SC_EMP_ESIC   = "Employee ESIC"
SC_EMPR_ESIC  = "Employer ESIC"
SC_EMP_PF     = "Employee PF"
SC_EMPR_PF    = "Employer PF"
SC_EMPR_EPS   = "Employer EPS"
SC_EMPR_EDLI  = "Employer EDLI"
SC_EMPR_PFADM = "Employer PF Admin Charges"
SC_PT         = "Professional Tax"
SC_EMP_LWF    = "Employee Labour Welfare Fund"
SC_EMPR_LWF   = "Employer Labour Welfare Fund"


def get_statutory_components_internal(company, gross_salary, earnings_map,
                                      from_date, is_esic_applicable,
                                      is_pf_applicable, pf_type,
                                      is_pt_applicable, is_lwf_applicable):
    VIRTUAL = {"Gross", "Gross Including Additional Salary"}

    def _sum_components(components, gross, emap):
        total = 0.0
        for comp in components:
            if comp in VIRTUAL:
                total += flt(gross)
            elif comp in emap:
                total += flt(emap[comp])
        return max(total, 0.0)

    def abbr(name):
        return frappe.db.get_value("Salary Component", name, "salary_component_abbr") or ""

    def row(name, amount, employer=0):
        return {
            "salary_component":      name,
            "abbr":                  abbr(name),
            "amount":                flt(amount, 2),
            "employer_contribution": employer,
        }

    deductions     = []
    employer_share = []

    comp_doc = frappe.get_doc("Company", company) if company else None

    # ── ESIC ──────────────────────────────────────────────────
    if is_esic_applicable and comp_doc:
        esic_cfg = comp_doc.get_esic_config()
        if esic_cfg:
            esic_components = comp_doc._get_child_components("esic_dependent_component")
            wage = _sum_components(esic_components, gross_salary, earnings_map)

            emp_pct  = flt(esic_cfg.get("employee_percent", 0))
            empr_pct = flt(esic_cfg.get("employer_percent", 0))

            if emp_pct:
                deductions.append(row(SC_EMP_ESIC, wage * emp_pct / 100))
            if empr_pct:
                employer_share.append(row(SC_EMPR_ESIC, wage * empr_pct / 100, employer=1))

    # ── PF ────────────────────────────────────────────────────
    if is_pf_applicable and comp_doc:
        pf_cfg = comp_doc.get_pf_config()
        if pf_cfg:
            pf_components = comp_doc._get_child_components("pf_dependent_component")
            raw_wage = _sum_components(pf_components, gross_salary, earnings_map)

            if pf_type == "Limited PF" and pf_cfg.get("wage_limit"):
                wage = min(raw_wage, flt(pf_cfg["wage_limit"]))
            else:
                wage = raw_wage

            emp_pct  = flt(pf_cfg.get("employee_percent", 0))
            epf_pct  = flt(pf_cfg.get("employer_epf",    0))
            eps_pct  = flt(pf_cfg.get("employer_eps",    0))
            edli_pct = flt(pf_cfg.get("edli_insurance",  0))
            adm_pct  = flt(pf_cfg.get("admin_charges",   0))

            if emp_pct:
                deductions.append(row(SC_EMP_PF,     wage * emp_pct  / 100))
            if epf_pct:
                employer_share.append(row(SC_EMPR_PF,    wage * epf_pct  / 100, employer=1))
            if eps_pct:
                employer_share.append(row(SC_EMPR_EPS,   wage * eps_pct  / 100, employer=1))
            if edli_pct:
                employer_share.append(row(SC_EMPR_EDLI,  wage * edli_pct / 100, employer=1))
            if adm_pct:
                employer_share.append(row(SC_EMPR_PFADM, wage * adm_pct  / 100, employer=1))

    # ── PT ────────────────────────────────────────────────────
    if is_pt_applicable and from_date:
        month_name = MONTHS_LIST[getdate(from_date).month - 1]
        pt_amt     = _special_component_amount_local(SC_PT, month_name)
        deductions.append(row(SC_PT, pt_amt))

    # ── LWF ───────────────────────────────────────────────────
    if is_lwf_applicable:
        emp_lwf_amt  = _special_component_constant_amount_local(SC_EMP_LWF)
        empr_lwf_amt = _special_component_constant_amount_local(SC_EMPR_LWF)
        deductions.append(row(SC_EMP_LWF,  emp_lwf_amt))
        employer_share.append(row(SC_EMPR_LWF, empr_lwf_amt, employer=1))

    return {"deductions": deductions, "employer_share": employer_share}


def _special_component_amount_local(component_name, month_name):
    try:
        doc = frappe.get_doc("Salary Component", component_name)
        if not int(doc.is_special_component or 0):
            return 0.0
        for r in (doc.monthly_amounts or []):
            if r.month == month_name:
                return flt(r.amount)
    except frappe.DoesNotExistError:
        pass
    return 0.0


def _special_component_constant_amount_local(component_name):
    try:
        doc = frappe.get_doc("Salary Component", component_name)
        if not int(doc.is_special_component or 0):
            return 0.0
        non_zero = [flt(r.amount) for r in (doc.monthly_amounts or []) if flt(r.amount) > 0]
        if not non_zero:
            return 0.0
        from collections import Counter
        return Counter(non_zero).most_common(1)[0][0]
    except frappe.DoesNotExistError:
        pass
    return 0.0


# ─── Additional Components ────────────────────────────────────────────────────

def get_additional_components_for_employee(employee, year, month):
    additional_earnings   = []
    additional_deductions = []

    for rec in frappe.db.get_all("Additional Salary",
            filters={"employee": employee, "year": year, "month": month, "docstatus": 1},
            fields=["name"]):
        doc = frappe.get_doc("Additional Salary", rec.name)
        for row in doc.components:
            additional_earnings.append({
                "salary_component":                 row.component_type,
                "abbr":                             "",
                "amount":                           flt(row.amount),
                "base_amount":                      flt(row.amount),
                "depends_on_payment_days":          0,
                "depends_on_physical_working_days": 0,
            })

    for rec in frappe.db.get_all("Additional Deductions",
            filters={"employee": employee, "year": year, "month": month, "docstatus": 1},
            fields=["name"]):
        doc = frappe.get_doc("Additional Deductions", rec.name)
        for row in doc.deductions:
            additional_deductions.append({
                "salary_component":                 row.component_type,
                "abbr":                             "",
                "amount":                           flt(row.amount),
                "base_amount":                      flt(row.amount),
                "employer_contribution":            0,
                "depends_on_payment_days":          0,
                "depends_on_physical_working_days": 0,
            })

    return additional_earnings, additional_deductions


@frappe.whitelist()
def get_additional_components_api(employee, start_date):
    if not employee or not start_date:
        return {"earnings": [], "deductions": []}
    start_date_obj = getdate(start_date)
    year_str  = str(start_date_obj.year)
    month_names = ["January","February","March","April","May","June",
                   "July","August","September","October","November","December"]
    month_str = month_names[start_date_obj.month - 1]
    earnings, deductions = get_additional_components_for_employee(employee, year_str, month_str)
    return {"earnings": earnings, "deductions": deductions}


# ─── Variable Pay ─────────────────────────────────────────────────────────────

def _employee_requires_variable_pay(employee):
    return bool(frappe.db.get_value("Company Link", employee, "requires_variable_pay"))


@frappe.whitelist()
def get_variable_pay_percentage(employee, start_date):
    if not employee or not start_date:
        return None
    if not _employee_requires_variable_pay(employee):
        return None
    division = frappe.db.get_value("Company Link", employee, "division")
    if not division:
        return None
    date_obj = getdate(start_date)
    year     = str(date_obj.year)
    month_names = ["January","February","March","April","May","June",
                   "July","August","September","October","November","December"]
    month    = month_names[date_obj.month - 1]
    vpa_name = f"{year} - {month}"
    if not frappe.db.exists("Variable Pay Assignment", vpa_name):
        return None
    vpa_doc = frappe.get_doc("Variable Pay Assignment", vpa_name)
    for row in vpa_doc.variable_pay:
        if row.division == division:
            return flt(row.percentage)
    return None


@frappe.whitelist()
def check_variable_pay_assignment(employee, start_date):
    if not employee or not start_date:
        return {"status": "ok"}
    if not _employee_requires_variable_pay(employee):
        return {"status": "ok"}
    division = frappe.db.get_value("Company Link", employee, "division")
    if not division:
        return {"status": "ok"}
    date_obj = getdate(start_date)
    year     = str(date_obj.year)
    month_names = ["January","February","March","April","May","June",
                   "July","August","September","October","November","December"]
    month    = month_names[date_obj.month - 1]
    vpa_name = f"{year} - {month}"
    if not frappe.db.exists("Variable Pay Assignment", vpa_name):
        return {
            "status":  "missing",
            "message": (
                f"No Variable Pay Assignment has been created for {month} {year}. "
                f"Please set up a Variable Pay Assignment for this payroll period "
                f"before processing salary slips."
            )
        }
    vpa_doc        = frappe.get_doc("Variable Pay Assignment", vpa_name)
    division_found = any(row.division == division for row in vpa_doc.variable_pay)
    if not division_found:
        return {
            "status":  "missing",
            "message": (
                f"The division '{division}' has not been configured in the Variable Pay "
                f"Assignment for {month} {year}. Please update the Variable Pay Assignment "
                f"to include this division before processing salary slips."
            )
        }
    return {"status": "ok"}


# ─── Attendance ───────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_attendance_and_days(employee, start_date, working_days_calculation_method=None):
    start_date = getdate(start_date)
    end_date   = get_last_day(start_date)

    if not working_days_calculation_method:
        company = frappe.db.get_value("Company Link", employee, "company")
        if company:
            working_days_calculation_method = frappe.db.get_value(
                "Company", company, "salary_calculation_based_on"
            ) or ""

    calculation_method = (
        "Include Weekly Offs"
        if "Include" in (working_days_calculation_method or "")
        else "Exclude Weekly Offs"
    )

    weekly_off   = frappe.db.get_value("Company Link", employee, "weekly_off")
    total_days   = calendar.monthrange(start_date.year, start_date.month)[1]
    day_map      = {"Monday":0,"Tuesday":1,"Wednesday":2,"Thursday":3,
                    "Friday":4,"Saturday":5,"Sunday":6}
    weekly_off_count = 0
    if weekly_off:
        off_day = day_map.get(weekly_off)
        if off_day is not None:
            current = start_date
            while current <= end_date:
                if current.weekday() == off_day:
                    weekly_off_count += 1
                current += timedelta(days=1)

    attendance = frappe.db.get_all("Attendance",
        filters={"employee": employee, "attendance_date": ["between", [start_date, end_date]]},
        fields=["status"])

    present_days = absent_days = half_day_count = 0
    lwp_days = holiday_days = earned_leave_days = casual_leave_days = 0
    on_tour_days = comp_off_days = 0

    for a in attendance:
        if a.status == "Present":
            present_days += 1
        elif a.status == "Earned Leave":
            earned_leave_days += 1
            present_days      += 1
        elif a.status == "Casual Leave":
            casual_leave_days += 1
            present_days      += 1
        elif a.status == "Half Day":
            half_day_count += 1
            present_days   += 0.5
            absent_days    += 0.5
        elif a.status == "Absent":
            absent_days += 1
        elif a.status == "LWP":
            lwp_days += 1
        elif a.status == "Holiday":
            holiday_days += 1
        elif a.status == "On Tour":
            on_tour_days += 1
            present_days += 1
        elif a.status == "Comp Off":
            comp_off_days += 1
            present_days  += 1

    combined_absent_days = flt(absent_days + lwp_days, 2)

    if calculation_method == "Include Weekly Offs":
        working_days = total_days
        payment_days = flt(total_days - combined_absent_days, 2)
    else:
        working_days = total_days - weekly_off_count
        payment_days = flt(working_days - combined_absent_days, 2)

    physical_working_days = flt(
        payment_days - earned_leave_days - casual_leave_days - comp_off_days, 2
    )

    return {
        "attendance_count":      len(attendance),
        "total_days":            total_days,
        "weekly_offs":           weekly_off_count,
        "working_days":          working_days,
        "payment_days":          payment_days,
        "physical_working_days": physical_working_days,
        "present_days":          present_days,
        "absent_days":           combined_absent_days,
        "total_half_days":       flt(half_day_count * 0.5, 2),
        "total_lwp":             flt(lwp_days, 2),
        "total_holidays":        flt(holiday_days, 2),
        "total_earned_leaves":   flt(earned_leave_days, 2),
        "total_casual_leaves":   flt(casual_leave_days, 2),
        "total_on_tour":         flt(on_tour_days, 2),
        "total_comp_off":        flt(comp_off_days, 2),
        "calculation_method":    calculation_method,
    }


# ─── Core Salary Calculation ──────────────────────────────────────────────────
#
# earnings        → prorated by payment_days / physical_working_days / variable pay
# deductions      → employee-share only; statutory fixed; PT overridden by month
# employer_share  → fixed, never prorated; summed into total_employer_contribution

def calculate_salary_slip_amounts_exact(salary_slip, variable_pay_percentage,
                                        start_date, category=None,
                                        ssa_gross=None):
    wd           = flt(salary_slip.total_working_days)
    pd           = flt(salary_slip.payment_days)
    phd          = flt(salary_slip.physical_working_days)
    variable_pct = flt(variable_pay_percentage)

    total_earnings              = 0.0
    total_deductions            = 0.0
    total_employer_contribution = 0.0
    total_basic_da              = 0.0
    retention                   = 0.0
    basic_amount                = 0.0
    da_amount                   = 0.0

    start_month = getdate(start_date).month if start_date else None

    # ── Pass 1: earnings ──────────────────────────────────────
    for row in salary_slip.earnings:
        base = flt(row.base_amount if row.base_amount is not None else row.amount)
        row.base_amount = base
        comp = (row.salary_component or "").lower()

        if "variable" in comp:
            if pd == 0:
                amount = 0.0
            elif wd > 0 and row.depends_on_payment_days:
                amount = (base / wd) * pd * variable_pct
            else:
                amount = base * variable_pct

        elif row.depends_on_physical_working_days and wd > 0:
            amount = (base / wd) * phd

        elif row.depends_on_payment_days and wd > 0:
            amount = (base / wd) * pd

        else:
            amount = base

        row.amount      = flt(amount, 2)
        total_earnings += row.amount

        if "basic" in comp:
            basic_amount = row.amount
        if _is_da_component(row.salary_component, getattr(row, "abbr", "")):
            da_amount = row.amount

    total_basic_da = basic_amount + da_amount

    # ── Pass 2: deductions (employee share only) ──────────────
    for row in salary_slip.deductions:
        base = flt(row.base_amount if row.base_amount is not None else row.amount)
        row.base_amount = base
        comp = (row.salary_component or "").lower()

        is_statutory = _is_statutory_component(row.salary_component)
        is_pt        = _is_pt_component(row.salary_component)

        if is_pt:
            amount = 300.0 if start_month == 2 else 200.0

        elif is_statutory:
            amount = base

        elif row.depends_on_physical_working_days and wd > 0 and base > 0:
            amount = (base / wd) * phd

        elif row.depends_on_payment_days and wd > 0 and base > 0:
            amount = (base / wd) * pd

        else:
            amount = base

        row.amount        = flt(amount, 2)
        total_deductions += row.amount

        if "retention" in comp:
            retention += row.amount

    # ── Pass 3: employer share (fixed, never prorated) ────────
    for row in (salary_slip.employer_share or []):
        base = flt(row.base_amount if row.base_amount is not None else row.amount)
        row.base_amount = base
        row.amount      = flt(base, 2)
        total_employer_contribution += row.amount

    salary_slip.total_earnings              = flt(total_earnings, 2)
    salary_slip.total_deductions            = flt(total_deductions, 2)
    salary_slip.net_salary                  = flt(total_earnings - total_deductions, 2)
    salary_slip.total_basic_da              = flt(total_basic_da, 2)
    salary_slip.total_employer_contribution = flt(total_employer_contribution, 2)
    salary_slip.retention                   = flt(retention, 2)


def _is_da_component(comp_name, abbr):
    name_lower = (comp_name or "").lower()
    abbr_lower = (abbr or "").lower()
    return (
        "dearness" in name_lower
        or name_lower == "da"
        or abbr_lower == "da"
        or abbr_lower.startswith("da-")
        or abbr_lower.startswith("da ")
        or abbr_lower == "da - dr"
        or abbr_lower.startswith("da-dr")
    )


# ─── Eligible Employees ───────────────────────────────────────────────────────

@frappe.whitelist()
def get_eligible_employees_for_salary_slip(company, year, month, category=None):
    month_map = {
        'January':1,'February':2,'March':3,'April':4,'May':5,'June':6,
        'July':7,'August':8,'September':9,'October':10,'November':11,'December':12
    }
    month_num = month_map.get(month)
    if not month_num:
        frappe.throw("Invalid month")

    start_date     = f"{year}-{month_num:02d}-01"
    start_date_obj = getdate(start_date)
    end_date       = get_last_day(start_date_obj)

    vpa_name      = f"{year} - {month}"
    vpa_exists    = frappe.db.exists("Variable Pay Assignment", vpa_name)
    vpa_divisions = set()
    if vpa_exists:
        vpa_doc       = frappe.get_doc("Variable Pay Assignment", vpa_name)
        vpa_divisions = {row.division for row in vpa_doc.variable_pay}

    category_filter = "AND cl.category = %(category)s" if category else ""
    all_active_employees = frappe.db.sql(f"""
        SELECT DISTINCT cl.name, cl.full_name AS employee_name,
            cl.department, cl.designation, cl.company,
            cl.division, cl.requires_variable_pay
        FROM `tabCompany Link` cl
        WHERE cl.is_active = 1
          AND cl.company = %(company)s
          {category_filter}
    """, {"company": company, "category": category}, as_dict=1)

    total_active = len(all_active_employees)

    employees_with_structure = frappe.db.sql("""
        SELECT DISTINCT cl.name
        FROM `tabCompany Link` cl
        INNER JOIN `tabSalary Structure Assignment` ssa ON ssa.employee = cl.name
        WHERE cl.is_active = 1
          AND cl.company    = %(company)s
          AND ssa.docstatus = 1
          AND ssa.from_date <= %(start_date)s
          AND (ssa.to_date IS NULL OR ssa.to_date >= %(end_date)s)
    """, {"company": company, "start_date": start_date, "end_date": str(end_date)}, as_dict=1)
    employees_with_structure_ids = {e.name for e in employees_with_structure}

    employee_names_list = [e.name for e in all_active_employees]
    attendance_counts   = {}
    if employee_names_list:
        placeholders = ", ".join(["%s"] * len(employee_names_list))
        rows = frappe.db.sql(
            f"""SELECT employee, COUNT(*) AS cnt FROM `tabAttendance`
                WHERE employee IN ({placeholders})
                  AND attendance_date BETWEEN %s AND %s
                GROUP BY employee""",
            tuple(employee_names_list) + (str(start_date_obj), str(end_date))
        )
        attendance_counts = {r[0]: r[1] for r in rows}

    eligible_employees   = []
    ineligible_employees = []

    for emp in all_active_employees:
        unmet_criteria = []
        if emp.name not in employees_with_structure_ids:
            unmet_criteria.append("No submitted Salary Structure Assignment found covering the full payroll period")
        if attendance_counts.get(emp.name, 0) == 0:
            unmet_criteria.append("No attendance has been recorded for this employee in the selected period")
        if emp.get("requires_variable_pay"):
            division = emp.get("division")
            if division:
                if not vpa_exists:
                    unmet_criteria.append(f"No Variable Pay Assignment has been created for {month} {year}")
                elif division not in vpa_divisions:
                    unmet_criteria.append(f"Division '{division}' is not configured in the Variable Pay Assignment for {month} {year}")

        if unmet_criteria:
            ineligible_employees.append({"id": emp.name, "name": emp.employee_name or emp.name, "reasons": unmet_criteria})
        else:
            eligible_employees.append(emp)

    category_requires_variable_pay = False
    if category:
        category_requires_variable_pay = bool(frappe.db.get_value("Category", category, "requires_variable_pay"))

    return {
        "eligible":                       eligible_employees,
        "skipped":                        ineligible_employees,
        "total_active":                   total_active,
        "total_eligible":                 len(eligible_employees),
        "category_requires_variable_pay": category_requires_variable_pay,
    }


# ─── Bulk Generate ────────────────────────────────────────────────────────────

@frappe.whitelist()
def bulk_generate_salary_slips(employees, year, month):
    if isinstance(employees, str):
        employees = json.loads(employees)

    month_map = {
        'January':1,'February':2,'March':3,'April':4,'May':5,'June':6,
        'July':7,'August':8,'September':9,'October':10,'November':11,'December':12
    }
    month_num = month_map.get(month)
    if not month_num:
        return {"success": 0, "failed": len(employees), "errors": ["Invalid month specified"]}

    start_date    = f"{year}-{month_num:02d}-01"
    success_count = 0
    failed_count  = 0
    errors        = []

    for emp_data in employees:
        employee = emp_data.get('employee')
        try:
            emp_display = emp_data.get('employee_name', employee)

            dup = check_duplicate_salary_slip(employee, start_date)
            if dup.get("status") == "duplicate":
                errors.append(f"{emp_display}: {dup.get('message')}")
                failed_count += 1
                continue

            if _employee_requires_variable_pay(employee):
                division = frappe.db.get_value("Company Link", employee, "division")
                if division:
                    vpa_name = f"{year} - {month}"
                    if not frappe.db.exists("Variable Pay Assignment", vpa_name):
                        errors.append(f"{emp_display}: No Variable Pay Assignment found for {month} {year}")
                        failed_count += 1
                        continue
                    vpa_doc = frappe.get_doc("Variable Pay Assignment", vpa_name)
                    if not any(row.division == division for row in vpa_doc.variable_pay):
                        errors.append(f"{emp_display}: Division '{division}' not configured in Variable Pay Assignment for {month} {year}")
                        failed_count += 1
                        continue

            # ── Fetch attendance first — needed for correct statutory basis ──
            category     = frappe.db.get_value("Company Link", employee, "category")
            company_name = frappe.db.get_value("Company Link", employee, "company")
            working_days_calculation_method = None
            if company_name:
                working_days_calculation_method = frappe.db.get_value(
                    "Company", company_name, "salary_calculation_based_on"
                ) or ""

            attendance_data = get_attendance_and_days(employee, start_date, working_days_calculation_method)
            if not attendance_data:
                errors.append(f"{emp_display}: Attendance data could not be retrieved for this period")
                failed_count += 1
                continue
            if attendance_data.get("attendance_count", 0) == 0:
                errors.append(f"{emp_display}: No attendance has been recorded for {month} {year}")
                failed_count += 1
                continue

            variable_pay_pct     = get_variable_pay_percentage(employee, start_date)
            variable_pay_decimal = flt(variable_pay_pct if variable_pay_pct is not None else 0) / 100.0

            # ── Now fetch salary structure with actual attendance data ─────────
            # Statutory (ESIC/PF) will be computed on actual prorated wages
            salary_data = get_salary_structure_for_employee(
                employee, start_date,
                working_days=attendance_data.get('working_days'),
                payment_days=attendance_data.get('payment_days'),
                physical_working_days=attendance_data.get('physical_working_days'),
                variable_pay_percentage=variable_pay_pct if variable_pay_pct is not None else 0,
            )
            if not salary_data:
                errors.append(f"{emp_display}: No active Salary Structure Assignment found for this payroll period")
                failed_count += 1
                continue

            add_earnings, add_deductions = get_additional_components_for_employee(employee, year, month)

            salary_slip = frappe.new_doc("Salary Slip")
            salary_slip.employee   = employee
            salary_slip.start_date = start_date
            salary_slip.end_date   = get_last_day(getdate(start_date))
            salary_slip.currency   = "INR"
            salary_slip.salary_structure                = salary_data.get('salary_structure')
            salary_slip.working_days_calculation_method = working_days_calculation_method or ""
            salary_slip.total_working_days    = attendance_data.get('working_days')
            salary_slip.payment_days          = attendance_data.get('payment_days')
            salary_slip.physical_working_days = attendance_data.get('physical_working_days')
            salary_slip.present_days          = attendance_data.get('present_days')
            salary_slip.absent_days           = attendance_data.get('absent_days')
            salary_slip.weekly_offs_count     = attendance_data.get('weekly_offs')
            salary_slip.total_half_days       = attendance_data.get('total_half_days')
            salary_slip.total_lwp             = attendance_data.get('total_lwp', 0)
            salary_slip.total_holidays        = attendance_data.get('total_holidays', 0)
            salary_slip.total_earned_leaves   = attendance_data.get('total_earned_leaves', 0)
            salary_slip.total_casual_leaves   = attendance_data.get('total_casual_leaves', 0)
            salary_slip.total_on_tour         = attendance_data.get('total_on_tour', 0)
            salary_slip.total_comp_off        = attendance_data.get('total_comp_off', 0)

            # ── Earnings ──────────────────────────────────────
            for earning in salary_data.get('earnings', []):
                row = salary_slip.append('earnings', {})
                row.salary_component                 = earning.get('salary_component')
                row.abbr                             = earning.get('abbr', '')
                row.amount                           = flt(earning.get('amount'))
                row.base_amount                      = flt(earning.get('base_amount', earning.get('amount')))
                row.depends_on_payment_days          = int(earning.get('depends_on_payment_days', 0))
                row.depends_on_physical_working_days = int(earning.get('depends_on_physical_working_days', 0))

            # ── Deductions (employee share only) ──────────────
            for deduction in salary_data.get('deductions', []):
                row = salary_slip.append('deductions', {})
                row.salary_component                 = deduction.get('salary_component')
                row.abbr                             = deduction.get('abbr', '')
                row.amount                           = flt(deduction.get('amount'))
                row.base_amount                      = flt(deduction.get('base_amount', deduction.get('amount')))
                row.employer_contribution            = 0
                row.depends_on_payment_days          = int(deduction.get('depends_on_payment_days', 0))
                row.depends_on_physical_working_days = int(deduction.get('depends_on_physical_working_days', 0))

            # ── Employer share ────────────────────────────────
            for emp_row in salary_data.get('employer_share', []):
                row = salary_slip.append('employer_share', {})
                row.salary_component                 = emp_row.get('salary_component')
                row.abbr                             = emp_row.get('abbr', '')
                row.amount                           = flt(emp_row.get('amount'))
                row.base_amount                      = flt(emp_row.get('base_amount', emp_row.get('amount')))
                row.employer_contribution            = 1
                row.depends_on_payment_days          = 0
                row.depends_on_physical_working_days = 0

            # ── Additional earnings ───────────────────────────
            for earning in add_earnings:
                row = salary_slip.append('earnings', {})
                row.salary_component                 = earning.get('salary_component')
                row.abbr                             = ""
                row.amount                           = flt(earning.get('amount'))
                row.base_amount                      = flt(earning.get('amount'))
                row.depends_on_payment_days          = 0
                row.depends_on_physical_working_days = 0

            # ── Additional deductions ─────────────────────────
            for deduction in add_deductions:
                row = salary_slip.append('deductions', {})
                row.salary_component                 = deduction.get('salary_component')
                row.abbr                             = ""
                row.amount                           = flt(deduction.get('amount'))
                row.base_amount                      = flt(deduction.get('amount'))
                row.employer_contribution            = 0
                row.depends_on_payment_days          = 0
                row.depends_on_physical_working_days = 0

            calculate_salary_slip_amounts_exact(
                salary_slip, variable_pay_decimal, start_date, category,
                ssa_gross=salary_data.get('ssa_gross', 0)
            )

            salary_slip.insert(ignore_permissions=True)
            success_count += 1
            frappe.db.commit()

        except Exception as e:
            errors.append(f"{emp_data.get('employee_name', employee)}: {str(e)}")
            failed_count += 1
            frappe.log_error(f"Error generating salary slip for {employee}: {str(e)}", "Bulk Salary Slip Generation")
            frappe.db.rollback()

    return {"success": success_count, "failed": failed_count, "errors": errors}


# ─── Submitted / Draft Queries ────────────────────────────────────────────────

@frappe.whitelist()
def get_submitted_salary_slips(company, year, month):
    month_map = {'January':1,'February':2,'March':3,'April':4,'May':5,'June':6,
                 'July':7,'August':8,'September':9,'October':10,'November':11,'December':12}
    month_num = month_map.get(month)
    if not month_num:
        frappe.throw("Invalid month")
    start_date = f"{year}-{month_num:02d}-01"
    return frappe.db.sql("""
        SELECT ss.name, ss.employee, ss.employee_name, ss.department,
               ss.designation, ss.net_salary, ss.start_date, ss.end_date
        FROM `tabSalary Slip` ss
        WHERE ss.docstatus=1 AND ss.start_date=%(start_date)s AND ss.company=%(company)s
        ORDER BY ss.employee_name
    """, {"company": company, "start_date": start_date}, as_dict=1)


@frappe.whitelist()
def get_draft_salary_slips(company, year, month):
    month_map = {'January':1,'February':2,'March':3,'April':4,'May':5,'June':6,
                 'July':7,'August':8,'September':9,'October':10,'November':11,'December':12}
    month_num = month_map.get(month)
    if not month_num:
        frappe.throw("Invalid month")
    start_date = f"{year}-{month_num:02d}-01"
    return frappe.db.sql("""
        SELECT ss.name, ss.employee, ss.employee_name, ss.department,
               ss.designation, ss.net_salary, ss.start_date, ss.end_date
        FROM `tabSalary Slip` ss
        WHERE ss.docstatus=0 AND ss.start_date=%(start_date)s AND ss.company=%(company)s
        ORDER BY ss.employee_name
    """, {"company": company, "start_date": start_date}, as_dict=1)


# ─── Bulk Submit ──────────────────────────────────────────────────────────────

@frappe.whitelist()
def bulk_submit_salary_slips(salary_slip_names):
    if isinstance(salary_slip_names, str):
        salary_slip_names = json.loads(salary_slip_names)
    if not salary_slip_names:
        frappe.throw("No salary slips were selected for submission")

    success_count = 0
    failed_count  = 0
    errors        = []

    for slip_name in salary_slip_names:
        try:
            slip_doc = frappe.get_doc("Salary Slip", slip_name)
            if slip_doc.docstatus != 0:
                errors.append(f"{slip_name}: Not in Draft status, cannot be submitted")
                failed_count += 1
                continue
            slip_doc.submit()
            success_count += 1
            frappe.db.commit()
        except Exception as e:
            errors.append(f"{slip_name}: {str(e)}")
            failed_count += 1
            frappe.log_error(f"Error submitting salary slip {slip_name}: {str(e)}", "Bulk Submit Salary Slips")
            frappe.db.rollback()

    return {"success": success_count, "failed": failed_count, "errors": errors}


# ─── Bulk Print ───────────────────────────────────────────────────────────────

@frappe.whitelist()
def bulk_print_salary_slips(salary_slip_names):
    if isinstance(salary_slip_names, str):
        salary_slip_names = json.loads(salary_slip_names)
    if not salary_slip_names:
        frappe.throw("No salary slips were selected for printing")

    merger     = PdfMerger()
    temp_files = []

    import hashlib
    session_tag = hashlib.md5(
        f"{frappe.session.user}_{frappe.utils.now_datetime()}".encode()
    ).hexdigest()[:8]

    try:
        for slip_name in salary_slip_names:
            slip_doc = frappe.get_doc("Salary Slip", slip_name)
            html     = generate_bulk_print_html(slip_doc)
            pdf_options = {
                "page-size":"A4","orientation":"Portrait",
                "margin-top":"10mm","margin-right":"10mm",
                "margin-bottom":"10mm","margin-left":"10mm",
                "encoding":"UTF-8","no-outline":None,"enable-local-file-access":None
            }
            pdf_data  = get_pdf(html, options=pdf_options)
            temp_file = frappe.utils.get_files_path(f"temp_slip_{session_tag}_{slip_name}.pdf", is_private=1)
            temp_files.append(temp_file)
            with open(temp_file, "wb") as f:
                f.write(pdf_data)
            merger.append(temp_file)

        timestamp      = frappe.utils.now_datetime().strftime("%Y%m%d_%H%M%S")
        final_filename = f"Salary_Slips_{timestamp}.pdf"
        final_filepath = frappe.utils.get_files_path(final_filename, is_private=1)
        with open(final_filepath, "wb") as f:
            merger.write(f)
        merger.close()

        file_doc = frappe.get_doc({
            "doctype":"File","file_name":final_filename,
            "is_private":1,"file_url":f"/private/files/{final_filename}"
        })
        file_doc.insert(ignore_permissions=True)
        frappe.db.commit()

        for temp_file in temp_files:
            if os.path.exists(temp_file):
                os.remove(temp_file)

        return {"pdf_url": file_doc.file_url, "file_name": final_filename}

    except Exception as e:
        for temp_file in temp_files:
            if os.path.exists(temp_file):
                try: os.remove(temp_file)
                except Exception: pass
        frappe.log_error(f"Error during bulk salary slip print: {str(e)}", "Bulk Print Salary Slips")
        frappe.throw("An error occurred while generating the PDF. Please try again or contact your system administrator.")


@frappe.whitelist()
def get_salary_slips_print_summary(company, year, month, category=None):
    month_map = {'January':1,'February':2,'March':3,'April':4,'May':5,'June':6,
                 'July':7,'August':8,'September':9,'October':10,'November':11,'December':12}
    month_num = month_map.get(month)
    if not month_num:
        frappe.throw("Invalid month")
    start_date = f"{year}-{month_num:02d}-01"

    category_filter = "AND category = %(category)s" if category else ""
    all_employees = frappe.db.sql(f"""
        SELECT name, full_name AS employee_name FROM `tabCompany Link`
        WHERE is_active=1 AND company=%(company)s {category_filter}
    """, {"company": company, "category": category}, as_dict=1)
    total_active = len(all_employees)

    all_slips = frappe.db.sql("""
        SELECT name, employee, employee_name, docstatus FROM `tabSalary Slip`
        WHERE start_date=%(start_date)s AND company=%(company)s ORDER BY employee_name
    """, {"company": company, "start_date": start_date}, as_dict=1)
    slip_by_emp = {sl.employee: sl for sl in all_slips}

    submitted     = []
    not_printable = []
    for emp in all_employees:
        slip = slip_by_emp.get(emp.name)
        if slip and slip.docstatus == 1:
            submitted.append(slip)
        else:
            reasons     = []
            slip_name   = None
            slip_status = 'No Slip'
            if not slip:
                reasons.append('Salary slip has not been created for this period')
            elif slip.docstatus == 0:
                slip_name = slip.name; slip_status = 'Draft'
                reasons.append('Salary slip is in Draft — submit it first to enable printing')
            elif slip.docstatus == 2:
                slip_name = slip.name; slip_status = 'Cancelled'
                reasons.append('Salary slip was cancelled and cannot be printed')
            not_printable.append({
                'employee': emp.name, 'employee_name': emp.employee_name or emp.name,
                'slip_name': slip_name, 'slip_status': slip_status, 'reasons': reasons,
            })

    return {
        'submitted': submitted, 'not_printable': not_printable,
        'total_active': total_active, 'total_submitted': len(submitted),
    }


# ─── Print HTML ───────────────────────────────────────────────────────────────

def generate_bulk_print_html(doc):
    from frappe.utils import fmt_money, formatdate, money_in_words

    company_address = ""
    if doc.company:
        company_address = frappe.db.get_value("Company", doc.company, "address") or ""

    company_link_details = {}
    if doc.employee:
        result = frappe.db.get_value("Company Link", doc.employee,
            ["employee","date_of_joining","designation","department","branch","category","division"], as_dict=True)
        if result:
            company_link_details = result

    doj           = company_link_details.get("date_of_joining")
    employee_link = company_link_details.get("employee")
    designation   = company_link_details.get("designation")
    department    = company_link_details.get("department")
    branch        = company_link_details.get("branch")
    category      = company_link_details.get("category")
    division      = company_link_details.get("division")

    employee_details = {}
    if employee_link:
        result = frappe.db.get_value("Employee", employee_link,
            ["employee_pf_account","esic_number","lin_number","bank_name","account_number","ifsc_code","gender"], as_dict=True)
        if result:
            employee_details = result

    present_days = doc.present_days or 0

    # ── SSA earnings (for print left column) ─────────────────
    salary_assignment = frappe.db.sql("""
        SELECT name FROM `tabSalary Structure Assignment`
        WHERE employee=%s AND docstatus=1 AND from_date<=%s AND (to_date IS NULL OR to_date>=%s)
        ORDER BY from_date DESC LIMIT 1
    """, (doc.employee, doc.end_date, doc.start_date), as_dict=1)
    assignment_name = salary_assignment[0].name if salary_assignment else None

    assignment_earnings       = []
    assignment_earnings_total = 0
    if assignment_name:
        assignment_earnings = frappe.db.sql("""
            SELECT salary_component, amount FROM `tabSalary Details`
            WHERE parent=%s AND parenttype='Salary Structure Assignment' AND parentfield='earnings'
            ORDER BY idx ASC
        """, (assignment_name,), as_dict=1)
        for ae in assignment_earnings:
            assignment_earnings_total += (ae.amount or 0)

    # ── Computed earnings ─────────────────────────────────────
    computed_earnings_total = 0
    computed_items = []
    for e in doc.earnings:
        computed_items.append(e)
        computed_earnings_total += (e.amount or 0)

    # ── Employee-share deductions ─────────────────────────────
    deductions_total = 0
    deduction_items  = []
    for d in doc.deductions:
        deduction_items.append(d)
        deductions_total += (d.amount or 0)

    # ── Employer-share rows ───────────────────────────────────
    employer_share_total = 0
    employer_share_items = []
    for d in (doc.employer_share or []):
        employer_share_items.append(d)
        employer_share_total += (d.amount or 0)

    max_rows = max(len(assignment_earnings), len(computed_items), len(deduction_items), 1)
    earnings_deductions_rows = ""
    for i in range(max_rows):
        earnings_deductions_rows += "<tr>"
        if i < len(assignment_earnings):
            ae = assignment_earnings[i]
            earnings_deductions_rows += (
                f'<td style="padding:6px;border:1px solid #ddd;font-size:11px;">{ae.salary_component}</td>'
                f'<td style="padding:6px;border:1px solid #ddd;text-align:right;font-size:11px;">{fmt_money(ae.amount, currency=doc.currency)}</td>'
            )
        else:
            earnings_deductions_rows += '<td style="padding:6px;border:1px solid #ddd;">&nbsp;</td><td style="padding:6px;border:1px solid #ddd;">&nbsp;</td>'
        if i < len(computed_items):
            e = computed_items[i]
            earnings_deductions_rows += (
                f'<td style="padding:6px;border:1px solid #ddd;font-size:11px;">{e.salary_component}</td>'
                f'<td style="padding:6px;border:1px solid #ddd;text-align:right;font-size:11px;">{fmt_money(e.amount, currency=doc.currency)}</td>'
            )
        else:
            earnings_deductions_rows += '<td style="padding:6px;border:1px solid #ddd;">&nbsp;</td><td style="padding:6px;border:1px solid #ddd;">&nbsp;</td>'
        if i < len(deduction_items):
            d = deduction_items[i]
            earnings_deductions_rows += (
                f'<td style="padding:6px;border:1px solid #ddd;font-size:11px;">{d.salary_component}</td>'
                f'<td style="padding:6px;border:1px solid #ddd;text-align:right;font-size:11px;">{fmt_money(d.amount, currency=doc.currency)}</td>'
            )
        else:
            earnings_deductions_rows += '<td style="padding:6px;border:1px solid #ddd;">&nbsp;</td><td style="padding:6px;border:1px solid #ddd;">&nbsp;</td>'
        earnings_deductions_rows += "</tr>"

    employer_share_rows = ""  # kept for backward compat but not printed

    address_html = f'<p style="font-size:11px;margin:2px 0;"><strong>Address:</strong> {company_address}</p>' if company_address else ""

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
* {{ margin:0;padding:0;box-sizing:border-box; }}
body {{ font-family:Arial,sans-serif;font-size:11px; }}
.container {{ border:2px solid #000;padding:15px;max-width:100%; }}
.header {{ text-align:center;margin-bottom:10px;border-bottom:2px solid #000;padding-bottom:8px; }}
.header h2 {{ font-size:16px;margin-bottom:5px; }}
.payslip-title {{ background-color:#f2f2f2;text-align:center;padding:8px;margin-bottom:10px;border:1px solid #ccc; }}
.payslip-title h3 {{ font-size:14px;margin:0; }}
table {{ width:100%;border-collapse:collapse; }}
.summary-table th {{ background-color:#e8e8e8;padding:6px;text-align:left;border:1px solid #ccc;font-size:12px; }}
.summary-table td {{ padding:5px 8px;border:1px solid #ddd;font-size:11px; }}
.summary-table .label {{ font-weight:600;background-color:#f5f5f5;width:16%; }}
.earnings-table th {{ background-color:#f8f8f8;padding:8px;border:2px solid #000;font-size:12px;font-weight:bold;text-align:center; }}
.earnings-table .total-row {{ background-color:#e8f4f8;font-weight:bold; }}
.employer-table th {{ background-color:#f0f4f8;padding:8px;border:2px solid #000;font-size:12px;font-weight:bold;text-align:center; }}
.employer-table .total-row {{ background-color:#ddeeff;font-weight:bold; }}
.net-payable {{ background-color:#f9f9f9;padding:10px;text-align:center;border:2px solid #000;margin-top:10px; }}
.net-payable .amount {{ font-size:14px;font-weight:bold;margin-bottom:3px; }}
</style></head><body>
<div class="container">
<div class="header"><h2><strong>{doc.company}</strong></h2>{address_html}</div>
<div class="payslip-title"><h3>Payslip for the Month of {formatdate(doc.start_date, "MMMM yyyy")}</h3></div>
<table class="summary-table"><thead><tr><th colspan="6">Employee Pay Summary</th></tr></thead><tbody>
<tr><td class="label">Employee Name</td><td>{doc.employee_name or '-'}</td><td class="label">Gender</td><td>{employee_details.get('gender') or '-'}</td><td class="label">Date of Joining</td><td>{formatdate(doj,'dd-MM-yyyy') if doj else '-'}</td></tr>
<tr><td class="label">Designation</td><td>{designation or '-'}</td><td class="label">Department</td><td>{department or '-'}</td><td class="label">Branch</td><td>{branch or '-'}</td></tr>
<tr><td class="label">Category</td><td>{category or '-'}</td><td class="label">Division</td><td>{division or '-'}</td><td class="label">Payment Days</td><td>{doc.payment_days or 0}</td></tr>
<tr><td class="label">PF Account No</td><td>{employee_details.get('employee_pf_account') or '-'}</td><td class="label">ESI Number</td><td>{employee_details.get('esic_number') or '-'}</td><td class="label">LIN Number</td><td>{employee_details.get('lin_number') or '-'}</td></tr>
<tr><td class="label">Bank Name</td><td>{employee_details.get('bank_name') or '-'}</td><td class="label">Account Number</td><td>{employee_details.get('account_number') or '-'}</td><td class="label">IFSC Code</td><td>{employee_details.get('ifsc_code') or '-'}</td></tr>
<tr><td class="label">Working Days</td><td>{doc.total_working_days or 0}</td><td class="label">Present Days</td><td>{present_days}</td><td class="label">Absent Days</td><td>{doc.absent_days or 0}</td></tr>
<tr><td class="label">Holidays</td><td>{doc.total_holidays or 0}</td><td class="label">Half Days</td><td>{doc.total_half_days or 0}</td><td class="label">LWP</td><td>{doc.total_lwp or 0}</td></tr>
<tr><td class="label">Earned Leaves</td><td>{doc.total_earned_leaves or 0}</td><td class="label">Casual Leaves</td><td>{doc.total_casual_leaves or 0}</td><td class="label">Physical Working Days</td><td>{doc.physical_working_days or 0}</td></tr>
</tbody></table>
<table class="earnings-table" style="margin-top:10px;"><thead>
<tr><th colspan="2">Earnings (SSA)</th><th colspan="2">Computed Earnings</th><th colspan="2">Deductions (Employee)</th></tr>
<tr>
<th style="width:16.66%;text-align:left;font-size:10px;font-weight:normal;">Component</th>
<th style="width:16.66%;text-align:right;font-size:10px;font-weight:normal;">Amount</th>
<th style="width:16.66%;text-align:left;font-size:10px;font-weight:normal;">Component</th>
<th style="width:16.66%;text-align:right;font-size:10px;font-weight:normal;">Amount</th>
<th style="width:16.66%;text-align:left;font-size:10px;font-weight:normal;">Component</th>
<th style="width:16.66%;text-align:right;font-size:10px;font-weight:normal;">Amount</th>
</tr></thead><tbody>
{earnings_deductions_rows}
<tr class="total-row">
<td style="padding:8px;border:1px solid #000;font-size:12px;">Total</td>
<td style="padding:8px;border:1px solid #000;text-align:right;font-size:12px;">{fmt_money(assignment_earnings_total, currency=doc.currency)}</td>
<td style="padding:8px;border:1px solid #000;font-size:12px;">Total</td>
<td style="padding:8px;border:1px solid #000;text-align:right;font-size:12px;">{fmt_money(computed_earnings_total, currency=doc.currency)}</td>
<td style="padding:8px;border:1px solid #000;font-size:12px;">Total</td>
<td style="padding:8px;border:1px solid #000;text-align:right;font-size:12px;">{fmt_money(deductions_total, currency=doc.currency)}</td>
</tr></tbody></table>
<div class="net-payable">
<div class="amount">Total Net Payable: {fmt_money(flt(doc.net_salary,2), currency=doc.currency)}</div>
<div class="words">({money_in_words(flt(doc.net_salary,2), doc.currency)})</div>
</div></div></body></html>"""
    return html