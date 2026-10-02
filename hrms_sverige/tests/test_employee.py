import frappe
from frappe.tests import IntegrationTestCase

from hrms_sverige.setup.custom_fields import create_custom_fields, ensure_personnummer_permissions
from hrms_sverige.setup.employment_types import EMPLOYMENT_TYPES, ensure_employment_types
from hrms_sverige.tests.utils import make_test_employee

READER = "hrms-sverige-reader@example.com"
HR_READER = "hrms-sverige-hr@example.com"


def free(personnummer: str, keep: str | None = None):
	"""Testanställda återanvänds mellan körningar; ta bort numret från alla andra."""
	frappe.db.set_value(
		"Employee", {"personnummer": personnummer, "name": ("!=", keep or "")}, "personnummer", None
	)


class TestEmployeeFields(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		create_custom_fields()
		ensure_personnummer_permissions()
		ensure_employment_types()

	def test_personnummer_is_normalized(self):
		name = make_test_employee("Pnr")
		free("19811218-9876")
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
		free("19900101-1239")
		name = make_test_employee("Dold", personnummer="19900101-1239")
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
		self.assertEqual(self._personnummer_as(HR_READER, "HR User"), "19900101-1239")

	def test_personnummer_not_in_version_history(self):
		free("19900202-2342")
		doc = frappe.get_doc("Employee", make_test_employee("Historik"))
		doc.personnummer = "900202-2342"
		doc.cell_number = "0701234567"
		doc.save(ignore_version=False)  # Frappe sparar ingen historik i tester annars
		data = frappe.get_all(
			"Version",
			{"ref_doctype": "Employee", "docname": doc.name},
			pluck="data",
			order_by="creation desc",
			limit=1,
		)[0]
		self.assertNotIn("2342", data)
		self.assertIn("0701234567", data)

	def test_migrate_keeps_admin_permission_changes(self):
		from hrms_sverige.setup.install import after_migrate

		perm = frappe.db.get_value(
			"Custom DocPerm", {"parent": "Employee", "role": "HR User", "permlevel": 1}
		)
		frappe.db.set_value("Custom DocPerm", perm, "write", 0)
		after_migrate()
		self.assertEqual(frappe.db.get_value("Custom DocPerm", perm, "write"), 0)

	def test_duplicate_personnummer_rejected(self):
		free("19900303-3454")
		make_test_employee("Först", personnummer="19900303-3454")
		doc = frappe.get_doc("Employee", make_test_employee("Andra"))
		doc.personnummer = "900303-3454"
		self.assertRaises(frappe.ValidationError, doc.save)

	def test_sysselsattningsgrad_range(self):
		doc = frappe.get_doc("Employee", make_test_employee("Grad"))
		doc.sysselsattningsgrad = 120
		self.assertRaises(frappe.ValidationError, doc.save)
		doc = frappe.get_doc("Employee", doc.name)
		doc.sysselsattningsgrad = 75
		doc.save()

	def test_migrate_keeps_label_edits(self):
		from hrms_sverige.setup.install import after_migrate

		name = frappe.db.get_value("Custom Field", {"dt": "Employee", "fieldname": "sysselsattningsgrad"})
		frappe.db.set_value("Custom Field", name, "label", "Tjänstgöringsgrad")
		after_migrate()
		self.assertEqual(frappe.db.get_value("Custom Field", name, "label"), "Tjänstgöringsgrad")


class TestLoneform(IntegrationTestCase):
	def test_loneform_finns_med_manadslon_och_timlon(self):
		from hrms_sverige.setup.custom_fields import create_custom_fields

		create_custom_fields()
		falt = frappe.get_meta("Employee").get_field("loneform")
		self.assertIsNotNone(falt)
		self.assertEqual(falt.fieldtype, "Select")
		self.assertEqual(falt.options.split("\n"), ["", "Månadslön", "Timlön"])
