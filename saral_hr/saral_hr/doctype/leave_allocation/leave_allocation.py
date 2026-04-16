# Copyright (c) 2026, sj and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import today, getdate


class LeaveAllocation(Document):

    def validate(self):
        self._recalculate_remaining()
        self._update_status()

    def on_submit(self):
        self._recalculate_remaining()
        self._update_status()

    def _recalculate_remaining(self):
        """Recalculate remaining_leaves for every row in the child table."""
        for row in self.leave_allocation_details:
            row.remaining_leaves = (row.allocated_leaves or 0) - (row.used_leaves or 0)

    def _update_status(self):
        """Auto-set status based on to_date."""
        if self.status == "Cancelled":
            return
        if self.to_date and getdate(self.to_date) < getdate(today()):
            self.status = "Expired"
        else:
            self.status = "Active"


@frappe.whitelist()
def expire_allocation(name):
    """Manually expire a Leave Allocation."""
    doc = frappe.get_doc("Leave Allocation", name)
    doc.status = "Expired"
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return "Expired"


@frappe.whitelist()
def reactivate_allocation(name):
    """Reactivate an expired Leave Allocation."""
    doc = frappe.get_doc("Leave Allocation", name)
    doc.status = "Active"
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return "Active"


@frappe.whitelist()
def get_all_leave_types():
    """Return all leave types — used by the form JS to auto-populate child rows."""
    return frappe.get_all(
        "Leave Types",
        fields=["name", "abbr", "max_days_allowed"],
        order_by="name asc"
    )


@frappe.whitelist()
def get_flat_allocations():
    """
    Return one row per (employee, leave_type) for the custom list view.
    emp.employee = the Full Name field on the Employee doctype (fieldname: employee, label: Full Name).
    la.employee  = stores the Employee series ID e.g. HR-EMP-00001.
    """
    rows = frappe.db.sql("""
        SELECT
            la.name              AS allocation_name,
            la.employee          AS employee,
            emp.employee         AS employee_name,
            la.from_date         AS from_date,
            la.to_date           AS to_date,
            la.status            AS status,
            lad.leave_type       AS leave_type,
            lad.allocated_leaves AS allocated,
            lad.used_leaves      AS used,
            lad.remaining_leaves AS balance
        FROM
            `tabLeave Allocation` la
            JOIN `tabLeave Allocation Detail` lad ON lad.parent = la.name
            LEFT JOIN `tabEmployee` emp ON emp.name = la.employee
        WHERE
            la.docstatus < 2
        ORDER BY
            la.employee, lad.leave_type
    """, as_dict=True)
    return rows


@frappe.whitelist()
def get_leave_ledger(employee, leave_type, from_date, to_date):
    """
    Return a list of ledger entries for the given employee + leave_type + period.

    Each entry has:
        date, day, status, leaves_in, leaves_out, balance
    """
    alloc = frappe.db.get_value(
        "Leave Allocation",
        {
            "employee":  employee,
            "from_date": ["<=", from_date],
            "to_date":   [">=", to_date],
            "docstatus": ["<", 2],
        },
        ["name", "from_date", "to_date"],
        as_dict=True
    )

    entries = []
    balance = 0.0

    # ── Opening entry: allocated amount ─────────────────────────────────────
    if alloc:
        allocated = frappe.db.get_value(
            "Leave Allocation Detail",
            {"parent": alloc.name, "leave_type": leave_type},
            "allocated_leaves"
        ) or 0.0

        open_date = frappe.utils.getdate(from_date)

        if allocated:
            balance = float(allocated)
            entries.append({
                "date":       frappe.utils.format_date(from_date),
                "day":        open_date.strftime("%A"),
                "status":     "Added",
                "leaves_in":  allocated,
                "leaves_out": "-",
                "balance":    balance
            })

    # ── Usage entries from Attendance ────────────────────────────────────────
    # Map attendance status → leave type name
    STATUS_LEAVE_MAP = {
        "Sick Leave":      "Sick Leave",
        "Casual Leave":    "Casual Leave",
        "Annual Leave":    "Annual Leave",
        "Earned Leave":    "Earned Leave",
        "Comp Off":        "Comp Off",
        "LWP":             "LWP",
        "Earned Comp Off": "Earned Comp Off",
    }

    # Reverse-map: leave type → attendance status(es)
    attendance_statuses = [
        status for status, lt in STATUS_LEAVE_MAP.items()
        if lt == leave_type
    ]

    if attendance_statuses:
        attendance_records = frappe.get_all(
            "Attendance",
            filters={
                "employee":        employee,
                "attendance_date": ["between", [from_date, to_date]],
                "status":          ["in", attendance_statuses],
                "docstatus":       ["<", 2],
            },
            fields=["attendance_date", "status"],
            order_by="attendance_date asc"
        )

        for att in attendance_records:
            att_date = frappe.utils.getdate(att.attendance_date)
            balance -= 1.0
            entries.append({
                "date":       frappe.utils.format_date(att.attendance_date),
                "day":        att_date.strftime("%A"),
                "status":     "Used",
                "leaves_in":  "-",
                "leaves_out": 1,
                "balance":    balance
            })

    # ── Expiry entry at period end ───────────────────────────────────────────
    if alloc and balance > 0:
        exp_date = frappe.utils.getdate(to_date)
        entries.append({
            "date":       frappe.utils.format_date(to_date),
            "day":        exp_date.strftime("%A"),
            "status":     "Expired",
            "leaves_in":  "-",
            "leaves_out": balance,
            "balance":    0
        })

    return entries


@frappe.whitelist()
def update_used_leaves_from_attendance(employee, attendance_date, status):
    """
    Called after an Attendance record is saved/submitted.
    Finds the active Leave Allocation for the employee on that date,
    increments used_leaves for the matching leave type, and saves.
    """
    STATUS_LEAVE_MAP = {
        "Sick Leave":      "Sick Leave",
        "Casual Leave":    "Casual Leave",
        "Annual Leave":    "Annual Leave",
        "Earned Leave":    "Earned Leave",
        "Comp Off":        "Comp Off",
        "LWP":             "LWP",
        "Earned Comp Off": "Earned Comp Off",
    }

    leave_type = STATUS_LEAVE_MAP.get(status)
    if not leave_type:
        return  # Not a leave status — nothing to update

    alloc_name = frappe.db.get_value(
        "Leave Allocation",
        {
            "employee":  employee,
            "from_date": ["<=", attendance_date],
            "to_date":   [">=", attendance_date],
            "docstatus": ["<", 2],
        },
        "name"
    )

    if not alloc_name:
        return  # No active allocation found

    alloc_doc = frappe.get_doc("Leave Allocation", alloc_name)

    for row in alloc_doc.leave_allocation_details:
        if row.leave_type == leave_type:
            row.used_leaves = (row.used_leaves or 0) + 1
            row.remaining_leaves = (row.allocated_leaves or 0) - row.used_leaves
            break

    alloc_doc.save(ignore_permissions=True)
    frappe.db.commit()