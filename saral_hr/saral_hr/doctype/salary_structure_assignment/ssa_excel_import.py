# Copyright (c) 2026, sj and contributors
# For license information, please see license.txt

"""Import Salary Structure Assignments from Excel.

Same as the form: pick Salary Structure in the dialog; Excel only needs
employee name (or id), from/to dates, and component amounts.

Company, employee name, designation, branch, department, category and
skill type are fetched from Company Link — not from Excel.

Non-statutory amounts come from Excel columns (exact Salary Component names).

If PF / ESIC / PT / LWF columns are in the sheet, those checkboxes turn ON
and both employee + employer shares are filled by existing
get_statutory_components (Company config). Excel numbers for those columns
are ignored.
"""

from __future__ import annotations

from datetime import datetime

import frappe
from frappe import _
from frappe.utils import flt, getdate
from frappe.utils.xlsxutils import (
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


def _link_for_employee(employee, company=None):
	filters = {"employee": employee}
	if company:
		filters["company"] = company
	return frappe.db.get_value("Company Link", filters, "name")


def _resolve_company_link(employee_id, employee_name, company=None):
	"""Resolve Excel name/id to Company Link, same record the SSA form uses."""
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
		return None, _("employee not found")

	found = _by_docname(label)
	if found:
		return found, None

	params = {"n": label.lower()}
	company_sql = ""
	if company:
		company_sql = " and company = %(c)s"
		params["c"] = company
	matches = [
		r[0]
		for r in frappe.db.sql(
			f"""
			select name from `tabCompany Link`
			where is_active = 1 and lower(trim(full_name)) = %(n)s
			{company_sql}
			""",
			params,
		)
	]
	if len(matches) == 1:
		return matches[0], None
	if len(matches) > 1:
		return None, _("name matches more than one employee")

	emps = [
		r[0]
		for r in frappe.db.sql(
			"select name from `tabEmployee` where lower(trim(employee)) = %s",
			label.lower(),
		)
	]
	if len(emps) == 1:
		link = _link_for_employee(emps[0], company)
		if link:
			return link, None
	if len(emps) > 1:
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


def _find_row(tables, component_name):
	target = _norm_key(component_name)
	for table in tables:
		for row in table:
			if _norm_key(row.get("salary_component")) == target:
				return row
	return None


def statutory_flags_from_columns(component_names, pf_type=None):
	"""Turn SSA checkboxes on when those statutory columns exist in the sheet."""
	flags = {
		"is_esic_applicable": 0,
		"is_pf_applicable": 0,
		"pf_applicable": "",
		"is_pt_applicable": 0,
		"is_lwf_applicable": 0,
	}
	names = {_norm_key(n) for n in (component_names or [])}
	if names & {_norm_key(n) for n in ESIC_COMPONENTS}:
		flags["is_esic_applicable"] = 1
	if names & {_norm_key(n) for n in PF_COMPONENTS}:
		flags["is_pf_applicable"] = 1
		flags["pf_applicable"] = _norm(pf_type)
	if names & {_norm_key(n) for n in PT_COMPONENTS}:
		flags["is_pt_applicable"] = 1
	if names & {_norm_key(n) for n in LWF_COMPONENTS}:
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


def import_from_rows(salary_structure, rows):
	if not salary_structure or not frappe.db.exists("Salary Structure", salary_structure):
		frappe.throw(_("Salary Structure {0} not found").format(salary_structure))
	if not rows:
		return {"created": [], "errors": [_("Excel is empty")], "warnings": []}

	header = rows[0]
	mapping = parse_header_map(header)
	header_components = [col[1] for col in mapping if col and col[0] == "component"]
	structure = frappe.get_doc("Salary Structure", salary_structure)
	created = []
	errors = []
	warnings = []
	unknown_components = []

	for col in mapping:
		if not col or col[0] != "component":
			continue
		name = col[1]
		if not frappe.db.exists("Salary Component", name):
			unknown_components.append(name)
	if unknown_components:
		warnings.append(
			_("Skipped unknown component columns: {0}").format(", ".join(unknown_components))
		)

	structure_keys = set()
	for row in list(structure.earnings or []) + list(structure.deductions or []):
		if row.salary_component:
			structure_keys.add(_norm_key(row.salary_component))
	not_on_structure = []
	for name in header_components:
		if name in unknown_components or _is_statutory(name):
			continue
		if _norm_key(name) not in structure_keys:
			not_on_structure.append(name)
	if not_on_structure:
		warnings.append(
			_("These components are not available on Salary Structure {0}: {1}").format(
				structure.name, ", ".join(not_on_structure)
			)
		)

	for i, raw in enumerate(rows[1:], start=2):
		if not raw or not any(_cell_has_value(c) for c in raw):
			continue
		meta, components = _row_dict(mapping, raw)
		for unknown in unknown_components:
			components.pop(unknown, None)
		for extra in not_on_structure:
			components.pop(extra, None)

		link, resolve_error = _resolve_company_link(
			meta.get("employee"),
			meta.get("employee_name"),
			company=structure.company,
		)
		if not link:
			errors.append(_("Row {0}: {1}").format(i, resolve_error or _("employee not found")))
			continue
		fetched = _fetched_employee_fields(link)
		if structure.company and fetched.get("company") and fetched["company"] != structure.company:
			errors.append(
				_("Row {0}: employee company {1} does not match Salary Structure company {2}").format(
					i, fetched["company"], structure.company
				)
			)
			continue
		try:
			from_date = _parse_date(meta.get("from_date"))
			to_date = _parse_date(meta.get("to_date"))
		except Exception:
			errors.append(_("Row {0}: invalid from/to date").format(i))
			continue
		if not from_date or not to_date:
			errors.append(_("Row {0}: from date and to date are required").format(i))
			continue

		flags = statutory_flags_from_columns(header_components, meta.get("pf_type"))
		earnings, deductions, employer_share = _structure_tables(structure)

		row_failed = False
		for comp_name, amount in components.items():
			if _is_statutory(comp_name):
				continue
			if int(frappe.db.get_value("Salary Component", comp_name, "is_additional_only") or 0):
				errors.append(
					_("Row {0}: {1} is Additional-Only and cannot go on SSA").format(i, comp_name)
				)
				row_failed = True
				break
			row = _find_row([earnings, deductions, employer_share], comp_name)
			if row:
				row["amount"] = amount
				row["base_amount"] = amount
		if row_failed:
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
		except frappe.DuplicateEntryError as e:
			errors.append(_("Row {0}: {1}").format(i, str(e)[:200]))
		except frappe.ValidationError as e:
			errors.append(_("Row {0}: {1}").format(i, str(e)[:200]))

	return {"created": created, "errors": errors, "warnings": warnings}


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
def import_ssa_excel(salary_structure, file_url):
	frappe.has_permission("Salary Structure Assignment", "create", throw=True)
	rows = _read_excel(file_url)
	return import_from_rows(salary_structure, rows)
