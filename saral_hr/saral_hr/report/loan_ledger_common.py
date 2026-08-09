# Copyright (c) 2026, sj and contributors
# For license information, please see license.txt

"""Shared Employee Loan / Loan ledger rows, opening balance, and PDF helpers."""

from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import flt, getdate
from frappe.utils.pdf import get_pdf

_CSS = """<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Arial,sans-serif;font-size:10px;color:#000;background:#fff}
.hdr{text-align:center;border-bottom:2px solid #000;padding:6px 6px 5px;margin-bottom:4px;}
.hdr .co{font-size:16px;font-weight:900;letter-spacing:.5px;text-transform:uppercase}
.hdr .ttl{font-size:13px;font-weight:700;margin-top:2px}
.hdr .meta{font-size:10px;margin-top:2px}
table.data-tbl{width:100%;border-collapse:collapse;table-layout:fixed;}
table.data-tbl th{border:1px solid #000;padding:4px 5px;font-size:9px;font-weight:700;background:#f0f0f0;text-align:center;}
table.data-tbl td{border:1px solid #000;padding:3px 5px;font-size:9px;vertical-align:middle;}
tr.tot td{background:#e8e8e8;font-weight:700;}
.nd{text-align:center;padding:14px;color:#888}
.pg-foot{text-align:right;font-size:8px;color:#555;margin-top:2px;}
.sig{display:flex;justify-content:space-between;width:100%;margin-top:18px;padding-top:6px;}
.sig-b{text-align:center;width:160px}
.sig-l{border-top:1px solid #000;margin-bottom:3px}
.sig-t{font-size:10px;color:#333}
.sig-d{font-size:9px;color:#555;margin-top:5px}
</style>"""

B = "1px solid #000"
ROWS_FIRST_PAGE = 28
ROWS_OTHER_PAGE = 32


def ledger_columns():
	return [
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Particulars"), "fieldname": "particulars", "fieldtype": "Data", "width": 280},
		{"label": _("Loan ID"), "fieldname": "reference", "fieldtype": "Link", "options": "Employee Loan", "width": 120},
		{"label": _("Voucher"), "fieldname": "voucher", "fieldtype": "Dynamic Link", "options": "voucher_type", "width": 160},
		{"label": _("Voucher Type"), "fieldname": "voucher_type", "fieldtype": "Data", "width": 120, "hidden": 1},
		{"label": _("Debit"), "fieldname": "debit", "fieldtype": "Currency", "width": 110},
		{"label": _("Credit"), "fieldname": "credit", "fieldtype": "Currency", "width": 110},
		{"label": _("Balance"), "fieldname": "balance", "fieldtype": "Currency", "width": 120},
	]


def _collect_raw_events(employee=None, loan=None, company=None):
	"""All ledger movements for matching loans (no date window)."""
	loan_filters = {"docstatus": 1}
	if employee:
		loan_filters["employee"] = employee
	if loan:
		loan_filters["name"] = loan
	if company:
		loan_filters["company"] = company

	loans = frappe.get_all(
		"Employee Loan",
		filters=loan_filters,
		fields=["name", "employee", "full_name", "company", "loan_date", "amount", "reason"],
		order_by="loan_date asc, name asc",
	)
	if not loans:
		return []

	loan_names = [l.name for l in loans]
	events = []

	for l in loans:
		events.append(
			{
				"posting_date": getdate(l.loan_date),
				"particulars": f"Loan given — {l.name}"
				+ (f" ({l.reason})" if l.reason else ""),
				"voucher": l.name,
				"voucher_type": "Employee Loan",
				"reference": l.name,
				"debit": flt(l.amount),
				"credit": 0.0,
				"loan": l.name,
				"employee": l.employee,
				"_sort": 0,
			}
		)

	dues = frappe.get_all(
		"Employee Loan Due",
		filters={
			"loan": ["in", loan_names],
			"salary_slip": ["is", "set"],
			"amount": [">", 0],
		},
		fields=["name", "loan", "employee", "amount", "salary_slip", "month"],
	)
	slip_names = list({d.salary_slip for d in dues if d.salary_slip})
	slip_dates = {}
	if slip_names:
		for s in frappe.get_all(
			"Salary Slip",
			filters={"name": ["in", slip_names]},
			fields=["name", "end_date", "start_date"],
		):
			slip_dates[s.name] = getdate(s.end_date or s.start_date)

	for d in dues:
		dt = slip_dates.get(d.salary_slip)
		if not dt:
			continue
		events.append(
			{
				"posting_date": dt,
				"particulars": f"Salary recovery — {d.loan} — {d.salary_slip} ({d.month})",
				"voucher": d.salary_slip,
				"voucher_type": "Salary Slip",
				"reference": d.loan,
				"debit": 0.0,
				"credit": flt(d.amount),
				"loan": d.loan,
				"employee": d.employee,
				"_sort": 1,
			}
		)

	prepay_rows = frappe.db.sql(
		"""
		SELECT p.prepayment_date, p.amount, p.remark, p.parent AS loan, l.employee
		FROM `tabEmployee Loan Prepayment` p
		INNER JOIN `tabEmployee Loan` l ON l.name = p.parent
		WHERE p.parent IN %(loans)s
		""",
		{"loans": tuple(loan_names)},
		as_dict=True,
	)
	for p in prepay_rows:
		remark = (p.remark or "").strip()
		particulars = "Prepayment"
		if remark:
			particulars = f"Prepayment — {remark}"
		events.append(
			{
				"posting_date": getdate(p.prepayment_date),
				"particulars": f"{particulars} ({p.loan})",
				"voucher": p.loan,
				"voucher_type": "Employee Loan",
				"reference": p.loan,
				"debit": 0.0,
				"credit": flt(p.amount),
				"loan": p.loan,
				"employee": p.employee,
				"_sort": 2,
			}
		)

	events.sort(key=lambda e: (e["posting_date"], e["_sort"], e["voucher"] or ""))
	return events


def build_ledger_rows(employee=None, loan=None, company=None, from_date=None, to_date=None):
	"""Return (rows, totals) with running balance. Positive balance = receivable."""
	raw = _collect_raw_events(employee=employee, loan=loan, company=company)
	from_d = getdate(from_date) if from_date else None
	to_d = getdate(to_date) if to_date else None

	opening = 0.0
	in_range = []
	for e in raw:
		d = e["posting_date"]
		delta = flt(e["debit"]) - flt(e["credit"])
		if from_d and d < from_d:
			opening += delta
			continue
		if to_d and d > to_d:
			continue
		in_range.append(e)

	rows = []
	balance = flt(opening)
	total_dr = 0.0
	total_cr = 0.0

	if from_d and (opening or in_range or raw):
		rows.append(
			{
				"posting_date": from_d,
				"particulars": _("Opening Balance"),
				"voucher": "",
				"voucher_type": "",
				"reference": "",
				"debit": flt(opening) if opening > 0 else 0.0,
				"credit": flt(-opening) if opening < 0 else 0.0,
				"balance": flt(opening, 2),
				"indent": 0,
			}
		)
		# Opening shown in Dr/Cr for clarity; balance starts at opening.
		# Do not double-count opening into period totals.

	for e in in_range:
		balance += flt(e["debit"]) - flt(e["credit"])
		total_dr += flt(e["debit"])
		total_cr += flt(e["credit"])
		rows.append(
			{
				"posting_date": e["posting_date"],
				"particulars": e["particulars"],
				"voucher": e["voucher"],
				"voucher_type": e["voucher_type"],
				"reference": e.get("reference") or e.get("loan") or "",
				"debit": flt(e["debit"], 2) or None,
				"credit": flt(e["credit"], 2) or None,
				"balance": flt(balance, 2),
			}
		)

	if rows:
		rows.append(
			{
				"posting_date": "",
				"particulars": _("Total"),
				"voucher": "",
				"voucher_type": "",
				"reference": "",
				"debit": flt(total_dr, 2),
				"credit": flt(total_cr, 2),
				"balance": flt(balance, 2),
				"bold": 1,
			}
		)

	return rows, {"debit": total_dr, "credit": total_cr, "balance": balance, "opening": opening}


def _fmt(v):
	if v is None or v == "":
		return ""
	try:
		return "{:,.2f}".format(float(v))
	except (TypeError, ValueError):
		return str(v)


def _sig_html():
	labels = ["Prepared By", "Checked By", "Authorised Signatory"]
	blocks = "".join(
		'<div class="sig-b"><div class="sig-l"></div>'
		'<div class="sig-t">{l}</div>'
		'<div class="sig-d">Date: ___________</div></div>'.format(l=l)
		for l in labels
	)
	return '<div class="sig">{}</div>'.format(blocks)


def build_ledger_pdf_html(title, company, meta_lines, rows):
	cols = [
		("posting_date", "Date", "9%", "center"),
		("particulars", "Particulars", "28%", "left"),
		("reference", "Loan ID", "12%", "left"),
		("voucher", "Voucher", "17%", "left"),
		("debit", "Debit", "11%", "right"),
		("credit", "Credit", "11%", "right"),
		("balance", "Balance", "12%", "right"),
	]
	cg = "<colgroup>" + "".join(
		'<col style="width:{w};"/>'.format(w=c[2]) for c in cols
	) + "</colgroup>"

	meta = " &mdash; ".join([m for m in meta_lines if m])
	page1_hdr = (
		'<div class="hdr"><div class="co">{co}</div>'
		'<div class="ttl">{ttl}</div>'
		'<div class="meta">{meta}</div></div>'
	).format(co=frappe.utils.escape_html(company or ""), ttl=frappe.utils.escape_html(title), meta=frappe.utils.escape_html(meta))
	cont_hdr = (
		'<div class="hdr"><div class="co">{co}</div>'
		'<div class="ttl">{ttl} (contd.)</div></div>'
	).format(co=frappe.utils.escape_html(company or ""), ttl=frappe.utils.escape_html(title))

	header_tr = "<tr>" + "".join(
		'<th style="border:{B};">{lbl}</th>'.format(B=B, lbl=c[1]) for c in cols
	) + "</tr>"

	def row_html(row, idx):
		is_tot = bool(row.get("bold"))
		bg = "#e8e8e8" if is_tot else ("#f9f9f9" if idx % 2 else "#ffffff")
		fw = "font-weight:700;" if is_tot else ""
		html = "<tr>"
		for fn, _lbl, _w, align in cols:
			val = row.get(fn, "")
			if fn in ("debit", "credit", "balance"):
				disp = _fmt(val) if val not in ("", None) else ""
			elif fn == "posting_date":
				disp = str(val) if val else ""
			else:
				disp = frappe.utils.escape_html(str(val)) if val else ""
			html += (
				'<td style="border:{B};text-align:{a};background:{bg};{fw}">{v}</td>'
			).format(B=B, a=align, bg=bg, fw=fw, v=disp)
		html += "</tr>"
		return html

	body_rows = [r for r in rows if not r.get("bold")]
	tot_rows = [r for r in rows if r.get("bold")]

	if not body_rows and not tot_rows:
		pages, has_data = [[]], False
	elif not body_rows:
		pages, has_data = [tot_rows], True
	else:
		has_data = True
		pages, idx, first = [], 0, True
		while idx < len(body_rows):
			lim = ROWS_FIRST_PAGE if first else ROWS_OTHER_PAGE
			pages.append(body_rows[idx : idx + lim])
			idx += lim
			first = False
		if tot_rows:
			pages[-1] = pages[-1] + tot_rows

	parts = []
	total_pages = len(pages)
	row_counter = 0
	for pn, page_rows in enumerate(pages):
		pb = '<div style="page-break-before:always;"></div>' if pn > 0 else ""
		is_last = pn == total_pages - 1
		hdr = page1_hdr if pn == 0 else cont_hdr
		if not has_data:
			tbl = (
				'<table class="data-tbl">{cg}<thead>{hdr}</thead>'
				'<tbody><tr><td colspan="7" class="nd">No entries</td></tr></tbody></table>'
			).format(cg=cg, hdr=header_tr)
		else:
			tbody = "".join(row_html(r, row_counter + j) for j, r in enumerate(page_rows))
			tbl = (
				'<table class="data-tbl">{cg}<thead>{hdr}</thead><tbody>{tb}</tbody></table>'
			).format(cg=cg, hdr=header_tr, tb=tbody)
			row_counter += len([r for r in page_rows if not r.get("bold")])
		foot = '<div class="pg-foot">Page {p} of {t}</div>'.format(p=pn + 1, t=total_pages)
		sig = _sig_html() if is_last else ""
		parts.append("{pb}{hdr}{tbl}{foot}{sig}".format(pb=pb, hdr=hdr, tbl=tbl, foot=foot, sig=sig))

	return '<!DOCTYPE html><html><head><meta charset="UTF-8">{css}</head><body>{body}</body></html>'.format(
		css=_CSS, body="".join(parts)
	)


def save_ledger_pdf(html, prefix):
	pdf = get_pdf(
		html,
		options={
			"page-size": "A4",
			"orientation": "Portrait",
			"margin-top": "8mm",
			"margin-right": "8mm",
			"margin-bottom": "10mm",
			"margin-left": "8mm",
			"encoding": "UTF-8",
			"no-outline": None,
		},
	)
	ts = frappe.utils.now_datetime().strftime("%Y%m%d_%H%M%S")
	fn = "{prefix}_{ts}.pdf".format(prefix=prefix, ts=ts)
	with open(frappe.utils.get_files_path(fn, is_private=0), "wb") as fh:
		fh.write(pdf)
	doc = frappe.get_doc(
		{"doctype": "File", "file_name": fn, "is_private": 0, "file_url": "/files/{fn}".format(fn=fn)}
	)
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return doc.file_url


def parse_filters(filters):
	if isinstance(filters, str):
		filters = json.loads(filters)
	return filters or {}
