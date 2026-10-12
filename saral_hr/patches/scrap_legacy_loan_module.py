"""Remove legacy loan/advance DocTypes and reports from the site."""

import frappe


REPORTS = [
	"Loan Deduction For Month",
	"Employee Loan Advance Ledger",
	"Loan Register",
	"Advance Register",
]

# Parents first, then children (force also handles orphans).
# Do NOT delete "Employee Loan" — the new loan register reuses that DocType name.
# Deleting it after model sync leaves Salary Details.loan pointing at a missing DocType.
DOCTYPES = [
	"Employee Advance",
	"Employee Loan Advance",
	"Employee Loan Schedule",
	"Employee Loan Cash Recovery",
	"Employee Advance Cash Recovery",
	"Employee Loan Advance Schedule",
]

WORKSPACE_LINK_TARGETS = {
	"Employee Loan Advance",
	"Loan Deduction For Month",
	"Employee Loan Advance Ledger",
	"Loan Register",
	"Advance Register",
}


def execute():
	_delete_reports()
	_delete_doctypes()
	_strip_workspace_links()


def _delete_reports():
	for name in REPORTS:
		if frappe.db.exists("Report", name):
			frappe.delete_doc("Report", name, force=1, ignore_permissions=True)


def _delete_doctypes():
	for name in DOCTYPES:
		if frappe.db.exists("DocType", name):
			frappe.delete_doc("DocType", name, force=1, ignore_permissions=True)


def _strip_workspace_links():
	"""DB workspaces may keep stale links/shortcuts even after fixture JSON changes."""
	if not frappe.db.exists("Workspace", "Saral HR"):
		return
	ws = frappe.get_doc("Workspace", "Saral HR")
	changed = False

	kept_links = []
	for link in ws.links or []:
		if (link.link_to or "") in WORKSPACE_LINK_TARGETS:
			changed = True
			continue
		kept_links.append(link)
	ws.links = kept_links

	kept_shortcuts = []
	for sc in ws.shortcuts or []:
		target = sc.link_to or sc.label or ""
		if target in WORKSPACE_LINK_TARGETS:
			changed = True
			continue
		kept_shortcuts.append(sc)
	ws.shortcuts = kept_shortcuts

	if changed:
		ws.flags.ignore_permissions = True
		ws.flags.ignore_links = True
		ws.save()
