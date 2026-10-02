"""Frånvaro från godkända ledighetsansökningar som rader i löneunderlaget."""

from datetime import date, timedelta

import frappe
from frappe.utils import getdate

HEL = 100
HALV = 50


def dela_upp(
	from_date: date, to_date: date, halvdag: date | None, period_from: date, period_to: date
) -> list[tuple[date, date, int]]:
	"""Delar en ledighet i intervall med omfattning och klipper vid perioden.

	En halvdag blir ett eget intervall med 50 %; dagarna före och efter får 100 %.
	"""
	if halvdag and from_date <= halvdag <= to_date:
		delar = [
			(from_date, halvdag - timedelta(days=1), HEL),
			(halvdag, halvdag, HALV),
			(halvdag + timedelta(days=1), to_date, HEL),
		]
	else:
		delar = [(from_date, to_date, HEL)]
	klippta = []
	for start, slut, omfattning in delar:
		start, slut = max(start, period_from), min(slut, period_to)
		if start <= slut:
			klippta.append((start, slut, omfattning))
	return klippta


def rader_for_period(company: str, from_date, to_date) -> list[dict]:
	"""Rader för bolagets godkända ledighetsansökningar som överlappar perioden."""
	from_date, to_date = getdate(from_date), getdate(to_date)
	ansokningar = frappe.get_all(
		"Leave Application",
		filters={
			"company": company,
			"docstatus": 1,
			"status": "Approved",
			"from_date": ("<=", to_date),
			"to_date": (">=", from_date),
		},
		fields=["name", "employee", "leave_type", "from_date", "to_date", "half_day", "half_day_date"],
	)
	rader = []
	for a in ansokningar:
		halvdag = None
		if a.half_day:
			halvdag = getdate(a.half_day_date or a.from_date)
		for start, slut, omfattning in dela_upp(
			getdate(a.from_date), getdate(a.to_date), halvdag, from_date, to_date
		):
			rader.append(
				{
					"employee": a.employee,
					"leave_type": a.leave_type,
					"from_date": start,
					"to_date": slut,
					"omfattning": omfattning,
					"leave_application": a.name,
				}
			)
	nummer = dict(
		frappe.get_all(
			"Employee",
			filters={"name": ("in", list({r["employee"] for r in rader}) or [""])},
			fields=["name", "employee_number"],
			as_list=True,
		)
	)
	rader.sort(key=lambda r: (nummer.get(r["employee"]) or "", r["employee"], r["from_date"]))
	return rader
