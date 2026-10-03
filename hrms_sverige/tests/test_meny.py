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

	def test_logotyp_i_samma_stil_som_hrms(self):
		# Samma färger som hrms ikoner i gruppen: ljusgrön bakgrund och mörkgrön symbol
		logo_url = frappe.get_doc("Desktop Icon", MENY).logo_url
		self.assertTrue(logo_url.startswith("/assets/hrms_sverige/"))
		svg = open(
			frappe.get_app_path("hrms_sverige", "public", logo_url.removeprefix("/assets/hrms_sverige/"))
		).read()
		self.assertIn('fill="#06B58B" fill-opacity="0.1"', svg)
		self.assertIn("#1F876C", svg)

	def test_ikonvarianter_som_hrms(self):
		# Desk väljer assets/<app>/icons/desktop_icons/<solid|subtle>/<etikett>.svg efter användarens ikonstil
		farger = {
			"solid": ('fill="#06B58B"/>', 'stroke="white"'),
			"subtle": ('fill-opacity="0.1"', "#1F876C"),
		}
		for variant, (bakgrund, symbol) in farger.items():
			svg = open(
				frappe.get_app_path(
					"hrms_sverige", "public", "icons", "desktop_icons", variant, f"{frappe.scrub(MENY)}.svg"
				)
			).read()
			self.assertIn(bakgrund, svg, variant)
			self.assertIn(symbol, svg, variant)

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
