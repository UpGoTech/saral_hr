# Specs progress

Single board for all specs in this folder. New specs get the next number (`002-…`, `003-…`). Update status here when work moves.

| # | Spec | Status | Notes |
|---|------|--------|-------|
| 001 | [Company list employee counts](./001-company-list-employee-counts.md) | done | List + form headcount from Company Link; tests passing |
| 002 | [Maharashtra Professional Tax](./002-maharashtra-professional-tax.md) | in progress | Per-slab Feb amounts; Female no Feb surcharge; multi-state deferred |
| 003 | [Attendance Dashboard yearly](./003-attendance-dashboard-yearly.md) | in progress | Yearly headcount + full-calendar marking coverage |

## Status legend

| Status | Meaning |
|--------|---------|
| `planned` | Spec written; not started |
| `in progress` | Implementation underway on a `feat/` / `fix/` branch |
| `done` | Merged / complete; keep the row for history |
| `cancelled` | Won't do; leave a short note |

## Conventions

- One markdown file per spec: `specs/NNN-short-slug.md`
- Numbers are zero-padded (`001`, `002`, …) so files sort naturally
- Commit the spec before development commits (see `AGENTS.md`)
- Reconcile this board after each meaningful phase
