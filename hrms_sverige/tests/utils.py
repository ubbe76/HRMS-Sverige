"""Gemensamma testdata: ett eget testbolag och testanställda."""

import frappe

COMPANY = "_Test HR Sverige AB"
COMPANY_ABBR = "_THRS"


def before_tests():
	"""Kör installationsguiden med testbolaget på en ny site (t.ex. i CI). Befintliga siter lämnas orörda."""
	from frappe.desk.page.setup_wizard.setup_wizard import setup_complete
	from frappe.utils import now_datetime

	frappe.clear_cache()
	if not frappe.get_list("Company"):
		year = now_datetime().year
		setup_complete(
			{
				"currency": "SEK",
				"full_name": "Test User",
				"company_name": COMPANY,
				"company_abbr": COMPANY_ABBR,
				"timezone": "Europe/Stockholm",
				"country": "Sweden",
				"fy_start_date": f"{year}-01-01",
				"fy_end_date": f"{year}-12-31",
				"language": "english",
				"email": "test@example.com",
				"password": "test",
				"chart_of_accounts": "Standard",
			}
		)
	frappe.db.commit()  # nosemgrep


def ensure_test_company() -> str:
	if not frappe.db.exists("Company", COMPANY):
		frappe.get_doc(
			{
				"doctype": "Company",
				"company_name": COMPANY,
				"abbr": COMPANY_ABBR,
				"country": "Sweden",
				"default_currency": "SEK",
				"create_chart_of_accounts_based_on": "Standard Template",
				"chart_of_accounts": "Standard",
			}
		).insert()
	return COMPANY


def make_test_employee(first_name: str, **fields) -> str:
	"""Skapa (eller hämta) en anställd i testbolaget. `fields` skriver över standardvärdena."""
	ensure_test_company()
	existing = frappe.db.get_value("Employee", {"first_name": first_name, "company": COMPANY})
	if existing:
		if fields:
			frappe.db.set_value("Employee", existing, fields)
		return existing
	doc = frappe.get_doc(
		{
			"doctype": "Employee",
			"first_name": first_name,
			"company": COMPANY,
			"gender": "Female",
			"date_of_birth": "1990-05-08",
			"date_of_joining": "2020-01-01",
			"status": "Active",
		}
	)
	doc.update(fields)
	doc.insert()
	return doc.name


def make_leave_application(
	employee: str,
	leave_type: str,
	from_date: str,
	to_date: str,
	half_day: int = 0,
	half_day_date: str | None = None,
	submit: bool = True,
) -> str:
	"""Godkänd (och inskickad) ledighetsansökan i testbolaget."""
	frappe.db.set_single_value("HR Settings", "leave_approver_mandatory_in_leave_application", 0)
	doc = frappe.get_doc(
		{
			"doctype": "Leave Application",
			"employee": employee,
			"company": COMPANY,
			"leave_type": leave_type,
			"from_date": from_date,
			"to_date": to_date,
			"half_day": half_day,
			"half_day_date": half_day_date,
			"posting_date": from_date,
			"status": "Approved" if submit else "Open",
		}
	).insert()
	if submit:
		doc.submit()
	return doc.name


def make_shift_type(name: str, start_time: str, end_time: str) -> str:
	if not frappe.db.exists("Shift Type", name):
		frappe.get_doc(
			{"doctype": "Shift Type", "__newname": name, "start_time": start_time, "end_time": end_time}
		).insert()
	return name


def assign_shift(employee: str, shift_type: str, start_date: str, end_date: str | None = None) -> str:
	doc = frappe.get_doc(
		{
			"doctype": "Shift Assignment",
			"employee": employee,
			"company": COMPANY,
			"shift_type": shift_type,
			"start_date": start_date,
			"end_date": end_date,
			"status": "Active",
		}
	).insert()
	doc.submit()
	return doc.name


def make_attendance(
	employee: str,
	datum: str,
	working_hours: float,
	status: str = "Present",
	submit: bool = True,
	in_time: str | None = None,
	out_time: str | None = None,
) -> str:
	doc = frappe.get_doc(
		{
			"doctype": "Attendance",
			"employee": employee,
			"company": COMPANY,
			"attendance_date": datum,
			"status": status,
			"working_hours": working_hours,
			"in_time": in_time,
			"out_time": out_time,
		}
	).insert()
	if submit:
		doc.submit()
	return doc.name


def make_checkin(employee: str, tid: str, log_type: str = "IN", skip_auto_attendance: int = 0) -> str:
	return (
		frappe.get_doc(
			{
				"doctype": "Employee Checkin",
				"employee": employee,
				"time": tid,
				"log_type": log_type,
				"skip_auto_attendance": skip_auto_attendance,
			}
		)
		.insert()
		.name
	)


def satt_tidsregler(regler: list[dict], heltid: float = 8) -> None:
	"""Ersätt tidsreglerna i Löneinställningar. Varje regel: typ, niva, dagar (t.ex. "man tis"), fran, till."""
	inst = frappe.get_single("Loneinstallningar")
	inst.heltid_per_dag = heltid
	inst.set("tidsregler", [])
	for regel in regler:
		rad = {"typ": regel["typ"], "niva": regel["niva"], "fran": regel["fran"], "till": regel["till"]}
		for dag in regel["dagar"].split():
			rad[dag] = 1
		inst.append("tidsregler", rad)
	inst.save()
