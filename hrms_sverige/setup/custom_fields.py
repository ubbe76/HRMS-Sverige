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
			{
				"fieldname": "loneform",
				"label": _("Löneform"),
				"fieldtype": "Select",
				"options": "\nMånadslön\nTimlön",
				"insert_after": "sysselsattningsgrad",
				"description": _(
					"Timlön: arbetad tid och frånvaro skickas i timmar i löneunderlaget. Tomt räknas som månadslön."
				),
			},
			{
				"fieldname": "overtid_som",
				"label": _("Övertid som"),
				"fieldtype": "Select",
				"options": "Pengar\nKomptid",
				"default": "Pengar",
				"insert_after": "loneform",
				"description": _(
					"Förval när utstämplingen inte anger något: övertid som pengar (ÖT) eller komptid (ÖK)."
				),
			},
			{
				"fieldname": "stampel_utan_pin",
				"label": _("Stämpla utan PIN"),
				"fieldtype": "Check",
				"permlevel": PERSONNUMMER_PERMLEVEL,
				"insert_after": "overtid_som",
				"description": _(
					"Den anställde stämplar med bara anställningsnumret. Vem som helst vid enheten kan då "
					"stämpla åt den anställde. Utan bocken krävs en PIN-kod (Stämpling > Sätt PIN)."
				),
			},
			{
				"fieldname": "stampel_pin_maste_bytas",
				"label": _("PIN måste bytas"),
				"fieldtype": "Check",
				"read_only": 1,
				"permlevel": PERSONNUMMER_PERMLEVEL,
				"insert_after": "stampel_utan_pin",
				"description": _(
					"Sätts när HR sätter en PIN-kod; den anställde byter vid första stämplingen."
				),
			},
			{
				"fieldname": "stampel_last_till",
				"label": _("Stämpling låst till"),
				"fieldtype": "Datetime",
				"read_only": 1,
				"permlevel": PERSONNUMMER_PERMLEVEL,
				"insert_after": "stampel_pin_maste_bytas",
			},
			{
				"fieldname": "stampel_pin_hash",
				"label": _("PIN-hash"),
				"fieldtype": "Data",
				"hidden": 1,
				"read_only": 1,
				"permlevel": PERSONNUMMER_PERMLEVEL,
				"insert_after": "stampel_last_till",
			},
			{
				"fieldname": "stampel_fel_forsok",
				"label": _("Felaktiga PIN-försök"),
				"fieldtype": "Int",
				"hidden": 1,
				"read_only": 1,
				"permlevel": PERSONNUMMER_PERMLEVEL,
				"insert_after": "stampel_pin_hash",
			},
		],
		"Employee Checkin": [
			{
				"fieldname": "overtidsersattning",
				"label": _("Övertidsersättning"),
				"fieldtype": "Select",
				"options": "\nPengar\nKomptid",
				"insert_after": "log_type",
				"description": _(
					"Väljs vid utstämpling utanför skiftet. Tomt: den anställdes förval gäller."
				),
			},
		],
		"Leave Type": [
			{
				"fieldname": "paxml_tidkod",
				"label": _("PAXml-tidkod"),
				"fieldtype": "Data",
				"insert_after": "leave_type_name",
				"description": _(
					"Kod i löneunderlaget till lönesystemet, t.ex. SEM, SJK eller VAB. "
					"Lönesystemet kopplar koden till rätt löneart."
				),
			},
		],
	}


def create_custom_fields():
	# update=False: skapa bara saknade fält, så att en administratörs etiketter och beskrivningar ligger kvar
	_create_custom_fields(get_custom_fields(), update=False)


def ensure_personnummer_permissions():
	"""Läs- och skrivrätt på permlevel 1 för HR-rollerna. Körs bara vid installation/uppsättning,
	inte vid migrate, så att en administratörs ändringar ligger kvar.

	Obs: första gången kopieras Employees standardbehörigheter till Custom DocPerm (Frappes sätt att
	anpassa behörigheter); senare ändringar i HRMS/ERPNext:s standardbehörigheter för Employee
	slår då inte igenom automatiskt."""
	for role in HR_ROLES:
		if not frappe.db.exists(
			"Custom DocPerm", {"parent": "Employee", "role": role, "permlevel": PERSONNUMMER_PERMLEVEL}
		):
			add_permission("Employee", role, PERSONNUMMER_PERMLEVEL)
			update_permission_property("Employee", role, PERSONNUMMER_PERMLEVEL, "write", 1)
