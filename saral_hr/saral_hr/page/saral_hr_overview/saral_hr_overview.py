import frappe
import json
from frappe.utils import getdate, get_last_day, flt, today, add_days
from dateutil.relativedelta import relativedelta
import calendar


# ─── Permission helper ────────────────────────────────────────────────────────

def _get_permitted_employees():
    user = frappe.session.user
    if "System Manager" in frappe.get_roles(user):
        return None
    user_permissions = frappe.permissions.get_user_permissions(user)
    if "Employee" in user_permissions and user_permissions["Employee"]:
        permitted = [p.get("doc") for p in user_permissions["Employee"] if p.get("doc")]
        return permitted if permitted else None
    return None


def _emp_filter_clause(permitted, alias="cl", param_prefix="pe"):
    if permitted is None:
        return "", {}
    if len(permitted) == 0:
        return None, None
    placeholders = ", ".join([f"%({param_prefix}_{i})s" for i in range(len(permitted))])
    clause = f"AND {alias}.name IN ({placeholders})"
    params = {f"{param_prefix}_{i}": e for i, e in enumerate(permitted)}
    return clause, params


# ─── Parse companies arg ──────────────────────────────────────────────────────

def _parse_companies(companies):
    """Accept either a JSON string list or a plain string (single company)."""
    if isinstance(companies, list):
        return [c for c in companies if c]
    try:
        parsed = json.loads(companies)
        if isinstance(parsed, list):
            return [c for c in parsed if c]
        return [str(parsed)]
    except Exception:
        return [companies] if companies else []


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
    """Employees employed at any point in [month_start, month_end].

    Uses joining/left dates only — not Company Link.is_active — so historical
    months still include people who have since left.
    """
    filters = {
        "company":         company,
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
    from frappe.permissions import get_user_permissions
    user_permissions = get_user_permissions(user)
    if "Company" in user_permissions and user_permissions["Company"]:
        permitted_companies = [p.get("doc") for p in user_permissions["Company"] if p.get("doc")]
        if permitted_companies:
            return frappe.db.get_all(
                "Company",
                filters={"company": ["in", permitted_companies]},
                pluck="company",
                order_by="company asc"
            )
    return frappe.db.get_all("Company", pluck="company", order_by="company asc")


# ---------------------------------------------------------------------------
# KPI data — aggregated across companies
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_kpi_data(companies, from_date, to_date):
    company_list = _parse_companies(companies)
    from_date    = getdate(from_date)
    to_date      = getdate(to_date)
    permitted    = _get_permitted_employees()

    agg = {
        "total_registered": 0, "total_active": 0,
        "salary_structures": 0, "ssa_count": 0,
        "holiday_count": 0, "on_hold_count": 0,
        "without_assignment": 0, "esic_filled": 0, "pf_filled": 0,
        "ytd_salary_cost": 0.0,
        "gender_counts": {}, "gender_missing": 0,
        "dept_count": 0, "designation_count": 0,
        "category_count": 0, "division_count": 0,
        "salary_components": 0,
    }

    agg["dept_count"]        = frappe.db.count("Department")
    agg["designation_count"] = frappe.db.count("Designation")
    agg["category_count"]    = frappe.db.count("Category")
    agg["division_count"]    = frappe.db.count("Division")
    agg["salary_components"] = frappe.db.count("Salary Component")

    _seen_holiday_lists = set()

    for company in company_list:
        if permitted is not None:
            if len(permitted) == 0:
                pass
            else:
                agg["total_registered"] += frappe.db.count("Company Link", {"company": company, "name": ["in", permitted]})
                agg["total_active"]     += frappe.db.count("Company Link", {"company": company, "is_active": 1, "name": ["in", permitted]})
        else:
            agg["total_registered"] += frappe.db.count("Company Link", filters={"company": company})
            agg["total_active"]     += frappe.db.count("Company Link", filters={"company": company, "is_active": 1})

        agg["salary_structures"] += frappe.db.count("Salary Structure", filters={"company": company})

        ssa_filters = {
            "company": company, "docstatus": 1,
            "from_date": ["<=", to_date], "to_date": [">=", from_date]
        }
        if permitted is not None:
            if len(permitted) == 0:
                pass
            else:
                ssa_filters["employee"] = ["in", permitted]
                agg["ssa_count"] += frappe.db.count("Salary Structure Assignment", filters=ssa_filters)
        else:
            agg["ssa_count"] += frappe.db.count("Salary Structure Assignment", filters=ssa_filters)

        from saral_hr.utils.holiday_utils import get_holiday_list_for_date
        holiday_list_name = get_holiday_list_for_date(frappe.utils.today(), company)
        if holiday_list_name and holiday_list_name not in _seen_holiday_lists:
            _seen_holiday_lists.add(holiday_list_name)
            agg["holiday_count"] += frappe.db.count("Holiday", filters={
                "parent":       holiday_list_name,
                "holiday_date": ["between", [from_date, to_date]]
            })

        hold_filters = {"company": company, "status": "On Hold", "docstatus": 1}
        if permitted is not None and len(permitted) > 0:
            hold_filters["employee"] = ["in", permitted]
        if not (permitted is not None and len(permitted) == 0):
            agg["on_hold_count"] += frappe.db.count("Employee Salary Hold", filters=hold_filters)

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
        agg["without_assignment"] += len([e for e in active_employees if e not in assigned_set])

        emp_name_filters = {"company": company, "is_active": 1}
        if permitted is not None and len(permitted) > 0:
            emp_name_filters["name"] = ["in", permitted]
        emp_names = frappe.db.get_all(
            "Company Link", filters=emp_name_filters, pluck="employee"
        ) if not (permitted is not None and len(permitted) == 0) else []

        if emp_names:
            agg["esic_filled"] += frappe.db.count("Employee", filters={"name": ["in", emp_names], "esic_number": ["!=", ""]})
            agg["pf_filled"]   += frappe.db.count("Employee", filters={"name": ["in", emp_names], "pf_uan_number": ["!=", ""]})
            genders = frappe.db.get_all("Employee", filters={"name": ["in", emp_names]}, fields=["gender"])
            for g in genders:
                key = g.gender or "Not specified"
                agg["gender_counts"][key] = agg["gender_counts"].get(key, 0) + 1
            agg["gender_missing"] += agg["gender_counts"].get("Not specified", 0)

        if not (permitted is not None and len(permitted) == 0):
            if permitted is not None:
                placeholders = ", ".join(["%s"] * len(permitted))
                ytd_result   = frappe.db.sql(f"""
                    SELECT COALESCE(SUM(net_salary), 0) as total
                    FROM `tabSalary Slip`
                    WHERE company = %s AND docstatus = 1
                      AND start_date >= %s AND end_date <= %s
                      AND employee IN ({placeholders})
                """, (company, from_date, to_date) + tuple(permitted), as_dict=True)
            else:
                ytd_result = frappe.db.sql("""
                    SELECT COALESCE(SUM(net_salary), 0) as total
                    FROM `tabSalary Slip`
                    WHERE company = %s AND docstatus = 1
                      AND start_date >= %s AND end_date <= %s
                """, (company, from_date, to_date), as_dict=True)
            agg["ytd_salary_cost"] += flt(ytd_result[0].total, 2) if ytd_result else 0

    return agg


# ---------------------------------------------------------------------------
# Monthly tracker — aggregated across companies
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_monthly_data(companies, from_date, to_date):
    company_list = _parse_companies(companies)
    from_date    = getdate(from_date)
    to_date      = getdate(to_date)
    permitted    = _get_permitted_employees()

    if permitted is not None and len(permitted) == 0:
        return []

    PRESENT_STATUSES = {"Present", "On Tour", "Earned Leave", "Casual Leave",
                        "Comp Off", "Earned Comp Off"}

    month_map = {}

    for company in company_list:
        prev_closing = None

        for month_start, month_end in _month_range(from_date, to_date):
            mk = month_start.strftime("%Y-%m")

            active_recs  = _active_in_month(company, month_start, month_end, permitted)
            active_count = len(active_recs)
            active_names = {r.name for r in active_recs}

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

            att_filters = {"company": company, "attendance_date": ["between", [month_start, month_end]]}
            if active_names:
                att_filters["employee"] = ["in", list(active_names)]

            att_records = frappe.db.get_all(
                "Attendance", filters=att_filters, fields=["employee", "status"]
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

            emps_with_att = len(set(r["employee"] for r in att_records) & active_names)
            absent_total  = sum(1 for r in att_records if r["status"] == "Absent")
            lwp_total     = sum(1 for r in att_records if r["status"] == "LWP")
            min_att       = min(emp_att_map.values()) if emp_att_map else 0
            max_att       = max(emp_att_map.values()) if emp_att_map else 0

            slip_filters = {
                "company": company, "start_date": [">=", month_start],
                "end_date": ["<=", month_end], "docstatus": 1
            }
            if active_names:
                slip_filters["employee"] = ["in", list(active_names)]
                slip_count = frappe.db.count("Salary Slip", filters=slip_filters)
            else:
                slip_count = 0

            hold_filters = {
                "company": company, "month": month_start.strftime("%B"),
                "year": str(month_start.year), "status": "On Hold", "docstatus": 1
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

            on_hold_emps = set(frappe.db.get_all(
                "Employee Salary Hold",
                filters={**hold_filters},
                pluck="employee"
            ))
            last3_start = month_end - relativedelta(days=2)
            late_joiners = {
                r.name for r in active_recs
                if r.date_of_joining and getdate(r.date_of_joining) >= last3_start
            }
            adjusted_active_names  = active_names - late_joiners
            adjusted_active_count  = len(adjusted_active_names)
            adjusted_emps_with_att = len(set(r["employee"] for r in att_records) & adjusted_active_names)
            active_names_excl_hold = active_names - on_hold_emps
            ready_ssa   = active_names_excl_hold.issubset(ssa_this_month)
            expected_slips = max(0, active_count - hold_count)
            ready_slips    = (slip_count >= expected_slips) and (expected_slips > 0)
            slips_pending  = max(0, active_count - hold_count - slip_count)
            attrition_pct  = round((left / opening * 100), 1) if opening > 0 else 0

            if mk not in month_map:
                month_map[mk] = {
                    "month":            month_start.strftime("%b %Y"),
                    "month_key":        mk,
                    "month_name":       month_start.strftime("%B"),
                    "month_year":       str(month_start.year),
                    "opening":          0, "joined": 0, "left": 0, "closing": 0,
                    "attrition_pct":    0,
                    "active_count":     0, "att_total": 0, "emps_with_att": 0,
                    "half_day_total":   0, "absent_total": 0, "lwp_total": 0,
                    "min_att":          0, "max_att": 0,
                    "slip_count":       0, "hold_count": 0, "slips_pending": 0,
                    "readiness_score":  0,
                    "ready_att":        True, "ready_ssa": True,
                    "ready_no_holds":   True, "ready_slips": True,
                    "_att_adj_active":  0, "_att_adj_with_att": 0,
                }

            m = month_map[mk]
            m["opening"]         += opening
            m["joined"]          += joined
            m["left"]            += left
            m["closing"]         += closing
            m["active_count"]    += active_count
            m["att_total"]       += att_total
            m["emps_with_att"]   += emps_with_att
            m["half_day_total"]  += half_day_total
            m["absent_total"]    += absent_total
            m["lwp_total"]       += lwp_total
            m["min_att"]          = min(m["min_att"], min_att) if m["min_att"] else min_att
            m["max_att"]          = max(m["max_att"], max_att)
            m["slip_count"]      += slip_count
            m["hold_count"]      += hold_count
            m["slips_pending"]   += slips_pending
            m["ready_att"]       = m["ready_att"]       and (adjusted_active_count == 0 or adjusted_emps_with_att >= adjusted_active_count)
            m["ready_ssa"]       = m["ready_ssa"]       and ready_ssa
            m["ready_no_holds"]  = m["ready_no_holds"]  and (hold_count == 0)
            m["ready_slips"]     = m["ready_slips"]     and ready_slips

    result = []
    for mk in sorted(month_map.keys()):
        m = month_map[mk]
        m["att_coverage_pct"] = round(m["emps_with_att"] / m["active_count"] * 100) if m["active_count"] else 0
        m["attrition_pct"]    = round(m["left"] / m["opening"] * 100, 1) if m["opening"] > 0 else 0
        m["readiness_score"]  = sum([
            1 if m["ready_att"]      else 0,
            1 if m["ready_ssa"]      else 0,
            1 if m["ready_no_holds"] else 0,
            1 if m["ready_slips"]    else 0,
        ])
        result.append(m)

    return result


# ---------------------------------------------------------------------------
# Assignment expiry tracker
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_expiring_assignments(companies, from_date, to_date):
    company_list = _parse_companies(companies)
    today_date   = getdate(today())
    window_end   = add_days(today_date, 30)
    permitted    = _get_permitted_employees()

    all_rows = []
    for company in company_list:
        filters = {
            "company": company, "docstatus": 1,
            "to_date": ["between", [today_date, window_end]]
        }
        if permitted is not None:
            if len(permitted) == 0:
                continue
            filters["employee"] = ["in", permitted]
        rows = frappe.db.get_all(
            "Salary Structure Assignment", filters=filters,
            fields=["employee", "employee_name", "salary_structure", "from_date", "to_date", "company"],
            order_by="to_date asc"
        )
        for r in rows:
            r["days_remaining"] = (getdate(r.to_date) - today_date).days
        all_rows.extend(rows)

    return sorted(all_rows, key=lambda x: x["days_remaining"])


# ---------------------------------------------------------------------------
# Employee classification breakdown
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_classification_data(companies):
    company_list = _parse_companies(companies)
    permitted    = _get_permitted_employees()

    all_emp_rows = []
    for company in company_list:
        filters = {"company": company, "is_active": 1}
        if permitted is not None:
            if len(permitted) == 0:
                continue
            filters["name"] = ["in", permitted]
        rows = frappe.db.get_all(
            "Company Link", filters=filters,
            fields=["category", "skill_type", "department"]
        )
        all_emp_rows.extend(rows)

    cat_names = list({r.category for r in all_emp_rows if r.category})
    has_subtype_map = {}
    if cat_names:
        cat_docs = frappe.db.get_all(
            "Category", filters={"name": ["in", cat_names]}, fields=["category", "has_subtype"]
        )
        has_subtype_map = {c.category: bool(c.has_subtype) for c in cat_docs}

    breakdown = {}
    for r in all_emp_rows:
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
            "category": cat, "has_subtype": data["has_subtype"],
            "counts": data["counts"], "total": data["total"],
            "by_department": data["by_department"],
        })

    return {"rows": result, "active_skill_types": sorted(list(active_skill_types))}


# ---------------------------------------------------------------------------
# Department-wise headcount
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_department_headcount(companies):
    company_list = _parse_companies(companies)
    permitted    = _get_permitted_employees()

    counts = {}
    for company in company_list:
        filters = {"company": company, "is_active": 1}
        if permitted is not None:
            if len(permitted) == 0:
                continue
            filters["name"] = ["in", permitted]
        rows = frappe.db.get_all("Company Link", filters=filters, fields=["department"])
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
def get_on_hold_employees(companies, from_date, to_date):
    company_list = _parse_companies(companies)
    from_date    = getdate(from_date)
    to_date      = getdate(to_date)
    permitted    = _get_permitted_employees()

    valid_periods = set()
    cursor = from_date.replace(day=1)
    while cursor <= to_date:
        valid_periods.add((cursor.strftime("%B"), str(cursor.year)))
        cursor = (cursor + relativedelta(months=1)).replace(day=1)

    all_rows = []
    for company in company_list:
        hold_filters = {"company": company, "status": "On Hold", "docstatus": 1}
        if permitted is not None:
            if len(permitted) == 0:
                continue
            hold_filters["employee"] = ["in", permitted]
        rows = frappe.db.get_all(
            "Employee Salary Hold", filters=hold_filters,
            fields=["employee", "employee_name", "hold_date", "hold_reason",
                    "department", "designation", "branch", "month", "year", "company"]
        )
        all_rows.extend([r for r in rows if (r.month, r.year) in valid_periods])

    emp_ids  = [r.employee for r in all_rows if r.employee]
    name_map = _get_employee_names(emp_ids)

    return sorted([{
        "employee":    r.employee,
        "full_name":   name_map.get(r.employee, r.employee_name or r.employee),
        "company":     r.company,
        "month_year":  f"{r.month} {r.year}" if r.month and r.year else "—",
        "hold_date":   str(r.hold_date) if r.hold_date else "—",
        "hold_reason": r.hold_reason or "—",
        "department":  r.department or "—",
    } for r in all_rows], key=lambda x: x["full_name"])


# ---------------------------------------------------------------------------
# POPUP: Month-specific on hold employees
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_month_on_hold_employees(companies, month_key):
    company_list = _parse_companies(companies)
    year, month  = month_key.split("-")
    month_start  = getdate(f"{year}-{month}-01")
    month_name   = month_start.strftime("%B")
    permitted    = _get_permitted_employees()

    all_rows = []
    for company in company_list:
        hold_filters = {
            "company": company, "month": month_name,
            "year": year, "status": "On Hold", "docstatus": 1
        }
        if permitted is not None:
            if len(permitted) == 0:
                continue
            hold_filters["employee"] = ["in", permitted]
        rows = frappe.db.get_all(
            "Employee Salary Hold", filters=hold_filters,
            fields=["employee", "employee_name", "hold_date", "hold_reason", "department", "company"]
        )
        all_rows.extend(rows)

    emp_ids  = [r.employee for r in all_rows if r.employee]
    name_map = _get_employee_names(emp_ids)

    return sorted([{
        "employee":    r.employee,
        "full_name":   name_map.get(r.employee, r.employee_name or r.employee),
        "company":     r.company,
        "hold_date":   str(r.hold_date) if r.hold_date else "—",
        "hold_reason": r.hold_reason or "—",
        "department":  r.department or "—",
    } for r in all_rows], key=lambda x: x["full_name"])


# ---------------------------------------------------------------------------
# POPUP: Employees without assignment
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_employees_without_assignment(companies, from_date, to_date):
    company_list = _parse_companies(companies)
    from_date    = getdate(from_date)
    to_date      = getdate(to_date)
    permitted    = _get_permitted_employees()

    all_unassigned = []
    for company in company_list:
        active_filters = {"company": company, "is_active": 1}
        if permitted is not None:
            if len(permitted) == 0:
                continue
            active_filters["name"] = ["in", permitted]
        active = frappe.db.get_all("Company Link", filters=active_filters, fields=["name", "date_of_joining"])

        ssa_filters = {
            "company": company, "docstatus": 1,
            "from_date": ["<=", to_date], "to_date": [">=", from_date]
        }
        if permitted is not None:
            ssa_filters["employee"] = ["in", permitted]
        assigned_set = set(frappe.db.get_all("Salary Structure Assignment", filters=ssa_filters, pluck="employee"))

        for e in active:
            if e.name not in assigned_set:
                all_unassigned.append({"name": e.name, "date_of_joining": e.date_of_joining, "company": company})

    name_map = _get_employee_names([e["name"] for e in all_unassigned])

    return sorted([{
        "employee":        emp["name"],
        "full_name":       name_map.get(emp["name"], emp["name"]),
        "company":         emp["company"],
        "date_of_joining": str(emp["date_of_joining"]) if emp["date_of_joining"] else ""
    } for emp in all_unassigned], key=lambda x: x["full_name"])


# ---------------------------------------------------------------------------
# POPUP: Employees with no attendance in a month
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_employees_no_attendance(companies, month_key):
    company_list = _parse_companies(companies)
    year, month  = month_key.split("-")
    month_start  = getdate(f"{year}-{month}-01")
    month_end    = getdate(get_last_day(month_start))
    permitted    = _get_permitted_employees()

    all_no_att = []
    for company in company_list:
        active_recs  = _active_in_month(company, month_start, month_end, permitted)
        active_names = {r.name for r in active_recs}
        if not active_names:
            continue
        emps_with_att = set(frappe.db.get_all(
            "Attendance",
            filters={"company": company, "employee": ["in", list(active_names)],
                     "attendance_date": ["between", [month_start, month_end]]},
            pluck="employee"
        ))
        no_att_names = active_names - emps_with_att
        if not no_att_names:
            continue
        rows = frappe.db.get_all(
            "Company Link", filters={"name": ["in", list(no_att_names)]},
            fields=["name", "date_of_joining"]
        )
        for r in rows:
            all_no_att.append({"name": r.name, "date_of_joining": r.date_of_joining, "company": company})

    if not all_no_att:
        return []

    name_map = _get_employee_names([e["name"] for e in all_no_att])
    return sorted([{
        "employee":        e["name"],
        "full_name":       name_map.get(e["name"], e["name"]),
        "company":         e["company"],
        "date_of_joining": str(e["date_of_joining"]) if e["date_of_joining"] else ""
    } for e in all_no_att], key=lambda x: x["full_name"])


# ---------------------------------------------------------------------------
# POPUP: Employees by category and skill type
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_employees_by_category_skill(companies, category, skill_type="", department=""):
    company_list = _parse_companies(companies)
    permitted    = _get_permitted_employees()

    all_rows = []
    for company in company_list:
        filters = {"company": company, "is_active": 1, "category": category}
        if skill_type:
            filters["skill_type"] = skill_type
        if department:
            filters["department"] = department
        if permitted is not None:
            if len(permitted) == 0:
                continue
            filters["name"] = ["in", permitted]
        rows = frappe.db.get_all(
            "Company Link", filters=filters,
            fields=["name", "date_of_joining", "skill_type", "designation", "department"]
        )
        for r in rows:
            r["company"] = company
        all_rows.extend(rows)

    name_map = _get_employee_names([r.name for r in all_rows])
    return sorted([{
        "employee":        r.name,
        "full_name":       name_map.get(r.name, r.name),
        "company":         r["company"],
        "date_of_joining": str(r.date_of_joining) if r.date_of_joining else "",
        "skill_type":      r.skill_type or "—",
        "designation":     r.designation or "—",
        "department":      r.department or "—",
    } for r in all_rows], key=lambda x: x["full_name"])


# ---------------------------------------------------------------------------
# POPUP: Salary slip status for a month
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_salary_slip_status(companies, month_key):
    company_list = _parse_companies(companies)
    year, month  = month_key.split("-")
    month_start  = getdate(f"{year}-{month}-01")
    month_end    = getdate(get_last_day(month_start))
    permitted    = _get_permitted_employees()

    generated     = []
    not_generated = []

    for company in company_list:
        active_recs = _active_in_month(company, month_start, month_end, permitted)
        name_map    = _get_employee_names([r.name for r in active_recs])

        slip_filters = {
            "company": company, "start_date": [">=", month_start],
            "end_date": ["<=", month_end], "docstatus": 1
        }
        if permitted is not None and len(permitted) > 0:
            slip_filters["employee"] = ["in", permitted]
        elif permitted is not None and len(permitted) == 0:
            continue

        slips    = frappe.db.get_all("Salary Slip", filters=slip_filters, fields=["name", "employee", "net_salary"])
        slip_map = {s.employee: s for s in slips}

        for emp in active_recs:
            slip      = slip_map.get(emp.name)
            full_name = name_map.get(emp.name, emp.name)
            if slip:
                generated.append({
                    "employee": emp.name, "full_name": full_name,
                    "net_salary": flt(slip.net_salary, 2),
                    "slip_name": slip.name, "slip_url": f"/app/salary-slip/{slip.name}",
                    "company": company,
                })
            else:
                not_generated.append({
                    "employee": emp.name, "full_name": full_name, "company": company
                })

    return {
        "generated":     sorted(generated,     key=lambda x: x["full_name"]),
        "not_generated": sorted(not_generated, key=lambda x: x["full_name"]),
    }


# ---------------------------------------------------------------------------
# POPUP: Head count employees by month and type
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_headcount_employees(companies, month_key, hc_type):
    company_list = _parse_companies(companies)
    year, month  = month_key.split("-")
    month_start  = getdate(f"{year}-{month}-01")
    month_end    = getdate(get_last_day(month_start))
    permitted    = _get_permitted_employees()

    all_rows = []
    for company in company_list:
        if hc_type == "joined":
            filters = {"company": company, "date_of_joining": ["between", [month_start, month_end]]}
            if permitted is not None:
                if len(permitted) == 0: continue
                filters["name"] = ["in", permitted]
            rows = frappe.db.get_all("Company Link", filters=filters,
                fields=["name", "date_of_joining", "designation", "department"])

        elif hc_type == "left":
            filters = {"company": company, "left_date": ["between", [month_start, month_end]]}
            if permitted is not None:
                if len(permitted) == 0: continue
                filters["name"] = ["in", permitted]
            rows = frappe.db.get_all("Company Link", filters=filters,
                fields=["name", "date_of_joining", "left_date", "designation", "department"])

        elif hc_type == "opening":
            day_before = month_start - relativedelta(days=1)
            filters    = {"company": company, "date_of_joining": ["<=", day_before]}
            if permitted is not None:
                if len(permitted) == 0: continue
                filters["name"] = ["in", permitted]
            rr = frappe.db.get_all("Company Link", filters=filters,
                fields=["name", "date_of_joining", "left_date", "designation", "department"])
            rows = [r for r in rr if not r.left_date or getdate(r.left_date) >= month_start]

        else:  # closing
            filters = {"company": company, "date_of_joining": ["<=", month_end]}
            if permitted is not None:
                if len(permitted) == 0: continue
                filters["name"] = ["in", permitted]
            rr = frappe.db.get_all("Company Link", filters=filters,
                fields=["name", "date_of_joining", "left_date", "designation", "department"])
            rows = [r for r in rr if not r.left_date or getdate(r.left_date) >= month_start]

        for r in rows:
            r["company"] = company
        all_rows.extend(rows)

    name_map = _get_employee_names([r.name for r in all_rows])
    return sorted([{
        "employee":        r.name,
        "full_name":       name_map.get(r.name, r.name),
        "company":         r["company"],
        "date_of_joining": str(r.date_of_joining) if r.date_of_joining else "",
        "left_date":       str(r.get("left_date", "") or ""),
        "designation":     r.get("designation") or "—",
        "department":      r.get("department") or "—",
    } for r in all_rows], key=lambda x: x["full_name"])


# ---------------------------------------------------------------------------
# POPUP: Full attendance summary for a month
# *** FIX: company field added to each row so JS filter works correctly ***
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_month_attendance_summary(companies, month_key):
    company_list = _parse_companies(companies)
    year, month  = month_key.split("-")
    month_start  = getdate(f"{year}-{month}-01")
    month_end    = getdate(get_last_day(month_start))
    total_days   = calendar.monthrange(int(year), int(month))[1]
    permitted    = _get_permitted_employees()

    weekend_days = []
    for day in range(1, total_days + 1):
        d = getdate(f"{year}-{month}-{day:02d}")
        if d.weekday() >= 5:
            weekend_days.append(day)

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

    # emp_id -> { ...counts, day_1..day_N, company }
    emp_data    = {}
    # Track which company each employee belongs to (first company wins for multi-link edge case)
    emp_company = {}

    for company in company_list:
        active_recs = _active_in_month(company, month_start, month_end, permitted)

        for emp_rec in active_recs:
            name = emp_rec.name
            if name not in emp_data:
                emp_data[name]    = {k: 0 for k in STATUS_FIELDS.values()}
                emp_company[name] = company          # ← store company
                for d in range(1, total_days + 1):
                    emp_data[name][f"day_{d}"] = ""
            # If employee appeared in a previous company loop, keep first assignment
            # (edge case: same employee linked to multiple companies)

        active_map = {r.name: r for r in active_recs}
        if not active_map:
            continue

        att_records = frappe.db.get_all(
            "Attendance",
            filters={
                "company":         company,
                "employee":        ["in", list(active_map.keys())],
                "attendance_date": ["between", [month_start, month_end]]
            },
            fields=["employee", "status", "attendance_date"]
        )
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

    all_emp_ids = list(emp_data.keys())
    name_map    = _get_employee_names(all_emp_ids)

    result = []
    for emp_id, counts in emp_data.items():
        row = {
            "employee":  emp_id,
            "full_name": name_map.get(emp_id, emp_id),
            "company":   emp_company.get(emp_id, ""),   # ← company field in response
        }
        row.update(counts)
        result.append(row)

    return {
        "rows":         sorted(result, key=lambda x: x["full_name"]),
        "total_days":   total_days,
        "weekend_days": weekend_days,
    }


# ---------------------------------------------------------------------------
# POPUP: All registered employees (active + inactive) across selected companies
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_registered_employees(companies):
    company_list = _parse_companies(companies)
    permitted    = _get_permitted_employees()

    all_rows = []
    for company in company_list:
        filters = {"company": company}
        if permitted is not None:
            if len(permitted) == 0:
                continue
            filters["name"] = ["in", permitted]
        rows = frappe.db.get_all(
            "Company Link",
            filters=filters,
            fields=["name", "date_of_joining", "left_date", "designation", "department", "is_active"]
        )
        for r in rows:
            r["company"] = company
        all_rows.extend(rows)

    name_map = _get_employee_names([r.name for r in all_rows])
    return sorted([{
        "employee":        r.name,
        "full_name":       name_map.get(r.name, r.name),
        "company":         r["company"],
        "department":      r.get("department") or "—",
        "designation":     r.get("designation") or "—",
        "date_of_joining": str(r.date_of_joining) if r.date_of_joining else "",
        "left_date":       str(r.left_date) if r.left_date else "",
        "status":          "Active" if r.is_active else "Inactive",
    } for r in all_rows], key=lambda x: x["full_name"])


# ---------------------------------------------------------------------------
# POPUP: Currently active employees across selected companies
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_active_employees(companies):
    company_list = _parse_companies(companies)
    permitted    = _get_permitted_employees()

    all_rows = []
    for company in company_list:
        filters = {"company": company, "is_active": 1}
        if permitted is not None:
            if len(permitted) == 0:
                continue
            filters["name"] = ["in", permitted]
        rows = frappe.db.get_all(
            "Company Link",
            filters=filters,
            fields=["name", "date_of_joining", "designation", "department"]
        )
        for r in rows:
            r["company"] = company
        all_rows.extend(rows)

    name_map = _get_employee_names([r.name for r in all_rows])
    return sorted([{
        "employee":        r.name,
        "full_name":       name_map.get(r.name, r.name),
        "company":         r["company"],
        "department":      r.get("department") or "—",
        "designation":     r.get("designation") or "—",
        "date_of_joining": str(r.date_of_joining) if r.date_of_joining else "",
    } for r in all_rows], key=lambda x: x["full_name"])


# ---------------------------------------------------------------------------
# POPUP: Salary structures defined for selected companies
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_salary_structures_list(companies):
    company_list = _parse_companies(companies)

    all_rows = []
    for company in company_list:
        rows = frappe.db.get_all(
            "Salary Structure",
            filters={"company": company},
            fields=["name", "company", "currency", "docstatus", "is_active", "modified"]
        )
        all_rows.extend(rows)

    return sorted([{
        "name":      r.name,
        "company":   r.company,
        "currency":  r.currency or "INR",
        "is_active": "Yes" if r.is_active else "No",
        "status":    "Submitted" if r.docstatus == 1 else "Draft",
        "modified":  str(r.modified)[:10] if r.modified else "",
    } for r in all_rows], key=lambda x: x["name"])


# ---------------------------------------------------------------------------
# POPUP: Submitted salary structure assignments in the selected period
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_ssa_list(companies, from_date, to_date):
    company_list = _parse_companies(companies)
    from_date    = getdate(from_date)
    to_date      = getdate(to_date)
    permitted    = _get_permitted_employees()

    all_rows = []
    for company in company_list:
        filters = {
            "company":   company,
            "docstatus": 1,
            "from_date": ["<=", to_date],
            "to_date":   [">=", from_date],
        }
        if permitted is not None:
            if len(permitted) == 0:
                continue
            filters["employee"] = ["in", permitted]
        rows = frappe.db.get_all(
            "Salary Structure Assignment",
            filters=filters,
            fields=["name", "employee", "employee_name", "salary_structure",
                    "from_date", "to_date", "company"]
        )
        all_rows.extend(rows)

    emp_ids  = [r.employee for r in all_rows if r.employee]
    name_map = _get_employee_names(emp_ids)

    return sorted([{
        "name":             r.name,
        "employee":         r.employee,
        "full_name":        name_map.get(r.employee, r.employee_name or r.employee),
        "company":          r.company,
        "salary_structure": r.salary_structure,
        "from_date":        str(r.from_date) if r.from_date else "",
        "to_date":          str(r.to_date)   if r.to_date   else "",
    } for r in all_rows], key=lambda x: x["full_name"])


# ---------------------------------------------------------------------------
# POPUP: Holidays from the default holiday list in the selected period
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_holiday_list(companies, from_date, to_date):
    company_list = _parse_companies(companies)
    from_date    = getdate(from_date)
    to_date      = getdate(to_date)

    seen_lists = set()
    all_rows   = []

    for company in company_list:
        from saral_hr.utils.holiday_utils import get_holiday_list_for_date
        holiday_list_name = get_holiday_list_for_date(frappe.utils.today(), company)
        if not holiday_list_name or holiday_list_name in seen_lists:
            continue
        seen_lists.add(holiday_list_name)

        holidays = frappe.db.get_all(
            "Holiday",
            filters={
                "parent":       holiday_list_name,
                "holiday_date": ["between", [from_date, to_date]],
            },
            fields=["holiday_date", "description"],
            order_by="holiday_date asc"
        )
        for h in holidays:
            all_rows.append({
                "holiday_date":  str(h.holiday_date),
                "description":   h.description or "—",
                "holiday_list":  holiday_list_name,
                "company":       company,
                "day":           getdate(h.holiday_date).strftime("%A"),
            })

    return sorted(all_rows, key=lambda x: x["holiday_date"])