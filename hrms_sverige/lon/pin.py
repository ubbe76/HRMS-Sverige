"""PIN-koder för stämpling: regler och hashning. Lagras aldrig i klartext."""

import re
from itertools import pairwise

import frappe
from frappe import _
from frappe.utils.password import passlibctx


def kontrollera_pin_regler(pin: str, gammal: str | None = None) -> None:
	if not re.fullmatch(r"\d{4,6}", pin or ""):
		frappe.throw(_("PIN-koden ska vara 4 till 6 siffror."))
	if len(set(pin)) == 1:
		frappe.throw(_("PIN-koden får inte bara vara samma siffra."))
	if _for_vanlig(pin):
		frappe.throw(_("PIN-koden är för lätt att gissa. Undvik följder som 1234 och vanliga koder."))
	if gammal is not None and pin == gammal:
		frappe.throw(_("Den nya PIN-koden måste skilja sig från den gamla."))


# Vanliga koder utöver stigande och fallande följder (2580 är mittkolumnen på en knappsats)
VANLIGA = {"2580", "0852", "1212", "1122", "1010", "6969", "1004", "2000", "7777", "1313"}


def _for_vanlig(pin: str) -> bool:
	steg = {int(b) - int(a) for a, b in pairwise(pin)}
	return pin in VANLIGA or steg in ({1}, {-1})


def hasha_pin(pin: str) -> str:
	return passlibctx.hash(pin)


def pin_stammer(pin: str, pin_hash: str | None) -> bool:
	if not pin_hash or not pin:
		return False
	try:
		return passlibctx.verify(pin, pin_hash)
	except ValueError:
		return False
