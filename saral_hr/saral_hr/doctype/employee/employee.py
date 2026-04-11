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

        # Aadhar Number validation (optional but must be valid if provided)
        if self.aadhar_number:
            if not self.aadhar_number.isdigit() or len(self.aadhar_number) != 12:
                frappe.throw("Aadhar Number must be exactly 12 digits.")

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
        self.sync_full_name_to_linked_docs()

    def on_update(self):
        self.sync_active_company()
        self.sync_full_name_to_linked_docs()

    def sync_active_company(self):
        companies = frappe.get_all(
            "Company Link",
            filters={"employee": self.name, "is_active": 1},
            fields=["company"]
        )
        val = "\n".join([c.company for c in companies]) if companies else "No Active Company"
        frappe.db.set_value("Employee", self.name, "active_company", val)
        frappe.db.commit()

    def sync_full_name_to_linked_docs(self):
        """
        When an employee's name changes, push the updated full_name to:
        1. All Company Link records (active + archived)
        2. All Attendance records (employee_name field)
        3. All Salary Slip records (employee_name field)
        """
        if not self.employee:
            return

        # ── 1. Company Link ──────────────────────────────────────────────────
        all_links = frappe.get_all(
            "Company Link",
            filters={"employee": self.name},
            fields=["name"]
        )
        for link in all_links:
            frappe.db.set_value(
                "Company Link",
                link.name,
                {
                    "full_name":     self.employee,
                    "aadhar_number": self.aadhar_number or ""
                },
                update_modified=False
            )

        # ── 2. Attendance ────────────────────────────────────────────────────
        # employee_name is a fetch_from field — update stored value directly
        frappe.db.sql("""
            UPDATE `tabAttendance`
            SET employee_name = %(name)s
            WHERE employee IN (
                SELECT name FROM `tabCompany Link`
                WHERE employee = %(emp)s
            )
        """, {"name": self.employee, "emp": self.name})

        # ── 3. Salary Slip ───────────────────────────────────────────────────
        # employee_name fetches from Company Link.full_name — update stored value
        frappe.db.sql("""
            UPDATE `tabSalary Slip`
            SET employee_name = %(name)s
            WHERE employee IN (
                SELECT name FROM `tabCompany Link`
                WHERE employee = %(emp)s
            )
        """, {"name": self.employee, "emp": self.name})

        frappe.db.commit()