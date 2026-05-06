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
    # ──────────────────────────────────────────────

    def _populate_monthly_amounts(self):
        if not self.is_special_component:
            self.monthly_amounts = []
            return

        existing = {row.month: row for row in (self.monthly_amounts or [])}
        self.monthly_amounts = []
        for month in MONTHS:
            self.append("monthly_amounts", {
                "month":  month,
                "amount": existing[month].amount if month in existing else 0,
            })

    # ──────────────────────────────────────────────
    # Helpers — public accessor for payroll
    # ──────────────────────────────────────────────

    def get_amount_for_month(self, month_name: str) -> float:
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
        """Push updated payment-day flags, daily_wage_component flag,
        and exclude_from_ctc flag to every Salary Details row that
        references this component."""
        try:
            existing_columns = set(frappe.db.get_table_columns("tabSalary Details"))
        except Exception:
            return

        updates = {}

        if {"depends_on_payment_days", "depends_on_physical_working_days"}.issubset(existing_columns):
            updates["depends_on_payment_days"]          = self.depends_on_payment_days or 0
            updates["depends_on_physical_working_days"] = self.depends_on_physical_working_days or 0

        if "daily_wage_component" in existing_columns:
            updates["daily_wage_component"] = self.daily_wage_component or 0

        if "exclude_from_ctc" in existing_columns:
            updates["exclude_from_ctc"] = self.exclude_from_ctc or 0

        if not updates:
            return

        frappe.db.set_value(
            "Salary Details",
            {"salary_component": self.salary_component},
            updates
        )