# Copyright (c) 2026, sj and Contributors
# See license.txt

"""Employee Salary History — one row per month for a single employee."""

from __future__ import annotations

import io
import json
import re

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate
from frappe.utils.pdf import get_pdf
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.properties import PageSetupProperties


def execute(filters=None):
	filters = _normalize_filters(filters)
	if not filters.company or not filters.employee:
		return _columns([], [], []), []

	from_date, to_date = _period_dates(filters)
	if _is_period(filters) and (not from_date or not to_date):
		return _columns([], [], []), []

	slips = _load_slips(filters.company, filters.employee, from_date, to_date)
	if not slips:
		return _columns([], [], []), []

	ssa_by_slip = {s.name: _resolve_ssa(s.employee, s.start_date, s.end_date) for s in slips}
	actual_union = _actual_union(ssa_by_slip)
	earn_maps, ded_maps, add_earn_maps, add_ded_maps, labels = _slip_component_maps([s.name for s in slips])
	add_earn_names = _map_names(add_earn_maps)
	earn_union = _earn_union(actual_union, earn_maps, labels, add_earn_names)
	ded_union = _ded_union(ded_maps, labels)
	add_earn_union = _extra_union(add_earn_maps, labels, use_name=True)
	add_ded_union = _extra_union(add_ded_maps, labels, use_name=True)

	rows = []
	for slip in slips:
		row = _slip_row(
			slip,
			ssa_by_slip.get(slip.name),
			actual_union,
			earn_union,
			ded_union,
			add_earn_union,
			add_ded_union,
			earn_maps,
			ded_maps,
			add_earn_maps,
			add_ded_maps,
		)
		rows.append(row)

	if rows:
		rows.append(_totals_row(rows, actual_union, earn_union, ded_union, add_earn_union, add_ded_union))

	return _columns(actual_union, earn_union, ded_union, add_earn_union, add_ded_union), rows


def _normalize_filters(filters):
	if isinstance(filters, str):
		filters = json.loads(filters or "{}")
	return frappe._dict(filters or {})


def _is_period(filters):
	return (filters.get("show") or "Full") == "Select Period"


def _period_dates(filters):
	if not _is_period(filters):
		return None, None
	if not filters.from_date or not filters.to_date:
		return None, None
	from_date = getdate(filters.from_date)
	to_date = getdate(filters.to_date)
	if from_date > to_date:
		frappe.msgprint(_("From Date cannot be after To Date."))
		return None, None
	return from_date, to_date


def _load_slips(company, employee, from_date=None, to_date=None):
	date_sql = ""
	params = {"company": company, "employee": employee}
	if from_date and to_date:
		date_sql = """
		  AND ss.start_date <= %(to_date)s
		  AND ss.end_date >= %(from_date)s
		"""
		params["from_date"] = str(from_date)
		params["to_date"] = str(to_date)
	return frappe.db.sql(
		f"""
		SELECT
			ss.name, ss.employee, ss.start_date, ss.end_date,
			ss.payment_days, ss.total_earnings, ss.total_deductions, ss.net_salary
		FROM `tabSalary Slip` ss
		WHERE ss.docstatus = 1
		  AND ss.company = %(company)s
		  AND ss.employee = %(employee)s
		  {date_sql}
		ORDER BY ss.start_date ASC
		""",
		params,
		as_dict=True,
	)


def _resolve_ssa(employee, start, end):
	rows = frappe.db.sql(
		"""
		SELECT name
		FROM `tabSalary Structure Assignment`
		WHERE employee = %(employee)s
		  AND docstatus = 1
		  AND from_date <= %(start)s
		  AND (to_date IS NULL OR to_date >= %(end)s)
		ORDER BY from_date DESC
		LIMIT 1
		""",
		{"employee": employee, "start": str(start), "end": str(end)},
		as_dict=True,
	)
	return rows[0].name if rows else None


def _ssa_earnings(ssa_name):
	if not ssa_name:
		return []
	return frappe.db.sql(
		"""
		SELECT salary_component, abbr, amount
		FROM `tabSalary Details`
		WHERE parent = %(parent)s
		  AND parenttype = 'Salary Structure Assignment'
		  AND parentfield = 'earnings'
		  AND IFNULL(amount, 0) != 0
		ORDER BY idx ASC
		""",
		{"parent": ssa_name},
		as_dict=True,
	)


def _slip_component_maps(slip_names):
	earn = {n: {} for n in slip_names}
	ded = {n: {} for n in slip_names}
	add_earn = {n: {} for n in slip_names}
	add_ded = {n: {} for n in slip_names}
	labels = {}
	if not slip_names:
		return earn, ded, add_earn, add_ded, labels

	rows = frappe.db.sql(
		"""
		SELECT sd.parent, sd.parentfield, sd.salary_component, sd.abbr, sd.amount,
		       IFNULL(sc.employer_contribution, 0) AS employer_contribution,
		       IFNULL(sc.is_additional_only, 0) AS is_additional_only
		FROM `tabSalary Details` sd
		LEFT JOIN `tabSalary Component` sc ON sc.name = sd.salary_component
		WHERE sd.parent IN %(parents)s
		  AND sd.parenttype = 'Salary Slip'
		  AND sd.parentfield IN ('earnings', 'deductions')
		ORDER BY sd.idx ASC
		""",
		{"parents": slip_names},
		as_dict=True,
	)
	for row in rows:
		amount = flt(row.amount)
		if not amount:
			continue
		if row.abbr and row.salary_component not in labels:
			labels[row.salary_component] = row.abbr
		additional = int(row.is_additional_only or 0)
		if row.parentfield == "earnings":
			bucket = add_earn if additional else earn
			bucket[row.parent][row.salary_component] = flt(bucket[row.parent].get(row.salary_component)) + amount
		elif row.parentfield == "deductions" and not int(row.employer_contribution or 0):
			bucket = add_ded if additional else ded
			bucket[row.parent][row.salary_component] = flt(bucket[row.parent].get(row.salary_component)) + amount
	return earn, ded, add_earn, add_ded, labels


def _comp(name, abbr=None):
	# Short title under the group heading: Basic, DA, PF, ESIC, PT, RET.
	return {"name": name, "label": _heading(name, abbr), "full_name": _proper_name(name)}


def _heading(name, abbr):
	text = " ".join((abbr or "").split())
	# Professional Tax stores the slab note in Abbr. The column title is PT.
	if (name or "").strip().lower() == "professional tax":
		return "PT"
	if text and len(text) <= 16:
		return text
	return (name or text).strip()


# Codes such as PRODUCTIONIN and Add-Deduct are hard to read. Use the real name.
_DISPLAY_NAMES = {
	"additional saralry": "Additional Salary",
	"additional salary": "Additional Salary",
	"additional deduction": "Additional Deduction",
	"production incentive": "Production Incentive",
}


def _proper_name(name):
	key = " ".join((name or "").split()).lower()
	if key in _DISPLAY_NAMES:
		return _DISPLAY_NAMES[key]
	return " ".join((name or "").split())


def _actual_union(ssa_by_slip):
	comps = []
	seen = set()
	for ssa_name in ssa_by_slip.values():
		for row in _ssa_earnings(ssa_name):
			name = row.salary_component
			if name not in seen:
				seen.add(name)
				comps.append(_comp(name, row.abbr))
	return comps


def _map_names(maps):
	names = set()
	for amounts in maps.values():
		names.update(amounts)
	return names


def _earn_union(actual_union, earn_maps, labels, skip_names=None):
	skip_names = skip_names or set()
	comps = []
	seen = set()
	for comp in actual_union:
		if comp["name"] in skip_names or comp["name"] in seen:
			continue
		seen.add(comp["name"])
		comps.append(dict(comp))
	for amounts in earn_maps.values():
		for name in amounts:
			if name in seen or name in skip_names:
				continue
			seen.add(name)
			comps.append(_comp(name, labels.get(name)))
	return comps


def _ded_union(ded_maps, labels):
	return _extra_union(ded_maps, labels)


def _extra_union(comp_maps, labels, use_name=False):
	comps = []
	seen = set()
	for amounts in comp_maps.values():
		for name in amounts:
			if name not in seen:
				seen.add(name)
				if use_name:
					proper = _proper_name(name)
					comps.append({"name": name, "label": proper, "full_name": proper})
				else:
					comps.append(_comp(name, labels.get(name)))
	return comps


def _month_label(start_date):
	start = getdate(start_date)
	return f"{start.strftime('%b')}-{start.strftime('%y')}"


def _slip_row(
	slip,
	ssa_name,
	actual_union,
	earn_union,
	ded_union,
	add_earn_union,
	add_ded_union,
	earn_maps,
	ded_maps,
	add_earn_maps,
	add_ded_maps,
):
	row = {
		"month_year": _month_label(slip.start_date),
		"salary_slip": slip.name,
		"paid_days": flt(slip.payment_days),
		"total_gross": 0.0,
		"total_earning": 0.0,
		"total_additional_salary": 0.0,
		"total_deductions": 0.0,
		"total_additional_deduction": 0.0,
		"net_payable": flt(slip.net_salary),
		"_is_total": 0,
	}
	ssa_amounts = {r.salary_component: flt(r.amount) for r in _ssa_earnings(ssa_name)}
	gross = 0.0
	for comp in actual_union:
		value = flt(ssa_amounts.get(comp["name"]))
		row[_act_fn(comp["name"])] = value
		gross += value
	row["total_gross"] = flt(gross, 2)

	slip_earn = earn_maps.get(slip.name) or {}
	earn_total = 0.0
	for comp in earn_union:
		value = flt(slip_earn.get(comp["name"]))
		row[_earn_fn(comp["name"])] = value
		earn_total += value
	row["total_earning"] = flt(earn_total, 2)

	add_earn = add_earn_maps.get(slip.name) or {}
	add_earn_total = 0.0
	for comp in add_earn_union:
		value = flt(add_earn.get(comp["name"]))
		row[_add_earn_fn(comp["name"])] = value
		add_earn_total += value
	row["total_additional_salary"] = flt(add_earn_total, 2)

	slip_ded = ded_maps.get(slip.name) or {}
	ded_total = 0.0
	for comp in ded_union:
		value = flt(slip_ded.get(comp["name"]))
		row[_ded_fn(comp["name"])] = value
		ded_total += value
	row["total_deductions"] = flt(ded_total, 2)

	add_ded = add_ded_maps.get(slip.name) or {}
	add_ded_total = 0.0
	for comp in add_ded_union:
		value = flt(add_ded.get(comp["name"]))
		row[_add_ded_fn(comp["name"])] = value
		add_ded_total += value
	row["total_additional_deduction"] = flt(add_ded_total, 2)
	return row


def _totals_row(rows, actual_union, earn_union, ded_union, add_earn_union, add_ded_union):
	total = {
		"month_year": _("Total"),
		"paid_days": flt(sum(flt(r.get("paid_days")) for r in rows), 1),
		"total_gross": flt(sum(flt(r.get("total_gross")) for r in rows), 2),
		"total_earning": flt(sum(flt(r.get("total_earning")) for r in rows), 2),
		"total_additional_salary": flt(sum(flt(r.get("total_additional_salary")) for r in rows), 2),
		"total_deductions": flt(sum(flt(r.get("total_deductions")) for r in rows), 2),
		"total_additional_deduction": flt(sum(flt(r.get("total_additional_deduction")) for r in rows), 2),
		"net_payable": flt(sum(flt(r.get("net_payable")) for r in rows), 2),
		"_is_total": 1,
	}
	for comp in actual_union:
		fn = _act_fn(comp["name"])
		total[fn] = flt(sum(flt(r.get(fn)) for r in rows), 2)
	for comp in earn_union:
		fn = _earn_fn(comp["name"])
		total[fn] = flt(sum(flt(r.get(fn)) for r in rows), 2)
	for comp in ded_union:
		fn = _ded_fn(comp["name"])
		total[fn] = flt(sum(flt(r.get(fn)) for r in rows), 2)
	for comp in add_earn_union:
		fn = _add_earn_fn(comp["name"])
		total[fn] = flt(sum(flt(r.get(fn)) for r in rows), 2)
	for comp in add_ded_union:
		fn = _add_ded_fn(comp["name"])
		total[fn] = flt(sum(flt(r.get(fn)) for r in rows), 2)
	return total


def _slug(comp):
	slug = re.sub(r"[^A-Za-z0-9]+", "_", comp or "").strip("_").lower()
	return slug or "comp"


def _act_fn(comp):
	return f"act_{_slug(comp)}"


def _earn_fn(comp):
	return f"earn_{_slug(comp)}"


def _ded_fn(comp):
	return f"ded_{_slug(comp)}"


def _add_earn_fn(comp):
	return f"add_earn_{_slug(comp)}"


def _add_ded_fn(comp):
	return f"add_ded_{_slug(comp)}"


def _col(label, fieldname, fieldtype="Currency", width=110, group=None, full_name=None):
	column = {
		"label": _(label),
		"fieldname": fieldname,
		"fieldtype": fieldtype,
		"width": width,
	}
	if group:
		column["esh_group"] = group
	if full_name:
		column["esh_full_name"] = full_name
	return column


def _stack_part(comp, fieldname):
	return {
		"fieldname": fieldname,
		"label": comp["label"],
		"full_name": comp.get("full_name"),
	}


def _paired_component_columns(comps, fn_builder, group):
	"""Two components share one column: first on the top line, second under it."""
	columns = []
	index = 0
	while index < len(comps):
		parts = [_stack_part(comps[index], fn_builder(comps[index]["name"]))]
		if index + 1 < len(comps):
			nxt = comps[index + 1]
			parts.append(_stack_part(nxt, fn_builder(nxt["name"])))
			index += 2
		else:
			index += 1
		label = parts[0]["label"] if len(parts) == 1 else f"{parts[0]['label']}\n{parts[1]['label']}"
		col = _col(label, parts[0]["fieldname"], "Data", 110, group)
		col["label"] = label
		col["esh_stack"] = parts
		columns.append(col)
	return columns


def _columns(actual_comps, earn_comps, ded_comps, add_earn_comps=None, add_ded_comps=None):
	add_earn_comps = add_earn_comps or []
	add_ded_comps = add_ded_comps or []
	columns = [_col("", "month_year", "Data", 130, "Months")]
	for comp in actual_comps:
		columns.append(_col(comp["label"], _act_fn(comp["name"]), "Currency", 100, "Actual Earning", comp.get("full_name")))
	columns.append(_col("Total", "total_gross", "Currency", 110, "Actual Earning"))
	columns.append(_col("", "paid_days", "Float", 100, "Paid Days"))
	for comp in earn_comps:
		columns.append(_col(comp["label"], _earn_fn(comp["name"]), "Currency", 100, "Calculated Earning", comp.get("full_name")))
	columns.append(_col("Total", "total_earning", "Currency", 110, "Calculated Earning"))
	for comp in add_earn_comps:
		columns.append(_col(comp["label"], _add_earn_fn(comp["name"]), "Currency", 140, "Additional Salary", comp.get("full_name")))
	if add_earn_comps:
		columns.append(_col("Total", "total_additional_salary", "Currency", 120, "Additional Salary"))
	for comp in ded_comps:
		columns.append(_col(comp["label"], _ded_fn(comp["name"]), "Currency", 100, "Deduction", comp.get("full_name")))
	columns.append(_col("Total", "total_deductions", "Currency", 110, "Deduction"))
	for comp in add_ded_comps:
		columns.append(_col(comp["label"], _add_ded_fn(comp["name"]), "Currency", 150, "Additional Deduction", comp.get("full_name")))
	if add_ded_comps:
		columns.append(_col("Total", "total_additional_deduction", "Currency", 130, "Additional Deduction"))
	columns.append(_col("", "net_payable", "Currency", 130, "Net Payable"))
	slip_col = _col("Salary Slip", "salary_slip", "Data", 0)
	slip_col["hidden"] = 1
	columns.append(slip_col)
	return columns


def _export_part(col):
	return {
		"fieldname": col["fieldname"],
		"label": col.get("label"),
		"full_name": col.get("esh_full_name"),
	}


def _columns_for_export(columns):
	"""PDF and Excel only. Screen keeps one component per column."""
	pair_groups = {"Actual Earning", "Calculated Earning"}
	skip = {"total_gross", "total_earning"}
	out = []
	index = 0
	while index < len(columns):
		col = columns[index]
		if col.get("esh_group") not in pair_groups or col.get("fieldname") in skip:
			out.append(col)
			index += 1
			continue
		group = col.get("esh_group")
		batch = []
		while (
			index < len(columns)
			and columns[index].get("esh_group") == group
			and columns[index].get("fieldname") not in skip
		):
			batch.append(columns[index])
			index += 1
		step = 0
		while step < len(batch):
			parts = [_export_part(batch[step])]
			if step + 1 < len(batch):
				parts.append(_export_part(batch[step + 1]))
				step += 2
			else:
				step += 1
			label = parts[0]["label"] if len(parts) == 1 else f"{parts[0]['label']}\n{parts[1]['label']}"
			out.append(
				{
					"label": label,
					"fieldname": parts[0]["fieldname"],
					"fieldtype": "Data",
					"width": 110,
					"esh_group": group,
					"esh_stack": parts,
				}
			)
	return out


# ─── PDF / Excel (same download path as Monthly Salary Register) ─────────────

ACTUAL_HDR = "#FDEBD0"
EARN_HDR = "#E5F6E5"
ADD_EARN_HDR = "#E7F1FE"
DED_HDR = "#FDE8E8"
ADD_DED_HDR = "#F4E9FE"
PLAIN_HDR = "#F7F7F7"


def _require_filters(filters):
	filters = _normalize_filters(filters)
	if not filters.company or not filters.employee:
		frappe.throw(_("Please select Company and Employee."))
	if _is_period(filters):
		if not filters.from_date or not filters.to_date:
			frappe.throw(_("Please select From Date and To Date."))
		if getdate(filters.from_date) > getdate(filters.to_date):
			frappe.throw(_("From Date cannot be after To Date."))
	return filters


def _export_meta(filters):
	employee_name = (
		frappe.db.get_value("Company Link", filters.employee, "full_name") or filters.employee
	)
	if _is_period(filters):
		start = getdate(filters.from_date).strftime("%d-%b-%Y")
		end = getdate(filters.to_date).strftime("%d-%b-%Y")
		period = f"{start} to {end}"
	else:
		period = _("Full History")
	return {
		"company": filters.company or "",
		"employee_name": employee_name,
		"employee": filters.employee,
		"period": period,
	}


def _group_spans(cols):
	spans = []
	for col in cols:
		name = col.get("esh_group") or ""
		if spans and spans[-1]["name"] == name:
			spans[-1]["cols"].append(col)
		else:
			spans.append({"name": name, "cols": [col]})
	return spans


def _hdr_color(group):
	if group == "Actual Earning":
		return ACTUAL_HDR
	if group == "Calculated Earning":
		return EARN_HDR
	if group == "Additional Salary":
		return ADD_EARN_HDR
	if group == "Deduction":
		return DED_HDR
	if group == "Additional Deduction":
		return ADD_DED_HDR
	return PLAIN_HDR


def _excel_fill(group):
	return PatternFill("solid", fgColor=_hdr_color(group).lstrip("#"))


def _export_width(col):
	"""PDF/Excel widths. The marked groups are tighter than Actual Earning."""
	fn = col.get("fieldname") or ""
	label = str(col.get("label") or "")
	group = col.get("esh_group") or ""
	if col.get("esh_stack"):
		return 52
	if fn == "month_year":
		return 48
	if fn == "paid_days":
		return 22
	if fn == "net_payable":
		return 48
	if group in ("Calculated Earning", "Additional Salary", "Deduction", "Additional Deduction"):
		if fn.startswith("total_"):
			return 52
		return 42
	if fn.startswith("total_"):
		return 54
	if len(label) > 6:
		return 46
	return 42


def _display_value(col, row):
	fn = col["fieldname"]
	val = row.get(fn)
	if val is None or val == "":
		return ""
	if fn == "paid_days":
		n = flt(val)
		if abs(n - round(n)) < 1e-9:
			return str(int(round(n)))
		return f"{n:.1f}"
	if col.get("fieldtype") == "Currency" and isinstance(val, (int, float)):
		return f"{flt(val):,.2f}"
	if col.get("fieldtype") == "Float" and isinstance(val, (int, float)):
		return f"{flt(val):,.2f}"
	return str(val)


def _wrap_heading(text):
	"""Long PDF/Excel headings break onto two lines. Short codes stay on one."""
	text = str(text or "")
	if "\n" in text:
		return text
	words = text.split()
	text = " ".join(words)
	if len(words) < 2 or len(text) < 12:
		return text
	best_at = 1
	best_gap = None
	for index in range(1, len(words)):
		gap = abs(len(" ".join(words[:index])) - len(" ".join(words[index:])))
		if best_gap is None or gap < best_gap:
			best_gap = gap
			best_at = index
	return " ".join(words[:best_at]) + "\n" + " ".join(words[best_at:])


def _heading_html(text):
	if text == "Paid Days":
		return "Paid<br>Days"
	return "<br>".join(frappe.utils.escape_html(line) for line in _wrap_heading(text).split("\n"))


def _header_label_html(col):
	stack = col.get("esh_stack")
	if stack:
		return "<br>".join(frappe.utils.escape_html(part["label"]) for part in stack)
	return _heading_html(col.get("label") or "")


def _cell_html(col, row):
	stack = col.get("esh_stack")
	if not stack:
		return frappe.utils.escape_html(_display_value(col, row))
	lines = []
	for part in stack:
		text = frappe.utils.escape_html(
			_display_value({"fieldname": part["fieldname"], "fieldtype": "Currency"}, row)
		)
		lines.append(f'<div class="ln">{text}</div>')
	return f'<div class="stk">{"".join(lines)}</div>'


def _has_extra_groups(columns):
	return any(
		c.get("esh_group") in ("Additional Salary", "Additional Deduction") for c in columns
	)


@frappe.whitelist()
def print_report(filters):
	filters = _require_filters(filters)
	columns, rows = execute(filters)
	if not rows:
		frappe.throw(_("No salary slips found for this employee."))
	html = _build_html(_columns_for_export(columns), rows, _export_meta(filters))
	return _save_pdf(html, "Employee_Salary_History")


def _build_html(columns, rows, meta):
	columns = [c for c in columns if not c.get("hidden")]
	tight = _has_extra_groups(columns)
	value_px = "9px" if tight else "10px"
	spans = _group_spans(columns)
	multi = any(len(group["cols"]) > 1 for group in spans)
	top = []
	sub = []
	for group in spans:
		color = _hdr_color(group["name"])
		n = len(group["cols"])
		style = (
			f"padding:3px 1px;font-size:10px;background:{color};"
			"vertical-align:middle;text-align:center;"
		)
		if len(group["cols"]) == 1 and group["cols"][0].get("fieldname") == "month_year":
			style += "white-space:nowrap;word-wrap:normal;"
		label = _heading_html(group["name"])
		if n == 1 and multi:
			top.append(f'<th rowspan="2" style="{style}">{label}</th>')
		elif n > 1:
			top.append(f'<th colspan="{n}" style="{style}">{label}</th>')
			for col in group["cols"]:
				sub.append(f'<th style="{style}">{_header_label_html(col)}</th>')
		else:
			top.append(f'<th style="{style}">{label}</th>')

	header = f"<tr>{''.join(top)}</tr>"
	if sub:
		header += f"<tr>{''.join(sub)}</tr>"

	body_rows = []
	data_idx = 0
	for row in rows:
		is_tot = row.get("_is_total")
		if not is_tot:
			data_idx += 1
		tds = ""
		for col in columns:
			fn = col["fieldname"]
			disp = _cell_html(col, row)
			if is_tot:
				bg = "#e8e8e8"
			elif data_idx % 2 == 0:
				bg = "#f5f5f5"
			else:
				bg = "#fff"
			align = "center"
			weight = "bold" if is_tot else "normal"
			row_cls = "tot" if is_tot else "data"
			if fn == "month_year" and not is_tot:
				row_cls += " month"
			tds += (
				f'<td class="{row_cls}" style="text-align:{align};background:{bg};font-weight:{weight};">{disp}</td>'
			)
		body_rows.append(f"<tr>{tds}</tr>")

	widths = [_export_width(c) for c in columns]
	total_width = sum(widths) or 1
	colgroup = "<colgroup>" + "".join(
		f'<col style="width:{100.0 * w / total_width:.2f}%">' for w in widths
	) + "</colgroup>"
	sheet = (
		f'<table class="sheet">{colgroup}<thead>{header}</thead>'
		f'<tbody>{"".join(body_rows)}</tbody></table>'
	)
	company = frappe.utils.escape_html(meta["company"])
	employee = frappe.utils.escape_html(f"{meta['employee_name']} ({meta['employee']})")
	period = frappe.utils.escape_html(str(meta["period"]))
	return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:Arial,sans-serif;font-size:8px;color:#000}}
.hdr{{text-align:center;margin-bottom:6px}}
.hdr .co{{font-size:20px;font-weight:900}}
.hdr .ttl{{font-size:16px;font-weight:700;margin-top:2px}}
.hdr .per{{font-size:14px;margin-top:2px}}
table.sheet{{width:100%;border-collapse:collapse;table-layout:fixed;page-break-inside:auto}}
table.sheet thead{{display:table-header-group}}
table.sheet tr{{page-break-inside:avoid;page-break-after:auto}}
table.sheet th,table.sheet td{{word-wrap:break-word;vertical-align:middle;text-align:center}}
table.sheet th{{border:1px solid #000}}
td.data{{border:1px solid #000;padding:5px 1px;font-size:{value_px};line-height:1.35;vertical-align:middle;text-align:center;white-space:nowrap}}
td.data.month{{white-space:nowrap;word-wrap:normal;overflow:hidden}}
td.tot{{border:1px solid #000;padding:5px 1px;font-size:{value_px};line-height:1.35;vertical-align:middle;text-align:center;white-space:nowrap}}
.stk .ln{{display:block;line-height:1.45;padding:2px 0}}
table.note{{width:auto;margin-top:16px;border-collapse:collapse;table-layout:auto}}
table.note th,table.note td{{border:1px solid #000;background:#fff;color:#000;padding:5px 10px;vertical-align:middle}}
table.note th{{font-size:15px;font-weight:700;text-align:center}}
table.note td.code{{font-size:14px;font-weight:700;text-align:center}}
table.note td.name{{font-size:14px;font-weight:400;text-align:left}}
</style></head><body>
<div class="hdr">
  <div class="co">{company}</div>
  <div class="ttl">Employee Salary History</div>
  <div class="per">{employee}<br>For the Period {period}</div>
</div>
{sheet}
{_legend_html(columns)}
</body></html>"""


def _save_pdf(html, prefix):
	pdf = get_pdf(
		html,
		options={
			"page-size": "A4",
			"orientation": "Landscape",
			"margin-top": "6mm",
			"margin-right": "4mm",
			"margin-bottom": "6mm",
			"margin-left": "4mm",
			"encoding": "UTF-8",
			"no-outline": None,
		},
	)
	ts = frappe.utils.now_datetime().strftime("%Y%m%d_%H%M%S")
	fn = f"{prefix}_{ts}.pdf"
	with open(frappe.utils.get_files_path(fn, is_private=0), "wb") as fh:
		fh.write(pdf)
	doc = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": fn,
			"is_private": 0,
			"file_url": f"/files/{fn}",
		}
	)
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return doc.file_url


@frappe.whitelist()
def excel_report(filters):
	filters = _require_filters(filters)
	columns, rows = execute(filters)
	if not rows:
		frappe.throw(_("No salary slips found for this employee."))
	wb = _build_workbook(_columns_for_export(columns), rows, _export_meta(filters))
	return _save_excel(wb, "Employee_Salary_History")


def _build_workbook(columns, rows, meta):
	columns = [c for c in columns if not c.get("hidden")]
	wb = Workbook()
	ws = wb.active
	ws.title = "Salary History"
	thin = Border(
		left=Side(style="thin", color="000000"),
		right=Side(style="thin", color="000000"),
		top=Side(style="thin", color="000000"),
		bottom=Side(style="thin", color="000000"),
	)
	ws.sheet_format.defaultRowHeight = 24
	n_cols = max(len(columns), 1)
	ws.row_dimensions[1].height = 40
	ws.row_dimensions[2].height = 30
	ws.row_dimensions[3].height = 24
	ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=n_cols)
	title = ws.cell(1, 1, f"{meta['company']} - Employee Salary History")
	title.font = Font(name="Arial", size=24, bold=True, color="000000")
	title.alignment = Alignment(horizontal="center", vertical="center")

	ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=n_cols)
	who = ws.cell(2, 1, f"{meta['employee_name']} ({meta['employee']})")
	who.font = Font(name="Arial", size=18, bold=True, color="000000")
	who.alignment = Alignment(horizontal="center", vertical="center")

	ws.merge_cells(start_row=3, start_column=1, end_row=3, end_column=n_cols)
	period = ws.cell(3, 1, f"For the Period {meta['period']}")
	period.font = Font(name="Arial", size=15)
	period.alignment = Alignment(horizontal="center", vertical="center")

	spans = _group_spans(columns)
	multi = any(len(group["cols"]) > 1 for group in spans)
	group_row = 5
	sub_row = 6 if multi else 5
	data_start = sub_row + 1
	col_idx = 1
	for group in spans:
		n = len(group["cols"])
		fill = _excel_fill(group["name"])
		end_col = col_idx + n - 1
		if n == 1 and multi:
			ws.merge_cells(start_row=group_row, start_column=col_idx, end_row=sub_row, end_column=col_idx)
		elif n > 1:
			ws.merge_cells(start_row=group_row, start_column=col_idx, end_row=group_row, end_column=end_col)
		header_name = "Paid\nDays" if group["name"] == "Paid Days" else _wrap_heading(group["name"])
		cell = ws.cell(group_row, col_idx, header_name)
		cell.font = Font(name="Arial", size=13, bold=True, color="000000")
		cell.fill = fill
		cell.border = thin
		cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
		for offset in range(n):
			covered = ws.cell(group_row, col_idx + offset)
			covered.fill = fill
			covered.border = thin
			if multi and n > 1:
				sub = ws.cell(sub_row, col_idx + offset, _wrap_heading(group["cols"][offset].get("label") or ""))
				sub.font = Font(name="Arial", size=13, bold=True, color="000000")
				sub.fill = fill
				sub.border = thin
				sub.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
		col_idx += n

	tot_fill = PatternFill("solid", fgColor="E8E8E8")
	paired = any(col.get("esh_stack") and len(col["esh_stack"]) > 1 for col in columns)
	for r_idx, row in enumerate(rows, start=data_start):
		is_tot = row.get("_is_total")
		ws.row_dimensions[r_idx].height = 44 if paired else 26
		for c_idx, col in enumerate(columns, start=1):
			fn = col["fieldname"]
			cell = ws.cell(r_idx, c_idx)
			cell.font = Font(name="Arial", size=12, bold=bool(is_tot))
			cell.border = thin
			cell.alignment = Alignment(horizontal="center", vertical="center")
			if is_tot:
				cell.fill = tot_fill
			stack = col.get("esh_stack")
			if stack:
				lines = [
					_display_value({"fieldname": part["fieldname"], "fieldtype": "Currency"}, row)
					for part in stack
				]
				cell.value = "\n".join(lines)
				cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
				continue
			val = row.get(fn)
			cell.value = None if val in (None, "") else val
			if fn == "paid_days" and isinstance(val, (int, float)):
				v = flt(val)
				if abs(v - round(v)) < 1e-9:
					cell.value = int(round(v))
					cell.number_format = "0"
				else:
					cell.number_format = "0.0"
				cell.alignment = Alignment(horizontal="center", vertical="center")
			elif col.get("fieldtype") in ("Currency", "Float") and isinstance(val, (int, float)):
				cell.number_format = "#,##0.00"
				cell.alignment = Alignment(horizontal="right", vertical="center", wrap_text=False)
			elif fn == "month_year":
				cell.alignment = Alignment(horizontal="left", vertical="center")

	for i, col in enumerate(columns, start=1):
		ws.column_dimensions[get_column_letter(i)].width = _excel_width_for_values(
			ws, i, group_row, sub_row if multi else group_row, data_start, data_start + len(rows) - 1
		)
	ws.row_dimensions[group_row].height = 40
	if multi:
		ws.row_dimensions[sub_row].height = 44
	_write_abbreviation_legend(ws, columns, data_start + len(rows) + 3)
	_prepare_print(ws, group_row, sub_row if multi else group_row)
	return wb


def _prepare_print(ws, header_start, header_end):
	"""Fit the columns across the page. Leave row height and font at their real size."""
	ws.page_setup.orientation = "landscape"
	ws.page_setup.paperSize = ws.PAPERSIZE_A4
	ws.page_setup.fitToWidth = 1
	ws.page_setup.fitToHeight = 0
	ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
	ws.page_margins.left = 0.25
	ws.page_margins.right = 0.25
	ws.page_margins.top = 0.4
	ws.page_margins.bottom = 0.4
	ws.print_title_rows = f"{header_start}:{header_end}"
	ws.page_setup.horizontalCentered = True


# Headings people already read as words. Everything else comes from the component itself.
_CLEAR_HEADINGS = {"loan", "tds"}


def _legend_pair(short, full):
	"""Short heading and its name, when the heading itself is not already clear."""
	short = " ".join(str(short or "").split())
	full = " ".join(str(full or "").split())
	if not short or not full or short.lower() == full.lower():
		return None
	if short.lower() in _CLEAR_HEADINGS:
		return None
	return short, full


def _legend_pairs(columns):
	pairs = []
	seen = set()
	for col in columns:
		sources = col.get("esh_stack") or [
			{"label": col.get("label"), "full_name": col.get("esh_full_name")}
		]
		for source in sources:
			pair = _legend_pair(source.get("label"), source.get("full_name"))
			if not pair:
				continue
			key = pair[0].lower()
			if key in seen:
				continue
			seen.add(key)
			pairs.append(pair)
	return pairs


def _legend_html(columns):
	pairs = _legend_pairs(columns)
	if not pairs:
		return ""
	rows = []
	for short, full in pairs:
		code = frappe.utils.escape_html(short)
		name = frappe.utils.escape_html(full)
		rows.append(f'<tr><td class="code">{code}</td><td class="name">{name}</td></tr>')
	return (
		'<table class="note"><thead><tr><th colspan="2">NOTE</th></tr></thead>'
		f"<tbody>{''.join(rows)}</tbody></table>"
	)


def _write_abbreviation_legend(ws, columns, start_row):
	"""NOTE table under the sheet: yellow title, then code and full name."""
	pairs = _legend_pairs(columns)
	if not pairs:
		return
	# Code in column A. The name spans the next columns so print does not cut it.
	name_end = 5
	thin = Border(
		left=Side(style="thin", color="000000"),
		right=Side(style="thin", color="000000"),
		top=Side(style="thin", color="000000"),
		bottom=Side(style="thin", color="000000"),
	)
	yellow = PatternFill("solid", fgColor="FFFF00")
	white = PatternFill("solid", fgColor="FFFFFF")
	ws.merge_cells(start_row=start_row, start_column=1, end_row=start_row, end_column=name_end)
	ws.row_dimensions[start_row].height = 28
	for c in range(1, name_end + 1):
		head = ws.cell(start_row, c)
		head.fill = yellow
		head.border = thin
	title = ws.cell(start_row, 1, "NOTE")
	title.font = Font(name="Arial", size=13, bold=True, color="000000")
	title.alignment = Alignment(horizontal="center", vertical="center")
	title.fill = yellow
	for offset, (short, full) in enumerate(pairs, start=1):
		r = start_row + offset
		ws.row_dimensions[r].height = 24
		ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=name_end)
		code = ws.cell(r, 1, short)
		code.font = Font(name="Arial", size=12, color="000000")
		code.alignment = Alignment(horizontal="center", vertical="center")
		code.fill = white
		code.border = thin
		for c in range(2, name_end + 1):
			box = ws.cell(r, c)
			box.fill = white
			box.border = Border(
				left=Side(style="thin", color="000000") if c == 2 else Side(),
				right=Side(style="thin", color="000000") if c == name_end else Side(),
				top=Side(style="thin", color="000000"),
				bottom=Side(style="thin", color="000000"),
			)
		name = ws.cell(r, 2, full)
		name.font = Font(name="Arial", size=12, color="000000")
		name.alignment = Alignment(horizontal="left", vertical="center", indent=1)
		name.fill = white


def _excel_text_width(value, number_format):
	if value is None or value == "":
		return 0
	if isinstance(value, str):
		return max((len(line) for line in value.split("\n")), default=0)
	if isinstance(value, (int, float)) and not isinstance(value, bool):
		fmt = number_format or ""
		if fmt == "0":
			text = str(int(round(value)))
		elif fmt == "0.0":
			text = f"{float(value):.1f}"
		elif "0.00" in fmt:
			text = f"{float(value):,.2f}"
		else:
			text = str(value)
		return len(text)
	return len(str(value))


def _excel_width_for_values(ws, col_idx, group_row, sub_row, data_start, data_end):
	"""Wide enough for the largest amount in the column. A short amount stays narrow."""
	longest = 0
	for row_idx in range(data_start, data_end + 1):
		cell = ws.cell(row_idx, col_idx)
		longest = max(longest, _excel_text_width(cell.value, cell.number_format))
	label_cell = ws.cell(sub_row, col_idx)
	if not label_cell.value:
		label_cell = ws.cell(group_row, col_idx)
	longest = max(longest, _excel_text_width(label_cell.value, label_cell.number_format))
	# Arial 12 is wider than Excel's width unit, so ###### does not hide 10 lakh.
	return min(max(longest * 1.25 + 2, 6), 28)


def _save_excel(wb, prefix):
	buf = io.BytesIO()
	wb.save(buf)
	ts = frappe.utils.now_datetime().strftime("%Y%m%d_%H%M%S")
	fn = f"{prefix}_{ts}.xlsx"
	with open(frappe.utils.get_files_path(fn, is_private=0), "wb") as fh:
		fh.write(buf.getvalue())
	doc = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": fn,
			"is_private": 0,
			"file_url": f"/files/{fn}",
		}
	)
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return doc.file_url
