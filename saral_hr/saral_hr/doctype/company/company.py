# Copyright (c) 2026, sj and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

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
        if comp == "Gross":
            if "Gross" in salary_components:
                return float(salary_components["Gross"])
            return float(sum(
                v for k, v in salary_components.items()
                if k not in VIRTUAL_COMPONENTS and not k.startswith("_")
            ))
        if comp == "Gross Including Additional Salary":
            if "Gross Including Additional Salary" in salary_components:
                return float(salary_components["Gross Including Additional Salary"])
            gross = float(sum(
                v for k, v in salary_components.items()
                if k not in VIRTUAL_COMPONENTS and not k.startswith("_")
            ))
            return gross + float(salary_components.get("_additional_salary", 0.0))
        return float(salary_components.get(comp, 0.0))

    # ──────────────────────────────────────────────
    # Wage basis calculators
    # ──────────────────────────────────────────────

    def compute_esic_wage_basis(self, salary_components: dict) -> float:
        """Sum ALL listed ESIC components — NO CAP (esic_wage_limit is display only)."""
        components = self._get_child_components("esic_dependent_component")
        if not components:
            return 0.0
        return max(
            sum(self._resolve_component_value(c, salary_components) for c in components),
            0.0
        )

    def compute_pf_wage_basis(self, salary_components: dict) -> float:
        """Sum ALL listed PF components — cap applied by caller for Limited PF."""
        components = self._get_child_components("pf_dependent_component")
        if not components:
            return 0.0
        return max(
            sum(self._resolve_component_value(c, salary_components) for c in components),
            0.0
        )

    # ──────────────────────────────────────────────
    # Public config helpers for payroll
    # ──────────────────────────────────────────────

    def get_salary_calculation_method(self) -> str:
        val = self.salary_calculation_based_on or ""
        if "Include" in val:
            return "Include Weekly Offs"
        return "Exclude Weekly Offs"

    def get_esic_config(self):
        components = self._get_child_components("esic_dependent_component")
        if not components:
            return None
        return {
            "is_applicable":    True,
            "wage_components":  components,
            "wage_limit":       self.esic_wage_limit or None,
            "employee_percent": self.esic_employee_contribution or 0,
            "employer_percent": self.esic_employer_contribution or 0,
        }

    def get_pf_config(self):
        components = self._get_child_components("pf_dependent_component")
        if not components:
            return None
        return {
            "is_applicable":    True,
            "wage_components":  components,
            "wage_limit":       self.pf_wage_limit or None,
            "employee_percent": self.pf_employee_percent or 0,
            "employer_eps":     self.pf_employer_eps or 0,
            "employer_epf":     self.pf_employer_epf or 0,
            "edli_insurance":   self.pf_edli_insurance or 0,
            "admin_charges":    self.pf_admin_charges or 0,
        }