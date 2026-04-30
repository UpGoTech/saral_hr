---
name: saral-hr-development
description: 'Complete Saral HR development workflow for Frappe. Use when: generating salary slips, processing payroll, managing employee loans, creating tax reports, marking attendance, running fixtures, testing doctypes, managing permissions.'
argument-hint: 'Enter action: salary-slip, payroll, loan, report, attendance, fixture, test, or permissions'
user-invocable: true
---

# Saral HR Development Workflow

Complete development guide for **Saral HR** Frappe app with salary processing, payroll, loans, reports, and attendance management.

## Setup Information

- **App**: saral_hr (Saral HR)
- **Python**: >=3.10
- **Frappe**: v15+ (managed by bench)
- **Main Dependencies**: PyPDF2
- **License**: MIT
- **Key Modules**: Employee, Salary, Attendance, Loans, Payroll, Reports

---

## When to Use

- ✅ Generate salary slips for employees
- ✅ Calculate and process monthly payroll
- ✅ Process employee loans and advances
- ✅ Create tax registers (IT, PT, ESI, Professional Tax)
- ✅ Generate bank advice and payment reports
- ✅ Mark and validate attendance
- ✅ Setup permissions for roles
- ✅ Run fixtures and migrations
- ✅ Test and debug doctypes
- ✅ Export payroll data

---

## Quick Commands

### Setup & Installation

```bash
# Activate bench environment
source ~/fb/bin/activate

# Navigate to app
cd ~/saral_hr_bench/apps/saral_hr

# Install app in bench
bench get-app saral_hr ~/saral_hr_bench/apps/saral_hr
bench install-app saral_hr

# Migrate after changes
bench migrate
```

### Create/Import Fixtures

```bash
# Export current fixtures
bench export-fixtures --app saral_hr

# Import fixtures
bench import-fixtures --app saral_hr

# Create workspace
bench execute saral_hr.install.create_roles
```

### Run Tests

```bash
# Test all doctypes
bench run-tests --app saral_hr

# Test specific doctype
bench run-tests saral_hr.saral_hr.doctype.salary_slip.test_salary_slip

# Run with coverage
bench run-tests --app saral_hr --coverage
```

### Development Mode

```bash
# Clear cache
bench clear-cache

# Rebuild
bench build

# Watch and auto-reload
bench watch
```

---

## Workflows

### 1️⃣ Salary Slip Generation

**Files**: [salary_slip/](./references/salary-slip-guide.md)

**Steps**:
1. Create Salary Structure with components
2. Assign salary structure to employee
3. Create Salary Slip from template
4. Calculate deductions (IT, PT, ESI, LWF)
5. Validate and submit
6. Generate PDF for employee

**Key Doctypes**:
- `salary_component` - Salary components (Basic, DA, HRA, etc.)
- `salary_structure` - Employee salary template
- `salary_structure_assignment` - Assign structure to employee
- `salary_slip` - Monthly salary slip
- `salary_details` - Line items in salary slip

**Common Issues**:
- Missing salary structure assignment
- Deduction components not linked
- Date range mismatch for leave deductions

---

### 2️⃣ Payroll Processing

**Files**: [payroll/](./references/payroll-guide.md)

**Steps**:
1. Validate attendance for month
2. Process leave deductions
3. Calculate variable pay
4. Generate salary slips (bulk)
5. Create bank advice
6. Submit and lock payroll

**Key Doctypes**:
- `salary_slip` - Individual salary slip
- `bank_advice` - Bank payment file for bulk transfers
- `attendance` - Daily attendance records
- `leave_application` - Leave requests
- `variable_pay_assignment` - Bonus/incentive tracking

**Reports Available**:
- `payroll_report` - Monthly payroll summary
- `salary_statistics` - Salary trends
- `monthly_attendance_report` - Attendance analysis

---

### 3️⃣ Employee Loans & Advances

**Files**: [loan_advance/](./references/loan-advance-guide.md)

**Steps**:
1. Create loan/advance application
2. Approve by manager
3. Disburse to employee
4. Track deduction schedule
5. Generate ledger report

**Key Doctypes**:
- `employee_loan_advance` - Main loan record
- `employee_loan_advance_schedule` - Repayment schedule
- `employee_salary_hold` - Temporary salary hold

**Reports**:
- `employee_loan_advance_ledger` - Loan transaction history
- `loan_register` - All active loans
- `loan_deduction_for_month` - Monthly deduction status

---

### 4️⃣ Tax & Compliance Reports

**Files**: [reports/](./references/reports-guide.md)

**Available Reports**:
- `income_tax_report` - IT register
- `professional_tax_register` - PT deductions
- `esi_register` - ESI contributions
- `labour_welfare_fund_register` - LWF deductions
- `bank_advice` - Bank payment file
- `other_bank_advice` - Alternative format
- `employee_loan_advance_ledger` - Loan details
- `advance_register` - Advances register
- `educational_allowance_register` - Education allowance
- `daily_wage_calculation_report` - Daily wage workers

**Excel Export**:
```bash
# Use menu: Report → Export → Excel
# Or via API:
bench execute saral_hr.saral_hr.report.income_tax_report.income_tax_report.get_report_data \
  --kwargs '{"year": 2025, "month": 4}'
```

---

### 5️⃣ Attendance Management

**Files**: [attendance/](./references/attendance-guide.md)

**Features**:
- Mark daily attendance
- Bulk import from CSV
- Leave application processing
- Shift management
- Late/absent tracking
- Daily wage worker rates

**Key Doctypes**:
- `attendance` - Daily attendance
- `leave_application` - Leave requests
- `leave_types` - Types of leave (Casual, Sick, etc.)
- `leave_allocation` - Leave balance per employee
- `shift_type` - Shift definitions
- `shift_assignment` - Employee shift assignment
- `daily_rates_worker` - Daily wage rates

**Bulk Mark Attendance**:
```bash
# Via API - Create attendance records programmatically
frappe.call({
    method: 'saral_hr.saral_hr.doctype.attendance.attendance.mark_attendance',
    args: {'date': '2025-04-30', 'status': 'Present'}
})
```

---

### 6️⃣ Permission & Role Management

**Files**: [permissions/](./references/permissions-guide.md)

**Default Roles**:
- `Saral HR Manager` - Full access
- `Saral HR User` - Limited access

**Permission Rules** (in hooks.py):
- `Company Link` - View only own company
- `Employee` - View own record
- `Attendance` - View own/company attendance
- `Salary Structure Assignment` - Manage structure
- `Salary Slip` - View own slip

**Add Custom Permission**:
```python
# In permission.py
def custom_permission_query(doctype, user):
    if doctype == "Salary Slip":
        return {"employee": frappe.session.user}
```

---

### 7️⃣ Custom Doctype Development

**Structure**:
```
saral_hr/doctype/<doctype_name>/
├── __init__.py
├── <doctype_name>.py          # Backend logic
├── <doctype_name>.json        # DocType definition
├── <doctype_name>.js          # Frontend logic
└── test_<doctype_name>.py     # Unit tests
```

**Example: Create New DocType**:
```bash
# Via bench CLI
bench new-doc-type saral_hr new_doctype_name

# Edit JSON, Python, JS files
# Then run tests
bench run-tests saral_hr.saral_hr.doctype.new_doctype_name
```

---

## Directory Structure

```
saral_hr/
├── saral_hr/
│   ├── doctype/
│   │   ├── employee/
│   │   ├── salary_slip/
│   │   ├── employee_loan_advance/
│   │   ├── attendance/
│   │   └── ...
│   ├── page/              # Custom pages
│   ├── report/            # Report scripts
│   └── permission.py      # Permission rules
├── fixtures/              # Initial data (roles, components)
├── public/                # Static assets (CSS, JS)
└── hooks.py              # App configuration
```

---

## Common Tasks

### Generate Salary Slip for Employee

```python
from frappe import _

emp_id = "HR-EMP-001"
year, month = 2025, 4

# Get salary structure assignment
assignment = frappe.get_doc("Salary Structure Assignment", {
    "employee": emp_id,
    "docstatus": 1
})

# Create salary slip
slip = frappe.get_doc({
    "doctype": "Salary Slip",
    "employee": emp_id,
    "salary_structure": assignment.salary_structure,
    "name_of_employee": assignment.employee_name,
    "posting_date": frappe.utils.get_last_day(f"{year}-{month:02d}-01"),
    "start_date": frappe.utils.get_first_day(f"{year}-{month:02d}-01"),
    "end_date": frappe.utils.get_last_day(f"{year}-{month:02d}-01")
})
slip.insert()
slip.amend()
```

### Bulk Mark Attendance

```python
import frappe
from datetime import datetime, timedelta

company = "Your Company"
start_date = datetime(2025, 4, 1)
end_date = datetime(2025, 4, 30)

employees = frappe.get_list("Employee", 
    filters={"status": "Active", "company": company},
    pluck="name"
)

current_date = start_date
while current_date <= end_date:
    # Skip weekends
    if current_date.weekday() < 5:
        for emp_id in employees:
            frappe.get_doc({
                "doctype": "Attendance",
                "employee": emp_id,
                "attendance_date": current_date,
                "status": "Present",
                "working_hours": 8
            }).submit()
    current_date += timedelta(days=1)

frappe.db.commit()
```

### Export Salary Data to CSV

```python
import frappe
import csv
from io import StringIO

month, year = 4, 2025
filename = f"payroll_{year}_{month:02d}.csv"

slips = frappe.get_list("Salary Slip",
    filters={
        "month": month,
        "year": year,
        "docstatus": 1
    }
)

# Generate CSV
with open(filename, 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['Employee', 'Salary', 'Deductions', 'Net Pay'])
    for slip in slips:
        doc = frappe.get_doc("Salary Slip", slip.name)
        writer.writerow([
            doc.employee_name,
            doc.gross_pay,
            doc.total_deduction,
            doc.net_pay
        ])
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Salary Slip calculation wrong | Check salary_component rates, assignment dates |
| Attendance not recording | Verify employee company, check date format |
| Report empty | Ensure docstatus=1 (submitted), check date filters |
| Permission denied | Run `bench setup permissions` or check permission.py |
| Fixtures not importing | Check fixture filters in hooks.py, run `bench migrate` |

---

## Resources

- [Frappe Documentation](https://frappeframework.com/docs)
- [Frappe HR Module](https://frappe.io/docs/user/en/modules/hr)
- [Your App Hooks](../../hooks.py)
- [Permission Rules](../../permission.py)
- [Installation Script](../../install.py)

