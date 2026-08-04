import frappe
from frappe.model.document import Document
from frappe.utils import getdate, get_last_day, flt
import calendar
from datetime import timedelta, date as date_type
import json
from decimal import Decimal, ROUND_HALF_UP
from PyPDF2 import PdfMerger
import os

BULK_PRINT_FORMAT = "Salary Slip Custom"

ATTENDANCE_ALLOWANCE_COMPONENT = "Attendance Allowance"


def _round_net_salary(value):
    return int(Decimal(str(flt(value, 2))).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def get_salary_amount_rounding_digits(company=None):
    """Company Misc Setting: 0 = whole rupees, 2 = paise. Default 2."""
    digits = 2
    if company:
        raw = frappe.db.get_value("Company", company, "salary_amount_rounding_digits")
        if raw is not None and raw != "":
            try:
                digits = int(raw)
            except (TypeError, ValueError):
                digits = 2
    return 0 if digits == 0 else 2


def _company_for_employee(employee):
    if not employee:
        return None
    return frappe.db.get_value("Company Link", employee, "company")


def _employee_gender_dob(employee):
    """Resolve gender and DOB from Employee / Company Link."""
    gender = None
    dob = None
    if not employee:
        return gender, dob
    if frappe.db.exists("Employee", employee):
        row = frappe.db.get_value("Employee", employee, ["gender", "date_of_birth"], as_dict=True)
        if row:
            gender, dob = row.gender, row.date_of_birth
    if not dob or not gender:
        link = frappe.db.get_value(
            "Company Link", employee, ["employee", "date_of_birth", "gender"], as_dict=True
        )
        if link:
            dob = dob or link.date_of_birth
            gender = gender or getattr(link, "gender", None)
            if link.employee and (not dob or not gender):
                emp = frappe.db.get_value(
                    "Employee", link.employee, ["gender", "date_of_birth"], as_dict=True
                )
                if emp:
                    gender = gender or emp.gender
                    dob = dob or emp.date_of_birth
    return gender, dob


def _company_pt_amount(company, gross, employee, period_date):
    if not company or not period_date:
        return 0.0
    try:
        comp_doc = frappe.get_doc("Company", company)
    except frappe.DoesNotExistError:
        return 0.0
    if not hasattr(comp_doc, "calculate_pt"):
        return 0.0
    gender, dob = _employee_gender_dob(employee)
    return flt(comp_doc.calculate_pt(gross, gender, period_date, dob))


def round_salary_amount(value, company=None, digits=None):
    if digits is None:
        digits = get_salary_amount_rounding_digits(company)
    return flt(value, digits)


class SalarySlip(Document):
    def validate(self):
        if self.start_date:
            self.end_date = get_last_day(getdate(self.start_date))

    def on_submit(self):
        self._sync_loan_advance_deducted(deducted=True)

    def on_cancel(self):
        self._sync_loan_advance_deducted(deducted=False)

    def _sync_loan_advance_deducted(self, deducted):
        d                = getdate(self.start_date)
        slip_month_label = f"{MONTHS_LIST[d.month - 1]} {d.year}"
        flag             = 1 if deducted else 0

        loan_doc_names    = set()
        advance_doc_names = set()

        for r in self.deductions:
            comp = (r.salary_component or "").lower()
            if "loan" in comp:
                loan_ref = (
                    getattr(r, "loan_name", None) or
                    getattr(r, "loan_id", None)
                )
                if loan_ref:
                    loan_doc_names.add(loan_ref)
            elif "advance" in comp:
                adv_ref = (
                    getattr(r, "loan_name", None) or
                    getattr(r, "loan_id", None)
                )
                if adv_ref:
                    advance_doc_names.add(adv_ref)

        if "loan" in " ".join(
            (r.salary_component or "").lower() for r in self.deductions
        ) and not loan_doc_names:
            rows = frappe.db.get_all(
                "Employee Loan Advance",
                filters={"employee": self.employee, "type": "Loan", "docstatus": 1},
                fields=["name"]
            )
            loan_doc_names = {r.name for r in rows}

        if "advance" in " ".join(
            (r.salary_component or "").lower() for r in self.deductions
        ) and not advance_doc_names:
            rows = frappe.db.get_all(
                "Employee Loan Advance",
                filters={"employee": self.employee, "type": "Advance", "docstatus": 1},
                fields=["name"]
            )
            advance_doc_names = {r.name for r in rows}

        for loan_name in loan_doc_names:
            try:
                doc = frappe.get_doc("Employee Loan Advance", loan_name)
            except frappe.DoesNotExistError:
                continue
            changed = False
            for srow in doc.schedule:
                if srow.month == slip_month_label and not srow.is_deferred:
                    frappe.db.set_value(
                        srow.doctype, srow.name,
                        "is_deducted", flag,
                        update_modified=False
                    )
                    changed = True
            if changed:
                doc.reload()
                doc.calculate_outstanding()
                frappe.db.set_value(
                    "Employee Loan Advance", doc.name,
                    {
                        "outstanding_amount": doc.outstanding_amount,
                        "total_deducted":     doc.total_deducted
                    },
                    update_modified=False
                )

        for adv_name in advance_doc_names:
            try:
                frappe.db.set_value(
                    "Employee Loan Advance", adv_name,
                    "is_deducted", flag,
                    update_modified=False
                )
            except frappe.DoesNotExistError:
                continue


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
    amount_digits = get_salary_amount_rounding_digits(ssa_doc.company)

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

        actual_earnings_map[row.salary_component] = flt(actual, amount_digits)
        earnings.append({
            "salary_component":                 row.salary_component,
            "abbr":                             meta.get("salary_component_abbr") or getattr(row, "abbr", "") or "",
            "amount":                           flt(base, amount_digits),
            "base_amount":                      flt(base, amount_digits),
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
    # AFTER
    elif additional_total_for_check > 0 and ssa_doc.company:
        comp_doc   = frappe.get_doc("Company", ssa_doc.company)
        esic_cfg   = comp_doc.get_esic_config(start_date)
        pf_cfg     = comp_doc.get_pf_config(start_date)
        esic_comps = set(esic_cfg.get("wage_components", []) if esic_cfg else [])
        pf_comps   = set(pf_cfg.get("wage_components", []) if pf_cfg else [])
        if (esic_comps & _ADDITIONAL_SALARY_ALIASES) or (pf_comps & _ADDITIONAL_SALARY_ALIASES):
            statutory_needs_recompute = True

    for row in (ssa_doc.deductions or []):
        if statutory_needs_recompute and _is_statutory_component(row.salary_component):
            continue
        meta          = _comp_meta(row.salary_component)
        is_daily_wage = int(meta.get("daily_wage_component") or getattr(row, "daily_wage_component", 0) or 0)
        per_day_rate  = flt(getattr(row, "per_day_rate", None) or 0)
        amount        = flt(row.amount, amount_digits)
        if _is_pt_component(row.salary_component):
            # Preview only — final PT is applied after gross in calculate_salary_slip_amounts_exact
            ssa_gross_est = sum(flt(r.amount) for r in (ssa_doc.earnings or []))
            amount = flt(
                _company_pt_amount(ssa_doc.company, ssa_gross_est, employee, start_date),
                amount_digits,
            )
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
            "amount":                           flt(row.amount, amount_digits),
            "base_amount":                      flt(row.amount, amount_digits),
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
            employee=employee,
        )
        for d in (recomputed.get("deductions") or []):
            amount = flt(d["amount"], amount_digits)
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
                "amount": flt(d["amount"], amount_digits), "base_amount": flt(d["amount"], amount_digits),
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


def calculate_salary_slip_amounts_exact(
    salary_slip, variable_pay_percentage,
    start_date, category=None, ssa_gross=None
):
    wd           = flt(salary_slip.total_working_days)
    pd           = flt(salary_slip.payment_days)
    phd          = flt(salary_slip.physical_working_days)
    variable_pct = flt(variable_pay_percentage)
    company = (
        getattr(salary_slip, "company", None)
        or _company_for_employee(getattr(salary_slip, "employee", None))
    )
    digits = get_salary_amount_rounding_digits(company)

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

        row.amount      = flt(amount, digits)
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

        if is_pt:
            amount = _company_pt_amount(company, total_earnings, salary_slip.employee, start_date)
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

        row.amount        = flt(amount, digits)
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
                per_day_rate * phd if row.depends_on_physical_working_days else per_day_rate * pd,
                digits,
            )
        else:
            row.amount = flt(base, digits)

        total_employer_contribution += row.amount

    salary_slip.total_earnings              = flt(total_earnings, digits)
    salary_slip.total_deductions            = flt(total_deductions, digits)
    salary_slip.net_salary                  = _round_net_salary(total_earnings - total_deductions)
    salary_slip.total_basic_da              = flt(basic_amount + da_amount, digits)
    salary_slip.total_employer_contribution = flt(total_employer_contribution, digits)
    salary_slip.retention                   = flt(retention, digits)


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
    is_pt_applicable, is_lwf_applicable, employee=None
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

    # AFTER
    if is_esic_applicable and comp_doc:
        cfg = comp_doc.get_esic_config(from_date)
        if cfg:
            wage = _sum(cfg["wage_components"], gross_salary, earnings_map)
            ep  = flt(cfg.get("employee_percent", 0))
            erp = flt(cfg.get("employer_percent", 0))
            if ep:  deductions.append(row(SC_EMP_ESIC, wage * ep / 100))
            if erp: employer_share.append(row(SC_EMPR_ESIC, wage * erp / 100, emp=1))

    if is_pf_applicable and comp_doc:
        cfg = comp_doc.get_pf_config(from_date)
        if cfg:
            raw  = _sum(cfg["wage_components"], gross_salary, earnings_map)
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

    if is_pt_applicable and from_date and comp_doc:
        gender, dob = _employee_gender_dob(employee)
        pt_amt = flt(comp_doc.calculate_pt(gross_salary, gender, from_date, dob))
        deductions.append(row(SC_PT, pt_amt))

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


@frappe.whitelist()
def get_loan_advance_deductions(employee, start_date):
    if not employee or not start_date:
        return []

    d                = getdate(start_date)
    slip_month_label = f"{MONTHS_LIST[d.month - 1]} {d.year}"

    records = frappe.db.get_all(
        "Employee Loan Advance",
        filters={"employee": employee, "docstatus": 1},
        fields=["name", "type"]
    )

    deductions = []

    for rec in records:
        doc = frappe.get_doc("Employee Loan Advance", rec.name)

        if doc.type == "Loan":
            for row in doc.schedule:
                if row.month == slip_month_label and not row.is_deducted:
                    component_name = f"{doc.type}-{doc.name.split('-')[-1]}"  # ✅ "Loan-0001"
                    deductions.append({
                        "salary_component": component_name,
                        "abbr":             component_name,
                        "amount":           flt(row.deduction_amount),
                        "is_deferred":      int(row.get("is_deferred", 0)),
                        "loan_name":        doc.name,
                        "loan_id":          doc.name,
                        "loan_type":        "Loan"
                    })

        elif doc.type == "Advance":
            if not doc.is_deducted:
                component_name = f"{doc.type}-{doc.name.split('-')[-1]}"  # ✅ "Advance-0001"
                deductions.append({
                    "salary_component": component_name,
                    "abbr":             component_name,
                    "amount":           flt(doc.amount),
                    "is_deferred":      0,
                    "loan_name":        doc.name,
                    "loan_id":          doc.name,
                    "loan_type":        "Advance"
                })

    return deductions  # ✅ Outside the loop


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


# ─── Sandwich Rule: statuses that are considered "paid" for holiday eligibility ───
# A day with any of these statuses will NOT break the sandwich around a holiday.
# Absent and LWP are unpaid and will break the sandwich.
_PAID_STATUSES_FOR_SANDWICH = {
    "Present", "On Tour", "Earned Comp Off",
    "Earned Leave", "Casual Leave", "Comp Off"
}


def _build_day_status_map(attendance_records, effective_start, effective_end):
    """
    Build a dict mapping each date in the effective range to its attendance status.
    Days with no attendance record are treated as Absent (unpaid).
    Half Day records are stored as a tuple of (first_half_status, second_half_status)
    so the sandwich check can evaluate them correctly.
    """
    day_map = {}

    # Pre-fill every day in the effective range as Absent (no record = unpaid)
    cur = effective_start
    while cur <= effective_end:
        day_map[cur] = "Absent"
        cur += timedelta(days=1)

    for a in attendance_records:
        att_date = getdate(a.attendance_date) if hasattr(a, "attendance_date") else None
        if not att_date:
            continue
        status = (a.status or "").strip()
        if status == "Half Day":
            fh = (a.custom_first_half or "").strip()
            sh = (a.custom_second_half or "").strip()
            day_map[att_date] = ("Half Day", fh, sh)
        else:
            day_map[att_date] = status

    return day_map


def _is_paid_day(day_status):
    """
    Returns True if the given day status is considered a paid working day
    for the purpose of sandwich rule evaluation.
    Weekly Off days return None (neutral/transparent — the check looks through them).
    Absent and LWP return False (break the sandwich).
    Half Day: paid if at least one half is a paid status.
    """
    if day_status is None:
        return None
    if isinstance(day_status, tuple) and day_status[0] == "Half Day":
        _, fh, sh = day_status
        fh_paid = fh in _PAID_STATUSES_FOR_SANDWICH
        sh_paid = sh in _PAID_STATUSES_FOR_SANDWICH
        # If at least one half is paid, the day is considered paid for sandwich purposes
        return fh_paid or sh_paid
    if day_status in ("Weekly Off",):
        return None  # transparent — look further
    if day_status in _PAID_STATUSES_FOR_SANDWICH:
        return True
    return False  # Absent, LWP, or unknown


def _find_nearest_working_day_status(day_map, from_date, direction, holiday_date_set, off_weekday):
    """
    Walk in the given direction (+1 = forward, -1 = backward) from from_date,
    skipping over Weekly Offs and other holidays (they are neutral for sandwich check).
    Returns True if the nearest actual working day is paid, False if unpaid,
    or True if no working day exists in the effective range (benefit of doubt
    for first/last day of the employee's service period).
    """
    cur = from_date + timedelta(days=direction)
    while cur in day_map:
        # Skip weekly off days (neutral — look through them)
        if off_weekday is not None and cur.weekday() == off_weekday:
            cur += timedelta(days=direction)
            continue
        # Skip other holidays in the block (they are also neutral during block evaluation)
        if cur in holiday_date_set:
            cur += timedelta(days=direction)
            continue
        status = day_map.get(cur)
        result = _is_paid_day(status)
        if result is None:
            # Another weekly off encountered — keep walking
            cur += timedelta(days=direction)
            continue
        return result
    # No working day found in effective range — benefit of doubt: treat as paid
    return True


def _calculate_eligible_holidays(holiday_date_set, day_map, off_weekday):
    """
    Apply the sandwich rule to each holiday (or consecutive holiday block) and
    return the count of holidays the employee is eligible to be paid for.

    Sandwich Rule:
    - Identify contiguous blocks of holidays (consecutive calendar dates that are holidays).
    - For each block, find the nearest paid working day before the block and after the block,
      skipping through Weekly Offs transparently.
    - If BOTH the preceding and following working days are paid → entire block is paid.
    - If EITHER is absent/LWP → entire block is unpaid.
    - If no working day exists on one or both sides (start/end of service) → benefit of doubt → paid.
    """
    if not holiday_date_set:
        return 0.0

    sorted_holidays = sorted(holiday_date_set)
    visited         = set()
    eligible_count  = 0.0

    for hdate in sorted_holidays:
        if hdate in visited:
            continue

        # Build the contiguous block starting from hdate
        block = [hdate]
        visited.add(hdate)
        nxt = hdate + timedelta(days=1)
        while nxt in holiday_date_set:
            block.append(nxt)
            visited.add(nxt)
            nxt += timedelta(days=1)

        block_start = block[0]
        block_end   = block[-1]

        # Check the working day immediately before the block (skipping weekly offs)
        before_paid = _find_nearest_working_day_status(
            day_map, block_start, direction=-1,
            holiday_date_set=holiday_date_set, off_weekday=off_weekday
        )

        # Check the working day immediately after the block (skipping weekly offs)
        after_paid = _find_nearest_working_day_status(
            day_map, block_end, direction=+1,
            holiday_date_set=holiday_date_set, off_weekday=off_weekday
        )

        # Both sides must be paid for the holiday block to be eligible
        if before_paid and after_paid:
            eligible_count += len(block)

    return flt(eligible_count, 2)


@frappe.whitelist()
def get_attendance_and_days(employee, start_date, working_days_calculation_method=None):
    start_date = getdate(start_date)
    month_end  = get_last_day(start_date)

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

    cl_data = frappe.db.get_value(
        "Company Link", employee,
        ["date_of_joining", "left_date"],
        as_dict=True
    ) or {}

    joining_date = getdate(cl_data.get("date_of_joining")) if cl_data.get("date_of_joining") else None
    left_date    = getdate(cl_data.get("left_date"))        if cl_data.get("left_date")        else None

    # Use the full calendar month as working-days denominator.
    # Days before joining / after left are marked Absent in attendance
    # (Mark Attendance), so payment_days shrinks — do not shrink working_days
    # from the joining date (that overstates pay for mid-month joiners).
    if joining_date and joining_date > month_end:
        return _empty_attendance_result(start_date, month_end, calculation_method)
    if left_date and left_date < start_date:
        return _empty_attendance_result(start_date, month_end, calculation_method)

    effective_start = start_date
    effective_end = month_end

    total_days = (effective_end - effective_start).days + 1

    weekly_off = frappe.db.get_value("Company Link", employee, "weekly_off")
    day_map_weekday = {
        "Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3,
        "Friday": 4, "Saturday": 5, "Sunday": 6,
    }
    off_weekday = day_map_weekday.get(weekly_off) if weekly_off else None

    total_weekly_off_days_full_month = 0
    if off_weekday is not None:
        cur = start_date
        while cur <= month_end:
            if cur.weekday() == off_weekday:
                total_weekly_off_days_full_month += 1
            cur += timedelta(days=1)

    weekly_off_count = 0
    if off_weekday is not None:
        cur = effective_start
        while cur <= effective_end:
            if cur.weekday() == off_weekday:
                weekly_off_count += 1
            cur += timedelta(days=1)

    company = frappe.db.get_value("Company Link", employee, "company")
    holiday_date_set = set()

    if company:
        from saral_hr.utils.holiday_utils import get_holiday_list_for_date
        holiday_list = get_holiday_list_for_date(effective_start, company)
        if holiday_list:
            holidays = frappe.db.get_all(
                "Holiday",
                filters={
                    "parent":       holiday_list,
                    "holiday_date": ["between", [effective_start, effective_end]],
                },
                pluck="holiday_date"
            )
            for h in holidays:
                holiday_date_set.add(getdate(h))

    holiday_count_in_range = len(holiday_date_set)

    # Remove holidays that fall on weekly off days (a day cannot be both)
    if off_weekday is not None:
        overlap = sum(1 for h in holiday_date_set if h.weekday() == off_weekday)
        weekly_off_count = max(weekly_off_count - overlap, 0)
        holiday_date_set = {h for h in holiday_date_set if h.weekday() != off_weekday}

    # Fetch attendance records
    attendance_records = frappe.db.get_all(
        "Attendance",
        filters={
            "employee":        employee,
            "attendance_date": ["between", [effective_start, effective_end]],
            "docstatus":       ["<", 2],
        },
        fields=["attendance_date", "status", "custom_first_half", "custom_second_half"]
    )

    # Build set of dates that have a REAL attendance record
    dates_with_real_attendance = {getdate(a.attendance_date) for a in attendance_records}

    # ── Build per-day status map for sandwich rule evaluation ─────────────────
    day_map = _build_day_status_map(attendance_records, effective_start, effective_end)

    # Mark holiday dates in the day_map so the sandwich walker can skip them.
    # Only mark as "Holiday" if there is NO real attendance record for this date.
    # If the employee has a real attendance status on a holiday date, keep it.
    for hdate in holiday_date_set:
        if hdate not in dates_with_real_attendance:
            day_map[hdate] = "Holiday"
        # else: real attendance exists — keep it as-is in day_map

    # Mark weekly off dates in the day_map so the sandwich walker can skip them
    if off_weekday is not None:
        cur = effective_start
        while cur <= effective_end:
            if cur.weekday() == off_weekday:
                day_map[cur] = "Weekly Off"
            cur += timedelta(days=1)

    present_days      = 0.0
    on_tour           = 0.0
    earned_comp_off   = 0.0
    earned_leave      = 0.0
    casual_leave      = 0.0
    comp_off          = 0.0
    absent_days       = 0.0
    lwp_days          = 0.0
    half_day_count    = 0
    weekly_offs_taken = 0
    holidays_taken    = 0.0   # ← NEW: count of "Holiday" status records in attendance

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
        elif status == "Weekly Off":       weekly_offs_taken += 1
        elif status == "Holiday":          holidays_taken  += 1.0   # ← NEW
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

    # ── Apply sandwich rule ONLY to holidays with no real attendance record ────
    # Holidays where the employee was marked with a real status (Present, Holiday,
    # Absent, etc.) are already handled above. Only unattended holidays go through
    # the sandwich rule to decide if they are eligible as paid days.
    holidays_no_attendance   = {h for h in holiday_date_set if h not in dates_with_real_attendance}
    holidays_with_attendance = holiday_date_set - holidays_no_attendance

    eligible_holidays   = _calculate_eligible_holidays(holidays_no_attendance, day_map, off_weekday)
    ineligible_holidays = (holiday_count_in_range - len(holidays_with_attendance)) - eligible_holidays

    # ── Working Days: contractual denominator for proration (unchanged) ───────
    if calculation_method == "Include Weekly Offs":
        working_days = total_days
    else:
        working_days = max(total_days - weekly_off_count, 0)

    # ── Payment Days ──────────────────────────────────────────────────────────
    # = present + on_tour + leaves + comp_off
    #   + holidays_taken (explicitly marked Holiday in attendance)
    #   + eligible_holidays (sandwich-rule approved unattended holidays)
    payment_days = flt(
    present_days + on_tour +
    earned_leave + casual_leave + comp_off +
    holidays_taken +           
    eligible_holidays +
    (weekly_offs_taken if calculation_method == "Include Weekly Offs" else 0),
    2
)
    payment_days = max(payment_days, 0.0)

    # ── Physical Working Days ─────────────────────────────────────────────────
    physical_working_days = flt(payment_days - earned_leave - casual_leave - comp_off, 2)
    if physical_working_days < 0:
        physical_working_days = 0.0

    total_unpaid = flt(absent_days + lwp_days + ineligible_holidays, 2)

    return {
        "attendance_count":           len(attendance_records),
        "total_days":                 total_days,
        "total_weekly_off_days":      total_weekly_off_days_full_month,
        "weekly_offs_taken":          weekly_offs_taken,
        "weekly_offs":                weekly_off_count,
        "total_holidays":             holiday_count_in_range,
        "holidays_taken":             flt(holidays_taken, 2),          # ← NEW
        "eligible_holidays":          eligible_holidays,
        "ineligible_holidays":        ineligible_holidays,
        "working_days":               flt(working_days, 2),
        "payment_days":               flt(payment_days, 2),
        "physical_working_days":      flt(physical_working_days, 2),
        "present_days":               flt(present_days, 2),
        "absent_days":                flt(absent_days, 2),
        "total_half_days":            flt(half_day_count * 0.5, 2),
        "total_lwp":                  flt(lwp_days, 2),
        "total_earned_leaves":        flt(earned_leave, 2),
        "total_casual_leaves":        flt(casual_leave, 2),
        "total_on_tour":              flt(on_tour, 2),
        "total_comp_off":             flt(comp_off, 2),
        "total_earned_comp_off":      flt(earned_comp_off, 2),
        "total_unpaid_days":          flt(total_unpaid, 2),
        "calculation_method":         calculation_method,
    }
def _empty_attendance_result(start_date, month_end, calculation_method="Exclude Weekly Offs"):
    total_days = (month_end - start_date).days + 1
    return {
        "attendance_count":      0,
        "total_days":            total_days,
        "total_weekly_off_days": 0,
        "weekly_offs_taken":     0,
        "weekly_offs":           0,
        "total_holidays":        0,
        "holidays_taken":        0,   # ← ADD THIS
        "eligible_holidays":     0,
        "ineligible_holidays":   0,
        "working_days":          0,
        "payment_days":          0,
        "physical_working_days": 0,
        "present_days":          0,
        "absent_days":           0,
        "total_half_days":       0,
        "total_lwp":             0,
        "total_earned_leaves":   0,
        "total_casual_leaves":   0,
        "total_on_tour":         0,
        "total_comp_off":        0,
        "total_earned_comp_off": 0,
        "total_unpaid_days":     0,
        "calculation_method":    calculation_method,
    }

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
            loan_advance_rows = get_loan_advance_deductions(employee, start_date)

            ss = frappe.new_doc("Salary Slip")
            ss.employee = employee; ss.start_date = start_date
            ss.end_date = get_last_day(getdate(start_date)); ss.currency = "INR"
            ss.company = company_name
            ss.salary_structure = sd.get('salary_structure'); ss.working_days_calculation_method = wdcm

            ss.month_days              = att.get('total_days', 0)
            ss.total_weekly_off_days   = att.get('total_weekly_off_days', 0)
            ss.weekly_offs_taken       = att.get('weekly_offs_taken', 0)
            ss.total_working_days      = att.get('working_days')
            ss.payment_days            = att.get('payment_days')
            ss.physical_working_days   = att.get('physical_working_days')
            ss.present_days            = att.get('present_days')
            ss.absent_days             = att.get('absent_days')
            ss.weekly_offs_count       = att.get('weekly_offs')
            ss.total_half_days         = att.get('total_half_days')
            ss.total_lwp               = att.get('total_lwp', 0)
            ss.total_holidays          = att.get('total_holidays', 0)
            ss.total_earned_leaves     = att.get('total_earned_leaves', 0)
            ss.total_casual_leaves     = att.get('total_casual_leaves', 0)
            ss.total_on_tour           = att.get('total_on_tour', 0)
            ss.total_comp_off          = att.get('total_comp_off', 0)
            ss.total_earned_comp_off   = att.get('total_earned_comp_off', 0)
            ss.total_unpaid_days       = att.get('total_unpaid_days', 0)

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

            for item in loan_advance_rows:
                row = ss.append('deductions', {})
                row.salary_component                 = item.get('salary_component')
                row.abbr                             = item.get('abbr', '')
                row.amount                           = flt(item.get('amount'))
                row.base_amount                      = flt(item.get('amount'))
                row.employer_contribution            = 0
                row.depends_on_payment_days          = 0
                row.depends_on_physical_working_days = 0
                row.is_deferred                      = int(item.get('is_deferred') or 0)

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
            pdf = frappe.get_print(doctype="Salary Slip", name=name, print_format=BULK_PRINT_FORMAT, as_pdf=True, letterhead=None, pdf_options={"load-error-handling": "ignore", "load-media-error-handling": "ignore"})
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