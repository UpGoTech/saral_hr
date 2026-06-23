# Copyright (c) 2026, sj and contributors
# For license information, please see license.txt

import json
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate

VIRTUAL_COMPONENTS = {"Gross", "Gross Including Additional Salary"}


class Company(Document):

    def validate(self):
        self.validate_esic_settings()
        self.validate_pf_settings()
        self._validate_locked_periods(
            "esic_dependent_component", "ESIC",
            ["wage_components", "esic_wage_limit", "employee_contribution", "employer_contribution"]
        )
        self._validate_locked_periods(
            "pf_dependent_component", "PF",
            ["wage_components", "pf_wage_limit", "employee_percent",
             "employer_epf", "employer_eps", "edli_insurance", "admin_charges"]
        )

    def on_update(self):
        pass

    # ──────────────────────────────────────────────
    # Validate
    # ──────────────────────────────────────────────

    def validate_esic_settings(self):
        for row in (self.get("esic_dependent_component") or []):
            comps = self._parse_components(row)
            if comps:
                self._validate_components(comps, "ESIC")
            for field, lbl in [
                ("esic_wage_limit",      "ESIC Wage Limit"),
                ("employee_contribution","Employee Contribution %"),
                ("employer_contribution","Employer Contribution %"),
            ]:
                if flt(row.get(field)) < 0:
                    frappe.throw(_("ESIC {0} cannot be negative (row {1}).").format(lbl, row.idx))

    def validate_pf_settings(self):
        for row in (self.get("pf_dependent_component") or []):
            comps = self._parse_components(row)
            if comps:
                self._validate_components(comps, "PF")
            for field, lbl in [
                ("pf_wage_limit",   "PF Wage Limit"),
                ("employee_percent","Employee PF %"),
                ("employer_epf",    "Employer EPF %"),
                ("employer_eps",    "Employer EPS %"),
                ("edli_insurance",  "EDLI Insurance %"),
                ("admin_charges",   "Admin Charges %"),
            ]:
                if flt(row.get(field)) < 0:
                    frappe.throw(_("PF {0} cannot be negative (row {1}).").format(lbl, row.idx))

    # ──────────────────────────────────────────────
    # Lock validation — SSA exists → cannot edit period
    # ──────────────────────────────────────────────

    def _validate_locked_periods(self, table_fieldname, label, protected_fields):
        """If a submitted Salary Structure Assignment exists for a period,
        block edits to components and rate fields."""
        old_doc = self.get_doc_before_save()
        if not old_doc:
            return  # new doc — nothing to compare

        old_rows = {
            row.name: row
            for row in (old_doc.get(table_fieldname) or [])
            if row.name
        }

        for row in (self.get(table_fieldname) or []):
            if not row.name or row.name not in old_rows:
                continue  # newly added row — allowed

            if not self._period_has_ssa(row.from_date, row.to_date):
                continue  # no SSA for this period — editable

            old_row = old_rows[row.name]
            for field in protected_fields:
                old_val = str(old_row.get(field) or "")
                new_val = str(row.get(field) or "")
                # For floats compare numerically to avoid "0" vs "0.0" false positives
                try:
                    changed = flt(old_val) != flt(new_val)
                except Exception:
                    changed = old_val != new_val

                if changed:
                    period_str = "{0} → {1}".format(
                        row.from_date or "open", row.to_date or "open"
                    )
                    frappe.throw(
                        _("{0} period <b>{1}</b>: Cannot edit — "
                          "Salary Structure Assignment already exists for this period.")
                        .format(label, period_str)
                    )

    def _period_has_ssa(self, from_date, to_date) -> bool:
        """Return True if any submitted SSA's from_date falls within [from_date, to_date]."""
        filters = {"company": self.name, "docstatus": 1}
        if from_date and to_date:
            filters["from_date"] = ["between", [from_date, to_date]]
        elif from_date:
            filters["from_date"] = [">=", from_date]
        elif to_date:
            filters["from_date"] = ["<=", to_date]
        return bool(frappe.db.exists("Salary Structure Assignment", filters))

    # ──────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────

    def _parse_components(self, row) -> list:
        raw = row.get("wage_components") if row else None
        if not raw:
            return []
        try:
            result = json.loads(raw)
            return result if isinstance(result, list) else []
        except (json.JSONDecodeError, TypeError, ValueError):
            return []

    def _get_matching_row(self, table_fieldname: str, period_date=None):
        """Return first row whose date range covers period_date. None if no match."""
        for row in (self.get(table_fieldname) or []):
            if not period_date:
                return row   # validate time — just return first
            if not row.from_date and not row.to_date:
                return row   # always active
            from_ok = (not row.from_date) or (getdate(row.from_date) <= getdate(period_date))
            to_ok   = (not row.to_date)   or (getdate(row.to_date)   >= getdate(period_date))
            if from_ok and to_ok:
                return row
        return None

    def _validate_components(self, components: list, label_prefix: str):
        for comp in components:
            if comp in VIRTUAL_COMPONENTS:
                continue
            comp_type = frappe.db.get_value("Salary Component", comp, "type")
            if not comp_type:
                frappe.throw(_("{0} Wage Component <b>{1}</b> does not exist.").format(label_prefix, comp))
            if comp_type != "Earning":
                frappe.throw(_("{0} Wage Component <b>{1}</b> must be of type Earning.").format(label_prefix, comp))

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

    def compute_esic_wage_basis(self, salary_components: dict, period_date=None) -> float:
        row = self._get_matching_row("esic_dependent_component", period_date)
        if not row:
            return 0.0
        components = self._parse_components(row)
        if not components:
            return 0.0
        return max(sum(self._resolve_component_value(c, salary_components) for c in components), 0.0)

    def compute_pf_wage_basis(self, salary_components: dict, period_date=None) -> float:
        row = self._get_matching_row("pf_dependent_component", period_date)
        if not row:
            return 0.0
        components = self._parse_components(row)
        if not components:
            return 0.0
        return max(sum(self._resolve_component_value(c, salary_components) for c in components), 0.0)

    # ──────────────────────────────────────────────
    # Public config helpers
    # ──────────────────────────────────────────────

    def get_salary_calculation_method(self) -> str:
        return "Include Weekly Offs" if "Include" in (self.salary_calculation_based_on or "") else "Exclude Weekly Offs"

    def get_esic_config(self, period_date=None):
        row = self._get_matching_row("esic_dependent_component", period_date)
        if not row:
            return None
        components = self._parse_components(row)
        if not components:
            return None
        return {
            "is_applicable":    True,
            "wage_components":  components,
            "wage_limit":       flt(row.esic_wage_limit) or None,
            "employee_percent": flt(row.employee_contribution) or 0,
            "employer_percent": flt(row.employer_contribution) or 0,
        }

    def get_pf_config(self, period_date=None):
        row = self._get_matching_row("pf_dependent_component", period_date)
        if not row:
            return None
        components = self._parse_components(row)
        if not components:
            return None
        return {
            "is_applicable":    True,
            "wage_components":  components,
            "wage_limit":       flt(row.pf_wage_limit) or None,
            "employee_percent": flt(row.employee_percent) or 0,
            "employer_eps":     flt(row.employer_eps) or 0,
            "employer_epf":     flt(row.employer_epf) or 0,
            "edli_insurance":   flt(row.edli_insurance) or 0,
            "admin_charges":    flt(row.admin_charges) or 0,
        }