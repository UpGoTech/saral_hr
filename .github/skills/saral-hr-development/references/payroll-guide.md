# Payroll Processing Guide

## Monthly Payroll Cycle

### Step 1: Prepare Data
- Validate employee list
- Check attendance records
- Process leave applications
- Update salary structures

### Step 2: Generate Salary Slips
- Bulk create salary slips
- System calculates earnings/deductions
- Review for errors

### Step 3: Verification
- Check total payroll cost
- Verify deduction amounts
- Review individual slips

### Step 4: Approval & Lock
- Approve by finance manager
- Lock month to prevent changes
- Generate bank advice

### Step 5: Payment
- Export bank advice file
- Submit to bank
- Confirm payment completion

## Salary Slip Calculations

```
Gross Salary = Sum(Earnings)
Total Deductions = Sum(Deductions)
Net Pay = Gross Salary - Total Deductions
```

### Earnings
- Basic Salary
- Allowances (HRA, DA, etc.)
- Variable Pay (Bonus, Incentive)
- Leave Encashment

### Deductions
- Professional Tax (fixed %)
- Income Tax (progressive %)
- ESI (employee share)
- LWF (fixed amount)
- Loan EMI
- Advance Recovery

## Bulk Operations

### Generate Slips for Month

```bash
# Via API
frappe.call({
    method: 'saral_hr.saral_hr.report.payroll_report.get_report_data',
    args: {
        'month': 4,
        'year': 2025,
        'company': 'Your Company'
    },
    callback: function(r) {
        console.log(r.message);
    }
});
```

### Export to Excel

```bash
# Monthly payroll summary
# Menu: Report → Payroll Report → Export → Excel
```

## Reports Available

| Report | Purpose |
|--------|---------|
| Payroll Report | Summary of salaries |
| Salary Statistics | Trend analysis |
| Monthly Attendance Report | Attendance details |
| Bank Advice | Payment file for bank |

## Validation Checklist

- [ ] All employees assigned salary structure
- [ ] Attendance marked for full month
- [ ] Leave applications approved
- [ ] Loan/advance records updated
- [ ] Salary slip calculations verified
- [ ] No salary holds active
- [ ] Bank account details updated

