"""PAXml 2.0: bygger en fil med tidtransaktioner till ett lönesystem.

Känner inte till Frappe-dokument, så att arbetad tid och tillägg (del B och C) kan återanvända den.
Format: https://www.paxml.se (teknisk beskrivning PAXml 2.0, schema paxml.xsd).
"""

import re
from dataclasses import dataclass
from datetime import date, datetime
from xml.etree import ElementTree as ET

XSI = "http://www.w3.org/2001/XMLSchema-instance"
SCHEMA = "http://www.paxml.se/2.0/paxml.xsd"

# Tidkoder som schemat tillåter (tidkodTYPE i paxml.xsd)
TIDKODER = frozenset(
	"SJK SJK_KAR SJK_LÖN SJK_ERS SJK_PEN ASK HAV FPE VAB SMB UTB MIL SVE NÄR TJL SEM SEM_BET SEM_SPA SEM_OBE "
	"SEM_FÖR KOM PEM PER FAC ATK KON PAP ATF FR1 FR2 FR3 FR4 FR5 FR6 FR7 FR8 FR9 FLX SCH TS1 TS2 TS3 TS4 TS5 "
	"TS6 TS7 TS8 TS9 TID ARB MER ÖT1 ÖT2 ÖT3 ÖT4 ÖT5 ÖK1 ÖK2 ÖK3 ÖK4 ÖK5 OB1 OB2 OB3 OB4 OB5 OS1 OS2 OS3 "
	"OS4 OS5 JR1 JR2 JR3 JS1 JS2 JS3 BE1 BE2 BE3 BS1 BS2 BS3 RE1 RE2 RE3 HLG SKI LT1 LT2 LT3 LT4 LT5 LT6 "
	"LT7 LT8 LT9 NV1 NV2 NV3 NV4 NV5 NV6 NV7 NV8 NV9".split()
)


@dataclass(frozen=True)
class Huvud:
	datum: datetime
	foretagnamn: str
	programnamn: str
	foretagorgnr: str | None = None


@dataclass(frozen=True)
class Tidtransaktion:
	postid: int
	anstid: str
	tidkod: str
	from_date: date
	to_date: date
	omfattning: float | None = None
	timmar: float | None = None


def orgnr_fran_tax_id(tax_id: str | None) -> str | None:
	"""Tio siffror ur bolagets Tax ID: "SE556000000001" och "556000-0000" ger "5560000000"."""
	siffror = re.sub(r"\D", "", tax_id or "")
	if len(siffror) == 12 and siffror.endswith("01"):
		siffror = siffror[:10]
	return siffror if len(siffror) == 10 else None


def _tal(varde: float) -> str:
	return str(int(varde)) if float(varde).is_integer() else f"{varde:g}"


def bygg_paxml(huvud: Huvud, transaktioner: list[Tidtransaktion]) -> bytes:
	ET.register_namespace("xsi", XSI)
	rot = ET.Element("paxml", {f"{{{XSI}}}noNamespaceSchemaLocation": SCHEMA})

	header = ET.SubElement(rot, "header")
	for tagg, varde in (
		("version", "2.0"),
		("format", "LÖNIN"),
		("datum", huvud.datum.replace(microsecond=0).isoformat()),
		("foretagorgnr", huvud.foretagorgnr),
		("foretagnamn", huvud.foretagnamn),
		("programnamn", huvud.programnamn),
	):
		if varde:
			ET.SubElement(header, tagg).text = varde

	tidtransaktioner = ET.SubElement(rot, "tidtransaktioner")
	for t in transaktioner:
		tidtrans = ET.SubElement(tidtransaktioner, "tidtrans", {"anstid": t.anstid, "postid": str(t.postid)})
		ET.SubElement(tidtrans, "tidkod").text = t.tidkod
		if t.timmar is not None:
			# PAXml: timmar får bara anges på ett enskilt datum
			if t.from_date != t.to_date:
				raise ValueError(f"Postid {t.postid}: timmar kan bara gälla en dag")
			ET.SubElement(tidtrans, "datum").text = t.from_date.isoformat()
			ET.SubElement(tidtrans, "timmar").text = f"{t.timmar:.2f}"
			continue
		if t.from_date == t.to_date:
			ET.SubElement(tidtrans, "datum").text = t.from_date.isoformat()
		else:
			ET.SubElement(tidtrans, "datumfrom").text = t.from_date.isoformat()
			ET.SubElement(tidtrans, "datumtom").text = t.to_date.isoformat()
		ET.SubElement(tidtrans, "omfattning").text = _tal(t.omfattning)

	ET.indent(rot)
	return ET.tostring(rot, encoding="UTF-8", xml_declaration=True)
