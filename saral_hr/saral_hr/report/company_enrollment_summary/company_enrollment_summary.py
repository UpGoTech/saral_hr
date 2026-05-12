import frappe
from frappe import _


# ──────────────────────────────────────────────────────────────
# PERMISSION HELPERS
# ──────────────────────────────────────────────────────────────

def is_hr_manager(user=None):
    user = user or frappe.session.user
    return "Saral HR Manager" in frappe.get_roles(user)


def get_permitted_companies(user=None):
    user = user or frappe.session.user
    if is_hr_manager(user):
        return None

    companies = frappe.get_all(
        "User Permission",
        filters={"user": user, "allow": "Company"},
        pluck="for_value",
    )
    return companies or []


def get_permitted_employees(user=None, company=None):
    user = user or frappe.session.user
    if is_hr_manager(user):
        return None

    filters = {"user": user, "allow": "Employee"}
    if company:
        filters["applicable_for"] = "Company"
        filters["apply_to_all_doctypes"] = 0

    emp_perms = frappe.get_all(
        "User Permission",
        filters={"user": user, "allow": "Employee"},
        pluck="for_value",
    )

    if not emp_perms:
        return None

    return emp_perms


# ──────────────────────────────────────────────────────────────
# EXECUTE
# ──────────────────────────────────────────────────────────────

def execute(filters=None):
    if not filters:
        filters = {}

    columns = get_columns()
    data    = get_data(filters)
    summary = get_report_summary(data)

    return columns, data, None, None, summary


# ──────────────────────────────────────────────────────────────
# COLUMNS — widths tuned to fill ~1280px table evenly
# Company: 380  |  Employees: 200  |  Assigned: 220  |  Unassigned: 230  |  CTC: 220
# ──────────────────────────────────────────────────────────────

def get_columns():
    return [
        {
            "fieldname": "company",
            "label":     _("Company Name"),
            "fieldtype": "Data",
            "width":     380,
        },
        {
            "fieldname": "total_employees",
            "label":     _("Number of Employee"),
            "fieldtype": "Int",
            "width":     200,
        },
        {
            "fieldname": "salary_structure_assigned",
            "label":     _("Salary Structure Assigned"),
            "fieldtype": "Int",
            "width":     200,
        },
        {
            "fieldname": "salary_structure_unassigned",
            "label":     _("Salary Structure Un-Assigned"),
            "fieldtype": "Int",
            "width":     220,
        },
        {
            "fieldname": "total_ctc",
            "label":     _("Total CTC (\u20b9)"),
            "fieldtype": "Float",
            "precision": 2,
            "width":     200,
        },
    ]


# ──────────────────────────────────────────────────────────────
# DATA
# ──────────────────────────────────────────────────────────────

def get_data(filters):
    user               = frappe.session.user
    permitted_companies = get_permitted_companies(user)

    if permitted_companies is not None and len(permitted_companies) == 0:
        return []

    companies = get_companies(filters, permitted_companies)
    if not companies:
        return []

    category = filters.get("category") or None
    data = []
    for company in companies:
        row = get_company_row(company, category, filters, user)
        data.append(row)
    return data


def get_companies(filters, permitted_companies):
    if filters.get("company"):
        requested = [filters["company"]]
    else:
        if permitted_companies is None:
            requested = frappe.db.get_all("Company", pluck="name", order_by="name asc")
        else:
            requested = permitted_companies

    if permitted_companies is not None:
        requested = [c for c in requested if c in permitted_companies]

    return requested


def get_company_row(company, category=None, filters=None, user=None):
    user = user or frappe.session.user

    permitted_emp_ids = get_permitted_employees(user, company)

    active_f = {"company": company, "is_active": 1}
    if category:
        active_f["category"] = category

    cl_records = frappe.db.get_all(
        "Company Link",
        filters=active_f,
        fields=["name", "employee", "full_name", "category", "department"],
    )

    active_ids = []
    for rec in cl_records:
        eid = rec.get("employee") or rec.get("name")
        if eid:
            active_ids.append(eid)

    if permitted_emp_ids is not None:
        active_ids = [e for e in active_ids if e in permitted_emp_ids]

    active_ids      = list(set(active_ids))
    total_employees = len(active_ids)

    if permitted_emp_ids is None:
        total_staff   = frappe.db.count("Company Link", {"company": company, "is_active": 1, "category": "Staff"})
        total_workers = frappe.db.count("Company Link", {"company": company, "is_active": 1, "category": "Worker"})
    else:
        all_cl = frappe.db.get_all(
            "Company Link",
            filters={"company": company, "is_active": 1},
            fields=["employee", "name", "category"],
        )
        total_staff   = sum(1 for r in all_cl
                            if r.get("category") == "Staff"
                            and (r.get("employee") or r.get("name")) in permitted_emp_ids)
        total_workers = sum(1 for r in all_cl
                            if r.get("category") == "Worker"
                            and (r.get("employee") or r.get("name")) in permitted_emp_ids)

    salary_structure_assigned   = 0
    salary_structure_unassigned = total_employees
    total_ctc                   = 0.0

    if active_ids:
        assigned_rows = frappe.db.get_all(
            "Salary Structure Assignment",
            filters={
                "company":   company,
                "docstatus": 1,
                "employee":  ["in", active_ids],
            },
            pluck="employee",
        )
        assigned_set                = set(assigned_rows)
        salary_structure_assigned   = len(assigned_set)
        salary_structure_unassigned = len([e for e in active_ids if e not in assigned_set])

        res = frappe.db.sql(
            """
            SELECT IFNULL(SUM(annual_ctc), 0)
            FROM   `tabSalary Structure Assignment`
            WHERE  company   = %(company)s
              AND  docstatus = 1
              AND  employee  IN %(employees)s
            """,
            {"company": company, "employees": active_ids},
        )
        total_ctc = _flt(res[0][0]) if res else 0.0

    return {
        "company":                     company,
        "total_employees":             total_employees,
        "salary_structure_assigned":   salary_structure_assigned,
        "salary_structure_unassigned": salary_structure_unassigned,
        "total_ctc":                   total_ctc,
        "_total_staff":                total_staff,
        "_total_workers":              total_workers,
    }


def _flt(v):
    try:
        return float(v or 0)
    except Exception:
        return 0.0


# ──────────────────────────────────────────────────────────────
# SUMMARY CARDS
# ──────────────────────────────────────────────────────────────

def get_report_summary(data):
    if not data:
        return []

    return [
        {
            "value":    len(data),
            "label":    _("Number of Companies"),
            "datatype": "Int",
            "color":    "blue",
        },
        {
            "value":    sum(r.get("total_employees", 0) for r in data),
            "label":    _("Number of Employees"),
            "datatype": "Int",
            "color":    "green",
        },
        {
            "value":    sum(r.get("_total_staff", 0) for r in data),
            "label":    _("Number of Staff"),
            "datatype": "Int",
            "color":    "purple",
        },
        {
            "value":    sum(r.get("_total_workers", 0) for r in data),
            "label":    _("Number of Workers"),
            "datatype": "Int",
            "color":    "orange",
        },
        {
            "value":    sum(r.get("salary_structure_unassigned", 0) for r in data),
            "label":    _("Unassigned Employees"),
            "datatype": "Int",
            "color":    "red",
        },
    ]


# ──────────────────────────────────────────────────────────────
# WHITELISTED API — Employee filter dropdown
# ──────────────────────────────────────────────────────────────

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_employees_for_filter(doctype, txt, searchfield, start, page_len, filters):
    user    = frappe.session.user
    company = (filters or {}).get("company")

    permitted_companies = get_permitted_companies(user)
    permitted_emp_ids   = get_permitted_employees(user, company)

    conditions = ["cl.is_active = 1"]
    values     = {"txt": f"%{txt}%", "start": start, "page_len": page_len}

    if permitted_companies is not None:
        if not permitted_companies:
            return []
        escaped = ", ".join(frappe.db.escape(c) for c in permitted_companies)
        conditions.append(f"cl.company IN ({escaped})")
    elif company:
        conditions.append("cl.company = %(company)s")
        values["company"] = company

    if company and permitted_companies is None:
        conditions.append("cl.company = %(company)s")
        values["company"] = company

    if permitted_emp_ids is not None:
        if not permitted_emp_ids:
            return []
        escaped_emp = ", ".join(frappe.db.escape(e) for e in permitted_emp_ids)
        conditions.append(f"COALESCE(cl.employee, cl.name) IN ({escaped_emp})")

    conditions.append("(cl.full_name LIKE %(txt)s OR cl.employee LIKE %(txt)s)")
    where = " AND ".join(conditions)

    rows = frappe.db.sql(
        f"""
        SELECT
            COALESCE(cl.employee, cl.name) AS value,
            cl.full_name                   AS label,
            cl.category                    AS description
        FROM `tabCompany Link` cl
        WHERE {where}
        ORDER BY cl.full_name ASC
        LIMIT %(page_len)s OFFSET %(start)s
        """,
        values,
        as_dict=True,
    )

    return [(r.value, r.label, r.description or "") for r in rows]


# ──────────────────────────────────────────────────────────────
# WHITELISTED API — Company popup employee list
# ──────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_company_employees(company, category=None):
    user = frappe.session.user

    permitted_companies = get_permitted_companies(user)
    if permitted_companies is not None and company not in permitted_companies:
        frappe.throw(_("Not permitted to view this company."), frappe.PermissionError)

    permitted_emp_ids = get_permitted_employees(user, company)

    active_f = {"company": company, "is_active": 1}
    if category:
        active_f["category"] = category

    cl_records = frappe.db.get_all(
        "Company Link",
        filters=active_f,
        fields=["name", "employee", "full_name", "department", "category"],
        order_by="full_name asc",
    )
    if not cl_records:
        return []

    emp_map = {}
    for rec in cl_records:
        eid = rec.get("employee") or rec.get("name")
        if eid:
            if permitted_emp_ids is not None and eid not in permitted_emp_ids:
                continue
            emp_map[eid] = rec

    if not emp_map:
        return []

    emp_ids  = list(emp_map.keys())
    ssa_list = frappe.db.get_all(
        "Salary Structure Assignment",
        filters={"company": company, "docstatus": 1, "employee": ["in", emp_ids]},
        fields=["employee", "annual_ctc", "salary_structure"],
        order_by="from_date desc",
    )

    ssa_map = {}
    for s in ssa_list:
        if s["employee"] not in ssa_map:
            ssa_map[s["employee"]] = s

    result = []
    for eid, rec in emp_map.items():
        s = ssa_map.get(eid, {})
        result.append({
            "employee":         eid,
            "full_name":        rec.get("full_name") or eid,
            "department":       rec.get("department") or "\u2014",
            "category":         rec.get("category") or "\u2014",
            "salary_structure": s.get("salary_structure") or "Not Assigned",
            "annual_ctc":       _flt(s.get("annual_ctc")),
        })

    result.sort(key=lambda x: x["full_name"])
    return result


@frappe.whitelist()
def debug_company_link(company=None):
    f = {}
    if company:
        f["company"] = company
    rows = frappe.db.get_all(
        "Company Link",
        filters=f,
        fields=["name", "employee", "full_name", "company", "is_active", "category"],
        limit=5,
    )
    return rows