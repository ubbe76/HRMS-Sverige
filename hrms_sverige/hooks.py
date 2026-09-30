app_name = "hrms_sverige"
app_title = "HRMS Sverige"
app_publisher = "Urban Källefors"
app_description = "Swedish localization of Frappe HRMS"
app_email = "18618863+ubbe76@users.noreply.github.com"
app_license = "gpl-3.0"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "hrms_sverige",
# 		"logo": "/assets/hrms_sverige/logo.png",
# 		"title": "HRMS Sverige",
# 		"route": "/hrms_sverige",
# 		"has_permission": "hrms_sverige.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/hrms_sverige/css/hrms_sverige.css"
# app_include_js = "/assets/hrms_sverige/js/hrms_sverige.js"

# include js, css files in header of web template
# web_include_css = "/assets/hrms_sverige/css/hrms_sverige.css"
# web_include_js = "/assets/hrms_sverige/js/hrms_sverige.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "hrms_sverige/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "hrms_sverige/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "hrms_sverige.utils.jinja_methods",
# 	"filters": "hrms_sverige.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "hrms_sverige.install.before_install"
# after_install = "hrms_sverige.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "hrms_sverige.uninstall.before_uninstall"
# after_uninstall = "hrms_sverige.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "hrms_sverige.utils.before_app_install"
# after_app_install = "hrms_sverige.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "hrms_sverige.utils.before_app_uninstall"
# after_app_uninstall = "hrms_sverige.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "hrms_sverige.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "hrms_sverige.notifications.get_notification_config"

# Awesome Bar
# -----------
# Extra search results: list of dicts with label, description, route, index.
# route: ["List", "ToDo"], "/desk/docs/some/page", or "https://example.com"
# awesomebar_search = ["hrms_sverige.search.awesomebar_results"]

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"hrms_sverige.tasks.all"
# 	],
# 	"daily": [
# 		"hrms_sverige.tasks.daily"
# 	],
# 	"hourly": [
# 		"hrms_sverige.tasks.hourly"
# 	],
# 	"weekly": [
# 		"hrms_sverige.tasks.weekly"
# 	],
# 	"monthly": [
# 		"hrms_sverige.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "hrms_sverige.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "hrms_sverige.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "hrms_sverige.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "hrms_sverige.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["hrms_sverige.utils.before_request"]
# after_request = ["hrms_sverige.utils.after_request"]

# Job Events
# ----------
# before_job = ["hrms_sverige.utils.before_job"]
# after_job = ["hrms_sverige.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"hrms_sverige.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

