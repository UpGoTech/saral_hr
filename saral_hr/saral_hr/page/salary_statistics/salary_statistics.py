import frappe
from frappe import _
from frappe.utils import getdate, get_last_day, flt
import calendar


@frappe.whitelist()
def get_employees_for_company(company, year, month):
    """
    Returns all active employees for a company with their
    net pay for each month of the selected year.
    """
    MONTHS = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]
    month_map = {m: i + 1 for i, m in enumerate(MONTHS)}

    employees = frappe.db.sql("""
        SELECT
            cl.name        AS employee,
            cl.full_name   AS employee_name,
            cl.department,
            cl.designation,
            e.date_of_birth,
            e.employee_image AS image,
            ssa.net_salary  AS ctc_net_salary
        FROM `tabCompany Link` cl
        LEFT JOIN `tabEmployee` e ON e.name = cl.employee
        LEFT JOIN `tabSalary Structure Assignment` ssa
            ON  ssa.employee  = cl.name
            AND ssa.docstatus = 1
            AND ssa.from_date = (
                SELECT MAX(s2.from_date)
                FROM `tabSalary Structure Assignment` s2
                WHERE s2.employee  = cl.name
                  AND s2.docstatus = 1
            )
        WHERE cl.is_active = 1
          AND cl.company   = %(company)s
        ORDER BY cl.full_name
    """, {"company": company}, as_dict=True)

    employee_ids = [emp.employee for emp in employees]
    if not employee_ids:
        return []

    # Fetch all salary slips for the year for these employees
    placeholders = ", ".join(["%s"] * len(employee_ids))
    slips = frappe.db.sql(f"""
        SELECT employee, start_date, net_salary
        FROM `tabSalary Slip`
        WHERE docstatus = 1
          AND employee IN ({placeholders})
          AND YEAR(start_date) = %s
        ORDER BY start_date
    """, tuple(employee_ids) + (year,), as_dict=True)

    # Build a map: employee -> {month_name: net_salary}
    slip_map = {}
    for slip in slips:
        emp_id = slip.employee
        month_num = getdate(slip.start_date).month
        month_name = MONTHS[month_num - 1]
        if emp_id not in slip_map:
            slip_map[emp_id] = {}
        slip_map[emp_id][month_name] = flt(slip.net_salary, 2)

    result = []
    for emp in employees:
        emp_data = {
            "employee":        emp.employee,
            "employee_name":   emp.employee_name or emp.employee,
            "department":      emp.department or "",
            "designation":     emp.designation or "",
            "date_of_birth":   str(emp.date_of_birth) if emp.date_of_birth else "",
            "image":           emp.image or "",
            "ctc_net_salary":  flt(emp.ctc_net_salary, 2) if emp.ctc_net_salary else None,
            "monthly_net":     {}
        }
        for m in MONTHS:
            emp_data["monthly_net"][m] = slip_map.get(emp.employee, {}).get(m, None)
        result.append(emp_data)

    return result


@frappe.whitelist()
def get_employee_month_details(employee, year, month):
    """
    Returns full salary slip details + attendance heatmap for a given employee/month.
    """
    MONTHS = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]
    month_map = {m: i + 1 for i, m in enumerate(MONTHS)}
    month_num = month_map.get(month)
    if not month_num:
        return None

    start_date = f"{year}-{month_num:02d}-01"

    # ── Salary Slip ────────────────────────────────────────────────────────────
    slip = frappe.db.get_value(
        "Salary Slip",
        {"employee": employee, "start_date": start_date, "docstatus": 1},
        [
            "name", "net_salary", "total_earnings", "total_deductions",
            "total_employer_contribution", "total_basic_da", "retention",
            "payment_days", "total_working_days", "physical_working_days",
            "present_days", "absent_days", "total_half_days", "total_lwp",
            "total_holidays", "total_earned_leaves", "total_casual_leaves",
            "total_on_tour", "total_comp_off", "weekly_offs_count"
        ],
        as_dict=True
    )

    salary_details = None
    if slip:
        # Earnings rows
        earnings = frappe.db.get_all(
            "Salary Details",
            filters={"parent": slip.name, "parentfield": "earnings"},
            fields=["salary_component", "abbr", "amount"],
            order_by="idx"
        )
        # Deduction rows
        deductions = frappe.db.get_all(
            "Salary Details",
            filters={"parent": slip.name, "parentfield": "deductions"},
            fields=["salary_component", "abbr", "amount"],
            order_by="idx"
        )
        # Employer share rows
        employer_share = frappe.db.get_all(
            "Salary Details",
            filters={"parent": slip.name, "parentfield": "employer_share"},
            fields=["salary_component", "abbr", "amount"],
            order_by="idx"
        )

        # Additional Salary
        additional_salary_total = 0.0
        additional_salary_components = []
        add_sal_docs = frappe.db.get_all(
            "Additional Salary",
            filters={"employee": employee, "year": str(year), "month": month, "docstatus": 1},
            fields=["name", "total_amount"]
        )
        for doc in add_sal_docs:
            additional_salary_total += flt(doc.total_amount)
            comps = frappe.db.get_all(
                "Additional Salary Component",
                filters={"parent": doc.name},
                fields=["component_type", "amount"]
            )
            for c in comps:
                additional_salary_components.append({
                    "salary_component": c.component_type,
                    "amount": flt(c.amount)
                })

        # Additional Deductions
        additional_deduction_total = 0.0
        additional_deduction_components = []
        add_ded_docs = frappe.db.get_all(
            "Additional Deductions",
            filters={"employee": employee, "year": str(year), "month": month, "docstatus": 1},
            fields=["name", "total_deduction_amount"]
        )
        for doc in add_ded_docs:
            additional_deduction_total += flt(doc.total_deduction_amount)
            comps = frappe.db.get_all(
                "Additional Deduction Component",
                filters={"parent": doc.name},
                fields=["component_type", "amount"]
            )
            for c in comps:
                additional_deduction_components.append({
                    "salary_component": c.component_type,
                    "amount": flt(c.amount)
                })

        salary_details = {
            "slip_name":                       slip.name,
            "net_salary":                      flt(slip.net_salary, 2),
            "total_earnings":                  flt(slip.total_earnings, 2),
            "total_deductions":                flt(slip.total_deductions, 2),
            "total_employer_contribution":     flt(slip.total_employer_contribution, 2),
            "total_basic_da":                  flt(slip.total_basic_da, 2),
            "retention":                       flt(slip.retention, 2),
            "earnings":                        earnings,
            "deductions":                      deductions,
            "employer_share":                  employer_share,
            "additional_salary_total":         flt(additional_salary_total, 2),
            "additional_salary_components":    additional_salary_components,
            "additional_deduction_total":      flt(additional_deduction_total, 2),
            "additional_deduction_components": additional_deduction_components,
            # attendance summary from slip
            "payment_days":           flt(slip.payment_days, 2),
            "total_working_days":     flt(slip.total_working_days, 2),
            "physical_working_days":  flt(slip.physical_working_days, 2),
            "present_days":           flt(slip.present_days, 2),
            "absent_days":            flt(slip.absent_days, 2),
            "total_half_days":        flt(slip.total_half_days, 2),
            "total_lwp":              flt(slip.total_lwp, 2),
            "total_holidays":         flt(slip.total_holidays, 2),
            "total_earned_leaves":    flt(slip.total_earned_leaves, 2),
            "total_casual_leaves":    flt(slip.total_casual_leaves, 2),
            "total_on_tour":          flt(slip.total_on_tour, 2),
            "total_comp_off":         flt(slip.total_comp_off, 2),
            "weekly_offs_count":      flt(slip.weekly_offs_count, 2),
        }

    # ── Attendance Heatmap ─────────────────────────────────────────────────────
    start_dt = getdate(start_date)
    end_dt = get_last_day(start_dt)
    total_days = calendar.monthrange(start_dt.year, start_dt.month)[1]

    attendance_records = frappe.db.get_all(
        "Attendance",
        filters={
            "employee":        employee,
            "attendance_date": ["between", [str(start_dt), str(end_dt)]]
        },
        fields=["attendance_date", "status", "in_time", "out_time", "late_entry", "early_exit"]
    )

    att_map = {}
    for rec in attendance_records:
        day = getdate(rec.attendance_date).day
        att_map[day] = {
            "status":      rec.status,
            "in_time":     str(rec.in_time)  if rec.in_time  else "",
            "out_time":    str(rec.out_time) if rec.out_time else "",
            "late_entry":  rec.late_entry,
            "early_exit":  rec.early_exit,
        }

    heatmap = []
    for day in range(1, total_days + 1):
        heatmap.append({
            "day":    day,
            "date":   f"{year}-{month_num:02d}-{day:02d}",
            "status": att_map.get(day, {}).get("status", "No Record"),
            "in_time":    att_map.get(day, {}).get("in_time", ""),
            "out_time":   att_map.get(day, {}).get("out_time", ""),
            "late_entry": att_map.get(day, {}).get("late_entry", 0),
            "early_exit": att_map.get(day, {}).get("early_exit", 0),
        })

    # ── Live attendance counts from actual records ───────────────────────────
    from datetime import timedelta

    # Get company settings for salary calculation method
    company_name = frappe.db.get_value("Company Link", employee, "company")
    salary_calc_method = ""
    weekly_off_day = frappe.db.get_value("Company Link", employee, "weekly_off") or ""
    if company_name:
        salary_calc_method = frappe.db.get_value("Company", company_name, "salary_calculation_based_on") or ""

    use_calendar_days = "Include" in salary_calc_method

    # Count weekly offs in month
    day_map = {"Monday":0,"Tuesday":1,"Wednesday":2,"Thursday":3,"Friday":4,"Saturday":5,"Sunday":6}
    weekly_off_count = 0
    if weekly_off_day and weekly_off_day in day_map:
        off_weekday = day_map[weekly_off_day]
        cur = start_dt
        while cur <= end_dt:
            if cur.weekday() == off_weekday:
                weekly_off_count += 1
            cur += timedelta(days=1)

    # Count each status
    def count_status(st):
        return sum(1 for v in att_map.values() if v["status"] == st)

    present          = count_status("Present")
    absent           = count_status("Absent")
    half_day         = count_status("Half Day")
    lwp              = count_status("LWP")
    holiday          = count_status("Holiday")
    on_tour          = count_status("On Tour")
    earned_leave     = count_status("Earned Leave")
    casual_leave     = count_status("Casual Leave")
    comp_off         = count_status("Comp Off")
    earned_comp_off  = count_status("Earned Comp Off")
    weekly_off_taken = count_status("Weekly Off")

    # Physical present = only actual physical presence (no EL/CL/Comp Off/Earned Comp Off)
    physical_present = present  # raw "Present" status only

    # Combined absent days (Absent + LWP)
    combined_absent = flt(absent + lwp, 2)

    # Working days & payment days based on company setting
    if use_calendar_days:
        working_days = total_days
        payment_days = flt(total_days - combined_absent, 2)
    else:
        working_days = total_days - weekly_off_count
        payment_days = flt(working_days - combined_absent + comp_off + earned_comp_off, 2)

    live_attendance = {
        "total_days":        total_days,
        "working_days":      working_days,
        "payment_days":      flt(payment_days, 2),
        "physical_present":  physical_present,
        "present":           present + earned_leave + casual_leave + comp_off + earned_comp_off + on_tour,
        "absent":            combined_absent,
        "half_days":         half_day,
        "weekly_offs_scheduled": weekly_off_count,
        "weekly_offs_taken":     weekly_off_taken,
        "holidays":          holiday,
        "lwp":               flt(lwp, 2),
        "earned_leave":      earned_leave,
        "casual_leave":      casual_leave,
        "on_tour":           on_tour,
        "comp_off":          comp_off,
        "earned_comp_off":   earned_comp_off,
        "calc_method":       salary_calc_method,
    }

    return {
        "salary": salary_details,
        "heatmap": heatmap,
        "live_attendance": live_attendance,
        "total_days": total_days,
        "month_num": month_num,
        "year": int(year),
        "month": month,
        "has_attendance": len(att_map) > 0,
    }


@frappe.whitelist()
def get_ytd_summary(employee, year):
    """Returns year-to-date net pay and total earnings for the employee."""
    MONTHS = ["January","February","March","April","May","June",
              "July","August","September","October","November","December"]
    slips = frappe.db.sql("""
        SELECT net_salary, total_earnings
        FROM `tabSalary Slip`
        WHERE employee = %(employee)s
          AND YEAR(start_date) = %(year)s
          AND docstatus = 1
    """, {"employee": employee, "year": year}, as_dict=True)
    ytd_net  = sum(flt(s.net_salary)    for s in slips)
    ytd_earn = sum(flt(s.total_earnings) for s in slips)
    return {"ytd_net": flt(ytd_net, 2), "ytd_earn": flt(ytd_earn, 2)}