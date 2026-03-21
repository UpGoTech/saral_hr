import frappe
from frappe.utils import getdate, get_last_day
from dateutil.relativedelta import relativedelta
from collections import Counter


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _month_range(from_date, to_date):
	"""Yield (month_start, month_end) pairs for every month in [from_date, to_date]."""
	cursor = from_date.replace(day=1)
	while cursor <= to_date:
		month_start = cursor
		month_end   = min(getdate(get_last_day(cursor)), to_date)
		yield month_start, month_end
		cursor = (cursor + relativedelta(months=1)).replace(day=1)


# ---------------------------------------------------------------------------
# Company dropdown
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_companies():
	return frappe.db.get_all("Company", pluck="company", order_by="company asc")


# ---------------------------------------------------------------------------
# KPI data  (company-scoped + global masters)
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_kpi_data(company, from_date, to_date):
	from_date = getdate(from_date)
	to_date   = getdate(to_date)

	# ── Company snapshot ────────────────────────────────────────────────────

	# 1. Total registered (all Company Link rows for this company — history)
	total_registered = frappe.db.count("Company Link", filters={"company": company})

	# 2. Active employees right now
	total_active = frappe.db.count("Company Link", filters={
		"company":   company,
		"is_active": 1
	})

	# 3. Salary structures for this company
	salary_structures = frappe.db.count("Salary Structure", filters={"company": company})

	# 4. Submitted Salary Structure Assignments overlapping the period
	ssa_count = frappe.db.count("Salary Structure Assignment", filters={
		"company":   company,
		"docstatus": 1,
		"from_date": ["<=", to_date],
		"to_date":   [">=", from_date]
	})

	# 5. Salary components (global)
	salary_components = frappe.db.count("Salary Component")

	# 6. Holiday days in range from company default holiday list
	holiday_list_name = frappe.db.get_value("Company", company, "default_holiday_list")
	holiday_count = 0
	if holiday_list_name:
		holiday_count = frappe.db.count("Holiday", filters={
			"parent":       holiday_list_name,
			"holiday_date": ["between", [from_date, to_date]]
		})

	# 7. Employees currently On Hold (salary hold, status = On Hold)
	on_hold_count = frappe.db.count("Employee Salary Hold", filters={
		"company":   company,
		"status":    "On Hold",
		"docstatus": 1
	})

	# 8. Active employees WITHOUT a submitted Salary Structure Assignment
	#    in the selected period
	active_employees = frappe.db.get_all(
		"Company Link",
		filters={"company": company, "is_active": 1},
		pluck="name"
	)
	assigned_employees = frappe.db.get_all(
		"Salary Structure Assignment",
		filters={
			"company":   company,
			"docstatus": 1,
			"from_date": ["<=", to_date],
			"to_date":   [">=", from_date]
		},
		pluck="employee"
	)
	assigned_set         = set(assigned_employees)
	without_assignment   = len([e for e in active_employees if e not in assigned_set])

	# ── Statutory completeness ──────────────────────────────────────────────
	# Get employee names linked to this company (active)
	emp_names = frappe.db.get_all(
		"Company Link",
		filters={"company": company, "is_active": 1},
		pluck="employee"   # employee field links to Employee doctype
	)

	esic_filled = 0
	pf_filled   = 0
	if emp_names:
		esic_filled = frappe.db.count("Employee", filters={
			"name":        ["in", emp_names],
			"esic_number": ["!=", ""]
		})
		pf_filled = frappe.db.count("Employee", filters={
			"name":           ["in", emp_names],
			"pf_uan_number":  ["!=", ""]
		})

	# ── Global masters ──────────────────────────────────────────────────────
	dept_count        = frappe.db.count("Department")
	designation_count = frappe.db.count("Designation")
	category_count    = frappe.db.count("Category")
	division_count    = frappe.db.count("Division")

	return {
		# company snapshot
		"total_registered":    total_registered,
		"total_active":        total_active,
		"salary_structures":   salary_structures,
		"ssa_count":           ssa_count,
		"salary_components":   salary_components,
		"holiday_count":       holiday_count,
		"on_hold_count":       on_hold_count,
		"without_assignment":  without_assignment,
		# statutory
		"esic_filled":         esic_filled,
		"pf_filled":           pf_filled,
		# global masters
		"dept_count":          dept_count,
		"designation_count":   designation_count,
		"category_count":      category_count,
		"division_count":      division_count,
	}


# ---------------------------------------------------------------------------
# Monthly tracker table
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_monthly_data(company, from_date, to_date):
	from_date = getdate(from_date)
	to_date   = getdate(to_date)

	rows = []

	for month_start, month_end in _month_range(from_date, to_date):

		# ── Active employees this month ──────────────────────────────────────
		# joined on or before month_end AND (no left_date OR left_date >= month_start)
		all_in_company = frappe.db.get_all(
			"Company Link",
			filters={
				"company":         company,
				"is_active":       1,
				"date_of_joining": ["<=", month_end]
			},
			fields=["name", "left_date"]
		)
		active_this_month = [
			r for r in all_in_company
			if not r.left_date or getdate(r.left_date) >= month_start
		]
		active_count = len(active_this_month)

		# ── Attendance this month ────────────────────────────────────────────
		att_records = frappe.db.get_all(
			"Attendance",
			filters={
				"company":         company,
				"attendance_date": ["between", [month_start, month_end]]
			},
			fields=["employee", "status"]
		)

		att_total = len(att_records)

		# Min/Max = count of days employee was present (Present, On Tour, Earned Leave,
		# Casual Leave, Comp Off, Earned Comp Off, Half Day counted as 0.5)
		PRESENT_STATUSES = {"Present", "On Tour", "Earned Leave", "Casual Leave",
		                    "Comp Off", "Earned Comp Off"}
		HALF_DAY_STATUS  = "Half Day"

		emp_att_map = {}
		for r in att_records:
			emp = r["employee"]
			if emp not in emp_att_map:
				emp_att_map[emp] = 0
			if r["status"] in PRESENT_STATUSES:
				emp_att_map[emp] += 1
			elif r["status"] == HALF_DAY_STATUS:
				emp_att_map[emp] += 0.5

		if emp_att_map:
			min_att = min(emp_att_map.values())
			max_att = max(emp_att_map.values())
		else:
			min_att = 0
			max_att = 0

		# Absent days total this month
		absent_total = sum(1 for r in att_records if r["status"] == "Absent")

		# LWP total this month
		lwp_total = sum(1 for r in att_records if r["status"] == "LWP")

		# ── Salary slips (submitted) this month ─────────────────────────────
		slip_count = frappe.db.count("Salary Slip", filters={
			"company":    company,
			"start_date": [">=", month_start],
			"end_date":   ["<=", month_end],
			"docstatus":  1
		})

		# ── Salary hold — On Hold this month ────────────────────────────────
		month_name = month_start.strftime("%B")   # e.g. "April"
		year_str   = str(month_start.year)

		hold_count = frappe.db.count("Employee Salary Hold", filters={
			"company":   company,
			"month":     month_name,
			"year":      year_str,
			"status":    "On Hold",
			"docstatus": 1
		})

		rows.append({
			"month":        month_start.strftime("%b %Y"),
			"active_count": active_count,
			"att_total":    att_total,
			"min_att":      min_att,
			"max_att":      max_att,
			"slip_count":   slip_count,
			"hold_count":   hold_count,
			"absent_total": absent_total,
			"lwp_total":    lwp_total,
		})

	return rows



# ---------------------------------------------------------------------------
# Employee classification breakdown
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_classification_data(company):
	# Fetch all active employees in this company with their category + skill_type
	emp_rows = frappe.db.get_all(
		"Company Link",
		filters={"company": company, "is_active": 1},
		fields=["category", "skill_type"]
	)

	# Fetch has_subtype flag for every category in one query
	cat_names = list({r.category for r in emp_rows if r.category})
	has_subtype_map = {}
	if cat_names:
		cat_docs = frappe.db.get_all(
			"Category",
			filters={"name": ["in", cat_names]},
			fields=["category", "has_subtype"]
		)
		has_subtype_map = {c.category: bool(c.has_subtype) for c in cat_docs}

	# Build breakdown dict
	breakdown = {}
	for r in emp_rows:
		cat     = r.category or "Unassigned"
		has_sub = has_subtype_map.get(cat, False)
		skill   = r.skill_type if (has_sub and r.skill_type) else None

		if cat not in breakdown:
			breakdown[cat] = {"has_subtype": has_sub, "counts": {}, "total": 0}

		breakdown[cat]["total"] += 1

		if has_sub:
			breakdown[cat]["counts"][skill] = breakdown[cat]["counts"].get(skill, 0) + 1

	# Flatten to list sorted by category name
	result = []
	for cat, data in sorted(breakdown.items()):
		result.append({
			"category":    cat,
			"has_subtype": data["has_subtype"],
			"counts":      data["counts"],
			"total":       data["total"]
		})

	return result