# Copyright (c) 2026, sj and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Category(Document):

    def on_update(self):
        self.sync_variable_pay_to_company_links()

    def sync_variable_pay_to_company_links(self):
        """
        Whenever requires_variable_pay is changed on Category,
        push the updated value to all Company Link records
        that belong to this category.
        """
        frappe.db.set_value(
            "Company Link",
            {"category": self.category},
            "requires_variable_pay",
            self.requires_variable_pay
        )