from datetime import date
from unittest.mock import patch

from frappe.tests import UnitTestCase

from hrms_sverige.hr.personnummer import OgiltigtPersonnummer, luhn_ok, normalize

TODAY = date(2026, 9, 30)


class TestPersonnummer(UnitTestCase):
	def test_luhn(self):
		self.assertTrue(luhn_ok("8112189876"))
		self.assertFalse(luhn_ok("8112189875"))

	def test_valid_formats_normalize(self):
		for value in (
			"811218-9876",
			"8112189876",
			"19811218-9876",
			"198112189876",
			" 19811218 - 9876 ",
		):
			self.assertEqual(normalize(value, TODAY), "19811218-9876", value)

	def test_century_without_plus(self):
		self.assertEqual(normalize("121212-1212", TODAY), "20121212-1212")

	def test_plus_means_hundred_years_or_older(self):
		self.assertEqual(normalize("121212+1212", TODAY), "19121212-1212")

	def test_ten_digits_future_date_goes_back_a_century(self):
		self.assertEqual(normalize("261201-1235", TODAY), "19261201-1235")

	def test_samordningsnummer(self):
		self.assertEqual(normalize("701063-2391", TODAY), "19701063-2391")

	def test_invalid(self):
		for value in (
			"811218-9875",  # fel kontrollsiffra
			"200230-1238",  # 30 februari, rätt kontrollsiffra
			"20261201-1235",  # 12 siffror i framtiden
			"12345",
			"abcdef-ghij",
			"",
		):
			with self.assertRaises(OgiltigtPersonnummer, msg=value):
				normalize(value, TODAY)

	def test_dash_variants_accepted(self):
		for value in ("811218–9876", "811218—9876", "811218−9876"):  # noqa: RUF001
			self.assertEqual(normalize(value, TODAY), "19811218-9876", value)

	def test_twelve_digits_with_plus_requires_hundred_years(self):
		self.assertEqual(normalize("19121212+1212", TODAY), "19121212-1212")
		with self.assertRaises(OgiltigtPersonnummer):
			normalize("19811218+9876", TODAY)

	def test_default_today_uses_site_date(self):
		with patch("hrms_sverige.hr.personnummer.getdate", return_value=date(2026, 9, 30)):
			self.assertEqual(normalize("261201-1235"), "19261201-1235")
