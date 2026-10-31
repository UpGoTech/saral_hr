import re
from typing import Literal

import frappe
from frappe.translate import print_language
from frappe.utils.pdf import get_pdf
from frappe.www.printview import validate_print_permission

_STYLESHEET_LINK = re.compile(r"<link\b[^>]*>", re.I)
_COL_VERT_TH = re.compile(r"(<th\b(?=[^>]*\bcol-vert\b)[^>]*>)(.*?)(</th>)", re.I | re.S)
_CARD_WRAP = re.compile(
	r'(<div class="card">)(.*?)(</div>\s*<div class="sign-row">)',
	re.I | re.S,
)
WKHTMLTOPDF_PDF_OPTIONS = {
	"load-error-handling": "ignore",
	"load-media-error-handling": "ignore",
}

MUSTER_CUM_WAGES_SLIP = "Muster Cum Wages Slip"

# print.bundle.css is stripped (HTTPS/SSL). Restore hide for printview chrome.
_PDF_CHROME_CSS = """<style>
.print-hide,.action-banner{display:none!important}
</style>"""

# PDF button only. Desk Print / preview keep the print-format CSS as-is.
# wkhtmltopdf ignores flex and writing-mode:sideways-lr; transform on <th> also
# fails. Table-cell + 1%/99% mimics flex shrink-wrap. Vertical headers need a
# <span> (see _wrap_vert_headers) — same trick as .leave-txt.
# .print-format { margin-* } is read as wkhtmltopdf page margins (else 15mm).
_MUSTER_PDF_CSS = """<style>
.print-format{
	margin-top:4mm;
	margin-right:8mm;
	margin-bottom:4mm;
	margin-left:20mm;
}
@media print{
	.print-format{
		margin:0!important;
		width:100%!important;
		max-width:100%!important;
		padding:0!important;
		height:auto!important;
		min-height:0!important;
		box-sizing:border-box!important;
	}
	.print-block{
		padding:8px 2mm 0!important;
		width:100%!important;
		max-width:100%!important;
		box-sizing:border-box!important;
	}
	.print-block .card-frame{
		border:1.5px solid #222!important;
		border-radius:18px!important;
		overflow:visible!important;
		width:100%!important;
		max-width:100%!important;
		box-sizing:border-box!important;
	}
	.print-block .card{
		overflow:hidden!important;
		border:none!important;
		border-radius:18px!important;
		width:100%!important;
		max-width:100%!important;
		box-sizing:border-box!important;
	}
	.print-block table{
		width:100%!important;
		max-width:100%!important;
		box-sizing:border-box!important;
		border-collapse:collapse!important;
	}
	.print-block,.print-block .card{
		page-break-inside:auto!important;
		page-break-before:avoid!important;
	}
	.muster-card{
		page-break-after:avoid!important;
		page-break-inside:auto!important;
	}
	.muster-layout > tbody > tr > td.col-left,
	.muster-layout > tbody > tr > td.col-right{
		display:table-cell!important;
		width:50%!important;
		vertical-align:top!important;
		overflow:visible!important;
	}
	.col-right{
		display:table-cell!important;
		flex-direction:unset!important;
	}
	.right-head{
		display:block!important;
		position:relative!important;
		padding-top:15mm!important;
		margin:0 0 10mm 0!important;
		text-align:center!important;
	}
	.right-head .brand{
		position:absolute!important;
		top:0!important;
		left:0!important;
		display:block!important;
		text-align:left!important;
	}
	.right-head .title{
		display:block!important;
		text-align:center!important;
	}
	.fline{
		display:table!important;
		width:100%!important;
		border-collapse:collapse!important;
		table-layout:auto!important;
		min-height:7.5mm!important;
		margin-bottom:2.4mm!important;
	}
	.fline .fl,.fline .fv{
		display:table-cell!important;
		vertical-align:bottom!important;
	}
	.fline .fl{
		width:1%!important;
		white-space:nowrap!important;
	}
	.fline .fl.stack{
		white-space:nowrap!important;
		vertical-align:bottom!important;
	}
	.fline .fv{
		width:99%!important;
		min-height:6mm!important;
		padding-top:2px!important;
		padding-bottom:2px!important;
	}
	.fline.split .fv.mid{
		width:40%!important;
	}
	.fline .fv.short{
		width:18%!important;
	}
	.fline.age-row .fv:first-child{
		width:auto!important;
	}
	.wage-grid > tbody > tr > td{
		height:8mm!important;
	}
	.wage-grid .leave-wrap{
		height:32mm!important;
		max-height:32mm!important;
	}
	.print-block tr.cols th{
		height:116px!important;
	}
	.print-block th.col-vert{
		writing-mode:horizontal-tb!important;
		-webkit-writing-mode:horizontal-tb!important;
		transform:none!important;
	}
	.print-block th.col-vert .vert-label{
		display:inline-block!important;
		white-space:nowrap!important;
		font-weight:700!important;
		font-size:10px!important;
		writing-mode:vertical-rl!important;
		-webkit-writing-mode:vertical-rl!important;
		-webkit-transform:rotate(180deg)!important;
		transform:rotate(180deg)!important;
	}
	.print-block th.col-date{
		writing-mode:horizontal-tb!important;
		-webkit-writing-mode:horizontal-tb!important;
		transform:none!important;
	}
}
</style>"""


def _wrap_vert_headers(html):
	"""Wrap col-vert <th> text in a span so wkhtmltopdf can rotate it."""

	def _repl(match):
		inner = match.group(2)
		if "vert-label" in inner:
			return match.group(0)
		return f'{match.group(1)}<span class="vert-label">{inner}</span>{match.group(3)}'

	return _COL_VERT_TH.sub(_repl, html)


def _wrap_attendance_card(html):
	"""Outer rounded stroke on a wrapper so overflow:hidden does not clip it.

	Inner cell borders stay on .card > table (print-format CSS).
	"""
	return _CARD_WRAP.sub(r'<div class="card-frame">\1\2</div>\3', html, count=1)


def offline_print_html(html, print_format=None):
	"""Drop <link> tags so wkhtmltopdf does not fetch HTTPS assets (SslHandshakeFailedError).

	Print-format CSS is already inlined in a <style> block.
	Muster PDF-only chrome/layout CSS is injected here so Desk print preview is unchanged.
	"""
	html = _STYLESHEET_LINK.sub("", html or "")
	if print_format != MUSTER_CUM_WAGES_SLIP:
		return html
	html = _wrap_attendance_card(_wrap_vert_headers(html))
	inject = _PDF_CHROME_CSS + _MUSTER_PDF_CSS
	if "</head>" in html:
		return html.replace("</head>", inject + "</head>", 1)
	return inject + html


@frappe.whitelist(allow_guest=True)
def download_pdf(
	doctype: str,
	name: str,
	format=None,
	doc=None,
	no_letterhead=0,
	language=None,
	letterhead=None,
	pdf_generator: Literal["wkhtmltopdf", "chrome"] | None = None,
):
	doc = doc or frappe.get_doc(doctype, name)
	validate_print_permission(doc)

	with print_language(language):
		html = frappe.get_print(
			doctype,
			name,
			format,
			doc=doc,
			letterhead=letterhead,
			no_letterhead=no_letterhead,
		)
		options = dict(WKHTMLTOPDF_PDF_OPTIONS)
		if format == MUSTER_CUM_WAGES_SLIP:
			# Preview layout is slightly taller than A4 in wkhtmltopdf; zoom keeps 1 page.
			options["zoom"] = "0.9"
		pdf_file = get_pdf(offline_print_html(html, print_format=format), options=options)

	frappe.local.response.filename = "{name}.pdf".format(name=name.replace(" ", "-").replace("/", "-"))
	frappe.local.response.filecontent = pdf_file
	frappe.local.response.type = "pdf"
