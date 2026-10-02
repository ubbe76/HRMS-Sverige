# Löneunderlag till Crona Lön (PAXml), del C2: övertid, mertid och OB – design

## Bakgrund

Del A gav dokumentet **Löneunderlag**: månadens godkända frånvaro som en PAXml 2.0-fil till Crona Lön (PR #12).
Del B lade till arbetad tid (ARB) och frånvaro i timmar för timavlönade (PR #13).

Del C delas i två delprojekt:

- **C1. Stämplingssida:** en egen sida för in- och utstämpling. Vid en utstämpling utanför skiftet väljer den
  anställde om övertiden ska ersättas med pengar eller komptid. C1 får en egen spec efter C2.
- **C2. Övertid, mertid och OB (den här specen):** regler, beräkning och rader i löneunderlaget. C2 läser valet från
  C1. Tills C1 finns gäller ett förval per anställd, och HR kan ändra koden per rad.

## Mål

- Alla som stämplar, både tim- och månadsavlönade, får **MER**, **ÖT1–ÖT5** eller **ÖK1–ÖK5** och **OB1–OB5** i timmar
  per dag i samma löneunderlag och fil.
- Reglerna läggs in i ERPNext, så att lösningen fungerar oavsett kollektivavtal.
- Samma timme betalas aldrig två gånger. Timavlönades ARB minskas med de timmar som skickas som MER eller ÖT/ÖK.
- HR granskar övertiden i löneunderlaget och kan ändra koden eller ta bort raden innan godkännandet.

**Utanför C2:**

- stämplingssidan (C1);
- övertid per vecka;
- jour, beredskap och restid;
- förinlagda kollektivavtal.

## Fakta om formatet

Enligt PAXml 2.0 är MER, ÖT1–ÖT5, ÖK1–ÖK5 och OB1–OB5 tillåtna tidkoder. ÖT och ÖK är "Övertid N – Betalning"
och "Övertid N – Komptid". Timmar anges per enskilt datum, som för ARB i del B. Det är lönesystemet som gör om
koderna till lönearter och belopp.

## Innehåll

### Inställningar: Löneinställningar

Nytt Single-dokument **Löneinställningar** (`Loneinstallningar`) i modulen Lon:

- **Heltid per dag (timmar)** (`heltid_per_dag`, Float, standard 8). Mertidstaket per dag.
- **Tidsregler** (`tidsregler`, tabell `Tidsregel`). Varje rad har:
  - **Typ** (`typ`, Select: `OB`, `Övertid`);
  - **Nivå** (`niva`, Int 1–5);
  - **Dagar**: kryssrutor `man`, `tis`, `ons`, `tor`, `fre`, `lor`, `son` och `helgdag`;
  - **Från** och **Till** (`fran`, `till`, Time). Om Till är lika med eller före Från går perioden över midnatt
    till nästa dag. Från = Till betyder hela dygnet.

En regel gäller en dag om dagens veckodag är ikryssad, eller om dagen är en **helgdag** och `helgdag` är ikryssad.
Helgdag betyder här en helgdag i den anställdes helglista som inte är en vanlig veckoledighet (`weekly_off = 0`), till
exempel juldagen. En regel som går över midnatt hör till dagen den börjar.

Exempel: OB nivå 1 mån–fre 18–22, OB nivå 2 alla dagar 22–06, OB nivå 3 lör, sön och helgdag 00–00, Övertid nivå 1
mån–fre 06–20 och Övertid nivå 2 alla dagar 20–06.

### Övertidsval

- **Employee:** nytt fält **Övertid som** (`overtid_som`, Select: `Pengar`, `Komptid`, standard `Pengar`).
- **Employee Checkin:** nytt fält **Övertidsersättning** (`overtidsersattning`, Select: tomt, `Pengar`, `Komptid`).
  C1 fyller i det vid utstämpling.
- För en närvaro gäller valet på den senaste utstämplingen (`log_type = "OUT"`) som är kopplad till närvaron.
  Är det tomt, gäller den anställdes **Övertid som**.

### Planerat skift med klockslag

`tid.py` får `planerat_skift(employee, datum) -> tuple[datetime, datetime] | None`. Den ger skiftets start och slut
på datumet, med samma val av skift som `planerade_timmar`: aktiv tilldelning, annars standardskift, ingenting på
helgdagar. Slutet ligger nästa dag om skiftet går över midnatt. `planerade_timmar` räknas från den.

### Beräkning per närvaro

Gäller godkänd närvaro (`docstatus = 1`) med status Present eller Half Day och både `in_time` och `out_time`, i
bolaget och månaden, för alla anställda.

1. **Arbetad tid** = intervallet [in_time, out_time].
2. **Extra tid** = de delar av den arbetade tiden som ligger utanför det planerade skiftet. Finns inget planerat skift
   (inklusive helgdag) blir det ingen extra tid, bara OB.
3. **Mertid:** för deltidsanställda (`sysselsattningsgrad` under 100) blir extra tid MER, tills dagens arbetade timmar
   når `heltid_per_dag`. Resten blir övertid. Mertiden tas från den tidigaste extra tiden. Heltidsanställda (100 % eller
   tomt) får ingen mertid.
4. **Övertid:** övertidsintervallen delas mot övertidsreglerna. Varje del får nivån från regeln som täcker tiden.
   Tid som ingen regel täcker får nivå 1. Täcker flera regler samma tid gäller den högsta nivån. Koden blir `ÖT<nivå>`
   vid Pengar och `ÖK<nivå>` vid Komptid.
5. **OB:** hela den arbetade tiden delas mot OB-reglerna. Varje del får `OB<nivå>`. Där flera OB-regler överlappar
   gäller den högsta nivån, så att samma tid inte räknas två gånger.

Resultatet blir en rad per kod och närvaro, med timmar avrundade till två decimaler och länk till närvaron. Rader med
0 timmar tas inte med. Dagen på raden är närvarons `attendance_date`.

### ARB för timavlönade

`arbetad_tid` minskar ARB för en närvaro med summan av MER-, ÖT- och ÖK-timmarna för samma närvaro. OB minskar inte
ARB, eftersom OB är ett tillägg. Blir ARB 0 eller mindre tas raden inte med. Månadsavlönade får som förut ingen ARB.

### Löneunderlaget

- Hämtningen tar även med tilläggsraderna.
- Tidkoden på rader utan frånvarotyp får ändras. `uppdatera_rader` behåller den, normaliserad till versaler. HR kan
  ändra ÖT↔ÖK, nivån eller ta bort raden. Okända koder stoppas redan av del A:s kontroll mot `TIDKODER`.
- Vid godkännandet visas en varning, inte ett stopp, om det finns närvaro i månaden med arbetade timmar men utan
  in- eller utstämplingstid. Där beräknas varken övertid eller OB. Varningen listar anställda och datum.

## Struktur

- `lon/regler.py` (ny, utan databas):
  - dataklass `Tidsregel(typ, niva, dagar: frozenset[int], helgdag: bool, fran: time, till: time)`;
  - `regelintervall(regel, dag: date, ar_helgdag: bool) -> list[tuple[datetime, datetime]]`;
  - `fordela(intervall, regler, helgdagar: set[date]) -> dict[int, float]` ger timmar per nivå, med högsta nivån där
    regler överlappar och nivå 1 för täckning saknas när det gäller övertid;
  - `extra_tid(arbetat, skift) -> list[tuple[datetime, datetime]]`;
  - `dela_mertid(extra, redan_arbetat_timmar, tak_timmar) -> (mertid, overtid)`.
- `lon/tillagg.py` (ny):
  - `regler_fran_installningar() -> list[Tidsregel]`;
  - `tillaggsrader(company, from_date, to_date) -> list[dict]`;
  - `narvaro_utan_klockslag(company, from_date, to_date) -> dict[str, list[date]]`.
- `lon/doctype/loneinstallningar/` och `lon/doctype/tidsregel/` (nya).
- `lon/tid.py`: `planerat_skift`. `arbetad_tid` tar ett valfritt avdrag per närvaro.
- `lon/franvaro.py`: `rader_for_period` tar med tilläggsraderna och skickar avdraget till `arbetad_tid`.
- `lon/doctype/loneunderlag_rad`: `tidkod` är inte längre skrivskyddad. Den skrivs ändå över från frånvarotypen på
  frånvarorader.
- `lon/doctype/loneunderlag`: varningen vid godkännande.
- `setup/custom_fields.py`: `overtid_som` (Employee) och `overtidsersattning` (Employee Checkin).

## Tester

Skrivs före koden (TDD) och körs på `<testsite>` och i CI.

- **regler.py:**
  - period över midnatt;
  - Från = Till betyder hela dygnet;
  - helgdag kontra helg;
  - överlappande OB-regler ger högsta nivån;
  - övertid över två nivåer;
  - övertid utan täckande regel ger nivå 1;
  - extra tid före och efter skiftet;
  - mertid upp till heltid och resten övertid;
  - ingen mertid för heltid.
- **tillagg.py:**
  - ÖK när utstämplingen säger Komptid;
  - ÖT vid Pengar eller förval;
  - OB för en månadsavlönad, utan ARB;
  - ingen extra tid utan skift;
  - närvaro utan klockslag ger inga tillägg men listas.
- **ARB:** minskas med MER och ÖT/ÖK men inte med OB. Del B:s tester utan övertid ger oförändrad ARB.
- **Löneunderlag:**
  - hämta ger tilläggsrader;
  - HR ändrar ÖT1 till ÖK1 och filen får ÖK1;
  - varning för närvaro utan klockslag;
  - filen med MER/ÖT/ÖK/OB validerar mot schemat.
- Del A:s och del B:s tester går igenom.

## Dokumentation

Nytt avsnitt "Övertid, mertid och OB" på manualsidan "Löneunderlag till Crona". Det tar upp:

- hur tidsreglerna läggs in, med exemplet ovan;
- Övertid som och Övertidsersättning;
- att MER- och ÖT-lönearterna i Crona ska omfatta hela timlönen plus tillägget, eftersom ARB minskas;
- att OB är ett rent tillägg;
- kopplingen av koderna i Löneartsstyrning.

README och CHANGELOG uppdateras.

## Utrullning

Utrullningen görs tillsammans med del A och B, efter provimporten i Crona:

1. PR i HRMS-Sverige. CI ska gå igenom.
2. `clear-cache` och `migrate` på <testsite> och <demosite>. Provkörning med tidsregler och en anställd med
   övertid och OB.
3. Provimport i Crona (användaren).
4. `clear-cache` och `migrate` på <site>.
