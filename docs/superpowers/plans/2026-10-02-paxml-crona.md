# Löneunderlag till Crona Lön (PAXml), del A – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ett löneunderlag per bolag och kalendermånad som gör om godkänd frånvaro till en PAXml 2.0-fil som Crona Lön kan läsa in.

**Architecture:** En ren PAXml-byggare (`lon/paxml.py`, inga Frappe-beroenden) och en ren uppdelningsfunktion för ledigheter (`lon/franvaro.py: dela_upp`) testas utan databas. Dokumentet `Loneunderlag` (inskickbart, barntabell `Loneunderlag Rad`) hämtar frånvaro via `franvaro.rader_for_period`, kontrollerar vid godkännande och levererar filen via en whitelistad nedladdning. Frånvarotypen får fältet `paxml_tidkod`, som förifylls vid uppsättning och `migrate`.

**Tech Stack:** Frappe 16 / HRMS 16 (Python 3.14), `xml.etree.ElementTree` för XML, `lxml` (finns i miljön) för schemavalidering i tester.

**Spec:** `docs/superpowers/specs/2026-10-02-paxml-crona-design.md`

## Global Constraints

- Appen är `hrms_sverige` i `apps/hrms_sverige` (eget git-repo, gren `version-16`). Arbeta på grenen `feat/paxml-crona`.
- Alla `bench`-kommandon körs från `/home/ubbe/ERPNext/my-frappe-bench`. Tester körs **endast** på `test-erp.local`, aldrig på `svensk-erp.local` (produktion).
- Benchen delas med produktionssiten: byt tillbaka till `version-16` (`git -C apps/hrms_sverige checkout version-16`) när du lämnar arbetet, och kör aldrig `migrate` på `svensk-erp.local` från grenen.
- Kodstil: tabbar, radlängd 110, ruff (pre-commit körs vid commit; om den formaterar om en fil, `git add` igen och committa på nytt).
- Etiketter, meddelanden och kommentarer på svenska. Dokumentnamn i ASCII (`Loneunderlag`), svenska visningsnamn i `hrms_sverige/locale/sv.po`.
- PAXml: version `2.0`, schema `http://www.paxml.se/2.0/paxml.xsd`, teckenkodning UTF-8, `<format>LÖNIN</format>`.
- Tidkoder: Semester → SEM, Sjukfrånvaro → SJK, VAB → VAB, Föräldraledighet → FPE, Tjänstledighet → TJL, Kompledighet → KOM.
- Omfattning 100 för hela dagar, 50 för halvdag. Inga timmar i del A.
- `anstid` = Employee `employee_number`. Behörigheter: HR Manager skapar/godkänner/makulerar, HR User skapar och läser.
- Commit-meddelanden på engelska och avslutas med:
  ```
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_016yYYj5agMiCoxsTCe4usfY
  ```

## Review Focus

1. **Ledighet över månadsskifte med halvdag i andra månaden** – bara delarna inom perioden ska komma med, och halvdagen ska inte dyka upp i fel månad. Test i Task 3 (`test_halvdag_utanfor_perioden_klipps_bort`).
2. **Tidkod med små bokstäver eller blanksteg** (`" sem "`) – ska skickas som `SEM`. Test i Task 4 (`test_tidkod_normaliseras`).
3. **Ledighetsansökan makuleras efter Hämta frånvaro men före godkännande** – godkännandet ska stoppas med uppmaning att hämta igen, inte skicka en makulerad frånvaro. Test i Task 4 (`test_makulerad_ansokan_stoppar`).
4. **Bolagets Tax ID i olika format** (`SE556000000001`, `556000-0000`, tomt) – rätt tiosiffrigt organisationsnummer eller inget element. Test i Task 2 (`test_orgnr_fran_tax_id`).
5. **Hämta frånvaro körs två gånger** – raderna ska ersättas, inte dubbleras. Test i Task 4 (`test_hamta_tva_ganger_dubblerar_inte`).

---

## Filkarta

| Fil | Ansvar |
|---|---|
| `hrms_sverige/setup/custom_fields.py` (ändras) | Fältet `paxml_tidkod` på Leave Type |
| `hrms_sverige/setup/leave.py` (ändras) | `PAXML_TIDKODER`, `ensure_paxml_tidkoder()` |
| `hrms_sverige/setup/install.py` (ändras) | Anropar `ensure_paxml_tidkoder()` i `setup_all` och `after_migrate` |
| `hrms_sverige/modules.txt` (ändras) | Ny modul `Lön` |
| `hrms_sverige/lon/__init__.py`, `lon/doctype/__init__.py` (nya) | Modulpaket |
| `hrms_sverige/lon/paxml.py` (ny) | Bygger PAXml-XML från dataklasser; orgnr ur Tax ID |
| `hrms_sverige/lon/franvaro.py` (ny) | `dela_upp`, `rader_for_period`, varningshooken |
| `hrms_sverige/lon/doctype/loneunderlag/*` (nya) | Dokumentet, formulärskript, nedladdning |
| `hrms_sverige/lon/doctype/loneunderlag_rad/*` (nya) | Barntabellen |
| `hrms_sverige/hooks.py` (ändras) | `doc_events` för Leave Application |
| `hrms_sverige/locale/sv.po` (ändras) | Visningsnamn för dokumenten |
| `hrms_sverige/tests/fixtures/paxml-2.0.xsd` (ny) | Schemat för validering i tester |
| `hrms_sverige/tests/test_paxml.py`, `test_franvaro.py`, `test_loneunderlag.py` (nya), `test_leave.py`, `utils.py` (ändras) | Tester |
| `README.md`, `CHANGELOG.md` (ändras); docs-repot `docs/personal/loneunderlag.md`, `mkdocs.yml` | Dokumentation |

---

### Task 1: PAXml-tidkod på frånvarotypen

**Files:**
- Modify: `hrms_sverige/setup/custom_fields.py` (i `get_custom_fields()`)
- Modify: `hrms_sverige/setup/leave.py`
- Modify: `hrms_sverige/setup/install.py` (`setup_all`, `after_migrate`)
- Test: `hrms_sverige/tests/test_leave.py`

**Interfaces:**
- Produces: custom field `Leave Type.paxml_tidkod` (Data); `hrms_sverige.setup.leave.PAXML_TIDKODER: dict[str, str]`; `hrms_sverige.setup.leave.ensure_paxml_tidkoder() -> None`.

- [ ] **Step 1: Skapa grenen**

```bash
cd /home/ubbe/ERPNext/my-frappe-bench/apps/hrms_sverige
git fetch -q && git checkout feat/paxml-crona && git merge -q --ff-only origin/version-16 || git rebase origin/version-16
```

- [ ] **Step 2: Skriv det fallerande testet** – lägg till sist i `hrms_sverige/tests/test_leave.py`:

```python
class TestPaxmlTidkoder(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		from hrms_sverige.setup.custom_fields import create_custom_fields

		create_custom_fields()
		ensure_leave_types()

	def test_koder_forifylls(self):
		from hrms_sverige.setup.leave import PAXML_TIDKODER, ensure_paxml_tidkoder

		frappe.db.set_value("Leave Type", "VAB", "paxml_tidkod", None)
		ensure_paxml_tidkoder()
		for leave_type, kod in PAXML_TIDKODER.items():
			self.assertEqual(frappe.db.get_value("Leave Type", leave_type, "paxml_tidkod"), kod, leave_type)

	def test_andrad_kod_behalls(self):
		from hrms_sverige.setup.leave import ensure_paxml_tidkoder

		frappe.db.set_value("Leave Type", "Tjänstledighet", "paxml_tidkod", "FR1")
		ensure_paxml_tidkoder()
		self.assertEqual(frappe.db.get_value("Leave Type", "Tjänstledighet", "paxml_tidkod"), "FR1")

	def test_after_migrate_fyller_i(self):
		from hrms_sverige.setup.install import after_migrate

		frappe.db.set_value("Leave Type", "Semester", "paxml_tidkod", None)
		after_migrate()
		self.assertEqual(frappe.db.get_value("Leave Type", "Semester", "paxml_tidkod"), "SEM")
```

- [ ] **Step 3: Kör och se det fallera**

Run: `bench --site test-erp.local run-tests --app hrms_sverige --module hrms_sverige.tests.test_leave`
Expected: FAIL/ERROR i `TestPaxmlTidkoder` (`ImportError: cannot import name 'PAXML_TIDKODER'`, eller okänd kolumn `paxml_tidkod`).

- [ ] **Step 4: Lägg till fältet** – i `get_custom_fields()` i `hrms_sverige/setup/custom_fields.py`, lägg till nyckeln `"Leave Type"` i den returnerade dict:en (efter `"Employee": [...]`):

```python
		"Leave Type": [
			{
				"fieldname": "paxml_tidkod",
				"label": _("PAXml-tidkod"),
				"fieldtype": "Data",
				"insert_after": "leave_type_name",
				"description": _(
					"Kod i löneunderlaget till lönesystemet, t.ex. SEM, SJK eller VAB. "
					"Lönesystemet kopplar koden till rätt löneart."
				),
			},
		],
```

- [ ] **Step 5: Förifyllningen** – i `hrms_sverige/setup/leave.py`, efter `HRMS_DEFAULT_LEAVE_TYPES`:

```python
# Standardkoder för frånvaro i PAXml 2.0. Lönesystemet (t.ex. Crona Lön) kopplar dem till lönearter.
PAXML_TIDKODER = {
	SEMESTER: "SEM",
	"Sjukfrånvaro": "SJK",
	"VAB": "VAB",
	"Föräldraledighet": "FPE",
	"Tjänstledighet": "TJL",
	KOMPLEDIGHET: "KOM",
}
```

och sist i filen:

```python
def ensure_paxml_tidkoder():
	"""Sätt PAXml-tidkod på appens frånvarotyper där den saknas. Ändrade koder lämnas orörda."""
	for leave_type, kod in PAXML_TIDKODER.items():
		if frappe.db.exists("Leave Type", leave_type) and not frappe.db.get_value(
			"Leave Type", leave_type, "paxml_tidkod"
		):
			frappe.db.set_value("Leave Type", leave_type, "paxml_tidkod", kod)
```

- [ ] **Step 6: Anropa den** – i `hrms_sverige/setup/install.py`: lägg `ensure_paxml_tidkoder` i importen från `hrms_sverige.setup.leave`, anropa `ensure_paxml_tidkoder()` direkt efter `ensure_leave_types()` i `setup_all`, och ändra `after_migrate` till:

```python
def after_migrate():
	# Migrate synkar om arbetsytor och ikoner från HRMS och kan visa dem igen.
	create_custom_fields()
	ensure_paxml_tidkoder()
	hide_unused()
```

- [ ] **Step 7: Kör testerna**

Run: `bench --site test-erp.local run-tests --app hrms_sverige --module hrms_sverige.tests.test_leave`
Expected: OK, alla tester i modulen.

- [ ] **Step 8: Commit**

```bash
git add hrms_sverige/setup/custom_fields.py hrms_sverige/setup/leave.py hrms_sverige/setup/install.py hrms_sverige/tests/test_leave.py
git commit -m "feat: PAXml time code on leave types, prefilled for the Swedish leave types" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016yYYj5agMiCoxsTCe4usfY"
```

---

### Task 2: PAXml-byggaren

**Files:**
- Create: `hrms_sverige/lon/__init__.py` (tom), `hrms_sverige/lon/paxml.py`
- Create: `hrms_sverige/tests/fixtures/paxml-2.0.xsd`
- Test: `hrms_sverige/tests/test_paxml.py`

**Interfaces:**
- Produces:
  - `hrms_sverige.lon.paxml.Huvud(datum: datetime, foretagnamn: str, programnamn: str, foretagorgnr: str | None = None)` (frozen dataclass)
  - `hrms_sverige.lon.paxml.Tidtransaktion(postid: int, anstid: str, tidkod: str, from_date: date, to_date: date, omfattning: float)` (frozen dataclass)
  - `hrms_sverige.lon.paxml.bygg_paxml(huvud: Huvud, transaktioner: list[Tidtransaktion]) -> bytes` (UTF-8 med XML-deklaration)
  - `hrms_sverige.lon.paxml.orgnr_fran_tax_id(tax_id: str | None) -> str | None`

- [ ] **Step 1: Lägg in schemat**

```bash
mkdir -p hrms_sverige/tests/fixtures
curl -sSfL -o hrms_sverige/tests/fixtures/paxml-2.0.xsd https://www.paxml.se/2.0/paxml.xsd
head -3 hrms_sverige/tests/fixtures/paxml-2.0.xsd
```
Expected: filen börjar med `<?xml version="1.0" encoding="iso-8859-1"?>` och är 37 047 byte. Ändra inte filen; den har inga avslutande blanksteg, så pre-commit lämnar den orörd.

- [ ] **Step 2: Skriv de fallerande testerna** – `hrms_sverige/tests/test_paxml.py`:

```python
import os
from datetime import date, datetime

from frappe.tests import UnitTestCase
from lxml import etree

from hrms_sverige.lon.paxml import Huvud, Tidtransaktion, bygg_paxml, orgnr_fran_tax_id

XSD = os.path.join(os.path.dirname(__file__), "fixtures", "paxml-2.0.xsd")
HUVUD = Huvud(
	datum=datetime(2026, 10, 2, 14, 30, 15, 123456),
	foretagnamn="Exempelbolaget AB",
	programnamn="HRMS Sverige 0.1.0",
	foretagorgnr="5560000000",
)


def transaktion(postid=1, from_date=date(2026, 9, 14), to_date=date(2026, 9, 16), omfattning=100, tidkod="SJK"):
	return Tidtransaktion(
		postid=postid, anstid="101", tidkod=tidkod, from_date=from_date, to_date=to_date, omfattning=omfattning
	)


class TestPaxml(UnitTestCase):
	def parse(self, data: bytes):
		return etree.fromstring(data)

	def test_validerar_mot_schemat(self):
		data = bygg_paxml(
			HUVUD, [transaktion(), transaktion(2, date(2026, 9, 18), date(2026, 9, 18), 50, "SEM")]
		)
		schema = etree.XMLSchema(etree.parse(XSD))
		self.assertTrue(schema.validate(etree.fromstring(data)), schema.error_log)

	def test_huvud(self):
		rot = self.parse(bygg_paxml(HUVUD, [transaktion()]))
		self.assertEqual(rot.findtext("header/version"), "2.0")
		self.assertEqual(rot.findtext("header/format"), "LÖNIN")
		self.assertEqual(rot.findtext("header/datum"), "2026-10-02T14:30:15")
		self.assertEqual(rot.findtext("header/foretagorgnr"), "5560000000")
		self.assertEqual(rot.findtext("header/foretagnamn"), "Exempelbolaget AB")

	def test_utf8_deklaration(self):
		data = bygg_paxml(HUVUD, [transaktion()])
		self.assertTrue(data.startswith(b"<?xml version='1.0' encoding='UTF-8'?>"))
		self.assertIn("LÖNIN".encode(), data)

	def test_intervall_och_omfattning(self):
		tt = self.parse(bygg_paxml(HUVUD, [transaktion()])).find("tidtransaktioner/tidtrans")
		self.assertEqual((tt.get("anstid"), tt.get("postid")), ("101", "1"))
		self.assertEqual(tt.findtext("tidkod"), "SJK")
		self.assertEqual((tt.findtext("datumfrom"), tt.findtext("datumtom")), ("2026-09-14", "2026-09-16"))
		self.assertIsNone(tt.find("datum"))
		self.assertEqual(tt.findtext("omfattning"), "100")

	def test_en_dag_skrivs_som_datum(self):
		tt = self.parse(
			bygg_paxml(HUVUD, [transaktion(from_date=date(2026, 9, 18), to_date=date(2026, 9, 18), omfattning=50)])
		).find("tidtransaktioner/tidtrans")
		self.assertEqual(tt.findtext("datum"), "2026-09-18")
		self.assertIsNone(tt.find("datumfrom"))
		self.assertEqual(tt.findtext("omfattning"), "50")

	def test_utan_orgnr(self):
		huvud = Huvud(datum=HUVUD.datum, foretagnamn="X AB", programnamn="HRMS Sverige")
		self.assertIsNone(self.parse(bygg_paxml(huvud, [transaktion()])).find("header/foretagorgnr"))

	def test_orgnr_fran_tax_id(self):
		self.assertEqual(orgnr_fran_tax_id("SE556000000001"), "5560000000")
		self.assertEqual(orgnr_fran_tax_id("556000-0000"), "5560000000")
		self.assertEqual(orgnr_fran_tax_id("5560000000"), "5560000000")
		self.assertIsNone(orgnr_fran_tax_id(""))
		self.assertIsNone(orgnr_fran_tax_id(None))
		self.assertIsNone(orgnr_fran_tax_id("12345"))
```

- [ ] **Step 3: Kör och se dem fallera**

Run: `bench --site test-erp.local run-tests --app hrms_sverige --module hrms_sverige.tests.test_paxml`
Expected: ERROR, `ModuleNotFoundError: No module named 'hrms_sverige.lon'`.

- [ ] **Step 4: Implementera** – skapa tom `hrms_sverige/lon/__init__.py` och `hrms_sverige/lon/paxml.py`:

```python
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
```

- [ ] **Step 5: Kör testerna**

Run: `bench --site test-erp.local run-tests --app hrms_sverige --module hrms_sverige.tests.test_paxml`
Expected: OK (7 tester).

- [ ] **Step 6: Commit**

```bash
git add hrms_sverige/lon/__init__.py hrms_sverige/lon/paxml.py hrms_sverige/tests/fixtures/paxml-2.0.xsd hrms_sverige/tests/test_paxml.py
git commit -m "feat: PAXml 2.0 builder for time transactions" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016yYYj5agMiCoxsTCe4usfY"
```

---

### Task 3: Från ledighetsansökan till rader

**Files:**
- Create: `hrms_sverige/lon/franvaro.py`
- Modify: `hrms_sverige/tests/utils.py` (ny hjälpfunktion)
- Test: `hrms_sverige/tests/test_franvaro.py`

**Interfaces:**
- Consumes: `hrms_sverige.tests.utils.make_test_employee(first_name, **fields) -> str`, `COMPANY`; `hrms_sverige.setup.holidays.create_holiday_list(year, company)`; `hrms_sverige.setup.leave.ensure_leave_types()`.
- Produces:
  - `hrms_sverige.lon.franvaro.dela_upp(from_date: date, to_date: date, halvdag: date | None, period_from: date, period_to: date) -> list[tuple[date, date, int]]`
  - `hrms_sverige.lon.franvaro.rader_for_period(company: str, from_date, to_date) -> list[dict]` – varje dict har nycklarna `employee`, `leave_type`, `from_date`, `to_date`, `omfattning`, `leave_application`; sorterad på anställningsnummer, anställd, från-datum.
  - `hrms_sverige.tests.utils.make_leave_application(employee: str, leave_type: str, from_date: str, to_date: str, half_day: int = 0, half_day_date: str | None = None, submit: bool = True) -> str`

- [ ] **Step 1: Testhjälpen** – lägg sist i `hrms_sverige/tests/utils.py`:

```python
def make_leave_application(
	employee: str,
	leave_type: str,
	from_date: str,
	to_date: str,
	half_day: int = 0,
	half_day_date: str | None = None,
	submit: bool = True,
) -> str:
	"""Godkänd (och inskickad) ledighetsansökan i testbolaget."""
	frappe.db.set_single_value("HR Settings", "leave_approver_mandatory_in_leave_application", 0)
	doc = frappe.get_doc(
		{
			"doctype": "Leave Application",
			"employee": employee,
			"company": COMPANY,
			"leave_type": leave_type,
			"from_date": from_date,
			"to_date": to_date,
			"half_day": half_day,
			"half_day_date": half_day_date,
			"posting_date": from_date,
			"status": "Approved" if submit else "Open",
		}
	).insert()
	if submit:
		doc.submit()
	return doc.name
```

- [ ] **Step 2: Skriv de fallerande testerna** – `hrms_sverige/tests/test_franvaro.py`:

```python
from datetime import date

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from hrms_sverige.lon.franvaro import dela_upp, rader_for_period
from hrms_sverige.setup.holidays import create_holiday_list
from hrms_sverige.setup.leave import ensure_leave_types
from hrms_sverige.tests.utils import COMPANY, ensure_test_company, make_leave_application, make_test_employee

SEPT = (date(2026, 9, 1), date(2026, 9, 30))


class TestDelaUpp(UnitTestCase):
	def test_hela_dagar(self):
		self.assertEqual(dela_upp(date(2026, 9, 14), date(2026, 9, 16), None, *SEPT), [
			(date(2026, 9, 14), date(2026, 9, 16), 100),
		])

	def test_klipps_vid_manadsskifte(self):
		self.assertEqual(dela_upp(date(2026, 8, 28), date(2026, 9, 2), None, *SEPT), [
			(date(2026, 9, 1), date(2026, 9, 2), 100),
		])

	def test_halvdag_mitt_i(self):
		self.assertEqual(dela_upp(date(2026, 9, 14), date(2026, 9, 18), date(2026, 9, 16), *SEPT), [
			(date(2026, 9, 14), date(2026, 9, 15), 100),
			(date(2026, 9, 16), date(2026, 9, 16), 50),
			(date(2026, 9, 17), date(2026, 9, 18), 100),
		])

	def test_halvdag_forst(self):
		self.assertEqual(dela_upp(date(2026, 9, 14), date(2026, 9, 16), date(2026, 9, 14), *SEPT), [
			(date(2026, 9, 14), date(2026, 9, 14), 50),
			(date(2026, 9, 15), date(2026, 9, 16), 100),
		])

	def test_ensam_halvdag(self):
		self.assertEqual(dela_upp(date(2026, 9, 14), date(2026, 9, 14), date(2026, 9, 14), *SEPT), [
			(date(2026, 9, 14), date(2026, 9, 14), 50),
		])

	def test_halvdag_utanfor_perioden_klipps_bort(self):
		# Halvdagen 31 aug hör till augusti; september får bara hela dagar
		self.assertEqual(dela_upp(date(2026, 8, 31), date(2026, 9, 2), date(2026, 8, 31), *SEPT), [
			(date(2026, 9, 1), date(2026, 9, 2), 100),
		])

	def test_helt_utanfor(self):
		self.assertEqual(dela_upp(date(2026, 8, 3), date(2026, 8, 5), None, *SEPT), [])


class TestRaderForPeriod(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_test_company()
		ensure_leave_types()
		create_holiday_list(2026, COMPANY)

	def test_godkand_frånvaro_blir_rader(self):
		anstalld = make_test_employee("Rad Ett", employee_number="R-1")
		ansokan = make_leave_application(anstalld, "Sjukfrånvaro", "2026-09-14", "2026-09-16")
		rader = [r for r in rader_for_period(COMPANY, *SEPT) if r["employee"] == anstalld]
		self.assertEqual(rader, [
			{
				"employee": anstalld,
				"leave_type": "Sjukfrånvaro",
				"from_date": date(2026, 9, 14),
				"to_date": date(2026, 9, 16),
				"omfattning": 100,
				"leave_application": ansokan,
			}
		])

	def test_halvdag_ger_egen_rad(self):
		anstalld = make_test_employee("Rad Halv", employee_number="R-2")
		make_leave_application(anstalld, "VAB", "2026-09-21", "2026-09-23", half_day=1, half_day_date="2026-09-22")
		rader = [(r["from_date"], r["to_date"], r["omfattning"]) for r in rader_for_period(COMPANY, *SEPT) if r["employee"] == anstalld]
		self.assertEqual(rader, [
			(date(2026, 9, 21), date(2026, 9, 21), 100),
			(date(2026, 9, 22), date(2026, 9, 22), 50),
			(date(2026, 9, 23), date(2026, 9, 23), 100),
		])

	def test_ej_godkand_och_makulerad_kommer_inte_med(self):
		anstalld = make_test_employee("Rad Utkast", employee_number="R-3")
		make_leave_application(anstalld, "Sjukfrånvaro", "2026-09-07", "2026-09-07", submit=False)
		makulerad = make_leave_application(anstalld, "Sjukfrånvaro", "2026-09-09", "2026-09-09")
		frappe.get_doc("Leave Application", makulerad).cancel()
		self.assertEqual([r for r in rader_for_period(COMPANY, *SEPT) if r["employee"] == anstalld], [])

	def test_annat_bolag_kommer_inte_med(self):
		anstalld = make_test_employee("Rad Bolag", employee_number="R-4")
		make_leave_application(anstalld, "Sjukfrånvaro", "2026-09-24", "2026-09-24")
		self.assertEqual([r for r in rader_for_period("Annat bolag AB", *SEPT) if r["employee"] == anstalld], [])

	def test_sorteras_pa_anstallningsnummer(self):
		b = make_test_employee("Rad Sort B", employee_number="S-2")
		a = make_test_employee("Rad Sort A", employee_number="S-1")
		make_leave_application(b, "Sjukfrånvaro", "2026-09-01", "2026-09-01")
		make_leave_application(a, "Sjukfrånvaro", "2026-09-02", "2026-09-02")
		ordning = [r["employee"] for r in rader_for_period(COMPANY, *SEPT) if r["employee"] in (a, b)]
		self.assertEqual(ordning, [a, b])
```

- [ ] **Step 3: Kör och se dem fallera**

Run: `bench --site test-erp.local run-tests --app hrms_sverige --module hrms_sverige.tests.test_franvaro`
Expected: ERROR, `ModuleNotFoundError: No module named 'hrms_sverige.lon.franvaro'`.

- [ ] **Step 4: Implementera** – `hrms_sverige/lon/franvaro.py`:

```python
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
```

- [ ] **Step 5: Kör testerna**

Run: `bench --site test-erp.local run-tests --app hrms_sverige --module hrms_sverige.tests.test_franvaro`
Expected: OK (12 tester). Om HRMS stoppar en ledighetsansökan (t.ex. "Leave Approver" eller saknad helglista), läs felet och justera **testdata** i `make_leave_application`, inte logiken i `franvaro.py`.

- [ ] **Step 6: Commit**

```bash
git add hrms_sverige/lon/franvaro.py hrms_sverige/tests/utils.py hrms_sverige/tests/test_franvaro.py
git commit -m "feat: turn approved leave applications into payroll rows per period" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016yYYj5agMiCoxsTCe4usfY"
```

---

### Task 4: Dokumentet Löneunderlag

**Files:**
- Modify: `hrms_sverige/modules.txt` (lägg till raden `Lön`)
- Create: `hrms_sverige/lon/doctype/__init__.py` (tom)
- Create: `hrms_sverige/lon/doctype/loneunderlag_rad/__init__.py` (tom), `loneunderlag_rad.json`, `loneunderlag_rad.py`
- Create: `hrms_sverige/lon/doctype/loneunderlag/__init__.py` (tom), `loneunderlag.json`, `loneunderlag.py`, `loneunderlag.js`
- Modify: `hrms_sverige/locale/sv.po`
- Test: `hrms_sverige/tests/test_loneunderlag.py`

**Interfaces:**
- Consumes: `rader_for_period` (Task 3), `bygg_paxml`, `Huvud`, `Tidtransaktion`, `orgnr_fran_tax_id` (Task 2), `Leave Type.paxml_tidkod` (Task 1), `make_leave_application` (Task 3).
- Produces:
  - DocType `Loneunderlag` (fält `company`, `ar`, `manad`, `from_date`, `to_date`, `rader`), DocType `Loneunderlag Rad` (fält `employee`, `anstallningsnummer`, `leave_type`, `tidkod`, `from_date`, `to_date`, `omfattning`, `leave_application`).
  - `Loneunderlag.hamta_franvaro()` (whitelistad dokumentmetod), `Loneunderlag.paxml() -> bytes`, `Loneunderlag.filnamn() -> str`.
  - `hrms_sverige.lon.doctype.loneunderlag.loneunderlag.ladda_ner(name: str)` (whitelistad).
  - `hrms_sverige.lon.doctype.loneunderlag.loneunderlag.MANADER: list[str]` (Januari … December).

- [ ] **Step 1: Modulen** – lägg till en rad `Lön` sist i `hrms_sverige/modules.txt` (filen ska sluta med radbrytning) och skapa tomma `__init__.py` enligt filistan ovan.

- [ ] **Step 2: Barntabellen** – `hrms_sverige/lon/doctype/loneunderlag_rad/loneunderlag_rad.json`:

```json
{
 "actions": [],
 "creation": "2026-10-02 15:00:00.000000",
 "doctype": "DocType",
 "editable_grid": 1,
 "engine": "InnoDB",
 "field_order": [
  "employee",
  "anstallningsnummer",
  "leave_type",
  "tidkod",
  "from_date",
  "to_date",
  "omfattning",
  "leave_application"
 ],
 "fields": [
  {"fieldname": "employee", "fieldtype": "Link", "label": "Anställd", "options": "Employee", "reqd": 1, "in_list_view": 1, "columns": 2},
  {"fieldname": "anstallningsnummer", "fieldtype": "Data", "label": "Anställningsnummer", "read_only": 1, "in_list_view": 1, "columns": 1},
  {"fieldname": "leave_type", "fieldtype": "Link", "label": "Frånvarotyp", "options": "Leave Type", "reqd": 1, "in_list_view": 1, "columns": 2},
  {"fieldname": "tidkod", "fieldtype": "Data", "label": "Tidkod", "read_only": 1, "in_list_view": 1, "columns": 1},
  {"fieldname": "from_date", "fieldtype": "Date", "label": "Från", "reqd": 1, "in_list_view": 1, "columns": 1},
  {"fieldname": "to_date", "fieldtype": "Date", "label": "Till", "reqd": 1, "in_list_view": 1, "columns": 1},
  {"fieldname": "omfattning", "fieldtype": "Percent", "label": "Omfattning", "reqd": 1, "default": "100", "in_list_view": 1, "columns": 1},
  {"fieldname": "leave_application", "fieldtype": "Link", "label": "Ledighetsansökan", "options": "Leave Application", "read_only": 1, "in_list_view": 1, "columns": 1}
 ],
 "istable": 1,
 "modified": "2026-10-02 15:00:00.000000",
 "modified_by": "Administrator",
 "module": "Lön",
 "name": "Loneunderlag Rad",
 "owner": "Administrator",
 "permissions": [],
 "sort_field": "creation",
 "sort_order": "ASC",
 "states": []
}
```

och `loneunderlag_rad.py`:

```python
from frappe.model.document import Document


class LoneunderlagRad(Document):
	pass
```

- [ ] **Step 3: Huvuddokumentet** – `hrms_sverige/lon/doctype/loneunderlag/loneunderlag.json`:

```json
{
 "actions": [],
 "autoname": "format:LU-{YYYY}-{#####}",
 "creation": "2026-10-02 15:00:00.000000",
 "doctype": "DocType",
 "engine": "InnoDB",
 "field_order": [
  "company",
  "ar",
  "manad",
  "column_break_1",
  "from_date",
  "to_date",
  "amended_from",
  "section_rader",
  "rader"
 ],
 "fields": [
  {"fieldname": "company", "fieldtype": "Link", "label": "Bolag", "options": "Company", "reqd": 1, "in_list_view": 1, "in_standard_filter": 1},
  {"fieldname": "ar", "fieldtype": "Int", "label": "År", "reqd": 1, "in_list_view": 1, "in_standard_filter": 1},
  {"fieldname": "manad", "fieldtype": "Select", "label": "Månad", "options": "Januari\nFebruari\nMars\nApril\nMaj\nJuni\nJuli\nAugusti\nSeptember\nOktober\nNovember\nDecember", "reqd": 1, "in_list_view": 1, "in_standard_filter": 1},
  {"fieldname": "column_break_1", "fieldtype": "Column Break"},
  {"fieldname": "from_date", "fieldtype": "Date", "label": "Från", "read_only": 1},
  {"fieldname": "to_date", "fieldtype": "Date", "label": "Till", "read_only": 1},
  {"fieldname": "amended_from", "fieldtype": "Link", "label": "Ändrad från", "options": "Loneunderlag", "no_copy": 1, "print_hide": 1, "read_only": 1, "search_index": 1},
  {"fieldname": "section_rader", "fieldtype": "Section Break", "label": "Frånvaro"},
  {"fieldname": "rader", "fieldtype": "Table", "label": "Rader", "options": "Loneunderlag Rad"}
 ],
 "is_submittable": 1,
 "links": [],
 "modified": "2026-10-02 15:00:00.000000",
 "modified_by": "Administrator",
 "module": "Lön",
 "name": "Loneunderlag",
 "naming_rule": "Expression",
 "owner": "Administrator",
 "permissions": [
  {"role": "HR Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "submit": 1, "cancel": 1, "amend": 1, "report": 1, "export": 1, "print": 1},
  {"role": "HR User", "read": 1, "write": 1, "create": 1, "report": 1, "print": 1}
 ],
 "sort_field": "creation",
 "sort_order": "DESC",
 "states": [],
 "title_field": "company",
 "track_changes": 1
}
```

- [ ] **Step 4: Skriv de fallerande testerna** – `hrms_sverige/tests/test_loneunderlag.py`:

```python
import frappe
from frappe.tests import IntegrationTestCase
from lxml import etree

from hrms_sverige.lon.doctype.loneunderlag.loneunderlag import ladda_ner
from hrms_sverige.setup.custom_fields import create_custom_fields
from hrms_sverige.setup.holidays import create_holiday_list
from hrms_sverige.setup.leave import ensure_leave_types, ensure_paxml_tidkoder
from hrms_sverige.tests.utils import COMPANY, ensure_test_company, make_leave_application, make_test_employee


def nytt_underlag(manad="September", ar=2026):
	return frappe.get_doc({"doctype": "Loneunderlag", "company": COMPANY, "ar": ar, "manad": manad}).insert()


class TestLoneunderlag(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_test_company()
		create_custom_fields()
		ensure_leave_types()
		ensure_paxml_tidkoder()
		create_holiday_list(2026, COMPANY)
		cls.anstalld = make_test_employee("Lön Ett", employee_number="L-1")
		make_leave_application(cls.anstalld, "Sjukfrånvaro", "2026-09-14", "2026-09-16")

	def test_period_raknas_fram(self):
		doc = nytt_underlag("Februari", 2028)
		self.assertEqual((str(doc.from_date), str(doc.to_date)), ("2028-02-01", "2028-02-29"))

	def test_hamta_franvaro(self):
		doc = nytt_underlag()
		doc.hamta_franvaro()
		rad = next(r for r in doc.rader if r.employee == self.anstalld)
		self.assertEqual((rad.anstallningsnummer, rad.tidkod, rad.omfattning), ("L-1", "SJK", 100))
		self.assertEqual((str(rad.from_date), str(rad.to_date)), ("2026-09-14", "2026-09-16"))

	def test_hamta_tva_ganger_dubblerar_inte(self):
		doc = nytt_underlag()
		doc.hamta_franvaro()
		antal = len(doc.rader)
		doc.hamta_franvaro()
		self.assertEqual(len(doc.rader), antal)

	def test_tidkod_normaliseras(self):
		frappe.db.set_value("Leave Type", "Sjukfrånvaro", "paxml_tidkod", " sjk ")
		doc = nytt_underlag()
		doc.hamta_franvaro()
		self.assertEqual(next(r for r in doc.rader if r.employee == self.anstalld).tidkod, "SJK")
		frappe.db.set_value("Leave Type", "Sjukfrånvaro", "paxml_tidkod", "SJK")

	def test_godkann_och_ladda_ner(self):
		doc = nytt_underlag("Oktober", 2031)
		doc.append("rader", {"employee": self.anstalld, "leave_type": "Sjukfrånvaro",
			"from_date": "2031-10-06", "to_date": "2031-10-07", "omfattning": 100})
		doc.save()
		doc.submit()
		ladda_ner(doc.name)
		self.assertEqual(frappe.response.type, "download")
		self.assertEqual(frappe.response.filename, f"paxml-{frappe.db.get_value('Company', COMPANY, 'abbr')}-2031-10.xml")
		tt = etree.fromstring(frappe.response.filecontent).find("tidtransaktioner/tidtrans")
		self.assertEqual((tt.get("anstid"), tt.get("postid"), tt.findtext("tidkod")), ("L-1", "1", "SJK"))

	def test_saknat_anstallningsnummer_stoppar(self):
		utan = make_test_employee("Lön Utan")
		frappe.db.set_value("Employee", utan, "employee_number", None)
		doc = nytt_underlag("Mars", 2031)
		doc.append("rader", {"employee": utan, "leave_type": "Sjukfrånvaro",
			"from_date": "2031-03-03", "to_date": "2031-03-03", "omfattning": 100})
		doc.save()
		self.assertRaisesRegex(frappe.ValidationError, "anställningsnummer", doc.submit)

	def test_saknad_tidkod_stoppar(self):
		frappe.db.set_value("Leave Type", "Tjänstledighet", "paxml_tidkod", None)
		doc = nytt_underlag("April", 2031)
		doc.append("rader", {"employee": self.anstalld, "leave_type": "Tjänstledighet",
			"from_date": "2031-04-07", "to_date": "2031-04-07", "omfattning": 100})
		doc.save()
		self.assertRaisesRegex(frappe.ValidationError, "PAXml-tidkod", doc.submit)
		frappe.db.set_value("Leave Type", "Tjänstledighet", "paxml_tidkod", "TJL")

	def test_tomt_underlag_stoppar(self):
		doc = nytt_underlag("Maj", 2031)
		self.assertRaisesRegex(frappe.ValidationError, "rader", doc.submit)

	def test_dubbelt_underlag_stoppar(self):
		forsta = nytt_underlag("Juni", 2031)
		forsta.append("rader", {"employee": self.anstalld, "leave_type": "Sjukfrånvaro",
			"from_date": "2031-06-02", "to_date": "2031-06-02", "omfattning": 100})
		forsta.save()
		forsta.submit()
		andra = frappe.copy_doc(forsta)
		andra.insert()
		self.assertRaisesRegex(frappe.ValidationError, "redan", andra.submit)

	def test_makulerad_ansokan_stoppar(self):
		anstalld = make_test_employee("Lön Makulerad", employee_number="L-9")
		ansokan = make_leave_application(anstalld, "Sjukfrånvaro", "2026-09-28", "2026-09-28")
		doc = nytt_underlag()
		doc.hamta_franvaro()
		frappe.get_doc("Leave Application", ansokan).cancel()
		self.assertRaisesRegex(frappe.ValidationError, "Hämta frånvaro", doc.submit)

	def test_makulera_och_gor_om(self):
		doc = nytt_underlag("Juli", 2031)
		doc.append("rader", {"employee": self.anstalld, "leave_type": "Sjukfrånvaro",
			"from_date": "2031-07-07", "to_date": "2031-07-07", "omfattning": 100})
		doc.save()
		doc.submit()
		doc.cancel()
		ny = frappe.copy_doc(doc)
		ny.amended_from = doc.name
		ny.insert()
		ny.submit()
		self.assertEqual(ny.docstatus, 1)
```

- [ ] **Step 5: Kör och se dem fallera**

Run: `bench --site test-erp.local migrate && bench --site test-erp.local run-tests --app hrms_sverige --module hrms_sverige.tests.test_loneunderlag`
Expected: ERROR, `ImportError` för `loneunderlag` (controllern finns inte än). `migrate` behövs för att skapa tabellerna och modulen `Lön`.

- [ ] **Step 6: Controllern** – `hrms_sverige/lon/doctype/loneunderlag/loneunderlag.py`:

```python
"""Löneunderlag per bolag och kalendermånad: godkänd frånvaro som PAXml-fil till lönesystemet."""

import calendar
from datetime import date

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime

import hrms_sverige
from hrms_sverige.lon.franvaro import rader_for_period
from hrms_sverige.lon.paxml import Huvud, Tidtransaktion, bygg_paxml, orgnr_fran_tax_id

MANADER = [
	"Januari",
	"Februari",
	"Mars",
	"April",
	"Maj",
	"Juni",
	"Juli",
	"Augusti",
	"September",
	"Oktober",
	"November",
	"December",
]


class Loneunderlag(Document):
	def validate(self):
		self.satt_period()
		self.uppdatera_rader()

	def satt_period(self):
		manad = MANADER.index(self.manad) + 1
		self.from_date = date(self.ar, manad, 1)
		self.to_date = date(self.ar, manad, calendar.monthrange(self.ar, manad)[1])

	def uppdatera_rader(self):
		"""Anställningsnummer och tidkod hämtas på nytt, så att raderna speglar dagens register."""
		for rad in self.rader:
			rad.anstallningsnummer = (frappe.db.get_value("Employee", rad.employee, "employee_number") or "").strip()
			rad.tidkod = (frappe.db.get_value("Leave Type", rad.leave_type, "paxml_tidkod") or "").strip().upper()

	def before_submit(self):
		if not self.rader:
			frappe.throw(_("Löneunderlaget har inga rader."))
		utan_nummer = sorted({r.employee for r in self.rader if not r.anstallningsnummer})
		if utan_nummer:
			frappe.throw(
				_("Anställda utan anställningsnummer: {0}. Ange samma nummer som i lönesystemet.").format(
					", ".join(utan_nummer)
				)
			)
		utan_kod = sorted({r.leave_type for r in self.rader if not r.tidkod})
		if utan_kod:
			frappe.throw(
				_("Frånvarotyper utan PAXml-tidkod: {0}. Ange koden på frånvarotypen.").format(", ".join(utan_kod))
			)
		makulerade = sorted(
			{
				r.leave_application
				for r in self.rader
				if r.leave_application
				and frappe.db.get_value("Leave Application", r.leave_application, "docstatus") != 1
			}
		)
		if makulerade:
			frappe.throw(
				_("Ledighetsansökningar har ändrats sedan raderna hämtades: {0}. Klicka på Hämta frånvaro igen.").format(
					", ".join(makulerade)
				)
			)
		befintligt = frappe.db.get_value(
			"Loneunderlag",
			{"company": self.company, "ar": self.ar, "manad": self.manad, "docstatus": 1, "name": ("!=", self.name)},
		)
		if befintligt:
			frappe.throw(
				_("Det finns redan ett godkänt löneunderlag för {0} {1}: {2}.").format(self.manad, self.ar, befintligt)
			)

	@frappe.whitelist()
	def hamta_franvaro(self):
		if self.docstatus != 0:
			frappe.throw(_("Frånvaro kan bara hämtas till ett utkast."))
		self.check_permission("write")
		self.satt_period()
		self.set("rader", [])
		for rad in rader_for_period(self.company, self.from_date, self.to_date):
			self.append("rader", rad)
		self.save()

	def filnamn(self) -> str:
		abbr = frappe.db.get_value("Company", self.company, "abbr")
		return f"paxml-{abbr}-{getdate(self.from_date):%Y-%m}.xml"

	def paxml(self) -> bytes:
		huvud = Huvud(
			datum=now_datetime(),
			foretagnamn=self.company,
			programnamn=f"HRMS Sverige {hrms_sverige.__version__}",
			foretagorgnr=orgnr_fran_tax_id(frappe.db.get_value("Company", self.company, "tax_id")),
		)
		transaktioner = [
			Tidtransaktion(
				postid=rad.idx,
				anstid=rad.anstallningsnummer,
				tidkod=rad.tidkod,
				from_date=getdate(rad.from_date),
				to_date=getdate(rad.to_date),
				omfattning=rad.omfattning,
			)
			for rad in self.rader
		]
		return bygg_paxml(huvud, transaktioner)


@frappe.whitelist()
def ladda_ner(name: str):
	doc = frappe.get_doc("Loneunderlag", name)
	doc.check_permission("read")
	if doc.docstatus != 1:
		frappe.throw(_("Godkänn löneunderlaget innan filen laddas ner."))
	frappe.response.filename = doc.filnamn()
	frappe.response.filecontent = doc.paxml()
	frappe.response.type = "download"
```

- [ ] **Step 7: Formulärskriptet** – `hrms_sverige/lon/doctype/loneunderlag/loneunderlag.js`:

```javascript
frappe.ui.form.on("Loneunderlag", {
	onload(frm) {
		if (frm.is_new() && !frm.doc.ar) {
			const forra = moment().subtract(1, "month");
			frm.set_value("ar", forra.year());
			frm.set_value("manad", frm.fields_dict.manad.df.options.split("\n")[forra.month()]);
		}
	},

	refresh(frm) {
		if (frm.is_new()) return;
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Hämta frånvaro"), () =>
				frm
					.call({ doc: frm.doc, method: "hamta_franvaro", freeze: true, freeze_message: __("Hämtar frånvaro …") })
					.then(() => frm.reload_doc())
			);
		}
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__("Ladda ner PAXml"), () =>
				window.open(
					"/api/method/hrms_sverige.lon.doctype.loneunderlag.loneunderlag.ladda_ner?name=" +
						encodeURIComponent(frm.doc.name)
				)
			).addClass("btn-primary");
		}
	},
});
```

- [ ] **Step 8: Visningsnamn** – lägg till i `hrms_sverige/locale/sv.po` (sist i filen):

```
msgid "Loneunderlag"
msgstr "Löneunderlag"

msgid "Loneunderlag Rad"
msgstr "Löneunderlagsrad"

msgid "Lön"
msgstr "Lön"
```

Kompilera: `bench compile-po-to-mo --app hrms_sverige --locale sv --force`

- [ ] **Step 9: Migrera och kör testerna**

Run: `bench --site test-erp.local migrate && bench --site test-erp.local run-tests --app hrms_sverige --module hrms_sverige.tests.test_loneunderlag`
Expected: OK (11 tester).

- [ ] **Step 10: Hela sviten**

Run: `bench --site test-erp.local run-tests --app hrms_sverige`
Expected: OK. `test_translations` får inte gå sönder (den kontrollerar bara HRMS etiketter, men kör den ändå).

- [ ] **Step 11: Prova i webbläsaren** – starta testsiten (`bench --site test-erp.local serve --port 8001`, Administrator/admin), skapa ett Löneunderlag för en månad med frånvaro, klicka **Hämta frånvaro**, godkänn och **Ladda ner PAXml**. Kontrollera att filen öppnas och att knapparna visas på svenska.

- [ ] **Step 12: Commit**

```bash
git add hrms_sverige/modules.txt hrms_sverige/lon hrms_sverige/locale/sv.po hrms_sverige/tests/test_loneunderlag.py
git commit -m "feat: Löneunderlag document with PAXml download for Crona Lön" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016yYYj5agMiCoxsTCe4usfY"
```

---

### Task 5: Varning när en exporterad period ändras

**Files:**
- Modify: `hrms_sverige/lon/franvaro.py` (ny funktion)
- Modify: `hrms_sverige/hooks.py` (`doc_events`)
- Test: `hrms_sverige/tests/test_franvaro.py`

**Interfaces:**
- Consumes: DocType `Loneunderlag` med `company`, `from_date`, `to_date` (Task 4).
- Produces: `hrms_sverige.lon.franvaro.varna_om_exporterad(doc, method=None) -> None`, kopplad till `Leave Application.on_submit` och `on_cancel`.

- [ ] **Step 1: Skriv det fallerande testet** – lägg sist i `hrms_sverige/tests/test_franvaro.py` (och `from unittest.mock import patch` överst):

```python
class TestVarningExporteradPeriod(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		from hrms_sverige.setup.custom_fields import create_custom_fields
		from hrms_sverige.setup.leave import ensure_paxml_tidkoder

		ensure_test_company()
		create_custom_fields()
		ensure_leave_types()
		ensure_paxml_tidkoder()
		create_holiday_list(2026, COMPANY)
		cls.anstalld = make_test_employee("Varning", employee_number="V-1")
		underlag = frappe.get_doc({"doctype": "Loneunderlag", "company": COMPANY, "ar": 2026, "manad": "Augusti"})
		underlag.append("rader", {"employee": cls.anstalld, "leave_type": "Sjukfrånvaro",
			"from_date": "2026-08-03", "to_date": "2026-08-03", "omfattning": 100})
		underlag.insert()
		underlag.submit()

	def test_varning_vid_godkannande_i_exporterad_manad(self):
		with patch("frappe.msgprint") as msgprint:
			make_leave_application(self.anstalld, "Sjukfrånvaro", "2026-08-10", "2026-08-10")
		self.assertTrue(any("redan exporterad" in str(c) for c in msgprint.call_args_list))

	def test_varning_vid_makulering(self):
		ansokan = make_leave_application(self.anstalld, "Sjukfrånvaro", "2026-08-12", "2026-08-12")
		with patch("frappe.msgprint") as msgprint:
			frappe.get_doc("Leave Application", ansokan).cancel()
		self.assertTrue(any("redan exporterad" in str(c) for c in msgprint.call_args_list))

	def test_ingen_varning_i_annan_manad(self):
		with patch("frappe.msgprint") as msgprint:
			make_leave_application(self.anstalld, "Sjukfrånvaro", "2026-10-05", "2026-10-05")
		self.assertFalse(any("redan exporterad" in str(c) for c in msgprint.call_args_list))
```

- [ ] **Step 2: Kör och se det fallera**

Run: `bench --site test-erp.local run-tests --app hrms_sverige --module hrms_sverige.tests.test_franvaro`
Expected: FAIL i `test_varning_vid_godkannande_i_exporterad_manad` och `test_varning_vid_makulering` (ingen varning).

- [ ] **Step 3: Implementera** – lägg sist i `hrms_sverige/lon/franvaro.py` (och `from frappe import _` överst):

```python
def varna_om_exporterad(doc, method=None):
	"""Varna när en ledighet ändras i en period som redan finns i ett godkänt löneunderlag."""
	underlag = frappe.get_all(
		"Loneunderlag",
		filters={
			"company": doc.company,
			"docstatus": 1,
			"from_date": ("<=", doc.to_date),
			"to_date": (">=", doc.from_date),
		},
		pluck="name",
	)
	if underlag:
		frappe.msgprint(
			_(
				"Perioden finns redan i godkänt löneunderlag {0}. Rätta frånvaron för hand i lönesystemet, "
				"eller makulera löneunderlaget och gör om det."
			).format(", ".join(underlag)),
			title=_("Perioden är redan exporterad"),
			indicator="orange",
		)
```

och i `hrms_sverige/hooks.py`, lägg till i `doc_events`:

```python
	"Leave Application": {
		"on_submit": "hrms_sverige.lon.franvaro.varna_om_exporterad",
		"on_cancel": "hrms_sverige.lon.franvaro.varna_om_exporterad",
	},
```

- [ ] **Step 4: Kör testerna**

Run: `bench --site test-erp.local clear-cache && bench --site test-erp.local run-tests --app hrms_sverige --module hrms_sverige.tests.test_franvaro`
Expected: OK (15 tester). `clear-cache` behövs för att hooks.py ska läsas om.

- [ ] **Step 5: Commit**

```bash
git add hrms_sverige/lon/franvaro.py hrms_sverige/hooks.py hrms_sverige/tests/test_franvaro.py
git commit -m "feat: warn when leave changes in a month that is already exported" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016yYYj5agMiCoxsTCe4usfY"
```

---

### Task 6: Dokumentation, CI och PR

**Files:**
- Modify: `README.md`, `CHANGELOG.md` (i `apps/hrms_sverige`)
- Create: `/home/ubbe/ERPNext/ERPNext-Sverige-docs/docs/personal/loneunderlag.md`
- Modify: `/home/ubbe/ERPNext/ERPNext-Sverige-docs/mkdocs.yml` (nav)

- [ ] **Step 1: README** – lägg till en punkt sist i listan under "## HRMS Sverige":

```markdown
- Löneunderlag till lönesystemet: dokumentet **Löneunderlag** samlar månadens godkända frånvaro och laddar ner den
  som PAXml 2.0-fil (provat mot formatet för Crona Lön). Frånvarotypens **PAXml-tidkod** (SEM, SJK, VAB, FPE, TJL,
  KOM) kopplas till lönearter i lönesystemet. Anställningsnumret måste vara samma som i lönesystemet.
```

- [ ] **Step 2: CHANGELOG** – lägg in överst, under rubriken `# Ändringslogg`:

```markdown
## Ej släppt

- **Löneunderlag till Crona Lön:** godkänd frånvaro per bolag och månad som PAXml 2.0-fil, med PAXml-tidkod på
  frånvarotypen och varning när en redan exporterad månad ändras. Arbetad tid och tillägg kommer senare.
```

- [ ] **Step 3: Manualen** – skapa `docs/personal/loneunderlag.md` i docs-repot:

```markdown
# Löneunderlag till Crona Lön

Frånvaron i ERPNext kan föras över till Crona Lön som en PAXml-fil, så att den inte behöver skrivas in två gånger.
Filen innehåller den godkända frånvaron för en månad. Arbetad tid och tillägg ingår inte än.

## Förberedelser i ERPNext

- **Anställningsnummer:** fyll i fältet *Anställningsnummer* på varje anställd. Det måste vara samma nummer som i
  Crona, annars hittar Crona inte den anställde.
- **Tidkoder:** varje frånvarotyp har en *PAXml-tidkod*. De svenska frånvarotyperna har koderna från början:

| Frånvarotyp | PAXml-tidkod |
|---|---|
| Semester | SEM |
| Sjukfrånvaro | SJK |
| VAB | VAB |
| Föräldraledighet | FPE |
| Tjänstledighet | TJL |
| Kompledighet | KOM |

## Förberedelser i Crona Lön

1. Under **Import > Försystem**, skapa ett nytt försystem med importformat **PAXml** och filändelse **XML**.
2. Under **Register > Löneartsstyrning**, koppla varje tidkod ovan till rätt löneart. Kontrollera om
   kopplingen gäller månadsavlönade eller timavlönade.
3. Alla anställda behöver ett schema i Crona. Frånvaron skickas som procent av schemat, och Crona räknar
   timmarna och karensavdraget.

## Varje månad

1. Gå till **Löneunderlag** och skapa ett nytt. Bolag och förra månaden är förvalda.
2. Klicka på **Hämta frånvaro**. Alla godkända ledighetsansökningar i månaden blir rader. En halvdag blir en
   egen rad med 50 %.
3. Granska raderna och **godkänn** löneunderlaget.
4. Klicka på **Ladda ner PAXml** och läs in filen i Crona under **Lön > Importera löneunderlag**.

Godkännandet stoppas om en anställd saknar anställningsnummer, en frånvarotyp saknar tidkod eller månaden redan
har ett godkänt löneunderlag.

!!! tip "Prova med en anställd först"
    Första gången: läs in filen för en anställd och kontrollera i Cronas kalendarium att frånvaron hamnade på
    rätt dagar innan du läser in hela personalen.

!!! warning "Ändringar efter exporten"
    Godkänns eller makuleras en ledighet i en månad som redan är exporterad visas en varning. Rätta då
    frånvaron för hand i Crona, eller makulera löneunderlaget och gör om det.
```

och i `mkdocs.yml`, ändra raden `  - Personal: personal/index.md` till:

```yaml
  - Personal:
      - personal/index.md
      - Löneunderlag till Crona: personal/loneunderlag.md
```

Bygg: `cd /home/ubbe/ERPNext/ERPNext-Sverige-docs && .venv/bin/mkdocs build --strict -q` – Expected: inga fel.

- [ ] **Step 4: Commit i båda repona** (docs-repot på en egen gren `personal/loneunderlag`, publiceras först när appens PR är mergad):

```bash
cd /home/ubbe/ERPNext/my-frappe-bench/apps/hrms_sverige
git add README.md CHANGELOG.md
git commit -m "docs: document the Löneunderlag export" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016yYYj5agMiCoxsTCe4usfY"
cd /home/ubbe/ERPNext/ERPNext-Sverige-docs
git checkout -b personal/loneunderlag
git add docs/personal/loneunderlag.md mkdocs.yml
git commit -m "docs: payroll export to Crona Lön" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016yYYj5agMiCoxsTCe4usfY"
```

- [ ] **Step 5: Push, PR och CI**

```bash
cd /home/ubbe/ERPNext/my-frappe-bench/apps/hrms_sverige
git push -u origin feat/paxml-crona
gh pr create --base version-16 --title "Löneunderlag till Crona Lön (PAXml), del A" --body-file <(printf '%s\n' "Godkänd frånvaro per bolag och månad som PAXml 2.0-fil till Crona Lön. Spec: docs/superpowers/specs/2026-10-02-paxml-crona-design.md" "" "🤖 Generated with [Claude Code](https://claude.com/claude-code)" "" "https://claude.ai/code/session_016yYYj5agMiCoxsTCe4usfY")
gh run watch --exit-status $(gh run list --branch feat/paxml-crona --limit 1 --json databaseId -q '.[0].databaseId')
```
Expected: CI grön.

- [ ] **Step 6: Demo-siten och tillbaka till version-16**

```bash
cd /home/ubbe/ERPNext/my-frappe-bench
bench --site demo-erp.local migrate
git -C apps/hrms_sverige checkout version-16
```

Merge, `migrate` på `svensk-erp.local` och publicering av manualen görs först efter användarens godkännande och provimport i Crona (spec, avsnitt Utrullning).
