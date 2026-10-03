# Ändringslogg

## Ej släppt

- **Löneunderlag till Crona Lön:** godkänd frånvaro per bolag och månad som PAXml 2.0-fil, med PAXml-tidkod på
  frånvarotypen och varning när en redan exporterad månad ändras.
- **Arbetad tid för timavlönade:** fältet Löneform på den anställde. Timavlönade får ARB-timmar per dag från
  godkänd närvaro och frånvaro i timmar per planerat skift. Stämplingar utan närvaro stoppar godkännandet.
- **Övertid, mertid och OB:** Löneinställningar med tidsregler, fälten Övertid som (anställd) och
  Övertidsersättning (stämpling). Tilläggsrader per närvaro; timavlönades ARB minskas med MER och ÖT/ÖK.
- **Stämplingssida:** `/stampla` med anställningsnummer och PIN-kod, registrerade enheter, låsning efter fem
  felaktiga försök och fråga om pengar eller komptid vid övertid.
- **Helgpass är övertid:** ett pass på en helg eller röd dag räknas som övertid (eller mertid vid deltid) för den
  som har ett skift. Den som saknar skift får som tidigare bara OB.
- **Stämpla utan PIN:** ny inställning per anställd. Stämplingssidan frågar då bara efter anställningsnumret.

## v0.1.0 – 2026-10-02 (pre-release)

Första versionen. Kräver Frappe, ERPNext och Frappe HR version 16. Detaljer finns i [README](README.md) och i
[manualen](https://ubbe76.github.io/ERPNext-Sverige-docs/personal/).

### Innehåll

- **Frånvarotyper:** Semester (25 dagar per år, högst 5 sparade dagar per år, förfaller efter 5 år),
  Sjukfrånvaro, VAB, Föräldraledighet, Tjänstledighet och Kompledighet. HRMS engelska standardtyper tas bort
  om de inte används.
- **Helglistor "Sverige ÅÅÅÅ"** med röda dagar samt midsommar-, jul- och nyårsafton, och frånvaroperioder för i
  år och nästa år.
- **Anställd:** personnummer (bara för HR-roller, unikt och borttaget ur ändringshistoriken), anställningsform,
  arbetsdagar per vecka och sysselsättningsgrad.
- **Semester vid deltid:** antalet dagar och taket för sparade dagar räknas om efter arbetsdagar per vecka.
- **Enklare meny:** lön, rekrytering, utlägg och medarbetarsamtal är dolda.
- **Svenska översättningar** för frånvaro, närvaro och skift.

### Begränsningar

- Ingen lönehantering. Lön görs i ett separat lönesystem.
- Nästa års helglista och frånvaroperiod skapas inte automatiskt. Kör `setup_all` en gång per år enligt
  README.
- Appen är testad automatiskt men ännu inte använd i skarp personaladministration.
