# Copyright (c) 2026, sj and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

MONTHS = [
    "January", "February", "March", "April",
    "May", "June", "July", "August",
    "September", "October", "November", "December"
]


class SalaryComponent(Document):

    def validate(self):
        self._validate_calculation_flags()
        self._populate_monthly_amounts()

    def on_update(self):
        self._sync_flags_to_salary_details()

    # ──────────────────────────────────────────────
    # Validation
    # ──────────────────────────────────────────────

    def _validate_calculation_flags(self):
        """Only one payment-day calculation mode may be active at a time."""
        if self.depends_on_payment_days and self.depends_on_physical_working_days:
            frappe.throw(
                "Only one calculation mode can be enabled at a time. "
                "Please check only one of: <b>Depends on Payment Days</b> or "
                "<b>Depends on Physical Working Days</b>."
            )

    # ──────────────────────────────────────────────
    # Monthly amounts — ensure all 12 months exist
    # in correct Jan→Dec order when special component
    # ──────────────────────────────────────────────

    def _populate_monthly_amounts(self):
        if not self.is_special_component:
            # Clear rows if the flag is turned off
            self.monthly_amounts = []
            return

        # Build a map of existing rows keyed by month name
        existing = {row.month: row for row in (self.monthly_amounts or [])}

        # Rebuild the table in strict Jan→Dec order,
        # preserving any amounts the user has already entered
        self.monthly_amounts = []
        for month in MONTHS:
            row = self.append("monthly_amounts", {
                "month":  month,
                "amount": existing[month].amount if month in existing else 0,
            })

    # ──────────────────────────────────────────────
    # Helpers — public accessor for payroll
    # ──────────────────────────────────────────────

    def get_amount_for_month(self, month_name: str) -> float:
        """
        Return the configured amount for a given month name.
        Used during payroll to fetch the correct monthly value.

        :param month_name: e.g. 'March'
        :return: float amount (0.0 if not found)
        """
        if not self.is_special_component:
            return 0.0
        for row in (self.monthly_amounts or []):
            if row.month == month_name:
                return float(row.amount or 0)
        return 0.0

    # ──────────────────────────────────────────────
    # Sync to Salary Details child rows
    # ──────────────────────────────────────────────

    def _sync_flags_to_salary_details(self):
        """Push updated payment-day flags to every Salary Details row
        that references this component."""
        try:
            existing_columns = set(frappe.db.get_table_columns("Salary Details"))
        except Exception:
            return

        required = {"depends_on_payment_days", "depends_on_physical_working_days"}
        if not required.issubset(existing_columns):
            return

        frappe.db.set_value(
            "Salary Details",
            {"salary_component": self.salary_component},
            {
                "depends_on_payment_days":          self.depends_on_payment_days or 0,
                "depends_on_physical_working_days": self.depends_on_physical_working_days or 0,
            }
        )