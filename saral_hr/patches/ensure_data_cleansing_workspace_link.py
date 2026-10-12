import json

import frappe

CARD_NAME = "Data Auditing and Cleansing"
LINK_LABEL = "Data Cleansing"
PAGE_NAME = "data-cleansing"
CARD_BLOCK_ID = "dcCard00001"


def execute():
	"""Ensure Saral HR workspace shows Data Cleansing (DB workspaces skip JSON sync)."""
	if not frappe.db.exists("Workspace", "Saral HR"):
		return

	ws = frappe.get_doc("Workspace", "Saral HR")
	changed = False

	if not _has_data_cleansing_link(ws):
		ws.append(
			"links",
			{
				"type": "Card Break",
				"label": CARD_NAME,
				"hidden": 0,
				"is_query_report": 0,
				"link_count": 1,
				"link_type": "DocType",
				"onboard": 0,
			},
		)
		ws.append(
			"links",
			{
				"type": "Link",
				"label": LINK_LABEL,
				"link_type": "Page",
				"link_to": PAGE_NAME,
				"hidden": 0,
				"is_query_report": 0,
				"link_count": 0,
				"onboard": 0,
			},
		)
		changed = True

	if _ensure_card_in_content(ws):
		changed = True

	if not changed:
		return

	ws.flags.ignore_links = True
	ws.flags.ignore_permissions = True
	ws.save(ignore_permissions=True)


def _has_data_cleansing_link(ws) -> bool:
	return any(
		row.type == "Link" and row.label == LINK_LABEL and row.link_to == PAGE_NAME for row in ws.links
	)


def _ensure_card_in_content(ws) -> bool:
	try:
		blocks = json.loads(ws.content or "[]")
	except (TypeError, json.JSONDecodeError):
		return False

	if any(
		block.get("type") == "card" and block.get("data", {}).get("card_name") == CARD_NAME
		for block in blocks
	):
		return False

	card = {
		"id": CARD_BLOCK_ID,
		"type": "card",
		"data": {"card_name": CARD_NAME, "col": 4},
	}

	# Place before Loan header when present; otherwise append.
	insert_at = len(blocks)
	for idx, block in enumerate(blocks):
		if block.get("type") == "header" and "Loan" in (block.get("data", {}).get("text") or ""):
			insert_at = idx
			break

	blocks.insert(insert_at, card)
	ws.content = json.dumps(blocks)
	return True
