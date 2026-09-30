from datetime import date

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from hrms_sverige.setup.holidays import create_holiday_list, holiday_list_name, svenska_helgdagar
from hrms_sverige.tests.utils import COMPANY, ensure_test_company

KNOWN = {
	2025: {
		"Långfredagen": date(2025, 4, 18),
		"Midsommardagen": date(2025, 6, 21),
		"Alla helgons dag": date(2025, 11, 1),
	},
	2026: {
		"Långfredagen": date(2026, 4, 3),
		"Midsommardagen": date(2026, 6, 20),
		"Alla helgons dag": date(2026, 10, 31),
	},
	2027: {
		"Långfredagen": date(2027, 3, 26),
		"Midsommardagen": date(2027, 6, 26),
		"Alla helgons dag": date(2027, 11, 6),
	},
	2028: {
		"Långfredagen": date(2028, 4, 14),
		"Midsommardagen": date(2028, 6, 24),
		"Alla helgons dag": date(2028, 11, 4),
	},
}


class TestSvenskaHelgdagar(UnitTestCase):
	def test_known_dates(self):
		for year, expected in KNOWN.items():
			by_name = {name: day for day, name in svenska_helgdagar(year).items()}
			for name, day in expected.items():
				self.assertEqual(by_name[name], day, f"{name} {year}")

	def test_aftnar(self):
		with_eves = svenska_helgdagar(2026)
		without = svenska_helgdagar(2026, aftnar=False)
		for day in (date(2026, 6, 19), date(2026, 12, 24), date(2026, 12, 31)):
			self.assertIn(day, with_eves)
			self.assertNotIn(day, without)
		self.assertEqual(len(without), 13)  # röda dagar; söndagar räknas inte som helgdag i sig


class TestHolidayList(IntegrationTestCase):
	def test_create_is_idempotent_and_assigned(self):
		ensure_test_company()
		name = create_holiday_list(2031, COMPANY)
		self.assertEqual(name, holiday_list_name(2031))
		first = frappe.get_doc("Holiday List", name)
		create_holiday_list(2031, COMPANY)
		second = frappe.get_doc("Holiday List", name)
		self.assertEqual(len(first.holidays), len(second.holidays))
		dates = [h.holiday_date for h in second.holidays]
		self.assertEqual(len(dates), len(set(dates)))
		self.assertIn(date(2031, 12, 24), dates)
		self.assertIn(date(2031, 1, 4), dates)  # lördag = veckovila
		self.assertEqual(
			frappe.db.count(
				"Holiday List Assignment",
				{"assigned_to": COMPANY, "from_date": "2031-01-01", "docstatus": 1},
			),
			1,
		)

	def test_existing_assignment_is_respected(self):
		ensure_test_company()
		own = frappe.get_doc(
			{
				"doctype": "Holiday List",
				"holiday_list_name": "_Test Egen lista 2032",
				"from_date": "2032-01-01",
				"to_date": "2032-12-31",
			}
		).insert()
		frappe.get_doc(
			{
				"doctype": "Holiday List Assignment",
				"applicable_for": "Company",
				"assigned_to": COMPANY,
				"holiday_list": own.name,
				"from_date": "2032-01-01",
			}
		).submit()
		create_holiday_list(2032, COMPANY)
		assigned = frappe.get_all(
			"Holiday List Assignment",
			{"assigned_to": COMPANY, "from_date": "2032-01-01", "docstatus": 1},
			pluck="holiday_list",
		)
		self.assertEqual(assigned, [own.name])
