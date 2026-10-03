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
	} catch (e) {
		// utan localStorage fungerar sidan bara med nyckeln i adressen
	}
	let lage = {};
	let timer;
	let upptagen = false;

	function visa(rubrik, text, falt, sekunder = 30) {
		$("rubrik").textContent = rubrik;
		$("text").textContent = text || "";
		$("falt").textContent = falt || "";
		$("fel").textContent = "";
		clearTimeout(timer);
		timer = setTimeout(start, sekunder * 1000);
	}

	function fel(meddelande) {
		$("fel").textContent = meddelande;
	}

	function anropa(funktion, args) {
		// Dubbeltryck på pekskärmen: ignorera nya tryck medan ett anrop pågår
		if (upptagen) return new Promise(() => {});
		upptagen = true;
		return frappe
			.call({ method: METOD + funktion, type: "POST", args: { enhet, ...args } })
			.then((r) => r.message || {})
			.finally(() => {
				upptagen = false;
			});
	}

	function knappsats(etikett, dold, klar) {
		let varde = "";
		const yta = $("yta");
		yta.innerHTML = "";
		const rutnat = document.createElement("div");
		rutnat.className = "knappar";
		for (const k of ["1", "2", "3", "4", "5", "6", "7", "8", "9", "⌫", "0", "OK"]) {
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
			lage.pin = "";
			identifiera();
		});
	}

	function identifiera() {
		anropa("identifiera", { anstallningsnummer: lage.nummer, pin: lage.pin }).then((svar) => {
			if (svar.fel) return start(), fel(svar.fel);
			// PIN-kod frågas bara efter när den anställde (eller ett okänt nummer) kräver en
			if (svar.behover_pin && !lage.pin)
				return knappsats("PIN-kod", true, (pin) => {
					lage.pin = pin;
					identifiera();
				});
			if (svar.behover_pin) return start();
			lage.svar = svar;
			if (svar.maste_byta_pin) return bytPin();
			valjRiktning();
		});
	}

	function bytPin() {
		knappsats(
			`Hej ${lage.svar.fornamn}! Välj en ny PIN-kod (4 till 6 siffror)`,
			true,
			(ny) => {
				knappsats("Upprepa den nya PIN-koden", true, (igen) => {
					if (igen !== ny) return bytPin(), fel("PIN-koderna var inte lika.");
					anropa("byt_pin", {
						anstallningsnummer: lage.nummer,
						pin: lage.pin,
						ny_pin: ny,
					}).then((svar) => {
						if (svar.fel) return bytPin(), fel(svar.fel);
						lage.pin = ny;
						identifiera();
					});
				});
			}
		);
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
		visa(`Hej ${s.fornamn}!`, "", "", 10);
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
			const klass = "andra" + (val === lage.svar.forval ? " vald" : "");
			rutnat.appendChild(knapp(val, klass, () => stampla("OUT", val)));
		}
		yta.appendChild(rutnat);
		visa(
			"Övertid",
			`Du har ${lage.svar.extra_minuter} minuter utanför ditt skift. Vill du ha pengar eller komptid?`,
			"",
			10
		);
	}

	function stampla(riktning, val) {
		anropa("stampla", {
			anstallningsnummer: lage.nummer,
			pin: lage.pin,
			log_type: riktning,
			overtidsersattning: val,
		}).then((svar) => {
			if (svar.fel || svar.behover_pin) return start(), fel(svar.fel || "");
			$("yta").innerHTML = "";
			visa(
				`${riktning === "IN" ? "Instämplad" : "Utstämplad"} ${svar.tid}`,
				`Tack, ${svar.fornamn}!`
			);
			clearTimeout(timer);
			timer = setTimeout(start, 4000);
		});
	}

	frappe.ready(start);
})();
