import frappe


def execute():
	"""PT is calculated from Company slabs — clear special monthly amounts."""
	if not frappe.db.exists("Salary Component", "Professional Tax"):
		return

	doc = frappe.get_doc("Salary Component", "Professional Tax")
	changed = False
	if int(getattr(doc, "is_special_component", 0) or 0):
		doc.is_special_component = 0
		changed = True
	if doc.get("monthly_amounts"):
		doc.set("monthly_amounts", [])
		changed = True
	if hasattr(doc, "is_pt_component") and not int(doc.is_pt_component or 0):
		doc.is_pt_component = 1
		changed = True
	if changed:
		doc.save(ignore_permissions=True)
