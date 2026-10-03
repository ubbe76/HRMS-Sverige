"""Skrivbordsikon och sidomeny: lönedelen ska synas under Frappe HR i menyn."""

import frappe
from frappe.tests import IntegrationTestCase

MENY = "Lön och stämpling"


class TestMeny(IntegrationTestCase):
	def test_ikon_under_frappe_hr(self):
		ikon = frappe.get_doc("Desktop Icon", MENY)
		self.assertEqual(
			(ikon.parent_icon, ikon.link_type, ikon.link_to), ("Frappe HR", "Workspace Sidebar", MENY)
		)
		self.assertFalse(ikon.hidden)

	def test_sidomenyns_lankar(self):
		lankar = [
			(rad.link_type, rad.link_to)
			for rad in frappe.get_doc("Workspace Sidebar", MENY).items
			if rad.type == "Link"
		]
		self.assertEqual(
			lankar,
			[("DocType", "Loneunderlag"), ("DocType", "Stamplingsenhet"), ("DocType", "Loneinstallningar")],
		)
		for link_type, link_to in lankar:
			self.assertTrue(frappe.db.exists(link_type, link_to), link_to)
