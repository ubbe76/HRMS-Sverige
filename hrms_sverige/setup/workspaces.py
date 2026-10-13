"""Dölj HRMS-arbetsytor vi inte använder. Modulerna finns kvar och kan visas igen."""

import frappe

HIDDEN = ("Payroll", "Tax & Benefits", "Recruitment", "Expenses", "Performance", "Tenure")


def hide_unused():
	for name in HIDDEN:
		if frappe.db.exists("Workspace", name):
			frappe.db.set_value("Workspace", name, "is_hidden", 1)
		if frappe.db.exists("Desktop Icon", name):
			frappe.db.set_value("Desktop Icon", name, "hidden", 1)
	hide_in_dock()


def hide_in_dock():
	"""Dölj samma delar i HRMS-menyn i Apps-läget (frappe 16.51+), via dockans lager för hela siten.

	Ett sparat lager är hela menyn, så vi sparar alla rader i nuvarande ordning och sätter bara
	`hidden` på HIDDEN. Äldre frappe utan Dock hoppas över.
	"""
	if not frappe.db.exists("DocType", "Dock"):
		return

	from frappe.desk.doctype.dock.dock import destination, get_app_dock, resolve_app_dock, save_site_dock

	if not get_app_dock("hrms"):
		return

	rail = resolve_app_dock("hrms", upto="site", gated=False)
	rows = [
		{
			**destination(entry),
			"hidden": 1 if is_hidden_entry(entry) else entry.get("hidden", 0),
		}
		for entry in rail
	]
	if all(row["hidden"] == entry.get("hidden", 0) for row, entry in zip(rows, rail, strict=True)):
		return
	save_site_dock("hrms", rows)


def is_hidden_entry(entry) -> bool:
	return entry.get("link_type") == "Sidebar" and entry.get("link_to") in HIDDEN
