import frappe
from frappe import _
from frappe.model.document import Document

VALID_FULL_STATUSES = {"Present", "On Tour", "Absent", "Half Day", "Holiday"}

class AttendanceDailyRate(Document):

    def validate(self):
        self.validate_status()
        self.clear_half_day_fields()
        self.compute_ot_minutes()
        self.validate_duplicate()

    def validate_status(self):
        if self.status not in VALID_FULL_STATUSES:
            frappe.throw(_("Invalid status: {0}").format(frappe.bold(self.status)))

    def clear_half_day_fields(self):
        # first_half / second_half are no longer used — always blank
        self.first_half  = ""
        self.second_half = ""

    def compute_ot_minutes(self):
        raw = (self.ot_hours or "").strip()
        if not raw:
            self.ot_minutes = 0
            return
        if ":" in raw:
            parts = raw.split(":")
            h = int(parts[0]) if parts[0].isdigit() else 0
            m = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
            if m > 59:
                m = 59
            self.ot_minutes = h * 60 + m
        else:
            n = int(raw) if raw.isdigit() else 0
            self.ot_minutes = n * 60

    def validate_duplicate(self):
        existing = frappe.db.exists(
            "Attendance Daily Rate",
            {
                "employee":        self.employee,
                "attendance_date": self.attendance_date,
                "name":            ["!=", self.name or ""],
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