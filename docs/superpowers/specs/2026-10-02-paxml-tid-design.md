# Löneunderlag till Crona Lön (PAXml), del B: arbetad tid – design

## Bakgrund

Del A (`2026-10-02-paxml-crona-design.md`, PR #12) gav dokumentet **Löneunderlag**. Det samlar en månads godkända
frånvaro och laddar ner den som PAXml 2.0-fil till Crona Lön. Frånvaron skickas där som omfattning i procent av
Cronas schema.

Del B lägger till **arbetad tid för timavlönade**. Tiden kommer från in- och utstämpling (Employee Checkin) mot skift,
via den närvaro (Attendance) som HRMS räknar fram per dag. Del C (övertid, mertid och OB) kommer senare och omfattas
inte här.

## Mål

- Timavlönade får sina arbetade timmar per dag som tidkod **ARB** i samma löneunderlag och fil som frånvaron.
- Timavlönades frånvaro skickas som timmar per dag med planerat skift, eftersom de normalt saknar schema i Crona.
- Månadsavlönade påverkas inte. Deras ordinarie tid skickas inte, eftersom Crona har deras schema. Planday:s guide
  för Crona utesluter TID av samma skäl: annars blir det dubbla timmar i kalendariet.
- Stämplingar som inte blivit närvaro stoppar godkännandet, så att ingen får för lite lön.

**Utanför del B:** övertid, mertid och OB (del C). Inga rastavdrag utöver det som HRMS närvaroberäkning redan gör.

## Fakta om formatet

Enligt PAXml 2.0 (teknisk beskrivning och `paxml.xsd`):

- `<timmar>` (decimal) får bara anges på ett enskilt datum, inte med datumintervall.
- `<timmar>` och `<omfattning>` får inte anges tillsammans.
- Närvaro anges alltid i timmar.
- ARB betyder "Timlön (arbetstid utanför schema/timanställd)" och är en tillåten tidkod.

## Innehåll

### Löneform på den anställde (Employee)

Nytt fält **Löneform** (`loneform`, Select: `Månadslön`, `Timlön`), placerat efter `sysselsattningsgrad`. Tomt
räknas som Månadslön, så befintliga anställda påverkas inte.

### Rader i löneunderlaget

`Loneunderlag Rad` får två nya fält och en ändring:

- **Timmar** (`timmar`, Float, två decimaler): används i stället för omfattning.
- **Närvaro** (`attendance`, Link till Attendance, skrivskyddad): närvaron som ARB-raden kommer från.
- **Omfattning** (`omfattning`) är inte längre obligatorisk.

En rad har antingen omfattning eller timmar.

### Hämta frånvaro och tid

Knappen heter **Hämta frånvaro och tid**. Dokumentmetoden `hamta_franvaro` behåller sitt namn. Raderna ersätts med:

1. **Månadsavlönades frånvaro:** som i del A, ett datumintervall med omfattning 100 eller 50.
2. **Timavlönades frånvaro:** en rad per dag i ledigheten som ligger inom månaden, har ett planerat skift och inte
   är en helgdag för den anställde. Timmar = skiftets längd, eller hälften på en halvdag. Raden länkar till
   ledighetsansökan.
3. **Timavlönades arbetade tid:** en ARB-rad per godkänd närvaro (`docstatus = 1`) i bolaget och månaden med status
   Present eller Half Day och arbetade timmar över 0. Timmar = närvarons `working_hours`, avrundat till två
   decimaler. Raden länkar till närvaron.

En dag kan ha både en ARB-rad och en frånvarorad, till exempel sjuk halva passet. Crona räknar ihop dem.

Raderna sorteras på anställningsnummer, anställd och från-datum. Samma dag kommer frånvaro före arbetad tid.

### Planerat skift

`planerade_timmar(employee, datum)`:

- Är datumet en helgdag för den anställde (ERPNext `is_holiday`) blir det 0.
- Annars används skifttypen från den aktiva, godkända skifttilldelning (Shift Assignment, `docstatus = 1`,
  `status = "Active"`) som täcker datumet. `start_date <= datum` och `end_date` tom eller `>= datum`. Finns ingen,
  används den anställdes standardskift (`default_shift`).
- Skiftets längd = sluttid minus starttid. Är sluttiden före eller lika med starttiden går skiftet över midnatt, och
  24 timmar läggs till. Finns inget skift blir det 0.

### Kontroller vid godkännande

Utöver del A:s kontroller stoppas godkännandet om:

- En timavlönad anställd har stämplingar i månaden som saknar närvaro (`attendance` tom och
  `skip_auto_attendance = 0`). Meddelandet listar anställda och datum.
- En rad har både omfattning och timmar, eller ingen av dem.
- En timmarrad omfattar mer än en dag.
- Timmar är 0 eller mindre, eller över 24.

Omfattningskontrollen från del A (över 0 och högst 100) gäller bara rader med omfattning.

### Makulering av närvaro i exporterad period

En närvaro som ingår i ett godkänt löneunderlag ska kunna makuleras. Det ger en varning i stället för att stoppas av
Frappe:s länkkontroll, på samma sätt som för ledighetsansökningar i del A (`before_cancel` sätter
`ignore_linked_doctypes`, `on_cancel` varnar).

### PAXml-filen

`Tidtransaktion` får `timmar: float | None` och `omfattning: float | None`. En rad med timmar skrivs alltid med
`<datum>` och `<timmar>`:

```xml
<tidtrans anstid="2001" postid="9">
  <tidkod>ARB</tidkod>
  <datum>2026-09-14</datum>
  <timmar>7.87</timmar>
</tidtrans>
```

Rader med omfattning skrivs som i del A.

## Struktur

- `lon/tid.py` (ny): `planerade_timmar(employee, datum) -> float`,
  `arbetad_tid(company, from_date, to_date) -> list[dict]` och
  `stamplingar_utan_narvaro(company, from_date, to_date) -> dict[str, list[date]]`. De två sista gäller bara
  timavlönade.
- `lon/franvaro.py`:
  - Timavlönades frånvaro delas per dag med `planerade_timmar`.
  - `rader_for_period` lägger även till `arbetad_tid`.
  - En `before_cancel`- och `on_cancel`-hook för Attendance, motsvarande den för ledighetsansökningar.
- `lon/paxml.py`: `timmar` i `Tidtransaktion` och i XML-utskriften.
- `lon/doctype/loneunderlag*`:
  - Nya fält på raden.
  - Kontrollerna ovan.
  - Knapptexten ändras.
- `setup/custom_fields.py`: fältet `loneform`.
- `hooks.py`: Attendance `before_cancel` och `on_cancel`.

## Tester

Skrivs före koden (TDD) och körs på `<testsite>` och i CI.

- **planerade_timmar:**
  - dagskift;
  - nattskift över midnatt;
  - helgdag;
  - inget skift;
  - avslutad och inaktiv skifttilldelning;
  - standardskift.
- **arbetad_tid:**
  - bara timavlönade;
  - bara godkänd närvaro med Present eller Half Day;
  - ingen rad vid 0 timmar;
  - annat bolag ingår inte;
  - timmar avrundas till två decimaler.
- **Timavlönades frånvaro:**
  - en rad per skiftdag;
  - dagar utan skift och helgdagar utesluts;
  - halvdag ger halva skiftet;
  - månadsskifte.
- **Månadsavlönade:** samma rader som i del A. Del A:s tester ska fortsätta gå igenom oförändrade.
- **Stopp:**
  - stämplingar utan närvaro;
  - både timmar och omfattning;
  - timmarrad över flera dagar;
  - timmar 0 och över 24.
- **paxml:**
  - fil med timmarrader validerar mot schemat;
  - en timmarrad skrivs aldrig som intervall.
- **Makulering av närvaro i exporterad period:** tillåts med varning.

## Dokumentation

Manualsidan "Löneunderlag till Crona" får ett avsnitt om timavlönade. Där står att löneformen sätts till Timlön, att
ARB kopplas till en löneart för timavlönade i Löneartsstyrning, och att frånvaron skickas i timmar utan krav på
schema i Crona. Avsnittet beskriver även kravet på skift och stämplingar och vad som stoppar godkännandet. README och
CHANGELOG uppdateras.

## Utrullning

Utrullningen görs tillsammans med del A, efter provimporten i Crona:

1. PR i HRMS-Sverige. CI ska gå igenom.
2. `clear-cache` och `migrate` på <testsite> och <demosite>. Provkörning med en timavlönad testanställd.
3. Provimport i Crona (användaren).
4. `clear-cache` och `migrate` på <site>. Kontrollera att tabellerna och fälten finns.
