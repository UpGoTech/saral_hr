#!/usr/bin/env python
"""
Export payroll data to CSV for a given month.
Usage: bench execute saral_hr.export_payroll_data --kwargs '{"month": 4, "year": 2025}'
"""

import frappe
import csv
from pathlib import Path

def export_payroll_data(month, year, company=None, output_dir=None):
    """
    Export salary slip data to CSV
    
    Args:
        month (int): Month (1-12)
        year (int): Year (YYYY)
        company (str): Company name (optional)
        output_dir (str): Output directory path
    
    Returns:
        str: File path of exported CSV
    """
    
    if output_dir is None:
        output_dir = "/tmp"
    
    # Get salary slips
    filters = {
        "month": month,
        "year": year,
        "docstatus": 1
    }
    
    if company:
        filters["company"] = company
    
    slips = frappe.get_list("Salary Slip", filters=filters, order_by="employee")
    
    if not slips:
        frappe.msgprint(f"No salary slips found for {month}/{year}")
        return None
    
    # Generate CSV
    filename = f"payroll_{year}_{month:02d}.csv"
    filepath = Path(output_dir) / filename
    
    with open(filepath, 'w', newline='') as csvfile:
        fieldnames = [
            'Employee ID',
            'Employee Name',
            'Company',
            'Department',
            'Designation',
            'Basic Salary',
            'Gross Pay',
            'Total Deduction',
            'Net Pay',
            'Status'
        ]
        
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for slip_info in slips:
            slip = frappe.get_doc("Salary Slip", slip_info.name)
            
            writer.writerow({
                'Employee ID': slip.employee,
                'Employee Name': slip.employee_name,
                'Company': slip.company,
                'Department': slip.get("department", ""),
                'Designation': slip.get("designation", ""),
                'Basic Salary': slip.get_earning_component_value("Basic"),
                'Gross Pay': slip.gross_pay,
                'Total Deduction': slip.total_deduction,
                'Net Pay': slip.net_pay,
                'Status': 'Submitted' if slip.docstatus == 1 else 'Draft'
            })
    
    message = f"Payroll data exported to {filepath}"
    frappe.msgprint(message)
    return str(filepath)

if __name__ == "__main__":
    # Example usage
    filepath = export_payroll_data(month=4, year=2025)
    print(f"Exported to: {filepath}")
