import frappe
from frappe.model.document import Document
from frappe.utils import today, getdate


class EmployeeSalaryHold(Document):

    def validate(self):
        self.validate_period_year()
        self.validate_employee_not_already_on_hold()
        self.validate_release_fields()
        self.fetch_employee_details()

    def validate_period_year(self):
        from saral_hr.utils.period import validate_period_year

        if self.year:
            validate_period_year(self.year)

    def validate_employee_not_already_on_hold(self):
        if self.status == "On Hold":
            existing = frappe.db.get_value(
                "Employee Salary Hold",
                {
                    "employee": self.employee,
                    "status": "On Hold",
                    "docstatus": 1,
                    "name": ("!=", self.name),
                },
                "name",
            )
            if existing:
                frappe.throw(
                    f"Employee <b>{self.employee_name}</b> already has an active Salary Hold: "
                    f"<a href='/app/employee-salary-hold/{existing}'>{existing}</a>. "
                    "Please release the existing hold before creating a new one."
                )

    def validate_release_fields(self):
        if self.status == "Released":
            if not self.release_date:
                frappe.throw("Release Date is mandatory when Status is <b>Released</b>.")
            if not self.release_reason:
                frappe.throw("Reason for Release is mandatory when Status is <b>Released</b>.")
            if self.hold_date and getdate(self.release_date) < getdate(self.hold_date):
                frappe.throw("Release Date cannot be earlier than Hold Date.")

    def fetch_employee_details(self):
        if self.employee:
            emp = frappe.db.get_value(
                "Company Link",
                {"employee": self.employee, "is_active": 1},
                ["department", "designation", "branch", "company"],
                as_dict=True,
            )
            if emp:
                self.department  = emp.department
                self.designation = emp.designation
                self.branch      = emp.branch
                self.company     = emp.company


@frappe.whitelist()
def release_salary_hold(hold_name: str, release_date: str, release_reason: str):
    hold = frappe.get_doc("Employee Salary Hold", hold_name)

    if hold.docstatus != 1:
        frappe.throw("Only submitted records can be released.")

    if hold.status == "Released":
        frappe.throw("This hold is already released.")

    frappe.db.set_value("Employee Salary Hold", hold_name, "status", "Was On Hold")

    hold.reload()
    hold.cancel()

    amended = frappe.copy_doc(hold)
    amended.amended_from   = hold.name
    amended.status         = "Released"
    amended.release_date   = release_date
    amended.release_reason = release_reason
    amended.insert()
    amended.submit()

    return amended.name


@frappe.whitelist()
def get_hold_status(employee: str):
    hold = frappe.db.get_value(
        "Employee Salary Hold",
        {"employee": employee, "status": "On Hold", "docstatus": 1},
        ["name", "hold_date", "hold_reason"],
        as_dict=True,
    )
    return hold or {}


@frappe.whitelist()
def is_employee_on_hold(employee: str) -> bool:
    return bool(
        frappe.db.exists(
            "Employee Salary Hold",
            {"employee": employee, "status": "On Hold", "docstatus": 1},
        )
    )