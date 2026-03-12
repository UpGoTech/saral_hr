# Copyright (c) 2026, sj and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

VIRTUAL_COMPONENTS = {"Gross", "Gross Including Additional Salary"}


class Company(Document):

    def validate(self):
        self.validate_esic_settings()
        self.validate_pf_settings()

    def on_update(self):
        pass

    # ──────────────────────────────────────────────
    # ESIC
    # ──────────────────────────────────────────────

    def validate_esic_settings(self):
        components = self._get_child_components("esic_dependent_component")
        if not components:
            return

        self._validate_components(components, "ESIC")

        if len(components) < 2:
            frappe.msgprint(
                _("ESIC Wage Basis: only one component listed — nothing will be subtracted."),
                indicator="orange",
                alert=True
            )

        if self.esic_wage_limit and self.esic_wage_limit < 0:
            frappe.throw(_("ESIC Wage Limit cannot be negative."))
        if self.esic_employee_contribution is not None and self.esic_employee_contribution < 0:
            frappe.throw(_("ESIC Employee Contribution % cannot be negative."))
        if self.esic_employer_contribution is not None and self.esic_employer_contribution < 0:
            frappe.throw(_("ESIC Employer Contribution % cannot be negative."))

    # ──────────────────────────────────────────────
    # PF
    # ──────────────────────────────────────────────

    def validate_pf_settings(self):
        components = self._get_child_components("pf_dependent_component")
        if not components:
            return

        self._validate_components(components, "PF")

        for fieldname, label in [
            ("pf_employee_percent", "PF Employee Contribution %"),
            ("pf_employer_eps",     "PF Employer EPS %"),
            ("pf_employer_epf",     "PF Employer EPF %"),
            ("pf_edli_insurance",   "PF Employee EDLI Insurance %"),
            ("pf_admin_charges",    "PF Employer Admin Charges %"),
        ]:
            val = self.get(fieldname)
            if val is not None and val < 0:
                frappe.throw(_("{0} cannot be negative.").format(label))

    # ──────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────

    def _get_child_components(self, table_fieldname):
        """Return an ordered list of component names from a child table field."""
        rows = self.get(table_fieldname) or []
        return [row.wage_components for row in rows if row.wage_components]

    def _validate_components(self, components, label_prefix):
        for comp in components:
            if comp in VIRTUAL_COMPONENTS:
                continue
            comp_type = frappe.db.get_value("Salary Component", comp, "type")
            if not comp_type:
                frappe.throw(
                    _("{0} Wage Component <b>{1}</b> does not exist.").format(label_prefix, comp)
                )
            if comp_type != "Earning":
                frappe.throw(
                    _("{0} Wage Component <b>{1}</b> must be of type Earning.").format(label_prefix, comp)
                )

    def _resolve_component_value(self, comp: str, salary_components: dict) -> float:
        """
        Resolve a component name to its numeric value.

        Virtual components are resolved as follows:

        "Gross"
            = sum of all values in salary_components whose key is a real
              Earning component (i.e. NOT a virtual keyword and NOT a
              reserved internal key starting with "_").
              Callers must pass every earning row as {component_name: amount}.

        "Gross Including Additional Salary"
            = Gross (as above) + salary_components.get("_additional_salary", 0)
              Callers must inject the pre-fetched Additional Salary amount
              under the reserved key "_additional_salary".

        Any other name
            = direct lookup in salary_components, defaulting to 0.0.

        Example salary_components dict the caller should build:
            {
                "Basic":              15000.0,
                "Dearness Allowance":  5000.0,
                "Conveyance Allowance": 800.0,
                "_additional_salary":  2000.0,   # optional; 0 if none
            }
        """
        if comp == "Gross":
            # Direct lookup first (SSA passes gross_salary under "Gross" key)
            if "Gross" in salary_components:
                return float(salary_components["Gross"])
            # Fallback: sum all real earning component values
            return float(sum(
                v for k, v in salary_components.items()
                if k not in VIRTUAL_COMPONENTS and not k.startswith("_")
            ))

        if comp == "Gross Including Additional Salary":
            # Direct lookup first
            if "Gross Including Additional Salary" in salary_components:
                return float(salary_components["Gross Including Additional Salary"])
            # Fallback: sum real components + additional salary
            gross = float(sum(
                v for k, v in salary_components.items()
                if k not in VIRTUAL_COMPONENTS and not k.startswith("_")
            ))
            additional = float(salary_components.get("_additional_salary", 0.0))
            return gross + additional

        return float(salary_components.get(comp, 0.0))

    # ──────────────────────────────────────────────
    # Wage basis calculators (called from payroll)
    # ──────────────────────────────────────────────

    def compute_esic_wage_basis(self, salary_components: dict) -> float:
        """
        ESIC wage basis = FIRST component MINUS all remaining components,
        then capped at esic_wage_limit (if set).

        Common configurations:
            [Gross]                          → Gross
            [Gross, Conveyance Allowance]    → Gross − Conveyance Allowance
            [Basic, DA]                      → Basic − DA  (unusual but supported)

        :param salary_components: dict of {component_name: amount}.
               Pass "_additional_salary" key if Gross Including Additional
               Salary is used as a component.
        :return: wage basis as float, clamped to 0, capped at esic_wage_limit.
        """
        components = self._get_child_components("esic_dependent_component")
        if not components:
            return 0.0

        result = self._resolve_component_value(components[0], salary_components)
        for comp in components[1:]:
            result -= self._resolve_component_value(comp, salary_components)

        result = max(result, 0.0)

        if self.esic_wage_limit:
            result = min(result, float(self.esic_wage_limit))

        return result

    def compute_pf_wage_basis(self, salary_components: dict) -> float:
        """
        PF wage basis = SUM of ALL listed components (no cap applied here).

        The Limited PF wage cap is applied by the caller (get_statutory_components)
        based on the pf_type selected on the Salary Structure Assignment:
            - Limited PF  → wage capped at pf_wage_limit from Company
            - Full PF     → no cap, full computed wage basis used

        Common configurations:
            [Basic, Dearness Allowance]      → Basic + DA
            [Gross]                          → full gross
            [Basic, DA, Special Allowance]   → Basic + DA + Special Allowance

        :param salary_components: dict of {component_name: amount}.
        :return: raw wage basis as float, clamped to 0. No cap applied.
        """
        components = self._get_child_components("pf_dependent_component")
        if not components:
            return 0.0

        result = sum(
            self._resolve_component_value(comp, salary_components)
            for comp in components
        )

        return max(result, 0.0)

    # ──────────────────────────────────────────────
    # Public config helpers for payroll
    # ──────────────────────────────────────────────

    def get_salary_calculation_method(self) -> str:
        """
        Returns the payroll calculation method for this company.
        Used by attendance/payment-days logic.

        Returns:
            "Exclude Weekly Offs" — payment days = working days − weekly offs − absences
            "Include Weekly Offs" — payment days = calendar days − absences
        """
        val = self.salary_calculation_based_on or ""
        if "Include" in val:
            return "Include Weekly Offs"
        return "Exclude Weekly Offs"

    def get_esic_config(self):
        """
        Returns the full ESIC config for payroll processing.
        wage_basis_mode = 'subtract'
            ESIC wage = first component − rest, capped at esic_wage_limit.
        """
        components = self._get_child_components("esic_dependent_component")
        if not components:
            return None
        return {
            "is_applicable":    True,
            "wage_basis_mode":  "subtract",
            "wage_components":  components,
            "wage_limit":       self.esic_wage_limit or None,
            "employee_percent": self.esic_employee_contribution or 0,
            "employer_percent": self.esic_employer_contribution or 0,
        }

    def get_pf_config(self):
        """
        Returns the full PF config for payroll processing.
        wage_basis_mode = 'sum'
            PF wage = sum of all components, capped at pf_wage_limit.
        """
        components = self._get_child_components("pf_dependent_component")
        if not components:
            return None
        return {
            "is_applicable":    True,
            "wage_basis_mode":  "sum",
            "wage_components":  components,
            "wage_limit":       self.pf_wage_limit or None,
            "employee_percent": self.pf_employee_percent or 0,
            "employer_eps":     self.pf_employer_eps or 0,
            "employer_epf":     self.pf_employer_epf or 0,
            "edli_insurance":   self.pf_edli_insurance or 0,
            "admin_charges":    self.pf_admin_charges or 0,
        }