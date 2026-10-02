import frappe
from frappe.tests import IntegrationTestCase
from lxml import etree

from hrms_sverige.lon.doctype.loneunderlag.loneunderlag import ladda_ner
from hrms_sverige.setup.custom_fields import create_custom_fields
from hrms_sverige.setup.holidays import create_holiday_list
from hrms_sverige.setup.leave import ensure_leave_types, ensure_paxml_tidkoder
from hrms_sverige.tests.utils import COMPANY, ensure_test_company, make_leave_application, make_test_employee


def nytt_underlag(manad="September", ar=2026):
	return frappe.get_doc({"doctype": "Loneunderlag", "company": COMPANY, "ar": ar, "manad": manad}).insert()


def rad(employee, leave_type, from_date, to_date, omfattning=100):
	return {
		"employee": employee,
		"leave_type": leave_type,
		"from_date": from_date,
		"to_date": to_date,
		"omfattning": omfattning,
	}


class TestLoneunderlag(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_test_company()
		create_custom_fields()
		ensure_leave_types()
		ensure_paxml_tidkoder()
		create_holiday_list(2026, COMPANY)
		cls.anstalld = make_test_employee("Lön Ett", employee_number="L-1")
		make_leave_application(cls.anstalld, "Sjukfrånvaro", "2026-09-14", "2026-09-16")

	def setUp(self):
		# Varje test börjar från klassens testdata; ändringar i ett test syns inte i nästa
		frappe.db.savepoint("loneunderlag_test")

	def tearDown(self):
		frappe.db.rollback(save_point="loneunderlag_test")

	def test_period_raknas_fram(self):
		doc = nytt_underlag("Februari", 2028)
		self.assertEqual((str(doc.from_date), str(doc.to_date)), ("2028-02-01", "2028-02-29"))

	def test_hamta_franvaro(self):
		doc = nytt_underlag()
		doc.hamta_franvaro()
		r = next(r for r in doc.rader if r.employee == self.anstalld)
		self.assertEqual((r.anstallningsnummer, r.tidkod, r.omfattning), ("L-1", "SJK", 100))
		self.assertEqual((str(r.from_date), str(r.to_date)), ("2026-09-14", "2026-09-16"))

	def test_hamta_tva_ganger_dubblerar_inte(self):
		doc = nytt_underlag()
		doc.hamta_franvaro()
		antal = len(doc.rader)
		doc.hamta_franvaro()
		self.assertEqual(len(doc.rader), antal)

	def test_tidkod_normaliseras(self):
		frappe.db.set_value("Leave Type", "Sjukfrånvaro", "paxml_tidkod", " sjk ")
		doc = nytt_underlag()
		doc.hamta_franvaro()
		self.assertEqual(next(r for r in doc.rader if r.employee == self.anstalld).tidkod, "SJK")

	def test_godkann_och_ladda_ner(self):
		doc = nytt_underlag("Oktober", 2031)
		doc.append("rader", rad(self.anstalld, "Sjukfrånvaro", "2031-10-06", "2031-10-07"))
		doc.save()
		doc.submit()
		ladda_ner(doc.name)
		abbr = frappe.db.get_value("Company", COMPANY, "abbr")
		self.assertEqual(frappe.response.type, "download")
		self.assertEqual(frappe.response.filename, f"paxml-{abbr}-2031-10.xml")
		tt = etree.fromstring(frappe.response.filecontent).find("tidtransaktioner/tidtrans")
		self.assertEqual((tt.get("anstid"), tt.get("postid"), tt.findtext("tidkod")), ("L-1", "1", "SJK"))

	def test_saknat_anstallningsnummer_stoppar(self):
		utan = make_test_employee("Lön Utan")
		frappe.db.set_value("Employee", utan, "employee_number", None)
		doc = nytt_underlag("Mars", 2031)
		doc.append("rader", rad(utan, "Sjukfrånvaro", "2031-03-03", "2031-03-03"))
		doc.save()
		self.assertRaisesRegex(frappe.ValidationError, "anställningsnummer", doc.submit)

	def test_saknad_tidkod_stoppar(self):
		frappe.db.set_value("Leave Type", "Tjänstledighet", "paxml_tidkod", None)
		doc = nytt_underlag("April", 2031)
		doc.append("rader", rad(self.anstalld, "Tjänstledighet", "2031-04-07", "2031-04-07"))
		doc.save()
		self.assertRaisesRegex(frappe.ValidationError, "PAXml-tidkod", doc.submit)

	def test_tomt_underlag_stoppar(self):
		doc = nytt_underlag("Maj", 2031)
		self.assertRaisesRegex(frappe.ValidationError, "rader", doc.submit)

	def test_dubbelt_underlag_stoppar(self):
		forsta = nytt_underlag("Juni", 2031)
		forsta.append("rader", rad(self.anstalld, "Sjukfrånvaro", "2031-06-02", "2031-06-02"))
		forsta.save()
		forsta.submit()
		andra = frappe.copy_doc(forsta)
		andra.docstatus = 0
		andra.insert()
		self.assertRaisesRegex(frappe.ValidationError, "redan", andra.submit)

	def test_makulerad_ansokan_stoppar(self):
		anstalld = make_test_employee("Lön Makulerad", employee_number="L-9")
		ansokan = make_leave_application(anstalld, "Sjukfrånvaro", "2026-09-28", "2026-09-28")
		doc = nytt_underlag()
		doc.hamta_franvaro()
		frappe.get_doc("Leave Application", ansokan).cancel()
		# Frappe stoppar länkar till makulerade dokument och pekar ut raden
		self.assertRaisesRegex(frappe.CancelledLinkError, ansokan, doc.submit)

	def test_makulera_och_gor_om(self):
		doc = nytt_underlag("Juli", 2031)
		doc.append("rader", rad(self.anstalld, "Sjukfrånvaro", "2031-07-07", "2031-07-07"))
		doc.save()
		doc.submit()
		doc.cancel()
		ny = frappe.copy_doc(doc)
		ny.docstatus = 0
		ny.amended_from = doc.name
		ny.insert()
		ny.submit()
		self.assertEqual(ny.docstatus, 1)
