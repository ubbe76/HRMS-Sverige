"""Svenska helgdagslistor: röda dagar plus midsommarafton, julafton och nyårsafton."""

from datetime import date, timedelta

import erpnext
import frappe
import holidays

SATURDAY, SUNDAY = 5, 6
WEEKDAY_NAMES = {SATURDAY: "Lördag", SUNDAY: "Söndag"}


def svenska_helgdagar(year: int, aftnar: bool = True) -> dict[date, str]:
	categories = ("public", "de_facto") if aftnar else ("public",)
	days = holidays.Sweden(years=year, include_sundays=False, language="sv", categories=categories)
	return dict(sorted(days.items()))


def holiday_list_name(year: int) -> str:
	return f"Sverige {year}"


def create_holiday_list(year: int, company: str | None = None, aftnar: bool = True) -> str:
	"""Skapa eller uppdatera "Sverige ÅÅÅÅ" och tilldela den företaget från 1 januari.

	bench --site <site> execute hrms_sverige.setup.holidays.create_holiday_list --kwargs "{'year': 2027}"
	"""
	year = int(year)
	name = holiday_list_name(year)
	if frappe.db.exists("Holiday List", name):
		doc = frappe.get_doc("Holiday List", name)
		doc.set("holidays", [])
	else:
		doc = frappe.new_doc("Holiday List")
		doc.holiday_list_name = name
	doc.from_date = date(year, 1, 1)
	doc.to_date = date(year, 12, 31)
	doc.country = "SE"

	named = svenska_helgdagar(year, aftnar)
	day = doc.from_date
	while day <= doc.to_date:
		weekend = day.weekday() in WEEKDAY_NAMES
		if day in named:
			doc.append(
				"holidays", {"holiday_date": day, "description": named[day], "weekly_off": int(weekend)}
			)
		elif weekend:
			doc.append(
				"holidays",
				{"holiday_date": day, "description": WEEKDAY_NAMES[day.weekday()], "weekly_off": 1},
			)
		day += timedelta(days=1)
	doc.save(ignore_permissions=True)

	company = company or erpnext.get_default_company()
	if company:
		_assign_to_company(doc.name, company, doc.from_date)
	return doc.name


def _assign_to_company(holiday_list: str, company: str, from_date: date):
	"""Rör inte en befintlig tilldelning för samma startdatum; HR kan ha valt en egen lista."""
	if frappe.db.exists(
		"Holiday List Assignment", {"assigned_to": company, "from_date": from_date, "docstatus": 1}
	):
		return
	frappe.get_doc(
		{
			"doctype": "Holiday List Assignment",
			"applicable_for": "Company",
			"assigned_to": company,
			"holiday_list": holiday_list,
			"from_date": from_date,
		}
	).submit()
