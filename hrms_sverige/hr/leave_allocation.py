"""Semester vid deltid: 25 dagar räknas om till uttagsdagar efter arbetsdagar per vecka."""

import math

import frappe

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
	arbetsdagar = frappe.db.get_value("Employee", doc.employee, "arbetsdagar_per_vecka")
	doc.new_leaves_allocated = semesterdagar(doc.new_leaves_allocated, arbetsdagar)
