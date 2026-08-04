import frappe

from saral_hr.saral_hr.doctype.company.company import seed_pt_period_on_company


def execute():
	"""Seed Maharashtra PT period on companies that have none."""
	if not frappe.db.table_exists("Professional Tax Period"):
		return
	for name in frappe.get_all("Company", pluck="name"):
		seed_pt_period_on_company(name)
