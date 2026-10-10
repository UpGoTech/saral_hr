# Copyright (c) 2026, sj and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

import saral_hr.install as install_mod
from saral_hr.install import ensure_desk_home_consistent


class TestInstall(FrappeTestCase):
	def setUp(self):
		self._prev_home = frappe.db.get_default("desktop:home_page")
		self._prev_setup_default = frappe.db.get_default("setup_complete")

	def tearDown(self):
		if self._prev_home is not None:
			frappe.db.set_default("desktop:home_page", self._prev_home)
		if self._prev_setup_default is not None:
			frappe.db.set_default("setup_complete", self._prev_setup_default)
		frappe.clear_cache()

	def test_ensure_desk_home_consistent_fixes_setup_wizard_loop_state(self):
		"""Broken combo: setup complete + home still setup-wizard must be repaired."""
		if not install_mod._is_setup_complete():
			self.skipTest("Site setup is not complete; cannot assert repair path")

		frappe.db.set_default("desktop:home_page", "setup-wizard")
		frappe.db.set_default("setup_complete", "0")

		ensure_desk_home_consistent()

		self.assertEqual(frappe.db.get_default("desktop:home_page"), "workspace")
		self.assertEqual(str(frappe.db.get_default("setup_complete")), "1")

	def test_ensure_desk_home_consistent_noop_when_setup_incomplete(self):
		"""Must not flip home away from setup-wizard while setup is incomplete."""
		# Force the early-return path without mutating Installed Application rows.
		original = install_mod._is_setup_complete
		install_mod._is_setup_complete = lambda: False
		try:
			frappe.db.set_default("desktop:home_page", "setup-wizard")
			ensure_desk_home_consistent()
			self.assertEqual(frappe.db.get_default("desktop:home_page"), "setup-wizard")
		finally:
			install_mod._is_setup_complete = original
