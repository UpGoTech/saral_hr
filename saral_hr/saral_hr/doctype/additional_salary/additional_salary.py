# Copyright (c) 2026, sj and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class AdditionalSalary(Document):
	def validate(self):
		self._validate_period_year()
		self._validate_components()
		self._recalculate_total()

	def _validate_period_year(self):
		from saral_hr.utils.period import validate_period_year

		if self.year:
			validate_period_year(self.year)

	def _validate_components(self):
		for row in self.components or []:
			_assert_additional_only_component(
				row.component_type, expected_type="Earning", row_idx=row.idx
			)

	def _recalculate_total(self):
		self.total_amount = sum(float(r.amount or 0) for r in (self.components or []))


def _assert_additional_only_component(name, expected_type, row_idx):
	if not name:
		frappe.throw(_("Row #{0}: Component is required.").format(row_idx))

	meta = frappe.db.get_value(
		"Salary Component",
		name,
		["name", "type", "is_additional_only"],
		as_dict=True,
	)
	if not meta:
		frappe.throw(
			_("Row #{0}: Salary Component {1} does not exist.").format(
				row_idx, frappe.bold(name)
			)
		)
	if meta.type != expected_type:
		frappe.throw(
			_("Row #{0}: {1} must be an {2} component.").format(
				row_idx, frappe.bold(name), expected_type
			)
		)
	if not int(meta.is_additional_only or 0):
		frappe.throw(
			_(
				"Row #{0}: {1} is not an Additional-Only component. "
				"Enable <b>Is Additional Only</b> on the Salary Component, "
				"or pick a registered additional-only component."
			).format(row_idx, frappe.bold(name))
		)
