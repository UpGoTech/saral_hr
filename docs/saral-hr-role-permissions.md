# Saral HR role permissions

Source of truth as of this file: DocType JSON `permissions`, `hooks.py`, `permission.py`, `install.py`, `fixtures/role.json`, `fixtures/custom_docperm.json`, Page/Report/Workspace JSON, and extra Python checks on Desk pages.

Two custom roles exist. Both have **Desk access**. They are created on install (`saral_hr/install.py`) and exported as fixtures.

| Role | Desk | Created in |
|---|---|---|
| **Saral HR Manager** | Yes | `after_install` + `fixtures/role.json` |
| **Saral HR User** | Yes | `after_install` + `fixtures/role.json` |

Frappe ORs every matching permission row. Effective access below is **DocType JSON ∪ Custom DocPerm**.

---

## How the two roles differ

**Saral HR Manager** is the company-wide HR admin:

- Full create / write / delete on almost every Saral DocType (masters, employees, payroll, attendance, loans).
- Sees **all companies**. `permission_query_conditions` returns no extra filter.
- Can run Data Cleansing mutations.
- Can edit Frappe **Page**, **Gender**, **Salutation**, and **Shift Assignment** (User cannot).

**Saral HR User** is the company-scoped operator:

- **Read-only** on Employee and most masters (Company, Department, Designation, Salary Structure, …).
- **Can write** day-to-day transactions: Attendance, Leave, Salary Slip, SSA, Loans, Variable Pay, Company Link, etc.
- List views for Employee / Attendance / Company Link / SSA / Salary Slip are limited to companies set in **User Permission → Company**. If none are set, those lists are empty (`1=0`).
- Can open Data Cleansing but **cannot** cleanse; Manager only.

`hooks.py` does **not** register a `has_permission` map. Record filtering is only via `permission_query_conditions`.

---

## Record-level filters (`saral_hr/permission.py`)

Registered in `hooks.py` → `permission_query_conditions`.

| DocType | Manager | User |
|---|---|---|
| Company Link | All rows | `company` in User Permissions (Company). No companies → nothing. |
| Employee | All rows | Employees that have a Company Link in those companies. No companies → nothing. |
| Attendance | All rows | Attendance whose employee is in those companies. No companies → nothing. |
| Salary Structure Assignment | All rows | `company` in User Permissions. No companies → nothing. |
| Salary Slip | All rows | `company` in User Permissions. No companies → nothing. |
| Variable Pay Assignment | All rows | **Also all rows** (User is unrestricted here). Other roles still company-filtered. |

Pages such as Salary Statistics apply the same idea in Python: Manager / System Manager → all companies; User → only User Permission companies (none → no access).

Employee Profile, Mark Attendance, Salary Insight, Attendance Dashboard, Overview only special-case **System Manager** for employee User Permissions — they do **not** treat Saral HR Manager as a bypass for Employee-level User Permissions.

---

## Desk pages

| Page | Manager | User | Extra Python |
|---|---|---|---|
| Saral HR Overview | Yes | Yes | Employee User Permission filter (not Manager-exempt) |
| Employee Profile | Yes | Yes | Same |
| Mark Attendance | Yes | Yes | Same + Company User Permissions for company list |
| Attendance Dashboard | Yes | Yes | Employee User Permission filter |
| Daily Wage Attendance | Yes | Yes | — |
| Salary Calculator | Yes | Yes | — |
| Salary Insight | Yes | Yes | Employee User Permission filter |
| Salary Statistics | Yes | Yes | Manager sees all companies; User needs Company User Permissions |
| Data Cleansing | Yes | Yes | User may **view**; only Manager / System Manager / Administrator may **mutate** |
| Generate Monthly Loan Dues | Yes | Yes | Also System Manager |
| CTC Calculator | **No** | **No** | Page roles = `HR User` only — neither Saral role is listed |

Workspace **Saral HR** is assigned to both roles (`public: 1`).

---

## Reports

All Saral HR Script Reports list **both** roles (loan ledgers also list System Manager). Running a report still requires `report` + `read` on the ref DocType.

| Report | Ref DocType |
|---|---|
| Attendance Daily Rate Workers Report | Attendance Daily Rate |
| Bank Advice | Salary Slip |
| Other Bank Advice | Salary Slip |
| Company Enrollment Summary | Salary Structure Assignment (Python: Manager sees all companies; User is company-scoped) |
| Educational Allowance Register | Salary Slip |
| Employee Loan Ledger | Employee Loan |
| Loan Ledger | Employee Loan |
| Employee Timeline Report | Company Link |
| ESI Register | Salary Slip |
| Income Tax Report | Salary Slip |
| Labour Welfare Fund Register | Salary Slip |
| Monthly Attendance Report | Attendance |
| Monthly Salary Register Old Format Net Payable | Salary Slip |
| Payroll Report | Salary Slip |
| Professional Tax Register | Salary Slip |
| Provident Fund Register | Salary Slip |
| Retention Deposit Register | Salary Slip |
| Salary Summary | Salary Slip |
| Salary Summary Individual Employee | Salary Slip |
| Transaction Checklist | Salary Slip |
| Variable Pay Register | Salary Slip |

---

## DocType access (effective)

Legend: **CRUD** = read/write/create/delete. **Full + submit/cancel** = CRUD plus submit, cancel, amend. **Read** = no write/create/delete.

### Same for Manager and User (write)

| DocType | Access |
|---|---|
| Additional Deductions | Full + submit/cancel |
| Additional Salary | Full + submit/cancel |
| Attendance | CRUD |
| Attendance Daily Rate | CRUD |
| Branch | CRUD |
| Company Link | CRUD |
| Daily Rates Worker | CRUD |
| Employee Loan | Full + submit/cancel |
| Employee Loan Due | CRUD |
| Employee Salary Hold | Full + submit/cancel |
| Grade | CRUD |
| Leave Allocation | CRUD |
| Leave Application | CRUD |
| Salary Slip | Full + submit/cancel |
| Salary Structure Assignment | Full + submit/cancel |
| Shift Type | CRUD |
| Variable Pay Assignment | CRUD |
| Currency (Frappe core, Custom DocPerm) | CRUD |
| Role (Frappe core, Custom DocPerm) | CRUD |

### Manager writes, User read-only

| DocType | Manager | User |
|---|---|---|
| Employee | CRUD | Read |
| Company | CRUD | Read |
| Department | CRUD | Read |
| Designation | CRUD | Read |
| Division | CRUD | Read |
| Category | CRUD | Read |
| Bank Name | CRUD | Read |
| Holiday List | CRUD | Read |
| Leave Types | CRUD | Read |
| Salary Component | CRUD | Read |
| Salary Structure | CRUD | Read |
| Skill Rate Revision | Full + submit/cancel | Read |
| Employee Checkin | CRUD | Read |
| Biometric machine | CRUD | Read |
| Biometric attendance log | CRUD | Read |
| Biometric sync settings (Single) | CRUD | Read (select only in JSON) |
| Data Cleansing Log | Create + read (no write/delete) | Read |

### Manager only (User has no DocPerm)

| DocType | Notes |
|---|---|
| Shift Assignment | User cannot open this DocType |
| Gender | Custom DocPerm, Manager only |
| Salutation | Custom DocPerm, Manager only |
| Page | Custom DocPerm, Manager can edit Desk Pages |

### Partial

| DocType | Manager | User |
|---|---|---|
| Ctc Calculator Record | CRUD | Create + write, **no delete** |

Child tables (Holiday, Salary Details, Variable Pay Detail Table, …) have no own roles; they follow the parent DocType.

---

## Custom DocPerm vs DocType JSON

`fixtures/custom_docperm.json` is loaded because `hooks.py` exports Custom DocPerm for these two roles.

- For **Frappe core** DocTypes (Currency, Gender, Page, Role, Salutation) this fixture is the only Saral grant.
- For **Saral** DocTypes the fixture often **duplicates** JSON and adds `import`.
- Frappe **adds** rows; it does not replace JSON. Example: Company Link User is read-only in Custom DocPerm but **CRUD in DocType JSON**, so User can still write Company Link.

---

## Notable gaps / caveats

1. **CTC Calculator page** is not granted to either Saral role (`HR User` only).
2. **Shift Assignment** is Manager-only.
3. **Saral HR User can CRUD the Role DocType** via Custom DocPerm — they can create/edit roles if they find the form.
4. **Variable Pay Assignment** list is not company-filtered for Saral HR User (unlike Employee / Slip / SSA).
5. `has_permission` in `hooks.py` is commented out; only query conditions apply.
6. User with **no Company User Permission** sees empty Employee / Attendance / Company Link / SSA / Salary Slip lists.

---

## Where this is defined

| Layer | File |
|---|---|
| Role records | `saral_hr/fixtures/role.json`, `saral_hr/install.py` |
| Extra DocPerm | `saral_hr/fixtures/custom_docperm.json` |
| DocType roles | each `saral_hr/saral_hr/doctype/<name>/<name>.json` → `permissions` |
| Query conditions | `saral_hr/hooks.py`, `saral_hr/permission.py` |
| Page roles | `saral_hr/saral_hr/page/<page>/<page>.json` |
| Report roles | `saral_hr/saral_hr/report/<report>/<report>.json` |
| Workspace | `saral_hr/saral_hr/workspace/saral_hr/saral_hr.json` |
| Data Cleansing | `saral_hr/saral_hr/page/data_cleansing/data_cleansing.py` |
| Uninstall cleanup | `saral_hr/uninstall.py` |
