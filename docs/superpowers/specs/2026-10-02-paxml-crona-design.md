# Löneunderlag till Crona Lön (PAXml), del A – design

## Bakgrund

HRMS Sverige har frånvaro men ingen lönehantering; lönen körs i ett separat lönesystem. Frånvaron ska kunna föras
över som löneunderlag i stället för att skrivas in för hand. Första lönesystemet är **Crona Lön**, som läser
**PAXml 2.0** från ett försystem (Import > Försystem, importformat PAXml, filändelse XML).

Arbetet är uppdelat i tre delar som byggs i tur och ordning, var och en med egen spec och plan:

- **A. Löneunderlaget (den här specen):** dokument, PAXml-fil, kodmappning och frånvaro.
- **B. Arbetad tid:** in- och utstämpling (Employee Checkin) mot skift ger arbetade timmar (ARB) för timavlönade.
- **C. Tillägg:** övertid, mertid och OB räknas fram ur klockslagen enligt regler.

B och C blir fler radtyper i samma löneunderlag och samma fil.

## Mål

- Ett löneunderlag per bolag och kalendermånad som innehåller den godkända frånvaron.
- En PAXml 2.0-fil som Crona Lön kan läsa in, där frånvaron hamnar på rätt dagar i den anställdes kalendarium.
- Mappningen från frånvarotyp till PAXml-tidkod ska gå att ändra; Crona mappar sedan koden till sin egen löneart.

**Utanför del A:** arbetad tid (B), övertid och OB (C), barnets personnummer vid VAB, andra lönesystem än Crona.

## Fakta om formatet och Crona

Från PAXml 2.0 (teknisk beskrivning, paxml.se, schema `http://www.paxml.se/2.0/paxml.xsd`):

- Rotelement `<paxml>`; `<header>` är obligatoriskt och kräver bara `<version>2.0</version>`.
- Frånvaro skickas i `<tidtransaktioner>` som `<tidtrans>` med attributet `anstid` (anställningsnummer) eller
  `persnr`, `<tidkod>` och antingen ett datum eller ett datumintervall.
- **Omfattning:** frånvaro kan anges som `<omfattning>` i procent över ett datumintervall (`<datumfrom>`,
  `<datumtom>`). Löneprogrammet räknar då timmarna mot sitt schema. Timmar får bara anges på enskilda datum, inte
  tillsammans med datumintervall.
- Standardkoder för frånvaro: SEM (semester), SJK (sjukdom), VAB, FPE (föräldraledig), TJL (tjänstledig),
  KOM (kompledig) m.fl. Löneprogrammet avgör karens, sjuklön, betald eller sparad semester.

Från Planday:s guide för Crona (Crona:s egna hjälpsidor var inte åtkomliga):

- Crona matchar anställda på **anställningsnummer**.
- Tidkoder mappas till lönearter i Crona under **Register > Löneartsstyrning**, separat för månads- och
  timavlönade.
- Importerade tidtransaktioner hamnar i den anställdes **kalendarium**.
- Rekommendation: provimportera med en anställd först.

**Okänt, avgörs vid provimporten:** vilken teckenkodning Crona kräver och om Crona kontrollerar organisationsnumret
i huvudet.

## Innehåll

### PAXml-tidkod på frånvarotypen (Leave Type)

Nytt fält **PAXml-tidkod** (`paxml_tidkod`, Data). Förifylls för appens frånvarotyper när fältet saknar värde:

| Frånvarotyp | PAXml-tidkod |
|---|---|
| Semester | SEM |
| Sjukfrånvaro | SJK |
| VAB | VAB |
| Föräldraledighet | FPE |
| Tjänstledighet | TJL |
| Kompledighet | KOM |

Ett ändrat värde skrivs inte över. Frånvarotyper utan kod kan inte ingå i ett godkänt löneunderlag.

### Anställningsnummer

ERPNext:s befintliga fält **Employee Number** (`employee_number`) på den anställde skickas som `anstid`. Det
måste vara samma som i Crona.

### Dokumentet Löneunderlag

Inskickbart dokument `Loneunderlag` (visas som "Löneunderlag") med barntabellen `Loneunderlag Rad`.

Fält:
- **Bolag** (Company, obligatoriskt)
- **Månad**: år och månad. Från- och till-datum (första och sista dagen) räknas fram och visas skrivskyddade.
- **Rader** (`Loneunderlag Rad`): anställd, anställningsnummer, frånvarotyp, PAXml-tidkod, från-datum,
  till-datum, omfattning (%), ledighetsansökan (länk), radnummer (postid).

Flöde:
1. Välj bolag och månad och klicka **Hämta frånvaro**. Raderna ersätts med den godkända frånvaron i perioden.
2. Granska raderna och **godkänn** (skicka in).
3. **Ladda ner PAXml** skapar filen från det godkända underlaget. Den kan laddas ner igen.

Ett godkänt underlag kan makuleras och göras om (Frappe:s amend).

### Från ledighetsansökan till rader

- Med kommer ledighetsansökningar för bolaget med status **Approved** och `docstatus = 1` som överlappar
  perioden. Utkast, avslagna och makulerade tas inte med.
- Datumintervallet klipps vid periodens gränser.
- Hela dagar blir en rad med omfattning 100.
- Halvdag (`half_day`, `half_day_date`): halvdagen blir en egen rad med omfattning 50. Om den ligger mitt i
  intervallet delas ansökan i tre rader: dagarna före (100), halvdagen (50) och dagarna efter (100). En
  ansökan som bara är en halvdag ger en rad med 50.
- Helger och röda dagar ligger kvar inom intervallet; Crona tillämpar sitt schema.
- Raderna sorteras på anställningsnummer och från-datum. Radnumret (postid) är löpande 1, 2, 3 …

### Kontroller vid godkännande

Godkännandet stoppas med ett tydligt meddelande om:
- en anställd på en rad saknar anställningsnummer,
- en frånvarotyp saknar PAXml-tidkod,
- det redan finns ett godkänt löneunderlag för samma bolag och månad,
- underlaget saknar rader.

### Ändringar efter export

Om en ledighetsansökan godkänns eller makuleras och den överlappar en månad som redan har ett godkänt
löneunderlag för bolaget, visas en varning (inte stopp): perioden är redan exporterad och ändringen måste göras
för hand i Crona, eller så makuleras och görs underlaget om.

### PAXml-filen

```xml
<?xml version="1.0" encoding="UTF-8"?>
<paxml xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
       xsi:noNamespaceSchemaLocation="http://www.paxml.se/2.0/paxml.xsd">
  <header>
    <version>2.0</version>
    <format>LÖNIN</format>
    <datum>2026-10-02T14:30:00</datum>
    <foretagorgnr>5560000000</foretagorgnr>
    <foretagnamn>Exempelbolaget AB</foretagnamn>
    <programnamn>HRMS Sverige 0.1.0</programnamn>
  </header>
  <tidtransaktioner>
    <tidtrans anstid="101" postid="1">
      <tidkod>SJK</tidkod>
      <datumfrom>2026-09-14</datumfrom>
      <datumtom>2026-09-16</datumtom>
      <omfattning>100</omfattning>
    </tidtrans>
  </tidtransaktioner>
</paxml>
```

- Teckenkodning UTF-8. Visar provimporten att Crona kräver ISO-8859-1 läggs en inställning till.
- `<foretagorgnr>` räknas fram ur bolagets Tax ID: tio siffror, utan "SE" och "01". Saknas Tax ID utelämnas
  elementet.
- En rad med samma från- och till-datum skrivs med `<datum>` i stället för ett intervall.
- Filnamn: `paxml-<bolagets förkortning>-<ÅÅÅÅ-MM>.xml`.

## Struktur

Ny modul **Lön** (`hrms_sverige/lon/`) i `modules.txt`:

- `lon/doctype/loneunderlag/` och `lon/doctype/loneunderlag_rad/`: dokumenten, med controller för hämtning,
  kontroller och nedladdning.
- `lon/paxml.py`: bygger XML-filen ur en lista med transaktioner och huvuduppgifter. Känner inte till
  Frappe-dokument, så att del B och C kan återanvända den.
- `lon/franvaro.py`: gör om ledighetsansökningar till rader för en period.
- Fältet `paxml_tidkod` läggs i `setup/custom_fields.py` (skapas vid installation och i `after_migrate`).
  Förifyllningen görs i `setup/leave.py` när frånvarotyperna skapas och anropas även från `after_migrate`. Den
  fyller bara tomma värden, så befintliga siter får koderna vid nästa `migrate` utan separat patch.
- Hook på `Leave Application` (`on_submit`, `on_cancel`) för varningen om redan exporterad period.
- Svenska namn på dokument och fält i `locale/sv.po`.

Behörigheter: HR Manager skapar, godkänner och makulerar; HR User skapar och läser. Inga andra roller.

## Tester

Skrivs före koden (TDD), körs på `<testsite>` och i CI.

- **paxml.py:** filen valideras mot PAXml 2.0-schemat (`paxml.xsd`), som läggs in bland testfilerna så att CI inte
  beror på paxml.se. Huvudet, `<datum>` för endagsrader, intervall och omfattning, organisationsnumret.
- **franvaro.py:** hel period, ansökan över månadsskifte, halvdag mitt i och ensam, status som inte är Approved,
  makulerad ansökan, annat bolag.
- **Loneunderlag:** hämta frånvaro, stopp vid saknat anställningsnummer, saknad tidkod, dubbelt underlag samma
  månad och tomt underlag; makulera och gör om.
- **Varningen** när en ledighetsansökan ändras i en exporterad månad.
- **Förifyllningen:** koderna sätts för appens frånvarotyper och ändrade värden behålls.

## Dokumentation

Nytt avsnitt "Löneunderlag till Crona" under Personal i manualen: försystem i Crona (PAXml, filändelse XML),
Löneartsstyrning för SEM, SJK, VAB, FPE, TJL och KOM, anställningsnummer som måste stämma, och rådet att
provimportera med en anställd först. README och CHANGELOG uppdateras.

## Utrullning

1. PR i HRMS-Sverige; CI ska gå igenom.
2. `migrate` på <testsite> och <demosite>, provkörning i webbläsaren.
3. Provimport i Crona med en anställd (användaren). Avvikelser (t.ex. teckenkodning) rättas innan produktion.
4. `migrate` på <site>.
