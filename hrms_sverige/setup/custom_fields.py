import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields as _create_custom_fields
from frappe.permissions import add_permission, update_permission_property

# Roller som får läsa och ändra personnummer (permlevel 1 på Employee)
HR_ROLES = ("HR Manager", "HR User")
PERSONNUMMER_PERMLEVEL = 1


def get_custom_fields():
	return {
		"Employee": [
			{
				"fieldname": "personnummer",
				"label": _("Personnummer"),
				"fieldtype": "Data",
				"insert_after": "date_of_birth",
				"permlevel": PERSONNUMMER_PERMLEVEL,
				"description": _("ÅÅÅÅMMDD-NNNN. Samordningsnummer godkänns."),
			},
			{
				"fieldname": "arbetsdagar_per_vecka",
				"label": _("Arbetsdagar per vecka"),
				"fieldtype": "Int",
				"insert_after": "employment_type",
				"description": _("1 till 5. Tomt räknas som 5. Styr antalet semesterdagar vid deltid."),
			},
			{
				"fieldname": "sysselsattningsgrad",
				"label": _("Sysselsättningsgrad (%)"),
				"fieldtype": "Percent",
				"insert_after": "arbetsdagar_per_vecka",
			},
		],
	}


def create_custom_fields():
	_create_custom_fields(get_custom_fields(), update=True)
	for role in HR_ROLES:
		if not frappe.db.exists(
			"Custom DocPerm", {"parent": "Employee", "role": role, "permlevel": PERSONNUMMER_PERMLEVEL}
		):
			add_permission("Employee", role, PERSONNUMMER_PERMLEVEL)
		update_permission_property("Employee", role, PERSONNUMMER_PERMLEVEL, "write", 1)
