import frappe
from frappe import _


def execute(filters=None):
    filters = filters or {}

    # Permission Check
    user_roles = frappe.get_roles(frappe.session.user)
    is_hr = bool({"Saral HR Manager", "Saral HR User", "System Manager"} & set(user_roles))

    if not is_hr:
        user_employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
        if user_employee:
            filters["employee"] = user_employee
        else:
            frappe.throw(_("No Employee record linked to your user account."))

    view = filters.get("view") or "Summary"

    if view == "Summary":
        columns = get_summary_columns()
        data    = get_summary_data(filters)
    else:
        columns = get_detail_columns()
        data    = get_detail_data(filters)

    return columns, data


# ==================================================================
#  Helper — fetch employee full name
# ==================================================================

def get_employee_name(employee_id):
    if not employee_id:
        return ""
    try:
        emp = frappe.db.sql(
            "SELECT * FROM `tabEmployee` WHERE name = %s LIMIT 1",
            employee_id, as_dict=True
        )
        if not emp:
            return employee_id
        emp = emp[0]
        for field in ["employee", "employee_name", "full_name", "emp_name"]:
            if emp.get(field):
                return emp[field]
        first = (emp.get("first_name") or "").strip()
        last  = (emp.get("last_name")  or "").strip()
        if first or last:
            return "{} {}".format(first, last).strip()
    except Exception:
        pass
    return employee_id


# ==================================================================
#  Helper — check if schedule child table exists for this loan
# ==================================================================

def has_schedule(loan_id):
    count = frappe.db.sql("""
        SELECT COUNT(*) FROM `tabEmployee Loan Advance Schedule`
        WHERE parent = %s
    """, loan_id)[0][0]
    return count > 0


# ==================================================================
#  Helper — get total paid from schedule
# ==================================================================

def get_schedule_paid(loan_id):
    result = frappe.db.sql("""
        SELECT COALESCE(SUM(deduction_amount), 0)
        FROM `tabEmployee Loan Advance Schedule`
        WHERE parent = %s AND is_deducted = 1
    """, loan_id)[0][0]
    return float(result or 0)


# ==================================================================
#  SUMMARY VIEW
# ==================================================================

def get_summary_columns():
    return [
        {"label": _("Loan ID"),       "fieldname": "loan_id",       "fieldtype": "Link",  "options": "Employee Loan Advance", "width": 180},
        {"label": _("Employee"),      "fieldname": "employee",      "fieldtype": "Link",  "options": "Employee",              "width": 130},
        {"label": _("Employee Name"), "fieldname": "employee_name", "fieldtype": "Data",                                      "width": 160},
        {"label": _("Type"),          "fieldname": "type",          "fieldtype": "Data",                                      "width": 90},
        {"label": _("Loan Amount"),   "fieldname": "amount",        "fieldtype": "Float",                                     "width": 130},
        {"label": _("Frequency"),     "fieldname": "frequency",     "fieldtype": "Data",                                      "width": 110},
        {"label": _("Start"),         "fieldname": "start",         "fieldtype": "Data",                                      "width": 120},
        {"label": _("Total Paid"),    "fieldname": "total_paid",    "fieldtype": "Float",                                     "width": 130},
        {"label": _("Outstanding"),   "fieldname": "outstanding",   "fieldtype": "Float",                                     "width": 130},
        {"label": _("Status"),        "fieldname": "status",        "fieldtype": "Data",                                      "width": 100},
    ]


def get_summary_data(filters):
    conditions = get_conditions(filters)

    loans = frappe.db.sql("""
        SELECT
            ela.name             AS loan_id,
            ela.employee         AS employee,
            ela.type             AS type,
            ela.amount           AS amount,
            ela.installment_gap  AS frequency,
            ela.start_month      AS start_month,
            ela.start_year       AS start_year,
            ela.is_deducted      AS is_deducted,
            ela.date             AS date
        FROM
            `tabEmployee Loan Advance` ela
        WHERE
            ela.docstatus = 1
            {conditions}
        ORDER BY
            ela.employee, ela.type, ela.creation
    """.format(conditions=conditions), filters, as_dict=True)

    data              = []
    grand_amount      = 0
    grand_paid        = 0
    grand_outstanding = 0

    for loan in loans:
        loan_id = loan.loan_id

        # --- Determine total paid based on type ---
        if has_schedule(loan_id):
            # Loan-I / Loan-II: use schedule deductions
            total_paid = get_schedule_paid(loan_id)
        else:
            # Advance: single deduction tracked by is_deducted on parent
            total_paid = loan.amount if loan.is_deducted else 0

        total_paid    = round(total_paid, 2)
        outstanding   = round(loan.amount - total_paid, 2)
        status        = "Completed" if outstanding <= 0 else "Active"
        employee_name = get_employee_name(loan.employee)

        # Start date — use start_month/year for loans, date for advance
        if loan.start_month or loan.start_year:
            start = "{} {}".format(loan.start_month or "", loan.start_year or "").strip()
        elif loan.date:
            start = str(loan.date)
        else:
            start = ""

        grand_amount      += loan.amount
        grand_paid        += total_paid
        grand_outstanding += outstanding

        data.append({
            "loan_id":       loan_id,
            "employee":      loan.employee,
            "employee_name": employee_name,
            "type":          loan.type,
            "amount":        loan.amount,
            "frequency":     loan.frequency or "One-Time" if not has_schedule(loan_id) else loan.frequency,
            "start":         start,
            "total_paid":    total_paid,
            "outstanding":   outstanding,
            "status":        status,
        })

    if data:
        data.append({
            "loan_id":       "TOTAL",
            "employee":      "",
            "employee_name": "",
            "type":          "",
            "amount":        round(grand_amount, 2),
            "frequency":     "",
            "start":         "",
            "total_paid":    round(grand_paid, 2),
            "outstanding":   round(grand_outstanding, 2),
            "status":        "",
            "bold":          1,
        })

    return data


# ==================================================================
#  DETAIL VIEW
# ==================================================================

def get_detail_columns():
    return [
        {"label": _("Loan ID"),         "fieldname": "loan_id",       "fieldtype": "Link",  "options": "Employee Loan Advance", "width": 180},
        {"label": _("Employee Name"),   "fieldname": "employee_name", "fieldtype": "Data",                                      "width": 150},
        {"label": _("Type"),            "fieldname": "type",          "fieldtype": "Data",                                      "width": 90},
        {"label": _("Month"),           "fieldname": "month",         "fieldtype": "Data",                                      "width": 130},
        {"label": _("Base EMI"),        "fieldname": "scheduled_amt", "fieldtype": "Float",                                     "width": 130},
        {"label": _("Actual Deducted"), "fieldname": "actual_amt",    "fieldtype": "Float",                                     "width": 140},
        {"label": _("Status"),          "fieldname": "status",        "fieldtype": "Data",                                      "width": 120},
        {"label": _("Deferred To"),     "fieldname": "deferred_to",   "fieldtype": "Data",                                      "width": 130},
        {"label": _("Running Balance"), "fieldname": "running_bal",   "fieldtype": "Float",                                     "width": 140},
    ]


def get_detail_data(filters):
    conditions = get_conditions(filters)

    loans = frappe.db.sql("""
        SELECT
            ela.name              AS loan_id,
            ela.employee          AS employee,
            ela.type              AS type,
            ela.amount            AS amount,
            ela.monthly_deduction AS base_emi,
            ela.is_deducted       AS is_deducted,
            ela.date              AS date,
            ela.start_month       AS start_month,
            ela.start_year        AS start_year
        FROM
            `tabEmployee Loan Advance` ela
        WHERE
            ela.docstatus = 1
            {conditions}
        ORDER BY
            ela.employee, ela.type, ela.creation
    """.format(conditions=conditions), filters, as_dict=True)

    data          = []
    loan_emp_name = {}

    for loan in loans:
        lid      = loan.loan_id
        emp_name = loan_emp_name.setdefault(lid, get_employee_name(loan.employee))

        # ── Group header row ──
        data.append({
            "loan_id":       lid,
            "employee_name": emp_name,
            "type":          loan.type,
            "month":         "",
            "scheduled_amt": "",
            "actual_amt":    "",
            "status":        "",
            "deferred_to":   "",
            "running_bal":   "",
            "bold":          1,
            "is_group_row":  1,
        })

        if has_schedule(lid):
            # ── Loan-I / Loan-II: schedule-based detail ──
            schedule = frappe.db.sql("""
                SELECT
                    month, deduction_amount, is_deducted,
                    is_deferred, deferred_to, idx
                FROM `tabEmployee Loan Advance Schedule`
                WHERE parent = %s
                ORDER BY idx
            """, lid, as_dict=True)

            running_bal = loan.amount
            paid_so_far = 0

            for row in schedule:
                if row.is_deducted:
                    status      = "Deducted"
                    paid_so_far = round(paid_so_far + row.deduction_amount, 2)
                    running_bal = round(loan.amount - paid_so_far, 2)
                    actual_amt  = row.deduction_amount
                elif row.is_deferred:
                    status     = "Deferred"
                    actual_amt = 0
                else:
                    status     = "Pending"
                    actual_amt = 0

                data.append({
                    "loan_id":       lid,
                    "employee_name": emp_name,
                    "type":          loan.type,
                    "month":         row.month,
                    "scheduled_amt": loan.base_emi,
                    "actual_amt":    actual_amt,
                    "status":        status,
                    "deferred_to":   row.deferred_to or "",
                    "running_bal":   running_bal,
                })

        else:
            # ── Advance: single row, is_deducted on parent ──
            if loan.date:
                month_label = frappe.utils.formatdate(loan.date, "MMMM yyyy")
            elif loan.start_month or loan.start_year:
                month_label = "{} {}".format(loan.start_month or "", loan.start_year or "").strip()
            else:
                month_label = "—"

            if loan.is_deducted:
                status      = "Deducted"
                actual_amt  = loan.amount
                running_bal = 0
            else:
                status      = "Pending"
                actual_amt  = 0
                running_bal = loan.amount

            data.append({
                "loan_id":       lid,
                "employee_name": emp_name,
                "type":          loan.type,
                "month":         month_label,
                "scheduled_amt": loan.amount,
                "actual_amt":    actual_amt,
                "status":        status,
                "deferred_to":   "",
                "running_bal":   running_bal,
            })

    return data


# ==================================================================
#  Shared SQL Conditions Builder
# ==================================================================

def get_conditions(filters):
    conditions = ""

    if filters.get("employee"):
        conditions += " AND ela.employee = %(employee)s"

    if filters.get("type"):
        conditions += " AND ela.type = %(type)s"

    if filters.get("status"):
        if filters["status"] == "Active":
            conditions += """
                AND (
                    CASE
                        WHEN (
                            SELECT COUNT(*) FROM `tabEmployee Loan Advance Schedule` s2
                            WHERE s2.parent = ela.name
                        ) > 0
                        THEN (
                            SELECT COALESCE(SUM(s2.deduction_amount), 0)
                            FROM `tabEmployee Loan Advance Schedule` s2
                            WHERE s2.parent = ela.name AND s2.is_deducted = 1
                        ) < ela.amount
                        ELSE ela.is_deducted = 0
                    END
                )
            """
        elif filters["status"] == "Completed":
            conditions += """
                AND (
                    CASE
                        WHEN (
                            SELECT COUNT(*) FROM `tabEmployee Loan Advance Schedule` s2
                            WHERE s2.parent = ela.name
                        ) > 0
                        THEN (
                            SELECT COALESCE(SUM(s2.deduction_amount), 0)
                            FROM `tabEmployee Loan Advance Schedule` s2
                            WHERE s2.parent = ela.name AND s2.is_deducted = 1
                        ) >= ela.amount
                        ELSE ela.is_deducted = 1
                    END
                )
            """

    return conditions