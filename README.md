<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset=".github/images/hrms-sverige-dark.svg">
    <img alt="HRMS Sverige" src=".github/images/hrms-sverige.svg" width="420">
  </picture>
</p>

## HRMS Sverige

Svensk anpassning av Frappe HRMS: personalregister, frånvaro/ledighet och närvaro.

- Frånvarotyper: Semester (25 dagar/år, max 5 sparade dagar/år, förfaller efter 5 år), Sjukfrånvaro, VAB,
  Föräldraledighet, Tjänstledighet, Kompledighet, Arbetstidskonto.
  HRMS engelska standardtyper (Casual Leave, Sick Leave m.fl.) tas bort om de inte används.
- Helglistor "Sverige ÅÅÅÅ" med röda dagar samt midsommar-, jul- och nyårsafton, kopplade till företaget
  från 1 januari.
- Anställd: personnummer (bara HR-roller, unikt, tål tankstreck och mellanslag), anställningsform, arbetsdagar per
  vecka, sysselsättningsgrad (0–100 %).
- Semester vid deltid: 25 × arbetsdagar/5, avrundat uppåt, när tilldelningen skapas från frånvaropolicyn.
  Taket för sparade dagar räknas om på samma sätt (3 dagar/vecka → högst 3 sparade dagar).
- Lön, rekrytering, utlägg och medarbetarsamtal är dolda.
- Rättade svenska översättningar för frånvaro, närvaro och skift.
- Löneunderlag till lönesystemet: dokumentet **Löneunderlag** samlar månadens godkända frånvaro och, för
  timavlönade, arbetad tid från stämpling och närvaro, och laddar ner det som PAXml 2.0-fil, byggd för Crona Lön.
  Frånvarotypens **PAXml-tidkod** (SEM, SJK, VAB, FPE, TJL, KOM, ATK) och ARB kopplas till lönearter i lönesystemet.
  **Löneform** på den anställde (Månadslön/Timlön) styr om tid och frånvaro skickas i procent eller timmar.
  Anställningsnumret måste vara samma som i lönesystemet. Fältet **Anställningsnummer** visas alltid; HRMS döljer
  det annars när anställda namnges med nummerserie. Sätt gärna **HR-inställningar > Namngivning av anställd efter**
  till *Employee Number*, så blir numret den anställdes ID. Vid bytet fyller HRMS i ID:t (HR-EMP-…) som nummer på
  anställda som saknar ett; ändra dem till numret i lönesystemet.
- Övertid, mertid och OB: egna tidsregler i **Löneinställningar** (veckodagar, helgdagar och klockslag per nivå).
  Närvarons in- och utstämplingstid jämförs med planerat skift och ger MER, ÖT1–ÖT5 eller ÖK1–ÖK5 och OB1–OB5 i
  löneunderlaget. Ett pass på en helg eller röd dag är övertid för den som har ett skift. Valet pengar eller
  komptid tas från utstämplingen eller den anställdes förval.
- Obetalda raster: tabellen **Obetalda raster** på skifttypen (börjar, minuter). Rasterna dras av från planerade
  timmar, arbetad tid (ARB), mertid, övertid och OB. En rast som den anställde stämplar ut på dras inte två gånger.
- Heltid per veckodag i **Löneinställningar**: gränsen för mertid en dag som skiljer sig från *Heltid per dag*,
  t.ex. en kortare fredag.
- Stämplingssida `/stampla` för en gemensam surfplatta eller dator: anställningsnummer och PIN-kod, in- och
  utstämpling och val av pengar eller komptid vid övertid. Enheter registreras som **Stämplingsenhet** med en
  hemlig länk; HR sätter PIN-koder med **Sätt PIN** på den anställde, eller bockar i **Stämpla utan PIN**.

### Arbetstidsförkortning och veckoschema

Ett schema som skiljer sig mellan veckodagarna läggs upp med en skifttyp per sorts dag och ett **Skiftschema**
per skifttyp (veckodagar), som tilldelas den anställde med **Tilldelning av skiftschema**. Exempel: 15 minuter
längre dagar måndag till torsdag och arbetstidskontot (Teknikavtalet) uttaget som kortare fredag:

| Skifttyp | Dagar | Tid | Obetalda raster | Arbetstid |
|---|---|---|---|---|
| Mån-tor | måndag–torsdag | 07:00–16:15 | 09:00 20 min, 12:00 40 min | 8 h 15 min |
| Fredag | fredag | 07:00–12:58 | 09:00 20 min | 5 h 38 min |

Veckan blir 38 h 38 min. I **Löneinställningar** sätts *Heltid per dag* till 8,25 (timmar) och *Heltid per veckodag*
fredag till 5 h 38 min, så att deltidsanställdas mertid slutar och övertiden börjar vid heltid den dagen. Arbete
efter skiftets slut är övertid för heltidsanställda. I lönesystemet ställs arbetstidskontot in så att det används
till förkortningen och inte betalas ut.

Tre sätt att ta ut arbetstidskontot:

- **Kortare arbetstid**, varje dag eller en dag i veckan: bara skiften, som i exemplet. Inget skickas i löneunderlaget.
- **Ledighet**: frånvarotypen **Arbetstidskonto** (PAXml `ATK`). Den kräver ingen tilldelning; saldot förs i
  lönesystemet.
- **Pengar eller pension**: sköts helt i lönesystemet.

En röd dag ger ingen planerad tid. Faller den i en vecka med inarbetad tid (t.ex. en fredag) och tiden ska tas ut
en annan dag, ändras skiftet för de dagarna med en egen skifttilldelning.

### Installation

Redis (kö och cache) måste vara igång, annars avbryts HRMS installation halvvägs.

Senast testad med frappe 16.36.1, erpnext 16.37.0 och hrms 16.20.1 (2026-10-04). CI kör testerna mot senaste
`version-16` av frappe, erpnext och hrms vid varje pull request.

```bash
bench get-app hrms --branch version-16
bench get-app https://github.com/ubbe76/HRMS-Sverige --branch version-16
bench --site <site> install-app hrms
bench --site <site> install-app hrms_sverige
bench compile-po-to-mo --app hrms_sverige --locale sv --force
bench --site <site> clear-cache
```

Helglistor ("Sverige ÅÅÅÅ") och frånvaroperioder för i år och nästa år kräver ett företag. På en ny site skapas
de automatiskt när installationsguiden är klar. Fanns företaget redan när appen installerades skapas de direkt;
annars (t.ex. om företaget lades upp på annat sätt) kör `setup_all` enligt nedan.

### Varje år

```bash
# Nästa års helglista och frånvaroperiod
bench --site <site> execute hrms_sverige.setup.install.setup_all
```

Uppsättningen skapar bara det som saknas: befintliga frånvarotyper, helglistor och frånvaroperioder (även en
egen brytning, t.ex. 1 april–31 mars) rörs inte, och en helglista som redan gäller företaget vid årsskiftet
behålls. Vill du bygga om en helglista från grunden:
`bench --site <site> execute hrms_sverige.setup.holidays.create_holiday_list --kwargs "{'year': 2027, 'overwrite': True}"`.

Skapa sedan årets semestertilldelning: öppna frånvaropolicyn "Semester 25 dagar" och använd masskopplingen till
frånvaropolicy med årets frånvaroperiod.

Ändras en anställds arbetsdagar per vecka mitt i året räknas redan skapade tilldelningar inte om – justera
tilldelningen för hand.

### Personnummer och behörigheter

Personnummer ligger på behörighetsnivå 1 och kan bara läsas av HR Manager och HR User. Det sparas inte i den
anställdes ändringshistorik. Vid installationen kopieras Employees standardbehörigheter till anpassade
behörigheter (Custom DocPerm); senare ändringar av standardbehörigheterna i HRMS/ERPNext slår därför inte igenom
automatiskt för Employee. `migrate` ändrar inte behörigheterna.

### Översättning

Efter uppgradering av HRMS:

```bash
bench --site <site> execute hrms_sverige.scripts.sarskrivningar.report --kwargs "{'title_case_only': True}"
bench compile-po-to-mo --app hrms_sverige --locale sv --force
```

Raderna `KONFLIKT` visar strängar där HRMS skriver över en rättelse i `erpnext_sverige`; lägg in
`erpnext_sverige`:s översättning i `hrms_sverige/locale/sv.po`.

### Tester

```bash
bench --site <testsite> run-tests --app hrms_sverige
```

### Licens

Copyright (C) 2026 Urban Källefors

GPL-3.0, samma licens som Frappe HR. Se [license.txt](license.txt).
