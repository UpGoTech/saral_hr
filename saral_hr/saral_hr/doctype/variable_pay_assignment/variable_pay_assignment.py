from frappe.model.document import Document
import frappe
from frappe.utils import cint

from saral_hr.utils.period import validate_period_year


class VariablePayAssignment(Document):

    def validate(self):
        self.validate_year()
        self.validate_unique_month_year()
        self.validate_duplicate_divisions()

    def validate_year(self):
        self.year = validate_period_year(self.year)

    def validate_unique_month_year(self):
        """One record per Year + Month"""
        existing = frappe.db.exists(
            "Variable Pay Assignment",
            {
                "year": self.year,
                "month": self.month,
                "name": ["!=", self.name]
            }
        )
        if existing:
            frappe.throw(f"Variable Pay Assignment for {self.month} {self.year} already exists")

    def validate_duplicate_divisions(self):
        divisions = [row.division for row in self.variable_pay or [] if row.division]
        if len(divisions) != len(set(divisions)):
            frappe.throw("Duplicate divisions found in Variable Pay table")


@frappe.whitelist()
def check_existing_assignment(year, month, name=None):
    filters = {"year": year, "month": month}
    if name:
        filters["name"] = ["!=", name]
    existing = frappe.db.exists("Variable Pay Assignment", filters)
    return {"exists": bool(existing)}


@frappe.whitelist()
def get_all_divisions():
    return frappe.get_all("Division", fields=["name"], order_by="name asc")
