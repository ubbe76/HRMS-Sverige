"""Löneunderlag per bolag och kalendermånad: godkänd frånvaro som PAXml-fil till lönesystemet."""

import calendar
from datetime import date

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime

import hrms_sverige
from hrms_sverige.lon.franvaro import rader_for_period
from hrms_sverige.lon.paxml import TIDKODER, Huvud, Tidtransaktion, bygg_paxml, orgnr_fran_tax_id

MANADER = [
	"Januari",
	"Februari",
	"Mars",
	"April",
	"Maj",
	"Juni",
	"Juli",
	"Augusti",
	"September",
	"Oktober",
	"November",
	"December",
]


class Loneunderlag(Document):
	def validate(self):
		self.satt_period()
		self.uppdatera_rader()

	def satt_period(self):
		manad = MANADER.index(self.manad) + 1
		self.from_date = date(self.ar, manad, 1)
		self.to_date = date(self.ar, manad, calendar.monthrange(self.ar, manad)[1])

	def uppdatera_rader(self):
		"""Anställningsnummer och tidkod hämtas på nytt, så att raderna speglar dagens register."""
		for rad in self.rader:
			rad.anstallningsnummer = (
				frappe.db.get_value("Employee", rad.employee, "employee_number") or ""
			).strip()
			rad.tidkod = (
				(frappe.db.get_value("Leave Type", rad.leave_type, "paxml_tidkod") or "").strip().upper()
			)

	def before_submit(self):
		if not self.rader:
			frappe.throw(_("Löneunderlaget har inga rader."))
		utan_nummer = sorted({r.employee for r in self.rader if not r.anstallningsnummer})
		if utan_nummer:
			frappe.throw(
				_("Anställda utan anställningsnummer: {0}. Ange samma nummer som i lönesystemet.").format(
					", ".join(utan_nummer)
				)
			)
		utan_kod = sorted({r.leave_type for r in self.rader if not r.tidkod})
		if utan_kod:
			frappe.throw(
				_("Frånvarotyper utan PAXml-tidkod: {0}. Ange koden på frånvarotypen.").format(
					", ".join(utan_kod)
				)
			)
		ogiltiga = sorted({r.tidkod for r in self.rader if r.tidkod not in TIDKODER})
		if ogiltiga:
			frappe.throw(
				_(
					"Okända PAXml-tidkoder: {0}. Använd en kod från PAXml-standarden, t.ex. SEM, SJK eller VAB."
				).format(", ".join(ogiltiga))
			)
		for r in self.rader:
			if not 0 < (r.omfattning or 0) <= 100:
				frappe.throw(_("Rad {0}: Omfattning måste vara större än 0 och högst 100 %.").format(r.idx))
			if not (
				getdate(self.from_date) <= getdate(r.from_date) <= getdate(r.to_date) <= getdate(self.to_date)
			):
				frappe.throw(
					_("Rad {0}: från- och till-datum måste ligga i {1} {2}, med från-datum först.").format(
						r.idx, self.manad, self.ar
					)
				)
		delade = sorted(
			n
			for n in {r.anstallningsnummer for r in self.rader}
			if frappe.db.count("Employee", {"employee_number": n}) > 1
		)
		if delade:
			frappe.throw(
				_(
					"Anställningsnummer som finns på flera anställda: {0}. Varje anställd måste ha ett eget nummer."
				).format(", ".join(delade))
			)
		befintligt = frappe.db.get_value(
			"Loneunderlag",
			{
				"company": self.company,
				"ar": self.ar,
				"manad": self.manad,
				"docstatus": 1,
				"name": ("!=", self.name),
			},
		)
		if befintligt:
			frappe.throw(
				_("Det finns redan ett godkänt löneunderlag för {0} {1}: {2}.").format(
					self.manad, self.ar, befintligt
				)
			)

	@frappe.whitelist()
	def hamta_franvaro(self):
		if self.docstatus != 0:
			frappe.throw(_("Frånvaro kan bara hämtas till ett utkast."))
		self.check_permission("write")
		self.satt_period()
		self.set("rader", [])
		for rad in rader_for_period(self.company, self.from_date, self.to_date):
			self.append("rader", rad)
		self.save()

	def filnamn(self) -> str:
		abbr = frappe.db.get_value("Company", self.company, "abbr")
		return f"paxml-{abbr}-{getdate(self.from_date):%Y-%m}.xml"

	def paxml(self) -> bytes:
		huvud = Huvud(
			datum=now_datetime(),
			foretagnamn=self.company,
			programnamn=f"HRMS Sverige {hrms_sverige.__version__}",
			foretagorgnr=orgnr_fran_tax_id(frappe.db.get_value("Company", self.company, "tax_id")),
		)
		transaktioner = [
			Tidtransaktion(
				postid=rad.idx,
				anstid=rad.anstallningsnummer,
				tidkod=rad.tidkod,
				from_date=getdate(rad.from_date),
				to_date=getdate(rad.to_date),
				omfattning=rad.omfattning,
			)
			for rad in self.rader
		]
		return bygg_paxml(huvud, transaktioner)


@frappe.whitelist()
def ladda_ner(name: str):
	doc = frappe.get_doc("Loneunderlag", name)
	doc.check_permission("read")
	if doc.docstatus != 1:
		frappe.throw(_("Godkänn löneunderlaget innan filen laddas ner."))
	frappe.response.filename = doc.filnamn()
	frappe.response.filecontent = doc.paxml()
	frappe.response.type = "download"
