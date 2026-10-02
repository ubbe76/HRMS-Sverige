import os
from datetime import date, datetime

from frappe.tests import UnitTestCase
from lxml import etree

from hrms_sverige.lon.paxml import Huvud, Tidtransaktion, bygg_paxml, orgnr_fran_tax_id

XSD = os.path.join(os.path.dirname(__file__), "fixtures", "paxml-2.0.xsd")
HUVUD = Huvud(
	datum=datetime(2026, 10, 2, 14, 30, 15, 123456),
	foretagnamn="Exempelbolaget AB",
	programnamn="HRMS Sverige 0.1.0",
	foretagorgnr="5560000000",
)


def transaktion(
	postid=1, from_date=date(2026, 9, 14), to_date=date(2026, 9, 16), omfattning=100, tidkod="SJK"
):
	return Tidtransaktion(
		postid=postid,
		anstid="101",
		tidkod=tidkod,
		from_date=from_date,
		to_date=to_date,
		omfattning=omfattning,
	)


class TestPaxml(UnitTestCase):
	def parse(self, data: bytes):
		return etree.fromstring(data)

	def test_validerar_mot_schemat(self):
		data = bygg_paxml(
			HUVUD, [transaktion(), transaktion(2, date(2026, 9, 18), date(2026, 9, 18), 50, "SEM")]
		)
		schema = etree.XMLSchema(etree.parse(XSD))
		self.assertTrue(schema.validate(etree.fromstring(data)), schema.error_log)

	def test_huvud(self):
		rot = self.parse(bygg_paxml(HUVUD, [transaktion()]))
		self.assertEqual(rot.findtext("header/version"), "2.0")
		self.assertEqual(rot.findtext("header/format"), "LÖNIN")
		self.assertEqual(rot.findtext("header/datum"), "2026-10-02T14:30:15")
		self.assertEqual(rot.findtext("header/foretagorgnr"), "5560000000")
		self.assertEqual(rot.findtext("header/foretagnamn"), "Exempelbolaget AB")

	def test_utf8_deklaration(self):
		data = bygg_paxml(HUVUD, [transaktion()])
		self.assertTrue(data.startswith(b"<?xml version='1.0' encoding='UTF-8'?>"))
		self.assertIn("LÖNIN".encode(), data)

	def test_intervall_och_omfattning(self):
		tt = self.parse(bygg_paxml(HUVUD, [transaktion()])).find("tidtransaktioner/tidtrans")
		self.assertEqual((tt.get("anstid"), tt.get("postid")), ("101", "1"))
		self.assertEqual(tt.findtext("tidkod"), "SJK")
		self.assertEqual((tt.findtext("datumfrom"), tt.findtext("datumtom")), ("2026-09-14", "2026-09-16"))
		self.assertIsNone(tt.find("datum"))
		self.assertEqual(tt.findtext("omfattning"), "100")

	def test_en_dag_skrivs_som_datum(self):
		tt = self.parse(
			bygg_paxml(
				HUVUD, [transaktion(from_date=date(2026, 9, 18), to_date=date(2026, 9, 18), omfattning=50)]
			)
		).find("tidtransaktioner/tidtrans")
		self.assertEqual(tt.findtext("datum"), "2026-09-18")
		self.assertIsNone(tt.find("datumfrom"))
		self.assertEqual(tt.findtext("omfattning"), "50")

	def test_utan_orgnr(self):
		huvud = Huvud(datum=HUVUD.datum, foretagnamn="X AB", programnamn="HRMS Sverige")
		self.assertIsNone(self.parse(bygg_paxml(huvud, [transaktion()])).find("header/foretagorgnr"))

	def test_orgnr_fran_tax_id(self):
		self.assertEqual(orgnr_fran_tax_id("SE556000000001"), "5560000000")
		self.assertEqual(orgnr_fran_tax_id("556000-0000"), "5560000000")
		self.assertEqual(orgnr_fran_tax_id("5560000000"), "5560000000")
		self.assertIsNone(orgnr_fran_tax_id(""))
		self.assertIsNone(orgnr_fran_tax_id(None))
		self.assertIsNone(orgnr_fran_tax_id("12345"))
