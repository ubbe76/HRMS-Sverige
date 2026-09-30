import erpnext
from frappe.utils import getdate

from hrms_sverige.setup.custom_fields import create_custom_fields
from hrms_sverige.setup.employment_types import ensure_employment_types
from hrms_sverige.setup.holidays import create_holiday_list
from hrms_sverige.setup.leave import ensure_leave_period, ensure_leave_types, ensure_semester_policy
from hrms_sverige.setup.workspaces import hide_unused


def setup_all(company: str | None = None):
	"""All svensk uppsättning. Kan köras om:

	bench --site <site> execute hrms_sverige.setup.install.setup_all
	"""
	company = company or erpnext.get_default_company()
	create_custom_fields()
	ensure_employment_types()
	ensure_leave_types()
	ensure_semester_policy()
	if company:
		year = getdate().year
		for y in (year, year + 1):
			create_holiday_list(y, company)
			ensure_leave_period(y, company)
	hide_unused()


def after_install():
	setup_all()


def after_migrate():
	# Migrate synkar om arbetsytor och ikoner från HRMS och kan visa dem igen.
	create_custom_fields()
	hide_unused()
