import frappe
from frappe.installer import update_site_config

def execute():
    update_site_config("pdf_options", {"load-error-handling": "ignore"})
