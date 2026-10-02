import os
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from lxml import etree

from hrms_sverige.lon.doctype.loneunderlag.loneunderlag import ladda_ner
from hrms_sverige.setup.custom_fields import create_custom_fields
from hrms_sverige.setup.holidays import create_holiday_list
from hrms_sverige.setup.leave import ensure_leave_types, ensure_paxml_tidkoder
from hrms_sverige.tests.utils import (
	COMPANY,
	assign_shift,
	ensure_test_company,
	make_attendance,
	make_checkin,
	make_leave_application,
	make_shift_type,
	make_test_employee,
)


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

	def test_ogiltig_tidkod_stoppar(self):
		frappe.db.set_value("Leave Type", "Sjukfrånvaro", "paxml_tidkod", "SJUK")
		doc = nytt_underlag("Augusti", 2031)
		doc.append("rader", rad(self.anstalld, "Sjukfrånvaro", "2031-08-04", "2031-08-04"))
		doc.save()
		self.assertRaisesRegex(frappe.ValidationError, "SJUK", doc.submit)

	def test_ogiltig_omfattning_stoppar(self):
		for omfattning in (0, 150):
			doc = nytt_underlag("September", 2031)
			doc.append("rader", rad(self.anstalld, "Sjukfrånvaro", "2031-09-01", "2031-09-01", omfattning))
			doc.save()
			self.assertRaisesRegex(frappe.ValidationError, "Omfattning", doc.submit)

	def test_datum_utanfor_manaden_eller_omvanda_stoppar(self):
		for from_date, to_date in (("2031-11-28", "2031-12-02"), ("2031-11-10", "2031-11-05")):
			doc = nytt_underlag("November", 2031)
			doc.append("rader", rad(self.anstalld, "Sjukfrånvaro", from_date, to_date))
			doc.save()
			self.assertRaisesRegex(frappe.ValidationError, "datum", doc.submit)

	def test_delat_anstallningsnummer_stoppar(self):
		make_test_employee("Lön Dubblett", employee_number="L-1")
		doc = nytt_underlag("December", 2031)
		doc.append("rader", rad(self.anstalld, "Sjukfrånvaro", "2031-12-01", "2031-12-01"))
		doc.save()
		self.assertRaisesRegex(frappe.ValidationError, "L-1", doc.submit)


class TestLoneunderlagTid(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_test_company()
		create_custom_fields()
		ensure_leave_types()
		ensure_paxml_tidkoder()
		create_holiday_list(2026, COMPANY)
		cls.dag = make_shift_type("_Test Dag", "08:00:00", "16:30:00")
		cls.tim = make_test_employee("Lön Tim", employee_number="LT-1", loneform="Timlön")
		assign_shift(cls.tim, cls.dag, "2026-08-01")
		cls.narvaro = make_attendance(cls.tim, "2026-09-14", 7.866)
		make_leave_application(cls.tim, "Sjukfrånvaro", "2026-09-15", "2026-09-15")

	def setUp(self):
		frappe.db.savepoint("lu_tid_test")

	def tearDown(self):
		frappe.db.rollback(save_point="lu_tid_test")

	def tim_rader(self, doc):
		return [
			(r.tidkod, str(r.from_date), r.timmar, frappe.utils.flt(r.omfattning), r.attendance)
			for r in doc.rader
			if r.employee == self.tim
		]

	def godkant_underlag(self):
		doc = nytt_underlag()
		doc.hamta_franvaro()
		doc.set("rader", [r for r in doc.rader if r.employee == self.tim])
		doc.save()
		doc.submit()
		return doc

	def test_hamta_ger_arb_och_franvaro_i_timmar(self):
		doc = nytt_underlag()
		doc.hamta_franvaro()
		self.assertEqual(
			self.tim_rader(doc),
			[("ARB", "2026-09-14", 7.87, 0, self.narvaro), ("SJK", "2026-09-15", 8.5, 0, None)],
		)

	def test_hamta_tva_ganger_med_tid(self):
		doc = nytt_underlag()
		doc.hamta_franvaro()
		antal = len(doc.rader)
		doc.hamta_franvaro()
		self.assertEqual(len(doc.rader), antal)

	def test_godkann_och_fil_med_timmar(self):
		doc = self.godkant_underlag()
		ladda_ner(doc.name)
		rot = etree.fromstring(frappe.response.filecontent)
		xsd = os.path.join(os.path.dirname(__file__), "fixtures", "paxml-2.0.xsd")
		schema = etree.XMLSchema(etree.parse(xsd))
		self.assertTrue(schema.validate(rot), schema.error_log)
		arb = rot.find("tidtransaktioner/tidtrans")
		self.assertEqual(
			(arb.findtext("tidkod"), arb.findtext("datum"), arb.findtext("timmar")),
			("ARB", "2026-09-14", "7.87"),
		)

	def test_stampling_utan_narvaro_stoppar(self):
		make_checkin(self.tim, "2026-09-16 08:02:00")
		doc = nytt_underlag()
		doc.hamta_franvaro()
		self.assertRaisesRegex(frappe.ValidationError, "Stämplingar utan närvaro", doc.submit)

	def test_bade_timmar_och_omfattning_stoppar(self):
		doc = nytt_underlag("Oktober", 2031)
		doc.append("rader", {**rad(self.tim, "Sjukfrånvaro", "2031-10-06", "2031-10-06"), "timmar": 8})
		doc.save()
		self.assertRaisesRegex(frappe.ValidationError, "antingen Timmar eller Omfattning", doc.submit)

	def test_timrad_over_flera_dagar_stoppar(self):
		doc = nytt_underlag("Oktober", 2031)
		doc.append(
			"rader",
			{**rad(self.tim, "Sjukfrånvaro", "2031-10-06", "2031-10-07"), "omfattning": None, "timmar": 8},
		)
		doc.save()
		self.assertRaisesRegex(frappe.ValidationError, "bara gälla en dag", doc.submit)

	def test_for_manga_timmar_stoppar(self):
		doc = nytt_underlag("Oktober", 2031)
		doc.append(
			"rader",
			{**rad(self.tim, "Sjukfrånvaro", "2031-10-06", "2031-10-06"), "omfattning": None, "timmar": 25},
		)
		doc.save()
		self.assertRaisesRegex(frappe.ValidationError, "högst 24", doc.submit)

	def test_makulera_narvaro_i_exporterad_manad_tillats_med_varning(self):
		self.godkant_underlag()
		with patch("frappe.msgprint") as msgprint:
			frappe.get_doc("Attendance", self.narvaro).cancel()
		self.assertEqual(frappe.db.get_value("Attendance", self.narvaro, "docstatus"), 2)
		self.assertTrue(any("redan exporterad" in str(c) for c in msgprint.call_args_list))

	def test_ny_narvaro_i_exporterad_manad_varnar(self):
		self.godkant_underlag()
		with patch("frappe.msgprint") as msgprint:
			make_attendance(self.tim, "2026-09-21", 8)
		self.assertTrue(any("redan exporterad" in str(c) for c in msgprint.call_args_list))

	def antal_varningar(self, msgprint):
		return sum("redan exporterad" in str(c) for c in msgprint.call_args_list)

	def test_godkand_ledighet_ger_en_varning(self):
		self.godkant_underlag()
		with patch("frappe.msgprint") as msgprint:
			make_leave_application(self.tim, "Sjukfrånvaro", "2026-09-22", "2026-09-24")
		self.assertEqual(self.antal_varningar(msgprint), 1)

	def test_manadsavlonads_narvaro_varnar_inte(self):
		self.godkant_underlag()
		manad = make_test_employee("Lön Månad Närvaro", employee_number="LM-1")
		with patch("frappe.msgprint") as msgprint:
			make_attendance(manad, "2026-09-21", 8)
		self.assertEqual(self.antal_varningar(msgprint), 0)
