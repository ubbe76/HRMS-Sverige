# Stämplingssida, del C1 – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** En stämplingssida på en gemensam surfplatta eller dator där anställda stämplar in och ut med anställningsnummer och PIN-kod och väljer pengar eller komptid vid övertid.

**Architecture:** `lon/pin.py` (ren PIN-logik), dokumentet `Stamplingsenhet` (enhet med hashad nyckel), PIN-fält på Employee och tre gäst-API:er i `lon/stampling.py` som alltid kontrollerar enhetsnyckel och PIN. Nekanden returneras som `{"fel": ...}` i stället för undantag, så att räknaren för felaktiga försök sparas. Sidan `www/stampla` är vanlig HTML och JavaScript utan byggsteg.

**Tech Stack:** Frappe 16 / HRMS 16 (Python 3.14), `frappe.utils.password.passlibctx`, `frappe.rate_limiter.rate_limit`, Frappe www-sidor (Jinja + colocated JS, `frappe.call`).

**Spec:** `docs/superpowers/specs/2026-10-02-stampling-design.md` (bygger på C2: `2026-10-02-paxml-tillagg-design.md`)

## Global Constraints

- Appen `hrms_sverige` i `apps/hrms_sverige`, gren `feat/stampling`. Byt tillbaka till `version-16` när du lämnar arbetet; benchen delas med produktionssiten.
- `bench`-kommandon från `~/frappe-bench`. Tester bara på `<testsite>`. Aldrig `migrate` på `<site>`.
- Efter ändringar i doctype-JSON, custom fields eller `hooks.py`: `bench --site <testsite> clear-cache && bench --site <testsite> migrate`.
- Tabbar, radlängd 110, ruff via pre-commit; inga tvetydiga tecken som `–` i kommentarer. Kör `pre-commit run --files <filer>` före commit och `git add` igen.
- PIN: 4–6 siffror, inte bara samma siffra, ny skild från gammal. Lagras bara som hash (`passlibctx`).
- Enhetsnyckel: `secrets.token_urlsafe(32)`, lagras bara som SHA-256-hex i `nyckel_hash`.
- Samma fel för okänt nummer, inaktiv anställd och fel PIN: "Fel anställningsnummer eller PIN-kod".
- Låsning: 5 fel → 15 minuter ("För många felaktiga försök. Försök igen senare."). Rätt PIN nollställer.
- Dubbeltryck: samma anställd inom 60 sekunder → "Du stämplade nyss".
- Riktning: `OUT` om senaste stämplingen de senaste 24 timmarna är `IN`, annars `IN`.
- Övertidsfråga: vid `OUT`, om planerat skift finns för datumet då passet började och extra tid (från senaste `IN` till nu) är fler minuter än `overtid_fraga_minuter` (standard 15).
- Servertid (`now_datetime`) för alla stämplingar. `device_id` = enhetens namn.
- Commit-meddelanden på engelska och avslutas med:
  ```
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_016yYYj5agMiCoxsTCe4usfY
  ```

## Review Focus

1. **Den anställde stämplar ut utan att ha stämplat in** (glömt) – riktningen föreslår IN; väljer den anställde ändå OUT ska det fungera, utan övertidsfråga. Test i Task 4 (`test_utstampling_utan_instampling`).
2. **Passet började igår (nattskift)** – övertidsfrågan räknas mot gårdagens skift. Test i Task 4 (`test_nattskift_fraga_mot_gardagens_skift`).
3. **Låst anställningsnummer med rätt PIN** – ska fortfarande nekas tills låsningen gått ut. Test i Task 3 (`test_last_trots_ratt_pin`).
4. **PIN-byte med fel gammal PIN** – nekas och räknas som fel försök. Test i Task 3 (`test_byt_pin_med_fel_gammal_pin`).
5. **Gäst anropar `satt_pin`** – nekas. Test i Task 2 (`test_satt_pin_kraver_hr`).

---

## Filkarta

| Fil | Ansvar |
|---|---|
| `hrms_sverige/lon/pin.py` (ny) | `kontrollera_pin_regler`, `hasha_pin`, `pin_stammer` |
| `hrms_sverige/lon/doctype/stamplingsenhet/*` (ny) | Enhet och `skapa_nyckel` |
| `hrms_sverige/lon/stampling.py` (ny) | `satt_pin`, `identifiera`, `byt_pin`, `stampla` och hjälpfunktioner |
| `hrms_sverige/setup/custom_fields.py` (ändras) | PIN-fälten på Employee |
| `hrms_sverige/lon/doctype/loneinstallningar/loneinstallningar.json` (ändras) | `overtid_fraga_minuter` |
| `hrms_sverige/public/js/employee.js` (ny), `hooks.py` (ändras) | Knappen Sätt PIN |
| `hrms_sverige/www/stampla.html`, `stampla.js`, `stampla.py` (nya) | Sidan |
| `hrms_sverige/locale/sv.po` (ändras) | Visningsnamn |
| `hrms_sverige/tests/utils.py` (ändras) | `make_enhet` |
| `hrms_sverige/tests/test_pin.py`, `test_stampling.py` (nya) | Tester |
| `README.md`, `CHANGELOG.md`; docs-repot `docs/personal/stampling.md`, `mkdocs.yml` | Dokumentation |

---

### Task 1: PIN-logik

**Files:**
- Create: `hrms_sverige/lon/pin.py`
- Test: `hrms_sverige/tests/test_pin.py`

**Interfaces:**
- Produces: `kontrollera_pin_regler(pin: str, gammal: str | None = None) -> None` (kastar `frappe.ValidationError`), `hasha_pin(pin: str) -> str`, `pin_stammer(pin: str, pin_hash: str | None) -> bool`.

- [ ] **Step 1: Grenen** – `git checkout feat/stampling && git merge --ff-only origin/version-16 || git rebase origin/version-16`

- [ ] **Step 2: Skriv de fallerande testerna** – `hrms_sverige/tests/test_pin.py`:

```python
import frappe
from frappe.tests import UnitTestCase

from hrms_sverige.lon.pin import hasha_pin, kontrollera_pin_regler, pin_stammer


class TestPin(UnitTestCase):
	def test_hash_och_kontroll(self):
		pin_hash = hasha_pin("4821")
		self.assertNotIn("4821", pin_hash)
		self.assertTrue(pin_stammer("4821", pin_hash))
		self.assertFalse(pin_stammer("4822", pin_hash))

	def test_tom_hash_stammer_aldrig(self):
		self.assertFalse(pin_stammer("4821", None))
		self.assertFalse(pin_stammer("4821", ""))

	def test_giltiga(self):
		for pin in ("4821", "48213", "482135"):
			kontrollera_pin_regler(pin)

	def test_ogiltiga(self):
		for pin in ("482", "4821357", "48a1", "", "1111", " 4821"):
			self.assertRaises(frappe.ValidationError, kontrollera_pin_regler, pin)

	def test_ny_maste_skilja_sig_fran_gammal(self):
		self.assertRaisesRegex(frappe.ValidationError, "skilja sig", kontrollera_pin_regler, "4821", "4821")
```

- [ ] **Step 3: Kör och se dem fallera**

Run: `bench --site <testsite> run-tests --app hrms_sverige --module hrms_sverige.tests.test_pin`
Expected: ERROR, `ModuleNotFoundError: No module named 'hrms_sverige.lon.pin'`.

- [ ] **Step 4: Implementera** – `hrms_sverige/lon/pin.py`:

```python
"""PIN-koder för stämpling: regler och hashning. Lagras aldrig i klartext."""

import re

import frappe
from frappe import _
from frappe.utils.password import passlibctx


def kontrollera_pin_regler(pin: str, gammal: str | None = None) -> None:
	if not re.fullmatch(r"\d{4,6}", pin or ""):
		frappe.throw(_("PIN-koden ska vara 4 till 6 siffror."))
	if len(set(pin)) == 1:
		frappe.throw(_("PIN-koden får inte bara vara samma siffra."))
	if gammal is not None and pin == gammal:
		frappe.throw(_("Den nya PIN-koden måste skilja sig från den gamla."))


def hasha_pin(pin: str) -> str:
	return passlibctx.hash(pin)


def pin_stammer(pin: str, pin_hash: str | None) -> bool:
	if not pin_hash or not pin:
		return False
	try:
		return passlibctx.verify(pin, pin_hash)
	except ValueError:
		return False
```

- [ ] **Step 5: Kör testerna**

Run: `bench --site <testsite> run-tests --app hrms_sverige --module hrms_sverige.tests.test_pin`
Expected: OK (5 tester).

- [ ] **Step 6: Commit**

```bash
pre-commit run --files hrms_sverige/lon/pin.py hrms_sverige/tests/test_pin.py; git add hrms_sverige/lon/pin.py hrms_sverige/tests/test_pin.py
git commit -m "feat: PIN rules and hashing for the time clock" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016yYYj5agMiCoxsTCe4usfY"
```

---

### Task 2: Enheter, PIN-fält och Sätt PIN

**Files:**
- Create: `hrms_sverige/lon/doctype/stamplingsenhet/__init__.py` (tom), `stamplingsenhet.json`, `stamplingsenhet.py`, `stamplingsenhet.js`
- Create: `hrms_sverige/lon/stampling.py` (bara `nyckel_hash`, `satt_pin` i den här tasken)
- Create: `hrms_sverige/public/js/employee.js`
- Modify: `hrms_sverige/hooks.py` (`doctype_js`), `hrms_sverige/setup/custom_fields.py`, `hrms_sverige/lon/doctype/loneinstallningar/loneinstallningar.json`, `hrms_sverige/locale/sv.po`, `hrms_sverige/tests/utils.py`
- Test: `hrms_sverige/tests/test_stampling.py`

**Interfaces:**
- Consumes: `kontrollera_pin_regler`, `hasha_pin` (Task 1).
- Produces:
  - DocType `Stamplingsenhet` (`enhetsnamn`, `aktiv`, `nyckel_hash`, `senast_anvand`), autoname `field:enhetsnamn`; dokumentmetod `skapa_nyckel() -> dict` med `nyckel` och `lank`.
  - `hrms_sverige.lon.stampling.nyckel_hash(nyckel: str) -> str` (SHA-256-hex)
  - `hrms_sverige.lon.stampling.satt_pin(employee: str, pin: str) -> None` (whitelistad, HR Manager/HR User)
  - Employee-fält `stampel_pin_hash`, `stampel_pin_maste_bytas`, `stampel_fel_forsok`, `stampel_last_till` (permlevel 1); Löneinställningar `overtid_fraga_minuter` (Int, standard 15).
  - `hrms_sverige.tests.utils.make_enhet(namn: str = "_Test Surfplatta") -> tuple[str, str]` (namn, nyckel)

- [ ] **Step 1: Enhetsdokumentet** – `hrms_sverige/lon/doctype/stamplingsenhet/stamplingsenhet.json`:

```json
{
 "actions": [],
 "autoname": "field:enhetsnamn",
 "creation": "2026-10-03 00:00:00.000000",
 "doctype": "DocType",
 "engine": "InnoDB",
 "field_order": ["enhetsnamn", "aktiv", "column_break_1", "senast_anvand", "nyckel_hash"],
 "fields": [
  {"fieldname": "enhetsnamn", "fieldtype": "Data", "in_list_view": 1, "label": "Namn", "reqd": 1, "unique": 1, "description": "T.ex. Surfplatta entrén."},
  {"default": "1", "fieldname": "aktiv", "fieldtype": "Check", "in_list_view": 1, "label": "Aktiv", "description": "Stäng av en förlorad eller utbytt enhet."},
  {"fieldname": "column_break_1", "fieldtype": "Column Break"},
  {"fieldname": "senast_anvand", "fieldtype": "Datetime", "in_list_view": 1, "label": "Senast använd", "read_only": 1},
  {"fieldname": "nyckel_hash", "fieldtype": "Data", "hidden": 1, "label": "Nyckelhash", "read_only": 1}
 ],
 "modified": "2026-10-03 00:00:00.000000",
 "modified_by": "Administrator",
 "module": "Lon",
 "name": "Stamplingsenhet",
 "naming_rule": "By fieldname",
 "owner": "Administrator",
 "permissions": [
  {"create": 1, "delete": 1, "read": 1, "role": "HR Manager", "write": 1},
  {"create": 1, "delete": 1, "read": 1, "role": "System Manager", "write": 1}
 ],
 "sort_field": "creation",
 "sort_order": "DESC",
 "states": [],
 "track_changes": 1
}
```

`stamplingsenhet.py`:

```python
import secrets

import frappe
from frappe.model.document import Document
from frappe.utils import get_url


class Stamplingsenhet(Document):
	@frappe.whitelist()
	def skapa_nyckel(self) -> dict:
		"""Ny hemlig nyckel; bara hashen sparas och den gamla länken slutar fungera."""
		from hrms_sverige.lon.stampling import nyckel_hash

		self.check_permission("write")
		nyckel = secrets.token_urlsafe(32)
		self.db_set("nyckel_hash", nyckel_hash(nyckel))
		return {"nyckel": nyckel, "lank": get_url(f"/stampla?enhet={nyckel}")}
```

`stamplingsenhet.js`:

```javascript
frappe.ui.form.on("Stamplingsenhet", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("Skapa länk"), () =>
			frappe.confirm(
				__("En ny länk gör den gamla ogiltig. Fortsätta?"),
				() =>
					frm.call("skapa_nyckel").then((r) => {
						frappe.msgprint({
							title: __("Länk till stämplingssidan"),
							message:
								__("Öppna länken en gång på enheten. Den visas bara nu.") +
								`<p><input class="form-control" readonly value="${r.message.lank}" onclick="this.select()"></p>`,
						});
						frm.reload_doc();
					})
			)
		);
	},
});
```

- [ ] **Step 2: Fälten** – i `hrms_sverige/setup/custom_fields.py`, lägg sist i listan `"Employee"` (efter `overtid_som`):

```python
			{
				"fieldname": "stampel_pin_maste_bytas",
				"label": _("PIN måste bytas"),
				"fieldtype": "Check",
				"read_only": 1,
				"permlevel": PERSONNUMMER_PERMLEVEL,
				"insert_after": "overtid_som",
				"description": _("Sätts när HR sätter en PIN-kod; den anställde byter vid första stämplingen."),
			},
			{
				"fieldname": "stampel_last_till",
				"label": _("Stämpling låst till"),
				"fieldtype": "Datetime",
				"read_only": 1,
				"permlevel": PERSONNUMMER_PERMLEVEL,
				"insert_after": "stampel_pin_maste_bytas",
			},
			{
				"fieldname": "stampel_pin_hash",
				"label": _("PIN-hash"),
				"fieldtype": "Data",
				"hidden": 1,
				"read_only": 1,
				"permlevel": PERSONNUMMER_PERMLEVEL,
				"insert_after": "stampel_last_till",
			},
			{
				"fieldname": "stampel_fel_forsok",
				"label": _("Felaktiga PIN-försök"),
				"fieldtype": "Int",
				"hidden": 1,
				"read_only": 1,
				"permlevel": PERSONNUMMER_PERMLEVEL,
				"insert_after": "stampel_pin_hash",
			},
```

I `loneinstallningar.json`: lägg `"overtid_fraga_minuter"` efter `"heltid_per_dag"` i `field_order` och fältet:

```json
  {"default": "15", "description": "Stämplingssidan frågar om pengar eller komptid när passet har mer extra tid än så här utanför skiftet.", "fieldname": "overtid_fraga_minuter", "fieldtype": "Int", "label": "Fråga om övertid efter (minuter)"}
```

och sätt `"modified": "2026-10-03 00:00:00.000000"`.

- [ ] **Step 3: Testhjälp** – lägg sist i `hrms_sverige/tests/utils.py`:

```python
def make_enhet(namn: str = "_Test Surfplatta") -> tuple[str, str]:
	"""Stämplingsenhet med ny nyckel; returnerar (namn, nyckel)."""
	if not frappe.db.exists("Stamplingsenhet", namn):
		frappe.get_doc({"doctype": "Stamplingsenhet", "enhetsnamn": namn}).insert()
	return namn, frappe.get_doc("Stamplingsenhet", namn).skapa_nyckel()["nyckel"]
```

- [ ] **Step 4: Skriv de fallerande testerna** – `hrms_sverige/tests/test_stampling.py`:

```python
import frappe
from frappe.tests import IntegrationTestCase

from hrms_sverige.lon.pin import pin_stammer
from hrms_sverige.lon.stampling import nyckel_hash, satt_pin
from hrms_sverige.setup.custom_fields import create_custom_fields
from hrms_sverige.tests.utils import ensure_test_company, make_enhet, make_test_employee


class StamplingTestCase(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_test_company()
		create_custom_fields()

	def setUp(self):
		frappe.db.savepoint("stampling_test")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point="stampling_test")


class TestEnhetOchPin(StamplingTestCase):
	def test_bara_hashen_sparas(self):
		namn, nyckel = make_enhet()
		self.assertEqual(frappe.db.get_value("Stamplingsenhet", namn, "nyckel_hash"), nyckel_hash(nyckel))
		self.assertNotEqual(nyckel_hash(nyckel), nyckel)

	def test_ny_nyckel_ersatter_gammal(self):
		namn, gammal = make_enhet()
		_, ny = make_enhet()
		self.assertNotEqual(gammal, ny)
		self.assertEqual(frappe.db.get_value("Stamplingsenhet", namn, "nyckel_hash"), nyckel_hash(ny))

	def test_satt_pin(self):
		anstalld = make_test_employee("Stämpel Pin", employee_number="SP-1")
		frappe.db.set_value("Employee", anstalld, {"stampel_fel_forsok": 3, "stampel_last_till": "2030-01-01 00:00:00"})
		satt_pin(anstalld, "4821")
		rad = frappe.db.get_value(
			"Employee",
			anstalld,
			["stampel_pin_hash", "stampel_pin_maste_bytas", "stampel_fel_forsok", "stampel_last_till"],
			as_dict=True,
		)
		self.assertTrue(pin_stammer("4821", rad.stampel_pin_hash))
		self.assertEqual((rad.stampel_pin_maste_bytas, rad.stampel_fel_forsok, rad.stampel_last_till), (1, 0, None))

	def test_satt_pin_foljer_reglerna(self):
		anstalld = make_test_employee("Stämpel Regel", employee_number="SP-2")
		self.assertRaises(frappe.ValidationError, satt_pin, anstalld, "1111")

	def test_satt_pin_kraver_hr(self):
		anstalld = make_test_employee("Stämpel Gäst", employee_number="SP-3")
		frappe.set_user("Guest")
		self.assertRaises(frappe.PermissionError, satt_pin, anstalld, "4821")

	def test_fraga_minuter_har_standard(self):
		self.assertEqual(frappe.get_meta("Loneinstallningar").get_field("overtid_fraga_minuter").default, "15")
```

- [ ] **Step 5: Migrera och se dem fallera**

Run: `bench --site <testsite> clear-cache && bench --site <testsite> migrate && bench --site <testsite> run-tests --app hrms_sverige --module hrms_sverige.tests.test_stampling`
Expected: ERROR, `ModuleNotFoundError: No module named 'hrms_sverige.lon.stampling'`.

- [ ] **Step 6: Implementera** – `hrms_sverige/lon/stampling.py`:

```python
"""Stämplingssidan: gäst-API för registrerade enheter, med anställningsnummer och PIN-kod."""

import hashlib

import frappe

from hrms_sverige.lon.pin import hasha_pin, kontrollera_pin_regler

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
```

`hrms_sverige/public/js/employee.js`:

```javascript
frappe.ui.form.on("Employee", {
	refresh(frm) {
		if (frm.is_new() || !(frappe.user.has_role("HR Manager") || frappe.user.has_role("HR User"))) return;
		frm.add_custom_button(
			__("Sätt PIN"),
			() => {
				const d = new frappe.ui.Dialog({
					title: __("PIN-kod för stämpling"),
					fields: [
						{
							fieldname: "pin",
							fieldtype: "Password",
							label: __("Ny PIN-kod (4 till 6 siffror)"),
							reqd: 1,
						},
					],
					primary_action_label: __("Spara"),
					primary_action(values) {
						frappe
							.call("hrms_sverige.lon.stampling.satt_pin", { employee: frm.doc.name, pin: values.pin })
							.then(() => {
								d.hide();
								frappe.show_alert({
									message: __("PIN-koden är satt. Den anställde byter den vid första stämplingen."),
									indicator: "green",
								});
								frm.reload_doc();
							});
					},
				});
				d.show();
			},
			__("Stämpling")
		);
	},
});
```

I `hooks.py`, ersätt raden `# doctype_js = {"doctype" : "public/js/doctype.js"}` med:

```python
doctype_js = {"Employee": "public/js/employee.js"}
```

I `hrms_sverige/locale/sv.po`, sist:

```
msgid "Stamplingsenhet"
msgstr "Stämplingsenhet"
```

och kompilera: `bench compile-po-to-mo --app hrms_sverige --locale sv --force`.

- [ ] **Step 7: Migrera och kör testerna**

Run: `bench --site <testsite> clear-cache && bench --site <testsite> migrate && bench --site <testsite> run-tests --app hrms_sverige --module hrms_sverige.tests.test_stampling`
Expected: OK (6 tester).

- [ ] **Step 8: Commit**

```bash
F="hrms_sverige/lon/doctype/stamplingsenhet hrms_sverige/lon/stampling.py hrms_sverige/public/js/employee.js hrms_sverige/hooks.py hrms_sverige/setup/custom_fields.py hrms_sverige/lon/doctype/loneinstallningar/loneinstallningar.json hrms_sverige/locale/sv.po hrms_sverige/tests/utils.py hrms_sverige/tests/test_stampling.py"
git add $F; pre-commit run --files $F; git add $F
git commit -m "feat: time clock devices, PIN fields and Set PIN for HR" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016yYYj5agMiCoxsTCe4usfY"
```

---

### Task 3: Identifiera och byta PIN

**Files:**
- Modify: `hrms_sverige/lon/stampling.py`
- Test: `hrms_sverige/tests/test_stampling.py`

**Interfaces:**
- Consumes: Task 1 och 2.
- Produces (alla whitelistade `allow_guest=True, methods=["POST"]`, alla returnerar `{"fel": str}` vid nekande):
  - `identifiera(enhet: str, anstallningsnummer: str, pin: str) -> dict` – `fornamn`, `riktning` (`"IN"`/`"OUT"`), `maste_byta_pin` (bool), `fraga_overtid` (bool), `forval` (`"Pengar"`/`"Komptid"`), `extra_minuter` (int)
  - `byt_pin(enhet: str, anstallningsnummer: str, pin: str, ny_pin: str) -> dict` – `{"ok": True}`
  - intern `_fraga_overtid(employee, nu) -> tuple[bool, int]` (Task 3 ger alltid `(False, 0)`; Task 4 gör den riktig)
  - `FEL_INLOGGNING = "Fel anställningsnummer eller PIN-kod"`, `FEL_LAST`, `FEL_ENHET`, `FEL_BYT_PIN`
- Testhjälp i testfilen: `pin_anstalld(namn, nummer, pin="4821", maste_bytas=False) -> str`

- [ ] **Step 1: Skriv de fallerande testerna** – lägg till i `hrms_sverige/tests/test_stampling.py` (utöka importen från `hrms_sverige.lon.stampling` med `FEL_BYT_PIN, FEL_ENHET, FEL_INLOGGNING, FEL_LAST, byt_pin, identifiera`; lägg till `from datetime import datetime` och `from unittest.mock import patch`):

```python
NU = datetime(2026, 9, 14, 8, 0)


def pin_anstalld(namn, nummer, pin="4821", maste_bytas=False):
	anstalld = make_test_employee(namn, employee_number=nummer)
	satt_pin(anstalld, pin)
	if not maste_bytas:
		frappe.db.set_value("Employee", anstalld, "stampel_pin_maste_bytas", 0)
	return anstalld


class TestIdentifiera(StamplingTestCase):
	def setUp(self):
		super().setUp()
		self.enhet, self.nyckel = make_enhet()
		self.anstalld = pin_anstalld("Åsa Identifiera", "ID-1")
		frappe.db.set_value("Employee", self.anstalld, "first_name", "Åsa")

	def test_ratt_pin(self):
		svar = identifiera(self.nyckel, "ID-1", "4821")
		self.assertEqual((svar["fornamn"], svar["riktning"], svar["maste_byta_pin"]), ("Åsa", "IN", False))
		self.assertTrue(frappe.db.get_value("Stamplingsenhet", self.enhet, "senast_anvand"))

	def test_fel_enhet(self):
		self.assertEqual(identifiera("fel-nyckel", "ID-1", "4821"), {"fel": FEL_ENHET})
		frappe.db.set_value("Stamplingsenhet", self.enhet, "aktiv", 0)
		self.assertEqual(identifiera(self.nyckel, "ID-1", "4821"), {"fel": FEL_ENHET})

	def test_samma_fel_for_okant_nummer_fel_pin_och_inaktiv(self):
		self.assertEqual(identifiera(self.nyckel, "FINNS-EJ", "4821"), {"fel": FEL_INLOGGNING})
		self.assertEqual(identifiera(self.nyckel, "ID-1", "9999"), {"fel": FEL_INLOGGNING})
		frappe.db.set_value("Employee", self.anstalld, "status", "Inactive")
		self.assertEqual(identifiera(self.nyckel, "ID-1", "4821"), {"fel": FEL_INLOGGNING})

	def test_lasning_efter_fem_fel_och_upplasning(self):
		with patch("hrms_sverige.lon.stampling.now_datetime", return_value=NU):
			for _ in range(5):
				identifiera(self.nyckel, "ID-1", "0000")
			self.assertEqual(identifiera(self.nyckel, "ID-1", "4821"), {"fel": FEL_LAST})
		with patch("hrms_sverige.lon.stampling.now_datetime", return_value=datetime(2026, 9, 14, 8, 16)):
			self.assertEqual(identifiera(self.nyckel, "ID-1", "4821")["fornamn"], "Åsa")

	def test_last_trots_ratt_pin(self):
		frappe.db.set_value("Employee", self.anstalld, "stampel_last_till", "2026-09-14 08:10:00")
		with patch("hrms_sverige.lon.stampling.now_datetime", return_value=NU):
			self.assertEqual(identifiera(self.nyckel, "ID-1", "4821"), {"fel": FEL_LAST})

	def test_ratt_pin_nollstaller_raknaren(self):
		identifiera(self.nyckel, "ID-1", "0000")
		identifiera(self.nyckel, "ID-1", "4821")
		self.assertEqual(frappe.db.get_value("Employee", self.anstalld, "stampel_fel_forsok"), 0)

	def test_riktning_efter_senaste_stampling(self):
		frappe.get_doc(
			{"doctype": "Employee Checkin", "employee": self.anstalld, "log_type": "IN", "time": "2026-09-14 07:00:00"}
		).insert()
		with patch("hrms_sverige.lon.stampling.now_datetime", return_value=NU):
			self.assertEqual(identifiera(self.nyckel, "ID-1", "4821")["riktning"], "OUT")
		with patch("hrms_sverige.lon.stampling.now_datetime", return_value=datetime(2026, 9, 15, 8, 0)):
			self.assertEqual(identifiera(self.nyckel, "ID-1", "4821")["riktning"], "IN")

	def test_maste_byta_pin(self):
		pin_anstalld("Ny Anställd", "ID-2", "5173", maste_bytas=True)
		self.assertTrue(identifiera(self.nyckel, "ID-2", "5173")["maste_byta_pin"])

	def test_byt_pin(self):
		pin_anstalld("Byter", "ID-3", "5173", maste_bytas=True)
		self.assertEqual(byt_pin(self.nyckel, "ID-3", "5173", "8264"), {"ok": True})
		svar = identifiera(self.nyckel, "ID-3", "8264")
		self.assertFalse(svar["maste_byta_pin"])

	def test_byt_pin_foljer_reglerna(self):
		self.assertIn("fel", byt_pin(self.nyckel, "ID-1", "4821", "4821"))
		self.assertIn("fel", byt_pin(self.nyckel, "ID-1", "4821", "12"))

	def test_byt_pin_med_fel_gammal_pin(self):
		self.assertEqual(byt_pin(self.nyckel, "ID-1", "0000", "8264"), {"fel": FEL_INLOGGNING})
		self.assertEqual(frappe.db.get_value("Employee", self.anstalld, "stampel_fel_forsok"), 1)
```

- [ ] **Step 2: Kör och se dem fallera**

Run: `bench --site <testsite> run-tests --app hrms_sverige --module hrms_sverige.tests.test_stampling`
Expected: ERROR, `ImportError: cannot import name 'FEL_BYT_PIN'`.

- [ ] **Step 3: Implementera** – lägg till i `hrms_sverige/lon/stampling.py` (utöka importerna: `from datetime import timedelta`, `from functools import wraps`, `from frappe import _`, `from frappe.rate_limiter import rate_limit`, `from frappe.utils import get_datetime, now_datetime`, `from hrms_sverige.lon.pin import hasha_pin, kontrollera_pin_regler, pin_stammer`):

```python
FEL_ENHET = "Enheten är inte registrerad. Be HR om en ny länk."
FEL_INLOGGNING = "Fel anställningsnummer eller PIN-kod"
FEL_LAST = "För många felaktiga försök. Försök igen senare."
FEL_BYT_PIN = "Byt PIN-kod först."
MAX_FORSOK = 5
LASTID = timedelta(minutes=15)


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
	frappe.db.set_value("Stamplingsenhet", namn, "senast_anvand", now_datetime(), update_modified=False)
	return namn


def _anstalld(anstallningsnummer: str, pin: str) -> frappe._dict:
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
		raise Nekad(FEL_INLOGGNING)
	nu = now_datetime()
	if rad.stampel_last_till and get_datetime(rad.stampel_last_till) > nu:
		raise Nekad(FEL_LAST)
	if not pin_stammer(pin, rad.stampel_pin_hash):
		forsok = (rad.stampel_fel_forsok or 0) + 1
		if forsok >= MAX_FORSOK:
			frappe.db.set_value(
				"Employee", rad.name, {"stampel_fel_forsok": 0, "stampel_last_till": nu + LASTID}, update_modified=False
			)
		else:
			frappe.db.set_value("Employee", rad.name, "stampel_fel_forsok", forsok, update_modified=False)
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


def _fraga_overtid(employee: str, nu) -> tuple[bool, int]:
	return False, 0


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(key="enhet", limit=30, seconds=60)
@_svar
def identifiera(enhet: str, anstallningsnummer: str, pin: str) -> dict:
	_enhet(enhet)
	rad = _anstalld(anstallningsnummer, pin)
	nu = now_datetime()
	senaste = _senaste(rad.name, nu)
	riktning = "OUT" if senaste and senaste.log_type == "IN" else "IN"
	fraga, minuter = _fraga_overtid(rad.name, nu) if riktning == "OUT" else (False, 0)
	return {
		"fornamn": rad.first_name,
		"riktning": riktning,
		"maste_byta_pin": bool(rad.stampel_pin_maste_bytas),
		"fraga_overtid": fraga,
		"forval": rad.overtid_som or "Pengar",
		"extra_minuter": minuter,
	}


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(key="enhet", limit=30, seconds=60)
@_svar
def byt_pin(enhet: str, anstallningsnummer: str, pin: str, ny_pin: str) -> dict:
	_enhet(enhet)
	rad = _anstalld(anstallningsnummer, pin)
	kontrollera_pin_regler(ny_pin, gammal=pin)
	frappe.db.set_value(
		"Employee", rad.name, {"stampel_pin_hash": hasha_pin(ny_pin), "stampel_pin_maste_bytas": 0}, update_modified=False
	)
	return {"ok": True}
```

(`frappe.whitelist` måste ligga ytterst så att den registrerar den färdiga funktionen. `rate_limit` gör inget i tester utan request.)

- [ ] **Step 4: Kör testerna**

Run: `bench --site <testsite> run-tests --app hrms_sverige --module hrms_sverige.tests.test_stampling`
Expected: OK (17 tester).

- [ ] **Step 5: Commit**

```bash
F="hrms_sverige/lon/stampling.py hrms_sverige/tests/test_stampling.py"; git add $F; pre-commit run --files $F; git add $F
git commit -m "feat: identify employees and change PIN on the time clock" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016yYYj5agMiCoxsTCe4usfY"
```

---

### Task 4: Stämpla och övertidsfrågan

**Files:**
- Modify: `hrms_sverige/lon/stampling.py`
- Test: `hrms_sverige/tests/test_stampling.py`

**Interfaces:**
- Consumes: Task 3; `planerat_skift` (`hrms_sverige.lon.tid`), `extra_tid`, `timmar` (`hrms_sverige.lon.regler`), `tillaggsrader` (`hrms_sverige.lon.tillagg`) i flödestestet; testhjälparna `make_shift_type`, `assign_shift`, `make_attendance`, `satt_tidsregler`, `create_holiday_list`, `COMPANY`.
- Produces: `stampla(enhet: str, anstallningsnummer: str, pin: str, log_type: str, overtidsersattning: str | None = None) -> dict` – `fornamn`, `log_type`, `tid` (`"HH:MM"`); `_fraga_overtid` räknar på riktigt.

- [ ] **Step 1: Skriv de fallerande testerna** – lägg sist i `hrms_sverige/tests/test_stampling.py` (utöka importen med `stampla`; lägg till `from datetime import date`; från `hrms_sverige.setup.holidays` `create_holiday_list`; från `hrms_sverige.tests.utils` även `COMPANY, assign_shift, make_attendance, make_shift_type, satt_tidsregler`; från `hrms_sverige.lon.tillagg` `tillaggsrader`):

```python
def klockan(timme, minut=0, dag=14):
	return patch("hrms_sverige.lon.stampling.now_datetime", return_value=datetime(2026, 9, dag, timme, minut))


class TestStampla(StamplingTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		create_holiday_list(2026, COMPANY)
		cls.dag = make_shift_type("_Test Dag", "08:00:00", "16:30:00")
		cls.natt = make_shift_type("_Test Natt", "22:00:00", "06:00:00")

	def setUp(self):
		super().setUp()
		self.enhet, self.nyckel = make_enhet()
		self.anstalld = pin_anstalld("Stämplar", "ST-1")
		assign_shift(self.anstalld, self.dag, "2026-08-01")

	def checkins(self):
		return frappe.get_all(
			"Employee Checkin",
			filters={"employee": self.anstalld},
			fields=["log_type", "time", "device_id", "overtidsersattning"],
			order_by="time asc",
		)

	def test_stampla_in_och_ut(self):
		with klockan(8):
			svar = stampla(self.nyckel, "ST-1", "4821", "IN")
		self.assertEqual((svar["log_type"], svar["tid"]), ("IN", "08:00"))
		with klockan(16, 35):
			stampla(self.nyckel, "ST-1", "4821", "OUT", "Komptid")
		rader = self.checkins()
		self.assertEqual([(r.log_type, str(r.time), r.device_id) for r in rader], [
			("IN", "2026-09-14 08:00:00", self.enhet),
			("OUT", "2026-09-14 16:35:00", self.enhet),
		])
		self.assertEqual(rader[1].overtidsersattning, "Komptid")

	def test_val_sparas_inte_vid_in(self):
		with klockan(8):
			stampla(self.nyckel, "ST-1", "4821", "IN", "Komptid")
		self.assertFalse(self.checkins()[0].overtidsersattning)

	def test_dubbeltryck(self):
		with klockan(8):
			stampla(self.nyckel, "ST-1", "4821", "IN")
		with klockan(8, 0):
			self.assertEqual(stampla(self.nyckel, "ST-1", "4821", "OUT"), {"fel": "Du stämplade nyss."})
		self.assertEqual(len(self.checkins()), 1)

	def test_ogiltig_riktning_och_val(self):
		with klockan(8):
			self.assertIn("fel", stampla(self.nyckel, "ST-1", "4821", "PAUS"))
			self.assertIn("fel", stampla(self.nyckel, "ST-1", "4821", "OUT", "Bonus"))
		self.assertEqual(self.checkins(), [])

	def test_maste_byta_pin_forst(self):
		pin_anstalld("Ny", "ST-2", "5173", maste_bytas=True)
		with klockan(8):
			self.assertEqual(stampla(self.nyckel, "ST-2", "5173", "IN"), {"fel": FEL_BYT_PIN})

	def test_fraga_overtid_over_gransen(self):
		with klockan(8):
			stampla(self.nyckel, "ST-1", "4821", "IN")
		with klockan(16, 50):
			svar = identifiera(self.nyckel, "ST-1", "4821")
		self.assertEqual((svar["riktning"], svar["fraga_overtid"], svar["extra_minuter"]), ("OUT", True, 20))

	def test_ingen_fraga_under_gransen(self):
		with klockan(8):
			stampla(self.nyckel, "ST-1", "4821", "IN")
		with klockan(16, 40):
			svar = identifiera(self.nyckel, "ST-1", "4821")
		self.assertEqual((svar["fraga_overtid"], svar["extra_minuter"]), (False, 10))

	def test_ingen_fraga_utan_skift(self):
		with klockan(9, dag=12):  # lördag: helgdag, inget skift
			stampla(self.nyckel, "ST-1", "4821", "IN")
		with klockan(17, dag=12):
			self.assertFalse(identifiera(self.nyckel, "ST-1", "4821")["fraga_overtid"])

	def test_utstampling_utan_instampling(self):
		with klockan(16, 45):
			svar = identifiera(self.nyckel, "ST-1", "4821")
			self.assertEqual((svar["riktning"], svar["fraga_overtid"]), ("IN", False))
			self.assertEqual(stampla(self.nyckel, "ST-1", "4821", "OUT")["log_type"], "OUT")

	def test_nattskift_fraga_mot_gardagens_skift(self):
		natt = pin_anstalld("Natt", "ST-3")
		frappe.db.set_value("Employee", natt, "default_shift", self.natt)
		with klockan(22, dag=14):
			stampla(self.nyckel, "ST-3", "4821", "IN")
		with klockan(7, dag=15):
			svar = identifiera(self.nyckel, "ST-3", "4821")
		self.assertEqual((svar["fraga_overtid"], svar["extra_minuter"]), (True, 60))

	def test_flode_till_c2(self):
		satt_tidsregler(
			[{"typ": "Övertid", "niva": 1, "dagar": "man tis ons tor fre", "fran": "06:00:00", "till": "20:00:00"}]
		)
		with klockan(8):
			stampla(self.nyckel, "ST-1", "4821", "IN")
		with klockan(19):
			stampla(self.nyckel, "ST-1", "4821", "OUT", "Komptid")
		narvaro = make_attendance(
			self.anstalld, "2026-09-14", 11, in_time="2026-09-14 08:00:00", out_time="2026-09-14 19:00:00"
		)
		for namn in frappe.get_all("Employee Checkin", filters={"employee": self.anstalld}, pluck="name"):
			frappe.db.set_value("Employee Checkin", namn, "attendance", narvaro)
		rader = [
			(r["tidkod"], r["timmar"])
			for r in tillaggsrader(COMPANY, date(2026, 9, 1), date(2026, 9, 30))
			if r["employee"] == self.anstalld
		]
		self.assertEqual(rader, [("ÖK1", 2.5)])
```

- [ ] **Step 2: Kör och se dem fallera**

Run: `bench --site <testsite> run-tests --app hrms_sverige --module hrms_sverige.tests.test_stampling`
Expected: ERROR, `ImportError: cannot import name 'stampla'`.

- [ ] **Step 3: Implementera** – i `hrms_sverige/lon/stampling.py`, importera `from frappe.utils import cint, get_datetime, now_datetime`, `from hrms_sverige.lon.regler import extra_tid, timmar` och `from hrms_sverige.lon.tid import planerat_skift`, ersätt `_fraga_overtid` och lägg till `stampla`:

```python
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
def stampla(
	enhet: str, anstallningsnummer: str, pin: str, log_type: str, overtidsersattning: str | None = None
) -> dict:
	namn = _enhet(enhet)
	rad = _anstalld(anstallningsnummer, pin)
	if rad.stampel_pin_maste_bytas:
		raise Nekad(FEL_BYT_PIN)
	if log_type not in RIKTNINGAR or (overtidsersattning and overtidsersattning not in ERSATTNINGAR):
		raise Nekad("Ogiltig stämpling.")
	nu = now_datetime()
	senaste = _senaste(rad.name, nu)
	if senaste and nu - get_datetime(senaste.time) < DUBBELTRYCK:
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
```

och i `identifiera`, lägg efter `rad = _anstalld(...)`:

```python
	if rad.stampel_pin_maste_bytas:
		return {"fornamn": rad.first_name, "maste_byta_pin": True}
```

(ta bort `maste_byta_pin` ur det vanliga svaret och sätt det till `False` där.)

- [ ] **Step 4: Kör testerna**

Run: `bench --site <testsite> run-tests --app hrms_sverige --module hrms_sverige.tests.test_stampling`
Expected: OK (28 tester). `test_maste_byta_pin` i Task 3 förväntar `True`; svaret `{"fornamn":..., "maste_byta_pin": True}` uppfyller det.

- [ ] **Step 5: Hela sviten**

Run: `bench --site <testsite> run-tests --app hrms_sverige`
Expected: OK.

- [ ] **Step 6: Commit**

```bash
F="hrms_sverige/lon/stampling.py hrms_sverige/tests/test_stampling.py"; git add $F; pre-commit run --files $F; git add $F
git commit -m "feat: clock in and out with the overtime question" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016yYYj5agMiCoxsTCe4usfY"
```

---

### Task 5: Sidan /stampla

**Files:**
- Create: `hrms_sverige/www/stampla.py`, `stampla.html`, `stampla.js`

**Interfaces:**
- Consumes: `identifiera`, `byt_pin`, `stampla` (Task 3–4) via `frappe.call` (POST).

- [ ] **Step 1: Kontexten** – `hrms_sverige/www/stampla.py`:

```python
no_cache = 1


def get_context(context):
	context.title = "Stämpling"
	context.no_header = 1
	context.no_breadcrumbs = 1
```

- [ ] **Step 2: Sidan** – `hrms_sverige/www/stampla.html`:

```html
{% extends "templates/base.html" %}
{% block title %}Stämpling{% endblock %}
{% block content %}
<style>
	body { background: #f4f5f6; }
	.st { max-width: 420px; margin: 4vh auto; padding: 16px; font-family: system-ui, sans-serif; text-align: center; }
	.st h1 { font-size: 1.6rem; margin-bottom: 0.5rem; }
	.st .falt { font-size: 2rem; letter-spacing: 0.3rem; min-height: 3rem; border-bottom: 2px solid #888; margin: 1rem 0; }
	.st .knappar { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
	.st button { font-size: 1.6rem; padding: 18px 0; border-radius: 10px; border: 1px solid #ccc; background: #fff; }
	.st button.stor { grid-column: span 3; font-size: 1.8rem; background: #1f7a45; color: #fff; border: none; }
	.st button.andra { grid-column: span 3; font-size: 1.1rem; }
	.st .fel { color: #b00020; min-height: 1.5rem; }
	.st .val button.vald { outline: 4px solid #1f7a45; }
</style>
<div class="st">
	<h1 id="rubrik">Stämpling</h1>
	<p id="text"></p>
	<div class="falt" id="falt"></div>
	<div class="fel" id="fel"></div>
	<div id="yta"></div>
</div>
{% endblock %}
```

- [ ] **Step 3: Skriptet** – `hrms_sverige/www/stampla.js`:

```javascript
(() => {
	const NYCKEL = "stampla_enhet";
	const METOD = "hrms_sverige.lon.stampling.";
	const $ = (id) => document.getElementById(id);
	let enhet = new URLSearchParams(location.search).get("enhet");
	try {
		if (enhet) {
			localStorage.setItem(NYCKEL, enhet);
			history.replaceState(null, "", "/stampla");
		}
		enhet = localStorage.getItem(NYCKEL);
	} catch (e) {}
	let lage = {};
	let timer;

	function visa(rubrik, text, falt) {
		$("rubrik").textContent = rubrik;
		$("text").textContent = text || "";
		$("falt").textContent = falt || "";
		$("fel").textContent = "";
		clearTimeout(timer);
		timer = setTimeout(start, 30000);
	}

	function fel(meddelande) {
		$("fel").textContent = meddelande;
	}

	function anropa(funktion, args) {
		return frappe
			.call({ method: METOD + funktion, type: "POST", args: { enhet, ...args } })
			.then((r) => r.message || {});
	}

	function knappsats(etikett, dold, klar) {
		let varde = "";
		const yta = $("yta");
		yta.innerHTML = "";
		const rutnat = document.createElement("div");
		rutnat.className = "knappar";
		const knappar = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "⌫", "0", "OK"];
		for (const k of knappar) {
			const b = document.createElement("button");
			b.textContent = k;
			b.onclick = () => {
				if (k === "⌫") varde = varde.slice(0, -1);
				else if (k === "OK") return varde && klar(varde);
				else if (varde.length < 10) varde += k;
				$("falt").textContent = dold ? "•".repeat(varde.length) : varde;
			};
			rutnat.appendChild(b);
		}
		yta.appendChild(rutnat);
		visa("Stämpling", etikett, "");
	}

	function knapp(text, klass, klick) {
		const b = document.createElement("button");
		b.textContent = text;
		b.className = klass;
		b.onclick = klick;
		return b;
	}

	function start() {
		lage = {};
		if (!enhet) {
			$("yta").innerHTML = "";
			return visa("Stämpling", "Enheten är inte registrerad. Be HR om en länk.");
		}
		knappsats("Anställningsnummer", false, (nummer) => {
			lage.nummer = nummer;
			knappsats("PIN-kod", true, (pin) => {
				lage.pin = pin;
				identifiera();
			});
		});
	}

	function identifiera() {
		anropa("identifiera", { anstallningsnummer: lage.nummer, pin: lage.pin }).then((svar) => {
			if (svar.fel) return start(), fel(svar.fel);
			lage.svar = svar;
			if (svar.maste_byta_pin) return bytPin();
			valjRiktning();
		});
	}

	function bytPin() {
		knappsats(`Hej ${lage.svar.fornamn}! Välj en ny PIN-kod (4 till 6 siffror)`, true, (ny) => {
			knappsats("Upprepa den nya PIN-koden", true, (igen) => {
				if (igen !== ny) return bytPin(), fel("PIN-koderna var inte lika.");
				anropa("byt_pin", { anstallningsnummer: lage.nummer, pin: lage.pin, ny_pin: ny }).then((svar) => {
					if (svar.fel) return bytPin(), fel(svar.fel);
					lage.pin = ny;
					identifiera();
				});
			});
		});
	}

	function valjRiktning() {
		const s = lage.svar;
		const yta = $("yta");
		yta.innerHTML = "";
		const rutnat = document.createElement("div");
		rutnat.className = "knappar";
		const text = { IN: "Stämpla in", OUT: "Stämpla ut" };
		const andra = s.riktning === "IN" ? "OUT" : "IN";
		rutnat.appendChild(knapp(text[s.riktning], "stor", () => fortsatt(s.riktning)));
		rutnat.appendChild(knapp(text[andra], "andra", () => fortsatt(andra)));
		yta.appendChild(rutnat);
		visa(`Hej ${s.fornamn}!`, "");
	}

	function fortsatt(riktning) {
		if (riktning === "OUT" && lage.svar.fraga_overtid) return valjErsattning();
		stampla(riktning, null);
	}

	function valjErsattning() {
		const yta = $("yta");
		yta.innerHTML = "";
		const rutnat = document.createElement("div");
		rutnat.className = "knappar val";
		for (const val of ["Pengar", "Komptid"]) {
			const b = knapp(val, "andra" + (val === lage.svar.forval ? " vald" : ""), () => stampla("OUT", val));
			rutnat.appendChild(b);
		}
		yta.appendChild(rutnat);
		visa(
			"Övertid",
			`Du har ${lage.svar.extra_minuter} minuter utanför ditt skift. Vill du ha pengar eller komptid?`
		);
	}

	function stampla(riktning, val) {
		anropa("stampla", {
			anstallningsnummer: lage.nummer,
			pin: lage.pin,
			log_type: riktning,
			overtidsersattning: val,
		}).then((svar) => {
			if (svar.fel) return start(), fel(svar.fel);
			$("yta").innerHTML = "";
			visa(`${riktning === "IN" ? "Instämplad" : "Utstämplad"} ${svar.tid}`, `Tack, ${svar.fornamn}!`);
			clearTimeout(timer);
			timer = setTimeout(start, 4000);
		});
	}

	frappe.ready(start);
})();
```

- [ ] **Step 4: Prova i webbläsaren** – på `<testsite>` (`bench --site <testsite> serve --port 8001` i bakgrunden):
  1. Skapa en Stämplingsenhet och en testanställd med anställningsnummer och skift; sätt PIN med Sätt PIN.
  2. Öppna länken från **Skapa länk**: anställningsnummer → PIN → byt PIN → "Hej …" → Stämpla in → kvittens.
  3. Ändra klockan går inte; kontrollera i stället att en checkin skapats med rätt enhet, och att fel PIN ger felmeddelandet.
  4. Ta bort testdata efteråt (checkins, enheten, testanställd) eller använd en rollback via konsolen.
  Om Playwright saknar Chrome: gör samma flöde med HTTP-anrop (`requests`) mot `/api/method/hrms_sverige.lon.stampling.*` och kontrollera att `/stampla` svarar 200 och innehåller `id="yta"`. Notera i ledger att den visuella kontrollen görs av användaren.

- [ ] **Step 5: Commit**

```bash
F="hrms_sverige/www/stampla.py hrms_sverige/www/stampla.html hrms_sverige/www/stampla.js"; git add $F; pre-commit run --files $F; git add $F
git commit -m "feat: time clock page /stampla" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016yYYj5agMiCoxsTCe4usfY"
```

---

### Task 6: Dokumentation, PR och CI

**Files:**
- Modify: `README.md`, `CHANGELOG.md`
- Create: docs-repot `docs/personal/stampling.md`; Modify: `mkdocs.yml` (grenen `personal/loneunderlag`)

- [ ] **Step 1: README** – lägg till efter punkten om övertid under "## HRMS Sverige":

```markdown
- Stämplingssida `/stampla` för en gemensam surfplatta eller dator: anställningsnummer och PIN-kod, in- och
  utstämpling och val av pengar eller komptid vid övertid. Enheter registreras som **Stämplingsenhet** med en
  hemlig länk; HR sätter PIN-koder med **Sätt PIN** på den anställde.
```

- [ ] **Step 2: CHANGELOG** – under `## Ej släppt`:

```markdown
- **Stämplingssida:** `/stampla` med anställningsnummer och PIN-kod, registrerade enheter, låsning efter fem
  felaktiga försök och fråga om pengar eller komptid vid övertid.
```

- [ ] **Step 3: Manualen** – i docs-repot (`git checkout personal/loneunderlag`), skapa `docs/personal/stampling.md`:

```markdown
# Stämpling

Personalen stämplar in och ut på en gemensam surfplatta eller dator. De identifierar sig med anställningsnummer och
en egen PIN-kod. Stämplingarna blir närvaro i ERPNext, och övertid och OB räknas ur dem i löneunderlaget.

## För HR

**Registrera en enhet:**

1. Sök efter **Stämplingsenhet** och skapa en ny, till exempel "Surfplatta entrén".
2. Klicka på **Skapa länk** och öppna länken en gång i webbläsaren på surfplattan eller datorn. Länken visas bara
   den gången; enheten kommer ihåg den.
3. Lägg gärna sidan på hemskärmen eller som startsida.

En förlorad enhet stängs av genom att ta bort bocken **Aktiv**. En ny länk gör den gamla ogiltig.

**Sätt PIN-koder:** öppna den anställde och välj **Stämpling > Sätt PIN**. Den anställde väljer en egen PIN-kod
vid första stämplingen. Har någon glömt sin kod sätter HR en ny på samma sätt. Anställningsnumret måste vara ifyllt.

Efter fem felaktiga försök låses anställningsnumret i 15 minuter.

## För personalen

1. Slå ditt anställningsnummer och tryck **OK**, sedan din PIN-kod och **OK**.
2. Första gången väljer du en ny PIN-kod (4 till 6 siffror) och upprepar den.
3. Tryck **Stämpla in** eller **Stämpla ut**. Sidan föreslår rätt knapp; den mindre knappen används om du glömt
   att stämpla förra gången.
4. Har du jobbat mer än en kvart utanför ditt skift frågar sidan om du vill ha **pengar** eller **komptid** för
   övertiden.

Glömt att stämpla? Säg till HR, som rättar närvaron i ERPNext.
```

och i `mkdocs.yml`, lägg till under `Personal:` efter `Löneunderlag till Crona`:

```yaml
      - Stämpling: personal/stampling.md
```

Bygg: `.venv/bin/mkdocs build --strict -q` – Expected: exit 0.

- [ ] **Step 4: Commit i båda repona, push, PR och CI**

```bash
cd <docs-repo>
git add docs/personal/stampling.md mkdocs.yml
git commit -m "docs: time clock" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016yYYj5agMiCoxsTCe4usfY"
git push; git checkout main
cd ~/frappe-bench/apps/hrms_sverige
git add README.md CHANGELOG.md
git commit -m "docs: document the time clock" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016yYYj5agMiCoxsTCe4usfY"
git push -u origin feat/stampling
gh pr create --base version-16 --title "Stämplingssida (del C1)" --body "Stämplingssidan /stampla. Spec: docs/superpowers/specs/2026-10-02-stampling-design.md

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_016yYYj5agMiCoxsTCe4usfY"
gh run watch --exit-status $(gh run list --branch feat/stampling --limit 1 --json databaseId -q '.[0].databaseId')
```
Expected: CI grön.

- [ ] **Step 5: Demo-siten och tillbaka till version-16**

```bash
cd ~/frappe-bench
bench --site <demosite> clear-cache && bench --site <demosite> migrate
git -C apps/hrms_sverige checkout version-16
bench --site <testsite> clear-cache && bench --site <demosite> clear-cache
```

Merge och produktion görs först efter användarens godkännande.
