import frappe
from frappe.model.document import Document
from datetime import date

FAR_FUTURE = date(9999, 12, 31)


class SalaryStructureAssignment(Document):
    def on_submit(self):
        _check_overlap(
            employee=self.employee,
            from_date=self.from_date,
            to_date=self.to_date,
            employee_name=self.employee_name,
            current_name=self.name,
            throw_if_overlap=True,
        )

    def on_cancel(self):
        pass


@frappe.whitelist()
def check_overlap(employee, from_date, to_date=None, employee_name=None, current_name=None, throw_if_overlap=False):
    return _check_overlap(
        employee=employee, from_date=from_date, to_date=to_date,
        employee_name=employee_name, current_name=current_name,
        throw_if_overlap=throw_if_overlap, submitted_only=False,
    )


def _check_overlap(employee, from_date, to_date=None, employee_name=None,
                   current_name=None, throw_if_overlap=False, submitted_only=False):
    if not employee or not from_date:
        return None

    filters = {"employee": employee, "docstatus": 1 if submitted_only else ["!=", 2]}
    if current_name:
        filters["name"] = ["!=", current_name]

    records = frappe.db.get_all(
        "Salary Structure Assignment",
        filters=filters,
        fields=["name", "from_date", "to_date"],
    )

    a_start = frappe.utils.getdate(from_date)
    a_end   = frappe.utils.getdate(to_date) if to_date else None

    for rec in records:
        b_start = frappe.utils.getdate(rec.from_date)
        b_end   = frappe.utils.getdate(rec.to_date) if rec.to_date else FAR_FUTURE

        if (b_start <= a_start <= b_end) or (a_end and b_start <= a_end <= b_end):
            if throw_if_overlap:
                frappe.throw(
                    title="Duplicate Salary Structure Assignment",
                    msg=(
                        f"A Salary Structure Assignment already exists for "
                        f"<b>{employee_name or employee}</b> overlapping the selected period.<br><br>"
                        f"Existing: <a href='/app/salary-structure-assignment/{rec.name}' target='_blank'>"
                        f"<b>{rec.name}</b></a> &nbsp;|&nbsp; "
                        f"<b>{rec.from_date}</b> to <b>{rec.to_date or 'Ongoing'}</b>"
                    ),
                    exc=frappe.DuplicateEntryError,
                )
            else:
                return {
                    "name":      rec.name,
                    "from_date": str(rec.from_date),
                    "to_date":   str(rec.to_date) if rec.to_date else None,
                }

    return None


@frappe.whitelist()
def get_existing_assignments(employee):
    if not employee:
        return []
    return frappe.db.get_all(
        "Salary Structure Assignment",
        filters={"employee": employee, "docstatus": ["!=", 2]},
        fields=["name", "from_date", "to_date", "docstatus"],
        order_by="from_date desc",
    )