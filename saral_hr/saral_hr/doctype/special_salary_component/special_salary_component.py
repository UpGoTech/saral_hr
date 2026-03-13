# Copyright (c) 2026, sj and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class SpecialSalaryComponent(Document):

    def autoname(self):
        # Deterministic name: parent-month  e.g. "Professional Tax-January"
        # Parent deletes all rows via raw SQL before re-inserting,
        # so this name will never collide when saved.
        self.name = f"{self.parent}-{self.month}"