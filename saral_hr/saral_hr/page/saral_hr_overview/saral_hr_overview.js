frappe.pages["saral-hr-overview"].on_page_load = function (wrapper) {

	frappe.ui.make_app_page({
		parent: wrapper, title: "HR Workforce & Payroll Overview", single_column: true
	});

	// ── Styles ───────────────────────────────────────────────────────────────
	frappe.dom.set_style(`
		.sho-wrap { padding: 0 16px 40px; }

		/* filters */
		.sho-filters { display:flex; flex-wrap:wrap; align-items:flex-end; gap:12px; padding:16px 0 24px; }
		.sho-filter-group { display:flex; flex-direction:column; gap:4px; }
		.sho-filter-label { font-size:11px; color:var(--text-muted); font-weight:500; }

		/* section headings */
		.sho-section {
			font-size:11px; font-weight:600; color:var(--text-muted);
			text-transform:uppercase; letter-spacing:0.07em; margin:24px 0 10px;
		}
		.sho-divider { height:1px; background:var(--border-color); margin:20px 0; }

		/* KPI grid */
		.sho-kpi-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(155px,1fr)); gap:10px; }
		.sho-kpi {
			background:var(--control-bg); border-radius:var(--border-radius-md);
			padding:13px 15px; display:flex; flex-direction:column;
			justify-content:space-between; min-height:100px;
			cursor:pointer; transition:box-shadow 0.15s;
		}
		.sho-kpi:hover { box-shadow:0 0 0 1.5px var(--primary); }
		.sho-kpi.no-link { cursor:default; }
		.sho-kpi.no-link:hover { box-shadow:none; }
		.sho-kpi-label { font-size:11px; color:var(--text-muted); line-height:1.4; }
		.sho-kpi-bottom { display:flex; flex-direction:column; margin-top:10px; }
		.sho-kpi-val { font-size:24px; font-weight:600; color:var(--text-color); line-height:1; }
		.sho-kpi-sub { font-size:11px; color:var(--text-light); margin-top:5px; }
		.sho-kpi.alert-card { background:var(--alert-bg,#fff5f5); }
		.sho-kpi.alert-card .sho-kpi-val { color:var(--red); }

		/* statutory bars */
		.sho-stat-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:10px; }
		.sho-stat-card { background:var(--control-bg); border-radius:var(--border-radius-md); padding:12px 15px; }
		.sho-stat-title { font-size:12px; font-weight:500; color:var(--text-color); margin-bottom:6px; }
		.sho-stat-bar-bg { height:6px; background:var(--border-color); border-radius:3px; overflow:hidden; margin-bottom:5px; }
		.sho-stat-bar-fill { height:100%; border-radius:3px; transition:width 0.4s ease; }
		.sho-stat-nums { font-size:11px; color:var(--text-muted); }

		/* tables */
		.sho-table-outer { overflow-x:auto; border:1px solid var(--border-color); border-radius:var(--border-radius-md); }
		.sho-table { width:100%; border-collapse:collapse; font-size:13px; min-width:820px; }
		.sho-table thead tr { background:var(--subtle-fg); }
		.sho-table th { padding:9px 11px; font-size:11px; font-weight:600; color:var(--text-muted); border-bottom:1px solid var(--border-color); text-align:center; white-space:nowrap; }
		.sho-table th.l { text-align:left; }
		.sho-table td { padding:7px 11px; text-align:center; color:var(--text-color); border-bottom:1px solid var(--border-color); }
		.sho-table td.l { text-align:left; font-weight:500; color:var(--text-muted); }
		.sho-table tfoot td { padding:8px 11px; font-weight:600; font-size:12px; border-top:1px solid var(--border-color); background:var(--subtle-fg); text-align:center; }
		.sho-table tfoot td.l { text-align:left; }
		.sho-table tbody tr:last-child td { border-bottom:none; }
		.sho-table tbody tr:hover td { background:var(--control-bg); }
		.sho-table td a { color:var(--blue); text-decoration:none; }
		.sho-table td a:hover { text-decoration:underline; }

		/* classification tables */
		.sho-cls-outer { overflow-x:auto; border:1px solid var(--border-color); border-radius:var(--border-radius-md); }
		.sho-cls-table { width:100%; border-collapse:collapse; font-size:13px; }
		.sho-cls-table thead tr { background:var(--subtle-fg); }
		.sho-cls-table th { padding:8px 12px; font-size:11px; font-weight:600; color:var(--text-muted); border-bottom:1px solid var(--border-color); text-align:center; }
		.sho-cls-table th.l { text-align:left; }
		.sho-cls-table td { padding:7px 12px; text-align:center; color:var(--text-color); border-bottom:1px solid var(--border-color); }
		.sho-cls-table td.l { text-align:left; font-weight:500; }
		.sho-cls-table tbody tr:last-child td { border-bottom:none; }
		.sho-cls-table tfoot td { padding:8px 12px; font-weight:600; font-size:12px; border-top:1px solid var(--border-color); background:var(--subtle-fg); text-align:center; }
		.sho-cls-table tfoot td.l { text-align:left; }

		/* ── Zone layout ── */
		.sho-zone-2col {
			display: grid;
			grid-template-columns: 55% 1fr;
			gap: 0 24px;
			align-items: start;
		}
		.sho-zone-2col-equal {
			display: grid;
			grid-template-columns: 1fr 1fr;
			gap: 0 24px;
			align-items: start;
		}
		.sho-col { min-width: 0; }

		/* badges */
		.sho-badge { display:inline-block; padding:2px 8px; border-radius:99px; font-size:11px; font-weight:500; }
		.badge-red  { background:var(--red-highlight,#fff0f0); color:var(--red); }
		.badge-blue { background:var(--blue-highlight,#f0f4ff); color:var(--blue); }
		.badge-green { background:var(--green-highlight,#f0fff4); color:var(--green,#28a745); }
		.badge-orange { background:#fff8f0; color:#e67e22; }

		/* coverage bar inline */
		.sho-cov-wrap { display:inline-flex; align-items:center; gap:5px; }
		.sho-cov-bar { width:40px; height:5px; background:var(--border-color); border-radius:3px; overflow:hidden; }
		.sho-cov-fill { height:100%; border-radius:3px; }

		.sho-spinner { text-align:center; padding:36px 0; color:var(--text-muted); font-size:13px; }
	`);

	// ── Page skeleton ────────────────────────────────────────────────────────
	const $body = $(wrapper).find(".page-content");
	$body.empty();
	const $w = $('<div class="sho-wrap"></div>').appendTo($body);

	// ── Filter bar ───────────────────────────────────────────────────────────
	const $filters = $('<div class="sho-filters"></div>').appendTo($w);

	// Fiscal year quick-select options (generate last 3 + next FY)
	const fyOptions = (function () {
		const opts = [];
		const now  = frappe.datetime.now_date ? new Date() : new Date();
		const yr   = now.getFullYear();
		for (let y = yr - 2; y <= yr + 1; y++) {
			opts.push(`<option value="${y}-04-01|${y+1}-03-31">${y}-${String(y+1).slice(-2)} (Apr–Mar)</option>`);
		}
		return opts.join("");
	})();

	$filters.append(`
		<div class="sho-filter-group">
			<span class="sho-filter-label">Company</span>
			<select id="sho-company" class="form-control" style="min-width:180px;height:32px;font-size:13px;">
				<option value="">Loading…</option>
			</select>
		</div>
		<div class="sho-filter-group">
			<span class="sho-filter-label">Fiscal year</span>
			<select id="sho-fy" class="form-control" style="height:32px;font-size:13px;">
				<option value="">Custom</option>
				${fyOptions}
			</select>
		</div>
		<div class="sho-filter-group">
			<span class="sho-filter-label">From</span>
			<input type="date" id="sho-from" class="form-control" value="2025-04-01" style="height:32px;font-size:13px;width:140px;" />
		</div>
		<div class="sho-filter-group">
			<span class="sho-filter-label">To</span>
			<input type="date" id="sho-to" class="form-control" value="2026-03-31" style="height:32px;font-size:13px;width:140px;" />
		</div>
		<div class="sho-filter-group">
			<span class="sho-filter-label">&nbsp;</span>
			<button id="sho-apply" class="btn btn-primary btn-sm" style="height:32px;padding:0 18px;">Apply</button>
		</div>
		<div class="sho-filter-group" style="margin-left:auto;">
			<span class="sho-filter-label">&nbsp;</span>
			<span id="sho-refreshed" style="font-size:11px;color:var(--text-muted);line-height:32px;"></span>
		</div>
	`);

	// FY quick-select auto-fills dates
	$("#sho-fy", wrapper).on("change", function () {
		const val = $(this).val();
		if (!val) return;
		const [from, to] = val.split("|");
		$("#sho-from", wrapper).val(from);
		$("#sho-to",   wrapper).val(to);
	});

	// ── ZONE 1: Headline KPIs — full width ──────────────────────────────────
	$w.append('<div class="sho-section">Company snapshot</div>');
	$w.append('<div id="sho-kpi-snapshot" class="sho-kpi-grid"></div>');

	$w.append('<div class="sho-divider"></div>');

	// ── ZONE 2: Master data (left) + Statutory & Expiry (right) ─────────────
	const $zone2 = $('<div class="sho-zone-2col"></div>').appendTo($w);

	const $z2left  = $('<div class="sho-col"></div>').appendTo($zone2);
	const $z2right = $('<div class="sho-col"></div>').appendTo($zone2);

	$z2left.append('<div class="sho-section" style="margin-top:0;">Master data</div>');
	$z2left.append('<div id="sho-kpi-masters" class="sho-kpi-grid"></div>');

	$z2right.append('<div class="sho-section" style="margin-top:0;">Statutory completeness</div>');
	$z2right.append('<div id="sho-statutory" class="sho-stat-grid"></div>');
	$z2right.append('<div class="sho-section">Assignment expiry tracker <span style="font-size:10px;font-weight:400;text-transform:none;letter-spacing:0;">(next 30 days)</span></div>');
	$z2right.append('<div id="sho-expiry"></div>');

	$w.append('<div class="sho-divider"></div>');

	// ── ZONE 3: Full width tables ────────────────────────────────────────────
	$w.append('<div class="sho-section">Head count movement</div>');
	$w.append('<div id="sho-headcount"></div>');

	$w.append('<div class="sho-section" style="margin-top:24px;">Monthly attendance &amp; payroll tracker</div>');
	$w.append('<div id="sho-monthly"></div>');

	$w.append('<div class="sho-divider"></div>');

	// ── ZONE 4: Payroll readiness (left) + Classification (right) ───────────
	const $zone4 = $('<div class="sho-zone-2col-equal"></div>').appendTo($w);

	const $z4left  = $('<div class="sho-col"></div>').appendTo($zone4);
	const $z4right = $('<div class="sho-col"></div>').appendTo($zone4);

	$z4left.append('<div class="sho-section" style="margin-top:0;">Payroll readiness checklist</div>');
	$z4left.append('<div id="sho-readiness"></div>');

	$z4right.append('<div class="sho-section" style="margin-top:0;">Employee classification breakdown</div>');
	$z4right.append('<div id="sho-classification"></div>');

	// ── Load companies ────────────────────────────────────────────────────────
	frappe.call({
		method: "saral_hr.saral_hr.page.saral_hr_overview.saral_hr_overview.get_companies",
		callback(r) {
			const $sel = $("#sho-company", wrapper);
			$sel.empty();
			(r.message || []).forEach(c => $sel.append(`<option value="${c}">${c}</option>`));
			if (r.message && r.message.length) loadAll();
		}
	});

	$("#sho-apply", wrapper).on("click", loadAll);

	// ── Main load ─────────────────────────────────────────────────────────────
	function loadAll() {
		const company   = $("#sho-company", wrapper).val();
		const from_date = $("#sho-from",    wrapper).val();
		const to_date   = $("#sho-to",      wrapper).val();

		if (!company)               return frappe.msgprint("Please select a company.");
		if (!from_date || !to_date) return frappe.msgprint("Please select From and To dates.");
		if (from_date > to_date)    return frappe.msgprint("From date cannot be after To date.");

		const sections = ["sho-kpi-snapshot","sho-kpi-masters","sho-statutory",
		                  "sho-headcount","sho-monthly",
		                  "sho-readiness","sho-expiry","sho-classification"];
		sections.forEach(id => $(`#${id}`, wrapper).html('<div class="sho-spinner">Loading…</div>'));

		Promise.all([
			frappe.call({ method: "saral_hr.saral_hr.page.saral_hr_overview.saral_hr_overview.get_kpi_data",
				args: { company, from_date, to_date } }),
			frappe.call({ method: "saral_hr.saral_hr.page.saral_hr_overview.saral_hr_overview.get_monthly_data",
				args: { company, from_date, to_date } }),
			frappe.call({ method: "saral_hr.saral_hr.page.saral_hr_overview.saral_hr_overview.get_expiring_assignments",
				args: { company, from_date, to_date } }),
			frappe.call({ method: "saral_hr.saral_hr.page.saral_hr_overview.saral_hr_overview.get_classification_data",
				args: { company } })
		]).then(([kpiR, monthR, expiryR, clsR]) => {
			const company   = $("#sho-company", wrapper).val();
			const from_date = $("#sho-from",    wrapper).val();
			const to_date   = $("#sho-to",      wrapper).val();

			renderSnapshot(kpiR.message   || {}, company, from_date, to_date);
			renderMasters(kpiR.message    || {});
			renderStatutory(kpiR.message  || {});
			renderHeadcount(monthR.message || []);
			renderMonthly(monthR.message  || [], company);
			renderReadiness(monthR.message || []);
			renderExpiry(expiryR.message  || []);
			renderClassification(clsR.message || []);

			$("#sho-refreshed", wrapper).text("Updated " + frappe.datetime.now_datetime().slice(11, 16));
		}).catch(err => {
			console.error(err);
			frappe.msgprint("Error loading dashboard. Check console.");
		});
	}

	// ── KPI: Company snapshot ─────────────────────────────────────────────────
	function renderSnapshot(d, company, from_date, to_date) {
		const base = `/app/company-link?company=${encodeURIComponent(company)}`;
		const ssa  = `/app/salary-structure-assignment?company=${encodeURIComponent(company)}`;

		const cards = [
			{ label: "Total registered employees", value: d.total_registered,
			  sub: "includes inactive / resigned",
			  link: base },
			{ label: "Active employees", value: d.total_active,
			  sub: "currently in company",
			  link: `${base}&is_active=1` },
			{ label: "Salary structures", value: d.salary_structures,
			  sub: "defined for this company",
			  link: `/app/salary-structure?company=${encodeURIComponent(company)}` },
			{ label: "Salary structure assignments", value: d.ssa_count,
			  sub: "submitted, in selected period",
			  link: `${ssa}&docstatus=1` },
			{ label: "Holiday days in range", value: d.holiday_count,
			  sub: "from default holiday list" },
			{ label: "Employees on salary hold", value: d.on_hold_count,
			  sub: "status: On Hold", alert: d.on_hold_count > 0,
			  link: `/app/employee-salary-hold?company=${encodeURIComponent(company)}&status=On Hold` },
			{ label: "Active without assignment", value: d.without_assignment,
			  sub: "no salary structure in period", alert: d.without_assignment > 0 }
		];

		$("#sho-kpi-snapshot", wrapper).html(cards.map(c => kpiCard(c)).join(""));
	}

	// ── KPI: Master data ──────────────────────────────────────────────────────
	function renderMasters(d) {
		const cards = [
			{ label: "Departments",       value: d.dept_count,        sub: "global master", link: "/app/department" },
			{ label: "Designations",      value: d.designation_count, sub: "global master", link: "/app/designation" },
			{ label: "Categories",        value: d.category_count,    sub: "global master", link: "/app/category" },
			{ label: "Divisions",         value: d.division_count,    sub: "global master", link: "/app/division" },
			{ label: "Salary components", value: d.salary_components, sub: "earning + deduction types", link: "/app/salary-component" }
		];
		$("#sho-kpi-masters", wrapper).html(cards.map(c => kpiCard(c)).join(""));
	}

	// ── Statutory completeness ────────────────────────────────────────────────
	function renderStatutory(d) {
		const active = d.total_active || 0;
		function statCard(title, filled, total) {
			const pct   = total > 0 ? Math.round((filled / total) * 100) : 0;
			const color = pct >= 90 ? "var(--green,#28a745)" : pct >= 60 ? "#e67e22" : "var(--red)";
			return `<div class="sho-stat-card">
				<div class="sho-stat-title">${title}</div>
				<div class="sho-stat-bar-bg"><div class="sho-stat-bar-fill" style="width:${pct}%;background:${color};"></div></div>
				<div class="sho-stat-nums">${filled} of ${total} filled &nbsp;·&nbsp; ${pct}%</div>
			</div>`;
		}
		$("#sho-statutory", wrapper).html(
			statCard("ESIC number filled",   d.esic_filled, active) +
			statCard("PF UAN number filled", d.pf_filled,   active)
		);
	}

	// ── Head count movement ───────────────────────────────────────────────────
	function renderHeadcount(rows) {
		if (!rows.length) return $("#sho-headcount", wrapper).html('<div class="sho-spinner">No data.</div>');

		const tbody = rows.map(r => `
			<tr>
				<td class="l">${r.month}</td>
				<td>${r.opening}</td>
				<td>${r.joined > 0 ? `<span class="sho-badge badge-green">+${r.joined}</span>` : "—"}</td>
				<td>${r.left   > 0 ? `<span class="sho-badge badge-red">-${r.left}</span>`   : "—"}</td>
				<td><strong>${r.closing}</strong></td>
			</tr>`).join("");

		// Totals
		const totJoined = rows.reduce((s, r) => s + r.joined, 0);
		const totLeft   = rows.reduce((s, r) => s + r.left,   0);

		$("#sho-headcount", wrapper).html(`
			<div class="sho-table-outer">
				<table class="sho-table" style="min-width:400px;">
					<thead><tr>
						<th class="l">Month</th>
						<th>Opening</th>
						<th>Joined</th>
						<th>Left</th>
						<th>Closing</th>
					</tr></thead>
					<tbody>${tbody}</tbody>
					<tfoot><tr>
						<td class="l">Total</td>
						<td>—</td>
						<td><strong>${totJoined}</strong></td>
						<td><strong>${totLeft}</strong></td>
						<td>—</td>
					</tr></tfoot>
				</table>
			</div>`);
	}

	// ── Monthly tracker ───────────────────────────────────────────────────────
	function renderMonthly(rows, company) {
		if (!rows.length) return $("#sho-monthly", wrapper).html('<div class="sho-spinner">No data.</div>');

		const tbody = rows.map(r => {
			const covColor = r.emps_with_att >= r.active_count ? "var(--green,#28a745)"
			               : r.emps_with_att >= r.active_count * 0.6 ? "#e67e22" : "var(--red)";

			// Clickable salary slip count
			const slipLink = `/app/salary-slip?company=${encodeURIComponent(company)}&start_date=${r.month_key}-01&docstatus=1`;

			return `<tr>
				<td class="l">${r.month}</td>
				<td>${r.active_count}</td>
				<td>${r.att_total}</td>
				<td style="color:${covColor};font-weight:500;">${r.emps_with_att} / ${r.active_count}</td>
				<td>${r.min_att}</td>
				<td>${r.max_att}</td>
				<td>${r.absent_total > 0 ? `<span class="sho-badge badge-red">${r.absent_total}</span>` : r.absent_total}</td>
				<td>${r.lwp_total > 0    ? `<span class="sho-badge badge-blue">${r.lwp_total}</span>`   : r.lwp_total}</td>
				<td><a href="${slipLink}" target="_blank">${r.slip_count}</a></td>
				<td>${r.hold_count > 0   ? `<span class="sho-badge badge-red">${r.hold_count}</span>`   : "—"}</td>
			</tr>`;
		}).join("");

		// Summary row
		const totAtt    = rows.reduce((s, r) => s + r.att_total,    0);
		const totAbsent = rows.reduce((s, r) => s + r.absent_total, 0);
		const totLwp    = rows.reduce((s, r) => s + r.lwp_total,    0);
		const totSlips  = rows.reduce((s, r) => s + r.slip_count,   0);
		const avgActive = Math.round(rows.reduce((s, r) => s + r.active_count,   0) / rows.length);
		const avgAttEmp = Math.round(rows.reduce((s, r) => s + r.emps_with_att,  0) / rows.length);

		$("#sho-monthly", wrapper).html(`
			<div class="sho-table-outer">
				<table class="sho-table">
					<thead><tr>
						<th class="l">Month</th>
						<th>Active</th>
						<th>Att. entries</th>
						<th>Att. entered<br>(emp count)</th>
						<th>Min att.</th>
						<th>Max att.</th>
						<th>Absent</th>
						<th>LWP</th>
						<th>Salary slips</th>
						<th>On hold</th>
					</tr></thead>
					<tbody>${tbody}</tbody>
					<tfoot><tr>
						<td class="l">Total / avg</td>
						<td>${avgActive} avg</td>
						<td>${totAtt}</td>
						<td>${avgAttEmp} avg</td>
						<td>—</td><td>—</td>
						<td>${totAbsent}</td>
						<td>${totLwp}</td>
						<td>${totSlips}</td>
						<td>—</td>
					</tr></tfoot>
				</table>
			</div>`);
	}

	// ── Payroll readiness checklist ───────────────────────────────────────────
	function renderReadiness(rows) {
		if (!rows.length) return $("#sho-readiness", wrapper).html('<div class="sho-spinner">No data.</div>');

		const checks = [
			{ key: "ready_att",      label: "Attendance entered" },
			{ key: "ready_ssa",      label: "Salary structure" },
			{ key: "ready_no_holds", label: "No salary holds" },
			{ key: "ready_slips",    label: "Slips generated" },
		];

		// Column headers = months
		const thMonths = rows.map(r =>
			`<th style="min-width:64px;">${r.month.replace(" ", "<br>")}</th>`
		).join("");

		// One row per check
		const tbodyRows = checks.map(c => {
			const cells = rows.map(r => {
				const ok    = r[c.key];
				const color = ok ? "var(--green,#28a745)" : "var(--red,#e63946)";
				const icon  = ok ? "✓" : "✗";
				return `<td style="color:${color};font-weight:600;font-size:13px;">${icon}</td>`;
			}).join("");
			return `<tr>
				<td class="l" style="white-space:nowrap;">${c.label}</td>
				${cells}
			</tr>`;
		}).join("");

		$("#sho-readiness", wrapper).html(`
			<div class="sho-table-outer">
				<table class="sho-cls-table" style="min-width:unset;">
					<thead>
						<tr>
							<th class="l">Check</th>
							${thMonths}
						</tr>
					</thead>
					<tbody>${tbodyRows}</tbody>
				</table>
			</div>`);
	}

	// ── Assignment expiry tracker ─────────────────────────────────────────────
	function renderExpiry(rows) {
		if (!rows.length) {
			return $("#sho-expiry", wrapper).html(
				'<div style="font-size:13px;color:var(--text-muted);padding:8px 0;">No assignments expiring in selected period.</div>'
			);
		}

		const tbody = rows.map(r => `
			<tr>
				<td class="l">${r.employee_name || r.employee}</td>
				<td class="l">${r.salary_structure}</td>
				<td>${frappe.datetime.str_to_user(r.from_date)}</td>
				<td>${frappe.datetime.str_to_user(r.to_date)}</td>
				<td>
					<a href="/app/salary-structure-assignment/new-salary-structure-assignment-1" target="_blank"
						class="sho-badge badge-orange">Renew</a>
				</td>
			</tr>`).join("");

		$("#sho-expiry", wrapper).html(`
			<div class="sho-table-outer">
				<table class="sho-table" style="min-width:500px;">
					<thead><tr>
						<th class="l">Employee</th>
						<th class="l">Structure</th>
						<th>From</th>
						<th>Expires on</th>
						<th>Action</th>
					</tr></thead>
					<tbody>${tbody}</tbody>
				</table>
			</div>`);
	}

	// ── Classification breakdown ──────────────────────────────────────────────
	function renderClassification(rows) {
		if (!rows.length) return $("#sho-classification", wrapper).html('<div class="sho-spinner">No data.</div>');

		const SKILL_ORDER = ["Skilled", "Semi-skilled", "Unskilled"];

		// Column headers
		const thSkills = SKILL_ORDER.map(s => `<th>${s}</th>`).join("");

		// One row per category — skill cells show value or — depending on has_subtype
		const tbody = rows.map(r => {
			const skillCells = SKILL_ORDER.map(s =>
				r.has_subtype ? `<td>${r.counts[s] || 0}</td>` : `<td style="color:var(--text-muted);">—</td>`
			).join("");
			return `<tr>
				<td class="l">${r.category}</td>
				${skillCells}
				<td><strong>${r.total}</strong></td>
			</tr>`;
		}).join("");

		// Footer totals — only sum rows that have_subtype for skill cols
		const grandTotal  = rows.reduce((s, r) => s + r.total, 0);
		const tfootSkills = SKILL_ORDER.map(s => {
			const sum = rows.filter(r => r.has_subtype).reduce((t, r) => t + (r.counts[s] || 0), 0);
			return `<td><strong>${sum}</strong></td>`;
		}).join("");

		$("#sho-classification", wrapper).html(`
			<div class="sho-cls-outer">
				<table class="sho-cls-table">
					<thead>
						<tr>
							<th class="l">Category</th>
							${thSkills}
							<th>Total</th>
						</tr>
					</thead>
					<tbody>${tbody}</tbody>
					<tfoot>
						<tr>
							<td class="l">Total</td>
							${tfootSkills}
							<td><strong>${grandTotal}</strong></td>
						</tr>
					</tfoot>
				</table>
			</div>`);
	}

	// ── KPI card helper ───────────────────────────────────────────────────────
	function kpiCard({ label, value, sub, alert, link }) {
		const cls   = `sho-kpi${alert ? " alert-card" : ""}${!link ? " no-link" : ""}`;
		const click = link ? `onclick="window.open('${link}','_blank')"` : "";
		return `
			<div class="${cls}" ${click}>
				<div class="sho-kpi-label">${label}</div>
				<div class="sho-kpi-bottom">
					<div class="sho-kpi-val">${value ?? "—"}</div>
					<div class="sho-kpi-sub">${sub}</div>
				</div>
			</div>`;
	}
};