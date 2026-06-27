frappe.pages["saral-hr-overview"].on_page_load = function (wrapper) {

	frappe.ui.make_app_page({
		parent: wrapper, title: "HR Workforce & Payroll Overview", single_column: true
	});

	// =========================================================================
	// STYLES — Injected once into <head> to avoid duplicates on re-load
	// =========================================================================
	if (!document.getElementById("sho-styles")) {
		$(`<style id="sho-styles">
		.sho-wrap * { box-sizing: border-box; }
		.sho-wrap { padding: 0 20px 48px; }

		/* Filter bar */
		.sho-filterbar {
			display: flex; flex-wrap: wrap; align-items: flex-end;
			gap: 12px; padding: 16px 0 20px;
			border-bottom: 1px solid var(--border-color);
		}
		.sho-filter-group { display: flex; flex-direction: column; gap: 5px; }
		.sho-filter-label { font-size: 11px; font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: .4px; }
		.sho-fselect, .sho-finput {
			height: 34px; font-size: 13px;
			border: 1px solid var(--border-color); border-radius: 6px;
			background: var(--bg-color); color: var(--text-color);
			padding: 0 10px; outline: none; transition: border-color .15s;
		}
		.sho-fselect:focus, .sho-finput:focus { border-color: var(--primary); }
		.sho-btn-apply {
			height: 34px; padding: 0 24px; font-size: 13px; font-weight: 600;
			border: none; border-radius: 6px; background: var(--primary);
			color: #fff; cursor: pointer; transition: opacity .15s;
			position: relative; min-width: 80px;
		}
		.sho-btn-apply:hover:not(:disabled) { opacity: .88; }
		.sho-btn-apply:disabled { opacity: .6; cursor: not-allowed; }
		.sho-btn-apply .btn-spinner {
			display: none; width: 14px; height: 14px;
			border: 2px solid rgba(255,255,255,.4); border-top-color: #fff;
			border-radius: 50%; animation: sho-spin .6s linear infinite;
			margin: 0 auto;
		}
		.sho-btn-apply.loading .btn-label { display: none; }
		.sho-btn-apply.loading .btn-spinner { display: block; }
		.sho-refreshed { font-size: 11px; color: var(--text-muted); line-height: 34px; margin-left: auto; display: flex; align-items: center; gap: 8px; }
		.sho-refresh-btn {
			background: none; border: 1px solid var(--border-color); border-radius: 6px;
			padding: 4px 10px; font-size: 11px; color: var(--text-muted); cursor: pointer;
			transition: background .1s; display: flex; align-items: center; gap: 4px;
		}
		.sho-refresh-btn:hover { background: var(--subtle-fg); color: var(--text-color); }

		/* ── Multi-select company dropdown ── */
		.sho-ms-wrap { position: relative; min-width: 220px; max-width: 340px; }
		.sho-ms-trigger {
			min-height: 34px; padding: 4px 28px 4px 8px; font-size: 13px;
			border: 1px solid var(--border-color); border-radius: 6px;
			background: var(--bg-color); color: var(--text-color);
			cursor: pointer; display: flex; flex-wrap: wrap; gap: 4px;
			align-items: center; position: relative; transition: border-color .15s;
			user-select: none;
		}
		.sho-ms-trigger:hover, .sho-ms-trigger.open { border-color: var(--primary); }
		.sho-ms-trigger::after {
			content: "▾"; position: absolute; right: 8px; top: 50%;
			transform: translateY(-50%); color: var(--text-muted); font-size: 12px;
			transition: transform .15s;
		}
		.sho-ms-trigger.open::after { transform: translateY(-50%) rotate(180deg); }
		.sho-ms-pill {
			display: inline-flex; align-items: center; gap: 4px;
			background: var(--primary); color: #fff;
			border-radius: 4px; padding: 1px 6px; font-size: 11px; font-weight: 600;
			white-space: nowrap; max-width: 140px; overflow: hidden; text-overflow: ellipsis;
		}
		.sho-ms-pill-x {
			cursor: pointer; font-size: 13px; line-height: 1;
			opacity: .8; flex-shrink: 0;
		}
		.sho-ms-pill-x:hover { opacity: 1; }
		.sho-ms-placeholder { color: var(--text-muted); font-size: 13px; }
		.sho-ms-dropdown {
			position: absolute; top: calc(100% + 4px); left: 0; right: 0;
			background: var(--card-bg); border: 1px solid var(--border-color);
			border-radius: 6px; box-shadow: 0 6px 20px rgba(0,0,0,.12);
			z-index: 9999; max-height: 260px; display: flex; flex-direction: column;
		}
		.sho-ms-search {
			padding: 6px 8px; border-bottom: 1px solid var(--border-color); flex-shrink: 0;
		}
		.sho-ms-search input {
			width: 100%; height: 28px; font-size: 12px;
			border: 1px solid var(--border-color); border-radius: 4px;
			padding: 0 8px; outline: none; background: var(--bg-color); color: var(--text-color);
		}
		.sho-ms-search input:focus { border-color: var(--primary); }
		.sho-ms-actions {
			display: flex; gap: 6px; padding: 4px 8px 6px;
			border-bottom: 1px solid var(--border-color); flex-shrink: 0;
		}
		.sho-ms-action-btn {
			font-size: 11px; padding: 2px 8px; border-radius: 4px; cursor: pointer;
			border: 1px solid var(--border-color); background: var(--subtle-fg);
			color: var(--text-muted); transition: background .1s;
		}
		.sho-ms-action-btn:hover { background: var(--border-color); color: var(--text-color); }
		.sho-ms-list { overflow-y: auto; flex: 1; }
		.sho-ms-option {
			display: flex; align-items: center; gap: 8px;
			padding: 7px 10px; cursor: pointer; font-size: 13px;
			color: var(--text-color); transition: background .1s;
		}
		.sho-ms-option:hover { background: var(--highlight-color); }
		.sho-ms-option.selected { font-weight: 600; }
		.sho-ms-option input[type=checkbox] { flex-shrink: 0; accent-color: var(--primary); }
		.sho-ms-empty { padding: 14px; text-align: center; font-size: 12px; color: var(--text-muted); font-style: italic; }

		/* Section blocks */
		.sho-block { margin-top: 28px; }
		.sho-block-header {
			display: flex; align-items: center; justify-content: space-between;
			margin-bottom: 14px; cursor: pointer; user-select: none; padding: 2px 0;
		}
		.sho-block-title {
			display: flex; align-items: center; gap: 8px;
			font-size: 11px; font-weight: 700; color: var(--text-muted);
			text-transform: uppercase; letter-spacing: .5px; flex: 1;
		}
		.sho-block-title::after { content: ""; flex: 1; height: 1px; background: var(--border-color); min-width: 40px; }
		.sho-title-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
		.sho-chevron { font-size: 11px; color: var(--text-muted); transition: transform .2s; flex-shrink: 0; margin-left: 8px; }
		.sho-block.collapsed .sho-chevron { transform: rotate(-90deg); }
		.sho-block.collapsed .sho-block-body { display: none; }
		.sho-block-export {
			height: 26px; padding: 0 12px; font-size: 11px; font-weight: 600;
			border: 1px solid var(--border-color); border-radius: 5px;
			background: var(--card-bg); color: var(--text-muted); cursor: pointer;
			transition: background .1s; margin-left: 10px; flex-shrink: 0;
		}
		.sho-block-export:hover { background: var(--subtle-fg); color: var(--text-color); }

		/* Zone layout */
		.sho-zone-2col { display: grid; grid-template-columns: 55% 1fr; gap: 0 28px; align-items: start; }
		.sho-zone-equal { display: grid; grid-template-columns: 1fr 1fr; gap: 0 28px; align-items: start; }
		.sho-col { min-width: 0; }
		.sho-col-divider { border-left: 1px solid var(--border-color); padding-left: 28px; }
		.sho-sub-label { font-size: 11px; font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: .4px; margin-bottom: 10px; }

		@media (max-width: 900px) {
			.sho-zone-2col, .sho-zone-equal { grid-template-columns: 1fr; }
			.sho-col-divider { border-left: none; padding-left: 0; border-top: 1px solid var(--border-color); padding-top: 20px; margin-top: 20px; }
		}

		/* KPI cards */
		.sho-kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(148px, 1fr)); gap: 10px; }
		.sho-kpi {
			background: var(--card-bg); border: 1px solid var(--border-color);
			border-radius: 8px; padding: 14px 16px; display: flex; flex-direction: column;
			justify-content: space-between; min-height: 96px;
			cursor: pointer; transition: box-shadow .15s, transform .1s, border-color .15s;
			position: relative; overflow: hidden;
		}
		.sho-kpi::before {
			content: ""; position: absolute; top: 0; left: 0; right: 0; height: 3px;
			background: var(--kpi-bar, var(--border-color)); border-radius: 8px 8px 0 0;
		}
		.sho-kpi:hover { box-shadow: 0 4px 14px rgba(0,0,0,.09); transform: translateY(-1px); border-color: var(--kpi-bar, var(--primary)); }
		.sho-kpi.no-link { cursor: default; }
		.sho-kpi.no-link:hover { box-shadow: none; transform: none; border-color: var(--border-color); }
		.sho-kpi.alert-card { background: #fff5f5; border-color: #fecaca; }
		.sho-kpi.alert-card::before { background: #ef4444; }
		.sho-kpi.alert-card .sho-kpi-val { color: #dc2626; }
		.sho-kpi.popup-card { cursor: pointer; }
		.sho-kpi.popup-card:hover { box-shadow: 0 4px 14px rgba(0,0,0,.12); border-color: var(--primary); }
		.sho-kpi-label { font-size: 11px; color: var(--text-muted); line-height: 1.4; font-weight: 500; }
		.sho-kpi-bottom { margin-top: 8px; }
		.sho-kpi-val { font-size: 26px; font-weight: 700; color: var(--text-color); line-height: 1; }
		.sho-kpi-sub { font-size: 10px; color: var(--text-light); margin-top: 4px; }
		.sho-kpi-hint { font-size: 10px; color: var(--primary); margin-top: 4px; font-weight: 600; }

		/* Tables */
		.sho-table-outer { overflow-x: auto; border: 1px solid var(--border-color); border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,.04); }
		.sho-table { width: 100%; border-collapse: collapse; font-size: 13px; }
		.sho-table thead tr { background: var(--subtle-fg); }
		.sho-table th { padding: 9px 14px; font-size: 11px; font-weight: 700; color: var(--text-muted); border-bottom: 1px solid var(--border-color); text-align: center; white-space: nowrap; letter-spacing: .3px; }
		.sho-table th.l { text-align: left; }
		.sho-table td { padding: 9px 14px; text-align: center; color: var(--text-color); border-bottom: 1px solid var(--border-color); }
		.sho-table td.l { text-align: left; font-weight: 600; }
		.sho-table tfoot td { padding: 9px 14px; font-weight: 700; font-size: 12px; border-top: 2px solid var(--border-color); background: var(--subtle-fg); text-align: center; }
		.sho-table tfoot td.l { text-align: left; }
		.sho-table tbody tr:last-child td { border-bottom: none; }
		.sho-table tbody tr:hover td { background: var(--highlight-color); transition: background .1s; }
		.sho-table td a { color: var(--primary); text-decoration: none; font-weight: 600; }
		.sho-table td a:hover { text-decoration: underline; }
		.sho-cell-link { color: var(--primary); font-weight: 700; cursor: pointer; border-bottom: 1px dashed var(--primary); }
		.sho-cell-link:hover { opacity: .8; }

		/* Sticky first column (readiness matrix) */
		.sho-matrix-outer { overflow-x: auto; border: 1px solid var(--border-color); border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,.04); }
		.sho-matrix { width: 100%; border-collapse: collapse; }
		.sho-matrix thead tr { background: var(--subtle-fg); }
		.sho-matrix th { padding: 8px 10px; font-size: 10px; font-weight: 700; color: var(--text-muted); border-bottom: 1px solid var(--border-color); text-align: center; white-space: nowrap; }
		.sho-matrix th.l, .sho-matrix td.l {
			text-align: left; position: sticky; left: 0; z-index: 2;
			background: var(--subtle-fg); min-width: 150px;
			border-right: 2px solid var(--border-color);
		}
		.sho-matrix td.l { background: var(--bg-color); font-weight: 600; color: var(--text-color); font-size: 12px; }
		.sho-matrix tbody tr:hover td.l { background: var(--highlight-color); }
		.sho-matrix td { padding: 8px 10px; text-align: center; border-bottom: 1px solid var(--border-color); }
		.sho-matrix tbody tr:last-child td { border-bottom: none; }
		.sho-matrix tbody tr:hover td { background: var(--highlight-color); }

		/* Classification table */
		.sho-cls-outer { overflow-x: auto; border: 1px solid var(--border-color); border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,.04); }
		.sho-cls-table { width: 100%; border-collapse: collapse; font-size: 13px; }
		.sho-cls-table thead tr { background: var(--subtle-fg); }
		.sho-cls-table th { padding: 9px 14px; font-size: 11px; font-weight: 700; color: var(--text-muted); border-bottom: 1px solid var(--border-color); text-align: center; letter-spacing: .3px; position: sticky; top: 0; z-index: 2; background: var(--subtle-fg); }
		.sho-cls-table th.l { text-align: left; }
		.sho-cls-table td { padding: 9px 14px; text-align: center; color: var(--text-color); border-bottom: 1px solid var(--border-color); }
		.sho-cls-table td.l { text-align: left; font-weight: 600; }
		.sho-cls-table tbody tr:last-child td { border-bottom: none; }
		.sho-cls-table tbody tr:hover td { background: var(--highlight-color); }
		.sho-cls-table tfoot td { padding: 9px 14px; font-weight: 700; font-size: 12px; border-top: 2px solid var(--border-color); background: var(--subtle-fg); text-align: center; }
		.sho-cls-table tfoot td.l { text-align: left; }

		/* Expiry table */
		.sho-expiry-outer { border: 1px solid var(--border-color); border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,.04); }
		.sho-expiry-scroll { max-height: 240px; overflow-y: auto; }
		.sho-expiry-table { width: 100%; border-collapse: collapse; font-size: 12px; }
		.sho-expiry-table thead th { padding: 8px 12px; font-size: 10px; font-weight: 700; color: var(--text-muted); border-bottom: 1px solid var(--border-color); text-align: left; letter-spacing: .3px; background: var(--subtle-fg); position: sticky; top: 0; z-index: 1; }
		.sho-expiry-table td { padding: 8px 12px; color: var(--text-color); border-bottom: 1px solid var(--border-color); }
		.sho-expiry-table tbody tr:last-child td { border-bottom: none; }
		.sho-expiry-table tbody tr:hover td { background: var(--highlight-color); }
		.expiry-ok { color: #16a34a; font-size: 13px; padding: 18px; text-align: center; font-weight: 500; }

		/* Search bar */
		.sho-search-wrap { padding: 8px 0 10px; }
		.sho-search-inner { position: relative; }
		.sho-search-inner svg { position: absolute; left: 10px; top: 50%; transform: translateY(-50%); color: var(--text-muted); pointer-events: none; }
		.sho-search-input { width: 100%; height: 32px; border: 1px solid var(--border-color); border-radius: 6px; padding: 0 12px 0 32px; font-size: 12px; background: var(--bg-color); color: var(--text-color); outline: none; }
		.sho-search-input:focus { border-color: var(--primary); }

		/* Badges */
		.sho-badge { display: inline-block; padding: 2px 9px; border-radius: 99px; font-size: 11px; font-weight: 600; white-space: nowrap; }
		.badge-red    { background: #fef2f2; color: #dc2626; border: 1px solid #fecaca; }
		.badge-green  { background: #f0fdf4; color: #16a34a; border: 1px solid #bbf7d0; }
		.badge-blue   { background: #eff6ff; color: #2563eb; border: 1px solid #bfdbfe; }
		.badge-orange { background: #fff7ed; color: #ea580c; border: 1px solid #fed7aa; }
		.badge-purple { background: #faf5ff; color: #7c3aed; border: 1px solid #e9d5ff; }
		.badge-muted  { background: var(--subtle-fg); color: var(--text-muted); border: 1px solid var(--border-color); }

		/* Attendance legend bar */
		.sho-att-legend {
			display: flex; flex-wrap: wrap; align-items: center;
			padding: 7px 12px; margin: 0 0 10px 0;
			background: #f4f5f6; border: 1px solid #d1d8dd;
			border-radius: 6px; font-family: inherit; flex-shrink: 0;
		}
		.sho-att-legend-title { font-weight: 600; font-size: 11px; color: #6c7680; margin-right: 12px; white-space: nowrap; }
		.sho-att-legend-item { display: inline-flex; align-items: center; gap: 4px; margin-right: 12px; margin-bottom: 2px; white-space: nowrap; }

		/* MODAL */
		.sho-modal-backdrop {
			position: fixed; inset: 0; background: rgba(0,0,0,.45);
			z-index: 9000; display: flex; align-items: center; justify-content: center;
			animation: sho-fade-in .15s ease;
		}
		@keyframes sho-fade-in { from { opacity: 0; } to { opacity: 1; } }
		.sho-modal {
			background: var(--card-bg); border-radius: 10px;
			box-shadow: 0 8px 40px rgba(0,0,0,.22);
			width: 96vw; max-width: 1200px; max-height: 82vh;
			display: flex; flex-direction: column;
			animation: sho-slide-up .18s ease;
		}
		.sho-modal.wide { max-width: 98vw; max-height: 86vh; }
		.sho-modal-body-pad { padding: 0 20px 20px; }

		/* Sticky first two cols in wide attendance table */
		.sho-att-table { border-collapse: separate; border-spacing: 0; }
		.sho-att-table td:nth-child(1), .sho-att-table th:nth-child(1) {
			position: sticky; left: 0; z-index: 2;
			background: var(--fg-color, #fff); border-right: 1px solid var(--border-color); min-width: 110px;
		}
		.sho-att-table td:nth-child(2), .sho-att-table th:nth-child(2) {
			position: sticky; left: 110px; z-index: 2;
			background: var(--fg-color, #fff); border-right: 2px solid var(--border-color); min-width: 140px;
		}
		.sho-att-table thead th:nth-child(1), .sho-att-table thead th:nth-child(2) { background: var(--subtle-fg); z-index: 4; }
		.sho-att-table tbody tr:hover td:nth-child(1), .sho-att-table tbody tr:hover td:nth-child(2) { background: var(--highlight-color); }
		@keyframes sho-slide-up { from { transform: translateY(16px); opacity: 0; } to { transform: none; opacity: 1; } }
		.sho-modal-header {
			display: flex; align-items: center; justify-content: space-between;
			padding: 16px 20px; border-bottom: 1px solid var(--border-color); flex-shrink: 0;
		}
		.sho-modal-title { font-size: 15px; font-weight: 700; color: var(--text-color); }
		.sho-modal-subtitle { font-size: 11px; color: var(--text-muted); margin-top: 2px; }
		.sho-modal-close {
			width: 28px; height: 28px; border-radius: 50%;
			border: 1px solid var(--border-color);
			background: var(--subtle-fg); cursor: pointer;
			display: flex; align-items: center; justify-content: center;
			font-size: 14px; color: var(--text-muted); transition: background .1s; flex-shrink: 0;
		}
		.sho-modal-close:hover { background: var(--border-color); color: var(--text-color); }
		.sho-modal-toolbar {
			padding: 12px 20px; border-bottom: 1px solid var(--border-color);
			display: flex; align-items: center; gap: 10px; flex-shrink: 0;
		}
		.sho-modal-body { flex: 1; overflow-y: auto; overflow-x: hidden; padding: 0; }
		.sho-modal-footer { padding: 12px 20px; border-top: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: center; flex-shrink: 0; }
		.sho-modal-count { font-size: 12px; color: var(--text-muted); }
		.sho-btn-export {
			height: 30px; padding: 0 16px; font-size: 12px; font-weight: 600;
			border: 1px solid var(--border-color); border-radius: 6px;
			background: var(--card-bg); color: var(--text-color);
			cursor: pointer; transition: background .1s;
		}
		.sho-btn-export:hover { background: var(--subtle-fg); }

		/* Slip popup two-column layout */
		.sho-slip-cols { display: grid; grid-template-columns: 1fr 1fr; gap: 0; height: 100%; }
		.sho-slip-col { display: flex; flex-direction: column; overflow: hidden; }
		.sho-slip-col + .sho-slip-col { border-left: 2px solid var(--border-color); }
		.sho-slip-col-header {
			padding: 12px 16px 10px; font-size: 11px; font-weight: 700; color: var(--text-muted);
			text-transform: uppercase; letter-spacing: .4px;
			background: var(--subtle-fg); border-bottom: 1px solid var(--border-color);
			display: flex; align-items: center; gap: 8px; flex-shrink: 0;
		}
		.sho-slip-col-scroll { flex: 1; overflow-y: auto; }

		/* General modal table — auto column widths, no horizontal scroll */
		.sho-modal-table { width: 100%; border-collapse: collapse; font-size: 13px; table-layout: auto; }
		.sho-modal-table thead th {
			padding: 10px 14px; font-size: 11px; font-weight: 700;
			color: var(--text-muted); border-bottom: 1px solid var(--border-color);
			text-align: left; background: var(--subtle-fg);
			position: sticky; top: 0; z-index: 3;
			white-space: nowrap; text-transform: uppercase; letter-spacing: .3px;
		}
		.sho-modal-table thead th.r { text-align: center; }
		.sho-modal-table td { padding: 10px 14px; color: var(--text-color); border-bottom: 1px solid var(--border-color); text-align: left; vertical-align: middle; word-break: break-word; }
		.sho-modal-table td.r { text-align: center; font-weight: 600; }
		.sho-modal-table td.muted { color: var(--text-muted); font-family: monospace; font-size: 12px; white-space: nowrap; }
		.sho-modal-table tbody tr:last-child td { border-bottom: none; }
		.sho-modal-table tbody tr:hover td { background: var(--highlight-color); }
		.sho-modal-empty { text-align: center; padding: 40px; color: var(--text-muted); font-size: 13px; font-style: italic; }

		/* Attendance status colors in modal */
		.att-P   { color: #1a6b1a; font-weight: 700; }
		.att-A   { color: #c0392b; font-weight: 700; }
		.att-HD  { color: #e67e22; font-weight: 700; }
		.att-T   { color: #2c3e50; font-weight: 700; }
		.att-H   { color: #27ae60; font-weight: 700; }
		.att-WO  { color: #2980b9; font-weight: 700; }
		.att-LWP { color: #8e44ad; font-weight: 700; }
		.att-EL  { color: #d35400; font-weight: 700; }
		.att-CL  { color: #16a085; font-weight: 700; }
		.att-CO  { color: #7f8c8d; font-weight: 700; }
		.att-ECO { color: #c0392b; font-weight: 700; }

		/* Skeleton */
		.sho-skeleton { background: linear-gradient(90deg, var(--subtle-fg) 25%, var(--border-color) 50%, var(--subtle-fg) 75%); background-size: 200% 100%; animation: sho-shimmer 1.4s infinite; border-radius: 6px; }
		@keyframes sho-shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }

		/* Spinner */
		.sho-spinner { text-align: center; padding: 40px 0; }
		.sho-spinner::before { content: ""; display: block; width: 28px; height: 28px; margin: 0 auto 10px; border: 3px solid var(--border-color); border-top-color: var(--primary); border-radius: 50%; animation: sho-spin .7s linear infinite; }
		@keyframes sho-spin { to { transform: rotate(360deg); } }
		.sho-empty { text-align: center; padding: 28px; color: var(--text-muted); font-size: 13px; font-style: italic; }

		/* Gender breakdown */
		.sho-gender-grid { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 10px; }
		.sho-gender-chip { display: flex; flex-direction: column; align-items: center; background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 8px; padding: 10px 16px; min-width: 80px; }
		.sho-gender-val { font-size: 20px; font-weight: 700; color: var(--text-color); }
		.sho-gender-label { font-size: 10px; color: var(--text-muted); margin-top: 3px; font-weight: 600; text-transform: uppercase; }

		/* Modal company filter select */
		.sho-modal-co-select {
			height: 32px; font-size: 12px; padding: 0 8px;
			border: 1px solid var(--border-color); border-radius: 6px;
			background: var(--bg-color); color: var(--text-color);
			outline: none; cursor: pointer; min-width: 160px;
		}
		.sho-modal-co-select:focus { border-color: var(--primary); }
		</style>`).appendTo("head");
	}

	// =========================================================================
	// HELPERS
	// =========================================================================

	function buildAttLegend() {
		const LEGEND = [
			{ code:"P",   label:"Present",           color:"#1a6b1a" },
			{ code:"A",   label:"Absent",            color:"#c0392b" },
			{ code:"HD",  label:"Half Day",          color:"#e67e22" },
			{ code:"T",   label:"On Tour",           color:"#2c3e50" },
			{ code:"H",   label:"Holiday",           color:"#27ae60" },
			{ code:"WO",  label:"Weekly Off",        color:"#2980b9" },
			{ code:"LWP", label:"Leave Without Pay", color:"#8e44ad" },
			{ code:"EL",  label:"Earned Leave",      color:"#d35400" },
			{ code:"CL",  label:"Casual Leave",      color:"#16a085" },
			{ code:"CO",  label:"Comp Off",          color:"#7f8c8d" },
			{ code:"ECO", label:"Earned Comp Off",   color:"#a93226" },
		];
		const items = LEGEND.map(({ code, label, color }) =>
			`<span class="sho-att-legend-item">
				<span style="font-weight:700;font-size:11px;color:${color};">${code}</span>
				<span style="font-size:11px;color:#555;">– ${label}</span>
			</span>`
		).join("");
		return `<div class="sho-att-legend">
			<span class="sho-att-legend-title">Legend :</span>${items}</div>`;
	}

	const COLLAPSE_KEY = "sho_collapsed_sections";
	function getCollapsedState() {
		try { return JSON.parse(localStorage.getItem(COLLAPSE_KEY) || "{}"); } catch { return {}; }
	}
	function saveCollapsedState(title, collapsed) {
		const s = getCollapsedState(); s[title] = collapsed;
		try { localStorage.setItem(COLLAPSE_KEY, JSON.stringify(s)); } catch {}
	}

	// =========================================================================
	// PAGE CONTAINER
	// =========================================================================
	const $body = $(wrapper).find(".page-content");
	$body.empty();
	const $w = $('<div class="sho-wrap"></div>').appendTo($body);

	let _companies    = [];
	let _from_date    = "";
	let _to_date      = "";
	let _allCompanies = [];

	// =========================================================================
	// FILTER BAR
	// =========================================================================
	const $fb = $('<div class="sho-filterbar"></div>').appendTo($w);

	const fyOptions = (function () {
		const yr = new Date().getFullYear();
		return Array.from({length: 5}, (_, i) => yr - 2 + i).map(y =>
			`<option value="${y}-04-01|${y+1}-03-31">${y}-${String(y+1).slice(-2)} (Apr-Mar)</option>`
		).join("");
	})();

	const _now     = new Date();
	const _cy      = _now.getFullYear();
	const _cm      = _now.getMonth() + 1;
	const _fy_from = _cm >= 4 ? `${_cy}-04-01` : `${_cy - 1}-04-01`;
	const _fy_to   = _cm >= 4 ? `${_cy + 1}-03-31` : `${_cy}-03-31`;

	$fb.append(`
		<div class="sho-filter-group">
			<span class="sho-filter-label">Company</span>
			<div class="sho-ms-wrap" id="sho-ms-wrap">
				<div class="sho-ms-trigger" id="sho-ms-trigger">
					<span class="sho-ms-placeholder" id="sho-ms-placeholder">Loading companies…</span>
				</div>
				<div class="sho-ms-dropdown" id="sho-ms-dropdown" style="display:none;">
					<div class="sho-ms-search"><input type="text" id="sho-ms-search" placeholder="Search…"></div>
					<div class="sho-ms-actions">
						<button class="sho-ms-action-btn" id="sho-ms-select-all">Select all</button>
						<button class="sho-ms-action-btn" id="sho-ms-clear-all">Clear</button>
					</div>
					<div class="sho-ms-list" id="sho-ms-list"></div>
				</div>
			</div>
		</div>
		<div class="sho-filter-group">
			<span class="sho-filter-label">Fiscal Year</span>
			<select id="sho-fy" class="sho-fselect" style="min-width:160px;">
				<option value="">Custom</option>${fyOptions}
			</select>
		</div>
		<div class="sho-filter-group">
			<span class="sho-filter-label">From</span>
			<input type="date" id="sho-from" class="sho-finput" value="${_fy_from}" style="width:140px;" />
		</div>
		<div class="sho-filter-group">
			<span class="sho-filter-label">To</span>
			<input type="date" id="sho-to" class="sho-finput" value="${_fy_to}" style="width:140px;" />
		</div>
		<div class="sho-filter-group">
			<span class="sho-filter-label">&nbsp;</span>
			<button id="sho-apply" class="sho-btn-apply">
				<span class="btn-label">Apply</span>
				<span class="btn-spinner"></span>
			</button>
		</div>
		<span class="sho-refreshed" id="sho-refreshed"></span>
	`);

	const $trigger  = $("#sho-ms-trigger", wrapper);
	const $dropdown = $("#sho-ms-dropdown", wrapper);
	const $list     = $("#sho-ms-list", wrapper);
	const $msSearch = $("#sho-ms-search", wrapper);

	let _msOpen = false;

	function openMs()  { _msOpen = true;  $trigger.addClass("open");  $dropdown.show(); }
	function closeMs() { _msOpen = false; $trigger.removeClass("open"); $dropdown.hide(); }

	$trigger.on("click", function (e) {
		e.stopPropagation();
		_msOpen ? closeMs() : openMs();
	});

	$(document).on("click.sho_ms", function (e) {
		if (!$(e.target).closest("#sho-ms-wrap", wrapper).length) closeMs();
	});

	function renderTrigger() {
		const $ph = $("#sho-ms-placeholder", wrapper);
		$trigger.find(".sho-ms-pill").remove();
		if (!_companies.length) {
			$ph.show().text("Select companies…");
		} else {
			$ph.hide();
			_companies.forEach(c => {
				const shortName = c.length > 18 ? c.slice(0, 16) + "…" : c;
				const $pill = $(`<span class="sho-ms-pill" title="${c}">
					${shortName}
					<span class="sho-ms-pill-x" data-co="${c}">×</span>
				</span>`);
				$pill.find(".sho-ms-pill-x").on("click", function (e) {
					e.stopPropagation();
					_companies = _companies.filter(x => x !== c);
					renderTrigger();
					renderList($msSearch.val());
				});
				$trigger.append($pill);
			});
		}
	}

	function renderList(q) {
		const filtered = q
			? _allCompanies.filter(c => c.toLowerCase().includes(q.toLowerCase()))
			: _allCompanies;
		if (!filtered.length) {
			$list.html('<div class="sho-ms-empty">No companies found</div>');
			return;
		}
		$list.empty();
		filtered.forEach(c => {
			const checked = _companies.includes(c);
			const $opt = $(`<div class="sho-ms-option${checked ? " selected" : ""}" data-co="${c}">
				<input type="checkbox" ${checked ? "checked" : ""}>
				<span>${c}</span>
			</div>`);
			$opt.on("click", function (e) {
				e.stopPropagation();
				const cb = $opt.find("input")[0];
				if (e.target !== cb) cb.checked = !cb.checked;
				if (cb.checked) {
					if (!_companies.includes(c)) _companies.push(c);
					$opt.addClass("selected");
				} else {
					_companies = _companies.filter(x => x !== c);
					$opt.removeClass("selected");
				}
				renderTrigger();
			});
			$list.append($opt);
		});
	}

	$msSearch.on("input", function () { renderList($(this).val()); });

	$("#sho-ms-select-all", wrapper).on("click", function (e) {
		e.stopPropagation();
		const q = $msSearch.val();
		const visible = q
			? _allCompanies.filter(c => c.toLowerCase().includes(q.toLowerCase()))
			: _allCompanies;
		visible.forEach(c => { if (!_companies.includes(c)) _companies.push(c); });
		renderTrigger(); renderList(q);
	});
	$("#sho-ms-clear-all", wrapper).on("click", function (e) {
		e.stopPropagation();
		_companies = [];
		renderTrigger(); renderList($msSearch.val());
	});

	$("#sho-fy", wrapper).on("change", function () {
		const val = $(this).val();
		if (!val) return;
		const [f, t] = val.split("|");
		$("#sho-from", wrapper).val(f);
		$("#sho-to",   wrapper).val(t);
	});

	// =========================================================================
	// SECTION BUILDER
	// =========================================================================
	function makeBlock(title, dotColor, collapsed, exportFn) {
		const collapsedState = getCollapsedState();
		const isCollapsed = collapsedState.hasOwnProperty(title) ? collapsedState[title] : !!collapsed;
		const $block = $(`<div class="sho-block${isCollapsed ? " collapsed" : ""}"></div>`).appendTo($w);
		const exportBtn = exportFn
			? `<button class="sho-block-export" title="Export section as CSV">&#11015; Export</button>` : "";
		$block.append(`
			<div class="sho-block-header">
				<div class="sho-block-title">
					<div class="sho-title-dot" style="background:${dotColor};"></div>${title}
				</div>
				${exportBtn}<span class="sho-chevron">&#9662;</span>
			</div>`);
		const $bd = $('<div class="sho-block-body"></div>').appendTo($block);
		$block.find(".sho-block-header").on("click", (e) => {
			if ($(e.target).hasClass("sho-block-export")) return;
			$block.toggleClass("collapsed");
			saveCollapsedState(title, $block.hasClass("collapsed"));
		});
		if (exportFn) $block.find(".sho-block-export").on("click", exportFn);
		return $bd;
	}

	function spinner()        { return `<div class="sho-spinner"></div>`; }
	function skeletonKpis(n)  {
		return `<div class="sho-kpi-grid">${Array.from({length: n}, () =>
			`<div class="sho-skeleton" style="height:96px;border-radius:8px;"></div>`).join("")}</div>`;
	}
	function searchBar(ph)    {
		return `<div class="sho-search-wrap"><div class="sho-search-inner">
			<svg width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
			<input type="text" class="sho-search-input" placeholder="${ph}">
		</div></div>`;
	}
	function emptyMsg(msg) { return `<div class="sho-empty">${msg}</div>`; }

	// =========================================================================
	// ZONES
	// =========================================================================
	const $z1 = makeBlock("Company Snapshot", "#4C9CF1", false);
	$z1.html(skeletonKpis(8));

	const $z2 = makeBlock("Master Data &amp; Gender", "#1D9E75", false);
	const $z2row = $('<div class="sho-zone-2col"></div>').appendTo($z2);
	const $z2l = $('<div class="sho-col"></div>').appendTo($z2row);
	const $z2r = $('<div class="sho-col sho-col-divider"></div>').appendTo($z2row);
	$z2l.append('<div class="sho-sub-label">Master Data</div><div id="sho-masters"></div>');
	$z2r.append('<div class="sho-sub-label" style="margin-top:0;">Gender Breakdown</div><div id="sho-gender"></div>');
	$z2r.append('<div class="sho-sub-label" style="margin-top:20px;">Assignment Expiry <span style="font-weight:400;text-transform:none;font-size:10px;">(next 30 days from today)</span></div>');
	$z2r.append('<div id="sho-expiry"></div>');

	const $z3 = makeBlock("Head Count Movement", "#7F77DD", false);
	const $z3row = $('<div class="sho-zone-2col"></div>').appendTo($z3);
	const $z3l   = $('<div class="sho-col"></div>').appendTo($z3row);
	const $z3r   = $('<div class="sho-col sho-col-divider"></div>').appendTo($z3row);
	$z3l.append('<div id="sho-headcount"></div>');
	$z3r.append('<div class="sho-sub-label">Department Headcount</div><div id="sho-deptcount"></div>');

	const $z4 = makeBlock("Monthly Attendance &amp; Payroll Tracker", "#BA7517", false);
	$z4.html(spinner());

	const $z5 = makeBlock("Payroll Readiness &amp; Workforce Breakdown", "#D85A30", false);
	const $z5row = $('<div class="sho-zone-equal"></div>').appendTo($z5);
	const $z5l = $('<div class="sho-col"></div>').appendTo($z5row);
	const $z5r = $('<div class="sho-col sho-col-divider"></div>').appendTo($z5row);
	$z5l.append('<div class="sho-sub-label">Payroll Readiness Checklist</div><div id="sho-readiness"></div>');
	$z5r.append('<div class="sho-sub-label">Employee Classification Breakdown</div><div id="sho-classification"></div>');

	// =========================================================================
	// LOAD COMPANIES
	// =========================================================================
	const COMPANIES_KEY = "sho_selected_companies";

	function saveSelectedCompanies() {
		try { localStorage.setItem(COMPANIES_KEY, JSON.stringify(_companies)); } catch {}
	}

	function loadSavedCompanies(available) {
		try {
			const saved = JSON.parse(localStorage.getItem(COMPANIES_KEY) || "[]");
			const valid = saved.filter(c => available.includes(c));
			return valid.length ? valid : [];
		} catch { return []; }
	}

	frappe.call({
		method: "saral_hr.saral_hr.page.saral_hr_overview.saral_hr_overview.get_companies",
		callback(r) {
			_allCompanies = r.message || [];
			const restored = loadSavedCompanies(_allCompanies);
			if (restored.length) {
				_companies = restored;
			} else if (_allCompanies.length) {
				_companies = [_allCompanies[0]];
			}
			renderTrigger();
			renderList("");
			if (_companies.length) loadAll();
		}
	});

	$("#sho-apply", wrapper).on("click", loadAll);

	function companiesJson() { return JSON.stringify(_companies); }

	function companyLabel() {
		if (_companies.length === 0) return "No company selected";
		if (_companies.length === 1) return _companies[0];
		return `${_companies.length} companies`;
	}

	// =========================================================================
	// MAIN LOAD
	// =========================================================================
	function loadAll() {
		_from_date = $("#sho-from", wrapper).val();
		_to_date   = $("#sho-to",   wrapper).val();

		if (!_companies.length)           return frappe.msgprint("Please select at least one company.");
		if (!_from_date || !_to_date)     return frappe.msgprint("Please select From and To dates.");
		if (_from_date > _to_date)        return frappe.msgprint("From date cannot be after To date.");

		saveSelectedCompanies();

		const $applyBtn = $("#sho-apply", wrapper);
		$applyBtn.addClass("loading").prop("disabled", true);

		$z1.html(skeletonKpis(8));
		$("#sho-headcount", wrapper).html(spinner());
		$("#sho-deptcount", wrapper).html(spinner());
		$z4.html(spinner());
		["sho-masters","sho-gender","sho-expiry","sho-readiness","sho-classification"]
			.forEach(id => $(`#${id}`, wrapper).html(spinner()));

		const cj = companiesJson();

		Promise.all([
			frappe.call({ method: "saral_hr.saral_hr.page.saral_hr_overview.saral_hr_overview.get_kpi_data",
				args: { companies: cj, from_date: _from_date, to_date: _to_date } }),
			frappe.call({ method: "saral_hr.saral_hr.page.saral_hr_overview.saral_hr_overview.get_monthly_data",
				args: { companies: cj, from_date: _from_date, to_date: _to_date } }),
			frappe.call({ method: "saral_hr.saral_hr.page.saral_hr_overview.saral_hr_overview.get_expiring_assignments",
				args: { companies: cj, from_date: _from_date, to_date: _to_date } }),
			frappe.call({ method: "saral_hr.saral_hr.page.saral_hr_overview.saral_hr_overview.get_classification_data",
				args: { companies: cj } }),
			frappe.call({ method: "saral_hr.saral_hr.page.saral_hr_overview.saral_hr_overview.get_department_headcount",
				args: { companies: cj } })
		]).then(([kR, mR, eR, cR, dR]) => {
			renderSnapshot(kR.message  || {});
			renderMasters(kR.message   || {});
			renderGender(kR.message    || {});
			renderHeadcount(mR.message || []);
			renderDeptCount(dR.message || {});
			renderMonthly(mR.message   || []);
			renderReadiness(mR.message || []);
			renderExpiry(eR.message    || []);
			renderClassification(cR.message || []);
			const t = frappe.datetime.now_datetime();
			$("#sho-refreshed", wrapper).html(
				`<span class="sho-badge badge-muted" style="font-size:10px;">Updated ${t.slice(11,16)}</span>
				<button class="sho-refresh-btn" onclick="document.getElementById('sho-apply').click()">&#128260; Refresh</button>`
			);
		}).catch(err => { console.error(err); frappe.msgprint("Error loading dashboard."); })
		.finally(() => { $applyBtn.removeClass("loading").prop("disabled", false); });
	}

	// =========================================================================
	// KPI HELPER
	// =========================================================================
	function kpiCard({ label, value, sub, hint, alert, link, bar, popup, popupArgs }) {
		const isPopup  = !!popup;
		const isLink   = !!link;
		const noAction = !isPopup && !isLink;
		let cls = "sho-kpi";
		if (alert)    cls += " alert-card";
		if (noAction) cls += " no-link";
		if (isPopup)  cls += " popup-card";
		const styleBar = bar && !alert ? `style="--kpi-bar:${bar};"` : "";
		let onclick = "";
		if (isPopup) onclick = `onclick="${popup}(${popupArgs || ""})"`;
		if (isLink)  onclick = `onclick="window.open('${link}','_blank')"`;
		return `<div class="${cls}" ${styleBar} ${onclick}>
			<div class="sho-kpi-label">${label}</div>
			<div class="sho-kpi-bottom">
				<div class="sho-kpi-val">${value ?? "&#8212;"}</div>
				${hint ? `<div class="sho-kpi-hint">${hint}</div>` : `<div class="sho-kpi-sub">${sub || ""}</div>`}
			</div>
		</div>`;
	}

	// =========================================================================
	// RENDER: Snapshot
	// =========================================================================
	function renderSnapshot(d) {
		const ytdFmt = d.ytd_salary_cost
			? `&#8377;${Number(d.ytd_salary_cost).toLocaleString("en-IN", {maximumFractionDigits:0})}`
			: "&#8377;0";

		const cards = [
			{ label: "Total Registered",     value: d.total_registered,
			  sub: _companies.length > 1 ? `across ${_companies.length} companies` : "includes inactive / resigned",
			  hint: "Click to view employees &#8599;",
			  popup: "openRegisteredPopup", bar: "#4C9CF1" },
			{ label: "Active Employees",      value: d.total_active,
			  hint: "Click to view employees &#8599;",
			  popup: "openActivePopup", bar: "#1D9E75" },
			{ label: "YTD Salary Cost",       value: ytdFmt,
			  sub: "net salary, selected period", bar: "#7F77DD" },
			{ label: "Salary Structures",     value: d.salary_structures,
			  hint: "Click to view structures &#8599;",
			  popup: "openSalaryStructuresPopup", bar: "#7F77DD" },
			{ label: "Structure Assignments", value: d.ssa_count,
			  hint: "Click to view assignments &#8599;",
			  popup: "openSSAPopup", bar: "#7F77DD" },
			{ label: "Holiday Days",          value: d.holiday_count,
			  hint: d.holiday_count > 0 ? "Click to view holidays &#8599;" : "from default holiday list",
			  popup: "openHolidayPopup", bar: "#BA7517" },
			{ label: "On Salary Hold",        value: d.on_hold_count,
			  hint: d.on_hold_count > 0 ? "Click to view employees &#8599;" : "status: On Hold",
			  alert: d.on_hold_count > 0, popup: "openOnHoldPopup" },
			{ label: "Without Assignment",    value: d.without_assignment,
			  hint: "Click to view employees &#8599;",
			  alert: d.without_assignment > 0, popup: "openWithoutAssignment" },
		];

		$z1.html(`<div class="sho-kpi-grid">${cards.map(kpiCard).join("")}</div>`);
	}

	// =========================================================================
	// RENDER: Masters
	// =========================================================================
	function renderMasters(d) {
		const cards = [
			{ label: "Departments",       value: d.dept_count,        sub: "global", link: "/app/department",       bar: "#4C9CF1" },
			{ label: "Designations",      value: d.designation_count, sub: "global", link: "/app/designation",      bar: "#4C9CF1" },
			{ label: "Categories",        value: d.category_count,    sub: "global", link: "/app/category",         bar: "#1D9E75" },
			{ label: "Divisions",         value: d.division_count,    sub: "global", link: "/app/division",         bar: "#1D9E75" },
			{ label: "Salary Components", value: d.salary_components, sub: "earning + deduction", link: "/app/salary-component", bar: "#7F77DD" },
		];
		$("#sho-masters", wrapper).html(`<div class="sho-kpi-grid">${cards.map(kpiCard).join("")}</div>`);
	}

	// =========================================================================
	// RENDER: Gender
	// =========================================================================
	function renderGender(d) {
		const gc = d.gender_counts || {};
		if (!Object.keys(gc).length) { $("#sho-gender", wrapper).html(emptyMsg("No employee data found.")); return; }
		const GENDER_COLORS = {
			"Male":          { bg: "#eff6ff", border: "#bfdbfe", val: "#1d4ed8", label: "#3b82f6" },
			"Female":        { bg: "#fdf2f8", border: "#f9a8d4", val: "#be185d", label: "#ec4899" },
			"Not specified": { bg: "var(--control-bg)", border: "var(--border-color)", val: "var(--text-color)", label: "var(--text-muted)" },
		};
		const total = Object.values(gc).reduce((s, v) => s + v, 0);
		const chips = Object.entries(gc).map(([g, c]) => {
			const col = GENDER_COLORS[g] || GENDER_COLORS["Not specified"];
			return `<div class="sho-gender-chip" style="background:${col.bg};border-color:${col.border};">
				<div class="sho-gender-val" style="color:${col.val};">${c}</div>
				<div class="sho-gender-label" style="color:${col.label};">${g}</div>
			</div>`;
		}).join("");
		const missingNote = d.gender_missing > 0
			? `<div style="margin-top:8px;font-size:11px;color:#dc2626;">&#9888; ${d.gender_missing} employee${d.gender_missing !== 1 ? "s" : ""} have no gender recorded.</div>`
			: "";
		$("#sho-gender", wrapper).html(`<div class="sho-gender-grid">${chips}</div>
			<div style="margin-top:8px;font-size:11px;color:var(--text-muted);">Total: <strong>${total}</strong> employees</div>${missingNote}`);
	}

	// =========================================================================
	// RENDER: Head count
	// =========================================================================
	function renderHeadcount(rows) {
		if (!rows.length) { $("#sho-headcount", wrapper).html(emptyMsg("No headcount data found for this period.")); return; }

		const processedRows = rows.map(r => ({ ...r, closing_calc: r.opening + r.joined - r.left }));
		const totJoined = processedRows.reduce((s, r) => s + r.joined, 0);
		const totLeft   = processedRows.reduce((s, r) => s + r.left,   0);

		const tbody = processedRows.map(r => {
			const netChange = r.joined - r.left;
			const netColor  = netChange > 0 ? "#16a34a" : netChange < 0 ? "#dc2626" : "var(--text-muted)";
			const netText   = netChange > 0 ? `+${netChange}` : `${netChange}`;
			return `<tr>
				<td class="l">${r.month}</td>
				<td><span class="sho-cell-link" onclick="openHcPopup('${r.month_key}','${r.month}','opening')">${r.opening} &#8599;</span></td>
				<td>${r.joined > 0
					? `<span class="sho-cell-link" onclick="openHcPopup('${r.month_key}','${r.month}','joined')"><span class="sho-badge badge-green">+${r.joined}</span> &#8599;</span>`
					: `<span style="color:var(--text-muted);">&#8212;</span>`}</td>
				<td>${r.left > 0
					? `<span class="sho-cell-link" onclick="openHcPopup('${r.month_key}','${r.month}','left')"><span class="sho-badge badge-red">&#8722;${r.left}</span> &#8599;</span>`
					: `<span style="color:var(--text-muted);">&#8212;</span>`}</td>
				<td style="color:${netColor};font-weight:700;">${netText}</td>
				<td><span class="sho-cell-link" onclick="openHcPopup('${r.month_key}','${r.month}','closing')"><strong>${r.closing_calc}</strong> &#8599;</span></td>
			</tr>`;
		}).join("");

		const totNet = totJoined - totLeft;
		const totNetColor = totNet > 0 ? "#16a34a" : totNet < 0 ? "#dc2626" : "var(--text-muted)";
		$(`#sho-headcount`, wrapper).html(`<div class="sho-table-outer"><table class="sho-table" style="min-width:380px;">
			<thead><tr><th class="l">Month</th><th>Opening &#8599;</th><th>Joined &#8599;</th><th>Left &#8599;</th><th>Net</th><th>Closing &#8599;</th></tr></thead>
			<tbody>${tbody}</tbody>
			<tfoot><tr>
				<td class="l">Total</td><td>&#8212;</td>
				<td>${totJoined}</td><td>${totLeft}</td>
				<td style="color:${totNetColor};font-weight:700;">${totNet > 0 ? '+' + totNet : totNet}</td>
				<td>&#8212;</td>
			</tr></tfoot>
		</table></div>`);
	}

	// =========================================================================
	// RENDER: Monthly tracker
	// =========================================================================
	function renderMonthly(rows) {
		if (!rows.length) { $z4.html(emptyMsg("No data found for the selected period.")); return; }

		const tbody = rows.map(r => {
			const allOk    = r.emps_with_att >= r.active_count;
			const someOk   = r.emps_with_att >= r.active_count * 0.6;
			const covColor = allOk ? "#16a34a" : someOk ? "#ea580c" : "#dc2626";
			const slipsPending = r.slips_pending || 0;

			return `<tr>
				<td class="l">${r.month}</td>
				<td><span class="sho-cell-link" onclick="openAttSummary('${r.month_key}','${r.month}')">${r.active_count} &#8599;</span></td>
				<td>${r.att_total}</td>
				<td style="color:${covColor};">${r.emps_with_att < r.active_count
					? `<span class="sho-cell-link" style="color:#dc2626;" onclick="openNoAttPopup('${r.month_key}','${r.month}')">${r.emps_with_att} / ${r.active_count} &#8599;</span>
					   <div style="font-size:10px;color:#dc2626;margin-top:2px;">&#9432; click to see missing</div>`
					: `<span style="color:#16a34a;font-weight:700;">${r.emps_with_att} / ${r.active_count}</span>`
				}</td>
				<td>${r.min_att}</td>
				<td>${r.max_att}</td>
				<td>${r.absent_total > 0   ? `<span class="sho-badge badge-red">${r.absent_total}</span>`      : `<span style="color:var(--text-muted);">0</span>`}</td>
				<td>${r.half_day_total > 0 ? `<span class="sho-badge badge-orange">${r.half_day_total}</span>` : `<span style="color:var(--text-muted);">0</span>`}</td>
				<td>${r.lwp_total > 0      ? `<span class="sho-badge badge-purple">${r.lwp_total}</span>`      : `<span style="color:var(--text-muted);">0</span>`}</td>
				<td>
					<span class="sho-cell-link" onclick="openSlipPopup('${r.month_key}','${r.month}')">
						${r.slip_count > 0 ? `<span class="sho-badge badge-blue">${r.slip_count}</span>` : `<span style="color:var(--text-muted);">0</span>`} &#8599;
					</span>
					${slipsPending > 0 ? `<span class="sho-badge badge-red" style="font-size:10px;">${slipsPending} pending</span>` : ""}
				</td>
				<td>${r.hold_count > 0
					? `<span class="sho-cell-link" onclick="openMonthHoldPopup('${r.month_key}','${r.month}')"><span class="sho-badge badge-orange">${r.hold_count}</span> &#8599;</span>`
					: `<span style="color:var(--text-muted);">&#8212;</span>`}
				</td>
			</tr>`;
		}).join("");

		const totAtt    = rows.reduce((s, r) => s + r.att_total,    0);
		const totAbsent = rows.reduce((s, r) => s + r.absent_total, 0);
		const totHD     = rows.reduce((s, r) => s + (r.half_day_total || 0), 0);
		const totLwp    = rows.reduce((s, r) => s + r.lwp_total,    0);
		const totSlips  = rows.reduce((s, r) => s + r.slip_count,   0);
		const avgActive = Math.round(rows.reduce((s, r) => s + r.active_count,  0) / rows.length);
		const avgAtt    = Math.round(rows.reduce((s, r) => s + r.emps_with_att, 0) / rows.length);

		$z4.html(`<div class="sho-table-outer"><table class="sho-table">
			<thead>
				<tr style="border-bottom:none;">
					<th class="l" rowspan="2" style="vertical-align:middle;border-right:1px solid var(--border-color);">Month</th>
					<th rowspan="2" style="vertical-align:middle;border-right:1px solid var(--border-color);">Active &#8599;</th>
					<th colspan="6" style="background:#fef3c7;color:#92400e;text-align:center;font-weight:700;">Attendance</th>
					<th colspan="1" style="background:#ede9fe;color:#4c1d95;text-align:center;font-weight:700;">Leave</th>
					<th colspan="2" style="background:#d1fae5;color:#065f46;text-align:center;font-weight:700;">Payroll</th>
				</tr>
				<tr>
					<th style="background:#fef3c7;color:#7c4d00;">Entries</th>
					<th style="background:#fef3c7;color:#7c4d00;">Emp. entered &#8599;</th>
					<th style="background:#fef3c7;color:#7c4d00;">Min days</th>
					<th style="background:#fef3c7;color:#7c4d00;">Max days</th>
					<th style="background:#fef3c7;color:#7c4d00;">Absent</th>
					<th style="background:#fef3c7;color:#7c4d00;border-right:2px solid var(--border-color);">Half Day</th>
					<th style="background:#ede9fe;color:#3b1d8e;border-right:2px solid var(--border-color);">LWP</th>
					<th style="background:#d1fae5;color:#065f46;">Slips &#8599;</th>
					<th style="background:#d1fae5;color:#065f46;">On hold &#8599;</th>
				</tr>
			</thead>
			<tbody>${tbody}</tbody>
			<tfoot><tr>
				<td class="l">Total / avg</td>
				<td>${avgActive} avg</td>
				<td>${totAtt}</td><td>${avgAtt} avg</td>
				<td>&#8212;</td><td>&#8212;</td><td>${totAbsent}</td><td>${totHD}</td><td>${totLwp}</td>
				<td>${totSlips}</td><td>&#8212;</td>
			</tr></tfoot>
		</table></div>`);
	}

	// =========================================================================
	// RENDER: Department headcount
	// =========================================================================
	function renderDeptCount(data) {
		const rows  = data.rows  || [];
		const total = data.total || 0;
		if (!rows.length) { $("#sho-deptcount", wrapper).html(emptyMsg("No department data found.")); return; }
		const bars = rows.map(r => {
			const pct = r.pct || 0;
			return `<div style="margin-bottom:10px;">
				<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:3px;">
					<span style="font-size:12px;font-weight:500;color:var(--text-color);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:65%;">${r.department}</span>
					<span style="font-size:13px;font-weight:700;color:var(--text-color);flex-shrink:0;margin-left:8px;">${r.count} <span style="font-weight:400;color:var(--text-muted);font-size:11px;">(${pct}%)</span></span>
				</div>
				<div style="height:7px;background:var(--border-color);border-radius:4px;overflow:hidden;">
					<div style="height:100%;width:${pct}%;background:#7F77DD;border-radius:4px;transition:width .5s ease;"></div>
				</div>
			</div>`;
		}).join("");
		$("#sho-deptcount", wrapper).html(`
			<div style="background:var(--card-bg);border:1px solid var(--border-color);border-radius:8px;padding:14px 16px;max-height:340px;overflow-y:auto;">
				<div style="font-size:11px;color:var(--text-muted);margin-bottom:12px;">${total} active employees across ${rows.length} department${rows.length !== 1 ? "s" : ""}</div>
				${bars}
			</div>`);
	}

	// =========================================================================
	// RENDER: Readiness matrix
	// =========================================================================
	function renderReadiness(rows) {
		if (!rows.length) { $("#sho-readiness", wrapper).html(emptyMsg("No data found.")); return; }
		const checks = [
			{ key: "ready_att",      label: "Attendance entered" },
			{ key: "ready_ssa",      label: "Salary structure" },
			{ key: "ready_no_holds", label: "No salary holds" },
			{ key: "ready_slips",    label: "Slips generated" },
		];
		const thMonths = rows.map(r => {
			const score = r.readiness_score || 0;
			const bg    = score === 4 ? "#dcfce7" : score === 3 ? "#fff7ed" : "#fef2f2";
			const color = score === 4 ? "#16a34a" : score === 3 ? "#ea580c" : "#dc2626";
			return `<th style="background:${bg};color:${color};">${r.month.replace(" ", "<br>")}</th>`;
		}).join("");
		const tbody = checks.map(c => {
			const cells = rows.map(r => {
				const ok = r[c.key];
				return `<td><span style="font-weight:700;font-size:13px;color:${ok ? "#16a34a" : "#dc2626"};">${ok ? "&#10003;" : "&#10007;"}</span></td>`;
			}).join("");
			return `<tr><td class="l">${c.label}</td>${cells}</tr>`;
		}).join("");
		$("#sho-readiness", wrapper).html(`
			<div class="sho-matrix-outer">
				<table class="sho-matrix">
					<thead><tr><th class="l">Check</th>${thMonths}</tr></thead>
					<tbody>${tbody}</tbody>
				</table>
			</div>`);
	}

	// =========================================================================
	// RENDER: Assignment expiry
	// =========================================================================
	function renderExpiry(rows) {
		if (!rows.length) {
			$("#sho-expiry", wrapper).html(`<div class="expiry-ok">&#10003; No assignments expiring in the next 30 days</div>`);
			return;
		}
		rows.sort((a, b) => (a.days_remaining || 0) - (b.days_remaining || 0));
		const showCompany = _companies.length > 1;
		const $wrap = $(`<div></div>`);
		$(`<div style="font-size:10px;color:var(--text-muted);margin-bottom:6px;font-style:italic;">Showing assignments expiring within 30 days from today.</div>`).appendTo($wrap);
		const $sb = $(searchBar("Search employee or structure...")).appendTo($wrap);
		const $tableWrap = $(`<div class="sho-expiry-outer"><div class="sho-expiry-scroll">
			<table class="sho-expiry-table">
				<thead><tr>
					<th>Employee</th><th>Structure</th>
					${showCompany ? "<th>Company</th>" : ""}
					<th>Expires on</th><th>Days left</th><th>Action</th>
				</tr></thead>
				<tbody></tbody>
			</table>
		</div></div>`).appendTo($wrap);

		function daysColor(d) { return d <= 7 ? "#dc2626" : d <= 15 ? "#ea580c" : "#16a34a"; }
		function buildRows(list) {
			$tableWrap.find("tbody").html(list.map(r => `<tr>
				<td>${r.employee_name || r.employee}</td>
				<td>${r.salary_structure}</td>
				${showCompany ? `<td style="font-size:11px;color:var(--text-muted);">${r.company || ""}</td>` : ""}
				<td>${frappe.datetime.str_to_user(r.to_date)}</td>
				<td><span style="font-weight:700;color:${daysColor(r.days_remaining)};">${r.days_remaining}d</span></td>
				<td><a href="/app/salary-structure-assignment/new-salary-structure-assignment-1?employee=${encodeURIComponent(r.employee)}" target="_blank" class="sho-badge badge-orange">Renew</a></td>
			</tr>`).join(""));
		}
		buildRows(rows);
		$sb.find(".sho-search-input").on("input", function () {
			const q = $(this).val().toLowerCase();
			buildRows(q ? rows.filter(r =>
				(r.employee_name || r.employee || "").toLowerCase().includes(q) ||
				(r.salary_structure || "").toLowerCase().includes(q)
			) : rows);
		});
		$("#sho-expiry", wrapper).html($wrap);
	}

	// =========================================================================
	// RENDER: Classification
	// =========================================================================
	function renderClassification(data) {
		const rows             = (data && data.rows)               || (Array.isArray(data) ? data : []);
		const activeSkillTypes = (data && data.active_skill_types) || ["Skilled", "Semi-skilled", "Unskilled"];
		if (!rows.length) { $("#sho-classification", wrapper).html(emptyMsg("No active employees found.")); return; }
		const SKILL_ORDER = activeSkillTypes.length ? activeSkillTypes : ["Skilled", "Semi-skilled", "Unskilled"];
		const thSkills    = SKILL_ORDER.map(s => `<th>${s}</th>`).join("");
		const grandTotal  = rows.reduce((s, r) => s + r.total, 0);
		const tbody = rows.map(r => {
			const isUnassigned = r.category === "Unassigned";
			const catLabel     = isUnassigned
				? `${r.category} <span class="sho-badge badge-orange" style="font-size:9px;">&#9888; no category</span>`
				: r.category;
			const skillCells = SKILL_ORDER.map(s => {
				if (!r.has_subtype) return `<td style="color:var(--text-muted);">&#8212;</td>`;
				const count = r.counts[s] || 0;
				const cell  = count > 0
					? `<span class="sho-cell-link" onclick="openClassPopup('${r.category}','${s}')">${count} &#8599;</span>`
					: `<span style="color:var(--text-muted);">0</span>`;
				return `<td>${cell}</td>`;
			}).join("");
			const totalCell = r.total > 0
				? `<span class="sho-cell-link" onclick="openClassPopup('${r.category}','')"><strong>${r.total}</strong> &#8599;</span>`
				: `<strong>0</strong>`;
			return `<tr><td class="l">${catLabel}</td>${skillCells}<td>${totalCell}</td></tr>`;
		}).join("");
		const tfootSkills = SKILL_ORDER.map(s => {
			const sum = rows.filter(r => r.has_subtype).reduce((t, r) => t + (r.counts[s] || 0), 0);
			return `<td><strong>${sum}</strong></td>`;
		}).join("");
		$("#sho-classification", wrapper).html(`
			<div class="sho-cls-outer"><table class="sho-cls-table">
				<thead><tr><th class="l">Category</th>${thSkills}<th>Total</th></tr></thead>
				<tbody>${tbody}</tbody>
				<tfoot><tr><td class="l">Total</td>${tfootSkills}<td><strong>${grandTotal}</strong></td></tr></tfoot>
			</table></div>`);
	}

	// =========================================================================
	// MODAL ENGINE
	// =========================================================================

	// Helper: builds company filter select HTML for modal toolbars
	function buildCoFilterHtml(rows) {
		if (_companies.length <= 1) return "";
		const hasCoField = rows.some(r => r.company);
		if (!hasCoField) return "";
		return `<select class="sho-modal-co-select">
			<option value="">All companies</option>
			${_companies.map(c => `<option value="${c}">${c}</option>`).join("")}
		</select>`;
	}

	function openModal({ title, subtitle, rows, columns, exportFilename, extraFooter }) {
		$(".sho-modal-backdrop").remove();

		const colHeaders = columns.map(c => {
			const isCenter = c.cls && c.cls.includes("r");
			return `<th class="${isCenter ? "r" : ""}">${c.label}</th>`;
		}).join("");

		const $backdrop = $('<div class="sho-modal-backdrop"></div>').appendTo("body");
		const $modal    = $('<div class="sho-modal"></div>').appendTo($backdrop);

		$modal.append(`
			<div class="sho-modal-header">
				<div>
					<div class="sho-modal-title">${title}</div>
					${subtitle ? `<div class="sho-modal-subtitle">${subtitle}</div>` : ""}
				</div>
				<button class="sho-modal-close" title="Close">&#10005;</button>
			</div>`);

		const hasCompanyField = _companies.length > 1 && rows.some(r => r.company);
		const companyOptions  = hasCompanyField
			? [...new Set(rows.map(r => r.company).filter(Boolean))].sort()
			: [];

		const $toolbar = $(`<div class="sho-modal-toolbar" style="gap:10px;">
			<div style="flex:1;"><div class="sho-search-inner">
				<svg width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
				<input type="text" class="sho-search-input" placeholder="Search...">
			</div></div>
			${hasCompanyField ? `
			<div>
				<select class="sho-modal-co-filter sho-modal-co-select">
					<option value="">All companies</option>
					${companyOptions.map(c => `<option value="${c}">${c}</option>`).join("")}
				</select>
			</div>` : ""}
		</div>`).appendTo($modal);

		const $body   = $('<div class="sho-modal-body"></div>').appendTo($modal);
		$body.css("padding", "0 20px 20px");
		const $footer = $('<div class="sho-modal-footer"></div>').appendTo($modal);
		const $count  = $('<span class="sho-modal-count"></span>').appendTo($footer);
		const $right  = $('<div style="display:flex;gap:8px;"></div>').appendTo($footer);

		if (exportFilename) {
			$(`<button class="sho-btn-export">&#11015; Export CSV</button>`).appendTo($right)
				.on("click", () => exportCSV(rows, columns, exportFilename));
		}
		if (extraFooter) $right.append(extraFooter);

		function buildTable(list) {
			$count.text(`${list.length} employee${list.length !== 1 ? "s" : ""}`);
			if (!list.length) { $body.html('<div class="sho-modal-empty">No records found.</div>'); return; }
			const trs = list.map(row => {
				const tds = columns.map(c => {
					const val   = row[c.key] ?? "&#8212;";
					const tdCls = (c.cls || "").trim();
					return `<td class="${tdCls}">${c.render ? c.render(row[c.key] ?? "", row) : val}</td>`;
				}).join("");
				return `<tr>${tds}</tr>`;
			}).join("");
			$body.html(`<table class="sho-modal-table"><thead><tr>${colHeaders}</tr></thead><tbody>${trs}</tbody></table>`);
		}

		function applyFilters() {
			const q       = $toolbar.find(".sho-search-input").val().toLowerCase();
			const selCo   = hasCompanyField
				? $toolbar.find(".sho-modal-co-filter").val()
				: "";
			let filtered = rows;
			if (selCo) filtered = filtered.filter(r => r.company === selCo);
			if (q)     filtered = filtered.filter(r =>
				columns.some(c => String(r[c.key] || "").toLowerCase().includes(q))
			);
			buildTable(filtered);
		}

		buildTable(rows);

		$toolbar.find(".sho-search-input").on("input", applyFilters);
		if (hasCompanyField) {
			$toolbar.find(".sho-modal-co-filter").on("change", applyFilters);
		}

		$modal.find(".sho-modal-close").on("click",  () => $backdrop.remove());
		$backdrop.on("click", e => { if (e.target === $backdrop[0]) $backdrop.remove(); });
	}

	function exportCSV(rows, columns, filename) {
		const header = columns.map(c => `"${c.label}"`).join(",");
		const body   = rows.map(r =>
			columns.map(c => `"${String(r[c.key] ?? "").replace(/"/g, '""')}"`).join(",")
		).join("\n");
		const blob = new Blob([header + "\n" + body], { type: "text/csv" });
		const a    = Object.assign(document.createElement("a"), {
			href: URL.createObjectURL(blob), download: filename + ".csv"
		});
		document.body.appendChild(a); a.click(); document.body.removeChild(a);
	}

	function companyCol() {
		return _companies.length > 1
			? [{ label: "Company", key: "company", cls: "muted" }]
			: [];
	}

	// =========================================================================
	// POPUP: Salary Slips — with company filter
	// =========================================================================
	window.openSlipPopup = function (monthKey, monthLabel) {
		frappe.call({
			method: "saral_hr.saral_hr.page.saral_hr_overview.saral_hr_overview.get_salary_slip_status",
			args: { companies: companiesJson(), month_key: monthKey },
			callback(r) {
				const data         = r.message || {};
				const generated    = data.generated    || [];
				const notGenerated = data.not_generated || [];
				const showCo       = _companies.length > 1;

				$(".sho-modal-backdrop").remove();
				const $backdrop = $('<div class="sho-modal-backdrop"></div>').appendTo("body");
				const $modal    = $('<div class="sho-modal wide"></div>').appendTo($backdrop);

				$modal.append(`
					<div class="sho-modal-header">
						<div>
							<div class="sho-modal-title">Salary Slip Status</div>
							<div class="sho-modal-subtitle">${monthLabel} &middot; ${companyLabel()}</div>
						</div>
						<button class="sho-modal-close" title="Close">&#10005;</button>
					</div>`);

				// ── Toolbar with search + company filter ─────────────────────
				const slipCoOptions = showCo
					? _companies.map(c => `<option value="${c}">${c}</option>`).join("")
					: "";

				const $toolbar = $(`<div class="sho-modal-toolbar" style="gap:10px;">
					<div style="flex:1;"><div class="sho-search-inner">
						<svg width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
						<input type="text" class="sho-search-input" placeholder="Search employee...">
					</div></div>
					${showCo ? `
					<div>
						<select class="sho-slip-co-filter sho-modal-co-select">
							<option value="">All companies</option>
							${slipCoOptions}
						</select>
					</div>` : ""}
				</div>`).appendTo($modal);

				const $body   = $(`<div class="sho-modal-body" style="overflow:hidden;"></div>`).appendTo($modal);
				const $cols   = $(`<div class="sho-slip-cols" style="height:100%;"></div>`).appendTo($body);
				const $leftCol    = $(`<div class="sho-slip-col"></div>`).appendTo($cols);
				const $leftHdr    = $(`<div class="sho-slip-col-header">Generated <span class="sho-badge badge-green" style="font-size:10px;" id="sho-gen-count">${generated.length}</span></div>`).appendTo($leftCol);
				const $leftScroll = $(`<div class="sho-slip-col-scroll"></div>`).appendTo($leftCol);
				const $rightCol   = $(`<div class="sho-slip-col"></div>`).appendTo($cols);
				const $rightHdr   = $(`<div class="sho-slip-col-header">Not Generated <span class="sho-badge badge-red" style="font-size:10px;" id="sho-ngen-count">${notGenerated.length}</span></div>`).appendTo($rightCol);
				const $rightScroll = $(`<div class="sho-slip-col-scroll"></div>`).appendTo($rightCol);
				const $footer = $(`<div class="sho-modal-footer"></div>`).appendTo($modal);
				const $count  = $(`<span class="sho-modal-count"></span>`).appendTo($footer);
				const $right  = $(`<div style="display:flex;gap:8px;"></div>`).appendTo($footer);

				$(`<button class="sho-btn-export">&#11015; Summary CSV</button>`).appendTo($right).on("click", () => {
					const allRows = [...generated.map(e => ({...e, _status:"Generated"})), ...notGenerated.map(e => ({...e, _status:"Not Generated"}))];
					const hdr = showCo ? "Employee ID,Name,Company,Net Salary,Status" : "Employee ID,Name,Net Salary,Status";
					const body = allRows.map(r => {
						const vals = showCo
							? [r.employee, r.full_name, r.company || "", r._status === "Generated" ? (r.net_salary || "0") : "", r._status]
							: [r.employee, r.full_name, r._status === "Generated" ? (r.net_salary || "0") : "", r._status];
						return vals.map(v => `"${String(v).replace(/"/g,'""')}"`).join(",");
					}).join("\n");
					const blob = new Blob([hdr + "\n" + body], {type:"text/csv"});
					const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: `salary_slips_summary_${monthKey}.csv` });
					document.body.appendChild(a); a.click(); document.body.removeChild(a);
				});

				function genTable(list) {
					if (!list.length) return `<div class="sho-modal-empty">No salary slips generated.</div>`;
					const rows = list.map(e => {
						const fmt = `&#8377;${Number(e.net_salary || 0).toLocaleString("en-IN", {minimumFractionDigits:2, maximumFractionDigits:2})}`;
						return `<tr>
							<td style="font-family:monospace;font-size:12px;color:var(--text-muted);white-space:nowrap;padding:9px 12px;">${e.employee}</td>
							<td style="font-weight:600;padding:9px 12px;">${e.full_name}</td>
							${showCo ? `<td style="font-size:11px;color:var(--text-muted);padding:9px 12px;">${e.company || ""}</td>` : ""}
							<td style="text-align:right;font-weight:700;color:#16a34a;white-space:nowrap;padding:9px 12px;">${fmt}</td>
							<td style="text-align:center;padding:9px 12px;white-space:nowrap;"><a href="${e.slip_url}" target="_blank" class="sho-badge badge-blue" style="font-size:10px;">${e.slip_name} &#8599;</a></td>
						</tr>`;
					}).join("");
					return `<table style="width:100%;border-collapse:collapse;font-size:13px;">
						<thead style="position:sticky;top:0;z-index:2;">
							<tr style="background:var(--subtle-fg);">
								<th style="padding:8px 12px;font-size:11px;font-weight:700;color:var(--text-muted);border-bottom:1px solid var(--border-color);text-align:left;">Emp ID</th>
								<th style="padding:8px 12px;font-size:11px;font-weight:700;color:var(--text-muted);border-bottom:1px solid var(--border-color);text-align:left;">Name</th>
								${showCo ? `<th style="padding:8px 12px;font-size:11px;font-weight:700;color:var(--text-muted);border-bottom:1px solid var(--border-color);text-align:left;">Company</th>` : ""}
								<th style="padding:8px 12px;font-size:11px;font-weight:700;color:var(--text-muted);border-bottom:1px solid var(--border-color);text-align:right;">Net Salary</th>
								<th style="padding:8px 12px;font-size:11px;font-weight:700;color:var(--text-muted);border-bottom:1px solid var(--border-color);text-align:center;">Slip</th>
							</tr>
						</thead>
						<tbody>${rows}</tbody>
					</table>`;
				}

				function notGenTable(list) {
					if (!list.length) return `<div class="sho-modal-empty" style="color:#16a34a;">All active employees have salary slips. &#10003;</div>`;
					const rows = list.map(e => `<tr>
						<td style="font-family:monospace;font-size:12px;color:var(--text-muted);white-space:nowrap;padding:9px 12px;">${e.employee}</td>
						<td style="font-weight:600;padding:9px 12px;">${e.full_name}</td>
						${showCo ? `<td style="font-size:11px;color:var(--text-muted);padding:9px 12px;">${e.company || ""}</td>` : ""}
					</tr>`).join("");
					return `<table style="width:100%;border-collapse:collapse;font-size:13px;">
						<thead style="position:sticky;top:0;z-index:2;">
							<tr style="background:var(--subtle-fg);">
								<th style="padding:8px 12px;font-size:11px;font-weight:700;color:var(--text-muted);border-bottom:1px solid var(--border-color);text-align:left;">Emp ID</th>
								<th style="padding:8px 12px;font-size:11px;font-weight:700;color:var(--text-muted);border-bottom:1px solid var(--border-color);text-align:left;">Name</th>
								${showCo ? `<th style="padding:8px 12px;font-size:11px;font-weight:700;color:var(--text-muted);border-bottom:1px solid var(--border-color);text-align:left;">Company</th>` : ""}
							</tr>
						</thead>
						<tbody>${rows}</tbody>
					</table>`;
				}

				let filteredGen = generated, filteredNotGen = notGenerated;

				function renderBoth() {
					$leftScroll.html(genTable(filteredGen));
					$rightScroll.html(notGenTable(filteredNotGen));
					$leftHdr.find("#sho-gen-count").text(filteredGen.length);
					$rightHdr.find("#sho-ngen-count").text(filteredNotGen.length);
					$count.text(`${filteredGen.length + filteredNotGen.length} employees total`);
				}
				renderBoth();

				// ── Combined search + company filter ─────────────────────────
				function applySlipFilters() {
					const q     = $toolbar.find(".sho-search-input").val().toLowerCase();
					const selCo = showCo ? $toolbar.find(".sho-slip-co-filter").val() : "";
					filteredGen = generated.filter(e =>
						(!selCo || e.company === selCo) &&
						(!q || e.employee.toLowerCase().includes(q) || e.full_name.toLowerCase().includes(q))
					);
					filteredNotGen = notGenerated.filter(e =>
						(!selCo || e.company === selCo) &&
						(!q || e.employee.toLowerCase().includes(q) || e.full_name.toLowerCase().includes(q))
					);
					renderBoth();
				}

				$toolbar.find(".sho-search-input").on("input", applySlipFilters);
				if (showCo) {
					$toolbar.find(".sho-slip-co-filter").on("change", applySlipFilters);
				}

				$modal.find(".sho-modal-close").on("click", () => $backdrop.remove());
				$backdrop.on("click", e => { if (e.target === $backdrop[0]) $backdrop.remove(); });
			}
		});
	};

	// =========================================================================
	// POPUP: Head count employees
	// =========================================================================
	window.openHcPopup = function (monthKey, monthLabel, hcType) {
		const titleMap = { opening:"Opening Headcount", joined:"Employees Who Joined", left:"Employees Who Left", closing:"Closing Headcount" };
		frappe.call({
			method: "saral_hr.saral_hr.page.saral_hr_overview.saral_hr_overview.get_headcount_employees",
			args: { companies: companiesJson(), month_key: monthKey, hc_type: hcType },
			callback(r) {
				const rows = r.message || [];
				const cols = [
					{ label: "Employee ID",     key: "employee",        cls: "muted" },
					{ label: "Name",            key: "full_name" },
					...companyCol(),
					{ label: "Department",      key: "department" },
					{ label: "Designation",     key: "designation" },
					{ label: "Date of Joining", key: "date_of_joining", cls: "muted", render: v => frappe.datetime.str_to_user(v) || "&#8212;" },
				];
				if (hcType === "left") cols.push({ label: "Left Date", key: "left_date", cls: "muted", render: v => frappe.datetime.str_to_user(v) || "&#8212;" });
				openModal({ title: titleMap[hcType], subtitle: `${monthLabel} &middot; ${companyLabel()}`, rows, columns: cols, exportFilename: `headcount_${hcType}_${monthKey}` });
			}
		});
	};

	// =========================================================================
	// POPUP: On Hold (company-wide)
	// =========================================================================
	window.openOnHoldPopup = function () {
		frappe.call({
			method: "saral_hr.saral_hr.page.saral_hr_overview.saral_hr_overview.get_on_hold_employees",
			args: { companies: companiesJson(), from_date: _from_date, to_date: _to_date },
			callback(r) {
				openModal({
					title: "Employees on Salary Hold", subtitle: companyLabel(),
					rows: r.message || [],
					columns: [
						{ label: "Employee ID",  key: "employee",   cls: "muted" },
						{ label: "Name",         key: "full_name" },
						...companyCol(),
						{ label: "Department",   key: "department" },
						{ label: "Month / Year", key: "month_year", cls: "r" },
						{ label: "Hold Date",    key: "hold_date",  cls: "r", render: v => frappe.datetime.str_to_user(v) || "&#8212;" },
						{ label: "Reason",       key: "hold_reason" },
					],
					exportFilename: "on_hold_employees"
				});
			}
		});
	};

	// =========================================================================
	// POPUP: On Hold (month-specific)
	// =========================================================================
	window.openMonthHoldPopup = function (monthKey, monthLabel) {
		frappe.call({
			method: "saral_hr.saral_hr.page.saral_hr_overview.saral_hr_overview.get_month_on_hold_employees",
			args: { companies: companiesJson(), month_key: monthKey },
			callback(r) {
				openModal({
					title: "Employees on Salary Hold", subtitle: `${monthLabel} &middot; ${companyLabel()}`,
					rows: r.message || [],
					columns: [
						{ label: "Employee ID", key: "employee",   cls: "muted" },
						{ label: "Name",        key: "full_name" },
						...companyCol(),
						{ label: "Department",  key: "department" },
						{ label: "Hold Date",   key: "hold_date",  cls: "r", render: v => frappe.datetime.str_to_user(v) || "&#8212;" },
						{ label: "Reason",      key: "hold_reason" },
					],
					exportFilename: `on_hold_${monthKey}`
				});
			}
		});
	};

	// =========================================================================
	// POPUP: Without Assignment
	// =========================================================================
	window.openWithoutAssignment = function () {
		frappe.call({
			method: "saral_hr.saral_hr.page.saral_hr_overview.saral_hr_overview.get_employees_without_assignment",
			args: { companies: companiesJson(), from_date: _from_date, to_date: _to_date },
			callback(r) {
				const rows = r.message || [];
				const createBtn = `<a href="/app/salary-structure-assignment/new-salary-structure-assignment-1" target="_blank" class="sho-btn-export">+ Create Assignment</a>`;
				openModal({
					title: "Employees Without Salary Structure Assignment",
					subtitle: `${companyLabel()} &middot; ${_from_date} to ${_to_date}`,
					rows,
					columns: [
						{ label: "Employee ID",    key: "employee",        cls: "muted" },
						{ label: "Name",           key: "full_name" },
						...companyCol(),
						{ label: "Date of Joining",key: "date_of_joining", cls: "muted", render: v => frappe.datetime.str_to_user(v) || "&#8212;" },
					],
					exportFilename: "without_assignment", extraFooter: createBtn
				});
			}
		});
	};

	// =========================================================================
	// POPUP: No Attendance
	// =========================================================================
	window.openNoAttPopup = function (monthKey, monthLabel) {
		frappe.call({
			method: "saral_hr.saral_hr.page.saral_hr_overview.saral_hr_overview.get_employees_no_attendance",
			args: { companies: companiesJson(), month_key: monthKey },
			callback(r) {
				openModal({
					title: "Employees With No Attendance", subtitle: `${monthLabel} &middot; ${companyLabel()}`,
					rows: r.message || [],
					columns: [
						{ label: "Employee ID",    key: "employee",        cls: "muted" },
						{ label: "Name",           key: "full_name" },
						...companyCol(),
						{ label: "Date of Joining",key: "date_of_joining", cls: "muted", render: v => frappe.datetime.str_to_user(v) || "&#8212;" },
					],
					exportFilename: `no_attendance_${monthKey}`
				});
			}
		});
	};

	// =========================================================================
	// POPUP: Attendance Summary — with company filter
	// =========================================================================
	window.openAttSummary = function (monthKey, monthLabel) {
		frappe.call({
			method: "saral_hr.saral_hr.page.saral_hr_overview.saral_hr_overview.get_month_attendance_summary",
			args: { companies: companiesJson(), month_key: monthKey },
			callback(r) {
				const data        = r.message || {};
				const rows        = data.rows || [];
				const totalDays   = data.total_days || 31;
				const weekendDays = data.weekend_days || [];
				const weekendSet  = new Set(weekendDays);

				const today      = frappe.datetime.get_today();
				const todayParts = today.split("-");
				const todayDay   = monthKey.startsWith(`${todayParts[0]}-${todayParts[1]}`) ? parseInt(todayParts[2]) : null;

				const COLOR_CLASS = {
					"P":"att-P","A":"att-A","HD":"att-HD","T":"att-T","H":"att-H",
					"WO":"att-WO","LWP":"att-LWP","EL":"att-EL","CL":"att-CL","CO":"att-CO","ECO":"att-ECO"
				};
				const SUMM = [
					{ label:"P",   key:"present" },          { label:"A",   key:"absent" },
					{ label:"HD",  key:"half_day" },         { label:"T",   key:"on_tour" },
					{ label:"EL",  key:"earned_leave" },     { label:"CL",  key:"casual_leave" },
					{ label:"CO",  key:"comp_off" },         { label:"ECO", key:"earned_comp_off" },
					{ label:"WO",  key:"weekly_off" },       { label:"H",   key:"holiday" },
					{ label:"LWP", key:"lwp" },
				];

				$(".sho-modal-backdrop").remove();
				const $backdrop = $('<div class="sho-modal-backdrop"></div>').appendTo("body");
				const $modal    = $('<div class="sho-modal wide"></div>').appendTo($backdrop);

				$modal.append(`
					<div class="sho-modal-header">
						<div>
							<div class="sho-modal-title">Monthly Attendance Summary</div>
							<div class="sho-modal-subtitle">${monthLabel} &middot; ${companyLabel()}</div>
						</div>
						<button class="sho-modal-close" title="Close">&#10005;</button>
					</div>`);
				$modal.append(buildAttLegend());

				// ── Toolbar with search + company filter ─────────────────────
				const showCo = _companies.length > 1;
				const attCoOptions = showCo
					? _companies.map(c => `<option value="${c}">${c}</option>`).join("")
					: "";

				const $toolbar = $(`<div class="sho-modal-toolbar" style="gap:10px;">
					<div style="flex:1;"><div class="sho-search-inner">
						<svg width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
						<input type="text" class="sho-search-input" placeholder="Search employee...">
					</div></div>
					${showCo ? `
					<div>
						<select class="sho-att-co-filter sho-modal-co-select">
							<option value="">All companies</option>
							${attCoOptions}
						</select>
					</div>` : ""}
				</div>`).appendTo($modal);

				const $body   = $('<div class="sho-modal-body"></div>').appendTo($modal);
				$body.css("padding", "0 20px 20px");
				const $footer = $('<div class="sho-modal-footer"></div>').appendTo($modal);
				const $count  = $(`<span class="sho-modal-count">${rows.length} employees</span>`).appendTo($footer);
				const $right  = $('<div style="display:flex;gap:8px;"></div>').appendTo($footer);

				$(`<button class="sho-btn-export">&#11015; Full CSV</button>`).appendTo($right).on("click", () => {
					const headers = ["Employee ID","Name",...Array.from({length:totalDays},(_,i)=>`Day ${i+1}`),...SUMM.map(s=>s.label)];
					const body = rows.map(r => [
						r.employee, r.full_name,
						...Array.from({length:totalDays},(_,i) => r[`day_${i+1}`] || ""),
						...SUMM.map(s => r[s.key] || 0)
					].map(v => `"${String(v).replace(/"/g,'""')}"`).join(",")).join("\n");
					const blob = new Blob([headers.join(",") + "\n" + body], {type:"text/csv"});
					const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: `attendance_full_${monthKey}.csv` });
					document.body.appendChild(a); a.click(); document.body.removeChild(a);
				});

				function buildTable(list) {
					$count.text(`${list.length} employee${list.length !== 1 ? "s" : ""}`);
					const dayHeaders = Array.from({length: totalDays}, (_, i) => {
						const day = i + 1; const isWkEnd = weekendSet.has(day); const isToday = day === todayDay;
						const bg = isToday ? "background:#eff6ff;color:#1d4ed8;font-weight:900;" : isWkEnd ? "background:#f3f4f6;color:#9ca3af;" : "";
						return `<th class="r" style="min-width:28px;padding:6px 4px;${bg}">${day}</th>`;
					}).join("");
					const summHeaders = SUMM.map(s =>
						`<th class="r" style="min-width:34px;padding:6px 5px;"><span class="${COLOR_CLASS[s.label]}">${s.label}</span></th>`
					).join("");
					if (!list.length) { $body.html('<div class="sho-modal-empty">No records found.</div>'); return; }
					const trs = list.map(row => {
						const dayCells = Array.from({length: totalDays}, (_, i) => {
							const day = i + 1; const code = row[`day_${day}`] || ""; const cls = COLOR_CLASS[code] || "";
							const isWkEnd = weekendSet.has(day); const isToday = day === todayDay;
							const bg = isToday ? "background:#eff6ff;" : isWkEnd ? "background:#f9fafb;" : "";
							return `<td class="r" style="padding:5px 2px;font-size:11px;font-weight:700;border-right:1px solid var(--border-color);${bg}">${code ? `<span class="${cls}">${code}</span>` : ``}</td>`;
						}).join("");
						const summCells = SUMM.map((s, i) => {
							const v = row[s.key] || 0; const cls = COLOR_CLASS[s.label] || "";
							const bdr = i === 0 ? "border-left:2px solid var(--border-color);border-right:1px solid var(--border-color);" : "border-right:1px solid var(--border-color);";
							return `<td class="r" style="padding:5px 5px;font-weight:700;${bdr}">${v > 0 ? `<span class="${cls}">${v}</span>` : `<span style="color:var(--text-muted);">0</span>`}</td>`;
						}).join("");
						return `<tr>
							<td class="muted" style="white-space:nowrap;font-size:11px;padding:5px 10px;">${row.employee}</td>
							<td style="white-space:nowrap;font-weight:600;padding:5px 10px;font-size:12px;">${row.full_name}</td>
							${dayCells}${summCells}
						</tr>`;
					}).join("");
					const grandTotals = SUMM.map(s => {
						const tot = list.reduce((acc, row) => acc + (row[s.key] || 0), 0);
						const cls = COLOR_CLASS[s.label] || "";
						return `<td class="r" style="font-weight:700;font-size:11px;border-right:1px solid var(--border-color);">${tot > 0 ? `<span class="${cls}">${tot}</span>` : `<span style="color:var(--text-muted);">0</span>`}</td>`;
					}).join("");
					const emptyDays = Array.from({length: totalDays}, () => `<td style="border-right:1px solid var(--border-color);"></td>`).join("");
					$body.html(`<table class="sho-modal-table sho-att-table" style="font-size:12px;">
						<thead><tr>
							<th style="white-space:nowrap;min-width:100px;">Employee ID</th>
							<th style="white-space:nowrap;min-width:130px;">Name</th>
							${dayHeaders}${summHeaders}
						</tr></thead>
						<tbody>${trs}</tbody>
						<tfoot><tr style="background:var(--subtle-fg);font-weight:700;">
							<td style="padding:6px 10px;font-size:11px;font-weight:700;color:var(--text-muted);">Total</td>
							<td style="padding:6px 10px;"></td>
							${emptyDays}${grandTotals}
						</tr></tfoot>
					</table>`);
				}

				buildTable(rows);

				// ── Combined search + company filter ─────────────────────────
				function applyAttFilters() {
					const q     = $toolbar.find(".sho-search-input").val().toLowerCase();
					const selCo = showCo ? $toolbar.find(".sho-att-co-filter").val() : "";
					let filtered = rows;
					if (selCo) filtered = filtered.filter(r => r.company === selCo);
					if (q)     filtered = filtered.filter(r =>
						r.full_name.toLowerCase().includes(q) || r.employee.toLowerCase().includes(q)
					);
					buildTable(filtered);
				}

				$toolbar.find(".sho-search-input").on("input", applyAttFilters);
				if (showCo) {
					$toolbar.find(".sho-att-co-filter").on("change", applyAttFilters);
				}

				$modal.find(".sho-modal-close").on("click", () => $backdrop.remove());
				$backdrop.on("click", e => { if (e.target === $backdrop[0]) $backdrop.remove(); });
			}
		});
	};

	// =========================================================================
	// POPUP: Classification
	// =========================================================================
	window.openClassPopup = function (category, skillType, department) {
		frappe.call({
			method: "saral_hr.saral_hr.page.saral_hr_overview.saral_hr_overview.get_employees_by_category_skill",
			args: { companies: companiesJson(), category, skill_type: skillType || "", department: department || "" },
			callback(r) {
				const rows   = r.message || [];
				let subtitle = category;
				if (skillType)  subtitle += ` &middot; ${skillType}`;
				if (department) subtitle += ` &middot; ${department}`;
				subtitle += ` &middot; ${companyLabel()}`;
				const hasSkill = rows.some(r => r.skill_type && r.skill_type !== "—");
				const hasDept  = rows.some(r => r.department && r.department !== "—");
				const columns  = [
					{ label: "Employee ID",    key: "employee",        cls: "muted" },
					{ label: "Name",           key: "full_name" },
					...companyCol(),
					...(hasSkill ? [{ label: "Skill Type",  key: "skill_type",  cls: "r" }] : []),
					...(hasDept  ? [{ label: "Department",  key: "department" }] : []),
					{ label: "Designation",    key: "designation" },
					{ label: "Date of Joining",key: "date_of_joining", cls: "muted", render: v => frappe.datetime.str_to_user(v) || "&#8212;" },
				];
				openModal({ title: "Employee List", subtitle, rows, columns, exportFilename: `classification_${category}_${skillType || "all"}` });
			}
		});
	};

	// =========================================================================
	// POPUP: Total Registered
	// =========================================================================
	window.openRegisteredPopup = function () {
		frappe.call({
			method: "saral_hr.saral_hr.page.saral_hr_overview.saral_hr_overview.get_registered_employees",
			args: { companies: companiesJson() },
			callback(r) {
				const rows = r.message || [];
				openModal({
					title:    "All Registered Employees",
					subtitle: `${companyLabel()} &middot; active + inactive`,
					rows,
					columns: [
						{ label: "Employee ID",     key: "employee",        cls: "muted" },
						{ label: "Name",            key: "full_name" },
						...companyCol(),
						{ label: "Department",      key: "department" },
						{ label: "Designation",     key: "designation" },
						{ label: "Date of Joining", key: "date_of_joining", cls: "muted",
						  render: v => frappe.datetime.str_to_user(v) || "&#8212;" },
						{ label: "Left Date",       key: "left_date",       cls: "muted",
						  render: v => frappe.datetime.str_to_user(v) || "&#8212;" },
						{ label: "Status",          key: "status",          cls: "r",
						  render: v => v === "Active"
						    ? `<span class="sho-badge badge-green">${v}</span>`
						    : `<span class="sho-badge badge-muted">${v}</span>` },
					],
					exportFilename: "registered_employees"
				});
			}
		});
	};

	// =========================================================================
	// POPUP: Active Employees
	// =========================================================================
	window.openActivePopup = function () {
		frappe.call({
			method: "saral_hr.saral_hr.page.saral_hr_overview.saral_hr_overview.get_active_employees",
			args: { companies: companiesJson() },
			callback(r) {
				const rows = r.message || [];
				openModal({
					title:    "Active Employees",
					subtitle: `${companyLabel()} &middot; currently active`,
					rows,
					columns: [
						{ label: "Employee ID",     key: "employee",        cls: "muted" },
						{ label: "Name",            key: "full_name" },
						...companyCol(),
						{ label: "Department",      key: "department" },
						{ label: "Designation",     key: "designation" },
						{ label: "Date of Joining", key: "date_of_joining", cls: "muted",
						  render: v => frappe.datetime.str_to_user(v) || "&#8212;" },
					],
					exportFilename: "active_employees"
				});
			}
		});
	};

	// =========================================================================
	// POPUP: Salary Structures
	// =========================================================================
	window.openSalaryStructuresPopup = function () {
		frappe.call({
			method: "saral_hr.saral_hr.page.saral_hr_overview.saral_hr_overview.get_salary_structures_list",
			args: { companies: companiesJson() },
			callback(r) {
				const rows = r.message || [];
				const showCo = _companies.length > 1;
				const columns = [
					{ label: "Structure Name", key: "name",
					  render: v => `<a href="/app/salary-structure/${encodeURIComponent(v)}" target="_blank"
					    style="color:var(--primary);font-weight:600;">${v} &#8599;</a>` },
					...(showCo ? [{ label: "Company", key: "company", cls: "muted" }] : []),
					{ label: "Currency",  key: "currency",  cls: "r" },
					{ label: "Active",    key: "is_active", cls: "r",
					  render: v => v === "Yes"
					    ? `<span class="sho-badge badge-green">${v}</span>`
					    : `<span class="sho-badge badge-muted">${v}</span>` },
					{ label: "Status",    key: "status",    cls: "r",
					  render: v => v === "Submitted"
					    ? `<span class="sho-badge badge-blue">${v}</span>`
					    : `<span class="sho-badge badge-orange">${v}</span>` },
					{ label: "Last Modified", key: "modified", cls: "muted" },
				];
				openModal({
					title:    "Salary Structures",
					subtitle: `${companyLabel()} &middot; all defined structures`,
					rows, columns,
					exportFilename: "salary_structures"
				});
			}
		});
	};

	// =========================================================================
	// POPUP: Structure Assignments
	// =========================================================================
	window.openSSAPopup = function () {
		frappe.call({
			method: "saral_hr.saral_hr.page.saral_hr_overview.saral_hr_overview.get_ssa_list",
			args: { companies: companiesJson(), from_date: _from_date, to_date: _to_date },
			callback(r) {
				const rows = r.message || [];
				openModal({
					title:    "Salary Structure Assignments",
					subtitle: `${companyLabel()} &middot; ${_from_date} to ${_to_date}`,
					rows,
					columns: [
						{ label: "Employee ID",    key: "employee",         cls: "muted" },
						{ label: "Name",           key: "full_name" },
						...companyCol(),
						{ label: "Structure",      key: "salary_structure" },
						{ label: "From Date",      key: "from_date",        cls: "muted",
						  render: v => frappe.datetime.str_to_user(v) || "&#8212;" },
						{ label: "To Date",        key: "to_date",          cls: "muted",
						  render: v => frappe.datetime.str_to_user(v) || "&#8212;" },
						{ label: "View",           key: "name",             cls: "r",
						  render: v => `<a href="/app/salary-structure-assignment/${encodeURIComponent(v)}"
						    target="_blank" class="sho-badge badge-blue" style="font-size:10px;">Open &#8599;</a>` },
					],
					exportFilename: "salary_structure_assignments"
				});
			}
		});
	};

	// =========================================================================
	// POPUP: Holiday Days
	// =========================================================================
	window.openHolidayPopup = function () {
		frappe.call({
			method: "saral_hr.saral_hr.page.saral_hr_overview.saral_hr_overview.get_holiday_list",
			args: { companies: companiesJson(), from_date: _from_date, to_date: _to_date },
			callback(r) {
				const rows = r.message || [];

				$(".sho-modal-backdrop").remove();

				const columns = [
					{ label: "Date",         key: "holiday_date",
					  render: v => frappe.datetime.str_to_user(v) || v },
					{ label: "Day",          key: "day" },
					{ label: "Description",  key: "description" },
					{ label: "Holiday List", key: "holiday_list", cls: "muted" },
				];

				const colHeaders = columns.map(c => `<th>${c.label}</th>`).join("");

				const $backdrop = $('<div class="sho-modal-backdrop"></div>').appendTo("body");
				const $modal    = $('<div class="sho-modal"></div>').appendTo($backdrop);

				$modal.append(`
					<div class="sho-modal-header">
						<div>
							<div class="sho-modal-title">Holidays</div>
							<div class="sho-modal-subtitle">${companyLabel()} &middot; ${_from_date} to ${_to_date}</div>
						</div>
						<button class="sho-modal-close" title="Close">&#10005;</button>
					</div>`);

				const $toolbar = $(`<div class="sho-modal-toolbar">
					<div style="flex:1;"><div class="sho-search-inner">
						<svg width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
						<input type="text" class="sho-search-input" placeholder="Search holiday...">
					</div></div>
				</div>`).appendTo($modal);

				const $body   = $('<div class="sho-modal-body"></div>').appendTo($modal);
				$body.css("padding", "0 20px 20px");
				const $footer = $('<div class="sho-modal-footer"></div>').appendTo($modal);
				const $count = $('<span class="sho-modal-count"></span>').appendTo($footer);
				const $right = $('<div style="display:flex;gap:8px;"></div>').appendTo($footer);

				$(`<button class="sho-btn-export">&#11015; Export CSV</button>`).appendTo($right).on("click", () => {
					const header = columns.map(c => `"${c.label}"`).join(",");
					const body   = rows.map(row =>
						columns.map(c => `"${String(row[c.key] ?? "").replace(/"/g, '""')}"`).join(",")
					).join("\n");
					const blob = new Blob([header + "\n" + body], { type: "text/csv" });
					const a = Object.assign(document.createElement("a"), {
						href: URL.createObjectURL(blob), download: "holidays.csv"
					});
					document.body.appendChild(a); a.click(); document.body.removeChild(a);
				});

				function buildTable(list) {
					$count.text(`${list.length} holiday${list.length !== 1 ? "s" : ""}`);
					if (!list.length) {
						$body.html('<div class="sho-modal-empty">No holidays found.</div>');
						return;
					}
					const trs = list.map(row => {
						const tds = columns.map(c => {
							const val = row[c.key] ?? "&#8212;";
							return `<td>${c.render ? c.render(row[c.key] ?? "", row) : val}</td>`;
						}).join("");
						return `<tr>${tds}</tr>`;
					}).join("");
					$body.html(`<table class="sho-modal-table">
						<thead><tr>${colHeaders}</tr></thead>
						<tbody>${trs}</tbody>
					</table>`);
				}

				buildTable(rows);

				$toolbar.find(".sho-search-input").on("input", function () {
					const q = $(this).val().toLowerCase();
					buildTable(q ? rows.filter(row =>
						columns.some(c => String(row[c.key] || "").toLowerCase().includes(q))
					) : rows);
				});

				$modal.find(".sho-modal-close").on("click", () => $backdrop.remove());
				$backdrop.on("click", e => { if (e.target === $backdrop[0]) $backdrop.remove(); });
			}
		});
	};

};