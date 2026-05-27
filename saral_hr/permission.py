import frappe

def company_link_permission_query(user):
    if "Saral HR Manager" in frappe.get_roles(user):
        return ""

    companies = frappe.get_all(
        "User Permission",
        filters={"user": user, "allow": "Company"},
        pluck="for_value"
    )

    if not companies:
        return "1=0"

    companies_escaped = ", ".join(frappe.db.escape(c) for c in companies)
    return f"`tabCompany Link`.company IN ({companies_escaped})"


def employee_permission_query(user):
    if "Saral HR Manager" in frappe.get_roles(user):
        return ""

    companies = frappe.get_all(
        "User Permission",
        filters={"user": user, "allow": "Company"},
        pluck="for_value"
    )

    if not companies:
        return "1=0"

    companies_escaped = ", ".join(frappe.db.escape(c) for c in companies)
    return f"`tabEmployee`.name IN (SELECT cl.employee FROM `tabCompany Link` cl WHERE cl.company IN ({companies_escaped}))"


def attendance_permission_query(user):
    if "Saral HR Manager" in frappe.get_roles(user):
        return ""

    companies = frappe.get_all(
        "User Permission",
        filters={"user": user, "allow": "Company"},
        pluck="for_value"
    )

    if not companies:
        return "1=0"

    companies_escaped = ", ".join(frappe.db.escape(c) for c in companies)
    return f"`tabAttendance`.employee IN (SELECT cl.employee FROM `tabCompany Link` cl WHERE cl.company IN ({companies_escaped}))"


def salary_structure_assignment_permission_query(user):
    if "Saral HR Manager" in frappe.get_roles(user):
        return ""

    companies = frappe.get_all(
        "User Permission",
        filters={"user": user, "allow": "Company"},
        pluck="for_value"
    )

    if not companies:
        return "1=0"

    companies_escaped = ", ".join(frappe.db.escape(c) for c in companies)
    return f"`tabSalary Structure Assignment`.company IN ({companies_escaped})"


def salary_slip_permission_query(user):
    if "Saral HR Manager" in frappe.get_roles(user):
        return ""

    companies = frappe.get_all(
        "User Permission",
        filters={"user": user, "allow": "Company"},
        pluck="for_value"
    )

    if not companies:
        return "1=0"

    companies_escaped = ", ".join(frappe.db.escape(c) for c in companies)
    return f"`tabSalary Slip`.company IN ({companies_escaped})"

def variable_pay_assignment_permission_query(user):
    if "Saral HR Manager" in frappe.get_roles(user):
        return ""

    if "Saral HR User" in frappe.get_roles(user):
        return ""

    companies = frappe.get_all(
        "User Permission",
        filters={"user": user, "allow": "Company"},
        pluck="for_value"
    )

    if not companies:
        return "1=0"

    companies_escaped = ", ".join(frappe.db.escape(c) for c in companies)
    
    return (
        f"`tabVariable Pay Assignment`.name IN ("
        f"SELECT vpa.name FROM `tabVariable Pay Assignment` vpa "
        f"INNER JOIN `tabVariable Pay Detail Table` vpd ON vpd.parent = vpa.name "
        f"INNER JOIN `tabCompany Link` cl ON cl.employee = vpd.employee "
        f"WHERE cl.company IN ({companies_escaped}))"
    )