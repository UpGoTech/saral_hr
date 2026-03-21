import frappe
from frappe.utils import getdate, get_last_day, today, add_days
from dateutil.relativedelta import relativedelta


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


def _active_in_month(company, month_start, month_end):
	rows = frappe.db.get_all(
		"Company Link",
		filters={
			"company":         company,
			"is_active":       1,
			"date_of_joining": ["<=", month_end]
		},
		fields=["name", "left_date"]
	)
	return [r for r in rows if not r.left_date or getdate(r.left_date) >= month_start]


# ---------------------------------------------------------------------------
# Company dropdown
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_companies():
	return frappe.db.get_all("Company", pluck="company", order_by="company asc")


# ---------------------------------------------------------------------------
# KPI data
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_kpi_data(company, from_date, to_date):
	from_date = getdate(from_date)
	to_date   = getdate(to_date)

	total_registered = frappe.db.count("Company Link", filters={"company": company})

	total_active = frappe.db.count("Company Link", filters={
		"company": company, "is_active": 1
	})

	salary_structures = frappe.db.count("Salary Structure", filters={"company": company})

	ssa_count = frappe.db.count("Salary Structure Assignment", filters={
		"company":   company,
		"docstatus": 1,
		"from_date": ["<=", to_date],
		"to_date":   [">=", from_date]
	})

	salary_components = frappe.db.count("Salary Component")

	holiday_list_name = frappe.db.get_value("Company", company, "default_holiday_list")
	holiday_count = 0
	if holiday_list_name:
		holiday_count = frappe.db.count("Holiday", filters={
			"parent":       holiday_list_name,
			"holiday_date": ["between", [from_date, to_date]]
		})

	on_hold_count = frappe.db.count("Employee Salary Hold", filters={
		"company": company, "status": "On Hold", "docstatus": 1
	})

	active_employees = frappe.db.get_all(
		"Company Link", filters={"company": company, "is_active": 1}, pluck="name"
	)
	assigned_set = set(frappe.db.get_all(
		"Salary Structure Assignment",
		filters={
			"company": company, "docstatus": 1,
			"from_date": ["<=", to_date], "to_date": [">=", from_date]
		},
		pluck="employee"
	))
	without_assignment = len([e for e in active_employees if e not in assigned_set])

	emp_names = frappe.db.get_all(
		"Company Link", filters={"company": company, "is_active": 1}, pluck="employee"
	)
	esic_filled = pf_filled = 0
	if emp_names:
		esic_filled = frappe.db.count("Employee", filters={
			"name": ["in", emp_names], "esic_number": ["!=", ""]
		})
		pf_filled = frappe.db.count("Employee", filters={
			"name": ["in", emp_names], "pf_uan_number": ["!=", ""]
		})

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

	PRESENT_STATUSES = {"Present", "On Tour", "Earned Leave", "Casual Leave",
	                    "Comp Off", "Earned Comp Off"}

	rows         = []
	prev_closing = None

	for month_start, month_end in _month_range(from_date, to_date):

		# ── Head count ───────────────────────────────────────────────────────
		active_recs  = _active_in_month(company, month_start, month_end)
		active_count = len(active_recs)
		active_names = {r.name for r in active_recs}

		joined = frappe.db.count("Company Link", filters={
			"company": company, "date_of_joining": ["between", [month_start, month_end]]
		})
		left = frappe.db.count("Company Link", filters={
			"company": company, "left_date": ["between", [month_start, month_end]]
		})

		if prev_closing is not None:
			opening = prev_closing
		else:
			opening = active_count - joined + left

		closing      = active_count
		prev_closing = closing

		# ── Attendance ───────────────────────────────────────────────────────
		att_records = frappe.db.get_all(
			"Attendance",
			filters={
				"company":         company,
				"attendance_date": ["between", [month_start, month_end]]
			},
			fields=["employee", "status"]
		)

		att_total   = len(att_records)
		emp_att_map = {}
		for r in att_records:
			emp = r["employee"]
			if emp not in emp_att_map:
				emp_att_map[emp] = 0
			if r["status"] in PRESENT_STATUSES:
				emp_att_map[emp] += 1
			elif r["status"] == "Half Day":
				emp_att_map[emp] += 0.5

		min_att = min(emp_att_map.values()) if emp_att_map else 0
		max_att = max(emp_att_map.values()) if emp_att_map else 0

		emps_with_att    = len(set(r["employee"] for r in att_records) & active_names)
		att_coverage_pct = round((emps_with_att / active_count * 100)) if active_count else 0
		absent_total     = sum(1 for r in att_records if r["status"] == "Absent")
		lwp_total        = sum(1 for r in att_records if r["status"] == "LWP")

		# ── Salary slips ─────────────────────────────────────────────────────
		slip_count = frappe.db.count("Salary Slip", filters={
			"company":    company,
			"start_date": [">=", month_start],
			"end_date":   ["<=", month_end],
			"docstatus":  1
		})

		# ── Salary hold ──────────────────────────────────────────────────────
		hold_count = frappe.db.count("Employee Salary Hold", filters={
			"company":   company,
			"month":     month_start.strftime("%B"),
			"year":      str(month_start.year),
			"status":    "On Hold",
			"docstatus": 1
		})

		# ── Payroll readiness flags ───────────────────────────────────────────
		ssa_this_month = set(frappe.db.get_all(
			"Salary Structure Assignment",
			filters={
				"company": company, "docstatus": 1,
				"from_date": ["<=", month_end], "to_date": [">=", month_start]
			},
			pluck="employee"
		))

		rows.append({
			"month":            month_start.strftime("%b %Y"),
			"month_key":        month_start.strftime("%Y-%m"),
			# headcount movement
			"opening":          opening,
			"joined":           joined,
			"left":             left,
			"closing":          closing,
			# attendance
			"active_count":     active_count,
			"att_total":        att_total,
			"min_att":          min_att,
			"max_att":          max_att,
			"att_coverage_pct": att_coverage_pct,
			"emps_with_att":    emps_with_att,
			"absent_total":     absent_total,
			"lwp_total":        lwp_total,
			# payroll
			"slip_count":       slip_count,
			"hold_count":       hold_count,
			# readiness (4 checks)
			"ready_att":        emps_with_att >= active_count and active_count > 0,
			"ready_ssa":        active_names.issubset(ssa_this_month),
			"ready_no_holds":   hold_count == 0,
			"ready_slips":      slip_count >= active_count and active_count > 0,
		})

	return rows
# ---------------------------------------------------------------------------
# Assignment expiry tracker  (next 30 days from today)
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_expiring_assignments(company, from_date, to_date):
	today_date = getdate(today())
	window_end = add_days(today_date, 30)

	return frappe.db.get_all(
		"Salary Structure Assignment",
		filters={
			"company":   company,
			"docstatus": 1,
			"to_date":   ["between", [today_date, window_end]]
		},
		fields=["employee", "employee_name", "salary_structure", "from_date", "to_date"],
		order_by="to_date asc"
	)



# ---------------------------------------------------------------------------
# Employee classification breakdown
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_classification_data(company):
	emp_rows = frappe.db.get_all(
		"Company Link",
		filters={"company": company, "is_active": 1},
		fields=["category", "skill_type"]
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

		if cat not in breakdown:
			breakdown[cat] = {"has_subtype": has_sub, "counts": {}, "total": 0}

		breakdown[cat]["total"] += 1
		if has_sub and skill:
			breakdown[cat]["counts"][skill] = breakdown[cat]["counts"].get(skill, 0) + 1

	result = []
	for cat, data in sorted(breakdown.items()):
		result.append({
			"category":    cat,
			"has_subtype": data["has_subtype"],
			"counts":      data["counts"],
			"total":       data["total"]
		})
	return result