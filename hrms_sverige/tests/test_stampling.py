from datetime import datetime
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from hrms_sverige.lon.pin import pin_stammer
from hrms_sverige.lon.stampling import (
	FEL_BYT_PIN,
	FEL_ENHET,
	FEL_INLOGGNING,
	FEL_LAST,
	byt_pin,
	identifiera,
	nyckel_hash,
	satt_pin,
)
from hrms_sverige.setup.custom_fields import create_custom_fields
from hrms_sverige.tests.utils import ensure_test_company, make_enhet, make_test_employee


class StamplingTestCase(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_test_company()
		create_custom_fields()

	def setUp(self):
		frappe.db.savepoint("stampling_test")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point="stampling_test")


class TestEnhetOchPin(StamplingTestCase):
	def test_bara_hashen_sparas(self):
		namn, nyckel = make_enhet()
		self.assertEqual(frappe.db.get_value("Stamplingsenhet", namn, "nyckel_hash"), nyckel_hash(nyckel))
		self.assertNotEqual(nyckel_hash(nyckel), nyckel)

	def test_ny_nyckel_ersatter_gammal(self):
		namn, gammal = make_enhet()
		_, ny = make_enhet()
		self.assertNotEqual(gammal, ny)
		self.assertEqual(frappe.db.get_value("Stamplingsenhet", namn, "nyckel_hash"), nyckel_hash(ny))

	def test_satt_pin(self):
		anstalld = make_test_employee("Stämpel Pin", employee_number="SP-1")
		frappe.db.set_value(
			"Employee", anstalld, {"stampel_fel_forsok": 3, "stampel_last_till": "2030-01-01 00:00:00"}
		)
		satt_pin(anstalld, "4821")
		rad = frappe.db.get_value(
			"Employee",
			anstalld,
			["stampel_pin_hash", "stampel_pin_maste_bytas", "stampel_fel_forsok", "stampel_last_till"],
			as_dict=True,
		)
		self.assertTrue(pin_stammer("4821", rad.stampel_pin_hash))
		self.assertEqual(
			(rad.stampel_pin_maste_bytas, rad.stampel_fel_forsok, rad.stampel_last_till), (1, 0, None)
		)

	def test_satt_pin_foljer_reglerna(self):
		anstalld = make_test_employee("Stämpel Regel", employee_number="SP-2")
		self.assertRaises(frappe.ValidationError, satt_pin, anstalld, "1111")

	def test_satt_pin_kraver_hr(self):
		anstalld = make_test_employee("Stämpel Gäst", employee_number="SP-3")
		frappe.set_user("Guest")
		self.assertRaises(frappe.PermissionError, satt_pin, anstalld, "4821")

	def test_fraga_minuter_har_standard(self):
		self.assertEqual(
			frappe.get_meta("Loneinstallningar").get_field("overtid_fraga_minuter").default, "15"
		)


NU = datetime(2026, 9, 14, 8, 0)


def pin_anstalld(namn, nummer, pin="4821", maste_bytas=False):
	anstalld = make_test_employee(namn, employee_number=nummer)
	satt_pin(anstalld, pin)
	if not maste_bytas:
		frappe.db.set_value("Employee", anstalld, "stampel_pin_maste_bytas", 0)
	return anstalld


class TestIdentifiera(StamplingTestCase):
	def setUp(self):
		super().setUp()
		self.enhet, self.nyckel = make_enhet()
		self.anstalld = pin_anstalld("Åsa Identifiera", "ID-1")
		frappe.db.set_value("Employee", self.anstalld, "first_name", "Åsa")

	def test_ratt_pin(self):
		svar = identifiera(self.nyckel, "ID-1", "4821")
		self.assertEqual((svar["fornamn"], svar["riktning"], svar["maste_byta_pin"]), ("Åsa", "IN", False))
		self.assertTrue(frappe.db.get_value("Stamplingsenhet", self.enhet, "senast_anvand"))

	def test_fel_enhet(self):
		self.assertEqual(identifiera("fel-nyckel", "ID-1", "4821"), {"fel": FEL_ENHET})
		frappe.db.set_value("Stamplingsenhet", self.enhet, "aktiv", 0)
		self.assertEqual(identifiera(self.nyckel, "ID-1", "4821"), {"fel": FEL_ENHET})

	def test_samma_fel_for_okant_nummer_fel_pin_och_inaktiv(self):
		self.assertEqual(identifiera(self.nyckel, "FINNS-EJ", "4821"), {"fel": FEL_INLOGGNING})
		self.assertEqual(identifiera(self.nyckel, "ID-1", "9999"), {"fel": FEL_INLOGGNING})
		frappe.db.set_value("Employee", self.anstalld, "status", "Inactive")
		self.assertEqual(identifiera(self.nyckel, "ID-1", "4821"), {"fel": FEL_INLOGGNING})

	def test_lasning_efter_fem_fel_och_upplasning(self):
		with patch("hrms_sverige.lon.stampling.now_datetime", return_value=NU):
			for _ in range(5):
				identifiera(self.nyckel, "ID-1", "0000")
			self.assertEqual(identifiera(self.nyckel, "ID-1", "4821"), {"fel": FEL_LAST})
		with patch("hrms_sverige.lon.stampling.now_datetime", return_value=datetime(2026, 9, 14, 8, 16)):
			self.assertEqual(identifiera(self.nyckel, "ID-1", "4821")["fornamn"], "Åsa")

	def test_last_trots_ratt_pin(self):
		frappe.db.set_value("Employee", self.anstalld, "stampel_last_till", "2026-09-14 08:10:00")
		with patch("hrms_sverige.lon.stampling.now_datetime", return_value=NU):
			self.assertEqual(identifiera(self.nyckel, "ID-1", "4821"), {"fel": FEL_LAST})

	def test_ratt_pin_nollstaller_raknaren(self):
		identifiera(self.nyckel, "ID-1", "0000")
		identifiera(self.nyckel, "ID-1", "4821")
		self.assertEqual(frappe.db.get_value("Employee", self.anstalld, "stampel_fel_forsok"), 0)

	def test_riktning_efter_senaste_stampling(self):
		frappe.get_doc(
			{
				"doctype": "Employee Checkin",
				"employee": self.anstalld,
				"log_type": "IN",
				"time": "2026-09-14 07:00:00",
			}
		).insert()
		with patch("hrms_sverige.lon.stampling.now_datetime", return_value=NU):
			self.assertEqual(identifiera(self.nyckel, "ID-1", "4821")["riktning"], "OUT")
		with patch("hrms_sverige.lon.stampling.now_datetime", return_value=datetime(2026, 9, 15, 8, 0)):
			self.assertEqual(identifiera(self.nyckel, "ID-1", "4821")["riktning"], "IN")

	def test_maste_byta_pin(self):
		pin_anstalld("Ny Anställd", "ID-2", "5173", maste_bytas=True)
		self.assertTrue(identifiera(self.nyckel, "ID-2", "5173")["maste_byta_pin"])

	def test_byt_pin(self):
		pin_anstalld("Byter", "ID-3", "5173", maste_bytas=True)
		self.assertEqual(byt_pin(self.nyckel, "ID-3", "5173", "8264"), {"ok": True})
		svar = identifiera(self.nyckel, "ID-3", "8264")
		self.assertFalse(svar["maste_byta_pin"])

	def test_byt_pin_foljer_reglerna(self):
		self.assertIn("fel", byt_pin(self.nyckel, "ID-1", "4821", "4821"))
		self.assertIn("fel", byt_pin(self.nyckel, "ID-1", "4821", "12"))

	def test_byt_pin_med_fel_gammal_pin(self):
		self.assertEqual(byt_pin(self.nyckel, "ID-1", "0000", "8264"), {"fel": FEL_INLOGGNING})
		self.assertEqual(frappe.db.get_value("Employee", self.anstalld, "stampel_fel_forsok"), 1)
