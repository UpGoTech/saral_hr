frappe.pages["daily-wage-attendance"].on_page_load = function (wrapper) {
    frappe.ui.make_app_page({ parent: wrapper, title: "Daily Wage Attendance" });
    $(wrapper).find(".layout-side-section").hide();
    inject_dwa_styles();
};

frappe.pages["daily-wage-attendance"].on_page_show = function (wrapper) {
    var $main = $(wrapper).find(".layout-main-section");
    $main.html(get_dwa_html());

    var $head = $(wrapper).find(".page-head-content");
    $head.find(".dwa-header-actions").remove();
    $head.append(`
        <div class="dwa-header-actions">
            <button id="dwa_save_btn" class="dwa-btn dwa-btn-primary">💾 Save Attendance</button>
        </div>
    `);

    init_daily_wage_attendance($main);
};

// ════════════════════════════════════════════════════════════════════════════
//  HTML TEMPLATE
// ════════════════════════════════════════════════════════════════════════════
function get_dwa_html() {
    return `
    <div class="dwa-wrap">

        <div class="dwa-filters-bar">
            <div class="dwa-filter-group">
                <label class="dwa-label">Company</label>
                <select id="dwa_company" class="dwa-input">
                    <option value="">Select Company</option>
                </select>
            </div>
            <div class="dwa-filter-group dwa-filter-employee">
                <label class="dwa-label">Employee</label>
                <div class="dwa-search-wrapper">
                    <input type="text" id="dwa_employee_search" class="dwa-input dwa-search-input"
                        placeholder="Search employee…" autocomplete="off" />
                    <button type="button" id="dwa_clear_employee" class="dwa-clear-btn"></button>
                    <div id="dwa_search_results" class="dwa-search-dropdown"></div>
                </div>
                <input type="hidden" id="dwa_employee_sel" value="" />
            </div>
            <div class="dwa-filter-group">
                <label class="dwa-label">Year</label>
                <select id="dwa_year" class="dwa-input">${get_dwa_year_options()}</select>
            </div>
            <div class="dwa-filter-group">
                <label class="dwa-label">Month</label>
                <select id="dwa_month" class="dwa-input">
                    <option value="">Select Month</option>
                    <option value="0">January</option><option value="1">February</option>
                    <option value="2">March</option><option value="3">April</option>
                    <option value="4">May</option><option value="5">June</option>
                    <option value="6">July</option><option value="7">August</option>
                    <option value="8">September</option><option value="9">October</option>
                    <option value="10">November</option><option value="11">December</option>
                </select>
            </div>
            <div class="dwa-filter-actions">
                <button id="dwa_load_btn" class="dwa-btn dwa-btn-primary">Load</button>
                <button id="dwa_clear_btn" class="dwa-btn">Clear</button>
            </div>
        </div>

        <!-- ── Info notices (no daily rate / no salary structure) ── -->
        <div id="dwa_info_panel"></div>

        <!-- Summary bar -->
        <div class="dwa-summary-bar" id="dwa_summary_bar" style="display:none;">
            <div class="dwa-summary-card dwa-card-total">
                <div class="dwa-card-val" id="dwa_cnt_total">0</div>
                <div class="dwa-card-lbl">Total Days</div>
            </div>
            <div class="dwa-summary-card dwa-card-present">
                <div class="dwa-card-val" id="dwa_cnt_present">0</div>
                <div class="dwa-card-lbl">Present</div>
            </div>
            <div class="dwa-summary-card dwa-card-absent">
                <div class="dwa-card-val" id="dwa_cnt_absent">0</div>
                <div class="dwa-card-lbl">Absent</div>
            </div>
            <div class="dwa-summary-card dwa-card-halfday">
                <div class="dwa-card-val" id="dwa_cnt_halfday">0</div>
                <div class="dwa-card-lbl">Half Day</div>
            </div>
            <div class="dwa-summary-card dwa-card-holiday">
                <div class="dwa-card-val" id="dwa_cnt_holiday">0</div>
                <div class="dwa-card-lbl">Holiday</div>
            </div>
            <div class="dwa-summary-card dwa-card-payment">
                <div class="dwa-card-val" id="dwa_cnt_payment">0</div>
                <div class="dwa-card-lbl">Payment Days</div>
            </div>
            <div class="dwa-summary-card dwa-card-unmarked">
                <div class="dwa-card-val" id="dwa_cnt_unmarked">0</div>
                <div class="dwa-card-lbl">Unmarked</div>
            </div>
            <div class="dwa-summary-card dwa-card-hours">
                <div class="dwa-card-val" id="dwa_cnt_hours">00:00</div>
                <div class="dwa-card-lbl">OT Hours</div>
            </div>
            <div class="dwa-summary-card dwa-card-basepay">
                <div class="dwa-card-val" id="dwa_cnt_basepay">&#8377;0</div>
                <div class="dwa-card-lbl">Base Pay</div>
            </div>
            <div class="dwa-summary-card dwa-card-otpayable">
                <div class="dwa-card-val" id="dwa_cnt_otpayable">&#8377;0</div>
                <div class="dwa-card-lbl">OT Payable</div>
            </div>
            <div class="dwa-summary-card dwa-card-payable">
                <div class="dwa-card-val" id="dwa_cnt_payable">&#8377;0</div>
                <div class="dwa-card-lbl">Gross Payable</div>
            </div>
        </div>

        <!-- Collapsible deductions panel (collapsed by default) -->
        <div class="dwa-ded-panel" id="dwa_ded_panel" style="display:none;">
            <button class="dwa-ded-toggle" id="dwa_ded_toggle" type="button">
                <span class="dwa-ded-toggle-icon" id="dwa_ded_icon">&#9654;</span>
                <span class="dwa-ded-toggle-title">Salary Deductions</span>
                <span class="dwa-ded-toggle-sub" id="dwa_ded_sub"></span>
                <span class="dwa-ded-toggle-totals" id="dwa_ded_totals"></span>
            </button>
            <div class="dwa-ded-body-wrap" id="dwa_ded_body_wrap" style="display:none;">
                <div class="dwa-ded-chips" id="dwa_ded_chips"></div>
                <div class="dwa-ded-footer" id="dwa_ded_footer"></div>
            </div>
        </div>

        <div class="dwa-bulk-bar" id="dwa_bulk_bar" style="display:none;">
            <span class="dwa-bulk-label">Mark all unmarked as:</span>
            <button class="dwa-pill-btn dwa-pill-present" id="dwa_bulk_present">Present</button>
            <button class="dwa-pill-btn dwa-pill-absent"  id="dwa_bulk_absent">Absent</button>
        </div>

        <div id="dwa_sandwich_banner" class="dwa-sandwich-banner" style="display:none;"></div>
        <div id="dwa_slip_banner" style="display:none;"></div>

        <div id="dwa_loading_table" class="dwa-loading" style="display:none;">
            <div class="dwa-spinner"></div>
            <span class="dwa-loading-text">Loading attendance&hellip;</span>
        </div>

        <div class="dwa-table-scroll" id="dwa_table_scroll" style="display:none;">
            <table class="dwa-table" id="dwa_table">
                <thead>
                    <tr class="dwa-thead-row">
                        <th class="dwa-th dwa-th-date">Date</th>
                        <th class="dwa-th dwa-th-day">Day</th>
                        <th class="dwa-th dwa-th-status">Present</th>
                        <th class="dwa-th dwa-th-status">On Tour</th>
                        <th class="dwa-th dwa-th-status">Absent</th>
                        <th class="dwa-th dwa-th-status">Holiday</th>
                        <th class="dwa-th dwa-th-status">Half Day</th>
                        <th class="dwa-th dwa-th-hours">OT Hours</th>
                        <th class="dwa-th dwa-th-rate">Daily Rate</th>
                        <th class="dwa-th dwa-th-rowamt">Row Amount</th>
                    </tr>
                </thead>
                <tbody id="dwa_tbody"></tbody>
            </table>
        </div>

        <div id="dwa_empty" class="dwa-empty" style="display:flex;">
            <div class="dwa-empty-icon">&#127959;</div>
            <div class="dwa-empty-title">No data loaded</div>
            <div class="dwa-empty-sub">Select a company, employee, year and month then click Load.</div>
        </div>
    </div>
    `;
}

function get_dwa_year_options() {
    var cur  = new Date().getFullYear();
    var html = '<option value="">Select Year</option>';
    for (var y = cur - 1; y <= cur + 1; y++)
        html += '<option value="' + y + '"' + (y === cur ? ' selected' : '') + '>' + y + '</option>';
    return html;
}

// ════════════════════════════════════════════════════════════════════════════
//  OT HELPERS
// ════════════════════════════════════════════════════════════════════════════
function formatOtHHMM(minutes) {
    if (!minutes) return "";
    var m = parseInt(minutes, 10) || 0;
    if (m <= 0) return "";
    return String(Math.floor(m / 60)).padStart(2, "0") + ":" + String(m % 60).padStart(2, "0");
}
function formatOtDisplay(minutes) {
    var m = parseInt(minutes, 10) || 0;
    return String(Math.floor(m / 60)).padStart(2, "0") + ":" + String(m % 60).padStart(2, "0");
}

// ════════════════════════════════════════════════════════════════════════════
//  SANDWICH HELPERS
// ════════════════════════════════════════════════════════════════════════════
function computeSandwichHolidays(attendanceData, holidayDates, joiningDate, leftDate) {
    var sortedHolidays = Object.keys(holidayDates).sort();
    var eligible = {}, sandwiched = {}, visited = {};
    sortedHolidays.forEach(function (hdate) {
        if (visited[hdate]) return;
        var block = [hdate]; visited[hdate] = true;
        var cur = addDays(hdate, 1);
        while (holidayDates[cur]) { block.push(cur); visited[cur] = true; cur = addDays(cur, 1); }
        var before = getNearestDayStatus(attendanceData, holidayDates, block[0], -1, joiningDate, leftDate);
        var after  = getNearestDayStatus(attendanceData, holidayDates, block[block.length - 1], +1, joiningDate, leftDate);
        block.forEach(function (d) {
            if (before === "paid" || after === "paid") eligible[d] = true;
            else if (before === "absent" && after === "absent") sandwiched[d] = true;
            else eligible[d] = true;
        });
    });
    return { eligible: eligible, sandwiched: sandwiched };
}

function getNearestDayStatus(attendanceData, holidayDates, fromDateKey, direction, joiningDate, leftDate) {
    var PAID = { "Present": true, "On Tour": true };
    var cur = addDays(fromDateKey, direction), limit = 90;
    while (limit-- > 0) {
        var cd = parseDateKey(cur);
        if (joiningDate && cd < joiningDate) return "outside";
        if (leftDate    && cd > leftDate)   return "outside";
        if (holidayDates[cur]) { cur = addDays(cur, direction); continue; }
        var rec = attendanceData[cur];
        if (!rec) return "absent";
        if (rec.mode === "full") {
            var s = rec.status || "";
            if (!s) return "absent";
            if (PAID[s]) return "paid";
            if (s === "Absent") return "absent";
            cur = addDays(cur, direction); continue;
        }
        if (rec.mode === "half") return "paid";
        return "absent";
    }
    return "unknown";
}

function addDays(dateKey, n) {
    var p = dateKey.split("-");
    var d = new Date(parseInt(p[0]), parseInt(p[1]) - 1, parseInt(p[2]));
    d.setDate(d.getDate() + n);
    return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
}
function parseDateKey(dk) {
    var p = dk.split("-");
    var d = new Date(parseInt(p[0]), parseInt(p[1]) - 1, parseInt(p[2]));
    d.setHours(0, 0, 0, 0);
    return d;
}

// ════════════════════════════════════════════════════════════════════════════
//  INIT
// ════════════════════════════════════════════════════════════════════════════
function init_daily_wage_attendance($main) {

    var allEmployees     = [];
    var filteredEmps     = [];
    var selectedIndex    = -1;
    var searchTimer      = null;
    var isSaving         = false;
    var attendanceData   = {};
    var originalData     = {};
    var otMinutesData    = {};
    var dirtyDates       = new Set();
    var holidayDates     = {};
    var joiningDate      = null;
    var leftDate         = null;
    var dailyRateMap     = {};
    var currentLockState = null;
    var sandwichEligible = {};
    var sandwichUnpaid   = {};
    var ssaDeductions    = [];
    var ssaTotalDed      = 0;
    var dedOpen          = false;

    var FULL_STATUSES    = ["Present", "On Tour", "Absent", "Holiday"];
    var STATUS_DOT_CLASS = { "Present": "present-dot", "On Tour": "present-dot", "Absent": "absent-dot", "Holiday": "holiday-dot" };

    // DOM refs
    var companySel    = document.getElementById("dwa_company");
    var searchInput   = document.getElementById("dwa_employee_search");
    var searchResults = document.getElementById("dwa_search_results");
    var clearEmpBtn   = document.getElementById("dwa_clear_employee");
    var employeeSel   = document.getElementById("dwa_employee_sel");
    var yearSel       = document.getElementById("dwa_year");
    var monthSel      = document.getElementById("dwa_month");
    var loadBtn       = document.getElementById("dwa_load_btn");
    var clearBtn      = document.getElementById("dwa_clear_btn");
    var loadingTable  = document.getElementById("dwa_loading_table");
    var tableScroll   = document.getElementById("dwa_table_scroll");
    var tbody         = document.getElementById("dwa_tbody");
    var emptyEl       = document.getElementById("dwa_empty");
    var summaryBar    = document.getElementById("dwa_summary_bar");
    var bulkBar       = document.getElementById("dwa_bulk_bar");
    var saveBtn       = document.getElementById("dwa_save_btn");
    var slipBanner    = document.getElementById("dwa_slip_banner");
    var sandwichBanner= document.getElementById("dwa_sandwich_banner");
    var dedPanel      = document.getElementById("dwa_ded_panel");
    var dedBodyWrap   = document.getElementById("dwa_ded_body_wrap");
    var dedChips      = document.getElementById("dwa_ded_chips");
    var dedFooter     = document.getElementById("dwa_ded_footer");
    var dedSub        = document.getElementById("dwa_ded_sub");
    var dedTotals     = document.getElementById("dwa_ded_totals");
    var dedIcon       = document.getElementById("dwa_ded_icon");
    var dedToggle     = document.getElementById("dwa_ded_toggle");
    var infoPanel     = document.getElementById("dwa_info_panel");

    // Collapsible deductions toggle
    dedToggle.addEventListener("click", function () {
        dedOpen = !dedOpen;
        dedBodyWrap.style.display = dedOpen ? "block" : "none";
        dedIcon.innerHTML = dedOpen ? "&#9660;" : "&#9654;";
    });

    // ════════════════════════════════════════════════════════════════════════
    //  INFO PANEL HELPERS
    //  Shows non-intrusive inline notices (no daily rate / no salary structure)
    // ════════════════════════════════════════════════════════════════════════
    var _infoFlags = { noRate: false, noSsa: false };

    function renderInfoPanel() {
        var notices = [];

        if (_infoFlags.noRate) {
            notices.push(
                '<div class="dwa-notice dwa-notice-warn">' +
                    '<span class="dwa-notice-icon">&#9888;</span>' +
                    '<div class="dwa-notice-body">' +
                        '<strong>No Daily Rate configured</strong> &mdash; ' +
                        'Daily Rate, Row Amount and payable figures will show &ldquo;&mdash;&rdquo; for this employee. ' +
                        'Please create a record in <em>Daily Rates Worker</em> for this employee to enable pay calculation.' +
                    '</div>' +
                    '<a class="dwa-notice-link" href="/app/daily-rates-worker/new-daily-rates-worker-1" target="_blank">+ Add Rate</a>' +
                '</div>'
            );
        }

        if (_infoFlags.noSsa) {
            notices.push(
                '<div class="dwa-notice dwa-notice-info">' +
                    '<span class="dwa-notice-icon">&#8505;</span>' +
                    '<div class="dwa-notice-body">' +
                        '<strong>No Salary Structure assigned</strong> &mdash; ' +
                        'Deduction breakdown cannot be displayed. ' +
                        'Assign a Salary Structure Assignment for this employee to see deductions and net payable.' +
                    '</div>' +
                    '<a class="dwa-notice-link" href="/app/salary-structure-assignment/new-salary-structure-assignment-1" target="_blank">+ Assign</a>' +
                '</div>'
            );
        }

        infoPanel.innerHTML = notices.join("");
        infoPanel.style.display = notices.length ? "flex" : "none";
    }

    function clearInfoPanel() {
        _infoFlags.noRate = false;
        _infoFlags.noSsa  = false;
        infoPanel.innerHTML = "";
        infoPanel.style.display = "none";
    }

    // ════════════════════════════════════════════════════════════════════════
    //  BOOTSTRAP — companies + employees
    // ════════════════════════════════════════════════════════════════════════
    frappe.call({
        method: "saral_hr.saral_hr.page.daily_wage_attendance.daily_wage_attendance.get_daily_wage_active_employees",
        callback: function (r) {
            var rows = (r && r.message) ? r.message : [];
            var seen = {};
            rows.forEach(function (row) {
                if (row.company && !seen[row.company]) {
                    seen[row.company] = true;
                    var opt = document.createElement("option");
                    opt.value = row.company; opt.text = row.company;
                    companySel.appendChild(opt);
                }
            });
            allEmployees = rows.map(function (row) {
                return { value: row.name, name: row.full_name || row.name, emp_id: row.employee || row.name, company: row.company || "" };
            });
        },
        error: function () {}
    });

    companySel.addEventListener("change", function () {
        searchInput.value = ""; employeeSel.value = "";
        clearEmpBtn.classList.remove("show"); searchResults.classList.remove("show");
        resetPage();
    });

    // ════════════════════════════════════════════════════════════════════════
    //  EMPLOYEE SEARCH
    // ════════════════════════════════════════════════════════════════════════
    function escHtml(t) {
        return (t || "").replace(/[&<>"']/g, function (m) {
            return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[m];
        });
    }
    function highlight(text, term) {
        if (!term) return escHtml(text);
        var et = term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        return escHtml(text).replace(new RegExp("(" + et + ")", "gi"), '<span class="dwa-hl">$1</span>');
    }
    function getPool() {
        var co = companySel.value;
        return co ? allEmployees.filter(function (e) { return e.company === co; }) : allEmployees;
    }
    function showDropdown(results, term) {
        if (!results.length) {
            searchResults.innerHTML = '<div class="dwa-no-results">No employee found</div>';
        } else {
            searchResults.innerHTML = results.map(function (e, i) {
                return '<div class="dwa-result-item" data-idx="' + i + '">' +
                    '<div class="dwa-result-name">' + highlight(e.name, term) + '</div>' +
                    '<div class="dwa-result-id">' + highlight(e.emp_id, term) + '</div></div>';
            }).join("");
            searchResults.querySelectorAll(".dwa-result-item").forEach(function (item) {
                item.addEventListener("click", function () { pickEmployee(filteredEmps[parseInt(item.dataset.idx)]); });
                item.addEventListener("mouseenter", function () { selectedIndex = parseInt(item.dataset.idx); hilite(); });
            });
        }
        searchResults.classList.add("show"); selectedIndex = -1;
    }
    function hilite() {
        searchResults.querySelectorAll(".dwa-result-item").forEach(function (item, i) {
            item.classList.toggle("selected", i === selectedIndex);
        });
    }
    function pickEmployee(emp) {
        if (!emp) return;
        searchInput.value = emp.name; employeeSel.value = emp.value;
        searchResults.classList.remove("show"); clearEmpBtn.classList.add("show");
    }
    searchInput.addEventListener("focus", function () { filteredEmps = getPool(); showDropdown(filteredEmps, ""); });
    searchInput.addEventListener("input", function () {
        var term = this.value.trim();
        clearEmpBtn.classList.toggle("show", !!term);
        clearTimeout(searchTimer);
        searchTimer = setTimeout(function () {
            filteredEmps = term ? getPool().filter(function (e) {
                return e.name.toLowerCase().includes(term.toLowerCase()) || e.emp_id.toLowerCase().includes(term.toLowerCase());
            }) : getPool();
            showDropdown(filteredEmps, term);
        }, 150);
    });
    searchInput.addEventListener("keydown", function (e) {
        if (!searchResults.classList.contains("show")) return;
        if (e.key === "ArrowDown") { e.preventDefault(); selectedIndex = (selectedIndex + 1) % Math.max(filteredEmps.length, 1); hilite(); }
        else if (e.key === "ArrowUp") { e.preventDefault(); selectedIndex = (selectedIndex - 1 + filteredEmps.length) % Math.max(filteredEmps.length, 1); hilite(); }
        else if (e.key === "Enter" && selectedIndex >= 0) { e.preventDefault(); pickEmployee(filteredEmps[selectedIndex]); }
        else if (e.key === "Escape") searchResults.classList.remove("show");
    });
    clearEmpBtn.addEventListener("click", function () {
        searchInput.value = ""; employeeSel.value = "";
        clearEmpBtn.classList.remove("show"); searchResults.classList.remove("show");
        resetPage();
    });
    document.addEventListener("click", function (e) {
        if (!searchInput.contains(e.target) && !searchResults.contains(e.target))
            searchResults.classList.remove("show");
    });

    // ════════════════════════════════════════════════════════════════════════
    //  DEDUCTIONS
    // ════════════════════════════════════════════════════════════════════════
    function loadSsaDeductions(employee, startDate) {
        ssaDeductions = []; ssaTotalDed = 0;
        dedPanel.style.display = "none";
        dedOpen = false; dedBodyWrap.style.display = "none"; dedIcon.innerHTML = "&#9654;";

        frappe.call({
            method: "frappe.client.get_list",
            args: {
                doctype:  "Salary Structure Assignment",
                filters:  [["employee","=",employee],["from_date","<=",startDate],["docstatus","=",1]],
                fields:   ["name","from_date","salary_structure"],
                order_by: "from_date desc",
                limit:    1
            },
            callback: function (r) {
                var rows = (r && r.message) ? r.message : [];

                // ── NEW: no SSA found ─────────────────────────────────────
                if (!rows.length) {
                    _infoFlags.noSsa = true;
                    renderInfoPanel();
                    return;
                }
                // ─────────────────────────────────────────────────────────

                dedSub.textContent = rows[0].salary_structure + "  \u00b7  from " + rows[0].from_date;
                frappe.call({
                    method: "frappe.client.get",
                    args: { doctype: "Salary Structure Assignment", name: rows[0].name },
                    callback: function (dr) {
                        var doc = dr && dr.message;
                        if (!doc) return;
                        ssaDeductions = (doc.deductions || [])
                            .filter(function (row) { return !parseInt(row.employer_contribution || 0); })
                            .map(function (row) {
                                return { salary_component: row.salary_component || "", abbr: row.abbr || "", amount: parseFloat(row.amount || 0) };
                            });
                        ssaTotalDed = ssaDeductions.reduce(function (s, r) { return s + r.amount; }, 0);
                        renderDedPanel();
                    }, error: function () {}
                });
            }, error: function () {}
        });
    }

    function renderDedPanel() {
        if (!ssaDeductions.length) { dedPanel.style.display = "none"; return; }
        dedChips.innerHTML = ssaDeductions.map(function (d) {
            return '<div class="dwa-ded-chip">' +
                '<span class="dwa-ded-chip-abbr">' + escHtml(d.abbr || d.salary_component) + '</span>' +
                '<span class="dwa-ded-chip-name">' + escHtml(d.salary_component) + '</span>' +
                '<span class="dwa-ded-chip-amt">&minus;&#8377;' + d.amount.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + '</span>' +
            '</div>';
        }).join("");
        updateDedFooter();
        dedPanel.style.display = "block";
    }

    function updateDedFooter() {
        if (!ssaDeductions.length) return;
        var fmtINR = function (n) { return "&#8377;" + n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 }); };
        var payableText  = (document.getElementById("dwa_cnt_payable") || {}).textContent || "0";
        var grossPayable = parseFloat(payableText.replace(/[^\d.]/g, "")) || 0;
        var netPayable   = grossPayable - ssaTotalDed;

        dedTotals.innerHTML =
            '<span class="dwa-ded-badge dwa-ded-badge-ded">&minus;' + fmtINR(ssaTotalDed) + '</span>' +
            '<span class="dwa-ded-badge dwa-ded-badge-net">Net&nbsp;' + fmtINR(netPayable) + '</span>';

        dedFooter.innerHTML =
            '<div class="dwa-ded-foot-grid">' +
                '<div class="dwa-ded-foot-row">' +
                    '<span class="dwa-ded-foot-lbl">Gross Payable (attendance)</span>' +
                    '<span class="dwa-ded-foot-val">' + fmtINR(grossPayable) + '</span>' +
                '</div>' +
                '<div class="dwa-ded-foot-row">' +
                    '<span class="dwa-ded-foot-lbl">Total Deductions</span>' +
                    '<span class="dwa-ded-foot-val dwa-ded-foot-ded">&minus;&nbsp;' + fmtINR(ssaTotalDed) + '</span>' +
                '</div>' +
                '<div class="dwa-ded-foot-row dwa-ded-foot-net-row">' +
                    '<span class="dwa-ded-foot-lbl">Net Payable</span>' +
                    '<span class="dwa-ded-foot-val dwa-ded-foot-net">' + fmtINR(netPayable) + '</span>' +
                '</div>' +
            '</div>';
    }

    // ════════════════════════════════════════════════════════════════════════
    //  LOAD ATTENDANCE
    // ════════════════════════════════════════════════════════════════════════
    loadBtn.addEventListener("click", loadAttendance);
    yearSel.addEventListener("change", loadAttendance);
    monthSel.addEventListener("change", loadAttendance);

    function loadAttendance() {
        var company = companySel.value || "—";
        var year    = yearSel.value;
        var month   = monthSel.value;
        if (!year || month === "") { frappe.show_alert({ message: "Please select Year and Month.", indicator: "orange" }); return; }

        var monthNum  = parseInt(month) + 1;
        var lastDay   = new Date(parseInt(year), parseInt(month) + 1, 0).getDate();
        var startDate = year + "-" + String(monthNum).padStart(2, "0") + "-01";
        var endDate   = year + "-" + String(monthNum).padStart(2, "0") + "-" + String(lastDay).padStart(2, "0");

        tableScroll.style.display = "none"; loadingTable.style.display = "flex";
        emptyEl.style.display = "none"; summaryBar.style.display = "none";
        bulkBar.style.display = "none"; slipBanner.style.display = "none";
        sandwichBanner.style.display = "none"; dedPanel.style.display = "none";

        // Clear info notices at the start of each load
        clearInfoPanel();

        attendanceData = {}; originalData = {}; otMinutesData = {}; dirtyDates.clear();
        holidayDates = {}; dailyRateMap = {}; joiningDate = null; leftDate = null;
        sandwichEligible = {}; sandwichUnpaid = {}; ssaDeductions = []; ssaTotalDed = 0;

        renderTable(startDate, endDate);

        var employee = employeeSel.value;
        if (!employee) return;

        loadSsaDeductions(employee, startDate);

        var pending = 3;
        function done() { if (--pending <= 0) { recomputeSandwich(); updateSummary(); } }

        // Holidays
        frappe.call({
            method: "saral_hr.saral_hr.page.mark_attendance.mark_attendance.get_holidays_between_dates",
            args: { company: company, start_date: startDate, end_date: endDate },
            callback: function (hr) {
                holidayDates = {};
                (hr.message || []).forEach(function (h) { holidayDates[h] = true; });
                Object.keys(holidayDates).forEach(function (dk) {
                    if (attendanceData[dk] && attendanceData[dk].mode === "full" && !attendanceData[dk].status) {
                        attendanceData[dk] = { mode: "full", status: "Holiday" };
                        refreshRowVisuals(dk);
                    }
                });
                done();
            }, error: function () { done(); }
        });

        // Joining / left dates
        frappe.call({
            method: "saral_hr.saral_hr.page.mark_attendance.mark_attendance.get_employee_joining_date",
            args: { employee: employee },
            callback: function (jr) {
                var jd = jr.message || {};
                joiningDate = jd.joining_date ? parseDateLocal(jd.joining_date) : null;
                leftDate    = jd.left_date    ? parseDateLocal(jd.left_date)    : null;
                tbody.querySelectorAll("tr[data-date]").forEach(function (row) {
                    var dk = row.getAttribute("data-date");
                    var cd = parseDateLocal(dk); cd.setHours(0, 0, 0, 0);
                    if ((joiningDate && cd < joiningDate) || (leftDate && cd > leftDate))
                        row.classList.add("dwa-future-row");
                });
                done();
            }, error: function () { done(); }
        });

        // Daily rates + ADR records
        frappe.call({
            method: "saral_hr.saral_hr.page.daily_wage_attendance.daily_wage_attendance.get_daily_wage_data",
            args: { employee: employee, start_date: startDate, end_date: endDate },
            callback: function (dr) {
                var dData = dr.message || {};
                dailyRateMap = dData.daily_rates || {};
                var adrRecords = dData.adr_records || {};

                // ── NEW: warn if no daily rate at all for this period ─────
                if (!Object.keys(dailyRateMap).length) {
                    _infoFlags.noRate = true;
                    renderInfoPanel();
                }
                // ─────────────────────────────────────────────────────────

                Object.keys(adrRecords).forEach(function (dk) {
                    var adr = adrRecords[dk];
                    var rec = adr.status === "Half Day"
                        ? { mode: "half" }
                        : { mode: "full", status: adr.status || "" };
                    attendanceData[dk] = rec;
                    originalData[dk]   = JSON.parse(JSON.stringify(rec));
                    if (adr.ot_minutes) otMinutesData[dk] = parseInt(adr.ot_minutes, 10) || 0;
                    refreshRowVisuals(dk);
                });

                tbody.querySelectorAll("tr[data-date]").forEach(function (row) {
                    var dk = row.getAttribute("data-date");
                    var rc = row.querySelector(".dwa-rate-cell");
                    if (rc) {
                        var r = dailyRateMap[dk] || (adrRecords[dk] && adrRecords[dk].daily_rate) || "";
                        rc.textContent = r ? "\u20b9" + parseFloat(r).toFixed(2) : "\u2014";
                    }
                    var oi = row.querySelector(".dwa-hours-input");
                    if (oi && otMinutesData[dk]) oi.value = formatOtHHMM(otMinutesData[dk]);
                    refreshRowAmount(dk);
                });
                done();
            }, error: function () { done(); }
        });
    }

    function parseDateLocal(str) {
        if (!str) return null;
        var p = str.split("-");
        return new Date(parseInt(p[0]), parseInt(p[1]) - 1, parseInt(p[2]));
    }

    // ════════════════════════════════════════════════════════════════════════
    //  ROW AMOUNT
    // ════════════════════════════════════════════════════════════════════════
    function calcRowAmount(dk) {
        var rate   = parseFloat(dailyRateMap[dk] || 0);
        var otMins = otMinutesData[dk] || 0;
        var rec    = attendanceData[dk] || {};
        var base   = 0;
        if (rec.mode === "full") {
            var s = rec.status || "";
            if (s === "Present" || s === "On Tour") base = rate;
            else if (s === "Holiday" && sandwichEligible[dk]) base = rate;
        } else if (rec.mode === "half") {
            base = rate / 2;
        }
        var ot = (rate > 0 ? rate / 8 : 0) * (otMins / 60);
        return { base: base, ot: ot, total: base + ot };
    }

    function refreshRowAmount(dk) {
        var row = document.querySelector('tr[data-date="' + dk + '"]');
        if (!row) return;
        var cell = row.querySelector(".dwa-rowamt-cell");
        if (!cell) return;
        var a = calcRowAmount(dk);
        if (a.total <= 0) { cell.textContent = "\u2014"; cell.classList.remove("dwa-rowamt-has"); return; }
        var parts = [];
        if (a.base > 0) parts.push("\u20b9" + a.base.toLocaleString("en-IN", { maximumFractionDigits: 2 }));
        if (a.ot   > 0) parts.push('<span class="dwa-ot-extra">+\u20b9' + a.ot.toLocaleString("en-IN", { maximumFractionDigits: 2 }) + " OT</span>");
        cell.innerHTML = parts.join(" ");
        cell.classList.add("dwa-rowamt-has");
    }

    // ════════════════════════════════════════════════════════════════════════
    //  SANDWICH
    // ════════════════════════════════════════════════════════════════════════
    function recomputeSandwich() {
        var r = computeSandwichHolidays(attendanceData, holidayDates, joiningDate, leftDate);
        sandwichEligible = r.eligible; sandwichUnpaid = r.sandwiched;
        Object.keys(holidayDates).forEach(function (dk) { refreshRowVisuals(dk); });
        var list = Object.keys(sandwichUnpaid).sort();
        if (list.length) {
            var chips = list.map(function (dk) {
                var p = dk.split("-");
                var d = new Date(parseInt(p[0]), parseInt(p[1]) - 1, parseInt(p[2]));
                return '<span class="dwa-sw-date-chip">' + d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric", weekday: "short" }) + '</span>';
            }).join("");
            sandwichBanner.innerHTML =
                '<div class="dwa-sw-icon">&#9888;</div>' +
                '<div class="dwa-sw-content">' +
                    '<div class="dwa-sw-title">Sandwiched Holiday Alert &mdash; treated as <strong>Absent</strong></div>' +
                    '<div class="dwa-sw-sub">Holiday surrounded by absent days on both sides earns no pay. Mark one adjacent day Present or On Tour to reinstate.</div>' +
                    '<div class="dwa-sw-dates">' + chips + '</div>' +
                '</div>';
            sandwichBanner.style.display = "flex";
        } else {
            sandwichBanner.style.display = "none";
            sandwichBanner.innerHTML = "";
        }
    }

    // ════════════════════════════════════════════════════════════════════════
    //  RENDER TABLE
    // ════════════════════════════════════════════════════════════════════════
    function renderTable(startDate, endDate) {
        tbody.innerHTML = "";
        var current = new Date(startDate + "T00:00:00");
        var end     = new Date(endDate   + "T00:00:00");
        var today   = new Date(); today.setHours(0, 0, 0, 0);
        var rowIdx  = 0;
        while (current <= end) {
            var cd = new Date(current); cd.setHours(0, 0, 0, 0);
            var dk = cd.getFullYear() + "-" + String(cd.getMonth() + 1).padStart(2, "0") + "-" + String(cd.getDate()).padStart(2, "0");
            var isHoliday = holidayDates[dk] === true;
            var isFuture  = cd > today;
            attendanceData[dk] = attendanceData[dk] || { mode: "full", status: isHoliday ? "Holiday" : "" };
            tbody.appendChild(buildRow(dk, cd, attendanceData[dk], isHoliday, isFuture, rowIdx++));
            current.setDate(current.getDate() + 1);
        }
        loadingTable.style.display = "none"; tableScroll.style.display = "block";
        summaryBar.style.display = "flex"; bulkBar.style.display = "flex";
        emptyEl.style.display = "none"; updateSummary();
    }

    // ════════════════════════════════════════════════════════════════════════
    //  BUILD ROW
    // ════════════════════════════════════════════════════════════════════════
    function buildRow(dk, dateObj, savedRec, isHoliday, isFuture, rowIdx) {
        var row = document.createElement("tr");
        row.setAttribute("data-date", dk);
        row.className = "dwa-row";

        var isLocked      = currentLockState === "submitted";
        var cellsDisabled = isFuture || isLocked;
        var dayName       = dateObj.toLocaleDateString("en-US", { weekday: "long" });
        var dateLabel     = String(dateObj.getDate()).padStart(2, "0") + " " +
                            dateObj.toLocaleDateString("en-US", { month: "short" }) + " " + dateObj.getFullYear();

        if (isFuture) row.classList.add("dwa-future-row");
        if (savedRec.mode === "full" && savedRec.status === "Holiday") row.classList.add("dwa-row-holiday");
        if (sandwichUnpaid[dk]) row.classList.add("dwa-row-sandwich");
        if (savedRec.mode === "half") row.classList.add("dwa-row-halfday");

        var dateTd = document.createElement("td");
        dateTd.className = "dwa-td dwa-date-cell" + (isHoliday ? " dwa-date-holiday" : "");
        var swBadge = sandwichUnpaid[dk] ? ' <span class="dwa-sandwich-badge" title="Sandwiched holiday">&#x1F96A;</span>' : "";
        dateTd.innerHTML = escHtml(dateLabel) + swBadge;
        row.appendChild(dateTd);

        var dayTd = document.createElement("td");
        dayTd.className = "dwa-td dwa-day-cell" + (isHoliday ? " dwa-date-holiday" : "");
        dayTd.textContent = dayName;
        row.appendChild(dayTd);

        FULL_STATUSES.forEach(function (status) {
            var td = document.createElement("td");
            td.className = "dwa-td dwa-status-cell" + (cellsDisabled ? " dwa-cell-disabled" : "");
            var isActive = savedRec.mode === "full" && savedRec.status === status;
            var dot = document.createElement("div");
            dot.className = "dwa-col-dot" + (isActive ? " active " + (STATUS_DOT_CLASS[status] || "") : "");
            dot.setAttribute("data-status", status);
            if (!cellsDisabled) td.addEventListener("click", function () { onFullDayClick(dk, status, isHoliday); });
            td.appendChild(dot); row.appendChild(td);
        });

        var hdTd = document.createElement("td");
        hdTd.className = "dwa-td dwa-status-cell" + (cellsDisabled ? " dwa-cell-disabled" : "");
        var hdDot = document.createElement("div");
        hdDot.className = "dwa-col-dot" + (savedRec.mode === "half" ? " active halfday-dot" : "");
        hdDot.setAttribute("data-status", "Half Day");
        if (!cellsDisabled) {
            hdTd.addEventListener("click", function () { onHalfDayClick(dk, isHoliday); });
        }
        hdTd.appendChild(hdDot); row.appendChild(hdTd);

        var hoursTd = document.createElement("td");
        hoursTd.className = "dwa-td dwa-hours-cell";
        var hoursInput = document.createElement("input");
        hoursInput.type = "text"; hoursInput.className = "dwa-hours-input";
        hoursInput.placeholder = "00:00"; hoursInput.maxLength = 5;
        hoursInput.value = otMinutesData[dk] ? formatOtHHMM(otMinutesData[dk]) : "";
        if (cellsDisabled) { hoursInput.disabled = true; hoursInput.style.opacity = "0.4"; }
        hoursInput.addEventListener("blur", function () {
            var mins = parseOtInput(this.value.trim());
            otMinutesData[dk] = mins; this.value = mins ? formatOtHHMM(mins) : "";
            markDirty(dk); refreshRowAmount(dk); updateSummary();
        });
        hoursInput.addEventListener("keypress", function (e) { if (!/[\d:]/.test(e.key)) e.preventDefault(); });
        hoursInput.addEventListener("input", function () {
            var v = this.value.replace(/[^0-9:]/g, "");
            if (v.length === 2 && !v.includes(":")) v += ":";
            this.value = v;
        });
        hoursTd.appendChild(hoursInput); row.appendChild(hoursTd);

        var rateTd = document.createElement("td");
        rateTd.className = "dwa-td dwa-rate-cell";
        var rate = dailyRateMap[dk] || "";
        rateTd.textContent = rate ? "\u20b9" + parseFloat(rate).toFixed(2) : "\u2014";
        row.appendChild(rateTd);

        var amtTd = document.createElement("td");
        amtTd.className = "dwa-td dwa-rowamt-cell";
        amtTd.textContent = "\u2014";
        row.appendChild(amtTd);

        return row;
    }

    function parseOtInput(raw) {
        if (!raw) return 0; raw = raw.trim();
        if (raw.includes(":")) {
            var p = raw.split(":"), h = parseInt(p[0], 10) || 0, m = parseInt(p[1], 10) || 0;
            return h * 60 + Math.min(m, 59);
        }
        var n = parseInt(raw, 10) || 0;
        if (raw.length <= 2) return n * 60;
        return Math.floor(n / 100) * 60 + Math.min(n % 100, 59);
    }

    // ════════════════════════════════════════════════════════════════════════
    //  CLICK HANDLERS
    // ════════════════════════════════════════════════════════════════════════
    function onFullDayClick(dk, status, isHoliday) {
        var rec = attendanceData[dk] || {};
        attendanceData[dk] = (rec.mode === "full" && rec.status === status)
            ? { mode: "full", status: isHoliday ? "Holiday" : "" }
            : { mode: "full", status: status };
        markDirty(dk); recomputeSandwich(); refreshRowVisuals(dk); refreshRowAmount(dk); updateSummary();
    }

    function onHalfDayClick(dk, isHoliday) {
        var rec = attendanceData[dk] || {};
        if (rec.mode === "half") {
            attendanceData[dk] = { mode: "full", status: isHoliday ? "Holiday" : "" };
        } else {
            attendanceData[dk] = { mode: "half" };
        }
        markDirty(dk); recomputeSandwich(); refreshRowVisuals(dk); refreshRowAmount(dk); updateSummary();
    }

    // ════════════════════════════════════════════════════════════════════════
    //  ROW VISUAL REFRESH
    // ════════════════════════════════════════════════════════════════════════
    function refreshRowVisuals(dk) {
        var row = document.querySelector('tr[data-date="' + dk + '"]');
        if (!row) return;
        var rec = attendanceData[dk] || {};
        row.classList.remove("dwa-row-halfday", "dwa-row-holiday", "dwa-row-sandwich");

        row.querySelectorAll(".dwa-col-dot[data-status]").forEach(function (dot) {
            var ds = dot.getAttribute("data-status");
            if (ds === "Half Day") {
                dot.className = "dwa-col-dot" + (rec.mode === "half" ? " active halfday-dot" : "");
            } else {
                var isActive = rec.mode === "full" && rec.status === ds;
                dot.className = "dwa-col-dot" + (isActive ? " active " + (STATUS_DOT_CLASS[ds] || "") : "");
            }
        });

        if (rec.mode === "half") {
            row.classList.add("dwa-row-halfday");
        } else {
            var s = rec.status || "";
            if (s === "Holiday") row.classList.add("dwa-row-holiday");
            if (sandwichUnpaid[dk]) row.classList.add("dwa-row-sandwich");
        }

        var dateTd = row.querySelector(".dwa-date-cell");
        if (dateTd) {
            var dl = dateTd.textContent.replace(/\s*🥪\s*/, "").trim();
            var badge = sandwichUnpaid[dk] ? ' <span class="dwa-sandwich-badge" title="Sandwiched holiday">&#x1F96A;</span>' : "";
            dateTd.innerHTML = escHtml(dl) + badge;
        }

        if (dirtyDates.has(dk)) row.classList.add("dwa-row-dirty");
        else row.classList.remove("dwa-row-dirty");
    }

    function markDirty(dk) {
        dirtyDates.add(dk);
        var row = document.querySelector('tr[data-date="' + dk + '"]');
        if (row) row.classList.add("dwa-row-dirty");
    }

    // ════════════════════════════════════════════════════════════════════════
    //  SUMMARY
    // ════════════════════════════════════════════════════════════════════════
    function updateSummary() {
        var cnt  = { total: 0, present: 0, absent: 0, halfday: 0, holiday: 0, unmarked: 0, payment: 0 };
        var totalOtMin = 0, totalBase = 0, totalOtPay = 0;

        tbody.querySelectorAll("tr[data-date]").forEach(function (row) {
            if (row.classList.contains("dwa-future-row")) return;
            cnt.total++;
            var dk   = row.getAttribute("data-date");
            var rec  = attendanceData[dk] || {};
            var rate = parseFloat(dailyRateMap[dk] || 0);
            var otM  = otMinutesData[dk] || 0;
            totalOtMin += otM;
            if (rate > 0 && otM > 0) totalOtPay += (rate / 8) * (otM / 60);

            if (rec.mode === "full") {
                var s = rec.status || "";
                if      (!s)                                 cnt.unmarked++;
                else if (s === "Present" || s === "On Tour") { cnt.present++; cnt.payment++; totalBase += rate; }
                else if (s === "Absent")                     cnt.absent++;
                else if (s === "Holiday") {
                    cnt.holiday++;
                    if (sandwichEligible[dk]) { cnt.payment++; totalBase += rate; }
                } else cnt.unmarked++;
            } else if (rec.mode === "half") {
                cnt.halfday++;
                cnt.present += 0.5;
                cnt.absent  += 0.5;
                cnt.payment += 0.5;
                totalBase   += rate / 2;
            } else {
                cnt.unmarked++;
            }
        });

        var totalPay = totalBase + totalOtPay;
        var fmtINR   = function (n) { return "\u20b9" + n.toLocaleString("en-IN", { minimumFractionDigits: 0, maximumFractionDigits: 2 }); };

        document.getElementById("dwa_cnt_total").textContent    = cnt.total;
        document.getElementById("dwa_cnt_present").textContent  = fmt(cnt.present);
        document.getElementById("dwa_cnt_absent").textContent   = fmt(cnt.absent);
        document.getElementById("dwa_cnt_halfday").textContent  = cnt.halfday;
        document.getElementById("dwa_cnt_holiday").textContent  = cnt.holiday;
        document.getElementById("dwa_cnt_payment").textContent  = fmt(cnt.payment);
        document.getElementById("dwa_cnt_unmarked").textContent = cnt.unmarked;
        document.getElementById("dwa_cnt_hours").textContent    = formatOtDisplay(totalOtMin);
        document.getElementById("dwa_cnt_basepay").textContent   = fmtINR(totalBase);
        document.getElementById("dwa_cnt_otpayable").textContent = fmtINR(totalOtPay);
        document.getElementById("dwa_cnt_payable").textContent   = fmtINR(totalPay);

        tbody.querySelectorAll("tr[data-date]").forEach(function (r) { refreshRowAmount(r.getAttribute("data-date")); });
        updateDedFooter();
    }

    function fmt(v) { return v % 1 === 0 ? String(v) : v.toFixed(1); }

    // ════════════════════════════════════════════════════════════════════════
    //  BULK MARK
    // ════════════════════════════════════════════════════════════════════════
    function bulkMark(status) {
        tbody.querySelectorAll("tr[data-date]").forEach(function (row) {
            if (row.classList.contains("dwa-future-row")) return;
            var dk = row.getAttribute("data-date");
            if (originalData[dk]) return;
            var rec = attendanceData[dk] || {};
            if (rec.mode === "full" && rec.status === "Holiday") return;
            attendanceData[dk] = { mode: "full", status: status };
            markDirty(dk); refreshRowVisuals(dk);
        });
        recomputeSandwich(); updateSummary();
    }
    document.getElementById("dwa_bulk_present").onclick = function () { bulkMark("Present"); };
    document.getElementById("dwa_bulk_absent").onclick  = function () { bulkMark("Absent"); };

    // ════════════════════════════════════════════════════════════════════════
    //  CLEAR / RESET
    // ════════════════════════════════════════════════════════════════════════
    function resetPage() {
        tbody.innerHTML = "";
        tableScroll.style.display = "none"; loadingTable.style.display = "none";
        summaryBar.style.display = "none"; bulkBar.style.display = "none";
        emptyEl.style.display = "flex"; slipBanner.style.display = "none";
        sandwichBanner.style.display = "none"; dedPanel.style.display = "none";
        attendanceData = {}; originalData = {}; otMinutesData = {}; dirtyDates.clear();
        holidayDates = {}; dailyRateMap = {}; joiningDate = null; leftDate = null;
        sandwichEligible = {}; sandwichUnpaid = {}; ssaDeductions = []; ssaTotalDed = 0;
        dedOpen = false; dedBodyWrap.style.display = "none"; dedIcon.innerHTML = "&#9654;";
        clearInfoPanel();
    }
    clearBtn.addEventListener("click", resetPage);

    // ════════════════════════════════════════════════════════════════════════
    //  SAVE
    // ════════════════════════════════════════════════════════════════════════
    saveBtn.addEventListener("click", function () {
        if (isSaving) return;
        var employee = employeeSel.value;
        if (!employee || !yearSel.value || monthSel.value === "") {
            frappe.show_alert({ message: "Please load attendance first.", indicator: "orange" }); return;
        }
        var records = [];
        tbody.querySelectorAll("tr[data-date]").forEach(function (row) {
            if (row.classList.contains("dwa-future-row")) return;
            var dk = row.getAttribute("data-date");
            if (!dirtyDates.has(dk)) return;
            var rec = attendanceData[dk] || {};
            var entry = {
                employee: employee,
                attendance_date: dk,
                ot_hours: formatOtHHMM(otMinutesData[dk] || 0) || "",
                daily_rate: dailyRateMap[dk] || 0
            };
            if (rec.mode === "full") {
                if (!rec.status) return;
                entry.mode   = "full";
                entry.status = rec.status;
            } else if (rec.mode === "half") {
                entry.mode = "half";
            } else return;
            records.push(entry);
        });
        if (!records.length) { frappe.show_alert({ message: "No changes to save.", indicator: "orange" }); return; }

        isSaving = true; saveBtn.textContent = "Saving\u2026";
        frappe.call({
            method: "saral_hr.saral_hr.page.daily_wage_attendance.daily_wage_attendance.save_daily_wage_attendance_batch",
            args: { attendance_data: records },
            callback: function (r) {
                isSaving = false; saveBtn.textContent = "&#128190; Save Attendance";
                if (r.message && r.message.success) {
                    frappe.show_alert({ message: (r.message.saved_count || records.length) + " record(s) saved.", indicator: "green" });
                    setTimeout(loadAttendance, 400);
                } else {
                    frappe.show_alert({ message: (r.message && r.message.error) || "Error saving.", indicator: "red" });
                }
            },
            error: function () { isSaving = false; saveBtn.textContent = "&#128190; Save Attendance"; frappe.show_alert({ message: "Error saving.", indicator: "red" }); }
        });
    });

    document.addEventListener("keydown", function (e) {
        if ((e.ctrlKey || e.metaKey) && e.key === "s") { e.preventDefault(); saveBtn.click(); }
    });
}

// ════════════════════════════════════════════════════════════════════════════
//  STYLES
// ════════════════════════════════════════════════════════════════════════════
function inject_dwa_styles() {
    if (document.getElementById("dwa-styles")) return;
    var style = document.createElement("style");
    style.id = "dwa-styles";
    style.innerHTML = `
        .dwa-wrap { padding:0 4px; display:flex; flex-direction:column; gap:0; }
        .dwa-header-actions { display:flex; align-items:center; gap:10px; margin-left:20px; }

        .dwa-btn { background:var(--control-bg,#f4f5f6); color:var(--text-color); border:1px solid var(--border-color,#d1d8dd); border-radius:5px; padding:6px 16px; font-weight:500; cursor:pointer; font-size:13px; white-space:nowrap; transition:background 0.15s; }
        .dwa-btn-primary { background:var(--primary) !important; color:#fff !important; border-color:var(--primary) !important; }
        .dwa-btn-primary:hover { opacity:0.88; }
        .dwa-btn:hover:not(.dwa-btn-primary) { background:var(--control-bg-on-gray,#eee); }

        .dwa-filters-bar { display:flex; gap:14px; align-items:flex-end; padding:16px 0 14px; border-bottom:1px solid var(--border-color,#e5e7eb); flex-wrap:wrap; }
        .dwa-filter-group { display:flex; flex-direction:column; gap:4px; }
        .dwa-filter-employee { flex:1; min-width:200px; max-width:340px; position:relative; }
        .dwa-filter-actions { display:flex; gap:8px; align-items:flex-end; }
        .dwa-label { font-size:11px; font-weight:600; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.04em; }
        .dwa-input { height:32px; padding:0 10px; border:1px solid var(--border-color,#d1d8dd); border-radius:4px; font-size:13px; background:var(--card-bg,#fff); color:var(--text-color); box-sizing:border-box; width:100%; min-width:140px; }
        .dwa-input:focus { outline:none; border-color:var(--primary); box-shadow:0 0 0 2px rgba(45,108,223,0.12); }
        .dwa-search-wrapper { position:relative; }
        .dwa-search-input { padding-right:30px; }
        .dwa-clear-btn { position:absolute; right:8px; top:50%; transform:translateY(-50%); width:18px; height:18px; border-radius:50%; background:var(--text-muted); border:none; color:#fff; font-size:11px; cursor:pointer; display:none; align-items:center; justify-content:center; }
        .dwa-clear-btn::before { content:'\\2715'; }
        .dwa-clear-btn.show { display:flex !important; }
        .dwa-search-dropdown { display:none; position:absolute; top:100%; left:0; right:0; background:var(--card-bg,#fff); border:1px solid var(--border-color,#d1d8dd); border-top:none; border-radius:0 0 4px 4px; max-height:260px; overflow-y:auto; box-shadow:0 4px 12px rgba(0,0,0,0.1); z-index:9999; }
        .dwa-search-dropdown.show { display:block; }
        .dwa-result-item { padding:8px 12px; cursor:pointer; border-bottom:1px solid var(--border-color,#f0f0f0); }
        .dwa-result-item:last-child { border-bottom:none; }
        .dwa-result-item:hover,.dwa-result-item.selected { background:var(--control-bg,#f4f5f6); }
        .dwa-result-name { font-size:13px; font-weight:500; }
        .dwa-result-id   { font-size:11px; color:var(--text-muted); margin-top:1px; }
        .dwa-hl { font-weight:700; }
        .dwa-no-results { padding:12px; font-size:13px; color:var(--text-muted); text-align:center; }

        /* ── Info notices ──────────────────────────────────────────────── */
        #dwa_info_panel { display:none; flex-direction:column; gap:8px; padding:10px 0 2px; }
        .dwa-notice { display:flex; align-items:flex-start; gap:10px; padding:10px 14px;
                      border-radius:6px; border:1px solid; font-size:12.5px; line-height:1.5; }
        .dwa-notice-warn { background:#fffbeb; border-color:#fbbf24; border-left:4px solid #f59e0b; color:#92400e; }
        .dwa-notice-info { background:#eff6ff; border-color:#93c5fd; border-left:4px solid #3b82f6; color:#1e40af; }
        .dwa-notice-icon { font-size:15px; flex-shrink:0; margin-top:1px; }
        .dwa-notice-body { flex:1; }
        .dwa-notice-body strong { font-weight:700; }
        .dwa-notice-link { flex-shrink:0; align-self:center; font-size:12px; font-weight:600;
                           padding:3px 10px; border-radius:4px; border:1px solid currentColor;
                           text-decoration:none; white-space:nowrap; opacity:0.85; transition:opacity 0.15s; }
        .dwa-notice-link:hover { opacity:1; }
        /* ─────────────────────────────────────────────────────────────── */

        .dwa-summary-bar { display:flex; gap:10px; padding:12px 0; flex-wrap:wrap; }
        .dwa-summary-card { flex:1; min-width:80px; background:var(--card-bg,#fff); border:1px solid var(--border-color,#e5e7eb); border-radius:8px; padding:10px 14px; display:flex; flex-direction:column; align-items:center; gap:2px; }
        .dwa-card-val { font-size:20px; font-weight:700; line-height:1; }
        .dwa-card-lbl { font-size:10px; font-weight:600; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.04em; text-align:center; }
        .dwa-card-total   .dwa-card-val { color:var(--text-color); }
        .dwa-card-present .dwa-card-val { color:#28a745; }
        .dwa-card-absent  .dwa-card-val { color:#e74c3c; }
        .dwa-card-halfday .dwa-card-val { color:#f59e0b; }
        .dwa-card-holiday .dwa-card-val { color:#6f42c1; }
        .dwa-card-payment .dwa-card-val { color:#0d6efd; }
        .dwa-card-unmarked .dwa-card-val{ color:var(--text-muted); }
        .dwa-card-hours   .dwa-card-val { color:#0ea5e9; font-size:16px; }
        .dwa-card-basepay  { border:1.5px solid #0d6efd44 !important; }
        .dwa-card-basepay  .dwa-card-val { color:#0d6efd; font-size:16px; }
        .dwa-card-otpayable{ border:1.5px solid #f59e0b44 !important; }
        .dwa-card-otpayable .dwa-card-val { color:#b45309; font-size:16px; }
        .dwa-card-payable  { border:2px solid #16a34a !important; background:linear-gradient(135deg,#f0fdf4,#dcfce7) !important; }
        .dwa-card-payable  .dwa-card-val { color:#16a34a; font-size:18px; }
        .dwa-card-payable  .dwa-card-lbl { color:#15803d; font-weight:700; }

        .dwa-ded-panel { border:1px solid var(--border-color,#e5e7eb); border-radius:8px; margin:8px 0 0; overflow:hidden; }
        .dwa-ded-toggle { width:100%; display:flex; align-items:center; gap:10px; padding:10px 16px; background:var(--control-bg,#f8f9fa); border:none; cursor:pointer; text-align:left; font-size:13px; color:var(--text-color); transition:background 0.15s; border-radius:0; }
        .dwa-ded-toggle:hover { background:var(--control-bg-on-gray,#f0f1f2); }
        .dwa-ded-toggle-icon  { font-size:10px; color:var(--text-muted); width:12px; flex-shrink:0; }
        .dwa-ded-toggle-title { font-weight:600; }
        .dwa-ded-toggle-sub   { font-size:11px; color:var(--text-muted); margin-left:4px; }
        .dwa-ded-toggle-totals { margin-left:auto; display:flex; gap:6px; align-items:center; }
        .dwa-ded-badge { font-size:11px; font-weight:600; padding:2px 8px; border-radius:20px; white-space:nowrap; }
        .dwa-ded-badge-ded { background:#fdf2f2; color:#c0392b; border:1px solid #f5b7b1; }
        .dwa-ded-badge-net { background:#f0fdf4; color:#16a34a; border:1px solid #a3d9b1; }
        .dwa-ded-body-wrap { border-top:1px solid var(--border-color,#e5e7eb); }
        .dwa-ded-chips { display:flex; flex-wrap:wrap; gap:8px; padding:12px 16px; }
        .dwa-ded-chip  { display:flex; align-items:center; gap:6px; background:var(--control-bg,#f3f4f6); border:1px solid var(--border-color,#e5e7eb); border-radius:6px; padding:5px 12px; }
        .dwa-ded-chip-abbr { font-size:11px; font-weight:700; color:var(--primary,#2d6adf); background:rgba(45,108,223,0.08); border-radius:4px; padding:1px 6px; }
        .dwa-ded-chip-name { font-size:12px; color:var(--text-color); }
        .dwa-ded-chip-amt  { font-size:13px; font-weight:600; color:#c0392b; margin-left:4px; }
        .dwa-ded-footer    { border-top:1px solid var(--border-color,#e5e7eb); }
        .dwa-ded-foot-grid { display:flex; flex-direction:column; }
        .dwa-ded-foot-row  { display:flex; align-items:center; justify-content:space-between; padding:9px 16px; border-bottom:1px solid var(--border-color,#f0f0f0); }
        .dwa-ded-foot-row:last-child { border-bottom:none; }
        .dwa-ded-foot-lbl  { font-size:12px; color:var(--text-muted); }
        .dwa-ded-foot-val  { font-size:13px; font-weight:600; color:var(--text-color); }
        .dwa-ded-foot-ded  { color:#c0392b; }
        .dwa-ded-foot-net-row { background:var(--control-bg,#f8f9fa); }
        .dwa-ded-foot-net  { font-size:16px; font-weight:700; color:#16a34a; }

        .dwa-sandwich-banner { display:flex; gap:12px; align-items:flex-start; background:#fff8f0; border:1px solid #f59e0b; border-left:4px solid #f59e0b; border-radius:6px; padding:12px 16px; margin:10px 0 0; }
        .dwa-sw-icon { font-size:18px; flex-shrink:0; margin-top:1px; }
        .dwa-sw-content { display:flex; flex-direction:column; gap:4px; }
        .dwa-sw-title { font-size:13px; font-weight:600; color:#92400e; }
        .dwa-sw-sub   { font-size:12px; color:#a16207; line-height:1.5; }
        .dwa-sw-dates { display:flex; flex-wrap:wrap; gap:6px; margin-top:6px; }
        .dwa-sw-date-chip { background:#fef3c7; border:1px solid #fcd34d; border-radius:4px; padding:3px 8px; font-size:11px; font-weight:500; color:#92400e; }

        .dwa-bulk-bar { display:flex; align-items:center; gap:8px; padding:8px 0; flex-wrap:wrap; border-bottom:1px solid var(--border-color,#e5e7eb); }
        .dwa-bulk-label { font-size:12px; color:var(--text-muted); font-weight:500; margin-right:4px; }
        .dwa-pill-btn { border:none; border-radius:20px; padding:4px 14px; font-size:12px; font-weight:600; cursor:pointer; transition:opacity 0.15s; color:#fff; }
        .dwa-pill-present { background:#28a745; } .dwa-pill-absent { background:#e74c3c; }
        .dwa-pill-btn:hover { opacity:0.85; }

        .dwa-loading { display:flex; align-items:center; justify-content:center; gap:12px; padding:48px 0; }
        .dwa-spinner { width:28px; height:28px; border:3px solid var(--border-color,#e5e7eb); border-top-color:var(--primary); border-radius:50%; animation:dwa-spin 0.7s linear infinite; }
        @keyframes dwa-spin { to { transform:rotate(360deg); } }
        .dwa-loading-text { font-size:13px; color:var(--text-muted); }

        .dwa-table-scroll { overflow-x:auto; border-top:1px solid var(--border-color,#e5e7eb); }
        .dwa-table { width:100%; border-collapse:collapse; font-size:12px; }
        .dwa-th { background:var(--control-bg,#f7f7f7); border:1px solid var(--border-color,#d1d8dd); padding:8px; font-size:11px; font-weight:600; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.04em; white-space:nowrap; position:sticky; top:0; z-index:10; text-align:center; }
        .dwa-th-date   { text-align:left; min-width:150px; }
        .dwa-th-day    { text-align:left; min-width:90px; }
        .dwa-th-status { min-width:64px; }
        .dwa-th-hours  { min-width:90px; }
        .dwa-th-rate   { min-width:100px; }
        .dwa-th-rowamt { min-width:130px; }
        .dwa-td { border:1px solid var(--border-color,#d1d8dd); padding:5px 8px; vertical-align:middle; }
        .dwa-table tbody tr:nth-child(even) .dwa-td { background:rgba(0,0,0,0.013); }
        .dwa-row:hover     .dwa-td { background:rgba(45,108,223,0.03) !important; }
        .dwa-row-dirty     .dwa-td { background:rgba(245,158,11,0.07) !important; }
        .dwa-row-halfday   .dwa-td { background:rgba(251,191,36,0.05) !important; }
        .dwa-row-holiday   .dwa-td { background:rgba(224,154,42,0.06) !important; }
        .dwa-row-sandwich  .dwa-td { background:rgba(220,53,69,0.06) !important; }
        .dwa-future-row    .dwa-td { opacity:0.4; }
        .dwa-date-cell    { font-size:12px; font-weight:500; white-space:nowrap; }
        .dwa-day-cell     { font-size:12px; color:var(--text-muted); white-space:nowrap; }
        .dwa-date-holiday { color:#c05800 !important; font-weight:600 !important; }
        .dwa-sandwich-badge { font-size:11px; cursor:help; }

        .dwa-status-cell { text-align:center; cursor:pointer; }
        .dwa-status-cell:hover { background:rgba(0,0,0,0.04) !important; }
        .dwa-cell-disabled { opacity:0.2 !important; pointer-events:none !important; cursor:default !important; }
        .dwa-col-dot { width:16px; height:16px; border-radius:50%; border:2px solid #c8cdd2; margin:0 auto; transition:all 0.13s; background:transparent; box-sizing:border-box; }
        .dwa-col-dot.active { border-color:transparent; }
        .dwa-col-dot.present-dot { background:#28a745; border-color:#28a745; }
        .dwa-col-dot.absent-dot  { background:#e74c3c; border-color:#e74c3c; }
        .dwa-col-dot.holiday-dot { background:#e09a2a; border-color:#e09a2a; }
        .dwa-col-dot.halfday-dot { background:#f59e0b; border-color:#f59e0b; box-shadow:0 0 0 2px rgba(245,158,11,0.22); }

        .dwa-hours-cell { text-align:center; }
        .dwa-hours-input { width:72px; border:1px solid var(--border-color,#d1d8dd); border-radius:4px; padding:3px 6px; font-size:13px; text-align:center; background:var(--card-bg,#fff); color:var(--text-color); box-sizing:border-box; font-variant-numeric:tabular-nums; letter-spacing:0.03em; }
        .dwa-hours-input:focus { outline:none; border-color:var(--primary); box-shadow:0 0 0 2px rgba(45,108,223,0.10); }
        .dwa-hours-input::placeholder { color:#b0b8c4; }
        .dwa-rate-cell   { text-align:right; font-size:12px; font-weight:600; color:#0ea5e9; white-space:nowrap; }
        .dwa-rowamt-cell { text-align:right; font-size:12px; font-weight:500; color:var(--text-muted); white-space:nowrap; }
        .dwa-rowamt-cell.dwa-rowamt-has { color:#16a34a; font-weight:600; }
        .dwa-ot-extra    { font-size:11px; color:#b45309; font-weight:500; }

        .dwa-empty { display:flex; flex-direction:column; align-items:center; justify-content:center; padding:64px 0; gap:10px; }
        .dwa-empty-icon  { font-size:40px; }
        .dwa-empty-title { font-size:16px; font-weight:600; color:var(--text-color); }
        .dwa-empty-sub   { font-size:13px; color:var(--text-muted); }

        .page-head-content { padding:8px 17px 0 0 !important; }
    `;
    document.head.appendChild(style);
}