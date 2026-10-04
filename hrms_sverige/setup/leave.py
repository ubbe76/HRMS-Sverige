"""Svenska frånvarotyper, ledighetsperiod per kalenderår och semesterpolicy (25 dagar)."""

from datetime import date

import frappe

SEMESTER = "Semester"
KOMPLEDIGHET = "Kompledighet"
ARBETSTIDSKONTO = "Arbetstidskonto"
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
	# Teknikavtalets arbetstidskonto uttaget som ledighet. Saldot förs i lönesystemet.
	ARBETSTIDSKONTO: {"is_lwp": 1, "include_holiday": 0},
}


# Skapas av HRMS vid installation. Bara exakta engelska namn: översatta namn kan krocka med våra
# (HRMS "Sick Leave" översätts till "Sjukfrånvaro").
HRMS_DEFAULT_LEAVE_TYPES = (
	"Casual Leave",
	"Compensatory Off",
	"Sick Leave",
	"Privilege Leave",
	"Leave Without Pay",
)

# Standardkoder för frånvaro i PAXml 2.0. Lönesystemet (t.ex. Crona Lön) kopplar dem till lönearter.
PAXML_TIDKODER = {
	SEMESTER: "SEM",
	"Sjukfrånvaro": "SJK",
	"VAB": "VAB",
	"Föräldraledighet": "FPE",
	"Tjänstledighet": "TJL",
	KOMPLEDIGHET: "KOM",
	ARBETSTIDSKONTO: "ATK",
}


def remove_unused_hrms_leave_types():
	"""Ta bort HRMS engelska standardtyper som inte används; de som är länkade behålls."""
	for name in HRMS_DEFAULT_LEAVE_TYPES:
		if not frappe.db.exists("Leave Type", name):
			continue
		try:
			frappe.delete_doc("Leave Type", name, ignore_permissions=True)
		except frappe.LinkExistsError:
			frappe.clear_last_message()


def ensure_leave_types(names=None):
	"""Skapa saknade frånvarotyper (alla, eller bara `names`). Befintliga rörs inte, så HR:s ändringar
	ligger kvar."""
	for name, settings in LEAVE_TYPES.items():
		if names is not None and name not in names:
			continue
		if frappe.db.exists("Leave Type", name):
			continue
		doc = frappe.new_doc("Leave Type")
		doc.leave_type_name = name
		doc.update(settings)
		doc.insert(ignore_permissions=True)


def ensure_leave_period(year: int, company: str) -> str:
	"""Kalenderårets frånvaroperiod. Finns redan en period som överlappar året (t.ex. en egen
	brytning 1 april) returneras den i stället; HRMS tillåter inte överlappande perioder."""
	from_date, to_date = date(year, 1, 1), date(year, 12, 31)
	existing = frappe.db.get_value(
		"Leave Period",
		{"company": company, "from_date": ("<=", to_date), "to_date": (">=", from_date)},
		order_by="from_date asc",
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


def ensure_paxml_tidkoder():
	"""Sätt PAXml-tidkod på appens frånvarotyper där den saknas. Ändrade koder lämnas orörda."""
	for leave_type, kod in PAXML_TIDKODER.items():
		if frappe.db.exists("Leave Type", leave_type) and not frappe.db.get_value(
			"Leave Type", leave_type, "paxml_tidkod"
		):
			frappe.db.set_value("Leave Type", leave_type, "paxml_tidkod", kod)
