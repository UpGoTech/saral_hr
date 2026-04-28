import frappe
import calendar
from datetime import datetime
from frappe.model.document import Document
from frappe.utils import getdate, get_last_day


class EmployeeLoanAdvance(Document):

    def on_update_after_submit(self):
        if self.type == "Loan":
            self.validate_schedule_total()
            self.calculate_outstanding()
            self.sync_tenure_from_schedule() 
            self.validate_only_changed_rows()
        else:
            self.validate_only_changed_rows()

    def is_submittable(self):
        return True

    def is_allow_on_submit(self):
        return True

    def autoname(self):
        prefix = f"{self.employee}-{self.type}-"

        last = frappe.db.sql(
            """
            SELECT name FROM `tabEmployee Loan Advance`
            WHERE name LIKE %s
            ORDER BY CAST(SUBSTRING_INDEX(name, '-', -1) AS UNSIGNED) DESC
            LIMIT 1
            """,
            (prefix + "%",),
            as_dict=True
        )

        if last:
            try:
                last_num = int(last[0]["name"].split("-")[-1])
            except (ValueError, IndexError):
                last_num = 0
        else:
            last_num = 0

        self.name = f"{prefix}{str(last_num + 1).zfill(4)}"
    def validate(self):
        self.validate_only_changed_rows()

        if self.type == "Loan":
            self.calculate_outstanding()
            self.validate_schedule_total()
            # ✅ Auto-update tenure from actual schedule row count
            self.sync_tenure_from_schedule()

    def sync_tenure_from_schedule(self):
        """Count valid schedule rows and update tenure_months to match."""
        if not self.schedule:
            return
        valid_rows = [row for row in self.schedule if row.month and row.month.strip()]
        count = len(valid_rows)
        if count and self.tenure_months != count:
            # ✅ Use db.set_value to bypass Frappe's submit lock on parent fields
            frappe.db.set_value(
                "Employee Loan Advance",
                self.name,
                "tenure_months",
                count,
                update_modified=False
            )
            self.tenure_months = count  # keep in-memory object in sync

    def on_submit(self):
        pass

    def on_cancel(self):
        if self.type == "Loan" and self.schedule:
            for row in self.schedule:
                frappe.db.set_value(
                    "Employee Loan Advance Schedule",
                    row.name,
                    {"is_deducted": 0, "is_deferred": 0, "deferred_to": ""},
                    update_modified=False
                )
        elif self.type == "Advance":
            frappe.db.set_value(
                "Employee Loan Advance",
                self.name,
                "is_deducted", 0,
                update_modified=False
            )

    # ------------------------------------------------------------------ #
    #  Calculations                                                        #
    # ------------------------------------------------------------------ #

    def calculate_outstanding(self):
        if not self.schedule:
            self.outstanding_amount = self.amount
            self.total_deducted = 0
            return
        total_deducted = sum(
            row.deduction_amount for row in self.schedule if row.is_deducted
        )
        self.total_deducted = total_deducted
        self.outstanding_amount = self.amount - total_deducted

    def validate_schedule_total(self):
        if not self.schedule:
            return
        valid_rows = [row for row in self.schedule if row.month and row.month.strip()]
        if not valid_rows:
            return
        total = round(sum(row.deduction_amount for row in valid_rows), 2)
        loan_amount = round(self.amount, 2)
        if total > loan_amount:
            frappe.throw(
                f"Installments total ₹{total}, but loan is only ₹{loan_amount}. "
                f"Reduce amounts so they match the loan.",
                title="Total Exceeds Loan"
            )
        elif abs(total - loan_amount) > 0.01:
            frappe.throw(
                f"Installments total ₹{total}, loan is ₹{loan_amount}. "
                f"Adjust amounts to match.",
                title="Total Mismatch"
            )

    # ------------------------------------------------------------------ #
    #  Salary Slip Validation                                              #
    # ------------------------------------------------------------------ #

    def validate_only_changed_rows(self):
        # ✅ Fixed indentation bug — was breaking the entire method
        if not self.employee:
            return

        if self.type == "Loan":
            for row in (self.schedule or []):
                if not row.month:
                    continue

                # ✅ Only block if THIS ROW is being marked as deducted
                #    AND a salary slip already exists for that month.
                #    Deferral (is_deferred / deferred_to) is always allowed.
                if row.is_deducted:
                    slip = _get_submitted_slip_for_month(self.employee, row.month)
                    if slip:
                        # Row is being deducted and slip exists — that's fine,
                        # it means the slip itself triggered the deduction.
                        # We only want to BLOCK manual edits to deduction_amount
                        # on already-deducted rows, which is handled in JS.
                        pass

                # ✅ Block changing deduction_amount on an already-deducted row
                #    by checking the saved (DB) value vs the current value.
                if row.is_deducted:
                    db_amount = frappe.db.get_value(
                        "Employee Loan Advance Schedule", row.name, "deduction_amount"
                    )
                    if db_amount is not None and abs((db_amount or 0) - (row.deduction_amount or 0)) > 0.01:
                        frappe.throw(
                            f"Row <b>{row.idx}</b>: Cannot change deduction amount for "
                            f"<b>{row.month}</b> — it is already deducted via Salary Slip. "
                            f"Cancel the Salary Slip first.",
                            title="Edit Not Allowed"
                        )

        elif self.type == "Advance":
            if not self.date:
                return
            d = getdate(self.date)
            month_start = d.strftime("%Y-%m-01")
            month_end = str(get_last_day(d))
            slip = frappe.db.get_value(
                "Salary Slip",
                {
                    "employee": self.employee,
                    "docstatus": 1,
                    "start_date": ["between", [month_start, month_end]]
                },
                "name"
            )
            if slip and self.is_deducted:
                frappe.throw(
                    f"Salary Slip <b>{slip}</b> for this employee is already submitted.<br><br>"
                    f"Please <b>cancel Salary Slip {slip}</b> first, then try again.",
                    title="Salary Slip Already Submitted"
                )


# ================================================================== #
#  Whitelisted API                                                    #
# ================================================================== #

@frappe.whitelist()
def get_submitted_slip_for_month(employee, month_name):
    return _get_submitted_slip_for_month(employee, month_name)


def _get_submitted_slip_for_month(employee, month_name):
    try:
        dt = datetime.strptime(month_name, "%B %Y")
        month_start = dt.strftime("%Y-%m-01")
        last_day = calendar.monthrange(dt.year, dt.month)[1]
        month_end = dt.strftime(f"%Y-%m-{last_day}")
    except Exception:
        return None

    return frappe.db.get_value(
        "Salary Slip",
        {
            "employee": employee,
            "docstatus": 1,
            "start_date": ["between", [month_start, month_end]],
        },
        "name"
    )