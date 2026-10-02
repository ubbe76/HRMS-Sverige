# Stämplingssida, del C1 – design

## Bakgrund

Del C2 (`2026-10-02-paxml-tillagg-design.md`, PR #14) räknar övertid, mertid och OB ur närvarons stämplingar. Den
läser den anställdes val av ersättning för övertid, pengar eller komptid, från fältet **Övertidsersättning**
(`overtidsersattning`) på utstämplingen (Employee Checkin). C1 är stämplingssidan där valet görs.

Personalen stämplar på en **gemensam surfplatta eller dator**. De identifierar sig med **anställningsnummer och
PIN-kod**. Enheten får tillgång till sidan som en **registrerad enhet med en hemlig nyckel**, utan inloggning.

## Mål

- En enkel stämplingssida som fungerar i webbläsaren på en surfplatta eller dator.
- In- och utstämpling blir vanliga Employee Checkin. HRMS gör närvaro av dem som vanligt, och C2 räknar på dem.
- Vid utstämpling med extra tid över en gräns väljer den anställde pengar eller komptid.
- Ingen kan stämpla åt en kollega utan dennes PIN. En stulen databaskopia kan inte användas för att stämpla.

**Utanför C1:**

- kortläsare;
- kontroll av var enheten står (IP eller GPS);
- stämpling i den egna mobilen;
- rättning av glömda stämplingar på enheten, som HR gör i ERPNext.

## Innehåll

### Stämplingsenhet

Nytt dokument **Stämplingsenhet** (`Stamplingsenhet`, modul Lon):

- **Namn** (`enhetsnamn`, Data, obligatoriskt, unikt), till exempel "Surfplatta entrén".
- **Aktiv** (`aktiv`, Check, standard 1).
- **Nyckelhash** (`nyckel_hash`, Data, dold och skrivskyddad).
- **Senast använd** (`senast_anvand`, Datetime, skrivskyddad).

Knappen **Skapa länk** (whitelistad metod `skapa_nyckel`, för HR Manager och System Manager) gör följande:

1. Den skapar en slumpad nyckel (`secrets.token_urlsafe(32)`).
2. Den sparar bara SHA-256-hashen av nyckeln.
3. Den visar länken `https://<site>/stampla?enhet=<nyckel>` en gång.

En ny länk gör den gamla ogiltig. Behörigheter: HR Manager och System Manager skapar, ändrar och läser.

### PIN-kod på den anställde

Nya fält på Employee:

- **PIN-hash** (`stampel_pin_hash`, Data, dolt, permlevel 1).
- **PIN måste bytas** (`stampel_pin_maste_bytas`, Check, skrivskyddad).
- **Felaktiga PIN-försök** (`stampel_fel_forsok`, Int, dolt).
- **Låst till** (`stampel_last_till`, Datetime, skrivskyddad).

Knappen **Sätt PIN** på den anställde (whitelistad metod `satt_pin`, för HR Manager och HR User) sätter en PIN-kod.
Den markerar att PIN-koden måste bytas och nollställer låsningen.

PIN-regler:

- 4–6 siffror.
- Inte bara samma siffra.
- En ny PIN-kod vid byte måste skilja sig från den gamla.

PIN-koden hashas med `frappe.utils.password.passlibctx` (samma bibliotek som Frappe använder för lösenord). Den
sparas aldrig i klartext.

### Löneinställningar

Nytt fält **Fråga om övertid efter (minuter)** (`overtid_fraga_minuter`, Int, standard 15).

### Serverfunktioner (`lon/stampling.py`)

Alla är `@frappe.whitelist(allow_guest=True, methods=["POST"])` och kontrollerar först enhetsnyckeln. Enheten
söks på `nyckel_hash = sha256(nyckel)`, och den måste vara aktiv. En okänd eller avstängd enhet ger felet
"Enheten är inte registrerad". Varje anrop uppdaterar `senast_anvand`.

- **`identifiera(enhet, anstallningsnummer, pin)`** returnerar:
  - `fornamn`;
  - `riktning`: `IN` eller `OUT`. Den blir `OUT` om den senaste stämplingen de senaste 24 timmarna är `IN`, annars
    `IN`;
  - `maste_byta_pin`;
  - `fraga_overtid`, `forval` och `extra_minuter`, som gäller vid riktning `OUT`.
- **`byt_pin(enhet, anstallningsnummer, pin, ny_pin)`**: byter PIN-kod och tar bort markeringen "måste bytas".
- **`stampla(enhet, anstallningsnummer, pin, log_type, overtidsersattning=None)`**: skapar Employee Checkin med
  servertid, `device_id` = enhetens namn och vald `overtidsersattning`. Returnerar `fornamn`, `log_type` och
  tiden.

Kontroll av anställd och PIN-kod (i alla tre):

- Den anställde söks på `employee_number` och `status = "Active"`.
- Ett okänt anställningsnummer, en inaktiv anställd och en fel PIN-kod ger **samma** fel: "Fel anställningsnummer
  eller PIN-kod".
- Under en låsning (`stampel_last_till` i framtiden) ges felet "För många felaktiga försök. Försök igen senare."
- Vid fel PIN-kod räknas `stampel_fel_forsok` upp. Vid 5 försök låses anställningsnumret i 15 minuter, och
  räknaren nollställs. En rätt PIN-kod nollställer också räknaren.
- `identifiera` och `stampla` stoppas med "Byt PIN-kod först" om PIN-koden måste bytas. `byt_pin` tillåts då.
- Varje enhet får högst 30 anrop per minut (`frappe.rate_limiter.rate_limit`, nyckel per enhet).

Stämplingsregler:

- `log_type` ska vara `IN` eller `OUT`. `overtidsersattning` ska vara tom, `Pengar` eller `Komptid`, och sparas
  bara vid `OUT`.
- Två stämplingar av samma anställd inom 60 sekunder stoppas med "Du stämplade nyss". Det fångar dubbeltryck.

### Fråga om övertid

Vid riktning `OUT` jämförs passet med dagens planerade skift (`planerat_skift` i `lon/tid.py`, för datumet då
passet började). Passet räknas från den senaste `IN`-stämplingen till nu. Med `extra_tid` blir
`extra_minuter` summan av tiden utanför skiftet. `fraga_overtid` blir sant om det finns ett planerat skift och
`extra_minuter` är större än `overtid_fraga_minuter`.

`forval` är den anställdes **Övertid som** (`Pengar` om fältet är tomt).

### Sidan (`www/stampla.html`, `www/stampla.js`)

- **Gäst-sida.** Nyckeln läses från `?enhet=` första gången och sparas sedan i `localStorage`. Därefter tas den
  bort ur adressfältet.
- **Skärmar:**
  1. Sifferknappsats för anställningsnummer, sedan PIN-kod.
  2. Byte av PIN-kod (ny PIN-kod två gånger), när det krävs.
  3. "Hej <förnamn>" med en stor knapp för föreslagen riktning och en mindre knapp för den andra riktningen.
  4. Vid utstämpling med fråga: knapparna **Pengar** och **Komptid**, där förvalet är markerat.
  5. Kvittens, till exempel "Utstämplad 17:42", som går tillbaka till start efter 4 sekunder.
- Fel visas som text på skärmen, och sidan går tillbaka till start efter 30 sekunder utan aktivitet.
- Svensk text, stora knappar. Sidan fungerar i stående och liggande läge.
- Sidan visar bara förnamn och klockslag, inga andra uppgifter om den anställde.

## Struktur

- `lon/pin.py` (ny, utan databas):
  - `kontrollera_pin_regler(pin, gammal=None)` stoppar med `frappe.ValidationError` vid regelbrott;
  - `hasha_pin(pin)`;
  - `pin_stammer(pin, pin_hash)`.
- `lon/stampling.py` (ny): de tre serverfunktionerna, `satt_pin(employee, pin)`, och hjälpfunktioner för enhet,
  anställd, låsning, riktning och övertidsfråga.
- `lon/doctype/stamplingsenhet/` (ny) med `skapa_nyckel`.
- `setup/custom_fields.py`: PIN-fälten på Employee.
- `lon/doctype/loneinstallningar`: `overtid_fraga_minuter`.
- `public/js/employee.js` med `doctype_js` i `hooks.py`: knappen **Sätt PIN**.
- `www/stampla.html`, `www/stampla.js` och `www/stampla.py` (`no_cache = 1`).

## Tester

Skrivs före koden (TDD) och körs på `test-erp.local` och i CI.

- **pin.py:**
  - hash och kontroll;
  - för kort och för lång PIN-kod;
  - bokstäver;
  - samma siffra;
  - samma som den gamla.
- **Enhet:**
  - okänd nyckel;
  - avstängd enhet;
  - `skapa_nyckel` gör den gamla nyckeln ogiltig;
  - bara hashen sparas.
- **identifiera:**
  - samma fel för okänt nummer, fel PIN-kod och inaktiv anställd;
  - låsning efter 5 fel och upplåsning efter 15 minuter, med simulerad tid;
  - riktning efter senaste stämpling;
  - "Byt PIN-kod först".
- **byt_pin:** gammal PIN-kod krävs, reglerna gäller, och markeringen tas bort.
- **stampla:**
  - checkin med servertid, enhetens namn och val;
  - dubbeltryck inom 60 sekunder stoppas;
  - ogiltig `log_type`;
  - valet sparas inte vid `IN`.
- **Fråga om övertid:** över gränsen, under gränsen, och ingen fråga utan skift.
- **satt_pin:** kräver HR-roll, sätter markeringen och nollställer låsning.
- **Flöde mot C2:** en stämpling `IN` + `OUT` med Komptid, kopplad till närvaro, ger ÖK-rader i
  `tillaggsrader`.
- **Sidan:** jag provar den i en webbläsare på testsiten, eftersom appen saknar testmiljö för JavaScript.

## Dokumentation

Ny manualsida **Stämpling** under Personal. Den beskriver:

- för HR: skapa en enhet och öppna länken på surfplattan eller datorn, sätta PIN-koder, och stänga av en enhet;
- för personalen: hur man stämplar, byter PIN-kod och väljer pengar eller komptid;
- vad man gör om man glömt att stämpla (HR rättar i ERPNext).

README och CHANGELOG uppdateras.

## Utrullning

Utrullningen görs tillsammans med del A, B och C2, efter provimporten i Crona:

1. PR i HRMS-Sverige. CI ska gå igenom.
2. `clear-cache` och `migrate` på test-erp.local och demo-erp.local. Provstämpla i webbläsaren med en testenhet.
3. `clear-cache` och `migrate` på svensk-erp.local. HR skapar enheter och sätter PIN-koder.
