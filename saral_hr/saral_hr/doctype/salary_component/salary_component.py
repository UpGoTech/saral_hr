import frappe
from frappe.model.document import Document
from frappe.utils import flt
from frappe import generate_hash

MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]


class SalaryComponent(Document):

    def validate(self):
        self._validate_calculation_flags()
        self._validate_esic_pf_flags()
        if self.is_special_component:
            self._rebuild_month_table()
        else:
            self.enter_amount_according_to_months = []

    def on_update(self):
        self._sync_flags_to_salary_details()

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_calculation_flags(self):
        """
        Only one of the three calculation modes may be active at a time:
          - depends_on_payment_days
          - is_daily_rate
          - depends_on_physical_working_days
        """
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
        """Validate ESIC and PF component configuration."""

        # ESIC validations
        if self.is_esic_component:
            if not self.esic_calculation_based_on:
                frappe.throw(
                    "Please select <b>ESIC Calculation Based On</b> when ESIC component is enabled."
                )
            if not self.esic_percentage or flt(self.esic_percentage) <= 0:
                frappe.throw(
                    "Please enter a valid <b>ESIC Percentage</b> greater than 0."
                )
            if flt(self.esic_percentage) > 100:
                frappe.throw(
                    "<b>ESIC Percentage</b> cannot exceed 100%."
                )

        # PF validations
        if self.is_pf_component:
            if not self.pf_calculation_based_on:
                frappe.throw(
                    "Please select <b>PF Calculation Based On</b> when PF component is enabled."
                )
            if not self.pf_percentage or flt(self.pf_percentage) <= 0:
                frappe.throw(
                    "Please enter a valid <b>PF Percentage</b> greater than 0."
                )
            if flt(self.pf_percentage) > 100:
                frappe.throw(
                    "<b>PF Percentage</b> cannot exceed 100%."
                )
            # cap amount must be positive if provided
            if self.pf_cap_amount and flt(self.pf_cap_amount) < 0:
                frappe.throw("<b>PF Cap Amount</b> cannot be negative.")

        # ESIC cap must be positive if provided
        if self.is_esic_component and self.esic_cap_amount and flt(self.esic_cap_amount) < 0:
            frappe.throw("<b>ESIC Cap Amount</b> cannot be negative.")

    # ------------------------------------------------------------------
    # Sync to child tables
    # ------------------------------------------------------------------

    def _sync_flags_to_salary_details(self):
        """
        Push updated calculation flags to every Salary Details row
        (in Salary Structure, Salary Structure Assignment, and Salary Slip)
        that references this component.

        Skips gracefully during migrate if the columns don't exist yet on
        the Salary Details table (prevents IntegrityError: Column cannot be null).
        """
        try:
            existing_columns = frappe.db.get_table_columns("Salary Details")
        except Exception:
            return

        required_columns = {
            "is_daily_rate",
            "depends_on_payment_days",
            "depends_on_physical_working_days",
        }
        if not required_columns.issubset(set(existing_columns)):
            return

        update_fields = {
            "depends_on_payment_days":          self.depends_on_payment_days or 0,
            "is_daily_rate":                    self.is_daily_rate or 0,
            "depends_on_physical_working_days": self.depends_on_physical_working_days or 0,
        }

        # Sync ESIC / PF flags if columns exist
        optional_fields = {
            "is_esic_component":          self.is_esic_component or 0,
            "esic_calculation_based_on":  self.esic_calculation_based_on or "",
            "esic_percentage":            flt(self.esic_percentage),
            "esic_cap_amount":            flt(self.esic_cap_amount),
            "is_pf_component":            self.is_pf_component or 0,
            "pf_calculation_based_on":    self.pf_calculation_based_on or "",
            "pf_percentage":              flt(self.pf_percentage),
            "pf_cap_amount":              flt(self.pf_cap_amount),
        }
        for col, val in optional_fields.items():
            if col in existing_columns:
                update_fields[col] = val

        frappe.db.set_value(
            "Salary Details",
            {"salary_component": self.salary_component},
            update_fields
        )

    # ------------------------------------------------------------------
    # Special Component — month table
    # ------------------------------------------------------------------

    def _rebuild_month_table(self):
        # Step 1: preserve any amounts the user already typed
        existing = {}
        for row in (self.enter_amount_according_to_months or []):
            if row.month and row.month not in existing:
                existing[row.month] = flt(row.amount)

        # Step 2: wipe via raw SQL so there are zero stale rows in DB
        if not self.is_new():
            frappe.db.sql("""
                DELETE FROM `tabSpecial Salary Component`
                WHERE parent = %s
            """, self.name)

        # Step 3: rebuild exactly 12 rows with guaranteed-unique names
        self.enter_amount_according_to_months = []
        for idx, month in enumerate(MONTHS, start=1):
            child_name = f"{self.name}-{month}-{generate_hash(length=6)}"
            self.append("enter_amount_according_to_months", {
                "name":   child_name,
                "month":  month,
                "amount": existing.get(month, 0.0),
                "idx":    idx,
            })