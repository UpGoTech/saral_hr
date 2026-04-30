#!/usr/bin/env python
"""
Generate salary slips for all active employees for a given month.
Usage: bench execute saral_hr.generate_salary_slips --kwargs '{"month": 4, "year": 2025}'
"""

import frappe
from datetime import datetime
from dateutil.utils import get_last_day_of_month, get_first_day_of_month

def generate_salary_slips(month, year, company=None):
    """
    Generate salary slips for employees
    
    Args:
        month (int): Month (1-12)
        year (int): Year (YYYY)
        company (str): Company name (optional)
    
    Returns:
        dict: Summary of created slips
    """
    
    # Get employees
    filters = {"status": "Active"}
    if company:
        filters["company"] = company
    
    employees = frappe.get_list("Employee", filters=filters, pluck="name")
    
    if not employees:
        frappe.msgprint("No active employees found")
        return {"created": 0, "skipped": 0, "errors": []}
    
    # Calculate dates
    first_day = get_first_day_of_month(year, month)
    last_day = get_last_day_of_month(year, month)
    
    created = 0
    skipped = 0
    errors = []
    
    for emp_id in employees:
        try:
            # Check if salary structure assignment exists
            assignment = frappe.get_doc("Salary Structure Assignment", {
                "employee": emp_id,
                "docstatus": 1,
                "from_date": ["<=", first_day]
            })
            
            # Check if salary slip already exists
            existing = frappe.get_list("Salary Slip", filters={
                "employee": emp_id,
                "month": month,
                "year": year
            })
            
            if existing:
                skipped += 1
                continue
            
            # Create salary slip
            slip = frappe.get_doc({
                "doctype": "Salary Slip",
                "employee": emp_id,
                "employee_name": assignment.employee_name,
                "company": assignment.company,
                "salary_structure": assignment.salary_structure,
                "posting_date": last_day,
                "start_date": first_day,
                "end_date": last_day,
                "month": month,
                "year": year
            })
            
            slip.insert()
            created += 1
            
        except frappe.DoesNotExistError:
            errors.append(f"{emp_id}: No salary structure assignment found")
            skipped += 1
        except Exception as e:
            errors.append(f"{emp_id}: {str(e)}")
            skipped += 1
    
    result = {
        "created": created,
        "skipped": skipped,
        "errors": errors,
        "message": f"Created {created} salary slips, skipped {skipped}"
    }
    
    frappe.msgprint(result["message"])
    return result

if __name__ == "__main__":
    # Example usage
    result = generate_salary_slips(month=4, year=2025)
    print(result)
