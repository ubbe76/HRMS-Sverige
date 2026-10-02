"""Övertid, mertid och OB för löneunderlaget, räknat ur närvarons klockslag."""

from datetime import date

import frappe
from frappe.utils import flt, get_datetime, getdate, to_timedelta
from hrms.utils.holiday_list import get_holiday_list_for_employee

from hrms_sverige.lon.regler import OB, OVERTID, Tidsregel, dela_mertid, extra_tid, fordela, timmar
from hrms_sverige.lon.tid import planerat_skift

DAGFALT = ("man", "tis", "ons", "tor", "fre", "lor", "son")
NARVARO_STATUS = ("Present", "Half Day")
KOMPTID = "Komptid"


def _tid(varde):
	return (get_datetime("2000-01-01") + to_timedelta(varde)).time()


def regler_fran_installningar() -> list[Tidsregel]:
	inst = frappe.get_single("Loneinstallningar")
	return [
		Tidsregel(
			typ=r.typ,
			niva=int(r.niva),
			dagar=frozenset(i for i, falt in enumerate(DAGFALT) if r.get(falt)),
			helgdag=bool(r.helgdag),
			fran=_tid(r.fran),
			till=_tid(r.till),
		)
		for r in inst.tidsregler
	]


def heltid_per_dag() -> float:
	return flt(frappe.db.get_single_value("Loneinstallningar", "heltid_per_dag")) or 8.0


def helgdagar(employee: str, from_date, to_date) -> set[date]:
	"""Röda dagar (inte vanliga veckoledigheter) i den anställdes helglista under perioden."""
	lista = get_holiday_list_for_employee(employee, raise_exception=False, as_on=from_date)
	if not lista:
		return set()
	return {
		getdate(d)
		for d in frappe.get_all(
			"Holiday",
			filters={
				"parent": lista,
				"weekly_off": 0,
				"holiday_date": ("between", [getdate(from_date), getdate(to_date)]),
			},
			pluck="holiday_date",
		)
	}


def overtidsval(attendance: str, employee: str) -> str:
	"""Valet på den senaste utstämplingen för närvaron, annars den anställdes förval."""
	val = frappe.get_all(
		"Employee Checkin",
		filters={"attendance": attendance, "log_type": "OUT", "overtidsersattning": ("is", "set")},
		pluck="overtidsersattning",
		order_by="time desc",
		limit=1,
	)
	return (val[0] if val else None) or frappe.db.get_value("Employee", employee, "overtid_som") or "Pengar"


def _narvaro(company: str, from_date, to_date, med_klockslag: bool) -> list:
	filters = {
		"company": company,
		"docstatus": 1,
		"status": ("in", NARVARO_STATUS),
		"attendance_date": ("between", [getdate(from_date), getdate(to_date)]),
	}
	if med_klockslag:
		filters.update({"in_time": ("is", "set"), "out_time": ("is", "set")})
	return frappe.get_all(
		"Attendance",
		filters=filters,
		fields=["name", "employee", "attendance_date", "in_time", "out_time", "working_hours"],
		order_by="attendance_date asc",
	)


def tillaggsrader(company: str, from_date, to_date) -> list[dict]:
	"""MER, ÖT/ÖK och OB per närvaro med klockslag, för alla anställda."""
	regler = regler_fran_installningar()
	ob_regler = [r for r in regler if r.typ == OB]
	ot_regler = [r for r in regler if r.typ == OVERTID]
	tak = heltid_per_dag()
	rader = []
	helg_cache: dict[str, set[date]] = {}
	for n in _narvaro(company, from_date, to_date, med_klockslag=True):
		dag = getdate(n.attendance_date)
		arbetat = (get_datetime(n.in_time), get_datetime(n.out_time))
		if arbetat[1] <= arbetat[0]:
			continue
		if n.employee not in helg_cache:
			helg_cache[n.employee] = helgdagar(n.employee, from_date, to_date)
		helg = helg_cache[n.employee]
		extra = extra_tid(arbetat, planerat_skift(n.employee, dag))
		grad = flt(frappe.db.get_value("Employee", n.employee, "sysselsattningsgrad"))
		if 0 < grad < 100:
			inom = timmar([arbetat]) - timmar(extra)
			mertid, overtid = dela_mertid(extra, inom, tak)
		else:
			mertid, overtid = [], extra
		prefix = "ÖK" if overtidsval(n.name, n.employee) == KOMPTID else "ÖT"
		koder = [("MER", timmar(mertid))]
		koder += [(f"{prefix}{niva}", h) for niva, h in sorted(fordela(overtid, ot_regler, helg, 1).items())]
		koder += [(f"OB{niva}", h) for niva, h in sorted(fordela([arbetat], ob_regler, helg).items())]
		for tidkod, h in koder:
			if round(h, 2) > 0:
				rader.append(
					{
						"employee": n.employee,
						"tidkod": tidkod,
						"from_date": dag,
						"to_date": dag,
						"timmar": round(h, 2),
						"attendance": n.name,
					}
				)
	return rader


def narvaro_utan_klockslag(company: str, from_date, to_date) -> dict[str, list[date]]:
	"""Närvaro med arbetade timmar men utan in- eller utstämplingstid; där räknas varken övertid eller OB."""
	saknas: dict[str, list[date]] = {}
	for n in _narvaro(company, from_date, to_date, med_klockslag=False):
		if flt(n.working_hours) > 0 and not (n.in_time and n.out_time):
			saknas.setdefault(n.employee, []).append(getdate(n.attendance_date))
	return saknas
