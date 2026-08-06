import frappe


def execute():
	"""Drop broken report name whose scrub() is not a valid Python module."""
	old = "Monthly Salary Register (Old Format) Net Payable"
	if frappe.db.exists("Report", old):
		frappe.delete_doc("Report", old, force=1, ignore_permissions=True)
