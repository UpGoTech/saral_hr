# Copyright (c) 2026, sj and contributors
# For license information, please see license.txt

import json
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, getdate

VIRTUAL_COMPONENTS = {"Gross", "Gross Including Additional Salary"}

MAHARASHTRA_PT_SLABS = [
	{"gender": "Male", "from_amount": 0, "to_amount": 7500, "tax_amount": 0, "february_amount": None},
	{"gender": "Male", "from_amount": 7501, "to_amount": 10000, "tax_amount": 175, "february_amount": 275},
	{"gender": "Male", "from_amount": 10001, "to_amount": None, "tax_amount": 200, "february_amount": 300},
	{"gender": "Female", "from_amount": 0, "to_amount": 25000, "tax_amount": 0, "february_amount": None},
	{"gender": "Female", "from_amount": 25001, "to_amount": None, "tax_amount": 200, "february_amount": None},
]

DEFAULT_PT_AGE_EXEMPT_YEARS = 65


def maharashtra_pt_slabs_json() -> str:
	return json.dumps(MAHARASHTRA_PT_SLABS)


def update_company_employee_counts(company: str | None) -> None:
	"""Recount active Staff/Worker Company Links onto Company headcount fields."""
	if not company or not frappe.db.exists("Company", company):
		return

	rows = frappe.db.sql(
		"""
		SELECT category, COUNT(*) AS cnt
		FROM `tabCompany Link`
		WHERE company = %s AND IFNULL(is_active, 0) = 1
		GROUP BY category
		""",
		company,
		as_dict=True,
	)
	by_cat = {r.category: int(r.cnt) for r in rows}
	staff = by_cat.get("Staff", 0)
	workers = by_cat.get("Worker", 0)

	frappe.db.set_value(
		"Company",
		company,
		{
			"no_of_staff": staff,
			"no_of_workers": workers,
			"total_no_of_employees": staff + workers,
		},
		update_modified=False,
	)


def backfill_all_company_employee_counts() -> None:
	for name in frappe.get_all("Company", pluck="name"):
		update_company_employee_counts(name)


def seed_pt_period_on_company(company_name: str) -> bool:
	"""Append one open Maharashtra PT period when company has none. Returns True if seeded."""
	if not company_name or not frappe.db.exists("Company", company_name):
		return False
	doc = frappe.get_doc("Company", company_name)
	if doc.get("pt_periods"):
		return False
	doc.append(
		"pt_periods",
		{
			"from_date": None,
			"to_date": None,
			"age_exempt_years": DEFAULT_PT_AGE_EXEMPT_YEARS,
			"slabs": maharashtra_pt_slabs_json(),
		},
	)
	doc.save(ignore_permissions=True)
	return True


class Company(Document):

	def validate(self):
		self.validate_esic_settings()
		self.validate_pf_settings()
		self.validate_pt_settings()
		# to_date excluded from protected_fields so it stays editable on locked rows
		self._validate_locked_periods(
			"esic_dependent_component", "ESIC",
			["wage_components", "esic_wage_limit", "employee_contribution", "employer_contribution"]
		)
		self._validate_locked_periods(
			"pf_dependent_component", "PF",
			["wage_components", "pf_wage_limit", "employee_percent",
			 "employer_epf", "employer_eps", "edli_insurance", "admin_charges"]
		)
		self._validate_locked_periods(
			"pt_periods", "Professional Tax",
			["slabs", "age_exempt_years", "from_date"]
		)

	def on_update(self):
		pass

	# ──────────────────────────────────────────────
	# Validate
	# ──────────────────────────────────────────────

	def validate_esic_settings(self):
		for row in (self.get("esic_dependent_component") or []):
			comps = self._parse_components(row)
			if comps:
				self._validate_components(comps, "ESIC")
			for field, lbl in [
				("esic_wage_limit",      "ESIC Wage Limit"),
				("employee_contribution","Employee Contribution %"),
				("employer_contribution","Employer Contribution %"),
			]:
				if flt(row.get(field)) < 0:
					frappe.throw(_("ESIC {0} cannot be negative (row {1}).").format(lbl, row.idx))

	def validate_pf_settings(self):
		for row in (self.get("pf_dependent_component") or []):
			comps = self._parse_components(row)
			if comps:
				self._validate_components(comps, "PF")
			for field, lbl in [
				("pf_wage_limit",   "PF Wage Limit"),
				("employee_percent","Employee PF %"),
				("employer_epf",    "Employer EPF %"),
				("employer_eps",    "Employer EPS %"),
				("edli_insurance",  "EDLI Insurance %"),
				("admin_charges",   "Admin Charges %"),
			]:
				if flt(row.get(field)) < 0:
					frappe.throw(_("PF {0} cannot be negative (row {1}).").format(lbl, row.idx))

	def validate_pt_settings(self):
		rows = list(self.get("pt_periods") or [])
		self._validate_pt_period_overlap(rows)
		for row in rows:
			if cint(row.get("age_exempt_years")) < 0:
				frappe.throw(
					_("Professional Tax Age Exempt Years cannot be negative (row {0}).").format(row.idx)
				)
			slabs = self._parse_slabs(row)
			self._validate_pt_slabs(slabs, row.idx)

	def _validate_pt_period_overlap(self, rows):
		dated = []
		for row in rows:
			if not row.from_date and not row.to_date:
				continue
			start = getdate(row.from_date) if row.from_date else getdate("1900-01-01")
			end = getdate(row.to_date) if row.to_date else getdate("9999-12-31")
			if start > end:
				frappe.throw(
					_("Professional Tax period row {0}: From Date cannot be after To Date.").format(row.idx)
				)
			dated.append((start, end, row.idx))

		for i, (a_start, a_end, a_idx) in enumerate(dated):
			for b_start, b_end, b_idx in dated[i + 1:]:
				if a_start <= b_end and b_start <= a_end:
					frappe.throw(
						_("Professional Tax periods overlap (rows {0} and {1}).").format(a_idx, b_idx)
					)

	def _validate_pt_slabs(self, slabs, row_idx):
		if not slabs:
			return
		by_gender = {"Male": [], "Female": []}
		for i, slab in enumerate(slabs):
			gender = slab.get("gender")
			if gender not in ("Male", "Female"):
				frappe.throw(
					_("Professional Tax slab {0} in period row {1}: gender must be Male or Female.")
					.format(i + 1, row_idx)
				)
			from_amount = flt(slab.get("from_amount"))
			to_raw = slab.get("to_amount")
			tax_amount = flt(slab.get("tax_amount"))
			feb_raw = slab.get("february_amount")
			if from_amount < 0 or tax_amount < 0:
				frappe.throw(
					_("Professional Tax slab {0} in period row {1}: amounts cannot be negative.")
					.format(i + 1, row_idx)
				)
			if feb_raw is not None and feb_raw != "":
				if flt(feb_raw) < 0:
					frappe.throw(
						_("Professional Tax slab {0} in period row {1}: February Amount cannot be negative.")
						.format(i + 1, row_idx)
					)
				if tax_amount == 0:
					frappe.throw(
						_("Professional Tax slab {0} in period row {1}: February Amount is not allowed when Tax is 0.")
						.format(i + 1, row_idx)
					)
			if to_raw is not None and to_raw != "":
				to_amount = flt(to_raw)
				if to_amount < 0:
					frappe.throw(
						_("Professional Tax slab {0} in period row {1}: To Amount cannot be negative.")
						.format(i + 1, row_idx)
					)
				if to_amount < from_amount:
					frappe.throw(
						_("Professional Tax slab {0} in period row {1}: To Amount cannot be less than From.")
						.format(i + 1, row_idx)
					)
			by_gender[gender].append(slab)

		for gender, gender_slabs in by_gender.items():
			if not gender_slabs:
				continue
			sorted_slabs = sorted(gender_slabs, key=lambda s: flt(s.get("from_amount")))
			for i in range(len(sorted_slabs) - 1):
				cur_to = sorted_slabs[i].get("to_amount")
				nxt_from = flt(sorted_slabs[i + 1].get("from_amount"))
				if cur_to is None or cur_to == "":
					frappe.throw(
						_("Professional Tax {0} slabs in period row {1}: open-ended slab must be last.")
						.format(gender, row_idx)
					)
				if flt(cur_to) >= nxt_from:
					frappe.throw(
						_("Professional Tax {0} slabs overlap in period row {1}.").format(gender, row_idx)
					)

	# ──────────────────────────────────────────────
	# Lock validation — period rates already used by payroll
	# ──────────────────────────────────────────────

	def _validate_locked_periods(self, table_fieldname, label, protected_fields):
		"""Block edits to wage components / rates once this period has been used.

		A period is locked when:
		- a submitted Salary Slip's start_date falls in the period, or
		- a submitted SSA's from_date falls in the period.

		to_date stays editable so the period can be closed and a new one opened.
		"""
		old_doc = self.get_doc_before_save()
		if not old_doc:
			return  # new doc — nothing to compare

		old_rows = {
			row.name: row
			for row in (old_doc.get(table_fieldname) or [])
			if row.name
		}

		for row in (self.get(table_fieldname) or []):
			if not row.name or row.name not in old_rows:
				continue  # newly added row — allowed

			if not self._period_is_locked(row.from_date, row.to_date):
				continue

			old_row = old_rows[row.name]
			for field in protected_fields:
				old_val = str(old_row.get(field) or "")
				new_val = str(row.get(field) or "")
				# Numeric compare only when both values are plain numbers (not JSON text)
				try:
					float(old_val)
					float(new_val)
					changed = flt(old_val) != flt(new_val)
				except (TypeError, ValueError):
					changed = old_val != new_val

				if changed:
					period_str = "{0} → {1}".format(
						row.from_date or "open", row.to_date or "open"
					)
					frappe.throw(
						_("{0} period <b>{1}</b>: Cannot edit — "
						  "submitted Salary Slip or Salary Structure Assignment "
						  "already uses this period.")
						.format(label, period_str)
					)

	def _period_is_locked(self, from_date, to_date) -> bool:
		"""True when payroll has already used this period's rates."""
		return self._period_has_ssa(from_date, to_date) or self._period_has_submitted_slip(
			from_date, to_date
		)

	def _period_has_ssa(self, from_date, to_date) -> bool:
		"""Submitted SSA whose assignment start falls in [from_date, to_date]."""
		return self._period_has_doc_date(
			"Salary Structure Assignment", "from_date", from_date, to_date
		)

	def _period_has_submitted_slip(self, from_date, to_date) -> bool:
		"""Submitted Salary Slip whose payroll month start falls in [from_date, to_date]."""
		return self._period_has_doc_date("Salary Slip", "start_date", from_date, to_date)

	def _period_has_doc_date(self, doctype, date_field, from_date, to_date) -> bool:
		filters = {"company": self.name, "docstatus": 1}
		if from_date and to_date:
			filters[date_field] = ["between", [from_date, to_date]]
		elif from_date:
			filters[date_field] = [">=", from_date]
		elif to_date:
			filters[date_field] = ["<=", to_date]
		return bool(frappe.db.exists(doctype, filters))

	# ──────────────────────────────────────────────
	# Helpers
	# ──────────────────────────────────────────────

	def _parse_components(self, row) -> list:
		raw = row.get("wage_components") if row else None
		if not raw:
			return []
		try:
			result = json.loads(raw)
			return result if isinstance(result, list) else []
		except (json.JSONDecodeError, TypeError, ValueError):
			return []

	def _parse_slabs(self, row) -> list:
		raw = row.get("slabs") if row else None
		if not raw:
			return []
		try:
			result = json.loads(raw)
			return result if isinstance(result, list) else []
		except (json.JSONDecodeError, TypeError, ValueError):
			return []

	def _get_matching_row(self, table_fieldname: str, period_date=None):
		"""Return first row whose date range covers period_date. None if no match."""
		for row in (self.get(table_fieldname) or []):
			if not period_date:
				return row   # validate time — just return first
			if not row.from_date and not row.to_date:
				return row   # always active
			from_ok = (not row.from_date) or (getdate(row.from_date) <= getdate(period_date))
			to_ok   = (not row.to_date)   or (getdate(row.to_date)   >= getdate(period_date))
			if from_ok and to_ok:
				return row
		return None

	def _validate_components(self, components: list, label_prefix: str):
		for comp in components:
			if comp in VIRTUAL_COMPONENTS:
				continue
			comp_type = frappe.db.get_value("Salary Component", comp, "type")
			if not comp_type:
				frappe.throw(_("{0} Wage Component <b>{1}</b> does not exist.").format(label_prefix, comp))
			if comp_type != "Earning":
				frappe.throw(_("{0} Wage Component <b>{1}</b> must be of type Earning.").format(label_prefix, comp))

	def _resolve_component_value(self, comp: str, salary_components: dict) -> float:
		if comp == "Gross":
			if "Gross" in salary_components:
				return float(salary_components["Gross"])
			return float(sum(
				v for k, v in salary_components.items()
				if k not in VIRTUAL_COMPONENTS and not k.startswith("_")
			))
		if comp == "Gross Including Additional Salary":
			if "Gross Including Additional Salary" in salary_components:
				return float(salary_components["Gross Including Additional Salary"])
			gross = float(sum(
				v for k, v in salary_components.items()
				if k not in VIRTUAL_COMPONENTS and not k.startswith("_")
			))
			return gross + float(salary_components.get("_additional_salary", 0.0))
		return float(salary_components.get(comp, 0.0))

	# ──────────────────────────────────────────────
	# Wage basis calculators
	# ──────────────────────────────────────────────

	def compute_esic_wage_basis(self, salary_components: dict, period_date=None) -> float:
		row = self._get_matching_row("esic_dependent_component", period_date)
		if not row:
			return 0.0
		components = self._parse_components(row)
		if not components:
			return 0.0
		return max(sum(self._resolve_component_value(c, salary_components) for c in components), 0.0)

	def compute_pf_wage_basis(self, salary_components: dict, period_date=None) -> float:
		row = self._get_matching_row("pf_dependent_component", period_date)
		if not row:
			return 0.0
		components = self._parse_components(row)
		if not components:
			return 0.0
		return max(sum(self._resolve_component_value(c, salary_components) for c in components), 0.0)

	# ──────────────────────────────────────────────
	# Public config helpers
	# ──────────────────────────────────────────────

	def get_salary_calculation_method(self) -> str:
		return "Include Weekly Offs" if "Include" in (self.salary_calculation_based_on or "") else "Exclude Weekly Offs"

	def get_esic_config(self, period_date=None):
		row = self._get_matching_row("esic_dependent_component", period_date)
		if not row:
			return None
		components = self._parse_components(row)
		if not components:
			return None
		return {
			"is_applicable":    True,
			"wage_components":  components,
			"wage_limit":       flt(row.esic_wage_limit) or None,
			"employee_percent": flt(row.employee_contribution) or 0,
			"employer_percent": flt(row.employer_contribution) or 0,
		}

	def get_pf_config(self, period_date=None):
		row = self._get_matching_row("pf_dependent_component", period_date)
		if not row:
			return None
		components = self._parse_components(row)
		if not components:
			return None
		return {
			"is_applicable":    True,
			"wage_components":  components,
			"wage_limit":       flt(row.pf_wage_limit) or None,
			"employee_percent": flt(row.employee_percent) or 0,
			"employer_eps":     flt(row.employer_eps) or 0,
			"employer_epf":     flt(row.employer_epf) or 0,
			"edli_insurance":   flt(row.edli_insurance) or 0,
			"admin_charges":    flt(row.admin_charges) or 0,
		}

	def get_pt_config(self, period_date=None):
		row = self._get_matching_row("pt_periods", period_date)
		if not row:
			return None
		return {
			"age_exempt_years": cint(row.age_exempt_years) if row.age_exempt_years is not None else DEFAULT_PT_AGE_EXEMPT_YEARS,
			"slabs": self._parse_slabs(row),
			"from_date": row.from_date,
			"to_date": row.to_date,
		}

	def calculate_pt(self, gross, gender, period_date, date_of_birth=None) -> float:
		"""Return monthly Professional Tax from company slabs for gross/gender/date."""
		cfg = self.get_pt_config(period_date)
		if not cfg:
			return 0.0

		if date_of_birth and period_date:
			from dateutil.relativedelta import relativedelta
			age = relativedelta(getdate(period_date), getdate(date_of_birth)).years
			if age >= cint(cfg.get("age_exempt_years") or DEFAULT_PT_AGE_EXEMPT_YEARS):
				return 0.0

		resolved_gender = gender if gender in ("Male", "Female") else "Male"
		gross_amt = flt(gross)
		matched_slab = None
		for slab in cfg.get("slabs") or []:
			if slab.get("gender") != resolved_gender:
				continue
			from_amount = flt(slab.get("from_amount"))
			to_raw = slab.get("to_amount")
			in_range = gross_amt >= from_amount and (
				to_raw is None or to_raw == "" or gross_amt <= flt(to_raw)
			)
			if in_range:
				matched_slab = slab
				break

		if not matched_slab:
			return 0.0

		tax = flt(matched_slab.get("tax_amount"))
		if tax == 0:
			return 0.0

		feb_raw = matched_slab.get("february_amount")
		if period_date and getdate(period_date).month == 2 and feb_raw is not None and feb_raw != "":
			return flt(feb_raw)
		return tax


@frappe.whitelist()
def get_statutory_lock_dates(company):
	"""Dates that lock ESIC / PF / PT periods for the Company form UI."""
	if not company:
		return {"ssa_from_dates": [], "slip_start_dates": []}
	ssa_from_dates = frappe.get_all(
		"Salary Structure Assignment",
		filters={"company": company, "docstatus": 1},
		pluck="from_date",
	)
	slip_start_dates = frappe.get_all(
		"Salary Slip",
		filters={"company": company, "docstatus": 1},
		pluck="start_date",
	)
	return {
		"ssa_from_dates": [str(d) for d in ssa_from_dates if d],
		"slip_start_dates": [str(d) for d in slip_start_dates if d],
	}
