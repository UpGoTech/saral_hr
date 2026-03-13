import frappe

def after_install():
    create_roles()
    create_salary_components()  # ✅ add this

def create_roles():
    roles = ["Saral HR Manager", "Saral HR User"]
    for role in roles:
        if not frappe.db.exists("Role", role):
            frappe.get_doc({
                "doctype": "Role",
                "role_name": role,
                "desk_access": 1
            }).insert(ignore_permissions=True)
    frappe.db.commit()
    print("✅ Saral HR Roles created successfully.")

