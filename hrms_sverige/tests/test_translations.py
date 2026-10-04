import frappe
from frappe.tests import UnitTestCase

from hrms_sverige.scripts.sarskrivningar import find_candidates, find_conflicts, find_untranslated_labels

IN_SCOPE = ("Leave", "Attendance", "Shift", "Check", "Holiday", "Compensatory", "Employment", "Half Day")


class TestTranslations(UnitTestCase):
	def test_glossary(self):
		previous = frappe.local.lang
		frappe.local.lang = "sv"
		try:
			self.assertEqual(frappe._("Leave Allocation"), "Frånvarotilldelning")
			self.assertEqual(frappe._("Shift Type"), "Skifttyp")
			self.assertEqual(frappe._("Employment Type"), "Anställningsform")
			self.assertEqual(frappe._("Uploading..."), "Laddar upp...")
			self.assertEqual(frappe._("Allocated Leaves"), "Tilldelad ledighet")
			self.assertEqual(frappe._("Employee Number"), "Anställningsnummer")
		finally:
			frappe.local.lang = previous

	def test_no_title_case_in_scope(self):
		left = [
			c["msgid"]
			for c in find_candidates(title_case_only=True)
			if any(word in c["msgid"] for word in IN_SCOPE)
		]
		self.assertEqual(left, [])

	def test_no_conflicts_with_erpnext_sverige(self):
		self.assertEqual(find_conflicts(), [])

	def test_visible_labels_translated(self):
		self.assertEqual(find_untranslated_labels(), [])
