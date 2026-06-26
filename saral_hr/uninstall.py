import frappe

SARAL_HR_ROLES = ["Saral HR Manager", "Saral HR User"]


def after_uninstall():
	# ponytail: doctype data is already dropped by Frappe before this hook runs
	delete_roles()


def delete_roles():
	for role in SARAL_HR_ROLES:
		for name in frappe.get_all("Custom DocPerm", filters={"role": role}, pluck="name"):
			frappe.delete_doc("Custom DocPerm", name, ignore_permissions=True, force=True)

		for name in frappe.get_all("Has Role", filters={"role": role}, pluck="name"):
			frappe.delete_doc("Has Role", name, ignore_permissions=True, force=True)

		if frappe.db.exists("Role", role):
			frappe.delete_doc("Role", role, ignore_permissions=True, force=True)

	frappe.db.commit()
	print("✅ Saral HR Roles deleted.")
