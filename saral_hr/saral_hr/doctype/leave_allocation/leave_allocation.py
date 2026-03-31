import frappe
from frappe.model.document import Document


class LeaveAllocation(Document):

    def validate(self):
        self.remaining_leaves = self.new_leaves_allocated - (self.used_leaves or 0)

    def on_submit(self):
        self.remaining_leaves = self.new_leaves_allocated - (self.used_leaves or 0)