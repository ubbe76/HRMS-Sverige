# Löneunderlag till Crona Lön (PAXml), del C2: övertid, mertid och OB – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Alla som stämplar får MER, ÖT1–5/ÖK1–5 och OB1–5 i timmar per dag i löneunderlaget och PAXml-filen, räknat ur närvarons klockslag mot planerat skift och egna tidsregler.

**Architecture:** `lon/regler.py` är ren intervallräkning utan databas (regelfönster, fördelning per nivå med högsta nivån vid överlapp, extra tid utanför skift, mertid upp till heltid). `lon/tillagg.py` läser inställningar, närvaro, skift, helgdagar och övertidsval och bygger tilläggsraderna. `rader_for_period` tar med dem och minskar timavlönades ARB med MER/ÖT/ÖK.

**Tech Stack:** Frappe 16 / HRMS 16 (Python 3.14), ERPNext/HRMS helglistor, `lxml` för schemavalidering i tester.

**Spec:** `docs/superpowers/specs/2026-10-02-paxml-tillagg-design.md` (bygger på del A och B: `2026-10-02-paxml-crona-design.md`, `2026-10-02-paxml-tid-design.md`)

## Global Constraints

- Appen `hrms_sverige` i `apps/hrms_sverige`, gren `feat/paxml-tillagg`. Byt tillbaka till `version-16` när du lämnar arbetet; benchen delas med produktionssiten.
- `bench`-kommandon från `~/frappe-bench`. Tester bara på `<testsite>`. Aldrig `migrate` på `<site>`.
- Efter ändringar i doctype-JSON, custom fields eller `hooks.py`: `bench --site <testsite> clear-cache && bench --site <testsite> migrate`.
- Tabbar, radlängd 110, ruff via pre-commit (inga tvetydiga tecken som `–` i kommentarer; skriv "till"); om pre-commit ändrar en fil: `git add` och committa igen.
- Koder: `MER`, `ÖT1`–`ÖT5`, `ÖK1`–`ÖK5`, `OB1`–`OB5`. Timmar avrundas till två decimaler; rader med 0 timmar tas inte med.
- Tidsregel: Typ `OB` eller `Övertid`, Nivå 1–5, dagar `man tis ons tor fre lor son` + `helgdag`, Från/Till (Till <= Från betyder över midnatt; Från = Till betyder hela dygnet). En regel som går över midnatt hör till dagen den börjar.
- Helgdag = helgdag i den anställdes helglista med `weekly_off = 0`.
- Överlappande regler: högsta nivån gäller. Övertid utan täckande regel: nivå 1. OB utan regel: inget.
- Mertid bara för `sysselsattningsgrad` under 100 (tomt räknas som heltid), upp till `heltid_per_dag` (standard 8) arbetade timmar per dag, från den tidigaste extra tiden.
- Övertidsval: senaste `OUT`-stämpling kopplad till närvaron (`overtidsersattning`), annars Employee `overtid_som`, annars `Pengar`. Komptid ger `ÖK`, annars `ÖT`.
- ARB minskas med MER + ÖT + ÖK för samma närvaro, inte med OB.
- Del A:s och B:s tester ska fortsätta gå igenom.
- Commit-meddelanden på engelska och avslutas med:
  ```
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_016yYYj5agMiCoxsTCe4usfY
  ```

## Review Focus

1. **Arbetspass efter midnatt som täcks av en regel från dagen före** (t.ex. 00:00 till 02:00 på tisdag inom OB2 22–06 från måndag) – ska få OB2. Test i Task 1 (`test_regel_fran_dagen_fore`).
2. **Inga tidsregler inlagda** – inga OB-rader, och övertid blir nivå 1. Test i Task 4 (`test_utan_regler`).
3. **Hela passet utanför skiftet** (t.ex. extrapass på en lördag utan skift för en heltidsanställd) – ingen extra tid utan skift, bara OB. Test i Task 4 (`test_utan_skift_bara_ob`).
4. **HR ändrar ÖT1 till ÖK1 och hämtar sedan igen** – hämtningen ersätter raderna (ändringen försvinner); godkänd fil ska innehålla det som stod vid godkännandet. Test i Task 5 (`test_hr_andrar_kod`).
5. **Närvaro för en månadsavlönad med övertid** – tilläggsrader men ingen ARB. Test i Task 4 (`test_manadsavlonad_far_ob_men_ingen_arb`, i kombination med Task 5:s ARB-test).

---

## Filkarta

| Fil | Ansvar |
|---|---|
| `hrms_sverige/lon/regler.py` (ny) | `Tidsregel`, `regelintervall`, `fordela`, `extra_tid`, `dela_mertid`, `timmar` |
| `hrms_sverige/lon/doctype/loneinstallningar/*`, `lon/doctype/tidsregel/*` (nya) | Inställningar och regeltabell |
| `hrms_sverige/lon/tillagg.py` (ny) | `regler_fran_installningar`, `heltid_per_dag`, `helgdagar`, `overtidsval`, `tillaggsrader`, `narvaro_utan_klockslag` |
| `hrms_sverige/lon/tid.py` (ändras) | `planerat_skift`; `planerade_timmar` via den; `arbetad_tid(..., avdrag=None)` |
| `hrms_sverige/lon/franvaro.py` (ändras) | Tilläggsrader och ARB-avdrag i `rader_for_period` |
| `hrms_sverige/lon/doctype/loneunderlag_rad/loneunderlag_rad.json` (ändras) | `tidkod` inte skrivskyddad |
| `hrms_sverige/lon/doctype/loneunderlag/loneunderlag.py` (ändras) | Varning för närvaro utan klockslag |
| `hrms_sverige/setup/custom_fields.py` (ändras) | `overtid_som` (Employee), `overtidsersattning` (Employee Checkin) |
| `hrms_sverige/tests/utils.py` (ändras) | `make_attendance` med klockslag, `satt_tidsregler` |
| `hrms_sverige/tests/test_regler.py`, `test_tillagg.py` (nya), `test_tid.py`, `test_loneunderlag.py` | Tester |
| `README.md`, `CHANGELOG.md`; docs-repot `docs/personal/loneunderlag.md` | Dokumentation |

---

### Task 1: Intervallräkning (regler.py)

**Files:**
- Create: `hrms_sverige/lon/regler.py`
- Test: `hrms_sverige/tests/test_regler.py`

**Interfaces:**
- Produces:
  - `Tidsregel(typ: str, niva: int, dagar: frozenset[int], helgdag: bool, fran: time, till: time)` (frozen dataclass; `dagar` med `date.weekday()`-nummer, måndag = 0)
  - `OB = "OB"`, `OVERTID = "Övertid"`
  - `regelintervall(regel, dag: date, ar_helgdag: bool) -> list[tuple[datetime, datetime]]`
  - `fordela(intervall: list[tuple[datetime, datetime]], regler: list[Tidsregel], helgdagar: set[date], standardniva: int | None = None) -> dict[int, float]` (timmar per nivå, oavrundade)
  - `extra_tid(arbetat: tuple[datetime, datetime], skift: tuple[datetime, datetime] | None) -> list[tuple[datetime, datetime]]`
  - `dela_mertid(extra: list[tuple[datetime, datetime]], inom_skift_timmar: float, tak_timmar: float) -> tuple[list, list]` (mertid, övertid)
  - `timmar(intervall: list[tuple[datetime, datetime]]) -> float`

- [ ] **Step 1: Skapa grenen** (finns redan med specen)

```bash
cd ~/frappe-bench/apps/hrms_sverige
git checkout feat/paxml-tillagg && git merge --ff-only origin/version-16 || git rebase origin/version-16
```

- [ ] **Step 2: Skriv de fallerande testerna** – `hrms_sverige/tests/test_regler.py`:

```python
from datetime import date, datetime, time

from frappe.tests import UnitTestCase

from hrms_sverige.lon.regler import (
	OB,
	OVERTID,
	Tidsregel,
	dela_mertid,
	extra_tid,
	fordela,
	regelintervall,
	timmar,
)

VARDAGAR = frozenset(range(5))
ALLA = frozenset(range(7))
OB1 = Tidsregel(OB, 1, VARDAGAR, False, time(18), time(22))
OB2 = Tidsregel(OB, 2, ALLA, False, time(22), time(6))
OB3 = Tidsregel(OB, 3, frozenset({5, 6}), True, time(0), time(0))
OT1 = Tidsregel(OVERTID, 1, VARDAGAR, False, time(6), time(20))
OT2 = Tidsregel(OVERTID, 2, ALLA, False, time(20), time(6))
MANDAG = date(2026, 9, 14)
LORDAG = date(2026, 9, 12)
JULDAGEN = date(2026, 12, 25)  # fredag


def dt(dag, timme, minut=0):
	return datetime.combine(dag, time(timme, minut))


class TestRegler(UnitTestCase):
	def test_regelintervall_over_midnatt(self):
		self.assertEqual(regelintervall(OB2, MANDAG, False), [(dt(MANDAG, 22), dt(date(2026, 9, 15), 6))])

	def test_fran_lika_med_till_ar_hela_dygnet(self):
		self.assertEqual(regelintervall(OB3, LORDAG, False), [(dt(LORDAG, 0), dt(date(2026, 9, 13), 0))])

	def test_helgdag_kontra_vardag(self):
		self.assertEqual(len(regelintervall(OB3, JULDAGEN, True)), 1)
		self.assertEqual(regelintervall(OB3, date(2026, 9, 18), False), [])

	def test_ob_fordelas_per_niva(self):
		self.assertEqual(fordela([(dt(MANDAG, 14), dt(MANDAG, 23, 30))], [OB1, OB2, OB3], set()), {1: 4.0, 2: 1.5})

	def test_overlapp_ger_hogsta_nivan(self):
		self.assertEqual(fordela([(dt(LORDAG, 20), dt(LORDAG, 23))], [OB1, OB2, OB3], set()), {3: 3.0})

	def test_regel_fran_dagen_fore(self):
		tisdag = date(2026, 9, 15)
		self.assertEqual(fordela([(dt(tisdag, 0), dt(tisdag, 2))], [OB1, OB2], set()), {2: 2.0})

	def test_juldagen_som_helgdag(self):
		self.assertEqual(fordela([(dt(JULDAGEN, 10), dt(JULDAGEN, 14))], [OB1, OB2, OB3], {JULDAGEN}), {3: 4.0})

	def test_overtid_over_tva_nivaer(self):
		self.assertEqual(
			fordela([(dt(MANDAG, 18), dt(MANDAG, 21))], [OT1, OT2], set(), standardniva=1), {1: 2.0, 2: 1.0}
		)

	def test_overtid_utan_regel_far_niva_1(self):
		self.assertEqual(fordela([(dt(MANDAG, 17), dt(MANDAG, 19))], [OT2], set(), standardniva=1), {1: 2.0})

	def test_ob_utan_regel_ger_inget(self):
		self.assertEqual(fordela([(dt(MANDAG, 9), dt(MANDAG, 12))], [OB1, OB2], set()), {})

	def test_extra_tid_fore_och_efter_skiftet(self):
		self.assertEqual(
			extra_tid((dt(MANDAG, 7), dt(MANDAG, 18, 30)), (dt(MANDAG, 8), dt(MANDAG, 16, 30))),
			[(dt(MANDAG, 7), dt(MANDAG, 8)), (dt(MANDAG, 16, 30), dt(MANDAG, 18, 30))],
		)

	def test_ingen_extra_tid_utan_skift(self):
		self.assertEqual(extra_tid((dt(MANDAG, 7), dt(MANDAG, 19)), None), [])

	def test_mertid_upp_till_heltid(self):
		extra = [(dt(MANDAG, 16, 30), dt(MANDAG, 18, 30))]
		self.assertEqual(dela_mertid(extra, 4, 8), (extra, []))
		self.assertEqual(
			dela_mertid(extra, 7, 8),
			([(dt(MANDAG, 16, 30), dt(MANDAG, 17, 30))], [(dt(MANDAG, 17, 30), dt(MANDAG, 18, 30))]),
		)

	def test_ingen_mertid_nar_skiftet_redan_ar_heltid(self):
		extra = [(dt(MANDAG, 16, 30), dt(MANDAG, 18, 30))]
		self.assertEqual(dela_mertid(extra, 8.5, 8), ([], extra))

	def test_timmar(self):
		self.assertEqual(timmar([(dt(MANDAG, 7), dt(MANDAG, 8)), (dt(MANDAG, 16, 30), dt(MANDAG, 18))]), 2.5)
```

- [ ] **Step 3: Kör och se dem fallera**

Run: `bench --site <testsite> run-tests --app hrms_sverige --module hrms_sverige.tests.test_regler`
Expected: ERROR, `ModuleNotFoundError: No module named 'hrms_sverige.lon.regler'`.

- [ ] **Step 4: Implementera** – `hrms_sverige/lon/regler.py`:

```python
"""Tidsregler för OB och övertid: ren intervallräkning utan databas."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

OB = "OB"
OVERTID = "Övertid"

Intervall = tuple[datetime, datetime]


@dataclass(frozen=True)
class Tidsregel:
	typ: str
	niva: int
	dagar: frozenset[int]  # date.weekday(): måndag = 0
	helgdag: bool
	fran: time
	till: time


def regelintervall(regel: Tidsregel, dag: date, ar_helgdag: bool) -> list[Intervall]:
	"""Regelns period den dagen. Till <= Från går över midnatt; Från = Till är hela dygnet."""
	if dag.weekday() not in regel.dagar and not (ar_helgdag and regel.helgdag):
		return []
	start = datetime.combine(dag, regel.fran)
	slut = datetime.combine(dag, regel.till)
	if slut <= start:
		slut += timedelta(days=1)
	return [(start, slut)]


def timmar(intervall: list[Intervall]) -> float:
	return sum((slut - start).total_seconds() for start, slut in intervall) / 3600


def fordela(
	intervall: list[Intervall],
	regler: list[Tidsregel],
	helgdagar: set[date],
	standardniva: int | None = None,
) -> dict[int, float]:
	"""Timmar per nivå. Högsta nivån gäller där regler överlappar; tid utan regel får standardnivån."""
	resultat: dict[int, float] = {}
	for start, slut in intervall:
		fonster = []
		dag = start.date() - timedelta(days=1)  # regler från dagen före kan gå över midnatt
		while dag <= slut.date():
			for regel in regler:
				for f_start, f_slut in regelintervall(regel, dag, dag in helgdagar):
					if f_start < slut and f_slut > start:
						fonster.append((max(f_start, start), min(f_slut, slut), regel.niva))
			dag += timedelta(days=1)
		punkter = sorted({start, slut, *(f[0] for f in fonster), *(f[1] for f in fonster)})
		for a, b in zip(punkter, punkter[1:], strict=False):
			nivaer = [niva for f_start, f_slut, niva in fonster if f_start <= a and f_slut >= b]
			niva = max(nivaer) if nivaer else standardniva
			if niva is not None:
				resultat[niva] = resultat.get(niva, 0.0) + (b - a).total_seconds() / 3600
	return resultat


def extra_tid(arbetat: Intervall, skift: Intervall | None) -> list[Intervall]:
	"""Arbetad tid utanför det planerade skiftet. Utan skift finns ingen extra tid."""
	if not skift:
		return []
	in_tid, ut_tid = arbetat
	s_start, s_slut = skift
	extra = []
	if in_tid < min(ut_tid, s_start):
		extra.append((in_tid, min(ut_tid, s_start)))
	if max(in_tid, s_slut) < ut_tid:
		extra.append((max(in_tid, s_slut), ut_tid))
	return extra


def dela_mertid(
	extra: list[Intervall], inom_skift_timmar: float, tak_timmar: float
) -> tuple[list[Intervall], list[Intervall]]:
	"""Delar den extra tiden i mertid (tidigast först, upp till taket) och övertid."""
	kvar = timedelta(hours=max(0.0, tak_timmar - inom_skift_timmar))
	mertid, overtid = [], []
	for start, slut in sorted(extra):
		langd = slut - start
		if kvar >= langd:
			mertid.append((start, slut))
			kvar -= langd
		elif kvar > timedelta(0):
			mertid.append((start, start + kvar))
			overtid.append((start + kvar, slut))
			kvar = timedelta(0)
		else:
			overtid.append((start, slut))
	return mertid, overtid
```

- [ ] **Step 5: Kör testerna**

Run: `bench --site <testsite> run-tests --app hrms_sverige --module hrms_sverige.tests.test_regler`
Expected: OK (15 tester).

- [ ] **Step 6: Commit**

```bash
git add hrms_sverige/lon/regler.py hrms_sverige/tests/test_regler.py
git commit -m "feat: interval arithmetic for OB and overtime rules" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016yYYj5agMiCoxsTCe4usfY"
```

---

### Task 2: Löneinställningar, tidsregler och övertidsfält

**Files:**
- Create: `hrms_sverige/lon/doctype/tidsregel/__init__.py` (tom), `tidsregel.json`, `tidsregel.py`
- Create: `hrms_sverige/lon/doctype/loneinstallningar/__init__.py` (tom), `loneinstallningar.json`, `loneinstallningar.py`
- Create: `hrms_sverige/lon/tillagg.py` (bara `regler_fran_installningar` och `heltid_per_dag` i den här tasken)
- Modify: `hrms_sverige/setup/custom_fields.py`
- Modify: `hrms_sverige/locale/sv.po`
- Modify: `hrms_sverige/tests/utils.py` (`satt_tidsregler`)
- Test: `hrms_sverige/tests/test_tillagg.py`

**Interfaces:**
- Consumes: `Tidsregel`, `OB`, `OVERTID` (Task 1).
- Produces:
  - Single `Loneinstallningar` (`heltid_per_dag` Float standard 8, `tidsregler` Table `Tidsregel`); child `Tidsregel` (`typ`, `niva`, `man`…`son`, `helgdag`, `fran`, `till`).
  - `hrms_sverige.lon.tillagg.regler_fran_installningar() -> list[Tidsregel]`
  - `hrms_sverige.lon.tillagg.heltid_per_dag() -> float`
  - Custom fields `Employee.overtid_som` (Select `Pengar\nKomptid`, standard `Pengar`) och `Employee Checkin.overtidsersattning` (Select `\nPengar\nKomptid`).
  - `hrms_sverige.tests.utils.satt_tidsregler(regler: list[dict], heltid: float = 8) -> None`

- [ ] **Step 1: Barntabellen** – `hrms_sverige/lon/doctype/tidsregel/tidsregel.json`:

```json
{
 "actions": [],
 "creation": "2026-10-02 22:00:00.000000",
 "doctype": "DocType",
 "editable_grid": 1,
 "engine": "InnoDB",
 "field_order": ["typ", "niva", "man", "tis", "ons", "tor", "fre", "lor", "son", "helgdag", "fran", "till"],
 "fields": [
  {"columns": 1, "fieldname": "typ", "fieldtype": "Select", "in_list_view": 1, "label": "Typ", "options": "OB\nÖvertid", "reqd": 1},
  {"columns": 1, "default": "1", "fieldname": "niva", "fieldtype": "Int", "in_list_view": 1, "label": "Nivå", "reqd": 1},
  {"columns": 1, "fieldname": "man", "fieldtype": "Check", "in_list_view": 1, "label": "Mån"},
  {"columns": 1, "fieldname": "tis", "fieldtype": "Check", "in_list_view": 1, "label": "Tis"},
  {"columns": 1, "fieldname": "ons", "fieldtype": "Check", "in_list_view": 1, "label": "Ons"},
  {"columns": 1, "fieldname": "tor", "fieldtype": "Check", "in_list_view": 1, "label": "Tor"},
  {"columns": 1, "fieldname": "fre", "fieldtype": "Check", "in_list_view": 1, "label": "Fre"},
  {"columns": 1, "fieldname": "lor", "fieldtype": "Check", "label": "Lör"},
  {"columns": 1, "fieldname": "son", "fieldtype": "Check", "label": "Sön"},
  {"columns": 1, "fieldname": "helgdag", "fieldtype": "Check", "label": "Helgdag"},
  {"columns": 1, "fieldname": "fran", "fieldtype": "Time", "in_list_view": 1, "label": "Från", "reqd": 1},
  {"columns": 1, "fieldname": "till", "fieldtype": "Time", "in_list_view": 1, "label": "Till", "reqd": 1}
 ],
 "istable": 1,
 "modified": "2026-10-02 22:00:00.000000",
 "modified_by": "Administrator",
 "module": "Lon",
 "name": "Tidsregel",
 "owner": "Administrator",
 "permissions": [],
 "sort_field": "creation",
 "sort_order": "ASC",
 "states": []
}
```

och `tidsregel.py`:

```python
from frappe.model.document import Document


class Tidsregel(Document):
	pass
```

- [ ] **Step 2: Inställningarna** – `hrms_sverige/lon/doctype/loneinstallningar/loneinstallningar.json`:

```json
{
 "actions": [],
 "creation": "2026-10-02 22:00:00.000000",
 "doctype": "DocType",
 "engine": "InnoDB",
 "field_order": ["heltid_per_dag", "section_regler", "tidsregler"],
 "fields": [
  {"default": "8", "description": "Gräns för mertid: deltidsanställda får mertid tills dagens arbetade timmar når heltid, därefter övertid.", "fieldname": "heltid_per_dag", "fieldtype": "Float", "label": "Heltid per dag (timmar)", "reqd": 1},
  {"description": "OB och övertidsnivåer. Till före eller lika med Från går över midnatt; Från = Till är hela dygnet. Helgdag är röda dagar i helglistan. Där regler överlappar gäller högsta nivån.", "fieldname": "section_regler", "fieldtype": "Section Break", "label": "Tidsregler"},
  {"fieldname": "tidsregler", "fieldtype": "Table", "label": "Tidsregler", "options": "Tidsregel"}
 ],
 "issingle": 1,
 "modified": "2026-10-02 22:00:00.000000",
 "modified_by": "Administrator",
 "module": "Lon",
 "name": "Loneinstallningar",
 "owner": "Administrator",
 "permissions": [
  {"create": 1, "print": 1, "read": 1, "role": "HR Manager", "write": 1},
  {"create": 1, "print": 1, "read": 1, "role": "System Manager", "write": 1}
 ],
 "sort_field": "creation",
 "sort_order": "DESC",
 "states": [],
 "track_changes": 1
}
```

och `loneinstallningar.py`:

```python
import frappe
from frappe import _
from frappe.model.document import Document


class Loneinstallningar(Document):
	def validate(self):
		if not self.heltid_per_dag or self.heltid_per_dag <= 0 or self.heltid_per_dag > 24:
			frappe.throw(_("Heltid per dag måste vara större än 0 och högst 24 timmar."))
		for regel in self.tidsregler:
			if not 1 <= (regel.niva or 0) <= 5:
				frappe.throw(_("Tidsregel rad {0}: Nivå måste vara 1 till 5.").format(regel.idx))
			if not any(regel.get(f) for f in ("man", "tis", "ons", "tor", "fre", "lor", "son", "helgdag")):
				frappe.throw(_("Tidsregel rad {0}: välj minst en dag.").format(regel.idx))
```

- [ ] **Step 3: Testhjälp** – lägg sist i `hrms_sverige/tests/utils.py`:

```python
def satt_tidsregler(regler: list[dict], heltid: float = 8) -> None:
	"""Ersätt tidsreglerna i Löneinställningar. Varje regel: typ, niva, dagar (t.ex. "man tis"), fran, till."""
	inst = frappe.get_single("Loneinstallningar")
	inst.heltid_per_dag = heltid
	inst.set("tidsregler", [])
	for regel in regler:
		rad = {"typ": regel["typ"], "niva": regel["niva"], "fran": regel["fran"], "till": regel["till"]}
		for dag in regel["dagar"].split():
			rad[dag] = 1
		inst.append("tidsregler", rad)
	inst.save()
```

- [ ] **Step 4: Skriv de fallerande testerna** – `hrms_sverige/tests/test_tillagg.py`:

```python
from datetime import time

import frappe
from frappe.tests import IntegrationTestCase

from hrms_sverige.lon.regler import OB, OVERTID
from hrms_sverige.lon.tillagg import heltid_per_dag, regler_fran_installningar
from hrms_sverige.setup.custom_fields import create_custom_fields
from hrms_sverige.tests.utils import ensure_test_company, satt_tidsregler


class TestLoneinstallningar(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_test_company()
		create_custom_fields()

	def setUp(self):
		frappe.db.savepoint("inst_test")

	def tearDown(self):
		frappe.db.rollback(save_point="inst_test")

	def test_regler_lases_in(self):
		satt_tidsregler(
			[
				{"typ": "OB", "niva": 1, "dagar": "man tis ons tor fre", "fran": "18:00:00", "till": "22:00:00"},
				{"typ": "Övertid", "niva": 2, "dagar": "lor son helgdag", "fran": "00:00:00", "till": "00:00:00"},
			],
			heltid=7.5,
		)
		ob, ot = regler_fran_installningar()
		self.assertEqual((ob.typ, ob.niva, ob.dagar, ob.helgdag, ob.fran, ob.till), (OB, 1, frozenset(range(5)), False, time(18), time(22)))
		self.assertEqual((ot.typ, ot.niva, ot.dagar, ot.helgdag), (OVERTID, 2, frozenset({5, 6}), True))
		self.assertEqual(heltid_per_dag(), 7.5)

	def test_niva_utanfor_1_till_5_stoppas(self):
		self.assertRaisesRegex(
			frappe.ValidationError,
			"Nivå",
			satt_tidsregler,
			[{"typ": "OB", "niva": 6, "dagar": "man", "fran": "18:00:00", "till": "22:00:00"}],
		)

	def test_regel_utan_dag_stoppas(self):
		self.assertRaisesRegex(
			frappe.ValidationError,
			"minst en dag",
			satt_tidsregler,
			[{"typ": "OB", "niva": 1, "dagar": "", "fran": "18:00:00", "till": "22:00:00"}],
		)

	def test_overtidsfalt_finns(self):
		self.assertEqual(frappe.get_meta("Employee").get_field("overtid_som").options.split("\n"), ["Pengar", "Komptid"])
		self.assertEqual(
			frappe.get_meta("Employee Checkin").get_field("overtidsersattning").options.split("\n"),
			["", "Pengar", "Komptid"],
		)
```

- [ ] **Step 5: Kör och se dem fallera**

Run: `bench --site <testsite> clear-cache && bench --site <testsite> migrate && bench --site <testsite> run-tests --app hrms_sverige --module hrms_sverige.tests.test_tillagg`
Expected: ERROR, `ModuleNotFoundError: No module named 'hrms_sverige.lon.tillagg'`. (`migrate` skapar doctypes; controllerfilerna finns redan från Step 1–2.)

- [ ] **Step 6: Implementera** – `hrms_sverige/lon/tillagg.py`:

```python
"""Övertid, mertid och OB för löneunderlaget, räknat ur närvarons klockslag."""

import frappe
from frappe.utils import flt, to_timedelta

from hrms_sverige.lon.regler import Tidsregel

DAGFALT = ("man", "tis", "ons", "tor", "fre", "lor", "son")


def _tid(varde):
	return (frappe.utils.get_datetime("2000-01-01") + to_timedelta(varde)).time()


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
```

I `hrms_sverige/setup/custom_fields.py`: lägg sist i listan `"Employee"` (efter `loneform`):

```python
			{
				"fieldname": "overtid_som",
				"label": _("Övertid som"),
				"fieldtype": "Select",
				"options": "Pengar\nKomptid",
				"default": "Pengar",
				"insert_after": "loneform",
				"description": _("Förval när utstämplingen inte anger något: övertid som pengar (ÖT) eller komptid (ÖK)."),
			},
```

och lägg till nyckeln:

```python
		"Employee Checkin": [
			{
				"fieldname": "overtidsersattning",
				"label": _("Övertidsersättning"),
				"fieldtype": "Select",
				"options": "\nPengar\nKomptid",
				"insert_after": "log_type",
				"description": _("Väljs vid utstämpling utanför skiftet. Tomt: den anställdes förval gäller."),
			},
		],
```

och i `hrms_sverige/locale/sv.po`, sist:

```
msgid "Loneinstallningar"
msgstr "Löneinställningar"

msgid "Tidsregel"
msgstr "Tidsregel"
```

Kompilera: `bench compile-po-to-mo --app hrms_sverige --locale sv --force`

- [ ] **Step 7: Migrera och kör testerna**

Run: `bench --site <testsite> clear-cache && bench --site <testsite> migrate && bench --site <testsite> run-tests --app hrms_sverige --module hrms_sverige.tests.test_tillagg`
Expected: OK (4 tester).

- [ ] **Step 8: Commit**

```bash
git add hrms_sverige/lon/doctype/tidsregel hrms_sverige/lon/doctype/loneinstallningar hrms_sverige/lon/tillagg.py hrms_sverige/setup/custom_fields.py hrms_sverige/locale/sv.po hrms_sverige/tests/utils.py hrms_sverige/tests/test_tillagg.py
git commit -m "feat: payroll settings with OB and overtime rules, overtime choice fields" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016yYYj5agMiCoxsTCe4usfY"
```

---

### Task 3: Planerat skift med klockslag

**Files:**
- Modify: `hrms_sverige/lon/tid.py`
- Test: `hrms_sverige/tests/test_tid.py`

**Interfaces:**
- Produces: `hrms_sverige.lon.tid.planerat_skift(employee: str, datum) -> tuple[datetime, datetime] | None`. `planerade_timmar` räknas från den (samma beteende som förut).

- [ ] **Step 1: Skriv de fallerande testerna** – lägg till i klassen `TestTid` i `hrms_sverige/tests/test_tid.py` (och `planerat_skift` i importen från `hrms_sverige.lon.tid`, `from datetime import date, datetime`):

```python
	def test_planerat_skift_med_klockslag(self):
		anstalld = self.timanstalld("Tid Klockslag", "T-20")
		assign_shift(anstalld, self.dag, "2026-09-01")
		self.assertEqual(
			planerat_skift(anstalld, "2026-09-14"),
			(datetime(2026, 9, 14, 8, 0), datetime(2026, 9, 14, 16, 30)),
		)

	def test_planerat_nattskift_slutar_nasta_dag(self):
		anstalld = self.timanstalld("Tid Klockslag Natt", "T-21")
		frappe.db.set_value("Employee", anstalld, "default_shift", self.natt)
		self.assertEqual(
			planerat_skift(anstalld, "2026-09-14"),
			(datetime(2026, 9, 14, 22, 0), datetime(2026, 9, 15, 6, 0)),
		)

	def test_inget_planerat_skift_pa_helgdag(self):
		anstalld = self.timanstalld("Tid Klockslag Helg", "T-22")
		assign_shift(anstalld, self.dag, "2026-09-01")
		self.assertIsNone(planerat_skift(anstalld, "2026-09-12"))
```

- [ ] **Step 2: Kör och se dem fallera**

Run: `bench --site <testsite> run-tests --app hrms_sverige --module hrms_sverige.tests.test_tid`
Expected: ERROR, `ImportError: cannot import name 'planerat_skift'`.

- [ ] **Step 3: Implementera** – i `hrms_sverige/lon/tid.py`, lägg till `from datetime import date, datetime, timedelta` och ersätt `planerade_timmar` med:

```python
def planerat_skift(employee: str, datum) -> tuple[datetime, datetime] | None:
	"""Det planerade skiftets start och slut den dagen; None på helgdagar och utan skift."""
	datum = getdate(datum)
	if is_holiday(employee, datum, raise_exception=False):
		return None
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
		return None
	start, slut = frappe.db.get_value("Shift Type", skift, ["start_time", "end_time"])
	borjan = datetime.combine(datum, datetime.min.time()) + to_timedelta(start)
	return borjan, borjan + timedelta(hours=skiftlangd(start, slut))


def planerade_timmar(employee: str, datum) -> float:
	"""Timmar enligt planerat skift den dagen; 0 på helgdagar och utan skift."""
	skift = planerat_skift(employee, datum)
	return (skift[1] - skift[0]).total_seconds() / 3600 if skift else 0.0
```

- [ ] **Step 4: Kör testerna**

Run: `bench --site <testsite> run-tests --app hrms_sverige --module hrms_sverige.tests.test_tid`
Expected: OK (19 tester, inklusive del B:s).

- [ ] **Step 5: Commit**

```bash
git add hrms_sverige/lon/tid.py hrms_sverige/tests/test_tid.py
git commit -m "feat: planned shift with start and end time" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016yYYj5agMiCoxsTCe4usfY"
```

---

### Task 4: Tilläggsrader

**Files:**
- Modify: `hrms_sverige/lon/tillagg.py`
- Modify: `hrms_sverige/tests/utils.py` (`make_attendance` med klockslag)
- Test: `hrms_sverige/tests/test_tillagg.py`

**Interfaces:**
- Consumes: `regler.py` (Task 1); `regler_fran_installningar`, `heltid_per_dag`, `satt_tidsregler`, custom fields (Task 2); `planerat_skift` (Task 3); testhjälparna `make_test_employee`, `make_shift_type`, `assign_shift`, `make_checkin`, `create_holiday_list`.
- Produces:
  - `hrms_sverige.lon.tillagg.helgdagar(employee: str, from_date, to_date) -> set[date]`
  - `hrms_sverige.lon.tillagg.overtidsval(attendance: str, employee: str) -> str` (`"Pengar"` eller `"Komptid"`)
  - `hrms_sverige.lon.tillagg.tillaggsrader(company: str, from_date, to_date) -> list[dict]` – nycklar `employee`, `tidkod`, `from_date`, `to_date`, `timmar` (två decimaler), `attendance`; ordning per närvaro: MER, ÖT/ÖK stigande nivå, OB stigande nivå.
  - `hrms_sverige.lon.tillagg.narvaro_utan_klockslag(company: str, from_date, to_date) -> dict[str, list[date]]`
  - `make_attendance(employee, datum, working_hours, status="Present", submit=True, in_time=None, out_time=None) -> str`

- [ ] **Step 1: Klockslag i testhjälpen** – i `hrms_sverige/tests/utils.py`, ändra `make_attendance` till:

```python
def make_attendance(
	employee: str,
	datum: str,
	working_hours: float,
	status: str = "Present",
	submit: bool = True,
	in_time: str | None = None,
	out_time: str | None = None,
) -> str:
	doc = frappe.get_doc(
		{
			"doctype": "Attendance",
			"employee": employee,
			"company": COMPANY,
			"attendance_date": datum,
			"status": status,
			"working_hours": working_hours,
			"in_time": in_time,
			"out_time": out_time,
		}
	).insert()
	if submit:
		doc.submit()
	return doc.name
```

- [ ] **Step 2: Skriv de fallerande testerna** – lägg sist i `hrms_sverige/tests/test_tillagg.py` (utöka importerna: `from datetime import date, time`; `from hrms_sverige.lon.tillagg import heltid_per_dag, narvaro_utan_klockslag, regler_fran_installningar, tillaggsrader`; `from hrms_sverige.setup.holidays import create_holiday_list`; från `hrms_sverige.tests.utils` även `COMPANY, assign_shift, make_attendance, make_checkin, make_shift_type, make_test_employee`):

```python
SEPT = (date(2026, 9, 1), date(2026, 9, 30))
REGLER = [
	{"typ": "OB", "niva": 1, "dagar": "man tis ons tor fre", "fran": "18:00:00", "till": "22:00:00"},
	{"typ": "OB", "niva": 2, "dagar": "man tis ons tor fre lor son", "fran": "22:00:00", "till": "06:00:00"},
	{"typ": "OB", "niva": 3, "dagar": "lor son helgdag", "fran": "00:00:00", "till": "00:00:00"},
	{"typ": "Övertid", "niva": 1, "dagar": "man tis ons tor fre", "fran": "06:00:00", "till": "20:00:00"},
	{"typ": "Övertid", "niva": 2, "dagar": "man tis ons tor fre lor son helgdag", "fran": "20:00:00", "till": "06:00:00"},
]


class TestTillaggsrader(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_test_company()
		create_custom_fields()
		create_holiday_list(2026, COMPANY)
		cls.dag = make_shift_type("_Test Dag", "08:00:00", "16:30:00")
		cls.halv = make_shift_type("_Test Halv", "08:00:00", "12:00:00")

	def setUp(self):
		frappe.db.savepoint("tillagg_test")
		satt_tidsregler(REGLER)

	def tearDown(self):
		frappe.db.rollback(save_point="tillagg_test")

	def anstalld(self, namn, nummer, skift=None, **falt):
		anstalld = make_test_employee(namn, employee_number=nummer, **falt)
		if skift:
			assign_shift(anstalld, skift, "2026-08-01")
		return anstalld

	def egna(self, anstalld):
		return [(r["tidkod"], str(r["from_date"]), r["timmar"]) for r in tillaggsrader(COMPANY, *SEPT) if r["employee"] == anstalld]

	def test_overtid_och_ob_for_heltid(self):
		a = self.anstalld("Till Heltid", "TL-1", self.dag, sysselsattningsgrad=100)
		make_attendance(a, "2026-09-14", 11, in_time="2026-09-14 08:00:00", out_time="2026-09-14 19:00:00")
		self.assertEqual(self.egna(a), [("ÖT1", "2026-09-14", 2.5), ("OB1", "2026-09-14", 1.0)])

	def test_komptid_fran_utstampling(self):
		a = self.anstalld("Till Komp", "TL-2", self.dag)
		narvaro = make_attendance(a, "2026-09-14", 11, in_time="2026-09-14 08:00:00", out_time="2026-09-14 19:00:00")
		utstampling = make_checkin(a, "2026-09-14 19:00:00", "OUT")
		frappe.db.set_value("Employee Checkin", utstampling, {"attendance": narvaro, "overtidsersattning": "Komptid"})
		self.assertEqual(self.egna(a)[0], ("ÖK1", "2026-09-14", 2.5))

	def test_forval_komptid_pa_anstalld(self):
		a = self.anstalld("Till Förval", "TL-3", self.dag, overtid_som="Komptid")
		make_attendance(a, "2026-09-14", 11, in_time="2026-09-14 08:00:00", out_time="2026-09-14 19:00:00")
		self.assertEqual(self.egna(a)[0], ("ÖK1", "2026-09-14", 2.5))

	def test_utstampling_pengar_vinner_over_forval(self):
		a = self.anstalld("Till Pengar", "TL-4", self.dag, overtid_som="Komptid")
		narvaro = make_attendance(a, "2026-09-14", 11, in_time="2026-09-14 08:00:00", out_time="2026-09-14 19:00:00")
		utstampling = make_checkin(a, "2026-09-14 19:00:00", "OUT")
		frappe.db.set_value("Employee Checkin", utstampling, {"attendance": narvaro, "overtidsersattning": "Pengar"})
		self.assertEqual(self.egna(a)[0], ("ÖT1", "2026-09-14", 2.5))

	def test_mertid_for_deltid(self):
		a = self.anstalld("Till Deltid", "TL-5", self.halv, sysselsattningsgrad=50)
		make_attendance(a, "2026-09-15", 10, in_time="2026-09-15 08:00:00", out_time="2026-09-15 18:00:00")
		self.assertEqual(self.egna(a), [("MER", "2026-09-15", 4.0), ("ÖT1", "2026-09-15", 2.0)])

	def test_overtid_over_tva_nivaer_och_ob(self):
		a = self.anstalld("Till Kväll", "TL-6", self.dag)
		make_attendance(a, "2026-09-16", 12.5, in_time="2026-09-16 08:00:00", out_time="2026-09-16 21:00:00")
		self.assertEqual(
			self.egna(a),
			[("ÖT1", "2026-09-16", 3.5), ("ÖT2", "2026-09-16", 1.0), ("OB1", "2026-09-16", 3.0)],
		)

	def test_utan_skift_bara_ob(self):
		a = self.anstalld("Till Lördag", "TL-7", self.dag)
		make_attendance(a, "2026-09-12", 4, in_time="2026-09-12 10:00:00", out_time="2026-09-12 14:00:00")
		self.assertEqual(self.egna(a), [("OB3", "2026-09-12", 4.0)])

	def test_manadsavlonad_far_ob_men_ingen_arb(self):
		a = self.anstalld("Till Månad", "TL-8", self.dag)
		make_attendance(a, "2026-09-14", 11, in_time="2026-09-14 08:00:00", out_time="2026-09-14 19:00:00")
		self.assertEqual([r[0] for r in self.egna(a)], ["ÖT1", "OB1"])

	def test_utan_regler(self):
		satt_tidsregler([])
		a = self.anstalld("Till Utan Regler", "TL-9", self.dag)
		make_attendance(a, "2026-09-14", 11, in_time="2026-09-14 08:00:00", out_time="2026-09-14 19:00:00")
		self.assertEqual(self.egna(a), [("ÖT1", "2026-09-14", 2.5)])

	def test_narvaro_utan_klockslag(self):
		a = self.anstalld("Till Utan Tid", "TL-10", self.dag)
		make_attendance(a, "2026-09-17", 10)
		self.assertEqual(self.egna(a), [])
		self.assertEqual(narvaro_utan_klockslag(COMPANY, *SEPT).get(a), [date(2026, 9, 17)])
```

(I `test_mertid_for_deltid`: skift 08–12 = 4 h, arbetat 08–18 = 10 h, extra 12–18 = 6 h; mertid upp till 8 h ger 4 h MER 12–16, övertid 16–18 = ÖT1 2 h; OB börjar 18:00, alltså ingen OB. I `test_overtid_over_tva_nivaer_och_ob`: extra 16:30–21:00 = 4,5 h; ÖT1 till 20:00 = 3,5 h, ÖT2 20–21 = 1 h; OB1 18–21 = 3 h.)

- [ ] **Step 3: Kör och se dem fallera**

Run: `bench --site <testsite> run-tests --app hrms_sverige --module hrms_sverige.tests.test_tillagg`
Expected: ERROR, `ImportError: cannot import name 'narvaro_utan_klockslag'` (och `tillaggsrader`).

- [ ] **Step 4: Implementera** – lägg till i `hrms_sverige/lon/tillagg.py` (utöka importerna med `from datetime import date`, `from frappe.utils import flt, get_datetime, getdate, to_timedelta`, `from hrms.utils.holiday_list import get_holiday_list_for_employee`, `from hrms_sverige.lon.regler import OB, OVERTID, Tidsregel, dela_mertid, extra_tid, fordela, timmar` och `from hrms_sverige.lon.tid import planerat_skift`):

```python
NARVARO_STATUS = ("Present", "Half Day")
KOMPTID = "Komptid"


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
```

- [ ] **Step 5: Kör testerna**

Run: `bench --site <testsite> run-tests --app hrms_sverige --module hrms_sverige.tests.test_tillagg`
Expected: OK (14 tester). Om HRMS stoppar testdata (t.ex. närvaro med klockslag mot skift, eller stämpling som får skiftfält), justera **testdata**, inte beräkningen.

- [ ] **Step 6: Commit**

```bash
git add hrms_sverige/lon/tillagg.py hrms_sverige/tests/utils.py hrms_sverige/tests/test_tillagg.py
git commit -m "feat: overtime, extra time and OB rows from attendance clock times" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016yYYj5agMiCoxsTCe4usfY"
```

---

### Task 5: Löneunderlaget med tillägg

**Files:**
- Modify: `hrms_sverige/lon/tid.py` (`arbetad_tid` med avdrag)
- Modify: `hrms_sverige/lon/franvaro.py` (`rader_for_period`)
- Modify: `hrms_sverige/lon/doctype/loneunderlag_rad/loneunderlag_rad.json` (`tidkod` ej skrivskyddad)
- Modify: `hrms_sverige/lon/doctype/loneunderlag/loneunderlag.py` (varning)
- Test: `hrms_sverige/tests/test_loneunderlag.py`

**Interfaces:**
- Consumes: `tillaggsrader`, `narvaro_utan_klockslag` (Task 4); `satt_tidsregler` (Task 2); `make_attendance` med klockslag (Task 4).
- Produces: `arbetad_tid(company, from_date, to_date, avdrag: dict[str, float] | None = None) -> list[dict]`; `rader_for_period` innehåller tilläggsraderna efter ARB.

- [ ] **Step 1: Skriv de fallerande testerna** – lägg sist i `hrms_sverige/tests/test_loneunderlag.py` (utöka importen från `hrms_sverige.tests.utils` med `satt_tidsregler`):

```python
class TestLoneunderlagTillagg(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_test_company()
		create_custom_fields()
		ensure_leave_types()
		ensure_paxml_tidkoder()
		create_holiday_list(2026, COMPANY)
		cls.dag = make_shift_type("_Test Dag", "08:00:00", "16:30:00")
		cls.tim = make_test_employee("Lön Tillägg", employee_number="LTT-1", loneform="Timlön")
		assign_shift(cls.tim, cls.dag, "2026-08-01")
		cls.narvaro = make_attendance(
			cls.tim, "2026-09-14", 11, in_time="2026-09-14 08:00:00", out_time="2026-09-14 19:00:00"
		)

	def setUp(self):
		frappe.db.savepoint("lu_tillagg_test")
		satt_tidsregler(
			[
				{"typ": "OB", "niva": 1, "dagar": "man tis ons tor fre", "fran": "18:00:00", "till": "22:00:00"},
				{"typ": "Övertid", "niva": 1, "dagar": "man tis ons tor fre", "fran": "06:00:00", "till": "20:00:00"},
			]
		)

	def tearDown(self):
		frappe.db.rollback(save_point="lu_tillagg_test")

	def egna(self, doc):
		return [(r.tidkod, str(r.from_date), r.timmar) for r in doc.rader if r.employee == self.tim]

	def test_arb_minskas_med_overtid_men_inte_ob(self):
		doc = nytt_underlag()
		doc.hamta_franvaro()
		self.assertEqual(
			self.egna(doc),
			[("ARB", "2026-09-14", 8.5), ("ÖT1", "2026-09-14", 2.5), ("OB1", "2026-09-14", 1.0)],
		)

	def test_hr_andrar_kod(self):
		doc = nytt_underlag()
		doc.hamta_franvaro()
		doc.set("rader", [r for r in doc.rader if r.employee == self.tim])
		next(r for r in doc.rader if r.tidkod == "ÖT1").tidkod = "ök1"
		doc.save()
		doc.submit()
		self.assertIn("ÖK1", [r.tidkod for r in doc.rader])
		ladda_ner(doc.name)
		rot = etree.fromstring(frappe.response.filecontent)
		xsd = os.path.join(os.path.dirname(__file__), "fixtures", "paxml-2.0.xsd")
		schema = etree.XMLSchema(etree.parse(xsd))
		self.assertTrue(schema.validate(rot), schema.error_log)
		self.assertEqual(
			[t.findtext("tidkod") for t in rot.iter("tidtrans")], ["ARB", "ÖK1", "OB1"]
		)

	def test_varning_for_narvaro_utan_klockslag(self):
		make_attendance(self.tim, "2026-09-15", 8.5)
		doc = nytt_underlag()
		doc.hamta_franvaro()
		doc.set("rader", [r for r in doc.rader if r.employee == self.tim])
		doc.save()
		with patch("frappe.msgprint") as msgprint:
			doc.submit()
		self.assertTrue(any("utan in- eller utstämplingstid" in str(c) for c in msgprint.call_args_list))
		self.assertEqual(doc.docstatus, 1)
```

- [ ] **Step 2: Kör och se dem fallera**

Run: `bench --site <testsite> run-tests --app hrms_sverige --module hrms_sverige.tests.test_loneunderlag`
Expected: FAIL i `TestLoneunderlagTillagg` (ARB 11.0 och inga tilläggsrader; ingen varning). Del A:s och B:s klasser går igenom.

- [ ] **Step 3: ARB-avdrag** – i `hrms_sverige/lon/tid.py`, ändra signaturen och timmarna i `arbetad_tid`:

```python
def arbetad_tid(company: str, from_date, to_date, avdrag: dict[str, float] | None = None) -> list[dict]:
	"""ARB-rader från timavlönades godkända närvaro i perioden.

	`avdrag` är timmar per närvaro som skickas som MER eller ÖT/ÖK och därför inte ska räknas som ARB.
	"""
```

och ersätt listan som returneras med:

```python
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
```

- [ ] **Step 4: Raderna** – i `hrms_sverige/lon/franvaro.py`, importera `from hrms_sverige.lon.tillagg import tillaggsrader` och ersätt raden `rader.extend(arbetad_tid(company, from_date, to_date))` med:

```python
	tillagg = tillaggsrader(company, from_date, to_date)
	avdrag: dict[str, float] = {}
	for r in tillagg:
		if r["tidkod"] == "MER" or r["tidkod"][:2] in ("ÖT", "ÖK"):
			avdrag[r["attendance"]] = avdrag.get(r["attendance"], 0.0) + r["timmar"]
	rader.extend(arbetad_tid(company, from_date, to_date, avdrag))
	rader.extend(tillagg)
```

(Sorteringen är stabil, så ARB kommer före tilläggen för samma närvaro.)

- [ ] **Step 5: Ändringsbar tidkod** – i `loneunderlag_rad.json`, ta bort `"read_only": 1` från fältet `tidkod`, lägg till `"description": "Kan ändras på rader för arbetad tid, övertid och OB (t.ex. ÖT1 till ÖK1). Frånvarorader får koden från frånvarotypen."` och sätt `"modified": "2026-10-02 23:00:00.000000"`.

- [ ] **Step 6: Varningen** – i `loneunderlag.py`, importera `from hrms_sverige.lon.tillagg import narvaro_utan_klockslag` och lägg sist i `before_submit`:

```python
		utan_tid = narvaro_utan_klockslag(self.company, self.from_date, self.to_date)
		if utan_tid:
			frappe.msgprint(
				_(
					"Närvaro utan in- eller utstämplingstid: {0}. För de dagarna räknas varken övertid eller OB."
				).format(
					"; ".join(
						f"{anstalld} ({', '.join(str(d) for d in dagar)})"
						for anstalld, dagar in sorted(utan_tid.items())
					)
				),
				title=_("Övertid och OB saknas"),
				indicator="orange",
			)
```

- [ ] **Step 7: Migrera och kör testerna**

Run: `bench --site <testsite> clear-cache && bench --site <testsite> migrate && bench --site <testsite> run-tests --app hrms_sverige --module hrms_sverige.tests.test_loneunderlag`
Expected: OK (alla klasser).

- [ ] **Step 8: Hela sviten**

Run: `bench --site <testsite> run-tests --app hrms_sverige`
Expected: OK. Del B:s ARB-tester (närvaro utan klockslag) ger oförändrad ARB.

- [ ] **Step 9: Commit**

```bash
git add hrms_sverige/lon hrms_sverige/tests/test_loneunderlag.py
git commit -m "feat: overtime, extra time and OB in the Löneunderlag, ARB reduced accordingly" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016yYYj5agMiCoxsTCe4usfY"
```

---

### Task 6: Dokumentation, PR och CI

**Files:**
- Modify: `README.md`, `CHANGELOG.md`
- Modify: docs-repot `docs/personal/loneunderlag.md` (grenen `personal/loneunderlag`)

- [ ] **Step 1: README** – lägg till efter punkten om löneunderlag under "## HRMS Sverige":

```markdown
- Övertid, mertid och OB: egna tidsregler i **Löneinställningar** (veckodagar, helgdagar och klockslag per nivå).
  Närvarons in- och utstämplingstid jämförs med planerat skift och ger MER, ÖT1–ÖT5 eller ÖK1–ÖK5 och OB1–OB5 i
  löneunderlaget. Valet pengar eller komptid tas från utstämplingen eller den anställdes förval.
```

- [ ] **Step 2: CHANGELOG** – lägg till under `## Ej släppt`:

```markdown
- **Övertid, mertid och OB:** Löneinställningar med tidsregler, fälten Övertid som (anställd) och
  Övertidsersättning (stämpling). Tilläggsrader per närvaro; timavlönades ARB minskas med MER och ÖT/ÖK.
```

- [ ] **Step 3: Manualen** – i docs-repot (`git checkout personal/loneunderlag`), lägg till före "## Varje månad" i `docs/personal/loneunderlag.md`:

```markdown
## Övertid, mertid och OB

Övertid, mertid och OB räknas ur närvarons in- och utstämplingstid, för alla som stämplar.

**Ställ in reglerna** under **Löneinställningar**:

- **Heltid per dag** (standard 8 timmar) är gränsen för mertid.
- **Tidsregler**: varje rad har typ (OB eller Övertid), nivå 1–5, dagar och klockslag. Till före Från går över
  midnatt, och Från = Till betyder hela dygnet. *Helgdag* är röda dagar i helglistan. Där regler överlappar gäller
  den högsta nivån.

| Typ | Nivå | Dagar | Från | Till |
|---|---|---|---|---|
| OB | 1 | mån–fre | 18:00 | 22:00 |
| OB | 2 | alla dagar | 22:00 | 06:00 |
| OB | 3 | lör, sön, helgdag | 00:00 | 00:00 |
| Övertid | 1 | mån–fre | 06:00 | 20:00 |
| Övertid | 2 | alla dagar och helgdag | 20:00 | 06:00 |

**Så räknas det per dag:**

- Tid utanför det planerade skiftet är extra tid. Utan skift blir det ingen extra tid, bara OB.
- Deltidsanställda får **MER** tills dagens arbetade tid når heltid; resten blir övertid.
- Övertiden delas efter övertidsreglerna och blir **ÖT** (pengar) eller **ÖK** (komptid). Valet görs vid
  utstämplingen (*Övertidsersättning*), annars gäller den anställdes *Övertid som*.
- **OB** räknas på hela passet.

HR kan ändra koden på en rad i löneunderlaget (till exempel ÖT1 till ÖK1) eller ta bort övertid som inte var
beordrad, innan underlaget godkänns. Närvaro utan stämplingstider ger en varning, eftersom där inte går att räkna
övertid eller OB.

**I Crona:** koppla MER, ÖT1–ÖT5, ÖK1–ÖK5 och OB1–OB5 under **Register > Löneartsstyrning**. För timavlönade
dras MER- och övertidstimmarna från ARB, så lönearterna för MER och ÖT ska omfatta hela timlönen plus tillägget.
OB är ett rent tillägg.
```

Bygg: `cd <docs-repo> && .venv/bin/mkdocs build --strict -q` – Expected: exit 0.

- [ ] **Step 4: Commit i båda repona**

```bash
cd ~/frappe-bench/apps/hrms_sverige
git add README.md CHANGELOG.md
git commit -m "docs: document overtime, extra time and OB" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016yYYj5agMiCoxsTCe4usfY"
cd <docs-repo>
git add docs/personal/loneunderlag.md
git commit -m "docs: overtime, extra time and OB in the payroll export" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016yYYj5agMiCoxsTCe4usfY"
git push
git checkout main
```

- [ ] **Step 5: Push, PR och CI**

```bash
cd ~/frappe-bench/apps/hrms_sverige
git push -u origin feat/paxml-tillagg
gh pr create --base version-16 --title "Löneunderlag: övertid, mertid och OB (PAXml, del C2)" --body "Del C2 av löneunderlaget till Crona Lön. Spec: docs/superpowers/specs/2026-10-02-paxml-tillagg-design.md

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_016yYYj5agMiCoxsTCe4usfY"
gh run watch --exit-status $(gh run list --branch feat/paxml-tillagg --limit 1 --json databaseId -q '.[0].databaseId')
```
Expected: CI grön.

- [ ] **Step 6: Demo-siten och tillbaka till version-16**

```bash
cd ~/frappe-bench
bench --site <demosite> clear-cache && bench --site <demosite> migrate
git -C apps/hrms_sverige checkout version-16
bench --site <testsite> clear-cache && bench --site <demosite> clear-cache
```

Merge och produktion görs först efter användarens godkännande, tillsammans med del A och B efter provimporten i Crona.
