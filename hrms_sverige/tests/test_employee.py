import frappe
from frappe.tests import IntegrationTestCase

from hrms_sverige.setup.custom_fields import create_custom_fields
from hrms_sverige.setup.employment_types import EMPLOYMENT_TYPES, ensure_employment_types
from hrms_sverige.tests.utils import make_test_employee

READER = "hrms-sverige-reader@example.com"
HR_READER = "hrms-sverige-hr@example.com"


class TestEmployeeFields(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		create_custom_fields()
		ensure_employment_types()

	def test_personnummer_is_normalized(self):
		name = make_test_employee("Pnr")
		doc = frappe.get_doc("Employee", name)
		doc.personnummer = "811218-9876"
		doc.save()
		self.assertEqual(doc.personnummer, "19811218-9876")

	def test_invalid_personnummer_is_rejected(self):
		doc = frappe.get_doc("Employee", make_test_employee("PnrFel"))
		doc.personnummer = "811218-9875"
		self.assertRaises(frappe.ValidationError, doc.save)

	def test_empty_fields_are_allowed(self):
		doc = frappe.get_doc("Employee", make_test_employee("Tom"))
		doc.personnummer = ""
		doc.arbetsdagar_per_vecka = 0
		doc.save()

	def test_arbetsdagar_out_of_range(self):
		doc = frappe.get_doc("Employee", make_test_employee("Dagar"))
		doc.arbetsdagar_per_vecka = 6
		self.assertRaises(frappe.ValidationError, doc.save)

	def test_employment_types_exist(self):
		for name in EMPLOYMENT_TYPES:
			self.assertTrue(frappe.db.exists("Employment Type", name), name)

	def _personnummer_as(self, email, role):
		name = make_test_employee("Dold", personnummer="19811218-9876")
		if not frappe.db.exists("User", email):
			user = frappe.get_doc(
				{"doctype": "User", "email": email, "first_name": role, "send_welcome_email": 0}
			).insert()
			user.add_roles(role)
		frappe.set_user(email)
		try:
			doc = frappe.get_doc("Employee", name)
			doc.apply_fieldlevel_read_permissions()
			return doc.get("personnummer")
		finally:
			frappe.set_user("Administrator")

	def test_personnummer_hidden_without_hr_role(self):
		# Accounts User har läsrätt på Employee, nivå 0
		self.assertFalse(self._personnummer_as(READER, "Accounts User"))

	def test_personnummer_visible_for_hr_user(self):
		self.assertEqual(self._personnummer_as(HR_READER, "HR User"), "19811218-9876")
