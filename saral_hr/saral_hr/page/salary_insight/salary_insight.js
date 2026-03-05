frappe.pages["salary-insight"].on_page_load = function (wrapper) {
    frappe.ui.make_app_page({ parent: wrapper, title: "Salary Insight" });
    inject_pp_styles();
};

frappe.pages["salary-insight"].on_page_show = function (wrapper) {
    var $main = $(wrapper).find(".layout-main-section");
    render_shell($main);
    load_companies($main);
};

// ─── Styles — Frappe native feel ─────────────────────────────────────────────
function inject_pp_styles() {
    if (document.getElementById("si-styles")) return;
    var s = document.createElement("style");
    s.id = "si-styles";
    s.innerHTML = `
        .layout-main-section {
            padding-left: 0 !important;
            padding-right: 0 !important;
        }

        /* Hide empty sidebar to reclaim full width */
        .layout-side-section:empty,
        .layout-side-section { display: none !important; }
        .layout-main-section-wrapper { width: 100% !important; }

        .pp-root {
            padding: 0 20px 40px 20px;
            font-family: var(--font-stack);
            color: var(--text-color);
        }

        /* ── Filter bar ── */
        .pp-filter-bar {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 16px 0 20px;
            flex-wrap: wrap;
        }
        .pp-filter-label {
            font-size: 12px;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.06em;
            margin-right: 4px;
        }
        .pp-select {
            border: 1px solid var(--border-color);
            background: var(--control-bg);
            color: var(--text-color);
            padding: 5px 10px;
            border-radius: var(--border-radius);
            font-size: 13px;
            font-family: var(--font-stack);
            outline: none;
            cursor: pointer;
            min-width: 120px;
            height: 30px;
            transition: border-color 0.15s;
        }
        .pp-select:focus, .pp-select:hover {
            border-color: var(--primary);
        }
        .pp-btn {
            height: 30px;
            padding: 0 14px;
            background: var(--primary);
            color: #fff;
            border: none;
            border-radius: var(--border-radius);
            font-size: 12px;
            font-weight: 600;
            font-family: var(--font-stack);
            cursor: pointer;
            transition: opacity 0.15s;
            white-space: nowrap;
        }
        .pp-btn:hover { opacity: 0.88; }

        /* ── Loading ── */
        .pp-loading {
            text-align: center;
            padding: 60px 0;
            color: var(--text-muted);
            font-size: 13px;
        }

        /* ── KPI strip ── */
        .pp-kpi-strip {
            display: grid;
            grid-template-columns: repeat(6, 1fr);
            gap: 12px;
            margin-bottom: 20px;
        }
        @media (max-width: 1200px) { .pp-kpi-strip { grid-template-columns: repeat(3, 1fr); } }
        @media (max-width: 700px)  { .pp-kpi-strip { grid-template-columns: repeat(2, 1fr); } }

        .pp-kpi {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: var(--border-radius-lg);
            padding: 16px 18px;
            position: relative;
            overflow: hidden;
        }
        .pp-kpi::after {
            content: '';
            position: absolute;
            bottom: 0; left: 0; right: 0;
            height: 3px;
            border-radius: 0 0 var(--border-radius-lg) var(--border-radius-lg);
        }
        .pp-kpi.k-total::after     { background: var(--blue-500, #5e64ff); }
        .pp-kpi.k-generated::after { background: var(--yellow-500, #f0a500); }
        .pp-kpi.k-submitted::after { background: var(--green-500, #28a745); }
        .pp-kpi.k-draft::after     { background: var(--orange-500, #f97316); }
        .pp-kpi.k-pending::after   { background: var(--red-500, #e03131); }
        .pp-kpi.k-cancelled::after { background: var(--gray-400, #adb5bd); }

        .pp-kpi-icon {
            font-size: 18px;
            margin-bottom: 8px;
            line-height: 1;
        }
        .pp-kpi-val {
            font-size: 28px;
            font-weight: 700;
            line-height: 1;
            margin-bottom: 4px;
            color: var(--text-color);
        }
        .pp-kpi.k-total .pp-kpi-val     { color: var(--blue-500, #5e64ff); }
        .pp-kpi.k-generated .pp-kpi-val { color: var(--yellow-600, #d97706); }
        .pp-kpi.k-submitted .pp-kpi-val { color: var(--green-600, #1a7431); }
        .pp-kpi.k-draft .pp-kpi-val     { color: var(--orange-500, #f97316); }
        .pp-kpi.k-pending .pp-kpi-val   { color: var(--red-500, #e03131); }
        .pp-kpi.k-cancelled .pp-kpi-val { color: var(--gray-500, #8d99a6); }

        .pp-kpi-label {
            font-size: 11px;
            color: var(--text-muted);
            font-weight: 500;
        }

        /* ── Section heading ── */
        .pp-section-heading {
            font-size: 14px;
            font-weight: 600;
            color: var(--text-color);
            margin: 0 0 14px;
            padding-bottom: 10px;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .pp-section-heading .pp-muted {
            font-size: 11px;
            color: var(--text-muted);
            font-weight: 400;
        }

        /* ── Card ── */
        .pp-card {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: var(--border-radius-lg);
            padding: 20px;
            margin-bottom: 16px;
        }

        /* ── Grid 2 col ── */
        .pp-grid-2 {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
            margin-bottom: 16px;
        }
        @media (max-width: 900px) { .pp-grid-2 { grid-template-columns: 1fr; } }

        /* ── Money totals ── */
        .pp-totals-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 0;
        }
        @media (max-width: 800px) { .pp-totals-grid { grid-template-columns: repeat(2,1fr); } }
        .pp-total-item {
            padding: 14px 16px;
            border-right: 1px solid var(--border-color);
        }
        .pp-total-item:last-child { border-right: none; }
        .pp-total-label { font-size: 11px; color: var(--text-muted); margin-bottom: 5px; text-transform: uppercase; letter-spacing: 0.05em; }
        .pp-total-val   { font-size: 18px; font-weight: 700; color: var(--text-color); }
        .pp-total-val.green  { color: var(--green-600, #1a7431); }
        .pp-total-val.red    { color: var(--red-500, #e03131); }
        .pp-total-val.blue   { color: var(--blue-500, #5e64ff); }
        .pp-total-val.orange { color: var(--orange-500, #f97316); }

        /* ── Bar chart ── */
        .pp-bar-row {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 10px;
            font-size: 12px;
        }
        .pp-bar-label {
            color: var(--text-color);
            font-weight: 500;
            min-width: 90px;
            max-width: 90px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            font-size: 12px;
        }
        .pp-bar-track {
            flex: 1;
            height: 8px;
            background: var(--control-bg);
            border-radius: 4px;
            overflow: hidden;
        }
        .pp-bar-fill {
            height: 100%;
            border-radius: 4px;
            transition: width 0.6s cubic-bezier(.4,0,.2,1);
        }
        .pp-bar-counts {
            font-size: 11px;
            color: var(--text-muted);
            min-width: 70px;
            text-align: right;
        }

        /* ── Donut ── */
        .pp-donut-wrap {
            display: flex;
            align-items: center;
            gap: 28px;
            flex-wrap: wrap;
            justify-content: center;
        }
        .pp-donut-legend { display: flex; flex-direction: column; gap: 10px; }
        .pp-legend-row {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 12px;
        }
        .pp-legend-dot {
            width: 10px; height: 10px;
            border-radius: 50%;
            flex-shrink: 0;
        }
        .pp-legend-name  { color: var(--text-color); flex: 1; }
        .pp-legend-count { font-weight: 700; color: var(--text-color); min-width: 28px; text-align: right; }
        .pp-legend-pct   { font-size: 11px; color: var(--text-muted); min-width: 36px; text-align: right; }

        /* ── Table ── */
        .pp-table-search-bar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 12px;
            flex-wrap: wrap;
            gap: 8px;
        }
        .pp-search-input {
            border: 1px solid var(--border-color);
            background: var(--control-bg);
            color: var(--text-color);
            padding: 5px 10px;
            border-radius: var(--border-radius);
            font-size: 12px;
            font-family: var(--font-stack);
            outline: none;
            width: 220px;
            height: 28px;
        }
        .pp-search-input:focus { border-color: var(--primary); }
        .pp-search-input::placeholder { color: var(--text-muted); }

        .pp-table { width: 100%; border-collapse: collapse; font-size: 12px; }
        .pp-table thead th {
            background: var(--control-bg);
            color: var(--text-muted);
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            padding: 8px 12px;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
            white-space: nowrap;
        }
        .pp-table tbody td {
            padding: 9px 12px;
            border-bottom: 1px solid var(--border-color);
            color: var(--text-color);
            vertical-align: middle;
        }
        .pp-table tbody tr:last-child td { border-bottom: none; }
        .pp-table tbody tr:hover { background: var(--fg-color, #f8f9fa); }

        .pp-emp-name  { font-weight: 600; font-size: 12px; color: var(--text-color); }
        .pp-emp-id    { font-size: 11px; color: var(--text-muted); margin-top: 1px; }
        .pp-net-sal   { font-weight: 700; color: var(--text-color); }

        .pp-badge {
            display: inline-block;
            padding: 2px 9px;
            border-radius: 20px;
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }
        .pp-badge.submitted { background: var(--green-highlight-color, #d4edda); color: var(--green-avatar-color, #155724); }
        .pp-badge.draft     { background: var(--yellow-highlight-color, #fff3cd); color: #856404; }
        .pp-badge.cancelled { background: var(--gray-100, #f1f3f4); color: var(--gray-600, #666); }

        .pp-table-empty {
            text-align: center;
            padding: 32px;
            color: var(--text-muted);
            font-size: 13px;
        }

        /* ── Activity list ── */
        .pp-activity-item {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 8px 0;
            border-bottom: 1px solid var(--border-color);
            font-size: 12px;
        }
        .pp-activity-item:last-child { border-bottom: none; }
        .pp-activity-dot {
            width: 8px; height: 8px;
            border-radius: 50%;
            flex-shrink: 0;
            background: var(--green-500, #28a745);
        }
        .pp-activity-info { flex: 1; }
        .pp-activity-name { font-weight: 600; color: var(--text-color); }
        .pp-activity-meta { font-size: 11px; color: var(--text-muted); margin-top: 1px; }
        .pp-activity-amt  { font-weight: 700; font-size: 12px; color: var(--text-color); white-space: nowrap; }
    `;
    document.head.appendChild(s);
}

// ─── Shell ────────────────────────────────────────────────────────────────────
function render_shell($main) {
    var yr = new Date().getFullYear();
    var MONTHS = ['January','February','March','April','May','June',
                  'July','August','September','October','November','December'];
    var cur_month = MONTHS[new Date().getMonth()];

    var year_opts = [yr - 2, yr - 1, yr, yr + 1].map(function(y) {
        return "<option value='" + y + "'" + (y === yr ? " selected" : "") + ">" + y + "</option>";
    }).join('');

    var month_sel = MONTHS.map(function(m) {
        return "<option value='" + m + "'" + (m === cur_month ? " selected" : "") + ">" + m + "</option>";
    }).join('');

    $main.html(`
        <div class="pp-root">
            <div class="pp-filter-bar">
                <span class="pp-filter-label">Filters</span>
                <select class="pp-select" id="pp-company"></select>
                <select class="pp-select" id="pp-year">${year_opts}</select>
                <select class="pp-select" id="pp-month">${month_sel}</select>
                <button class="pp-btn" id="pp-refresh">Refresh</button>
            </div>
            <div id="pp-body">
                <div class="pp-loading">${frappe.utils.icon('loading', 'xs')} &nbsp;Loading salary data...</div>
            </div>
        </div>
    `);

    $main.find('#pp-refresh').on('click', function() { load_dashboard($main); });
    $main.find('#pp-year, #pp-month, #pp-company').on('change', function() { load_dashboard($main); });
}

// ─── Load companies ───────────────────────────────────────────────────────────
function load_companies($main) {
    frappe.db.get_list('Company', { fields: ['name'], limit: 50 }).then(function(rows) {
        var $sel = $main.find('#pp-company');
        $sel.html(rows.map(function(r) {
            return "<option value='" + r.name + "'>" + r.name + "</option>";
        }).join(''));
        load_dashboard($main);
    });
}

// ─── Load data ────────────────────────────────────────────────────────────────
function load_dashboard($main) {
    var company = $main.find('#pp-company').val();
    var year    = $main.find('#pp-year').val();
    var month   = $main.find('#pp-month').val();
    if (!company || !year || !month) return;

    $main.find('#pp-body').html(
        "<div class='pp-loading'>" + frappe.utils.icon('loading','xs') + " &nbsp;Loading " + month + " " + year + "...</div>"
    );

    frappe.call({
        method: 'saral_hr.saral_hr.page.salary_insight.salary_insight.get_salary_insight_data',
        args: { company: company, year: year, month: month },
        callback: function(r) {
            if (r.message) {
                render_dashboard($main, r.message, month, year);
            } else {
                $main.find('#pp-body').html("<div class='pp-loading'>No data found.</div>");
            }
        },
        error: function() {
            $main.find('#pp-body').html("<div class='pp-loading'>Failed to load data. Please try again.</div>");
        }
    });
}

// ─── Render ───────────────────────────────────────────────────────────────────
function render_dashboard($main, d, month, year) {
    var slips       = d.salary_slips           || [];
    var categories  = d.category_summary       || [];
    var totals      = d.totals                 || {};
    var active_emps = d.total_active_employees || 0;

    var submitted = slips.filter(function(s) { return s.docstatus === 1; });
    var drafts    = slips.filter(function(s) { return s.docstatus === 0; });
    var cancelled = slips.filter(function(s) { return s.docstatus === 2; });
    var generated = submitted.length + drafts.length + cancelled.length;
    var pending   = Math.max(0, active_emps - generated);

    var html = '';

    // ── KPI Strip ──
    html += '<div class="pp-kpi-strip">';
    html += pp_kpi('k-total',     '👥', active_emps,       'Active Employees');
    html += pp_kpi('k-generated', '📋', generated,          'Slips Generated');
    html += pp_kpi('k-submitted', '✅', submitted.length,   'Submitted');
    html += pp_kpi('k-draft',     '✏️',  drafts.length,     'Draft');
    html += pp_kpi('k-pending',   '⏳', pending,            'No Slip Yet');
    html += pp_kpi('k-cancelled', '❌', cancelled.length,   'Cancelled');
    html += '</div>';

    // ── Money totals card ──
    html += '<div class="pp-card" style="padding:0;overflow:hidden;margin-bottom:16px;">';
    html += '<div style="padding:14px 20px 10px;border-bottom:1px solid var(--border-color);">';
    html += '<span style="font-size:13px;font-weight:600;color:var(--text-color);">Payroll Financials</span>';
    html += '<span style="font-size:11px;color:var(--text-muted);margin-left:8px;">submitted slips only · ' + month + ' ' + year + '</span>';
    html += '</div>';
    html += '<div class="pp-totals-grid">';
    html += pp_total('Gross Payout',        totals.total_earnings              || 0, 'green');
    html += pp_total('Total Deductions',    totals.total_deductions            || 0, 'red');
    html += pp_total('Net Payable',         totals.total_net                   || 0, 'orange');
    html += pp_total('Employer Contrib.',   totals.total_employer_contribution || 0, 'blue');
    html += '</div></div>';

    // ── Two col: category bars + donut ──
    html += '<div class="pp-grid-2">';

    // Category breakdown
    html += '<div class="pp-card">';
    html += '<div class="pp-section-heading">Category Breakdown <span class="pp-muted">slip count · ' + month + ' ' + year + '</span></div>';
    if (categories.length) {
        var max_c = Math.max.apply(null, categories.map(function(c) { return c.total || 0; }));
        var COLORS = ['#5e64ff','#28a745','#f0a500','#e03131','#7c3aed','#0891b2','#db2777'];
        categories.forEach(function(cat, i) {
            var col     = COLORS[i % COLORS.length];
            // ✅ FIX: if max_c is 0 (all slips are 0), fall back gracefully
            var pct     = max_c > 0 ? (cat.total / max_c * 100) : 0;
            var sub_pct = cat.total > 0 ? (cat.submitted / cat.total * 100) : 0;
            html += '<div class="pp-bar-row">';
            html += '<div class="pp-bar-label" title="' + pp_esc(cat.category||'') + '">' + pp_esc(cat.category || 'Uncat.') + '</div>';
            html += '<div style="flex:1;display:flex;flex-direction:column;gap:3px;">';
            // ✅ FIX: start at width:0%, store target width in data-w for post-paint animation
            html += '<div class="pp-bar-track"><div class="pp-bar-fill" data-w="' + pct.toFixed(2) + '" style="width:0%;background:' + col + '"></div></div>';
            html += '<div class="pp-bar-track" style="height:4px;opacity:0.6"><div class="pp-bar-fill" data-w="' + sub_pct.toFixed(2) + '" style="width:0%;background:#28a745"></div></div>';
            html += '</div>';
            html += '<div class="pp-bar-counts">' + cat.submitted + ' / ' + cat.total + '</div>';
            html += '</div>';
        });
        html += '<div style="font-size:10px;color:var(--text-muted);margin-top:6px;">Bar: total &nbsp;|&nbsp; Green sub-bar: submitted</div>';
    } else {
        html += '<div style="color:var(--text-muted);font-size:12px;text-align:center;padding:20px 0;">No category data available.</div>';
    }
    html += '</div>';

    // Donut
    html += '<div class="pp-card">';
    html += '<div class="pp-section-heading">Status Overview <span class="pp-muted">visual split</span></div>';
    html += render_donut(submitted.length, drafts.length, pending, cancelled.length);
    html += '</div>';

    html += '</div>'; // end grid-2

    // ── Two col: recent activity + dept summary ──
    html += '<div class="pp-grid-2">';

    // Recent submitted slips
    html += '<div class="pp-card">';
    html += '<div class="pp-section-heading">Recent Submitted Slips <span class="pp-muted">latest 8</span></div>';
    var recent = submitted.slice(0, 8);
    if (recent.length) {
        recent.forEach(function(s) {
            var meta = [s.category, s.department].filter(Boolean).join(' · ');
            html += '<div class="pp-activity-item">';
            html += '<div class="pp-activity-dot"></div>';
            html += '<div class="pp-activity-info">';
            html += '<div class="pp-activity-name">' + pp_esc(s.employee_name || s.employee) + '</div>';
            if (meta) html += '<div class="pp-activity-meta">' + pp_esc(meta) + '</div>';
            html += '</div>';
            html += '<div class="pp-activity-amt">₹' + fmt_inr(s.net_salary) + '</div>';
            html += '</div>';
        });
    } else {
        html += '<div style="color:var(--text-muted);font-size:12px;padding:16px 0;text-align:center;">No submitted slips yet.</div>';
    }
    html += '</div>';

    // Draft slips needing action
    html += '<div class="pp-card">';
    html += '<div class="pp-section-heading">Drafts Pending Submission <span class="pp-muted">' + drafts.length + ' slip(s)</span></div>';
    if (drafts.length) {
        drafts.slice(0, 8).forEach(function(s) {
            var meta = [s.category, s.department].filter(Boolean).join(' · ');
            html += '<div class="pp-activity-item">';
            html += '<div class="pp-activity-dot" style="background:#f0a500"></div>';
            html += '<div class="pp-activity-info">';
            html += '<div class="pp-activity-name">' + pp_esc(s.employee_name || s.employee) + '</div>';
            if (meta) html += '<div class="pp-activity-meta">' + pp_esc(meta) + '</div>';
            html += '</div>';
            html += '<div class="pp-activity-amt" style="color:#f0a500;">₹' + fmt_inr(s.net_salary) + '</div>';
            html += '</div>';
        });
    } else {
        html += '<div style="color:var(--text-muted);font-size:12px;padding:16px 0;text-align:center;">No drafts pending. 🎉</div>';
    }
    html += '</div>';

    html += '</div>'; // end grid-2

    // ── Full employee table ──
    html += '<div class="pp-card">';
    html += '<div class="pp-table-search-bar">';
    html += '<div class="pp-section-heading" style="margin:0;border:none;padding:0;">All Salary Slips <span class="pp-muted">' + slips.length + ' records · ' + month + ' ' + year + '</span></div>';
    html += '<input type="text" class="pp-search-input" id="pp-emp-search" placeholder="Search employee...">';
    html += '</div>';
    html += render_table(slips);
    html += '</div>';

    // ✅ Inject HTML into DOM first
    $main.find('#pp-body').html(html);

    // ✅ After one paint cycle, set real widths so CSS transition fires correctly
    setTimeout(function () {
        $main.find('.pp-bar-fill[data-w]').each(function () {
            $(this).css('width', $(this).attr('data-w') + '%');
        });
    }, 30);

    // Live search
    $main.find('#pp-emp-search').on('input', function() {
        var q = $(this).val().toLowerCase().trim();
        $main.find('#pp-emp-tbody tr').each(function() {
            $(this).toggle(!q || $(this).text().toLowerCase().includes(q));
        });
    });
}

// ─── Component helpers ────────────────────────────────────────────────────────

function pp_kpi(cls, icon, val, label) {
    return '<div class="pp-kpi ' + cls + '">' +
        '<div class="pp-kpi-icon">' + icon + '</div>' +
        '<div class="pp-kpi-val">' + val + '</div>' +
        '<div class="pp-kpi-label">' + label + '</div>' +
        '</div>';
}

function pp_total(label, val, color_cls) {
    return '<div class="pp-total-item">' +
        '<div class="pp-total-label">' + label + '</div>' +
        '<div class="pp-total-val ' + color_cls + '">₹' + fmt_inr(val) + '</div>' +
        '</div>';
}

function render_donut(submitted, draft, pending, cancelled) {
    var ITEMS = [
        { label: 'Submitted', val: submitted, color: '#28a745' },
        { label: 'Draft',     val: draft,     color: '#f0a500' },
        { label: 'Pending',   val: pending,   color: '#e03131' },
        { label: 'Cancelled', val: cancelled, color: '#adb5bd' },
    ];
    var total = submitted + draft + pending + cancelled;
    if (total === 0) return '<div style="color:var(--text-muted);font-size:12px;text-align:center;padding:24px 0;">No employee data for this period.</div>';

    var r = 52, cx = 68, cy = 68, sw = 14;
    var circ = 2 * Math.PI * r, offset = 0, arcs = '';
    ITEMS.forEach(function(item) {
        if (!item.val) return;
        var dash = (item.val / total) * circ;
        arcs += '<circle cx="' + cx + '" cy="' + cy + '" r="' + r + '" fill="none"' +
            ' stroke="' + item.color + '" stroke-width="' + sw + '"' +
            ' stroke-dasharray="' + dash + ' ' + (circ - dash) + '"' +
            ' stroke-dashoffset="-' + offset + '"' +
            ' transform="rotate(-90 ' + cx + ' ' + cy + ')" />';
        offset += dash;
    });

    var legend = ITEMS.map(function(item) {
        var pct = Math.round(item.val / total * 100);
        return '<div class="pp-legend-row">' +
            '<div class="pp-legend-dot" style="background:' + item.color + '"></div>' +
            '<span class="pp-legend-name">' + item.label + '</span>' +
            '<span class="pp-legend-count">' + item.val + '</span>' +
            '<span class="pp-legend-pct">' + pct + '%</span>' +
            '</div>';
    }).join('');

    return '<div class="pp-donut-wrap">' +
        '<svg width="136" height="136" viewBox="0 0 136 136">' +
        '<circle cx="' + cx + '" cy="' + cy + '" r="' + r + '" fill="none"' +
        ' stroke="var(--control-bg)" stroke-width="' + sw + '"/>' +
        arcs +
        '<text x="' + cx + '" y="' + (cy + 6) + '" text-anchor="middle"' +
        ' fill="var(--text-color)" font-size="22" font-weight="700"' +
        ' font-family="var(--font-stack)">' + total + '</text>' +
        '<text x="' + cx + '" y="' + (cy + 19) + '" text-anchor="middle"' +
        ' fill="var(--text-muted)" font-size="9"' +
        ' font-family="var(--font-stack)">employees</text>' +
        '</svg>' +
        '<div class="pp-donut-legend">' + legend + '</div>' +
        '</div>';
}

function render_table(slips) {
    if (!slips.length) return '<div class="pp-table-empty">No salary slips found for this period.</div>';
    var rows = slips.map(function(s) {
        var lbl = s.docstatus === 1 ? 'Submitted' : s.docstatus === 0 ? 'Draft' : 'Cancelled';
        var cls = s.docstatus === 1 ? 'submitted' : s.docstatus === 0 ? 'draft' : 'cancelled';
        return '<tr>' +
            '<td><div class="pp-emp-name">' + pp_esc(s.employee_name || '-') + '</div>' +
            '<div class="pp-emp-id">' + pp_esc(s.employee || '') + '</div></td>' +
            '<td>' + pp_esc(s.category    || '-') + '</td>' +
            '<td>' + pp_esc(s.department  || '-') + '</td>' +
            '<td>' + pp_esc(s.designation || '-') + '</td>' +
            '<td style="text-align:center">' + (s.payment_days || 0) + '</td>' +
            '<td class="pp-net-sal">₹' + fmt_inr(s.net_salary) + '</td>' +
            '<td><span class="pp-badge ' + cls + '">' + lbl + '</span></td>' +
            '</tr>';
    }).join('');
    return '<table class="pp-table">' +
        '<thead><tr>' +
        '<th>Employee</th><th>Category</th><th>Department</th>' +
        '<th>Designation</th><th style="text-align:center">Pay Days</th>' +
        '<th>Net Salary</th><th>Status</th>' +
        '</tr></thead>' +
        '<tbody id="pp-emp-tbody">' + rows + '</tbody>' +
        '</table>';
}

function fmt_inr(val) {
    if (!val) return '0';
    return Number(val).toLocaleString('en-IN', { maximumFractionDigits: 0 });
}

function pp_esc(str) {
    if (!str) return '';
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}