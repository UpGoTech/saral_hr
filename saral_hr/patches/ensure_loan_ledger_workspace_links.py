"""Add loan ledger report links to Saral HR workspace."""

from saral_hr.patches.ensure_employee_loan_workspace import execute as ensure_workspace


def execute():
	ensure_workspace()
