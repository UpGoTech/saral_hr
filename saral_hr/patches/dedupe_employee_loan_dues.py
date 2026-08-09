"""Remove duplicate Employee Loan Due rows (same loan+month); keep best row."""

import frappe


def execute():
	dupes = frappe.db.sql(
		"""
		SELECT loan, month, COUNT(*) AS c
		FROM `tabEmployee Loan Due`
		GROUP BY loan, month
		HAVING c > 1
		""",
		as_dict=True,
	)
	for d in dupes:
		rows = frappe.get_all(
			"Employee Loan Due",
			filters={"loan": d.loan, "month": d.month},
			fields=["name", "salary_slip", "creation", "modified"],
			order_by="creation asc",
		)
		# Prefer row linked to a salary slip; else keep earliest
		keep = None
		for r in rows:
			if r.salary_slip:
				keep = r.name
				break
		if not keep:
			keep = rows[0].name
		for r in rows:
			if r.name == keep:
				continue
			frappe.delete_doc("Employee Loan Due", r.name, force=1, ignore_permissions=True)

	# Enforce uniqueness at DB level (idempotent if already present)
	try:
		frappe.db.add_unique("Employee Loan Due", ["loan", "month"], constraint_name="unique_loan_month")
	except Exception:
		# Index may already exist
		pass
