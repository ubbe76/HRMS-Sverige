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
	omfattning: float


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
		if t.from_date == t.to_date:
			ET.SubElement(tidtrans, "datum").text = t.from_date.isoformat()
		else:
			ET.SubElement(tidtrans, "datumfrom").text = t.from_date.isoformat()
			ET.SubElement(tidtrans, "datumtom").text = t.to_date.isoformat()
		ET.SubElement(tidtrans, "omfattning").text = _tal(t.omfattning)

	ET.indent(rot)
	return ET.tostring(rot, encoding="UTF-8", xml_declaration=True)
