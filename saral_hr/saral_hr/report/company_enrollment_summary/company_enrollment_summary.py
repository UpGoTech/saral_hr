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
    emp_perms = frappe.get_all(
        "User Permission",
        filters={"user": user, "allow": "Employee"},
        pluck="for_value",
    )
    if not emp_perms:
        return None
    return emp_perms


# ──────────────────────────────────────────────────────────────
# HELPER — get employee ID from a Company Link record
# ──────────────────────────────────────────────────────────────

def _get_emp_id(rec):
    return rec.get("employee") or rec.get("name") or ""


# ──────────────────────────────────────────────────────────────
# EXECUTE
# ──────────────────────────────────────────────────────────────

def execute(filters=None):
    if not filters:
        filters = {}
    columns = get_columns()
    data    = get_data(filters)
    summary = get_report_summary(data, filters)
    return columns, data, None, None, summary


# ──────────────────────────────────────────────────────────────
# COLUMNS — added Number of Staff & Number of Workers
# ──────────────────────────────────────────────────────────────

def get_columns():
    return [
        {"fieldname": "company",                     "label": _("Company Name"),                 "fieldtype": "Data",  "width": 280},
        {"fieldname": "total_employees",             "label": _("Number of Employee"),           "fieldtype": "Int",   "width": 170},
        {"fieldname": "total_staff",                 "label": _("Number of Staff"),              "fieldtype": "Int",   "width": 160},
        {"fieldname": "total_workers",               "label": _("Number of Workers"),            "fieldtype": "Int",   "width": 160},
        {"fieldname": "salary_structure_assigned",   "label": _("Salary Structure Assigned"),    "fieldtype": "Int",   "width": 190},
        {"fieldname": "salary_structure_unassigned", "label": _("Salary Structure Un-Assigned"), "fieldtype": "Int",   "width": 210},
        {"fieldname": "total_ctc",                   "label": _("Total CTC (\u20b9)"),            "fieldtype": "Float", "precision": 2, "width": 180},
    ]


# ──────────────────────────────────────────────────────────────
# DATA
# ──────────────────────────────────────────────────────────────

def get_data(filters):
    user                = frappe.session.user
    permitted_companies = get_permitted_companies(user)

    if permitted_companies is not None and len(permitted_companies) == 0:
        return []

    companies = get_companies(filters, permitted_companies)
    if not companies:
        return []

    category = filters.get("category") or None
    all_employee_ids = set(frappe.db.get_all("Employee", pluck="name"))

    data = []
    for company in companies:
        row = get_company_row(company, category, filters, user, all_employee_ids)
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


def get_company_row(company, category=None, filters=None, user=None, all_employee_ids=None):
    user = user or frappe.session.user
    permitted_emp_ids = get_permitted_employees(user, company)

    if all_employee_ids is None:
        all_employee_ids = set(frappe.db.get_all("Employee", pluck="name"))

    cl_records = frappe.db.get_all(
        "Company Link",
        filters={"company": company, "is_active": 1},
        fields=["name", "employee", "category"],
    )

    cl_category_map = {}
    for rec in cl_records:
        eid = _get_emp_id(rec)
        if not eid:
            continue
        if eid not in all_employee_ids:
            continue
        cl_category_map[eid] = rec.get("category") or ""

    if permitted_emp_ids is not None:
        permitted_set = set(permitted_emp_ids)
        cl_category_map = {k: v for k, v in cl_category_map.items() if k in permitted_set}

    # Staff/Worker counts are always from ALL employees (not filtered by category)
    total_staff   = sum(1 for cat in cl_category_map.values() if cat == "Staff")
    total_workers = sum(1 for cat in cl_category_map.values() if cat == "Worker")

    if category:
        active_ids = [eid for eid, cat in cl_category_map.items() if cat == category]
    else:
        active_ids = list(cl_category_map.keys())

    total_employees = len(active_ids)

    salary_structure_assigned   = 0
    salary_structure_unassigned = total_employees
    total_ctc                   = 0.0

    if active_ids:
        assigned_rows = frappe.db.get_all(
            "Salary Structure Assignment",
            filters={"company": company, "docstatus": 1, "employee": ["in", active_ids]},
            pluck="employee",
        )
        assigned_set                = set(assigned_rows)
        salary_structure_assigned   = len(assigned_set)
        salary_structure_unassigned = len([e for e in active_ids if e not in assigned_set])

        res = frappe.db.sql(
            """
            SELECT IFNULL(SUM(ssa.annual_ctc), 0)
            FROM   `tabSalary Structure Assignment` ssa
            WHERE  ssa.company   = %(company)s
              AND  ssa.docstatus = 1
              AND  ssa.employee  IN %(employees)s
            """,
            {"company": company, "employees": active_ids},
        )
        total_ctc = _flt(res[0][0]) if res else 0.0

    return {
        "company":                     company,
        "total_employees":             total_employees,
        "total_staff":                 total_staff,
        "total_workers":               total_workers,
        "salary_structure_assigned":   salary_structure_assigned,
        "salary_structure_unassigned": salary_structure_unassigned,
        "total_ctc":                   total_ctc,
    }


def _flt(v):
    try:
        return float(v or 0)
    except Exception:
        return 0.0


# ──────────────────────────────────────────────────────────────
# SUMMARY CARDS
# ──────────────────────────────────────────────────────────────

def get_report_summary(data, filters=None):
    if not data:
        return []

    all_emp_ids     = set(frappe.db.get_all("Employee", pluck="name"))
    total_employees = len(all_emp_ids)

    cl_all = frappe.db.get_all(
        "Company Link",
        filters={"is_active": 1, "company": ["!=", ""]},
        fields=["name", "employee"]
    )
    linked_emp_ids = set()
    for rec in cl_all:
        eid = _get_emp_id(rec)
        if eid:
            linked_emp_ids.add(eid)

    company_unassigned = len(all_emp_ids - linked_emp_ids)

    assigned_emp_ids = set()
    if all_emp_ids:
        assigned_emp_ids = set(frappe.db.get_all(
            "Salary Structure Assignment",
            filters={"docstatus": 1, "employee": ["in", list(all_emp_ids)]},
            pluck="employee",
        ))
    salary_unassigned = len(all_emp_ids - assigned_emp_ids)

    return [
        {"value": len(data),          "label": _("Number of Companies"),        "datatype": "Int", "color": "blue"},
        {"value": total_employees,    "label": _("Number of Employees"),         "datatype": "Int", "color": "green"},
        {"value": sum(r.get("total_staff",   0) for r in data), "label": _("Number of Staff"),   "datatype": "Int", "color": "purple"},
        {"value": sum(r.get("total_workers", 0) for r in data), "label": _("Number of Workers"), "datatype": "Int", "color": "orange"},
        {"value": salary_unassigned,  "label": _("Unassigned Salary Structure"), "datatype": "Int", "color": "red"},
        {"value": company_unassigned, "label": _("Company Unassigned"),          "datatype": "Int", "color": "red"},
    ]


# ──────────────────────────────────────────────────────────────
# WHITELISTED API — Company popup employee list
# Now also returns monthly_ctc per employee
# ──────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_company_employees(company, category=None):
    user = frappe.session.user

    permitted_companies = get_permitted_companies(user)
    if permitted_companies is not None and company not in permitted_companies:
        frappe.throw(_("Not permitted to view this company."), frappe.PermissionError)

    permitted_emp_ids = get_permitted_employees(user, company)
    all_emp_ids = set(frappe.db.get_all("Employee", pluck="name"))

    cl_records = frappe.db.get_all(
        "Company Link",
        filters={"company": company, "is_active": 1},
        fields=["name", "employee", "category", "full_name"],
    )

    cl_category_map = {}
    cl_fullname_map = {}
    for rec in cl_records:
        eid = _get_emp_id(rec)
        if eid and eid in all_emp_ids:
            cl_category_map[eid] = rec.get("category") or "\u2014"
            cl_fullname_map[eid] = rec.get("full_name") or eid

    if permitted_emp_ids is not None:
        permitted_set = set(permitted_emp_ids)
        cl_category_map = {k: v for k, v in cl_category_map.items() if k in permitted_set}
        cl_fullname_map = {k: v for k, v in cl_fullname_map.items() if k in permitted_set}

    if not cl_category_map:
        return []

    emp_ids = list(cl_category_map.keys())

    if category:
        emp_ids = [eid for eid in emp_ids if cl_category_map.get(eid) == category]
        if not emp_ids:
            return []

    emp_records = frappe.db.get_all(
        "Employee",
        filters={"name": ["in", emp_ids]},
        fields=["name", "employee_name", "department"],
    )
    emp_map = {rec["name"]: rec for rec in emp_records}

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
    for eid in emp_ids:
        rec = emp_map.get(eid, {})
        s   = ssa_map.get(eid, {})

        annual_ctc  = _flt(s.get("annual_ctc"))
        monthly_ctc = round(annual_ctc / 12, 2) if annual_ctc else 0.0

        full_name = (
            cl_fullname_map.get(eid)
            or rec.get("employee_name")
            or eid
        )

        result.append({
            "employee":         eid,
            "full_name":        full_name,
            "department":       rec.get("department") or "\u2014",
            "category":         cl_category_map.get(eid, "\u2014"),
            "salary_structure": s.get("salary_structure") or "Not Assigned",
            "annual_ctc":       annual_ctc,
            "monthly_ctc":      monthly_ctc,   # ← NEW
        })

    result.sort(key=lambda x: x["full_name"])
    return result


# ──────────────────────────────────────────────────────────────
# WHITELISTED API — Company Unassigned popup
# ──────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_company_unassigned_employees():
    all_employees = frappe.db.get_all(
        "Employee",
        fields=["name", "employee_name", "first_name", "middle_name", "last_name", "department"],
    )

    cl_all = frappe.db.get_all(
        "Company Link",
        filters={"is_active": 1, "company": ["!=", ""]},
        fields=["name", "employee"],
    )
    linked_emp_ids = set()
    for rec in cl_all:
        eid = _get_emp_id(rec)
        if eid:
            linked_emp_ids.add(eid)

    unlinked = [e for e in all_employees if e["name"] not in linked_emp_ids]

    result = []
    for emp in unlinked:
        eid = emp["name"]
        ssa = frappe.db.get_value(
            "Salary Structure Assignment",
            {"employee": eid, "docstatus": 1},
            ["salary_structure", "annual_ctc"],
            as_dict=True,
        )

        full_name = " ".join(filter(None, [
            emp.get("first_name"),
            emp.get("middle_name"),
            emp.get("last_name"),
        ])) or eid

        annual_ctc  = _flt(ssa.get("annual_ctc")) if ssa else 0.0
        monthly_ctc = round(annual_ctc / 12, 2) if annual_ctc else 0.0

        result.append({
            "employee":         eid,
            "full_name":        full_name,
            "company":          "\u2014",
            "department":       emp.get("department") or "\u2014",
            "category":         "\u2014",
            "salary_structure": ssa.get("salary_structure") if ssa else "Not Assigned",
            "annual_ctc":       annual_ctc,
            "monthly_ctc":      monthly_ctc,
        })

    result.sort(key=lambda x: x["full_name"])
    return result


# ──────────────────────────────────────────────────────────────
# WHITELISTED APIs — KPI bar counts
# ──────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_unlinked_employee_count():
    all_emp = set(frappe.db.get_all("Employee", pluck="name"))
    cl_all  = frappe.db.get_all(
        "Company Link",
        filters={"is_active": 1, "company": ["!=", ""]},
        fields=["name", "employee"]
    )
    linked = set()
    for rec in cl_all:
        eid = _get_emp_id(rec)
        if eid:
            linked.add(eid)
    return len(all_emp - linked)


@frappe.whitelist()
def get_total_active_employee_count():
    return frappe.db.count("Employee")


@frappe.whitelist()
def get_salary_unassigned_employee_count():
    all_emp = set(frappe.db.get_all("Employee", pluck="name"))
    if not all_emp:
        return 0
    assigned = set(frappe.db.get_all(
        "Salary Structure Assignment",
        filters={"docstatus": 1, "employee": ["in", list(all_emp)]},
        pluck="employee",
    ))
    return len(all_emp - assigned)


@frappe.whitelist()
def get_category_employee_count(category):
    all_emp = set(frappe.db.get_all("Employee", pluck="name"))
    if not all_emp:
        return 0
    cl_records = frappe.db.get_all(
        "Company Link",
        filters={"is_active": 1, "category": category},
        fields=["name", "employee"],
    )
    count = 0
    for rec in cl_records:
        eid = _get_emp_id(rec)
        if eid and eid in all_emp:
            count += 1
    return count


@frappe.whitelist()
def get_salary_unassigned_employees(category=None):
    all_employees = frappe.db.get_all(
        "Employee",
        fields=["name", "employee_name", "first_name", "middle_name", "last_name", "department"],
    )
    if not all_employees:
        return []

    all_ids  = [e["name"] for e in all_employees]
    assigned = set(frappe.db.get_all(
        "Salary Structure Assignment",
        filters={"docstatus": 1, "employee": ["in", all_ids]},
        pluck="employee",
    ))

    cl_records = frappe.db.get_all(
        "Company Link",
        filters={"is_active": 1},
        fields=["name", "employee", "category", "full_name", "company"],
    )
    cl_category_map = {}
    cl_fullname_map = {}
    cl_company_map  = {}
    for rec in cl_records:
        eid = _get_emp_id(rec)
        if eid:
            cl_category_map[eid] = rec.get("category") or "\u2014"
            cl_fullname_map[eid] = rec.get("full_name") or ""
            cl_company_map[eid]  = rec.get("company") or "\u2014"

    result = []
    for emp in all_employees:
        eid = emp["name"]
        if eid in assigned:
            continue
        emp_category = cl_category_map.get(eid, "\u2014")
        if category and emp_category != category:
            continue

        full_name = (
            cl_fullname_map.get(eid)
            or " ".join(filter(None, [emp.get("first_name"), emp.get("middle_name"), emp.get("last_name")]))
            or eid
        )

        result.append({
            "employee":         eid,
            "full_name":        full_name,
            "company":          cl_company_map.get(eid, "\u2014"),
            "department":       emp.get("department") or "\u2014",
            "category":         emp_category,
            "salary_structure": "Not Assigned",
            "annual_ctc":       0.0,
            "monthly_ctc":      0.0,
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
        limit=10,
    )
    return rows