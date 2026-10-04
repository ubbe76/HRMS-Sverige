"""Anställningsnumret ska synas på den anställde, eftersom löneunderlaget kräver det."""

from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def visa_anstallningsnummer(doc=None, method=None):
	"""HR Settings.on_update och after_migrate: HRMS döljer fältet när anställda namnges med nummerserie."""
	make_property_setter(
		"Employee", "employee_number", "hidden", 0, "Check", validate_fields_for_doctype=False
	)
