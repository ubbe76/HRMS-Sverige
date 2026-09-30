import frappe
from frappe.tests import IntegrationTestCase

from hrms_sverige.setup.holidays import create_holiday_list
from hrms_sverige.setup.leave import (
	LEAVE_TYPES,
	SEMESTER,
	ensure_leave_period,
	ensure_leave_types,
	ensure_semester_policy,
)
from hrms_sverige.tests.utils import COMPANY, ensure_test_company, make_test_employee


class TestLeaveSetup(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_test_company()
		ensure_leave_types()

	def test_leave_types(self):
		for name in LEAVE_TYPES:
			self.assertTrue(frappe.db.exists("Leave Type", name), name)
		semester = frappe.get_doc("Leave Type", SEMESTER)
		self.assertEqual(semester.is_carry_forward, 1)
		self.assertEqual(semester.maximum_carry_forwarded_leaves, 5)
		self.assertEqual(semester.expire_carry_forwarded_leaves_after_days, 1826)
		self.assertEqual(semester.include_holiday, 0)
		self.assertEqual(frappe.db.get_value("Leave Type", "Kompledighet", "is_compensatory"), 1)

	def test_idempotent(self):
		ensure_leave_types()
		p1 = ensure_semester_policy()
		p2 = ensure_semester_policy()
		self.assertEqual(p1, p2)
		l1 = ensure_leave_period(2030, COMPANY)
		l2 = ensure_leave_period(2030, COMPANY)
		self.assertEqual(l1, l2)
		self.assertEqual(frappe.db.count("Leave Type", {"name": SEMESTER}), 1)

	def test_sick_leave_without_allocation(self):
		frappe.db.set_single_value("HR Settings", "leave_approver_mandatory_in_leave_application", 0)
		create_holiday_list(2026, COMPANY)
		employee = make_test_employee("Sjuk")
		application = frappe.get_doc(
			{
				"doctype": "Leave Application",
				"employee": employee,
				"company": COMPANY,
				"leave_type": "Sjukfrånvaro",
				"from_date": "2026-03-02",
				"to_date": "2026-03-03",
				"posting_date": "2026-03-02",
				"status": "Open",
			}
		).insert()
		self.assertEqual(application.total_leave_days, 2)

	def test_admin_edits_survive_setup(self):
		frappe.db.set_value("Leave Type", SEMESTER, "maximum_carry_forwarded_leaves", 3)
		try:
			ensure_leave_types()
			self.assertEqual(frappe.db.get_value("Leave Type", SEMESTER, "maximum_carry_forwarded_leaves"), 3)
		finally:
			frappe.db.set_value("Leave Type", SEMESTER, "maximum_carry_forwarded_leaves", 5)

	def test_overlapping_leave_period_is_respected(self):
		own = frappe.get_doc(
			{
				"doctype": "Leave Period",
				"company": COMPANY,
				"from_date": "2037-04-01",
				"to_date": "2038-03-31",
				"is_active": 1,
			}
		).insert()
		self.assertEqual(ensure_leave_period(2037, COMPANY), own.name)

	def test_unused_hrms_leave_types_are_removed(self):
		from hrms_sverige.setup.leave import HRMS_DEFAULT_LEAVE_TYPES, remove_unused_hrms_leave_types

		for name in HRMS_DEFAULT_LEAVE_TYPES:
			if not frappe.db.exists("Leave Type", name):
				frappe.get_doc({"doctype": "Leave Type", "leave_type_name": name}).insert()
		employee = make_test_employee("Engelsk")
		frappe.get_doc(
			{
				"doctype": "Leave Allocation",
				"employee": employee,
				"leave_type": "Casual Leave",
				"from_date": "2039-01-01",
				"to_date": "2039-12-31",
				"new_leaves_allocated": 5,
			}
		).insert()

		remove_unused_hrms_leave_types()

		self.assertTrue(frappe.db.exists("Leave Type", "Casual Leave"))  # används, behålls
		for name in set(HRMS_DEFAULT_LEAVE_TYPES) - {"Casual Leave"}:
			self.assertFalse(frappe.db.exists("Leave Type", name), name)
		for name in LEAVE_TYPES:
			self.assertTrue(frappe.db.exists("Leave Type", name), name)
