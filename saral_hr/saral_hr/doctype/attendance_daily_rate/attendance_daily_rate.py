# Copyright (c) 2026, sj and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

VALID_STATUSES = {"Present", "On Tour", "Absent", "Half Day", "Holiday"}


class AttendanceDailyRate(Document):

    def validate(self):
        self.validate_status()
        self.validate_duplicate()

    def validate_status(self):
        if self.status not in VALID_STATUSES:
            frappe.throw(_("Invalid status: {0}").format(frappe.bold(self.status)))

    def validate_duplicate(self):
        # Only block on brand-new inserts, never on updates
        if not self.is_new():
            return
        existing = frappe.db.exists(
            "Attendance Daily Rate",
            {
                "employee":        self.employee,
                "attendance_date": self.attendance_date,
            },
        )
        if existing:
            frappe.throw(
                _("Attendance Daily Rate for {0} on {1} already exists: {2}").format(
                    frappe.bold(self.employee),
                    frappe.bold(str(self.attendance_date)),
                    frappe.bold(existing),
                )
            )