"""Arbetad tid och planerade skift för timavlönade i löneunderlaget."""

from datetime import date, datetime, timedelta

import frappe
from frappe.utils import flt, getdate, to_timedelta
from hrms.utils.holiday_list import get_holiday_list_for_employee

from hrms_sverige.lon.regler import Intervall, extra_tid

TIMLON = "Timlön"
ARB = "ARB"


def timavlonade(company: str) -> list[str]:
	return frappe.get_all("Employee", filters={"company": company, "loneform": TIMLON}, pluck="name")


def skiftlangd(start, slut) -> float:
	"""Skiftets längd i timmar; ett skift som slutar före eller när det börjar går över midnatt."""
	sekunder = (to_timedelta(slut) - to_timedelta(start)).total_seconds()
	if sekunder <= 0:
		sekunder += 24 * 3600
	return sekunder / 3600


def ar_helgdag(employee: str, datum, bara_roda: bool = False) -> bool:
	"""Helgdag enligt den helglista som gäller för datumet (inte för idag).

	`bara_roda` räknar bara röda dagar, inte vanliga veckoledigheter.
	"""
	datum = getdate(datum)
	lista = get_holiday_list_for_employee(employee, raise_exception=False, as_on=datum)
	if not lista:
		return False
	filters = {"parent": lista, "holiday_date": datum}
	if bara_roda:
		filters["weekly_off"] = 0
	return bool(frappe.db.exists("Holiday", filters))


def _skifttyp(employee: str, datum: date) -> str | None:
	"""Skiftet som gäller för datumet enligt tilldelning eller standardskift, helgdag eller inte."""
	tilldelningar = frappe.get_all(
		"Shift Assignment",
		filters={"employee": employee, "docstatus": 1, "status": "Active", "start_date": ("<=", datum)},
		fields=["shift_type", "end_date"],
		order_by="start_date desc",
	)
	skift = next(
		(t.shift_type for t in tilldelningar if not t.end_date or getdate(t.end_date) >= datum), None
	)
	return skift or frappe.db.get_value("Employee", employee, "default_shift")


def planerat_skift(employee: str, datum) -> tuple[datetime, datetime] | None:
	"""Det planerade skiftets start och slut den dagen; None på helgdagar och utan skift."""
	datum = getdate(datum)
	if ar_helgdag(employee, datum):
		return None
	skift = _skifttyp(employee, datum)
	if not skift:
		return None
	start, slut = frappe.db.get_value("Shift Type", skift, ["start_time", "end_time"])
	borjan = datetime.combine(datum, datetime.min.time()) + to_timedelta(start)
	return borjan, borjan + timedelta(hours=skiftlangd(start, slut))


def tid_utanfor_schema(employee: str, datum, arbetat: list[Intervall]) -> list[Intervall]:
	"""Arbetad tid utanför schemat, som blir mertid eller övertid.

	En vanlig dag är det tiden utanför skiftet. En helgdag (helg eller röd dag) är hela passet utanför
	schemat för den som har ett skift. Den som saknar skift har inget schema och ingen extra tid.
	"""
	datum = getdate(datum)
	skift = planerat_skift(employee, datum)
	if skift:
		return [e for p in arbetat for e in extra_tid(p, skift)]
	if ar_helgdag(employee, datum) and _skifttyp(employee, datum):
		return list(arbetat)
	return []


def planerade_timmar(employee: str, datum) -> float:
	"""Timmar enligt planerat skift den dagen; 0 på helgdagar och utan skift."""
	skift = planerat_skift(employee, datum)
	return (skift[1] - skift[0]).total_seconds() / 3600 if skift else 0.0


def arbetad_tid(company: str, from_date, to_date, avdrag: dict[str, float] | None = None) -> list[dict]:
	"""ARB-rader från timavlönades godkända närvaro i perioden.

	`avdrag` är timmar per närvaro som skickas som MER eller ÖT/ÖK och därför inte ska räknas som ARB.
	"""
	anstallda = timavlonade(company)
	if not anstallda:
		return []
	narvaro = frappe.get_all(
		"Attendance",
		filters={
			"company": company,
			"docstatus": 1,
			"status": ("in", ["Present", "Half Day"]),
			"attendance_date": ("between", [getdate(from_date), getdate(to_date)]),
			"employee": ("in", anstallda),
			"working_hours": (">", 0),
		},
		fields=["name", "employee", "attendance_date", "working_hours"],
		order_by="attendance_date asc",
	)
	avdrag = avdrag or {}
	rader = []
	for n in narvaro:
		timmar_arb = round(flt(n.working_hours) - avdrag.get(n.name, 0.0), 2)
		if timmar_arb > 0:
			rader.append(
				{
					"employee": n.employee,
					"tidkod": ARB,
					"from_date": getdate(n.attendance_date),
					"to_date": getdate(n.attendance_date),
					"timmar": timmar_arb,
					"attendance": n.name,
				}
			)
	return rader


def stamplingar_utan_narvaro(company: str, from_date, to_date) -> dict[str, list[date]]:
	"""Timavlönades dagar med stämplingar men utan godkänd närvaro.

	En stämpling hör till skiftets startdag (som HRMS närvaro), så nattskiftets utstämpling dagen efter räknas
	till rätt dag. Stämplingar som redan är kopplade till en närvaro hoppas över.
	"""
	anstallda = timavlonade(company)
	if not anstallda:
		return {}
	from_date, to_date = getdate(from_date), getdate(to_date)
	# en dag extra åt båda hållen: nattskift kan börja dagen före eller sluta dagen efter perioden
	fran, till = from_date - timedelta(days=1), to_date + timedelta(days=1)
	loggar = frappe.get_all(
		"Employee Checkin",
		filters={
			"employee": ("in", anstallda),
			"skip_auto_attendance": 0,
			"time": ("between", [f"{fran} 00:00:00", f"{till} 23:59:59"]),
		},
		fields=["employee", "time", "attendance", "shift_start"],
	)
	narvaro = {
		(anstalld, getdate(datum))
		for anstalld, datum in frappe.get_all(
			"Attendance",
			filters={
				"employee": ("in", anstallda),
				"docstatus": 1,
				"attendance_date": ("between", [fran, till]),
			},
			fields=["employee", "attendance_date"],
			as_list=True,
		)
	}
	luckor: dict[str, set[date]] = {}
	for logg in loggar:
		if logg.attendance:
			continue
		datum = getdate(logg.shift_start or logg.time)
		if from_date <= datum <= to_date and (logg.employee, datum) not in narvaro:
			luckor.setdefault(logg.employee, set()).add(datum)
	return {anstalld: sorted(dagar) for anstalld, dagar in luckor.items()}
