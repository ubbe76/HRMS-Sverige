"""Arbetad tid och planerade skift för timavlönade i löneunderlaget."""

from datetime import date

import frappe
from erpnext.setup.doctype.employee.employee import is_holiday
from frappe.utils import flt, getdate, to_timedelta

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


def planerade_timmar(employee: str, datum) -> float:
	"""Timmar enligt planerat skift den dagen; 0 på helgdagar och utan skift."""
	datum = getdate(datum)
	if is_holiday(employee, datum, raise_exception=False):
		return 0.0
	tilldelningar = frappe.get_all(
		"Shift Assignment",
		filters={"employee": employee, "docstatus": 1, "status": "Active", "start_date": ("<=", datum)},
		fields=["shift_type", "end_date"],
		order_by="start_date desc",
	)
	skift = next(
		(t.shift_type for t in tilldelningar if not t.end_date or getdate(t.end_date) >= datum), None
	)
	skift = skift or frappe.db.get_value("Employee", employee, "default_shift")
	if not skift:
		return 0.0
	start, slut = frappe.db.get_value("Shift Type", skift, ["start_time", "end_time"])
	return skiftlangd(start, slut)


def arbetad_tid(company: str, from_date, to_date) -> list[dict]:
	"""ARB-rader från timavlönades godkända närvaro i perioden."""
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
	return [
		{
			"employee": n.employee,
			"tidkod": ARB,
			"from_date": getdate(n.attendance_date),
			"to_date": getdate(n.attendance_date),
			"timmar": round(flt(n.working_hours), 2),
			"attendance": n.name,
		}
		for n in narvaro
	]


def stamplingar_utan_narvaro(company: str, from_date, to_date) -> dict[str, list[date]]:
	"""Timavlönades dagar med stämplingar men utan godkänd närvaro."""
	anstallda = timavlonade(company)
	if not anstallda:
		return {}
	from_date, to_date = getdate(from_date), getdate(to_date)
	loggar = frappe.get_all(
		"Employee Checkin",
		filters={
			"employee": ("in", anstallda),
			"skip_auto_attendance": 0,
			"time": ("between", [f"{from_date} 00:00:00", f"{to_date} 23:59:59"]),
		},
		fields=["employee", "time"],
	)
	luckor: dict[str, set[date]] = {}
	for logg in loggar:
		datum = getdate(logg.time)
		if not frappe.db.exists(
			"Attendance", {"employee": logg.employee, "attendance_date": datum, "docstatus": 1}
		):
			luckor.setdefault(logg.employee, set()).add(datum)
	return {anstalld: sorted(dagar) for anstalld, dagar in luckor.items()}
