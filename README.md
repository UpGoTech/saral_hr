## Saral HR

Attendance, payroll, and employee management on Frappe Framework.

#### License

mit

## Known issues

### Desk refresh loop after fresh install

**Symptom:** After login, Desk keeps reloading and never opens.

**Cause:** Frappe left setup in an inconsistent state:

- Setup is marked complete (`System Settings.setup_complete = 1`)
- Desk home is still the Setup Wizard (`desktop:home_page = setup-wizard`)

The Setup Wizard page sees setup as complete and redirects to `/app`. `/app` loads the wizard again as the home page → infinite refresh.

This can happen when `saral_hr` is installed around site setup (especially if setup is auto-marked complete without running the wizard’s normal finish path that sets `desktop:home_page` to `workspace`).

**Prevention (in this app):** `after_install` / `after_migrate` call `ensure_desk_home_consistent()` to set `desktop:home_page = workspace` and sync the `setup_complete` default when setup is already complete.

**Manual fix (existing sites):**

```bash
bench --site <site> console
```

```python
import frappe
if frappe.is_setup_complete():
    frappe.db.set_default("desktop:home_page", "workspace")
    frappe.db.set_default("setup_complete", 1)
    frappe.clear_cache()
```

Then hard-refresh the browser (or clear site data) and log in again.

**Install tip:** Prefer completing the Frappe Setup Wizard (or confirming Desk opens) before installing `saral_hr` on a brand-new site.
