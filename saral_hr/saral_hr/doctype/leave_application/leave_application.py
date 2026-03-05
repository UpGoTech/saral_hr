# Copyright (c) 2026, sj and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import date_diff

class LeaveApplication(Document):
    def validate(self):
        self.total_days = date_diff(self.to_date, self.from_date) + 1