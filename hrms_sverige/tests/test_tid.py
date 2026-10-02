from datetime import date, datetime

import frappe
from frappe.tests import IntegrationTestCase

from hrms_sverige.lon.tid import (
	arbetad_tid,
	planerade_timmar,
	planerat_skift,
	skiftlangd,
	stamplingar_utan_narvaro,
)
from hrms_sverige.setup.custom_fields import create_custom_fields
from hrms_sverige.setup.holidays import create_holiday_list
from hrms_sverige.tests.utils import (
	COMPANY,
	assign_shift,
	ensure_test_company,
	make_attendance,
	make_checkin,
	make_shift_type,
	make_test_employee,
)

SEPT = (date(2026, 9, 1), date(2026, 9, 30))


class TestTid(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_test_company()
		create_custom_fields()
		create_holiday_list(2026, COMPANY)
		cls.dag = make_shift_type("_Test Dag", "08:00:00", "16:30:00")
		cls.natt = make_shift_type("_Test Natt", "22:00:00", "06:00:00")

	def setUp(self):
		frappe.db.savepoint("tid_test")

	def tearDown(self):
		frappe.db.rollback(save_point="tid_test")

	def timanstalld(self, namn, nummer):
		return make_test_employee(namn, employee_number=nummer, loneform="Timlön")

	def test_skiftlangd(self):
		self.assertEqual(skiftlangd("08:00:00", "16:30:00"), 8.5)
		self.assertEqual(skiftlangd("22:00:00", "06:00:00"), 8.0)

	def test_dagskift_fran_tilldelning(self):
		anstalld = self.timanstalld("Tid Dag", "T-1")
		assign_shift(anstalld, self.dag, "2026-09-01")
		self.assertEqual(planerade_timmar(anstalld, "2026-09-14"), 8.5)

	def test_standardskift_over_midnatt(self):
		anstalld = self.timanstalld("Tid Natt", "T-2")
		frappe.db.set_value("Employee", anstalld, "default_shift", self.natt)
		self.assertEqual(planerade_timmar(anstalld, "2026-09-14"), 8.0)

	def test_helgdag_ger_noll(self):
		anstalld = self.timanstalld("Tid Helg", "T-3")
		assign_shift(anstalld, self.dag, "2026-09-01")
		self.assertEqual(planerade_timmar(anstalld, "2026-09-12"), 0)  # lördag

	def test_inget_skift_ger_noll(self):
		anstalld = self.timanstalld("Tid Utan", "T-4")
		self.assertEqual(planerade_timmar(anstalld, "2026-09-14"), 0)

	def test_avslutad_tilldelning(self):
		anstalld = self.timanstalld("Tid Slut", "T-5")
		assign_shift(anstalld, self.dag, "2026-09-01", "2026-09-10")
		self.assertEqual(planerade_timmar(anstalld, "2026-09-14"), 0)

	def test_inaktiv_tilldelning(self):
		anstalld = self.timanstalld("Tid Inaktiv", "T-6")
		tilldelning = assign_shift(anstalld, self.dag, "2026-09-01")
		frappe.db.set_value("Shift Assignment", tilldelning, "status", "Inactive")
		self.assertEqual(planerade_timmar(anstalld, "2026-09-14"), 0)

	def test_arbetad_tid_for_timavlonade(self):
		anstalld = self.timanstalld("Tid Arb", "T-7")
		narvaro = make_attendance(anstalld, "2026-09-14", 7.866)
		make_attendance(anstalld, "2026-09-15", 4, status="Half Day")
		make_attendance(anstalld, "2026-09-16", 0)
		make_attendance(anstalld, "2026-09-17", 0, status="Absent")
		make_attendance(anstalld, "2026-09-18", 8, submit=False)
		rader = [r for r in arbetad_tid(COMPANY, *SEPT) if r["employee"] == anstalld]
		self.assertEqual(
			[(r["tidkod"], r["from_date"], r["to_date"], r["timmar"]) for r in rader],
			[
				("ARB", date(2026, 9, 14), date(2026, 9, 14), 7.87),
				("ARB", date(2026, 9, 15), date(2026, 9, 15), 4.0),
			],
		)
		self.assertEqual(rader[0]["attendance"], narvaro)

	def test_manadsavlonad_far_ingen_arbetad_tid(self):
		anstalld = make_test_employee("Tid Månad", employee_number="M-1")
		make_attendance(anstalld, "2026-09-14", 8)
		self.assertEqual([r for r in arbetad_tid(COMPANY, *SEPT) if r["employee"] == anstalld], [])

	def test_annat_bolag(self):
		anstalld = self.timanstalld("Tid Bolag", "T-8")
		make_attendance(anstalld, "2026-09-14", 8)
		self.assertEqual(arbetad_tid("Annat bolag AB", *SEPT), [])

	def test_stampling_utan_narvaro(self):
		anstalld = self.timanstalld("Tid Stämpel", "T-9")
		make_checkin(anstalld, "2026-09-16 08:01:00")
		self.assertEqual(stamplingar_utan_narvaro(COMPANY, *SEPT).get(anstalld), [date(2026, 9, 16)])

	def test_dag_med_narvaro_raknas_inte(self):
		anstalld = self.timanstalld("Tid Manuell", "T-10")
		make_checkin(anstalld, "2026-09-16 08:01:00")
		make_attendance(anstalld, "2026-09-16", 8)
		self.assertNotIn(anstalld, stamplingar_utan_narvaro(COMPANY, *SEPT))

	def test_manadsavlonad_ignoreras(self):
		anstalld = make_test_employee("Tid Månad Stämpel", employee_number="M-2")
		make_checkin(anstalld, "2026-09-16 08:01:00")
		self.assertNotIn(anstalld, stamplingar_utan_narvaro(COMPANY, *SEPT))

	def test_hoppa_over_auto_narvaro_ignoreras(self):
		anstalld = self.timanstalld("Tid Hoppa", "T-11")
		make_checkin(anstalld, "2026-09-16 08:01:00", skip_auto_attendance=1)
		self.assertNotIn(anstalld, stamplingar_utan_narvaro(COMPANY, *SEPT))

	def test_planerat_skift_med_klockslag(self):
		anstalld = self.timanstalld("Tid Klockslag", "T-20")
		assign_shift(anstalld, self.dag, "2026-09-01")
		self.assertEqual(
			planerat_skift(anstalld, "2026-09-14"),
			(datetime(2026, 9, 14, 8, 0), datetime(2026, 9, 14, 16, 30)),
		)

	def test_planerat_nattskift_slutar_nasta_dag(self):
		anstalld = self.timanstalld("Tid Klockslag Natt", "T-21")
		frappe.db.set_value("Employee", anstalld, "default_shift", self.natt)
		self.assertEqual(
			planerat_skift(anstalld, "2026-09-14"),
			(datetime(2026, 9, 14, 22, 0), datetime(2026, 9, 15, 6, 0)),
		)

	def test_inget_planerat_skift_pa_helgdag(self):
		anstalld = self.timanstalld("Tid Klockslag Helg", "T-22")
		assign_shift(anstalld, self.dag, "2026-09-01")
		self.assertIsNone(planerat_skift(anstalld, "2026-09-12"))

	def test_nattskift_med_utstampling_nasta_dag(self):
		# HRMS daterar närvaron efter skiftets startdag; utstämplingen 06:00 ligger dagen efter
		anstalld = self.timanstalld("Tid Nattpass", "T-12")
		frappe.db.set_value("Employee", anstalld, "default_shift", self.natt)
		make_checkin(anstalld, "2026-09-18 22:01:00", "IN")
		make_checkin(anstalld, "2026-09-19 06:02:00", "OUT")
		make_attendance(anstalld, "2026-09-18", 8)
		self.assertNotIn(anstalld, stamplingar_utan_narvaro(COMPANY, *SEPT))

	def test_nattskift_over_manadsskifte(self):
		anstalld = self.timanstalld("Tid Nattskifte", "T-13")
		frappe.db.set_value("Employee", anstalld, "default_shift", self.natt)
		make_checkin(anstalld, "2026-08-31 22:01:00", "IN")
		make_checkin(anstalld, "2026-09-01 06:02:00", "OUT")
		make_attendance(anstalld, "2026-08-31", 8)
		self.assertNotIn(anstalld, stamplingar_utan_narvaro(COMPANY, *SEPT))
