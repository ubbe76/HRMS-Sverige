from datetime import date, time

import frappe
from frappe.tests import IntegrationTestCase

from hrms_sverige.lon.regler import OB, OVERTID
from hrms_sverige.lon.tillagg import (
	heltid_for_dag,
	heltid_per_dag,
	narvaro_utan_klockslag,
	regler_fran_installningar,
	tillaggsrader,
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
	satt_tidsregler,
)


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

	def test_heltid_per_veckodag(self):
		satt_tidsregler([], heltid=8)
		frappe.db.set_single_value("Loneinstallningar", "heltid_fre", 5 * 3600 + 38 * 60)
		self.assertAlmostEqual(heltid_for_dag(date(2026, 9, 18)), 5 + 38 / 60)  # fredag
		self.assertEqual(heltid_for_dag(date(2026, 9, 14)), 8)  # måndag utan eget värde

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


SEPT = (date(2026, 9, 1), date(2026, 9, 30))
VARDAG = "man tis ons tor fre"
ALLA = "man tis ons tor fre lor son"
REGLER = [
	{"typ": "OB", "niva": 1, "dagar": VARDAG, "fran": "18:00:00", "till": "22:00:00"},
	{"typ": "OB", "niva": 2, "dagar": ALLA, "fran": "22:00:00", "till": "06:00:00"},
	{"typ": "OB", "niva": 3, "dagar": "lor son helgdag", "fran": "00:00:00", "till": "00:00:00"},
	{"typ": "Övertid", "niva": 1, "dagar": VARDAG, "fran": "06:00:00", "till": "20:00:00"},
	{"typ": "Övertid", "niva": 2, "dagar": ALLA + " helgdag", "fran": "20:00:00", "till": "06:00:00"},
]
KVALL = {"in_time": "2026-09-14 08:00:00", "out_time": "2026-09-14 19:00:00"}


class TestTillaggsrader(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_test_company()
		create_custom_fields()
		create_holiday_list(2026, COMPANY)
		cls.dag = make_shift_type("_Test Dag", "08:00:00", "16:30:00")
		cls.halv = make_shift_type("_Test Halv", "08:00:00", "12:00:00")

	def setUp(self):
		frappe.db.savepoint("tillagg_test")
		satt_tidsregler(REGLER)

	def tearDown(self):
		frappe.db.rollback(save_point="tillagg_test")

	def anstalld(self, namn, nummer, skift=None, **falt):
		anstalld = make_test_employee(namn, employee_number=nummer, **falt)
		if skift:
			assign_shift(anstalld, skift, "2026-08-01")
		return anstalld

	def egna(self, anstalld):
		return [
			(r["tidkod"], str(r["from_date"]), r["timmar"])
			for r in tillaggsrader(COMPANY, *SEPT)
			if r["employee"] == anstalld
		]

	def utstampling(self, anstalld, narvaro, val):
		stampling = make_checkin(anstalld, "2026-09-14 19:00:00", "OUT")
		frappe.db.set_value("Employee Checkin", stampling, {"attendance": narvaro, "overtidsersattning": val})

	def test_overtid_och_ob_for_heltid(self):
		a = self.anstalld("Till Heltid", "TL-1", self.dag, sysselsattningsgrad=100)
		make_attendance(a, "2026-09-14", 11, **KVALL)
		self.assertEqual(self.egna(a), [("ÖT1", "2026-09-14", 2.5), ("OB1", "2026-09-14", 1.0)])

	def test_komptid_fran_utstampling(self):
		a = self.anstalld("Till Komp", "TL-2", self.dag)
		self.utstampling(a, make_attendance(a, "2026-09-14", 11, **KVALL), "Komptid")
		self.assertEqual(self.egna(a)[0], ("ÖK1", "2026-09-14", 2.5))

	def test_forval_komptid_pa_anstalld(self):
		a = self.anstalld("Till Förval", "TL-3", self.dag, overtid_som="Komptid")
		make_attendance(a, "2026-09-14", 11, **KVALL)
		self.assertEqual(self.egna(a)[0], ("ÖK1", "2026-09-14", 2.5))

	def test_utstampling_pengar_vinner_over_forval(self):
		a = self.anstalld("Till Pengar", "TL-4", self.dag, overtid_som="Komptid")
		self.utstampling(a, make_attendance(a, "2026-09-14", 11, **KVALL), "Pengar")
		self.assertEqual(self.egna(a)[0], ("ÖT1", "2026-09-14", 2.5))

	def test_mertid_for_deltid(self):
		a = self.anstalld("Till Deltid", "TL-5", self.halv, sysselsattningsgrad=50)
		make_attendance(a, "2026-09-15", 10, in_time="2026-09-15 08:00:00", out_time="2026-09-15 18:00:00")
		self.assertEqual(self.egna(a), [("MER", "2026-09-15", 4.0), ("ÖT1", "2026-09-15", 2.0)])

	def test_overtid_over_tva_nivaer_och_ob(self):
		a = self.anstalld("Till Kväll", "TL-6", self.dag)
		make_attendance(a, "2026-09-16", 12.5, in_time="2026-09-16 08:00:00", out_time="2026-09-16 21:00:00")
		self.assertEqual(
			self.egna(a),
			[("ÖT1", "2026-09-16", 3.5), ("ÖT2", "2026-09-16", 1.0), ("OB1", "2026-09-16", 3.0)],
		)

	def test_helgpass_med_schema_ar_overtid(self):
		a = self.anstalld("Till Lördag", "TL-7", self.dag)
		make_attendance(a, "2026-09-12", 4, in_time="2026-09-12 10:00:00", out_time="2026-09-12 14:00:00")
		self.assertEqual(self.egna(a), [("ÖT1", "2026-09-12", 4.0), ("OB3", "2026-09-12", 4.0)])

	def test_helgpass_utan_schema_bara_ob(self):
		a = self.anstalld("Till Extra", "TL-13")
		make_attendance(a, "2026-09-12", 4, in_time="2026-09-12 10:00:00", out_time="2026-09-12 14:00:00")
		self.assertEqual(self.egna(a), [("OB3", "2026-09-12", 4.0)])

	def test_rod_vardag_med_schema_ar_overtid(self):
		# Kristi himmelsfärd, torsdag 14 maj 2026
		a = self.anstalld("Till Röd Dag", "TL-14")
		assign_shift(a, self.dag, "2026-01-01")
		make_attendance(a, "2026-05-14", 4, in_time="2026-05-14 10:00:00", out_time="2026-05-14 14:00:00")
		rader = [
			(r["tidkod"], r["timmar"])
			for r in tillaggsrader(COMPANY, date(2026, 5, 1), date(2026, 5, 31))
			if r["employee"] == a
		]
		self.assertEqual(rader, [("ÖT1", 4.0), ("OB3", 4.0)])

	def test_helgpass_for_deltid_ger_mertid_forst(self):
		a = self.anstalld("Till Deltid Helg", "TL-15", self.halv, sysselsattningsgrad=50)
		make_attendance(a, "2026-09-12", 10, in_time="2026-09-12 08:00:00", out_time="2026-09-12 18:00:00")
		self.assertEqual(
			self.egna(a),
			[("MER", "2026-09-12", 8.0), ("ÖT1", "2026-09-12", 2.0), ("OB3", "2026-09-12", 10.0)],
		)

	def test_manadsavlonad_far_ob_men_ingen_arb(self):
		a = self.anstalld("Till Månad", "TL-8", self.dag)
		make_attendance(a, "2026-09-14", 11, **KVALL)
		self.assertEqual([r[0] for r in self.egna(a)], ["ÖT1", "OB1"])

	def test_utan_regler(self):
		satt_tidsregler([])
		a = self.anstalld("Till Utan Regler", "TL-9", self.dag)
		make_attendance(a, "2026-09-14", 11, **KVALL)
		self.assertEqual(self.egna(a), [("ÖT1", "2026-09-14", 2.5)])

	def test_narvaro_utan_klockslag(self):
		a = self.anstalld("Till Utan Tid", "TL-10", self.dag)
		make_attendance(a, "2026-09-17", 10)
		self.assertEqual(self.egna(a), [])
		self.assertEqual(narvaro_utan_klockslag(COMPANY, *SEPT).get(a), [date(2026, 9, 17)])

	def test_rod_dag_dagen_efter_manaden(self):
		# Nattpass 30 april till 1 maj (fredag, röd dag): timmarna efter midnatt ger helgdags-OB
		natt = make_shift_type("_Test Natt", "22:00:00", "06:00:00")
		a = self.anstalld("Till Valborg", "TL-11", natt)
		make_attendance(a, "2026-04-30", 8, in_time="2026-04-30 22:00:00", out_time="2026-05-01 06:00:00")
		rader = [
			(r["tidkod"], r["timmar"])
			for r in tillaggsrader(COMPANY, date(2026, 4, 1), date(2026, 4, 30))
			if r["employee"] == a
		]
		self.assertEqual(rader, [("OB2", 2.0), ("OB3", 6.0)])

	def test_rast_raknas_inte_som_extra_tid(self):
		# Deltid 50 %, skift 08 till 12, stämplat 08-12 och 13-17: 4 h extra, allt mertid (rasten räknas inte)
		a = self.anstalld("Till Rast", "TL-12", self.halv, sysselsattningsgrad=50)
		narvaro = make_attendance(
			a, "2026-09-18", 8, in_time="2026-09-18 08:00:00", out_time="2026-09-18 17:00:00"
		)
		for tid, typ in (("08:00", "IN"), ("12:00", "OUT"), ("13:00", "IN"), ("17:00", "OUT")):
			stampling = make_checkin(a, f"2026-09-18 {tid}:00", typ)
			frappe.db.set_value("Employee Checkin", stampling, "attendance", narvaro)
		self.assertEqual(self.egna(a), [("MER", "2026-09-18", 4.0)])

	def test_ob_raknas_inte_pa_obetald_rast(self):
		kvall = make_shift_type("_Test Kväll Rast", "14:00:00", "22:00:00", [("19:00:00", 30)])
		a = self.anstalld("Till Kvällsrast", "TL-20", kvall)
		make_attendance(a, "2026-09-14", 8, in_time="2026-09-14 14:00:00", out_time="2026-09-14 22:00:00")
		self.assertEqual(self.egna(a), [("OB1", "2026-09-14", 3.5)])

	def test_overtid_borjar_efter_skiftet_trots_raster(self):
		lang = make_shift_type("_Test Mån-tor", "07:00:00", "16:15:00", [("09:00:00", 20), ("12:00:00", 40)])
		a = self.anstalld("Till Lång Dag", "TL-21", lang, sysselsattningsgrad=100)
		make_attendance(a, "2026-09-14", 10.25, in_time="2026-09-14 07:00:00", out_time="2026-09-14 17:15:00")
		self.assertEqual(self.egna(a), [("ÖT1", "2026-09-14", 1.0)])

	def test_mertid_en_kort_fredag_for_deltid(self):
		# Heltid på fredag är 5 h 38 min. Deltidsskift 07-10 med 20 min frukost ger 2 h 40 min inom skiftet;
		# 10-14 är extra: 2 h 58 min mertid upp till heltid, resten övertid.
		frappe.db.set_single_value("Loneinstallningar", "heltid_fre", 5 * 3600 + 38 * 60)
		kort = make_shift_type("_Test Deltid Fredag", "07:00:00", "10:00:00", [("09:00:00", 20)])
		a = self.anstalld("Till Kort Fredag", "TL-22", kort, sysselsattningsgrad=50)
		make_attendance(a, "2026-09-18", 6.67, in_time="2026-09-18 07:00:00", out_time="2026-09-18 14:00:00")
		self.assertEqual(self.egna(a), [("MER", "2026-09-18", 2.97), ("ÖT1", "2026-09-18", 1.03)])
