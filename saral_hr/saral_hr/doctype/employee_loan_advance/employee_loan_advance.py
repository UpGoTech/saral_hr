import frappe
import calendar
from datetime import datetime
from frappe.model.document import Document
from frappe.utils import getdate, get_last_day


class EmployeeLoanAdvance(Document):

    def autoname(self):
        """
        Build name as:  {employee}-{type}-{padded_counter}
        Example:  EMP-001-Loan-0001  |  EMP-001-Advance-0001

        We query the highest existing counter for this employee+type
        combination and increment it, avoiding Frappe's naming series
        parser which cannot substitute two runtime fields cleanly.
        """
        prefix = f"{self.employee}-{self.type}-"

        last = frappe.db.sql(
            """
            SELECT name FROM `tabEmployee Loan Advance`
            WHERE name LIKE %s
            ORDER BY name DESC
            LIMIT 1
            """,
            (prefix + "%",),
            as_dict=True
        )

        if last:
            try:
                last_num = int(last[0].name.replace(prefix, ""))
            except (ValueError, IndexError):
                last_num = 0
        else:
            last_num = 0

        self.name = f"{prefix}{str(last_num + 1).zfill(4)}"

    def validate(self):
        """
        Runs before every save.

        Key change from previous version:
          - validate_no_submitted_salary_slip() now only blocks saving if the
            user is trying to CHANGE a row whose Salary Slip is submitted.
            Rows that are unchanged (is_deducted = 1) are simply skipped —
            they no longer trigger the error on every save.
          - This prevents the "double message" situation where the Python
            validator and the JS handler both fired for the same row.
        """
        self.validate_only_changed_rows()

        if self.type in ("Loan-I", "Loan-II", "Loan"):
            self.calculate_outstanding()
            self.validate_schedule_total()

    def on_submit(self):
        pass  # Document becomes read-only after submit (enforced by Frappe)

    def on_cancel(self):
        """
        Reset all deduction/deferral flags on cancel.
        Uses frappe.db.set_value directly because self.save() cannot be called
        on a cancelled document.
        """
        if self.type in ("Loan-I", "Loan-II", "Loan") and self.schedule:
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
        total = sum(row.deduction_amount for row in self.schedule)
        if abs(round(total, 2) - round(self.amount, 2)) > 0.01:
            frappe.throw(
                f"Schedule total ₹{round(total, 2)} does not match "
                f"Loan Amount ₹{round(self.amount, 2)}. "
                f"Please regenerate the schedule."
            )

    # ------------------------------------------------------------------ #
    #  Salary Slip Validation — per-row, only for changed rows            #
    # ------------------------------------------------------------------ #

    def validate_only_changed_rows(self):
        """
        Blocks saving ONLY if the user is modifying a schedule row for a month
        whose Salary Slip is already submitted.

        Rows where is_deducted = 1 are SKIPPED entirely here — they are
        already locked in the UI by lock_protected_rows() in the client script.
        Attempting to re-validate them on every save was causing the double
        message problem (Python threw an error PLUS JS showed its own message).

        Logic:
          - For Loan: loop through schedule rows where is_deducted = 0
            (i.e., not yet deducted) and check if a submitted Salary Slip exists.
            If yes, the user should not be modifying this row — throw an error.
          - For Advance: check the month of the advance date field.
        """
        if not self.employee:
            return

        if self.type in ("Loan-I", "Loan-II", "Loan"):
            for row in (self.schedule or []):
                # Skip rows that are already marked as deducted — they are
                # locked in the UI and should not trigger validation errors.
                if row.is_deducted:
                    continue

                if not row.month:
                    continue

                slip = _get_submitted_slip_for_month(self.employee, row.month)
                if slip:
                    frappe.throw(
                        f"Salary Slip <b>{slip}</b> for <b>{row.month}</b> is already submitted.<br><br>"
                        f"You cannot modify this installment. "
                        f"Please <b>cancel Salary Slip {slip}</b> first, then try again.",
                        title="Salary Slip Already Submitted"
                    )

        elif self.type == "Advance":
            if not self.date:
                return
            d           = getdate(self.date)
            month_start = d.strftime("%Y-%m-01")
            month_end   = str(get_last_day(d))
            slip = frappe.db.get_value(
                "Salary Slip",
                {"employee": self.employee, "docstatus": 1, "start_date": ["between", [month_start, month_end]]},
                "name"
            )
            if slip:
                frappe.throw(
                    f"Salary Slip <b>{slip}</b> for this employee is already submitted.<br><br>"
                    f"Please <b>cancel Salary Slip {slip}</b> first, then try again.",
                    title="Salary Slip Already Submitted"
                )


# ================================================================== #
#  Whitelisted API — Called from the JS client script                #
# ================================================================== #

@frappe.whitelist()
def get_submitted_slip_for_month(employee, month_name):
    """
    Returns the name of a submitted Salary Slip for the given employee and
    month (e.g. "January 2026"), or None if none exists.

    Called from the JS check_salary_slip_for_month() function.
    This is the SINGLE place that checks for submitted slips from the client,
    so the message is shown exactly once.

    Args:
        employee  (str): Employee ID
        month_name (str): Month string like "January 2026"

    Returns:
        str | None: Salary Slip name if found, else None
    """
    return _get_submitted_slip_for_month(employee, month_name)


# ------------------------------------------------------------------ #
#  Internal Helper                                                    #
# ------------------------------------------------------------------ #

def _get_submitted_slip_for_month(employee, month_name):
    """
    Shared internal function used by both the whitelisted API and the
    validate() method so the date-parsing logic is never duplicated.

    Parses "January 2026" → date range → queries Salary Slip.

    Returns:
        str | None: Salary Slip name if a submitted slip exists, else None
    """
    try:
        dt          = datetime.strptime(month_name, "%B %Y")
        month_start = dt.strftime("%Y-%m-01")
        last_day    = calendar.monthrange(dt.year, dt.month)[1]
        month_end   = dt.strftime(f"%Y-%m-{last_day}")
    except Exception:
        return None

    return frappe.db.get_value(
        "Salary Slip",
        {
            "employee":   employee,
            "docstatus":  1,   # 1 = Submitted
            "start_date": ["between", [month_start, month_end]],
        },
        "name"
    )