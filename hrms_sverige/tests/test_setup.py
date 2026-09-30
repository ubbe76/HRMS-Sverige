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


class TestSetupAll(IntegrationTestCase):
	def test_idempotent(self):
		from hrms_sverige.setup.install import setup_all

		ensure_test_company()
		setup_all(COMPANY)
		doctypes = (
			"Leave Type",
			"Leave Period",
			"Leave Policy",
			"Holiday List",
			"Employment Type",
			"Holiday List Assignment",
		)
		counts = {doctype: frappe.db.count(doctype) for doctype in doctypes}
		setup_all(COMPANY)
		for doctype, count in counts.items():
			self.assertEqual(frappe.db.count(doctype), count, doctype)

	def test_workspaces_hidden(self):
		from hrms_sverige.setup.install import setup_all
		from hrms_sverige.setup.workspaces import HIDDEN

		setup_all(COMPANY)
		for name in HIDDEN:
			if frappe.db.exists("Workspace", name):
				self.assertEqual(frappe.db.get_value("Workspace", name, "is_hidden"), 1, name)
			if frappe.db.exists("Desktop Icon", name):
				self.assertEqual(frappe.db.get_value("Desktop Icon", name, "hidden"), 1, name)
		self.assertEqual(frappe.db.get_value("Workspace", "Leaves", "is_hidden"), 0)
