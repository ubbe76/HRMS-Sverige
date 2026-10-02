# HRMS Sverige – design

## Bakgrund

Vi behöver HR-stöd i ERPNext: personalregister, frånvaro/ledighet och närvaro. Frappe HRMS
(`github.com/frappe/hrms`, gren `version-16`, kräver frappe och erpnext `>=16,<17`) täcker detta men saknar svensk
anpassning. HRMS har regionala anpassningar bara för Indien och Förenade Arabemiraten. Dess `sv.po` är nästan
komplett men har samma särskrivningar och versaler mitt i orden som ERPNext hade ("Frånvaro Tilldelning",
"Skift Typ", "Frånvaro Princip").

Anpassningen görs i en ny app, `hrms_sverige` (repo `github.com/ubbe76/HRMS-Sverige`, GPL-3.0, gren `version-16`),
som kräver `hrms`. `erpnext_sverige` kräver fortsatt bara `erpnext`, så den som bara vill ha ekonomidelen slipper
installera HRMS.

## Mål

- HRMS installerat och användbart på svenska för **personalregister**, **frånvaro/ledighet** och **närvaro/tid**.
- Svenska frånvarotyper, svenska helgdagslistor och svensk semesterhantering (25 dagar per kalenderår).
- Svenska uppgifter om den anställde: personnummer, anställningsform, arbetsdagar per vecka och sysselsättningsgrad.
- Moduler vi inte använder döljs, så att menyerna blir enklare.

**Utanför:** lön och lönekörning, skatteavdrag, arbetsgivaravgifter, AGI, rekrytering, on-/offboarding, utlägg och
reseräkningar, medarbetarsamtal, kollektivavtal och facklig tillhörighet (känslig personuppgift, registreras inte).

## Semestermodell

Förenklad modell: **25 dagar per kalenderår och ett saldo per anställd**. Varken förskjutet semesterår eller
intjänande enligt semesterlagen används.

### Årlig tilldelning (HRMS standardflöde)

- Uppsättningen skapar en **ledighetsperiod** (Leave Period) per kalenderår, 1 januari–31 december, och en
  **ledighetspolicy** (Leave Policy) "Semester 25 dagar" med 25 dagar av frånvarotypen Semester.
- Varje anställd kopplas till policyn (Leave Policy Assignment). HR skapar varje år tilldelningen för alla
  anställda på en gång med HRMS massfunktion.
- Nyanställda under året får en proportionell andel utifrån anställningsdatum. HRMS räknar redan ut det
  (`calculate_pro_rated_leaves`).

### Deltid

Enligt semesterlagen har även den som arbetar deltid 25 semesterdagar, men om man arbetar färre dagar per vecka
räknas dagarna om till uttagsdagar.

- Egna fältet **Arbetsdagar per vecka** (heltal 1–5, tomt räknas som 5) styr omräkningen.
- När en frånvarotilldelning (Leave Allocation) av typen Semester skapas **från en policykoppling**
  (`leave_policy_assignment` är satt) räknas `new_leaves_allocated` om till
  `ceil(new_leaves_allocated × arbetsdagar / 5)`, alltså avrundat uppåt till hela dagar. Omräkningen görs
  efter HRMS proportionella beräkning.
  - Exempel: 5 dagar ger 25, 4 dagar ger 20 och 3 dagar ger 15. Deltid 3 dagar med start 1 juli ger
    ceil(12,5 × 3/5) = 8.
- Tilldelningar som läggs in för hand räknas inte om. HR bestämmer då antalet själv.
- Om arbetsdagarna ändras mitt i året räknas befintliga tilldelningar inte om. HR justerar för hand, och det
  står i README.
- **Sysselsättningsgrad** (procent) är bara information och påverkar ingen beräkning.

### Sparade dagar

Frånvarotypen Semester får föras över till nästa år (`is_carry_forward`), med högst 5 dagar per år
(`maximum_carry_forwarded_leaves = 5`). Det motsvarar lagens regel om att dagar utöver 20 får sparas. Överförda
dagar förfaller efter 5 år (`expire_carry_forwarded_leaves_after_days = 1826`).

## Innehåll

### Frånvarotyper (Leave Type)

| Namn | Inställning | Kommentar |
|---|---|---|
| Semester | tilldelas via policy, carry forward enligt ovan, `include_holiday = 0` | helgdagar räknas inte som semesterdagar |
| Sjukfrånvaro | `is_lwp = 1` | ingen tilldelning krävs, registreras bara |
| VAB | `is_lwp = 1` | som ovan |
| Föräldraledighet | `is_lwp = 1` | som ovan |
| Tjänstledighet | `is_lwp = 1` | obetald ledighet |
| Kompledighet | `is_compensatory = 1` | saldo byggs upp via ansökan om kompledighet (Compensatory Leave Request) |

`is_lwp` ("leave without pay") används för att ansökan ska kunna skickas utan tilldelning. HRMS hoppar då
över saldokontrollen. Utan lönemodul påverkar flaggan inget annat. Om lön införs senare måste Sjukfrånvaro, VAB
och Föräldraledighet ses över.

### Helgdagslistor (Holiday List)

En funktion räknar ut svenska helgdagar för ett givet år och skapar eller uppdaterar helgdagslistan
"Sverige ÅÅÅÅ" (1 januari–31 december) med lördagar och söndagar som veckovila:

- **Röda dagar:** nyårsdagen, trettondedag jul, långfredagen, påskdagen, annandag påsk, första maj,
  Kristi himmelsfärdsdag (påsk + 39), nationaldagen (6 juni), pingstdagen (påsk + 49), midsommardagen (lördag
  20–26 juni), alla helgons dag (lördag 31 oktober–6 november), juldagen och annandag jul.
- **Aftnar som i praktiken är lediga:** midsommarafton, julafton och nyårsafton. Med parametern `aftnar`
  (standard `True`) går det att välja om de ska tas med.
- Påsk räknas ut med den gregorianska påskformeln (Meeus/Jones/Butcher).
- Kommandot `bench --site <site> execute hrms_sverige.setup.holidays.create_holiday_list --kwargs "{'year': 2027}"`
  skapar nästa års lista.
- Vid installationen skapas listor för innevarande och nästa år. Listan sätts som företagets
  standardhelgdagslista om ingen finns.

### Anställd (Employee)

| Fält | Typ | Kommentar |
|---|---|---|
| Personnummer (`personnummer`) | Data, eget fält, `permlevel = 1` | 10 eller 12 siffror, med eller utan bindestreck, kontrollsiffran kontrolleras (Luhn). Samordningsnummer (dag + 60) godkänns. Lagras normaliserat som `ÅÅÅÅMMDD-NNNN`. Bara rollerna HR Manager och HR User får läsa och skriva på permlevel 1. |
| Anställningsform | befintligt `employment_type` (Link → Employment Type) | uppsättningen skapar Tillsvidare, Provanställning, Allmän visstid, Vikariat och Säsongsanställning |
| Slutdatum för visstid | befintligt `contract_end_date` | återanvänds |
| Arbetsdagar per vecka (`arbetsdagar_per_vecka`) | Int, eget fält, 1–5 | tomt räknas som 5 |
| Sysselsättningsgrad (`sysselsattningsgrad`) | Percent, eget fält, 0–100 | bara information |
| Anhörig | befintliga `person_to_be_contacted`, `relation` och `emergency_phone_number` | översätts bara |

Egna fält och permlevel-behörigheter levereras som fixtures (Custom Field, Custom DocPerm).

### Översättning

- `hrms_sverige/locale/sv.po` rättar HRMS-texter, till exempel "Frånvarotilldelning", "Skifttyp",
  "Ledighetsansökan", "Frånvaropolicy" och "Kompledighet".
- Samma princip som i `erpnext_sverige`: upstream-filen `sv.po` ändras aldrig, och appar som installeras senare
  vinner. `hrms_sverige` installeras efter `hrms`.
- `hrms_sverige/scripts/sarskrivningar.py` är en anpassad kopia av skriptet i `erpnext_sverige`. Den läser
  `hrms` plus `hrms_sverige` och listar kvarvarande särskrivningar efter uppgraderingar.

### Förenklade menyer

Arbetsytorna (Workspace) för Payroll, Tax & Benefits, Recruitment, Expenses, Performance och Tenure döljs. Leaves,
Shift & Attendance och HR Setup ligger kvar. Det görs vid installationen och går att köra om. Modulerna avinstalleras
inte, så de kan slås på igen senare.

## Struktur

```
hrms_sverige/
  hooks.py                 required_apps = ["hrms"], after_install, fixtures, doc_events
  setup/
    install.py             after_install → setup_all(); samlar stegen nedan och kan köras om
    leave.py               frånvarotyper, ledighetsperiod, ledighetspolicy
    holidays.py            svenska_helgdagar(year, aftnar) och create_holiday_list(year, company)
    employment_types.py    anställningsformer
    workspaces.py          döljer arbetsytor
  hr/
    personnummer.py        normalize(), validate() (Luhn, samordningsnummer); anropas från Employee.validate
    leave_allocation.py    deltidsomräkning; hookas på Leave Allocation before_insert
  fixtures/                custom_field.json, custom_docperm.json
  locale/sv.po
  scripts/sarskrivningar.py
  tests/
```

Alla uppsättningssteg är **idempotenta**: de skapar det som saknas och uppdaterar det som finns, utan dubbletter.
Företag anges som parameter eller hämtas från standardföretaget. Inga företagsnamn finns i koden.

## Tester

Körs med `bench --site <testsite> run-tests --app hrms_sverige`.

- **Personnummer:** giltiga 10- och 12-siffriga nummer med och utan bindestreck samt samordningsnummer godkänns
  och normaliseras. Fel kontrollsiffra, ogiltigt datum och fel längd avvisas.
- **Helgdagar:** påsk, midsommar och alla helgons dag stäms av mot kända datum för 2025–2028. Aftnarna följer med
  eller utesluts beroende på `aftnar`.
- **Deltidssemester:** 5, 4 och 3 dagar ger 25, 20 och 15. Tomt fält ger 25. Brutna dagar avrundas uppåt.
  Manuella tilldelningar räknas inte om.
- **Idempotens:** om `setup_all()` körs två gånger blir det inga dubbletter.
- **Behörighet:** en användare utan HR-roll får inte läsa personnumret.

## Utrullning

1. `bench get-app hrms --branch version-16` och `bench --site <testsite> install-app hrms`. Kontrollera att
   installationen körs klart, eftersom ERPNext avbröts förra gången.
2. Installera `hrms_sverige` på `<testsite>` och kör testerna. Klicka igenom flödet på port 8001: lägg upp en
   anställd, skapa semestertilldelning, ansök om ledighet och stämpla in.
3. `bench build --app hrms` och `--app hrms_sverige`, `bench compile-po-to-mo --app hrms_sverige --locale sv --force`
   och clear-cache.
4. Ta en säkerhetskopia av `<site>` med `bench --site <site> backup --with-files`.
5. Installera `hrms` och `hrms_sverige` på `<site>`.
6. Uppdatera `CLAUDE.md` i bench-roten med de nya apparna.

**Återställning:** återställ säkerhetskopian från steg 4. Att avinstallera appen räcker inte, eftersom HRMS
lägger till fält i ERPNext-doctypes.
