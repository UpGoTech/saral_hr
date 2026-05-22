import frappe
import math
from frappe.utils import flt
from decimal import Decimal, ROUND_HALF_UP


def _round2(value):
    return float(Decimal(str(flt(value, 4))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _round0(value):
    return int(Decimal(str(flt(value, 2))).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


# ─── Constants ────────────────────────────────────────────────────────────────

PF_WAGE_CAP    = 15000.0
GRATUITY_RATE  = 4.81  / 100
RETENTION_RATE = 2.00  / 100
ERPF_RATE      = 3.67  / 100
EPS_RATE       = 8.33  / 100
EDLI_RATE      = 0.50  / 100
PF_ADMIN_RATE  = 0.50  / 100
EMP_PF_RATE    = 12.00 / 100
PT_NORMAL      = 200.0
PT_FEBRUARY    = 300.0

STATUTORY_NAMES = {
    "Employee ESIC", "Employer ESIC",
    "Employee PF", "Employer PF", "Employer PF (ERPF)",
    "Employer EPS", "Employer EDLI",
    "Employer PF Admin Charges", "PF Admin Charges",
    "Professional Tax",
    "Employee Labour Welfare Fund", "Employer Labour Welfare Fund",
    "Gratuity",
    "Employer Gratuity",
}

EARNING_FORMULAS = {
    "basic":                lambda mc, b, da, bda, g: _round2(0.60 * mc - 6000.0),
    "dearness allowance":   lambda mc, b, da, bda, g: 6000.0,
    "da":                   lambda mc, b, da, bda, g: 6000.0,
    "house rent allowance": lambda mc, b, da, bda, g: _round2(0.125 * bda),
    "hra":                  lambda mc, b, da, bda, g: _round2(0.125 * bda),
    "conveyance allowance": lambda mc, b, da, bda, g: 1600.0,
    "conv":                 lambda mc, b, da, bda, g: 1600.0,
    "medical allowance":    lambda mc, b, da, bda, g: 1250.0,
    "med":                  lambda mc, b, da, bda, g: 1250.0,
    "education allowance":  lambda mc, b, da, bda, g: 200.0,
    "edu":                  lambda mc, b, da, bda, g: 200.0,
    "variable pay":         lambda mc, b, da, bda, g: _round2(0.075 * mc),
    "var":                  lambda mc, b, da, bda, g: _round2(0.075 * mc),
    "variable":             lambda mc, b, da, bda, g: _round2(0.075 * mc),
}

DEDUCTION_FORMULAS = {
    "retention": lambda mc, b, da, bda, g: _round2(bda * RETENTION_RATE),
    "ret":       lambda mc, b, da, bda, g: _round2(bda * RETENTION_RATE),
}

REMAINDER_KEYWORDS = ["other allowance", "others", "other", "oa", "remainder", "balance"]


# ─── 1. Get companies ─────────────────────────────────────────────────────────

@frappe.whitelist()
def get_companies():
    companies = frappe.db.get_all("Company", fields=["name"], order_by="name asc")
    return [c.name for c in companies]


# ─── 2. Get salary structures for a company ───────────────────────────────────

@frappe.whitelist()
def get_salary_structures(company):
    if not company:
        frappe.throw("Company is required")

    rows = frappe.db.sql("""
        SELECT name
        FROM `tabSalary Structure`
        WHERE company   = %(company)s
          AND is_active = 'Yes'
          AND docstatus != 2
        ORDER BY name ASC
    """, {"company": company}, as_dict=True)

    return [r.name for r in rows]


# ─── 3. Company statutory settings ───────────────────────────────────────────

def _get_company_statutory(company):
    try:
        comp = frappe.get_doc("Company", company)
    except Exception:
        return {}

    esic_emp_pct  = 0.0
    esic_empr_pct = 0.0

    if hasattr(comp, "get_esic_config"):
        try:
            cfg = comp.get_esic_config()
            if cfg:
                esic_emp_pct  = flt(cfg.get("employee_percent", 0))
                esic_empr_pct = flt(cfg.get("employer_percent", 0))
        except Exception:
            pass

    if not esic_emp_pct:
        esic_emp_pct = flt(
            getattr(comp, "esic_employee_contribution", 0) or
            getattr(comp, "employee_esic_percent", 0) or
            getattr(comp, "esic_emp_pct", 0) or 0.75
        )
    if not esic_empr_pct:
        esic_empr_pct = flt(
            getattr(comp, "esic_employer_contribution", 0) or
            getattr(comp, "employer_esic_percent", 0) or
            getattr(comp, "esic_empr_pct", 0) or 3.25
        )

    def _flag(attr):
        return int(bool(getattr(comp, attr, 0) or 0))

    return {
        "is_pf_applicable":   _flag("is_pf_applicable"),
        "is_esic_applicable": _flag("is_esic_applicable"),
        "is_pt_applicable":   _flag("is_pt_applicable"),
        "is_lwf_applicable":  _flag("is_lwf_applicable"),
        "esic_emp_pct":       esic_emp_pct,
        "esic_empr_pct":      esic_empr_pct,
    }


# ─── 4. Get component abbreviation ───────────────────────────────────────────

def _get_abbr(comp_name):
    return frappe.db.get_value(
        "Salary Component", comp_name, "salary_component_abbr"
    ) or comp_name


# ─── 5. Resolve formula for a component ──────────────────────────────────────

def _resolve_earning_formula(comp_name, abbr):
    key_name = (comp_name or "").lower().strip()
    key_abbr = (abbr or "").lower().strip()
    return EARNING_FORMULAS.get(key_name) or EARNING_FORMULAS.get(key_abbr)

def _resolve_deduction_formula(comp_name, abbr):
    key_name = (comp_name or "").lower().strip()
    key_abbr = (abbr or "").lower().strip()
    return DEDUCTION_FORMULAS.get(key_name) or DEDUCTION_FORMULAS.get(key_abbr)

def _is_remainder(comp_name, abbr):
    key_name = (comp_name or "").lower().strip()
    key_abbr = (abbr or "").lower().strip()
    return any(k in key_name for k in REMAINDER_KEYWORDS) or \
           any(k == key_abbr  for k in REMAINDER_KEYWORDS)


# ─── 6. Load structure component list ────────────────────────────────────────

def _load_structure_components(salary_structure):
    ss = frappe.get_doc("Salary Structure", salary_structure)

    earning_rows  = []
    has_remainder = False
    remainder_name = "Others"
    remainder_abbr = "OTH"

    for r in (ss.earnings or []):
        comp_name = r.salary_component or ""
        abbr      = _get_abbr(comp_name)

        if comp_name in STATUTORY_NAMES:
            continue

        if _is_remainder(comp_name, abbr):
            has_remainder  = True
            remainder_name = comp_name
            remainder_abbr = abbr
            continue

        earning_rows.append({
            "salary_component": comp_name,
            "abbr":             abbr,
            "is_variable":      "variable" in comp_name.lower() or "var" in abbr.lower(),
        })

    deduction_rows = []
    for r in (ss.deductions or []):
        comp_name = r.salary_component or ""
        abbr      = _get_abbr(comp_name)

        if comp_name in STATUTORY_NAMES:
            continue

        deduction_rows.append({
            "salary_component": comp_name,
            "abbr":             abbr,
        })

    return {
        "salary_structure": ss.name,
        "company":          ss.company,
        "earning_rows":     earning_rows,
        "deduction_rows":   deduction_rows,
        "has_remainder":    has_remainder,
        "remainder_name":   remainder_name,
        "remainder_abbr":   remainder_abbr,
    }


# ─── 7. Main CTC breakdown API ───────────────────────────────────────────────

@frappe.whitelist()
def calculate_ctc_breakdown(company, salary_structure, annual_ctc, month=None,
                            include_pf=None, include_esic=None, include_pt=None):
    if not company or not salary_structure or not annual_ctc:
        frappe.throw("Company, Salary Structure and Annual CTC are required")

    annual_ctc  = flt(annual_ctc)
    monthly_ctc = _round2(annual_ctc / 12)
    month_name  = month or "January"
    is_february = (month_name == "February")

    # ── Statutory flags ───────────────────────────────────────────────────────
    company_stat = _get_company_statutory(company)

    override_pf   = frappe.utils.cint(include_pf)   if include_pf   not in (None, "") else None
    override_esic = frappe.utils.cint(include_esic) if include_esic not in (None, "") else None
    override_pt   = frappe.utils.cint(include_pt)   if include_pt   not in (None, "") else None

    is_pf   = override_pf   if override_pf   is not None else company_stat.get("is_pf_applicable",   0)
    is_esic = override_esic if override_esic is not None else company_stat.get("is_esic_applicable",  0)
    is_pt   = override_pt   if override_pt   is not None else company_stat.get("is_pt_applicable",    0)
    is_lwf  = company_stat.get("is_lwf_applicable", 0)

    esic_emp_pct  = company_stat.get("esic_emp_pct",  0.75)
    esic_empr_pct = company_stat.get("esic_empr_pct", 3.25)

    # ── Load structure component list ─────────────────────────────────────────
    struct = _load_structure_components(salary_structure)

    # ── Iterative gross resolution ────────────────────────────────────────────
    def _calc_basic_da(mc):
        basic = _round2(0.60 * mc - 6000.0)
        da    = 6000.0
        return basic, da, _round2(basic + da)

    for _ in range(5):
        basic_e, da_e, basic_da_e = _calc_basic_da(monthly_ctc)
        pf_wage_e  = min(basic_da_e, PF_WAGE_CAP) if is_pf else 0.0
        gratuity_e = _round2(basic_da_e * GRATUITY_RATE)
        erpf_e     = _round2(pf_wage_e  * ERPF_RATE) if is_pf else 0.0
        eps_e      = _round2(pf_wage_e  * EPS_RATE)  if is_pf else 0.0
        gross_est  = _round2(monthly_ctc - (gratuity_e + erpf_e + eps_e))

    gross    = gross_est
    basic, da, basic_da = _calc_basic_da(monthly_ctc)
    pf_wage  = min(basic_da, PF_WAGE_CAP) if is_pf else 0.0
    gratuity = _round2(basic_da * GRATUITY_RATE)
    erpf     = _round2(pf_wage  * ERPF_RATE)     if is_pf else 0.0
    eps      = _round2(pf_wage  * EPS_RATE)      if is_pf else 0.0
    edli     = _round2(pf_wage  * EDLI_RATE)     if is_pf else 0.0
    pf_admin = _round2(pf_wage  * PF_ADMIN_RATE) if is_pf else 0.0

    # ── Earnings ──────────────────────────────────────────────────────────────
    earnings_out = []
    fixed_total  = 0.0

    for row in struct["earning_rows"]:
        formula = _resolve_earning_formula(row["salary_component"], row["abbr"])
        amount  = formula(monthly_ctc, basic, da, basic_da, gross) if formula else 0.0
        earnings_out.append({
            "salary_component": row["salary_component"],
            "abbr":             row["abbr"],
            "amount":           amount,
            "is_variable":      row["is_variable"],
        })
        fixed_total = _round2(fixed_total + amount)

    others_amount = _round2(max(gross - fixed_total, 0.0))
    if struct["has_remainder"] or others_amount > 0:
        earnings_out.append({
            "salary_component": struct["remainder_name"],
            "abbr":             struct["remainder_abbr"],
            "amount":           others_amount,
            "is_variable":      False,
            "is_others":        True,
        })

    total_gross = _round2(sum(e["amount"] for e in earnings_out))

    # ── Employee deductions ───────────────────────────────────────────────────
    emp_pf       = _round2(pf_wage * EMP_PF_RATE)            if is_pf   else 0.0
    esic_emp_amt = _round2(total_gross * esic_emp_pct / 100) if is_esic else 0.0
    pt_amount    = (PT_FEBRUARY if is_february else PT_NORMAL) if is_pt  else 0.0

    deductions_out = []

    if is_pf and emp_pf:
        deductions_out.append({
            "salary_component": "Employee PF",
            "abbr": "EPF", "amount": emp_pf, "statutory": True,
        })
    if is_esic and esic_emp_amt:
        deductions_out.append({
            "salary_component": "Employee ESIC",
            "abbr": "ESIC", "amount": esic_emp_amt, "statutory": True,
            "note": f"Gross × {esic_emp_pct}%",
        })
    if is_pt and pt_amount:
        deductions_out.append({
            "salary_component": "Professional Tax",
            "abbr": "PT", "amount": pt_amount, "statutory": True,
        })

    # Non-statutory deductions from structure (e.g. Retention)
    for row in struct["deduction_rows"]:
        formula = _resolve_deduction_formula(row["salary_component"], row["abbr"])
        amount  = formula(monthly_ctc, basic, da, basic_da, gross) if formula else 0.0
        if amount:
            deductions_out.append({
                "salary_component": row["salary_component"],
                "abbr":             row["abbr"],
                "amount":           amount,
                "statutory":        False,
            })

    total_deductions = _round2(sum(d["amount"] for d in deductions_out))
    net_salary       = _round0(total_gross - total_deductions)

    # ── Employer share ────────────────────────────────────────────────────────
    employer_share_out = [{
        "salary_component": "Gratuity",
        "abbr": "GRAT", "amount": gratuity, "in_ctc": True,
    }]
    if is_pf:
        employer_share_out.append({"salary_component": "Employer PF (ERPF)", "abbr": "ERPF",  "amount": erpf,     "in_ctc": True})
        employer_share_out.append({"salary_component": "Employer EPS",       "abbr": "EPS",   "amount": eps,      "in_ctc": True})
        employer_share_out.append({"salary_component": "Employer EDLI",      "abbr": "EDLI",  "amount": edli,     "in_ctc": False, "note": "Excl. CTC"})
        employer_share_out.append({"salary_component": "PF Admin Charges",   "abbr": "PFADM", "amount": pf_admin, "in_ctc": False, "note": "Excl. CTC"})

    esic_empr_amt = _round2(total_gross * esic_empr_pct / 100) if is_esic else 0.0
    if is_esic and esic_empr_amt:
        employer_share_out.append({
            "salary_component": "Employer ESIC",
            "abbr": "ESICE", "amount": esic_empr_amt, "in_ctc": True,
            "note": f"Gross × {esic_empr_pct}%",
        })

    total_employer_ctc   = _round2(sum(e["amount"] for e in employer_share_out if e.get("in_ctc")))
    total_employer_other = _round2(sum(e["amount"] for e in employer_share_out if not e.get("in_ctc")))

    return {
        "annual_ctc":           annual_ctc,
        "monthly_ctc":          monthly_ctc,
        "gross":                total_gross,
        "net_salary":           net_salary,
        "total_deductions":     total_deductions,
        "total_employer_ctc":   total_employer_ctc,
        "total_employer_other": total_employer_other,
        "basic_da":             _round2(basic_da),
        "pf_wage":              _round2(pf_wage),
        "earnings":             earnings_out,
        "deductions":           deductions_out,
        "employer_share":       employer_share_out,
        "flags": {
            "is_pf":   bool(is_pf),
            "is_esic": bool(is_esic),
            "is_pt":   bool(is_pt),
            "is_lwf":  bool(is_lwf),
        },
        "structure_info": {
            "company":          company,
            "salary_structure": salary_structure,
            "ssa_name":         salary_structure,
        },
        "_debug": {
            "monthly_ctc":      monthly_ctc,
            "gross":            total_gross,
            "basic":            basic,
            "da":               da,
            "basic_da":         _round2(basic_da),
            "pf_wage":          _round2(pf_wage),
            "is_pf":            is_pf,
            "is_esic":          is_esic,
            "is_pt":            is_pt,
            "esic_emp_pct":     esic_emp_pct,
            "esic_empr_pct":    esic_empr_pct,
            "struct_earnings":  [r["salary_component"] for r in struct["earning_rows"]],
            "struct_deductions":[r["salary_component"] for r in struct["deduction_rows"]],
        },
    }