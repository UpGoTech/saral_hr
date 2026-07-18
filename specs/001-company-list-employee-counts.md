# 001 — Company list employee counts

| | |
|---|---|
| **Status** | done |
| **Branch** | `feat/company-list-employee-counts` |
| **Primary DocTypes** | Company, Company Link |

## Why?

Company list view should show headcount at a glance (staff, workers, total) without opening each company or running a report. Counts come from Company Link and must stay correct as employment links change.

## What?

On the **Company** Desk list (and a small read-only section on the Company form), show three columns/fields:

1. **Staff**
2. **Worker**
3. **Total** (= Staff + Workers)

Also fix the duplicate company name on the list (ID + Company field both showing the same value).

## How?

### Data model (Company)

Add three **Int** fields, read-only:

| Fieldname | Label | Notes |
|-----------|-------|--------|
| `no_of_staff` | Staff | `in_list_view` |
| `no_of_workers` | Worker | `in_list_view` |
| `total_no_of_employees` | Total | `in_list_view` |

Place them in a read-only **Headcount** section on the Company **Details** tab (near company / country).

### List view layout

- Show: primary company title + the three count columns
- **Remove** `in_list_view` from `country` (still on form)
- **Remove** `in_list_view` from the `company` Data field (avoids a second Company field column)
- Set `title_field` to `company` so the subject column uses the company name
- Set `frappe.listview_settings["Company"].hide_name_column = true` in `company_list.js` — required because with `title_field` set, Frappe still appends an **ID** column, and for `autoname: field:company` that ID equals the title (double name)

### Count rules

Source: `Company Link` where `company` = this Company.

| Rule | Decision |
|------|----------|
| Active filter | Only `is_active = 1` |
| Staff | `category == "Staff"` |
| Workers | `category == "Worker"` |
| Total | Staff + Workers only (ignore other categories) |
| Category matching | Hardcoded names `"Staff"` / `"Worker"` (same as Company Enrollment Summary) |

### Sync

1. Shared helper, e.g. `update_company_employee_counts(company: str)`, that:
   - Aggregates active Company Links by category
   - Writes the three Int fields via `frappe.db.set_value(..., update_modified=False)`
2. Call from **Company Link** on `after_insert`, `on_update`, `on_trash`
3. If `company` changes on update, recalculate **both** old and new company
4. **Backfill patch** (one-time on migrate) for all existing companies so counts are not stuck at 0 after deploy

### Tests (unit only)

Cover the helper + hooks:

- Active Staff / Worker increment the right fields; Total = sum
- `is_active = 0` excluded
- Other categories do not affect Total
- Trash / deactivate decreases counts
- Changing `company` on a link moves counts from old → new company

No Playwright for this spec.

### Out of scope

- Changing Company Enrollment Summary
- Configurable category → staff/worker mapping
- Nightly reconcile job (hooks + backfill are enough)
- Implementation in this planning session (spec only)

## Acceptance criteria

- [x] Company list shows company name once (not ID + Company duplicate)
- [x] List shows Staff, Worker, Total
- [x] Country is not a list column (still on form)
- [x] Form shows the three fields read-only in a Headcount section
- [x] Creating / updating / deleting active Company Links updates counts live
- [x] Inactive links do not count
- [x] Backfill sets correct counts for existing companies after migrate
- [x] Unit tests above pass on the test site

## Progress log

| Date | Note |
|------|------|
| 2026-07-18 | Spec written after grilling; status `planned` |
| 2026-07-18 | Implemented on `feat/company-list-employee-counts`: Company fields, recount helper, Company Link hooks (`after_delete` used instead of recount-in-`on_trash` so the deleted row is excluded), transfer SQL path recounts old company, backfill patch, unit tests (7) green |
| 2026-07-18 | Fix double name: `title_field` + no `in_list_view` on `company` were not enough — Frappe still appends an ID column when title_field ≠ name; added `company_list.js` with `hide_name_column: true` |
