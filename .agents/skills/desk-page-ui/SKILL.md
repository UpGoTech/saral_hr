---
name: desk-page-ui
description: >-
  Desk Page UI conventions for Saral HR Frappe pages (filters, Link autocomplete,
  breadcrumbs, no full-bleed, event handlers, responsive tables). Use whenever
  creating or editing a Desk Page under saral_hr/saral_hr/page/, or when the user
  mentions broken filters, clipped Link dropdowns, double button clicks, missing
  breadcrumbs, horizontal overflow, or "same errors as data cleansing" on a Desk
  page.
---

# Desk Page UI (Saral HR)

Canonical reference implementation: `saral_hr/saral_hr/page/data_cleansing/data_cleansing.js`.
Also applied on: `generate_monthly_loan_dues`.

When building or fixing any Desk **Page**, copy these patterns. Do not invent a one-off layout that reintroduces the same bugs.

## Hard rules

### 1. Never go full-bleed

```js
frappe.pages["my-page"].on_page_show = function (wrapper) {
	$("body").removeClass("full-width");  // keep workspace sidebar / Desk chrome
	// ...
};
```

### 2. Set navbar breadcrumbs every show

```js
function set_breadcrumbs() {
	const $nb = $("#navbar-breadcrumbs");
	if (!$nb.length) return;
	$nb.empty().append(
		`<li><a href="/app/saral-hr">${__("Saral HR")}</a></li>`,
		`<li><a href="/app/my-page">${__("My Page")}</a></li>`
	);
	document.title = __("My Page");
}
```

### 3. Filter row = field groups with one external label

- Use a `.xx-filter-row` flex wrap of `.xx-fg` groups.
- Each group has `.xx-fg-label` (uppercase, muted) **above** the control.
- Align controls with `align-items: flex-end`.
- Action buttons sit in their own `.xx-fg` with a spacer label (`&nbsp;`) so heights line up.
- Control height **32px**; radius **6px**; use CSS variables (`--border-color`, `--text-muted`, `--primary`).

### 4. Link controls must not clip autocomplete

Wrap Link mounts:

```html
<div class="xx-link-wrap"><div class="xx-employee"></div></div>
```

CSS must:

- Set filter card `overflow: visible; z-index: 20` (results card lower, e.g. `z-index: 1`).
- Hide the Link's built-in `.control-label` / `.help-box` (they break alignment).
- Raise awesomplete: `.awesomplete { z-index: 30 }` and `ul { z-index: 40; max-height: 240px; overflow-y: auto }`.
- Use `only_select: 1` on Link `df`.

After `refresh()`, explicitly hide:

```js
$main.find(".xx-employee .control-label, .xx-employee .help-box").hide();
```

### 5. Namespaced delegated events — always off before on

`on_page_show` rebuilds HTML but `$main` persists. Stacked handlers = double API calls / duplicate inserts.

```js
$main.off(".mypage");
$main.on("click.mypage", ".xx-load", handler);
```

Guard in-flight mutations with a `state.loading` / `state.generating` flag.

### 6. One primary "open period" action when Load+Generate would confuse

If the page both **reads** and **creates missing rows**, use a **single** primary button (e.g. Load / Scan / Open) that:

1. Creates missing rows only when the period is unlocked.
2. Always returns the full list for the filters.
3. Locks edit/save/add when the business period is closed (e.g. submitted salary slips exist).

Do not ship separate Load + Generate unless the user explicitly wants both.

### 7. Responsive: stack filters; swap table ↔ cards

- `@media (max-width: 720px)`: filter row `flex-direction: column`; full-width controls/buttons.
- `@media (max-width: 900px)`: hide wide table, show stacked cards (same data). Desktop: table only.
- Results card: `overflow: hidden` / table wrap `overflow-x: auto` — never let the page grow sideways.

### 8. Safe formatters

Prefer guarded helpers; Desk globals are not always present:

```js
function fmt_currency(v) {
	const n = flt(v);
	if (typeof format_currency === "function") {
		try { return format_currency(n); } catch (e) {}
	}
	return frappe.format(n, { fieldtype: "Currency" });
}
```

Use `flt` / `cint` from Desk; do not assume Node/browser polyfills.

### 9. Inject versioned page CSS; remove prior ids

```js
$("#xx-styles, #xx-styles-v1").remove();
const s = document.createElement("style");
s.id = "xx-styles-v2";
// ...
document.head.appendChild(s);
```

### 10. Period / year selects

For historical payroll pages, year options must cover prior FY (at least `currentYear - 3` … `+ 2`), not only the current year.

## Checklist before shipping a Desk Page

- [ ] `full-width` removed on show
- [ ] Breadcrumbs + `document.title`
- [ ] Filter field groups + aligned labels
- [ ] Link autocomplete not clipped
- [ ] `$main.off(".ns")` before `.on(".ns")`
- [ ] In-flight click guard
- [ ] Mobile filter stack + card fallback for wide grids
- [ ] No horizontal page overflow
- [ ] Unique constraints / idempotent create if the page inserts docs
- [ ] Hard-refresh note for the user after JS-only changes (`bench clear-cache` if needed)

## Anti-patterns (do not repeat)

- Raw `frappe-card` + inline flex with Link's own label still visible
- `$main.on("click", …)` without namespace / off on every show
- Separate Load + Generate that both create rows
- `overflow: hidden` on the filter card that hosts Link awesomplete
- Table-only UI with no mobile alternative
- Relying on `format_currency` without a fallback
