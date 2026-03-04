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

        frappe.db.set_value(
            "Salary Details",
            {"salary_component": self.salary_component},
            {
                "depends_on_payment_days":          self.depends_on_payment_days or 0,
                "is_daily_rate":                    self.is_daily_rate or 0,
                "depends_on_physical_working_days": self.depends_on_physical_working_days or 0,
            }
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