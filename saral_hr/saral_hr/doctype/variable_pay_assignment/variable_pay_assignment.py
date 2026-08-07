from frappe.model.document import Document
import frappe
from frappe.utils import cint

YEAR_MIN = 1950
YEAR_MAX = 2099

class VariablePayAssignment(Document):

    def validate(self):
        self.validate_year()
        self.validate_unique_month_year()
        self.validate_duplicate_divisions()

    def validate_year(self):
        year = cint(self.year)
        if year < YEAR_MIN or year > YEAR_MAX:
            frappe.throw(f"Year must be between {YEAR_MIN} and {YEAR_MAX}")
        self.year = year

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
            frappe.throw(
                f"Variable Pay Assignment already exists for {self.month} {self.year}"
            )

    def validate_duplicate_divisions(self):
        """No duplicate Division in child table"""
        divisions = [row.division for row in self.variable_pay if row.division]
        if len(divisions) != len(set(divisions)):
            frappe.throw("Duplicate Division found in Variable Pay table")

@frappe.whitelist()
def check_existing_assignment(year, month, name=None):
    exists = frappe.db.exists(
        "Variable Pay Assignment",
        {
            "year": year,
            "month": month,
            "name": ["!=", name]
        }
    )
    return {"exists": bool(exists)}

@frappe.whitelist()
def get_all_divisions():
    return frappe.get_all("Division", fields=["name"])