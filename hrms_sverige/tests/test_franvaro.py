from datetime import date
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from hrms_sverige.lon.franvaro import dela_upp, rader_for_period
from hrms_sverige.setup.holidays import create_holiday_list
from hrms_sverige.setup.leave import ensure_leave_types
from hrms_sverige.tests.utils import COMPANY, ensure_test_company, make_leave_application, make_test_employee

SEPT = (date(2026, 9, 1), date(2026, 9, 30))


class TestDelaUpp(UnitTestCase):
	def test_hela_dagar(self):
		self.assertEqual(
			dela_upp(date(2026, 9, 14), date(2026, 9, 16), None, *SEPT),
			[(date(2026, 9, 14), date(2026, 9, 16), 100)],
		)

	def test_klipps_vid_manadsskifte(self):
		self.assertEqual(
			dela_upp(date(2026, 8, 28), date(2026, 9, 2), None, *SEPT),
			[(date(2026, 9, 1), date(2026, 9, 2), 100)],
		)

	def test_halvdag_mitt_i(self):
		self.assertEqual(
			dela_upp(date(2026, 9, 14), date(2026, 9, 18), date(2026, 9, 16), *SEPT),
			[
				(date(2026, 9, 14), date(2026, 9, 15), 100),
				(date(2026, 9, 16), date(2026, 9, 16), 50),
				(date(2026, 9, 17), date(2026, 9, 18), 100),
			],
		)

	def test_halvdag_forst(self):
		self.assertEqual(
			dela_upp(date(2026, 9, 14), date(2026, 9, 16), date(2026, 9, 14), *SEPT),
			[(date(2026, 9, 14), date(2026, 9, 14), 50), (date(2026, 9, 15), date(2026, 9, 16), 100)],
		)

	def test_ensam_halvdag(self):
		self.assertEqual(
			dela_upp(date(2026, 9, 14), date(2026, 9, 14), date(2026, 9, 14), *SEPT),
			[(date(2026, 9, 14), date(2026, 9, 14), 50)],
		)

	def test_halvdag_utanfor_perioden_klipps_bort(self):
		# Halvdagen 31 aug hör till augusti; september får bara hela dagar
		self.assertEqual(
			dela_upp(date(2026, 8, 31), date(2026, 9, 2), date(2026, 8, 31), *SEPT),
			[(date(2026, 9, 1), date(2026, 9, 2), 100)],
		)

	def test_helt_utanfor(self):
		self.assertEqual(dela_upp(date(2026, 8, 3), date(2026, 8, 5), None, *SEPT), [])


class TestRaderForPeriod(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_test_company()
		ensure_leave_types()
		create_holiday_list(2026, COMPANY)

	def egna(self, anstallda, period=SEPT, company=COMPANY):
		return [r for r in rader_for_period(company, *period) if r["employee"] in anstallda]

	def test_godkand_franvaro_blir_rader(self):
		anstalld = make_test_employee("Rad Ett", employee_number="R-1")
		ansokan = make_leave_application(anstalld, "Sjukfrånvaro", "2026-09-14", "2026-09-16")
		self.assertEqual(
			self.egna([anstalld]),
			[
				{
					"employee": anstalld,
					"leave_type": "Sjukfrånvaro",
					"from_date": date(2026, 9, 14),
					"to_date": date(2026, 9, 16),
					"omfattning": 100,
					"leave_application": ansokan,
				}
			],
		)

	def test_halvdag_ger_egen_rad(self):
		anstalld = make_test_employee("Rad Halv", employee_number="R-2")
		make_leave_application(
			anstalld, "VAB", "2026-09-21", "2026-09-23", half_day=1, half_day_date="2026-09-22"
		)
		self.assertEqual(
			[(r["from_date"], r["to_date"], r["omfattning"]) for r in self.egna([anstalld])],
			[
				(date(2026, 9, 21), date(2026, 9, 21), 100),
				(date(2026, 9, 22), date(2026, 9, 22), 50),
				(date(2026, 9, 23), date(2026, 9, 23), 100),
			],
		)

	def test_ej_godkand_och_makulerad_kommer_inte_med(self):
		anstalld = make_test_employee("Rad Utkast", employee_number="R-3")
		make_leave_application(anstalld, "Sjukfrånvaro", "2026-09-07", "2026-09-07", submit=False)
		makulerad = make_leave_application(anstalld, "Sjukfrånvaro", "2026-09-09", "2026-09-09")
		frappe.get_doc("Leave Application", makulerad).cancel()
		self.assertEqual(self.egna([anstalld]), [])

	def test_annat_bolag_kommer_inte_med(self):
		anstalld = make_test_employee("Rad Bolag", employee_number="R-4")
		make_leave_application(anstalld, "Sjukfrånvaro", "2026-09-24", "2026-09-24")
		self.assertEqual(self.egna([anstalld], company="Annat bolag AB"), [])

	def test_sorteras_pa_anstallningsnummer(self):
		b = make_test_employee("Rad Sort B", employee_number="S-2")
		a = make_test_employee("Rad Sort A", employee_number="S-1")
		make_leave_application(b, "Sjukfrånvaro", "2026-09-01", "2026-09-01")
		make_leave_application(a, "Sjukfrånvaro", "2026-09-02", "2026-09-02")
		self.assertEqual([r["employee"] for r in self.egna([a, b])], [a, b])


class TestVarningExporteradPeriod(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		from hrms_sverige.setup.custom_fields import create_custom_fields
		from hrms_sverige.setup.leave import ensure_paxml_tidkoder

		ensure_test_company()
		create_custom_fields()
		ensure_leave_types()
		ensure_paxml_tidkoder()
		create_holiday_list(2032, COMPANY)
		cls.anstalld = make_test_employee("Varning", employee_number="V-1")
		underlag = frappe.get_doc(
			{"doctype": "Loneunderlag", "company": COMPANY, "ar": 2032, "manad": "Augusti"}
		)
		underlag.append(
			"rader",
			{
				"employee": cls.anstalld,
				"leave_type": "Sjukfrånvaro",
				"from_date": "2032-08-03",
				"to_date": "2032-08-03",
				"omfattning": 100,
			},
		)
		underlag.insert()
		underlag.submit()

	def varnade(self, msgprint):
		return any("redan exporterad" in str(c) for c in msgprint.call_args_list)

	def test_varning_vid_godkannande_i_exporterad_manad(self):
		with patch("frappe.msgprint") as msgprint:
			make_leave_application(self.anstalld, "Sjukfrånvaro", "2032-08-10", "2032-08-10")
		self.assertTrue(self.varnade(msgprint))

	def test_varning_vid_makulering(self):
		ansokan = make_leave_application(self.anstalld, "Sjukfrånvaro", "2032-08-12", "2032-08-12")
		with patch("frappe.msgprint") as msgprint:
			frappe.get_doc("Leave Application", ansokan).cancel()
		self.assertTrue(self.varnade(msgprint))

	def test_ingen_varning_i_annan_manad(self):
		with patch("frappe.msgprint") as msgprint:
			make_leave_application(self.anstalld, "Sjukfrånvaro", "2032-10-05", "2032-10-05")
		self.assertFalse(self.varnade(msgprint))
