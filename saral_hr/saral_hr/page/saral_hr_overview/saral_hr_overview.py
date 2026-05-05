import frappe
from frappe.utils import getdate, get_last_day, flt, today, add_days
from dateutil.relativedelta import relativedelta
import calendar


# ─── Permission helper ────────────────────────────────────────────────────────

def _get_permitted_employees():
    """
    Returns:
        None  → no restriction (System Manager or no Employee User Permissions)
        []    → 0 permitted employees
        [...] → list of permitted Company Link name IDs
    """
    user = frappe.session.user

    if "System Manager" in frappe.get_roles(user):
        return None

    user_permissions = frappe.permissions.get_user_permissions(user)

    if "Employee" in user_permissions and user_permissions["Employee"]:
        permitted = [
            p.get("doc")
            for p in user_permissions["Employee"]
            if p.get("doc")
        ]
        return permitted if permitted else None

    return None


def _emp_filter_clause(permitted, alias="cl", param_prefix="pe"):
    """
    Returns (sql_fragment, params_dict) for an IN clause on `alias`.name.
    sql_fragment is "" if no restriction, or "AND alias.name IN (...)" if restricted.
    Returns None, None if permitted == [] (zero allowed — caller should short-circuit).
    """
    if permitted is None:
        return "", {}
    if len(permitted) == 0:
        return None, None
    placeholders = ", ".join([f"%({param_prefix}_{i})s" for i in range(len(permitted))])
    clause = f"AND {alias}.name IN ({placeholders})"
    params = {f"{param_prefix}_{i}": e for i, e in enumerate(permitted)}
    return clause, params


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _month_range(from_date, to_date):
    cursor = from_date.replace(day=1)
    while cursor <= to_date:
        month_start = cursor
        month_end   = min(getdate(get_last_day(cursor)), to_date)
        yield month_start, month_end
        cursor = (cursor + relativedelta(months=1)).replace(day=1)


def _active_in_month(company, month_start, month_end, permitted=None):
    filters = {
        "company":         company,
        "is_active":       1,
        "date_of_joining": ["<=", month_end]
    }
    if permitted is not None:
        if len(permitted) == 0:
            return []
        filters["name"] = ["in", permitted]

    rows = frappe.db.get_all(
        "Company Link",
        filters=filters,
        fields=["name", "left_date", "employee", "full_name", "date_of_joining"]
    )
    return [r for r in rows if not r.left_date or getdate(r.left_date) >= month_start]


def _get_employee_names(employee_ids):
    if not employee_ids:
        return {}
    emp_docs = frappe.db.get_all(
        "Employee",
        filters={"name": ["in", list(employee_ids)]},
        fields=["name", "first_name", "middle_name", "last_name"]
    )
    result = {}
    for e in emp_docs:
        parts = [e.first_name or "", e.middle_name or "", e.last_name or ""]
        full  = " ".join(p for p in parts if p).strip()
        result[e.name] = full if full else e.name
    return result


# ---------------------------------------------------------------------------
# Company dropdown
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_companies():
    user = frappe.session.user
    
    # Check if user has Company-level User Permissions
    from frappe.permissions import get_user_permissions
    user_permissions = get_user_permissions(user)
    
    if "Company" in user_permissions and user_permissions["Company"]:
        permitted_companies = [
            p.get("doc") for p in user_permissions["Company"] if p.get("doc")
        ]
        if permitted_companies:
            return frappe.db.get_all(
                "Company",
                filters={"company": ["in", permitted_companies]},
                pluck="company",
                order_by="company asc"
            )
    
    return frappe.db.get_all("Company", pluck="company", order_by="company asc")

# ---------------------------------------------------------------------------
# KPI data
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_kpi_data(company, from_date, to_date):
    from_date = getdate(from_date)
    to_date   = getdate(to_date)

    permitted = _get_permitted_employees()

    # ── Headcount KPIs (restricted if permitted) ──────────────────────────────
    if permitted is not None:
        if len(permitted) == 0:
            total_registered = 0
            total_active     = 0
        else:
            total_registered = frappe.db.count("Company Link", {
                "company": company, "name": ["in", permitted]
            })
            total_active = frappe.db.count("Company Link", {
                "company": company, "is_active": 1, "name": ["in", permitted]
            })
    else:
        total_registered = frappe.db.count("Company Link", filters={"company": company})
        total_active     = frappe.db.count("Company Link", filters={"company": company, "is_active": 1})

    # ── Structure KPIs (not employee-restricted) ──────────────────────────────
    salary_structures  = frappe.db.count("Salary Structure", filters={"company": company})
    salary_components  = frappe.db.count("Salary Component")

    # ── SSA count (restricted) ────────────────────────────────────────────────
    ssa_filters = {
        "company":   company,
        "docstatus": 1,
        "from_date": ["<=", to_date],
        "to_date":   [">=", from_date]
    }
    if permitted is not None:
        if len(permitted) == 0:
            ssa_count = 0
        else:
            ssa_filters["employee"] = ["in", permitted]
            ssa_count = frappe.db.count("Salary Structure Assignment", filters=ssa_filters)
    else:
        ssa_count = frappe.db.count("Salary Structure Assignment", filters=ssa_filters)

    # ── Holiday count ─────────────────────────────────────────────────────────
    holiday_list_name = frappe.db.get_value("Company", company, "default_holiday_list")
    holiday_count = 0
    if holiday_list_name:
        holiday_count = frappe.db.count("Holiday", filters={
            "parent":       holiday_list_name,
            "holiday_date": ["between", [from_date, to_date]]
        })

    # ── On hold count (restricted) ────────────────────────────────────────────
    hold_filters = {"company": company, "status": "On Hold", "docstatus": 1}
    if permitted is not None and len(permitted) > 0:
        hold_filters["employee"] = ["in", permitted]
    on_hold_count = 0 if (permitted is not None and len(permitted) == 0) else \
        frappe.db.count("Employee Salary Hold", filters=hold_filters)

    # ── Without assignment (restricted) ───────────────────────────────────────
    active_filters = {"company": company, "is_active": 1}
    if permitted is not None:
        if len(permitted) == 0:
            active_employees = []
        else:
            active_filters["name"] = ["in", permitted]
            active_employees = frappe.db.get_all("Company Link", filters=active_filters, pluck="name")
    else:
        active_employees = frappe.db.get_all("Company Link", filters=active_filters, pluck="name")

    assigned_filters = {
        "company": company, "docstatus": 1,
        "from_date": ["<=", to_date], "to_date": [">=", from_date]
    }
    if permitted is not None and len(permitted) > 0:
        assigned_filters["employee"] = ["in", permitted]
    assigned_set = set(frappe.db.get_all(
        "Salary Structure Assignment", filters=assigned_filters, pluck="employee"
    )) if not (permitted is not None and len(permitted) == 0) else set()

    without_assignment = len([e for e in active_employees if e not in assigned_set])

    # ── ESIC / PF / Gender (restricted) ──────────────────────────────────────
    emp_names = frappe.db.get_all(
        "Company Link",
        filters={**{"company": company, "is_active": 1},
                 **({} if permitted is None else {"name": ["in", permitted] if permitted else ["in", ["__never__"]]})},
        pluck="employee"
    ) if not (permitted is not None and len(permitted) == 0) else []

    esic_filled = pf_filled = 0
    gender_counts   = {}
    gender_missing  = 0
    if emp_names:
        esic_filled = frappe.db.count("Employee", filters={
            "name": ["in", emp_names], "esic_number": ["!=", ""]
        })
        pf_filled = frappe.db.count("Employee", filters={
            "name": ["in", emp_names], "pf_uan_number": ["!=", ""]
        })
        genders = frappe.db.get_all("Employee", filters={"name": ["in", emp_names]}, fields=["gender"])
        for g in genders:
            key = g.gender or "Not specified"
            gender_counts[key] = gender_counts.get(key, 0) + 1
        gender_missing = gender_counts.get("Not specified", 0)

    # ── YTD salary cost (restricted) ──────────────────────────────────────────
    if permitted is not None and len(permitted) == 0:
        ytd_salary_cost = 0.0
    elif permitted is not None:
        placeholders    = ", ".join(["%s"] * len(permitted))
        ytd_result      = frappe.db.sql(f"""
            SELECT COALESCE(SUM(net_salary), 0) as total
            FROM `tabSalary Slip`
            WHERE company = %s
              AND docstatus = 1
              AND start_date >= %s
              AND end_date   <= %s
              AND employee IN ({placeholders})
        """, (company, from_date, to_date) + tuple(permitted), as_dict=True)
        ytd_salary_cost = flt(ytd_result[0].total, 2) if ytd_result else 0
    else:
        ytd_result = frappe.db.sql("""
            SELECT COALESCE(SUM(net_salary), 0) as total
            FROM `tabSalary Slip`
            WHERE company = %s
              AND docstatus = 1
              AND start_date >= %s
              AND end_date   <= %s
        """, (company, from_date, to_date), as_dict=True)
        ytd_salary_cost = flt(ytd_result[0].total, 2) if ytd_result else 0

    return {
        "total_registered":   total_registered,
        "total_active":       total_active,
        "salary_structures":  salary_structures,
        "ssa_count":          ssa_count,
        "salary_components":  salary_components,
        "holiday_count":      holiday_count,
        "on_hold_count":      on_hold_count,
        "without_assignment": without_assignment,
        "esic_filled":        esic_filled,
        "pf_filled":          pf_filled,
        "gender_counts":      gender_counts,
        "gender_missing":     gender_missing,
        "ytd_salary_cost":    ytd_salary_cost,
        "dept_count":         frappe.db.count("Department"),
        "designation_count":  frappe.db.count("Designation"),
        "category_count":     frappe.db.count("Category"),
        "division_count":     frappe.db.count("Division"),
    }


# ---------------------------------------------------------------------------
# Monthly tracker
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_monthly_data(company, from_date, to_date):
    from_date = getdate(from_date)
    to_date   = getdate(to_date)

    permitted = _get_permitted_employees()
    if permitted is not None and len(permitted) == 0:
        return []

    PRESENT_STATUSES = {"Present", "On Tour", "Earned Leave", "Casual Leave",
                        "Comp Off", "Earned Comp Off"}

    rows         = []
    prev_closing = None

    for month_start, month_end in _month_range(from_date, to_date):

        active_recs  = _active_in_month(company, month_start, month_end, permitted)
        active_count = len(active_recs)
        active_names = {r.name for r in active_recs}

        # Joined / left — apply permitted filter
        joined_filters = {"company": company, "date_of_joining": ["between", [month_start, month_end]]}
        left_filters   = {"company": company, "left_date":       ["between", [month_start, month_end]]}
        if permitted is not None:
            joined_filters["name"] = ["in", permitted]
            left_filters["name"]   = ["in", permitted]

        joined = frappe.db.count("Company Link", filters=joined_filters)
        left   = frappe.db.count("Company Link", filters=left_filters)

        if prev_closing is not None:
            opening = prev_closing
        else:
            opening = active_count - joined + left

        closing      = active_count
        prev_closing = closing

        # Attendance — filtered by active_names (already permission-scoped)
        att_filters = {
            "company":         company,
            "attendance_date": ["between", [month_start, month_end]]
        }
        if active_names:
            att_filters["employee"] = ["in", list(active_names)]

        att_records = frappe.db.get_all(
            "Attendance",
            filters=att_filters,
            fields=["employee", "status"]
        ) if active_names else []

        att_total      = len(att_records)
        emp_att_map    = {}
        half_day_total = 0
        for r in att_records:
            emp = r["employee"]
            if emp not in emp_att_map:
                emp_att_map[emp] = 0
            if r["status"] in PRESENT_STATUSES:
                emp_att_map[emp] += 1
            elif r["status"] == "Half Day":
                emp_att_map[emp] += 0.5
                half_day_total += 1

        min_att = min(emp_att_map.values()) if emp_att_map else 0
        max_att = max(emp_att_map.values()) if emp_att_map else 0

        emps_with_att    = len(set(r["employee"] for r in att_records) & active_names)
        att_coverage_pct = round((emps_with_att / active_count * 100)) if active_count else 0
        absent_total     = sum(1 for r in att_records if r["status"] == "Absent")
        lwp_total        = sum(1 for r in att_records if r["status"] == "LWP")

        slip_filters = {
            "company":    company,
            "start_date": [">=", month_start],
            "end_date":   ["<=", month_end],
            "docstatus":  1
        }
        if permitted is not None:
            slip_filters["employee"] = ["in", permitted]
        slip_count = frappe.db.count("Salary Slip", filters=slip_filters)

        hold_filters = {
            "company":   company,
            "month":     month_start.strftime("%B"),
            "year":      str(month_start.year),
            "status":    "On Hold",
            "docstatus": 1
        }
        if permitted is not None:
            hold_filters["employee"] = ["in", permitted]
        hold_count = frappe.db.count("Employee Salary Hold", filters=hold_filters)

        ssa_filters = {
            "company": company, "docstatus": 1,
            "from_date": ["<=", month_end], "to_date": [">=", month_start]
        }
        if permitted is not None:
            ssa_filters["employee"] = ["in", permitted]
        ssa_this_month = set(frappe.db.get_all(
            "Salary Structure Assignment", filters=ssa_filters, pluck="employee"
        ))

        last3_start = month_end - relativedelta(days=2)
        late_joiners = {
            r.name for r in active_recs
            if r.date_of_joining and getdate(r.date_of_joining) >= last3_start
        }
        adjusted_active_names = active_names - late_joiners
        adjusted_active_count = len(adjusted_active_names)
        adjusted_emps_with_att = len(
            set(r["employee"] for r in att_records) & adjusted_active_names
        )

        on_hold_emps_filters = {
            "company":   company,
            "month":     month_start.strftime("%B"),
            "year":      str(month_start.year),
            "status":    "On Hold",
            "docstatus": 1
        }
        if permitted is not None:
            on_hold_emps_filters["employee"] = ["in", permitted]
        on_hold_emps = set(frappe.db.get_all(
            "Employee Salary Hold", filters=on_hold_emps_filters, pluck="employee"
        ))

        active_names_excl_hold = active_names - on_hold_emps
        ready_ssa = active_names_excl_hold.issubset(ssa_this_month)

        expected_slips = max(0, active_count - hold_count)
        ready_slips    = (slip_count >= expected_slips) and (expected_slips > 0)
        slips_pending  = max(0, active_count - hold_count - slip_count)
        attrition_pct  = round((left / opening * 100), 1) if opening > 0 else 0

        checks = [
            adjusted_active_count == 0 or adjusted_emps_with_att >= adjusted_active_count,
            ready_ssa,
            hold_count == 0,
            ready_slips
        ]
        readiness_score = sum(1 for c in checks if c)

        rows.append({
            "month":            month_start.strftime("%b %Y"),
            "month_key":        month_start.strftime("%Y-%m"),
            "month_name":       month_start.strftime("%B"),
            "month_year":       str(month_start.year),
            "opening":          opening,
            "joined":           joined,
            "left":             left,
            "closing":          closing,
            "attrition_pct":    attrition_pct,
            "active_count":     active_count,
            "att_total":        att_total,
            "att_coverage_pct": att_coverage_pct,
            "emps_with_att":    emps_with_att,
            "half_day_total":   half_day_total,
            "absent_total":     absent_total,
            "lwp_total":        lwp_total,
            "min_att":          min_att,
            "max_att":          max_att,
            "slip_count":       slip_count,
            "hold_count":       hold_count,
            "slips_pending":    slips_pending,
            "readiness_score":  readiness_score,
            "ready_att":        adjusted_active_count == 0 or adjusted_emps_with_att >= adjusted_active_count,
            "ready_ssa":        ready_ssa,
            "ready_no_holds":   hold_count == 0,
            "ready_slips":      ready_slips,
        })

    return rows


# ---------------------------------------------------------------------------
# Assignment expiry tracker
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_expiring_assignments(company, from_date, to_date):
    today_date = getdate(today())
    window_end = add_days(today_date, 30)
    permitted  = _get_permitted_employees()

    filters = {
        "company":   company,
        "docstatus": 1,
        "to_date":   ["between", [today_date, window_end]]
    }
    if permitted is not None:
        if len(permitted) == 0:
            return []
        filters["employee"] = ["in", permitted]

    rows = frappe.db.get_all(
        "Salary Structure Assignment",
        filters=filters,
        fields=["employee", "employee_name", "salary_structure", "from_date", "to_date"],
        order_by="to_date asc"
    )

    for r in rows:
        exp = getdate(r.to_date)
        r["days_remaining"] = (exp - today_date).days

    return rows


# ---------------------------------------------------------------------------
# Employee classification breakdown
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_classification_data(company):
    permitted = _get_permitted_employees()

    filters = {"company": company, "is_active": 1}
    if permitted is not None:
        if len(permitted) == 0:
            return {"rows": [], "active_skill_types": []}
        filters["name"] = ["in", permitted]

    emp_rows = frappe.db.get_all(
        "Company Link",
        filters=filters,
        fields=["category", "skill_type", "department"]
    )

    cat_names = list({r.category for r in emp_rows if r.category})
    has_subtype_map = {}
    if cat_names:
        cat_docs = frappe.db.get_all(
            "Category",
            filters={"name": ["in", cat_names]},
            fields=["category", "has_subtype"]
        )
        has_subtype_map = {c.category: bool(c.has_subtype) for c in cat_docs}

    breakdown = {}
    for r in emp_rows:
        cat     = r.category or "Unassigned"
        has_sub = has_subtype_map.get(cat, False)
        skill   = r.skill_type if (has_sub and r.skill_type) else None
        dept    = r.department or "Unassigned"

        if cat not in breakdown:
            breakdown[cat] = {"has_subtype": has_sub, "counts": {}, "total": 0, "by_department": {}}

        breakdown[cat]["total"] += 1
        if has_sub and skill:
            breakdown[cat]["counts"][skill] = breakdown[cat]["counts"].get(skill, 0) + 1
        if dept not in breakdown[cat]["by_department"]:
            breakdown[cat]["by_department"][dept] = 0
        breakdown[cat]["by_department"][dept] += 1

    active_skill_types = set()
    for cat, data in breakdown.items():
        for skill, cnt in data["counts"].items():
            if cnt > 0:
                active_skill_types.add(skill)

    result = []
    for cat, data in sorted(breakdown.items()):
        result.append({
            "category":      cat,
            "has_subtype":   data["has_subtype"],
            "counts":        data["counts"],
            "total":         data["total"],
            "by_department": data["by_department"],
        })

    return {"rows": result, "active_skill_types": sorted(list(active_skill_types))}


# ---------------------------------------------------------------------------
# Department-wise headcount
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_department_headcount(company):
    permitted = _get_permitted_employees()

    filters = {"company": company, "is_active": 1}
    if permitted is not None:
        if len(permitted) == 0:
            return {"rows": [], "total": 0}
        filters["name"] = ["in", permitted]

    rows = frappe.db.get_all("Company Link", filters=filters, fields=["department"])
    counts = {}
    for r in rows:
        dept = r.department or "Unassigned"
        counts[dept] = counts.get(dept, 0) + 1

    total = sum(counts.values())
    result = sorted(
        [{"department": d, "count": c, "pct": round(c / total * 100) if total else 0}
         for d, c in counts.items()],
        key=lambda x: x["count"], reverse=True
    )
    return {"rows": result, "total": total}


# ---------------------------------------------------------------------------
# POPUP: Employees on salary hold
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_on_hold_employees(company, from_date, to_date):
    from_date = getdate(from_date)
    to_date   = getdate(to_date)
    permitted = _get_permitted_employees()

    valid_periods = set()
    cursor = from_date.replace(day=1)
    while cursor <= to_date:
        valid_periods.add((cursor.strftime("%B"), str(cursor.year)))
        cursor = (cursor + relativedelta(months=1)).replace(day=1)

    hold_filters = {"company": company, "status": "On Hold", "docstatus": 1}
    if permitted is not None:
        if len(permitted) == 0:
            return []
        hold_filters["employee"] = ["in", permitted]

    rows = frappe.db.get_all(
        "Employee Salary Hold",
        filters=hold_filters,
        fields=["employee", "employee_name", "hold_date", "hold_reason",
                "department", "designation", "branch", "month", "year"]
    )

    rows     = [r for r in rows if (r.month, r.year) in valid_periods]
    emp_ids  = [r.employee for r in rows if r.employee]
    name_map = _get_employee_names(emp_ids)

    return sorted([{
        "employee":    r.employee,
        "full_name":   name_map.get(r.employee, r.employee_name or r.employee),
        "month_year":  f"{r.month} {r.year}" if r.month and r.year else "—",
        "hold_date":   str(r.hold_date) if r.hold_date else "—",
        "hold_reason": r.hold_reason or "—",
        "department":  r.department or "—",
    } for r in rows], key=lambda x: x["full_name"])


# ---------------------------------------------------------------------------
# POPUP: Month-specific on hold employees
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_month_on_hold_employees(company, month_key):
    year, month = month_key.split("-")
    month_start = getdate(f"{year}-{month}-01")
    month_name  = month_start.strftime("%B")
    permitted   = _get_permitted_employees()

    hold_filters = {
        "company":   company,
        "month":     month_name,
        "year":      year,
        "status":    "On Hold",
        "docstatus": 1
    }
    if permitted is not None:
        if len(permitted) == 0:
            return []
        hold_filters["employee"] = ["in", permitted]

    rows     = frappe.db.get_all(
        "Employee Salary Hold",
        filters=hold_filters,
        fields=["employee", "employee_name", "hold_date", "hold_reason", "department"]
    )
    emp_ids  = [r.employee for r in rows if r.employee]
    name_map = _get_employee_names(emp_ids)

    return sorted([{
        "employee":    r.employee,
        "full_name":   name_map.get(r.employee, r.employee_name or r.employee),
        "hold_date":   str(r.hold_date) if r.hold_date else "—",
        "hold_reason": r.hold_reason or "—",
        "department":  r.department or "—",
    } for r in rows], key=lambda x: x["full_name"])


# ---------------------------------------------------------------------------
# POPUP: Employees without assignment
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_employees_without_assignment(company, from_date, to_date):
    from_date = getdate(from_date)
    to_date   = getdate(to_date)
    permitted = _get_permitted_employees()

    active_filters = {"company": company, "is_active": 1}
    if permitted is not None:
        if len(permitted) == 0:
            return []
        active_filters["name"] = ["in", permitted]

    active = frappe.db.get_all(
        "Company Link",
        filters=active_filters,
        fields=["name", "date_of_joining"]
    )

    ssa_filters = {
        "company": company, "docstatus": 1,
        "from_date": ["<=", to_date], "to_date": [">=", from_date]
    }
    if permitted is not None:
        ssa_filters["employee"] = ["in", permitted]

    assigned_set = set(frappe.db.get_all(
        "Salary Structure Assignment", filters=ssa_filters, pluck="employee"
    ))

    unassigned = [e for e in active if e.name not in assigned_set]
    name_map   = _get_employee_names([e.name for e in unassigned])

    return sorted([{
        "employee":        emp.name,
        "full_name":       name_map.get(emp.name, emp.name),
        "date_of_joining": str(emp.date_of_joining) if emp.date_of_joining else ""
    } for emp in unassigned], key=lambda x: x["full_name"])


# ---------------------------------------------------------------------------
# POPUP: Employees with no attendance in a month
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_employees_no_attendance(company, month_key):
    year, month = month_key.split("-")
    month_start = getdate(f"{year}-{month}-01")
    month_end   = getdate(get_last_day(month_start))
    permitted   = _get_permitted_employees()

    active_recs  = _active_in_month(company, month_start, month_end, permitted)
    active_names = {r.name for r in active_recs}

    if not active_names:
        return []

    emps_with_att = set(frappe.db.get_all(
        "Attendance",
        filters={
            "company":         company,
            "employee":        ["in", list(active_names)],
            "attendance_date": ["between", [month_start, month_end]]
        },
        pluck="employee"
    ))

    no_att_names = active_names - emps_with_att
    if not no_att_names:
        return []

    rows     = frappe.db.get_all(
        "Company Link",
        filters={"name": ["in", list(no_att_names)]},
        fields=["name", "date_of_joining"]
    )
    name_map = _get_employee_names(list(no_att_names))

    return sorted([{
        "employee":        r.name,
        "full_name":       name_map.get(r.name, r.name),
        "date_of_joining": str(r.date_of_joining) if r.date_of_joining else ""
    } for r in rows], key=lambda x: x["full_name"])


# ---------------------------------------------------------------------------
# POPUP: Employees by category and skill type
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_employees_by_category_skill(company, category, skill_type="", department=""):
    permitted = _get_permitted_employees()

    filters = {"company": company, "is_active": 1, "category": category}
    if skill_type:
        filters["skill_type"] = skill_type
    if department:
        filters["department"] = department
    if permitted is not None:
        if len(permitted) == 0:
            return []
        filters["name"] = ["in", permitted]

    rows     = frappe.db.get_all(
        "Company Link",
        filters=filters,
        fields=["name", "date_of_joining", "skill_type", "designation", "department"]
    )
    name_map = _get_employee_names([r.name for r in rows])

    return sorted([{
        "employee":        r.name,
        "full_name":       name_map.get(r.name, r.name),
        "date_of_joining": str(r.date_of_joining) if r.date_of_joining else "",
        "skill_type":      r.skill_type or "—",
        "designation":     r.designation or "—",
        "department":      r.department or "—",
    } for r in rows], key=lambda x: x["full_name"])


# ---------------------------------------------------------------------------
# POPUP: Salary slip status for a month
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_salary_slip_status(company, month_key):
    year, month = month_key.split("-")
    month_start = getdate(f"{year}-{month}-01")
    month_end   = getdate(get_last_day(month_start))
    permitted   = _get_permitted_employees()

    active_recs = _active_in_month(company, month_start, month_end, permitted)
    name_map    = _get_employee_names([r.name for r in active_recs])

    slip_filters = {
        "company":    company,
        "start_date": [">=", month_start],
        "end_date":   ["<=", month_end],
        "docstatus":  1
    }
    if permitted is not None and len(permitted) > 0:
        slip_filters["employee"] = ["in", permitted]
    elif permitted is not None and len(permitted) == 0:
        return {"generated": [], "not_generated": []}

    slips   = frappe.db.get_all(
        "Salary Slip", filters=slip_filters, fields=["name", "employee", "net_salary"]
    )
    slip_map = {s.employee: s for s in slips}

    generated     = []
    not_generated = []

    for emp in active_recs:
        slip      = slip_map.get(emp.name)
        full_name = name_map.get(emp.name, emp.name)
        if slip:
            generated.append({
                "employee":   emp.name,
                "full_name":  full_name,
                "net_salary": flt(slip.net_salary, 2),
                "slip_name":  slip.name,
                "slip_url":   f"/app/salary-slip/{slip.name}",
            })
        else:
            not_generated.append({
                "employee":  emp.name,
                "full_name": full_name,
            })

    return {
        "generated":     sorted(generated,     key=lambda x: x["full_name"]),
        "not_generated": sorted(not_generated, key=lambda x: x["full_name"]),
    }


# ---------------------------------------------------------------------------
# POPUP: Head count employees by month and type
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_headcount_employees(company, month_key, hc_type):
    year, month = month_key.split("-")
    month_start = getdate(f"{year}-{month}-01")
    month_end   = getdate(get_last_day(month_start))
    permitted   = _get_permitted_employees()

    if hc_type == "joined":
        filters = {"company": company, "date_of_joining": ["between", [month_start, month_end]]}
        if permitted is not None:
            if len(permitted) == 0:
                return []
            filters["name"] = ["in", permitted]
        rows = frappe.db.get_all(
            "Company Link", filters=filters,
            fields=["name", "date_of_joining", "designation", "department"]
        )

    elif hc_type == "left":
        filters = {"company": company, "left_date": ["between", [month_start, month_end]]}
        if permitted is not None:
            if len(permitted) == 0:
                return []
            filters["name"] = ["in", permitted]
        rows = frappe.db.get_all(
            "Company Link", filters=filters,
            fields=["name", "date_of_joining", "left_date", "designation", "department"]
        )

    elif hc_type == "opening":
        day_before = month_start - relativedelta(days=1)
        filters    = {"company": company, "date_of_joining": ["<=", day_before]}
        if permitted is not None:
            if len(permitted) == 0:
                return []
            filters["name"] = ["in", permitted]
        all_rows = frappe.db.get_all(
            "Company Link", filters=filters,
            fields=["name", "date_of_joining", "left_date", "designation", "department"]
        )
        rows = [r for r in all_rows if not r.left_date or getdate(r.left_date) >= month_start]

    else:  # closing
        filters = {"company": company, "date_of_joining": ["<=", month_end]}
        if permitted is not None:
            if len(permitted) == 0:
                return []
            filters["name"] = ["in", permitted]
        all_rows = frappe.db.get_all(
            "Company Link", filters=filters,
            fields=["name", "date_of_joining", "left_date", "designation", "department"]
        )
        rows = [r for r in all_rows if not r.left_date or getdate(r.left_date) >= month_start]

    name_map = _get_employee_names([r.name for r in rows])

    return sorted([{
        "employee":        r.name,
        "full_name":       name_map.get(r.name, r.name),
        "date_of_joining": str(r.date_of_joining) if r.date_of_joining else "",
        "left_date":       str(r.get("left_date", "") or ""),
        "designation":     r.get("designation") or "—",
        "department":      r.get("department") or "—",
    } for r in rows], key=lambda x: x["full_name"])


# ---------------------------------------------------------------------------
# POPUP: Full attendance summary for a month
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_month_attendance_summary(company, month_key):
    year, month = month_key.split("-")
    month_start = getdate(f"{year}-{month}-01")
    month_end   = getdate(get_last_day(month_start))
    total_days  = calendar.monthrange(int(year), int(month))[1]
    permitted   = _get_permitted_employees()

    weekend_days = []
    for day in range(1, total_days + 1):
        d = getdate(f"{year}-{month}-{day:02d}")
        if d.weekday() >= 5:
            weekend_days.append(day)

    active_recs = _active_in_month(company, month_start, month_end, permitted)
    active_map  = {r.name: r for r in active_recs}

    if not active_map:
        return {"rows": [], "total_days": total_days, "weekend_days": weekend_days}

    att_filters = {
        "company":         company,
        "employee":        ["in", list(active_map.keys())],
        "attendance_date": ["between", [month_start, month_end]]
    }
    att_records = frappe.db.get_all(
        "Attendance", filters=att_filters, fields=["employee", "status", "attendance_date"]
    )

    STATUS_CODE = {
        "Present": "P", "On Tour": "T", "Absent": "A", "Half Day": "HD",
        "Holiday": "H", "Weekly Off": "WO", "LWP": "LWP",
        "Earned Leave": "EL", "Casual Leave": "CL", "Comp Off": "CO", "Earned Comp Off": "ECO",
    }
    STATUS_FIELDS = {
        "Present": "present", "On Tour": "on_tour", "Absent": "absent",
        "Half Day": "half_day", "Holiday": "holiday", "Weekly Off": "weekly_off",
        "LWP": "lwp", "Earned Leave": "earned_leave", "Casual Leave": "casual_leave",
        "Comp Off": "comp_off", "Earned Comp Off": "earned_comp_off",
    }

    emp_data = {}
    for name in active_map:
        emp_data[name] = {k: 0 for k in STATUS_FIELDS.values()}
        for d in range(1, total_days + 1):
            emp_data[name][f"day_{d}"] = ""

    for r in att_records:
        emp = r["employee"]
        if emp not in emp_data:
            continue
        day   = getdate(r["attendance_date"]).day
        code  = STATUS_CODE.get(r["status"], "")
        field = STATUS_FIELDS.get(r["status"])
        emp_data[emp][f"day_{day}"] = code
        if field:
            emp_data[emp][field] += 1

    name_map = _get_employee_names([r.name for r in active_recs])

    result = []
    for emp_id, counts in emp_data.items():
        row = {"employee": emp_id, "full_name": name_map.get(emp_id, emp_id)}
        row.update(counts)
        result.append(row)

    return {
        "rows":         sorted(result, key=lambda x: x["full_name"]),
        "total_days":   total_days,
        "weekend_days": weekend_days
    }