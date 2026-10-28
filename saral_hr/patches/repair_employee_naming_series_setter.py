"""Realign Employee naming-series Property Setter before DocType sync.

A TimeBridge rename updated `doc_type` to "TimeBridge Employee" and left the
primary key as `Employee-naming_series-options`. Reloading Employee looks up
the setter by DocType, misses this row, and inserts the same key.
"""

import frappe

SUFFIX = "-naming_series-options"


def execute():
	rows = frappe.db.sql(
		"""
		SELECT name, doc_type, field_name, property
		FROM `tabProperty Setter`
		WHERE name LIKE %s
		""",
		(f"%{SUFFIX}",),
		as_dict=True,
	)
	for row in rows:
		doctype = row.name[: -len(SUFFIX)]
		if not doctype or not frappe.db.exists("DocType", doctype):
			continue
		if (
			row.doc_type == doctype
			and row.field_name == "naming_series"
			and row.property == "options"
		):
			continue
		frappe.db.sql(
			"""
			UPDATE `tabProperty Setter`
			SET doc_type = %s, field_name = 'naming_series', property = 'options'
			WHERE name = %s
			""",
			(doctype, row.name),
		)
