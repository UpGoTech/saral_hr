frappe.pages["salary-statistics"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Salary Statistics",
		single_column: true,
	});

	const MONTHS = ["January","February","March","April","May","June","July","August","September","October","November","December"];
	const TODAY         = new Date();
	const CUR_MONTH_IDX = TODAY.getMonth();
	const CUR_YEAR      = TODAY.getFullYear();

	let state = {
		company:   null,
		year:      String(CUR_YEAR),
		month:     MONTHS[CUR_MONTH_IDX],
		employees: [],
	};

	// ─────────────────────────────────────────────────────────────────────────
	// STYLES
	// ─────────────────────────────────────────────────────────────────────────
	if (!document.getElementById("ss-styles")) {
		$(`<style id="ss-styles">
		.ss-wrap * { box-sizing: border-box; }

		/* ── Search Page ── */
		.ss-search-page { padding: 16px 20px; max-width: 1000px; margin: 0 auto; }
		.ss-filter-card {
			background: var(--card-bg); border: 1px solid var(--border-color);
			border-radius: 8px; padding: 14px 16px; margin-bottom: 16px;
			box-shadow: 0 1px 3px rgba(0,0,0,.04);
		}
		.ss-filter-row { display: flex; gap: 12px; align-items: flex-end; flex-wrap: wrap; }
		.ss-filter-item { display: flex; flex-direction: column; gap: 5px; }
		.ss-filter-label { font-size: 11px; font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: .4px; }
		.ss-select {
			height: 34px; min-width: 140px; font-size: 13px;
			border: 1px solid var(--border-color); border-radius: 6px;
			background: var(--bg-color); color: var(--text-color);
			padding: 0 10px; outline: none; transition: border-color .15s;
		}
		.ss-select:focus { border-color: var(--primary); }
		.ss-btn-search {
			height: 34px; padding: 0 24px; font-size: 13px; font-weight: 600;
			border: none; border-radius: 6px; background: var(--primary);
			color: #fff; cursor: pointer; transition: opacity .15s;
			white-space: nowrap; align-self: flex-end;
		}
		.ss-btn-search:hover { opacity: .88; }

		/* ── Employee Table ── */
		.ss-results-card {
			background: var(--card-bg); border: 1px solid var(--border-color);
			border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,.04);
		}
		.ss-results-header {
			display: flex; align-items: center; justify-content: space-between;
			padding: 14px 18px; border-bottom: 1px solid var(--border-color);
		}
		.ss-results-title { font-size: 13px; font-weight: 700; color: var(--text-color); }
		.ss-results-count {
			font-size: 12px; color: var(--text-muted); background: var(--subtle-fg);
			padding: 2px 10px; border-radius: 10px; font-weight: 600;
		}
		.ss-search-bar-wrap { padding: 12px 18px; border-bottom: 1px solid var(--border-color); }
		.ss-search-input-inner { position: relative; }
		.ss-search-input-inner svg {
			position: absolute; left: 10px; top: 50%; transform: translateY(-50%);
			color: var(--text-muted); pointer-events: none;
		}
		.ss-search-input {
			width: 100%; height: 34px; border: 1px solid var(--border-color);
			border-radius: 6px; padding: 0 12px 0 34px; font-size: 13px;
			background: var(--bg-color); color: var(--text-color); outline: none;
		}
		.ss-search-input:focus { border-color: var(--primary); }
		.ss-emp-table { width: 100%; border-collapse: collapse; }
		.ss-emp-table thead th {
			padding: 9px 18px; text-align: left; font-size: 11px; font-weight: 700;
			color: var(--text-muted); text-transform: uppercase; letter-spacing: .4px;
			background: var(--subtle-fg); border-bottom: 1px solid var(--border-color);
		}
		.ss-emp-table tbody tr { border-bottom: 1px solid var(--border-color); cursor: pointer; transition: background .1s; }
		.ss-emp-table tbody tr:last-child { border-bottom: none; }
		.ss-emp-table tbody tr:hover { background: var(--highlight-color); }
		.ss-emp-table tbody td { padding: 12px 18px; font-size: 13px; color: var(--text-color); }
		.ss-emp-name-cell { display: flex; align-items: center; gap: 10px; }
		.ss-emp-avatar-sm {
			width: 34px; height: 34px; border-radius: 50%;
			display: flex; align-items: center; justify-content: center;
			font-size: 12px; font-weight: 700; color: #fff;
			background: var(--primary); flex-shrink: 0;
		}
		.ss-emp-name { font-weight: 600; font-size: 13px; }
		.ss-dept-badge {
			display: inline-block; font-size: 11px; background: var(--subtle-fg);
			color: var(--text-muted); border-radius: 4px; padding: 1px 7px;
		}
		.ss-empty { text-align: center; padding: 48px 24px; color: var(--text-muted); font-size: 14px; }
		.ss-empty-icon { font-size: 36px; margin-bottom: 10px; }

		/* ── Profile link button ── */
		.ss-profile-link-btn {
			display: flex; align-items: center; justify-content: center; gap: 6px;
			margin: 10px 16px 4px; padding: 7px 12px;
			border-radius: 7px; border: 1px solid var(--border-color);
			background: var(--subtle-fg); color: var(--text-color);
			font-size: 12px; font-weight: 600; text-decoration: none;
			transition: all 0.15s; cursor: pointer;
		}
		.ss-profile-link-btn:hover {
			background: var(--highlight-color); border-color: var(--primary);
			color: var(--primary); text-decoration: none;
		}

		/* ── Row profile icon link ── */
		.ss-row-profile-link {
			display: inline-flex; align-items: center; gap: 3px;
			font-size: 11px; font-weight: 600; color: var(--text-muted);
			border: 1px solid var(--border-color); border-radius: 5px;
			padding: 2px 8px; text-decoration: none; white-space: nowrap;
			transition: all 0.12s;
		}
		.ss-row-profile-link:hover {
			color: var(--primary); border-color: var(--primary);
			background: var(--subtle-fg); text-decoration: none;
		}

		/* ── Skeleton ── */
		.ss-skeleton {
			background: linear-gradient(90deg, var(--subtle-fg) 25%, var(--border-color) 50%, var(--subtle-fg) 75%);
			background-size: 200% 100%; animation: ss-shimmer 1.4s infinite; border-radius: 4px;
		}
		@keyframes ss-shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }

		/* ── Detail Page Layout ── */
		.ss-detail-page { display: flex; height: calc(100vh - 60px); overflow: hidden; }

		/* Left panel */
		.ss-detail-left {
			width: 270px; min-width: 220px; border-right: 1px solid var(--border-color);
			overflow-y: auto; background: var(--fg-color);
			display: flex; flex-direction: column; flex-shrink: 0;
		}

		/* Nav bar — replaces breadcrumb */
		.ss-nav-bar {
			display: flex; align-items: center; gap: 8px;
			padding: 10px 14px; border-bottom: 1px solid var(--border-color);
			background: var(--subtle-fg);
		}
		.ss-nav-back {
			display: flex; align-items: center; gap: 4px;
			font-size: 11px; font-weight: 700; color: var(--primary);
			cursor: pointer; white-space: nowrap;
		}
		.ss-nav-back:hover { text-decoration: underline; }
		.ss-nav-sep { font-size: 11px; color: var(--border-color); }
		.ss-nav-current {
			font-size: 11px; color: var(--text-muted);
			white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0;
		}

		/* Employee name below nav */
		.ss-emp-heading {
			padding: 12px 14px 0;
			font-size: 16px; font-weight: 700; color: var(--text-color);
			white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
		}

		/* Profile box */
		.ss-profile-box {
			padding: 12px 16px 16px; border-bottom: 1px solid var(--border-color); text-align: center;
		}
		.ss-profile-img {
			width: 90px; height: 90px; border-radius: 50%; object-fit: cover;
			border: 3px solid var(--border-color); margin: 0 auto 10px; display: block;
			box-shadow: 0 2px 8px rgba(0,0,0,.12);
		}
		.ss-profile-avatar {
			width: 90px; height: 90px; border-radius: 50%;
			background: linear-gradient(135deg, var(--primary) 0%, #7c3aed 100%);
			display: flex; align-items: center; justify-content: center;
			font-size: 32px; font-weight: 700; color: #fff;
			margin: 0 auto 10px; box-shadow: 0 2px 8px rgba(0,0,0,.15);
		}
		.ss-profile-meta-row {
			display: flex; align-items: center; justify-content: center;
			gap: 5px; font-size: 11px; color: var(--text-muted); margin-bottom: 3px;
		}

		/* Year switcher */
		.ss-year-switcher {
			display: flex; align-items: center; justify-content: space-between;
			padding: 8px 14px; border-bottom: 1px solid var(--border-color);
			background: var(--subtle-fg);
		}
		.ss-year-label { font-size: 11px; font-weight: 700; color: var(--text-muted); text-transform: uppercase; }
		.ss-year-controls { display: flex; align-items: center; gap: 6px; }
		.ss-year-btn {
			width: 22px; height: 22px; border-radius: 4px;
			border: 1px solid var(--border-color); background: var(--card-bg);
			cursor: pointer; font-size: 12px; color: var(--text-color);
			display: flex; align-items: center; justify-content: center; transition: background .12s;
		}
		.ss-year-btn:hover { background: var(--highlight-color); }
		.ss-year-val { font-size: 13px; font-weight: 700; color: var(--text-color); min-width: 36px; text-align: center; }

		/* Month list */
		.ss-month-list { flex: 1; overflow-y: auto; }
		.ss-month-row {
			display: flex; align-items: center; justify-content: space-between;
			padding: 9px 14px; cursor: pointer;
			border-bottom: 1px solid var(--border-color);
			transition: background .1s; border-radius: 0;
		}
		.ss-month-row:hover { background: var(--highlight-color); }
		.ss-month-row.ss-active {
			background: var(--primary-light);
			border-left: 3px solid var(--primary);
		}
		.ss-month-row.ss-active .ss-month-name-txt { color: var(--primary) !important; font-weight: 700; }
		.ss-month-row.ss-active .ss-net-amount { color: #16a34a !important; }
		.ss-month-row.ss-active .ss-net-none { color: var(--text-muted) !important; }
		.ss-month-row.ss-active .ss-month-dot { background: var(--primary) !important; }
		.ss-month-row.ss-future { opacity: .4; cursor: default; pointer-events: none; }
		.ss-month-left { display: flex; align-items: center; gap: 8px; }
		.ss-month-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--border-color); flex-shrink: 0; }
		.ss-month-dot.processed { background: #22c55e; }
		.ss-month-name-txt { font-size: 13px; color: var(--text-color); }
		.ss-month-row.ss-active .ss-month-name-txt { font-weight: 700; }
		.ss-cur-month-badge {
			font-size: 9px; font-weight: 700;
			background: var(--primary); color: #fff;
			border-radius: 3px; padding: 1px 5px; text-transform: uppercase;
			margin-left: 4px;
		}
		.ss-net-amount { font-size: 12px; font-weight: 700; color: #22c55e; }
		.ss-net-none { font-size: 11px; color: var(--text-muted); font-style: italic; }

		/* Right panel */
		.ss-detail-right { flex: 1; overflow-y: auto; padding: 0; background: var(--bg-color); }
		.ss-right-inner { padding: 24px 28px 40px; max-width: 900px; }

		.ss-month-heading {
			display: flex; align-items: center; justify-content: space-between; gap: 12px;
			margin-bottom: 20px; padding-bottom: 14px;
			border-bottom: 1px solid var(--border-color);
			flex-wrap: wrap;
		}
		.ss-month-heading-left { display: flex; align-items: center; gap: 12px; }
		.ss-month-heading-title { font-size: 20px; font-weight: 700; color: var(--text-color); }
		.ss-slip-link {
			font-size: 11px; color: var(--primary); cursor: pointer;
			border: 1px solid var(--primary); border-radius: 4px;
			padding: 2px 8px; font-weight: 600; text-decoration: none;
		}
		.ss-slip-link:hover { background: var(--primary-light); }

		/* Header employee switcher (search bar beside month heading) */
		.ss-hdr-switch-wrap { display: flex; align-items: center; gap: 10px; }
		.ss-hdr-search-group { position: relative; width: 240px; flex-shrink: 0; }
		.ss-hdr-switch-input-inner {
			position: relative; display: flex; align-items: center;
			width: 100%; height: 34px;
			background: linear-gradient(135deg, #eef2ff 0%, #f3f4f6 100%);
			border: 1px solid var(--border-color); border-radius: 999px;
			overflow: hidden; transition: box-shadow .15s, border-color .15s;
		}
		.ss-hdr-switch-input-inner:focus-within {
			border-color: #6366f1; box-shadow: 0 0 0 3px rgba(99,102,241,.15);
		}
		.ss-search-icon-badge {
			display: flex; align-items: center; justify-content: center;
			width: 24px; height: 24px; border-radius: 50%; flex-shrink: 0;
			margin-left: 5px;
			background: linear-gradient(135deg, #38bdf8 0%, #6366f1 100%);
			box-shadow: 0 1px 4px rgba(99,102,241,.4);
		}
		.ss-hdr-switch-input {
			flex: 1; min-width: 0; height: 100%; border: none;
			background: transparent; padding: 0 14px 0 8px; font-size: 12px;
			color: var(--text-color); outline: none;
		}
		.ss-hdr-switch-dropdown {
			position: absolute; top: calc(100% + 4px); left: 0; width: 260px;
			background: var(--card-bg); border: 1px solid var(--border-color);
			border-radius: 6px; box-shadow: 0 4px 14px rgba(0,0,0,.12);
			max-height: 260px; overflow-y: auto; z-index: 100; display: none;
		}
		.ss-hdr-switch-clear {
			display: flex; align-items: center; justify-content: center;
			width: 18px; height: 18px; border-radius: 50%; flex-shrink: 0;
			margin-right: 8px; background: #1f2937; color: #fff; border: none;
			cursor: pointer; font-size: 10px; line-height: 1; padding: 0;
		}
		.ss-hdr-switch-clear:hover { background: #111827; }
		.ss-hdr-switch-item {
			display: flex; align-items: center; gap: 10px; padding: 9px 12px;
			cursor: pointer; font-size: 12px; border-bottom: 1px solid var(--border-color);
		}
		.ss-hdr-switch-item-avatar {
			width: 30px; height: 30px; border-radius: 50%; flex-shrink: 0;
			display: flex; align-items: center; justify-content: center;
			font-size: 11px; font-weight: 700; color: #fff;
			background: linear-gradient(135deg, var(--primary) 0%, #7c3aed 100%);
		}
		.ss-hdr-switch-item-body { min-width: 0; }
		.ss-hdr-switch-item:last-child { border-bottom: none; }
		.ss-hdr-switch-item:hover { background: var(--highlight-color); }
		.ss-hdr-switch-item-name { font-weight: 600; color: var(--text-color); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
		.ss-hdr-switch-item-id { font-size: 10px; color: var(--text-muted); font-family: monospace; margin-top: 1px; }
		.ss-hdr-switch-empty { padding: 14px; text-align: center; font-size: 12px; color: var(--text-muted); }

		.ss-print-icon-btn {
			display: flex; align-items: center; gap: 6px; flex-shrink: 0;
			height: 30px; padding: 0 12px; border-radius: 999px;
			border: 1px solid var(--border-color); background: var(--card-bg);
			color: var(--text-color); cursor: pointer; white-space: nowrap;
			transition: background .12s, color .12s, border-color .12s;
		}
		.ss-print-btn-label { font-size: 11px; font-weight: 600; }
		.ss-print-icon-btn svg { flex-shrink: 0; }
		.ss-print-icon-btn:hover { background: var(--highlight-color); color: var(--primary); border-color: var(--primary); }
		.ss-print-icon-btn:disabled, .ss-print-icon-btn.ss-print-icon-disabled { opacity: .35; cursor: not-allowed; pointer-events: none; }

		/* Section heading */
		.ss-sec-heading {
			font-size: 11px; font-weight: 700; text-transform: uppercase;
			letter-spacing: .5px; color: var(--text-muted);
			margin: 24px 0 10px; display: flex; align-items: center; gap: 8px;
		}
		.ss-sec-heading::after { content: ""; flex: 1; height: 1px; background: var(--border-color); }

		/* Summary cards */
		.ss-summary-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 4px; }
		.ss-scard {
			background: var(--card-bg); border: 1px solid var(--border-color);
			border-radius: 8px; padding: 14px 14px 12px;
		}
		.ss-scard.ss-scard-hero {
			border-color: transparent;
			box-shadow: 0 2px 12px rgba(34,197,94,.18);
			background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
		}
		.ss-scard.ss-scard-hero .ss-scard-value { font-size: 20px; }
		.ss-scard-top { display: flex; align-items: center; gap: 6px; margin-bottom: 8px; }
		.ss-scard-icon { font-size: 14px; }
		.ss-scard-label { font-size: 10px; font-weight: 700; text-transform: uppercase; color: var(--text-muted); letter-spacing: .3px; }
		.ss-scard-value { font-size: 16px; font-weight: 700; }
		.ss-scard-zero { opacity: .45; }

		/* Accordion */
		.ss-accordion { border: 1px solid var(--border-color); border-radius: 8px; margin-bottom: 8px; overflow: hidden; background: var(--card-bg); }
		.ss-acc-header {
			display: flex; align-items: center; justify-content: space-between;
			padding: 12px 16px; cursor: pointer; transition: background .1s; user-select: none;
		}
		.ss-acc-header:hover { background: var(--highlight-color); }
		.ss-acc-left { display: flex; align-items: center; gap: 10px; }
		.ss-acc-dot { width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }
		.ss-acc-title { font-size: 13px; font-weight: 600; color: var(--text-color); }
		.ss-acc-count { font-size: 11px; color: var(--text-muted); background: var(--subtle-fg); border-radius: 10px; padding: 1px 8px; font-weight: 600; }
		.ss-acc-total { font-size: 12px; font-weight: 700; color: var(--text-color); margin-left: auto; margin-right: 10px; }
		.ss-acc-arrow { font-size: 11px; color: var(--text-muted); transition: transform .2s; flex-shrink: 0; }
		.ss-acc-body { display: none; border-top: 1px solid var(--border-color); }
		.ss-acc-table { width: 100%; border-collapse: collapse; font-size: 12px; }
		.ss-acc-table thead th {
			padding: 7px 16px; background: var(--subtle-fg); font-size: 11px; font-weight: 700;
			color: var(--text-muted); text-transform: uppercase; text-align: left;
			border-bottom: 1px solid var(--border-color);
		}
		.ss-acc-table thead th:last-child { text-align: right; }
		.ss-acc-table tbody tr { border-bottom: 1px solid var(--border-color); }
		.ss-acc-table tbody tr:last-child { border-bottom: none; }
		.ss-acc-table tbody tr:nth-child(even) { background: var(--subtle-fg); }
		.ss-acc-table tbody td { padding: 8px 16px; }
		.ss-acc-table tbody td:last-child { text-align: right; font-weight: 600; }
		.ss-acc-table tfoot td { padding: 8px 16px; font-weight: 700; font-size: 12px; border-top: 2px solid var(--border-color); background: var(--subtle-fg); }
		.ss-acc-table tfoot td:last-child { text-align: right; }

		/* Attendance chips */
		.ss-att-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(90px, 1fr)); gap: 8px; }
		.ss-att-chip { background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 8px; padding: 10px 8px; text-align: center; }
		.ss-att-chip.ss-chip-muted { opacity: .4; }
		.ss-att-chip.ss-chip-green  { border-color: #bbf7d0; background: #f0fdf4; }
		.ss-att-chip.ss-chip-red    { border-color: #fecaca; background: #fef2f2; }
		.ss-att-chip.ss-chip-yellow { border-color: #fef08a; background: #fefce8; }
		.ss-att-chip.ss-chip-blue   { border-color: #bfdbfe; background: #eff6ff; }
		.ss-att-chip.ss-chip-purple { border-color: #e9d5ff; background: #faf5ff; }
		.ss-att-chip-val { font-size: 20px; font-weight: 700; line-height: 1; }
		.ss-att-chip.ss-chip-green  .ss-att-chip-val { color: #16a34a; }
		.ss-att-chip.ss-chip-red    .ss-att-chip-val { color: #dc2626; }
		.ss-att-chip.ss-chip-yellow .ss-att-chip-val { color: #ca8a04; }
		.ss-att-chip.ss-chip-blue   .ss-att-chip-val { color: #2563eb; }
		.ss-att-chip.ss-chip-purple .ss-att-chip-val { color: #7c3aed; }
		.ss-att-chip-label { font-size: 10px; color: var(--text-muted); margin-top: 4px; font-weight: 600; line-height: 1.2; }

		/* Heatmap */
		.ss-heatmap-wrap { overflow-x: auto; }
		.ss-heatmap-grid { display: grid; grid-template-columns: repeat(7, 38px); gap: 5px; min-width: max-content; }
		.ss-hm-day-lbl { width: 38px; text-align: center; font-size: 10px; font-weight: 700; color: var(--text-muted); padding: 2px 0; }
		.ss-hm-empty { width: 38px; height: 38px; }
		.ss-hm-cell {
			width: 38px; height: 38px; border-radius: 6px;
			display: flex; align-items: center; justify-content: center;
			font-size: 11px; font-weight: 700; color: #fff;
			cursor: default; position: relative; transition: transform .1s;
		}
		.ss-hm-cell:hover { transform: scale(1.12); z-index: 1; }
		.ss-hm-cell.ss-hm-today { box-shadow: 0 0 0 2px #fff, 0 0 0 4px var(--primary); }
		.ss-legend { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 12px; }
		.ss-legend-item { display: flex; align-items: center; gap: 5px; font-size: 11px; color: var(--text-muted); }
		.ss-legend-dot { width: 11px; height: 11px; border-radius: 3px; flex-shrink: 0; }

		.ss-no-slip {
			padding: 32px 24px; text-align: center; color: var(--text-muted); font-size: 14px;
			background: var(--card-bg); border: 1px dashed var(--border-color); border-radius: 10px;
			margin-bottom: 20px;
		}
		.ss-no-slip-icon { font-size: 36px; margin-bottom: 10px; }
		.ss-no-att {
			padding: 24px; text-align: center; color: var(--text-muted); font-size: 13px;
			background: var(--card-bg); border: 1px dashed var(--border-color); border-radius: 8px;
		}

		/* Earnings & Deductions grid */
		.ss-ed-grid {
			display: grid;
			gap: 8px;
		}
		.ss-ed-grid-3 { grid-template-columns: repeat(3, 1fr); }
		.ss-ed-grid-2 { grid-template-columns: repeat(2, 1fr); }
		.ss-ed-grid-1 { grid-template-columns: 1fr; }
		.ss-ed-col {
			border: 1px solid var(--border-color);
			border-radius: 8px;
			overflow: hidden;
			background: var(--card-bg);
			min-width: 0;
		}
		.ss-ed-col-header {
			display: flex; flex-direction: column; gap: 6px;
			padding: 10px 12px; cursor: pointer; transition: background .1s;
			user-select: none;
		}
		.ss-ed-col-header:hover { background: var(--highlight-color); }
		.ss-ed-col-header-top {
			display: flex; align-items: center; gap: 6px;
		}
		.ss-ed-col-header-bot {
			display: flex; align-items: center; justify-content: space-between;
		}
		.ss-ed-col-body { border-top: 1px solid var(--border-color); }

		/* Custom Tooltip */
		.ss-tooltip {
			position: fixed;
			background: rgba(15,15,15,.92);
			color: #fff;
			font-size: 11px;
			font-weight: 500;
			padding: 5px 10px;
			border-radius: 5px;
			pointer-events: none;
			z-index: 9999;
			white-space: nowrap;
			display: none;
			box-shadow: 0 2px 8px rgba(0,0,0,.25);
		}
		</style>`).appendTo("head");
	}

	// ─────────────────────────────────────────────────────────────────────────
	// CONTAINER
	// ─────────────────────────────────────────────────────────────────────────
	const $wrap = $(`<div class="ss-wrap"></div>`).appendTo(page.main);

	// Global tooltip element
	if (!document.querySelector(".ss-tooltip")) {
		$(`<div class="ss-tooltip"></div>`).appendTo("body");
	}

	// ─────────────────────────────────────────────────────────────────────────
	// HELPER: read URL search params
	// ─────────────────────────────────────────────────────────────────────────
	function getUrlParam(key) {
		try {
			var params = new URLSearchParams(window.location.search);
			return params.get(key) || null;
		} catch(e) {
			return null;
		}
	}

	// ─────────────────────────────────────────────────────────────────────────
	// HELPER: build a proper, human-readable file name for the Salary Slip PDF
	// e.g. "Salary Slip - Naina Khode - April 2026"
	// ─────────────────────────────────────────────────────────────────────────
	function buildSalarySlipFileName(employeeName, month, year) {
		const safeName = (employeeName || "Employee").replace(/[\\/:*?"<>|]/g, "").trim();
		return `Salary Slip - ${safeName} - ${month} ${year}`;
	}

	// ─────────────────────────────────────────────────────────────────────────
	// HELPER: open the Salary Slip as a PDF (preview first — user decides to print)
	// Uses the print format already configured as default on the Salary Slip doctype.
	// ─────────────────────────────────────────────────────────────────────────
	let _cachedSalarySlipPrintFormat = null;

	function printSalarySlip(slipName, fileLabel) {
		if (_cachedSalarySlipPrintFormat) {
			openSalarySlipPdf(slipName, _cachedSalarySlipPrintFormat, fileLabel);
			return;
		}
		frappe.db.get_value("DocType", "Salary Slip", "default_print_format").then(r => {
			const fmt = (r && r.message && r.message.default_print_format) || "Standard";
			_cachedSalarySlipPrintFormat = fmt;
			openSalarySlipPdf(slipName, fmt, fileLabel);
		});
	}

	function openSalarySlipPdf(slipName, printFormat, fileLabel) {
		frappe.show_alert({ message: __("Preparing PDF…"), indicator: "blue" });

		const url = frappe.urllib.get_full_url(
			"/api/method/frappe.utils.print_format.download_pdf" +
			"?doctype=" + encodeURIComponent("Salary Slip") +
			"&name=" + encodeURIComponent(slipName) +
			"&format=" + encodeURIComponent(printFormat) +
			"&no_letterhead=0"
		);

		fetch(url, { credentials: "same-origin" })
			.then(resp => {
				if (!resp.ok) throw new Error("PDF generation failed");
				return resp.blob();
			})
			.then(blob => {
				// Name the file properly so the browser's PDF viewer / Save dialog shows it clearly
				const namedFile = new File([blob], (fileLabel || "Salary Slip") + ".pdf", { type: "application/pdf" });
				const blobUrl   = URL.createObjectURL(namedFile);
				// Opens the PDF directly in a new tab using the browser's native PDF viewer —
				// the person sees the document first and decides themselves whether to print it.
				window.open(blobUrl, "_blank");
			})
			.catch(() => {
				frappe.msgprint(__("Could not generate the salary slip PDF. Please try again."));
			});
	}

	// ─────────────────────────────────────────────────────────────────────────
	// PAGE 1 — SEARCH
	// ─────────────────────────────────────────────────────────────────────────
// ─────────────────────────────────────────────────────────────────────────
	// PAGE 1 — SEARCH
	// ─────────────────────────────────────────────────────────────────────────
	function renderSearchPage() {
		$wrap.empty();
		page.set_title("Salary Statistics");

		const $pg      = $(`<div class="ss-search-page"></div>`).appendTo($wrap);
		const $fc      = $(`<div class="ss-filter-card"></div>`).appendTo($pg);
		const $fr      = $(`<div class="ss-filter-row"></div>`).appendTo($fc);
		const $results = $(`<div class="ss-results"></div>`).appendTo($pg);

		// Year
		const $yw = $(`<div class="ss-filter-item"><span class="ss-filter-label">Year</span></div>`).appendTo($fr);
		const $yr = $(`<select class="ss-select"></select>`).appendTo($yw);
		saral_hr.period_picker.get_period_year_options(false).forEach((y) => {
			$yr.append(`<option value="${y}" ${String(y) === state.year ? "selected" : ""}>${y}</option>`);
		});
		$yr.on("change", () => { state.year = $yr.val(); });

		// Month
		const $mw = $(`<div class="ss-filter-item"><span class="ss-filter-label">Month</span></div>`).appendTo($fr);
		const $mn = $(`<select class="ss-select"></select>`).appendTo($mw);
		MONTHS.forEach(m => $mn.append(`<option ${m === state.month ? "selected":""}>${m}</option>`));
		$mn.on("change", () => { state.month = $mn.val(); });

		// Search button (only shown for multi-company users)
		const $searchBtn = $(`<button class="ss-btn-search" style="display:none">Search</button>`).appendTo($fr);

		$searchBtn.on("click", () => {
			if (!state.company) { frappe.show_alert({ message:"Please select a company.", indicator:"orange" }); return; }
			state.year  = $yr.val();
			state.month = $mn.val();
			fetchEmployees($results);
		});

		// ── Load permitted companies ──────────────────────────────────────────
		frappe.call({
			method: "saral_hr.saral_hr.page.salary_statistics.salary_statistics.get_permitted_companies",
			callback(r) {
				const companies = r.message || [];

				if (companies.length === 1) {
					// Single company user — no dropdown, auto-load
					state.company = companies[0];

					// Show company name as a plain label (not a dropdown)
					$fr.prepend(`
						<div class="ss-filter-item">
							<span class="ss-filter-label">Company</span>
							<div style="height:34px;display:flex;align-items:center;
								font-size:13px;font-weight:600;color:var(--text-color);
								padding:0 10px;background:var(--subtle-fg);
								border:1px solid var(--border-color);border-radius:6px;
								min-width:200px;">
								${frappe.utils.escape_html(companies[0])}
							</div>
						</div>`);

					// Auto-fetch on load
					fetchEmployees($results);

					// Year/Month change → auto re-fetch (no search button needed)
					$yr.off("change").on("change", () => { state.year = $yr.val(); fetchEmployees($results); });
					$mn.off("change").on("change", () => { state.month = $mn.val(); fetchEmployees($results); });

				} else {
					// Multiple companies — show dropdown + Search button
					const $cw = $(`<div class="ss-filter-item" style="flex:1;min-width:200px;">
						<span class="ss-filter-label">Company</span>
						<select class="ss-select ss-company-sel">
							<option value="">— Select Company —</option>
						</select>
					</div>`);
					$fr.prepend($cw);
					const $csel = $cw.find(".ss-company-sel");

					companies.forEach(c => $csel.append(
						`<option value="${c}" ${c === state.company ? "selected":""}>${c}</option>`
					));
					$csel.on("change", () => { state.company = $csel.val(); });
					$searchBtn.show();

					if (state.employees.length) renderTable($results, state.employees);
				}
			}
		});

		// ── Deep-link from Employee Profile ──────────────────────────────────
		var deepEmpId   = getUrlParam("ep_employee");
		var deepCompany = getUrlParam("ep_company");
		var deepName    = getUrlParam("ep_name");

		if (deepEmpId && deepCompany) {
			state.company = deepCompany;
			frappe.call({
				method: "saral_hr.saral_hr.page.salary_statistics.salary_statistics.get_employees_for_company",
				args: { company: deepCompany, year: state.year, month: state.month },
				callback(r) {
					var employees = r.message || [];
					state.employees = employees;
					var matched = employees.find(e => e.employee === deepEmpId);
					if (matched) {
						renderDetailPage(matched);
					} else if (deepEmpId && deepName) {
						renderDetailPage({
							employee: deepEmpId, employee_name: deepName,
							department: "", designation: "", image: "",
							ctc_net_salary: null, monthly_net: {}
						});
					} else {
						renderTable($results, employees);
					}
				}
			});
		}
	}

	function fetchEmployees($results) {
		$results.html(`<div class="ss-results-card">${skeletonRows(6)}</div>`);
		frappe.call({
			method: "saral_hr.saral_hr.page.salary_statistics.salary_statistics.get_employees_for_company",
			args: { company: state.company, year: state.year, month: state.month },
			callback(r) { state.employees = r.message || []; renderTable($results, state.employees); },
			error()    { $results.html(`<div class="ss-empty"><div class="ss-empty-icon">⚠️</div>Failed to load employees.</div>`); }
		});
	}

	function skeletonRows(n) {
		let h = "";
		for (let i = 0; i < n; i++) {
			h += `<div style="display:flex;align-items:center;gap:12px;padding:14px 18px;border-bottom:1px solid var(--border-color);">
				<div class="ss-skeleton" style="width:34px;height:34px;border-radius:50%;flex-shrink:0;"></div>
				<div style="flex:1;"><div class="ss-skeleton" style="width:${120+(i*17)%80}px;height:13px;margin-bottom:5px;"></div>
				<div class="ss-skeleton" style="width:80px;height:10px;"></div></div>
				<div class="ss-skeleton" style="width:90px;height:12px;"></div>
				<div class="ss-skeleton" style="width:80px;height:12px;"></div>
			</div>`;
		}
		return h;
	}

	function renderTable($results, employees) {
		$results.empty();
		if (!employees.length) {
			$results.html(`<div class="ss-results-card"><div class="ss-empty"><div class="ss-empty-icon">👥</div>No active employees found.</div></div>`);
			return;
		}
		const $card = $(`<div class="ss-results-card"></div>`).appendTo($results);
		$(`<div class="ss-results-header">
			<span class="ss-results-title">Active Employees</span>
			<span class="ss-results-count ss-count-val">${employees.length} employees</span>
		</div>`).appendTo($card);
		$(`<div class="ss-search-bar-wrap"><div class="ss-search-input-inner">
			<svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
			<input type="text" class="ss-search-input" placeholder="Search by name or employee ID…">
		</div></div>`).appendTo($card);
		const $tw = $(`<div></div>`).appendTo($card);

		function buildTable(list) {
			$tw.empty();
			$card.find(".ss-count-val").text(`${list.length} employee${list.length!==1?"s":""}`);
			if (!list.length) { $tw.html(`<div class="ss-empty"><div class="ss-empty-icon">🔍</div>No results.</div>`); return; }
			const $tbl = $(`<table class="ss-emp-table"><thead><tr>
				<th style="width:34%">Employee</th><th>Employee ID</th>
				<th>Department</th><th>Date of Birth</th>
				<th style="text-align:right;">Net Salary (SSA)</th>
				<th style="text-align:center;">Profile</th>
			</tr></thead><tbody></tbody></table>`).appendTo($tw);
			const $tb = $tbl.find("tbody");
			list.forEach(emp => {
				const initials = (emp.employee_name||"?").split(" ").map(w=>w[0]).join("").toUpperCase().slice(0,2);
				const av = emp.image
					? `<img src="${emp.image}" style="width:34px;height:34px;border-radius:50%;object-fit:cover;border:2px solid var(--border-color);">`
					: `<div class="ss-emp-avatar-sm">${initials}</div>`;
				const netHtml = emp.ctc_net_salary != null
					? `<span style="font-weight:700;color:#16a34a;">₹${fmtNum(emp.ctc_net_salary)}</span>`
					: `<span style="color:var(--text-muted);font-style:italic;font-size:12px;">Not assigned</span>`;

				// ── Direction 3: "Profile ↗" link on each row ─────────────────────
				const profileUrl = "/app/employee-profile/" + encodeURIComponent(emp.employee);
				const profileLink = `<a href="${profileUrl}" target="_blank" class="ss-row-profile-link" onclick="event.stopPropagation();">
					👤 Profile ↗
				</a>`;

				const $tr = $(`<tr>
					<td><div class="ss-emp-name-cell">${av}<div>
						<div class="ss-emp-name">${emp.employee_name}</div>
						${emp.designation ? `<div style="font-size:11px;color:var(--text-muted);">${emp.designation}</div>` : ""}
					</div></div></td>
					<td style="color:var(--text-muted);font-family:monospace;font-size:12px;">${emp.employee}</td>
					<td>${emp.department ? `<span class="ss-dept-badge">${emp.department}</span>` : `<span style="color:var(--text-muted);">—</span>`}</td>
					<td style="color:var(--text-muted);font-size:12px;">${fmtDate(emp.date_of_birth)}</td>
					<td style="text-align:right;">${netHtml}</td>
					<td style="text-align:center;">${profileLink}</td>
				</tr>`);
				$tr.on("click", () => renderDetailPage(emp));
				$tb.append($tr);
			});
		}
		buildTable(employees);
		$card.find(".ss-search-input").on("input", function () {
			const q = $(this).val().toLowerCase().trim();
			buildTable(q ? employees.filter(e =>
				(e.employee_name||"").toLowerCase().includes(q) || (e.employee||"").toLowerCase().includes(q)
			) : employees);
		});
	}

	// ─────────────────────────────────────────────────────────────────────────
	// PAGE 2 — DETAIL
	// ─────────────────────────────────────────────────────────────────────────
	function renderDetailPage(emp) {
		$wrap.empty();
		page.set_title(emp.employee_name);

		const $dp   = $(`<div class="ss-detail-page"></div>`).appendTo($wrap);
		const $left = $(`<div class="ss-detail-left"></div>`).appendTo($dp);

		// ── Nav bar: context-aware back button ────────────────────────────────
		// If we arrived from Employee Profile (deep-link), go back there.
		// If we arrived from the Salary Statistics search list, go back there.
		var deepEmpId_nav  = getUrlParam("ep_employee");
		var fromProfile    = !!deepEmpId_nav;
		var profileBackUrl = fromProfile ? "/app/employee-profile/" + encodeURIComponent(deepEmpId_nav) : null;

		var navBackLabel = fromProfile ? "← Employee Profile" : "← Salary Statistics";
		var navChip      = fromProfile
			? ""  // no company chip needed — context is already clear
			: `<span class="ss-nav-sep">/</span><span class="ss-nav-current" title="${state.company}">${state.company}</span>`;

		const $nav = $(`<div class="ss-nav-bar">
			<span class="ss-nav-back">${navBackLabel}</span>
			${navChip}
		</div>`).appendTo($left);

		$nav.find(".ss-nav-back").on("click", function() {
			if (fromProfile && profileBackUrl) {
				window.location.href = profileBackUrl;
			} else {
				renderSearchPage();
			}
		});

		// ── Employee name heading ─────────────────────────────────────────────
		$left.append(`<div class="ss-emp-heading" title="${emp.employee_name}">${emp.employee_name}</div>`);

		// ── Profile ───────────────────────────────────────────────────────────
		const initials = (emp.employee_name||"?").split(" ").map(w=>w[0]).join("").toUpperCase().slice(0,2);
		$left.append(`<div class="ss-profile-box">
			${emp.image ? `<img src="${emp.image}" class="ss-profile-img">` : `<div class="ss-profile-avatar">${initials}</div>`}
			<div class="ss-profile-meta-row"><span>🪪</span><span>${emp.employee}</span></div>
			${emp.department  ? `<div class="ss-profile-meta-row"><span>🏢</span><span>${emp.department}</span></div>` : ""}
			${emp.designation ? `<div class="ss-profile-meta-row"><span>💼</span><span>${emp.designation}</span></div>` : ""}
		</div>`);

		// ── Direction 2: "View Employee Profile" button ───────────────────────
		var profileHref = "/app/employee-profile/" + encodeURIComponent(emp.employee);
		$left.append(`<a href="${profileHref}" target="_blank" class="ss-profile-link-btn">
			👤 View Employee Profile
		</a>`);

		// ── Year switcher ─────────────────────────────────────────────────────
		const $ys = $(`<div class="ss-year-switcher">
			<span class="ss-year-label">Year</span>
			<div class="ss-year-controls">
				<button class="ss-year-btn ss-yr-prev">‹</button>
				<span class="ss-year-val">${state.year}</span>
				<button class="ss-year-btn ss-yr-next">›</button>
			</div>
		</div>`).appendTo($left);

		const $monthList = $(`<div class="ss-month-list"></div>`).appendTo($left);
		const $right     = $(`<div class="ss-detail-right"><div class="ss-right-inner" style="color:var(--text-muted);padding-top:40px;text-align:center;">Select a month to view details.</div></div>`).appendTo($dp);

		let activeMonth     = state.month;
		let monthlyNetCache = {};

		function shiftYear(delta) {
			const ny = saral_hr.period_picker.clamp_period_year(parseInt(state.year, 10) + delta);
			state.year = String(ny);
			$ys.find(".ss-year-val").text(state.year);
			loadYearData(true);
		}
		$ys.find(".ss-yr-prev").on("click", () => shiftYear(-1));
		$ys.find(".ss-yr-next").on("click", () => shiftYear(+1));

		function loadYearData(resetMonth) {
			$monthList.html(`<div style="padding:16px;text-align:center;color:var(--text-muted);font-size:12px;"><div class="spinner-border spinner-border-sm"></div></div>`);
			frappe.call({
				method: "saral_hr.saral_hr.page.salary_statistics.salary_statistics.get_employees_for_company",
				args: { company: state.company, year: state.year, month: state.month },
				callback(r) {
					const found = (r.message||[]).find(e => e.employee === emp.employee);
					monthlyNetCache = found ? found.monthly_net : {};
					if (resetMonth) {
						activeMonth = (state.year === String(CUR_YEAR)) ? MONTHS[CUR_MONTH_IDX] : "January";
					}
					buildMonthList();
					loadMonthDetail(emp, activeMonth, $right);
				}
			});
		}

		function buildMonthList() {
			$monthList.empty();
			const selYear = parseInt(state.year);
			MONTHS.forEach((m, idx) => {
				const net      = monthlyNetCache[m];
				const isFuture = selYear > CUR_YEAR || (selYear === CUR_YEAR && idx > CUR_MONTH_IDX);
				const isCur    = selYear === CUR_YEAR && idx === CUR_MONTH_IDX;
				const isActive = m === activeMonth;

				const $row = $(`<div class="ss-month-row ${isActive?"ss-active":""} ${isFuture?"ss-future":""}">
					<div class="ss-month-left">
						<div class="ss-month-dot ${net!=null?"processed":""}"></div>
						<span class="ss-month-name-txt">${m}</span>
						${isCur ? `<span class="ss-cur-month-badge">Current</span>` : ""}
					</div>
					${net!=null
						? `<span class="ss-net-amount">₹${fmtNum(net)}</span>`
						: `<span class="ss-net-none">${isFuture ? "" : "Not processed"}</span>`}
				</div>`);

				if (!isFuture) {
					$row.on("click", function () {
						activeMonth = m;
						$monthList.find(".ss-month-row").removeClass("ss-active");
						$(this).addClass("ss-active");
						loadMonthDetail(emp, m, $right);
					});
				}
				$monthList.append($row);
			});
		}

		loadYearData(false);
	}

	// ─────────────────────────────────────────────────────────────────────────
	// LOAD MONTH DETAIL
	// ─────────────────────────────────────────────────────────────────────────
	function loadMonthDetail(emp, month, $right) {
		const employee = emp.employee;
		$right.html(`<div class="ss-right-inner">${skeletonDetail()}</div>`);
		let detailData = null, pending = 1;

		function tryRender() {
			if (--pending > 0) return;


			const $inner = $(`<div class="ss-right-inner"></div>`);

			// Heading
			const $heading = $(`<div class="ss-month-heading">
				<div class="ss-month-heading-left">
					<span class="ss-month-heading-title">${month} ${state.year}</span>
					${detailData && detailData.salary
						? `<a class="ss-slip-link" href="/app/salary-slip/${detailData.salary.slip_name}" target="_blank">${detailData.salary.slip_name} ↗</a>`
						: `<span style="font-size:12px;color:var(--text-muted);font-style:italic;">No salary slip</span>`}
				</div>
			</div>`).appendTo($inner);

			// ── Employee Switcher (colorful search bar, right side of heading) ──
			const $switchWrap = $(`<div class="ss-hdr-switch-wrap">
				<div class="ss-hdr-search-group">
					<div class="ss-hdr-switch-input-inner">
						<span class="ss-search-icon-badge">
							<svg width="12" height="12" fill="none" stroke="#fff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
						</span>
						<input type="text" class="ss-hdr-switch-input" placeholder="Search employee by name or ID…">
						<button type="button" class="ss-hdr-switch-clear" title="Clear" style="display:none;">✕</button>
					</div>
					<div class="ss-hdr-switch-dropdown"></div>
				</div>
				<button type="button" class="ss-print-icon-btn" title="View / Print Salary Slip">
					<span class="ss-print-btn-label">Salary Slip</span>
					<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 6 2 18 2 18 9"></polyline><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"></path><rect x="6" y="14" width="12" height="8"></rect></svg>
				</button>
			</div>`).appendTo($heading);

			const $si    = $switchWrap.find(".ss-hdr-switch-input");
			const $sd    = $switchWrap.find(".ss-hdr-switch-dropdown");
			const $clear = $switchWrap.find(".ss-hdr-switch-clear");
			const $printBtn = $switchWrap.find(".ss-print-icon-btn");

			// ── Print Salary Slip (uses the same print format configured on the Salary Slip doctype) ──
			if (detailData && detailData.salary && detailData.salary.slip_name) {
				$printBtn.on("click", function () {
					printSalarySlip(detailData.salary.slip_name, buildSalarySlipFileName(emp.employee_name, month, state.year));
				});
			} else {
				$printBtn.prop("disabled", true).addClass("ss-print-icon-disabled").attr("title", "No salary slip to print");
			}

			function getOtherEmployees() {
				return state.employees.filter(e => e.employee !== emp.employee);
			}

			function renderHdrSwitchResults(list) {
				$sd.empty();
				if (!list.length) {
					$sd.append(`<div class="ss-hdr-switch-empty">No matching employee found.</div>`);
				} else {
					list.forEach(e => {
						const initials = (e.employee_name||"?").split(" ").map(w=>w[0]).join("").toUpperCase().slice(0,2);
						const $item = $(`<div class="ss-hdr-switch-item">
							<div class="ss-hdr-switch-item-avatar">${initials}</div>
							<div class="ss-hdr-switch-item-body">
								<div class="ss-hdr-switch-item-name">${e.employee_name}</div>
								<div class="ss-hdr-switch-item-id">${e.employee}</div>
							</div>
						</div>`);
						$item.on("click", () => {
							$sd.hide();
							$si.val("");
							$clear.hide();
							renderDetailPage(e);
						});
						$sd.append($item);
					});
				}
				$sd.show();
			}

			$si.on("input", function () {
				const q = $(this).val().toLowerCase().trim();
				$clear.toggle(!!q);
				const pool = getOtherEmployees();
				const matches = q
					? pool.filter(e =>
						(e.employee_name||"").toLowerCase().includes(q) || (e.employee||"").toLowerCase().includes(q)
					  )
					: pool; // empty query → show full alphabetical employee list
				renderHdrSwitchResults(matches);
			});

			$si.on("focus", function () {
				const q = $(this).val().toLowerCase().trim();
				const pool = getOtherEmployees();
				const matches = q
					? pool.filter(e =>
						(e.employee_name||"").toLowerCase().includes(q) || (e.employee||"").toLowerCase().includes(q)
					  )
					: pool;
				renderHdrSwitchResults(matches);
			});

			$clear.on("click", function () {
				$si.val("").trigger("focus");
				$clear.hide();
			});

			$(document).off("click.ss-hdr-switch").on("click.ss-hdr-switch", function (e) {
				if (!$(e.target).closest(".ss-hdr-switch-wrap").length) $sd.hide();
			});

			// No slip notice
			if (!detailData || !detailData.salary) {
				$inner.append(`<div class="ss-no-slip">
					<div class="ss-no-slip-icon">📄</div>
					<div style="font-weight:600;margin-bottom:4px;">Salary Slip Not Generated</div>
					<div>No salary slip has been processed for <strong>${month} ${state.year}</strong>.</div>
				</div>`);
			} else {
	
				renderSalaryCards($inner, detailData.salary);
			}

			// Attendance summary chips (always shown if attendance exists)
			renderAttendanceSummary($inner, detailData, month);

			// Earnings & Deductions accordions (only if slip exists)
			if (detailData && detailData.salary) {
				renderEarningsAccordions($inner, detailData.salary);
			}

			// Attendance heatmap (always shown)
			renderAttendanceHeatmap($inner, detailData, month);

			$right.html("").append($inner);
		}

		frappe.call({
			method: "saral_hr.saral_hr.page.salary_statistics.salary_statistics.get_employee_month_details",
			args: { employee, year: state.year, month },
			callback(r) { detailData = r.message || null; tryRender(); },
			error()     { detailData = null; tryRender(); }
		});

	}

	// ─────────────────────────────────────────────────────────────────────────
	// 1. SALARY OVERVIEW CARDS
	// ─────────────────────────────────────────────────────────────────────────
	function renderSalaryCards($inner, s) {
		$inner.append(`<div class="ss-sec-heading">Salary Overview</div>`);
		const cards = [
			{ label:"Net Salary",            value: s.net_salary,                  color:"#16a34a", icon:"💰", hero:true },
			{ label:"Total Earnings",        value: s.total_earnings,              color:"#2563eb", icon:"📈" },
			{ label:"Total Deductions",      value: s.total_deductions,            color:"#dc2626", icon:"📉" },
			{ label:"Employer Contribution", value: s.total_employer_contribution, color:"#d97706", icon:"🏦" },
			{ label:"Additional Salary",     value: s.additional_salary_total,     color:"#0d9488", icon:"➕" },
			{ label:"Additional Deductions", value: s.additional_deduction_total,  color:"#b45309", icon:"➖" },
		];
		const $grid = $(`<div class="ss-summary-grid"></div>`).appendTo($inner);
		cards.forEach(c => {
			const isZero = !c.value || parseFloat(c.value) === 0;
			$grid.append(`<div class="ss-scard ${c.hero?"ss-scard-hero":""} ${isZero&&!c.hero?"ss-scard-zero":""}">
				<div class="ss-scard-top"><span class="ss-scard-icon">${c.icon}</span><span class="ss-scard-label">${c.label}</span></div>
				<div class="ss-scard-value" style="color:${c.color};">₹${fmtNum(c.value)}</div>
			</div>`);
		});
	}

	// ─────────────────────────────────────────────────────────────────────────
	// 2. ATTENDANCE SUMMARY CHIPS  (always live from attendance records)
	// ─────────────────────────────────────────────────────────────────────────
	function renderAttendanceSummary($inner, data, month) {
		const heatmap  = (data && data.heatmap) ? data.heatmap : [];
		const attCount = heatmap.filter(c => c.status !== "No Record").length;
		const la       = (data && data.live_attendance) ? data.live_attendance : null;

		$inner.append(`<div class="ss-sec-heading" style="margin-top:24px;">Attendance</div>`);

		if (attCount === 0 || !la) {
			$inner.append(`<div class="ss-no-att">
				<div style="font-size:26px;margin-bottom:8px;">📭</div>
				No attendance records found for <strong>${month} ${state.year}</strong>.
			</div>`);
			return;
		}

		// Show calc method as a small note
		if (la.calc_method) {
			$inner.append(`<div style="font-size:11px;color:var(--text-muted);margin-bottom:8px;">
				Calculation: <strong>${la.calc_method}</strong>
			</div>`);
		}

		// Chips — always from live attendance
		const attItems = [
			{ label:"Total Days",      value: la.total_days,       cls:"",              tooltip:"Calendar days in month" },
			{ label:"Working Days",    value: la.working_days,     cls:"",              tooltip:"Total days minus weekly offs" },
			{ label:"Payment Days",    value: la.payment_days,     cls:"",              tooltip:"Working days minus absences" },
			{ label:"Physical Present",value: la.physical_present, cls:"ss-chip-green", tooltip:"Days physically present (excl. EL, CL, Comp Off, Earned Comp Off)" },
			{ label:"Present (Total)", value: la.present,          cls:"ss-chip-green", tooltip:"Present + EL + CL + Comp Off + Earned Comp Off + On Tour" },
			{ label:"Absent",          value: la.absent,           cls:"ss-chip-red",   tooltip:"Absent + LWP days" },
			{ label:"Half Days",       value: la.half_days,        cls:"ss-chip-yellow",tooltip:"Half day attendances" },
			{ label:"Weekly Offs (Scheduled)", value: la.weekly_offs_scheduled, cls:"", tooltip:"Total weekly off days in this month based on the employee's weekly off day" },
			{ label:"Weekly Offs (Taken)",     value: la.weekly_offs_taken,     cls:"", tooltip:"Days marked as Weekly Off in attendance records" },
			{ label:"Holidays",        value: la.holidays,         cls:"ss-chip-blue",  tooltip:"Holiday marked attendances" },
			{ label:"LWP",             value: la.lwp,              cls:"ss-chip-red",   tooltip:"Leave Without Pay" },
			{ label:"Earned Leave",    value: la.earned_leave,     cls:"ss-chip-purple",tooltip:"Earned leave taken" },
			{ label:"Casual Leave",    value: la.casual_leave,     cls:"ss-chip-purple",tooltip:"Casual leave taken" },
			{ label:"On Tour",         value: la.on_tour,          cls:"ss-chip-blue",  tooltip:"On tour days" },
			{ label:"Comp Off",        value: la.comp_off,         cls:"ss-chip-yellow",tooltip:"Compensatory off days" },
			{ label:"Earned Comp Off", value: la.earned_comp_off || 0, cls:"ss-chip-yellow",tooltip:"Earned compensatory off days" },
		];

		const $attGrid = $(`<div class="ss-att-grid"></div>`).appendTo($inner);
		attItems.forEach(a => {
			const v = parseFloat(a.value) || 0;
			const $chip = $(`<div class="ss-att-chip ${a.cls} ${v===0?"ss-chip-muted":""}" title="${a.tooltip}">
				<div class="ss-att-chip-val">${v}</div>
				<div class="ss-att-chip-label">${a.label}</div>
			</div>`);
			$attGrid.append($chip);
		});
	}

	// ─────────────────────────────────────────────────────────────────────────
	// 3. EARNINGS & DEDUCTIONS — 3-column inline layout
	// ─────────────────────────────────────────────────────────────────────────
	function renderEarningsAccordions($inner, s) {
		$inner.append(`<div class="ss-sec-heading" style="margin-top:24px;">Earnings & Deductions</div>`);

		// First row: Earnings | Deductions | Employer Share (always the main 3)
		const mainCols = [
			{ title:"Earnings",       rows: s.earnings,       color:"#3b82f6" },
			{ title:"Deductions",     rows: s.deductions,     color:"#ef4444" },
			{ title:"Employer Share", rows: s.employer_share, color:"#f97316" },
		];

		// Second row (only if they have data): Additional Salary | Additional Deductions
		const extraCols = [
			{ title:"Additional Salary",     rows: s.additional_salary_components,    color:"#14b8a6" },
			{ title:"Additional Deductions", rows: s.additional_deduction_components, color:"#eab308" },
		].filter(a => (a.rows||[]).length > 0);

		function buildCol(a) {
			const rows  = a.rows || [];
			const total = rows.reduce((sum, r) => sum + (parseFloat(r.amount)||0), 0);
			const $col  = $(`<div class="ss-ed-col"></div>`);

			// Header
			const $hdr = $(`<div class="ss-ed-col-header">
				<div class="ss-ed-col-header-top">
					<span class="ss-acc-dot" style="background:${a.color};flex-shrink:0;"></span>
					<span class="ss-acc-title" style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${a.title}</span>
				</div>
				<div class="ss-ed-col-header-bot">
					<span class="ss-acc-count" style="flex-shrink:0;">${rows.length} item${rows.length!==1?"s":""}</span>
					<div style="display:flex;align-items:center;gap:6px;flex-shrink:0;">
						<span class="ss-acc-total">₹${fmtNum(total)}</span>
						<span class="ss-acc-arrow">▼</span>
					</div>
				</div>
			</div>`).appendTo($col);

			// Body (hidden by default)
			const $body = $(`<div class="ss-ed-col-body" style="display:none;">
				<table class="ss-acc-table">
					<thead><tr><th>Component</th><th>Amount</th></tr></thead>
					<tbody>${rows.map((r,i) => `<tr style="${i%2===1?"background:var(--subtle-fg)":""}">
						<td>${r.salary_component||r.component_type||""}</td>
						<td>₹${fmtNum(parseFloat(r.amount)||0)}</td>
					</tr>`).join("")}</tbody>
					<tfoot><tr><td>Total</td><td>₹${fmtNum(total)}</td></tr></tfoot>
				</table>
			</div>`).appendTo($col);

			$hdr.on("click", () => {
				const open = $body.is(":visible");
				$body.slideToggle(180);
				$hdr.find(".ss-acc-arrow").css("transform", open ? "" : "rotate(180deg)");
			});

			return $col;
		}

		// Main 3-column row
		const $mainRow = $(`<div class="ss-ed-grid ss-ed-grid-3"></div>`).appendTo($inner);
		mainCols.forEach(a => buildCol(a).appendTo($mainRow));

		// Extra row if needed
		if (extraCols.length) {
			const $extraRow = $(`<div class="ss-ed-grid ss-ed-grid-${extraCols.length}" style="margin-top:8px;"></div>`).appendTo($inner);
			extraCols.forEach(a => buildCol(a).appendTo($extraRow));
		}
	}

	// ─────────────────────────────────────────────────────────────────────────
	// 4. ATTENDANCE HEATMAP
	// ─────────────────────────────────────────────────────────────────────────
	function renderAttendanceHeatmap($inner, data, month) {
		const heatmap  = (data && data.heatmap) ? data.heatmap : [];
		const attCount = heatmap.filter(c => c.status !== "No Record").length;
		if (attCount === 0) return; // already shown "no records" in summary

		$inner.append(`<div class="ss-sec-heading" style="margin-top:24px;">Attendance Heatmap</div>`);
		const SC = {
			"Present":"#22c55e","Earned Leave":"#3b82f6","Casual Leave":"#8b5cf6",
			"Half Day":"#f59e0b","Absent":"#ef4444","LWP":"#dc2626",
			"Holiday":"#06b6d4","On Tour":"#0ea5e9","Comp Off":"#a855f7",
			"Earned Comp Off":"#d97706","Weekly Off":"#94a3b8","No Record":"#e2e8f0",
		};
		const todayStr = frappe.datetime.get_today();
		const year     = (data && data.year) ? parseInt(data.year) : CUR_YEAR;
		const monthNum = (data && data.month_num) ? data.month_num : (MONTHS.indexOf(month) + 1);
		const firstDay = new Date(year, monthNum - 1, 1).getDay();
		const $hmWrap  = $(`<div class="ss-heatmap-wrap"></div>`).appendTo($inner);
		const $hmGrid  = $(`<div class="ss-heatmap-grid"></div>`).appendTo($hmWrap);

		["Su","Mo","Tu","We","Th","Fr","Sa"].forEach(d => $hmGrid.append(`<div class="ss-hm-day-lbl">${d}</div>`));
		for (let i = 0; i < firstDay; i++) $hmGrid.append(`<div class="ss-hm-empty"></div>`);
		heatmap.forEach(c => {
			const col    = SC[c.status] || "#e2e8f0";
			const isNR   = c.status === "No Record";
			const isTod  = c.date === todayStr;
			const tip    = `${fmtDate(c.date)} · ${c.status}${c.late_entry?" [Late]":""}${c.early_exit?" [Early Exit]":""}`;
			const txtCol = isNR ? "#9ca3af" : "#fff";
			const $cell  = $(`<div class="ss-hm-cell ${isTod?"ss-hm-today":""}" style="background:${col};color:${txtCol};">${c.day}</div>`);
			$cell.on("mouseenter", function(e) {
				$(".ss-tooltip").text(tip).css({ display:"block", left: e.clientX + 12, top: e.clientY - 32 });
			});
			$cell.on("mousemove", function(e) {
				$(".ss-tooltip").css({ left: e.clientX + 12, top: e.clientY - 32 });
			});
			$cell.on("mouseleave", () => $(".ss-tooltip").hide());
			$hmGrid.append($cell);
		});

		const seenSt = [...new Set(heatmap.map(c => c.status))].filter(s => s !== "No Record");
		const $leg   = $(`<div class="ss-legend"></div>`).appendTo($hmWrap);
		seenSt.forEach(st => $leg.append(`<div class="ss-legend-item">
			<div class="ss-legend-dot" style="background:${SC[st]||"#e2e8f0"};"></div>${st}
		</div>`));
	}

	// ─────────────────────────────────────────────────────────────────────────
	// SKELETON
	// ─────────────────────────────────────────────────────────────────────────
	function skeletonDetail() {
		return `
			<div class="ss-skeleton" style="width:200px;height:24px;margin-bottom:20px;"></div>
			<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:20px;">
				${[1,2,3,4,5,6].map(()=>`<div class="ss-skeleton" style="height:70px;border-radius:8px;"></div>`).join("")}
			</div>
			${[1,2,3].map(()=>`<div class="ss-skeleton" style="height:44px;border-radius:8px;margin-bottom:8px;"></div>`).join("")}
			<div style="margin-top:20px;display:grid;grid-template-columns:repeat(auto-fill,minmax(90px,1fr));gap:8px;">
				${[1,2,3,4,5,6,7,8].map(()=>`<div class="ss-skeleton" style="height:60px;border-radius:8px;"></div>`).join("")}
			</div>`;
	}

	// ─────────────────────────────────────────────────────────────────────────
	// HELPERS
	// ─────────────────────────────────────────────────────────────────────────
	function fmtNum(n) {
		if (n == null) return "0.00";
		return parseFloat(n).toLocaleString("en-IN", { minimumFractionDigits:2, maximumFractionDigits:2 });
	}
	function fmtDate(d) {
		if (!d) return "—";
		const dt = new Date(d);
		if (isNaN(dt)) return d;
		return dt.toLocaleDateString("en-IN", { day:"2-digit", month:"short", year:"numeric" });
	}

	renderSearchPage();
};