import json

import frappe
from frappe.utils import flt


# Male tax → February amount (Maharashtra standard)
_MALE_TAX_TO_FEB = {
	175.0: 275.0,
	200.0: 300.0,
}


def execute():
	"""Move February override onto slabs; drop obsolete period february_amount column."""
	if not frappe.db.table_exists("Professional Tax Period"):
		return

	rows = frappe.db.sql(
		"""
		SELECT name, slabs
		FROM `tabProfessional Tax Period`
		""",
		as_dict=True,
	)

	for row in rows:
		slabs = []
		try:
			parsed = json.loads(row.slabs or "[]")
			if isinstance(parsed, list):
				slabs = parsed
		except (json.JSONDecodeError, TypeError, ValueError):
			slabs = []

		changed = False
		for slab in slabs:
			if "february_amount" not in slab:
				slab["february_amount"] = None
				changed = True
			if slab.get("gender") != "Male":
				continue
			if slab.get("february_amount") not in (None, ""):
				continue
			tax = flt(slab.get("tax_amount"))
			feb = _MALE_TAX_TO_FEB.get(tax)
			if feb is None:
				continue
			slab["february_amount"] = feb
			changed = True

		if changed:
			frappe.db.set_value(
				"Professional Tax Period",
				row.name,
				"slabs",
				json.dumps(slabs),
				update_modified=False,
			)

	if frappe.db.has_column("Professional Tax Period", "february_amount"):
		frappe.db.sql_ddl(
			"ALTER TABLE `tabProfessional Tax Period` DROP COLUMN `february_amount`"
		)
