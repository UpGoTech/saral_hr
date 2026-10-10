import frappe
from frappe.tests.utils import FrappeTestCase

from saral_hr.patches.repair_employee_naming_series_setter import execute


class TestRepairEmployeeNamingSeriesSetter(FrappeTestCase):
	def test_realigns_stale_timebridge_doc_type(self):
		name = "Employee-naming_series-options"
		frappe.db.sql("DELETE FROM `tabProperty Setter` WHERE name = %s", name)
		frappe.db.sql(
			"""
			INSERT INTO `tabProperty Setter`
				(name, creation, modified, modified_by, owner, docstatus, idx,
				 doctype_or_field, doc_type, field_name, property, property_type, value)
			VALUES
				(%s, NOW(6), NOW(6), 'Administrator', 'Administrator', 0, 0,
				 'DocField', 'TimeBridge Employee', 'naming_series', 'options', 'Text', 'HR-EMP-')
			""",
			name,
		)

		self.assertIsNone(
			frappe.db.get_value(
				"Property Setter",
				{"doc_type": "Employee", "property": "options", "field_name": "naming_series"},
			)
		)

		execute()

		self.assertEqual(
			frappe.db.get_value(
				"Property Setter",
				{"doc_type": "Employee", "property": "options", "field_name": "naming_series"},
			),
			name,
		)
		self.assertEqual(frappe.db.get_value("Property Setter", name, "value"), "HR-EMP-")
