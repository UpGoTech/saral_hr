# Copyright (c) 2026, sj and Contributors
# See license.txt

import json

import frappe
from frappe.tests.utils import FrappeTestCase

from saral_hr.patches.ensure_data_cleansing_workspace_link import (
	CARD_NAME,
	LINK_LABEL,
	PAGE_NAME,
	execute,
)


class TestEnsureDataCleansingWorkspaceLink(FrappeTestCase):
	def test_adds_missing_card_and_link_idempotently(self):
		if not frappe.db.exists("Workspace", "Saral HR"):
			self.skipTest("Saral HR workspace not installed")

		ws = frappe.get_doc("Workspace", "Saral HR")
		ws.links = [row for row in ws.links if row.label not in (CARD_NAME, LINK_LABEL)]
		blocks = json.loads(ws.content or "[]")
		ws.content = json.dumps(
			[
				b
				for b in blocks
				if not (b.get("type") == "card" and b.get("data", {}).get("card_name") == CARD_NAME)
			]
		)
		ws.flags.ignore_links = True
		ws.save(ignore_permissions=True)

		execute()
		ws.reload()
		self.assertTrue(
			any(row.type == "Link" and row.label == LINK_LABEL and row.link_to == PAGE_NAME for row in ws.links)
		)
		content = json.loads(ws.content)
		self.assertTrue(
			any(
				b.get("type") == "card" and b.get("data", {}).get("card_name") == CARD_NAME for b in content
			)
		)

		link_count_before = sum(1 for row in ws.links if row.label == LINK_LABEL)
		execute()
		ws.reload()
		link_count_after = sum(1 for row in ws.links if row.label == LINK_LABEL)
		self.assertEqual(link_count_before, link_count_after)
		self.assertEqual(link_count_after, 1)
