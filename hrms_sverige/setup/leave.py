"""Svenska frånvarotyper, ledighetsperiod per kalenderår och semesterpolicy (25 dagar)."""

from datetime import date

import frappe

SEMESTER = "Semester"
KOMPLEDIGHET = "Kompledighet"
ARLIG_SEMESTER = 25
SEMESTER_POLICY_TITLE = "Semester 25 dagar"

# Semesterlagen: dagar utöver 20 får sparas (max 5/år) och tas ut inom fem år.
LEAVE_TYPES = {
	SEMESTER: {
		"is_lwp": 0,
		"include_holiday": 0,
		"is_carry_forward": 1,
		"maximum_carry_forwarded_leaves": 5,
		"expire_carry_forwarded_leaves_after_days": 1826,
		"allow_encashment": 0,
	},
	# is_lwp: ansökan kräver ingen tilldelning. Utan lönemodul påverkar flaggan inget annat.
	"Sjukfrånvaro": {"is_lwp": 1, "include_holiday": 0},
	"VAB": {"is_lwp": 1, "include_holiday": 0},
	"Föräldraledighet": {"is_lwp": 1, "include_holiday": 0},
	"Tjänstledighet": {"is_lwp": 1, "include_holiday": 0},
	KOMPLEDIGHET: {"is_compensatory": 1, "is_lwp": 0, "include_holiday": 0},
}


def ensure_leave_types():
	for name, settings in LEAVE_TYPES.items():
		if frappe.db.exists("Leave Type", name):
			doc = frappe.get_doc("Leave Type", name)
		else:
			doc = frappe.new_doc("Leave Type")
			doc.leave_type_name = name
		doc.update(settings)
		doc.save(ignore_permissions=True)


def ensure_leave_period(year: int, company: str) -> str:
	from_date, to_date = date(year, 1, 1), date(year, 12, 31)
	existing = frappe.db.get_value(
		"Leave Period", {"company": company, "from_date": from_date, "to_date": to_date}
	)
	if existing:
		return existing
	doc = frappe.get_doc(
		{
			"doctype": "Leave Period",
			"company": company,
			"from_date": from_date,
			"to_date": to_date,
			"is_active": 1,
		}
	).insert(ignore_permissions=True)
	return doc.name


def ensure_semester_policy() -> str:
	existing = frappe.db.get_value("Leave Policy", {"title": SEMESTER_POLICY_TITLE, "docstatus": 1})
	if existing:
		return existing
	doc = frappe.get_doc(
		{
			"doctype": "Leave Policy",
			"title": SEMESTER_POLICY_TITLE,
			"leave_policy_details": [{"leave_type": SEMESTER, "annual_allocation": ARLIG_SEMESTER}],
		}
	)
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc.name
