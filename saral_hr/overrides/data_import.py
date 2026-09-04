# Copyright (c) 2026, sj and contributors
# For license information, please see license.txt

"""Keep Frappe Data Import unchanged for Employee / Company Link / etc.

SSA Excel imports only *write* a Data Import log row. These overrides stop
Frappe's generic importer from re-parsing that same Excel as SSA fields.
"""

import json

import frappe
from frappe import _
from frappe.core.doctype.data_import.data_import import DataImport as CoreDataImport


def _is_ssa_excel_import(doc):
	try:
		opts = json.loads(doc.template_options or "{}")
	except Exception:
		return False
	return isinstance(opts, dict) and bool(opts.get("ssa_excel_import"))


class DataImport(CoreDataImport):
	def validate(self):
		if _is_ssa_excel_import(self):
			return
		return super().validate()

	def get_preview_from_template(self, import_file=None, google_sheets_url=None):
		if _is_ssa_excel_import(self):
			from saral_hr.saral_hr.doctype.salary_structure_assignment.ssa_excel_import import (
				get_ssa_data_import_preview,
			)

			preview = get_ssa_data_import_preview(self.name)
			return {
				"data": preview.get("rows") or [],
				"columns": preview.get("columns") or [],
				"warnings": [],
				"import_log": [],
			}
		return super().get_preview_from_template(import_file, google_sheets_url)

	def start_import(self):
		if _is_ssa_excel_import(self):
			frappe.throw(
				_(
					"This log is from Salary Structure Assignment Import. Use Import on the SSA list to import again."
				)
			)
		return super().start_import()

	def export_errored_rows(self):
		if _is_ssa_excel_import(self):
			from saral_hr.saral_hr.doctype.salary_structure_assignment.ssa_excel_import import (
				download_ssa_import_errored_rows,
			)

			return download_ssa_import_errored_rows(self.name)
		return super().export_errored_rows()
