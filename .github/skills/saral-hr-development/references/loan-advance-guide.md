# Employee Loan & Advance Guide

## Overview

The app supports two types of financial assistance:
1. **Loans**: Long-term with scheduled repayment
2. **Advances**: Short-term salary advances

## Loan DocTypes

### Employee Loan Advance
Main loan record with:
- Employee details
- Loan amount
- Interest rate
- Repayment schedule
- Status tracking

### Employee Loan Advance Schedule
Repayment installment details:
- EMI amount
- Due date
- Principal/Interest split
- Payment status

### Employee Salary Hold
Temporary salary freezing for advance recovery

## Process Flow

### Create Loan

1. Employee submits loan application
2. Manager approves
3. Finance disburses amount
4. System generates schedule
5. Monthly deductions begin

### Track Repayment

- Monthly deduction in salary slip
- Schedule shows payment status
- Ledger shows transaction history
- Balance tracking

### Close Loan

- Final payment recorded
- Status updated to "Closed"
- No further deductions

## Key Fields

| Field | Example |
|-------|---------|
| Employee | HR-EMP-001 |
| Loan Amount | 50,000 |
| Interest Rate | 5% |
| Tenure (months) | 12 |
| EMI | 4,348 |

## Calculation Example

```
Principal: 50,000
Rate: 5% p.a.
Tenure: 12 months

Monthly Interest = (Principal × Rate) / 12
EMI = Principal / Tenure + Monthly Interest
```

## Reports

### Employee Loan Advance Ledger
Shows all transactions for each employee

### Loan Register
Master list of all loans

### Loan Deduction for Month
Monthly deduction summary

## Query Active Loans

```python
# Get all active loans for an employee
loans = frappe.get_list("Employee Loan Advance",
    filters={
        "employee": "HR-EMP-001",
        "status": "Active"
    }
)

for loan in loans:
    doc = frappe.get_doc("Employee Loan Advance", loan.name)
    print(f"Loan: {doc.name}, Outstanding: {doc.outstanding_amount}")
```

## Common Issues

- **EMI exceeds salary**: Approve only feasible loans
- **Schedule not generating**: Check calculation formulas
- **Deduction mismatch**: Verify month-to-month schedule
