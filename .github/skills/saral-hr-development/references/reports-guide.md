# Tax & Compliance Reports Guide

## Available Reports

### Statutory Reports

#### Income Tax Register
- Employee-wise IT deduction summary
- Annual IT calculation
- Export for audit

#### Professional Tax Register
- PT deductions by state
- Monthly summary
- Payment reconciliation

#### ESI Register
- Employee State Insurance details
- Employer & employee contributions
- Compliance documentation

#### Labour Welfare Fund Register
- LWF contributions
- State compliance
- Annual reporting

### Operational Reports

#### Bank Advice
- NEFT/RTGS payment file format
- Employee bank account details
- Amount and reference number

#### Payroll Report
- Overall salary summary
- Cost center wise breakdown
- Department comparison

#### Salary Statistics
- Salary trends
- Component analysis
- Year-over-year comparison

## Report Parameters

### Common Filters
- Month & Year
- Company/Branch
- Department
- Employee Status (Active/Inactive)

### Date Filters
- Period: Month/Quarter/Year
- Financial Year (Apr-Mar)
- Custom date range

## Export Options

### Excel Format
```
Menu: Report → [Report Name] → Export → Excel
```

### PDF Format
```
Menu: Report → [Report Name] → Print → PDF
```

### CSV Format
```
Report API → Download as CSV
```

## Compliance Checklist

### Monthly
- [ ] Salary processed
- [ ] Bank advice generated
- [ ] Deductions verified

### Quarterly
- [ ] ESI register reconciled
- [ ] PT compliance checked
- [ ] Leave balance updated

### Annual
- [ ] IT register prepared
- [ ] LWF annual reconciliation
- [ ] Financial audit compliance

## Query Report Data

```python
# Get income tax report data
report_data = frappe.call({
    method: 'saral_hr.saral_hr.report.income_tax_report.income_tax_report.get_report_data',
    args: {
        'year': 2025,
        'month': 4
    }
})
```

## Report Schedule

| Report | Frequency | Deadline |
|--------|-----------|----------|
| Payroll Summary | Monthly | 5th |
| Tax Registers | Monthly | 15th |
| Bank Advice | Monthly | 25th |
| Annual IT | Annual | Mar 31 |
| ESI Report | Quarterly | 15th |
