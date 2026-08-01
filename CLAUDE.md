# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Saral HR — attendance, payroll, and employee management app on the Frappe Framework (v15+) with Frappe UI (VueJS). Installed as an app inside a Frappe bench (`~/saral_hr_bench`), not run standalone. Default dev site: `saral.localhost`, admin credentials `administrator`/`admin` unless stated otherwise.

Always load and use the `saral-hr-development` skill (`.github/skills/saral-hr-development/SKILL.md`) for workflow-specific guidance (salary slip generation, payroll, loans, reports, attendance, permissions) — it has quick commands and doctype references per module under `references/`.

## Commands

```bash
# Install / reinstall app into a bench site
bench get-app saral_hr ~/saral_hr_bench/apps/saral_hr
bench install-app saral_hr
bench migrate

# Run all tests
bench --site saral.localhost run-tests --app saral_hr

# Run a single doctype's tests
bench run-tests saral_hr.saral_hr.doctype.salary_slip.test_salary_slip

# Install-guard test (what CI runs)
bench --site saral.localhost set-config allow_tests true
bench --site saral.localhost run-tests --app saral_hr --module saral_hr.tests.test_install

# Fixtures
bench export-fixtures --app saral_hr
bench import-fixtures --app saral_hr

# Frontend
bench clear-cache
bench build
bench watch
```

CI (`.github/workflows/ci.yml`) spins up a fresh bench + MariaDB against `develop`, installs the app, and runs `saral_hr.tests.test_install` only — this is the install/migrate-consistency guard, not full functional coverage. It's driven by `.github/helpers/install.sh`.

## Architecture

Standard Frappe app layout: one module (`Saral Hr`, per `modules.txt`), all doctypes flat under `saral_hr/saral_hr/doctype/`, reports under `saral_hr/saral_hr/report/`, custom desk pages under `saral_hr/saral_hr/page/`. Each doctype directory follows Frappe convention: `<name>.json` (schema), `<name>.py` (controller), `<name>.js` (client script), `test_<name>.py`.

### Permission model

Row-level access is company-scoped via a two-part mechanism:
- `saral_hr/permission.py` — `permission_query_conditions` functions (registered in `hooks.py`) restrict list/report queries per doctype (`Company Link`, `Employee`, `Attendance`, `Salary Structure Assignment`, `Salary Slip`, `Variable Pay Assignment`) to companies the user has a `User Permission` for, via joins through `Company Link` (which maps employee → company). `Saral HR Manager` role bypasses all restrictions (empty condition).
- Two roles drive access: `Saral HR Manager` (full) and `Saral HR User` (limited, company-scoped).

When adding a new doctype that should be company-scoped, add both a permission_query_conditions function here and the hooks.py entry — there's no other enforcement layer.

### Install / migrate lifecycle (`saral_hr/install.py`)

- `after_install`: creates the two roles, seeds a large fixed catalog of `Salary Component` records (PF/ESI/PT/LWF earning & deduction components with their calculation flags), then calls `ensure_desk_home_consistent()`.
- `after_migrate`: calls `ensure_desk_home_consistent()` only.
- `ensure_desk_home_consistent()` exists to prevent a known Desk refresh loop: Frappe can leave `setup_complete=1` while `desktop:home_page` is still `setup-wizard`, causing an infinite `/app` ↔ setup-wizard redirect. This function detects and repairs that combination. See README "Known issues" for the manual fix on already-broken sites. Any change to install/migrate hooks should preserve this call.

### Fixtures (`hooks.py`)

Exported/imported via the `fixtures` hook, filtered to app-owned records only: the `Saral HR` workspace, the two roles, `Custom DocPerm` for those roles, four named print formats, `Report` where `module = "Saral HR"`, and `Custom Field` on `Salary Slip`. When adding a new report, print format, or custom field meant to ship with the app, it must match one of these filters (or the filter needs updating) or `bench export-fixtures` won't pick it up.

### Payroll domain shape

Salary flow: `Salary Component` → `Salary Structure` → `Salary Structure Assignment` (per employee) → `Salary Slip` (+ `Salary Details` line items). Deduction components carry calculation-mode flags rather than separate doctypes: `is_pf_component`/`pf_calculation_based_on`/`pf_percentage`/`pf_cap_amount`, `is_esic_component`/`esic_calculation_based_on`/`esic_percentage`, `is_pt_component`, `employer_contribution` (splits employer- vs employee-side contributions), `is_daily_rate` / `depends_on_payment_days` / `depends_on_physical_working_days` (different proration bases for daily-wage vs monthly staff — see `daily_rates_worker` / `attendance_daily_rate`). Loans/advances are a parallel track: `Employee Loan Advance` → `Employee Loan Advance Schedule`, interacting with payroll via `Employee Salary Hold`.

Statutory/compliance reports (income tax, PT, ESI, LWF, PF, bank advice, wages register, loan register, etc.) live under `saral_hr/saral_hr/report/` and read from submitted (`docstatus=1`) Salary Slip / Attendance data — an empty report usually means unsubmitted documents or a date-filter mismatch, not a query bug.

## Contributing conventions (from AGENTS.md / README)

- Branch from `develop` using `feat/` or `fix/` prefixes; `develop` is protected (PRs required, CI must pass, no direct pushes).
- Commit the spec/plan before development commits; commit after each meaningful phase; reconcile spec and log progress after each phase.
- Comments only to explain *why*, never *how*.
- When a backend DocType field is added that's surfaced in the frontend (e.g. settings panels), the corresponding frontend component must be updated to match — there is no automatic sync, fields are enumerated explicitly on both sides.
- Bug fixes need at least a unit test; verify it actually catches the bug by temporarily reverting the fix. Bigger features/workflows need Playwright e2e tests.
- PR descriptions stay minimal: either Problem/Solution (bugs) or Why/What/How (features), against `develop`, after CI (`CI / Success`) passes.
