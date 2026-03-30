frappe.pages["employee-profile"].on_page_load = function(wrapper) {
    frappe.ui.make_app_page({ parent: wrapper, title: "Employee Profile" });
    inject_ep_styles();
};

frappe.pages["employee-profile"].on_page_show = function(wrapper) {
    var route = frappe.get_route();
    var emp = route[1];
    if (!emp) { return; }

    var $sidebar = $(wrapper).find(".layout-side-section");
    var $main    = $(wrapper).find(".layout-main-section");

    $main.html(render_skeleton());

    frappe.call({
        method: "saral_hr.saral_hr.page.employee_profile.employee_profile.get_employee_profile_data",
        args: { employee: emp },
        callback: function(r) {
            if (r.message) {
                ep_fix_breadcrumbs(r.message.employee || emp);
                $(wrapper).find(".title-text").text(r.message.employee || "Employee Profile");
                render_profile($sidebar, $main, r.message, emp);
            } else {
                render_error($main, "No data returned for this employee.");
            }
        },
        error: function() {
            render_error($main, "Failed to load employee profile. Please try again.");
        }
    });
};

function render_skeleton() {
    var pulse = "animation:ep-pulse 1.5s ease-in-out infinite;";
    var box = function(w, h, r) {
        return "<div style='background:#e5e7eb;border-radius:" + (r||"6px") + ";width:" + w + ";height:" + h + ";margin-bottom:10px;" + pulse + "'></div>";
    };
    var html = "<div style='padding:20px;'>";
    html += "<div style='background:#fff;border:1px solid #f3f4f6;border-radius:8px;padding:20px;margin-bottom:15px;'>";
    html += box("120px","14px") + "<div style='display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;'>";
    for (var i = 0; i < 6; i++) html += "<div>" + box("60px","10px") + box("80px","18px","4px") + "</div>";
    html += "</div></div>";
    html += "<div style='background:#fff;border:1px solid #f3f4f6;border-radius:8px;padding:20px;margin-bottom:15px;'>";
    html += box("160px","14px") + box("100%","120px","6px");
    html += "</div>";
    html += "<div style='background:#fff;border:1px solid #f3f4f6;border-radius:8px;padding:20px;'>";
    html += box("140px","14px");
    for (var j = 0; j < 2; j++) html += "<div style='margin-left:40px;'>" + box("200px","12px") + box("140px","10px") + "</div>";
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
    return d.toLocaleDateString("en-IN", { day:"numeric", month:"short", year:"numeric" });
}

function days_ago(date_str) {
    if (!date_str) return null;
    var days = Math.floor((Date.now() - new Date(date_str).getTime()) / 86400000);
    if (days === 0) return "today";
    if (days === 1) return "1 day ago";
    if (days < 30)  return days + " days ago";
    var months = Math.floor(days / 30);
    if (months < 12) return months + " mo ago";
    var yrs = Math.floor(months / 12), mos = months % 12;
    return yrs + "yr" + (mos ? " " + mos + "mo" : "") + " ago";
}

function calc_duration(start_str, end_str) {
    if (!start_str) return null;
    var end   = end_str ? new Date(end_str) : new Date();
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
    "Present":          "present",
    "Absent":           "absent",
    "Half Day":         "halfday",
    "LWP":              "lwp",
    "Holiday":          "holiday",
    "Weekly Off":       "weeklyoff",
    "Earned Leave":     "earnedleave",
    "Casual Leave":     "casualleave",
    "On Tour":          "ontour",
    "Comp Off":         "compoff",
    "Earned Comp Off":  "earnedcompoff"
};
var STATUS_HEX = {
    "present":       "#16a34a",
    "absent":        "#dc2626",
    "halfday":       "#ca8a04",
    "lwp":           "#ea580c",
    "holiday":       "#2563eb",
    "weeklyoff":     "#9333ea",
    "earnedleave":   "#0d9488",
    "casualleave":   "#db2777",
    "ontour":        "#16a34a",
    "compoff":       "#9333ea",
    "earnedcompoff": "#14b8a6"
};
var MONTH_NAMES = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

// ── Main render ───────────────────────────────────────────────────────────────

function render_profile($sidebar, $main, d, emp) {
    var s  = d.salary || {};
    var c  = d.company_link || {};
    var att_map        = d.attendance_map || {};
    var years          = d.years || [];
    var timeline       = d.timeline || [];
    var latest_ssa     = d.latest_ssa || null;
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
    if (c.company)         sb += info_row("Company",     c.company);
    if (c.branch)          sb += info_row("Branch",      c.branch);
    if (c.category)        sb += info_row("Category",    c.category);
    if (c.date_of_joining) sb += info_row("Joined",      fmt_date_human(c.date_of_joining));
    if (c.department)      sb += info_row("Department",  c.department);
    if (c.designation)     sb += info_row("Designation", c.designation);
    if (d.tenure)          sb += info_row("Tenure",      d.tenure);
    if (c.immediate_reporting_name) sb += info_row("Immediate Reporting", c.immediate_reporting_name);
    if (c.final_reporting_name)     sb += info_row("Final Reporting",     c.final_reporting_name);
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
    main += sal_item("Monthly CTC",           s.monthly_ctc);
    main += sal_item("Annual CTC",            s.annual_ctc);
    main += sal_item("Gross Salary",          s.gross_salary);
    main += sal_item("Net Salary",            s.net_salary);
    main += sal_item("Total Deductions",      s.total_deductions);
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
    var now       = new Date();
    var cur_year  = now.getFullYear();
    var cur_month = now.getMonth() + 1;

    main += "<div class='ep-card'>";
    main += "<div class='ep-title-area'><h4 class='ep-card-title'>Attendance Overview</h4>";
    main += "<div style='display:flex;gap:8px;align-items:center;'>";
    main += "<button class='ep-today-btn' id='ep-today-btn'>Today</button>";
    main += "<select class='ep-year-select' id='ep-year-select'>";
    years.forEach(function(yr) {
        main += "<option value='" + yr + "'" + (String(yr) === String(cur_year) ? " selected" : "") + ">" + yr + "</option>";
    });
    main += "</select></div></div>";
    main += "<div id='ep-heatmap-wrap'></div></div>";

    // Timeline + SSA
    main += "<div class='ep-card'>";
    main += "<div class='ep-title-area'><h4 class='ep-card-title'>Employee Timeline</h4></div>";
    main += "<div class='ep-timeline-ssa-wrap'>";
    main += "<div>" + render_timeline_html(timeline) + "</div>";
    main += "<div class='ep-ssa-panel'>" + render_ssa_panel_html(latest_ssa, cancelled_ssas, c) + "</div>";
    main += "</div></div>";

    $main.html(main);

    render_heatmap($main, att_map, cur_year, cur_month);

    $main.find("#ep-year-select").on("change", function() {
        var yr = parseInt($(this).val());
        var active_btn = $main.find(".ep-month-label-btn.active");
        var active_month = active_btn.length ? parseInt(active_btn.data("month")) : "all";
        render_heatmap($main, att_map, yr, active_month);
    });

    $main.find("#ep-heatmap-wrap").on("click", ".ep-month-label-btn", function() {
        var clicked = parseInt($(this).data("month"));
        var yr = parseInt($main.find("#ep-year-select").val());
        render_heatmap($main, att_map, yr, $(this).hasClass("active") ? "all" : clicked);
    });

    $main.find("#ep-today-btn").on("click", function() {
        var n = new Date();
        $main.find("#ep-year-select").val(n.getFullYear());
        render_heatmap($main, att_map, n.getFullYear(), n.getMonth() + 1);
    });

    $main.on("mouseenter", ".ep-day:not(.empty)", function(e) {
        var title = $(this).attr("title") || "";
        if (!title) return;
        var colon = title.indexOf(": ");
        var date_part   = colon > -1 ? title.slice(0, colon) : title;
        var status_part = colon > -1 ? title.slice(colon + 2) : "";
        var cls = ($(this).attr("class") || "").split(" ").find(function(c) { return STATUS_HEX[c]; }) || "";
        var color = STATUS_HEX[cls] || "#6b7280";
        var tip = document.getElementById("ep-tooltip");
        tip.innerHTML =
            "<div class='ep-tooltip-date'>" + fmt_date_human(date_part) + "</div>" +
            "<div><span class='ep-tooltip-dot' style='background:" + color + "'></span>" +
            (status_part || "No Record") + "</div>";
        tip.classList.add("visible");
        move_tooltip(e);
    });
    $main.on("mousemove",  ".ep-day:not(.empty)", function(e) { move_tooltip(e); });
    $main.on("mouseleave", ".ep-day", function() {
        document.getElementById("ep-tooltip").classList.remove("visible");
    });

    $main.on("click", ".ep-ssa-cancelled-header", function() {
        $(this).next(".ep-ssa-cancelled-list").toggleClass("open");
        $(this).find(".ep-ssa-toggle-icon").toggleClass("open");
    });
    $main.on("click", ".ep-sal-prog-header", function() {
        $(this).next(".ep-sal-prog-body").toggleClass("open");
        $(this).find(".ep-ssa-toggle-icon").toggleClass("open");
    });
    $main.on("click", ".ep-comp-toggle-btn", function() {
        var $section = $(this).closest(".ep-comp-section");
        var $list    = $section.find(".ep-comp-list");
        var $chev    = $(this).find(".ep-comp-chevron");
        $list.toggleClass("open");
        $chev.toggleClass("open");
    });
}

function move_tooltip(e) {
    var tip = document.getElementById("ep-tooltip");
    var x = e.clientX + 14, y = e.clientY - 10;
    if (x + 170 > window.innerWidth) x = e.clientX - 170;
    tip.style.left = x + "px";
    tip.style.top  = y + "px";
}

// ── Heatmap ───────────────────────────────────────────────────────────────────

function render_heatmap($w, att_map, year, active_month) {
    year = parseInt(year);
    active_month = active_month || "all";
    var today_str = new Date().toISOString().split("T")[0];

    // All counters — now includes earned_comp_off
    var summary = {
        present:0, absent:0, half_day:0, lwp:0,
        holiday:0, weekly_off:0, earned_leave:0, casual_leave:0,
        on_tour:0, comp_off:0, earned_comp_off:0
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

        weeks.forEach(function(wk) {
            inner += "<div class='ep-week-col'>";
            wk.forEach(function(d) {
                if (!d) { inner += "<div class='ep-day empty'></div>"; return; }
                var day_str = year + "-" + month_str + "-" + String(d).padStart(2, "0");
                var status  = att_map[day_str] || null;
                var cls, title_attr;
                if (day_str > today_str) {
                    cls = "ep-day future"; title_attr = day_str + " (future)";
                } else if (status) {
                    var ccls = STATUS_COLORS[status] || "future";
                    cls = "ep-day " + ccls;
                    title_attr = day_str + ": " + status;
                    if (selected_month === null || selected_month === month_num) {
                        if      (status === "Present")          { summary.present++;       total_counted++; }
                        else if (status === "Absent")           { summary.absent++;        total_counted++; }
                        else if (status === "Half Day")         { summary.half_day++;      total_counted++; }
                        else if (status === "LWP")              { summary.lwp++;           total_counted++; }
                        else if (status === "Holiday")          { summary.holiday++;       total_counted++; }
                        else if (status === "Weekly Off")       { summary.weekly_off++;    total_counted++; }
                        else if (status === "Earned Leave")     { summary.earned_leave++;  total_counted++; }
                        else if (status === "Casual Leave")     { summary.casual_leave++;  total_counted++; }
                        else if (status === "On Tour")          { summary.on_tour++;       total_counted++; }
                        else if (status === "Comp Off")         { summary.comp_off++;      total_counted++; }
                        else if (status === "Earned Comp Off")  { summary.earned_comp_off++; total_counted++; }
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
        ["present","Present"],["absent","Absent"],["halfday","Half Day"],
        ["lwp","LWP"],["holiday","Holiday"],["weeklyoff","Weekly Off"],
        ["earnedleave","Earned Leave"],["casualleave","Casual Leave"],
        ["ontour","On Tour"],["compoff","Comp Off"],["earnedcompoff","Earned Comp Off"],
        ["future","No Record"]
    ];
    var legend = "<div class='ep-legend'>";
    legend_items.forEach(function(li) {
        legend += "<div class='ep-legend-item'><div class='ep-legend-dot " + li[0] + "'></div><span class='ep-legend-label " + li[0] + "'>" + li[1] + "</span></div>";
    });
    legend += "</div>";

    // Summary boxes — updated to include Earned Comp Off, now 6 columns
    var boxes = [
        [summary.present,          "Present",          "#16a34a", true],
        [summary.absent,           "Absent",           "#dc2626", true],
        [summary.on_tour,          "On Tour",          "#16a34a", false],
        [summary.earned_comp_off,  "Earned Comp Off",  "#14b8a6", false],
        [summary.half_day,         "Half Day",         "#ca8a04", false],
        [summary.lwp,              "LWP",              "#ea580c", false],
        [summary.holiday,          "Holiday",          "#2563eb", false],
        [summary.weekly_off,       "Weekly Off",       "#9333ea", false],
        [summary.earned_leave,     "Earned Leave",     "#0d9488", false],
        [summary.casual_leave,     "Casual Leave",     "#db2777", false],
        [summary.comp_off,         "Comp Off",         "#9333ea", false]
    ];
    var summ = "<div class='ep-att-summary'>";
    boxes.forEach(function(b) {
        var pct_html = (b[3] && total_counted > 0)
            ? "<div class='ep-att-pct' style='color:" + b[2] + "'>" + Math.round((b[0]/total_counted)*100) + "%</div>"
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
    timeline.forEach(function(item) {
        var active_cls = item.is_active == 1 ? " tl-active" : "";
        var date_html = "";
        if (item.start_date) date_html += "<div class='ep-tl-date'><strong>Start:</strong> " + fmt_date_human(item.start_date) + "</div>";
        if (item.end_date)   date_html += "<div class='ep-tl-date'><strong>End:</strong> "   + fmt_date_human(item.end_date) + "</div>";
        var meta_parts = [];
        if (item.designation) meta_parts.push(item.designation);
        if (item.department)  meta_parts.push(item.department);
        if (item.branch)      meta_parts.push(item.branch);
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
        var department  = latest_ssa.department  || (company_link && company_link.department)  || "";

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
            if (department)  mp.push(department);
            html += "<div class='ep-ssa-designation'>" + mp.join(" · ") + "</div>";
        }
        html += "<div class='ep-ssa-ctc-row'>";
        html += "<span class='ep-ssa-ctc-val'>&#8377;" + fmt_currency(latest_ssa.monthly_ctc) + "</span>";
        html += "<span class='ep-ssa-ctc-label'>/ month (CTC)</span></div>";
        html += "<div class='ep-ssa-breakdown'>";
        html += ssa_breakdown_item("Gross Salary",     latest_ssa.gross_salary);
        html += ssa_breakdown_item("Net Salary",       latest_ssa.net_salary);
        html += ssa_breakdown_item("Total Deductions", latest_ssa.total_deductions);
        html += ssa_breakdown_item("Employer Contrib", latest_ssa.total_employer_contribution);
        html += "</div>";

        html += render_comp_toggles(
            latest_ssa.earnings       || [],
            latest_ssa.deductions     || [],
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
    if (cancelled_ssas && cancelled_ssas.length) cancelled_ssas.forEach(function(r) { all_ssas.push(r); });
    if (latest_ssa) all_ssas.unshift(latest_ssa);

    if (all_ssas.length > 1) {
        var ordered = all_ssas.slice().reverse();
        html += "<div class='ep-salary-progression'>";
        html += "<div class='ep-sal-prog-header'><span class='ep-sal-prog-title'>📈 Salary Progression</span><span class='ep-ssa-toggle-icon'>&#9660;</span></div>";
        html += "<div class='ep-sal-prog-body'><div class='ep-sal-prog-track'>";
        ordered.forEach(function(rec, idx) {
            var is_current = latest_ssa && rec.name === latest_ssa.name;
            var prev = idx > 0 ? ordered[idx-1] : null;
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
            html += "<div class='ep-sal-prog-node-date'>" + (rec.from_date ? rec.from_date.slice(0,7) : "—") + "</div>";
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
        cancelled_ssas.forEach(function(rec) {
            var dp = [];
            if (rec.from_date) dp.push(fmt_date_human(rec.from_date));
            dp.push(rec.to_date ? fmt_date_human(rec.to_date) : "—");
            var mp = [];
            if (rec.designation) mp.push(rec.designation);
            if (rec.department)  mp.push(rec.department);
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
                rec.earnings       || [],
                rec.deductions     || [],
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
        earnings.forEach(function(row) {
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
        deductions.forEach(function(row) {
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
        employer_share.forEach(function(row) {
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