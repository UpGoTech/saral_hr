import frappe
from frappe.utils import getdate, flt, add_months


MONTH_MAP = {
    'January':1,'February':2,'March':3,'April':4,
    'May':5,'June':6,'July':7,'August':8,
    'September':9,'October':10,'November':11,'December':12
}
MONTH_NUM_TO_NAME = {v:k for k,v in MONTH_MAP.items()}


def _start_date_for(year, month_num):
    return f"{year}-{month_num:02d}-01"


def _slips_for_period(company, start_date):
    return frappe.db.sql("""
        SELECT
            ss.name,
            ss.employee,
            ss.employee_name,
            ss.docstatus,
            ss.net_salary,
            ss.total_earnings,
            ss.total_deductions,
            ss.total_employer_contribution,
            ss.payment_days,
            ss.category,
            ss.department,
            ss.designation,
            ss.branch,
            ss.division
        FROM `tabSalary Slip` ss
        WHERE ss.start_date = %(start_date)s
          AND ss.company    = %(company)s
          AND ss.docstatus  IN (0, 1, 2)
        ORDER BY ss.employee_name ASC
    """, {"company": company, "start_date": start_date}, as_dict=1)


@frappe.whitelist()
def get_salary_insight_data(company, year, month):
    month_num = MONTH_MAP.get(month)
    if not month_num:
        frappe.throw("Invalid month")

    year = int(year)
    start_date = _start_date_for(year, month_num)

    # ── Active employees ──────────────────────────────────────────────────────
    total_active = frappe.db.count("Company Link", {"company": company, "is_active": 1})

    # ── Salary slips for this period ──────────────────────────────────────────
    salary_slips = _slips_for_period(company, start_date)

    # ── Aggregated totals (submitted only) ────────────────────────────────────
    def aggregate(slips):
        te = td = tn = tec = 0
        for s in slips:
            if s.docstatus == 1:
                te  += flt(s.total_earnings)
                td  += flt(s.total_deductions)
                tn  += flt(s.net_salary)
                tec += flt(s.total_employer_contribution)
        return {"total_earnings": flt(te,2), "total_deductions": flt(td,2),
                "total_net": flt(tn,2), "total_employer_contribution": flt(tec,2)}

    totals = aggregate(salary_slips)

    # ── Previous month totals (for MoM comparison) ───────────────────────────
    prev_date_obj = getdate(start_date)
    prev_date_obj = getdate(add_months(start_date, -1))
    prev_month_num = prev_date_obj.month
    prev_year      = prev_date_obj.year
    prev_start     = _start_date_for(prev_year, prev_month_num)
    prev_slips     = _slips_for_period(company, prev_start)
    prev_totals    = aggregate(prev_slips)

    # ── Trend: last 6 months net payroll ─────────────────────────────────────
    trend = []
    for i in range(5, -1, -1):
        t_date  = getdate(add_months(start_date, -i))
        t_start = _start_date_for(t_date.year, t_date.month)
        t_slips = _slips_for_period(company, t_start)
        t_net   = sum(flt(s.net_salary) for s in t_slips if s.docstatus == 1)
        trend.append({
            "month": MONTH_NUM_TO_NAME[t_date.month],
            "year":  t_date.year,
            "net":   flt(t_net, 2),
        })

    # ── Category summary ──────────────────────────────────────────────────────
    active_by_cat = frappe.db.sql("""
        SELECT category, COUNT(*) AS cnt
        FROM `tabCompany Link`
        WHERE company = %(company)s AND is_active = 1
        GROUP BY category
    """, {"company": company}, as_dict=1)
    cat_active_map = {r.category: r.cnt for r in active_by_cat}

    cat_map = {}
    for s in salary_slips:
        cat = s.category or "Uncategorised"
        if cat not in cat_map:
            cat_map[cat] = {"category": cat, "total": 0, "submitted": 0,
                            "draft": 0, "cancelled": 0, "active": 0, "net_amount": 0}
        cat_map[cat]["total"] += 1
        if s.docstatus == 1:
            cat_map[cat]["submitted"]  += 1
            cat_map[cat]["net_amount"] += flt(s.net_salary)
        elif s.docstatus == 0:
            cat_map[cat]["draft"] += 1
        elif s.docstatus == 2:
            cat_map[cat]["cancelled"] += 1

    for cat_name, cnt in cat_active_map.items():
        key = cat_name or "Uncategorised"
        if key not in cat_map:
            cat_map[key] = {"category": key, "total": 0, "submitted": 0,
                            "draft": 0, "cancelled": 0, "active": cnt, "net_amount": 0}
        else:
            cat_map[key]["active"] = cnt

    category_summary = sorted(cat_map.values(), key=lambda x: x["net_amount"], reverse=True)

    # ── Employees with NO salary slip this period ─────────────────────────────
    slip_employee_set = {s.employee for s in salary_slips if s.docstatus != 2}

    all_active_emps = frappe.db.sql("""
        SELECT cl.name, cl.full_name AS employee_name,
               cl.category, cl.department, cl.designation
        FROM `tabCompany Link` cl
        WHERE cl.company = %(company)s AND cl.is_active = 1
        ORDER BY cl.full_name ASC
    """, {"company": company}, as_dict=1)

    pending_employees = [
        e for e in all_active_emps
        if e.name not in slip_employee_set
    ]

    return {
        "salary_slips":           salary_slips,
        "totals":                 totals,
        "prev_totals":            prev_totals,
        "category_summary":       category_summary,
        "total_active_employees": total_active,
        "pending_employees":      pending_employees,
        "trend":                  trend,
    }