import frappe


def after_install():
    create_roles()
    create_salary_components()
    ensure_desk_home_consistent()


def after_migrate():
    ensure_desk_home_consistent()


def _is_setup_complete():
    """True when site setup is done. Works on Frappe with or without is_setup_complete()."""
    checker = getattr(frappe, "is_setup_complete", None)
    if callable(checker):
        return checker()
    return int(frappe.db.get_single_value("System Settings", "setup_complete") or 0)


def ensure_desk_home_consistent():
    """Avoid Setup Wizard ↔ /app redirect loop after install.

    Frappe can mark setup complete (System Settings / Installed Application)
    while `desktop:home_page` is still `setup-wizard`. Desk then loads the
    wizard, which redirects to `/app`, which loads the wizard again.
    """
    if not _is_setup_complete():
        return

    changed = False
    if frappe.db.get_default("desktop:home_page") == "setup-wizard":
        frappe.db.set_default("desktop:home_page", "workspace")
        changed = True

    if str(frappe.db.get_default("setup_complete") or "0") in ("0", "None"):
        frappe.db.set_default("setup_complete", 1)
        changed = True

    if changed:
        frappe.clear_cache()
        print("✅ Desk home defaults synced (setup complete).")

def create_roles():
    roles = ["Saral HR Manager", "Saral HR User"]
    for role in roles:
        if not frappe.db.exists("Role", role):
            frappe.get_doc({
                "doctype": "Role",
                "role_name": role,
                "desk_access": 1
            }).insert(ignore_permissions=True)
    frappe.db.commit()
    print("✅ Saral HR Roles created successfully.")

def create_salary_components():
    components = [
        {"salary_component": "Basic", "salary_component_abbr": "BASIC", "type": "Earning", "depends_on_payment_days": 1},
        {"salary_component": "House Rent Allowance", "salary_component_abbr": "HRA", "type": "Earning", "depends_on_payment_days": 1},
        {"salary_component": "Dearness Allowance", "salary_component_abbr": "DA", "type": "Earning", "depends_on_payment_days": 1},
        {"salary_component": "Transport Allowance", "salary_component_abbr": "TA", "type": "Earning", "depends_on_payment_days": 1},
        {"salary_component": "Conveyance Allowance", "salary_component_abbr": "CONV", "type": "Earning", "depends_on_payment_days": 1},
        {"salary_component": "Medical Allowance", "salary_component_abbr": "MED", "type": "Earning", "depends_on_payment_days": 1},
        {"salary_component": "Education Allowance", "salary_component_abbr": "EDU", "type": "Earning", "depends_on_payment_days": 1},
        {"salary_component": "Other Allowance", "salary_component_abbr": "OA", "type": "Earning", "depends_on_payment_days": 1},
        {"salary_component": "Variable Pay", "salary_component_abbr": "VAR", "type": "Earning", "depends_on_payment_days": 1},
        {"salary_component": "Arrears", "salary_component_abbr": "ARREARS", "type": "Earning", "depends_on_payment_days": 0, "is_additional_only": 1},
        {"salary_component": "Arrears - without PF", "salary_component_abbr": "ARR-NOPF", "type": "Earning", "depends_on_payment_days": 0, "is_additional_only": 1},
        {"salary_component": "Production Incentive", "salary_component_abbr": "PI", "type": "Earning", "depends_on_payment_days": 0, "is_additional_only": 1},
        {"salary_component": "Safety Gadget Penalty", "salary_component_abbr": "SGP", "type": "Deduction", "is_additional_only": 1},
        {"salary_component": "Basic - DR", "salary_component_abbr": "B-DR", "type": "Earning", "is_daily_rate": 1},
        {"salary_component": "Dearness Allowance - DR", "salary_component_abbr": "DA-DR", "type": "Earning", "is_daily_rate": 1},
        {"salary_component": "Dearness Allowance -  DR", "salary_component_abbr": "DA - DR", "type": "Earning", "is_daily_rate": 1},
        {"salary_component": "Heat Allowance - DR", "salary_component_abbr": "HEAT-DR", "type": "Earning", "is_daily_rate": 1},
        {"salary_component": "Wash Allowance - DR", "salary_component_abbr": "WASH-DR", "type": "Earning", "is_daily_rate": 1},
        {"salary_component": "Other Allowance - DR", "salary_component_abbr": "OA-DR", "type": "Earning", "is_daily_rate": 1},
        {"salary_component": "Attendance Allowance - PWD", "salary_component_abbr": "ATT-PWD", "type": "Earning", "depends_on_physical_working_days": 1},
        {"salary_component": "House Rent Allowance - PWD", "salary_component_abbr": "HRA-PWD", "type": "Earning", "depends_on_physical_working_days": 1},
        {"salary_component": "Seniority Allowance - PWD", "salary_component_abbr": "SR-PWD", "type": "Earning", "depends_on_physical_working_days": 1},
        {"salary_component": "Leading H. Allowance - PWD", "salary_component_abbr": "LH-PWD", "type": "Earning", "depends_on_physical_working_days": 1},
        {"salary_component": "Setter Allowance - PWD", "salary_component_abbr": "SET-PWD", "type": "Earning", "depends_on_physical_working_days": 1},
        {"salary_component": "Advance", "salary_component_abbr": "ADV", "type": "Deduction"},
        {"salary_component": "Loan", "salary_component_abbr": "LOAN", "type": "Deduction"},
        {"salary_component": "Income Tax", "salary_component_abbr": "IT", "type": "Deduction"},
        {"salary_component": "Professional Tax", "salary_component_abbr": "PT", "type": "Deduction", "is_pt_component": 1},
        {"salary_component": "Retention", "salary_component_abbr": "RET", "type": "Deduction"},
        {"salary_component": "Other Deduction - 1", "salary_component_abbr": "OD-1", "type": "Deduction"},
        {"salary_component": "Employee - Bonus", "salary_component_abbr": "BONUS", "type": "Deduction"},
        {"salary_component": "Employee -Bonus", "salary_component_abbr": "BONUS", "type": "Deduction"},
        {"salary_component": "Employee - Labour Welfare Fund", "salary_component_abbr": "EMP-LWF", "type": "Deduction"},
        {"salary_component": "Employee -Labour Welfare Fund", "salary_component_abbr": "Employee - LWF", "type": "Deduction"},
        {"salary_component": "Employee - ESIC", "salary_component_abbr": "ESI-EMP", "type": "Deduction", "is_esic_component": 1, "esic_calculation_based_on": "Prorated Gross", "esic_percentage": 0.75},
        {"salary_component": "Employee - Full PF", "salary_component_abbr": "F-PF-EMP", "type": "Deduction", "is_pf_component": 1, "pf_calculation_based_on": "Prorated Gross", "pf_percentage": 12.0},
        {"salary_component": "Employee - Limited PF", "salary_component_abbr": "L-PF-EMP", "type": "Deduction", "is_pf_component": 1, "pf_calculation_based_on": "Prorated Gross", "pf_percentage": 12.0, "pf_cap_amount": 1800.0},
        {"salary_component": "Employee - No PF", "salary_component_abbr": "NO-PF-EMP", "type": "Deduction", "is_pf_component": 1, "pf_calculation_based_on": "Prorated Gross", "pf_percentage": 0.0},
        {"salary_component": "Employee -  PF", "salary_component_abbr": "PF", "type": "Deduction", "depends_on_payment_days": 1},
        {"salary_component": "Employer - Bonus", "salary_component_abbr": "EMPR-BONUS", "type": "Deduction", "employer_contribution": 1},
        {"salary_component": "Employer - Gratuity", "salary_component_abbr": "GRAT", "type": "Deduction", "employer_contribution": 1},
        {"salary_component": "Employer - Labour Welfare Fund", "salary_component_abbr": "EMPR-LWF", "type": "Deduction", "employer_contribution": 1},
        {"salary_component": "Employer - ESIC", "salary_component_abbr": "EESI-EMPR", "type": "Deduction", "employer_contribution": 1, "is_esic_component": 1, "esic_calculation_based_on": "Prorated Gross", "esic_percentage": 3.25},
        {"salary_component": "Employer -  PF", "salary_component_abbr": "EPF", "type": "Deduction", "employer_contribution": 1, "depends_on_payment_days": 1},
        {"salary_component": "Employer - EPF (Limited)", "salary_component_abbr": "EPF-L-EMPR", "type": "Deduction", "employer_contribution": 1, "is_pf_component": 1, "pf_calculation_based_on": "Prorated Gross", "pf_percentage": 3.67},
        {"salary_component": "Employer - EPS (Limited)", "salary_component_abbr": "EPS-L-EMPR", "type": "Deduction", "employer_contribution": 1, "is_pf_component": 1, "pf_calculation_based_on": "Prorated Gross", "pf_percentage": 8.33},
        {"salary_component": "Employer - EDLI (Limited)", "salary_component_abbr": "EDLI-L-EMPR", "type": "Deduction", "employer_contribution": 1, "is_pf_component": 1, "pf_calculation_based_on": "Prorated Gross", "pf_percentage": 0.5},
        {"salary_component": "Employer - PF Admin (Limited)", "salary_component_abbr": "PF-ADM-L", "type": "Deduction", "employer_contribution": 1, "is_pf_component": 1, "pf_calculation_based_on": "Prorated Gross", "pf_percentage": 0.5},
        {"salary_component": "Employer - EPF (Full)", "salary_component_abbr": "EPF-F-EMPR", "type": "Deduction", "employer_contribution": 1, "is_pf_component": 1, "pf_calculation_based_on": "Prorated Gross", "pf_percentage": 3.67},
        {"salary_component": "Employer - EPS (Full)", "salary_component_abbr": "EPS-F-EMPR", "type": "Deduction", "employer_contribution": 1, "is_pf_component": 1, "pf_calculation_based_on": "Prorated Gross", "pf_percentage": 8.33},
        {"salary_component": "Employer - EDLI (Full)", "salary_component_abbr": "EDLI-F-EMPR", "type": "Deduction", "employer_contribution": 1, "is_pf_component": 1, "pf_calculation_based_on": "Prorated Gross", "pf_percentage": 0.5},
        {"salary_component": "Employer - PF Admin (Full)", "salary_component_abbr": "PF-ADM-F", "type": "Deduction", "employer_contribution": 1, "is_pf_component": 1, "pf_calculation_based_on": "Prorated Gross", "pf_percentage": 0.5},
        {"salary_component": "Employer - EPF (No PF)", "salary_component_abbr": "EPF-N-EMPR", "type": "Deduction", "employer_contribution": 1, "is_pf_component": 1, "pf_calculation_based_on": "Prorated Gross", "pf_percentage": 0.0},
        {"salary_component": "Employer - EPS (No PF)", "salary_component_abbr": "EPS-N-EMPR", "type": "Deduction", "employer_contribution": 1, "is_pf_component": 1, "pf_calculation_based_on": "Prorated Gross", "pf_percentage": 0.0},
        {"salary_component": "Employer - EDLI (No PF)", "salary_component_abbr": "EDLI-N-EMPR", "type": "Deduction", "employer_contribution": 1, "is_pf_component": 1, "pf_calculation_based_on": "Prorated Gross", "pf_percentage": 0.0},
        {"salary_component": "Employer - PF Admin (No PF)", "salary_component_abbr": "PF-ADM-N", "type": "Deduction", "employer_contribution": 1, "is_pf_component": 1, "pf_calculation_based_on": "Prorated Gross", "pf_percentage": 0.0},
    ]

    for comp in components:
        name = comp["salary_component"]
        if not frappe.db.exists("Salary Component", name):
            doc = frappe.get_doc({
                "doctype": "Salary Component",
                "salary_component": name,
                "salary_component_abbr": comp.get("salary_component_abbr"),
                "type": comp.get("type"),
                "depends_on_payment_days": comp.get("depends_on_payment_days", 0),
                "depends_on_physical_working_days": comp.get("depends_on_physical_working_days", 0),
                "is_daily_rate": comp.get("is_daily_rate", 0),
                "employer_contribution": comp.get("employer_contribution", 0),
                "is_pf_component": comp.get("is_pf_component", 0),
                "pf_calculation_based_on": comp.get("pf_calculation_based_on"),
                "pf_percentage": comp.get("pf_percentage", 0.0),
                "pf_cap_amount": comp.get("pf_cap_amount", 0.0),
                "is_esic_component": comp.get("is_esic_component", 0),
                "esic_calculation_based_on": comp.get("esic_calculation_based_on"),
                "esic_percentage": comp.get("esic_percentage", 0.0),
                "is_pt_component": comp.get("is_pt_component", 0),
                "is_additional_only": comp.get("is_additional_only", 0),
            })
            doc.insert(ignore_permissions=True)
            print(f"✅ Created: {name}")
        else:
            if comp.get("is_additional_only") and not int(
                frappe.db.get_value("Salary Component", name, "is_additional_only") or 0
            ):
                frappe.db.set_value("Salary Component", name, "is_additional_only", 1)
                print(f"✅ Marked additional-only: {name}")
            else:
                print(f"⏭️ Skipped (exists): {name}")

    frappe.db.commit()
    print("✅ Salary Components created successfully.")

