from datetime import date, datetime, time

from frappe.tests import UnitTestCase

from hrms_sverige.lon.regler import (
	OB,
	OVERTID,
	Tidsregel,
	dela_mertid,
	extra_tid,
	fordela,
	regelintervall,
	timmar,
)

VARDAGAR = frozenset(range(5))
ALLA = frozenset(range(7))
OB1 = Tidsregel(OB, 1, VARDAGAR, False, time(18), time(22))
OB2 = Tidsregel(OB, 2, ALLA, False, time(22), time(6))
OB3 = Tidsregel(OB, 3, frozenset({5, 6}), True, time(0), time(0))
OT1 = Tidsregel(OVERTID, 1, VARDAGAR, False, time(6), time(20))
OT2 = Tidsregel(OVERTID, 2, ALLA, False, time(20), time(6))
MANDAG = date(2026, 9, 14)
LORDAG = date(2026, 9, 12)
JULDAGEN = date(2026, 12, 25)  # fredag


def dt(dag, timme, minut=0):
	return datetime.combine(dag, time(timme, minut))


class TestRegler(UnitTestCase):
	def test_regelintervall_over_midnatt(self):
		self.assertEqual(regelintervall(OB2, MANDAG, False), [(dt(MANDAG, 22), dt(date(2026, 9, 15), 6))])

	def test_fran_lika_med_till_ar_hela_dygnet(self):
		self.assertEqual(regelintervall(OB3, LORDAG, False), [(dt(LORDAG, 0), dt(date(2026, 9, 13), 0))])

	def test_helgdag_kontra_vardag(self):
		self.assertEqual(len(regelintervall(OB3, JULDAGEN, True)), 1)
		self.assertEqual(regelintervall(OB3, date(2026, 9, 18), False), [])

	def test_ob_fordelas_per_niva(self):
		self.assertEqual(
			fordela([(dt(MANDAG, 14), dt(MANDAG, 23, 30))], [OB1, OB2, OB3], set()), {1: 4.0, 2: 1.5}
		)

	def test_overlapp_ger_hogsta_nivan(self):
		self.assertEqual(fordela([(dt(LORDAG, 20), dt(LORDAG, 23))], [OB1, OB2, OB3], set()), {3: 3.0})

	def test_regel_fran_dagen_fore(self):
		tisdag = date(2026, 9, 15)
		self.assertEqual(fordela([(dt(tisdag, 0), dt(tisdag, 2))], [OB1, OB2], set()), {2: 2.0})

	def test_juldagen_som_helgdag(self):
		self.assertEqual(
			fordela([(dt(JULDAGEN, 10), dt(JULDAGEN, 14))], [OB1, OB2, OB3], {JULDAGEN}), {3: 4.0}
		)

	def test_overtid_over_tva_nivaer(self):
		self.assertEqual(
			fordela([(dt(MANDAG, 18), dt(MANDAG, 21))], [OT1, OT2], set(), standardniva=1), {1: 2.0, 2: 1.0}
		)

	def test_overtid_utan_regel_far_niva_1(self):
		self.assertEqual(fordela([(dt(MANDAG, 17), dt(MANDAG, 19))], [OT2], set(), standardniva=1), {1: 2.0})

	def test_ob_utan_regel_ger_inget(self):
		self.assertEqual(fordela([(dt(MANDAG, 9), dt(MANDAG, 12))], [OB1, OB2], set()), {})

	def test_extra_tid_fore_och_efter_skiftet(self):
		self.assertEqual(
			extra_tid((dt(MANDAG, 7), dt(MANDAG, 18, 30)), (dt(MANDAG, 8), dt(MANDAG, 16, 30))),
			[(dt(MANDAG, 7), dt(MANDAG, 8)), (dt(MANDAG, 16, 30), dt(MANDAG, 18, 30))],
		)

	def test_ingen_extra_tid_utan_skift(self):
		self.assertEqual(extra_tid((dt(MANDAG, 7), dt(MANDAG, 19)), None), [])

	def test_mertid_upp_till_heltid(self):
		extra = [(dt(MANDAG, 16, 30), dt(MANDAG, 18, 30))]
		self.assertEqual(dela_mertid(extra, 4, 8), (extra, []))
		self.assertEqual(
			dela_mertid(extra, 7, 8),
			([(dt(MANDAG, 16, 30), dt(MANDAG, 17, 30))], [(dt(MANDAG, 17, 30), dt(MANDAG, 18, 30))]),
		)

	def test_ingen_mertid_nar_skiftet_redan_ar_heltid(self):
		extra = [(dt(MANDAG, 16, 30), dt(MANDAG, 18, 30))]
		self.assertEqual(dela_mertid(extra, 8.5, 8), ([], extra))

	def test_timmar(self):
		self.assertEqual(timmar([(dt(MANDAG, 7), dt(MANDAG, 8)), (dt(MANDAG, 16, 30), dt(MANDAG, 18))]), 2.5)
