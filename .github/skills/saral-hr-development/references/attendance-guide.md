# Attendance Management Guide

## Attendance Types

### Regular Attendance
- Daily mark (Present/Absent/Leave/Holiday)
- Working hours tracking
- Leave integration

### Shift-based
- Multiple shifts support
- Shift assignment per employee
- Overtime calculation

### Daily Wage Workers
- Hourly rate tracking
- Variable hours
- Daily settlement

## Key DocTypes

| DocType | Purpose |
|---------|---------|
| Attendance | Daily record |
| Leave Types | Holiday categories |
| Leave Allocation | Balance per employee |
| Leave Application | Leave request |
| Shift Type | Shift definition |
| Shift Assignment | Employee assignment |
| Daily Rates Worker | Wage tracking |

## Attendance Status

- **Present**: Full day work
- **Absent**: No work
- **Leave**: Approved leave (deducted from balance)
- **Holiday**: Non-working day
- **Half Day**: Partial work

## Mark Attendance

### Manual Entry
1. Go to Attendance
2. Select Employee & Date
3. Mark Status
4. Enter Working Hours
5. Submit

### Bulk Import
1. Download template
2. Fill employee ID, date, status
3. Upload CSV
4. System creates records

### API Method
```python
frappe.get_doc({
    "doctype": "Attendance",
    "employee": "HR-EMP-001",
    "attendance_date": "2025-04-30",
    "status": "Present",
    "working_hours": 8,
    "company": "Your Company"
}).submit()
```

## Leave Management

### Leave Types
- Casual Leave (CL)
- Sick Leave (SL)
- Earned Leave (EL)
- Optional Holiday

### Leave Allocation
- Allocated at year start
- Per employee per type
- Can be carried forward (with limit)

### Leave Application
1. Employee applies
2. Manager approves
3. Deducted from balance
4. Attendance auto-marked

## Daily Wage Workers

### Workflow
1. Define daily wage rates
2. Mark attendance with hours
3. Calculate daily settlement
4. Pay via bank/cash

### Rate Configuration
```
Daily Rate = (Monthly Salary / Days per Month)
Hourly Rate = (Daily Rate / Hours per Day)
```

## Shift Management

### Define Shift Type
- Shift name
- Start & end time
- Break duration
- Holidays

### Assign to Employee
- Employee ID
- Shift type
- Valid from date
- Status (Active/Inactive)

## Reports

### Monthly Attendance Report
- Attendance summary
- Present/Absent/Leave count
- Percentage analysis

### Daily Wage Calculation Report
- Daily worker earnings
- Hours worked
- Daily settlement

## Compliance

### Attendance Validation
- No duplicate entries
- Date format consistency
- Employee status check

### Leave Validation
- Balance available
- Approval required
- Date no-conflicts

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Duplicate attendance | Delete and re-enter |
| Leave not showing | Check leave allocation |
| Rate calculation wrong | Verify daily/hourly rate setup |
| Shift conflict | Check shift assignment dates |
