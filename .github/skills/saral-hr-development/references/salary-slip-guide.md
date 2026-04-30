# Salary Slip Generation Guide

## Overview
Salary slips are monthly payment records for employees showing earnings, deductions, and net pay.

## Key Components

### Salary Components
- **Basic Salary**: Base pay
- **Dearness Allowance (DA)**: Inflation-linked allowance
- **House Rent Allowance (HRA)**: Accommodation
- **Special Allowance**: Variable allowance
- **Leave Encashment**: Paid leave balance

### Deductions
- **Professional Tax (PT)**: State tax
- **Income Tax (IT)**: Federal tax
- **Employee State Insurance (ESI)**: Social security
- **Labour Welfare Fund (LWF)**: State welfare
- **Loan Deduction**: EMI repayment

## Process Flow

1. **Define Salary Structure**
   - Add earning components
   - Add deduction components
   - Set formulas for calculations

2. **Assign to Employee**
   - Link salary structure to employee
   - Set effective date
   - Enable automatic slip creation

3. **Generate Salary Slip**
   - Create from template
   - System calculates values
   - Review for accuracy

4. **Submit & Export**
   - Approve salary slip
   - Lock for the month
   - Generate PDF/export to payroll

## DocTypes

| DocType | Purpose |
|---------|---------|
| Salary Component | Define earning/deduction types |
| Salary Structure | Template for monthly salary |
| Salary Structure Assignment | Link structure to employee |
| Salary Slip | Monthly payment record |
| Salary Details | Line items in salary slip |

## Example: Create Salary Structure

```python
frappe.get_doc({
    "doctype": "Salary Structure",
    "name": "Standard 2025",
    "company": "Your Company",
    "payroll_frequency": "Monthly",
    "docstatus": 1,
    "earnings": [
        {
            "salary_component": "Basic",
            "amount": 50000
        },
        {
            "salary_component": "HRA",
            "amount": 15000
        },
        {
            "salary_component": "DA",
            "amount": 10000
        }
    ],
    "deductions": [
        {
            "salary_component": "Professional Tax",
            "amount": 200
        },
        {
            "salary_component": "ESI",
            "amount": 850
        }
    ]
}).save()
```

## Common Issues

- **Missing Components**: Add components before creating structure
- **No Assignment**: Salary slip needs active structure assignment
- **Calculation Errors**: Check component formulas and allocation amounts
