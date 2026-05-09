import frappe
from frappe.model.document import Document


class EmployeeCheckin(Document):

    def validate(self):
        self.validate_duplicate()

    def validate_duplicate(self):
        """Prevent duplicate checkin for same employee at same time."""
        exists = frappe.db.exists("Employee Checkin", {
            "employee": self.employee,
            "time": self.time,
            "log_type": self.log_type,
            "name": ["!=", self.name or ""],
        })
        if exists:
            frappe.throw(
                f"A {self.log_type} checkin for {self.employee} at {self.time} already exists.",
                frappe.DuplicateEntryError
            )