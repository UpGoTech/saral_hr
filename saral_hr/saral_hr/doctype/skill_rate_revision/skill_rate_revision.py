# Copyright (c) 2026, sj and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt

MONTH_NUM = {
    "January": 1, "February": 2, "March": 3,  "April": 4,
    "May": 5,     "June": 6,     "July": 7,    "August": 8,
    "September": 9, "October": 10, "November": 11, "December": 12,
}


class SkillRateRevision(Document):

    def validate(self):
        self._validate_period()
        self._validate_amounts()
        self._calculate_totals()

    def _validate_period(self):
        if not all([self.from_month, self.from_year, self.to_month, self.to_year]):
            return
        from_val = int(self.from_year) * 100 + MONTH_NUM[self.from_month]
        to_val   = int(self.to_year)   * 100 + MONTH_NUM[self.to_month]
        if to_val < from_val:
            frappe.throw(
                f"'To' period ({self.to_month} {self.to_year}) cannot be earlier than "
                f"'From' period ({self.from_month} {self.from_year})."
            )

    def _validate_amounts(self):
        for field, label in [
            ("vbasic_skilled",      "Variable Basic — Skilled"),
            ("vbasic_semi_skilled", "Variable Basic — Semi-skilled"),
            ("vbasic_unskilled",    "Variable Basic — Unskilled"),
            ("vda_skilled",         "Variable DA — Skilled"),
            ("vda_semi_skilled",    "Variable DA — Semi-skilled"),
            ("vda_unskilled",       "Variable DA — Unskilled"),
        ]:
            if flt(getattr(self, field, 0)) <= 0:
                frappe.throw(
                    f"Amount for <strong>{label}</strong> must be greater than zero."
                )

    def _calculate_totals(self):
        self.total_skilled      = flt(self.vbasic_skilled,      2) + flt(self.vda_skilled,      2)
        self.total_semi_skilled = flt(self.vbasic_semi_skilled, 2) + flt(self.vda_semi_skilled, 2)
        self.total_unskilled    = flt(self.vbasic_unskilled,    2) + flt(self.vda_unskilled,    2)


@frappe.whitelist()
def get_rate_for_period(component, month, year, skill_type):
    month_num = MONTH_NUM.get(month)
    if not month_num:
        return None

    target = int(year) * 100 + month_num

    FIELD_MAP = {
        "V-Basic": {
            "Skilled":      "vbasic_skilled",
            "Semi-skilled": "vbasic_semi_skilled",
            "Unskilled":    "vbasic_unskilled",
        },
        "V-Dearness Allowance": {
            "Skilled":      "vda_skilled",
            "Semi-skilled": "vda_semi_skilled",
            "Unskilled":    "vda_unskilled",
        },
    }

    comp_fields = FIELD_MAP.get(component)
    if not comp_fields:
        frappe.throw(f"Unknown component: {component}")

    amount_field = comp_fields.get(skill_type)
    if not amount_field:
        frappe.throw(f"Unknown skill type: {skill_type}")

    records = frappe.db.get_all(
        "Skill Rate Revision",
        filters={"docstatus": 1},
        fields=["from_month", "from_year", "to_month", "to_year", amount_field]
    )

    for r in records:
        if not all([r.from_month, r.from_year, r.to_month, r.to_year]):
            continue
        from_val = int(r.from_year) * 100 + MONTH_NUM[r.from_month]
        to_val   = int(r.to_year)   * 100 + MONTH_NUM[r.to_month]
        if from_val <= target <= to_val:
            return flt(r[amount_field], 2)

    return None