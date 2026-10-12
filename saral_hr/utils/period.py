from datetime import date

import frappe
from frappe import _
from frappe.utils import cint

PERIOD_YEAR_MIN = 2024


def period_year_max():
	return date.today().year + 1


def validate_period_year(year, label=None):
	y = cint(year)
	if y < PERIOD_YEAR_MIN or y > period_year_max():
		field = label or _("Year")
		frappe.throw(
			_("{0} must be between {1} and {2}").format(
				field, PERIOD_YEAR_MIN, period_year_max()
			)
		)
	return y
