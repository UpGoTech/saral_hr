import frappe


ADDITIONAL_ONLY_SEEDS = [
	{
		"salary_component": "Production Incentive",
		"salary_component_abbr": "PI",
		"type": "Earning",
	},
	{
		"salary_component": "Safety Gadget Penalty",
		"salary_component_abbr": "SGP",
		"type": "Deduction",
	},
	{
		"salary_component": "Arrears",
		"salary_component_abbr": "ARREARS",
		"type": "Earning",
	},
	{
		"salary_component": "Arrears - without PF",
		"salary_component_abbr": "ARR-NOPF",
		"type": "Earning",
	},
]


def execute():
	"""Seed additional-only components and convert free-text child rows to Links."""
	_seed_additional_only_components()
	_convert_child_rows("Additional Salary Component", "Earning")
	_convert_child_rows("Additional Deduction Component", "Deduction")


def _seed_additional_only_components():
	for seed in ADDITIONAL_ONLY_SEEDS:
		name = seed["salary_component"]
		if frappe.db.exists("Salary Component", name):
			frappe.db.set_value("Salary Component", name, "is_additional_only", 1)
			continue
		doc = frappe.get_doc(
			{
				"doctype": "Salary Component",
				"salary_component": name,
				"salary_component_abbr": seed["salary_component_abbr"],
				"type": seed["type"],
				"depends_on_payment_days": 0,
				"is_additional_only": 1,
			}
		)
		doc.insert(ignore_permissions=True)


def _convert_child_rows(child_doctype, expected_type):
	rows = frappe.db.sql(
		f"""
		SELECT name, component_type
		FROM `tab{child_doctype}`
		WHERE IFNULL(component_type, '') != ''
		""",
		as_dict=True,
	)
	for row in rows:
		name = (row.component_type or "").strip()
		if not name:
			continue
		_ensure_additional_only_component(name, expected_type)
		if name != row.component_type:
			frappe.db.set_value(child_doctype, row.name, "component_type", name, update_modified=False)


def _ensure_additional_only_component(name, expected_type):
	if frappe.db.exists("Salary Component", name):
		return

	abbr = "".join(ch for ch in name.upper() if ch.isalnum())[:12] or "ADD"
	doc = frappe.get_doc(
		{
			"doctype": "Salary Component",
			"salary_component": name,
			"salary_component_abbr": abbr,
			"type": expected_type,
			"depends_on_payment_days": 0,
			"is_additional_only": 1,
		}
	)
	doc.insert(ignore_permissions=True)
