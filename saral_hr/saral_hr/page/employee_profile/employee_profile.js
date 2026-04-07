frappe.pages["employee-profile"].on_page_load = function (wrapper) {
    frappe.ui.make_app_page({ parent: wrapper, title: "Employee Profile" });
    inject_ep_styles();
};

frappe.pages["employee-profile"].on_page_show = function (wrapper) {
    var route = frappe.get_route();
    var emp = route[1];
    if (!emp) { return; }

    var $sidebar = $(wrapper).find(".layout-side-section");
    var $main = $(wrapper).find(".layout-main-section");

    $main.html(render_skeleton());

    frappe.call({
        method: "saral_hr.saral_hr.page.employee_profile.employee_profile.get_employee_profile_data",
        args: { employee: emp },
        callback: function (r) {
            if (r.message) {
                ep_fix_breadcrumbs(r.message.employee || emp);
                $(wrapper).find(".title-text").text(r.message.employee || "Employee Profile");
                render_profile($sidebar, $main, r.message, emp);
            } else {
                render_error($main, "No data returned for this employee.");
            }
        },
        error: function () {
            render_error($main, "Failed to load employee profile. Please try again.");
        }
    });
};

function render_skeleton() {
    var pulse = "animation:ep-pulse 1.5s ease-in-out infinite;";
    var box = function (w, h, r) {
        return "<div style='background:#e5e7eb;border-radius:" + (r || "6px") + ";width:" + w + ";height:" + h + ";margin-bottom:10px;" + pulse + "'></div>";
    };
    var html = "<div style='padding:20px;'>";
    html += "<div style='background:#fff;border:1px solid #f3f4f6;border-radius:8px;padding:20px;margin-bottom:15px;'>";
    html += box("120px", "14px") + "<div style='display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;'>";
    for (var i = 0; i < 6; i++) html += "<div>" + box("60px", "10px") + box("80px", "18px", "4px") + "</div>";
    html += "</div></div>";
    html += "<div style='background:#fff;border:1px solid #f3f4f6;border-radius:8px;padding:20px;margin-bottom:15px;'>";
    html += box("160px", "14px") + box("100%", "120px", "6px");
    html += "</div>";
    html += "<div style='background:#fff;border:1px solid #f3f4f6;border-radius:8px;padding:20px;'>";
    html += box("140px", "14px");
    for (var j = 0; j < 2; j++) html += "<div style='margin-left:40px;'>" + box("200px", "12px") + box("140px", "10px") + "</div>";
    html += "</div></div>";
    return html;
}

function render_error($main, msg) {
    $main.html(
        "<div style='margin:40px auto;max-width:400px;text-align:center;padding:32px;" +
        "background:#fff;border:1px solid #fecaca;border-radius:10px;'>" +
        "<div style='font-size:32px;margin-bottom:12px;'>⚠️</div>" +
        "<div style='font-size:15px;font-weight:600;color:#dc2626;margin-bottom:6px;'>Something went wrong</div>" +
        "<div style='font-size:13px;color:#6b7280;'>" + msg + "</div>" +
        "<button onclick='window.location.reload()' style='margin-top:16px;padding:7px 20px;" +
        "background:#1d4ed8;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:13px;'>Retry</button>" +
        "</div>"
    );
}

function ep_fix_breadcrumbs(emp_name) {
    var $nb = $("#navbar-breadcrumbs");
    if (!$nb.length) { return; }
    $nb.html(
        "<li><a href='/app/saral-hr'>Saral HR</a></li>" +
        "<li><a href='/app/employee'>Employee</a></li>" +
        "<li>" + emp_name + "</li>"
    );
}

function inject_ep_styles() {
    if (document.getElementById("ep-styles")) return;
    var style = document.createElement("style");
    style.id = "ep-styles";
    style.innerHTML = `
        @keyframes ep-pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }

        .ep-sidebar-inner { padding: 0 4px; }
        .ep-avatar {
            width:80px; height:80px; border-radius:50%;
            background:linear-gradient(135deg,#667eea,#764ba2);
            display:flex; align-items:center; justify-content:center;
            font-size:30px; color:#fff; font-weight:700; margin:0 auto 8px;
        }
        .ep-avatar img { width:80px; height:80px; border-radius:50%; object-fit:cover; }
        .ep-emp-id   { text-align:center; font-size:11px; color:var(--text-muted); margin-bottom:3px;
                       font-family:monospace; letter-spacing:0.05em;
                       background:var(--control-bg,#f3f4f6); border-radius:4px; padding:2px 6px;
                       display:inline-block; width:100%; box-sizing:border-box; }
        .ep-name     { text-align:center; font-size:15px; font-weight:700; color:var(--text-color); margin-bottom:3px; }
        .ep-dob-row  { font-size:11px; color:var(--text-muted); text-align:center; margin-bottom:5px; }
        .ep-contact-row { display:flex; align-items:center; gap:6px; font-size:12px; color:var(--text-muted); margin-bottom:4px; }
        .ep-contact-row a { color:var(--blue-500,#1d4ed8); text-decoration:none; font-size:12px; }
        .ep-contact-row a:hover { text-decoration:underline; }
        .ep-divider { border:none; border-top:1px solid var(--border-color,#f3f4f6); margin:10px 0; }
        .ep-info-row   { margin-bottom:7px; font-size:12px; }
        .ep-info-label { color:var(--text-muted); font-size:10px; text-transform:uppercase; letter-spacing:0.04em; }
        .ep-info-val   { color:var(--text-color); font-weight:500; }
        .ep-link-btn {
            display:block; width:100%; text-align:left; padding:5px 0; font-size:12px;
            color:var(--blue-500,#1d4ed8); text-decoration:none;
            background:none; border:none; cursor:pointer; transition:color 0.15s;
        }
        .ep-link-btn:hover { color:#1e40af; text-decoration:underline; }

        .ep-card { background:var(--card-bg,#fff); border:1px solid var(--border-color,#f3f4f6); border-radius:8px; padding:20px; margin-bottom:15px; }
        .ep-title-area { display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; flex-wrap:wrap; gap:8px; }
        .ep-card-title { font-size:15px; font-weight:600; color:var(--text-color); margin:0; }

        .ep-salary-grid { display:grid; grid-template-columns:1fr 1fr 1fr; gap:0; }
        .ep-salary-item { padding:14px 16px; }
        .ep-salary-item-label { font-size:11px; color:var(--text-muted); margin-bottom:4px; text-transform:uppercase; letter-spacing:0.04em; }
        .ep-salary-item-val   { font-size:15px; font-weight:600; color:var(--text-color); }
        .ep-salary-structure-tag {
            display:inline-flex; align-items:center; gap:6px;
            background:#eff6ff; border:1px solid #bfdbfe;
            border-radius:20px; padding:3px 12px; font-size:11px; color:#1d4ed8; font-weight:500;
        }
        .ep-hike-banner {
            display:flex; align-items:center; gap:10px; flex-wrap:wrap;
            background:#f0fdf4; border:1px solid #86efac;
            border-radius:8px; padding:10px 14px; margin-top:14px;
        }
        .ep-hike-label { font-size:11px; color:#166534; font-weight:600; text-transform:uppercase; letter-spacing:0.04em; }
        .ep-hike-val   { font-size:15px; font-weight:700; color:#15803d; }
        .ep-hike-pct   { font-size:12px; color:#166534; background:#bbf7d0; border-radius:10px; padding:2px 8px; font-weight:600; }
        .ep-hike-from  { font-size:11px; color:#6b7280; }

        .ep-year-select {
            padding:3px 10px; border-radius:6px;
            border:1px solid var(--border-color,#e5e7eb);
            background:var(--card-bg,#fff); font-size:12px;
            cursor:pointer; color:var(--text-color); outline:none;
        }
        .ep-year-select:focus { border-color:#1d4ed8; }
        .ep-today-btn {
            padding:3px 10px; border-radius:6px; font-size:12px; font-weight:600;
            border:1px solid #bfdbfe; background:#eff6ff; color:#1d4ed8;
            cursor:pointer; transition:background 0.15s;
        }
        .ep-today-btn:hover { background:#dbeafe; }

        .ep-heatmap-scroll { overflow-x:auto; padding-bottom:6px; }
        .ep-heatmap-inner  { display:flex; align-items:flex-start; min-width:max-content; gap:4px; }
        .ep-month-col      { display:flex; flex-direction:column; }
        .ep-month-label-btn {
            font-size:10px; font-weight:600; text-transform:uppercase;
            letter-spacing:0.04em; margin-bottom:4px; text-align:center;
            background:none; border:none; cursor:pointer;
            color:var(--text-muted); padding:2px 4px; border-radius:4px;
            width:100%; transition:all 0.15s;
        }
        .ep-month-label-btn:hover { color:#1d4ed8; }
        .ep-month-label-btn.active { background:#1d4ed8; color:#fff; }
        .ep-month-weeks { display:flex; gap:2px; }
        .ep-week-col    { display:flex; flex-direction:column; gap:2px; }

        .ep-day {
            width:22px; height:22px; border-radius:4px;
            cursor:default; flex-shrink:0;
            display:flex; align-items:center; justify-content:center;
            font-size:9px; font-weight:600; line-height:1;
            box-sizing:border-box; transition:transform 0.1s, box-shadow 0.1s;
        }
        .ep-day:not(.empty):not(.future):hover { transform:scale(1.3); z-index:10; box-shadow:0 4px 12px rgba(0,0,0,0.2) !important; }
        .ep-day.empty      { background:transparent; }
        .ep-day.future     { background:#f3f4f6; color:#9ca3af; border:1.5px solid #e5e7eb; }
        .ep-day.present    { background:#bbf7d0; color:#14532d; border:2px solid #16a34a;  box-shadow:inset 0 0 0 2px #86efac; }
        .ep-day.absent     { background:#fecaca; color:#7f1d1d; border:2px solid #dc2626;  box-shadow:inset 0 0 0 2px #fca5a5; }
        .ep-day.halfday    { background:#fef9c3; color:#713f12; border:2px solid #ca8a04;  box-shadow:inset 0 0 0 2px #fde047; }
        .ep-day.lwp        { background:#fed7aa; color:#7c2d12; border:2px solid #ea580c;  box-shadow:inset 0 0 0 2px #fdba74; }
        .ep-day.holiday    { background:#bfdbfe; color:#1e3a8a; border:2px solid #2563eb;  box-shadow:inset 0 0 0 2px #93c5fd; }
        .ep-day.weeklyoff  { background:#e9d5ff; color:#4c1d95; border:2px solid #9333ea;  box-shadow:inset 0 0 0 2px #d8b4fe; }
        .ep-day.earnedleave  { background:#99f6e4; color:#134e4a; border:2px solid #0d9488; box-shadow:inset 0 0 0 2px #5eead4; }
        .ep-day.casualleave  { background:#fbcfe8; color:#831843; border:2px solid #db2777; box-shadow:inset 0 0 0 2px #f9a8d4; }
        .ep-day.ontour     { background:#bbf7d0; color:#14532d; border:2px solid #16a34a;  box-shadow:inset 0 0 0 2px #86efac; }
        .ep-day.compoff    { background:#e9d5ff; color:#4c1d95; border:2px solid #9333ea;  box-shadow:inset 0 0 0 2px #d8b4fe; }
        .ep-day.earnedcompoff { background:#ccfbf1; color:#134e4a; border:2px solid #14b8a6; box-shadow:inset 0 0 0 2px #5eead4; }

        .ep-tooltip {
            position:fixed; z-index:9999; pointer-events:none;
            background:#1e293b; color:#f8fafc;
            border-radius:6px; padding:7px 11px;
            font-size:11px; line-height:1.6;
            box-shadow:0 4px 16px rgba(0,0,0,0.22);
            white-space:nowrap; opacity:0; transition:opacity 0.12s;
        }
        .ep-tooltip.visible { opacity:1; }
        .ep-tooltip-date { font-weight:700; }
        .ep-tooltip-dot  { display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:5px; vertical-align:middle; }

        .ep-legend      { display:flex; gap:10px; flex-wrap:wrap; margin-top:12px; }
        .ep-legend-item { display:flex; align-items:center; gap:5px; font-size:11px; }
        .ep-legend-dot  { width:14px; height:14px; border-radius:3px; flex-shrink:0; border:1.5px solid transparent; }
        .ep-legend-dot.present     { background:#bbf7d0; border-color:#16a34a; }
        .ep-legend-dot.absent      { background:#fecaca; border-color:#dc2626; }
        .ep-legend-dot.halfday     { background:#fef9c3; border-color:#ca8a04; }
        .ep-legend-dot.lwp         { background:#fed7aa; border-color:#ea580c; }
        .ep-legend-dot.holiday     { background:#bfdbfe; border-color:#2563eb; }
        .ep-legend-dot.weeklyoff   { background:#e9d5ff; border-color:#9333ea; }
        .ep-legend-dot.earnedleave { background:#99f6e4; border-color:#0d9488; }
        .ep-legend-dot.casualleave { background:#fbcfe8; border-color:#db2777; }
        .ep-legend-dot.ontour      { background:#bbf7d0; border-color:#16a34a; }
        .ep-legend-dot.compoff     { background:#e9d5ff; border-color:#9333ea; }
        .ep-legend-dot.earnedcompoff { background:#ccfbf1; border-color:#14b8a6; }
        .ep-legend-dot.future      { background:#f3f4f6; border-color:#e5e7eb; }
        .ep-legend-label { font-weight:500; }
        .ep-legend-label.present     { color:#16a34a; }
        .ep-legend-label.absent      { color:#dc2626; }
        .ep-legend-label.halfday     { color:#ca8a04; }
        .ep-legend-label.lwp         { color:#ea580c; }
        .ep-legend-label.holiday     { color:#2563eb; }
        .ep-legend-label.weeklyoff   { color:#9333ea; }
        .ep-legend-label.earnedleave { color:#0d9488; }
        .ep-legend-label.casualleave { color:#db2777; }
        .ep-legend-label.ontour      { color:#16a34a; }
        .ep-legend-label.compoff     { color:#9333ea; }
        .ep-legend-label.earnedcompoff { color:#0d9488; }
        .ep-legend-label.future      { color:#9ca3af; }

        .ep-att-summary { display:grid; grid-template-columns:repeat(6,1fr); gap:8px; margin-top:14px; }
        .ep-att-box     { background:var(--control-bg,#f9fafb); border-radius:6px; padding:10px 6px; text-align:center; }
        .ep-att-val     { font-size:18px; font-weight:700; }
        .ep-att-label   { font-size:10px; color:var(--text-muted); margin-top:2px; }
        .ep-att-pct     { font-size:10px; font-weight:600; margin-top:1px; }

        .ep-timeline-ssa-wrap { display:grid; grid-template-columns:1fr 1fr; gap:20px; align-items:start; }
        @media (max-width:900px) {
            .ep-timeline-ssa-wrap { grid-template-columns:1fr; }
            .ep-att-summary { grid-template-columns:repeat(3,1fr); }
            .ep-salary-grid { grid-template-columns:1fr 1fr; }
        }

        .ep-timeline-scroll { max-height:480px; overflow-y:auto; padding-right:4px; }
        .ep-timeline-scroll::-webkit-scrollbar { width:4px; }
        .ep-timeline-scroll::-webkit-scrollbar-thumb { background:#d1d5db; border-radius:2px; }
        .ep-timeline {
            position:relative; padding-left:40px;
            border-left:2px solid var(--border-color,#d1d8dd);
            margin-left:6px; padding-top:4px;
        }
        .ep-timeline-item { position:relative; padding-bottom:18px; }
        .ep-timeline-item:last-child { padding-bottom:0; }
        .ep-tl-dot {
            position:absolute; left:-47px; top:16px;
            width:12px; height:12px; border-radius:50%;
            background:var(--gray-400,#adb5bd);
            border:2px solid white;
            box-shadow:0 0 0 2px var(--gray-400,#adb5bd); z-index:1;
        }
        .ep-timeline-item.tl-active .ep-tl-dot { background:#22c55e; box-shadow:0 0 0 2px #22c55e; }
        .ep-tl-card { border:1px solid var(--border-color,#e5e7eb); border-radius:6px; padding:12px 14px; }
        .ep-timeline-item.tl-active .ep-tl-card { border-color:#86efac; border-left:4px solid #22c55e; background:#f0fdf4; }
        .ep-tl-company { font-size:14px; font-weight:600; color:var(--text-color); margin-bottom:4px; }
        .ep-tl-date    { font-size:12px; color:var(--text-muted); margin-bottom:2px; }
        .ep-tl-meta    { font-size:11px; color:var(--text-muted); margin-bottom:2px; }
        .ep-tl-duration {
            display:inline-block; margin-top:6px;
            font-size:11px; font-weight:600;
            background:var(--control-bg,#f3f4f6); color:var(--text-muted);
            border-radius:10px; padding:2px 9px;
        }
        .ep-timeline-item.tl-active .ep-tl-duration { background:#bbf7d0; color:#166534; }
        .ep-timeline-empty { font-size:13px; color:var(--text-muted); text-align:center; padding:20px; }

        .ep-ssa-panel { display:flex; flex-direction:column; gap:12px; }
        .ep-ssa-current { background:var(--card-bg,#fff); border:1.5px solid #22c55e; border-radius:8px; overflow:hidden; }
        .ep-ssa-current-header { background:linear-gradient(135deg,#dcfce7,#bbf7d0); padding:10px 14px; display:flex; justify-content:space-between; align-items:center; }
        .ep-ssa-current-title { font-size:12px; font-weight:700; color:#14532d; text-transform:uppercase; letter-spacing:0.05em; }
        .ep-ssa-current-link { font-size:11px; font-weight:600; color:#15803d; text-decoration:none; background:rgba(255,255,255,0.7); padding:2px 8px; border-radius:10px; transition:background 0.15s; }
        .ep-ssa-current-link:hover { background:#fff; text-decoration:none; }
        .ep-ssa-current-body { padding:12px 14px; }
        .ep-ssa-since { font-size:11px; color:#6b7280; background:#f9fafb; border-radius:6px; padding:4px 10px; margin-bottom:8px; display:inline-block; }
        .ep-ssa-structure-tag { font-size:11px; color:#1d4ed8; background:#eff6ff; border:1px solid #bfdbfe; border-radius:20px; padding:2px 10px; display:inline-block; margin-bottom:8px; }
        .ep-ssa-designation { font-size:13px; font-weight:600; color:var(--text-color); margin-bottom:10px; padding-bottom:8px; border-bottom:1px solid var(--border-color,#f3f4f6); }
        .ep-ssa-ctc-row   { display:flex; align-items:baseline; gap:6px; margin-bottom:10px; }
        .ep-ssa-ctc-val   { font-size:20px; font-weight:700; color:var(--text-color); }
        .ep-ssa-ctc-label { font-size:11px; color:var(--text-muted); }
        .ep-ssa-breakdown { display:grid; grid-template-columns:1fr 1fr; gap:6px; margin-bottom:10px; }
        .ep-ssa-breakdown-item { background:var(--control-bg,#f9fafb); border-radius:6px; padding:7px 10px; }
        .ep-ssa-breakdown-label { font-size:10px; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.04em; margin-bottom:2px; }
        .ep-ssa-breakdown-val   { font-size:13px; font-weight:600; color:var(--text-color); }
        .ep-ssa-daterange { font-size:11px; color:var(--text-muted); margin-top:8px; padding-top:8px; border-top:1px solid var(--border-color,#f3f4f6); }
        .ep-ssa-empty { font-size:13px; color:var(--text-muted); text-align:center; padding:24px 16px; }

        .ep-salary-progression { border:1px solid var(--border-color,#e5e7eb); border-radius:8px; overflow:hidden; }
        .ep-sal-prog-header { background:var(--control-bg,#f9fafb); padding:8px 14px; display:flex; justify-content:space-between; align-items:center; cursor:pointer; user-select:none; }
        .ep-sal-prog-title  { font-size:12px; font-weight:600; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.05em; }
        .ep-sal-prog-body   { padding:14px; display:none; overflow-x:auto; }
        .ep-sal-prog-body.open { display:block; }
        .ep-sal-prog-track  { display:flex; align-items:flex-start; flex-wrap:nowrap; gap:0; }
        .ep-sal-prog-node   { display:flex; flex-direction:column; align-items:center; min-width:72px; text-align:center; }
        .ep-sal-prog-node-dot { width:10px; height:10px; border-radius:50%; border:2px solid #9333ea; background:#e9d5ff; margin-bottom:4px; }
        .ep-sal-prog-node-dot.current { background:#9333ea; border-color:#7e22ce; }
        .ep-sal-prog-node-amt  { font-size:11px; font-weight:700; color:var(--text-color); }
        .ep-sal-prog-node-date { font-size:9px; color:var(--text-muted); margin-top:1px; }
        .ep-sal-prog-arrow { font-size:14px; color:#d1d5db; padding:0 4px; margin-top:2px; }
        .ep-sal-prog-hike-chip { display:inline-block; font-size:10px; font-weight:700; background:#f0fdf4; color:#166534; border:1px solid #86efac; border-radius:10px; padding:1px 7px; margin-top:3px; }

        .ep-comp-toggle-wrap { margin-top:10px; }
        .ep-comp-cols { display:grid; grid-template-columns:1fr 1fr 1fr; gap:8px; }
        .ep-comp-toggle-btn {
            width:100%; display:flex; justify-content:space-between; align-items:center;
            padding:6px 10px; border-radius:6px;
            border:1px solid var(--border-color,#e5e7eb);
            background:var(--control-bg,#f9fafb); cursor:pointer;
            font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:0.05em;
            color:var(--text-color); transition:background 0.15s;
        }
        .ep-comp-toggle-btn.earnings-btn      { color:#15803d; border-color:#86efac; background:#f0fdf4; }
        .ep-comp-toggle-btn.earnings-btn:hover      { background:#dcfce7; }
        .ep-comp-toggle-btn.deductions-btn    { color:#b91c1c; border-color:#fca5a5; background:#fff5f5; }
        .ep-comp-toggle-btn.deductions-btn:hover    { background:#fee2e2; }
        .ep-comp-toggle-btn.employer-btn      { color:#1d4ed8; border-color:#bfdbfe; background:#eff6ff; }
        .ep-comp-toggle-btn.employer-btn:hover      { background:#dbeafe; }
        .ep-comp-btn-left  { display:flex; align-items:center; gap:6px; }
        .ep-comp-btn-count { font-size:10px; font-weight:700; padding:1px 6px; border-radius:8px; }
        .ep-comp-toggle-btn.earnings-btn   .ep-comp-btn-count { background:#bbf7d0; color:#14532d; }
        .ep-comp-toggle-btn.deductions-btn .ep-comp-btn-count { background:#fecaca; color:#7f1d1d; }
        .ep-comp-toggle-btn.employer-btn   .ep-comp-btn-count { background:#bfdbfe; color:#1e3a8a; }
        .ep-comp-chevron { font-size:9px; transition:transform 0.2s; }
        .ep-comp-chevron.open { transform:rotate(180deg); }
        .ep-comp-list { display:none; border:1px solid var(--border-color,#e5e7eb); border-top:none; border-radius:0 0 6px 6px; overflow:hidden; }
        .ep-comp-list.open { display:block; }
        .ep-comp-row { display:flex; justify-content:space-between; align-items:center; font-size:12px; padding:5px 10px; border-bottom:1px solid var(--border-color,#f3f4f6); }
        .ep-comp-row:last-child { border-bottom:none; }
        .ep-comp-row:nth-child(even) { background:var(--control-bg,#f9fafb); }
        .ep-comp-name { color:var(--text-color); }
        .ep-comp-amt        { font-weight:600; }
        .ep-comp-amt.earn   { color:#16a34a; }
        .ep-comp-amt.deduct { color:#ef4444; }
        .ep-comp-amt.employer { color:#1d4ed8; }

        .ep-ssa-cancelled-wrap { border:1px solid var(--border-color,#e5e7eb); border-radius:8px; overflow:hidden; }
        .ep-ssa-cancelled-header { background:var(--control-bg,#f9fafb); padding:8px 14px; display:flex; justify-content:space-between; align-items:center; cursor:pointer; user-select:none; }
        .ep-ssa-cancelled-title { font-size:12px; font-weight:600; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.05em; display:flex; align-items:center; gap:6px; }
        .ep-ssa-cancelled-count { background:#e5e7eb; color:var(--text-muted); font-size:10px; font-weight:700; padding:1px 7px; border-radius:10px; }
        .ep-ssa-toggle-icon { font-size:10px; color:var(--text-muted); transition:transform 0.2s; }
        .ep-ssa-toggle-icon.open { transform:rotate(180deg); }
        .ep-ssa-cancelled-list { display:none; }
        .ep-ssa-cancelled-list.open { display:block; }
        .ep-ssa-cancelled-item { padding:10px 14px; border-top:1px solid var(--border-color,#f3f4f6); display:flex; flex-direction:column; gap:3px; }
        .ep-ssa-cancelled-item:hover { background:var(--control-bg,#f9fafb); }
        .ep-ssa-cancelled-name { font-size:12px; font-weight:600; color:#1d4ed8; text-decoration:none; }
        .ep-ssa-cancelled-name:hover { text-decoration:underline; }
        .ep-ssa-cancelled-meta { font-size:11px; color:var(--text-muted); display:flex; gap:10px; flex-wrap:wrap; }
        .ep-ssa-cancelled-ctc  { font-size:12px; font-weight:600; color:var(--text-color); }
        .ep-ssa-cancelled-badge { display:inline-block; padding:1px 7px; font-size:10px; font-weight:600; border-radius:10px; background:#fee2e2; color:#991b1b; }

        /* ══════════════════════════════════════════════════════
           LOAN LEDGER STYLES
           ══════════════════════════════════════════════════════ */

        .ep-loan-section-title { font-size:15px; font-weight:600; color:var(--text-color); margin:0 0 12px 0; }

        .ep-loan-overview {
            display:grid; grid-template-columns:repeat(4,1fr);
            border:1px solid var(--border-color,#e5e7eb);
            border-radius:8px; overflow:hidden; margin-bottom:14px;
        }
        .ep-loan-ov-item {
            padding:14px 16px; text-align:center;
            border-right:1px solid var(--border-color,#e5e7eb);
        }
        .ep-loan-ov-item:last-child { border-right:none; }
        .ep-loan-ov-label { font-size:10px; text-transform:uppercase; letter-spacing:0.05em; color:var(--text-muted); margin-bottom:4px; }
        .ep-loan-ov-val { font-size:18px; font-weight:700; }
        .ep-loan-ov-val.blue   { color:#1d4ed8; }
        .ep-loan-ov-val.green  { color:#16a34a; }
        .ep-loan-ov-val.red    { color:#dc2626; }
        .ep-loan-ov-val.purple { color:#9333ea; }

        /* Filter buttons styling */
        .ep-filter-btn {
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            border: 1px solid var(--border-color, #e5e7eb);
            background: var(--control-bg, #f9fafb);
            color: var(--text-muted);
        }

        .ep-filter-btn:hover {
            background: #e5e7eb;
            border-color: #9ca3af;
            transform: translateY(-1px);
        }

        .ep-filter-btn.active {
            background: #1d4ed8;
            border-color: #1d4ed8;
            color: white;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
        }

        #loans-filter-buttons .ep-filter-btn.active,
        #advances-filter-buttons .ep-filter-btn.active {
            background: #1d4ed8;
            border-color: #1d4ed8;
            color: white;
        }

       /* Add to inject_ep_styles function */
        #loans-container,
        #advances-container {
         width: 100%;
        }

       /* Change this section only */
.ep-loan-grid {
    display: flex;
    flex-direction: column;
    gap: 16px;
    margin-bottom: 8px;
    width: 100%;
}

@media (min-width: 1400px) {
    .ep-loan-grid {
        grid-template-columns: repeat(3, 1fr);
    }
}

@media (max-width: 768px) {
    .ep-loan-grid {
        grid-template-columns: 1fr;
    }
}

        .ep-loan-card { 
            border: 1px solid var(--border-color,#e5e7eb); 
            border-radius: 8px; 
            overflow: hidden; 
            margin-bottom: 0;
            transition: box-shadow 0.2s;
            background: var(--card-bg, #fff);
        }
        
        .ep-loan-card:hover {
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
        }
        
        .ep-loan-card.active-loan { 
            border-color: #86efac;
            background: linear-gradient(135deg, #f0fdf4, #ffffff);
        }
        
        .ep-loan-card-header {
            display:flex; align-items:center; justify-content:space-between;
            padding:12px 16px; cursor:pointer; user-select:none;
            background:var(--control-bg,#f9fafb);
        }
        .ep-loan-card.active-loan .ep-loan-card-header { background:linear-gradient(135deg,#dcfce7,#bbf7d0); }
        .ep-loan-card-header-left  { display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
        .ep-loan-card-header-right { display:flex; align-items:center; gap:10px; }
        .ep-loan-card-id { font-size:12px; font-weight:700; color:#1d4ed8; font-family:monospace; }
        .ep-loan-type-badge {
            font-size:10px; font-weight:700; padding:2px 8px;
            border-radius:10px; background:#eff6ff; color:#1d4ed8; border:1px solid #bfdbfe;
        }
        .ep-loan-frequency {
            font-size: 11px;
            color: var(--text-muted);
            background: var(--control-bg, #f3f4f6);
            padding: 2px 6px;
            border-radius: 4px;
        }
        .ep-loan-date {
            font-size: 11px;
            color: var(--text-muted);
            display: inline-flex;
            align-items: center;
            gap: 3px;
        }
        .ep-loan-status-badge { font-size:10px; font-weight:700; padding:2px 8px; border-radius:10px; }
        .ep-loan-status-badge.active    { background:#dcfce7; color:#166534; border:1px solid #86efac; }
        .ep-loan-status-badge.completed { background:#e0e7ff; color:#3730a3; border:1px solid #a5b4fc; }
        .ep-loan-status-badge.pending   { background:#fef9c3; color:#713f12; border:1px solid #fde047; }
        .ep-loan-card-amount { font-size:14px; font-weight:700; color:var(--text-color); }
        .ep-loan-chev { font-size:10px; color:var(--text-muted); transition:transform 0.2s; display: inline-block; }
        .ep-loan-chev.open { transform:rotate(180deg); }

        .ep-loan-progress-wrap { padding:0 16px 12px; background:var(--control-bg,#f9fafb); }
        .ep-loan-card.active-loan .ep-loan-progress-wrap { background:linear-gradient(135deg,#dcfce7,#f0fdf4); }
        .ep-loan-progress-meta {
            display:flex; justify-content:space-between; flex-wrap:wrap;
            font-size:11px; color:var(--text-muted); margin-bottom:4px; gap:4px;
        }
        .ep-loan-progress-bar-bg { height:6px; border-radius:3px; background:var(--border-color,#e5e7eb); overflow:hidden; }
        .ep-loan-progress-bar-fill { height:100%; border-radius:3px; background:linear-gradient(90deg,#22c55e,#16a34a); transition:width 0.5s; }

        .ep-loan-card-body { display:none; border-top:1px solid var(--border-color,#e5e7eb); }
        .ep-loan-card-body.open { display:block; }

        .ep-loan-body-stats { display:grid; grid-template-columns:repeat(5,1fr); border-bottom:1px solid var(--border-color,#e5e7eb); }
        .ep-loan-body-stat { padding:10px 12px; text-align:center; border-right:1px solid var(--border-color,#e5e7eb); }
        .ep-loan-body-stat:last-child { border-right:none; }
        .ep-loan-body-stat-label { font-size:10px; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.04em; margin-bottom:3px; }
        .ep-loan-body-stat-val   { font-size:13px; font-weight:700; color:var(--text-color); }

        .ep-loan-tabs-wrap { padding:12px 16px; }
        .ep-loan-tabs-nav { display:flex; gap:4px; border-bottom:1px solid var(--border-color,#e5e7eb); margin-bottom:10px; }
        .ep-loan-tab-btn {
            padding:5px 12px; border:none; background:none;
            font-size:12px; font-weight:600; cursor:pointer;
            color:var(--text-muted); border-bottom:2px solid transparent;
            margin-bottom:-1px; transition:all 0.15s;
        }
        .ep-loan-tab-btn.active { color:#1d4ed8; border-bottom-color:#1d4ed8; }
        .ep-loan-tab-btn .ep-tab-count {
            font-size:10px; font-weight:700; padding:1px 5px;
            border-radius:8px; background:#e5e7eb; color:var(--text-muted); margin-left:4px;
        }
        .ep-loan-tab-btn.active .ep-tab-count { background:#bfdbfe; color:#1d4ed8; }
        .ep-loan-tab-panel { display:none; }
        .ep-loan-tab-panel.active { display:block; }

        .ep-loan-schedule-table { width:100%; border-collapse:collapse; font-size:12px; }
        .ep-loan-schedule-table th {
            text-align:left; padding:6px 10px;
            background:var(--control-bg,#f9fafb);
            border-bottom:1px solid var(--border-color,#e5e7eb);
            font-size:10px; text-transform:uppercase; letter-spacing:0.04em;
            color:var(--text-muted); font-weight:600;
        }
        .ep-loan-schedule-table td { padding:7px 10px; border-bottom:1px solid var(--border-color,#f3f4f6); vertical-align:middle; }
        .ep-loan-schedule-table tr:last-child td { border-bottom:none; }
        .ep-loan-schedule-table tr:nth-child(even) td { background:var(--control-bg,#f9fafb); }

        .ep-sched-status { display:inline-block; font-size:10px; font-weight:600; padding:2px 7px; border-radius:8px; }
        .ep-sched-status.deducted { background:#dcfce7; color:#166534; }
        .ep-sched-status.pending  { background:#fef9c3; color:#713f12; }
        .ep-sched-status.deferred { background:#fee2e2; color:#991b1b; }

        .ep-sched-bar-wrap { width:60px; height:5px; background:#e5e7eb; border-radius:3px; overflow:hidden; display:inline-block; vertical-align:middle; margin-left:6px; }
        .ep-sched-bar-fill { height:100%; border-radius:3px; background:#22c55e; }

        .ep-loan-empty {
            text-align:center; padding:32px 16px;
            font-size:13px; color:var(--text-muted);
            background:var(--control-bg,#f9fafb); border-radius:8px;
            border:1px dashed var(--border-color,#e5e7eb);
        }

        @media (max-width:900px) {
            .ep-loan-overview    { grid-template-columns:1fr 1fr; }
            .ep-loan-body-stats  { grid-template-columns:1fr 1fr 1fr; }
        }
    `;
    document.head.appendChild(style);

    if (!document.getElementById("ep-tooltip")) {
        var tip = document.createElement("div");
        tip.id = "ep-tooltip";
        tip.className = "ep-tooltip";
        document.body.appendChild(tip);
    }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt_currency(val) {
    if (!val) return "0";
    return Number(val).toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

function fmt_date_human(date_str) {
    if (!date_str) return "";
    var d = new Date(date_str);
    return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

function days_ago(date_str) {
    if (!date_str) return null;
    var days = Math.floor((Date.now() - new Date(date_str).getTime()) / 86400000);
    if (days === 0) return "today";
    if (days === 1) return "1 day ago";
    if (days < 30) return days + " days ago";
    var months = Math.floor(days / 30);
    if (months < 12) return months + " mo ago";
    var yrs = Math.floor(months / 12), mos = months % 12;
    return yrs + "yr" + (mos ? " " + mos + "mo" : "") + " ago";
}

function calc_duration(start_str, end_str) {
    if (!start_str) return null;
    var end = end_str ? new Date(end_str) : new Date();
    var start = new Date(start_str);
    var total_months = (end.getFullYear() - start.getFullYear()) * 12 + (end.getMonth() - start.getMonth());
    if (total_months < 0) return null;
    var yrs = Math.floor(total_months / 12), mos = total_months % 12;
    var parts = [];
    if (yrs) parts.push(yrs + " yr" + (yrs !== 1 ? "s" : ""));
    if (mos) parts.push(mos + " mo" + (mos !== 1 ? "s" : ""));
    return parts.length ? parts.join(" ") : "< 1 mo";
}

function calc_age(dob_str) {
    if (!dob_str) return null;
    var today = new Date(), dob = new Date(dob_str);
    var age = today.getFullYear() - dob.getFullYear();
    var m = today.getMonth() - dob.getMonth();
    if (m < 0 || (m === 0 && today.getDate() < dob.getDate())) age--;
    return age;
}

// ── Status maps — updated to include Earned Comp Off ─────────────────────────
var STATUS_COLORS = {
    "Present": "present",
    "Absent": "absent",
    "Half Day": "halfday",
    "LWP": "lwp",
    "Holiday": "holiday",
    "Weekly Off": "weeklyoff",
    "Earned Leave": "earnedleave",
    "Casual Leave": "casualleave",
    "On Tour": "ontour",
    "Comp Off": "compoff",
    "Earned Comp Off": "earnedcompoff"
};
var STATUS_HEX = {
    "present": "#16a34a",
    "absent": "#dc2626",
    "halfday": "#ca8a04",
    "lwp": "#ea580c",
    "holiday": "#2563eb",
    "weeklyoff": "#9333ea",
    "earnedleave": "#0d9488",
    "casualleave": "#db2777",
    "ontour": "#16a34a",
    "compoff": "#9333ea",
    "earnedcompoff": "#14b8a6"
};
var MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

// ── Main render ───────────────────────────────────────────────────────────────

function render_profile($sidebar, $main, d, emp) {
    var s = d.salary || {};
    var c = d.company_link || {};
    var att_map = d.attendance_map || {};
    var years = d.years || [];
    var timeline = d.timeline || [];
    var latest_ssa = d.latest_ssa || null;
    var cancelled_ssas = d.cancelled_ssas || [];

    var avatar_html = d.employee_image
        ? "<img src='" + d.employee_image + "' />"
        : (d.first_name ? d.first_name.charAt(0).toUpperCase() : "E");

    // ── SIDEBAR ──
    var sb = "<div class='ep-sidebar-inner'>";
    sb += "<div class='ep-avatar'>" + avatar_html + "</div>";
    if (emp) sb += "<div class='ep-emp-id'>ID: " + emp + "</div>";
    sb += "<div class='ep-name'>" + (d.employee || "") + "</div>";
    if (d.date_of_birth) {
        var age = calc_age(d.date_of_birth);
        sb += "<div class='ep-dob-row'>🎂 " + fmt_date_human(d.date_of_birth) + (age !== null ? " · " + age + " yrs" : "") + "</div>";
    }
    if (d.cell_number)
        sb += "<div class='ep-contact-row'>📞 <a href='tel:" + d.cell_number + "'>" + d.cell_number + "</a></div>";
    if (d.company_email || d.personal_email) {
        var email = d.company_email || d.personal_email;
        sb += "<div class='ep-contact-row'>✉️ <a href='mailto:" + email + "'>" + email + "</a></div>";
    }
    sb += "<hr class='ep-divider'>";
    if (c.company) sb += info_row("Company", c.company);
    if (c.branch) sb += info_row("Branch", c.branch);
    if (c.category) sb += info_row("Category", c.category);
    if (c.date_of_joining) sb += info_row("Joined", fmt_date_human(c.date_of_joining));
    if (c.department) sb += info_row("Department", c.department);
    if (c.designation) sb += info_row("Designation", c.designation);
    if (d.tenure) sb += info_row("Tenure", d.tenure);
    if (c.immediate_reporting_name) sb += info_row("Immediate Reporting", c.immediate_reporting_name);
    if (c.final_reporting_name) sb += info_row("Final Reporting", c.final_reporting_name);
    sb += "<hr class='ep-divider'>";
    sb += "<a href='/app/employee/" + emp + "' class='ep-link-btn'>✏️ Edit Employee</a>";
    if (d.company_link_name)
        sb += "<a href='/app/company-link/" + encodeURIComponent(d.company_link_name) + "' class='ep-link-btn'>🏢 View Company Record</a>";
    sb += "<a href='/app/salary-structure-assignment?employee=" + encodeURIComponent(emp) + "' class='ep-link-btn'>💰 Salary Assignment</a>";
    sb += "</div>";
    $sidebar.html(sb);

    // ── MAIN ──
    var prev_ctc = (cancelled_ssas && cancelled_ssas.length) ? cancelled_ssas[0].monthly_ctc : null;
    var main = "";

    // Salary card
    main += "<div class='ep-card'>";
    main += "<div class='ep-title-area'><h4 class='ep-card-title'>Salary Overview</h4>";
    if (latest_ssa && latest_ssa.salary_structure)
        main += "<span class='ep-salary-structure-tag'>📋 " + latest_ssa.salary_structure + "</span>";
    main += "</div>";
    main += "<div class='ep-salary-grid'>";
    main += sal_item("Monthly CTC", s.monthly_ctc);
    main += sal_item("Annual CTC", s.annual_ctc);
    main += sal_item("Gross Salary", s.gross_salary);
    main += sal_item("Net Salary", s.net_salary);
    main += sal_item("Total Deductions", s.total_deductions);
    main += sal_item("Employer Contribution", s.total_employer_contribution);
    main += "</div>";
    if (prev_ctc && s.monthly_ctc && Number(s.monthly_ctc) > 0 && Number(prev_ctc) > 0) {
        var hike_amt = Number(s.monthly_ctc) - Number(prev_ctc);
        var hike_pct = ((hike_amt / Number(prev_ctc)) * 100).toFixed(1);
        if (hike_amt > 0) {
            main += "<div class='ep-hike-banner'>";
            main += "<span class='ep-hike-label'>Last Hike</span>";
            main += "<span class='ep-hike-val'>+&#8377;" + fmt_currency(hike_amt) + "/mo</span>";
            main += "<span class='ep-hike-pct'>+" + hike_pct + "%</span>";
            main += "<span class='ep-hike-from'>from &#8377;" + fmt_currency(prev_ctc) + "</span>";
            main += "</div>";
        }
    }
    main += "</div>";

    // Attendance card
    var now = new Date();
    var cur_year = now.getFullYear();
    var cur_month = now.getMonth() + 1;

    main += "<div class='ep-card'>";
    main += "<div class='ep-title-area'><h4 class='ep-card-title'>Attendance Overview</h4>";
    main += "<div style='display:flex;gap:8px;align-items:center;'>";
    main += "<button class='ep-today-btn' id='ep-today-btn'>Today</button>";
    main += "<select class='ep-year-select' id='ep-year-select'>";
    years.forEach(function (yr) {
        main += "<option value='" + yr + "'" + (String(yr) === String(cur_year) ? " selected" : "") + ">" + yr + "</option>";
    });
    main += "</select></div></div>";
    main += "<div id='ep-heatmap-wrap'></div></div>";
    // ADD this marker right after:
    main += "<div id='ep-att-card-end'></div>";
    // Timeline + SSA
    main += "<div class='ep-card'>";
    main += "<div class='ep-title-area'><h4 class='ep-card-title'>Employee Timeline</h4></div>";
    main += "<div class='ep-timeline-ssa-wrap'>";
    main += "<div>" + render_timeline_html(timeline) + "</div>";
    main += "<div class='ep-ssa-panel'>" + render_ssa_panel_html(latest_ssa, cancelled_ssas, c) + "</div>";
    main += "</div></div>";
    main += render_loan_ledger_html(d.loan_ledger || []);

    $main.html(main);

    render_heatmap($main, att_map, cur_year, cur_month);

    $main.find("#ep-year-select").on("change", function () {
        var yr = parseInt($(this).val());
        var active_btn = $main.find(".ep-month-label-btn.active");
        var active_month = active_btn.length ? parseInt(active_btn.data("month")) : "all";
        render_heatmap($main, att_map, yr, active_month);
    });

    $main.find("#ep-heatmap-wrap").on("click", ".ep-month-label-btn", function () {
        var clicked = parseInt($(this).data("month"));
        var yr = parseInt($main.find("#ep-year-select").val());
        render_heatmap($main, att_map, yr, $(this).hasClass("active") ? "all" : clicked);
    });

    $main.find("#ep-today-btn").on("click", function () {
        var n = new Date();
        $main.find("#ep-year-select").val(n.getFullYear());
        render_heatmap($main, att_map, n.getFullYear(), n.getMonth() + 1);
    });

    $main.on("mouseenter", ".ep-day:not(.empty)", function (e) {
        var title = $(this).attr("title") || "";
        if (!title) return;
        var colon = title.indexOf(": ");
        var date_part = colon > -1 ? title.slice(0, colon) : title;
        var status_part = colon > -1 ? title.slice(colon + 2) : "";
        var cls = ($(this).attr("class") || "").split(" ").find(function (c) { return STATUS_HEX[c]; }) || "";
        var color = STATUS_HEX[cls] || "#6b7280";
        var tip = document.getElementById("ep-tooltip");
        tip.innerHTML =
            "<div class='ep-tooltip-date'>" + fmt_date_human(date_part) + "</div>" +
            "<div><span class='ep-tooltip-dot' style='background:" + color + "'></span>" +
            (status_part || "No Record") + "</div>";
        tip.classList.add("visible");
        move_tooltip(e);
    });
    $main.on("mousemove", ".ep-day:not(.empty)", function (e) { move_tooltip(e); });
    $main.on("mouseleave", ".ep-day", function () {
        document.getElementById("ep-tooltip").classList.remove("visible");
    });

    $main.on("click", ".ep-ssa-cancelled-header", function () {
        $(this).next(".ep-ssa-cancelled-list").toggleClass("open");
        $(this).find(".ep-ssa-toggle-icon").toggleClass("open");
    });
    $main.on("click", ".ep-sal-prog-header", function () {
        $(this).next(".ep-sal-prog-body").toggleClass("open");
        $(this).find(".ep-ssa-toggle-icon").toggleClass("open");
    });
    $main.on("click", ".ep-comp-toggle-btn", function () {
        var $section = $(this).closest(".ep-comp-section");
        var $list = $section.find(".ep-comp-list");
        var $chev = $(this).find(".ep-comp-chevron");
        $list.toggleClass("open");
        $chev.toggleClass("open");
    });

    // ── Loan card expansion toggle ──
    $main.on("click", ".ep-loan-card-header", function (e) {
        e.stopPropagation();
        var $header = $(this);
        var $card = $header.closest(".ep-loan-card");
        var $body = $card.find(".ep-loan-card-body");
        var $chev = $header.find(".ep-loan-chev");

        // Toggle with slide animation
        if ($body.is(":visible")) {
            $body.slideUp(200);
            $chev.css("transform", "rotate(0deg)");
        } else {
            $body.slideDown(200);
            $chev.css("transform", "rotate(180deg)");
        }
    });

    // ── Loan schedule tab switching ──
    $main.on("click", ".ep-loan-tab-btn", function (e) {
        e.stopPropagation();
        var $btn = $(this);
        var $wrap = $btn.closest(".ep-loan-tabs-wrap");
        $wrap.find(".ep-loan-tab-btn").removeClass("active");
        $btn.addClass("active");
        var target = $btn.data("tab");
        $wrap.find(".ep-loan-tab-panel").removeClass("active");
        $wrap.find("[data-tab='" + target + "'].ep-loan-tab-panel").addClass("active");
    });

    // ── Initialize loan filter functionality ──
    // In render_profile function, replace the loan filter initialization section with:

    setTimeout(function () {
        // Initial render of loans with filter
        if (typeof render_filtered_loans === 'function') {
            render_filtered_loans();
        }

        // Render advances (no filters needed)
        if (typeof render_filtered_advances === 'function') {
            render_filtered_advances();
        }

        // Attach filter button events only for Loans
        $main.find("#loans-filter-buttons .ep-filter-btn").off("click").on("click", function () {
            var filter = $(this).data("filter");
            if (window.loan_filter_state) {
                window.loan_filter_state.loans = filter;
            }

            // Update active state
            $(this).siblings().removeClass("active");
            $(this).addClass("active");

            if (typeof render_filtered_loans === 'function') {
                render_filtered_loans();
            }
            attach_loan_card_events($main.find("#loans-container"));
        });

        // Attach events to all loan cards in both containers
        attach_loan_card_events($main.find("#loans-container, #advances-container"));

        // ← ADD THIS LINE
        render_employee_deduction_section($main, emp);
    }, 100);
}


// ── Deduction Breakdown for Single Employee ───────────────────────────────────
function render_employee_deduction_section($main, emp) {
    var now = new Date();
    var cur_year = now.getFullYear();
    var cur_month = now.getMonth() + 1;

    var month_names = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ];

    // Build year options (last 3 years)
    var year_opts = "";
    for (var y = cur_year; y >= cur_year - 2; y--) {
        year_opts += "<option value='" + y + "'" + (y === cur_year ? " selected" : "") + ">" + y + "</option>";
    }

    // Build month options
    var month_opts = "";
    month_names.forEach(function (mn, idx) {
        var mnum = idx + 1;
        month_opts += "<option value='" + mnum + "'" + (mnum === cur_month ? " selected" : "") + ">" + mn + "</option>";
    });

    var section_html =
        "<div class='ep-card' id='ep-ded-breakdown-card'>" +
        "<div class='ep-title-area'>" +
        "<h4 class='ep-card-title'>📋 Salary Deduction Breakdown</h4>" +
        "<div style='display:flex;gap:8px;align-items:center;'>" +
        "<select id='ep-ded-month' style='padding:3px 10px;border-radius:6px;border:1px solid var(--border-color,#e5e7eb);background:var(--card-bg,#fff);font-size:12px;cursor:pointer;color:var(--text-color);'>" +
        month_opts +
        "</select>" +
        "<select id='ep-ded-year' style='padding:3px 10px;border-radius:6px;border:1px solid var(--border-color,#e5e7eb);background:var(--card-bg,#fff);font-size:12px;cursor:pointer;color:var(--text-color);'>" +
        year_opts +
        "</select>" +
        "<button id='ep-ded-load-btn' style='padding:4px 14px;border-radius:6px;font-size:12px;font-weight:600;border:1px solid #bfdbfe;background:#eff6ff;color:#1d4ed8;cursor:pointer;'>Load</button>" +
        "</div></div>" +
        "<div id='ep-ded-breakdown-body'><div style='text-align:center;padding:24px;font-size:13px;color:var(--text-muted);'>Select month and year then click Load.</div></div>" +
        "</div>";

    $main.find("#ep-att-card-end").after(section_html);

    // Auto-load current month
    load_employee_deduction($main, emp, cur_month, cur_year, month_names);

    $main.find("#ep-ded-load-btn").on("click", function () {
        var m = parseInt($main.find("#ep-ded-month").val());
        var y = parseInt($main.find("#ep-ded-year").val());
        load_employee_deduction($main, emp, m, y, month_names);
    });
}

function load_employee_deduction($main, emp, month_num, year, month_names) {
    var month_name = month_names[month_num - 1];
    var start_date = year + "-" + String(month_num).padStart(2, "0") + "-01";

    $main.find("#ep-ded-breakdown-body").html(
        "<div style='text-align:center;padding:24px;font-size:13px;color:var(--text-muted);'>⏳ Loading...</div>"
    );

    frappe.call({
        method: "saral_hr.saral_hr.page.employee_profile.employee_profile.get_employee_deduction_breakdown",
        args: { employee: emp, month: month_name, year: String(year), start_date: start_date },
        callback: function (r) {
            if (!r.message) {
                $main.find("#ep-ded-breakdown-body").html(
                    "<div style='text-align:center;padding:24px;font-size:13px;color:var(--text-muted);'>No salary slip found for " + month_name + " " + year + ".</div>"
                );
                return;
            }
            render_employee_ded_table($main, r.message, month_name, year);
        }
    });
}

function render_employee_ded_table($main, d, month_name, year) {
    function money(v) { return "₹" + fmt_currency(v || 0); }

    function formatComponents(components) {
        if (!components || Object.keys(components).length === 0) return "—";
        var parts = [];
        for (var name in components) {
            var amt = components[name];
            parts.push(
                "<span style='display:block;font-size:11px;'>" +
                name + ": <strong>" + money(amt) + "</strong></span>"
            );
        }
        return parts.join("");
    }

    function formatLoan(loan_info) {
        var total = loan_info.total || 0;
        if (total <= 0) return "—";
        return "<span style='font-weight:700;color:#dc2626;'>" + money(total) + "</span>";
    }

    var status_color = d.slip_status === "Submitted" ? "#16a34a" : "#f59e0b";
    var status_bg = d.slip_status === "Submitted" ? "#dcfce7" : "#fef9c3";

    var html =
        // ── Slip info bar ──
        "<div style='display:flex;align-items:center;gap:12px;margin-bottom:12px;flex-wrap:wrap;'>" +
        "<span style='font-size:12px;color:var(--text-muted);'>Slip:</span>" +
        "<a href='/app/salary-slip/" + d.slip_name + "' target='_blank' " +
        "style='font-size:12px;font-weight:700;color:#1d4ed8;'>" + d.slip_name + "</a>" +
        "<span style='font-size:11px;font-weight:600;padding:2px 10px;border-radius:10px;" +
        "background:" + status_bg + ";color:" + status_color + ";'>" + d.slip_status + "</span>" +
        "<span style='font-size:12px;color:var(--text-muted);margin-left:auto;'>" + month_name + " " + year + "</span>" +
        "</div>" +


        // ── Net Salary highlight (TOP) ──
        "<div style='display:flex;flex-direction:row;align-items:center;gap:24px;" +
        "background:linear-gradient(90deg,#eff6ff 0%,#f0fdf4 100%);" +
        "border:1px solid #bfdbfe;border-radius:10px;padding:10px 18px;margin-bottom:12px;'>" +
        "<div style='display:flex;flex-direction:column;'>" +
        "<span style='font-size:10px;font-weight:600;color:var(--text-muted);text-transform:uppercase;letter-spacing:.05em;'>Net Salary (Assignment)</span>" +
        "<span style='font-size:20px;font-weight:700;color:#15803d;'>" + money(d.ssa_net) + "</span>" +
        "</div>" +
        "<div style='width:1px;height:38px;background:#bfdbfe;flex-shrink:0;'></div>" +
        "<div style='display:flex;flex-direction:column;'>" +
        "<span style='font-size:10px;font-weight:600;color:var(--text-muted);text-transform:uppercase;letter-spacing:.05em;'>Net Salary (Slip)</span>" +
        "<span style='font-size:20px;font-weight:700;color:#dc2626;'>" + money(d.ss_net) + "</span>" +
        "</div>" +
        "</div>" +
        // ── Single table: all stats + deductions in one row ──
        "<div class='pp-table-wrap'>" +
        "<table style='width:100%;border-collapse:collapse;font-size:12px;border:1px solid var(--border-color,#e5e7eb);border-radius:8px;overflow:hidden;'>" +
        "<thead><tr>" +
        ep_ded_th("📅 Working Days", "#f3f4f6", "#374151") +
        ep_ded_th("🚫 Absent", "#fef2f2", "#dc2626") +
        ep_ded_th("✅ Paid Days", "#f0fdf4", "#15803d") +
        ep_ded_th("🏦 Loan", "#ede9fe", "#4c1d95") +
        ep_ded_th("📋 Retention", "#fef9c3", "#713f12") +
        ep_ded_th("➕ Additional Salary", "#dcfce7", "#14532d") +
        ep_ded_th("➖ Additional Deduction", "#fce7f3", "#9d174d") +
        "</tr></thead>" +
        "<tbody><tr>" +
        "<td style='text-align:center;padding:12px 10px;border-top:1px solid var(--border-color);font-weight:700;font-size:14px;color:#1e40af;'>" +
        d.total_days +
        "</td>" +
        "<td style='text-align:center;padding:12px 10px;border-top:1px solid var(--border-color);font-weight:700;font-size:14px;color:" + (d.absent_days > 0 ? "#dc2626" : "var(--text-muted)") + ";'>" +
        d.absent_days +
        "</td>" +
        "<td style='text-align:center;padding:12px 10px;border-top:1px solid var(--border-color);font-weight:700;font-size:14px;color:#15803d;'>" +
        d.paid_days +
        "</td>" +
        "<td style='text-align:center;padding:12px 10px;border-top:1px solid var(--border-color);vertical-align:middle;'>" +
        formatLoan(d.loan) +
        "</td>" +
        "<td style='text-align:center;padding:12px 10px;border-top:1px solid var(--border-color);'>" +
        (d.retention > 0
            ? "<span style='font-weight:700;color:#dc2626;'>" + money(d.retention) + "</span>"
            : "—") +
        "</td>" +
        "<td style='text-align:center;padding:12px 10px;border-top:1px solid var(--border-color);font-size:11px;'>" +
        formatComponents(d.additional_salary) +
        "</td>" +
        "<td style='text-align:center;padding:12px 10px;border-top:1px solid var(--border-color);font-size:11px;'>" +
        formatComponents(d.additional_deductions) +
        "</td>" +
        "</tr></tbody>" +
        "</table></div>";

    $main.find("#ep-ded-breakdown-body").html(html);
}

function ep_ded_stat(label, val, color) {
    return "<div style='padding:12px 10px;text-align:center;border-right:1px solid var(--border-color,#e5e7eb);'>" +
        "<div style='font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em;margin-bottom:4px;'>" + label + "</div>" +
        "<div style='font-size:14px;font-weight:700;color:" + color + ";'>" + val + "</div>" +
        "</div>";
}

function ep_ded_th(label, bg, color, align) {
    return "<th style='text-align:" + (align || "center") + ";padding:8px 12px;" +
        "border:1px solid var(--border-color);background:" + bg + ";" +
        "color:" + color + ";white-space:nowrap;font-size:11px;font-weight:700;'>" +
        label + "</th>";
}

function move_tooltip(e) {
    var tip = document.getElementById("ep-tooltip");
    var x = e.clientX + 14, y = e.clientY - 10;
    if (x + 170 > window.innerWidth) x = e.clientX - 170;
    tip.style.left = x + "px";
    tip.style.top = y + "px";
}

// ── Heatmap ───────────────────────────────────────────────────────────────────

function render_heatmap($w, att_map, year, active_month) {
    year = parseInt(year);
    active_month = active_month || "all";
    var today_str = new Date().toISOString().split("T")[0];

    // All counters — now includes earned_comp_off
    var summary = {
        present: 0, absent: 0, half_day: 0, lwp: 0,
        holiday: 0, weekly_off: 0, earned_leave: 0, casual_leave: 0,
        on_tour: 0, comp_off: 0, earned_comp_off: 0
    };
    var total_counted = 0;
    var selected_month = (active_month === "all") ? null : parseInt(active_month);

    var inner = "<div class='ep-heatmap-scroll'><div class='ep-heatmap-inner'>";

    for (var m = 0; m < 12; m++) {
        var month_num = m + 1;
        var month_str = String(month_num).padStart(2, "0");
        var days_in_month = new Date(year, month_num, 0).getDate();
        var first_dow = new Date(year, m, 1).getDay();
        var weeks = [], week = [];
        for (var p = 0; p < first_dow; p++) week.push(null);
        for (var day = 1; day <= days_in_month; day++) {
            week.push(day);
            if (week.length === 7) { weeks.push(week); week = []; }
        }
        if (week.length) { while (week.length < 7) week.push(null); weeks.push(week); }

        var is_selected = (active_month !== "all") && String(active_month) === String(month_num);
        inner += "<div class='ep-month-col'>";
        inner += "<button class='ep-month-label-btn" + (is_selected ? " active" : "") + "' data-month='" + month_num + "'>" + MONTH_NAMES[m] + "</button>";
        inner += "<div class='ep-month-weeks'>";

        weeks.forEach(function (wk) {
            inner += "<div class='ep-week-col'>";
            wk.forEach(function (d) {
                if (!d) { inner += "<div class='ep-day empty'></div>"; return; }
                var day_str = year + "-" + month_str + "-" + String(d).padStart(2, "0");
                var status = att_map[day_str] || null;
                var cls, title_attr;
                if (day_str > today_str) {
                    cls = "ep-day future"; title_attr = day_str + " (future)";
                } else if (status) {
                    var ccls = STATUS_COLORS[status] || "future";
                    cls = "ep-day " + ccls;
                    title_attr = day_str + ": " + status;
                    if (selected_month === null || selected_month === month_num) {
                        if (status === "Present") { summary.present++; total_counted++; }
                        else if (status === "Absent") { summary.absent++; total_counted++; }
                        else if (status === "Half Day") { summary.half_day++; total_counted++; }
                        else if (status === "LWP") { summary.lwp++; total_counted++; }
                        else if (status === "Holiday") { summary.holiday++; total_counted++; }
                        else if (status === "Weekly Off") { summary.weekly_off++; total_counted++; }
                        else if (status === "Earned Leave") { summary.earned_leave++; total_counted++; }
                        else if (status === "Casual Leave") { summary.casual_leave++; total_counted++; }
                        else if (status === "On Tour") { summary.on_tour++; total_counted++; }
                        else if (status === "Comp Off") { summary.comp_off++; total_counted++; }
                        else if (status === "Earned Comp Off") { summary.earned_comp_off++; total_counted++; }
                    }
                } else {
                    cls = "ep-day future"; title_attr = day_str + " (no record)";
                }
                inner += "<div class='" + cls + "' title='" + title_attr + "'>" + d + "</div>";
            });
            inner += "</div>";
        });
        inner += "</div></div>";
    }
    inner += "</div></div>";

    // Legend — added Earned Comp Off
    var legend_items = [
        ["present", "Present"], ["absent", "Absent"], ["halfday", "Half Day"],
        ["lwp", "LWP"], ["holiday", "Holiday"], ["weeklyoff", "Weekly Off"],
        ["earnedleave", "Earned Leave"], ["casualleave", "Casual Leave"],
        ["ontour", "On Tour"], ["compoff", "Comp Off"], ["earnedcompoff", "Earned Comp Off"],
        ["future", "No Record"]
    ];
    var legend = "<div class='ep-legend'>";
    legend_items.forEach(function (li) {
        legend += "<div class='ep-legend-item'><div class='ep-legend-dot " + li[0] + "'></div><span class='ep-legend-label " + li[0] + "'>" + li[1] + "</span></div>";
    });
    legend += "</div>";

    // Summary boxes — updated to include Earned Comp Off, now 6 columns
    var boxes = [
        [summary.present, "Present", "#16a34a", true],
        [summary.absent, "Absent", "#dc2626", true],
        [summary.on_tour, "On Tour", "#16a34a", false],
        [summary.earned_comp_off, "Earned Comp Off", "#14b8a6", false],
        [summary.half_day, "Half Day", "#ca8a04", false],
        [summary.lwp, "LWP", "#ea580c", false],
        [summary.holiday, "Holiday", "#2563eb", false],
        [summary.weekly_off, "Weekly Off", "#9333ea", false],
        [summary.earned_leave, "Earned Leave", "#0d9488", false],
        [summary.casual_leave, "Casual Leave", "#db2777", false],
        [summary.comp_off, "Comp Off", "#9333ea", false]
    ];
    var summ = "<div class='ep-att-summary'>";
    boxes.forEach(function (b) {
        var pct_html = (b[3] && total_counted > 0)
            ? "<div class='ep-att-pct' style='color:" + b[2] + "'>" + Math.round((b[0] / total_counted) * 100) + "%</div>"
            : "";
        summ += "<div class='ep-att-box'>" +
            "<div class='ep-att-val' style='color:" + b[2] + "'>" + b[0] + "</div>" +
            "<div class='ep-att-label'>" + b[1] + "</div>" +
            pct_html + "</div>";
    });
    summ += "</div>";

    $w.find("#ep-heatmap-wrap").html(inner + legend + summ);
}

// ── Timeline ─────────────────────────────────────────────────────────────────

function render_timeline_html(timeline) {
    if (!timeline || !timeline.length)
        return "<div class='ep-timeline-empty'>No timeline events found.</div>";
    var html = "<div class='ep-timeline-scroll'><div class='ep-timeline'>";
    timeline.forEach(function (item) {
        var active_cls = item.is_active == 1 ? " tl-active" : "";
        var date_html = "";
        if (item.start_date) date_html += "<div class='ep-tl-date'><strong>Start:</strong> " + fmt_date_human(item.start_date) + "</div>";
        if (item.end_date) date_html += "<div class='ep-tl-date'><strong>End:</strong> " + fmt_date_human(item.end_date) + "</div>";
        var meta_parts = [];
        if (item.designation) meta_parts.push(item.designation);
        if (item.department) meta_parts.push(item.department);
        if (item.branch) meta_parts.push(item.branch);
        var meta_html = meta_parts.length ? "<div class='ep-tl-meta'>" + meta_parts.join(" · ") + "</div>" : "";
        var dur = calc_duration(item.start_date, item.end_date);
        var dur_html = dur ? "<span class='ep-tl-duration'>⏱ " + dur + "</span>" : "";
        var active_badge = item.is_active == 1
            ? " <span style='font-size:10px;background:#bbf7d0;color:#166534;border-radius:8px;padding:1px 7px;font-weight:600;margin-left:4px;'>Active</span>"
            : "";
        html += "<div class='ep-timeline-item" + active_cls + "'>";
        html += "<div class='ep-tl-dot'></div>";
        html += "<div class='ep-tl-card'>";
        html += "<div class='ep-tl-company'>" + (item.company || "-") + active_badge + "</div>";
        html += date_html + meta_html + dur_html;
        html += "</div></div>";
    });
    html += "</div></div>";
    return html;
}

// ── SSA Panel ─────────────────────────────────────────────────────────────────

function render_ssa_panel_html(latest_ssa, cancelled_ssas, company_link) {
    var html = "";

    if (latest_ssa) {
        var designation = latest_ssa.designation || (company_link && company_link.designation) || "";
        var department = latest_ssa.department || (company_link && company_link.department) || "";

        html += "<div class='ep-ssa-current'>";
        html += "<div class='ep-ssa-current-header'>";
        html += "<span class='ep-ssa-current-title'>&#9646; Active Salary Assignment</span>";
        html += "<a href='/app/salary-structure-assignment/" + encodeURIComponent(latest_ssa.name) + "' class='ep-ssa-current-link' target='_blank'>" + latest_ssa.name + " &rarr;</a>";
        html += "</div><div class='ep-ssa-current-body'>";

        if (latest_ssa.salary_structure)
            html += "<div><span class='ep-ssa-structure-tag'>📋 " + latest_ssa.salary_structure + "</span></div>";
        if (latest_ssa.from_date) {
            var since = days_ago(latest_ssa.from_date);
            html += "<div class='ep-ssa-since'>📅 Active since " + fmt_date_human(latest_ssa.from_date) + " · <strong>" + since + "</strong></div>";
        }
        if (designation || department) {
            var mp = [];
            if (designation) mp.push(designation);
            if (department) mp.push(department);
            html += "<div class='ep-ssa-designation'>" + mp.join(" · ") + "</div>";
        }
        html += "<div class='ep-ssa-ctc-row'>";
        html += "<span class='ep-ssa-ctc-val'>&#8377;" + fmt_currency(latest_ssa.monthly_ctc) + "</span>";
        html += "<span class='ep-ssa-ctc-label'>/ month (CTC)</span></div>";
        html += "<div class='ep-ssa-breakdown'>";
        html += ssa_breakdown_item("Gross Salary", latest_ssa.gross_salary);
        html += ssa_breakdown_item("Net Salary", latest_ssa.net_salary);
        html += ssa_breakdown_item("Total Deductions", latest_ssa.total_deductions);
        html += ssa_breakdown_item("Employer Contrib", latest_ssa.total_employer_contribution);
        html += "</div>";

        html += render_comp_toggles(
            latest_ssa.earnings || [],
            latest_ssa.deductions || [],
            latest_ssa.employer_share || []
        );

        var dp = [];
        if (latest_ssa.from_date) dp.push("From: " + fmt_date_human(latest_ssa.from_date));
        dp.push(latest_ssa.to_date ? "To: " + fmt_date_human(latest_ssa.to_date) : "Ongoing");
        html += "<div class='ep-ssa-daterange'>" + dp.join(" &nbsp;·&nbsp; ") + "</div>";
        html += "</div></div>";
    } else {
        html += "<div class='ep-ssa-empty' style='border:1px dashed var(--border-color,#e5e7eb);border-radius:8px;'>No active salary structure assignment found.</div>";
    }

    // Salary Progression
    var all_ssas = [];
    if (cancelled_ssas && cancelled_ssas.length) cancelled_ssas.forEach(function (r) { all_ssas.push(r); });
    if (latest_ssa) all_ssas.unshift(latest_ssa);

    if (all_ssas.length > 1) {
        var ordered = all_ssas.slice().reverse();
        html += "<div class='ep-salary-progression'>";
        html += "<div class='ep-sal-prog-header'><span class='ep-sal-prog-title'>📈 Salary Progression</span><span class='ep-ssa-toggle-icon'>&#9660;</span></div>";
        html += "<div class='ep-sal-prog-body'><div class='ep-sal-prog-track'>";
        ordered.forEach(function (rec, idx) {
            var is_current = latest_ssa && rec.name === latest_ssa.name;
            var prev = idx > 0 ? ordered[idx - 1] : null;
            var hike_html = "";
            if (prev && prev.monthly_ctc && rec.monthly_ctc) {
                var diff = Number(rec.monthly_ctc) - Number(prev.monthly_ctc);
                if (diff > 0) {
                    var pct = ((diff / Number(prev.monthly_ctc)) * 100).toFixed(1);
                    hike_html = "<div class='ep-sal-prog-hike-chip'>+" + pct + "%</div>";
                }
            }
            if (idx > 0) html += "<span class='ep-sal-prog-arrow'>&#8594;</span>";
            html += "<div class='ep-sal-prog-node'>";
            html += "<div class='ep-sal-prog-node-dot" + (is_current ? " current" : "") + "'></div>";
            html += "<div class='ep-sal-prog-node-amt'>&#8377;" + fmt_currency(rec.monthly_ctc) + "</div>";
            html += "<div class='ep-sal-prog-node-date'>" + (rec.from_date ? rec.from_date.slice(0, 7) : "—") + "</div>";
            html += hike_html + "</div>";
        });
        html += "</div></div></div>";
    }

    // Cancelled SSAs
    if (cancelled_ssas && cancelled_ssas.length) {
        html += "<div class='ep-ssa-cancelled-wrap'>";
        html += "<div class='ep-ssa-cancelled-header'>";
        html += "<span class='ep-ssa-cancelled-title'>Previous Assignments <span class='ep-ssa-cancelled-count'>" + cancelled_ssas.length + "</span></span>";
        html += "<span class='ep-ssa-toggle-icon'>&#9660;</span></div>";
        html += "<div class='ep-ssa-cancelled-list'>";
        cancelled_ssas.forEach(function (rec) {
            var dp = [];
            if (rec.from_date) dp.push(fmt_date_human(rec.from_date));
            dp.push(rec.to_date ? fmt_date_human(rec.to_date) : "—");
            var mp = [];
            if (rec.designation) mp.push(rec.designation);
            if (rec.department) mp.push(rec.department);
            html += "<div class='ep-ssa-cancelled-item'>";
            html += "<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;'>";
            html += "<a href='/app/salary-structure-assignment/" + encodeURIComponent(rec.name) + "' class='ep-ssa-cancelled-name' target='_blank'>" + rec.name + "</a>";
            html += "<span class='ep-ssa-cancelled-badge'>Cancelled</span></div>";
            html += "<div class='ep-ssa-cancelled-meta'><span>" + dp.join(" → ") + "</span>";
            if (mp.length) html += "<span>" + mp.join(" · ") + "</span>";
            html += "</div>";
            html += "<div class='ep-ssa-cancelled-ctc' style='margin:4px 0 6px;'>&#8377;" + fmt_currency(rec.monthly_ctc) + " <span style='font-size:10px;font-weight:400;color:var(--text-muted);'>/ mo CTC</span></div>";
            html += "<div style='display:grid;grid-template-columns:1fr 1fr;gap:4px;margin-bottom:8px;'>";
            html += "<div style='font-size:11px;color:var(--text-muted);'>Gross: <strong>&#8377;" + fmt_currency(rec.gross_salary) + "</strong></div>";
            html += "<div style='font-size:11px;color:var(--text-muted);'>Net: <strong>&#8377;" + fmt_currency(rec.net_salary) + "</strong></div>";
            html += "<div style='font-size:11px;color:var(--text-muted);'>Deductions: <strong>&#8377;" + fmt_currency(rec.total_deductions) + "</strong></div>";
            html += "<div style='font-size:11px;color:var(--text-muted);'>Employer: <strong>&#8377;" + fmt_currency(rec.total_employer_contribution) + "</strong></div>";
            html += "</div>";
            html += render_comp_toggles(
                rec.earnings || [],
                rec.deductions || [],
                rec.employer_share || []
            );
            html += "</div>";
        });
        html += "</div></div>";
    }

    return html;
}

// ── Component toggles — Earnings / Deductions / Employer Share ────────────────

function render_comp_toggles(earnings, deductions, employer_share) {
    if (!earnings.length && !deductions.length && !employer_share.length) return "";

    var html = "<div class='ep-comp-toggle-wrap'><div class='ep-comp-cols'>";

    // Earnings
    html += "<div class='ep-comp-section'>";
    if (earnings.length) {
        html += "<button class='ep-comp-toggle-btn earnings-btn'>";
        html += "<span class='ep-comp-btn-left'>Earnings <span class='ep-comp-btn-count'>" + earnings.length + "</span></span>";
        html += "<span class='ep-comp-chevron'>&#9660;</span></button>";
        html += "<div class='ep-comp-list'>";
        earnings.forEach(function (row) {
            html += "<div class='ep-comp-row'><span class='ep-comp-name'>" + (row.salary_component || "") + "</span>" +
                "<span class='ep-comp-amt earn'>&#8377;" + fmt_currency(row.amount) + "</span></div>";
        });
        html += "</div>";
    }
    html += "</div>";

    // Deductions
    html += "<div class='ep-comp-section'>";
    if (deductions.length) {
        html += "<button class='ep-comp-toggle-btn deductions-btn'>";
        html += "<span class='ep-comp-btn-left'>Deductions <span class='ep-comp-btn-count'>" + deductions.length + "</span></span>";
        html += "<span class='ep-comp-chevron'>&#9660;</span></button>";
        html += "<div class='ep-comp-list'>";
        deductions.forEach(function (row) {
            html += "<div class='ep-comp-row'><span class='ep-comp-name'>" + (row.salary_component || "") + "</span>" +
                "<span class='ep-comp-amt deduct'>&#8377;" + fmt_currency(row.amount) + "</span></div>";
        });
        html += "</div>";
    }
    html += "</div>";

    // Employer Share
    html += "<div class='ep-comp-section'>";
    if (employer_share.length) {
        html += "<button class='ep-comp-toggle-btn employer-btn'>";
        html += "<span class='ep-comp-btn-left'>Employer Share <span class='ep-comp-btn-count'>" + employer_share.length + "</span></span>";
        html += "<span class='ep-comp-chevron'>&#9660;</span></button>";
        html += "<div class='ep-comp-list'>";
        employer_share.forEach(function (row) {
            html += "<div class='ep-comp-row'><span class='ep-comp-name'>" + (row.salary_component || "") + "</span>" +
                "<span class='ep-comp-amt employer'>&#8377;" + fmt_currency(row.amount) + "</span></div>";
        });
        html += "</div>";
    }
    html += "</div>";

    html += "</div></div>";
    return html;
}

// ── Small helpers ─────────────────────────────────────────────────────────────

function ssa_breakdown_item(label, val) {
    return "<div class='ep-ssa-breakdown-item'><div class='ep-ssa-breakdown-label'>" + label + "</div><div class='ep-ssa-breakdown-val'>&#8377;" + fmt_currency(val) + "</div></div>";
}
function info_row(label, val) {
    return "<div class='ep-info-row'><div class='ep-info-label'>" + label + "</div><div class='ep-info-val'>" + val + "</div></div>";
}
function sal_item(label, val) {
    return "<div class='ep-salary-item'><div class='ep-salary-item-label'>" + label + "</div><div class='ep-salary-item-val'>&#8377;" + fmt_currency(val) + "</div></div>";
}
// ── Loan Ledger — main render ─────────────────────────────────────────────────
function render_loan_ledger_html(loan_ledger) {
    if (!loan_ledger || !loan_ledger.length) {
        return "<div class='ep-card'>" +
            "<div class='ep-title-area'><h4 class='ep-card-title'>💳 Loan Advance Ledger</h4></div>" +
            "<div class='ep-loan-empty'>No loans or advances found for this employee.</div>" +
            "</div>";
    }

    // Store original data for filtering
    window.original_loan_data = loan_ledger;

    // Separate loans and advances
    var all_loans = loan_ledger.filter(function (ln) {
        return (ln.loan_type || "").toLowerCase() !== "advance";
    });

    var all_advances = loan_ledger.filter(function (ln) {
        return (ln.loan_type || "").toLowerCase() === "advance";
    });

    // Create filter state if not exists (only for loans)
    if (!window.loan_filter_state) {
        window.loan_filter_state = {
            loans: "all"  // 'all', 'active', 'completed'
        };
    }

    // Compute overview totals for ACTIVE loans only
    var active_loans = all_loans.filter(function (ln) {
        return (ln.status || "").toLowerCase() === "active";
    });

    var active_total_borrowed = 0;
    var active_total_recovered = 0;
    var active_total_outstanding = 0;

    active_loans.forEach(function (ln) {
        active_total_borrowed += Number(ln.loan_amount || 0);
        active_total_recovered += Number(ln.total_recovered || 0);
        active_total_outstanding += Number(ln.outstanding || 0);
    });

    // Create main container HTML
    var main_html = "<div class='ep-card'>";
    main_html += "<div class='ep-title-area'>";
    main_html += "<h4 class='ep-card-title'>💳 Loan Advance Ledger</h4>";
    main_html += "</div>";
    main_html += "<div id='loan-ledger-container'>";

    // Overview strip — shows only ACTIVE loans summary
    main_html += "<div style='margin-bottom: 24px;'>";
    main_html += "<div style='font-size: 12px; font-weight: 600; color: var(--text-muted); margin-bottom: 8px;'>ACTIVE LOANS SUMMARY</div>";
    main_html += "<div class='ep-loan-overview'>";
    main_html += loan_ov_item("Total Borrowed", "&#8377;" + fmt_currency(active_total_borrowed), "blue");
    main_html += loan_ov_item("Total Recovered", "&#8377;" + fmt_currency(active_total_recovered), "green");
    main_html += loan_ov_item("Total Outstanding", "&#8377;" + fmt_currency(active_total_outstanding), "red");
    main_html += loan_ov_item("Active Loans", active_loans.length, "purple");
    main_html += "</div></div>";

    // LOANS SECTION with filter buttons (full width)
    main_html += "<div style='margin-bottom: 32px; width: 100%;'>";
    main_html += "<div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 10px;'>";
    main_html += "<div style='font-size: 14px; font-weight: 600; color: var(--text-color); border-left: 4px solid #1d4ed8; padding-left: 12px;'>💰 LOANS</div>";
    main_html += "<div style='display: flex; gap: 8px;' id='loans-filter-buttons'>";
    main_html += "<button data-filter='all' data-section='loans' class='ep-filter-btn " + (window.loan_filter_state.loans === 'all' ? 'active' : '') + "'>All Loans</button>";
    main_html += "<button data-filter='active' data-section='loans' class='ep-filter-btn " + (window.loan_filter_state.loans === 'active' ? 'active' : '') + "'>Active Only</button>";
    main_html += "<button data-filter='completed' data-section='loans' class='ep-filter-btn " + (window.loan_filter_state.loans === 'completed' ? 'active' : '') + "'>Completed Only</button>";
    main_html += "</div></div>";
    main_html += "<div id='loans-container' style='width: 100%;'></div>";
    main_html += "</div>";

    // ADVANCES SECTION (no filter buttons, full width)
    main_html += "<div style='margin-top: 16px; width: 100%;'>";
    main_html += "<div style='font-size: 14px; font-weight: 600; color: var(--text-color); margin-bottom: 12px; border-left: 4px solid #f59e0b; padding-left: 12px;'>💰 ADVANCES</div>";

    // Separate advances for display
    var active_advances = all_advances.filter(function (ln) {
        return (ln.status || "").toLowerCase() === "active";
    });

    var completed_advances = all_advances.filter(function (ln) {
        return (ln.status || "").toLowerCase() === "completed";
    });

    // Sort by date (recent first)
    active_advances.sort(function (a, b) {
        return new Date(b.start_date) - new Date(a.start_date);
    });
    completed_advances.sort(function (a, b) {
        return new Date(b.start_date) - new Date(a.start_date);
    });

    if (active_advances.length > 0) {
        main_html += "<div style='margin-bottom: 20px;'>";
        main_html += "<div style='font-size: 12px; font-weight: 500; color: #16a34a; margin-bottom: 8px;'>Active Advances</div>";
        main_html += "<div class='ep-loan-grid'>";
        active_advances.forEach(function (ln) {
            main_html += render_loan_card_html(ln);
        });
        main_html += "</div></div>";
    }

    if (completed_advances.length > 0) {
        main_html += "<div style='margin-top: 16px;'>";
        main_html += "<div style='font-size: 12px; font-weight: 500; color: var(--text-muted); margin-bottom: 8px;'>Completed Advances</div>";
        main_html += "<div class='ep-loan-grid'>";
        completed_advances.forEach(function (ln) {
            main_html += render_loan_card_html(ln);
        });
        main_html += "</div></div>";
    }

    if (active_advances.length === 0 && completed_advances.length === 0) {
        main_html += "<div class='ep-loan-empty'>No advances found.</div>";
    }
    main_html += "</div>";

    main_html += "</div>"; // Close loan-ledger-container
    main_html += "</div>"; // Close ep-card

    return main_html;
}

// Function to render filtered loans (full width)
function render_filtered_loans() {
    var all_loans = window.original_loan_data.filter(function (ln) {
        return (ln.loan_type || "").toLowerCase() !== "advance";
    });

    var filter = window.loan_filter_state.loans;
    var filtered_loans = [];

    if (filter === "active") {
        filtered_loans = all_loans.filter(function (ln) {
            return (ln.status || "").toLowerCase() === "active";
        });
    } else if (filter === "completed") {
        filtered_loans = all_loans.filter(function (ln) {
            return (ln.status || "").toLowerCase() === "completed";
        });
    } else {
        filtered_loans = all_loans;
    }

    // Separate active and completed for display
    var active_loans = filtered_loans.filter(function (ln) {
        return (ln.status || "").toLowerCase() === "active";
    });

    var completed_loans = filtered_loans.filter(function (ln) {
        return (ln.status || "").toLowerCase() === "completed";
    });

    // Sort by date (recent first)
    active_loans.sort(function (a, b) {
        return new Date(b.start_date) - new Date(a.start_date);
    });
    completed_loans.sort(function (a, b) {
        return new Date(b.start_date) - new Date(a.start_date);
    });

    var html = "";

    if (active_loans.length > 0) {
        html += "<div style='margin-bottom: 20px;'>";
        html += "<div style='font-size: 12px; font-weight: 500; color: #16a34a; margin-bottom: 8px;'>Active Loans</div>";
        html += "<div class='ep-loan-grid'>";
        active_loans.forEach(function (ln) {
            html += render_loan_card_html(ln);
        });
        html += "</div></div>";
    }

    if (completed_loans.length > 0) {
        html += "<div style='margin-top: 16px;'>";
        html += "<div style='font-size: 12px; font-weight: 500; color: var(--text-muted); margin-bottom: 8px;'>Completed Loans</div>";
        html += "<div class='ep-loan-grid'>";
        completed_loans.forEach(function (ln) {
            html += render_loan_card_html(ln);
        });
        html += "</div></div>";
    }

    if (active_loans.length === 0 && completed_loans.length === 0) {
        html += "<div class='ep-loan-empty'>No loans found for selected filter.</div>";
    }

    $("#loans-container").html(html);
}

// Function to render advances (no filters needed, but kept for compatibility)
function render_filtered_advances() {
    // This function is kept for compatibility but advances are rendered directly in the main HTML
    // No filtering needed for advances
    var all_advances = window.original_loan_data.filter(function (ln) {
        return (ln.loan_type || "").toLowerCase() === "advance";
    });

    var active_advances = all_advances.filter(function (ln) {
        return (ln.status || "").toLowerCase() === "active";
    });

    var completed_advances = all_advances.filter(function (ln) {
        return (ln.status || "").toLowerCase() === "completed";
    });

    active_advances.sort(function (a, b) {
        return new Date(b.start_date) - new Date(a.start_date);
    });
    completed_advances.sort(function (a, b) {
        return new Date(b.start_date) - new Date(a.start_date);
    });

    var html = "";

    if (active_advances.length > 0) {
        html += "<div style='margin-bottom: 20px;'>";
        html += "<div style='font-size: 12px; font-weight: 500; color: #16a34a; margin-bottom: 8px;'>Active Advances</div>";
        html += "<div class='ep-loan-grid'>";
        active_advances.forEach(function (ln) {
            html += render_loan_card_html(ln);
        });
        html += "</div></div>";
    }

    if (completed_advances.length > 0) {
        html += "<div style='margin-top: 16px;'>";
        html += "<div style='font-size: 12px; font-weight: 500; color: var(--text-muted); margin-bottom: 8px;'>Completed Advances</div>";
        html += "<div class='ep-loan-grid'>";
        completed_advances.forEach(function (ln) {
            html += render_loan_card_html(ln);
        });
        html += "</div></div>";
    }

    if (active_advances.length === 0 && completed_advances.length === 0) {
        html += "<div class='ep-loan-empty'>No advances found.</div>";
    }

    $("#advances-container").html(html);
}
// Helper function to render individual loan/advance card
function render_loan_card_html(ln) {
    var is_active = (ln.status || "").toLowerCase() === "active";
    var status_label = ln.status || "Unknown";
    var status_cls = is_active ? "active"
        : status_label.toLowerCase() === "completed" ? "completed" : "pending";

    var is_advance = (ln.loan_type || "").toLowerCase() === "advance";
    var pct = Number(ln.pct_recovered || 0);

    var html = "<div class='ep-loan-card" + (is_active ? " active-loan" : "") + "' data-loan-name='" + ln.name + "'>";

    // Card header
    html += "<div class='ep-loan-card-header' style='cursor: pointer;'>";
    html += "<div class='ep-loan-card-header-left'>";
    html += "<span class='ep-loan-card-id'>" + ln.name + "</span>";
    html += "<span class='ep-loan-type-badge'>" + (ln.loan_type || "Loan") + "</span>";
    if (!is_advance && ln.frequency)
        html += "<span style='font-size:11px;color:var(--text-muted);'>" + ln.frequency + "</span>";
    if (ln.start_date)
        html += "<span style='font-size:11px;color:var(--text-muted);'>&#128197; Taken: " + fmt_date_human(ln.start_date) + "</span>";
    html += "</div>";
    html += "<div class='ep-loan-card-header-right'>";
    html += "<span class='ep-loan-card-amount'>&#8377;" + fmt_currency(ln.loan_amount) + "</span>";
    html += "<span class='ep-loan-status-badge " + status_cls + "'>" + status_label + "</span>";
    html += "<span class='ep-loan-chev' style='display: inline-block; transition: transform 0.2s;'>&#9660;</span>";
    html += "</div></div>";

    // Progress bar
    html += "<div class='ep-loan-progress-wrap'>";
    html += "<div class='ep-loan-progress-meta'>";
    html += "<span>Recovered: <strong>&#8377;" + fmt_currency(ln.total_recovered) + "</strong></span>";
    html += "<span>Outstanding: <strong style='color:#dc2626;'>&#8377;" + fmt_currency(ln.outstanding) + "</strong></span>";
    html += "<span style='color:#16a34a;font-weight:700;'>" + pct + "% repaid</span>";
    html += "</div>";
    html += "<div class='ep-loan-progress-bar-bg'><div class='ep-loan-progress-bar-fill' style='width:" + Math.min(pct, 100) + "%'></div></div>";
    html += "</div>";

    // Expandable body - initially hidden
    html += "<div class='ep-loan-card-body' style='display: none;'>";

    if (is_advance) {
        // ADVANCE DISPLAY
        html += "<div class='ep-loan-body-stats' style='grid-template-columns: repeat(3, 1fr);'>";
        html += loan_body_stat("Advance Amount", "&#8377;" + fmt_currency(ln.loan_amount));
        html += loan_body_stat("Status", ln.is_deducted ? "Deducted" : "Pending");
        html += loan_body_stat("Taken On", ln.start_date ? fmt_date_human(ln.start_date) : "—");
        html += "</div>";
    } else {
        // LOAN DISPLAY - Keep original layout
        html += "<div class='ep-loan-body-stats'>";
        html += loan_body_stat("Loan Amount", "&#8377;" + fmt_currency(ln.loan_amount));
        html += loan_body_stat("Installment Amount", "&#8377;" + fmt_currency(ln.monthly_deduction || 0));
        html += loan_body_stat("Tenure Months", ln.tenure_display || (ln.tenure_months ? ln.tenure_months + " months" : "—"));
        html += loan_body_stat("Frequency", ln.frequency || "—");
        html += loan_body_stat("Taken On", ln.start_date ? fmt_date_human(ln.start_date) : "—");
        html += "</div>";

        // Schedule tabs for loans
        html += render_loan_schedule_tabs(ln.schedule || [], ln.loan_amount);
    }

    html += "</div>"; // .ep-loan-card-body
    html += "</div>"; // .ep-loan-card

    return html;
}

// Helper function to escape HTML special characters
function escapeHtml(str) {
    if (!str) return "";
    return str
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
// Helper function to attach event handlers for loan cards
function attach_loan_card_events($container) {
    // Loan card expansion - using slideToggle for smooth animation
    $container.find(".ep-loan-card-header").off("click").on("click", function (e) {
        e.stopPropagation();
        var $header = $(this);
        var $card = $header.closest(".ep-loan-card");
        var $body = $card.find(".ep-loan-card-body");
        var $chev = $header.find(".ep-loan-chev");

        // Toggle the body visibility with slide animation
        if ($body.is(":visible")) {
            $body.slideUp(200);
            $chev.css("transform", "rotate(0deg)");
        } else {
            $body.slideDown(200);
            $chev.css("transform", "rotate(180deg)");
        }
    });

    // Loan schedule tab switching
    $container.find(".ep-loan-tab-btn").off("click").on("click", function (e) {
        e.stopPropagation();
        var $btn = $(this);
        var $wrap = $btn.closest(".ep-loan-tabs-wrap");
        $wrap.find(".ep-loan-tab-btn").removeClass("active");
        $btn.addClass("active");
        var target = $btn.data("tab");
        $wrap.find(".ep-loan-tab-panel").removeClass("active");
        $wrap.find("[data-tab='" + target + "'].ep-loan-tab-panel").addClass("active");
    });
}

// ── Loan schedule tabs ────────────────────────────────────────────────────────
function render_loan_schedule_tabs(schedule, loan_amount) {
    if (!schedule.length) {
        return "<div style='padding:16px;font-size:12px;color:var(--text-muted);'>No repayment schedule found.</div>";
    }

    var all = schedule;
    var pending = schedule.filter(function (r) { return r.status === "Pending"; });
    var deferred = schedule.filter(function (r) { return r.status === "Deferred"; });
    var deducted = schedule.filter(function (r) { return r.status === "Deducted"; });

    var html = "<div class='ep-loan-tabs-wrap'>";
    html += "<div class='ep-loan-tabs-nav'>";
    html += loan_tab_btn("all", "All", all.length, true);
    html += loan_tab_btn("pending", "Pending", pending.length, false);
    html += loan_tab_btn("deferred", "Deferred", deferred.length, false);
    html += loan_tab_btn("deducted", "Deducted", deducted.length, false);
    html += "</div>";

    html += loan_tab_panel("all", all, loan_amount, true);
    html += loan_tab_panel("pending", pending, loan_amount, false);
    html += loan_tab_panel("deferred", deferred, loan_amount, false);
    html += loan_tab_panel("deducted", deducted, loan_amount, false);

    html += "</div>";
    return html;
}

// ── Schedule table ────────────────────────────────────────────────────────────
function render_loan_schedule_table(rows, loan_amount) {
    if (!rows.length) {
        return "<div style='padding:12px;text-align:center;font-size:12px;color:var(--text-muted);'>No entries in this filter.</div>";
    }

    var cumulative = 0;
    var html = "<div style='max-height:280px;overflow-y:auto;'>";
    html += "<table class='ep-loan-schedule-table'><thead><tr>";
    html += "<th>#</th><th>Month</th><th>Base EMI</th><th>Deducted</th><th>Status</th><th>Deferred To</th>";
    html += "</tr></thead><tbody>";

    rows.forEach(function (row, idx) {
        var deducted_amt = Number(row.actual_deducted || 0);
        if (row.status === "Deducted") cumulative += deducted_amt;

        var status_cls = row.status === "Deducted" ? "deducted"
            : row.status === "Deferred" ? "deferred" : "pending";
        var status_icon = row.status === "Deducted" ? "✓"
            : row.status === "Deferred" ? "↪" : "⌛";

        // Format deferred_to to show only month and year (remove day)
        var deferred_display = "—";
        if (row.deferred_to) {
            if (row.deferred_to.includes('-')) {
                var date_parts = row.deferred_to.split('-');
                if (date_parts.length === 3) {
                    var deferred_date = new Date(row.deferred_to);
                    if (!isNaN(deferred_date.getTime())) {
                        deferred_display = deferred_date.toLocaleDateString("en-IN", { month: "long", year: "numeric" });
                    } else {
                        deferred_display = row.deferred_to;
                    }
                } else {
                    deferred_display = row.deferred_to;
                }
            } else {
                deferred_display = row.deferred_to;
            }
        }

        html += "<tr>";
        html += "<td style='color:var(--text-muted);font-size:11px;'>" + (idx + 1) + "</td>";
        html += "<td style='font-weight:500;'>" + (row.month || "—") + "</td>";
        html += "<td>₹" + fmt_currency(row.base_emi) + "</td>";
        html += "<td>₹" + fmt_currency(row.actual_deducted) + "</td>";
        html += "<td><span class='ep-sched-status " + status_cls + "'>" + status_icon + " " + (row.status || "Pending") + "</span></td>";
        html += "<td style='font-size:11px;color:" + (row.deferred_to ? "#dc2626" : "var(--text-muted)") + ";'>" +
            (row.deferred_to ? "→ " + deferred_display : "—") + "</td>";
        html += "</tr>";
    });

    html += "</tbody></table></div>";
    return html;
}

// ── Small helpers (loan) ──────────────────────────────────────────────────────
function loan_ov_item(label, val, color_cls) {
    return "<div class='ep-loan-ov-item'>" +
        "<div class='ep-loan-ov-label'>" + label + "</div>" +
        "<div class='ep-loan-ov-val " + color_cls + "'>" + val + "</div>" +
        "</div>";
}

function loan_body_stat(label, val) {
    return "<div class='ep-loan-body-stat'>" +
        "<div class='ep-loan-body-stat-label'>" + label + "</div>" +
        "<div class='ep-loan-body-stat-val'>" + val + "</div>" +
        "</div>";
}

function loan_tab_btn(tab, label, count, active) {
    return "<button class='ep-loan-tab-btn" + (active ? " active" : "") + "' data-tab='" + tab + "'>" +
        label + "<span class='ep-tab-count'>" + count + "</span></button>";
}

function loan_tab_panel(tab, rows, loan_amount, active) {
    return "<div class='ep-loan-tab-panel" + (active ? " active" : "") + "' data-tab='" + tab + "'>" +
        render_loan_schedule_table(rows, loan_amount) +
        "</div>";
}