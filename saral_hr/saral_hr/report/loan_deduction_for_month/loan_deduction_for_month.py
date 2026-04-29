import frappe


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_employees_with_loans(doctype, txt, searchfield, start, page_len, filters):
    if isinstance(filters, str):
        import json
        filters = json.loads(filters)

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
            ela.employee,
            COALESCE(
                NULLIF(TRIM(CONCAT_WS(' ', e.first_name, e.middle_name, e.last_name)), ''),
                ela.full_name,
                ela.employee
            ) AS employee_name
        FROM `tabEmployee Loan Advance` ela
        LEFT JOIN `tabEmployee` e ON e.name = ela.employee
        WHERE ela.docstatus = 1
            {company_cond}
            AND (
                ela.employee LIKE %(txt)s
                OR CONCAT_WS(' ', e.first_name, e.middle_name, e.last_name) LIKE %(txt)s
                OR ela.full_name LIKE %(txt)s
            )
        ORDER BY ela.employee ASC
        LIMIT %(page_len)s OFFSET %(start)s
    """.format(company_cond=company_cond), params)

    return [[r[0], r[1] or r[0]] for r in results]


def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    if not filters.get("company"):
        return columns, []
    return columns, get_data(filters)


def get_columns():
    return [
        {"label": "Employee",      "fieldname": "employee",     "fieldtype": "Link",     "options": "Employee", "width": 140},
        {"label": "Full Name",     "fieldname": "full_name",    "fieldtype": "Data",     "width": 220},
        {"label": "Type",          "fieldname": "type",         "fieldtype": "Data",     "width": 120},
        {"label": "Total Amount",  "fieldname": "total_amount", "fieldtype": "Currency", "width": 160},
        {"label": "EMI to Deduct", "fieldname": "emi_amount",   "fieldtype": "Currency", "width": 160},
        {"label": "Status",        "fieldname": "status",       "fieldtype": "Data",     "width": 110},
    ]


def get_data(filters):
    company   = filters.get("company")
    employee  = filters.get("employee")
    loan_type = filters.get("loan_type") or None
    month     = filters.get("month")
    year      = filters.get("year")

    rows = []

    # ── LOANS ──────────────────────────────────────────────────────────────
    if not loan_type or loan_type == "Loan":
        cond = [
            "ela.docstatus = 1",
            "ela.company = %(company)s",
            "ela.type IN ('Loan','Loan-I','Loan-II')",
        ]
        vals = {"company": company}

        if employee:
            cond.append("ela.employee = %(employee)s")
            vals["employee"] = employee

        if month and year:
            cond.append("sch.month = %(my)s")
            vals["my"] = f"{month} {year}"
        elif month:
            cond.append("sch.month LIKE %(ml)s")
            vals["ml"] = f"{month}%"
        elif year:
            cond.append("sch.month LIKE %(yl)s")
            vals["yl"] = f"%{year}"

        if month or year:
            rows += frappe.db.sql(f"""
                SELECT
                    ela.employee,
                    ela.full_name,
                    'Loan'               AS type,
                    ela.amount           AS total_amount,
                    sch.deduction_amount AS emi_amount,
                    CASE WHEN sch.is_deducted = 1 THEN 'Deducted'
                         WHEN sch.is_deferred  = 1 THEN 'Deferred'
                         ELSE 'Pending'
                    END                  AS status
                FROM `tabEmployee Loan Advance` ela
                JOIN `tabEmployee Loan Advance Schedule` sch
                    ON sch.parent = ela.name
                WHERE {" AND ".join(cond)}
                ORDER BY ela.full_name
            """, vals, as_dict=1)
        else:
            cond.append("sch.is_deducted = 0")
            rows += frappe.db.sql(f"""
                SELECT
                    ela.employee,
                    ela.full_name,
                    'Loan'               AS type,
                    ela.amount           AS total_amount,
                    sch.deduction_amount AS emi_amount,
                    'Pending'            AS status
                FROM `tabEmployee Loan Advance` ela
                JOIN `tabEmployee Loan Advance Schedule` sch
                    ON sch.parent = ela.name
                    AND sch.idx = (
                        SELECT MIN(s2.idx)
                        FROM `tabEmployee Loan Advance Schedule` s2
                        WHERE s2.parent = ela.name
                          AND s2.is_deducted = 0
                    )
                WHERE {" AND ".join(cond)}
                ORDER BY ela.full_name
            """, vals, as_dict=1)

    # ── ADVANCES ───────────────────────────────────────────────────────────
    if not loan_type or loan_type == "Advance":
        cond = [
            "ela.docstatus = 1",
            "ela.company = %(company)s",
            "ela.type = 'Advance'",
        ]
        vals = {"company": company}

        if employee:
            cond.append("ela.employee = %(employee)s")
            vals["employee"] = employee

        if month and year:
            cond.append("DATE_FORMAT(ela.date, '%%M %%Y') = %(my)s")
            vals["my"] = f"{month} {year}"
        elif month:
            cond.append("MONTHNAME(ela.date) = %(month)s")
            vals["month"] = month
        elif year:
            cond.append("YEAR(ela.date) = %(year)s")
            vals["year"] = int(year)

        rows += frappe.db.sql(f"""
            SELECT
                ela.employee,
                ela.full_name,
                'Advance'  AS type,
                ela.amount AS total_amount,
                ela.amount AS emi_amount,
                CASE WHEN ela.is_deducted = 1 THEN 'Deducted'
                     ELSE 'Pending'
                END        AS status
            FROM `tabEmployee Loan Advance` ela
            WHERE {" AND ".join(cond)}
            ORDER BY ela.full_name
        """, vals, as_dict=1)

    return rows