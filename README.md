## HRMS Sverige

Svensk anpassning av Frappe HRMS: personalregister, frånvaro/ledighet och närvaro.

- Frånvarotyper: Semester (25 dagar/år, max 5 sparade dagar/år, förfaller efter 5 år), Sjukfrånvaro, VAB,
  Föräldraledighet, Tjänstledighet, Kompledighet.
- Helglistor "Sverige ÅÅÅÅ" med röda dagar samt midsommar-, jul- och nyårsafton, kopplade till företaget
  från 1 januari.
- Anställd: personnummer (bara HR-roller), anställningsform, arbetsdagar per vecka, sysselsättningsgrad.
- Semester vid deltid: 25 × arbetsdagar/5, avrundat uppåt, när tilldelningen skapas från frånvaropolicyn.
- Lön, rekrytering, utlägg och medarbetarsamtal är dolda.
- Rättade svenska översättningar för frånvaro, närvaro och skift.

### Installation

Redis (kö och cache) måste vara igång, annars avbryts HRMS installation halvvägs.

```bash
bench get-app hrms --branch version-16
bench get-app https://github.com/ubbe76/HRMS-Sverige --branch version-16
bench --site <site> install-app hrms
bench --site <site> install-app hrms_sverige
bench compile-po-to-mo --app hrms_sverige --locale sv --force
bench --site <site> clear-cache
```

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
bench --site test-erp.local run-tests --app hrms_sverige
```

### License

gpl-3.0
