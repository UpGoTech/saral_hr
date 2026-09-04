# Copyright (c) 2026, sj and contributors
# For license information, please see license.txt

"""Import Salary Structure Assignments from Excel.

Same as the form: pick Salary Structure in the dialog; Excel only needs
employee Name, from/to dates, and component amounts (no Employee ID).

Company, employee name, designation, branch, department, category and
skill type are fetched from Company Link — not from Excel.

Non-statutory amounts come from Excel columns (exact Salary Component names).

PF / ESIC / PT / LWF cells are flags, not the SSA amount: 0 or blank = off;
1 or any amount = on. Shares still come from get_statutory_components
(Company config). When PF is on, the PF Type column (Limited PF / Full PF)
sets the type.

Worker (category has_subtype): Basic and V-DA come from Skill Rate Revision
for from_date + skill_type; Excel values there are ignored. Daily-wage
columns are per-day × SRR daily_wage_multiplier (default 26). No covering
SRR → that row errors, same as the form.
"""

from __future__ import annotations

from datetime import datetime
import json
import re

import frappe
from frappe import _
from frappe.utils import flt, getdate
from frappe.utils.xlsxutils import (
	make_xlsx,
	read_xls_file_from_attached_file,
	read_xlsx_file_from_attached_file,
)

from saral_hr.saral_hr.doctype.salary_structure_assignment.salary_structure_assignment import (
	SC_EMP_ESIC,
	SC_EMP_LWF,
	SC_EMP_PF,
	SC_EMPR_EDLI,
	SC_EMPR_EPS,
	SC_EMPR_ESIC,
	SC_EMPR_LWF,
	SC_EMPR_PF,
	SC_EMPR_PFADM,
	SC_PT,
	get_daily_wage_multiplier,
	get_srr_for_ssa,
	get_statutory_components,
)

SKIP_CHILD_KEYS = {
	"name",
	"parent",
	"parenttype",
	"parentfield",
	"idx",
	"docstatus",
	"creation",
	"modified",
	"modified_by",
	"owner",
	"doctype",
}

META_ALIASES = {
	"employee": {"employee", "employee id", "company link", "emp id", "emp"},
	"employee_name": {"name", "employee name", "full name"},
	"company": {"company"},
	"from_date": {"from date", "from_date", "start date", "startdate", "period from"},
	"to_date": {"to date", "to_date", "end date", "enddate", "period to"},
	"pf_type": {"pf type", "pf_type", "pf applicable"},
}

ESIC_COMPONENTS = {SC_EMP_ESIC, SC_EMPR_ESIC}
PF_COMPONENTS = {SC_EMP_PF, SC_EMPR_PF, SC_EMPR_EPS, SC_EMPR_EDLI, SC_EMPR_PFADM}
LWF_COMPONENTS = {SC_EMP_LWF, SC_EMPR_LWF}
PT_COMPONENTS = {SC_PT}
ALL_STATUTORY = ESIC_COMPONENTS | PF_COMPONENTS | LWF_COMPONENTS | PT_COMPONENTS


def _norm(value):
	return str(value or "").strip()


def _norm_key(value):
	return " ".join(_norm(value).lower().split())


_STATUTORY_KEYS = {_norm_key(n) for n in ALL_STATUTORY}


def _is_statutory(component_name):
	return _norm_key(component_name) in _STATUTORY_KEYS


def _cell_has_value(value):
	if value is None:
		return False
	if isinstance(value, str) and not value.strip():
		return False
	return True


def parse_header_map(header_row):
	"""Map column index → ('meta', field) or ('component', exact_name)."""
	mapping = []
	seen_meta = {}
	for idx, raw in enumerate(header_row or []):
		key = _norm_key(raw)
		if not key:
			mapping.append(None)
			continue
		meta_field = None
		for field, aliases in META_ALIASES.items():
			if key in aliases:
				meta_field = field
				break
		if meta_field:
			if meta_field in seen_meta:
				mapping.append(None)
				continue
			seen_meta[meta_field] = idx
			mapping.append(("meta", meta_field))
		else:
			mapping.append(("component", _norm(raw)))
	return mapping


def _kind_from_map_value(target):
	if not target or target in ("__skip__", "Don't Import"):
		return None
	if ":" in str(target):
		typ, name = str(target).split(":", 1)
		if typ in ("meta", "component") and name:
			return (typ, name)
	return None


def apply_column_map(mapping, column_map):
	"""Override auto-mapping with user picks from the Map Columns select."""
	mapping = list(mapping or [])
	if not column_map:
		return mapping
	if isinstance(column_map, str):
		try:
			column_map = json.loads(column_map)
		except Exception:
			column_map = {}
	for key, target in (column_map or {}).items():
		try:
			idx = int(key)
		except (TypeError, ValueError):
			continue
		if idx < 0 or idx >= len(mapping):
			continue
		kind = _kind_from_map_value(target)
		if kind and kind[0] == "meta":
			for i, existing in enumerate(mapping):
				if existing and existing[0] == "meta" and existing[1] == kind[1]:
					mapping[i] = None
		mapping[idx] = kind
	return mapping


META_FIELD_LABELS = {
	"employee": "Employee",
	"employee_name": "Employee Name",
	"company": "Company",
	"from_date": "From Date",
	"to_date": "To Date",
	"pf_type": "PF Type",
}


def _excel_col_number(index):
	"""1-based Excel column, matching Frappe Data Import (Sr. No is column 0)."""
	return index + 1


def _name_column_number(mapping):
	for i, kind in enumerate(mapping or []):
		if kind and kind[0] == "meta" and kind[1] in ("employee_name", "employee"):
			return _excel_col_number(i)
	return 1


def _ssa_column_warnings(header, mapping, skip_unmapped, skip_not_on_structure):
	"""Frappe Data Import shape: mapping / cannot-match / skipping."""
	warnings = []
	skip_unmapped = set(skip_unmapped or [])
	skip_not_on_structure = set(skip_not_on_structure or [])
	for i, raw in enumerate(header or []):
		col = _excel_col_number(i)
		kind = mapping[i] if i < len(mapping) else None
		title = _norm(raw)
		if not kind:
			if not title:
				warnings.append({"col": col, "message": _("Skipping Untitled Column")})
			else:
				warnings.append(
					{
						"col": col,
						"message": _("Skipping Duplicate Column {0}").format(frappe.bold(title)),
					}
				)
			continue
		if kind[0] == "meta":
			field_label = META_FIELD_LABELS.get(kind[1], kind[1])
			warnings.append(
				{
					"message": _("Mapping column {0} to field {1}").format(
						frappe.bold(title), frappe.bold(_(field_label))
					)
				}
			)
			continue
		comp = kind[1]
		if comp in skip_unmapped:
			warnings.append(
				{
					"col": col,
					"message": _("Cannot match column {0} with any field").format(frappe.bold(title)),
				}
			)
		elif comp in skip_not_on_structure:
			warnings.append(
				{
					"col": col,
					"message": _("Skipping column {0}").format(frappe.bold(title)),
				}
			)
		else:
			warnings.append(
				{
					"message": _("Mapping column {0} to field {1}").format(
						frappe.bold(title), frappe.bold(comp)
					)
				}
			)
	return warnings


def _classify_ssa_header(salary_structure, header, column_map=None):
	if not salary_structure or not frappe.db.exists("Salary Structure", salary_structure):
		frappe.throw(_("Salary Structure {0} not found").format(salary_structure))
	mapping = apply_column_map(parse_header_map(header), column_map)
	header_components = [col[1] for col in mapping if col and col[0] == "component"]
	structure = frappe.get_doc("Salary Structure", salary_structure)
	unmapped = []
	for name in header_components:
		if not frappe.db.exists("Salary Component", name):
			unmapped.append(name)
	structure_keys = set()
	for row in list(structure.earnings or []) + list(structure.deductions or []):
		if row.salary_component:
			structure_keys.add(_norm_key(row.salary_component))
	not_on_structure = []
	for name in header_components:
		if name in unmapped or _is_statutory(name):
			continue
		if _norm_key(name) not in structure_keys:
			not_on_structure.append(name)
	return {
		"mapping": mapping,
		"unmapped": unmapped,
		"not_on_structure": not_on_structure,
		"structure_keys": structure_keys,
		"company": structure.company,
		"warnings": _ssa_column_warnings(header, mapping, unmapped, not_on_structure),
	}


def _preview_cell(value):
	if value is None:
		return ""
	if isinstance(value, datetime):
		return str(value.date())
	return value


def _preview_columns(header, mapping, structure_keys):
	columns = []
	for i, label in enumerate(header or []):
		kind = mapping[i] if i < len(mapping) else None
		shown = _norm(label)
		if kind and kind[0] == "meta":
			columns.append(
				{
					"label": shown,
					"header_title": shown,
					"mapped": True,
					"maps_to": _(META_FIELD_LABELS.get(kind[1], kind[1])),
					"value": f"meta:{kind[1]}",
					"fieldname": kind[1],
				}
			)
		elif kind and kind[0] == "component":
			exists = bool(frappe.db.exists("Salary Component", kind[1]))
			on_structure = _is_statutory(kind[1]) or _norm_key(kind[1]) in structure_keys
			mapped = exists and on_structure
			columns.append(
				{
					"label": shown,
					"header_title": shown,
					"mapped": mapped,
					"maps_to": kind[1] if mapped else None,
					"value": f"component:{kind[1]}" if mapped else "",
					"fieldname": kind[1] if mapped else "",
				}
			)
		else:
			columns.append(
				{
					"label": shown,
					"header_title": shown,
					"mapped": False,
					"maps_to": None,
					"value": "",
					"fieldname": "",
				}
			)
	return columns


def _missing_employee_warning(rows, mapping, company):
	missing = []
	cache = {}
	for raw in (rows or [])[1:]:
		if not raw or not any(_cell_has_value(c) for c in raw):
			continue
		meta, _components = _row_dict(mapping, raw)
		cache_key = (_norm(meta.get("employee")), _norm(meta.get("employee_name")))
		if cache_key not in cache:
			cache[cache_key] = _resolve_company_link(
				meta.get("employee"),
				meta.get("employee_name"),
				company=_row_company(meta, company),
			)
		link, err = cache[cache_key]
		if link or err != _("employee not found"):
			continue
		label = cache_key[1] or cache_key[0]
		if label and label not in missing:
			missing.append(label)
	if not missing:
		return None
	return {
		"col": _name_column_number(mapping),
		"message": _("The following values do not exist for {0}: {1}").format(
			_("Employee"), ", ".join(missing)
		),
	}


def build_ssa_excel_preview(salary_structure, rows, max_rows=10):
	"""Mapping + sample rows for the Import dialog and Data Import log. Does not insert."""
	header = rows[0] if rows else []
	classified = _classify_ssa_header(salary_structure, header)
	warnings = list(classified["warnings"])
	missing = _missing_employee_warning(rows, classified["mapping"], classified["company"])
	if missing:
		warnings.append(missing)
	body = []
	for raw in (rows[1:max_rows + 1] if rows else []):
		body.append([_preview_cell(c) for c in (raw or [])])
	return {
		"columns": _preview_columns(header, classified["mapping"], classified["structure_keys"]),
		"rows": body,
		"warnings": warnings,
		"salary_structure": salary_structure,
		"fields": get_ssa_import_fields(salary_structure),
	}


def _parse_date(value):
	if not value:
		return None
	if isinstance(value, datetime):
		return getdate(value.date())
	return getdate(value)


def _excel_amount(value):
	if not _cell_has_value(value):
		return None
	return flt(value, 2)


def _row_company(meta, structure_company):
	return _norm((meta or {}).get("company")) or structure_company


def _validate_row_company(meta, structure_company):
	excel_company = _norm((meta or {}).get("company"))
	if not excel_company:
		return structure_company, None
	if not frappe.db.exists("Company", excel_company):
		return None, _("company {0} not found").format(excel_company)
	if structure_company and excel_company != structure_company:
		return None, _("Excel company {0} does not match Salary Structure company {1}").format(
			excel_company, structure_company
		)
	return excel_company, None


def _link_for_employee(employee, company=None):
	filters = {"employee": employee}
	if company:
		filters["company"] = company
	return frappe.db.get_value("Company Link", filters, "name")


def _matches_by_name(label, company=None):
	"""Match Excel name to Company Link. Extra spaces and case are ignored."""
	key = _norm_key(label)
	if not key:
		return []
	filters = {"is_active": 1}
	if company:
		filters["company"] = company
	candidates = frappe.db.get_all(
		"Company Link",
		filters=filters,
		fields=["name", "full_name", "employee"],
	)
	emp_ids = [c.employee for c in candidates if c.employee]
	emp_full = {}
	if emp_ids:
		for row in frappe.db.get_all(
			"Employee",
			filters={"name": ["in", emp_ids]},
			fields=["name", "employee"],
		):
			emp_full[row.name] = row.employee
	matched = []
	for c in candidates:
		if _norm_key(c.full_name) == key:
			matched.append(c.name)
		elif _norm_key(emp_full.get(c.employee)) == key:
			matched.append(c.name)
	return list(dict.fromkeys(matched))


def _resolve_company_link(employee_id, employee_name, company=None):
	"""Resolve Excel Name (ID optional) to Company Link used on the SSA form."""
	eid = _norm(employee_id)
	ename = _norm(employee_name)

	def _by_docname(value):
		if not value:
			return None
		if frappe.db.exists("Company Link", value):
			if company and frappe.db.get_value("Company Link", value, "company") != company:
				return None
			return value
		if frappe.db.exists("Employee", value):
			return _link_for_employee(value, company)
		return None

	found = _by_docname(eid)
	if found:
		return found, None

	label = ename or eid
	if not label:
		return None, _("Name is required")

	found = _by_docname(label)
	if found:
		return found, None

	matches = _matches_by_name(label, company)
	if len(matches) == 1:
		return matches[0], None
	if len(matches) > 1:
		return None, _("name matches more than one employee")
	return None, _("employee not found")


def _fetched_employee_fields(link):
	details = frappe.db.get_value(
		"Company Link",
		link,
		[
			"full_name",
			"company",
			"designation",
			"branch",
			"department",
			"category",
			"skill_type",
		],
		as_dict=True,
	) or {}
	return {
		"employee_name": details.get("full_name") or "",
		"company": details.get("company"),
		"designation": details.get("designation"),
		"branch": details.get("branch"),
		"department": details.get("department"),
		"category": details.get("category"),
		"skill_type": details.get("skill_type"),
	}


def _copy_child(row):
	data = row.as_dict()
	out = {}
	for key, val in data.items():
		if key in SKIP_CHILD_KEYS:
			continue
		out[key] = val
	out["amount"] = 0
	out["base_amount"] = 0
	return out


def _structure_tables(structure):
	"""Copy structure rows the same way the SSA form load_salary_structure does."""
	earnings = [
		_copy_child(r)
		for r in (structure.earnings or [])
		if not _is_statutory(r.salary_component)
	]
	deductions = []
	employer_share = []
	for row in structure.deductions or []:
		if _is_statutory(row.salary_component):
			continue
		copied = _copy_child(row)
		if int(copied.get("employer_contribution") or 0):
			employer_share.append(copied)
		else:
			deductions.append(copied)
	return earnings, deductions, employer_share


STATUTORY_FLAG_COLUMNS = (SC_EMP_PF, SC_EMP_ESIC, SC_PT, SC_EMP_LWF)


def _ssa_import_columns(salary_structure):
	"""SSA meta + this structure's earnings/deductions + statutory flag columns.

	PF / ESIC / PT / LWF live on the SSA form as checkboxes, not as Salary
	Structure child rows, so those headers are always on the template.
	"""
	if not salary_structure or not frappe.db.exists("Salary Structure", salary_structure):
		frappe.throw(_("Salary Structure {0} not found").format(salary_structure))
	structure = frappe.get_doc("Salary Structure", salary_structure)
	columns = [
		{
			"header": "Employee Name",
			"value": "meta:employee_name",
			"label": _("Employee Name"),
			"fieldname": "employee_name",
		},
		{
			"header": "Company",
			"value": "meta:company",
			"label": _("Company"),
			"fieldname": "company",
		},
		{
			"header": "From Date",
			"value": "meta:from_date",
			"label": _("From Date"),
			"fieldname": "from_date",
		},
		{
			"header": "To Date",
			"value": "meta:to_date",
			"label": _("To Date"),
			"fieldname": "to_date",
		},
	]
	seen = {_norm_key(c["header"]) for c in columns}
	for table in (structure.earnings, structure.deductions):
		for row in table or []:
			name = row.salary_component
			if not name or _is_statutory(name):
				continue
			if int(frappe.db.get_value("Salary Component", name, "is_additional_only") or 0):
				continue
			key = _norm_key(name)
			if key in seen:
				continue
			columns.append(
				{"header": name, "value": f"component:{name}", "label": name, "fieldname": name}
			)
			seen.add(key)
	columns.append(
		{
			"header": "PF Type",
			"value": "meta:pf_type",
			"label": _("PF Type"),
			"fieldname": "pf_type",
		}
	)
	seen.add(_norm_key("PF Type"))
	for flag in STATUTORY_FLAG_COLUMNS:
		key = _norm_key(flag)
		if key in seen:
			continue
		columns.append(
			{"header": flag, "value": f"component:{flag}", "label": flag, "fieldname": flag}
		)
		seen.add(key)
	return columns


def get_ssa_import_template_headers(salary_structure):
	"""Headers that parse_header_map already understands for this structure."""
	return [col["header"] for col in _ssa_import_columns(salary_structure)]


def get_ssa_import_fields(salary_structure):
	"""Map Columns left side: only SSA fields for this Salary Structure."""
	return [
		{
			"value": col["value"],
			"label": col["label"],
			"fieldname": col["fieldname"],
			"header": col["header"],
		}
		for col in _ssa_import_columns(salary_structure)
	]


def _find_row(tables, component_name):
	target = _norm_key(component_name)
	for table in tables:
		for row in table:
			if _norm_key(row.get("salary_component")) == target:
				return row
	return None


def _flag_yes(value):
	"""0 / no / blank = off. 1 / yes or any other amount = on."""
	if value is None:
		return False
	if isinstance(value, str):
		key = _norm_key(value)
		if key in {"yes", "y", "true", "on"}:
			return True
		if key in {"no", "n", "false", "off"}:
			return False
	return bool(flt(value))


def _norm_pf_type(value):
	key = _norm_key(value)
	if key in {"limited pf", "limited"}:
		return "Limited PF"
	if key in {"full pf", "full"}:
		return "Full PF"
	return _norm(value)


def _group_flag_on(components, group_names):
	keys = {_norm_key(n) for n in group_names}
	for name, val in (components or {}).items():
		if _norm_key(name) in keys and _flag_yes(val):
			return True
	return False


def _row_is_basic(row):
	comp = _norm_key(row.get("salary_component"))
	abbr = _norm_key(row.get("abbr"))
	return "basic" in comp or abbr == "basic"


def _row_is_vda(row):
	comp = _norm_key(row.get("salary_component"))
	abbr = _norm_key(row.get("abbr"))
	return "dearness" in comp or abbr in {"v-da", "vda"}


def _row_is_daily_wage(row):
	if int(row.get("daily_wage_component") or 0):
		return True
	name = row.get("salary_component")
	if not name:
		return False
	return int(frappe.db.get_value("Salary Component", name, "daily_wage_component") or 0)


def apply_srr_and_daily_wage(earnings, deductions, employer_share, srr, multiplier):
	"""Form path: SRR fills Basic/V-DA; daily-wage Excel cells are per-day × multiplier."""
	if srr:
		vbasic = flt(srr.get("vbasic"), 2)
		vda = flt(srr.get("vda"), 2)
		for row in earnings:
			if _row_is_basic(row):
				row["amount"] = vbasic
				row["base_amount"] = vbasic
			if _row_is_vda(row):
				row["amount"] = vda
				row["base_amount"] = vda
	mult = flt(multiplier) or 26
	for table in (earnings, deductions, employer_share):
		for row in table:
			if not _row_is_daily_wage(row):
				continue
			per_day = flt(row.get("amount"))
			monthly = flt(per_day * mult, 2)
			row["per_day_rate"] = per_day
			row["amount"] = monthly
			row["base_amount"] = monthly


def _apply_worker_rates(earnings, deductions, employer_share, fetched, from_date):
	"""Staff: no-op. Worker: SRR + daily wage, or an error string."""
	category = fetched.get("category")
	if not category or not int(frappe.db.get_value("Category", category, "has_subtype") or 0):
		return None
	skill_type = fetched.get("skill_type")
	if not skill_type:
		return _("skill type is required for category {0}").format(category)
	srr = get_srr_for_ssa(from_date, skill_type)
	if not srr:
		return _(
			"Skill Rate Revision Not Found covering {0} for {1} ({2}, {3})"
		).format(from_date, fetched.get("employee_name") or "", category, skill_type)
	dw = get_daily_wage_multiplier(from_date, skill_type) or {}
	apply_srr_and_daily_wage(
		earnings, deductions, employer_share, srr, dw.get("multiplier") or 26
	)
	return None


def statutory_flags_from_row(components, pf_type=None):
	"""Connect PF/ESIC/PT/LWF on-off (1, 0, or amount) with PF Type when PF is on."""
	flags = {
		"is_esic_applicable": 0,
		"is_pf_applicable": 0,
		"pf_applicable": "",
		"is_pt_applicable": 0,
		"is_lwf_applicable": 0,
	}
	if _group_flag_on(components, ESIC_COMPONENTS):
		flags["is_esic_applicable"] = 1
	if _group_flag_on(components, PF_COMPONENTS):
		flags["is_pf_applicable"] = 1
		flags["pf_applicable"] = _norm_pf_type(pf_type)
	if _group_flag_on(components, PT_COMPONENTS):
		flags["is_pt_applicable"] = 1
	if _group_flag_on(components, LWF_COMPONENTS):
		flags["is_lwf_applicable"] = 1
	return flags


def _apply_calculated_statutory(earnings, deductions, employer_share, flags, company, from_date, employee):
	"""Fill PF/ESIC/PT/LWF via existing Company calculation. Excel amounts are not used."""
	if not any(
		flags.get(k)
		for k in (
			"is_esic_applicable",
			"is_pf_applicable",
			"is_pt_applicable",
			"is_lwf_applicable",
		)
	):
		return earnings, deductions, employer_share

	earnings_map = {r.get("salary_component"): flt(r.get("amount")) for r in earnings}
	gross = sum(flt(r.get("amount")) for r in earnings)
	stat = get_statutory_components(
		company=company,
		gross_salary=gross,
		from_date=from_date,
		is_esic_applicable=flags.get("is_esic_applicable") or 0,
		is_pf_applicable=flags.get("is_pf_applicable") or 0,
		pf_type=flags.get("pf_applicable") or None,
		is_pt_applicable=flags.get("is_pt_applicable") or 0,
		is_lwf_applicable=flags.get("is_lwf_applicable") or 0,
		earnings_map=earnings_map,
		employee=employee,
	)
	for d in stat.get("deductions") or []:
		row = dict(d)
		row["base_amount"] = flt(d.get("amount"), 2)
		deductions.append(row)
	for d in stat.get("employer_share") or []:
		row = dict(d)
		row["base_amount"] = flt(d.get("amount"), 2)
		employer_share.append(row)
	return earnings, deductions, employer_share


def _apply_percent_of_total_earning(earnings, deductions):
	gross = sum(flt(r.get("amount")) for r in earnings)
	for row in deductions:
		if not int(row.get("percent_on_total_earning") or 0):
			continue
		pct = flt(row.get("percent_of_total_earning"))
		amount = flt(max(gross, 0) * pct / 100, 2)
		row["amount"] = amount
		row["base_amount"] = amount


def _sum_basic_da(earnings):
	basic = 0
	da = 0
	for r in earnings:
		amt = flt(r.get("amount"))
		comp = _norm_key(r.get("salary_component"))
		abbr = _norm_key(r.get("abbr"))
		if "basic" in comp or abbr == "basic":
			basic += amt
		if (
			"dearness" in comp
			or comp == "da"
			or abbr == "da"
			or abbr.startswith("da-")
			or abbr.startswith("da ")
		):
			da += amt
	return flt(basic + da, 2)


def _apply_totals(ssa):
	gross = sum(flt(r.amount) for r in (ssa.earnings or []))
	emp_ded = sum(flt(r.amount) for r in (ssa.deductions or []))
	empr = sum(flt(r.amount) for r in (ssa.employer_share or []))
	empr_ctc = sum(
		flt(r.amount) for r in (ssa.employer_share or []) if not int(r.exclude_from_ctc or 0)
	)
	ssa.gross_salary = flt(gross, 2)
	ssa.total_deductions = flt(emp_ded, 2)
	ssa.total_employer_contribution = flt(empr, 2)
	ssa.net_salary = flt(gross - emp_ded, 2)
	ssa.monthly_ctc = flt(gross + empr_ctc, 2)
	ssa.annual_ctc = flt((gross + empr_ctc) * 12, 2)
	ssa.total_basic_da = _sum_basic_da(ssa.earnings or [])


def _row_dict(mapping, row):
	meta = {}
	components = {}
	for idx, kind in enumerate(mapping):
		if not kind:
			continue
		value = row[idx] if idx < len(row) else None
		typ, name = kind
		if typ == "meta":
			meta[name] = value
		else:
			amt = _excel_amount(value)
			if amt is not None:
				components[name] = amt
	return meta, components


def import_from_rows(salary_structure, rows, column_map=None):
	if not salary_structure or not frappe.db.exists("Salary Structure", salary_structure):
		frappe.throw(_("Salary Structure {0} not found").format(salary_structure))
	if not rows:
		return {
			"created": [],
			"created_rows": [],
			"errors": [_("Excel is empty")],
			"warnings": [],
			"import_warnings": [{"message": _("Excel is empty")}],
			"failed_logs": [],
		}

	header = rows[0]
	mapping = apply_column_map(parse_header_map(header), column_map)
	header_components = [col[1] for col in mapping if col and col[0] == "component"]
	structure = frappe.get_doc("Salary Structure", salary_structure)
	created = []
	created_rows = []
	errors = []
	warnings = []
	failed_logs = []
	missing_employees = []
	resolve_cache = {}

	unmapped_components = []
	for name in header_components:
		if not frappe.db.exists("Salary Component", name):
			unmapped_components.append(name)

	structure_keys = set()
	for row in list(structure.earnings or []) + list(structure.deductions or []):
		if row.salary_component:
			structure_keys.add(_norm_key(row.salary_component))
	not_on_structure = []
	for name in header_components:
		if name in unmapped_components or _is_statutory(name):
			continue
		if _norm_key(name) not in structure_keys:
			not_on_structure.append(name)
	if not_on_structure:
		warnings.append(
			_("These components are not available on Salary Structure {0}: {1}").format(
				structure.name, ", ".join(not_on_structure)
			)
		)
	if unmapped_components:
		warnings.append(
			_("Cannot match column {0} with any field").format(", ".join(unmapped_components))
		)

	import_warnings = _ssa_column_warnings(
		header, mapping, unmapped_components, not_on_structure
	)
	skip_components = set(unmapped_components) | set(not_on_structure)
	name_col = _name_column_number(mapping)

	for i, raw in enumerate(rows[1:], start=2):
		if not raw or not any(_cell_has_value(c) for c in raw):
			continue
		meta, components = _row_dict(mapping, raw)
		for extra in skip_components:
			components.pop(extra, None)

		cache_key = (
			_norm(meta.get("employee")),
			_norm(meta.get("employee_name")),
			_norm(meta.get("company")),
		)
		if cache_key not in resolve_cache:
			row_company, company_error = _validate_row_company(meta, structure.company)
			if company_error:
				resolve_cache[cache_key] = (None, company_error)
			else:
				resolve_cache[cache_key] = _resolve_company_link(
					meta.get("employee"),
					meta.get("employee_name"),
					company=row_company,
				)
		link, resolve_error = resolve_cache[cache_key]
		if not link:
			label = _norm(meta.get("employee_name")) or _norm(meta.get("employee"))
			msg = resolve_error or _("employee not found")
			errors.append(_("Row {0}: {1}").format(i, msg))
			if msg == _("employee not found") and label:
				if label not in missing_employees:
					missing_employees.append(label)
				failed_logs.append(
					{
						"row": i,
						"messages": [
							{
								"message": _("Value {0} missing for {1}").format(
									frappe.bold(label), frappe.bold(_("Employee"))
								)
							}
						],
						"exception": _("Value {0} missing for {1}").format(label, _("Employee")),
					}
				)
			else:
				failed_logs.append(
					{
						"row": i,
						"messages": [{"message": msg}],
						"exception": msg,
					}
				)
			continue
		fetched = _fetched_employee_fields(link)
		if structure.company and fetched.get("company") and fetched["company"] != structure.company:
			msg = _("employee company {0} does not match Salary Structure company {1}").format(
				fetched["company"], structure.company
			)
			errors.append(_("Row {0}: {1}").format(i, msg))
			failed_logs.append({"row": i, "messages": [{"message": msg}], "exception": msg})
			continue
		try:
			from_date = _parse_date(meta.get("from_date"))
			to_date = _parse_date(meta.get("to_date"))
		except Exception:
			msg = _("invalid from/to date")
			errors.append(_("Row {0}: {1}").format(i, msg))
			failed_logs.append({"row": i, "messages": [{"message": msg}], "exception": msg})
			continue
		if not from_date or not to_date:
			msg = _("from date and to date are required")
			errors.append(_("Row {0}: {1}").format(i, msg))
			failed_logs.append({"row": i, "messages": [{"message": msg}], "exception": msg})
			continue

		flags = statutory_flags_from_row(components, meta.get("pf_type"))
		earnings, deductions, employer_share = _structure_tables(structure)

		row_failed = False
		for comp_name, amount in components.items():
			if _is_statutory(comp_name):
				continue
			if int(frappe.db.get_value("Salary Component", comp_name, "is_additional_only") or 0):
				msg = _("{0} is Additional-Only and cannot go on SSA").format(comp_name)
				errors.append(_("Row {0}: {1}").format(i, msg))
				failed_logs.append({"row": i, "messages": [{"message": msg}], "exception": msg})
				row_failed = True
				break
			row = _find_row([earnings, deductions, employer_share], comp_name)
			if row:
				row["amount"] = amount
				row["base_amount"] = amount
		if row_failed:
			continue

		worker_error = _apply_worker_rates(
			earnings, deductions, employer_share, fetched, from_date
		)
		if worker_error:
			errors.append(_("Row {0}: {1}").format(i, worker_error))
			failed_logs.append(
				{"row": i, "messages": [{"message": worker_error}], "exception": worker_error}
			)
			continue

		_apply_percent_of_total_earning(earnings, deductions)

		company = fetched.get("company")
		earnings, deductions, employer_share = _apply_calculated_statutory(
			earnings,
			deductions,
			employer_share,
			flags,
			company,
			from_date,
			link,
		)

		ssa = frappe.new_doc("Salary Structure Assignment")
		ssa.employee = link
		ssa.salary_structure = salary_structure
		ssa.from_date = from_date
		ssa.to_date = to_date
		ssa.currency = structure.currency or "INR"
		ssa.update(fetched)
		ssa.update(flags)
		for r in earnings:
			ssa.append("earnings", r)
		for r in deductions:
			ssa.append("deductions", r)
		for r in employer_share:
			ssa.append("employer_share", r)
		_apply_totals(ssa)
		try:
			ssa.insert()
			created.append(ssa.name)
			created_rows.append(i)
		except frappe.DuplicateEntryError as e:
			msg = str(e)[:200]
			errors.append(_("Row {0}: {1}").format(i, msg))
			failed_logs.append({"row": i, "messages": [{"message": msg}], "exception": msg})
		except frappe.ValidationError as e:
			msg = str(e)[:200]
			errors.append(_("Row {0}: {1}").format(i, msg))
			failed_logs.append({"row": i, "messages": [{"message": msg}], "exception": msg})

	if missing_employees:
		import_warnings.append(
			{
				"col": name_col,
				"message": _("The following values do not exist for {0}: {1}").format(
					_("Employee"), ", ".join(missing_employees)
				),
			}
		)

	return {
		"created": created,
		"created_rows": created_rows,
		"errors": errors,
		"warnings": warnings,
		"import_warnings": import_warnings,
		"failed_logs": failed_logs,
	}


def _row_number_from_error(message):
	match = re.match(r"Row\s+(\d+)\s*:", str(message or ""), flags=re.I)
	return int(match.group(1)) if match else None


def _ssa_import_status(created, errors):
	if created and errors:
		return "Partial Success"
	if created:
		return "Success"
	return "Error"


def is_ssa_excel_import_doc(doc):
	raw = getattr(doc, "template_options", None) or "{}"
	try:
		opts = json.loads(raw)
	except Exception:
		return False
	return isinstance(opts, dict) and bool(opts.get("ssa_excel_import"))


def record_ssa_import_on_data_import(file_url, salary_structure, result):
	"""Write a Data Import list record. Does not change the Data Import DocType."""
	from frappe.core.doctype.data_import.importer import create_import_log

	created = result.get("created") or []
	created_rows = result.get("created_rows") or []
	errors = result.get("errors") or []
	failed_logs = result.get("failed_logs") or []
	import_warnings = result.get("import_warnings")

	di = frappe.new_doc("Data Import")
	di.reference_doctype = "Salary Structure Assignment"
	di.import_type = "Insert New Records"
	di.mute_emails = 1
	di.submit_after_import = 0
	di.import_file = file_url
	di.template_options = json.dumps(
		{"ssa_excel_import": 1, "salary_structure": salary_structure}
	)
	di.flags.ignore_validate = True
	di.insert(ignore_permissions=True, ignore_mandatory=True)

	if import_warnings is None:
		import_warnings = []
		for warning in result.get("warnings") or []:
			import_warnings.append({"message": warning})
		for err in errors:
			row = _row_number_from_error(err)
			item = {"message": err}
			if row:
				item["row"] = row
			import_warnings.append(item)
	di.db_set("template_warnings", json.dumps(import_warnings), update_modified=False)

	log_index = 0
	for idx, name in enumerate(created):
		log_index += 1
		row = created_rows[idx] if idx < len(created_rows) else None
		create_import_log(
			di.name,
			log_index,
			{
				"success": 1,
				"docname": name,
				"row_indexes": [row] if row else [],
				"messages": [],
				"exception": None,
			},
		)
	if failed_logs:
		for fail in failed_logs:
			log_index += 1
			row = fail.get("row")
			create_import_log(
				di.name,
				log_index,
				{
					"success": 0,
					"docname": None,
					"row_indexes": [row] if row else [log_index],
					"messages": fail.get("messages") or [{"message": fail.get("exception")}],
					"exception": fail.get("exception"),
				},
			)
	else:
		for err in errors:
			log_index += 1
			row = _row_number_from_error(err)
			create_import_log(
				di.name,
				log_index,
				{
					"success": 0,
					"docname": None,
					"row_indexes": [row] if row else [log_index],
					"messages": [{"message": err}],
					"exception": err,
				},
			)

	di.db_set("payload_count", len(created) + len(failed_logs or errors), update_modified=False)
	di.db_set("status", _ssa_import_status(created, errors), update_modified=False)
	return di.name


def _read_excel(file_url):
	if not file_url:
		frappe.throw(_("Please attach an Excel file"))
	lower = file_url.lower()
	if lower.endswith(".xls"):
		file_doc = frappe.get_doc("File", {"file_url": file_url})
		with open(file_doc.get_full_path(), "rb") as fh:
			return read_xls_file_from_attached_file(fh.read())
	return read_xlsx_file_from_attached_file(file_url=file_url)


@frappe.whitelist()
def import_ssa_excel(salary_structure, file_url, column_map=None):
	frappe.has_permission("Salary Structure Assignment", "create", throw=True)
	rows = _read_excel(file_url)
	result = import_from_rows(salary_structure, rows, column_map=column_map)
	try:
		result["data_import"] = record_ssa_import_on_data_import(
			file_url, salary_structure, result
		)
	except Exception:
		frappe.log_error(title="SSA import Data Import log", message=frappe.get_traceback())
		result["data_import"] = None
		result.setdefault("warnings", []).append(
			_("Could not write the Data Import log. Check Error Log.")
		)
	return result


@frappe.whitelist()
def download_ssa_import_template(salary_structure: str):
	"""Excel template for the SSA Import button. Does not change Data Import."""
	frappe.has_permission("Salary Structure Assignment", "create", throw=True)
	headers = get_ssa_import_template_headers(salary_structure)
	xlsx_file = make_xlsx([headers], "SSA Import")
	safe = "".join(ch if ch.isalnum() or ch in "-_ " else "_" for ch in salary_structure)[:40]
	frappe.response["filename"] = f"SSA_Import_{safe.strip() or 'Template'}.xlsx"
	frappe.response["filecontent"] = xlsx_file.getvalue()
	frappe.response["type"] = "binary"


@frappe.whitelist()
def preview_ssa_excel(salary_structure, file_url):
	"""Column mapping for the SSA Import dialog. Does not import."""
	frappe.has_permission("Salary Structure Assignment", "create", throw=True)
	if not salary_structure:
		frappe.throw(_("Select Salary Structure first."))
	rows = _read_excel(file_url)
	return build_ssa_excel_preview(salary_structure, rows)


def _ssa_template_options(data_import):
	raw = frappe.db.get_value("Data Import", data_import, "template_options") or "{}"
	try:
		opts = json.loads(raw)
	except Exception:
		opts = {}
	return opts if isinstance(opts, dict) else {}


@frappe.whitelist()
def get_ssa_data_import_preview(data_import: str):
	frappe.has_permission("Data Import", "read", throw=True)
	opts = _ssa_template_options(data_import)
	if not opts.get("ssa_excel_import"):
		frappe.throw(_("Not an SSA Excel import log"))
	file_url = frappe.db.get_value("Data Import", data_import, "import_file")
	salary_structure = opts.get("salary_structure")
	rows = _read_excel(file_url) if file_url else []
	if not salary_structure:
		return {"columns": [], "rows": [], "warnings": [], "salary_structure": None}
	return build_ssa_excel_preview(salary_structure, rows)


@frappe.whitelist()
def download_ssa_import_errored_rows(data_import: str):
	frappe.has_permission("Data Import", "read", throw=True)
	opts = _ssa_template_options(data_import)
	if not opts.get("ssa_excel_import"):
		frappe.throw(_("Not an SSA Excel import log"))
	file_url = frappe.db.get_value("Data Import", data_import, "import_file")
	rows = _read_excel(file_url) if file_url else []
	if not rows:
		frappe.throw(_("Import file is empty"))
	failed = set()
	for log in frappe.get_all(
		"Data Import Log",
		filters={"data_import": data_import, "success": 0},
		fields=["row_indexes"],
	):
		try:
			failed.update(json.loads(log.row_indexes or "[]"))
		except Exception:
			pass
	out = [rows[0]]
	for i, row in enumerate(rows[1:], start=2):
		if i in failed:
			out.append(row)
	if len(out) == 1:
		frappe.throw(_("No errored rows"))
	xlsx_file = make_xlsx(out, "Errored Rows")
	frappe.response["filename"] = "SSA_Import_Errored_Rows.xlsx"
	frappe.response["filecontent"] = xlsx_file.getvalue()
	frappe.response["type"] = "binary"
