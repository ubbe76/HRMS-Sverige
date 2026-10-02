import frappe
from frappe.tests import IntegrationTestCase

from hrms_sverige.lon.pin import pin_stammer
from hrms_sverige.lon.stampling import nyckel_hash, satt_pin
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
