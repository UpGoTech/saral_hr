# Copyright (c) 2026, sj and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.model.naming import set_name_by_naming_series

class Employee(Document):
    def autoname(self):
        set_name_by_naming_series(self)

    def validate(self):
        # Populate Full Name into the actual field "employee"
        name_parts = [self.first_name, self.middle_name, self.last_name]
        self.employee = " ".join(filter(None, name_parts))

        # Aadhar Number uniqueness check
        if self.aadhar_number:
            duplicate = frappe.db.exists(
                "Employee",
                {
                    "aadhar_number": self.aadhar_number,
                    "name": ("!=", self.name)
                }
            )
            if duplicate:
                frappe.throw(
                    f"Aadhar Number <b>{self.aadhar_number}</b> already exists for Employee <b>{duplicate}</b>."
                )

    def after_insert(self):
        self.sync_active_company()

    def on_update(self):
        self.sync_active_company()

    def sync_active_company(self):
        companies = frappe.get_all(
            "Company Link",
            filters={"employee": self.name, "is_active": 1},
            fields=["company"]
        )
        val = "\n".join([c.company for c in companies]) if companies else "No Active Company"
        frappe.db.set_value("Employee", self.name, "active_company", val)
        frappe.db.commit()