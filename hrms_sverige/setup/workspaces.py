"""Dölj HRMS-arbetsytor vi inte använder. Modulerna finns kvar och kan visas igen."""

import frappe

HIDDEN = ("Payroll", "Tax & Benefits", "Recruitment", "Expenses", "Performance", "Tenure")


def hide_unused():
	for name in HIDDEN:
		if frappe.db.exists("Workspace", name):
			frappe.db.set_value("Workspace", name, "is_hidden", 1)
		if frappe.db.exists("Desktop Icon", name):
			frappe.db.set_value("Desktop Icon", name, "hidden", 1)
