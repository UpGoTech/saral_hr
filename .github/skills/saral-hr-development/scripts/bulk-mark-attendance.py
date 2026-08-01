#!/usr/bin/env python
"""
Bulk mark attendance for all employees for a date range.
Usage: bench execute saral_hr.bulk_mark_attendance --kwargs '{"from_date": "2025-04-01", "to_date": "2025-04-30"}'
"""

import frappe
from datetime import datetime, timedelta

def bulk_mark_attendance(from_date, to_date, company=None, status="Present", skip_weekends=True):
    """
    Mark attendance for multiple employees over a date range
    
    Args:
        from_date (str): Start date (YYYY-MM-DD)
        to_date (str): End date (YYYY-MM-DD)
        company (str): Company name (optional)
        status (str): Attendance status (Present/Absent/Leave)
        skip_weekends (bool): Skip Saturdays and Sundays
    
    Returns:
        dict: Summary of records created
    """
    
    # Parse dates
    start = datetime.strptime(from_date, "%Y-%m-%d")
    end = datetime.strptime(to_date, "%Y-%m-%d")
    
    # Get active employees
    filters = {"status": "Active"}
    if company:
        filters["company"] = company
    
    employees = frappe.get_list("Employee", filters=filters, pluck="name")
    
    if not employees:
        frappe.msgprint("No active employees found")
        return {"created": 0, "skipped": 0, "errors": []}
    
    created = 0
    skipped = 0
    errors = []
    
    current_date = start
    while current_date <= end:
        # Skip weekends if flag is True
        if skip_weekends and current_date.weekday() >= 5:  # 5=Saturday, 6=Sunday
            current_date += timedelta(days=1)
            continue
        
        # Check if it's a holiday
        is_holiday = frappe.get_list("Holiday", filters={
            "holiday_date": current_date.date()
        })
        
        if is_holiday:
            current_date += timedelta(days=1)
            continue
        
        # Create attendance for each employee
        for emp_id in employees:
            try:
                # Check if attendance already exists
                existing = frappe.get_list("Attendance", filters={
                    "employee": emp_id,
                    "attendance_date": current_date.date()
                })
                
                if existing:
                    skipped += 1
                    continue
                
                # Get employee company
                emp = frappe.get_doc("Employee", emp_id)
                
                # Create attendance record
                attendance = frappe.get_doc({
                    "doctype": "Attendance",
                    "employee": emp_id,
                    "employee_name": emp.employee_name,
                    "company": emp.company,
                    "attendance_date": current_date.date(),
                    "status": status,
                    "working_hours": 8
                })
                
                attendance.submit()
                created += 1
                
            except Exception as e:
                errors.append(f"{emp_id} on {current_date.date()}: {str(e)}")
                skipped += 1
        
        current_date += timedelta(days=1)
    
    result = {
        "created": created,
        "skipped": skipped,
        "errors": errors,
        "message": f"Created {created} attendance records, skipped {skipped}"
    }
    
    frappe.msgprint(result["message"])
    return result

if __name__ == "__main__":
    # Example usage
    result = bulk_mark_attendance(
        from_date="2025-04-01",
        to_date="2025-04-30"
    )
    print(result)
