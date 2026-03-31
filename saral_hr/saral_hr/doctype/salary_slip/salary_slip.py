import frappe
from frappe.model.document import Document
from frappe.utils import getdate, get_last_day, flt
import calendar
from datetime import timedelta
import json
from PyPDF2 import PdfMerger
import os

BULK_PRINT_FORMAT = "Salary Slip Custom"

ATTENDANCE_ALLOWANCE_COMPONENT = "Attendance Allowance"


class SalarySlip(Document):
    def validate(self):
        if self.start_date:
            self.end_date = get_last_day(getdate(self.start_date))


def _is_attendance_allowance(comp_name):
    return (comp_name or "").strip() == ATTENDANCE_ALLOWANCE_COMPONENT


def _calc_attendance_allowance(base, physical_working_days, working_days, start_month):
    if base == 0:
        return 0.0
    phd = flt(physical_working_days)
    if start_month == 2:
        required = flt(working_days)
        return flt(base, 2) if phd >= required else 0.0
    else:
        return flt(base, 2) if phd >= 25 else 0.0


@frappe.whitelist()
def check_duplicate_salary_slip(employee, start_date, current_doc=""):
    filters = {"employee": employee, "start_date": start_date, "docstatus": ["in", [0, 1]]}
    existing = frappe.db.get_value("Salary Slip", filters, ["name", "docstatus"], as_dict=True)
    if not existing:
        return {"status": "ok"}
    if current_doc and existing.name == current_doc:
        return {"status": "ok"}
    status_label = "Draft" if existing.docstatus == 0 else "Submitted"
    return {
        "status": "duplicate",
        "message": (
            f"A salary slip ({existing.name}) already exists for this employee "
            f"for the selected period and is currently in {status_label} status."
        )
    }


_ADDITIONAL_SALARY_KEY     = "Additional Salary"
_ADDITIONAL_SALARY_ALIASES = {"Additional Salary", "Arrears"}


def _get_additional_salary_total(employee, year_str, month_str):
    total = 0.0
    records = frappe.db.get_all(
        "Additional Salary",
        filters={"employee": employee, "year": year_str, "month": month_str, "docstatus": 1},
        fields=["name"]
    )
    for rec in records:
        doc = frappe.get_doc("Additional Salary", rec.name)
        for row in doc.components or []:
            total += flt(row.amount)
    return total


@frappe.whitelist()
def get_salary_structure_for_employee(
    employee, start_date=None,
    working_days=None, payment_days=None,
    physical_working_days=None,
    variable_pay_percentage=None
):
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
    year_str = month_str = None
    start_month_num = None
    if start_date:
        d = getdate(start_date)
        current_month   = month_names[d.month - 1]
        year_str        = str(d.year)
        month_str       = current_month
        start_month_num = d.month

    wd     = flt(working_days)            if working_days            is not None else None
    pd     = flt(payment_days)            if payment_days            is not None else None
    phd    = flt(physical_working_days)   if physical_working_days   is not None else None
    vp_pct = flt(variable_pay_percentage) / 100.0 if variable_pay_percentage is not None else None
    has_att_data = (wd is not None and pd is not None and phd is not None and vp_pct is not None)

    def _comp_meta(comp_name):
        return frappe.db.get_value(
            "Salary Component", comp_name,
            ["salary_component_abbr", "depends_on_payment_days",
             "depends_on_physical_working_days", "employer_contribution",
             "type", "daily_wage_component"],
            as_dict=True
        ) or {}

    def _prorate(base, dep_pd, dep_phd, is_daily_wage, per_day_rate, comp_name=None):
        if is_daily_wage and flt(per_day_rate) > 0:
            if not has_att_data:
                return base
            if dep_phd and phd is not None:
                return flt(per_day_rate) * phd
            else:
                return flt(per_day_rate) * (pd if pd is not None else 0)
        if not has_att_data or wd == 0:
            return base
        if dep_phd:
            return (base / wd) * phd
        if dep_pd:
            return (base / wd) * pd
        return base

    earnings       = []
    deductions     = []
    employer_share = []
    actual_earnings_map = {}

    for row in (ssa_doc.earnings or []):
        meta          = _comp_meta(row.salary_component)
        base          = flt(row.amount, 2)
        dep_pd        = int(meta.get("depends_on_payment_days") or 0)
        dep_phd       = int(meta.get("depends_on_physical_working_days") or 0)
        is_daily_wage = int(meta.get("daily_wage_component") or getattr(row, "daily_wage_component", 0) or 0)
        per_day_rate  = flt(getattr(row, "per_day_rate", None) or 0)
        comp_lower    = (row.salary_component or "").lower()

        if _is_attendance_allowance(row.salary_component):
            actual = _calc_attendance_allowance(base, phd, wd, start_month_num) if (has_att_data and base > 0) else base
        elif has_att_data and "variable" in comp_lower:
            actual = (base / wd * pd * vp_pct) if (dep_pd and wd > 0) else (base * vp_pct)
        else:
            actual = _prorate(base, dep_pd, dep_phd, is_daily_wage, per_day_rate, row.salary_component)

        actual_earnings_map[row.salary_component] = flt(actual, 2)
        earnings.append({
            "salary_component":                 row.salary_component,
            "abbr":                             meta.get("salary_component_abbr") or getattr(row, "abbr", "") or "",
            "amount":                           base,
            "base_amount":                      base,
            "per_day_rate":                     per_day_rate,
            "daily_wage_component":             is_daily_wage,
            "depends_on_payment_days":          dep_pd,
            "depends_on_physical_working_days": dep_phd,
        })

    additional_total_for_check = 0.0
    if employee and year_str and month_str:
        additional_total_for_check = _get_additional_salary_total(employee, year_str, month_str)

    statutory_needs_recompute = False
    if has_att_data:
        statutory_needs_recompute = True
    elif additional_total_for_check > 0 and ssa_doc.company:
        comp_doc   = frappe.get_doc("Company", ssa_doc.company)
        esic_comps = set(comp_doc._get_child_components("esic_dependent_component"))
        pf_comps   = set(comp_doc._get_child_components("pf_dependent_component"))
        if (esic_comps & _ADDITIONAL_SALARY_ALIASES) or (pf_comps & _ADDITIONAL_SALARY_ALIASES):
            statutory_needs_recompute = True

    for row in (ssa_doc.deductions or []):
        if statutory_needs_recompute and _is_statutory_component(row.salary_component):
            continue
        if _is_pt_component(row.salary_component) and _is_pt_exempt(employee, start_date):
            continue
        meta          = _comp_meta(row.salary_component)
        is_daily_wage = int(meta.get("daily_wage_component") or getattr(row, "daily_wage_component", 0) or 0)
        per_day_rate  = flt(getattr(row, "per_day_rate", None) or 0)
        amount        = flt(row.amount, 2)
        if _is_pt_component(row.salary_component):
            amount = 300.0 if current_month == "February" else 200.0
        deductions.append({
            "salary_component":                 row.salary_component,
            "abbr":                             meta.get("salary_component_abbr") or getattr(row, "abbr", "") or "",
            "amount":                           amount,
            "base_amount":                      amount,
            "per_day_rate":                     per_day_rate,
            "daily_wage_component":             is_daily_wage,
            "employer_contribution":            0,
            "depends_on_payment_days":          int(meta.get("depends_on_payment_days") or 0),
            "depends_on_physical_working_days": int(meta.get("depends_on_physical_working_days") or 0),
        })

    for row in (ssa_doc.employer_share or []):
        if statutory_needs_recompute and _is_statutory_component(row.salary_component):
            continue
        meta          = _comp_meta(row.salary_component)
        is_daily_wage = int(meta.get("daily_wage_component") or getattr(row, "daily_wage_component", 0) or 0)
        per_day_rate  = flt(getattr(row, "per_day_rate", None) or 0)
        employer_share.append({
            "salary_component":                 row.salary_component,
            "abbr":                             meta.get("salary_component_abbr") or getattr(row, "abbr", "") or "",
            "amount":                           flt(row.amount, 2),
            "base_amount":                      flt(row.amount, 2),
            "per_day_rate":                     per_day_rate,
            "daily_wage_component":             is_daily_wage,
            "employer_contribution":            1,
            "depends_on_payment_days":          0,
            "depends_on_physical_working_days": 0,
        })

    if statutory_needs_recompute:
        earnings_map = dict(actual_earnings_map)
        if additional_total_for_check > 0:
            earnings_map[_ADDITIONAL_SALARY_KEY] = (
                earnings_map.get(_ADDITIONAL_SALARY_KEY, 0.0) + additional_total_for_check
            )
        gross_salary = sum(earnings_map.values())
        recomputed = get_statutory_components_internal(
            company=ssa_doc.company, gross_salary=gross_salary,
            earnings_map=earnings_map, from_date=start_date or "",
            is_esic_applicable=int(ssa_doc.is_esic_applicable or 0),
            is_pf_applicable=int(ssa_doc.is_pf_applicable or 0),
            pf_type=ssa_doc.pf_applicable or "",
            is_pt_applicable=int(ssa_doc.is_pt_applicable or 0),
            is_lwf_applicable=int(ssa_doc.is_lwf_applicable or 0),
        )
        for d in (recomputed.get("deductions") or []):
            if _is_pt_component(d["salary_component"]) and _is_pt_exempt(employee, start_date):
                continue
            amount = flt(d["amount"], 2)
            if _is_pt_component(d["salary_component"]):
                amount = 300.0 if current_month == "February" else 200.0
            deductions.append({
                "salary_component": d["salary_component"], "abbr": d.get("abbr") or "",
                "amount": amount, "base_amount": amount,
                "per_day_rate": 0, "daily_wage_component": 0,
                "employer_contribution": 0,
                "depends_on_payment_days": 0, "depends_on_physical_working_days": 0,
            })
        for d in (recomputed.get("employer_share") or []):
            employer_share.append({
                "salary_component": d["salary_component"], "abbr": d.get("abbr") or "",
                "amount": flt(d["amount"], 2), "base_amount": flt(d["amount"], 2),
                "per_day_rate": 0, "daily_wage_component": 0, "employer_contribution": 1,
                "depends_on_payment_days": 0, "depends_on_physical_working_days": 0,
            })

    return {
        "salary_structure": ssa_doc.salary_structure,
        "currency":         "INR",
        "earnings":         earnings,
        "deductions":       deductions,
        "employer_share":   employer_share,
        "ssa_gross":        sum(flt(r.amount) for r in (ssa_doc.earnings or [])),
    }


STATUTORY_COMPONENTS = {
    "Employee ESIC", "Employer ESIC", "Employee PF", "Employer PF",
    "Employer EPS", "Employer EDLI", "Employer PF Admin Charges",
    "Professional Tax", "Employee Labour Welfare Fund", "Employer Labour Welfare Fund",
}
PT_COMPONENT_NAME = "Professional Tax"


def _is_statutory_component(comp_name):
    return (comp_name or "").strip() in STATUTORY_COMPONENTS


def _is_pt_component(comp_name):
    return (comp_name or "").strip() == PT_COMPONENT_NAME


def _is_pt_exempt(employee, start_date):
    if not employee or not start_date:
        return False
    try:
        dob = frappe.db.get_value("Employee", employee, "date_of_birth")
        if not dob:
            dob = (
                frappe.db.get_value("Company Link", employee, "date_of_birth") or
                frappe.db.get_value(
                    "Employee",
                    frappe.db.get_value("Company Link", employee, "employee"),
                    "date_of_birth"
                )
            )
        if not dob:
            return False
        from dateutil.relativedelta import relativedelta
        return relativedelta(getdate(start_date), getdate(dob)).years >= 65
    except Exception:
        return False


def calculate_salary_slip_amounts_exact(
    salary_slip, variable_pay_percentage,
    start_date, category=None, ssa_gross=None
):
    wd           = flt(salary_slip.total_working_days)
    pd           = flt(salary_slip.payment_days)
    phd          = flt(salary_slip.physical_working_days)
    variable_pct = flt(variable_pay_percentage)

    total_earnings = total_deductions = total_employer_contribution = 0.0
    basic_amount = da_amount = retention = 0.0
    start_month = getdate(start_date).month if start_date else None

    for row in salary_slip.earnings:
        base          = flt(row.base_amount if row.base_amount is not None else row.amount)
        row.base_amount = base
        comp          = (row.salary_component or "").lower()
        is_daily_wage = int(getattr(row, "daily_wage_component", 0) or 0)
        per_day_rate  = flt(getattr(row, "per_day_rate", 0) or 0)

        if _is_attendance_allowance(row.salary_component):
            amount = _calc_attendance_allowance(base, phd, wd, start_month)
        elif "variable" in comp:
            amount = (
                0.0 if pd == 0 else
                (base / wd) * pd * variable_pct if (wd > 0 and row.depends_on_payment_days)
                else base * variable_pct
            )
        elif is_daily_wage and per_day_rate > 0:
            amount = per_day_rate * phd if row.depends_on_physical_working_days else per_day_rate * pd
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

    for row in salary_slip.deductions:
        base          = flt(row.base_amount if row.base_amount is not None else row.amount)
        row.base_amount = base
        is_daily_wage = int(getattr(row, "daily_wage_component", 0) or 0)
        per_day_rate  = flt(getattr(row, "per_day_rate", 0) or 0)
        is_pt         = _is_pt_component(row.salary_component)

        if is_pt and _is_pt_exempt(salary_slip.employee, start_date):
            row.amount = 0.0
            continue

        if is_pt:
            amount = 300.0 if start_month == 2 else 200.0
        elif _is_statutory_component(row.salary_component):
            amount = base
        elif is_daily_wage and per_day_rate > 0:
            amount = per_day_rate * phd if row.depends_on_physical_working_days else per_day_rate * pd
        elif row.depends_on_physical_working_days and wd > 0 and base > 0:
            amount = (base / wd) * phd
        elif row.depends_on_payment_days and wd > 0 and base > 0:
            amount = (base / wd) * pd
        else:
            amount = base

        row.amount        = flt(amount, 2)
        total_deductions += row.amount
        if "retention" in (row.salary_component or "").lower():
            retention += row.amount

    for row in (salary_slip.employer_share or []):
        base          = flt(row.base_amount if row.base_amount is not None else row.amount)
        row.base_amount = base
        is_daily_wage = int(getattr(row, "daily_wage_component", 0) or 0)
        per_day_rate  = flt(getattr(row, "per_day_rate", 0) or 0)

        if is_daily_wage and per_day_rate > 0:
            row.amount = flt(
                per_day_rate * phd if row.depends_on_physical_working_days else per_day_rate * pd, 2
            )
        else:
            row.amount = flt(base, 2)

        total_employer_contribution += row.amount

    salary_slip.total_earnings              = flt(total_earnings, 2)
    salary_slip.total_deductions            = flt(total_deductions, 2)
    salary_slip.net_salary                  = flt(total_earnings - total_deductions, 2)
    salary_slip.total_basic_da              = flt(basic_amount + da_amount, 2)
    salary_slip.total_employer_contribution = flt(total_employer_contribution, 2)
    salary_slip.retention                   = flt(retention, 2)


def _is_da_component(comp_name, abbr):
    n = (comp_name or "").lower()
    a = (abbr or "").lower()
    return (
        "dearness" in n or n == "da" or a == "da" or
        a.startswith("da-") or a.startswith("da ") or
        a == "da - dr" or a.startswith("da-dr")
    )


MONTHS_LIST = [
    "January","February","March","April","May","June",
    "July","August","September","October","November","December"
]

SC_EMP_ESIC   = "Employee ESIC";   SC_EMPR_ESIC  = "Employer ESIC"
SC_EMP_PF     = "Employee PF";     SC_EMPR_PF    = "Employer PF"
SC_EMPR_EPS   = "Employer EPS";    SC_EMPR_EDLI  = "Employer EDLI"
SC_EMPR_PFADM = "Employer PF Admin Charges"
SC_PT         = "Professional Tax"
SC_EMP_LWF    = "Employee Labour Welfare Fund"
SC_EMPR_LWF   = "Employer Labour Welfare Fund"


def get_statutory_components_internal(
    company, gross_salary, earnings_map, from_date,
    is_esic_applicable, is_pf_applicable, pf_type,
    is_pt_applicable, is_lwf_applicable
):
    VIRTUAL = {"Gross", "Gross Including Additional Salary"}

    def _sum(comps, gross, emap):
        t = 0.0
        for c in comps:
            if c in VIRTUAL: t += flt(gross)
            elif c in emap:  t += flt(emap[c])
        return max(t, 0.0)

    def abbr(n):
        return frappe.db.get_value("Salary Component", n, "salary_component_abbr") or ""

    def row(n, amt, emp=0):
        return {"salary_component": n, "abbr": abbr(n), "amount": flt(amt, 2), "employer_contribution": emp}

    deductions = []; employer_share = []
    comp_doc   = frappe.get_doc("Company", company) if company else None
    month_name = MONTHS_LIST[getdate(from_date).month - 1] if from_date else None

    if is_esic_applicable and comp_doc:
        cfg = comp_doc.get_esic_config()
        if cfg:
            wage = _sum(comp_doc._get_child_components("esic_dependent_component"), gross_salary, earnings_map)
            ep  = flt(cfg.get("employee_percent", 0))
            erp = flt(cfg.get("employer_percent", 0))
            if ep:  deductions.append(row(SC_EMP_ESIC, wage * ep / 100))
            if erp: employer_share.append(row(SC_EMPR_ESIC, wage * erp / 100, emp=1))

    if is_pf_applicable and comp_doc:
        cfg = comp_doc.get_pf_config()
        if cfg:
            raw  = _sum(comp_doc._get_child_components("pf_dependent_component"), gross_salary, earnings_map)
            wage = min(raw, flt(cfg["wage_limit"])) if pf_type == "Limited PF" and cfg.get("wage_limit") else raw
            ep   = flt(cfg.get("employee_percent", 0))
            epf  = flt(cfg.get("employer_epf", 0))
            eps  = flt(cfg.get("employer_eps", 0))
            edli = flt(cfg.get("edli_insurance", 0))
            adm  = flt(cfg.get("admin_charges", 0))
            if ep:   deductions.append(row(SC_EMP_PF,     wage * ep   / 100))
            if epf:  employer_share.append(row(SC_EMPR_PF,    wage * epf  / 100, emp=1))
            if eps:  employer_share.append(row(SC_EMPR_EPS,   wage * eps  / 100, emp=1))
            if edli: employer_share.append(row(SC_EMPR_EDLI,  wage * edli / 100, emp=1))
            if adm:  employer_share.append(row(SC_EMPR_PFADM, wage * adm  / 100, emp=1))

    if is_pt_applicable and month_name:
        deductions.append(row(SC_PT, _sa_local(SC_PT, month_name)))

    if is_lwf_applicable and month_name:
        deductions.append(row(SC_EMP_LWF, _sa_local(SC_EMP_LWF, month_name)))
        employer_share.append(row(SC_EMPR_LWF, _sa_local(SC_EMPR_LWF, month_name), emp=1))

    return {"deductions": deductions, "employer_share": employer_share}


def _sa_local(comp, month):
    try:
        doc = frappe.get_doc("Salary Component", comp)
        if not int(doc.is_special_component or 0): return 0.0
        for r in (doc.monthly_amounts or []):
            if r.month == month: return flt(r.amount)
    except frappe.DoesNotExistError:
        pass
    return 0.0


def get_additional_components_for_employee(employee, year, month):
    earnings = []; deductions = []
    for rec in frappe.db.get_all(
        "Additional Salary",
        filters={"employee": employee, "year": year, "month": month, "docstatus": 1},
        fields=["name"]
    ):
        doc = frappe.get_doc("Additional Salary", rec.name)
        for row in doc.components:
            earnings.append({
                "salary_component": row.component_type, "abbr": "",
                "amount": flt(row.amount), "base_amount": flt(row.amount),
                "depends_on_payment_days": 0, "depends_on_physical_working_days": 0
            })
    for rec in frappe.db.get_all(
        "Additional Deductions",
        filters={"employee": employee, "year": year, "month": month, "docstatus": 1},
        fields=["name"]
    ):
        doc = frappe.get_doc("Additional Deductions", rec.name)
        for row in doc.deductions:
            deductions.append({
                "salary_component": row.component_type, "abbr": "",
                "amount": flt(row.amount), "base_amount": flt(row.amount),
                "employer_contribution": 0,
                "depends_on_payment_days": 0, "depends_on_physical_working_days": 0
            })
    return earnings, deductions


@frappe.whitelist()
def get_additional_components_api(employee, start_date):
    if not employee or not start_date:
        return {"earnings": [], "deductions": []}
    d  = getdate(start_date)
    mn = [
        "January","February","March","April","May","June",
        "July","August","September","October","November","December"
    ]
    e, ded = get_additional_components_for_employee(employee, str(d.year), mn[d.month - 1])
    return {"earnings": e, "deductions": ded}


def _employee_requires_variable_pay(employee):
    return bool(frappe.db.get_value("Company Link", employee, "requires_variable_pay"))


@frappe.whitelist()
def get_variable_pay_percentage(employee, start_date):
    if not employee or not start_date: return None
    if not _employee_requires_variable_pay(employee): return None
    division = frappe.db.get_value("Company Link", employee, "division")
    if not division: return None
    d  = getdate(start_date); year = str(d.year)
    mn = [
        "January","February","March","April","May","June",
        "July","August","September","October","November","December"
    ]
    month = mn[d.month - 1]; vpa_name = f"{year} - {month}"
    if not frappe.db.exists("Variable Pay Assignment", vpa_name): return None
    vpa = frappe.get_doc("Variable Pay Assignment", vpa_name)
    for row in vpa.variable_pay:
        if row.division == division: return flt(row.percentage)
    return None


@frappe.whitelist()
def check_variable_pay_assignment(employee, start_date):
    if not employee or not start_date: return {"status": "ok"}
    if not _employee_requires_variable_pay(employee): return {"status": "ok"}
    division = frappe.db.get_value("Company Link", employee, "division")
    if not division: return {"status": "ok"}
    d  = getdate(start_date); year = str(d.year)
    mn = [
        "January","February","March","April","May","June",
        "July","August","September","October","November","December"
    ]
    month = mn[d.month - 1]; vpa_name = f"{year} - {month}"
    if not frappe.db.exists("Variable Pay Assignment", vpa_name):
        return {
            "status": "missing",
            "message": (
                f"No Variable Pay Assignment has been created for {month} {year}. "
                f"Please set up a Variable Pay Assignment for this payroll period before processing salary slips."
            )
        }
    vpa = frappe.get_doc("Variable Pay Assignment", vpa_name)
    if not any(r.division == division for r in vpa.variable_pay):
        return {
            "status": "missing",
            "message": (
                f"The division '{division}' has not been configured in the Variable Pay Assignment "
                f"for {month} {year}. Please update the Variable Pay Assignment to include this "
                f"division before processing salary slips."
            )
        }
    return {"status": "ok"}


def _classify_half(status):
    base = {
        "present": 0.0, "on_tour": 0.0, "eco": 0.0,
        "earned_leave": 0.0, "casual_leave": 0.0, "comp_off": 0.0,
        "absent": 0.0, "lwp": 0.0,
    }
    s = (status or "").strip()
    if s == "Present":           base["present"]      = 0.5
    elif s == "On Tour":         base["on_tour"]       = 0.5
    elif s == "Earned Comp Off": base["eco"]           = 0.5
    elif s == "Earned Leave":    base["earned_leave"]  = 0.5
    elif s == "Casual Leave":    base["casual_leave"]  = 0.5
    elif s == "Comp Off":        base["comp_off"]      = 0.5
    elif s == "LWP":             base["lwp"]           = 0.5
    else:                        base["absent"]        = 0.5
    return base


@frappe.whitelist()
def get_attendance_and_days(employee, start_date, working_days_calculation_method=None):
    start_date = getdate(start_date)
    end_date   = get_last_day(start_date)

    if not working_days_calculation_method:
        company = frappe.db.get_value("Company Link", employee, "company")
        if company:
            working_days_calculation_method = (
                frappe.db.get_value("Company", company, "salary_calculation_based_on") or ""
            )

    calculation_method = (
        "Include Weekly Offs"
        if "Include" in (working_days_calculation_method or "")
        else "Exclude Weekly Offs"
    )

    weekly_off       = frappe.db.get_value("Company Link", employee, "weekly_off")
    total_days       = calendar.monthrange(start_date.year, start_date.month)[1]
    day_map          = {
        "Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3,
        "Friday": 4, "Saturday": 5, "Sunday": 6,
    }
    weekly_off_count = 0
    if weekly_off:
        off_day = day_map.get(weekly_off)
        if off_day is not None:
            cur = start_date
            while cur <= end_date:
                if cur.weekday() == off_day:
                    weekly_off_count += 1
                cur += timedelta(days=1)

    attendance_records = frappe.db.get_all(
        "Attendance",
        filters={
            "employee":        employee,
            "attendance_date": ["between", [start_date, end_date]],
            "docstatus":       ["<", 2],
        },
        fields=["status", "custom_first_half", "custom_second_half"]
    )

    present_days    = 0.0
    on_tour         = 0.0
    earned_comp_off = 0.0
    earned_leave    = 0.0
    casual_leave    = 0.0
    comp_off        = 0.0
    absent_days     = 0.0
    lwp_days        = 0.0
    holiday_days    = 0.0
    half_day_count  = 0

    for a in attendance_records:
        status = (a.status or "").strip()
        if   status == "Present":          present_days    += 1.0
        elif status == "On Tour":          on_tour         += 1.0
        elif status == "Earned Comp Off":  earned_comp_off += 1.0
        elif status == "Earned Leave":     earned_leave    += 1.0
        elif status == "Casual Leave":     casual_leave    += 1.0
        elif status == "Comp Off":         comp_off        += 1.0
        elif status == "Absent":           absent_days     += 1.0
        elif status == "LWP":              lwp_days        += 1.0
        elif status == "Holiday":          holiday_days    += 1.0
        elif status == "Half Day":
            half_day_count += 1
            fh = (a.custom_first_half  or "").strip()
            sh = (a.custom_second_half or "").strip()
            for h in (fh, sh):
                c = _classify_half(h)
                present_days    += c["present"]
                on_tour         += c["on_tour"]
                earned_comp_off += c["eco"]
                earned_leave    += c["earned_leave"]
                casual_leave    += c["casual_leave"]
                comp_off        += c["comp_off"]
                absent_days     += c["absent"]
                lwp_days        += c["lwp"]

    total_unpaid = flt(absent_days + lwp_days, 2)

    if calculation_method == "Include Weekly Offs":
        working_days = total_days
        payment_days = flt(total_days - total_unpaid, 2)
    else:
        working_days = total_days - weekly_off_count
        payment_days = flt(working_days - total_unpaid, 2)

    physical_working_days = flt(payment_days - earned_leave - casual_leave - comp_off, 2)
    if physical_working_days < 0:
        physical_working_days = 0.0

    return {
        "attendance_count":      len(attendance_records),
        "total_days":            total_days,
        "weekly_offs":           weekly_off_count,
        "working_days":          working_days,
        "payment_days":          flt(payment_days, 2),
        "physical_working_days": flt(physical_working_days, 2),
        "present_days":          flt(present_days, 2),
        "absent_days":           flt(absent_days, 2),
        "total_half_days":       flt(half_day_count * 0.5, 2),
        "total_lwp":             flt(lwp_days, 2),
        "total_holidays":        flt(holiday_days, 2),
        "total_earned_leaves":   flt(earned_leave, 2),
        "total_casual_leaves":   flt(casual_leave, 2),
        "total_on_tour":         flt(on_tour, 2),
        "total_comp_off":        flt(comp_off, 2),
        "total_earned_comp_off": flt(earned_comp_off, 2),
        "total_unpaid_days":     flt(total_unpaid, 2),
        "calculation_method":    calculation_method,
    }


# ─── Eligible employees — three buckets ──────────────────────────────────────
#
#  eligible          → no slip yet, all prereqs met → checkbox enabled
#  already_generated → slip already exists (Draft or Submitted) → shown separately
#  skipped           → missing salary structure / attendance / VPA → not eligible

@frappe.whitelist()
def get_eligible_employees_for_salary_slip(company, year, month, category=None, division=None):
    month_map = {
        'January':1,'February':2,'March':3,'April':4,'May':5,'June':6,
        'July':7,'August':8,'September':9,'October':10,'November':11,'December':12
    }
    month_num = month_map.get(month)
    if not month_num: frappe.throw("Invalid month")
    start_date     = f"{year}-{month_num:02d}-01"
    start_date_obj = getdate(start_date)
    end_date       = get_last_day(start_date_obj)

    vpa_name      = f"{year} - {month}"
    vpa_exists    = frappe.db.exists("Variable Pay Assignment", vpa_name)
    vpa_divisions = set()
    if vpa_exists:
        vpa_doc       = frappe.get_doc("Variable Pay Assignment", vpa_name)
        vpa_divisions = {r.division for r in vpa_doc.variable_pay}

    # Build optional WHERE clauses
    extra_filters = ""
    filter_params = {"company": company}
    if category:
        extra_filters += " AND cl.category = %(category)s"
        filter_params["category"] = category
    if division:
        extra_filters += " AND cl.division = %(division)s"
        filter_params["division"] = division

    all_emps = frappe.db.sql(f"""
        SELECT DISTINCT cl.name, cl.full_name AS employee_name, cl.department,
            cl.designation, cl.company, cl.division, cl.requires_variable_pay
        FROM `tabCompany Link` cl
        WHERE cl.is_active=1 AND cl.company=%(company)s {extra_filters}
    """, filter_params, as_dict=1)

    with_structure = frappe.db.sql("""
        SELECT DISTINCT cl.name FROM `tabCompany Link` cl
        INNER JOIN `tabSalary Structure Assignment` ssa ON ssa.employee=cl.name
        WHERE cl.is_active=1 AND cl.company=%(company)s AND ssa.docstatus=1
          AND ssa.from_date<=%(start_date)s AND (ssa.to_date IS NULL OR ssa.to_date>=%(end_date)s)
    """, {"company": company, "start_date": start_date, "end_date": str(end_date)}, as_dict=1)
    with_structure_ids = {e.name for e in with_structure}

    emp_names = [e.name for e in all_emps]
    att_counts = {}
    if emp_names:
        ph   = ", ".join(["%s"] * len(emp_names))
        rows = frappe.db.sql(
            f"SELECT employee, COUNT(*) AS cnt FROM `tabAttendance` "
            f"WHERE employee IN ({ph}) AND attendance_date BETWEEN %s AND %s GROUP BY employee",
            tuple(emp_names) + (str(start_date_obj), str(end_date))
        )
        att_counts = {r[0]: r[1] for r in rows}

    # Fetch existing slips (Draft or Submitted) for the period
    existing_slips = {}
    if emp_names:
        ph = ", ".join(["%s"] * len(emp_names))
        slip_rows = frappe.db.sql(
            f"SELECT name, employee, docstatus FROM `tabSalary Slip` "
            f"WHERE employee IN ({ph}) AND start_date=%s AND docstatus IN (0,1)",
            tuple(emp_names) + (start_date,),
            as_dict=1
        )
        for s in slip_rows:
            existing_slips[s.employee] = s

    eligible = []; ineligible = []; already_generated = []

    for emp in all_emps:
        # Check if already has a slip
        existing = existing_slips.get(emp.name)
        if existing:
            status_label = "Submitted" if existing.docstatus == 1 else "Draft"
            already_generated.append({
                "id":          emp.name,
                "name":        emp.employee_name or emp.name,
                "slip_name":   existing.name,
                "slip_status": status_label,
                "slip_info":   f"Salary slip ({existing.name}) already exists — {status_label}"
            })
            continue

        # Check prereqs
        unmet = []
        if emp.name not in with_structure_ids:
            unmet.append("No submitted Salary Structure Assignment found covering the full payroll period")
        if att_counts.get(emp.name, 0) == 0:
            unmet.append("No attendance has been recorded for this employee in the selected period")
        if emp.get("requires_variable_pay"):
            div = emp.get("division")
            if div:
                if not vpa_exists:
                    unmet.append(f"No Variable Pay Assignment has been created for {month} {year}")
                elif div not in vpa_divisions:
                    unmet.append(f"Division '{div}' is not configured in the Variable Pay Assignment for {month} {year}")

        if unmet:
            ineligible.append({"id": emp.name, "name": emp.employee_name or emp.name, "reasons": unmet})
        else:
            eligible.append(emp)

    cat_requires_vpa = any(e.get("requires_variable_pay") for e in all_emps)

    return {
        "eligible":                       eligible,
        "skipped":                        ineligible,
        "already_generated":              already_generated,
        "total_active":                   len(all_emps),
        "total_eligible":                 len(eligible),
        "category_requires_variable_pay": cat_requires_vpa,
    }


@frappe.whitelist()
def bulk_generate_salary_slips(employees, year, month):
    if isinstance(employees, str): employees = json.loads(employees)
    month_map = {
        'January':1,'February':2,'March':3,'April':4,'May':5,'June':6,
        'July':7,'August':8,'September':9,'October':10,'November':11,'December':12
    }
    month_num = month_map.get(month)
    if not month_num:
        return {"success": 0, "failed": len(employees), "errors": ["Invalid month"]}

    start_date = f"{year}-{month_num:02d}-01"
    success_count = failed_count = 0; errors = []

    for emp_data in employees:
        employee = emp_data.get('employee')
        try:
            emp_display = emp_data.get('employee_name', employee)
            dup = check_duplicate_salary_slip(employee, start_date)
            if dup.get("status") == "duplicate":
                errors.append(f"{emp_display}: {dup.get('message')}"); failed_count += 1; continue

            if _employee_requires_variable_pay(employee):
                division = frappe.db.get_value("Company Link", employee, "division")
                if division:
                    vpa_name = f"{year} - {month}"
                    if not frappe.db.exists("Variable Pay Assignment", vpa_name):
                        errors.append(f"{emp_display}: No Variable Pay Assignment found for {month} {year}"); failed_count += 1; continue
                    vpa = frappe.get_doc("Variable Pay Assignment", vpa_name)
                    if not any(r.division == division for r in vpa.variable_pay):
                        errors.append(f"{emp_display}: Division '{division}' not configured in VPA"); failed_count += 1; continue

            company_name = frappe.db.get_value("Company Link", employee, "company")
            wdcm = frappe.db.get_value("Company", company_name, "salary_calculation_based_on") or "" if company_name else ""

            att = get_attendance_and_days(employee, start_date, wdcm)
            if not att: errors.append(f"{emp_display}: Attendance data unavailable"); failed_count += 1; continue
            if att.get("attendance_count", 0) == 0: errors.append(f"{emp_display}: No attendance for {month} {year}"); failed_count += 1; continue

            vp_pct = get_variable_pay_percentage(employee, start_date)
            vp_dec = flt(vp_pct if vp_pct is not None else 0) / 100.0

            sd = get_salary_structure_for_employee(
                employee, start_date,
                working_days=att.get('working_days'), payment_days=att.get('payment_days'),
                physical_working_days=att.get('physical_working_days'),
                variable_pay_percentage=vp_pct if vp_pct is not None else 0
            )
            if not sd: errors.append(f"{emp_display}: No active SSA found"); failed_count += 1; continue

            category = frappe.db.get_value("Company Link", employee, "category")
            add_e, add_d = get_additional_components_for_employee(employee, year, month)

            ss = frappe.new_doc("Salary Slip")
            ss.employee = employee; ss.start_date = start_date
            ss.end_date = get_last_day(getdate(start_date)); ss.currency = "INR"
            ss.salary_structure = sd.get('salary_structure'); ss.working_days_calculation_method = wdcm

            ss.month_days            = att.get('total_days', 0)
            ss.total_working_days    = att.get('working_days')
            ss.payment_days          = att.get('payment_days')
            ss.physical_working_days = att.get('physical_working_days')
            ss.present_days          = att.get('present_days')
            ss.absent_days           = att.get('absent_days')
            ss.weekly_offs_count     = att.get('weekly_offs')
            ss.total_half_days       = att.get('total_half_days')
            ss.total_lwp             = att.get('total_lwp', 0)
            ss.total_holidays        = att.get('total_holidays', 0)
            ss.total_earned_leaves   = att.get('total_earned_leaves', 0)
            ss.total_casual_leaves   = att.get('total_casual_leaves', 0)
            ss.total_on_tour         = att.get('total_on_tour', 0)
            ss.total_comp_off        = att.get('total_comp_off', 0)
            ss.total_earned_comp_off = att.get('total_earned_comp_off', 0)
            ss.total_unpaid_days     = att.get('total_unpaid_days', 0)

            def _append_row(table, src, extra=None):
                r = ss.append(table, {})
                r.salary_component = src.get('salary_component')
                r.abbr             = src.get('abbr', '')
                r.amount           = flt(src.get('amount'))
                r.base_amount      = flt(src.get('base_amount', src.get('amount')))
                r.per_day_rate     = flt(src.get('per_day_rate', 0))
                r.daily_wage_component             = int(src.get('daily_wage_component', 0))
                r.depends_on_payment_days          = int(src.get('depends_on_payment_days', 0))
                r.depends_on_physical_working_days = int(src.get('depends_on_physical_working_days', 0))
                if extra is not None: r.employer_contribution = extra

            for e in sd.get('earnings', []):       _append_row('earnings', e)
            for d in sd.get('deductions', []):     _append_row('deductions', d, extra=0)
            for s in sd.get('employer_share', []): _append_row('employer_share', s, extra=1)
            for e in add_e: _append_row('earnings',   {**e, 'per_day_rate': 0, 'daily_wage_component': 0})
            for d in add_d: _append_row('deductions', {**d, 'per_day_rate': 0, 'daily_wage_component': 0, 'employer_contribution': 0})

            calculate_salary_slip_amounts_exact(ss, vp_dec, start_date, category, ssa_gross=sd.get('ssa_gross', 0))
            ss.insert(ignore_permissions=True); success_count += 1; frappe.db.commit()

        except Exception as e:
            errors.append(f"{emp_data.get('employee_name', employee)}: {str(e)}")
            failed_count += 1
            frappe.log_error(f"Salary slip error for {employee}: {str(e)}", "Bulk Salary Slip")
            frappe.db.rollback()

    return {"success": success_count, "failed": failed_count, "errors": errors}


@frappe.whitelist()
def get_submitted_salary_slips(company, year, month):
    month_map = {'January':1,'February':2,'March':3,'April':4,'May':5,'June':6,'July':7,'August':8,'September':9,'October':10,'November':11,'December':12}
    start_date = f"{year}-{month_map[month]:02d}-01"
    return frappe.db.sql(
        "SELECT ss.name,ss.employee,ss.employee_name,ss.department,ss.designation,"
        "ss.net_salary,ss.start_date,ss.end_date FROM `tabSalary Slip` ss "
        "WHERE ss.docstatus=1 AND ss.start_date=%(sd)s AND ss.company=%(co)s ORDER BY ss.employee_name",
        {"co": company, "sd": start_date}, as_dict=1
    )


@frappe.whitelist()
def get_draft_salary_slips(company, year, month):
    month_map = {'January':1,'February':2,'March':3,'April':4,'May':5,'June':6,'July':7,'August':8,'September':9,'October':10,'November':11,'December':12}
    start_date = f"{year}-{month_map[month]:02d}-01"
    return frappe.db.sql(
        "SELECT ss.name,ss.employee,ss.employee_name,ss.department,ss.designation,"
        "ss.net_salary,ss.start_date,ss.end_date FROM `tabSalary Slip` ss "
        "WHERE ss.docstatus=0 AND ss.start_date=%(sd)s AND ss.company=%(co)s ORDER BY ss.employee_name",
        {"co": company, "sd": start_date}, as_dict=1
    )


@frappe.whitelist()
def bulk_submit_salary_slips(salary_slip_names):
    if isinstance(salary_slip_names, str): salary_slip_names = json.loads(salary_slip_names)
    if not salary_slip_names: frappe.throw("No salary slips selected")
    success_count = failed_count = 0; errors = []
    for name in salary_slip_names:
        try:
            doc = frappe.get_doc("Salary Slip", name)
            if doc.docstatus != 0: errors.append(f"{name}: Not Draft"); failed_count += 1; continue
            doc.submit(); success_count += 1; frappe.db.commit()
        except Exception as e:
            errors.append(f"{name}: {str(e)}"); failed_count += 1
            frappe.log_error(f"Submit error {name}: {str(e)}", "Bulk Submit"); frappe.db.rollback()
    return {"success": success_count, "failed": failed_count, "errors": errors}


@frappe.whitelist()
def bulk_print_salary_slips(salary_slip_names):
    if isinstance(salary_slip_names, str): salary_slip_names = json.loads(salary_slip_names)
    if not salary_slip_names: frappe.throw("No salary slips selected")
    merger = PdfMerger(); temp_files = []
    import hashlib
    tag = hashlib.md5(f"{frappe.session.user}_{frappe.utils.now_datetime()}".encode()).hexdigest()[:8]
    try:
        for name in salary_slip_names:
            pdf = frappe.get_print(doctype="Salary Slip", name=name, print_format=BULK_PRINT_FORMAT, as_pdf=True, letterhead=None)
            tf = frappe.utils.get_files_path(f"temp_slip_{tag}_{name}.pdf", is_private=1)
            temp_files.append(tf)
            with open(tf, "wb") as f: f.write(pdf)
            merger.append(tf)
        ts = frappe.utils.now_datetime().strftime("%Y%m%d_%H%M%S")
        fn = f"Salary_Slips_{ts}.pdf"; fp = frappe.utils.get_files_path(fn, is_private=1)
        with open(fp, "wb") as f: merger.write(f)
        merger.close()
        fd = frappe.get_doc({"doctype": "File", "file_name": fn, "is_private": 1, "file_url": f"/private/files/{fn}"})
        fd.insert(ignore_permissions=True); frappe.db.commit()
        for tf in temp_files:
            if os.path.exists(tf): os.remove(tf)
        return {"pdf_url": fd.file_url, "file_name": fn}
    except Exception as e:
        merger.close()
        for tf in temp_files:
            if os.path.exists(tf):
                try: os.remove(tf)
                except: pass
        frappe.log_error(f"Bulk print error: {str(e)}", "Bulk Print"); frappe.throw("PDF generation failed.")


@frappe.whitelist()
def get_salary_slips_print_summary(company, year, month, category=None, division=None):
    month_map = {'January':1,'February':2,'March':3,'April':4,'May':5,'June':6,'July':7,'August':8,'September':9,'October':10,'November':11,'December':12}
    start_date = f"{year}-{month_map[month]:02d}-01"

    extra_filters = ""
    filter_params = {"company": company}
    if category:
        extra_filters += " AND category=%(category)s"
        filter_params["category"] = category
    if division:
        extra_filters += " AND division=%(division)s"
        filter_params["division"] = division

    all_emps = frappe.db.sql(
        f"SELECT name, full_name AS employee_name FROM `tabCompany Link` "
        f"WHERE is_active=1 AND company=%(company)s {extra_filters}",
        filter_params, as_dict=1
    )

    all_slips = frappe.db.sql(
        "SELECT name,employee,employee_name,docstatus FROM `tabSalary Slip` "
        "WHERE start_date=%(sd)s AND company=%(co)s ORDER BY employee_name",
        {"co": company, "sd": start_date}, as_dict=1
    )
    slip_map = {s.employee: s for s in all_slips}

    submitted = []; not_printable = []
    for emp in all_emps:
        slip = slip_map.get(emp.name)
        if slip and slip.docstatus == 1:
            submitted.append(slip)
        else:
            reasons = []; sn = None; ss = 'No Slip'
            if not slip:
                reasons.append('Salary slip has not been created for this period')
            elif slip.docstatus == 0:
                sn = slip.name; ss = 'Draft'
                reasons.append('Salary slip is in Draft — submit it first')
            elif slip.docstatus == 2:
                sn = slip.name; ss = 'Cancelled'
                reasons.append('Salary slip was cancelled')
            not_printable.append({
                'employee': emp.name,
                'employee_name': emp.employee_name or emp.name,
                'slip_name': sn, 'slip_status': ss, 'reasons': reasons
            })

    return {
        'submitted':       submitted,
        'not_printable':   not_printable,
        'total_active':    len(all_emps),
        'total_submitted': len(submitted)
    }