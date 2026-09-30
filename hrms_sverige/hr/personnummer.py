"""Svenska personnummer och samordningsnummer (dag + 60), med kontrollsiffra enligt Luhn."""

import json
import re
from datetime import date

import frappe
from frappe import _

PATTERN = re.compile(r"^(\d{2})?(\d{2})(\d{2})(\d{2})([-+]?)(\d{4})$")
SAMORDNING_OFFSET = 60


class OgiltigtPersonnummer(ValueError):
	pass


def luhn_ok(digits: str) -> bool:
	"""Kontrollsiffra för de tio sista siffrorna (ÅÅMMDDNNNN)."""
	total = 0
	for i, ch in enumerate(digits):
		n = int(ch) * (2 if i % 2 == 0 else 1)
		total += n - 9 if n > 9 else n
	return total % 10 == 0


def normalize(value: str, today: date | None = None) -> str:
	"""Returnera numret som ÅÅÅÅMMDD-NNNN eller kasta OgiltigtPersonnummer.

	Tio siffror: seklet väljs så att födelsedatumet inte ligger i framtiden; "+" betyder 100 år eller äldre.
	"""
	today = today or date.today()
	match = PATTERN.match(re.sub(r"\s", "", value or ""))
	if not match:
		raise OgiltigtPersonnummer(value)
	century, yy, mm, dd, separator, tail = match.groups()

	day = int(dd)
	if day > SAMORDNING_OFFSET:
		day -= SAMORDNING_OFFSET

	def birth_date(year: int) -> date:
		try:
			return date(year, int(mm), day)
		except ValueError:
			raise OgiltigtPersonnummer(value) from None

	if century:
		year = int(century + yy)
		if birth_date(year) > today:
			raise OgiltigtPersonnummer(value)
	else:
		year = today.year // 100 * 100 + int(yy)
		if birth_date(year) > today:
			year -= 100
		if separator == "+":
			year -= 100
		birth_date(year)

	if not luhn_ok(yy + mm + dd + tail):
		raise OgiltigtPersonnummer(value)
	return f"{year:04d}{mm}{dd}-{tail}"


HELTID_DAGAR = 5


def validate_employee(doc, method=None):
	"""Employee.validate: normalisera personnummer och kontrollera arbetsdagar per vecka."""
	if doc.get("personnummer"):
		try:
			doc.personnummer = normalize(doc.personnummer)
		except OgiltigtPersonnummer:
			frappe.throw(_("Ogiltigt personnummer: {0}").format(doc.personnummer))
	if doc.get("arbetsdagar_per_vecka") and not 1 <= doc.arbetsdagar_per_vecka <= HELTID_DAGAR:
		frappe.throw(_("Arbetsdagar per vecka ska vara mellan 1 och {0}.").format(HELTID_DAGAR))


def strip_from_version(doc, method=None):
	"""Version.before_insert: ändringshistoriken skickas till alla som kan öppna den anställde,
	även utan HR-roll, så personnummer får inte lagras där."""
	if doc.ref_doctype != "Employee" or not doc.data:
		return
	data = json.loads(doc.data)
	changed = data.get("changed") or []
	kept = [row for row in changed if row[0] != "personnummer"]
	if len(kept) != len(changed):
		data["changed"] = kept
		doc.data = frappe.as_json(data)
