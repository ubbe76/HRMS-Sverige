"""Gemensamma testdata: ett eget testbolag och testanställda."""

import frappe

COMPANY = "_Test HR Sverige AB"
COMPANY_ABBR = "_THRS"


def ensure_test_company() -> str:
	if not frappe.db.exists("Company", COMPANY):
		frappe.get_doc(
			{
				"doctype": "Company",
				"company_name": COMPANY,
				"abbr": COMPANY_ABBR,
				"country": "Sweden",
				"default_currency": "SEK",
				"create_chart_of_accounts_based_on": "Standard Template",
				"chart_of_accounts": "Standard",
			}
		).insert()
	return COMPANY


def make_test_employee(first_name: str, **fields) -> str:
	"""Skapa (eller hämta) en anställd i testbolaget. `fields` skriver över standardvärdena."""
	ensure_test_company()
	existing = frappe.db.get_value("Employee", {"first_name": first_name, "company": COMPANY})
	if existing:
		if fields:
			frappe.db.set_value("Employee", existing, fields)
		return existing
	doc = frappe.get_doc(
		{
			"doctype": "Employee",
			"first_name": first_name,
			"company": COMPANY,
			"gender": "Female",
			"date_of_birth": "1990-05-08",
			"date_of_joining": "2020-01-01",
			"status": "Active",
		}
	)
	doc.update(fields)
	doc.insert()
	return doc.name
