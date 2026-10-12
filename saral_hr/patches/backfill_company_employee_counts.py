import frappe

from saral_hr.saral_hr.doctype.company.company import backfill_all_company_employee_counts


def execute():
	"""One-time backfill of Company headcount fields from active Company Links."""
	if not frappe.db.has_column("Company", "no_of_staff"):
		return
	backfill_all_company_employee_counts()
