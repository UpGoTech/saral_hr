frappe.pages["salary-insight"].on_page_load = function (wrapper) {
    frappe.ui.make_app_page({ parent: wrapper, title: "Salary Insight" });
    inject_pp_styles();
};

frappe.pages["salary-insight"].on_page_show = function (wrapper) {
    var $main = $(wrapper).find(".layout-main-section");
    render_shell($main);
    load_companies($main);
};

// ─── Styles ───────────────────────────────────────────────────────────────────
function inject_pp_styles() {
    if (document.getElementById("si-styles")) return;
    var s = document.createElement("style");
    s.id = "si-styles";
    s.innerHTML = `
            .layout-main-section { padding-left:0!important; padding-right:0!important; }
            .layout-side-section:empty, .layout-side-section { display:none!important; }
            .layout-main-section-wrapper { width:100%!important; }

            .pp-root { padding:0 20px 40px; font-family:var(--font-stack); color:var(--text-color); }

            /* Filter bar */
            .pp-filter-bar { display:flex; align-items:center; gap:10px; padding:16px 0 0; flex-wrap:wrap; }
            .pp-filter-label { font-size:12px; font-weight:600; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.06em; margin-right:4px; }
            .pp-select {
                border:1px solid var(--border-color); background:var(--control-bg); color:var(--text-color);
                padding:5px 10px; border-radius:var(--border-radius); font-size:13px;
                font-family:var(--font-stack); outline:none; cursor:pointer; min-width:120px;
                height:30px; transition:border-color 0.15s;
            }
            .pp-select:focus, .pp-select:hover { border-color:var(--primary); }
            .pp-btn {
                height:30px; padding:0 14px; background:var(--primary); color:#fff;
                border:none; border-radius:var(--border-radius); font-size:12px; font-weight:600;
                font-family:var(--font-stack); cursor:pointer; transition:opacity 0.15s; white-space:nowrap;
            }
            .pp-btn:hover { opacity:0.88; }
            .pp-btn-outline {
                height:30px; padding:0 14px; background:transparent;
                color:var(--primary); border:1px solid var(--primary);
                border-radius:var(--border-radius); font-size:12px; font-weight:600;
                font-family:var(--font-stack); cursor:pointer; transition:all 0.15s; white-space:nowrap;
            }
            .pp-btn-outline:hover { background:var(--primary); color:#fff; }

            /* Period badge */
            .pp-period-badge {
                background:var(--blue-highlight-color,#e8f4fd); color:var(--blue-500,#1d4ed8);
                border-radius:20px; padding:3px 12px; font-size:11px; font-weight:700;
                letter-spacing:0.04em; margin-left:auto;
            }

            .pp-loading { text-align:center; padding:60px 0; color:var(--text-muted); font-size:13px; }

            /* ── TABS ── */
            .pp-tabs-bar {
                display:flex; align-items:center; gap:0;
                border-bottom:2px solid var(--border-color);
                margin:16px 0 20px; position:relative;
            }
            .pp-tab {
                padding:9px 20px; font-size:13px; font-weight:600;
                color:var(--text-muted); cursor:pointer; border:none; background:none;
                border-bottom:3px solid transparent; margin-bottom:-2px;
                transition:color 0.15s, border-color 0.15s;
                font-family:var(--font-stack); white-space:nowrap;
                display:flex; align-items:center; gap:7px;
            }
            .pp-tab:hover { color:var(--text-color); }
            .pp-tab.active { color:var(--primary); border-bottom-color:var(--primary); }
            .pp-tab-icon { font-size:15px; line-height:1; }
            .pp-tab-panel { display:none; }
            .pp-tab-panel.active { display:block; }

            /* KPI strip */
            .pp-kpi-strip { display:grid; grid-template-columns:repeat(6,1fr); gap:12px; margin-bottom:20px; }
            @media (max-width:1200px) { .pp-kpi-strip { grid-template-columns:repeat(3,1fr); } }
            @media (max-width:700px)  { .pp-kpi-strip { grid-template-columns:repeat(2,1fr); } }

            .pp-kpi {
                background:var(--card-bg); border:1px solid var(--border-color);
                border-radius:var(--border-radius-lg); padding:16px 18px;
                position:relative; overflow:hidden;
            }
            .pp-kpi::after {
                content:''; position:absolute; bottom:0; left:0; right:0;
                height:3px; border-radius:0 0 var(--border-radius-lg) var(--border-radius-lg);
            }
            .pp-kpi.k-total::after     { background:var(--blue-500,#5e64ff); }
            .pp-kpi.k-generated::after { background:var(--yellow-500,#f0a500); }
            .pp-kpi.k-submitted::after { background:var(--green-500,#28a745); }
            .pp-kpi.k-draft::after     { background:var(--orange-500,#f97316); }
            .pp-kpi.k-pending::after   { background:var(--red-500,#e03131); }
            .pp-kpi.k-cancelled::after { background:var(--gray-400,#adb5bd); }

            .pp-kpi-icon { font-size:18px; margin-bottom:8px; line-height:1; }
            .pp-kpi-val  { font-size:28px; font-weight:700; line-height:1; margin-bottom:4px; }
            .pp-kpi.k-total .pp-kpi-val     { color:var(--blue-500,#5e64ff); }
            .pp-kpi.k-generated .pp-kpi-val { color:var(--yellow-600,#d97706); }
            .pp-kpi.k-submitted .pp-kpi-val { color:var(--green-600,#1a7431); }
            .pp-kpi.k-draft .pp-kpi-val     { color:var(--orange-500,#f97316); }
            .pp-kpi.k-pending .pp-kpi-val   { color:var(--red-500,#e03131); }
            .pp-kpi.k-cancelled .pp-kpi-val { color:var(--gray-500,#8d99a6); }
            .pp-kpi-label   { font-size:11px; color:var(--text-muted); font-weight:500; }
            .pp-kpi-sub     { font-size:10px; color:var(--text-muted); margin-top:3px; }

            /* Section heading */
            .pp-section-heading {
                font-size:14px; font-weight:600; color:var(--text-color);
                margin:0 0 14px; padding-bottom:10px; border-bottom:1px solid var(--border-color);
                display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:6px;
            }
            .pp-section-heading .pp-muted { font-size:11px; color:var(--text-muted); font-weight:400; }

            /* Card */
            .pp-card { background:var(--card-bg); border:1px solid var(--border-color); border-radius:var(--border-radius-lg); padding:20px; margin-bottom:16px; }

            /* Grid */
            .pp-grid-2 { display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:16px; }
            .pp-grid-3 { display:grid; grid-template-columns:1fr 1fr 1fr; gap:16px; margin-bottom:16px; }
            @media (max-width:900px) { .pp-grid-2,.pp-grid-3 { grid-template-columns:1fr; } }

            /* Money totals */
            .pp-totals-grid { display:grid; grid-template-columns:repeat(5,1fr); gap:0; }
            @media (max-width:800px) { .pp-totals-grid { grid-template-columns:repeat(2,1fr); } }
            .pp-total-item { padding:14px 16px; border-right:1px solid var(--border-color); }
            .pp-total-item:last-child { border-right:none; }
            .pp-total-label { font-size:11px; color:var(--text-muted); margin-bottom:5px; text-transform:uppercase; letter-spacing:0.05em; }
            .pp-total-val   { font-size:18px; font-weight:700; color:var(--text-color); }
            .pp-total-val.green  { color:var(--green-600,#1a7431); }
            .pp-total-val.red    { color:var(--red-500,#e03131); }
            .pp-total-val.blue   { color:var(--blue-500,#5e64ff); }
            .pp-total-val.orange { color:var(--orange-500,#f97316); }
            .pp-total-val.purple { color:#7c3aed; }
            .pp-total-change { font-size:10px; font-weight:600; margin-top:3px; }
            .pp-total-change.up   { color:var(--green-600,#16a34a); }
            .pp-total-change.down { color:var(--red-500,#e03131); }

            /* Bar chart */
            .pp-bar-row { display:flex; align-items:center; gap:10px; margin-bottom:10px; font-size:12px; }
            .pp-bar-label {
                color:var(--text-color); font-weight:500;
                min-width:90px; max-width:90px;
                white-space:nowrap; overflow:hidden; text-overflow:ellipsis; font-size:12px;
            }
            .pp-bar-track { flex:1; height:8px; background:var(--control-bg); border-radius:4px; overflow:hidden; }
            .pp-bar-fill  { height:100%; border-radius:4px; transition:width 0.6s cubic-bezier(.4,0,.2,1); }
            .pp-bar-counts { font-size:11px; color:var(--text-muted); min-width:80px; text-align:right; }

            /* Donut */
            .pp-donut-wrap { display:flex; align-items:center; gap:28px; flex-wrap:wrap; justify-content:center; }
            .pp-donut-legend { display:flex; flex-direction:column; gap:10px; }
            .pp-legend-row  { display:flex; align-items:center; gap:8px; font-size:12px; }
            .pp-legend-dot  { width:10px; height:10px; border-radius:50%; flex-shrink:0; }
            .pp-legend-name  { color:var(--text-color); flex:1; }
            .pp-legend-count { font-weight:700; color:var(--text-color); min-width:28px; text-align:right; }
            .pp-legend-pct   { font-size:11px; color:var(--text-muted); min-width:36px; text-align:right; }

            /* Trend chart */
            .pp-trend-wrap { width:100%; overflow-x:auto; }
            .pp-trend-chart { display:flex; align-items:flex-end; gap:6px; height:80px; padding-bottom:20px; position:relative; }
            .pp-trend-bar-wrap { display:flex; flex-direction:column; align-items:center; flex:1; min-width:28px; }
            .pp-trend-bar {
                width:100%; border-radius:3px 3px 0 0;
                background:var(--blue-500,#5e64ff); opacity:0.7;
                transition:opacity 0.15s, height 0.6s cubic-bezier(.4,0,.2,1);
                cursor:pointer; position:relative;
            }
            .pp-trend-bar:hover { opacity:1; }
            .pp-trend-bar.current { opacity:1; background:var(--green-500,#28a745); }
            .pp-trend-label { font-size:9px; color:var(--text-muted); margin-top:4px; text-align:center; white-space:nowrap; }
            .pp-trend-val { font-size:9px; color:var(--text-muted); margin-bottom:2px; }

            /* Table */
            .pp-table-toolbar {
                display:flex; align-items:center; justify-content:space-between;
                margin-bottom:12px; flex-wrap:wrap; gap:8px;
            }
            .pp-table-actions { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
            .pp-search-input {
                border:1px solid var(--border-color); background:var(--control-bg); color:var(--text-color);
                padding:5px 10px; border-radius:var(--border-radius); font-size:12px;
                font-family:var(--font-stack); outline:none; width:200px; height:28px;
            }
            .pp-search-input:focus { border-color:var(--primary); }
            .pp-search-input::placeholder { color:var(--text-muted); }
            .pp-filter-select {
                border:1px solid var(--border-color); background:var(--control-bg); color:var(--text-color);
                padding:3px 8px; border-radius:var(--border-radius); font-size:12px;
                height:28px; outline:none; cursor:pointer;
            }
            .pp-filter-select:focus { border-color:var(--primary); }

            .pp-table-wrap { overflow-x:auto; }
            .pp-table { width:100%; border-collapse:collapse; font-size:12px; min-width:700px; }
            .pp-table thead th {
                background:var(--control-bg); color:var(--text-muted); font-size:11px; font-weight:600;
                text-transform:uppercase; letter-spacing:0.06em; padding:8px 12px; text-align:left;
                border-bottom:1px solid var(--border-color); white-space:nowrap;
                cursor:pointer; user-select:none; position:relative;
            }
            .pp-table thead th:hover { color:var(--text-color); }
            .pp-table thead th .pp-sort-icon { font-size:9px; margin-left:4px; opacity:0.4; }
            .pp-table thead th.sorted-asc .pp-sort-icon,
            .pp-table thead th.sorted-desc .pp-sort-icon { opacity:1; color:var(--primary); }
            .pp-table tbody td {
                padding:9px 12px; border-bottom:1px solid var(--border-color);
                color:var(--text-color); vertical-align:middle;
            }
            .pp-table tbody tr:last-child td { border-bottom:none; }
            .pp-table tbody tr:hover { background:var(--fg-color,#f8f9fa); cursor:pointer; }
            .pp-emp-name { font-weight:600; font-size:12px; color:var(--text-color); }
            .pp-emp-id   { font-size:11px; color:var(--text-muted); margin-top:1px; }
            .pp-net-sal  { font-weight:700; color:var(--text-color); }

            .pp-badge {
                display:inline-block; padding:2px 9px; border-radius:20px;
                font-size:10px; font-weight:700; letter-spacing:0.04em; text-transform:uppercase;
            }
            .pp-badge.submitted { background:var(--green-highlight-color,#d4edda); color:var(--green-avatar-color,#155724); }
            .pp-badge.draft     { background:var(--yellow-highlight-color,#fff3cd); color:#856404; }
            .pp-badge.cancelled { background:var(--gray-100,#f1f3f4); color:var(--gray-600,#666); }

            .pp-table-empty { text-align:center; padding:32px; color:var(--text-muted); font-size:13px; }

            /* Pagination */
            .pp-pagination {
                display:flex; align-items:center; justify-content:space-between;
                margin-top:12px; flex-wrap:wrap; gap:8px; font-size:12px; color:var(--text-muted);
            }
            .pp-page-btns { display:flex; gap:4px; }
            .pp-page-btn {
                min-width:28px; height:28px; padding:0 8px;
                border:1px solid var(--border-color); background:var(--card-bg);
                color:var(--text-color); border-radius:var(--border-radius);
                font-size:12px; cursor:pointer; transition:all 0.15s;
                display:flex; align-items:center; justify-content:center;
            }
            .pp-page-btn:hover { border-color:var(--primary); color:var(--primary); }
            .pp-page-btn.active { background:var(--primary); color:#fff; border-color:var(--primary); }
            .pp-page-btn:disabled { opacity:0.4; cursor:default; }

            /* Activity list */
            .pp-activity-item {
                display:flex; align-items:center; gap:10px; padding:8px 0;
                border-bottom:1px solid var(--border-color); font-size:12px;
            }
            .pp-activity-item:last-child { border-bottom:none; }
            .pp-activity-dot { width:8px; height:8px; border-radius:50%; flex-shrink:0; }
            .pp-activity-info { flex:1; min-width:0; }
            .pp-activity-name { font-weight:600; color:var(--text-color); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
            .pp-activity-meta { font-size:11px; color:var(--text-muted); margin-top:1px; }
            .pp-activity-amt  { font-weight:700; font-size:12px; white-space:nowrap; }

            .pp-pending-emp {
                display:flex; align-items:center; justify-content:space-between;
                padding:6px 0; border-bottom:1px solid var(--border-color); font-size:12px;
            }
            .pp-pending-emp:last-child { border-bottom:none; }

            .pp-highlight-row {
                display:flex; justify-content:space-between; align-items:center;
                padding:8px 12px; border-radius:6px; margin-bottom:6px; font-size:12px;
            }
            .pp-highlight-row.top    { background:#f0fdf4; }
            .pp-highlight-row.bottom { background:#fff5f5; }
            .pp-highlight-name { font-weight:600; color:var(--text-color); }
            .pp-highlight-meta { font-size:11px; color:var(--text-muted); }
            .pp-highlight-amt  { font-weight:700; }
            .pp-highlight-amt.top    { color:var(--green-600,#16a34a); }
            .pp-highlight-amt.bottom { color:var(--red-500,#e03131); }

            /* ── SSA TOOLS TAB ── */
            .ssa-tools-root { padding-top:4px; }

            .ssa-tools-grid {
                display:grid;
                grid-template-columns:1fr 1fr;
                gap:16px;
                margin-bottom:16px;
            }
            @media (max-width:900px) { .ssa-tools-grid { grid-template-columns:1fr; } }

            /* Search card */
            .ssa-search-card {
                background:var(--card-bg);
                border:1px solid var(--border-color);
                border-radius:var(--border-radius-lg);
                overflow:hidden;
            }
            .ssa-card-header {
                padding:14px 18px 12px;
                border-bottom:1px solid var(--border-color);
                display:flex; align-items:center; gap:10px;
            }
            .ssa-card-icon {
                width:32px; height:32px; border-radius:8px;
                display:flex; align-items:center; justify-content:center;
                font-size:16px; flex-shrink:0;
            }
            .ssa-card-icon.blue   { background:#eff6ff; }
            .ssa-card-icon.green  { background:#f0fdf4; }
            .ssa-card-title { font-size:13px; font-weight:600; color:var(--text-color); }
            .ssa-card-subtitle { font-size:11px; color:var(--text-muted); margin-top:1px; }
            .ssa-card-body { padding:16px 18px; }

            /* Employee search input */
            .ssa-search-wrap { position:relative; margin-bottom:12px; }
            .ssa-search-icon {
                position:absolute; left:10px; top:50%; transform:translateY(-50%);
                color:var(--text-muted); font-size:13px; pointer-events:none;
            }
            .ssa-emp-input {
                width:100%; height:34px; padding:0 34px 0 32px;
                border:1px solid var(--border-color); border-radius:var(--border-radius);
                background:var(--control-bg); color:var(--text-color);
                font-size:13px; font-family:var(--font-stack); outline:none;
                box-sizing:border-box; transition:border-color 0.15s;
            }
            .ssa-emp-input:focus { border-color:var(--primary); box-shadow:0 0 0 2px rgba(var(--primary-rgb,94,100,255),0.08); }
            .ssa-emp-input::placeholder { color:var(--text-muted); }
            .ssa-search-clear {
                position:absolute; right:8px; top:50%; transform:translateY(-50%);
                width:18px; height:18px; border-radius:50%; background:var(--text-muted);
                color:#fff; border:none; cursor:pointer; font-size:10px;
                display:none; align-items:center; justify-content:center; padding:0;
            }
            .ssa-search-clear.show { display:flex; }
            .ssa-search-clear:hover { background:var(--text-color); }

            /* Dropdown results */
            .ssa-emp-dropdown {
                display:none; position:absolute; top:100%; left:0; right:0; z-index:500;
                background:var(--card-bg); border:1px solid var(--border-color);
                border-top:none; border-radius:0 0 var(--border-radius) var(--border-radius);
                max-height:240px; overflow-y:auto;
                box-shadow:0 4px 12px rgba(0,0,0,0.08);
            }
            .ssa-emp-dropdown.show { display:block; }
            .ssa-emp-opt {
                padding:9px 14px; cursor:pointer; border-bottom:1px solid var(--border-color);
                transition:background 0.12s;
            }
            .ssa-emp-opt:last-child { border-bottom:none; }
            .ssa-emp-opt:hover, .ssa-emp-opt.focused { background:var(--control-bg); }
            .ssa-emp-opt-name { font-size:13px; font-weight:500; color:var(--text-color); }
            .ssa-emp-opt-id   { font-size:11px; color:var(--text-muted); margin-top:1px; }
            .ssa-emp-no-result { padding:12px 14px; font-size:12px; color:var(--text-muted); text-align:center; }
            .ssa-highlight { font-weight:700; color:var(--primary); }

            /* SSA result cards */
            .ssa-result-area { min-height:60px; }
            .ssa-result-empty {
                text-align:center; padding:28px 0;
                color:var(--text-muted); font-size:12px;
            }
            .ssa-result-empty .ssa-result-icon { font-size:28px; margin-bottom:8px; }

            .ssa-result-card {
                border:1px solid var(--border-color); border-radius:var(--border-radius-lg);
                overflow:hidden; margin-bottom:10px;
                transition:box-shadow 0.15s;
            }
            .ssa-result-card:hover { box-shadow:0 2px 8px rgba(0,0,0,0.08); }
            .ssa-result-head {
                display:flex; align-items:center; justify-content:space-between;
                padding:10px 14px; background:var(--control-bg);
                border-bottom:1px solid var(--border-color);
            }
            .ssa-result-name-block .ssa-result-empname { font-size:13px; font-weight:600; color:var(--text-color); }
            .ssa-result-name-block .ssa-result-empid   { font-size:11px; color:var(--text-muted); margin-top:1px; }
            .ssa-result-actions { display:flex; gap:6px; align-items:center; }

            .ssa-result-body { padding:12px 14px; }
            .ssa-result-row {
                display:grid; grid-template-columns:1fr 1fr;
                gap:6px 16px; font-size:12px;
            }
            .ssa-result-field { display:flex; flex-direction:column; gap:1px; padding:5px 0; border-bottom:1px solid var(--border-color); }
            .ssa-result-field:nth-last-child(-n+2) { border-bottom:none; }
            .ssa-result-field-label { font-size:10px; text-transform:uppercase; letter-spacing:0.05em; color:var(--text-muted); font-weight:600; }
            .ssa-result-field-val   { font-size:12px; font-weight:500; color:var(--text-color); }
            .ssa-result-field-val.money { color:var(--green-600,#16a34a); font-weight:700; }
            .ssa-status-pill {
                display:inline-flex; align-items:center; gap:4px;
                padding:2px 8px; border-radius:20px; font-size:10px; font-weight:700;
            }
            .ssa-status-pill.submitted { background:#d4edda; color:#155724; }
            .ssa-status-pill.draft     { background:#fff3cd; color:#856404; }
            .ssa-status-pill.cancelled { background:#f1f3f4; color:#666; }
            .ssa-status-dot { width:6px; height:6px; border-radius:50%; }
            .ssa-status-pill.submitted .ssa-status-dot { background:#28a745; }
            .ssa-status-pill.draft     .ssa-status-dot { background:#f0a500; }
            .ssa-status-pill.cancelled .ssa-status-dot { background:#adb5bd; }

            /* Export card */
            .ssa-export-card {
                background:var(--card-bg);
                border:1px solid var(--border-color);
                border-radius:var(--border-radius-lg);
                overflow:hidden;
            }

            .ssa-export-option {
                display:flex; align-items:center; gap:14px;
                padding:14px 18px; border-bottom:1px solid var(--border-color);
                cursor:pointer; transition:background 0.12s;
            }
            .ssa-export-option:last-child { border-bottom:none; }
            .ssa-export-option:hover { background:var(--control-bg); }
            .ssa-export-opt-icon {
                width:38px; height:38px; border-radius:10px; flex-shrink:0;
                display:flex; align-items:center; justify-content:center; font-size:18px;
            }
            .ssa-export-opt-icon.xlsx { background:#e8f5e9; }
            .ssa-export-opt-icon.csv  { background:#e3f2fd; }
            .ssa-export-opt-info { flex:1; min-width:0; }
            .ssa-export-opt-title { font-size:13px; font-weight:600; color:var(--text-color); }
            .ssa-export-opt-desc  { font-size:11px; color:var(--text-muted); margin-top:2px; }
            .ssa-export-opt-arrow { color:var(--text-muted); font-size:16px; transition:transform 0.15s; }
            .ssa-export-option:hover .ssa-export-opt-arrow { transform:translateX(3px); color:var(--primary); }

            .ssa-export-loading {
                display:none; align-items:center; gap:8px; padding:10px 18px;
                font-size:12px; color:var(--text-muted);
                border-top:1px solid var(--border-color);
            }
            .ssa-export-loading.show { display:flex; }
            .ssa-spinner {
                width:14px; height:14px; border-radius:50%;
                border:2px solid var(--border-color);
                border-top-color:var(--primary);
                animation:ssa-spin 0.7s linear infinite;
            }
            @keyframes ssa-spin { to { transform:rotate(360deg); } }

            /* Filters for SSA export */
            .ssa-export-filters {
                padding:12px 18px; border-bottom:1px solid var(--border-color);
                display:flex; gap:8px; flex-wrap:wrap; align-items:center;
            }
            .ssa-filter-chip {
                display:inline-flex; align-items:center; gap:5px;
                padding:3px 10px; border-radius:20px; font-size:11px; font-weight:600;
                border:1px solid var(--border-color); cursor:pointer;
                background:var(--card-bg); color:var(--text-muted);
                transition:all 0.12s;
            }
            .ssa-filter-chip:hover { border-color:var(--primary); color:var(--primary); }
            .ssa-filter-chip.active { background:var(--primary); color:#fff; border-color:var(--primary); }
            .ssa-filter-label { font-size:11px; font-weight:600; color:var(--text-muted); }
        `;
    document.head.appendChild(s);
}

// ─── Shell ────────────────────────────────────────────────────────────────────
function render_shell($main) {
    var yr = new Date().getFullYear();
    var MONTHS = ['January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'];
    var cur_month = MONTHS[new Date().getMonth()];

    var saved_year = localStorage.getItem('si_year') || yr;
    var saved_month = localStorage.getItem('si_month') || cur_month;
    var saved_tab = localStorage.getItem('si_tab') || 'payroll';

    var year_opts = [yr - 2, yr - 1, yr, yr + 1].map(function (y) {
        return "<option value='" + y + "'" + (String(y) === String(saved_year) ? " selected" : "") + ">" + y + "</option>";
    }).join('');

    var month_sel = MONTHS.map(function (m) {
        return "<option value='" + m + "'" + (m === saved_month ? " selected" : "") + ">" + m + "</option>";
    }).join('');

    $main.html(`
            <div class="pp-root">
                <div class="pp-filter-bar" id="pp-filter-bar">
                    <span class="pp-filter-label">Filters</span>
                    <select class="pp-select" id="pp-company"></select>
                    <select class="pp-select" id="pp-year">${year_opts}</select>
                    <select class="pp-select" id="pp-month">${month_sel}</select>
                    <button class="pp-btn" id="pp-refresh">Refresh</button>
                    <button class="pp-btn-outline" id="pp-export-csv">⬇ Export CSV</button>
                    <span class="pp-period-badge" id="pp-period-label"></span>
                </div>

                <div class="pp-tabs-bar">
                    <button class="pp-tab ${saved_tab === 'payroll' ? 'active' : ''}" data-tab="payroll">
                        <span class="pp-tab-icon">📊</span> Payroll Overview
                    </button>
                    <button class="pp-tab ${saved_tab === 'ssa' ? 'active' : ''}" data-tab="ssa">
                        <span class="pp-tab-icon">📄</span> Salary Structures
                    </button>
                </div>

                <div class="pp-tab-panel ${saved_tab === 'payroll' ? 'active' : ''}" id="pp-tab-payroll">
                    <div id="pp-body">
                        <div class="pp-loading">${frappe.utils.icon('loading', 'xs')} &nbsp;Loading salary data...</div>
                    </div>
                </div>

                <div class="pp-tab-panel ${saved_tab === 'ssa' ? 'active' : ''}" id="pp-tab-ssa">
                    <div class="ssa-tools-root" id="ssa-tools-root"></div>
                </div>
            </div>
        `);

    // Tab switching
    $main.find('.pp-tab').on('click', function () {
        var tab = $(this).data('tab');
        $main.find('.pp-tab').removeClass('active');
        $main.find('.pp-tab-panel').removeClass('active');
        $(this).addClass('active');
        $main.find('#pp-tab-' + tab).addClass('active');
        localStorage.setItem('si_tab', tab);

        // Show/hide filter bar only for payroll tab
        if (tab === 'payroll') {
            $main.find('#pp-filter-bar').show();
        } else {
            $main.find('#pp-filter-bar').hide();
            // Render SSA tools if not yet rendered
            if (!$main.find('#ssa-tools-root').data('rendered')) {
                render_ssa_tools($main);
                $main.find('#ssa-tools-root').data('rendered', true);
            }
        }
    });

    // Hide filter bar if starting on SSA tab
    if (saved_tab === 'ssa') {
        $main.find('#pp-filter-bar').hide();
    }

    $main.find('#pp-refresh').on('click', function () { load_dashboard($main); });
    $main.find('#pp-year, #pp-month, #pp-company').on('change', function () { load_dashboard($main); });
    $main.find('#pp-export-csv').on('click', function () { export_csv($main); });
}

// ─── Load companies ───────────────────────────────────────────────────────────
function load_companies($main) {
    frappe.db.get_list('Company', { fields: ['name'], limit: 50 }).then(function (rows) {
        var saved_co = localStorage.getItem('si_company') || '';
        var $sel = $main.find('#pp-company');
        $sel.html(rows.map(function (r) {
            return "<option value='" + r.name + "'" + (r.name === saved_co ? " selected" : "") + ">" + r.name + "</option>";
        }).join(''));
        // If starting on SSA tab, render it; else load dashboard
        var saved_tab = localStorage.getItem('si_tab') || 'payroll';
        if (saved_tab === 'ssa') {
            render_ssa_tools($main);
            $main.find('#ssa-tools-root').data('rendered', true);
        } else {
            load_dashboard($main);
        }
    });
}

// ═══════════════════════════════════════════════════════════════════════════════
// ─── SSA TOOLS TAB ────────────────────────────────────────────────────────────
// ═══════════════════════════════════════════════════════════════════════════════

function render_ssa_tools($main) {
    var $root = $main.find('#ssa-tools-root');

    $root.html(`
            <div class="ssa-tools-grid">

                <!-- Left: Employee SSA Search -->
                <div class="ssa-search-card">
                    <div class="ssa-card-header">
                        <div class="ssa-card-icon blue">🔍</div>
                        <div>
                            <div class="ssa-card-title">Employee Salary Structure</div>
                            <div class="ssa-card-subtitle">Search an employee to view their active assignments</div>
                        </div>
                    </div>
                    <div class="ssa-card-body">
                        <div class="ssa-search-wrap">
                            <span class="ssa-search-icon">🔎</span>
                            <input type="text" class="ssa-emp-input" id="ssa-emp-input"
                                placeholder="Type name or employee ID..." autocomplete="off">
                            <button class="ssa-search-clear" id="ssa-clear-btn">✕</button>
                            <div class="ssa-emp-dropdown" id="ssa-emp-dropdown"></div>
                        </div>
                        <div class="ssa-result-area" id="ssa-result-area">
                            <div class="ssa-result-empty">
                                <div class="ssa-result-icon">👤</div>
                                <div>Search for an employee to view their salary structure assignments</div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Right: Export -->
                <div class="ssa-export-card">
                    <div class="ssa-card-header">
                        <div class="ssa-card-icon green">⬇️</div>
                        <div>
                            <div class="ssa-card-title">Export Salary Structures</div>
                            <div class="ssa-card-subtitle">Download all assignments as a flat, single-row-per-record file</div>
                        </div>
                    </div>

                    <div class="ssa-export-filters">
                        <span class="ssa-filter-label">Status:</span>
                        <span class="ssa-filter-chip active" data-status="">All</span>
                        <span class="ssa-filter-chip" data-status="1">Submitted</span>
                        <span class="ssa-filter-chip" data-status="0">Draft</span>
                        <span class="ssa-filter-chip" data-status="2">Cancelled</span>
                    </div>

                    <div class="ssa-export-option" id="ssa-export-xlsx">
                        <div class="ssa-export-opt-icon xlsx">📊</div>
                        <div class="ssa-export-opt-info">
                            <div class="ssa-export-opt-title">Download Excel (.xlsx)</div>
                            <div class="ssa-export-opt-desc">Formatted workbook — one row per assignment, earnings &amp; deductions as columns</div>
                        </div>
                        <span class="ssa-export-opt-arrow">›</span>
                    </div>

                    <div class="ssa-export-option" id="ssa-export-csv-btn">
                        <div class="ssa-export-opt-icon csv">📋</div>
                        <div class="ssa-export-opt-info">
                            <div class="ssa-export-opt-title">Download CSV</div>
                            <div class="ssa-export-opt-desc">Plain CSV — easy to open in any spreadsheet tool</div>
                        </div>
                        <span class="ssa-export-opt-arrow">›</span>
                    </div>

                    <div class="ssa-export-loading" id="ssa-export-loading">
                        <div class="ssa-spinner"></div>
                        <span id="ssa-export-loading-text">Preparing export…</span>
                    </div>
                </div>

            </div>
        `);

    _init_ssa_search($root);
    _init_ssa_export($root);
}

// ── SSA Employee Search ───────────────────────────────────────────────────────
function _init_ssa_search($root) {
    var $input = $root.find('#ssa-emp-input');
    var $dropdown = $root.find('#ssa-emp-dropdown');
    var $clearBtn = $root.find('#ssa-clear-btn');
    var $result = $root.find('#ssa-result-area');
    var debounceT = null;
    var focusedIdx = -1;

    function esc(str) {
        if (!str) return '';
        return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    function highlight(text, term) {
        if (!term) return esc(text);
        var re = new RegExp('(' + term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'gi');
        return esc(text).replace(re, '<span class="ssa-highlight">$1</span>');
    }

    function showDropdown(emps, term) {
        focusedIdx = -1;
        if (!emps.length) {
            $dropdown.html('<div class="ssa-emp-no-result">No employees found</div>').addClass('show');
            return;
        }
        $dropdown.html(emps.map(function (e, i) {
            return '<div class="ssa-emp-opt" data-idx="' + i + '" data-id="' + esc(e.name) + '">' +
                '<div class="ssa-emp-opt-name">' + highlight(e.employee_name || e.full_name || e.name, term) + '</div>' +
                '<div class="ssa-emp-opt-id">' + highlight(e.name, term) + '</div>' +
                '</div>';
        }).join('')).addClass('show');

        $dropdown.find('.ssa-emp-opt').on('click', function () {
            var id = $(this).data('id');
            var emp = emps.find(function (e) { return e.name === id; });
            if (emp) selectEmployee(emp);
        });
    }

    function hideDropdown() { $dropdown.removeClass('show').html(''); }

    function selectEmployee(emp) {
        $input.val(emp.employee_name || emp.full_name || emp.name);
        $clearBtn.addClass('show');
        hideDropdown();
        loadSSAForEmployee(emp.name, emp.employee_name || emp.full_name || emp.name);
    }

    function loadSSAForEmployee(empId, empName) {
        $result.html('<div class="ssa-result-empty"><div class="ssa-result-icon">⏳</div><div>Loading assignments…</div></div>');

        frappe.db.get_list('Salary Structure Assignment', {
            filters: { employee: empId, docstatus: ['!=', 2] },
            fields: ['name', 'from_date', 'to_date', 'salary_structure', 'docstatus',
                'gross_salary', 'net_salary', 'total_deductions', 'total_employer_contribution',
                'monthly_ctc', 'annual_ctc', 'company', 'designation'],
            order_by: 'from_date desc',
            limit: 20
        }).then(function (rows) {
            if (!rows.length) {
                $result.html(
                    '<div class="ssa-result-empty">' +
                    '<div class="ssa-result-icon">📭</div>' +
                    '<div>No salary structure assignments found for <strong>' + esc(empName) + '</strong></div>' +
                    '</div>'
                );
                return;
            }

            var STATUS_MAP = { 0: 'draft', 1: 'submitted', 2: 'cancelled' };
            var STATUS_LBL = { 0: 'Draft', 1: 'Submitted', 2: 'Cancelled' };

            var html = rows.map(function (r) {
                var cls = STATUS_MAP[r.docstatus] || 'draft';
                var lbl = STATUS_LBL[r.docstatus] || 'Draft';
                var date_range = r.from_date + ' → ' + (r.to_date || 'Ongoing');
                return `
                    <div class="ssa-result-card">
                        <div class="ssa-result-head">
                            <div class="ssa-result-name-block">
                                <div class="ssa-result-empname">${esc(r.salary_structure)}</div>
                                <div class="ssa-result-empid">${esc(date_range)}</div>
                            </div>
                            <div class="ssa-result-actions">
                                <span class="ssa-status-pill ${cls}">
                                    <span class="ssa-status-dot"></span>${lbl}
                                </span>
                                <a href="/app/salary-structure-assignment/${esc(r.name)}"
                                target="_blank" class="pp-btn-outline"
                                style="font-size:11px;height:24px;padding:0 10px;">Open ↗</a>
                            </div>
                        </div>
                        <div class="ssa-result-body">
                            <div class="ssa-result-row">
                                <div class="ssa-result-field">
                                    <span class="ssa-result-field-label">Gross Salary</span>
                                    <span class="ssa-result-field-val money">₹${fmt_inr(r.gross_salary)}</span>
                                </div>
                                <div class="ssa-result-field">
                                    <span class="ssa-result-field-label">Net Salary</span>
                                    <span class="ssa-result-field-val money">₹${fmt_inr(r.net_salary)}</span>
                                </div>
                                <div class="ssa-result-field">
                                    <span class="ssa-result-field-label">Deductions</span>
                                    <span class="ssa-result-field-val" style="color:var(--red-500,#e03131);font-weight:700;">₹${fmt_inr(r.total_deductions)}</span>
                                </div>
                                <div class="ssa-result-field">
                                    <span class="ssa-result-field-label">Monthly CTC</span>
                                    <span class="ssa-result-field-val" style="color:var(--blue-500,#5e64ff);font-weight:700;">₹${fmt_inr(r.monthly_ctc)}</span>
                                </div>
                                <div class="ssa-result-field">
                                    <span class="ssa-result-field-label">Annual CTC</span>
                                    <span class="ssa-result-field-val">₹${fmt_inr(r.annual_ctc)}</span>
                                </div>
                                <div class="ssa-result-field">
                                    <span class="ssa-result-field-label">Employer Contrib.</span>
                                    <span class="ssa-result-field-val">₹${fmt_inr(r.total_employer_contribution)}</span>
                                </div>
                            </div>
                        </div>
                    </div>`;
            }).join('');

            $result.html(html);
        });
    }

    // Input handler
    $input.on('input', function () {
        var term = $(this).val().trim();
        $clearBtn.toggleClass('show', term.length > 0);
        if (!term) { hideDropdown(); return; }

        clearTimeout(debounceT);
        debounceT = setTimeout(function () {
            frappe.call({
                method: 'saral_hr.saral_hr.page.mark_attendance.mark_attendance.search_employees',
                args: { query: term },
                freeze: false,
                callback: function (r) {
                    var emps = (r.message || []).map(function (e) {
                        return { name: e.name, employee_name: e.full_name || e.name };
                    });
                    if (emps.length) {
                        showDropdown(emps, term);
                    } else {
                        // Fallback: search Company Link directly
                        frappe.db.get_list('Company Link', {
                            filters: [['full_name', 'like', '%' + term + '%'], ['is_active', '=', 1]],
                            fields: ['name', 'full_name'],
                            limit: 10
                        }).then(function (rows) {
                            showDropdown(rows.map(function (r) {
                                return { name: r.name, employee_name: r.full_name };
                            }), term);
                        });
                    }
                },
                error: function () {
                    frappe.db.get_list('Company Link', {
                        filters: [['full_name', 'like', '%' + term + '%'], ['is_active', '=', 1]],
                        fields: ['name', 'full_name'],
                        limit: 10
                    }).then(function (rows) {
                        showDropdown(rows.map(function (r) {
                            return { name: r.name, employee_name: r.full_name };
                        }), term);
                    });
                }
            });
        }, 250);
    });

    // Keyboard nav
    $input.on('keydown', function (e) {
        var $opts = $dropdown.find('.ssa-emp-opt');
        if (!$dropdown.hasClass('show') || !$opts.length) return;
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            focusedIdx = Math.min(focusedIdx + 1, $opts.length - 1);
            $opts.removeClass('focused').eq(focusedIdx).addClass('focused');
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            focusedIdx = Math.max(focusedIdx - 1, 0);
            $opts.removeClass('focused').eq(focusedIdx).addClass('focused');
        } else if (e.key === 'Enter' && focusedIdx >= 0) {
            $opts.eq(focusedIdx).trigger('click');
        } else if (e.key === 'Escape') {
            hideDropdown();
        }
    });

    // Clear
    $clearBtn.on('click', function () {
        $input.val('');
        $clearBtn.removeClass('show');
        hideDropdown();
        $result.html(
            '<div class="ssa-result-empty">' +
            '<div class="ssa-result-icon">👤</div>' +
            '<div>Search for an employee to view their salary structure assignments</div>' +
            '</div>'
        );
    });

    // Close on outside click
    $(document).on('click.ssa-search', function (e) {
        if (!$input[0].contains(e.target) && !$dropdown[0].contains(e.target)) {
            hideDropdown();
        }
    });
}

// ── SSA Export ────────────────────────────────────────────────────────────────
function _init_ssa_export($root) {
    var selectedStatus = '';
    var $loading = $root.find('#ssa-export-loading');
    var $loadingText = $root.find('#ssa-export-loading-text');

    // Status filter chips
    $root.find('.ssa-filter-chip').on('click', function () {
        $root.find('.ssa-filter-chip').removeClass('active');
        $(this).addClass('active');
        selectedStatus = $(this).data('status');
    });

    // XLSX export
    $root.find('#ssa-export-xlsx').on('click', function () {
        $loading.addClass('show');
        $loadingText.text('Generating Excel file…');

        frappe.call({
            method: 'saral_hr.saral_hr.page.salary_insight.salary_insight.export_ssa_to_excel',
            args: { status_filter: selectedStatus },
            callback: function (r) {
                $loading.removeClass('show');
                if (r.message && r.message.file_url) {
                    frappe.show_alert({ message: r.message.rows + ' records exported.', indicator: 'green' });

                    // ✅ Replace window.open with this
                    var a = document.createElement('a');
                    a.href = r.message.file_url;
                    a.download = 'ssa_export.xlsx';
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);

                } else {
                    frappe.show_alert({ message: 'Export failed.', indicator: 'red' });
                }
            },
            error: function () {
                $loading.removeClass('show');
                frappe.show_alert({ message: 'Export failed. Please try again.', indicator: 'red' });
            }
        });
    });

    // CSV export (client-side, fetches data then builds CSV)
    $root.find('#ssa-export-csv-btn').on('click', function () {
        $loading.addClass('show');
        $loadingText.text('Fetching data for CSV…');

        var filters = { docstatus: ['!=', 2] };
        if (selectedStatus !== '') filters.docstatus = parseInt(selectedStatus);

        frappe.db.get_list('Salary Structure Assignment', {
            filters: filters,
            fields: ['name', 'employee', 'employee_name', 'company', 'from_date', 'to_date',
                'salary_structure', 'designation', 'branch', 'department', 'currency',
                'gross_salary', 'total_deductions', 'total_employer_contribution',
                'monthly_ctc', 'net_salary', 'annual_ctc', 'docstatus'],
            limit: 5000,
            order_by: 'from_date desc'
        }).then(function (rows) {
            $loading.removeClass('show');
            if (!rows.length) { frappe.msgprint('No records found.'); return; }

            var STATUS = { 0: 'Draft', 1: 'Submitted', 2: 'Cancelled' };
            var headers = ['ID', 'Employee', 'Employee Name', 'Company', 'From Date', 'To Date',
                'Salary Structure', 'Designation', 'Branch', 'Department', 'Currency',
                'Gross Salary', 'Total Deductions', 'Employer Contribution',
                'Monthly CTC', 'Net Salary', 'Annual CTC', 'Status'];
            var csv_rows = rows.map(function (r) {
                return [
                    r.name, r.employee, r.employee_name, r.company,
                    r.from_date || '', r.to_date || '', r.salary_structure,
                    r.designation || '', r.branch || '', r.department || '', r.currency || 'INR',
                    r.gross_salary || 0, r.total_deductions || 0, r.total_employer_contribution || 0,
                    r.monthly_ctc || 0, r.net_salary || 0, r.annual_ctc || 0,
                    STATUS[r.docstatus] || ''
                ].map(function (v) { return '"' + String(v).replace(/"/g, '""') + '"'; }).join(',');
            });

            var csv = [headers.join(',')].concat(csv_rows).join('\n');
            var blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
            var url = URL.createObjectURL(blob);
            var a = document.createElement('a');
            a.href = url;
            a.download = 'salary_structure_assignments_' + new Date().toISOString().slice(0, 10) + '.csv';
            document.body.appendChild(a); a.click();
            document.body.removeChild(a); URL.revokeObjectURL(url);
            frappe.show_alert({ message: rows.length + ' records exported.', indicator: 'green' });
        });
    });
}

// ─── Load data (payroll tab) ──────────────────────────────────────────────────
function load_dashboard($main) {
    var company = $main.find('#pp-company').val();
    var year = $main.find('#pp-year').val();
    var month = $main.find('#pp-month').val();
    if (!company || !year || !month) return;

    localStorage.setItem('si_company', company);
    localStorage.setItem('si_year', year);
    localStorage.setItem('si_month', month);

    $main.find('#pp-period-label').text(month + ' ' + year);

    $main.find('#pp-body').html(
        "<div class='pp-loading'>" + frappe.utils.icon('loading', 'xs') + " &nbsp;Loading " + month + " " + year + "...</div>"
    );

    frappe.call({
        method: 'saral_hr.saral_hr.page.salary_insight.salary_insight.get_salary_insight_data',
        args: { company: company, year: year, month: month },
        callback: function (r) {
            if (r.message) {
                render_dashboard($main, r.message, month, year, company);
            } else {
                $main.find('#pp-body').html("<div class='pp-loading'>No data found.</div>");
            }
        },
        error: function () {
            $main.find('#pp-body').html("<div class='pp-loading'>⚠️ Failed to load data. Please try again.</div>");
        }
    });
}

// ─── Render payroll dashboard ─────────────────────────────────────────────────
function render_dashboard($main, d, month, year, company) {
    var slips = d.salary_slips || [];
    var categories = d.category_summary || [];
    var totals = d.totals || {};
    var prev_totals = d.prev_totals || {};
    var active_emps = d.total_active_employees || 0;
    var pending_emps = d.pending_employees || [];
    var trend = d.trend || [];

    $main.data('slips', slips);
    $main.data('company', company);

    var submitted = slips.filter(function (s) { return s.docstatus === 1; });
    var drafts = slips.filter(function (s) { return s.docstatus === 0; });
    var cancelled = slips.filter(function (s) { return s.docstatus === 2; });
    var generated = submitted.length + drafts.length + cancelled.length;
    var pending = Math.max(0, active_emps - generated);
    var avg_net = submitted.length ? Math.round((totals.total_net || 0) / submitted.length) : 0;

    var html = '';

    // KPI Strip
    html += '<div class="pp-kpi-strip">';
    html += pp_kpi('k-total', '👥', active_emps, 'Active Employees', null);
    html += pp_kpi('k-generated', '📋', generated, 'Slips Generated', null);
    html += pp_kpi('k-submitted', '✅', submitted.length, 'Submitted', submitted.length ? '₹' + fmt_inr(avg_net) + ' avg net' : null);
    html += pp_kpi('k-draft', '✏️', drafts.length, 'Draft', null);
    html += pp_kpi('k-pending', '⏳', pending, 'No Slip Yet', pending ? '<a href="#pp-pending-section" style="color:inherit;text-decoration:underline;">View list</a>' : null);
    html += pp_kpi('k-cancelled', '❌', cancelled.length, 'Cancelled', null);
    html += '</div>';

    // Money totals
    html += '<div class="pp-card" style="padding:0;overflow:hidden;margin-bottom:16px;">';
    html += '<div style="padding:14px 20px 10px;border-bottom:1px solid var(--border-color);display:flex;align-items:center;justify-content:space-between;">';
    html += '<span style="font-size:13px;font-weight:600;">Payroll Financials</span>';
    html += '<span style="font-size:11px;color:var(--text-muted);">submitted slips only · ' + month + ' ' + year + '</span>';
    html += '</div>';
    html += '<div class="pp-totals-grid">';
    html += pp_total('Gross Payout', totals.total_earnings || 0, 'green', prev_totals.total_earnings);
    html += pp_total('Total Deductions', totals.total_deductions || 0, 'red', prev_totals.total_deductions);
    html += pp_total('Net Payable', totals.total_net || 0, 'orange', prev_totals.total_net);
    html += pp_total('Employer Contrib.', totals.total_employer_contribution || 0, 'blue', prev_totals.total_employer_contribution);
    html += pp_total('Avg. Net Salary', avg_net, 'purple', null);
    html += '</div></div>';

    // Trend
    if (trend && trend.length > 1) {
        html += '<div class="pp-card" style="margin-bottom:16px;">';
        html += '<div class="pp-section-heading">Net Payroll Trend <span class="pp-muted">last ' + trend.length + ' months</span></div>';
        html += render_trend(trend, month, year);
        html += '</div>';
    }

    // Category + donut
    html += '<div class="pp-grid-2">';
    html += '<div class="pp-card">';
    html += '<div class="pp-section-heading">Category Breakdown <span class="pp-muted">₹ net payroll</span></div>';
    if (categories.length) {
        var max_amt = Math.max.apply(null, categories.map(function (c) { return c.net_amount || 0; }));
        var COLORS = ['#5e64ff', '#28a745', '#f0a500', '#e03131', '#7c3aed', '#0891b2', '#db2777'];
        categories.forEach(function (cat, i) {
            var col = COLORS[i % COLORS.length];
            var amt_pct = max_amt > 0 ? (cat.net_amount / max_amt * 100) : 0;
            var sub_pct = cat.total > 0 ? (cat.submitted / cat.total * 100) : 0;
            html += '<div class="pp-bar-row">';
            html += '<div class="pp-bar-label" title="' + pp_esc(cat.category || '') + '">' + pp_esc(cat.category || 'Uncat.') + '</div>';
            html += '<div style="flex:1;display:flex;flex-direction:column;gap:3px;">';
            html += '<div class="pp-bar-track"><div class="pp-bar-fill" data-w="' + amt_pct.toFixed(2) + '" style="width:0%;background:' + col + '"></div></div>';
            html += '<div class="pp-bar-track" style="height:4px;opacity:0.6"><div class="pp-bar-fill" data-w="' + sub_pct.toFixed(2) + '" style="width:0%;background:#28a745"></div></div>';
            html += '</div>';
            html += '<div class="pp-bar-counts">₹' + fmt_inr(cat.net_amount || 0) + '<br><span style="color:var(--text-muted);font-size:10px;">' + cat.submitted + '/' + cat.total + '</span></div>';
            html += '</div>';
        });
    } else {
        html += '<div style="color:var(--text-muted);font-size:12px;text-align:center;padding:20px 0;">No category data.</div>';
    }
    html += '</div>';

    html += '<div class="pp-card">';
    html += '<div class="pp-section-heading">Status Overview <span class="pp-muted">by count</span></div>';
    html += render_donut(submitted.length, drafts.length, pending, cancelled.length);
    html += '</div>';
    html += '</div>';

    // Top / bottom earners
    if (submitted.length >= 2) {
        var sorted_net = submitted.slice().sort(function (a, b) { return (b.net_salary || 0) - (a.net_salary || 0); });
        html += '<div class="pp-grid-2">';
        html += '<div class="pp-card">';
        html += '<div class="pp-section-heading">Top Earners <span class="pp-muted">net salary · submitted</span></div>';
        sorted_net.slice(0, 3).forEach(function (s) {
            html += '<div class="pp-highlight-row top"><div><div class="pp-highlight-name">' + pp_esc(s.employee_name || s.employee) + '</div><div class="pp-highlight-meta">' + pp_esc([s.category, s.department].filter(Boolean).join(' · ')) + '</div></div><div class="pp-highlight-amt top">₹' + fmt_inr(s.net_salary) + '</div></div>';
        });
        html += '</div>';
        html += '<div class="pp-card">';
        html += '<div class="pp-section-heading">Lowest Earners <span class="pp-muted">net salary · submitted</span></div>';
        sorted_net.slice(-3).reverse().forEach(function (s) {
            html += '<div class="pp-highlight-row bottom"><div><div class="pp-highlight-name">' + pp_esc(s.employee_name || s.employee) + '</div><div class="pp-highlight-meta">' + pp_esc([s.category, s.department].filter(Boolean).join(' · ')) + '</div></div><div class="pp-highlight-amt bottom">₹' + fmt_inr(s.net_salary) + '</div></div>';
        });
        html += '</div>';
        html += '</div>';
    }

    // Recent submitted + drafts
    html += '<div class="pp-grid-2">';
    html += '<div class="pp-card"><div class="pp-section-heading">Recent Submitted <span class="pp-muted">latest 8</span></div>';
    if (submitted.length) {
        submitted.slice(0, 8).forEach(function (s) {
            var meta = [s.category, s.department].filter(Boolean).join(' · ');
            html += '<div class="pp-activity-item"><div class="pp-activity-dot" style="background:#28a745"></div><div class="pp-activity-info"><div class="pp-activity-name">' + pp_esc(s.employee_name || s.employee) + '</div>' + (meta ? '<div class="pp-activity-meta">' + pp_esc(meta) + '</div>' : '') + '</div><div class="pp-activity-amt" style="color:var(--green-600,#16a34a);">₹' + fmt_inr(s.net_salary) + '</div></div>';
        });
    } else {
        html += '<div style="color:var(--text-muted);font-size:12px;padding:16px 0;text-align:center;">No submitted slips yet.</div>';
    }
    html += '</div>';

    html += '<div class="pp-card"><div class="pp-section-heading">Drafts Pending Submission <span class="pp-muted">' + drafts.length + ' slip(s)</span></div>';
    if (drafts.length) {
        drafts.slice(0, 8).forEach(function (s) {
            var meta = [s.category, s.department].filter(Boolean).join(' · ');
            html += '<div class="pp-activity-item"><div class="pp-activity-dot" style="background:#f0a500"></div><div class="pp-activity-info"><div class="pp-activity-name">' + pp_esc(s.employee_name || s.employee) + '</div>' + (meta ? '<div class="pp-activity-meta">' + pp_esc(meta) + '</div>' : '') + '</div><div class="pp-activity-amt" style="color:#f0a500;">₹' + fmt_inr(s.net_salary) + '</div></div>';
        });
    } else {
        html += '<div style="color:var(--text-muted);font-size:12px;padding:16px 0;text-align:center;">No drafts pending. 🎉</div>';
    }
    html += '</div></div>';

    // Pending employees
    html += '<div id="pp-pending-section">';
    if (pending_emps && pending_emps.length) {
        html += '<div class="pp-card" style="margin-bottom:16px;"><div class="pp-section-heading" style="cursor:pointer;" id="pp-pending-toggle">⏳ Employees Without Salary Slip <span class="pp-muted">' + pending_emps.length + ' employee(s) — click to expand</span></div>';
        html += '<div id="pp-pending-list" style="display:none;">';
        pending_emps.forEach(function (e) {
            var meta = [e.category, e.department, e.designation].filter(Boolean).join(' · ');
            html += '<div class="pp-pending-emp"><div><div style="font-weight:600;font-size:12px;">' + pp_esc(e.employee_name || e.name) + '</div><div style="font-size:11px;color:var(--text-muted);">' + pp_esc(e.name) + (meta ? ' · ' + pp_esc(meta) : '') + '</div></div><a href="/app/salary-slip/new-salary-slip-1?employee=' + encodeURIComponent(e.name) + '" target="_blank" class="pp-btn-outline" style="font-size:11px;height:24px;padding:0 10px;">Generate</a></div>';
        });
        html += '</div></div>';
    }
    html += '</div>';

    // Full table
    html += '<div class="pp-card">';
    html += '<div class="pp-table-toolbar"><div class="pp-section-heading" style="margin:0;border:none;padding:0;">All Salary Slips <span class="pp-muted" id="pp-table-count">' + slips.length + ' records</span></div>';
    html += '<div class="pp-table-actions"><input type="text" class="pp-search-input" id="pp-emp-search" placeholder="Search name / ID..."><select class="pp-filter-select" id="pp-status-filter"><option value="">All Status</option><option value="1">Submitted</option><option value="0">Draft</option><option value="2">Cancelled</option></select></div></div>';
    html += '<div class="pp-table-wrap" id="pp-table-wrap"></div><div id="pp-pagination"></div>';
    html += '</div>';

    $main.find('#pp-body').html(html);

    setTimeout(function () {
        $main.find('.pp-bar-fill[data-w]').each(function () { $(this).css('width', $(this).attr('data-w') + '%'); });
        $main.find('.pp-trend-bar[data-h]').each(function () { $(this).css('height', $(this).attr('data-h') + '%'); });
    }, 60);

    $main.find('#pp-pending-toggle').on('click', function () { $main.find('#pp-pending-list').slideToggle(200); });

    var table_state = { q: '', status: '', sort_col: null, sort_dir: 1, page: 1, per_page: 20 };
    render_table_section($main, slips, table_state);
    // ADD THIS LINE — always render deduction table on load
    render_deduction_breakdown_table($main, slips);

    $main.find('#pp-emp-search').on('input', function () { table_state.q = $(this).val().toLowerCase().trim(); table_state.page = 1; render_table_section($main, slips, table_state); });
    $main.find('#pp-status-filter').on('change', function () { table_state.status = $(this).val(); table_state.page = 1; render_table_section($main, slips, table_state); });
    $main.find('#pp-table-wrap').on('click', 'th[data-col]', function () {
        var col = $(this).data('col');
        table_state.sort_col = col;
        table_state.sort_dir = table_state.sort_col === col ? table_state.sort_dir * -1 : 1;
        table_state.page = 1;
        render_table_section($main, slips, table_state);
    });
    $main.find('#pp-table-wrap').on('click', 'tbody tr[data-name]', function (e) {
        if ($(e.target).closest('.pp-ded-cell').length) return; // ← add this line
        var name = $(this).data('name');
        if (name) frappe.set_route('Form', 'Salary Slip', name);
    });
    // ← ADD THIS RIGHT HERE
    $main.find('#pp-table-wrap').on('click', '.pp-ded-cell', function () {
        var slip_name = $(this).data('name');
        show_deduction_breakdown($main, slip_name);
    });
}



function show_deduction_breakdown($main, slip_name) {
    var $existing = $main.find('#pp-ded-breakdown');
    if ($existing.length) {
        $existing[0].scrollIntoView({ behavior: 'smooth', block: 'start' });
        highlight_ded_row($main, slip_name);
        return;
    }
}

function highlight_ded_row($main, slip_name) {
    $main.find('#pp-ded-breakdown tr').css('background', '');
    var $r = $main.find('#pp-ded-breakdown tr[data-name="' + slip_name + '"]');
    $r.css('background', 'var(--yellow-highlight-color,#fff3cd)');
    setTimeout(function () { $r.css('background', ''); }, 2000);
}

function render_deduction_breakdown_table($main, slips) {
    var slip_names = slips.map(function (s) { return s.name; });

    $main.find('#pp-pagination').after(
        '<div id="pp-ded-breakdown" style="margin-top:24px;border-top:1px solid var(--border-color);padding-top:16px;">' +
        '<div class="pp-loading">⏳ Loading deduction breakdown...</div>' +
        '</div>'
    );

    frappe.call({
        method: 'saral_hr.saral_hr.page.salary_insight.salary_insight.get_all_slip_deductions',
        args: { slip_names: slip_names },
        callback: function (r) {
            if (!r.message) return;
            var all_data = r.message;

            function money(v) { return '₹' + fmt_inr(v || 0); }

            function formatAdditionalComponents(components) {
                if (!components || Object.keys(components).length === 0) return '—';
                var parts = [];
                for (var name in components) {
                    var amt = components[name];
                    if (amt > 0) {
                        parts.push(pp_esc(name) + ': ' + money(amt));
                    } else if (amt === 0) {
                        parts.push(pp_esc(name) + ': ₹0');
                    }
                }
                return parts.join('<br>');
            }

            function formatLoanDisplay(loan_info) {
                var loan_total = loan_info.total || 0;
                var loan_deferred = loan_info.deferred || false;

                if (loan_total <= 0) return '—';

                var html = '<span style="font-weight:700;color:#dc2626;">' + money(loan_total) + '</span>';

                if (loan_deferred) {
                    html += ' <span style="font-size:10px;color:#f59e0b;font-weight:600;">(Deferred)</span>';
                }

                return html;
            }

            function th(label, bg, color, align) {
                return '<th style="text-align:' + (align || 'right') + ';padding:8px 12px;' +
                    'border:1px solid var(--border-color);background:' + bg + ';' +
                    'color:' + color + ';white-space:nowrap;font-size:11px;font-weight:700;">' +
                    label + '</th>';
            }

            var header = '<tr>';
            header += th('Employee', 'var(--control-bg)', 'var(--text-color)', 'left');
            header += th('Net Salary<br><span style="font-size:10px;font-weight:400;">(Assignment)</span>', '#f0fdf4', '#14532d');
            header += th('Net Salary<br><span style="font-size:10px;font-weight:400;">(Salary Slip)</span>', '#fef2f2', '#991b1b');
            header += th('Working Days', '#dbeafe', '#1e40af', 'center');
            header += th('Absent', '#dbeafe', '#dc2626', 'center');
            header += th('Paid Days', '#dbeafe', '#15803d', 'center');
            header += th('🏦 Loan', '#ede9fe', '#4c1d95', 'center');
            header += th('📋 Retention', '#fef9c3', '#713f12');
            header += th('➕ Additional Salary', '#dcfce7', '#14532d');
            header += th('➖ Additional Deduction', '#fce7f3', '#9d174d');
            header += '</tr>';

            var rows_html = slips.map(function (s) {
                var d = all_data[s.name];
                if (!d) return '';

                var absent = d.absent_days || 0;
                var total_d = d.total_days || 0;
                var paid_d = d.paid_days || 0;

                function td(val, color, bold) {
                    return '<td style="text-align:right;padding:7px 10px;' +
                        'border-bottom:1px solid var(--border-color);' +
                        'color:' + (color || 'var(--text-color)') + ';' +
                        'font-weight:' + (bold ? '700' : '400') + ';">' + val + '</td>';
                }
                function tdC(val, color, bold) {
                    return '<td style="text-align:center;padding:7px 10px;' +
                        'border-bottom:1px solid var(--border-color);' +
                        'color:' + (color || 'var(--text-color)') + ';' +
                        'font-weight:' + (bold ? '700' : '400') + ';">' + val + '</td>';
                }

                var loan_info = d.loan || {};
                var loan_total = loan_info.total || 0;
                var loan_display = formatLoanDisplay(loan_info);

                var retention_total = d.retention || 0;
                var add_salary_html = formatAdditionalComponents(d.additional_salary);
                var add_deduction_html = formatAdditionalComponents(d.additional_deductions);

                var ssa_net = d.ssa_net || 0;
                var ss_net = d.ss_net || 0;

                var row = '<tr data-name="' + pp_esc(s.name) + '" style="cursor:pointer;">';

                row += '<td style="padding:8px 12px;border-bottom:1px solid var(--border-color);">' +
                    '<div class="pp-emp-name">' + pp_esc(d.employee_name || d.employee) + '</div>' +
                    '<div class="pp-emp-id">' + pp_esc(d.employee) + '</div></td>';

                // Net Salary (Assignment)
                row += '<td style="text-align:right;padding:7px 10px;border-bottom:1px solid var(--border-color);color:#15803d;font-weight:700;">' + money(ssa_net) + '</td>';

                // Net Salary (Salary Slip)
                row += '<td style="text-align:right;padding:7px 10px;border-bottom:1px solid var(--border-color);color:#dc2626;font-weight:700;">' + money(ss_net) + '</td>';

                row += tdC(total_d, 'var(--text-color)', false);
                row += tdC(absent, absent > 0 ? '#dc2626' : 'var(--text-muted)', absent > 0);
                row += tdC(paid_d, '#15803d', true);

                // Loan — centered, combined total only
                row += '<td style="text-align:center;padding:7px 10px;' +
                    'border-bottom:1px solid var(--border-color);' +
                    'vertical-align:middle;">' + loan_display + '</td>';

                row += td(
                    retention_total > 0 ? money(retention_total) : '—',
                    retention_total > 0 ? '#dc2626' : 'var(--text-muted)',
                    retention_total > 0
                );

                // Additional Salary
                row += '<td style="text-align:right;padding:7px 10px;border-bottom:1px solid var(--border-color);font-size:11px;">' + add_salary_html + '</td>';

                // Additional Deduction
                row += '<td style="text-align:right;padding:7px 10px;border-bottom:1px solid var(--border-color);font-size:11px;">' + add_deduction_html + '</td>';

                row += '</tr>';
                return row;
            }).join('');

            var html =
                '<div class="pp-table-toolbar" style="margin-bottom:12px;">' +
                '<div class="pp-section-heading" style="margin:0;border:none;padding:0;">📋 Deduction Breakdown — All Employees</div>' +
                '<div class="pp-table-actions">' +
                '<input type="text" class="pp-search-input" id="pp-ded-search" placeholder="Search name / ID...">' +
                '</div></div>' +
                '<div class="pp-table-wrap">' +
                '<table class="pp-table" style="font-size:12px;">' +
                '<thead>' + header + '</thead>' +
                '<tbody>' + rows_html + '</tbody>' +
                '</table></div>';

            $main.find('#pp-ded-breakdown').html(html);

            $main.find('#pp-ded-breakdown tbody tr').on('click', function () {
                frappe.set_route('Form', 'Salary Slip', $(this).data('name'));
            });

            $main.find('#pp-ded-search').on('input', function () {
                var q = $(this).val().toLowerCase().trim();
                $main.find('#pp-ded-breakdown tbody tr').each(function () {
                    var nm = $(this).find('.pp-emp-name').text().toLowerCase();
                    var id = $(this).find('.pp-emp-id').text().toLowerCase();
                    $(this).toggle(!q || nm.includes(q) || id.includes(q));
                });
            });
        }
    });
}
// ─── Table ────────────────────────────────────────────────────────────────────
function render_table_section($main, slips, state) {
    var filtered = slips.filter(function (s) {
        var q_ok = !state.q || (s.employee_name || '').toLowerCase().includes(state.q) || (s.employee || '').toLowerCase().includes(state.q);
        var st_ok = state.status === '' || String(s.docstatus) === String(state.status);
        return q_ok && st_ok;
    });

    if (state.sort_col) {
        var col = state.sort_col, dir = state.sort_dir;
        filtered = filtered.slice().sort(function (a, b) {
            var av = a[col], bv = b[col];
            if (typeof av === 'number') return dir * (av - bv);
            return dir * String(av || '').localeCompare(String(bv || ''));
        });
    }

    var total = filtered.length;
    var pages = Math.max(1, Math.ceil(total / state.per_page));
    state.page = Math.min(state.page, pages);
    var start = (state.page - 1) * state.per_page;
    var page_rows = filtered.slice(start, start + state.per_page);

    $main.find('#pp-table-count').text(total + ' records');

    var COL_DEFS = [
        { label: 'Employee', key: 'employee_name', sortable: true },
        { label: 'Category', key: 'category', sortable: true },
        { label: 'Department', key: 'department', sortable: true },
        { label: 'Designation', key: 'designation', sortable: true },
        { label: 'Pay Days', key: 'payment_days', sortable: true, align: 'center' },
        { label: 'Gross', key: 'total_earnings', sortable: true },
        { label: 'Deductions', key: 'total_deductions', sortable: true },
        { label: 'Net Salary', key: 'net_salary', sortable: true },
        { label: 'Status', key: 'docstatus', sortable: false }
    ];

    var head = '<thead><tr>' + COL_DEFS.map(function (c) {
        var sort_cls = state.sort_col === c.key ? (state.sort_dir === 1 ? 'sorted-asc' : 'sorted-desc') : '';
        var sort_icon = c.sortable ? '<span class="pp-sort-icon">' + (state.sort_col === c.key ? (state.sort_dir === 1 ? '▲' : '▼') : '⇅') + '</span>' : '';
        var align_sty = c.align ? 'style="text-align:' + c.align + '"' : '';
        return '<th ' + align_sty + ' class="' + sort_cls + '" ' + (c.sortable ? 'data-col="' + c.key + '"' : '') + '>' + c.label + sort_icon + '</th>';
    }).join('') + '</tr></thead>';

    var body;
    if (!page_rows.length) {
        body = '<tbody><tr><td colspan="' + COL_DEFS.length + '" class="pp-table-empty">No records match your filters.</td></tr></tbody>';
    } else {
        body = '<tbody>' + page_rows.map(function (s) {
            var lbl = s.docstatus === 1 ? 'Submitted' : s.docstatus === 0 ? 'Draft' : 'Cancelled';
            var cls = s.docstatus === 1 ? 'submitted' : s.docstatus === 0 ? 'draft' : 'cancelled';
            return '<tr data-name="' + pp_esc(s.name) + '">' +
                '<td><div class="pp-emp-name">' + pp_esc(s.employee_name || '-') + '</div><div class="pp-emp-id">' + pp_esc(s.employee || '') + '</div></td>' +
                '<td>' + pp_esc(s.category || '-') + '</td>' +
                '<td>' + pp_esc(s.department || '-') + '</td>' +
                '<td>' + pp_esc(s.designation || '-') + '</td>' +
                '<td style="text-align:center">' + (s.payment_days || 0) + '</td>' +
                '<td>₹' + fmt_inr(s.total_earnings) + '</td>' +
                '<td class="pp-ded-cell" data-name="' + pp_esc(s.name) + '" style="color:var(--red-500,#e03131);cursor:pointer;">₹' + fmt_inr(s.total_deductions) + '</td>' +
                '<td class="pp-net-sal">₹' + fmt_inr(s.net_salary) + '</td>' +
                '<td><span class="pp-badge ' + cls + '">' + lbl + '</span></td>' +
                '</tr>';
        }).join('') + '</tbody>';
    }

    $main.find('#pp-table-wrap').html('<table class="pp-table">' + head + body + '</table>');

    if (pages <= 1) {
        $main.find('#pp-pagination').html(total ? '<div style="font-size:12px;color:var(--text-muted);padding-top:10px;">Showing all ' + total + ' record' + (total !== 1 ? 's' : '') + '</div>' : '');
        return;
    }

    var pag = '<div class="pp-pagination"><span>Showing ' + (start + 1) + '–' + Math.min(start + state.per_page, total) + ' of ' + total + '</span><div class="pp-page-btns">';
    pag += '<button class="pp-page-btn" id="pp-prev-page" ' + (state.page <= 1 ? 'disabled' : '') + '>‹</button>';
    for (var pg = Math.max(1, state.page - 2); pg <= Math.min(pages, state.page + 2); pg++) {
        pag += '<button class="pp-page-btn' + (pg === state.page ? ' active' : '') + '" data-page="' + pg + '">' + pg + '</button>';
    }
    pag += '<button class="pp-page-btn" id="pp-next-page" ' + (state.page >= pages ? 'disabled' : '') + '>›</button>';
    pag += '</div></div>';
    $main.find('#pp-pagination').html(pag);

    $main.find('#pp-prev-page').on('click', function () { if (state.page > 1) { state.page--; render_table_section($main, slips, state); } });
    $main.find('#pp-next-page').on('click', function () { if (state.page < pages) { state.page++; render_table_section($main, slips, state); } });
    $main.find('.pp-page-btn[data-page]').on('click', function () { state.page = parseInt($(this).data('page')); render_table_section($main, slips, state); });
}

// ─── Export CSV (payroll tab) ─────────────────────────────────────────────────
function export_csv($main) {
    var slips = $main.data('slips') || [];
    if (!slips.length) { frappe.msgprint('No data to export.'); return; }
    var month = $main.find('#pp-month').val();
    var year = $main.find('#pp-year').val();
    var headers = ['Employee ID', 'Employee Name', 'Category', 'Department', 'Designation', 'Pay Days', 'Gross', 'Deductions', 'Net Salary', 'Employer Contrib', 'Status'];
    var STATUS = { 0: 'Draft', 1: 'Submitted', 2: 'Cancelled' };
    var rows = slips.map(function (s) {
        return [s.employee, s.employee_name, s.category || '', s.department || '', s.designation || '',
        s.payment_days || 0, s.total_earnings || 0, s.total_deductions || 0,
        s.net_salary || 0, s.total_employer_contribution || 0, STATUS[s.docstatus] || '']
            .map(function (v) { return '"' + String(v).replace(/"/g, '""') + '"'; }).join(',');
    });
    var csv = [headers.join(',')].concat(rows).join('\n');
    var blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url; a.download = 'salary_insight_' + month + '_' + year + '.csv';
    document.body.appendChild(a); a.click();
    document.body.removeChild(a); URL.revokeObjectURL(url);
}

// ─── Trend ────────────────────────────────────────────────────────────────────
function render_trend(trend, cur_month, cur_year) {
    var max_val = Math.max.apply(null, trend.map(function (t) { return t.net || 0; }));
    if (!max_val) return '<div style="color:var(--text-muted);font-size:12px;text-align:center;padding:20px 0;">No trend data.</div>';
    var html = '<div class="pp-trend-wrap"><div class="pp-trend-chart">';
    trend.forEach(function (t) {
        var pct = Math.round((t.net / max_val) * 100);
        var is_cur = (t.month === cur_month && String(t.year) === String(cur_year));
        html += '<div class="pp-trend-bar-wrap"><div class="pp-trend-val">₹' + fmt_inr_short(t.net) + '</div>';
        html += '<div class="pp-trend-bar' + (is_cur ? ' current' : '') + '" data-h="' + pct + '" style="height:0%;min-height:2px;" title="' + t.month + ' ' + t.year + ': ₹' + fmt_inr(t.net) + '"></div>';
        html += '<div class="pp-trend-label">' + t.month.slice(0, 3) + '<br>' + String(t.year).slice(2) + '</div></div>';
    });
    html += '</div></div>';
    return html;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
function pp_kpi(cls, icon, val, label, sub) {
    return '<div class="pp-kpi ' + cls + '"><div class="pp-kpi-icon">' + icon + '</div><div class="pp-kpi-val">' + val + '</div><div class="pp-kpi-label">' + label + '</div>' + (sub ? '<div class="pp-kpi-sub">' + sub + '</div>' : '') + ' </div>';
}

function pp_total(label, val, color_cls, prev_val) {
    var change_html = '';
    if (prev_val && prev_val > 0) {
        var diff = ((val - prev_val) / prev_val * 100).toFixed(1);
        var dir = diff >= 0 ? 'up' : 'down';
        change_html = '<div class="pp-total-change ' + dir + '">' + (diff >= 0 ? '▲' : '▼') + ' ' + Math.abs(diff) + '% vs prev month</div>';
    }
    return '<div class="pp-total-item"><div class="pp-total-label">' + label + '</div><div class="pp-total-val ' + color_cls + '">₹' + fmt_inr(val) + '</div>' + change_html + '</div>';
}

function render_donut(submitted, draft, pending, cancelled) {
    var ITEMS = [
        { label: 'Submitted', val: submitted, color: '#28a745' },
        { label: 'Draft', val: draft, color: '#f0a500' },
        { label: 'Pending', val: pending, color: '#e03131' },
        { label: 'Cancelled', val: cancelled, color: '#adb5bd' },
    ];
    var total = submitted + draft + pending + cancelled;
    if (!total) return '<div style="color:var(--text-muted);font-size:12px;text-align:center;padding:24px 0;">No data for this period.</div>';
    var r = 52, cx = 68, cy = 68, sw = 14, circ = 2 * Math.PI * r, offset = 0, arcs = '';
    ITEMS.forEach(function (item) {
        if (!item.val) return;
        var dash = (item.val / total) * circ;
        arcs += '<circle cx="' + cx + '" cy="' + cy + '" r="' + r + '" fill="none" stroke="' + item.color + '" stroke-width="' + sw + '" stroke-dasharray="' + dash + ' ' + (circ - dash) + '" stroke-dashoffset="-' + offset + '" transform="rotate(-90 ' + cx + ' ' + cy + ')" />';
        offset += dash;
    });
    var legend = ITEMS.map(function (item) {
        var pct = Math.round(item.val / total * 100);
        return '<div class="pp-legend-row"><div class="pp-legend-dot" style="background:' + item.color + '"></div><span class="pp-legend-name">' + item.label + '</span><span class="pp-legend-count">' + item.val + '</span><span class="pp-legend-pct">' + pct + '%</span></div>';
    }).join('');
    return '<div class="pp-donut-wrap"><svg width="136" height="136" viewBox="0 0 136 136"><circle cx="' + cx + '" cy="' + cy + '" r="' + r + '" fill="none" stroke="var(--control-bg)" stroke-width="' + sw + '"/>' + arcs + '<text x="' + cx + '" y="' + (cy + 6) + '" text-anchor="middle" fill="var(--text-color)" font-size="22" font-weight="700" font-family="var(--font-stack)">' + total + '</text><text x="' + cx + '" y="' + (cy + 19) + '" text-anchor="middle" fill="var(--text-muted)" font-size="9" font-family="var(--font-stack)">employees</text></svg><div class="pp-donut-legend">' + legend + '</div></div>';
}

function fmt_inr(val) {
    if (!val) return '0';
    return Number(val).toLocaleString('en-IN', { maximumFractionDigits: 0 });
}
function fmt_inr_short(val) {
    if (!val) return '0';
    val = Number(val);
    if (val >= 10000000) return (val / 10000000).toFixed(1) + 'Cr';
    if (val >= 100000) return (val / 100000).toFixed(1) + 'L';
    if (val >= 1000) return (val / 1000).toFixed(1) + 'K';
    return val.toLocaleString('en-IN', { maximumFractionDigits: 0 });
}
function pp_esc(str) {
    if (!str) return '';
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}