# Copyright (c) 2026, sj and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate
from datetime import date

FAR_FUTURE = date(9999, 12, 31)

MONTHS = [
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


class SalaryStructureAssignment(Document):

    def before_save(self):
        if self.docstatus == 1:
            return
        self.status = "Draft"
        # amended_from set hai matlab yeh amend ka draft hai
        # cancelled original se overlap hoga — sirf submitted check karo
        submitted_only = bool(self.amended_from)
        _check_overlap(
            employee=self.employee,
            from_date=self.from_date,
            to_date=self.to_date,
            employee_name=self.employee_name,
            current_name=self.name,
            throw_if_overlap=True,
            submitted_only=submitted_only,
        )

    def on_update_after_submit(self):
        # amend ke baad submitted doc mein date edit — overlap check nahi karna
        # (original cancel ho chuka hai, us period pe koi submitted record nahi hoga)
        # sirf SRR check Python side pe nahi hota — JS check_srr_and_apply_validate_only handle karta hai
        pass

    def on_submit(self):
        self.status = "Submitted"
        self.db_set("status", "Submitted")
        # ── CHANGED: check only against other submitted SSAs on submit ──
        _check_overlap(
            employee=self.employee,
            from_date=self.from_date,
            to_date=self.to_date,
            employee_name=self.employee_name,
            current_name=self.name,
            throw_if_overlap=True,
            submitted_only=True,
        )

    def on_cancel(self):
        self.status = "Cancelled"
        self.db_set("status", "Cancelled")


@frappe.whitelist()
def get_statutory_components(company, gross_salary, from_date,
                              is_esic_applicable=0, is_pf_applicable=0,
                              pf_type=None, is_pt_applicable=0,
                              is_lwf_applicable=0,
                              earnings_map=None):
    import json as _json

    gross_salary       = flt(gross_salary)
    is_esic_applicable = int(is_esic_applicable or 0)
    is_pf_applicable   = int(is_pf_applicable   or 0)
    is_pt_applicable   = int(is_pt_applicable   or 0)
    is_lwf_applicable  = int(is_lwf_applicable  or 0)

    if isinstance(earnings_map, str):
        try:
            earnings_map = _json.loads(earnings_map)
        except Exception:
            earnings_map = {}
    earnings_map = earnings_map or {}

    deductions     = []
    employer_share = []

    comp_doc    = frappe.get_doc("Company", company) if company else None
    period_date = getdate(from_date) if from_date else None

    def abbr(name):
        return frappe.db.get_value("Salary Component", name, "salary_component_abbr") or ""

    def row(name, amount, employer=0):
        exclude = frappe.db.get_value("Salary Component", name, "exclude_from_ctc") or 0
        return {
            "salary_component":      name,
            "abbr":                  abbr(name),
            "amount":                flt(amount, 2),
            "employer_contribution": employer,
            "exclude_from_ctc":      int(exclude),
        }

    # ── ESIC ──
    if is_esic_applicable and comp_doc:
        esic_cfg = comp_doc.get_esic_config(period_date=period_date)
        if esic_cfg:
            esic_components = esic_cfg.get("wage_components", [])
            wage     = _sum_components(esic_components, gross_salary, earnings_map)
            emp_pct  = flt(esic_cfg.get("employee_percent", 0))
            empr_pct = flt(esic_cfg.get("employer_percent", 0))
            if emp_pct:
                deductions.append(row(SC_EMP_ESIC, wage * emp_pct / 100))
            if empr_pct:
                employer_share.append(row(SC_EMPR_ESIC, wage * empr_pct / 100, employer=1))

    # ── PF ──
    if is_pf_applicable and comp_doc:
        pf_cfg = comp_doc.get_pf_config(period_date=period_date)
        if pf_cfg:
            pf_components = pf_cfg.get("wage_components", [])
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

    # ── PT ──
    if is_pt_applicable and from_date:
        month_name = MONTHS[getdate(from_date).month - 1]
        pt_amt     = _special_component_amount(SC_PT, month_name)
        deductions.append(row(SC_PT, pt_amt))

    # ── LWF ──
    if is_lwf_applicable:
        deductions.append(row(SC_EMP_LWF,  _special_component_constant_amount(SC_EMP_LWF)))
        employer_share.append(row(SC_EMPR_LWF, _special_component_constant_amount(SC_EMPR_LWF), employer=1))

    return {"deductions": deductions, "employer_share": employer_share}


def _sum_components(components, gross_salary, earnings_map):
    VIRTUAL     = {"Gross", "Gross Including Additional Salary"}
    total       = 0.0
    matched_any = False

    for comp in components:
        if comp in VIRTUAL:
            total += flt(gross_salary)
            matched_any = True
        elif comp in earnings_map:
            total += flt(earnings_map[comp])
            matched_any = True

    return flt(gross_salary) if not matched_any else max(total, 0.0)


def _special_component_amount(component_name, month_name):
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


def _special_component_constant_amount(component_name):
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


@frappe.whitelist()
def get_srr_for_ssa(start_date, skill_type):
    MONTH_NUM = {
        "January": 1, "February": 2, "March": 3,  "April": 4,
        "May": 5,     "June": 6,     "July": 7,    "August": 8,
        "September": 9, "October": 10, "November": 11, "December": 12,
    }
    SKILL_FIELD_MAP = {
        "Skilled":      ("vbasic_skilled",     "vda_skilled"),
        "Semi-skilled": ("vbasic_semi_skilled", "vda_semi_skilled"),
        "Unskilled":    ("vbasic_unskilled",    "vda_unskilled"),
    }
    fields = SKILL_FIELD_MAP.get(skill_type)
    if not fields:
        return None

    vbasic_field, vda_field = fields
    d      = getdate(start_date)
    target = d.year * 100 + MONTH_NUM[MONTHS[d.month - 1]]

    for r in frappe.db.get_all("Skill Rate Revision",
            filters={"docstatus": 1},
            fields=["from_month", "from_year", "to_month", "to_year", vbasic_field, vda_field]):
        if not all([r.from_month, r.from_year, r.to_month, r.to_year]):
            continue
        if int(r.from_year)*100 + MONTH_NUM[r.from_month] <= target <= int(r.to_year)*100 + MONTH_NUM[r.to_month]:
            return {"vbasic": flt(r[vbasic_field], 2), "vda": flt(r[vda_field], 2)}
    return None


@frappe.whitelist()
def get_daily_wage_multiplier(start_date, skill_type):
    MONTH_NUM = {
        "January": 1, "February": 2, "March": 3,  "April": 4,
        "May": 5,     "June": 6,     "July": 7,    "August": 8,
        "September": 9, "October": 10, "November": 11, "December": 12,
    }
    d      = getdate(start_date)
    target = d.year * 100 + MONTH_NUM[MONTHS[d.month - 1]]

    for r in frappe.db.get_all("Skill Rate Revision",
            filters={"docstatus": 1},
            fields=["from_month", "from_year", "to_month", "to_year", "daily_wage_multiplier"]):
        if not all([r.from_month, r.from_year, r.to_month, r.to_year]):
            continue
        if int(r.from_year)*100 + MONTH_NUM[r.from_month] <= target <= int(r.to_year)*100 + MONTH_NUM[r.to_month]:
            return {"multiplier": flt(r.daily_wage_multiplier) or 26}
    return {"multiplier": 26}


@frappe.whitelist()
def check_overlap(employee, from_date, to_date=None, employee_name=None,
                  current_name=None, throw_if_overlap=False):
    # ── CHANGED: always check submitted only — drafts should not block new drafts ──
    return _check_overlap(
        employee=employee, from_date=from_date, to_date=to_date,
        employee_name=employee_name, current_name=current_name,
        throw_if_overlap=throw_if_overlap, submitted_only=True,
    )


def _check_overlap(employee, from_date, to_date=None, employee_name=None,
                   current_name=None, throw_if_overlap=False, submitted_only=False):
    if not employee or not from_date:
        return None

    # submitted_only=True → only submitted; False → Draft+Submitted+Cancelled (all)
    filters = {
        "employee": employee,
        "docstatus": 1 if submitted_only else ["in", [0, 1, 2]],
    }
    if current_name:
        filters["name"] = ["!=", current_name]

    a_start = getdate(from_date)
    a_end   = getdate(to_date) if to_date else FAR_FUTURE

    for rec in frappe.db.get_all("Salary Structure Assignment",
            filters=filters, fields=["name", "from_date", "to_date"]):
        b_start = getdate(rec.from_date)
        b_end   = getdate(rec.to_date) if rec.to_date else FAR_FUTURE

        # overlap: the two ranges intersect
        if a_start <= b_end and b_start <= a_end:
            if throw_if_overlap:
                frappe.throw(
                    title=_("Duplicate Salary Structure Assignment"),
                    msg=(
                        f"A Salary Structure Assignment already exists for "
                        f"<b>{employee_name or employee}</b> overlapping the selected period.<br><br>"
                        f"Existing: <a href='/app/salary-structure-assignment/{rec.name}' target='_blank'>"
                        f"<b>{rec.name}</b></a> &nbsp;|&nbsp; "
                        f"<b>{rec.from_date}</b> to <b>{rec.to_date or 'Ongoing'}</b>"
                    ),
                    exc=frappe.DuplicateEntryError,
                )
            else:
                return {
                    "name":      rec.name,
                    "from_date": str(rec.from_date),
                    "to_date":   str(rec.to_date) if rec.to_date else None,
                }
    return None


@frappe.whitelist()
def get_existing_assignments(employee):
    if not employee:
        return []
    return frappe.db.get_all(
        "Salary Structure Assignment",
        filters={"employee": employee, "docstatus": ["!=", 2]},
        fields=["name", "from_date", "to_date", "docstatus"],
        order_by="from_date desc",
    )