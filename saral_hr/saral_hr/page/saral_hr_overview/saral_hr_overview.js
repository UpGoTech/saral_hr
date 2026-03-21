frappe.pages["saral-hr-overview"].on_page_load = function (wrapper) {

	const page = frappe.ui.make_app_page({
		parent:        wrapper,
		title:         "HR Workforce & Payroll Overview",
		single_column: true
	});

	// ── Styles ───────────────────────────────────────────────────────────────
	frappe.dom.set_style(`
		.sho-wrap { padding: 0 16px 32px; }

		/* ── Filters ── */
		.sho-filters {
			display: flex;
			flex-wrap: wrap;
			align-items: flex-end;
			gap: 12px;
			padding: 16px 0 24px;
		}
		.sho-filter-group { display: flex; flex-direction: column; gap: 4px; }
		.sho-filter-label { font-size: 11px; color: var(--text-muted); font-weight: 500; }

		/* ── Section headings ── */
		.sho-section {
			font-size: 11px;
			font-weight: 600;
			color: var(--text-muted);
			text-transform: uppercase;
			letter-spacing: 0.07em;
			margin: 24px 0 10px;
		}

		/* ── KPI grid ── */
		.sho-kpi-grid {
			display: grid;
			grid-template-columns: repeat(auto-fit, minmax(155px, 1fr));
			gap: 10px;
		}
		.sho-kpi {
			background: var(--control-bg);
			border-radius: var(--border-radius-md);
			padding: 13px 15px;
			display: flex;
			flex-direction: column;
			justify-content: space-between;
			min-height: 100px;
		}
		.sho-kpi-label { font-size: 11px; color: var(--text-muted); line-height: 1.4; }
		.sho-kpi-bottom { display: flex; flex-direction: column; margin-top: 10px; }
		.sho-kpi-val   { font-size: 24px; font-weight: 600; color: var(--text-color); line-height: 1; }
		.sho-kpi-sub   { font-size: 11px; color: var(--text-light); margin-top: 5px; }

		/* alert kpi (red tint) */
		.sho-kpi.alert-card { background: var(--alert-bg, #fff5f5); }
		.sho-kpi.alert-card .sho-kpi-val { color: var(--red); }

		/* ── Statutory bar ── */
		.sho-stat-grid {
			display: grid;
			grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
			gap: 10px;
		}
		.sho-stat-card {
			background: var(--control-bg);
			border-radius: var(--border-radius-md);
			padding: 12px 15px;
		}
		.sho-stat-title { font-size: 12px; font-weight: 500; color: var(--text-color); margin-bottom: 6px; }
		.sho-stat-bar-bg {
			height: 6px;
			background: var(--border-color);
			border-radius: 3px;
			overflow: hidden;
			margin-bottom: 5px;
		}
		.sho-stat-bar-fill {
			height: 100%;
			border-radius: 3px;
			background: var(--blue);
			transition: width 0.4s ease;
		}
		.sho-stat-nums { font-size: 11px; color: var(--text-muted); }

		/* ── Divider ── */
		.sho-divider { height: 1px; background: var(--border-color); margin: 4px 0; }

		/* ── Table ── */
		.sho-table-outer {
			overflow-x: auto;
			border: 1px solid var(--border-color);
			border-radius: var(--border-radius-md);
		}
		.sho-table {
			width: 100%;
			border-collapse: collapse;
			font-size: 13px;
			min-width: 780px;
		}
		.sho-table thead tr { background: var(--subtle-fg); }
		.sho-table th {
			padding: 9px 11px;
			font-size: 11px;
			font-weight: 600;
			color: var(--text-muted);
			border-bottom: 1px solid var(--border-color);
			text-align: center;
			white-space: nowrap;
		}
		.sho-table th.l { text-align: left; }
		.sho-table td {
			padding: 7px 11px;
			text-align: center;
			color: var(--text-color);
			border-bottom: 1px solid var(--border-color);
		}
		.sho-table td.l { text-align: left; font-weight: 500; color: var(--text-muted); }
		.sho-table tbody tr:last-child td { border-bottom: none; }
		.sho-table tbody tr:hover td { background: var(--control-bg); }

		/* ── Classification table ── */
		.sho-cls-outer {
			overflow-x: auto;
			border: 1px solid var(--border-color);
			border-radius: var(--border-radius-md);
		}
		.sho-cls-table {
			width: 100%;
			border-collapse: collapse;
			font-size: 13px;
		}
		.sho-cls-table thead tr { background: var(--subtle-fg); }
		.sho-cls-table th {
			padding: 8px 12px;
			font-size: 11px;
			font-weight: 600;
			color: var(--text-muted);
			border-bottom: 1px solid var(--border-color);
			text-align: center;
		}
		.sho-cls-table th.l { text-align: left; }
		.sho-cls-table td {
			padding: 7px 12px;
			text-align: center;
			color: var(--text-color);
			border-bottom: 1px solid var(--border-color);
		}
		.sho-cls-table td.l { text-align: left; font-weight: 500; }
		.sho-cls-table tbody tr:last-child td { border-bottom: none; }
		.sho-cls-table tfoot td {
			padding: 8px 12px;
			font-weight: 600;
			font-size: 12px;
			border-top: 1px solid var(--border-color);
			background: var(--subtle-fg);
			text-align: center;
		}
		.sho-cls-table tfoot td.l { text-align: left; }

		/* ── Spinner ── */
		.sho-spinner { text-align: center; padding: 36px 0; color: var(--text-muted); font-size: 13px; }

		/* badge */
		.sho-badge {
			display: inline-block;
			padding: 2px 8px;
			border-radius: 99px;
			font-size: 11px;
			font-weight: 500;
		}
		.badge-red  { background: var(--red-highlight, #fff0f0); color: var(--red);   }
		.badge-blue { background: var(--blue-highlight,#f0f4ff); color: var(--blue);  }
	`);

	// ── Page skeleton ────────────────────────────────────────────────────────
	const $body = $(wrapper).find(".page-content");
	$body.empty();

	const $w = $('<div class="sho-wrap"></div>').appendTo($body);

	// Filter bar
	const $filters = $('<div class="sho-filters"></div>').appendTo($w);

	$filters.append(`
		<div class="sho-filter-group">
			<span class="sho-filter-label">Company</span>
			<select id="sho-company" class="form-control"
				style="min-width:180px;height:32px;font-size:13px;">
				<option value="">Loading…</option>
			</select>
		</div>
		<div class="sho-filter-group">
			<span class="sho-filter-label">From</span>
			<input type="date" id="sho-from" class="form-control"
				value="2025-04-01" style="height:32px;font-size:13px;width:140px;" />
		</div>
		<div class="sho-filter-group">
			<span class="sho-filter-label">To</span>
			<input type="date" id="sho-to" class="form-control"
				value="2026-03-31" style="height:32px;font-size:13px;width:140px;" />
		</div>
		<div class="sho-filter-group">
			<span class="sho-filter-label">&nbsp;</span>
			<button id="sho-apply" class="btn btn-primary btn-sm"
				style="height:32px;padding:0 18px;">Apply</button>
		</div>
	`);

	// Sections (placeholders that get filled on load)
	$w.append('<div class="sho-section">Company snapshot</div>');
	$w.append('<div id="sho-kpi-snapshot" class="sho-kpi-grid"></div>');

	$w.append('<div class="sho-section">Master data</div>');
	$w.append('<div id="sho-kpi-masters" class="sho-kpi-grid"></div>');

	$w.append('<div class="sho-section">Statutory completeness</div>');
	$w.append('<div id="sho-statutory" class="sho-stat-grid"></div>');

	$w.append('<div class="sho-divider" style="margin:20px 0;"></div>');

	$w.append('<div class="sho-section">Monthly attendance &amp; payroll tracker</div>');
	$w.append('<div id="sho-monthly"></div>');

	$w.append('<div class="sho-section" style="margin-top:28px;">Employee classification breakdown</div>');
	$w.append('<div id="sho-classification"></div>');

	// ── Load companies ───────────────────────────────────────────────────────
	frappe.call({
		method: "saral_hr.saral_hr.page.saral_hr_overview.saral_hr_overview.get_companies",
		callback(r) {
			const $sel = $("#sho-company", wrapper);
			$sel.empty();
			(r.message || []).forEach(c => $sel.append(`<option value="${c}">${c}</option>`));
			if (r.message && r.message.length) loadAll();
		}
	});

	// ── Apply ────────────────────────────────────────────────────────────────
	$("#sho-apply", wrapper).on("click", loadAll);

	// ── Load all data ────────────────────────────────────────────────────────
	function loadAll() {
		const company   = $("#sho-company", wrapper).val();
		const from_date = $("#sho-from",    wrapper).val();
		const to_date   = $("#sho-to",      wrapper).val();

		if (!company)              return frappe.msgprint("Please select a company.");
		if (!from_date || !to_date) return frappe.msgprint("Please select From and To dates.");
		if (from_date > to_date)   return frappe.msgprint("From date cannot be after To date.");

		// Spinners
		["sho-kpi-snapshot","sho-kpi-masters","sho-statutory","sho-monthly","sho-classification"]
			.forEach(id => $(`#${id}`, wrapper).html('<div class="sho-spinner">Loading…</div>'));

		Promise.all([
			frappe.call({
				method: "saral_hr.saral_hr.page.saral_hr_overview.saral_hr_overview.get_kpi_data",
				args: { company, from_date, to_date }
			}),
			frappe.call({
				method: "saral_hr.saral_hr.page.saral_hr_overview.saral_hr_overview.get_monthly_data",
				args: { company, from_date, to_date }
			}),
			frappe.call({
				method: "saral_hr.saral_hr.page.saral_hr_overview.saral_hr_overview.get_classification_data",
				args: { company }
			})
		]).then(([kpiR, monthR, clsR]) => {
			renderSnapshot(kpiR.message  || {});
			renderMasters(kpiR.message   || {});
			renderStatutory(kpiR.message || {});
			renderMonthly(monthR.message || []);
			renderClassification(clsR.message || []);
		}).catch(err => {
			console.error(err);
			frappe.msgprint("Error loading dashboard data. Check console.");
		});
	}

	// ── Render: Company snapshot KPIs ────────────────────────────────────────
	function renderSnapshot(d) {
		const cards = [
			{
				label: "Total registered employees",
				value: d.total_registered,
				sub:   "includes inactive / resigned"
			},
			{
				label: "Active employees",
				value: d.total_active,
				sub:   "currently in company"
			},
			{
				label: "Salary structures",
				value: d.salary_structures,
				sub:   "defined for this company"
			},
			{
				label: "Salary structure assignments",
				value: d.ssa_count,
				sub:   "submitted, in selected period"
			},
			{
				label: "Holiday days in range",
				value: d.holiday_count,
				sub:   "from default holiday list"
			},
			{
				label: "Employees on salary hold",
				value: d.on_hold_count,
				sub:   "status: On Hold",
				alert: d.on_hold_count > 0
			},
			{
				label: "Active without assignment",
				value: d.without_assignment,
				sub:   "no salary structure in period",
				alert: d.without_assignment > 0
			}
		];

		$("#sho-kpi-snapshot", wrapper).html(
			cards.map(c => kpiCard(c)).join("")
		);
	}

	// ── Render: Global masters KPIs ──────────────────────────────────────────
	function renderMasters(d) {
		const cards = [
			{ label: "Departments",       value: d.dept_count,        sub: "global master" },
			{ label: "Designations",      value: d.designation_count, sub: "global master" },
			{ label: "Categories",        value: d.category_count,    sub: "global master" },
			{ label: "Divisions",         value: d.division_count,    sub: "global master" },
			{ label: "Salary components", value: d.salary_components, sub: "earning + deduction types" }
		];

		$("#sho-kpi-masters", wrapper).html(
			cards.map(c => kpiCard(c)).join("")
		);
	}

	// ── Render: Statutory completeness ──────────────────────────────────────
	function renderStatutory(d) {
		const active = d.total_active || 0;

		function statCard(title, filled, total) {
			const pct = total > 0 ? Math.round((filled / total) * 100) : 0;
			const color = pct >= 90 ? "var(--green)" : pct >= 60 ? "var(--orange)" : "var(--red)";
			return `
				<div class="sho-stat-card">
					<div class="sho-stat-title">${title}</div>
					<div class="sho-stat-bar-bg">
						<div class="sho-stat-bar-fill" style="width:${pct}%;background:${color};"></div>
					</div>
					<div class="sho-stat-nums">${filled} of ${total} filled &nbsp;·&nbsp; ${pct}%</div>
				</div>`;
		}

		$("#sho-statutory", wrapper).html(
			statCard("ESIC number filled",   d.esic_filled, active) +
			statCard("PF UAN number filled", d.pf_filled,   active)
		);
	}

	// ── Render: Monthly table ────────────────────────────────────────────────
	function renderMonthly(rows) {
		if (!rows.length) {
			return $("#sho-monthly", wrapper).html(
				'<div class="sho-spinner">No data for selected range.</div>'
			);
		}

		const thead = `
			<thead>
				<tr>
					<th class="l">Month</th>
					<th>Active<br>employees</th>
					<th>Attendance<br>entries</th>
					<th>Min att.<br>(days)</th>
					<th>Max att.<br>(days)</th>
					<th>Salary slips<br>generated</th>
					<th>On hold</th>
					<th>Absent<br>days</th>
					<th>LWP<br>days</th>
				</tr>
			</thead>`;

		const tbody = rows.map(r => `
			<tr>
				<td class="l">${r.month}</td>
				<td>${r.active_count}</td>
				<td>${r.att_total}</td>
				<td>${r.min_att}</td>
				<td>${r.max_att}</td>
				<td>${r.slip_count}</td>
				<td>${r.hold_count > 0
					? `<span class="sho-badge badge-red">${r.hold_count}</span>`
					: "—"}</td>
				<td>${r.absent_total > 0
					? `<span class="sho-badge badge-red">${r.absent_total}</span>`
					: r.absent_total}</td>
				<td>${r.lwp_total > 0
					? `<span class="sho-badge badge-blue">${r.lwp_total}</span>`
					: r.lwp_total}</td>
			</tr>`).join("");

		$("#sho-monthly", wrapper).html(`
			<div class="sho-table-outer">
				<table class="sho-table">
					${thead}
					<tbody>${tbody}</tbody>
				</table>
			</div>`);
	}


	// ── Render: Classification breakdown ────────────────────────────────────
	function renderClassification(rows) {
		if (!rows.length) {
			return $("#sho-classification", wrapper).html(
				'<div class="sho-spinner">No classification data.</div>'
			);
		}

		// Separate categories: ones with skill subtypes vs plain count-only
		const withSkill    = rows.filter(r => r.has_subtype);
		const withoutSkill = rows.filter(r => !r.has_subtype);

		let html = "";

		// ── Table 1: Categories WITH skill subtypes ──────────────────────────
		if (withSkill.length) {
			// Always show all 3 fixed skill type columns + any extras + "Not set" if present
			const SKILL_ORDER = ["Skilled", "Semi-skilled", "Unskilled"];
			const extraSkills = [...new Set(
				withSkill.flatMap(r => Object.keys(r.counts))
			)].filter(s => !SKILL_ORDER.includes(s) && s !== "Not set").sort();
			const skillCols = [
				...SKILL_ORDER,   // always show Skilled, Semi-skilled, Unskilled
				// ...extraSkills
			];

			const thSkills = skillCols.map(s =>
				`<th>${s}</th>`
			).join("");

			const tbody1 = withSkill.map(r => {
				const cells = skillCols.map(s =>
					`<td>${r.counts[s] || "—"}</td>`
				).join("");
				return `<tr><td class="l">${r.category}</td>${cells}<td><strong>${r.total}</strong></td></tr>`;
			}).join("");

			const grandTotal1 = withSkill.reduce((s, r) => s + r.total, 0);
			const tfootCells1 = skillCols.map(s =>
				`<td><strong>${withSkill.reduce((sum, r) => sum + (r.counts[s] || 0), 0)}</strong></td>`
			).join("");

			html += `
				<div class="sho-section" style="margin-top:0;">Categories with skill subtypes</div>
				<div class="sho-cls-outer" style="margin-bottom:16px;">
					<table class="sho-cls-table">
						<thead><tr>
							<th class="l">Category</th>
							${thSkills}
							<th>Total</th>
						</tr></thead>
						<tbody>${tbody1}</tbody>
						<tfoot><tr>
							<td class="l">Total</td>${tfootCells1}
							<td><strong>${grandTotal1}</strong></td>
						</tr></tfoot>
					</table>
				</div>`;
		}

		// ── Table 2: Categories WITHOUT skill subtypes ───────────────────────
		if (withoutSkill.length) {
			const grandTotal2 = withoutSkill.reduce((s, r) => s + r.total, 0);

			const tbody2 = withoutSkill.map(r =>
				`<tr><td class="l">${r.category}</td><td><strong>${r.total}</strong></td></tr>`
			).join("");

			html += `
				<div class="sho-section" style="margin-top:${withSkill.length ? "16px" : "0"};">Other categories</div>
				<div class="sho-cls-outer">
					<table class="sho-cls-table">
						<thead><tr>
							<th class="l">Category</th>
							<th>Total</th>
						</tr></thead>
						<tbody>${tbody2}</tbody>
						<tfoot><tr>
							<td class="l">Total</td>
							<td><strong>${grandTotal2}</strong></td>
						</tr></tfoot>
					</table>
				</div>`;
		}

		$("#sho-classification", wrapper).html(html);
	}


	// ── KPI card helper ──────────────────────────────────────────────────────
	function kpiCard({ label, value, sub, alert }) {
		return `
			<div class="sho-kpi${alert ? " alert-card" : ""}">
				<div class="sho-kpi-label">${label}</div>
				<div class="sho-kpi-bottom">
					<div class="sho-kpi-val">${value ?? "—"}</div>
					<div class="sho-kpi-sub">${sub}</div>
				</div>
			</div>`;
	}
};