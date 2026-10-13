"""Meny: lönedelen ska synas under Frappe HR.

frappe 16.51 har två lägen. I Apps-läget (standard på nya siter) ligger posten i HRMS dock och öppnar
sidomenyn "Lön och stämpling". I ikonläget ("Desktop Icons") ligger en ikon under Frappe HR.
"""

import json

import frappe
from frappe.desk.doctype.desktop_settings.desktop_settings import is_desktop_icons_page
from frappe.desk.doctype.dock.dock import mounted_apps, resolve_app_dock
from frappe.tests import IntegrationTestCase

MENY = "Lön och stämpling"
APP = "hrms_sverige"


def ikonfil() -> dict:
	with open(frappe.get_app_path(APP, "desktop_icon", "lön_och_stämpling.json")) as f:
		return json.load(f)


class TestMeny(IntegrationTestCase):
	def test_i_hrms_dockan(self):
		self.assertEqual(mounted_apps().get(APP), "hrms")
		self.assertIn(
			("Sidebar", MENY), [(e["link_type"], e["link_to"]) for e in resolve_app_dock("hrms", gated=False)]
		)

	def test_ikon_under_frappe_hr(self):
		ikon = ikonfil()
		self.assertEqual(
			(ikon["parent_icon"], ikon["link_type"], ikon["link_to"]),
			("Frappe HR", "Workspace Sidebar", MENY),
		)
		if is_desktop_icons_page():
			self.assertEqual(frappe.db.get_value("Desktop Icon", MENY, "parent_icon"), "Frappe HR")
			self.assertFalse(frappe.db.get_value("Desktop Icon", MENY, "hidden"))

	def test_logotyp_i_samma_stil_som_hrms(self):
		# Samma färger som hrms ikoner i gruppen: ljusgrön bakgrund och mörkgrön symbol
		logo_url = ikonfil()["logo_url"]
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
		meny = frappe.get_doc("Sidebar", MENY)
		self.assertEqual((meny.app, meny.module, meny.standard), (APP, "Lon", 1))
		lankar = [(rad.link_type, rad.link_to) for rad in meny.items if rad.type == "Link"]
		self.assertEqual(
			lankar,
			[("DocType", "Loneunderlag"), ("DocType", "Stamplingsenhet"), ("DocType", "Loneinstallningar")],
		)
		for link_type, link_to in lankar:
			self.assertTrue(frappe.db.exists(link_type, link_to), link_to)
