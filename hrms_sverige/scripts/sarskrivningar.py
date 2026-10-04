"""Hitta svenska översättningar med särskrivningar eller engelska versaler.

Läser sv.po för hrms, lägger på hrms_sverige/locale/sv.po och listar
poster där fler än första ordet har stor bokstav, t.ex. "Resultat Enhet".

Körs efter uppdatering av hrms för att hitta nya strängar att rätta:

    bench --site <site> execute hrms_sverige.scripts.sarskrivningar.report
    bench --site <site> execute hrms_sverige.scripts.sarskrivningar.report --kwargs "{'output': '/tmp/sv.json'}"
"""

import glob
import json
import os
import re

import frappe
from babel.messages.pofile import read_po

SOURCE_APPS = ("hrms",)
OVERRIDE_APP = "hrms_sverige"
TOKEN = re.compile(r"\{[^}]*\}|%\(?\w*\)?[sd]|<[^>]+>|&\w+;")
WORD = re.compile(r"[A-Za-zÅÄÖåäöÉéÜü][\wÅÄÖåäöÉéÜü\-]*")
SENTENCE_START = ".!?:\n(\"'«–-•*"  # noqa: RUF001

# Egennamn och produktnamn som får ha stor bokstav mitt i en mening
PROPER_NOUNS = {
	"ERPNext",
	"Frappe HR",
	"HRMS",
	"Frappe",
	"Google",
	"Microsoft",
	"Stripe",
	"Plaid",
	"Slack",
	"DocType",
	"Sverige",
	"Excel",
	"Markdown",
	"Jinja",
	"Python",
	"JavaScript",
	"Webhook",
	"GitHub",
	"Dropbox",
	"Gmail",
	"Outlook",
	"Kalender",
	"Kontakter",
	"Drive",
	"Sheets",
	"Cloud",
	"Mail",
	"Gallon",
	"Cubic",
	"Liter",
	"Ounce",
	"DocTypes",
}
ACRONYM_COMPOUND = re.compile(r"^[A-ZÅÄÖ0-9]{2,}-|^[A-ZÅÄÖ][a-zåäö]+-[A-Za-zåäö]")


def _load(path):
	with open(path, "rb") as f:
		return {
			(m.context or "", m.id): m.string
			for m in read_po(f)
			if m.id and m.string and isinstance(m.id, str)
		}


def capitalized_words(text: str) -> list[str]:
	text = TOKEN.sub(" ", text)
	words = []
	for m in WORD.finditer(text):
		word = m.group()
		before = text[: m.start()].rstrip()
		if not before or before[-1] in SENTENCE_START:
			continue
		if (
			word[0].isupper()
			and not word.isupper()
			and word not in PROPER_NOUNS
			and not ACRONYM_COMPOUND.match(word)
		):
			words.append(word)
	return words


def is_title_case(text: str) -> bool:
	"""Etikett med Stor Bokstav På Varje Ord, t.ex. "Inaktivera Automatiska Senaste Filter"."""
	words = WORD.findall(TOKEN.sub(" ", text))
	return len(words) >= 2 and all(w[0].isupper() for w in words)


def find_candidates(title_case_only: bool = False) -> list[dict]:
	merged = {}
	for app in SOURCE_APPS:
		merged.update(_load(frappe.get_app_path(app, "locale", "sv.po")))
	merged.update(_load(frappe.get_app_path(OVERRIDE_APP, "locale", "sv.po")))
	return [
		{"ctx": ctx, "msgid": msgid, "msgstr": msgstr, "words": words}
		for (ctx, msgid), msgstr in sorted(merged.items(), key=lambda kv: kv[0][1].lower())
		if (words := capitalized_words(msgstr)) and (not title_case_only or is_title_case(msgstr))
	]


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


# Sökvägsdelar för HRMS-moduler som är dolda eller inte används (lön, rekrytering, utlägg m.m.)
HIDDEN_PATHS = (
	"payroll",
	"salary",
	"tax",
	"gratuity",
	"appraisal",
	"recruit",
	"interview",
	"job_",
	"expense",
	"travel",
	"training",
	"loan",
	"grievance",
	"vehicle",
	"benefit",
	"incentive",
	"retention",
	"promotion",
	"transfer",
	"separation",
	"boarding",
	"exit",
	"kra",
	"goal",
	"skill",
	"appointment",
	"staffing",
	"full_and_final",
	"employee_advance",
	"pwa",
	"referral",
	"daily_work",
	"encashment",
	"performance",
	"feedback",
	"telemetry",
)


def _labels(path: str) -> list[str]:
	try:
		with open(path, encoding="utf-8") as f:
			d = json.load(f)
	except (ValueError, OSError):
		return []
	if not isinstance(d, dict):
		return []
	labels = []
	if d.get("doctype") in ("Workspace", "Workspace Sidebar", "Desktop Icon"):
		labels += [d.get("label"), d.get("title")]
	if d.get("doctype") == "DocType":
		labels.append(d.get("name"))
	# Rubriker på översikternas kort och diagram, som visas med __()
	if d.get("doctype") == "Number Card":
		labels.append(d.get("label"))
	if d.get("doctype") == "Dashboard Chart":
		labels.append(d.get("chart_name"))
	if d.get("doctype") == "Dashboard":
		labels.append(d.get("dashboard_name"))
	for key in ("fields", "items", "links", "shortcuts", "cards"):
		labels += [row.get("label") for row in d.get(key) or [] if isinstance(row, dict)]
	return [label for label in labels if label]


def find_untranslated_labels() -> list[str]:
	"""Etiketter (doctypes, fält, arbetsytor, sidomeny, översikternas kort och diagram) i HRMS-delar vi använder som saknar svensk översättning."""
	from frappe.translate import get_all_translations

	translations = get_all_translations("sv")
	root = frappe.get_app_path("hrms")
	missing = set()
	for path in glob.glob(os.path.join(root, "**", "*.json"), recursive=True):
		if any(part in path.lower() for part in HIDDEN_PATHS):
			continue
		missing.update(label for label in _labels(path) if label not in translations)
	return sorted(missing)


def report(output: str | None = None, title_case_only: bool = False):
	candidates = find_candidates(title_case_only)
	if output:
		with open(output, "w", encoding="utf-8") as f:
			json.dump(candidates, f, ensure_ascii=False, indent=1)
	for c in candidates[:50]:
		print(f"{c['msgid']!r} -> {c['msgstr']!r}")
	print(f"{len(candidates)} kandidater")
	for label in find_untranslated_labels():
		print(f"SAKNAS {label!r}")
	for c in find_conflicts():
		print(f"KONFLIKT {c['msgid']!r}: erpnext_sverige {c['erpnext_sverige']!r}, hrms {c['hrms']!r}")
