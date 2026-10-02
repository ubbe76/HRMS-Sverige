"""Stämplingssidan: gäst-API för registrerade enheter, med anställningsnummer och PIN-kod."""

import hashlib

import frappe

from hrms_sverige.lon.pin import hasha_pin, kontrollera_pin_regler

HR_ROLLER = ("HR Manager", "HR User")


def nyckel_hash(nyckel: str) -> str:
	return hashlib.sha256((nyckel or "").encode()).hexdigest()


@frappe.whitelist()
def satt_pin(employee: str, pin: str) -> None:
	"""HR sätter en PIN-kod; den anställde måste byta den vid första stämplingen."""
	frappe.only_for(HR_ROLLER)
	kontrollera_pin_regler(pin)
	frappe.db.set_value(
		"Employee",
		employee,
		{
			"stampel_pin_hash": hasha_pin(pin),
			"stampel_pin_maste_bytas": 1,
			"stampel_fel_forsok": 0,
			"stampel_last_till": None,
		},
	)
