import frappe
from frappe.utils import today, getdate, date_diff


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
        # Fetch ONLY submitted loans (docstatus = 1) for this employee
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
                
                # Check if this is Advance or Loan
                if loan_type == "Advance":
                    # ADVANCE: Single deduction, no schedule
                    is_deducted = loan_doc.get("is_deducted", 0)
                    
                    if is_deducted:
                        total_recovered = loan_amount
                        total_outstanding = 0
                    else:
                        total_recovered = 0
                        total_outstanding = loan_amount
                    
                    # For display consistency
                    schedule_rows = []  # No schedule for advance
                    
                else:
                    # LOAN-I or LOAN-II: Has schedule table
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
                        # Should not happen for loans, but fallback
                        total_outstanding = loan_amount
                
                pct_recovered = round((total_recovered / loan_amount * 100), 1) if loan_amount else 0
                
                # Determine status
                if total_outstanding <= 0:
                    status = "Completed"
                else:
                    status = "Active"
                
                # Prepare loan data
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
                
                # Add loan-specific fields
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