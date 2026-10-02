# HRMS Sverige Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Installera Frappe HRMS och gör det användbart på svenska för personalregister, frånvaro och närvaro via
appen `hrms_sverige`.

**Architecture:** HRMS (`version-16`) installeras oförändrat. `hrms_sverige` (redan skapad med `bench new-app` i
`apps/hrms_sverige`, ett commit med spec) lägger på svenska uppsättningsdata i idempotenta Python-funktioner
(`setup/`), två doc_events-hooks (Employee.validate, Leave Allocation.before_insert) och en `sv.po` som vinner
över HRMS:s översättning eftersom appen installeras efter `hrms`.

**Tech Stack:** Frappe/ERPNext/HRMS 16, Python 3.14, `holidays` (redan beroende till ERPNext), babel `.po`,
Frappes testlöpare (`IntegrationTestCase`/`UnitTestCase`).

**Spec:** `apps/hrms_sverige/docs/superpowers/specs/2026-09-30-hrms-sverige-design.md`

**Avvikelser från specen (medvetna, bättre lösningar hittade vid planeringen):**
1. Helgdagar räknas **inte** med egen påskformel. Biblioteket `holidays` (`holidays.Sweden`, kategori
   `de_facto` ger midsommarafton/julafton/nyårsafton) används; det är redan ERPNext-beroende och har svenska namn.
2. HRMS 16 väljer helgdagslista via **Holiday List Assignment** (per företag/anställd, med startdatum), inte via
   `Company.default_holiday_list`. `create_holiday_list` skapar därför också en Holiday List Assignment för
   företaget från 1 januari. Då byter alla anställda lista automatiskt vid årsskiftet.
3. Egna fält och personnummerbehörighet skapas **i kod** (som `erpnext_sverige/setup/custom_fields.py`), inte som
   fixtures. En Custom DocPerm-fixture för Employee skulle ersätta alla standardbehörigheter på Employee.

## Global Constraints

- Frappe/ERPNext/HRMS `>=16,<17`, gren `version-16` för `hrms` och `hrms_sverige`.
- `required_apps = ["hrms"]` i `hrms_sverige/hooks.py`. `erpnext_sverige` rörs inte.
- Inga riktiga företagsnamn i repot. Tester använder eget testbolag `_Test HR Sverige AB`.
- Python: tabbar, radlängd 110, ruff + ruff-format via pre-commit (samma som `erpnext_sverige`).
- Fältetiketter skrivs direkt på svenska med `_()` (som i `erpnext_sverige`).
- Upstream-filer (`apps/hrms/**`, `apps/erpnext/**`, `apps/frappe/**`) ändras aldrig.
- Alla uppsättningsfunktioner är idempotenta: skapar det som saknas, uppdaterar det som finns, inga dubbletter.
- Semester: 25 dagar/kalenderår; deltid `ceil(dagar × arbetsdagar / 5)`, bara för tilldelningar med
  `leave_policy_assignment`; tomt/5 arbetsdagar lämnar värdet orört.
- Sparade dagar: `maximum_carry_forwarded_leaves = 5`, `expire_carry_forwarded_leaves_after_days = 1826`.
- Tester körs på `<testsite>` (har `allow_tests`), aldrig på `<site>`.
- Commits avslutas med `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Personnummer som skrivs "slarvigt"** (mellanslag, `+` för 100+ år, 10 siffror med framtida datum): ska
   normaliseras rätt, inte avvisas eller få fel sekel. → testas i Task 2.
2. **Anställd utan personnummer/arbetsdagar** (fälten är frivilliga): ska sparas utan fel, och semestern ska bli
   25 dagar. → testas i Task 3 och Task 6.
3. **Andra frånvarotyper och manuella tilldelningar** får aldrig deltidsomräknas. → testas i Task 6.
4. **Uppsättningen körs om efter att HR ändrat något** (t.ex. redan finns en Holiday List Assignment för
   företaget från 1 januari med en egen lista): vår kod ska inte skapa en konkurrerande tilldelning. → testas i
   Task 4.
5. **Översättningskonflikt med `erpnext_sverige`**: HRMS installeras efter `erpnext_sverige` och skriver över
   dess rättelser för gemensamma strängar (i dag "Advance Paid (Company Currency)" och "Uploading..."). →
   rapporteras av skriptet och rättas i Task 8.

## Filstruktur

```
apps/hrms_sverige/
  hrms_sverige/
    hooks.py                        required_apps, after_install, after_migrate, doc_events
    setup/
      __init__.py
      install.py                    setup_all(company=None), after_install(), after_migrate()
      custom_fields.py              egna Employee-fält + permlevel-behörighet
      employment_types.py           svenska anställningsformer
      holidays.py                   svenska_helgdagar(), create_holiday_list()
      leave.py                      frånvarotyper, ledighetsperiod, ledighetspolicy
      workspaces.py                 dölj arbetsytor/skrivbordsikoner
    hr/
      __init__.py
      personnummer.py               normalize(), validate_employee()
      leave_allocation.py           semesterdagar(), justera_for_deltid()
    scripts/
      __init__.py
      sarskrivningar.py
    locale/sv.po
    tests/
      __init__.py
      utils.py                      testbolag, testanställd
      test_personnummer.py
      test_employee.py
      test_holidays.py
      test_leave.py
      test_deltid.py
      test_setup.py
  README.md
```

---

### Task 1: Installera HRMS och hrms_sverige på testsajten, testinfrastruktur

**Files:**
- Modify: `apps/hrms_sverige/hrms_sverige/hooks.py` (rad `# required_apps = []`)
- Create: `apps/hrms_sverige/hrms_sverige/tests/__init__.py`
- Create: `apps/hrms_sverige/hrms_sverige/tests/utils.py`
- Create: `apps/hrms_sverige/hrms_sverige/tests/test_setup.py`

**Interfaces:**
- Produces: `hrms_sverige.tests.utils.COMPANY = "_Test HR Sverige AB"`, `ensure_test_company() -> str`,
  `make_test_employee(first_name: str, **fields) -> str` (Employee-namn).

- [ ] **Step 1: Hämta HRMS**

Från bench-roten (`~/frappe-bench`):
```bash
bench get-app hrms --branch version-16
```
Expected: `apps/hrms` finns, `hrms` tillagd i `sites/apps.txt`. Om kommandot slutar med
`sudo supervisorctl status ... non-zero exit status` är det bara omstartssteget; appen är ändå hämtad
(kontrollera `ls apps/hrms/hrms/hooks.py`).

- [ ] **Step 2: Installera HRMS på testsajten**

```bash
bench --site <testsite> install-app hrms
```
Expected: slutar utan traceback. Verifiera att `after_install` körts helt:
```bash
bench --site <testsite> execute frappe.db.get_value --args "['Custom Field', {'dt': 'Employee', 'fieldname': 'employment_type'}, 'name']"
```
Expected: `"Employee-employment_type"` (inte `None`). Om `None`: kör
`bench --site <testsite> execute hrms.install.after_install` och kontrollera igen.

- [ ] **Step 3: Sätt required_apps och installera hrms_sverige**

I `apps/hrms_sverige/hrms_sverige/hooks.py`, ersätt `# required_apps = []` med:
```python
required_apps = ["hrms"]
```
Sedan:
```bash
bench --site <testsite> install-app hrms_sverige
cd apps/hrms_sverige && pre-commit install && cd ../..
```
Expected: installationen lyckas; `bench --site <testsite> list-apps` visar
`frappe, erpnext, erpnext_sverige, hrms, hrms_sverige` i den ordningen.

- [ ] **Step 4: Skriv testhjälpare**

`apps/hrms_sverige/hrms_sverige/tests/__init__.py`: tom fil.

`apps/hrms_sverige/hrms_sverige/tests/utils.py`:
```python
"""Gemensamma testdata: ett eget testbolag och testanställda."""

import frappe

COMPANY = "_Test HR Sverige AB"
COMPANY_ABBR = "_THRS"


def ensure_test_company() -> str:
	if not frappe.db.exists("Company", COMPANY):
		frappe.get_doc(
			{
				"doctype": "Company",
				"company_name": COMPANY,
				"abbr": COMPANY_ABBR,
				"country": "Sweden",
				"default_currency": "SEK",
				"create_chart_of_accounts_based_on": "Standard Template",
				"chart_of_accounts": "Standard",
			}
		).insert()
	return COMPANY


def make_test_employee(first_name: str, **fields) -> str:
	"""Skapa (eller hämta) en anställd i testbolaget. `fields` skriver över standardvärdena."""
	ensure_test_company()
	existing = frappe.db.get_value("Employee", {"first_name": first_name, "company": COMPANY})
	if existing:
		if fields:
			frappe.db.set_value("Employee", existing, fields)
		return existing
	doc = frappe.get_doc(
		{
			"doctype": "Employee",
			"first_name": first_name,
			"company": COMPANY,
			"gender": "Female",
			"date_of_birth": "1990-05-08",
			"date_of_joining": "2020-01-01",
			"status": "Active",
		}
	)
	doc.update(fields)
	doc.insert()
	return doc.name
```

- [ ] **Step 5: Skriv ett rökttest för att se att testlöparen hittar appen**

`apps/hrms_sverige/hrms_sverige/tests/test_setup.py`:
```python
import frappe
from frappe.tests import IntegrationTestCase

from hrms_sverige.tests.utils import COMPANY, ensure_test_company, make_test_employee


class TestInstall(IntegrationTestCase):
	def test_hrms_installed_before_us(self):
		apps = frappe.get_installed_apps()
		self.assertLess(apps.index("hrms"), apps.index("hrms_sverige"))

	def test_test_employee(self):
		ensure_test_company()
		name = make_test_employee("Rök")
		self.assertEqual(frappe.db.get_value("Employee", name, "company"), COMPANY)
```

- [ ] **Step 6: Kör testet**

```bash
bench --site <testsite> run-tests --app hrms_sverige --module hrms_sverige.tests.test_setup
```
Expected: `OK`, 2 tester.

- [ ] **Step 7: Commit**

```bash
cd apps/hrms_sverige
git add hrms_sverige/hooks.py hrms_sverige/tests
git commit -m "feat: require hrms and add test helpers

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Personnummer (ren logik)

**Files:**
- Create: `apps/hrms_sverige/hrms_sverige/hr/__init__.py` (tom)
- Create: `apps/hrms_sverige/hrms_sverige/hr/personnummer.py`
- Test: `apps/hrms_sverige/hrms_sverige/tests/test_personnummer.py`

**Interfaces:**
- Produces: `hrms_sverige.hr.personnummer.normalize(value: str, today: date | None = None) -> str` (returnerar
  `ÅÅÅÅMMDD-NNNN`, kastar `OgiltigtPersonnummer(ValueError)`), `luhn_ok(digits10: str) -> bool`.

- [ ] **Step 1: Skriv de fallerande testerna**

`apps/hrms_sverige/hrms_sverige/tests/test_personnummer.py`:
```python
from datetime import date

from frappe.tests import UnitTestCase

from hrms_sverige.hr.personnummer import OgiltigtPersonnummer, luhn_ok, normalize

TODAY = date(2026, 9, 30)


class TestPersonnummer(UnitTestCase):
	def test_luhn(self):
		self.assertTrue(luhn_ok("8112189876"))
		self.assertFalse(luhn_ok("8112189875"))

	def test_valid_formats_normalize(self):
		for value in (
			"811218-9876",
			"8112189876",
			"19811218-9876",
			"198112189876",
			" 19811218 - 9876 ",
		):
			self.assertEqual(normalize(value, TODAY), "19811218-9876", value)

	def test_century_without_plus(self):
		self.assertEqual(normalize("121212-1212", TODAY), "20121212-1212")

	def test_plus_means_hundred_years_or_older(self):
		self.assertEqual(normalize("121212+1212", TODAY), "19121212-1212")

	def test_ten_digits_future_date_goes_back_a_century(self):
		self.assertEqual(normalize("261201-1235", TODAY), "19261201-1235")

	def test_samordningsnummer(self):
		self.assertEqual(normalize("701063-2391", TODAY), "19701063-2391")

	def test_invalid(self):
		for value in (
			"811218-9875",  # fel kontrollsiffra
			"200230-1238",  # 30 februari, rätt kontrollsiffra
			"20261201-1235",  # 12 siffror i framtiden
			"12345",
			"abcdef-ghij",
			"",
		):
			with self.assertRaises(OgiltigtPersonnummer, msg=value):
				normalize(value, TODAY)
```

- [ ] **Step 2: Kör och se att de fallerar**

```bash
bench --site <testsite> run-tests --app hrms_sverige --module hrms_sverige.tests.test_personnummer
```
Expected: FAIL/ERROR med `ModuleNotFoundError: No module named 'hrms_sverige.hr'`.

- [ ] **Step 3: Implementera**

`apps/hrms_sverige/hrms_sverige/hr/__init__.py`: tom fil.

`apps/hrms_sverige/hrms_sverige/hr/personnummer.py`:
```python
"""Svenska personnummer och samordningsnummer (dag + 60), med kontrollsiffra enligt Luhn."""

import re
from datetime import date

PATTERN = re.compile(r"^(\d{2})?(\d{2})(\d{2})(\d{2})([-+]?)(\d{4})$")
SAMORDNING_OFFSET = 60


class OgiltigtPersonnummer(ValueError):
	pass


def luhn_ok(digits: str) -> bool:
	"""Kontrollsiffra för de tio sista siffrorna (ÅÅMMDDNNNN)."""
	total = 0
	for i, ch in enumerate(digits):
		n = int(ch) * (2 if i % 2 == 0 else 1)
		total += n - 9 if n > 9 else n
	return total % 10 == 0


def normalize(value: str, today: date | None = None) -> str:
	"""Returnera numret som ÅÅÅÅMMDD-NNNN eller kasta OgiltigtPersonnummer.

	Tio siffror: seklet väljs så att födelsedatumet inte ligger i framtiden; "+" betyder 100 år eller äldre.
	"""
	today = today or date.today()
	match = PATTERN.match(re.sub(r"\s", "", value or ""))
	if not match:
		raise OgiltigtPersonnummer(value)
	century, yy, mm, dd, separator, tail = match.groups()

	day = int(dd)
	if day > SAMORDNING_OFFSET:
		day -= SAMORDNING_OFFSET

	def birth_date(year: int) -> date:
		try:
			return date(year, int(mm), day)
		except ValueError:
			raise OgiltigtPersonnummer(value) from None

	if century:
		year = int(century + yy)
		if birth_date(year) > today:
			raise OgiltigtPersonnummer(value)
	else:
		year = today.year // 100 * 100 + int(yy)
		if birth_date(year) > today:
			year -= 100
		if separator == "+":
			year -= 100
		birth_date(year)

	if not luhn_ok(yy + mm + dd + tail):
		raise OgiltigtPersonnummer(value)
	return f"{year:04d}{mm}{dd}-{tail}"
```

- [ ] **Step 4: Kör testerna**

```bash
bench --site <testsite> run-tests --app hrms_sverige --module hrms_sverige.tests.test_personnummer
```
Expected: `OK`, 7 tester.

- [ ] **Step 5: Commit**

```bash
cd apps/hrms_sverige
git add hrms_sverige/hr hrms_sverige/tests/test_personnummer.py
git commit -m "feat: validate and normalize Swedish personnummer

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Svenska fält på anställd, behörighet och anställningsformer

**Files:**
- Create: `apps/hrms_sverige/hrms_sverige/setup/__init__.py` (tom)
- Create: `apps/hrms_sverige/hrms_sverige/setup/custom_fields.py`
- Create: `apps/hrms_sverige/hrms_sverige/setup/employment_types.py`
- Modify: `apps/hrms_sverige/hrms_sverige/hr/personnummer.py` (lägg till `validate_employee`)
- Modify: `apps/hrms_sverige/hrms_sverige/hooks.py` (doc_events)
- Test: `apps/hrms_sverige/hrms_sverige/tests/test_employee.py`

**Interfaces:**
- Consumes: `normalize`, `OgiltigtPersonnummer` (Task 2), `make_test_employee` (Task 1).
- Produces: `setup.custom_fields.create_custom_fields() -> None`, `setup.custom_fields.HR_ROLES`,
  `setup.employment_types.EMPLOYMENT_TYPES: tuple[str, ...]`, `setup.employment_types.ensure_employment_types()`,
  `hr.personnummer.validate_employee(doc, method=None)`. Fältnamn: `personnummer`, `arbetsdagar_per_vecka`,
  `sysselsattningsgrad`.

- [ ] **Step 1: Skriv de fallerande testerna**

`apps/hrms_sverige/hrms_sverige/tests/test_employee.py`:
```python
import frappe
from frappe.tests import IntegrationTestCase

from hrms_sverige.setup.custom_fields import create_custom_fields
from hrms_sverige.setup.employment_types import EMPLOYMENT_TYPES, ensure_employment_types
from hrms_sverige.tests.utils import make_test_employee

READER = "hrms-sverige-reader@example.com"


class TestEmployeeFields(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		create_custom_fields()
		ensure_employment_types()

	def test_personnummer_is_normalized(self):
		name = make_test_employee("Pnr")
		doc = frappe.get_doc("Employee", name)
		doc.personnummer = "811218-9876"
		doc.save()
		self.assertEqual(doc.personnummer, "19811218-9876")

	def test_invalid_personnummer_is_rejected(self):
		doc = frappe.get_doc("Employee", make_test_employee("PnrFel"))
		doc.personnummer = "811218-9875"
		self.assertRaises(frappe.ValidationError, doc.save)

	def test_empty_fields_are_allowed(self):
		doc = frappe.get_doc("Employee", make_test_employee("Tom"))
		doc.personnummer = ""
		doc.arbetsdagar_per_vecka = 0
		doc.save()

	def test_arbetsdagar_out_of_range(self):
		doc = frappe.get_doc("Employee", make_test_employee("Dagar"))
		doc.arbetsdagar_per_vecka = 6
		self.assertRaises(frappe.ValidationError, doc.save)

	def test_employment_types_exist(self):
		for name in EMPLOYMENT_TYPES:
			self.assertTrue(frappe.db.exists("Employment Type", name), name)

	def test_personnummer_hidden_without_hr_role(self):
		name = make_test_employee("Dold", personnummer="19811218-9876")
		if not frappe.db.exists("User", READER):
			user = frappe.get_doc(
				{"doctype": "User", "email": READER, "first_name": "Läsare", "send_welcome_email": 0}
			).insert()
			user.add_roles("Accounts User")  # läsrätt på Employee, nivå 0
		frappe.set_user(READER)
		try:
			doc = frappe.get_doc("Employee", name)
			doc.apply_fieldlevel_read_permissions()
			self.assertFalse(doc.personnummer)
		finally:
			frappe.set_user("Administrator")
```

- [ ] **Step 2: Kör och se att de fallerar**

```bash
bench --site <testsite> run-tests --app hrms_sverige --module hrms_sverige.tests.test_employee
```
Expected: ERROR `No module named 'hrms_sverige.setup'`.

- [ ] **Step 3: Implementera fält och behörighet**

`apps/hrms_sverige/hrms_sverige/setup/__init__.py`: tom fil.

`apps/hrms_sverige/hrms_sverige/setup/custom_fields.py`:
```python
import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields as _create_custom_fields
from frappe.permissions import add_permission, update_permission_property

# Roller som får läsa och ändra personnummer (permlevel 1 på Employee)
HR_ROLES = ("HR Manager", "HR User")
PERSONNUMMER_PERMLEVEL = 1


def get_custom_fields():
	return {
		"Employee": [
			{
				"fieldname": "personnummer",
				"label": _("Personnummer"),
				"fieldtype": "Data",
				"insert_after": "date_of_birth",
				"permlevel": PERSONNUMMER_PERMLEVEL,
				"description": _("ÅÅÅÅMMDD-NNNN. Samordningsnummer godkänns."),
			},
			{
				"fieldname": "arbetsdagar_per_vecka",
				"label": _("Arbetsdagar per vecka"),
				"fieldtype": "Int",
				"insert_after": "employment_type",
				"description": _("1–5. Tomt räknas som 5. Styr antalet semesterdagar vid deltid."),
			},
			{
				"fieldname": "sysselsattningsgrad",
				"label": _("Sysselsättningsgrad (%)"),
				"fieldtype": "Percent",
				"insert_after": "arbetsdagar_per_vecka",
			},
		],
	}


def create_custom_fields():
	_create_custom_fields(get_custom_fields(), update=True)
	for role in HR_ROLES:
		if not frappe.db.exists(
			"Custom DocPerm", {"parent": "Employee", "role": role, "permlevel": PERSONNUMMER_PERMLEVEL}
		):
			add_permission("Employee", role, PERSONNUMMER_PERMLEVEL)
		update_permission_property("Employee", role, PERSONNUMMER_PERMLEVEL, "write", 1)
```

`apps/hrms_sverige/hrms_sverige/setup/employment_types.py`:
```python
import frappe

EMPLOYMENT_TYPES = ("Tillsvidare", "Provanställning", "Allmän visstid", "Vikariat", "Säsongsanställning")


def ensure_employment_types():
	for name in EMPLOYMENT_TYPES:
		if not frappe.db.exists("Employment Type", name):
			frappe.get_doc({"doctype": "Employment Type", "employee_type_name": name}).insert(
				ignore_permissions=True
			)
```

- [ ] **Step 4: Implementera validering och koppla in hooken**

Lägg till i slutet av `apps/hrms_sverige/hrms_sverige/hr/personnummer.py` (och `import frappe` + `from frappe import _`
överst bland importerna):
```python
HELTID_DAGAR = 5


def validate_employee(doc, method=None):
	"""Employee.validate: normalisera personnummer och kontrollera arbetsdagar per vecka."""
	if doc.get("personnummer"):
		try:
			doc.personnummer = normalize(doc.personnummer)
		except OgiltigtPersonnummer:
			frappe.throw(_("Ogiltigt personnummer: {0}").format(doc.personnummer))
	if doc.get("arbetsdagar_per_vecka") and not 1 <= doc.arbetsdagar_per_vecka <= HELTID_DAGAR:
		frappe.throw(_("Arbetsdagar per vecka ska vara mellan 1 och {0}.").format(HELTID_DAGAR))
```

I `apps/hrms_sverige/hrms_sverige/hooks.py`, ersätt det utkommenterade `# doc_events = {...}`-blocket med:
```python
doc_events = {
	"Employee": {
		"validate": "hrms_sverige.hr.personnummer.validate_employee",
	},
}
```

- [ ] **Step 5: Kör testerna**

```bash
bench --site <testsite> run-tests --app hrms_sverige --module hrms_sverige.tests.test_employee
```
Expected: `OK`, 6 tester. Om `test_personnummer_hidden_without_hr_role` fallerar för att "Accounts User" saknar
läsrätt på Employee: kontrollera med `frappe.get_meta("Employee").permissions` vilken icke-HR-roll som har
`read` på permlevel 0 och använd den i testet.

- [ ] **Step 6: Commit**

```bash
cd apps/hrms_sverige
git add hrms_sverige/setup hrms_sverige/hr/personnummer.py hrms_sverige/hooks.py hrms_sverige/tests/test_employee.py
git commit -m "feat: add Swedish employee fields and employment types

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Svenska helgdagslistor

**Files:**
- Create: `apps/hrms_sverige/hrms_sverige/setup/holidays.py`
- Test: `apps/hrms_sverige/hrms_sverige/tests/test_holidays.py`

**Interfaces:**
- Consumes: `ensure_test_company`, `COMPANY` (Task 1).
- Produces: `svenska_helgdagar(year: int, aftnar: bool = True) -> dict[date, str]`,
  `holiday_list_name(year: int) -> str` (`"Sverige 2027"`),
  `create_holiday_list(year: int, company: str | None = None, aftnar: bool = True) -> str`.

- [ ] **Step 1: Skriv de fallerande testerna**

`apps/hrms_sverige/hrms_sverige/tests/test_holidays.py`:
```python
from datetime import date

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from hrms_sverige.setup.holidays import create_holiday_list, holiday_list_name, svenska_helgdagar
from hrms_sverige.tests.utils import COMPANY, ensure_test_company

KNOWN = {
	2025: {"Långfredagen": date(2025, 4, 18), "Midsommardagen": date(2025, 6, 21), "Alla helgons dag": date(2025, 11, 1)},
	2026: {"Långfredagen": date(2026, 4, 3), "Midsommardagen": date(2026, 6, 20), "Alla helgons dag": date(2026, 10, 31)},
	2027: {"Långfredagen": date(2027, 3, 26), "Midsommardagen": date(2027, 6, 26), "Alla helgons dag": date(2027, 11, 6)},
	2028: {"Långfredagen": date(2028, 4, 14), "Midsommardagen": date(2028, 6, 24), "Alla helgons dag": date(2028, 11, 4)},
}


class TestSvenskaHelgdagar(UnitTestCase):
	def test_known_dates(self):
		for year, expected in KNOWN.items():
			by_name = {name: day for day, name in svenska_helgdagar(year).items()}
			for name, day in expected.items():
				self.assertEqual(by_name[name], day, f"{name} {year}")

	def test_aftnar(self):
		with_eves = svenska_helgdagar(2026)
		without = svenska_helgdagar(2026, aftnar=False)
		for day in (date(2026, 6, 19), date(2026, 12, 24), date(2026, 12, 31)):
			self.assertIn(day, with_eves)
			self.assertNotIn(day, without)
		self.assertEqual(len(without), 13)  # röda dagar utom söndagar som inte är helgdag i sig


class TestHolidayList(IntegrationTestCase):
	def test_create_is_idempotent_and_assigned(self):
		ensure_test_company()
		name = create_holiday_list(2031, COMPANY)
		self.assertEqual(name, holiday_list_name(2031))
		first = frappe.get_doc("Holiday List", name)
		create_holiday_list(2031, COMPANY)
		second = frappe.get_doc("Holiday List", name)
		self.assertEqual(len(first.holidays), len(second.holidays))
		dates = [h.holiday_date for h in second.holidays]
		self.assertEqual(len(dates), len(set(dates)))
		self.assertIn(date(2031, 12, 24), dates)
		self.assertIn(date(2031, 1, 4), dates)  # lördag = veckovila
		self.assertEqual(
			frappe.db.count(
				"Holiday List Assignment",
				{"assigned_to": COMPANY, "from_date": "2031-01-01", "docstatus": 1},
			),
			1,
		)

	def test_existing_assignment_is_respected(self):
		ensure_test_company()
		own = frappe.get_doc(
			{
				"doctype": "Holiday List",
				"holiday_list_name": "_Test Egen lista 2032",
				"from_date": "2032-01-01",
				"to_date": "2032-12-31",
			}
		).insert()
		frappe.get_doc(
			{
				"doctype": "Holiday List Assignment",
				"applicable_for": "Company",
				"assigned_to": COMPANY,
				"holiday_list": own.name,
				"from_date": "2032-01-01",
			}
		).submit()
		create_holiday_list(2032, COMPANY)
		assigned = frappe.get_all(
			"Holiday List Assignment",
			{"assigned_to": COMPANY, "from_date": "2032-01-01", "docstatus": 1},
			pluck="holiday_list",
		)
		self.assertEqual(assigned, [own.name])
```

Obs: kontrollera `len(without) == 13` mot biblioteket vid första körningen (13 röda dagar 2026: nyårsdagen,
trettondedag jul, långfredagen, påskdagen, annandag påsk, första maj, Kristi himmelsfärdsdag, pingstdagen,
nationaldagen, midsommardagen, alla helgons dag, juldagen, annandag jul).

- [ ] **Step 2: Kör och se att de fallerar**

```bash
bench --site <testsite> run-tests --app hrms_sverige --module hrms_sverige.tests.test_holidays
```
Expected: ERROR `cannot import name 'create_holiday_list'` / modul saknas.

- [ ] **Step 3: Implementera**

`apps/hrms_sverige/hrms_sverige/setup/holidays.py`:
```python
"""Svenska helgdagslistor: röda dagar plus midsommarafton, julafton och nyårsafton."""

from datetime import date, timedelta

import erpnext
import frappe
import holidays

SATURDAY, SUNDAY = 5, 6


def svenska_helgdagar(year: int, aftnar: bool = True) -> dict[date, str]:
	categories = ("public", "de_facto") if aftnar else ("public",)
	days = holidays.Sweden(years=year, include_sundays=False, language="sv", categories=categories)
	return dict(sorted(days.items()))


def holiday_list_name(year: int) -> str:
	return f"Sverige {year}"


def create_holiday_list(year: int, company: str | None = None, aftnar: bool = True) -> str:
	"""Skapa eller uppdatera "Sverige ÅÅÅÅ" och tilldela den företaget från 1 januari.

	    bench --site <site> execute hrms_sverige.setup.holidays.create_holiday_list --kwargs "{'year': 2027}"
	"""
	year = int(year)
	name = holiday_list_name(year)
	if frappe.db.exists("Holiday List", name):
		doc = frappe.get_doc("Holiday List", name)
		doc.set("holidays", [])
	else:
		doc = frappe.new_doc("Holiday List")
		doc.holiday_list_name = name
	doc.from_date = date(year, 1, 1)
	doc.to_date = date(year, 12, 31)
	doc.country = "SE"

	named = svenska_helgdagar(year, aftnar)
	day = doc.from_date
	while day <= doc.to_date:
		weekend = day.weekday() in (SATURDAY, SUNDAY)
		if day in named:
			doc.append("holidays", {"holiday_date": day, "description": named[day], "weekly_off": int(weekend)})
		elif weekend:
			doc.append(
				"holidays",
				{"holiday_date": day, "description": "Lördag" if day.weekday() == SATURDAY else "Söndag", "weekly_off": 1},
			)
		day += timedelta(days=1)
	doc.save(ignore_permissions=True)

	company = company or erpnext.get_default_company()
	if company:
		_assign_to_company(doc.name, company, doc.from_date)
	return doc.name


def _assign_to_company(holiday_list: str, company: str, from_date: date):
	"""Rör inte en befintlig tilldelning för samma startdatum; HR kan ha valt en egen lista."""
	if frappe.db.exists(
		"Holiday List Assignment", {"assigned_to": company, "from_date": from_date, "docstatus": 1}
	):
		return
	frappe.get_doc(
		{
			"doctype": "Holiday List Assignment",
			"applicable_for": "Company",
			"assigned_to": company,
			"holiday_list": holiday_list,
			"from_date": from_date,
		}
	).submit()
```

- [ ] **Step 4: Kör testerna**

```bash
bench --site <testsite> run-tests --app hrms_sverige --module hrms_sverige.tests.test_holidays
```
Expected: `OK`, 4 tester. Om `doc.country = "SE"` avvisas av Autocomplete-valideringen: ta bort raden (fältet
behövs bara för ERPNext:s knapp "Hämta lokala helgdagar").

- [ ] **Step 5: Commit**

```bash
cd apps/hrms_sverige
git add hrms_sverige/setup/holidays.py hrms_sverige/tests/test_holidays.py
git commit -m "feat: generate Swedish holiday lists and assign them to the company

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Frånvarotyper, ledighetsperiod och semesterpolicy

**Files:**
- Create: `apps/hrms_sverige/hrms_sverige/setup/leave.py`
- Test: `apps/hrms_sverige/hrms_sverige/tests/test_leave.py`

**Interfaces:**
- Consumes: `create_holiday_list` (Task 4), `make_test_employee`, `ensure_test_company`, `COMPANY` (Task 1).
- Produces: `SEMESTER = "Semester"`, `KOMPLEDIGHET = "Kompledighet"`, `LEAVE_TYPES: dict[str, dict]`,
  `SEMESTER_POLICY_TITLE = "Semester 25 dagar"`, `ARLIG_SEMESTER = 25`, `ensure_leave_types()`,
  `ensure_leave_period(year: int, company: str) -> str`, `ensure_semester_policy() -> str`.

- [ ] **Step 1: Skriv de fallerande testerna**

`apps/hrms_sverige/hrms_sverige/tests/test_leave.py`:
```python
import frappe
from frappe.tests import IntegrationTestCase

from hrms_sverige.setup.holidays import create_holiday_list
from hrms_sverige.setup.leave import (
	LEAVE_TYPES,
	SEMESTER,
	ensure_leave_period,
	ensure_leave_types,
	ensure_semester_policy,
)
from hrms_sverige.tests.utils import COMPANY, ensure_test_company, make_test_employee


class TestLeaveSetup(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_test_company()
		ensure_leave_types()

	def test_leave_types(self):
		for name in LEAVE_TYPES:
			self.assertTrue(frappe.db.exists("Leave Type", name), name)
		semester = frappe.get_doc("Leave Type", SEMESTER)
		self.assertEqual(semester.is_carry_forward, 1)
		self.assertEqual(semester.maximum_carry_forwarded_leaves, 5)
		self.assertEqual(semester.expire_carry_forwarded_leaves_after_days, 1826)
		self.assertEqual(semester.include_holiday, 0)
		self.assertEqual(frappe.db.get_value("Leave Type", "Kompledighet", "is_compensatory"), 1)

	def test_idempotent(self):
		ensure_leave_types()
		p1 = ensure_semester_policy()
		p2 = ensure_semester_policy()
		self.assertEqual(p1, p2)
		l1 = ensure_leave_period(2030, COMPANY)
		l2 = ensure_leave_period(2030, COMPANY)
		self.assertEqual(l1, l2)
		self.assertEqual(frappe.db.count("Leave Type", {"name": SEMESTER}), 1)

	def test_sick_leave_without_allocation(self):
		frappe.db.set_single_value("HR Settings", "leave_approver_mandatory_in_leave_application", 0)
		create_holiday_list(2026, COMPANY)
		employee = make_test_employee("Sjuk")
		application = frappe.get_doc(
			{
				"doctype": "Leave Application",
				"employee": employee,
				"company": COMPANY,
				"leave_type": "Sjukfrånvaro",
				"from_date": "2026-03-02",
				"to_date": "2026-03-03",
				"posting_date": "2026-03-02",
				"status": "Open",
			}
		).insert()
		self.assertEqual(application.total_leave_days, 2)
```

- [ ] **Step 2: Kör och se att de fallerar**

```bash
bench --site <testsite> run-tests --app hrms_sverige --module hrms_sverige.tests.test_leave
```
Expected: ERROR `No module named 'hrms_sverige.setup.leave'`.

- [ ] **Step 3: Implementera**

`apps/hrms_sverige/hrms_sverige/setup/leave.py`:
```python
"""Svenska frånvarotyper, ledighetsperiod per kalenderår och semesterpolicy (25 dagar)."""

from datetime import date

import frappe

SEMESTER = "Semester"
KOMPLEDIGHET = "Kompledighet"
ARLIG_SEMESTER = 25
SEMESTER_POLICY_TITLE = "Semester 25 dagar"

# Semesterlagen: dagar utöver 20 får sparas (max 5/år) och tas ut inom fem år.
LEAVE_TYPES = {
	SEMESTER: {
		"is_lwp": 0,
		"include_holiday": 0,
		"is_carry_forward": 1,
		"maximum_carry_forwarded_leaves": 5,
		"expire_carry_forwarded_leaves_after_days": 1826,
		"allow_encashment": 0,
	},
	# is_lwp: ansökan kräver ingen tilldelning. Utan lönemodul påverkar flaggan inget annat.
	"Sjukfrånvaro": {"is_lwp": 1, "include_holiday": 0},
	"VAB": {"is_lwp": 1, "include_holiday": 0},
	"Föräldraledighet": {"is_lwp": 1, "include_holiday": 0},
	"Tjänstledighet": {"is_lwp": 1, "include_holiday": 0},
	KOMPLEDIGHET: {"is_compensatory": 1, "is_lwp": 0, "include_holiday": 0},
}


def ensure_leave_types():
	for name, settings in LEAVE_TYPES.items():
		if frappe.db.exists("Leave Type", name):
			doc = frappe.get_doc("Leave Type", name)
		else:
			doc = frappe.new_doc("Leave Type")
			doc.leave_type_name = name
		doc.update(settings)
		doc.save(ignore_permissions=True)


def ensure_leave_period(year: int, company: str) -> str:
	from_date, to_date = date(year, 1, 1), date(year, 12, 31)
	existing = frappe.db.get_value(
		"Leave Period", {"company": company, "from_date": from_date, "to_date": to_date}
	)
	if existing:
		return existing
	doc = frappe.get_doc(
		{
			"doctype": "Leave Period",
			"company": company,
			"from_date": from_date,
			"to_date": to_date,
			"is_active": 1,
		}
	).insert(ignore_permissions=True)
	return doc.name


def ensure_semester_policy() -> str:
	existing = frappe.db.get_value("Leave Policy", {"title": SEMESTER_POLICY_TITLE, "docstatus": 1})
	if existing:
		return existing
	doc = frappe.get_doc(
		{
			"doctype": "Leave Policy",
			"title": SEMESTER_POLICY_TITLE,
			"leave_policy_details": [{"leave_type": SEMESTER, "annual_allocation": ARLIG_SEMESTER}],
		}
	)
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc.name
```

- [ ] **Step 4: Kör testerna**

```bash
bench --site <testsite> run-tests --app hrms_sverige --module hrms_sverige.tests.test_leave
```
Expected: `OK`, 3 tester. Om `test_sick_leave_without_allocation` fallerar på saknad ledighetsgodkännare trots
inställningen: sätt `"leave_approver": "Administrator"` i ansökan.

- [ ] **Step 5: Commit**

```bash
cd apps/hrms_sverige
git add hrms_sverige/setup/leave.py hrms_sverige/tests/test_leave.py
git commit -m "feat: add Swedish leave types, leave period and vacation policy

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Deltidsomräkning av semester

**Files:**
- Create: `apps/hrms_sverige/hrms_sverige/hr/leave_allocation.py`
- Modify: `apps/hrms_sverige/hrms_sverige/hooks.py` (doc_events)
- Test: `apps/hrms_sverige/hrms_sverige/tests/test_deltid.py`

**Interfaces:**
- Consumes: `SEMESTER`, `ensure_leave_types`, `ensure_leave_period`, `ensure_semester_policy` (Task 5),
  `create_holiday_list` (Task 4), `create_custom_fields` (Task 3), `HELTID_DAGAR` (Task 3,
  `hr/personnummer.py`), `make_test_employee` (Task 1).
- Produces: `semesterdagar(dagar: float, arbetsdagar_per_vecka: int | None) -> float`,
  `justera_for_deltid(doc, method=None)`.

- [ ] **Step 1: Skriv de fallerande testerna**

`apps/hrms_sverige/hrms_sverige/tests/test_deltid.py`:
```python
import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from hrms_sverige.hr.leave_allocation import semesterdagar
from hrms_sverige.setup.custom_fields import create_custom_fields
from hrms_sverige.setup.holidays import create_holiday_list
from hrms_sverige.setup.leave import (
	SEMESTER,
	ensure_leave_period,
	ensure_leave_types,
	ensure_semester_policy,
)
from hrms_sverige.tests.utils import COMPANY, ensure_test_company, make_test_employee

YEAR = 2026


class TestSemesterdagar(UnitTestCase):
	def test_values(self):
		self.assertEqual(semesterdagar(25, 5), 25)
		self.assertEqual(semesterdagar(25, 4), 20)
		self.assertEqual(semesterdagar(25, 3), 15)
		self.assertEqual(semesterdagar(25, None), 25)
		self.assertEqual(semesterdagar(25, 0), 25)
		self.assertEqual(semesterdagar(12.5, 3), 8)  # 7,5 avrundas uppåt
		self.assertEqual(semesterdagar(12.5, 5), 12.5)  # heltid lämnas orörd


class TestDeltidAllocation(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_test_company()
		create_custom_fields()
		ensure_leave_types()
		create_holiday_list(YEAR, COMPANY)
		cls.leave_period = ensure_leave_period(YEAR, COMPANY)
		cls.policy = ensure_semester_policy()

	def _clean(self, employee):
		"""Testanställda återanvänds mellan körningar; HRMS vägrar överlappande tilldelningar."""
		for doctype in ("Leave Ledger Entry", "Leave Allocation", "Leave Policy Assignment"):
			frappe.db.delete(doctype, {"employee": employee})

	def _assign(self, employee):
		self._clean(employee)
		assignment = frappe.get_doc(
			{
				"doctype": "Leave Policy Assignment",
				"employee": employee,
				"company": COMPANY,
				"leave_policy": self.policy,
				"assignment_based_on": "Leave Period",
				"leave_period": self.leave_period,
				"effective_from": f"{YEAR}-01-01",
				"effective_to": f"{YEAR}-12-31",
			}
		)
		assignment.submit()
		return frappe.db.get_value(
			"Leave Allocation",
			{"employee": employee, "leave_type": SEMESTER, "leave_policy_assignment": assignment.name},
			"new_leaves_allocated",
		)

	def test_part_time_three_days(self):
		self.assertEqual(self._assign(make_test_employee("Deltid3", arbetsdagar_per_vecka=3)), 15)

	def test_full_time_empty_field(self):
		self.assertEqual(self._assign(make_test_employee("Heltid")), 25)

	def test_manual_allocation_untouched(self):
		employee = make_test_employee("Manuell", arbetsdagar_per_vecka=3)
		self._clean(employee)
		allocation = frappe.get_doc(
			{
				"doctype": "Leave Allocation",
				"employee": employee,
				"leave_type": SEMESTER,
				"from_date": f"{YEAR}-01-01",
				"to_date": f"{YEAR}-12-31",
				"new_leaves_allocated": 25,
			}
		).insert()
		self.assertEqual(allocation.new_leaves_allocated, 25)

	def test_other_leave_type_untouched(self):
		employee = make_test_employee("Komp", arbetsdagar_per_vecka=3)
		self._clean(employee)
		allocation = frappe.get_doc(
			{
				"doctype": "Leave Allocation",
				"employee": employee,
				"leave_type": "Kompledighet",
				"from_date": f"{YEAR}-01-01",
				"to_date": f"{YEAR}-12-31",
				"new_leaves_allocated": 10,
			}
		).insert()
		self.assertEqual(allocation.new_leaves_allocated, 10)
```

- [ ] **Step 2: Kör och se att de fallerar**

```bash
bench --site <testsite> run-tests --app hrms_sverige --module hrms_sverige.tests.test_deltid
```
Expected: ERROR `No module named 'hrms_sverige.hr.leave_allocation'`.

- [ ] **Step 3: Implementera**

`apps/hrms_sverige/hrms_sverige/hr/leave_allocation.py`:
```python
"""Semester vid deltid: 25 dagar räknas om till uttagsdagar efter arbetsdagar per vecka."""

import math

import frappe

from hrms_sverige.hr.personnummer import HELTID_DAGAR
from hrms_sverige.setup.leave import SEMESTER


def semesterdagar(dagar: float, arbetsdagar_per_vecka: int | None) -> float:
	arbetsdagar = arbetsdagar_per_vecka or HELTID_DAGAR
	if arbetsdagar >= HELTID_DAGAR:
		return dagar
	# round() först så att flyttalsfel (15.000000001) inte avrundas upp till 16
	return math.ceil(round(dagar * arbetsdagar / HELTID_DAGAR, 6))


def justera_for_deltid(doc, method=None):
	"""Leave Allocation.before_insert: bara semester som skapas från en policykoppling."""
	if doc.leave_type != SEMESTER or not doc.leave_policy_assignment:
		return
	arbetsdagar = frappe.db.get_value("Employee", doc.employee, "arbetsdagar_per_vecka")
	doc.new_leaves_allocated = semesterdagar(doc.new_leaves_allocated, arbetsdagar)
```

I `apps/hrms_sverige/hrms_sverige/hooks.py`, utöka `doc_events`:
```python
doc_events = {
	"Employee": {
		"validate": "hrms_sverige.hr.personnummer.validate_employee",
	},
	"Leave Allocation": {
		"before_insert": "hrms_sverige.hr.leave_allocation.justera_for_deltid",
	},
}
```

- [ ] **Step 4: Kör testerna**

```bash
bench --site <testsite> run-tests --app hrms_sverige --module hrms_sverige.tests.test_deltid
```
Expected: `OK`, 5 tester. `before_insert` körs före `validate`, där HRMS räknar `total_leaves_allocated` från
`new_leaves_allocated`, så totalen följer med.

- [ ] **Step 5: Commit**

```bash
cd apps/hrms_sverige
git add hrms_sverige/hr/leave_allocation.py hrms_sverige/hooks.py hrms_sverige/tests/test_deltid.py
git commit -m "feat: scale vacation days for part-time employees

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Dölj oanvända arbetsytor och samla uppsättningen i install-hooks

**Files:**
- Create: `apps/hrms_sverige/hrms_sverige/setup/workspaces.py`
- Create: `apps/hrms_sverige/hrms_sverige/setup/install.py`
- Modify: `apps/hrms_sverige/hrms_sverige/hooks.py` (after_install, after_migrate)
- Modify: `apps/hrms_sverige/hrms_sverige/tests/test_setup.py`

**Interfaces:**
- Consumes: alla `ensure_*`/`create_*` från Task 3–5.
- Produces: `workspaces.HIDDEN: tuple[str, ...]`, `workspaces.hide_unused()`,
  `install.setup_all(company: str | None = None)`, `install.after_install()`, `install.after_migrate()`.

- [ ] **Step 1: Skriv de fallerande testerna**

Lägg till i `apps/hrms_sverige/hrms_sverige/tests/test_setup.py`:
```python
from hrms_sverige.setup.install import setup_all
from hrms_sverige.setup.workspaces import HIDDEN


class TestSetupAll(IntegrationTestCase):
	def test_idempotent(self):
		ensure_test_company()
		setup_all(COMPANY)
		counts = {
			doctype: frappe.db.count(doctype)
			for doctype in ("Leave Type", "Leave Period", "Leave Policy", "Holiday List", "Employment Type", "Holiday List Assignment")
		}
		setup_all(COMPANY)
		for doctype, count in counts.items():
			self.assertEqual(frappe.db.count(doctype), count, doctype)

	def test_workspaces_hidden(self):
		setup_all(COMPANY)
		for name in HIDDEN:
			if frappe.db.exists("Workspace", name):
				self.assertEqual(frappe.db.get_value("Workspace", name, "is_hidden"), 1, name)
			if frappe.db.exists("Desktop Icon", name):
				self.assertEqual(frappe.db.get_value("Desktop Icon", name, "hidden"), 1, name)
		self.assertEqual(frappe.db.get_value("Workspace", "Leaves", "is_hidden"), 0)
```

- [ ] **Step 2: Kör och se att de fallerar**

```bash
bench --site <testsite> run-tests --app hrms_sverige --module hrms_sverige.tests.test_setup
```
Expected: ERROR `No module named 'hrms_sverige.setup.install'`.

- [ ] **Step 3: Implementera**

`apps/hrms_sverige/hrms_sverige/setup/workspaces.py`:
```python
"""Dölj HRMS-arbetsytor vi inte använder. Modulerna finns kvar och kan visas igen."""

import frappe

HIDDEN = ("Payroll", "Tax & Benefits", "Recruitment", "Expenses", "Performance", "Tenure")


def hide_unused():
	for name in HIDDEN:
		if frappe.db.exists("Workspace", name):
			frappe.db.set_value("Workspace", name, "is_hidden", 1)
		if frappe.db.exists("Desktop Icon", name):
			frappe.db.set_value("Desktop Icon", name, "hidden", 1)
```

`apps/hrms_sverige/hrms_sverige/setup/install.py`:
```python
import erpnext
from frappe.utils import getdate

from hrms_sverige.setup.custom_fields import create_custom_fields
from hrms_sverige.setup.employment_types import ensure_employment_types
from hrms_sverige.setup.holidays import create_holiday_list
from hrms_sverige.setup.leave import ensure_leave_period, ensure_leave_types, ensure_semester_policy
from hrms_sverige.setup.workspaces import hide_unused


def setup_all(company: str | None = None):
	"""All svensk uppsättning. Kan köras om:

	bench --site <site> execute hrms_sverige.setup.install.setup_all
	"""
	company = company or erpnext.get_default_company()
	create_custom_fields()
	ensure_employment_types()
	ensure_leave_types()
	ensure_semester_policy()
	if company:
		year = getdate().year
		for y in (year, year + 1):
			create_holiday_list(y, company)
			ensure_leave_period(y, company)
	hide_unused()


def after_install():
	setup_all()


def after_migrate():
	# Migrate synkar om arbetsytor och ikoner från HRMS och kan visa dem igen.
	create_custom_fields()
	hide_unused()
```

I `apps/hrms_sverige/hrms_sverige/hooks.py`, ersätt de utkommenterade `# after_install = ...`-raderna med:
```python
after_install = "hrms_sverige.setup.install.after_install"
after_migrate = "hrms_sverige.setup.install.after_migrate"
```

- [ ] **Step 4: Kör testerna**

```bash
bench --site <testsite> run-tests --app hrms_sverige --module hrms_sverige.tests.test_setup
```
Expected: `OK`, 4 tester.

- [ ] **Step 5: Kör uppsättningen på testsajtens riktiga företag och migrera**

```bash
bench --site <testsite> execute hrms_sverige.setup.install.setup_all
bench --site <testsite> migrate
bench --site <testsite> execute frappe.db.get_value --args "['Workspace', 'Payroll', 'is_hidden']"
```
Expected: sista kommandot skriver `1` (dold även efter migrate).

- [ ] **Step 6: Commit**

```bash
cd apps/hrms_sverige
git add hrms_sverige/setup/workspaces.py hrms_sverige/setup/install.py hrms_sverige/hooks.py hrms_sverige/tests/test_setup.py
git commit -m "feat: run Swedish HR setup on install and hide unused workspaces

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Svensk översättning av HRMS

**Files:**
- Create: `apps/hrms_sverige/hrms_sverige/scripts/__init__.py` (tom)
- Create: `apps/hrms_sverige/hrms_sverige/scripts/sarskrivningar.py`
- Create: `apps/hrms_sverige/hrms_sverige/locale/sv.po`
- Test: `apps/hrms_sverige/hrms_sverige/tests/test_translations.py`

**Interfaces:**
- Produces: `scripts.sarskrivningar.find_candidates(title_case_only: bool = False) -> list[dict]`,
  `scripts.sarskrivningar.find_conflicts() -> list[dict]`, `report(output=None, title_case_only=False)`.

**Ordlista (gäller alla översättningar i uppgiften, håll den konsekvent):**

| Engelska | Svenska |
|---|---|
| Leave (substantiv) | Frånvaro / ledighet (ansökan: "ledighet") |
| Leave Type | Frånvarotyp |
| Leave Allocation | Frånvarotilldelning |
| Leave Application | Ledighetsansökan |
| Leave Policy | Frånvaropolicy |
| Leave Policy Assignment | Koppling till frånvaropolicy |
| Leave Period | Frånvaroperiod |
| Leave Balance | Frånvarosaldo |
| Compensatory Leave Request | Ansökan om kompledighet |
| Compensatory Off | Kompledighet |
| Carry Forwarded Leaves | Sparade dagar |
| Holiday List / Holiday List Assignment | Helgdagslista / Koppling till helgdagslista |
| Attendance / Attendance Request | Närvaro / Närvarobegäran |
| Employee Checkin, Check In, Check Out | Stämpling, Stämpla in, Stämpla ut |
| Shift Type / Shift Assignment / Shift Request | Skifttyp / Skifttilldelning / Skiftbegäran |
| Employment Type | Anställningsform |
| Leave Approver | Ledighetsgodkännare |
| Half Day | Halvdag |
| Late Entry / Early Exit | Sen instämpling / Tidig utstämpling |

Regel: sammansatta ord skrivs ihop, bara första ordet har stor bokstav (utom egennamn), som i
`erpnext_sverige/locale/sv.po`.

- [ ] **Step 1: Skriv det fallerande testet**

`apps/hrms_sverige/hrms_sverige/tests/test_translations.py`:
```python
import frappe
from frappe.tests import UnitTestCase

from hrms_sverige.scripts.sarskrivningar import find_candidates, find_conflicts

IN_SCOPE = ("Leave", "Attendance", "Shift", "Check", "Holiday", "Compensatory", "Employment", "Half Day")


class TestTranslations(UnitTestCase):
	def test_glossary(self):
		previous = frappe.local.lang
		frappe.local.lang = "sv"
		try:
			self.assertEqual(frappe._("Leave Allocation"), "Frånvarotilldelning")
			self.assertEqual(frappe._("Shift Type"), "Skifttyp")
			self.assertEqual(frappe._("Employment Type"), "Anställningsform")
		finally:
			frappe.local.lang = previous

	def test_no_title_case_in_scope(self):
		left = [
			c["msgid"]
			for c in find_candidates(title_case_only=True)
			if any(word in c["msgid"] for word in IN_SCOPE)
		]
		self.assertEqual(left, [])

	def test_no_conflicts_with_erpnext_sverige(self):
		self.assertEqual(find_conflicts(), [])
```

- [ ] **Step 2: Skriv skriptet (anpassad kopia av erpnext_sverige:s)**

Kopiera `apps/erpnext_sverige/erpnext_sverige/scripts/sarskrivningar.py` till
`apps/hrms_sverige/hrms_sverige/scripts/sarskrivningar.py` och gör dessa ändringar:

1. Docstring: byt "frappe och erpnext" mot "hrms", "erpnext_sverige/locale/sv.po" mot
   "hrms_sverige/locale/sv.po" och `erpnext_sverige.scripts` mot `hrms_sverige.scripts` i exemplen.
2. `SOURCE_APPS = ("hrms",)` och lägg till `OVERRIDE_APP = "hrms_sverige"`.
3. Lägg till `"Frappe HR"` och `"HRMS"` i mängden `PROPER_NOUNS`.
4. I `find_candidates`: byt `frappe.get_app_path("erpnext_sverige", "locale", "sv.po")` mot
   `frappe.get_app_path(OVERRIDE_APP, "locale", "sv.po")`.
5. Lägg till efter `find_candidates`:
```python
def find_conflicts() -> list[dict]:
	"""Strängar där erpnext_sverige har en rättelse som hrms (installerad senare) skriver över
	och hrms_sverige inte återställer."""
	if "erpnext_sverige" not in frappe.get_installed_apps():
		return []
	ours = _load(frappe.get_app_path("erpnext_sverige", "locale", "sv.po"))
	hrms = _load(frappe.get_app_path("hrms", "locale", "sv.po"))
	override = _load(frappe.get_app_path(OVERRIDE_APP, "locale", "sv.po"))
	return [
		{"ctx": ctx, "msgid": msgid, "erpnext_sverige": text, "hrms": hrms[(ctx, msgid)]}
		for (ctx, msgid), text in sorted(ours.items())
		if (ctx, msgid) in hrms and hrms[(ctx, msgid)] != text and override.get((ctx, msgid)) != text
	]
```
6. I `report`, efter kandidatutskriften:
```python
	for c in find_conflicts():
		print(f"KONFLIKT {c['msgid']!r}: erpnext_sverige {c['erpnext_sverige']!r}, hrms {c['hrms']!r}")
```

- [ ] **Step 3: Skapa sv.po med rubrik och de två konflikterna**

`apps/hrms_sverige/hrms_sverige/locale/sv.po`:
```
# Swedish translations for HRMS Sverige.
# This file is distributed under the same license as the HRMS Sverige project.
#
msgid ""
msgstr ""
"Project-Id-Version: HRMS Sverige\n"
"Report-Msgid-Bugs-To: https://github.com/ubbe76/HRMS-Sverige/issues\n"
"Language: sv\n"
"MIME-Version: 1.0\n"
"Content-Type: text/plain; charset=utf-8\n"
"Content-Transfer-Encoding: 8bit\n"
"Plural-Forms: nplurals=2; plural=(n != 1);\n"

msgid "Advance Paid (Company Currency)"
msgstr "Förskott betalt (bolagsvaluta)"

msgid "Uploading..."
msgstr "Ladda upp..."
```
(Ta värdena från `bench --site <testsite> execute hrms_sverige.scripts.sarskrivningar.report` –
KONFLIKT-raderna – om fler har tillkommit.)

- [ ] **Step 4: Kör testet och se att ordlistetestet och scope-testet fallerar**

```bash
bench compile-po-to-mo --app hrms_sverige --locale sv --force
bench --site <testsite> clear-cache
bench --site <testsite> run-tests --app hrms_sverige --module hrms_sverige.tests.test_translations
```
Expected: `test_no_conflicts_with_erpnext_sverige` PASS; `test_glossary` och `test_no_title_case_in_scope` FAIL
(den senare listar strängarna som återstår).

- [ ] **Step 5: Ta fram arbetslistan**

```bash
bench --site <testsite> execute hrms_sverige.scripts.sarskrivningar.report --kwargs "{'output': '/tmp/hrms-sv.json', 'title_case_only': True}"
```
Expected: cirka 950 kandidater. Filtrera ut de vars `msgid` innehåller något ord i `IN_SCOPE` (se testet) – det
är obligatoriska. Övriga (lön, rekrytering, utlägg, medarbetarsamtal) är valfria i denna uppgift.

- [ ] **Step 6: Översätt de obligatoriska strängarna**

För varje obligatorisk kandidat, lägg till en post i `sv.po` enligt ordlistan och regeln ovan, i bokstavsordning
efter msgid, t.ex.:
```
msgid "Leave Allocation"
msgstr "Frånvarotilldelning"

msgid "Leave Application"
msgstr "Ledighetsansökan"

msgid "Shift Type"
msgstr "Skifttyp"

msgid "Employment Type"
msgstr "Anställningsform"

msgid "Compensatory Leave Request"
msgstr "Ansökan om kompledighet"

msgid "Attendance Date"
msgstr "Närvarodatum"

msgid "Half Day Date"
msgstr "Datum för halvdag"
```
Behåll platshållare (`{0}`, `%s`, HTML-taggar) exakt. Om en post har `msgctxt` i HRMS:s `sv.po` ska den med.
Arbeta i omgångar om ca 100 och kompilera + kör testet mellan omgångarna (steg 7).

- [ ] **Step 7: Kompilera och kör testerna**

```bash
bench compile-po-to-mo --app hrms_sverige --locale sv --force
bench --site <testsite> clear-cache
bench --site <testsite> run-tests --app hrms_sverige --module hrms_sverige.tests.test_translations
```
Expected: `OK`, 3 tester.

- [ ] **Step 8: Commit**

```bash
cd apps/hrms_sverige
git add hrms_sverige/scripts hrms_sverige/locale hrms_sverige/tests/test_translations.py
git commit -m "feat(sv): fix split compounds and title case in HRMS translations

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Dokumentation, manuell kontroll, utrullning och push

**Files:**
- Modify: `apps/hrms_sverige/README.md`
- Modify: `~/frappe-bench/CLAUDE.md` (ej versionshanterad)

- [ ] **Step 1: Kör hela testsviten**

```bash
bench --site <testsite> run-tests --app hrms_sverige
```
Expected: `OK`, alla tester (ca 34).

- [ ] **Step 2: Skriv README**

Ersätt innehållet i `apps/hrms_sverige/README.md` med:
````markdown
## HRMS Sverige

Svensk anpassning av Frappe HRMS: personalregister, frånvaro/ledighet och närvaro.

- Frånvarotyper: Semester (25 dagar/år, max 5 sparade dagar/år, förfaller efter 5 år), Sjukfrånvaro, VAB,
  Föräldraledighet, Tjänstledighet, Kompledighet.
- Helgdagslistor "Sverige ÅÅÅÅ" med röda dagar samt midsommar-, jul- och nyårsafton, kopplade till företaget
  från 1 januari.
- Anställd: personnummer (bara HR-roller), anställningsform, arbetsdagar per vecka, sysselsättningsgrad.
- Semester vid deltid: 25 × arbetsdagar/5, avrundat uppåt, när tilldelningen skapas från frånvaropolicyn.
- Lön, rekrytering, utlägg och medarbetarsamtal är dolda.

### Installation

```bash
bench get-app hrms --branch version-16
bench get-app https://github.com/ubbe76/HRMS-Sverige --branch version-16
bench --site <site> install-app hrms
bench --site <site> install-app hrms_sverige
```

### Varje år

```bash
# Nästa års helgdagslista och frånvaroperiod
bench --site <site> execute hrms_sverige.setup.install.setup_all
```
Skapa sedan årets semestertilldelning: Frånvaropolicy "Semester 25 dagar" → massfunktionen för koppling till
frånvaropolicy, välj frånvaroperioden för året.

Ändras en anställds arbetsdagar per vecka mitt i året räknas redan skapade tilldelningar inte om – justera
tilldelningen för hand.

### Översättning

Efter uppgradering av HRMS:
```bash
bench --site <site> execute hrms_sverige.scripts.sarskrivningar.report --kwargs "{'title_case_only': True}"
bench compile-po-to-mo --app hrms_sverige --locale sv --force
```

### License

gpl-3.0
````

- [ ] **Step 3: Bygg och manuell genomgång på testsajten**

```bash
bench build --app hrms
bench build --app hrms_sverige
bench --site <testsite> clear-cache
bench --site <testsite> serve --port 8001
```
Logga in som Administrator/admin på `http://localhost:8001`, språk svenska, och kontrollera:
1. Skapa en anställd i testsajtens företag med personnummer `811218-9876`, anställningsform Tillsvidare,
   3 arbetsdagar/vecka → sparas som `19811218-9876`.
2. Koppla den anställde till frånvaropolicyn "Semester 25 dagar" för innevarande år → tilldelning 15 dagar
   (proportionellt om anställningsdatum är i år).
3. Ansök om semester över en vecka med en helgdag → helgdagen dras inte.
4. Registrera en stämpling (Stämpling) och se den i listan.
5. Sidomenyn visar inte Lön, Rekrytering, Utlägg, Medarbetarsamtal.
Stoppa servern (Ctrl-C) när du är klar.

- [ ] **Step 4: Commit och push**

```bash
cd apps/hrms_sverige
git add README.md
git commit -m "docs: describe installation and yearly routine

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git remote add origin https://github.com/ubbe76/HRMS-Sverige.git
git push -u origin version-16
```
**Fråga användaren innan push.** Expected: grenen `version-16` finns på GitHub.

- [ ] **Step 5: Säkerhetskopia av produktionssajten**

**Fråga användaren innan steg 5–6.**
```bash
bench --site <site> backup --with-files
```
Expected: sökvägar till databas- och fildump under `sites/<site>/private/backups/`. Notera dem.

- [ ] **Step 6: Installera på <site>**

```bash
bench --site <site> install-app hrms
bench --site <site> execute frappe.db.get_value --args "['Custom Field', {'dt': 'Employee', 'fieldname': 'employment_type'}, 'name']"
bench --site <site> install-app hrms_sverige
bench --site <site> clear-cache
```
Expected: båda installationerna utan traceback, mellankommandot skriver `"Employee-employment_type"`.
Vid fel: `bench --site <site> restore <databasdump> --with-public-files <...> --with-private-files <...>`
med filerna från steg 5.

- [ ] **Step 7: Uppdatera CLAUDE.md i bench-roten**

I `~/frappe-bench/CLAUDE.md`, lägg till i apptabellen:
```
| `hrms` | 16.x | `github.com/frappe/hrms` | Upstream HR, don't edit — override from `hrms_sverige` |
| `hrms_sverige` | 0.0.1 | `github.com/ubbe76/HRMS-Sverige` (GPL-3.0) | Our app: Swedish HR localization |
```
(ersätt `16.x` med versionen från `bench version`) och ett avsnitt `## hrms_sverige (our app)` med: kräver `hrms`;
`setup_all` körs vid installation och varje år; `sv.po`-rutinen som för `erpnext_sverige` men med
`--app hrms_sverige`; tester på `<testsite>`.
