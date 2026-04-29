# Copyright (c) 2026, sj and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import today, getdate


class LeaveAllocation(Document):

    def validate(self):
        self._recalculate_used_from_attendance()
        self._recalculate_remaining()
        self._update_status()

    def on_submit(self):
        self._recalculate_used_from_attendance()
        self._recalculate_remaining()
        self._update_status()

    def _recalculate_used_from_attendance(self):
        """
        Recalculate used_leaves for every row by querying Attendance directly.
        This avoids drift caused by edits/deletions/status changes in Attendance.
        Half-day leaves count as 0.5.
        """
        if not self.employee or not self.from_date or not self.to_date:
            return

        # Build a map: leave_type -> used count (float, supports half-days)
        used_map = _compute_used_leaves_from_attendance(
            self.employee, self.from_date, self.to_date
        )

        for row in self.leave_allocation_details:
            row.used_leaves = used_map.get(row.leave_type, 0.0)

    def _recalculate_remaining(self):
        """Recalculate remaining_leaves for every row in the child table."""
        for row in self.leave_allocation_details:
            row.remaining_leaves = (row.allocated_leaves or 0) - (row.used_leaves or 0)

    def _update_status(self):
        """
        Auto-set status based on to_date.
        Only expire when today >= to_date AND there are/were remaining leaves.
        If the period hasn't ended yet, keep Active regardless of balance.
        """
        if self.status == "Cancelled":
            return

        today_date = getdate(today())
        to_date    = getdate(self.to_date) if self.to_date else None

        if to_date and today_date >= to_date:
            self.status = "Expired"
        else:
            self.status = "Active"


# ---------------------------------------------------------------------------
# Internal helper: compute used leaves from Attendance (supports half-days)
# ---------------------------------------------------------------------------

# Maps Attendance status -> Leave Type name
STATUS_LEAVE_MAP = {
    "Sick Leave":      "Sick Leave",
    "Casual Leave":    "Casual Leave",
    "Annual Leave":    "Annual Leave",
    "Earned Leave":    "Earned Leave",
    "Comp Off":        "Comp Off",
    "LWP":             "LWP",
    "Earned Comp Off": "Earned Comp Off",
}

# Half-day fields to check for each leave type
HALF_DAY_FIELDS = ["custom_first_half", "custom_second_half"]


def _compute_used_leaves_from_attendance(employee, from_date, to_date):
    """
    Returns a dict  { leave_type: float_count }  where count supports 0.5
    increments for half-day leaves.

    Logic:
    - Full-day Attendance with a leave status => 1.0 deducted
    - Half-day Attendance (status == "Half Day"):
        custom_first_half / custom_second_half => each side that matches
        a leave type adds 0.5
    """
    used_map = {}

    # 1. Full-day leave records
    full_day_statuses = list(STATUS_LEAVE_MAP.keys())
    full_records = frappe.get_all(
        "Attendance",
        filters={
            "employee":        employee,
            "attendance_date": ["between", [from_date, to_date]],
            "status":          ["in", full_day_statuses],
            "docstatus":       ["<", 2],
        },
        fields=["status"]
    )
    for rec in full_records:
        lt = STATUS_LEAVE_MAP.get(rec.status)
        if lt:
            used_map[lt] = used_map.get(lt, 0.0) + 1.0

    # 2. Half-day records — check custom_first_half / custom_second_half
    half_records = frappe.get_all(
        "Attendance",
        filters={
            "employee":        employee,
            "attendance_date": ["between", [from_date, to_date]],
            "status":          "Half Day",
            "docstatus":       ["<", 2],
        },
        fields=["custom_first_half", "custom_second_half"]
    )
    for rec in half_records:
        for field in HALF_DAY_FIELDS:
            half_status = rec.get(field) or ""
            lt = STATUS_LEAVE_MAP.get(half_status)
            if lt:
                used_map[lt] = used_map.get(lt, 0.0) + 0.5

    return used_map


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

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

    Fix:
    - Expiry entry only appears when today >= to_date AND remaining > 0
    - Used count supports 0.5 (half-day)
    - leaves_out on expiry = actual remaining at period end (not current balance variable)
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
    attendance_statuses = [
        status for status, lt in STATUS_LEAVE_MAP.items()
        if lt == leave_type
    ]

    if attendance_statuses:
        # Full-day records
        full_records = frappe.get_all(
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

        for att in full_records:
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

        # Half-day records — check custom_first_half / custom_second_half
        half_records = frappe.get_all(
            "Attendance",
            filters={
                "employee":        employee,
                "attendance_date": ["between", [from_date, to_date]],
                "status":          "Half Day",
                "docstatus":       ["<", 2],
            },
            fields=["attendance_date", "custom_first_half", "custom_second_half"],
            order_by="attendance_date asc"
        )

        for att in half_records:
            used_halves = 0
            for field in HALF_DAY_FIELDS:
                half_status = att.get(field) or ""
                if half_status in attendance_statuses:
                    used_halves += 1

            if used_halves:
                att_date    = frappe.utils.getdate(att.attendance_date)
                deduction   = used_halves * 0.5
                balance    -= deduction
                entries.append({
                    "date":       frappe.utils.format_date(att.attendance_date),
                    "day":        att_date.strftime("%A"),
                    "status":     "Used",
                    "leaves_in":  "-",
                    "leaves_out": deduction,
                    "balance":    balance
                })

    # Sort all entries by date (opening entry stays first due to from_date)
    entries.sort(key=lambda e: e["date"])

    # ── Expiry entry at period end ───────────────────────────────────────────
    # Only append when today >= to_date AND there are remaining leaves
    today_date = getdate(today())
    period_end = frappe.utils.getdate(to_date) if to_date else None

    if alloc and balance > 0 and period_end and today_date >= period_end:
        exp_date = period_end
        entries.append({
            "date":       frappe.utils.format_date(to_date),
            "day":        exp_date.strftime("%A"),
            "status":     "Expired",
            "leaves_in":  "-",
            "leaves_out": balance,   # actual remaining at period end
            "balance":    0
        })

    return entries


@frappe.whitelist()
def update_used_leaves_from_attendance(employee, attendance_date, status):
    """
    Called after an Attendance record is saved/submitted.
    Instead of incrementing, we now RECALCULATE from Attendance directly
    to avoid any drift.
    """
    # Only proceed if status is a recognised leave type
    leave_type = STATUS_LEAVE_MAP.get(status)
    if not leave_type:
        # Also handle half-day — recalculate if status is "Half Day"
        if status != "Half Day":
            return

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

    # Recalculate live from Attendance
    used_map = _compute_used_leaves_from_attendance(
        employee, alloc_doc.from_date, alloc_doc.to_date
    )

    for row in alloc_doc.leave_allocation_details:
        row.used_leaves      = used_map.get(row.leave_type, 0.0)
        row.remaining_leaves = (row.allocated_leaves or 0) - row.used_leaves

    alloc_doc.save(ignore_permissions=True)
    frappe.db.commit()


@frappe.whitelist()
def get_leave_balance_for_month(employee, year, month):
    """
    Returns EL and CL allocated / used / remaining for the active Leave Allocation
    covering the given month.  Used by the mark-attendance page.

    Returns:
    {
        "has_allocation": True/False,
        "el": { "allocated": 0, "used": 0.0, "remaining": 0.0 },
        "cl": { "allocated": 0, "used": 0.0, "remaining": 0.0 },
    }
    """
    import datetime

    try:
        year_int  = int(year)
        month_int = int(month) + 1   # JS months are 0-based
    except (ValueError, TypeError):
        return {"has_allocation": False}

    month_start = datetime.date(year_int, month_int, 1)
    if month_int == 12:
        month_end = datetime.date(year_int + 1, 1, 1) - datetime.timedelta(days=1)
    else:
        month_end = datetime.date(year_int, month_int + 1, 1) - datetime.timedelta(days=1)

    # Find the active allocation that covers this month
    alloc = frappe.db.get_value(
        "Leave Allocation",
        {
            "employee":  employee,
            "from_date": ["<=", str(month_start)],
            "to_date":   [">=", str(month_end)],
            "docstatus": ["<", 2],
        },
        ["name", "from_date", "to_date"],
        as_dict=True
    )

    if not alloc:
        return {"has_allocation": False}

    # Get allocated amounts from child table
    details = frappe.get_all(
        "Leave Allocation Detail",
        filters={"parent": alloc.name},
        fields=["leave_type", "allocated_leaves"]
    )
    allocated_map = {d.leave_type: (d.allocated_leaves or 0) for d in details}

    # Recalculate used from Attendance for the full allocation period
    used_map = _compute_used_leaves_from_attendance(
        employee, alloc.from_date, alloc.to_date
    )

    el_allocated  = allocated_map.get("Earned Leave", 0)
    cl_allocated  = allocated_map.get("Casual Leave", 0)
    el_used       = used_map.get("Earned Leave", 0.0)
    cl_used       = used_map.get("Casual Leave", 0.0)

    return {
        "has_allocation": True,
        "el": {
            "allocated": el_allocated,
            "used":      el_used,
            "remaining": max(0, el_allocated - el_used),
        },
        "cl": {
            "allocated": cl_allocated,
            "used":      cl_used,
            "remaining": max(0, cl_allocated - cl_used),
        },
    }