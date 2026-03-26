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
    name = frappe.db.get_value("Employee", employee_id, "employee")
    if not name:
        # fallback: combine first + last name
        emp = frappe.db.get_value("Employee", employee_id, ["first_name", "last_name"], as_dict=True)
        if emp:
            name = "{} {}".format(emp.get("first_name") or "", emp.get("last_name") or "").strip()
    return name or employee_id

# ==================================================================
#  SUMMARY VIEW
# ==================================================================

def get_summary_columns():
    return [
        {"label": _("Loan ID"),       "fieldname": "loan_id",       "fieldtype": "Link",  "options": "Employee Loan Advance", "width": 160},
        {"label": _("Employee"),      "fieldname": "employee",      "fieldtype": "Link",  "options": "Employee",              "width": 120},
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
            COALESCE(
                SUM(CASE WHEN s.is_deducted = 1 THEN s.deduction_amount ELSE 0 END),
                0
            ) AS total_paid
        FROM
            `tabEmployee Loan Advance` ela
        LEFT JOIN
            `tabEmployee Loan Advance Schedule` s ON s.parent = ela.name
        WHERE
            ela.docstatus = 1
            {conditions}
        GROUP BY
            ela.name, ela.employee, ela.type, ela.amount,
            ela.installment_gap, ela.start_month, ela.start_year
        ORDER BY
            ela.employee, ela.creation
    """.format(conditions=conditions), filters, as_dict=True)

    data              = []
    grand_amount      = 0
    grand_paid        = 0
    grand_outstanding = 0

    for loan in loans:
        outstanding   = round(loan.amount - loan.total_paid, 2)
        status        = "Completed" if outstanding <= 0 else "Active"
        employee_name = get_employee_name(loan.employee)

        grand_amount      += loan.amount
        grand_paid        += loan.total_paid
        grand_outstanding += outstanding

        data.append({
            "loan_id":       loan.loan_id,
            "employee":      loan.employee,
            "employee_name": employee_name,
            "type":          loan.type,
            "amount":        loan.amount,
            "frequency":     loan.frequency,
            "start":         "{} {}".format(loan.start_month, loan.start_year),
            "total_paid":    loan.total_paid,
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
        {"label": _("Loan ID"),         "fieldname": "loan_id",       "fieldtype": "Link",  "options": "Employee Loan Advance", "width": 160},
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

    rows = frappe.db.sql("""
        SELECT
            ela.name              AS loan_id,
            ela.employee          AS employee,
            ela.type              AS type,
            ela.amount            AS amount,
            ela.monthly_deduction AS base_emi,
            s.month               AS month,
            s.deduction_amount    AS deduction_amount,
            s.is_deducted         AS is_deducted,
            s.is_deferred         AS is_deferred,
            s.deferred_to         AS deferred_to,
            s.idx                 AS idx
        FROM
            `tabEmployee Loan Advance` ela
        JOIN
            `tabEmployee Loan Advance Schedule` s ON s.parent = ela.name
        WHERE
            ela.docstatus = 1
            {conditions}
        ORDER BY
            ela.employee, ela.creation, s.idx
    """.format(conditions=conditions), filters, as_dict=True)

    data          = []
    loan_balance  = {}
    loan_paid     = {}
    loan_emp_name = {}

    for row in rows:
        lid = row.loan_id

        if lid not in loan_emp_name:
            loan_emp_name[lid] = get_employee_name(row.employee)

        emp_name = loan_emp_name[lid]

        if lid not in loan_balance:
            loan_balance[lid] = row.amount
            loan_paid[lid]    = 0

            data.append({
                "loan_id":       lid,
                "employee_name": emp_name,
                "type":          row.type,
                "month":         "",
                "scheduled_amt": "",
                "actual_amt":    "",
                "status":        "",
                "deferred_to":   "",
                "running_bal":   "",
                "bold":          1,
                "is_group_row":  1,
            })

        if row.is_deducted:
            status            = "Deducted"
            loan_paid[lid]    = round(loan_paid[lid] + row.deduction_amount, 2)
            loan_balance[lid] = round(row.amount - loan_paid[lid], 2)
            actual_amt        = row.deduction_amount
        elif row.is_deferred:
            status     = "Deferred"
            actual_amt = 0
        else:
            status     = "Pending"
            actual_amt = 0

        data.append({
            "loan_id":       lid,
            "employee_name": emp_name,
            "type":          row.type,
            "month":         row.month,
            "scheduled_amt": row.base_emi,
            "actual_amt":    actual_amt,
            "status":        status,
            "deferred_to":   row.deferred_to or "",
            "running_bal":   loan_balance[lid],
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
                    SELECT COALESCE(SUM(s2.deduction_amount), 0)
                    FROM `tabEmployee Loan Advance Schedule` s2
                    WHERE s2.parent = ela.name AND s2.is_deducted = 1
                ) < ela.amount
            """
        elif filters["status"] == "Completed":
            conditions += """
                AND (
                    SELECT COALESCE(SUM(s2.deduction_amount), 0)
                    FROM `tabEmployee Loan Advance Schedule` s2
                    WHERE s2.parent = ela.name AND s2.is_deducted = 1
                ) >= ela.amount
            """

    return conditions