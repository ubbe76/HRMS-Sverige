from datetime import time

import frappe
from frappe.tests import IntegrationTestCase

from hrms_sverige.lon.regler import OB, OVERTID
from hrms_sverige.lon.tillagg import heltid_per_dag, regler_fran_installningar
from hrms_sverige.setup.custom_fields import create_custom_fields
from hrms_sverige.tests.utils import ensure_test_company, satt_tidsregler


class TestLoneinstallningar(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_test_company()
		create_custom_fields()

	def setUp(self):
		frappe.db.savepoint("inst_test")

	def tearDown(self):
		frappe.db.rollback(save_point="inst_test")

	def test_regler_lases_in(self):
		satt_tidsregler(
			[
				{
					"typ": "OB",
					"niva": 1,
					"dagar": "man tis ons tor fre",
					"fran": "18:00:00",
					"till": "22:00:00",
				},
				{
					"typ": "Övertid",
					"niva": 2,
					"dagar": "lor son helgdag",
					"fran": "00:00:00",
					"till": "00:00:00",
				},
			],
			heltid=7.5,
		)
		ob, ot = regler_fran_installningar()
		self.assertEqual(
			(ob.typ, ob.niva, ob.dagar, ob.helgdag, ob.fran, ob.till),
			(OB, 1, frozenset(range(5)), False, time(18), time(22)),
		)
		self.assertEqual((ot.typ, ot.niva, ot.dagar, ot.helgdag), (OVERTID, 2, frozenset({5, 6}), True))
		self.assertEqual(heltid_per_dag(), 7.5)

	def test_niva_utanfor_1_till_5_stoppas(self):
		self.assertRaisesRegex(
			frappe.ValidationError,
			"Nivå",
			satt_tidsregler,
			[{"typ": "OB", "niva": 6, "dagar": "man", "fran": "18:00:00", "till": "22:00:00"}],
		)

	def test_regel_utan_dag_stoppas(self):
		self.assertRaisesRegex(
			frappe.ValidationError,
			"minst en dag",
			satt_tidsregler,
			[{"typ": "OB", "niva": 1, "dagar": "", "fran": "18:00:00", "till": "22:00:00"}],
		)

	def test_overtidsfalt_finns(self):
		self.assertEqual(
			frappe.get_meta("Employee").get_field("overtid_som").options.split("\n"), ["Pengar", "Komptid"]
		)
		self.assertEqual(
			frappe.get_meta("Employee Checkin").get_field("overtidsersattning").options.split("\n"),
			["", "Pengar", "Komptid"],
		)
