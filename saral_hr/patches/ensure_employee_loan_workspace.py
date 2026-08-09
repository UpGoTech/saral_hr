"""Seed Loan salary component and Employee Loans workspace card/links."""

import frappe


def execute():
	_ensure_loan_component()
	_ensure_workspace()


def _ensure_loan_component():
	if frappe.db.exists("Salary Component", "Loan"):
		return
	frappe.get_doc(
		{
			"doctype": "Salary Component",
			"salary_component": "Loan",
			"salary_component_abbr": "LOAN",
			"type": "Deduction",
			"depends_on_payment_days": 0,
		}
	).insert(ignore_permissions=True)


def _ensure_workspace():
	if not frappe.db.exists("Workspace", "Saral HR"):
		return
	ws = frappe.get_doc("Workspace", "Saral HR")
	labels = {l.label for l in (ws.links or [])}

	def add_link(**kwargs):
		if kwargs.get("label") in labels:
			return
		ws.append("links", kwargs)
		labels.add(kwargs.get("label"))

	if "Employee Loans" not in labels:
		ws.append(
			"links",
			{
				"type": "Card Break",
				"label": "Employee Loans",
				"hidden": 0,
			},
		)
		labels.add("Employee Loans")

	add_link(
		type="Link",
		label="Employee Loan",
		link_type="DocType",
		link_to="Employee Loan",
		hidden=0,
	)
	add_link(
		type="Link",
		label="Generate Monthly Loan Dues",
		link_type="Page",
		link_to="generate-monthly-loan-dues",
		hidden=0,
	)

	ws.flags.ignore_permissions = True
	ws.flags.ignore_links = True
	# Avoid writing workspace JSON when patch runs outside migrate.
	prev_dev = frappe.conf.developer_mode
	frappe.conf.developer_mode = 0
	try:
		ws.save()
	finally:
		frappe.conf.developer_mode = prev_dev
