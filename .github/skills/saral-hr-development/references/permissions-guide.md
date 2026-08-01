# Permission & Role Management Guide

## Default Roles

### Saral HR Manager
- Full access to all HR modules
- Can approve salary, leaves, loans
- Can access all employee records
- Can generate reports

### Saral HR User
- Limited access
- Can view own records
- Can submit leave applications
- Cannot access sensitive data

## Permission Rules

The app uses custom permission queries to restrict data access:

### Company Link
```python
# Users see only their assigned company
"Company Link": "saral_hr.permission.company_link_permission_query"
```

### Employee
```python
# Users see own employee record
"Employee": "saral_hr.permission.employee_permission_query"
```

### Attendance
```python
# Users see their own attendance
"Attendance": "saral_hr.permission.attendance_permission_query"
```

### Salary Structure Assignment
```python
# Managers see all, users see own
"Salary Structure Assignment": "saral_hr.permission.salary_structure_assignment_permission_query"
```

### Salary Slip
```python
# Users see own salary slip
"Salary Slip": "saral_hr.permission.salary_slip_permission_query"
```

## Access Levels

### Level 1: Public
- Any user can view
- Reports, dashboards

### Level 2: Role-based
- Requires specific role
- Employee, Salary Slip

### Level 3: Restricted
- User-specific data
- Own attendance, salary

### Level 4: Admin Only
- Configuration changes
- Setup & migration

## Adding New Role

```python
# In install.py
frappe.get_doc({
    "doctype": "Role",
    "role_name": "HR Executive",
    "desk_access": 1,
    "permissions": [
        {
            "doctype": "Employee",
            "read": 1,
            "write": 1
        },
        {
            "doctype": "Salary Slip",
            "read": 1,
            "write": 0
        }
    ]
}).insert(ignore_permissions=True)
```

## Custom Permission Query

### Example: Department-based Access

```python
# In permission.py
def department_permission_query(doctype, user):
    emp = frappe.get_doc("User", user).get_value()
    if emp.department:
        return {"department": emp.department}
    return {"department": ""}
```

## Setup Permissions

```bash
# Reset all permissions
bench execute frappe.core.doctype.doctype.doctype.rebuild_doctype_from_db --kwargs '{"doctype": "Employee"}'

# Apply permission changes
bench migrate

# Clear cache
bench clear-cache
```

## Audit Trail

Enable to track who modified what:
1. Go to Setup → Customize Form
2. Check "Track Changes"
3. Save

View changes in Document History.

## Best Practices

- [ ] Use roles instead of individual user permissions
- [ ] Document custom permission logic
- [ ] Test with test users before deployment
- [ ] Review permissions quarterly
- [ ] Keep role names consistent
- [ ] Audit sensitive operations

