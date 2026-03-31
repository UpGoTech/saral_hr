import frappe
from frappe import _


# ==================================================================
#  execute — entry point
# ==================================================================

def execute(filters=None):
    filters = filters or {}

    # ── Permission Check ──────────────────────────────────────────
    user_roles = frappe.get_roles(frappe.session.user)
    is_hr      = bool({"Saral HR Manager", "Saral HR User", "System Manager"} & set(user_roles))

    if not is_hr:
        user_employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
        if user_employee:
            filters["employee"] = user_employee
        else:
            frappe.throw(_("No Employee record linked to your user account."))

    columns = get_summary_columns()
    data    = get_summary_data(filters)
    return columns, data


# ==================================================================
#  Employee Link filter — only employees who have loans in that company
# ==================================================================

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_employees_with_loans(doctype, txt, searchfield, start, page_len, filters):
    company_cond = ""
    params = {
        "txt": f"%{txt}%",
        "start": start,
        "page_len": page_len,
    }

    if filters and filters.get("company"):
        company_cond = "AND ela.company = %(company)s"
        params["company"] = filters["company"]

    results = frappe.db.sql("""
        SELECT DISTINCT
            cl.name,
            cl.full_name
        FROM `tabCompany Link` cl
        INNER JOIN `tabEmployee Loan Advance` ela ON ela.employee = cl.name
        WHERE ela.docstatus = 1
            {company_cond}
            AND (cl.name LIKE %(txt)s OR cl.full_name LIKE %(txt)s)
        ORDER BY cl.full_name
        LIMIT %(page_len)s OFFSET %(start)s
    """.format(company_cond=company_cond), params)

    return results

# ==================================================================
#  SUMMARY — columns
# ==================================================================

def get_summary_columns():
    return [
        {"label": _("Loan ID"),       "fieldname": "loan_id",       "fieldtype": "Link",  "options": "Employee Loan Advance", "width": 200},
        {"label": _("Employee ID"),   "fieldname": "employee",      "fieldtype": "Link",  "options": "Employee",              "width": 130},
        {"label": _("Employee Name"), "fieldname": "employee_name", "fieldtype": "Data",                                      "width": 170},
        {"label": _("Loan Type"),     "fieldname": "type",          "fieldtype": "Data",                                      "width": 90},
        {"label": _("Taken On"),      "fieldname": "taken_on",      "fieldtype": "Date",                                      "width": 120},
        {"label": _("Frequency"),     "fieldname": "frequency",     "fieldtype": "Data",                                      "width": 100},
        {"label": _("Loan Amount"),   "fieldname": "amount",        "fieldtype": "Float",                                     "width": 130},
        {"label": _("Total Paid"),    "fieldname": "total_paid",    "fieldtype": "Float",                                     "width": 130},
        {"label": _("Outstanding"),   "fieldname": "outstanding",   "fieldtype": "Float",                                     "width": 130},
        {"label": _("Status"),        "fieldname": "status",        "fieldtype": "Data",                                      "width": 110},
        {"label": _("Details"),       "fieldname": "detail_btn",    "fieldtype": "Data",                                      "width": 100},
    ]


# ==================================================================
#  SUMMARY — data
# ==================================================================

def get_summary_data(filters):
    conditions = build_conditions(filters)

    loans = frappe.db.sql("""
        SELECT
            ela.name              AS loan_id,
            ela.employee          AS employee,
            ela.company           AS company,
            ela.type              AS type,
            ela.amount            AS amount,
            ela.monthly_deduction AS base_emi,
            ela.installment_gap   AS frequency,
            ela.is_deducted       AS is_deducted,
            ela.date              AS date,
            ela.start_month       AS start_month,
            ela.start_year        AS start_year,
            ela.full_name         AS employee_name
        FROM  `tabEmployee Loan Advance` ela
        INNER JOIN `tabEmployee` e ON e.name = ela.employee
        WHERE ela.docstatus = 1
              {conditions}
        ORDER BY ela.company, ela.employee, ela.type, ela.creation
    """.format(conditions=conditions), filters, as_dict=True)

    rows              = []
    grand_amount      = 0.0
    grand_paid        = 0.0
    grand_outstanding = 0.0

    for loan in loans:
        lid       = loan.loan_id
        emp_name  = loan.employee_name or loan.employee
        has_sched = has_schedule(lid)

        total_paid  = get_schedule_paid(lid) if has_sched else (float(loan.amount) if loan.is_deducted else 0.0)
        total_paid  = round(float(total_paid), 2)
        outstanding = round(float(loan.amount) - total_paid, 2)
        status      = "Completed" if outstanding <= 0 else "Active"

        # ── Taken On: always use ela.date directly ────────────────
        taken_on = loan.date if loan.date else None

        grand_amount      += float(loan.amount)
        grand_paid        += total_paid
        grand_outstanding += outstanding

        rows.append({
            "loan_id":       lid,
            "employee":      loan.employee,
            "employee_name": emp_name,
            "company":       loan.company or "",
            "type":          loan.type,
            "amount":        float(loan.amount),
            "frequency":     loan.frequency or ("One-Time" if not has_sched else ""),
            "taken_on":      taken_on,
            "total_paid":    total_paid,
            "outstanding":   outstanding,
            "status":        status,
            "detail_btn":    lid,
        })

    if rows:
        rows.append({
            "loan_id":       "TOTAL",
            "employee":      "",
            "employee_name": "",
            "company":       "",
            "type":          "",
            "amount":        round(grand_amount, 2),
            "frequency":     "",
            "taken_on":      None,
            "total_paid":    round(grand_paid, 2),
            "outstanding":   round(grand_outstanding, 2),
            "status":        "",
            "detail_btn":    "",
        })

    return rows


# ==================================================================
#  DETAIL — fetched on demand via whitelist call
# ==================================================================

@frappe.whitelist()
def get_loan_detail(loan_id):
    loan = frappe.db.sql("""
        SELECT
            ela.name              AS loan_id,
            ela.employee          AS employee,
            ela.company           AS company,
            ela.type              AS type,
            ela.amount            AS amount,
            ela.monthly_deduction AS base_emi,
            ela.is_deducted       AS is_deducted,
            ela.date              AS date,
            ela.start_month       AS start_month,
            ela.start_year        AS start_year,
            ela.full_name         AS employee_name
        FROM  `tabEmployee Loan Advance` ela
        INNER JOIN `tabEmployee` e ON e.name = ela.employee
        WHERE ela.name = %s AND ela.docstatus = 1
        LIMIT 1
    """, loan_id, as_dict=True)

    if not loan:
        frappe.throw(_("Loan record not found or not submitted."))

    loan = loan[0]
    rows = []

    if has_schedule(loan_id):
        schedule = frappe.db.sql("""
            SELECT month, deduction_amount, is_deducted,
                   is_deferred, deferred_to, idx
            FROM   `tabEmployee Loan Advance Schedule`
            WHERE  parent = %s
            ORDER  BY idx
        """, loan_id, as_dict=True)

        running_bal = float(loan.amount)
        paid_so_far = 0.0

        for row in schedule:
            if row.is_deducted:
                status      = "Deducted"
                paid_so_far = round(paid_so_far + float(row.deduction_amount), 2)
                running_bal = round(float(loan.amount) - paid_so_far, 2)
                actual_amt  = float(row.deduction_amount)
            elif row.is_deferred:
                status     = "Deferred"
                actual_amt = 0.0
            else:
                status     = "Pending"
                actual_amt = 0.0

            rows.append({
                "month":         row.month or "",
                "scheduled_amt": float(loan.base_emi or 0),
                "actual_amt":    actual_amt,
                "status":        status,
                "deferred_to":   row.deferred_to or "",
                "running_bal":   running_bal,
            })

    else:
        if loan.date:
            month_label = frappe.utils.formatdate(loan.date, "MMMM yyyy")
        elif loan.start_month or loan.start_year:
            month_label = "{} {}".format(loan.start_month or "", loan.start_year or "").strip()
        else:
            month_label = "—"

        if loan.is_deducted:
            status      = "Deducted"
            actual_amt  = float(loan.amount)
            running_bal = 0.0
        else:
            status      = "Pending"
            actual_amt  = 0.0
            running_bal = float(loan.amount)

        rows.append({
            "month":         month_label,
            "scheduled_amt": float(loan.amount),
            "actual_amt":    actual_amt,
            "status":        status,
            "deferred_to":   "",
            "running_bal":   running_bal,
        })

    # Format taken_on date for display in the modal
    taken_on_display = frappe.utils.formatdate(loan.date, "dd-MM-yyyy") if loan.date else "—"

    # Derive status from rows
    total_paid  = sum(r["actual_amt"] for r in rows)
    outstanding = round(float(loan.amount) - total_paid, 2)
    status      = "Completed" if outstanding <= 0 else "Active"

    return {
        "loan_id":       loan.loan_id,
        "employee":      loan.employee,
        "employee_name": loan.employee_name or loan.employee,
        "company":       loan.company or "",
        "type":          loan.type,
        "amount":        float(loan.amount),
        "taken_on":      taken_on_display,
        "status":        status,
        "rows":          rows,
    }


# ==================================================================
#  Helpers
# ==================================================================

def has_schedule(loan_id):
    return frappe.db.sql("""
        SELECT COUNT(*) FROM `tabEmployee Loan Advance Schedule` WHERE parent = %s
    """, loan_id)[0][0] > 0


def get_schedule_paid(loan_id):
    result = frappe.db.sql("""
        SELECT COALESCE(SUM(deduction_amount), 0)
        FROM   `tabEmployee Loan Advance Schedule`
        WHERE  parent = %s AND is_deducted = 1
    """, loan_id)[0][0]
    return float(result or 0)


# ==================================================================
#  SQL Conditions
# ==================================================================

def build_conditions(filters):
    conditions = ""

    if filters.get("company"):
        conditions += " AND ela.company = %(company)s"

    if filters.get("employee"):
        employee_value = filters["employee"]
        # Extract ID from "Name (ID)" format
        if " (" in employee_value:
            employee_id = employee_value.split(" (")[-1].rstrip(")")
        else:
            employee_id = employee_value
        conditions += " AND ela.employee = %(employee_id)s"
        filters["employee_id"] = employee_id

    if filters.get("type"):
        conditions += " AND ela.type = %(type)s"

    if filters.get("status"):
        if filters["status"] == "Active":
            conditions += """
                AND (
                    CASE
                        WHEN (SELECT COUNT(*) FROM `tabEmployee Loan Advance Schedule` s2
                              WHERE s2.parent = ela.name) > 0
                        THEN (SELECT COALESCE(SUM(s2.deduction_amount), 0)
                              FROM `tabEmployee Loan Advance Schedule` s2
                              WHERE s2.parent = ela.name AND s2.is_deducted = 1) < ela.amount
                        ELSE ela.is_deducted = 0
                    END
                )
            """
        elif filters["status"] == "Completed":
            conditions += """
                AND (
                    CASE
                        WHEN (SELECT COUNT(*) FROM `tabEmployee Loan Advance Schedule` s2
                              WHERE s2.parent = ela.name) > 0
                        THEN (SELECT COALESCE(SUM(s2.deduction_amount), 0)
                              FROM `tabEmployee Loan Advance Schedule` s2
                              WHERE s2.parent = ela.name AND s2.is_deducted = 1) >= ela.amount
                        ELSE ela.is_deducted = 1
                    END
                )
            """

    return conditions