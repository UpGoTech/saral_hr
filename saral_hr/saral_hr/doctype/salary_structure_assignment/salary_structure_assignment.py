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

# Exact component names — must match Salary Component records
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

    def on_submit(self):
        _check_overlap(
            employee=self.employee,
            from_date=self.from_date,
            to_date=self.to_date,
            employee_name=self.employee_name,
            current_name=self.name,
            throw_if_overlap=True,
        )

    def on_cancel(self):
        pass


# ─────────────────────────────────────────────────────────────
#  Statutory computation — called from JS
# ─────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_statutory_components(company, gross_salary, from_date,
                              is_esic_applicable=0, is_pf_applicable=0,
                              pf_type=None, is_pt_applicable=0,
                              is_lwf_applicable=0,
                              earnings_map=None):
    """
    Compute statutory deduction and employer-share amounts from Company config.

    Parameters
    ----------
    company             : Company name
    gross_salary        : Total gross (sum of all earnings rows) — used as
                          fallback when a component name in the wage-basis
                          config is not found in earnings_map.
    from_date           : Pay-period start (YYYY-MM-DD) — used for PT month.
    is_esic_applicable  : 1/0
    is_pf_applicable    : 1/0
    pf_type             : "Limited PF" | "Full PF" | ""
    is_pt_applicable    : 1/0
    is_lwf_applicable   : 1/0
    earnings_map        : JSON string or dict of {component_name: amount}
                          for every earning row in the SSA.  When supplied,
                          each component's actual amount is used for wage-basis
                          resolution instead of gross_salary as a proxy.
    """
    import json as _json

    gross_salary       = flt(gross_salary)
    is_esic_applicable = int(is_esic_applicable or 0)
    is_pf_applicable   = int(is_pf_applicable   or 0)
    is_pt_applicable   = int(is_pt_applicable   or 0)
    is_lwf_applicable  = int(is_lwf_applicable  or 0)

    # Parse earnings_map if sent as JSON string from JS
    if isinstance(earnings_map, str):
        try:
            earnings_map = _json.loads(earnings_map)
        except Exception:
            earnings_map = {}
    earnings_map = earnings_map or {}

    deductions     = []
    employer_share = []

    comp_doc = frappe.get_doc("Company", company) if company else None

    def abbr(name):
        return frappe.db.get_value("Salary Component", name, "salary_component_abbr") or ""

    def row(name, amount, employer=0):
        return {
            "salary_component":      name,
            "abbr":                  abbr(name),
            "amount":                flt(amount, 2),
            "employer_contribution": employer,
        }

    # ── ESIC ─────────────────────────────────────────────────
    # Wage basis = first component MINUS remaining components
    # (defined in Company → ESIC Wage Components table).
    # Example: [Gross, HRA, Conveyance] → Gross − HRA − Conveyance
    # Result is capped at esic_wage_limit (display/reference purpose on Company).
    # Applicability is controlled solely by is_esic_applicable on SSA.
    if is_esic_applicable and comp_doc:
        esic_cfg = comp_doc.get_esic_config()
        if esic_cfg:
            salary_map = _build_salary_map(
                comp_doc, "esic_dependent_component", gross_salary, earnings_map
            )
            wage     = comp_doc.compute_esic_wage_basis(salary_map)
            emp_pct  = flt(esic_cfg.get("employee_percent", 0))
            empr_pct = flt(esic_cfg.get("employer_percent", 0))

            if emp_pct:
                deductions.append(row(SC_EMP_ESIC, wage * emp_pct / 100))
            if empr_pct:
                employer_share.append(row(SC_EMPR_ESIC, wage * empr_pct / 100, employer=1))

    # ── PF ───────────────────────────────────────────────────
    # Wage basis = SUM of all listed components
    # (defined in Company → PF Wage Components table).
    # Example: [Basic, DA] → Basic + DA
    #
    # Limited PF: wage is capped at pf_wage_limit from Company.
    #   e.g. Basic+DA = 16000, limit = 15000 → PF calculated on 15000
    #   e.g. Basic+DA = 12000, limit = 15000 → PF calculated on 12000 (less than limit)
    #
    # Full PF: no cap — all percentages applied to full computed wage basis.
    if is_pf_applicable and comp_doc:
        pf_cfg = comp_doc.get_pf_config()
        if pf_cfg:
            salary_map = _build_salary_map(
                comp_doc, "pf_dependent_component", gross_salary, earnings_map
            )

            # Compute raw wage basis (sum of all components, no cap yet)
            pf_components = comp_doc._get_child_components("pf_dependent_component")
            raw_wage = max(
                sum(comp_doc._resolve_component_value(c, salary_map) for c in pf_components),
                0.0
            )

            # Apply Limited PF cap only when pf_type is explicitly "Limited PF"
            if pf_type == "Limited PF" and pf_cfg.get("wage_limit"):
                wage = min(raw_wage, flt(pf_cfg["wage_limit"]))
            else:
                # Full PF — use the full raw wage, ignore pf_wage_limit
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

    # ── PT ───────────────────────────────────────────────────
    # PT amount is month-specific — Feb = ₹300, all others = ₹200.
    # Amounts are read from the Professional Tax Special Salary Component.
    if is_pt_applicable and from_date:
        month_name = MONTHS[getdate(from_date).month - 1]
        pt_amt     = _special_component_amount(SC_PT, month_name)
        deductions.append(row(SC_PT, pt_amt))

    # ── LWF ──────────────────────────────────────────────────
    # LWF is a fixed constant amount (same every applicable month).
    # Most common non-zero value is used across all 12 months.
    if is_lwf_applicable:
        emp_lwf_amt  = _special_component_constant_amount(SC_EMP_LWF)
        empr_lwf_amt = _special_component_constant_amount(SC_EMPR_LWF)
        deductions.append(row(SC_EMP_LWF,  emp_lwf_amt))
        employer_share.append(row(SC_EMPR_LWF, empr_lwf_amt, employer=1))

    return {"deductions": deductions, "employer_share": employer_share}


def _build_salary_map(comp_doc, table_fieldname, gross_salary, earnings_map):
    """
    Build the salary_components dict that Company._resolve_component_value
    uses to resolve wage-basis component values.

    Resolution priority for each component in the wage-basis config:

    1. Virtual components ("Gross", "Gross Including Additional Salary"):
       Always injected as gross_salary — these are computed from all earnings.

    2. Real components present in earnings_map (actual SSA earnings rows
       sent from JS as {salary_component: amount}):
       Use the exact amount from the SSA form.

    3. Real components NOT in earnings_map:
       Fall back to gross_salary as a best-effort approximation.

    Examples
    --------
    Company ESIC config: [Gross, HRA, Conveyance Allowance]
    SSA earnings: {Basic: 10000, HRA: 4000, Conveyance Allowance: 800, ...}
    → salary_map = {Gross: 22000, HRA: 4000, Conveyance Allowance: 800}
    → ESIC wage = 22000 − 4000 − 800 = 17200, capped at esic_wage_limit

    Company PF config: [Basic, Dearness Allowance]
    SSA earnings: {Basic: 10000, Dearness Allowance: 2000, HRA: 4000, ...}
    → salary_map = {Basic: 10000, Dearness Allowance: 2000}
    → PF wage = 10000 + 2000 = 12000
    """
    VIRTUAL = {"Gross", "Gross Including Additional Salary"}

    rows       = comp_doc.get(table_fieldname) or []
    components = [r.wage_components for r in rows if r.wage_components]

    salary_map = {
        "Gross":                              flt(gross_salary),
        "Gross Including Additional Salary":  flt(gross_salary),
    }

    for comp in components:
        if comp in VIRTUAL:
            continue  # already injected above
        if comp in earnings_map:
            salary_map[comp] = flt(earnings_map[comp])
        else:
            # Component listed in Company config but not in SSA earnings
            salary_map[comp] = flt(gross_salary)

    return salary_map


def _special_component_amount(component_name, month_name):
    """Read monthly amount from a Special Salary Component."""
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
    """Return the most common non-zero amount across all months (for LWF)."""
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


# ─────────────────────────────────────────────────────────────
#  Overlap helpers
# ─────────────────────────────────────────────────────────────

@frappe.whitelist()
def check_overlap(employee, from_date, to_date=None, employee_name=None,
                  current_name=None, throw_if_overlap=False):
    return _check_overlap(
        employee=employee, from_date=from_date, to_date=to_date,
        employee_name=employee_name, current_name=current_name,
        throw_if_overlap=throw_if_overlap, submitted_only=False,
    )


def _check_overlap(employee, from_date, to_date=None, employee_name=None,
                   current_name=None, throw_if_overlap=False, submitted_only=False):
    if not employee or not from_date:
        return None

    filters = {"employee": employee, "docstatus": 1 if submitted_only else ["!=", 2]}
    if current_name:
        filters["name"] = ["!=", current_name]

    records = frappe.db.get_all(
        "Salary Structure Assignment",
        filters=filters,
        fields=["name", "from_date", "to_date"],
    )

    a_start = getdate(from_date)
    a_end   = getdate(to_date) if to_date else None

    for rec in records:
        b_start = getdate(rec.from_date)
        b_end   = getdate(rec.to_date) if rec.to_date else FAR_FUTURE

        if (b_start <= a_start <= b_end) or (a_end and b_start <= a_end <= b_end):
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