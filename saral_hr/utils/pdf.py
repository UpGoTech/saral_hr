import re
from typing import Literal

import frappe
from frappe.translate import print_language
from frappe.utils.pdf import get_pdf
from frappe.www.printview import validate_print_permission

_STYLESHEET_LINK = re.compile(r"<link\b[^>]*>", re.I)
WKHTMLTOPDF_PDF_OPTIONS = {
	"load-error-handling": "ignore",
	"load-media-error-handling": "ignore",
}


def offline_print_html(html):
	"""Drop <link> tags so wkhtmltopdf does not fetch HTTPS assets (SslHandshakeFailedError).

	Print-format CSS is already inlined in a <style> block.
	"""
	return _STYLESHEET_LINK.sub("", html or "")


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
			pdf_generator=pdf_generator,
		)
		pdf_file = get_pdf(offline_print_html(html), options=WKHTMLTOPDF_PDF_OPTIONS)

	frappe.local.response.filename = "{name}.pdf".format(name=name.replace(" ", "-").replace("/", "-"))
	frappe.local.response.filecontent = pdf_file
	frappe.local.response.type = "pdf"
