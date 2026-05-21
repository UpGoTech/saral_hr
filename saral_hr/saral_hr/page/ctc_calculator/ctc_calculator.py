import frappe
from frappe.utils import flt, getdate, get_last_day
from decimal import Decimal, ROUND_HALF_UP


def _round2(value):
    return float(Decimal(str(flt(value, 4))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _round0(value):
    return int(Decimal(str(flt(value, 2))).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


# ─── Constants ────────────────────────────────────────────────────────────────

PF_WAGE_CAP    = 15000.0
GRATUITY_RATE  = 4.81  / 100
ERPF_RATE      = 3.67  / 100
EPS_RATE       = 8.33  / 100
EDLI_RATE      = 0.50  / 100
PF_ADMIN_RATE  = 0.50  / 100
EMP_PF_RATE    = 12.00 / 100
RETENTION_RATE = 2.00  / 100
PT_NORMAL      = 200.0
PT_FEBRUARY    = 300.0

STATUTORY_NAMES = {
    "Employee ESIC", "Employer ESIC", "Employee PF", "Employer PF",
    "Employer EPS", "Employer EDLI", "Employer PF Admin Charges",
    "Professional Tax", "Employee Labour Welfare Fund", "Employer Labour Welfare Fund",
}

VARIABLE_KEYWORDS = ["variable", "var pay", "varpay"]
OTHERS_KEYWORDS   = ["other", "others"]


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
        SELECT DISTINCT ssa.salary_structure
        FROM `tabSalary Structure Assignment` ssa
        WHERE ssa.company = %(company)s AND ssa.docstatus = 1
        ORDER BY ssa.salary_structure ASC
    """, {"company": company}, as_dict=True)
    return [r.salary_structure for r in rows]


# ─── 3. Get component amounts from the latest SSA ────────────────────────────

@frappe.whitelist()
def get_structure_components(company, salary_structure):
    if not company or not salary_structure:
        frappe.throw("Company and Salary Structure are required")

    ssa_name = frappe.db.sql("""
        SELECT name FROM `tabSalary Structure Assignment`
        WHERE company = %(company)s
          AND salary_structure = %(ss)s
          AND docstatus = 1
        ORDER BY from_date DESC LIMIT 1
    """, {"company": company, "ss": salary_structure}, as_dict=True)

    if not ssa_name:
        frappe.throw(f"No submitted SSA found for '{salary_structure}' in '{company}'")

    ssa_doc = frappe.get_doc("Salary Structure Assignment", ssa_name[0].name)

    def _abbr(comp_name):
        return frappe.db.get_value("Salary Component", comp_name, "salary_component_abbr") or comp_name

    earnings = [{"salary_component": r.salary_component, "abbr": _abbr(r.salary_component), "amount": flt(r.amount, 2)} for r in (ssa_doc.earnings or [])]
    deductions = [{"salary_component": r.salary_component, "abbr": _abbr(r.salary_component), "amount": flt(r.amount, 2)} for r in (ssa_doc.deductions or [])]
    employer_share = [{"salary_component": r.salary_component, "abbr": _abbr(r.salary_component), "amount": flt(r.amount, 2)} for r in (ssa_doc.employer_share or [])]

    return {
        "ssa_name":           ssa_doc.name,
        "earnings":           earnings,
        "deductions":         deductions,
        "employer_share":     employer_share,
        "is_pf_applicable":   int(ssa_doc.is_pf_applicable or 0),
        "pf_type":            ssa_doc.pf_applicable or "Limited PF",
        "is_esic_applicable": int(ssa_doc.is_esic_applicable or 0),
        "is_pt_applicable":   int(ssa_doc.is_pt_applicable or 0),
        "is_lwf_applicable":  int(ssa_doc.is_lwf_applicable or 0),
    }


# ─── 4. Main CTC breakdown API ───────────────────────────────────────────────

@frappe.whitelist()
def calculate_ctc_breakdown(company, salary_structure, annual_ctc, month=None,
                            include_retention=False, include_pf=None, include_esic=None):
    if not company or not salary_structure or not annual_ctc:
        frappe.throw("Company, Salary Structure and Annual CTC are required")

    annual_ctc   = flt(annual_ctc)
    monthly_ctc  = _round2(annual_ctc / 12)
    include_ret  = frappe.utils.cint(include_retention)
    month_name   = month or "January"
    is_february  = (month_name == "February")

    # Toggle overrides — explicit value (even "0") wins over the SSA flag.
    # If the param is missing/blank, fall back to the SSA's own applicability flag.
    override_pf   = frappe.utils.cint(include_pf)   if include_pf   not in (None, "") else None
    override_esic = frappe.utils.cint(include_esic) if include_esic not in (None, "") else None

    # Load SSA data
    comp_data    = get_structure_components(company, salary_structure)
    ssa_earnings = comp_data["earnings"]
    ssa_deds     = comp_data["deductions"]
    ssa_emp      = comp_data["employer_share"]
    is_pf        = override_pf   if override_pf   is not None else comp_data["is_pf_applicable"]
    pf_type      = comp_data["pf_type"]
    is_esic      = override_esic if override_esic is not None else comp_data["is_esic_applicable"]
    is_pt        = comp_data["is_pt_applicable"]
    is_lwf       = comp_data["is_lwf_applicable"]

    # DEBUG — remove after verifying. View output in: bench --site <site> console
    # or in the browser Network tab response, under "_debug".
    _debug = {
        "raw_include_pf":   include_pf,
        "raw_include_esic": include_esic,
        "override_pf":      override_pf,
        "override_esic":    override_esic,
        "ssa_is_pf":        comp_data["is_pf_applicable"],
        "ssa_is_esic":      comp_data["is_esic_applicable"],
        "resolved_is_pf":   int(is_pf),
        "resolved_is_esic": int(is_esic),
    }
    frappe.logger("ctc_calc").info(_debug)

    # Identify Basic and DA
    basic_amount = 0.0
    da_amount    = 0.0
    for row in ssa_earnings:
        cl = (row["salary_component"] or "").lower()
        al = (row["abbr"] or "").lower()
        if "basic" in cl:
            basic_amount = flt(row["amount"])
        if "dearness" in cl or cl == "da" or al == "da" or al.startswith("da"):
            da_amount = flt(row["amount"])

    basic_da = basic_amount + da_amount
    pf_wage  = min(basic_da, PF_WAGE_CAP) if is_pf else 0.0

    # Employer CTC share
    gratuity = _round2(basic_da * GRATUITY_RATE)
    erpf     = _round2(pf_wage  * ERPF_RATE)     if is_pf else 0.0
    eps      = _round2(pf_wage  * EPS_RATE)      if is_pf else 0.0
    edli     = _round2(pf_wage  * EDLI_RATE)     if is_pf else 0.0
    pf_admin = _round2(pf_wage  * PF_ADMIN_RATE) if is_pf else 0.0

    # ESIC employer %
    esic_emp_pct  = 0.0
    esic_empr_pct = 0.0
    if is_esic:
        try:
            comp_doc = frappe.get_doc("Company", company)
            if hasattr(comp_doc, "get_esic_config"):
                cfg = comp_doc.get_esic_config()
                if cfg:
                    esic_emp_pct  = flt(cfg.get("employee_percent", 0))
                    esic_empr_pct = flt(cfg.get("employer_percent", 0))
        except Exception:
            pass
    # Statutory fallback if company config didn't supply rates
    if is_esic and not esic_emp_pct:
        esic_emp_pct = 0.75
    if is_esic and not esic_empr_pct:
        esic_empr_pct = 3.25

    # Gross = monthly_ctc - primary employer CTC share (gratuity + erpf + eps)
    primary_employer = gratuity + erpf + eps
    gross = _round2(monthly_ctc - primary_employer)

    # ── Build earnings ────────────────────────────────────────────────────────
    fixed_total          = 0.0
    has_others_component = False
    earnings_out         = []

    for row in ssa_earnings:
        cl         = (row["salary_component"] or "").lower()
        is_var     = any(k in cl for k in VARIABLE_KEYWORDS)
        is_others  = any(k in cl for k in OTHERS_KEYWORDS)
        if is_others:
            has_others_component = True
            continue
        amount = flt(row["amount"])
        earnings_out.append({
            "salary_component": row["salary_component"],
            "abbr":             row["abbr"],
            "amount":           amount,
            "is_variable":      is_var,
        })
        fixed_total += amount

    others_amount = _round2(max(gross - fixed_total, 0.0))
    if has_others_component or others_amount >= 0:
        earnings_out.append({
            "salary_component": "Others",
            "abbr":             "OTH",
            "amount":           others_amount,
            "is_variable":      False,
            "is_others":        True,
        })

    total_gross = _round2(sum(e["amount"] for e in earnings_out))

    # ── Build deductions ──────────────────────────────────────────────────────
    emp_pf       = _round2(pf_wage * EMP_PF_RATE)        if is_pf else 0.0
    pt_amount    = (PT_FEBRUARY if is_february else PT_NORMAL) if is_pt else 0.0
    retention    = _round2(basic_da * RETENTION_RATE)     if include_ret else 0.0
    esic_emp_amt = _round2(gross * esic_emp_pct / 100)    if is_esic and esic_emp_pct else 0.0

    deductions_out = []
    if is_pf and emp_pf:
        deductions_out.append({"salary_component": "Employee PF",      "abbr": "EPF",  "amount": emp_pf,       "statutory": True})
    if is_esic and esic_emp_amt:
        deductions_out.append({"salary_component": "Employee ESIC",    "abbr": "ESIC", "amount": esic_emp_amt, "statutory": True})
    if is_pt and pt_amount:
        deductions_out.append({"salary_component": "Professional Tax", "abbr": "PT",   "amount": pt_amount,    "statutory": True})
    if include_ret and retention:
        deductions_out.append({"salary_component": "Retention",        "abbr": "RET",  "amount": retention,    "statutory": False, "note": "First 3 years only"})

    for row in ssa_deds:
        if row["salary_component"] not in STATUTORY_NAMES:
            deductions_out.append({"salary_component": row["salary_component"], "abbr": row["abbr"], "amount": flt(row["amount"]), "statutory": False})

    total_deductions = _round2(sum(d["amount"] for d in deductions_out))
    net_salary       = _round0(total_gross - total_deductions)

    # ── Employer share ────────────────────────────────────────────────────────
    employer_share_out = []
    employer_share_out.append({"salary_component": "Gratuity",         "abbr": "GRAT",  "amount": gratuity, "in_ctc": True})
    if is_pf:
        employer_share_out.append({"salary_component": "Employer PF (ERPF)", "abbr": "ERPF",  "amount": erpf,     "in_ctc": True})
        employer_share_out.append({"salary_component": "Employer EPS",       "abbr": "EPS",   "amount": eps,      "in_ctc": True})
        employer_share_out.append({"salary_component": "Employer EDLI",      "abbr": "EDLI",  "amount": edli,     "in_ctc": False, "note": "Excl. CTC"})
        employer_share_out.append({"salary_component": "PF Admin Charges",   "abbr": "PFADM", "amount": pf_admin, "in_ctc": False, "note": "Excl. CTC"})

    esic_empr_amt = _round2(gross * esic_empr_pct / 100) if is_esic and esic_empr_pct else 0.0
    if is_esic and esic_empr_amt:
        employer_share_out.append({"salary_component": "Employer ESIC", "abbr": "ESICE", "amount": esic_empr_amt, "in_ctc": True})

    for row in ssa_emp:
        if row["salary_component"] not in STATUTORY_NAMES:
            employer_share_out.append({"salary_component": row["salary_component"], "abbr": row["abbr"], "amount": flt(row["amount"]), "in_ctc": True})

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
        "flags":                {"is_pf": bool(is_pf), "is_esic": bool(is_esic), "is_pt": bool(is_pt), "is_lwf": bool(is_lwf)},
        "structure_info":       {"company": company, "salary_structure": salary_structure, "ssa_name": comp_data["ssa_name"]},
        "_debug":               _debug,
    }