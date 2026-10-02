"""Övertid, mertid och OB för löneunderlaget, räknat ur närvarons klockslag."""

import frappe
from frappe.utils import flt, get_datetime, to_timedelta

from hrms_sverige.lon.regler import Tidsregel

DAGFALT = ("man", "tis", "ons", "tor", "fre", "lor", "son")


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
