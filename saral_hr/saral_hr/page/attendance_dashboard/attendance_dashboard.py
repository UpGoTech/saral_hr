import frappe


def get_context(context):
	pass


@frappe.whitelist()
def get_companies():
	user = frappe.session.user

	if "Saral HR Manager" in frappe.get_roles(user):
		return frappe.get_all("Company", pluck="name", order_by="name asc")

	companies = frappe.get_all(
		"User Permission",
		filters={"user": user, "allow": "Company"},
		pluck="for_value",
		order_by="for_value asc"
	)
	return companies


@frappe.whitelist()
def get_employee_stats(company):
	"""
	Get active and inactive employee counts for a company via Company Link doctype.
	"""
	total = frappe.db.count("Company Link", filters={"company": company})
	active = frappe.db.count("Company Link", filters={"company": company, "is_active": 1})
	inactive = total - active
	return {"total": total, "active": active, "inactive": inactive}


@frappe.whitelist()
def get_attendance_matrix(company, from_year, to_year):
	"""
	Returns: { year: { month: { marked: N, total_emp: N } } }
	  marked    = distinct employees who had attendance marked that month (any status)
	  total_emp = total employees linked to this company in Company Link
	"""
	from_year = int(from_year)
	to_year = int(to_year)

	# Total employees for this company — constant, fetched once
	total_employees = frappe.db.count("Company Link", filters={"company": company})

	matrix = {}
	for year in range(from_year, to_year + 1):
		matrix[year] = {}
		for month in range(1, 13):
			month_str = f"{year}-{str(month).zfill(2)}"

			emp_result = frappe.db.sql(
				"""
				SELECT COUNT(DISTINCT employee) AS cnt
				FROM `tabAttendance`
				WHERE company = %s
				  AND DATE_FORMAT(attendance_date, '%%Y-%%m') = %s
				""",
				(company, month_str),
				as_dict=True,
			)

			matrix[year][month] = {
				"marked": emp_result[0].cnt if emp_result else 0,
				"total_emp": total_employees,
			}

	return matrix


@frappe.whitelist()
def get_status_breakdown(company, year, month):
	"""Status breakdown for hover popover."""
	month_str = f"{int(year)}-{str(int(month)).zfill(2)}"
	rows = frappe.db.sql(
		"""
		SELECT status, COUNT(*) AS cnt
		FROM `tabAttendance`
		WHERE company = %s
		  AND DATE_FORMAT(attendance_date, '%%Y-%%m') = %s
		GROUP BY status
		ORDER BY cnt DESC
		""",
		(company, month_str),
		as_dict=True,
	)
	return {r.status: r.cnt for r in rows}