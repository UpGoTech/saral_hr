import frappe
from frappe.utils import getdate, get_last_day, flt


@frappe.whitelist()
def get_salary_insight_data(company, year, month):
    month_map = {
        'January': 1, 'February': 2, 'March': 3, 'April': 4,
        'May': 5, 'June': 6, 'July': 7, 'August': 8,
        'September': 9, 'October': 10, 'November': 11, 'December': 12
    }
    month_num = month_map.get(month)
    if not month_num:
        frappe.throw("Invalid month")

    start_date = f"{year}-{month_num:02d}-01"

    # ── Total active employees for this company ──────────────────────────────
    total_active = frappe.db.count("Company Link", {
        "company": company,
        "is_active": 1
    })

    # ── All salary slips for this period ────────────────────────────────────
    salary_slips = frappe.db.sql("""
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

    # ── Aggregate totals (submitted slips only) ──────────────────────────────
    total_earnings              = 0
    total_deductions            = 0
    total_net                   = 0
    total_employer_contribution = 0

    for s in salary_slips:
        if s.docstatus == 1:
            total_earnings              += flt(s.total_earnings)
            total_deductions            += flt(s.total_deductions)
            total_net                   += flt(s.net_salary)
            total_employer_contribution += flt(s.total_employer_contribution)

    totals = {
        "total_earnings":              flt(total_earnings,              2),
        "total_deductions":            flt(total_deductions,            2),
        "total_net":                   flt(total_net,                   2),
        "total_employer_contribution": flt(total_employer_contribution, 2),
    }

    # ── Category summary ─────────────────────────────────────────────────────
    # Count total active per category from Company Link
    active_by_cat = frappe.db.sql("""
        SELECT category, COUNT(*) AS cnt
        FROM `tabCompany Link`
        WHERE company = %(company)s
          AND is_active = 1
        GROUP BY category
    """, {"company": company}, as_dict=1)

    cat_active_map = {r.category: r.cnt for r in active_by_cat}

    # Build slip counts per category
    cat_map = {}
    for s in salary_slips:
        cat = s.category or "Uncategorised"
        if cat not in cat_map:
            cat_map[cat] = {"category": cat, "total": 0, "submitted": 0, "draft": 0, "cancelled": 0, "active": 0}
        cat_map[cat]["total"] += 1
        if s.docstatus == 1:
            cat_map[cat]["submitted"] += 1
        elif s.docstatus == 0:
            cat_map[cat]["draft"] += 1
        elif s.docstatus == 2:
            cat_map[cat]["cancelled"] += 1

    # Attach active employee count to each category
    for cat_name, cnt in cat_active_map.items():
        key = cat_name or "Uncategorised"
        if key not in cat_map:
            cat_map[key] = {"category": key, "total": 0, "submitted": 0, "draft": 0, "cancelled": 0, "active": cnt}
        else:
            cat_map[key]["active"] = cnt

    category_summary = sorted(cat_map.values(), key=lambda x: x["total"], reverse=True)

    return {
        "salary_slips":            salary_slips,
        "totals":                  totals,
        "category_summary":        category_summary,
        "total_active_employees":  total_active,
    }