"""Tillägg till bootinfo."""

import frappe
from frappe import _


def oversatt_dockan(bootinfo):
	"""Översätt HRMS-dockans etiketter i Apps-läget (frappe 16.51 visar `row.title` utan `__()`).

	Med ERPNext Sverige installerad gör den appen det för alla appar.
	"""
	if "erpnext_sverige" in frappe.get_installed_apps():
		return
	for rad in (bootinfo.get("dock") or {}).get("hrms") or []:
		if rad.get("title"):
			rad["title"] = _(rad["title"])
