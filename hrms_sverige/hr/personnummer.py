"""Svenska personnummer och samordningsnummer (dag + 60), med kontrollsiffra enligt Luhn."""

import re
from datetime import date

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
