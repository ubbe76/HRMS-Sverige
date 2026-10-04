import erpnext
from frappe.utils import getdate

from hrms_sverige.hr.anstallningsnummer import visa_anstallningsnummer
from hrms_sverige.setup.custom_fields import create_custom_fields, ensure_personnummer_permissions
from hrms_sverige.setup.employment_types import ensure_employment_types
from hrms_sverige.setup.holidays import create_holiday_list
from hrms_sverige.setup.leave import (
	ensure_leave_period,
	ensure_leave_types,
	ensure_paxml_tidkoder,
	ensure_semester_policy,
	remove_unused_hrms_leave_types,
)
from hrms_sverige.setup.workspaces import hide_unused


def setup_all(company: str | None = None):
	"""All svensk uppsättning. Kan köras om:

	bench --site <site> execute hrms_sverige.setup.install.setup_all
	"""
	company = company or erpnext.get_default_company()
	create_custom_fields()
	ensure_personnummer_permissions()
	ensure_employment_types()
	visa_anstallningsnummer()
	ensure_leave_types()
	ensure_paxml_tidkoder()
	remove_unused_hrms_leave_types()
	ensure_semester_policy()
	if company:
		year = getdate().year
		for y in (year, year + 1):
			create_holiday_list(y, company)
			ensure_leave_period(y, company)
	hide_unused()


def after_install():
	setup_all()


def after_setup_wizard(args: dict | None = None):
	# Vid installation finns inget företag än, så helgdagslistor och ledighetsperioder skapas här.
	setup_all((args or {}).get("company_name"))


def after_migrate():
	# Migrate synkar om arbetsytor och ikoner från HRMS och kan visa dem igen.
	create_custom_fields()
	ensure_paxml_tidkoder()
	visa_anstallningsnummer()
	hide_unused()
