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

    def _validate_calculation_flags(self):
        if self.is_daily_rate and self.depends_on_payment_days:
            frappe.throw(
                "A component cannot have both <b>Is Daily Rate Component</b> and "
                "<b>Depends on Payment Days</b> checked at the same time. "
                "Please enable only one."
            )

    def _sync_flags_to_salary_details(self):
        """
        Push updated depends_on_payment_days and is_daily_rate to every
        Salary Details row (in Salary Structure, Salary Structure Assignment,
        and Salary Slip) that references this component.

        Skips gracefully during migrate if the columns don't exist yet on
        the Salary Details table (prevents IntegrityError: Column cannot be null).
        """
        try:
            existing_columns = frappe.db.get_table_columns("Salary Details")
        except Exception:
            return

        if "is_daily_rate" not in existing_columns or "depends_on_payment_days" not in existing_columns:
            return

        frappe.db.set_value(
            "Salary Details",
            {"salary_component": self.salary_component},
            {
                "depends_on_payment_days": self.depends_on_payment_days or 0,
                "is_daily_rate":           self.is_daily_rate or 0,
            }
        )

    def _rebuild_month_table(self):
        # Step 1: preserve any amounts the user typed
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
            row = self.append("enter_amount_according_to_months", {
                "name":   child_name,
                "month":  month,
                "amount": existing.get(month, 0.0),
                "idx":    idx,
            })