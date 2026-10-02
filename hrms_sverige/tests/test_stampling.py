from datetime import date, datetime
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from hrms_sverige.lon.pin import pin_stammer
from hrms_sverige.lon.stampling import (
	FEL_BYT_PIN,
	FEL_ENHET,
	FEL_ENHET_SPARRAD,
	FEL_INLOGGNING,
	FEL_LAST,
	byt_pin,
	identifiera,
	nyckel_hash,
	satt_pin,
	stampla,
)
from hrms_sverige.lon.tillagg import tillaggsrader
from hrms_sverige.setup.custom_fields import create_custom_fields
from hrms_sverige.setup.holidays import create_holiday_list
from hrms_sverige.tests.utils import (
	COMPANY,
	assign_shift,
	ensure_test_company,
	make_attendance,
	make_enhet,
	make_shift_type,
	make_test_employee,
	satt_tidsregler,
)


class StamplingTestCase(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_test_company()
		create_custom_fields()

	def setUp(self):
		frappe.db.savepoint("stampling_test")
		frappe.cache.delete_keys("stampla:")

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

	def test_enheten_sparras_efter_tio_fel(self):
		# Gissningar mot många anställningsnummer från samma enhet
		for i in range(10):
			identifiera(self.nyckel, f"GISSA-{i}", "2468")
		self.assertEqual(identifiera(self.nyckel, "ID-1", "4821"), {"fel": FEL_ENHET_SPARRAD})

	def test_byt_pin_med_fel_gammal_pin(self):
		self.assertEqual(byt_pin(self.nyckel, "ID-1", "0000", "8264"), {"fel": FEL_INLOGGNING})
		self.assertEqual(frappe.db.get_value("Employee", self.anstalld, "stampel_fel_forsok"), 1)


def klockan(timme, minut=0, dag=14):
	return patch("hrms_sverige.lon.stampling.now_datetime", return_value=datetime(2026, 9, dag, timme, minut))


class TestStampla(StamplingTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		create_holiday_list(2026, COMPANY)
		cls.dag = make_shift_type("_Test Dag", "08:00:00", "16:30:00")
		cls.natt = make_shift_type("_Test Natt", "22:00:00", "06:00:00")

	def setUp(self):
		super().setUp()
		self.enhet, self.nyckel = make_enhet()
		self.anstalld = pin_anstalld("Stämplar", "ST-1")
		assign_shift(self.anstalld, self.dag, "2026-08-01")

	def checkins(self):
		return frappe.get_all(
			"Employee Checkin",
			filters={"employee": self.anstalld},
			fields=["log_type", "time", "device_id", "overtidsersattning"],
			order_by="time asc",
		)

	def test_stampla_in_och_ut(self):
		with klockan(8):
			svar = stampla(self.nyckel, "ST-1", "4821", "IN")
		self.assertEqual((svar["log_type"], svar["tid"]), ("IN", "08:00"))
		with klockan(16, 35):
			stampla(self.nyckel, "ST-1", "4821", "OUT", "Komptid")
		rader = self.checkins()
		self.assertEqual(
			[(r.log_type, str(r.time), r.device_id) for r in rader],
			[("IN", "2026-09-14 08:00:00", self.enhet), ("OUT", "2026-09-14 16:35:00", self.enhet)],
		)
		self.assertEqual(rader[1].overtidsersattning, "Komptid")

	def test_val_sparas_inte_vid_in(self):
		with klockan(8):
			stampla(self.nyckel, "ST-1", "4821", "IN", "Komptid")
		self.assertFalse(self.checkins()[0].overtidsersattning)

	def test_dubbeltryck(self):
		with klockan(8):
			stampla(self.nyckel, "ST-1", "4821", "IN")
		with klockan(8, 0):
			self.assertEqual(stampla(self.nyckel, "ST-1", "4821", "OUT"), {"fel": "Du stämplade nyss."})
		self.assertEqual(len(self.checkins()), 1)

	def test_samtidiga_tryck_stoppas(self):
		# Två samtidiga anrop: den andra ser ännu inte den första stämplingen i databasen
		with klockan(8):
			stampla(self.nyckel, "ST-1", "4821", "IN")
			with patch("hrms_sverige.lon.stampling._senaste", return_value=None):
				self.assertEqual(stampla(self.nyckel, "ST-1", "4821", "IN"), {"fel": "Du stämplade nyss."})
		self.assertEqual(len(self.checkins()), 1)

	def test_ogiltig_riktning_och_val(self):
		with klockan(8):
			self.assertIn("fel", stampla(self.nyckel, "ST-1", "4821", "PAUS"))
			self.assertIn("fel", stampla(self.nyckel, "ST-1", "4821", "OUT", "Bonus"))
		self.assertEqual(self.checkins(), [])

	def test_maste_byta_pin_forst(self):
		pin_anstalld("Ny", "ST-2", "5173", maste_bytas=True)
		with klockan(8):
			self.assertEqual(stampla(self.nyckel, "ST-2", "5173", "IN"), {"fel": FEL_BYT_PIN})

	def test_fraga_overtid_over_gransen(self):
		with klockan(8):
			stampla(self.nyckel, "ST-1", "4821", "IN")
		with klockan(16, 50):
			svar = identifiera(self.nyckel, "ST-1", "4821")
		self.assertEqual((svar["riktning"], svar["fraga_overtid"], svar["extra_minuter"]), ("OUT", True, 20))

	def test_ingen_fraga_under_gransen(self):
		with klockan(8):
			stampla(self.nyckel, "ST-1", "4821", "IN")
		with klockan(16, 40):
			svar = identifiera(self.nyckel, "ST-1", "4821")
		self.assertEqual((svar["fraga_overtid"], svar["extra_minuter"]), (False, 10))

	def test_ingen_fraga_utan_skift(self):
		with klockan(9, dag=12):  # lördag: helgdag, inget skift
			stampla(self.nyckel, "ST-1", "4821", "IN")
		with klockan(17, dag=12):
			self.assertFalse(identifiera(self.nyckel, "ST-1", "4821")["fraga_overtid"])

	def test_utstampling_utan_instampling(self):
		with klockan(16, 45):
			svar = identifiera(self.nyckel, "ST-1", "4821")
			self.assertEqual((svar["riktning"], svar["fraga_overtid"]), ("IN", False))
			self.assertEqual(stampla(self.nyckel, "ST-1", "4821", "OUT")["log_type"], "OUT")

	def test_nattskift_fraga_mot_gardagens_skift(self):
		natt = pin_anstalld("Natt", "ST-3")
		frappe.db.set_value("Employee", natt, "default_shift", self.natt)
		with klockan(22, dag=14):
			stampla(self.nyckel, "ST-3", "4821", "IN")
		with klockan(7, dag=15):
			svar = identifiera(self.nyckel, "ST-3", "4821")
		self.assertEqual((svar["fraga_overtid"], svar["extra_minuter"]), (True, 60))

	def test_flode_till_c2(self):
		satt_tidsregler(
			[
				{
					"typ": "Övertid",
					"niva": 1,
					"dagar": "man tis ons tor fre",
					"fran": "06:00:00",
					"till": "20:00:00",
				}
			]
		)
		with klockan(8):
			stampla(self.nyckel, "ST-1", "4821", "IN")
		with klockan(19):
			stampla(self.nyckel, "ST-1", "4821", "OUT", "Komptid")
		narvaro = make_attendance(
			self.anstalld, "2026-09-14", 11, in_time="2026-09-14 08:00:00", out_time="2026-09-14 19:00:00"
		)
		for namn in frappe.get_all("Employee Checkin", filters={"employee": self.anstalld}, pluck="name"):
			frappe.db.set_value("Employee Checkin", namn, "attendance", narvaro)
		rader = [
			(r["tidkod"], r["timmar"])
			for r in tillaggsrader(COMPANY, date(2026, 9, 1), date(2026, 9, 30))
			if r["employee"] == self.anstalld
		]
		self.assertEqual(rader, [("ÖK1", 2.5)])
