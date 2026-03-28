import frappe
import calendar
from datetime import datetime
from frappe.model.document import Document
from frappe.model.naming import set_name_by_naming_series
from frappe.utils import getdate, get_last_day


class EmployeeLoanAdvance(Document):

    def autoname(self):
        """
        Set the naming series based on loan type before the first save.
        """
        type_map = {
            "Loan-I":  "ELA-LI-.employee.-.YYYY.-.###",
            "Loan-II": "ELA-LII-.employee.-.YYYY.-.###",
            "Advance": "ELA-ADV-.employee.-.YYYY.-.###"
        }
        self.naming_series = type_map.get(self.type, "ELA-LI-.employee.-.YYYY.-.###")
        set_name_by_naming_series(self)

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
        self.validate_duplicate_active_loan()  # ← NEW

        if self.type in ("Loan-I", "Loan-II"):
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
        if self.type in ("Loan-I", "Loan-II") and self.schedule:
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
          - For Loan-I / Loan-II: loop through schedule rows where is_deducted = 0
            (i.e., not yet deducted) and check if a submitted Salary Slip exists.
            If yes, the user should not be modifying this row — throw an error.
          - For Advance: check the month of the advance date field.
        """
        if not self.employee:
            return

        if self.type in ("Loan-I", "Loan-II"):
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

    # ------------------------------------------------------------------ #
    #  Duplicate Active Loan Validation — NEW                             #
    # ------------------------------------------------------------------ #

    def validate_duplicate_active_loan(self):
        """
        Blocks saving if the same employee already has an active loan
        of the same type (Loan-I, Loan-II, or Advance) that is not fully repaid.

        For Loan-I / Loan-II:
          - Checks the schedule table — if ANY row has is_deducted = 0,
            the loan is still active. Uses actual schedule months so it works
            correctly for Monthly, Bi-Monthly, and Quarterly installments
            with any start month/year.

        For Advance:
          - Checks the is_deducted flag on the parent document itself.

        Rule:
          - Same employee + same type → BLOCKED if previous loan not complete
          - Same employee + different type → ALLOWED
        """
        if not self.employee:
            return

        # Only block on new unsaved documents
        if self.docstatus != 0:
            return

        # ---------------------------------------------------------------- #
        #  Loan-I and Loan-II check                                         #
        # ---------------------------------------------------------------- #
        if self.type in ("Loan-I", "Loan-II"):

            existing_loans = frappe.get_all(
                "Employee Loan Advance",
                filters={
                    "employee": self.employee,
                    "type":     self.type,
                    "docstatus": 1,          # submitted only
                    "name": ["!=", self.name]
                },
                fields=["name"]
            )

            for loan in existing_loans:

                # Get all schedule rows ordered by position
                schedule_rows = frappe.get_all(
                    "Employee Loan Advance Schedule",
                    filters={"parent": loan.name},
                    fields=["month", "is_deducted"],
                    order_by="idx asc"
                )

                if not schedule_rows:
                    continue

                # Find pending rows
                pending_rows = [r for r in schedule_rows if not r.is_deducted]

                if not pending_rows:
                    # All installments deducted — loan complete, allow new loan
                    continue

                # Loan is still active — block
                last_month      = schedule_rows[-1].get("month")
                pending_count   = len(pending_rows)
                first_pending   = pending_rows[0].get("month")

                frappe.throw(
                    f"Employee already has an active <b>{self.type}</b> loan "
                    f"<b>{loan.name}</b>.<br><br>"
                    f"Loan schedule runs until <b>{last_month}</b>.<br>"
                    f"Pending installments: <b>{pending_count}</b> "
                    f"(next due: <b>{first_pending}</b>).<br><br>"
                    f"Please complete all installments of <b>{loan.name}</b> "
                    f"before applying for a new <b>{self.type}</b>.",
                    title=f"Active {self.type} Loan Exists"
                )

        # ---------------------------------------------------------------- #
        #  Advance check                                                    #
        # ---------------------------------------------------------------- #
        elif self.type == "Advance":

            existing_advance = frappe.get_all(
                "Employee Loan Advance",
                filters={
                    "employee":   self.employee,
                    "type":       "Advance",
                    "docstatus":  1,          # submitted only
                    "is_deducted": 0,         # not yet deducted
                    "name": ["!=", self.name]
                },
                fields=["name", "amount", "date"]
            )

            if existing_advance:
                adv = existing_advance[0]
                frappe.throw(
                    f"Employee already has an active <b>Advance</b> "
                    f"<b>{adv.name}</b> of ₹{adv.amount} "
                    f"dated <b>{adv.date}</b> that has not been deducted yet.<br><br>"
                    f"Please ensure the existing advance is deducted via Salary Slip "
                    f"before applying for a new Advance.",
                    title="Active Advance Exists"
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