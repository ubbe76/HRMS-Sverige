import frappe

EMPLOYMENT_TYPES = ("Tillsvidare", "Provanställning", "Allmän visstid", "Vikariat", "Säsongsanställning")


def ensure_employment_types():
	for name in EMPLOYMENT_TYPES:
		if not frappe.db.exists("Employment Type", name):
			frappe.get_doc({"doctype": "Employment Type", "employee_type_name": name}).insert(
				ignore_permissions=True
			)
