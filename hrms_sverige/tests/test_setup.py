import frappe
from frappe.tests import IntegrationTestCase

from hrms_sverige.tests.utils import COMPANY, ensure_test_company, make_test_employee


class TestInstall(IntegrationTestCase):
	def test_hrms_installed_before_us(self):
		apps = frappe.get_installed_apps()
		self.assertLess(apps.index("hrms"), apps.index("hrms_sverige"))

	def test_test_employee(self):
		ensure_test_company()
		name = make_test_employee("Rök")
		self.assertEqual(frappe.db.get_value("Employee", name, "company"), COMPANY)
