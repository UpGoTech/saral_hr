# Copyright (c) 2026, sj and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt

MONTHS = [
    "January", "February", "March", "April",
    "May", "June", "July", "August",
    "September", "October", "November", "December"
]


@frappe.whitelist()
def is_percent_of_total_earning_locked(component_name: str) -> bool:
    """True when any non-cancelled SSA still references this component."""
    if not component_name:
        return False
    return bool(frappe.db.sql(
        """
        SELECT 1
        FROM `tabSalary Details` sd
        INNER JOIN `tabSalary Structure Assignment` ssa ON ssa.name = sd.parent
        WHERE sd.salary_component = %s
          AND sd.parenttype = 'Salary Structure Assignment'
          AND ssa.docstatus < 2
        LIMIT 1
        """,
        (component_name,),
    ))


class SalaryComponent(Document):

    def validate(self):
        self._validate_calculation_flags()
        self._validate_additional_only()
        self._validate_percent_of_total_earning()
        self._validate_percent_lock()
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

    def _validate_additional_only(self):
        if int(self.is_additional_only or 0) and int(self.is_special_component or 0):
            frappe.throw(
                "A component cannot be both <b>Is Special Component</b> and "
                "<b>Is Additional Only</b>."
            )

    def _validate_percent_of_total_earning(self):
        if not int(self.percent_on_total_earning or 0):
            self.percent_of_total_earning = 0
            return

        if (self.type or "") != "Deduction":
            frappe.throw(
                "<b>% on Total Earning</b> is only allowed for Deduction components."
            )

        pct = flt(self.percent_of_total_earning)
        if pct <= 0 or pct > 100:
            frappe.throw(
                "<b>Percent of Total Earning</b> must be greater than 0 and at most 100."
            )

        conflicts = []
        if int(self.depends_on_payment_days or 0):
            conflicts.append("Depends on Payment Days")
        if int(self.depends_on_physical_working_days or 0):
            conflicts.append("Depends on Physical Working Days")
        if int(self.daily_wage_component or 0):
            conflicts.append("Daily Wage Component")
        if int(self.is_special_component or 0):
            conflicts.append("Is Special Component")
        if int(self.is_additional_only or 0):
            conflicts.append("Is Additional Only")
        if int(self.employer_contribution or 0):
            conflicts.append("Employer Contribution")

        if conflicts:
            frappe.throw(
                "<b>% on Total Earning</b> cannot be combined with: "
                + ", ".join(f"<b>{c}</b>" for c in conflicts)
                + "."
            )

    def _validate_percent_lock(self):
        if self.is_new():
            return
        before = self.get_doc_before_save()
        if not before:
            return

        check_changed = int(before.percent_on_total_earning or 0) != int(
            self.percent_on_total_earning or 0
        )
        pct_changed = flt(before.percent_of_total_earning) != flt(
            self.percent_of_total_earning
        )
        if not (check_changed or pct_changed):
            return

        if is_percent_of_total_earning_locked(self.name):
            frappe.throw(
                "Cannot change <b>% on Total Earning</b> or the percent while this "
                "component is used on a Salary Structure Assignment. "
                "Cancel or delete those assignments first."
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
        exclude_from_ctc, and percent-of-earning fields to every Salary Details
        row that references this component."""
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

        if "percent_on_total_earning" in existing_columns:
            updates["percent_on_total_earning"] = self.percent_on_total_earning or 0

        if "percent_of_total_earning" in existing_columns:
            updates["percent_of_total_earning"] = (
                flt(self.percent_of_total_earning)
                if int(self.percent_on_total_earning or 0)
                else 0
            )

        if not updates:
            return

        frappe.db.set_value(
            "Salary Details",
            {"salary_component": self.salary_component},
            updates
        )
