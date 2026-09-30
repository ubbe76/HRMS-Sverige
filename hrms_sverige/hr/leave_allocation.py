"""Semester vid deltid: 25 dagar räknas om till uttagsdagar efter arbetsdagar per vecka."""

import math

import frappe
from frappe.utils import flt

from hrms_sverige.hr.personnummer import HELTID_DAGAR
from hrms_sverige.setup.leave import SEMESTER


def semesterdagar(dagar: float, arbetsdagar_per_vecka: int | None) -> float:
	arbetsdagar = arbetsdagar_per_vecka or HELTID_DAGAR
	if arbetsdagar >= HELTID_DAGAR:
		return dagar
	# round() först så att flyttalsfel (15.000000001) inte avrundas upp till 16
	return math.ceil(round(dagar * arbetsdagar / HELTID_DAGAR, 6))


def justera_for_deltid(doc, method=None):
	"""Leave Allocation.before_insert: bara semester som skapas från en policykoppling."""
	if doc.leave_type != SEMESTER or not doc.leave_policy_assignment:
		return
	# Ändrad eller kopierad tilldelning: originalet finns redan och är redan omräknat.
	if frappe.db.exists(
		"Leave Allocation",
		{"leave_policy_assignment": doc.leave_policy_assignment, "leave_type": doc.leave_type},
	):
		return
	arbetsdagar = frappe.db.get_value("Employee", doc.employee, "arbetsdagar_per_vecka")
	doc.new_leaves_allocated = semesterdagar(doc.new_leaves_allocated, arbetsdagar)


def begransa_sparade_dagar(doc, method=None):
	"""Leave Allocation.validate: taket för sparade dagar (frånvarotypens max, 5) räknas om vid deltid
	på samma sätt som semesterdagarna, t.ex. 3 dagar för den som arbetar 3 dagar i veckan."""
	if doc.leave_type != SEMESTER or not doc.carry_forward or not doc.unused_leaves:
		return
	arbetsdagar = frappe.db.get_value("Employee", doc.employee, "arbetsdagar_per_vecka")
	maximum = frappe.db.get_value("Leave Type", SEMESTER, "maximum_carry_forwarded_leaves")
	if not maximum:
		return
	tak = semesterdagar(maximum, arbetsdagar)
	if doc.unused_leaves > tak:
		doc.unused_leaves = tak
		doc.total_leaves_allocated = flt(doc.new_leaves_allocated) + tak
