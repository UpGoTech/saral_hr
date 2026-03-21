import frappe
from frappe.utils import getdate, get_last_day, today, add_days, flt
from dateutil.relativedelta import relativedelta
import calendar


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
		fields=["name", "left_date", "employee", "full_name", "date_of_joining"]
	)
	return [r for r in rows if not r.left_date or getdate(r.left_date) >= month_start]


def _get_employee_names(employee_ids):
	"""
	Returns a dict { company_link_name: display_name } by joining Employee.
	Company Link name = employee ID (e.g. HR-EMP-00068).
	Employee.employee = same ID.
	Actual name = first_name + middle_name + last_name on Employee doctype.
	"""
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
	gender_counts = {}
	if emp_names:
		esic_filled = frappe.db.count("Employee", filters={
			"name": ["in", emp_names], "esic_number": ["!=", ""]
		})
		pf_filled = frappe.db.count("Employee", filters={
			"name": ["in", emp_names], "pf_uan_number": ["!=", ""]
		})
		genders = frappe.db.get_all(
			"Employee",
			filters={"name": ["in", emp_names]},
			fields=["gender"]
		)
		for g in genders:
			key = g.gender or "Not specified"
			gender_counts[key] = gender_counts.get(key, 0) + 1

	# YTD salary cost — sum of net_salary from submitted salary slips in period
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

	PRESENT_STATUSES = {"Present", "On Tour", "Earned Leave", "Casual Leave",
	                    "Comp Off", "Earned Comp Off"}

	rows         = []
	prev_closing = None

	for month_start, month_end in _month_range(from_date, to_date):

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

		slip_count = frappe.db.count("Salary Slip", filters={
			"company":    company,
			"start_date": [">=", month_start],
			"end_date":   ["<=", month_end],
			"docstatus":  1
		})

		hold_count = frappe.db.count("Employee Salary Hold", filters={
			"company":   company,
			"month":     month_start.strftime("%B"),
			"year":      str(month_start.year),
			"status":    "On Hold",
			"docstatus": 1
		})

		ssa_this_month = set(frappe.db.get_all(
			"Salary Structure Assignment",
			filters={
				"company": company, "docstatus": 1,
				"from_date": ["<=", month_end], "to_date": [">=", month_start]
			},
			pluck="employee"
		))

		# Expected slips = active - on hold
		expected_slips = max(0, active_count - hold_count)

		# Attrition rate
		attrition_pct = round((left / opening * 100), 1) if opening > 0 else 0

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
			"absent_total":     absent_total,
			"lwp_total":        lwp_total,
			"min_att":          min_att,
			"max_att":          max_att,
			"slip_count":       slip_count,
			"hold_count":       hold_count,
			"ready_att":        emps_with_att >= active_count and active_count > 0,
			"ready_ssa":        active_names.issubset(ssa_this_month),
			"ready_no_holds":   hold_count == 0,
			"ready_slips":      slip_count >= expected_slips and expected_slips > 0,
		})

	return rows


# ---------------------------------------------------------------------------
# Assignment expiry tracker (next 30 days)
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


# ---------------------------------------------------------------------------
# Department-wise headcount
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_department_headcount(company):
	rows = frappe.db.get_all(
		"Company Link",
		filters={"company": company, "is_active": 1},
		fields=["department"]
	)
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

	# Build list of (month_name, year_str) tuples in the selected range
	valid_periods = set()
	cursor = from_date.replace(day=1)
	while cursor <= to_date:
		valid_periods.add((cursor.strftime("%B"), str(cursor.year)))
		cursor = (cursor + relativedelta(months=1)).replace(day=1)

	rows = frappe.db.get_all(
		"Employee Salary Hold",
		filters={"company": company, "status": "On Hold", "docstatus": 1},
		fields=["employee", "employee_name", "hold_date", "hold_reason",
		        "department", "designation", "branch", "month", "year"]
	)

	# Filter to only holds within the selected date range
	rows = [r for r in rows if (r.month, r.year) in valid_periods]

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
# POPUP: Employees without assignment
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_employees_without_assignment(company, from_date, to_date):
	from_date = getdate(from_date)
	to_date   = getdate(to_date)

	active = frappe.db.get_all(
		"Company Link",
		filters={"company": company, "is_active": 1},
		fields=["name", "date_of_joining"]
	)

	assigned_set = set(frappe.db.get_all(
		"Salary Structure Assignment",
		filters={
			"company": company, "docstatus": 1,
			"from_date": ["<=", to_date], "to_date": [">=", from_date]
		},
		pluck="employee"
	))

	unassigned = [e for e in active if e.name not in assigned_set]
	name_map   = _get_employee_names([e.name for e in unassigned])

	result = []
	for emp in unassigned:
		result.append({
			"employee":        emp.name,
			"full_name":       name_map.get(emp.name, emp.name),
			"date_of_joining": str(emp.date_of_joining) if emp.date_of_joining else ""
		})

	return sorted(result, key=lambda x: x["full_name"])


# ---------------------------------------------------------------------------
# POPUP: Employees with no attendance in a month
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_employees_no_attendance(company, month_key):
	"""month_key = YYYY-MM"""
	year, month = month_key.split("-")
	month_start = getdate(f"{year}-{month}-01")
	month_end   = getdate(get_last_day(month_start))

	active_recs  = _active_in_month(company, month_start, month_end)
	active_names = {r.name for r in active_recs}

	emps_with_att = set(frappe.db.get_all(
		"Attendance",
		filters={
			"company":         company,
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
def get_employees_by_category_skill(company, category, skill_type=""):
	filters = {"company": company, "is_active": 1, "category": category}
	if skill_type:
		filters["skill_type"] = skill_type

	rows     = frappe.db.get_all(
		"Company Link",
		filters=filters,
		fields=["name", "date_of_joining", "skill_type", "designation"]
	)
	name_map = _get_employee_names([r.name for r in rows])

	return sorted([{
		"employee":        r.name,
		"full_name":       name_map.get(r.name, r.name),
		"date_of_joining": str(r.date_of_joining) if r.date_of_joining else "",
		"skill_type":      r.skill_type or "—",
		"designation":     r.designation or "—"
	} for r in rows], key=lambda x: x["full_name"])


# ---------------------------------------------------------------------------
# POPUP: Salary slip status for a month
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_salary_slip_status(company, month_key):
	"""Returns two lists: generated (with net salary + link) and not generated."""
	year, month = month_key.split("-")
	month_start = getdate(f"{year}-{month}-01")
	month_end   = getdate(get_last_day(month_start))

	active_recs = _active_in_month(company, month_start, month_end)
	name_map    = _get_employee_names([r.name for r in active_recs])

	slips = frappe.db.get_all(
		"Salary Slip",
		filters={
			"company":    company,
			"start_date": [">=", month_start],
			"end_date":   ["<=", month_end],
			"docstatus":  1
		},
		fields=["name", "employee", "net_salary"]
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

	if hc_type == "joined":
		rows = frappe.db.get_all(
			"Company Link",
			filters={"company": company, "date_of_joining": ["between", [month_start, month_end]]},
			fields=["name", "date_of_joining", "designation", "department"]
		)
	elif hc_type == "left":
		rows = frappe.db.get_all(
			"Company Link",
			filters={"company": company, "left_date": ["between", [month_start, month_end]]},
			fields=["name", "date_of_joining", "left_date", "designation", "department"]
		)
	elif hc_type == "opening":
		day_before = month_start - relativedelta(days=1)
		all_rows = frappe.db.get_all(
			"Company Link",
			filters={"company": company, "date_of_joining": ["<=", day_before]},
			fields=["name", "date_of_joining", "left_date", "designation", "department"]
		)
		rows = [r for r in all_rows if not r.left_date or getdate(r.left_date) >= month_start]
	else:  # closing
		all_rows = frappe.db.get_all(
			"Company Link",
			filters={"company": company, "date_of_joining": ["<=", month_end]},
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
# POPUP: Full attendance summary for a month (like attendance report)
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_month_attendance_summary(company, month_key):
	"""month_key = YYYY-MM. Returns per-employee day-by-day + status counts."""
	year, month = month_key.split("-")
	month_start = getdate(f"{year}-{month}-01")
	month_end   = getdate(get_last_day(month_start))
	total_days  = calendar.monthrange(int(year), int(month))[1]

	active_recs = _active_in_month(company, month_start, month_end)
	active_map  = {r.name: r for r in active_recs}

	if not active_map:
		return {"rows": [], "total_days": total_days}

	att_records = frappe.db.get_all(
		"Attendance",
		filters={
			"company":         company,
			"attendance_date": ["between", [month_start, month_end]]
		},
		fields=["employee", "status", "attendance_date"]
	)

	STATUS_CODE = {
		"Present":         "P",
		"On Tour":         "T",
		"Absent":          "A",
		"Half Day":        "HD",
		"Holiday":         "H",
		"Weekly Off":      "WO",
		"LWP":             "LWP",
		"Earned Leave":    "EL",
		"Casual Leave":    "CL",
		"Comp Off":        "CO",
		"Earned Comp Off": "ECO",
	}

	STATUS_FIELDS = {
		"Present":         "present",
		"On Tour":         "on_tour",
		"Absent":          "absent",
		"Half Day":        "half_day",
		"Holiday":         "holiday",
		"Weekly Off":      "weekly_off",
		"LWP":             "lwp",
		"Earned Leave":    "earned_leave",
		"Casual Leave":    "casual_leave",
		"Comp Off":        "comp_off",
		"Earned Comp Off": "earned_comp_off",
	}

	# Initialise emp_data with zeros
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
		"rows":       sorted(result, key=lambda x: x["full_name"]),
		"total_days": total_days
	}