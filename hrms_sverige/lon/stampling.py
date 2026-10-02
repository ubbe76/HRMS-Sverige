"""Stämplingssidan: gäst-API för registrerade enheter, med anställningsnummer och PIN-kod."""

import hashlib
from datetime import timedelta
from functools import wraps

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import cint, get_datetime, now_datetime

from hrms_sverige.lon.pin import hasha_pin, kontrollera_pin_regler, pin_stammer
from hrms_sverige.lon.regler import extra_tid, timmar
from hrms_sverige.lon.tid import planerat_skift

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


FEL_ENHET = "Enheten är inte registrerad. Be HR om en ny länk."
FEL_INLOGGNING = "Fel anställningsnummer eller PIN-kod"
FEL_LAST = "För många felaktiga försök. Försök igen senare."
FEL_BYT_PIN = "Byt PIN-kod först."
FEL_ENHET_SPARRAD = "Enheten är tillfälligt spärrad efter för många felaktiga försök. Kontakta HR."
MAX_FORSOK = 5
LASTID = timedelta(minutes=15)
MAX_FEL_PER_ENHET = 10
ENHET_SPARRTID = 15 * 60  # sekunder


class Nekad(Exception):
	pass


def _svar(fn):
	"""Nekanden returneras som {"fel": ...}, så att räknaren för felaktiga försök sparas (inget undantag)."""

	@wraps(fn)  # behåller signaturen, som Frappe använder för att kontrollera argumenten
	def wrapper(*args, **kwargs):
		try:
			return fn(*args, **kwargs)
		except Nekad as nekad:
			return {"fel": _(str(nekad))}
		except frappe.ValidationError as fel:
			frappe.clear_last_message()
			return {"fel": str(fel)}

	return wrapper


def _enhet(nyckel: str) -> str:
	namn = frappe.db.get_value("Stamplingsenhet", {"nyckel_hash": nyckel_hash(nyckel), "aktiv": 1})
	if not nyckel or not namn:
		raise Nekad(FEL_ENHET)
	if int(frappe.cache.get(_enhet_fel_nyckel(namn)) or 0) >= MAX_FEL_PER_ENHET:
		raise Nekad(FEL_ENHET_SPARRAD)
	frappe.db.set_value("Stamplingsenhet", namn, "senast_anvand", now_datetime(), update_modified=False)
	return namn


def _enhet_fel_nyckel(namn: str) -> str:
	return frappe.cache.make_key(f"stampla:fel:{namn}")


def _rakna_enhetsfel(namn: str) -> None:
	"""Felaktiga försök per enhet, oavsett anställningsnummer: stoppar gissning mot många anställda."""
	nyckel = _enhet_fel_nyckel(namn)
	if frappe.cache.incr(nyckel) == 1:
		frappe.cache.expire(nyckel, ENHET_SPARRTID)


def _anstalld(anstallningsnummer: str, pin: str, enhet: str) -> frappe._dict:
	rad = frappe.db.get_value(
		"Employee",
		{"employee_number": (anstallningsnummer or "").strip(), "status": "Active"},
		[
			"name",
			"first_name",
			"stampel_pin_hash",
			"stampel_pin_maste_bytas",
			"stampel_fel_forsok",
			"stampel_last_till",
			"overtid_som",
		],
		as_dict=True,
	)
	if not rad:
		_rakna_enhetsfel(enhet)
		raise Nekad(FEL_INLOGGNING)
	nu = now_datetime()
	if rad.stampel_last_till and get_datetime(rad.stampel_last_till) > nu:
		raise Nekad(FEL_LAST)
	if not pin_stammer(pin, rad.stampel_pin_hash):
		_rakna_enhetsfel(enhet)
		# Räknas upp i databasen, så att samtidiga felaktiga försök inte skriver över varandra
		frappe.db.sql(
			"update `tabEmployee` set stampel_fel_forsok = ifnull(stampel_fel_forsok, 0) + 1 where name = %s",
			rad.name,
		)
		forsok = frappe.db.get_value("Employee", rad.name, "stampel_fel_forsok")
		if forsok >= MAX_FORSOK:
			frappe.db.set_value(
				"Employee",
				rad.name,
				{"stampel_fel_forsok": 0, "stampel_last_till": nu + LASTID},
				update_modified=False,
			)
		raise Nekad(FEL_INLOGGNING)
	if rad.stampel_fel_forsok or rad.stampel_last_till:
		frappe.db.set_value(
			"Employee", rad.name, {"stampel_fel_forsok": 0, "stampel_last_till": None}, update_modified=False
		)
	return rad


def _senaste(employee: str, nu) -> frappe._dict | None:
	rader = frappe.get_all(
		"Employee Checkin",
		filters={"employee": employee, "time": ("between", [nu - timedelta(hours=24), nu])},
		fields=["log_type", "time"],
		order_by="time desc",
		limit=1,
	)
	return rader[0] if rader else None


DUBBELTRYCK = timedelta(seconds=60)
RIKTNINGAR = ("IN", "OUT")
ERSATTNINGAR = ("Pengar", "Komptid")


def _fraga_overtid(employee: str, nu) -> tuple[bool, int]:
	"""Fråga om pengar eller komptid när passet har mer extra tid än gränsen utanför skiftet."""
	instampling = frappe.get_all(
		"Employee Checkin",
		filters={"employee": employee, "log_type": "IN", "time": ("between", [nu - timedelta(hours=24), nu])},
		pluck="time",
		order_by="time desc",
		limit=1,
	)
	if not instampling:
		return False, 0
	start = get_datetime(instampling[0])
	skift = planerat_skift(employee, start.date())
	if not skift:
		return False, 0
	minuter = round(timmar(extra_tid((start, nu), skift)) * 60)
	grans = cint(frappe.db.get_single_value("Loneinstallningar", "overtid_fraga_minuter") or 15)
	return minuter > grans, minuter


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(key="enhet", limit=30, seconds=60)
@_svar
def identifiera(enhet: str, anstallningsnummer: str, pin: str) -> dict:
	namn = _enhet(enhet)
	rad = _anstalld(anstallningsnummer, pin, namn)
	if rad.stampel_pin_maste_bytas:
		return {"fornamn": rad.first_name, "maste_byta_pin": True}
	nu = now_datetime()
	senaste = _senaste(rad.name, nu)
	riktning = "OUT" if senaste and senaste.log_type == "IN" else "IN"
	fraga, minuter = _fraga_overtid(rad.name, nu) if riktning == "OUT" else (False, 0)
	return {
		"fornamn": rad.first_name,
		"riktning": riktning,
		"maste_byta_pin": False,
		"fraga_overtid": fraga,
		"forval": rad.overtid_som or "Pengar",
		"extra_minuter": minuter,
	}


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(key="enhet", limit=30, seconds=60)
@_svar
def byt_pin(enhet: str, anstallningsnummer: str, pin: str, ny_pin: str) -> dict:
	namn = _enhet(enhet)
	rad = _anstalld(anstallningsnummer, pin, namn)
	kontrollera_pin_regler(ny_pin, gammal=pin)
	frappe.db.set_value(
		"Employee",
		rad.name,
		{"stampel_pin_hash": hasha_pin(ny_pin), "stampel_pin_maste_bytas": 0},
		update_modified=False,
	)
	return {"ok": True}


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(key="enhet", limit=30, seconds=60)
@_svar
def stampla(
	enhet: str, anstallningsnummer: str, pin: str, log_type: str, overtidsersattning: str | None = None
) -> dict:
	namn = _enhet(enhet)
	rad = _anstalld(anstallningsnummer, pin, namn)
	if rad.stampel_pin_maste_bytas:
		raise Nekad(FEL_BYT_PIN)
	if log_type not in RIKTNINGAR or (overtidsersattning and overtidsersattning not in ERSATTNINGAR):
		raise Nekad("Ogiltig stämpling.")
	nu = now_datetime()
	senaste = _senaste(rad.name, nu)
	# Låset i Redis stoppar även samtidiga tryck, som ännu inte syns i databasen
	las = frappe.cache.make_key(f"stampla:tryck:{rad.name}:{int(nu.timestamp()) // 60}")
	if (senaste and nu - get_datetime(senaste.time) < DUBBELTRYCK) or not frappe.cache.set(
		las, 1, nx=True, ex=120
	):
		raise Nekad("Du stämplade nyss.")
	frappe.get_doc(
		{
			"doctype": "Employee Checkin",
			"employee": rad.name,
			"log_type": log_type,
			"time": nu,
			"device_id": namn,
			"overtidsersattning": overtidsersattning if log_type == "OUT" else None,
		}
	).insert(ignore_permissions=True)
	return {"fornamn": rad.first_name, "log_type": log_type, "tid": nu.strftime("%H:%M")}
