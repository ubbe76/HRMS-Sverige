import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from hrms_sverige.hr.leave_allocation import semesterdagar
from hrms_sverige.setup.custom_fields import create_custom_fields
from hrms_sverige.setup.holidays import create_holiday_list
from hrms_sverige.setup.leave import (
	SEMESTER,
	ensure_leave_period,
	ensure_leave_types,
	ensure_semester_policy,
)
from hrms_sverige.tests.utils import COMPANY, ensure_test_company, make_test_employee

YEAR = 2026


class TestSemesterdagar(UnitTestCase):
	def test_values(self):
		self.assertEqual(semesterdagar(25, 5), 25)
		self.assertEqual(semesterdagar(25, 4), 20)
		self.assertEqual(semesterdagar(25, 3), 15)
		self.assertEqual(semesterdagar(25, None), 25)
		self.assertEqual(semesterdagar(25, 0), 25)
		self.assertEqual(semesterdagar(12.5, 3), 8)  # 7,5 avrundas uppåt
		self.assertEqual(semesterdagar(12.5, 5), 12.5)  # heltid lämnas orörd


class TestDeltidAllocation(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_test_company()
		create_custom_fields()
		ensure_leave_types()
		create_holiday_list(YEAR, COMPANY)
		cls.leave_period = ensure_leave_period(YEAR, COMPANY)
		cls.policy = ensure_semester_policy()

	def _clean(self, employee):
		"""Testanställda återanvänds mellan körningar; HRMS vägrar överlappande tilldelningar."""
		for doctype in ("Leave Ledger Entry", "Leave Allocation", "Leave Policy Assignment"):
			frappe.db.delete(doctype, {"employee": employee})

	def _assign(self, employee):
		self._clean(employee)
		assignment = frappe.get_doc(
			{
				"doctype": "Leave Policy Assignment",
				"employee": employee,
				"company": COMPANY,
				"leave_policy": self.policy,
				"assignment_based_on": "Leave Period",
				"leave_period": self.leave_period,
				"effective_from": f"{YEAR}-01-01",
				"effective_to": f"{YEAR}-12-31",
			}
		)
		assignment.submit()
		return frappe.db.get_value(
			"Leave Allocation",
			{"employee": employee, "leave_type": SEMESTER, "leave_policy_assignment": assignment.name},
			["new_leaves_allocated", "total_leaves_allocated"],
		)

	def test_part_time_three_days(self):
		self.assertEqual(self._assign(make_test_employee("Deltid3", arbetsdagar_per_vecka=3)), (15, 15))

	def test_full_time_empty_field(self):
		self.assertEqual(self._assign(make_test_employee("Heltid")), (25, 25))

	def test_manual_allocation_untouched(self):
		employee = make_test_employee("Manuell", arbetsdagar_per_vecka=3)
		self._clean(employee)
		allocation = frappe.get_doc(
			{
				"doctype": "Leave Allocation",
				"employee": employee,
				"leave_type": SEMESTER,
				"from_date": f"{YEAR}-01-01",
				"to_date": f"{YEAR}-12-31",
				"new_leaves_allocated": 25,
			}
		).insert()
		self.assertEqual(allocation.new_leaves_allocated, 25)

	def test_other_leave_type_untouched(self):
		employee = make_test_employee("Komp", arbetsdagar_per_vecka=3)
		self._clean(employee)
		allocation = frappe.get_doc(
			{
				"doctype": "Leave Allocation",
				"employee": employee,
				"leave_type": "Kompledighet",
				"from_date": f"{YEAR}-01-01",
				"to_date": f"{YEAR}-12-31",
				"new_leaves_allocated": 10,
			}
		).insert()
		self.assertEqual(allocation.new_leaves_allocated, 10)

	def test_amended_allocation_not_scaled_twice(self):
		employee = make_test_employee("Ändrad", arbetsdagar_per_vecka=3)
		self._assign(employee)
		original = frappe.get_doc(
			"Leave Allocation",
			frappe.db.get_value("Leave Allocation", {"employee": employee, "leave_type": SEMESTER}),
		)
		original.cancel()
		amended = frappe.copy_doc(original)
		amended.amended_from = original.name
		amended.docstatus = 0
		amended.insert()
		self.assertEqual(amended.new_leaves_allocated, 15)

	def _manual(self, employee, year, days, carry_forward=0):
		doc = frappe.get_doc(
			{
				"doctype": "Leave Allocation",
				"employee": employee,
				"leave_type": SEMESTER,
				"from_date": f"{year}-01-01",
				"to_date": f"{year}-12-31",
				"new_leaves_allocated": days,
				"carry_forward": carry_forward,
			}
		)
		doc.insert()
		doc.submit()
		return doc

	def test_carry_forward_limit_scaled_for_part_time(self):
		employee = make_test_employee("Spara3", arbetsdagar_per_vecka=3)
		self._clean(employee)
		self._manual(employee, 2040, 15)
		allocation = self._manual(employee, 2041, 15, carry_forward=1)
		self.assertEqual(allocation.unused_leaves, 3)  # 5 * 3/5
		self.assertEqual(allocation.total_leaves_allocated, 18)

	def test_carry_forward_limit_full_time(self):
		employee = make_test_employee("Spara5")
		self._clean(employee)
		self._manual(employee, 2040, 25)
		allocation = self._manual(employee, 2041, 25, carry_forward=1)
		self.assertEqual(allocation.unused_leaves, 5)
