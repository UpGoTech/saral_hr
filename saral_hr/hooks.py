app_name = "saral_hr"
app_title = "Saral HR"
app_publisher = "sj"
app_description = "Custome Saral Hr"
app_email = "sj@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "saral_hr",
# 		"logo": "/assets/saral_hr/logo.png",
# 		"title": "Saral HR",
# 		"route": "/saral_hr",
# 		"has_permission": "saral_hr.api.permission.has_app_permission"
# 	}
# ]



# Includes in <head>
# ------------------g

# include js, css files in header of desk.html
# app_include_css = "/assets/saral_hr/css/saral_hr.css"
# app_include_js = "/assets/saral_hr/js/saral_hr.js"

# include js, css files in header of web template
# web_include_css = "/assets/saral_hr/css/saral_hr.css"
# web_include_js = "/assets/saral_hr/js/saral_hr.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "saral_hr/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
doctype_list_js = {
    "Biometric machine": "saral_hr/doctype/biometric_machine/biometric_machine.js",
    "Biometric attendance log": "saral_hr/doctype/biometric_attendance_log/biometric_attendance_log.js"
}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "saral_hr/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

permission_query_conditions = {
    "Company Link": "saral_hr.permission.company_link_permission_query",
    "Employee": "saral_hr.permission.employee_permission_query",
    "Attendance": "saral_hr.permission.attendance_permission_query",
    "Salary Structure Assignment": "saral_hr.permission.salary_structure_assignment_permission_query",
    "Salary Slip": "saral_hr.permission.salary_slip_permission_query",
    "Variable Pay Assignment": "saral_hr.permission.variable_pay_assignment_permission_query"
}


# Document fixtures to be exported/imported
fixtures = [

    # Workspace
    {
        "dt": "Workspace",
        "filters": [
            ["name", "in", ["Saral HR"]]
        ]
    },

    # Roles
    {
        "dt": "Role",
        "filters": [
            ["name", "in", ["Saral HR Manager", "Saral HR User"]]
        ]
    },

    # DocType Permissions
    {
        "dt": "Custom DocPerm",
        "filters": [
            ["role", "in", ["Saral HR Manager", "Saral HR User"]]
        ]
    },

    # Print Formats
{
    "dt": "Print Format",
    "filters": [
        ["name", "in", [
            "Variable Pay",
            "Salary Slip Custom",
            "CTC Calculator Statement",
            "SSA Print Format"
        ]]
    ]
},

   # Reports
    {
        "dt": "Report",
        "filters": [
            ["module", "=", "Saral HR"]
        ]
    },

    # Custom Fields
    {
        "dt": "Custom Field",
        "filters": [
            ["dt", "=", "Salary Slip"]
        ]
    }

]

# your_app/hooks.py

before_install = "saral_hr.setup.before_install"





# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
jinja = {
    "methods": [
        "saral_hr.utils.jinja_methods.parse_json"
    ]
}
# Installation
# ------------

# before_install = "saral_hr.install.before_install"
after_install = "saral_hr.install.after_install"
after_migrate = "saral_hr.install.after_migrate"

# Uninstallation
# ------------

# before_uninstall = "saral_hr.uninstall.before_uninstall"
after_uninstall = "saral_hr.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "saral_hr.utils.before_app_install"
# after_app_install = "saral_hr.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "saral_hr.utils.before_app_uninstall"
# after_app_uninstall = "saral_hr.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "saral_hr.notifications.get_notification_config"

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

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
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
# 		"saral_hr.tasks.all"
# 	],
# 	"daily": [
# 		"saral_hr.tasks.daily"
# 	],
# 	"hourly": [
# 		"saral_hr.tasks.hourly"
# 	],
# 	"weekly": [
# 		"saral_hr.tasks.weekly"
# 	],
# 	"monthly": [
# 		"saral_hr.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "saral_hr.install.before_tests"

# Overriding Methods
# ------------------------------
override_whitelisted_methods = {
	"frappe.utils.print_format.download_pdf": "saral_hr.utils.pdf.download_pdf",
}

# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "saral_hr.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["saral_hr.utils.before_request"]
# after_request = ["saral_hr.utils.after_request"]

# Job Events
# ----------
# before_job = ["saral_hr.utils.before_job"]
# after_job = ["saral_hr.utils.after_job"]

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
# 	"saral_hr.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }


