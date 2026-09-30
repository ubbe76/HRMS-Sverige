"""Svenska personnummer och samordningsnummer (dag + 60), med kontrollsiffra enligt Luhn."""

import json
import re
from datetime import date

import frappe
from frappe import _
from frappe.utils import getdate

PATTERN = re.compile(r"^(\d{2})?(\d{2})(\d{2})(\d{2})([-+]?)(\d{4})$")
# Tankstreck och minustecken som följer med när numret klistras in från t.ex. Word
DASHES = re.compile("[\u2010-\u2015\u2212]")
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


def _years_before(day: date, years: int) -> date:
	try:
		return day.replace(year=day.year - years)
	except ValueError:  # 29 februari
		return day.replace(year=day.year - years, day=28)


def normalize(value: str, today: date | None = None) -> str:
	"""Returnera numret som ÅÅÅÅMMDD-NNNN eller kasta OgiltigtPersonnummer.

	Tio siffror: seklet väljs så att födelsedatumet inte ligger i framtiden; "+" betyder 100 år eller äldre.
	"""
	today = today or getdate()
	match = PATTERN.match(DASHES.sub("-", re.sub(r"\s", "", value or "")))
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
		born = birth_date(year)
		if born > today:
			raise OgiltigtPersonnummer(value)
		if separator == "+" and born > _years_before(today, 100):
			raise OgiltigtPersonnummer(value)  # "+" betyder 100 år eller äldre
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
	if not 0 <= (doc.get("sysselsattningsgrad") or 0) <= 100:
		frappe.throw(_("Sysselsättningsgraden ska vara mellan 0 och 100 %."))
	if doc.get("personnummer"):
		other = frappe.db.get_value(
			"Employee", {"personnummer": doc.personnummer, "name": ("!=", doc.name)}, "name"
		)
		if other:
			frappe.throw(_("Personnumret används redan av {0}.").format(other))


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
