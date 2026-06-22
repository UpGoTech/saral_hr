import frappe
from frappe.utils import getdate


def get_holiday_list_for_date(attendance_date, company):
    company_doc = frappe.get_doc("Company", company)
    attendance_date = getdate(attendance_date)

    for row in company_doc.get("holiday_list_periods", []):
        if getdate(row.from_date) <= attendance_date <= getdate(row.to_date):
            return row.holiday_list

    return None  # ✅ Default use nahi hoga


@frappe.whitelist()
def check_is_holiday(employee, attendance_date):
    company = frappe.db.get_value("Company Link", employee, "company")
    if not company:
        return None

    holiday_list_name = get_holiday_list_for_date(attendance_date, company)
    if not holiday_list_name:
        return None

    holiday_list = frappe.get_doc("Holiday List", holiday_list_name)

    for h in holiday_list.holidays:
        if getdate(h.holiday_date) == getdate(attendance_date):
            return h.description or holiday_list_name

    return None
