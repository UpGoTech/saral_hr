# Copyright (c) 2026, sj and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class LeaveAllocation(Document):
    def validate(self):
        if not self.used_leaves:
            self.used_leaves = 0
        self.remaining_leaves = self.total_allocated - self.used_leaves