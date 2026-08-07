# Copyright (c) 2026, sj and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from saral_hr.saral_hr.doctype.additional_salary.additional_salary import (
	_assert_additional_only_component,
)


class AdditionalDeductions(Document):
	def validate(self):
		self._validate_components()
		self._recalculate_total()

	def _validate_components(self):
		for row in self.deductions or []:
			_assert_additional_only_component(
				row.component_type, expected_type="Deduction", row_idx=row.idx
			)

	def _recalculate_total(self):
		self.total_deduction_amount = sum(
			float(r.amount or 0) for r in (self.deductions or [])
		)
