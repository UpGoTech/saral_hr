import frappe
from frappe.utils import flt
from decimal import Decimal, ROUND_HALF_UP


def _round2(value):
    return float(Decimal(str(flt(value, 4))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

def _round0(value):
    return int(Decimal(str(flt(value, 2))).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


EARNING_PCT = {
    "Basic":                0.50,
    "Dearness Allowance":   0.10,
    "House Rent Allowance": 0.075,
    "Conveyance Allowance": 0.02667,
    "Medical Allowance":    0.02083,
    "Education Allowance":  0.00333,
    "Variable Pay":         0.075,
}

GRATUITY_RATE = 4.81 / 100

PT_NORMAL   = 200.0
PT_FEBRUARY = 300.0

STATUTORY_NAMES = {
    "Employee ESIC", "Employer ESIC", "Employee PF", "Employer PF",
    "Employer EPS", "Employer EDLI", "Employer PF Admin Charges",
    "Professional Tax", "Employee Labour Welfare Fund", "Employer Labour Welfare Fund",
}

PF_DEDUCTION_NAMES   = {"Employee PF", "Employees PF"}
ESIC_DEDUCTION_NAMES = {"Employee ESIC", "Employees ESIC"}
PT_DEDUCTION_NAMES   = {"Professional Tax"}

GRATUITY_EMP_NAMES = {"Employer Gratuity", "Gratuity"}
ERPF_EMP_NAMES     = {"Employer PF", "Employer EPF"}
EPS_EMP_NAMES      = {"Employer EPS"}
EDLI_EMP_NAMES     = {"Employer EDLI"}
PFADM_EMP_NAMES    = {"Employer PF Admin Charges", "PF Admin Charges"}
ESIC_EMP_NAMES     = {"Employer ESIC"}

VARIABLE_KEYWORDS = ["variable", "var pay", "varpay"]
OTHERS_KEYWORDS   = ["other allowance", "other allow", "others", "other"]
OTHERS_ABBR       = {"oa", "oth", "oth."}


def _is_others_component(salary_component, abbr):
    cl     = (salary_component or "").lower().strip()
    abbr_l = (abbr or "").lower().strip()
    return any(cl == k for k in OTHERS_KEYWORDS) or abbr_l in OTHERS_ABBR

def _is_variable_component(salary_component):
    cl = (salary_component or "").lower()
    return any(k in cl for k in VARIABLE_KEYWORDS)

def _name_in(name, name_set):
    nl = (name or "").lower().strip()
    return any(nl == s.lower() for s in name_set)


# ─── APIs ─────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_companies():
    return [c.name for c in frappe.db.get_all("Company", fields=["name"], order_by="name asc")]


@frappe.whitelist()
def get_salary_structures(company):
    if not company:
        frappe.throw("Company is required")
    rows = frappe.db.sql("""
        SELECT DISTINCT ssa.salary_structure
        FROM `tabSalary Structure Assignment` ssa
        WHERE ssa.company = %(company)s AND ssa.docstatus = 1
        ORDER BY ssa.salary_structure ASC
    """, {"company": company}, as_dict=True)
    return [r.salary_structure for r in rows]


@frappe.whitelist()
def get_structure_components(company, salary_structure):
    if not company or not salary_structure:
        frappe.throw("Company and Salary Structure are required")

    ssa_row = frappe.db.sql("""
        SELECT name FROM `tabSalary Structure Assignment`
        WHERE company = %(company)s AND salary_structure = %(ss)s AND docstatus = 1
        ORDER BY from_date DESC LIMIT 1
    """, {"company": company, "ss": salary_structure}, as_dict=True)

    if not ssa_row:
        frappe.throw(f"No submitted SSA found for '{salary_structure}' in '{company}'")

    ssa = frappe.get_doc("Salary Structure Assignment", ssa_row[0].name)

    def _abbr(n):
        return frappe.db.get_value("Salary Component", n, "salary_component_abbr") or n

    earning_components = [
        {
            "salary_component": r.salary_component,
            "abbr":             _abbr(r.salary_component),
            "is_others":        _is_others_component(r.salary_component, r.abbr),
            "is_variable":      _is_variable_component(r.salary_component),
        }
        for r in (ssa.earnings or [])
    ]

    # All deduction rows from SSA
    all_deds = [
        {
            "salary_component": r.salary_component,
            "abbr":             _abbr(r.salary_component),
            "statutory":        r.salary_component in STATUTORY_NAMES,
        }
        for r in (ssa.deductions or [])
    ]

    return {
        "ssa_name":           ssa_row[0].name,
        "earning_components": earning_components,
        "all_deductions":     all_deds,
        "is_pf_applicable":   int(ssa.is_pf_applicable   or 0),
        "pf_type":            ssa.pf_applicable or "Limited PF",
        "is_esic_applicable": int(ssa.is_esic_applicable or 0),
        "is_pt_applicable":   int(ssa.is_pt_applicable   or 0),
        "is_lwf_applicable":  int(ssa.is_lwf_applicable  or 0),
    }


# ─── Main calculation ─────────────────────────────────────────────────────────

@frappe.whitelist()
def calculate_ctc_breakdown(company, salary_structure, annual_ctc,
                             month=None, include_pf=None, include_esic=None):
    if not company or not salary_structure or not annual_ctc:
        frappe.throw("Company, Salary Structure and Annual CTC are required")

    annual_ctc  = flt(annual_ctc)
    monthly_ctc = _round2(annual_ctc / 12)
    month_name  = month or "January"
    is_february = (month_name == "February")

    override_pf   = frappe.utils.cint(include_pf)   if include_pf   is not None else None
    override_esic = frappe.utils.cint(include_esic) if include_esic is not None else None

    comp_data  = get_structure_components(company, salary_structure)
    earn_comps = comp_data["earning_components"]
    all_deds   = comp_data["all_deductions"]

    # Toggle overrides SSA flag
    is_pf   = override_pf   if override_pf   is not None else comp_data["is_pf_applicable"]
    pf_type = comp_data["pf_type"]
    is_esic = override_esic if override_esic is not None else comp_data["is_esic_applicable"]
    is_pt   = comp_data["is_pt_applicable"]
    is_lwf  = comp_data["is_lwf_applicable"]

    # SSA deduction presence flags (controls non-statutory rows only)
    ssa_has_pt = any(_name_in(d["salary_component"], PT_DEDUCTION_NAMES) for d in all_deds)

    # Company config
    company_doc = frappe.get_doc("Company", company)
    pf_cfg      = company_doc.get_pf_config()   or {}
    esic_cfg    = company_doc.get_esic_config() or {}
    pf_comps    = company_doc._get_child_components("pf_dependent_component")
    esic_comps  = company_doc._get_child_components("esic_dependent_component")

    # ── Step 1: Static % → scaled earning amounts ─────────────────────────
    scaled_earn = {
        row["salary_component"]: _round2(EARNING_PCT.get(row["salary_component"], 0.0) * monthly_ctc)
        for row in earn_comps
        if not row["is_others"]
    }

    # ── Step 2: PF wage basis ──────────────────────────────────────────────
    if pf_comps:
        pf_wage_basis = sum(scaled_earn.get(c, 0.0) for c in pf_comps)
    else:
        pf_wage_basis = sum(
            amt for comp, amt in scaled_earn.items()
            if "basic" in comp.lower() or "dearness" in comp.lower()
        )

    wage_limit = flt(pf_cfg.get("wage_limit", 0))
    pf_wage    = (
        _round2(min(pf_wage_basis, wage_limit))
        if (is_pf and pf_type == "Limited PF" and wage_limit)
        else _round2(pf_wage_basis) if is_pf else 0.0
    )

    # ── Step 3: Compute all statutory amounts (toggle-gated) ──────────────
    gratuity = _round2(pf_wage_basis * GRATUITY_RATE)

    # PF components — only computed when toggle is ON
    erpf     = _round2(pf_wage * flt(pf_cfg.get("employer_epf",    0)) / 100) if is_pf else 0.0
    eps      = _round2(pf_wage * flt(pf_cfg.get("employer_eps",    0)) / 100) if is_pf else 0.0
    edli     = _round2(pf_wage * flt(pf_cfg.get("edli_insurance",  0)) / 100) if is_pf else 0.0
    pf_admin = _round2(pf_wage * flt(pf_cfg.get("admin_charges",   0)) / 100) if is_pf else 0.0
    emp_pf   = _round2(pf_wage * flt(pf_cfg.get("employee_percent",0)) / 100) if is_pf else 0.0

    # ── Step 4: ESIC — two-pass (employer ESIC affects gross) ─────────────
    def _esic_wage(target_gross):
        if esic_comps and is_esic:
            return sum(scaled_earn.get(c, 0.0) for c in esic_comps)
        return target_gross

    gross_p1     = _round2(monthly_ctc - gratuity - erpf - eps)
    esic_empr_p1 = (
        _round2(_esic_wage(gross_p1) * flt(esic_cfg.get("employer_percent", 0)) / 100)
        if is_esic else 0.0
    )

    gross         = _round2(monthly_ctc - gratuity - erpf - eps - esic_empr_p1)
    esic_wage_amt = _esic_wage(gross)
    esic_empr_amt = (
        _round2(esic_wage_amt * flt(esic_cfg.get("employer_percent", 0)) / 100)
        if is_esic else 0.0
    )
    esic_emp_amt  = (
        _round2(esic_wage_amt * flt(esic_cfg.get("employee_percent", 0)) / 100)
        if is_esic else 0.0
    )

    # ── Step 5: Build earnings — Others = remainder ────────────────────────
    fixed_total   = sum(scaled_earn.values())
    others_row    = next((r for r in earn_comps if r["is_others"]), None)
    others_amount = _round2(max(gross - fixed_total, 0.0))

    earnings_out = [
        {
            "salary_component": row["salary_component"],
            "abbr":             row["abbr"],
            "amount":           scaled_earn.get(row["salary_component"], 0.0),
            "is_variable":      row["is_variable"],
            "is_others":        False,
        }
        for row in earn_comps if not row["is_others"]
    ]
    if others_row or others_amount > 0:
        earnings_out.append({
            "salary_component": (others_row or {}).get("salary_component", "Others"),
            "abbr":             (others_row or {}).get("abbr", "OTH"),
            "amount":           others_amount,
            "is_variable":      False,
            "is_others":        True,
        })

    total_gross = _round2(sum(e["amount"] for e in earnings_out))

    # ── Step 6: Deductions ─────────────────────────────────────────────────
    # Walk SSA deduction rows first (preserves order, handles non-statutory)
    pt_amount      = (PT_FEBRUARY if is_february else PT_NORMAL) if (is_pt and ssa_has_pt) else 0.0
    deductions_out = []
    pf_added       = False
    esic_added     = False
    pt_added       = False

    for ded in all_deds:
        name = ded["salary_component"]

        if _name_in(name, PF_DEDUCTION_NAMES):
            # Only show when PF toggle ON
            if is_pf and emp_pf:
                deductions_out.append({
                    "salary_component": name,
                    "abbr":             ded["abbr"],
                    "amount":           emp_pf,
                    "statutory":        True,
                })
            pf_added = True

        elif _name_in(name, ESIC_DEDUCTION_NAMES):
            # Only show when ESIC toggle ON
            if is_esic and esic_emp_amt:
                deductions_out.append({
                    "salary_component": name,
                    "abbr":             ded["abbr"],
                    "amount":           esic_emp_amt,
                    "statutory":        True,
                })
            esic_added = True

        elif _name_in(name, PT_DEDUCTION_NAMES):
            if is_pt and pt_amount:
                deductions_out.append({
                    "salary_component": name,
                    "abbr":             ded["abbr"],
                    "amount":           pt_amount,
                    "statutory":        True,
                })
            pt_added = True

        else:
            # Non-statutory (e.g. Retention)
            comp_lower = name.lower()
            if "retention" in comp_lower:
                amount = _round2(pf_wage_basis * flt(pf_cfg.get("retention_rate", 0)) / 100)
            else:
                amount = 0.0
            deductions_out.append({
                "salary_component": name,
                "abbr":             ded["abbr"],
                "amount":           amount,
                "statutory":        False,
            })

    # If PF row not in SSA deductions but toggle is ON — still show it
    if is_pf and emp_pf and not pf_added:
        deductions_out.insert(0, {
            "salary_component": "Employee PF",
            "abbr":             "EPF",
            "amount":           emp_pf,
            "statutory":        True,
        })

    # If ESIC row not in SSA deductions but toggle is ON — still show it
    if is_esic and esic_emp_amt and not esic_added:
        deductions_out.insert(1, {
            "salary_component": "Employee ESIC",
            "abbr":             "ESIC",
            "amount":           esic_emp_amt,
            "statutory":        True,
        })

    total_deductions = _round2(sum(d["amount"] for d in deductions_out))
    net_salary       = _round0(total_gross - total_deductions)

    # ── Step 7: Employer share — driven purely by toggles ─────────────────
    employer_share_out = []

    # Gratuity — always present
    employer_share_out.append({
        "salary_component": "Employer Gratuity",
        "abbr":             "EMPR-GRAT",
        "amount":           gratuity,
        "in_ctc":           True,
    })

    # PF components — only when toggle ON
    if is_pf:
        employer_share_out.append({
            "salary_component": "Employer PF (ERPF)",
            "abbr":             "EMPR-PF",
            "amount":           erpf,
            "in_ctc":           True,
        })
        employer_share_out.append({
            "salary_component": "Employer EPS",
            "abbr":             "EMPR-EPS",
            "amount":           eps,
            "in_ctc":           True,
        })
        employer_share_out.append({
            "salary_component": "Employer EDLI",
            "abbr":             "EMPR-EDLI",
            "amount":           edli,
            "in_ctc":           False,
            "note":             "Excl. CTC",
        })
        employer_share_out.append({
            "salary_component": "Employer PF Admin Charges",
            "abbr":             "EMPR-PFADM",
            "amount":           pf_admin,
            "in_ctc":           False,
            "note":             "Excl. CTC",
        })

    # ESIC employer share — only when toggle ON
    if is_esic and esic_empr_amt:
        employer_share_out.append({
            "salary_component": "Employer ESIC",
            "abbr":             "EMPR-ESIC",
            "amount":           esic_empr_amt,
            "in_ctc":           True,
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
        "basic_da":             _round2(pf_wage_basis),
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
            "ssa_name":         comp_data["ssa_name"],
        },
    }