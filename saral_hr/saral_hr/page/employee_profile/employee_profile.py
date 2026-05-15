import frappe
from frappe.utils import today, getdate, date_diff


# ── Permission helper (mirrors salary_insight.py) ─────────────────────────────

def _get_permitted_employees():
    """
    Returns a list of employee IDs the current user is permitted to see,
    based on Frappe User Permissions.

    - System Manager / Administrator → None (no restriction, see all).
    - User with Employee-level User Permissions → list of permitted employee IDs.
    - User with NO Employee-level permissions → None (no restriction, see all).
    """
    user = frappe.session.user

    if "System Manager" in frappe.get_roles(user):
        return None

    user_permissions = frappe.permissions.get_user_permissions(user)

    if "Employee" in user_permissions and user_permissions["Employee"]:
        permitted = [
            perm.get("doc")
            for perm in user_permissions["Employee"]
            if perm.get("doc")
        ]
        return permitted if permitted else None

    return None


# ── New: search endpoint for the page-level search bar ───────────────────────

@frappe.whitelist()
def get_permitted_employees_for_search():
    """
    Returns the list of active employees the current user is allowed to view,
    formatted for the client-side search dropdown.

    Each entry: { name, full_name, designation, department, company }

    Uses the same permission logic as salary_insight.py so that restricted
    users (e.g. HR managers for a single company) only see their subset.
    """
    permitted = _get_permitted_employees()

    base_filters = {"is_active": 1}

    if permitted is not None:
        if not permitted:
            return []
        base_filters["name"] = ["in", permitted]

    rows = frappe.get_all(
        "Company Link",
        filters=base_filters,
        fields=["name", "full_name", "designation", "department", "company"],
        order_by="full_name asc",
        limit=2000,
    )

    return [
        {
            "name":        r.name,
            "full_name":   r.full_name or r.name,
            "designation": r.designation or "",
            "department":  r.department  or "",
            "company":     r.company     or "",
        }
        for r in rows
    ]


# ── Existing methods (all unchanged) ─────────────────────────────────────────

@frappe.whitelist()
def get_employee_profile_data(employee):
    emp = frappe.get_doc("Employee", employee)

    # ── Company Link ──────────────────────────────────────────────────────────
    CL_FIELDS = ["name", "company", "designation", "department", "branch",
                 "division", "category", "date_of_joining", "is_active", "left_date",
                 "immediate_reporting", "final_reporting"]

    company_link = frappe.db.get_value(
        "Company Link",
        {"employee": employee, "is_active": 1},
        CL_FIELDS,
        as_dict=True
    )
    if not company_link:
        company_link = frappe.db.get_value(
            "Company Link",
            {"employee": employee},
            CL_FIELDS,
            order_by="date_of_joining desc",
            as_dict=True
        )

    company_link_name = company_link.get("name") if company_link else None
    company_link = company_link or {}

    def get_emp_name(emp_id):
        if not emp_id:
            return None
        return frappe.db.get_value("Employee", emp_id, "employee") or emp_id

    if company_link:
        company_link["immediate_reporting_name"] = get_emp_name(company_link.get("immediate_reporting"))
        company_link["final_reporting_name"]     = get_emp_name(company_link.get("final_reporting"))

    # ── Salary (from latest submitted SSA) ───────────────────────────────────
    salary = frappe.db.get_value(
        "Salary Structure Assignment",
        filters={"employee": employee, "docstatus": 1},
        fieldname=["monthly_ctc", "annual_ctc", "net_salary",
                   "gross_salary", "total_deductions", "total_employer_contribution", "from_date"],
        order_by="from_date desc",
        as_dict=True
    )

    # ── Attendance ────────────────────────────────────────────────────────────
    all_cl_names = frappe.db.get_all(
        "Company Link",
        filters={"employee": employee},
        pluck="name"
    )

    att_map = {}
    years_set = set()

    if all_cl_names:
        all_attendance = frappe.get_all(
            "Attendance",
            filters={
                "employee": ["in", all_cl_names],
                "docstatus": ["!=", 2]
            },
            fields=["attendance_date", "status"],
            order_by="attendance_date desc"
        )
        for r in all_attendance:
            if r.attendance_date:
                date_str = str(r.attendance_date)
                att_map[date_str] = r.status
                years_set.add(date_str[:4])

    # Always include years from joining year → current year
    current_year = getdate(today()).year
    joining_year = current_year
    doj = company_link.get("date_of_joining") if company_link else None
    if doj:
        try:
            joining_year = getdate(doj).year
        except Exception:
            pass

    for yr in range(joining_year, current_year + 1):
        years_set.add(str(yr))

    years = sorted(list(years_set), reverse=True)

    # ── Tenure ────────────────────────────────────────────────────────────────
    tenure = None
    active_doj = None
    if company_link and company_link.get("is_active") and company_link.get("date_of_joining"):
        active_doj = company_link.get("date_of_joining")
    else:
        active_cl = frappe.db.get_value(
            "Company Link", {"employee": employee, "is_active": 1}, "date_of_joining"
        )
        if active_cl:
            active_doj = active_cl

    if active_doj:
        try:
            days = date_diff(today(), getdate(active_doj))
            if days >= 0:
                total_months = days // 30
                yrs = total_months // 12
                mos = total_months % 12
                parts = []
                if yrs:
                    parts.append("{} yr{}".format(yrs, "s" if yrs != 1 else ""))
                if mos:
                    parts.append("{} mo{}".format(mos, "s" if mos != 1 else ""))
                if not parts:
                    parts.append("{} day{}".format(days, "s" if days != 1 else ""))
                tenure = " ".join(parts)
        except Exception:
            pass

    # ── Timeline ──────────────────────────────────────────────────────────────
    raw_timeline = frappe.db.sql("""
        SELECT
            name, company, full_name,
            date_of_joining AS start_date,
            left_date       AS end_date,
            is_active, designation, department, branch, category
        FROM `tabCompany Link`
        WHERE employee = %(employee)s
           OR name LIKE %(pattern)s
        ORDER BY
            CASE WHEN is_active = 1 THEN 0 ELSE 1 END ASC,
            COALESCE(date_of_joining, '1900-01-01') DESC
    """, {"employee": employee, "pattern": "{0}-%".format(employee)}, as_dict=1)

    timeline = []
    for rec in raw_timeline:
        timeline.append({
            "company":     rec.get("company")     or "",
            "start_date":  str(rec["start_date"]) if rec.get("start_date") else None,
            "end_date":    str(rec["end_date"])   if rec.get("end_date")   else None,
            "is_active":   rec.get("is_active", 0),
            "designation": rec.get("designation") or "",
            "department":  rec.get("department")  or "",
            "branch":      rec.get("branch")      or "",
            "category":    rec.get("category")    or "",
        })

    # ── Reporting names ───────────────────────────────────────────────────────
    immediate_reporting_name = None
    final_reporting_name = None
    if company_link_name:
        reporting = frappe.db.get_value(
            "Company Link", company_link_name,
            ["immediate_reporting", "final_reporting"], as_dict=True
        )
        if reporting:
            if reporting.get("immediate_reporting"):
                immediate_reporting_name = frappe.db.get_value(
                    "Employee", reporting["immediate_reporting"], "employee"
                ) or reporting["immediate_reporting"]
            if reporting.get("final_reporting"):
                final_reporting_name = frappe.db.get_value(
                    "Employee", reporting["final_reporting"], "employee"
                ) or reporting["final_reporting"]

    # ── Helper: serialize a single SSA doc into a dict ────────────────────────
    def _serialize_ssa(ssa_doc):
        return {
            "name":                        ssa_doc.name,
            "salary_structure":            ssa_doc.salary_structure,
            "from_date":                   str(ssa_doc.from_date) if ssa_doc.from_date else None,
            "to_date":                     str(ssa_doc.to_date)   if ssa_doc.to_date   else None,
            "monthly_ctc":                 ssa_doc.monthly_ctc,
            "gross_salary":                ssa_doc.gross_salary,
            "total_deductions":            ssa_doc.total_deductions,
            "total_employer_contribution": ssa_doc.total_employer_contribution,
            "net_salary":                  ssa_doc.net_salary,
            "annual_ctc":                  ssa_doc.annual_ctc,
            "designation":                 ssa_doc.designation or "",
            "department":                  ssa_doc.department  or "",
            "branch":                      ssa_doc.branch      or "",
            "earnings": [
                {"salary_component": row.salary_component, "amount": row.amount}
                for row in (ssa_doc.earnings or [])
            ],
            "deductions": [
                {"salary_component": row.salary_component, "amount": row.amount}
                for row in (ssa_doc.deductions or [])
            ],
            "employer_share": [
                {"salary_component": row.salary_component, "amount": row.amount}
                for row in (ssa_doc.employer_share or [])
            ],
        }

    # ── Latest submitted SSA ──────────────────────────────────────────────────
    latest_ssa_name = frappe.db.get_value(
        "Salary Structure Assignment",
        filters={"employee": employee, "docstatus": 1},
        fieldname="name",
        order_by="from_date desc",
    )

    latest_ssa = None
    if latest_ssa_name:
        latest_ssa = _serialize_ssa(frappe.get_doc("Salary Structure Assignment", latest_ssa_name))

    # ── Cancelled SSAs ────────────────────────────────────────────────────────
    cancelled_ssas_names = frappe.db.get_all(
        "Salary Structure Assignment",
        filters={"employee": employee, "docstatus": 2},
        fields=["name"],
        order_by="from_date desc",
    )

    cancelled_ssas = []
    for rec in cancelled_ssas_names:
        try:
            cancelled_ssas.append(_serialize_ssa(frappe.get_doc("Salary Structure Assignment", rec.name)))
        except Exception:
            pass

    # ── Loan Ledger ────────────────────────────────────────────────────────────
    loan_ledger = []
    try:
        loan_names = frappe.db.get_all(
            "Employee Loan Advance",
            filters={
                "employee": employee,
                "docstatus": 1
            },
            fields=["name"],
            order_by="creation desc"
        )

        for ln in loan_names:
            try:
                loan_doc = frappe.get_doc("Employee Loan Advance", ln.name)

                schedule_rows = []
                total_recovered = 0.0
                total_outstanding = 0.0

                loan_type = loan_doc.get("type")
                loan_amount = float(loan_doc.get("amount") or 0)

                if loan_type == "Advance":
                    is_deducted = loan_doc.get("is_deducted", 0)
                    if is_deducted:
                        total_recovered = loan_amount
                        total_outstanding = 0
                    else:
                        total_recovered = 0
                        total_outstanding = loan_amount
                    schedule_rows = []

                else:
                    if loan_doc.get("schedule") and len(loan_doc.schedule) > 0:
                        for row in loan_doc.schedule:
                            deducted = float(row.get("deduction_amount") or 0)
                            base_emi = float(row.get("deduction_amount") or 0)
                            status = "Deducted" if row.get("is_deducted") else "Pending"
                            if row.get("is_deferred"):
                                status = "Deferred"
                            deferred_to = str(row.get("deferred_to")) if row.get("deferred_to") else None

                            if status == "Deducted":
                                total_recovered += deducted
                            else:
                                total_outstanding += base_emi

                            schedule_rows.append({
                                "month": str(row.get("month")) if row.get("month") else None,
                                "base_emi": base_emi,
                                "actual_deducted": deducted,
                                "status": status,
                                "deferred_to": deferred_to,
                            })
                    else:
                        total_outstanding = loan_amount

                pct_recovered = round((total_recovered / loan_amount * 100), 1) if loan_amount else 0

                if total_outstanding <= 0:
                    status = "Completed"
                else:
                    status = "Active"

                loan_data = {
                    "name": loan_doc.name,
                    "loan_type": loan_type,
                    "loan_amount": loan_amount,
                    "start_date": str(loan_doc.get("date")) if loan_doc.get("date") else None,
                    "status": status,
                    "total_recovered": total_recovered,
                    "outstanding": total_outstanding,
                    "pct_recovered": pct_recovered,
                    "schedule": schedule_rows,
                }

                if loan_type == "Advance":
                    loan_data["is_deducted"] = loan_doc.get("is_deducted", 0)
                else:
                    loan_data["frequency"] = loan_doc.get("installment_gap") or ""
                    loan_data["tenure_months"] = loan_doc.get("tenure_months")
                    loan_data["tenure_display"] = f"{loan_doc.get('tenure_months')} months" if loan_doc.get('tenure_months') else "—"
                    loan_data["monthly_deduction"] = float(loan_doc.get("monthly_deduction") or 0)
                    loan_data["start_month"] = loan_doc.get("start_month") or ""
                    loan_data["start_year"] = loan_doc.get("start_year") or ""

                loan_ledger.append(loan_data)

            except Exception as e:
                frappe.log_error(f"Error loading loan {ln.name}: {str(e)}", "Employee Profile")
                continue

    except Exception as e:
        frappe.log_error(f"Error fetching loans: {str(e)}", "Employee Profile")

    # ── Return data ────────────────────────────────────────────────────────────
    return {
        "employee":                  emp.employee,
        "first_name":                emp.first_name,
        "employee_image":            emp.employee_image,
        "date_of_birth":             str(emp.date_of_birth) if emp.date_of_birth else None,
        "pan_number":                emp.pan_number,
        "cell_number":               getattr(emp, "cell_number",    None),
        "personal_email":            getattr(emp, "personal_email", None),
        "company_email":             getattr(emp, "company_email",  None),
        "company_link":              company_link or {},
        "company_link_name":         company_link_name,
        "salary":                    salary,
        "attendance_map":            att_map,
        "years":                     years,
        "tenure":                    tenure,
        "timeline":                  timeline,
        "immediate_reporting_name":  immediate_reporting_name,
        "final_reporting_name":      final_reporting_name,
        "latest_ssa":                latest_ssa,
        "cancelled_ssas":            cancelled_ssas,
        "loan_ledger":               loan_ledger,
    }


# ── Leave Balance for Employee Profile Page ───────────────────────────────────

@frappe.whitelist()
def get_employee_leave_balance(employee):
    """
    Returns the active Leave Allocation for the employee with per-leave-type
    balances, used counts, and ledger entries.
    """
    today_date = getdate(today())

    alloc = frappe.db.get_value(
        "Leave Allocation",
        {
            "employee":  employee,
            "from_date": ["<=", str(today_date)],
            "to_date":   [">=", str(today_date)],
            "docstatus": ["<", 2],
        },
        ["name", "from_date", "to_date", "status"],
        as_dict=True
    )

    if not alloc:
        alloc = frappe.db.get_value(
            "Leave Allocation",
            {
                "employee":  employee,
                "docstatus": ["<", 2],
            },
            ["name", "from_date", "to_date", "status"],
            order_by="to_date desc",
            as_dict=True
        )

    if not alloc:
        return {"has_allocation": False}

    detail_rows = frappe.get_all(
        "Leave Allocation Detail",
        filters={"parent": alloc["name"]},
        fields=["leave_type", "allocated_leaves", "used_leaves", "remaining_leaves"],
        order_by="leave_type asc"
    )

    if not detail_rows:
        return {"has_allocation": True, "from_date": str(alloc["from_date"]),
                "to_date": str(alloc["to_date"]), "leave_types": []}

    leave_types_data = []
    for row in detail_rows:
        ledger_entries = _get_ledger_entries(
            employee=employee,
            leave_type=row.leave_type,
            allocated=float(row.allocated_leaves or 0),
            from_date=str(alloc["from_date"]),
            to_date=str(alloc["to_date"]),
            today_date=today_date
        )
        leave_types_data.append({
            "leave_type":       row.leave_type,
            "allocated_leaves": row.allocated_leaves or 0,
            "used_leaves":      row.used_leaves or 0,
            "remaining_leaves": row.remaining_leaves or 0,
            "ledger":           ledger_entries,
        })

    return {
        "has_allocation": True,
        "from_date":      str(alloc["from_date"]),
        "to_date":        str(alloc["to_date"]),
        "leave_types":    leave_types_data,
    }


_STATUS_LEAVE_MAP = {
    "Sick Leave":      "Sick Leave",
    "Casual Leave":    "Casual Leave",
    "Annual Leave":    "Annual Leave",
    "Earned Leave":    "Earned Leave",
    "Comp Off":        "Comp Off",
    "LWP":             "LWP",
    "Earned Comp Off": "Earned Comp Off",
}

_HALF_DAY_FIELDS = ["custom_first_half", "custom_second_half"]


def _get_ledger_entries(employee, leave_type, allocated, from_date, to_date, today_date):
    entries = []
    balance = 0.0

    if allocated:
        balance = float(allocated)
        open_date = getdate(from_date)
        entries.append({
            "date":       frappe.utils.format_date(from_date),
            "day":        open_date.strftime("%A"),
            "status":     "Added",
            "leaves_in":  allocated,
            "leaves_out": "-",
            "balance":    balance,
        })

    attendance_statuses = [s for s, lt in _STATUS_LEAVE_MAP.items() if lt == leave_type]

    if attendance_statuses:
        full_records = frappe.get_all(
            "Attendance",
            filters={
                "employee":        ["in", frappe.db.get_all("Company Link",
                                        filters={"employee": employee}, pluck="name") or [employee]],
                "attendance_date": ["between", [from_date, to_date]],
                "status":          ["in", attendance_statuses],
                "docstatus":       ["<", 2],
            },
            fields=["attendance_date", "status"],
            order_by="attendance_date asc"
        )
        for att in full_records:
            att_date = getdate(att.attendance_date)
            balance -= 1.0
            entries.append({
                "date":       frappe.utils.format_date(att.attendance_date),
                "day":        att_date.strftime("%A"),
                "status":     "Used",
                "leaves_in":  "-",
                "leaves_out": 1,
                "balance":    balance,
            })

        half_records = frappe.get_all(
            "Attendance",
            filters={
                "employee":        ["in", frappe.db.get_all("Company Link",
                                        filters={"employee": employee}, pluck="name") or [employee]],
                "attendance_date": ["between", [from_date, to_date]],
                "status":          "Half Day",
                "docstatus":       ["<", 2],
            },
            fields=["attendance_date", "custom_first_half", "custom_second_half"],
            order_by="attendance_date asc"
        )
        for att in half_records:
            used_halves = sum(
                1 for field in _HALF_DAY_FIELDS
                if (att.get(field) or "") in attendance_statuses
            )
            if used_halves:
                att_date  = getdate(att.attendance_date)
                deduction = used_halves * 0.5
                balance  -= deduction
                entries.append({
                    "date":       frappe.utils.format_date(att.attendance_date),
                    "day":        att_date.strftime("%A"),
                    "status":     "Used",
                    "leaves_in":  "-",
                    "leaves_out": deduction,
                    "balance":    balance,
                })

    entries.sort(key=lambda e: e["date"])

    period_end = getdate(to_date) if to_date else None
    if balance > 0 and period_end and today_date >= period_end:
        exp_date = period_end
        entries.append({
            "date":       frappe.utils.format_date(to_date),
            "day":        exp_date.strftime("%A"),
            "status":     "Expired",
            "leaves_in":  "-",
            "leaves_out": balance,
            "balance":    0,
        })

    return entries


@frappe.whitelist()
def get_employee_deduction_breakdown(employee, month, year, start_date):
    from frappe.utils import flt

    slip = frappe.db.get_value(
        "Salary Slip",
        {"employee": employee, "start_date": start_date, "docstatus": ["in", [0, 1]]},
        ["name", "docstatus"],
        as_dict=True
    )

    if not slip:
        return None

    doc = frappe.get_doc("Salary Slip", slip.name)

    total_days  = flt(getattr(doc, "total_working_days", None) or 0)
    absent_days = flt(getattr(doc, "absent_days", None) or 0)
    paid_days   = flt(getattr(doc, "payment_days", None) or 0)

    ss_net = flt(doc.net_salary)

    ssa_net = 0.0
    try:
        ssa_name = frappe.db.get_value(
            "Salary Structure Assignment",
            {"employee": employee, "docstatus": 1},
            "name", order_by="from_date desc"
        )
        if ssa_name:
            ssa_doc = frappe.get_doc("Salary Structure Assignment", ssa_name)
            ssa_net = sum(flt(r.amount) for r in (ssa_doc.earnings or [])) - \
                      sum(flt(r.amount) for r in (ssa_doc.deductions or []))
    except Exception:
        pass

    additional_salary_components    = {}
    additional_deduction_components = {}

    for rec in frappe.db.get_all(
        "Additional Salary",
        filters={"employee": employee, "year": year, "month": month, "docstatus": 1},
        fields=["name"]
    ):
        add_doc = frappe.get_doc("Additional Salary", rec.name)
        for row in add_doc.components or []:
            additional_salary_components[row.component_type] = flt(row.amount)

    for rec in frappe.db.get_all(
        "Additional Deductions",
        filters={"employee": employee, "year": year, "month": month, "docstatus": 1},
        fields=["name"]
    ):
        add_doc = frappe.get_doc("Additional Deductions", rec.name)
        for row in add_doc.deductions or []:
            additional_deduction_components[row.component_type] = flt(row.amount)

    loan_total         = 0.0
    retention_total    = 0.0
    loan_breakdown     = {}
    loan_names_in_slip = []
    add_sal_deducted   = {}
    add_ded_deducted   = {}

    for row in doc.deductions:
        comp       = row.salary_component or ""
        amt        = flt(row.amount)
        comp_lower = comp.lower()

        if comp_lower == "loan" or comp_lower.startswith("loan-"):
            loan_total += amt
            loan_breakdown[comp] = loan_breakdown.get(comp, 0.0) + amt
            loan_ref = getattr(row, "loan_name", None) or getattr(row, "loan_id", None)
            if loan_ref and loan_ref not in loan_names_in_slip:
                loan_names_in_slip.append(loan_ref)

        elif "retention" in comp_lower:
            retention_total += amt

        elif comp in additional_salary_components:
            add_sal_deducted[comp] = amt

        elif comp in additional_deduction_components:
            add_ded_deducted[comp] = amt

    for row in doc.earnings:
        comp = row.salary_component or ""
        amt  = flt(row.amount)
        if comp in additional_salary_components and comp not in add_sal_deducted:
            add_sal_deducted[comp] = amt

    for comp in additional_salary_components:
        if comp not in add_sal_deducted:
            add_sal_deducted[comp] = 0

    for comp in additional_deduction_components:
        if comp not in add_ded_deducted:
            add_ded_deducted[comp] = 0

    _slip_month   = frappe.utils.formatdate(doc.start_date, "MMMM YYYY") if doc.start_date else ""
    loan_deferred = False

    if loan_total > 0:
        docs_to_check = loan_names_in_slip or [
            r.name for r in frappe.db.get_all(
                "Employee Loan Advance",
                filters={"employee": employee, "docstatus": 1, "type": "Loan"},
                fields=["name"]
            )
        ]
        for loan_doc_name in docs_to_check:
            try:
                loan_doc = frappe.get_doc("Employee Loan Advance", loan_doc_name)
                for srow in loan_doc.schedule:
                    if srow.month == _slip_month:
                        if getattr(srow, "is_deferred", 0):
                            loan_deferred = True
                        break
            except Exception:
                pass
            if loan_deferred:
                break

    return {
        "employee":      doc.employee,
        "employee_name": doc.employee_name,
        "slip_name":     doc.name,
        "slip_status":   "Submitted" if doc.docstatus == 1 else "Draft",
        "ssa_net":       round(ssa_net, 2),
        "ss_net":        round(ss_net, 2),
        "total_days":    total_days,
        "absent_days":   absent_days,
        "paid_days":     paid_days,
        "loan": {
            "total":     round(loan_total, 2),
            "deferred":  loan_deferred,
            "breakdown": loan_breakdown,
        },
        "retention":             round(retention_total, 2),
        "additional_salary":     add_sal_deducted,
        "additional_deductions": add_ded_deducted,
    }