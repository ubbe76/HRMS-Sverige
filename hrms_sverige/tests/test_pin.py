import frappe
from frappe.tests import UnitTestCase

from hrms_sverige.lon.pin import hasha_pin, kontrollera_pin_regler, pin_stammer


class TestPin(UnitTestCase):
	def test_hash_och_kontroll(self):
		pin_hash = hasha_pin("4821")
		self.assertNotIn("4821", pin_hash)
		self.assertTrue(pin_stammer("4821", pin_hash))
		self.assertFalse(pin_stammer("4822", pin_hash))

	def test_tom_hash_stammer_aldrig(self):
		self.assertFalse(pin_stammer("4821", None))
		self.assertFalse(pin_stammer("4821", ""))

	def test_giltiga(self):
		for pin in ("4821", "48213", "482135"):
			kontrollera_pin_regler(pin)

	def test_ogiltiga(self):
		for pin in ("482", "4821357", "48a1", "", "1111", " 4821"):
			self.assertRaises(frappe.ValidationError, kontrollera_pin_regler, pin)

	def test_ny_maste_skilja_sig_fran_gammal(self):
		self.assertRaisesRegex(frappe.ValidationError, "skilja sig", kontrollera_pin_regler, "4821", "4821")

	def test_vanliga_pin_koder_stoppas(self):
		for pin in ("1234", "4321", "12345", "123456", "654321", "2580", "1212", "0852"):
			self.assertRaises(frappe.ValidationError, kontrollera_pin_regler, pin)
