import frappe
from frappe.model.document import Document
from frappe.utils import flt


class SalaryComponent(Document):

    def validate(self):
        self._validate_calculation_flags()
        self._validate_esic_pf_flags()

    def on_update(self):
        self._sync_flags_to_salary_details()

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_calculation_flags(self):
        active_flags = [
            bool(self.is_daily_rate),
            bool(self.depends_on_payment_days),
            bool(self.depends_on_physical_working_days),
        ]
        if sum(active_flags) > 1:
            frappe.throw(
                "Only one calculation mode can be enabled at a time. "
                "Please check only one of: <b>Is Daily Rate Component</b>, "
                "<b>Depends on Payment Days</b>, or "
                "<b>Depends on Physical Working Days</b>."
            )

    def _validate_esic_pf_flags(self):
        if self.is_esic_component:
            if not self.esic_calculation_based_on:
                frappe.throw("Please select <b>ESIC Calculation Based On</b> when ESIC component is enabled.")
            if not self.esic_percentage or flt(self.esic_percentage) <= 0:
                frappe.throw("Please enter a valid <b>ESIC Percentage</b> greater than 0.")
            if flt(self.esic_percentage) > 100:
                frappe.throw("<b>ESIC Percentage</b> cannot exceed 100%.")
            if self.esic_cap_amount and flt(self.esic_cap_amount) < 0:
                frappe.throw("<b>ESIC Cap Amount</b> cannot be negative.")

        if self.is_pf_component:
            if not self.pf_calculation_based_on:
                frappe.throw("Please select <b>PF Calculation Based On</b> when PF component is enabled.")
            if not self.pf_percentage or flt(self.pf_percentage) <= 0:
                frappe.throw("Please enter a valid <b>PF Percentage</b> greater than 0.")
            if flt(self.pf_percentage) > 100:
                frappe.throw("<b>PF Percentage</b> cannot exceed 100%.")
            if self.pf_cap_amount and flt(self.pf_cap_amount) < 0:
                frappe.throw("<b>PF Cap Amount</b> cannot be negative.")

    # ------------------------------------------------------------------
    # Sync to child tables
    # ------------------------------------------------------------------

    def _sync_flags_to_salary_details(self):
        """Push updated flags to every Salary Details row referencing this component."""
        try:
            existing_columns = frappe.db.get_table_columns("Salary Details")
        except Exception:
            return

        required_columns = {"is_daily_rate", "depends_on_payment_days", "depends_on_physical_working_days"}
        if not required_columns.issubset(set(existing_columns)):
            return

        update_fields = {
            "depends_on_payment_days":          self.depends_on_payment_days or 0,
            "is_daily_rate":                    self.is_daily_rate or 0,
            "depends_on_physical_working_days": self.depends_on_physical_working_days or 0,
        }

        optional_fields = {
            "is_esic_component":          self.is_esic_component or 0,
            "esic_calculation_based_on":  self.esic_calculation_based_on or "",
            "esic_percentage":            flt(self.esic_percentage),
            "esic_cap_amount":            flt(self.esic_cap_amount),
            "is_pf_component":            self.is_pf_component or 0,
            "pf_calculation_based_on":    self.pf_calculation_based_on or "",
            "pf_percentage":              flt(self.pf_percentage),
            "pf_cap_amount":              flt(self.pf_cap_amount),
            "is_pt_component":            self.is_pt_component or 0,
        }
        for col, val in optional_fields.items():
            if col in existing_columns:
                update_fields[col] = val

        frappe.db.set_value(
            "Salary Details",
            {"salary_component": self.salary_component},
            update_fields
        )