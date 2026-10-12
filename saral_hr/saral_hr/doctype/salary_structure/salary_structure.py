# Copyright (c) 2026, sj and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _


class SalaryStructure(Document):
    def validate(self):
        self.validate_salary_components()
        # Totals calculation removed

    def validate_salary_components(self):
        """Validate that earnings have Earning type and deductions have Deduction type"""
        
        # Check earnings
        for earning in self.get('earnings', []):
            if earning.salary_component:
                meta = frappe.db.get_value(
                    'Salary Component',
                    earning.salary_component,
                    ['type', 'is_additional_only'],
                    as_dict=True,
                ) or {}
                if meta.get('type') != 'Earning':
                    frappe.throw(
                        _('Row #{0}: Component {1} is not an Earning type component. Please select an Earning component.').format(
                            earning.idx,
                            frappe.bold(earning.salary_component)
                        )
                    )
                if int(meta.get('is_additional_only') or 0):
                    frappe.throw(
                        _('Row #{0}: Component {1} is Additional-Only and cannot be used on Salary Structure.').format(
                            earning.idx,
                            frappe.bold(earning.salary_component)
                        )
                    )
        
        # Check deductions
        for deduction in self.get('deductions', []):
            if deduction.salary_component:
                meta = frappe.db.get_value(
                    'Salary Component',
                    deduction.salary_component,
                    ['type', 'is_additional_only'],
                    as_dict=True,
                ) or {}
                if meta.get('type') != 'Deduction':
                    frappe.throw(
                        _('Row #{0}: Component {1} is not a Deduction type component. Please select a Deduction component.').format(
                            deduction.idx,
                            frappe.bold(deduction.salary_component)
                        )
                    )
                if int(meta.get('is_additional_only') or 0):
                    frappe.throw(
                        _('Row #{0}: Component {1} is Additional-Only and cannot be used on Salary Structure.').format(
                            deduction.idx,
                            frappe.bold(deduction.salary_component)
                        )
                    )
        
        # Check for duplicate components in earnings
        earnings_components = [d.salary_component for d in self.get('earnings', []) if d.salary_component]
        if len(earnings_components) != len(set(earnings_components)):
            frappe.throw(_('Duplicate salary components found in Earnings table. Each component can only be added once.'))
        
        # Check for duplicate components in deductions
        deductions_components = [d.salary_component for d in self.get('deductions', []) if d.salary_component]
        if len(deductions_components) != len(set(deductions_components)):
            frappe.throw(_('Duplicate salary components found in Deductions table. Each component can only be added once.'))

def flt(value, decimals=2):
    """Convert to float with proper handling"""
    try:
        return float(value or 0)
    except (ValueError, TypeError):
        return 0.0
