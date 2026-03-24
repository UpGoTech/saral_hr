import frappe
from frappe.model.document import Document
from frappe.utils import date_diff, today, getdate, add_days


class LeaveApplication(Document):

    def validate(self):
        self.calculate_total_days()
        self.fetch_leave_balance()
        self.validate_balance()
        self.validate_overlap()
        self.validate_max_consecutive()
        self.validate_joining_date()
        self.stamp_approved_on()

    def on_update(self):
        if self.status == "Approved":
            _deduct_balance(
                self.employee, self.leave_type,
                self.from_date, self.total_days, self.name
            )
            _create_attendance_for_leave(self)

        elif self.status == "Rejected":
            _reverse_deduction(
                self.employee, self.leave_type,
                self.from_date, self.total_days, self.name
            )
            _cancel_attendance_for_leave(self.name)

    # ── Validation methods ────────────────────────────────────────────────────

    def calculate_total_days(self):
        if not self.from_date or not self.to_date:
            return

        diff = date_diff(self.to_date, self.from_date) + 1

        if diff <= 0:
            frappe.throw("To Date must be on or after From Date.")

        if self.half_day and self.half_day_date:
            hd = getdate(self.half_day_date)
            fd = getdate(self.from_date)
            td = getdate(self.to_date)
            if fd <= hd <= td:
                # Half day is inside range — that day = 0.5 instead of 1
                self.total_days = diff - 0.5
            else:
                # Half day is outside range — extra partial day
                self.total_days = diff + 0.5
        elif self.half_day:
            self.total_days = diff + 0.5
        else:
            self.total_days = diff

    def fetch_leave_balance(self):
        self.leave_balance = _get_remaining_balance(
            self.employee, self.leave_type, self.from_date
        )

    def validate_balance(self):
        if self.status == "Rejected":
            return

        if self.leave_balance is None:
            frappe.throw(
                f"No Leave Allocation found for <b>{self.leave_type}</b>. "
                f"Please ask HR to create an allocation first."
            )

        if self.total_days > self.leave_balance:
            frappe.throw(
                f"Insufficient balance for <b>{self.leave_type}</b>. "
                f"Requested: <b>{self.total_days}</b> day(s), "
                f"Available: <b>{self.leave_balance}</b> day(s)."
            )

    def validate_overlap(self):
        """
        Block if another Approved leave application exists for this employee
        that overlaps with the current date range.
        """
        if self.status == "Rejected":
            return

        overlapping = frappe.db.get_value(
            "Leave Application",
            {
                "employee": self.employee,
                "status": "Approved",
                "name": ["!=", self.name],
                "from_date": ["<=", self.to_date],
                "to_date": [">=", self.from_date],
            },
            "name",
        )

        if overlapping:
            frappe.throw(
                f"An approved leave application <b>{overlapping}</b> already exists "
                f"for this employee that overlaps with the selected dates "
                f"<b>{self.from_date}</b> to <b>{self.to_date}</b>. "
                f"Please check or cancel the existing application first."
            )

    def validate_max_consecutive(self):
        """
        If Leave Type has max_consecutive_days set, validate the date range.
        Half day outside range adds 1 extra day to the consecutive count.
        """
        if self.status == "Rejected":
            return

        max_days = frappe.db.get_value(
            "Leave Types", self.leave_type, "max_consecutive_days"
        )

        if not max_days:
            return

        # Count only the from_date to to_date range for consecutive check
        consecutive = date_diff(self.to_date, self.from_date) + 1

        if consecutive > max_days:
            frappe.throw(
                f"<b>{self.leave_type}</b> allows a maximum of <b>{max_days}</b> "
                f"consecutive days per application. "
                f"You have applied for <b>{consecutive}</b> consecutive days."
            )

    def validate_joining_date(self):
        """
        Leave cannot start before the employee's date of joining.
        """
        if not self.from_date or not self.employee:
            return

        # employee links to Employee doctype in Leave Application
        # We get date_of_joining from Company Link (active employment record)
        date_of_joining = frappe.db.get_value(
            "Company Link",
            {"employee": self.employee},
            "date_of_joining",
        )

        if date_of_joining and getdate(self.from_date) < getdate(date_of_joining):
            frappe.throw(
                f"Leave From Date <b>{self.from_date}</b> cannot be before "
                f"the employee's joining date <b>{date_of_joining}</b>."
            )

    def stamp_approved_on(self):
        if self.status in ("Approved", "Rejected") and not self.approved_on:
            self.approved_on = today()


# ─── Whitelisted API ──────────────────────────────────────────────────────────

@frappe.whitelist()
def get_employee_leave_balances(employee, date):
    allocations = frappe.db.get_all(
        "Leave Allocation",
        filters={
            "employee": employee,
            "from_date": ("<=", date),
            "to_date": (">=", date),
        },
        fields=["leave_type", "new_leaves_allocated", "used_leaves", "remaining_leaves"],
        order_by="leave_type asc",
    )
    return [
        {
            "leave_type": a.leave_type,
            "allocated": a.new_leaves_allocated or 0,
            "used": a.used_leaves or 0,
            "remaining": a.remaining_leaves or 0,
        }
        for a in allocations
    ]


@frappe.whitelist()
def get_weekly_off_days_in_range(employee, from_date, to_date):
    """
    Returns a list of dates in the range that fall on the employee's weekly off day.
    Called by JS to warn the user before submitting.
    """
    weekly_off = frappe.db.get_value(
        "Company Link",
        {"employee": employee},
        "weekly_off",
    )

    if not weekly_off:
        return []

    # Map day name to weekday number (Monday=0 ... Sunday=6)
    DAY_MAP = {
        "Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3,
        "Friday": 4, "Saturday": 5, "Sunday": 6
    }

    weekly_off_num = DAY_MAP.get(weekly_off)
    if weekly_off_num is None:
        return []

    current = getdate(from_date)
    end = getdate(to_date)
    weekly_off_dates = []

    while current <= end:
        if current.weekday() == weekly_off_num:
            weekly_off_dates.append(str(current))
        current = add_days(current, 1)

    return weekly_off_dates


# ─── Balance helpers ──────────────────────────────────────────────────────────

def _get_remaining_balance(employee, leave_type, date):
    return frappe.db.get_value(
        "Leave Allocation",
        {
            "employee": employee,
            "leave_type": leave_type,
            "from_date": ("<=", date),
            "to_date": (">=", date),
        },
        "remaining_leaves",
    )


def _get_allocation_name(employee, leave_type, date):
    return frappe.db.get_value(
        "Leave Allocation",
        {
            "employee": employee,
            "leave_type": leave_type,
            "from_date": ("<=", date),
            "to_date": (">=", date),
        },
        "name",
    )


def _deduct_balance(employee, leave_type, date, days, application_name):
    # Guard: if attendance already exists for this leave, it was already deducted
    existing_att = frappe.db.count(
        "Attendance",
        {"leave_application": application_name, "docstatus": ["<", 2]}
    )
    if existing_att:
        return

    alloc_name = _get_allocation_name(employee, leave_type, date)
    if not alloc_name:
        return

    alloc = frappe.get_doc("Leave Allocation", alloc_name)
    alloc.used_leaves = (alloc.used_leaves or 0) + days
    alloc.remaining_leaves = alloc.new_leaves_allocated - alloc.used_leaves
    alloc.save(ignore_permissions=True)


def _reverse_deduction(employee, leave_type, date, days, application_name):
    # Only reverse if attendance records exist (meaning previously approved)
    existing_att = frappe.db.count(
        "Attendance",
        {"leave_application": application_name, "docstatus": ["<", 2]}
    )
    if not existing_att:
        return

    alloc_name = _get_allocation_name(employee, leave_type, date)
    if not alloc_name:
        return

    alloc = frappe.get_doc("Leave Allocation", alloc_name)
    alloc.used_leaves = max((alloc.used_leaves or 0) - days, 0)
    alloc.remaining_leaves = alloc.new_leaves_allocated - alloc.used_leaves
    alloc.save(ignore_permissions=True)


# ─── Leave type → Attendance status map ──────────────────────────────────────

LEAVE_ATTENDANCE_STATUS = {
    "Earned Leave": "Earned Leave",
    "Casual Leave": "Casual Leave",
    "Comp Off":     "Comp Off",
    "LWP":          "LWP",
}

# For half day attendance — what half_day_type to set
LEAVE_HALF_DAY_TYPE = {
    "Earned Leave": "Earned Leave",
    "Casual Leave": "Casual Leave",
    "Comp Off":     "Comp Off",
    "LWP":          "LWP",
}


# ─── Attendance auto-create ───────────────────────────────────────────────────

def _create_attendance_for_leave(doc):
    leave_status = LEAVE_ATTENDANCE_STATUS.get(doc.leave_type)
    if not leave_status:
        return

    from_date     = getdate(doc.from_date)
    to_date       = getdate(doc.to_date)
    half_day_date = getdate(doc.half_day_date) if doc.half_day and doc.half_day_date else None

    # Get employee's weekly off day to handle override
    weekly_off = frappe.db.get_value(
        "Company Link",
        {"employee": doc.employee},
        "weekly_off",
    )
    DAY_MAP = {
        "Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3,
        "Friday": 4, "Saturday": 5, "Sunday": 6
    }
    weekly_off_num = DAY_MAP.get(weekly_off) if weekly_off else None

    # Process each date in the from_date → to_date range
    current = from_date
    while current <= to_date:
        is_weekly_off = (weekly_off_num is not None and current.weekday() == weekly_off_num)

        if half_day_date and current == half_day_date:
            # This specific date is a half day
            _upsert_attendance(
                employee=doc.employee,
                date=current,
                status="Half Day",
                half_day_type=LEAVE_HALF_DAY_TYPE.get(doc.leave_type, "Present"),
                leave_application_name=doc.name,
                override_weekly_off=is_weekly_off,
            )
        else:
            _upsert_attendance(
                employee=doc.employee,
                date=current,
                status=leave_status,
                half_day_type=None,
                leave_application_name=doc.name,
                override_weekly_off=is_weekly_off,
            )

        current = add_days(current, 1)

    # Handle half day date outside the from_date → to_date range (extra day)
    if half_day_date and not (from_date <= half_day_date <= to_date):
        is_weekly_off = (weekly_off_num is not None and half_day_date.weekday() == weekly_off_num)
        _upsert_attendance(
            employee=doc.employee,
            date=half_day_date,
            status="Half Day",
            half_day_type=LEAVE_HALF_DAY_TYPE.get(doc.leave_type, "Present"),
            leave_application_name=doc.name,
            override_weekly_off=is_weekly_off,
        )


def _upsert_attendance(employee, date, status, half_day_type, leave_application_name, override_weekly_off=False):
    """
    Create or update attendance for the given employee and date.

    Rules:
    - If record exists and is linked to THIS leave → update it
    - If record exists with no leave link (manual/bulk) → overwrite with leave status
    - If record exists linked to a DIFFERENT leave → skip
    - If record is Weekly Off and override_weekly_off=True → override it with leave status
    - If no record exists → create new
    """
    existing = frappe.db.get_value(
        "Attendance",
        {
            "employee": employee,
            "attendance_date": date,
            "docstatus": ["<", 2],
        },
        ["name", "leave_application", "status"],
        as_dict=True,
    )

    if existing:
        # Linked to a different leave — do not touch
        if existing.leave_application and existing.leave_application != leave_application_name:
            return

        # Weekly Off record — only override if the leave explicitly covers this day
        if existing.status == "Weekly Off" and not override_weekly_off:
            return

        # Update the existing record
        att = frappe.get_doc("Attendance", existing.name)
        att.status = status
        att.half_day_type = half_day_type
        att.leave_application = leave_application_name
        att.save(ignore_permissions=True)

    else:
        att = frappe.new_doc("Attendance")
        att.naming_series = "HR-ATT-.YYYY.-"
        att.employee = employee
        att.attendance_date = date
        att.status = status
        att.half_day_type = half_day_type
        att.leave_application = leave_application_name
        att.insert(ignore_permissions=True)


def _cancel_attendance_for_leave(application_name):
    """
    When leave is rejected, revert all attendance records linked to it.
    Weekly Off days that were overridden go back to Weekly Off.
    All others go to Absent.
    """
    records = frappe.db.get_all(
        "Attendance",
        filters={
            "leave_application": application_name,
            "docstatus": ["<", 2],
        },
        fields=["name", "attendance_date", "employee"],
    )

    for r in records:
        # Check if this date is actually a weekly off for the employee
        weekly_off = frappe.db.get_value(
            "Company Link",
            {"employee": r.employee},
            "weekly_off",
        )
        DAY_MAP = {
            "Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3,
            "Friday": 4, "Saturday": 5, "Sunday": 6
        }
        weekly_off_num = DAY_MAP.get(weekly_off) if weekly_off else None
        att_date = getdate(r.attendance_date)
        is_weekly_off = (weekly_off_num is not None and att_date.weekday() == weekly_off_num)

        att = frappe.get_doc("Attendance", r.name)
        att.status = "Weekly Off" if is_weekly_off else "Absent"
        att.half_day_type = None
        att.leave_application = None
        att.save(ignore_permissions=True)