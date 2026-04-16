frappe.pages["mark-attendance"].on_page_load = function (wrapper) {
    frappe.ui.make_app_page({ parent: wrapper, title: "Mark Attendance" });
    $(wrapper).find(".layout-side-section").hide();
    inject_ma_styles();
    inject_ma_audio();
};

frappe.pages["mark-attendance"].on_page_show = function (wrapper) {
    var $main = $(wrapper).find(".layout-main-section");
    $main.html(get_ma_html());

    var $head = $(wrapper).find(".page-head-content");
    $head.find(".ma-header-actions").remove();
    $head.append(`
        <div class="ma-header-actions">
            <a id="ma_goto_attendance" class="ma-link">Attendance</a>
            <span class="ma-link-sep">|</span>
            <a id="ma_get_info" class="ma-link">&#128197; Get Attendance Info</a>
            <button id="ma_save_attendance" class="ma-btn ma-btn-primary">Save</button>
        </div>
    `);

    init_mark_attendance($main);
};

function get_year_options() {
    var current = new Date().getFullYear();
    var html = '<option value="">Select Year</option>';
    for (var y = current - 1; y <= current + 1; y++) {
        html += '<option value="' + y + '"' + (y === current ? ' selected' : '') + '>' + y + '</option>';
    }
    return html;
}

function get_ma_html() {
    return `
    <div class="ma-wrap">
        <div class="ma-sticky" id="ma_sticky_bar">
            <div class="ma-top-wrap">
            <div class="ma-left-block">
            <div class="ma-row1">
                <div class="ma-r1-company">
                    <label class="ma-label">Company</label>
                    <select id="ma_company" class="ma-input">
                        <option value="">Select Company</option>
                    </select>
                </div>
                <div class="ma-r1-employee">
                    <label class="ma-label">Employee</label>
                    <div class="ma-search-wrapper">
                        <input type="text" id="ma_employee_search" class="ma-input ma-search-input"
                            placeholder="Search Employee" autocomplete="off" disabled />
                        <button type="button" id="ma_clear_search" class="ma-clear-btn"></button>
                        <div id="ma_search_results" class="ma-search-dropdown"></div>
                    </div>
                    <select id="ma_employee" style="display:none !important; height:0; width:0; position:absolute; visibility:hidden;">
                        <option value="">Select Employee</option>
                    </select>
                </div>
                <div class="ma-r1-weeklyoff">
                    <label class="ma-label">Weekly Off</label>
                    <input type="text" id="ma_weekly_off" class="ma-input" readonly>
                </div>
            </div>
            <div class="ma-row2">
                <div class="ma-r2-year">
                    <label class="ma-label">Year</label>
                    <select id="ma_year" class="ma-input">
                        ${get_year_options()}
                    </select>
                </div>
                <div class="ma-r2-month">
                    <label class="ma-label">Month</label>
                    <select id="ma_month" class="ma-input">
                        <option value="">Select Month</option>
                        <option value="0">January</option>
                        <option value="1">February</option>
                        <option value="2">March</option>
                        <option value="3">April</option>
                        <option value="4">May</option>
                        <option value="5">June</option>
                        <option value="6">July</option>
                        <option value="7">August</option>
                        <option value="8">September</option>
                        <option value="9">October</option>
                        <option value="10">November</option>
                        <option value="11">December</option>
                    </select>
                </div>
                <div class="ma-r2-buttons">
                    <label class="ma-label">Mark remaining days as:</label>
                    <div class="ma-bulk-btns">
                        <button id="ma_mark_present"  class="ma-btn">Present</button>
                        <button id="ma_mark_absent"   class="ma-btn">Absent</button>
                        <button id="ma_mark_halfday"  class="ma-btn">Half Day</button>
                        <button id="ma_mark_lwp"      class="ma-btn">LWP</button>
                    </div>
                </div>
            </div>
            </div>

            <div class="ma-r1-leave">
                <table class="ma-leave-table">
                    <thead>
                        <tr>
                            <th class="ma-leave-th ma-leave-type-hdr">Leave Type</th>
                            <th class="ma-leave-th">Earned</th>
                            <th class="ma-leave-th">Casual</th>
                            <th class="ma-leave-th ma-leave-eco-hdr ma-eco-col">Comp Off</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td class="ma-leave-row-label">Available</td>
                            <td class="ma-leave-val ma-leave-bal">—</td>
                            <td class="ma-leave-val ma-leave-bal">—</td>
                            <td class="ma-leave-val ma-leave-eco-val ma-eco-col" id="ma_eco_available">0</td>
                        </tr>
                        <tr>
                            <td class="ma-leave-row-label">Earned</td>
                            <td class="ma-leave-val ma-leave-bal">—</td>
                            <td class="ma-leave-val ma-leave-bal">—</td>
                            <td class="ma-leave-val ma-leave-eco-val ma-eco-col" id="ma_eco_earned">0</td>
                        </tr>
                        <tr>
                            <td class="ma-leave-row-label">Taken</td>
                            <td class="ma-leave-val" id="ma_el_taken">0</td>
                            <td class="ma-leave-val" id="ma_cl_taken">0</td>
                            <td class="ma-leave-val ma-leave-eco-val ma-eco-col" id="ma_eco_used">0</td>
                        </tr>
                        <tr>
                            <td class="ma-leave-row-label">Balance</td>
                            <td class="ma-leave-val ma-leave-bal">0</td>
                            <td class="ma-leave-val ma-leave-bal">0</td>
                            <td class="ma-leave-val ma-leave-eco-val ma-eco-col" id="ma_eco_balance">0</td>
                        </tr>
                    </tbody>
                </table>
            </div>
            </div>

            <input type="hidden" id="ma_start_date">
            <input type="hidden" id="ma_end_date">
        </div>

        <div class="ma-table-scroll" id="ma_table_scroll">
            <table class="ma-table" id="ma_table" style="display:none;">
                <thead>
                    <tr class="ma-thead-row">
                        <th rowspan="2" class="ma-th-date">
                            <div class="ma-th-inner ma-th-left"><span class="ma-th-label">Date</span></div>
                        </th>
                        <th rowspan="2" class="ma-th-day">
                            <div class="ma-th-inner ma-th-left"><span class="ma-th-label">Day</span></div>
                        </th>
                        <th rowspan="2" class="ma-th-override">
                            <div class="ma-th-inner"><span class="ma-th-label">Override<br>Rest Day</span></div>
                        </th>
                        <th rowspan="2" class="ma-th-status">
                            <div class="ma-th-inner">
                                <span class="ma-th-label">Present</span>
                                <span class="ma-col-count" id="ma_cnt_regular">0</span>
                            </div>
                        </th>
                        <th rowspan="2" class="ma-th-status">
                            <div class="ma-th-inner">
                                <span class="ma-th-label">On Tour</span>
                                <span class="ma-col-count" id="ma_cnt_ontour">0</span>
                            </div>
                        </th>
                        <th rowspan="2" class="ma-th-status ma-eco-th-col">
                            <div class="ma-th-inner">
                                <span class="ma-th-label">Earned<br>Comp Off</span>
                                <span class="ma-col-count" id="ma_cnt_eco">0</span>
                            </div>
                        </th>
                        <th rowspan="2" class="ma-th-status">
                            <div class="ma-th-inner">
                                <span class="ma-th-label">Absent</span>
                                <span class="ma-col-count" id="ma_cnt_absent">0</span>
                            </div>
                        </th>
                        <th rowspan="2" class="ma-th-status">
                            <div class="ma-th-inner">
                                <span class="ma-th-label">LWP</span>
                                <span class="ma-col-count" id="ma_cnt_lwp">0</span>
                            </div>
                        </th>
                        <th rowspan="2" class="ma-th-status">
                            <div class="ma-th-inner">
                                <span class="ma-th-label">Earned<br>Leave</span>
                                <span class="ma-col-count" id="ma_cnt_el">0</span>
                            </div>
                        </th>
                        <th rowspan="2" class="ma-th-status">
                            <div class="ma-th-inner">
                                <span class="ma-th-label">Casual<br>Leave</span>
                                <span class="ma-col-count" id="ma_cnt_cl">0</span>
                            </div>
                        </th>
                        <th rowspan="2" class="ma-th-status ma-coff-th-col">
                            <div class="ma-th-inner">
                                <span class="ma-th-label">Comp Off</span>
                                <span class="ma-col-count" id="ma_cnt_coff">0</span>
                            </div>
                        </th>
                        <th rowspan="2" class="ma-th-status">
                            <div class="ma-th-inner">
                                <span class="ma-th-label">Weekly Off</span>
                                <span class="ma-col-count" id="ma_cnt_wo">0</span>
                            </div>
                        </th>
                        <th rowspan="2" class="ma-th-status">
                            <div class="ma-th-inner">
                                <span class="ma-th-label">Holiday</span>
                                <span class="ma-col-count" id="ma_cnt_holiday">0</span>
                            </div>
                        </th>
                        <th colspan="2" class="ma-th-hd-group">
                            <div class="ma-th-hd-top-wrap">
                                <span class="ma-th-label">Half Day</span>
                                <span class="ma-col-count" id="ma_cnt_hd_total">0</span>
                            </div>
                        </th>
                    </tr>
                    <tr class="ma-thead-row2">
                        <th class="ma-th-hd1">
                            <div class="ma-th-inner ma-th-sub">
                                <span class="ma-th-label">First Half</span>
                            </div>
                        </th>
                        <th class="ma-th-hd2">
                            <div class="ma-th-inner ma-th-sub">
                                <span class="ma-th-label">Second Half</span>
                            </div>
                        </th>
                    </tr>
                </thead>
                <tbody id="ma_table_body" tabindex="0"></tbody>
            </table>

            <div id="ma_table_loading" class="ma-table-loading" style="display:none;">
                <div class="ma-spinner"></div>
                <div class="ma-loading-text">Loading attendance…</div>
            </div>
        </div>
    </div>

    <!-- Half-day panel portal -->
    <div id="ma_hd_panel" class="ma-hd-panel" style="display:none;">
        <div class="ma-hd-panel-inner">
            <div class="ma-hd-panel-header">
                <div class="ma-hd-panel-header-info">
                    <span class="ma-hd-panel-title" id="ma_hd_panel_title">Half Day</span>
                    <span class="ma-hd-panel-date" id="ma_hd_panel_date"></span>
                </div>
                <button class="ma-hd-panel-close" id="ma_hd_panel_close">&#x2715;</button>
            </div>
            <div class="ma-hd-panel-body">
                <div class="ma-hd-col">
                    <div class="ma-hd-col-label">First Half</div>
                    <div class="ma-hd-options" id="ma_hd_opts_first"></div>
                </div>
                <div class="ma-hd-divider"></div>
                <div class="ma-hd-col">
                    <div class="ma-hd-col-label">Second Half</div>
                    <div class="ma-hd-options" id="ma_hd_opts_second"></div>
                </div>
            </div>
            <div class="ma-hd-panel-footer">
                <button class="ma-btn" id="ma_hd_clear_btn">Clear</button>
                <button class="ma-btn ma-btn-primary" id="ma_hd_apply_btn">Apply</button>
            </div>
        </div>
    </div>

    <!-- Calendar modal -->
    <div id="ma_cal_modal" class="ma-cal-modal">
        <div class="ma-cal-content">
            <button class="ma-cal-close" id="ma_cal_close">&#x2715;</button>
            <div class="ma-cal-body">
                <div class="ma-year-selector">
                    <button class="ma-year-nav" id="ma_year_prev">&#8249;</button>
                    <div class="ma-year-center">
                        <span id="ma_cal_year" class="ma-year-num">2025</span>
                        <span class="ma-year-sub">Employee Attendance Info</span>
                    </div>
                    <button class="ma-year-nav" id="ma_year_next">&#8250;</button>
                </div>
                <div class="ma-cal-legend">
                    <div class="ma-legend-item"><span class="ma-legend-dot present"></span>Present</div>
                    <div class="ma-legend-item"><span class="ma-legend-dot on-tour"></span>On Tour</div>
                    <div class="ma-legend-item ma-eco-legend-item"><span class="ma-legend-dot eco"></span>Earned Comp Off</div>
                    <div class="ma-legend-item"><span class="ma-legend-dot absent"></span>Absent</div>
                    <div class="ma-legend-item"><span class="ma-legend-dot halfday"></span>Half Day</div>
                    <div class="ma-legend-item"><span class="ma-legend-dot lwp"></span>LWP</div>
                    <div class="ma-legend-item"><span class="ma-legend-dot el"></span>Earned Leave</div>
                    <div class="ma-legend-item"><span class="ma-legend-dot cl"></span>Casual Leave</div>
                    <div class="ma-legend-item ma-coff-legend-item"><span class="ma-legend-dot coff"></span>Comp Off</div>
                    <div class="ma-legend-item"><span class="ma-legend-dot holiday"></span>Holiday</div>
                    <div class="ma-legend-item"><span class="ma-legend-dot weekend"></span>Weekly Off</div>
                </div>
                <div class="ma-months-grid" id="ma_months_grid"></div>
            </div>
        </div>
    </div>
    `;
}

// ════════════════════════════════════════════════════════════════════════════
//  INIT
// ════════════════════════════════════════════════════════════════════════════
function init_mark_attendance($main) {

    var employees = [];
    var filteredEmployees = [];
    var selectedIndex = -1;
    var searchDebounceTimer = null;
    var isSaving = false;
    var currentCalendarYear = new Date().getFullYear();
    var yearAttendanceData = {};
    var yearHolidayData = {};
    var employeeCompanyMap = {};
    var employeeWeeklyOffMap = {};
    var calendarCache = {};
    var joiningDateMap = {};
    var leftDateMap = {};

    // ── NEW: tracks whether current employee's category has_subtype ──
    var employeeHasSubtypeMap = {};   // employee name → true/false
    var currentEmployeeHasSubtype = false;

    var attendanceTableData = {};
    var originalAttendanceData = {};
    var dirtyDates = new Set();
    var holidayDates = {};
    var rowMetaMap = {};

    // ── Half-day panel state ──
    var hdPanelTarget = null;
    var hdPanelFirstVal = "";
    var hdPanelSecondVal = "";

    var focusedCell = null;

    // Base lists — ECO and Comp Off may be hidden per employee
    var ALL_FULL_DAY_STATUSES = [
        "Present", "On Tour", "Earned Comp Off",
        "Absent",
        "LWP", "Earned Leave", "Casual Leave", "Comp Off",
        "Weekly Off", "Holiday"
    ];
    var ALL_HALF_OPTIONS = [
        "Present", "On Tour", "Earned Comp Off",
        "Absent", "Earned Leave", "Casual Leave", "Comp Off", "LWP"
    ];

    // Active lists — updated when employee changes
    var FULL_DAY_STATUSES = ALL_FULL_DAY_STATUSES.slice();
    var HALF_OPTIONS       = ALL_HALF_OPTIONS.slice();
    var TOTAL_STATUS_COLS  = FULL_DAY_STATUSES.length + 2; // 12

    var PRESENT_TYPE = new Set(["Present", "On Tour", "Earned Comp Off"]);
    var ABSENT_TYPE  = new Set(["Absent", "LWP", "Earned Leave", "Casual Leave", "Comp Off"]);

    var HD_PILL_CLASS = {
        "Present":          "ma-hd-pill-present",
        "On Tour":          "ma-hd-pill-ontour",
        "Earned Comp Off":  "ma-hd-pill-eco",
        "Absent":           "ma-hd-pill-absent",
        "Earned Leave":     "ma-hd-pill-el",
        "Casual Leave":     "ma-hd-pill-cl",
        "Comp Off":         "ma-hd-pill-coff",
        "LWP":              "ma-hd-pill-lwp",
    };
    var HD_DOT_COLOR = {
        "Present":          "#28a745",
        "On Tour":          "#28a745",
        "Earned Comp Off":  "#20c997",
        "Absent":           "#e74c3c",
        "Earned Leave":     "#378add",
        "Casual Leave":     "#378add",
        "Comp Off":         "#868e96",
        "LWP":              "#f0ad4e",
    };

    var searchInput   = document.getElementById("ma_employee_search");
    var searchResults = document.getElementById("ma_search_results");
    var employeeSel   = document.getElementById("ma_employee");
    var clearBtn      = document.getElementById("ma_clear_search");
    var companySel    = document.getElementById("ma_company");
    var yearSel       = document.getElementById("ma_year");
    var monthSel      = document.getElementById("ma_month");
    var startDateInput = document.getElementById("ma_start_date");
    var endDateInput   = document.getElementById("ma_end_date");
    var tableLoading  = document.getElementById("ma_table_loading");
    var tableEl       = document.getElementById("ma_table");
    var tbody         = document.getElementById("ma_table_body");
    var stickyBar     = document.getElementById("ma_sticky_bar");
    var tableScroll   = document.getElementById("ma_table_scroll");
    var hdPanel       = document.getElementById("ma_hd_panel");

    var allEmployees = [];

    // ════════════════════════════════════════════════════════════════════════
    //  ECO / COFF VISIBILITY HELPERS
    //  When currentEmployeeHasSubtype === true, hide "Earned Comp Off" and
    //  "Comp Off" from columns, thead, leave table, and half-day panel.
    // ════════════════════════════════════════════════════════════════════════

    /**
     * Rebuild FULL_DAY_STATUSES and HALF_OPTIONS based on hasSubtype flag,
     * then apply CSS to show/hide the relevant columns.
     */
    function applySubtypeVisibility(hasSubtype) {
        currentEmployeeHasSubtype = hasSubtype;

        if (hasSubtype) {
            FULL_DAY_STATUSES = ALL_FULL_DAY_STATUSES.filter(function (s) {
                return s !== "Earned Comp Off" && s !== "Comp Off";
            });
            HALF_OPTIONS = ALL_HALF_OPTIONS.filter(function (s) {
                return s !== "Earned Comp Off" && s !== "Comp Off";
            });
        } else {
            FULL_DAY_STATUSES = ALL_FULL_DAY_STATUSES.slice();
            HALF_OPTIONS       = ALL_HALF_OPTIONS.slice();
        }
        TOTAL_STATUS_COLS = FULL_DAY_STATUSES.length + 2;

        // Toggle thead columns
        document.querySelectorAll(".ma-eco-th-col, .ma-coff-th-col").forEach(function (el) {
            el.style.display = hasSubtype ? "none" : "";
        });

        // Toggle leave balance table Comp Off column
        document.querySelectorAll(".ma-eco-col").forEach(function (el) {
            el.style.display = hasSubtype ? "none" : "";
        });

        // Toggle calendar legend items
        document.querySelectorAll(".ma-eco-legend-item, .ma-coff-legend-item").forEach(function (el) {
            el.style.display = hasSubtype ? "none" : "";
        });
    }

    function updateScrollHeight() {
        if (!stickyBar || !tableScroll) return;
        var stickyH    = stickyBar.offsetHeight;
        var pageHead   = document.querySelector(".page-head");
        var pageHeadH  = pageHead ? pageHead.offsetHeight : 60;
        var BOTTOM_PAD = 16;
        var availableH = window.innerHeight - pageHeadH - stickyH - BOTTOM_PAD;
        tableScroll.style.height = Math.max(availableH, 200) + "px";
        document.documentElement.style.setProperty("--ma-sticky-bar-h", stickyH + "px");
    }
    setTimeout(updateScrollHeight, 80);
    window.addEventListener("resize", updateScrollHeight);

    // ════════════════════════════════════════════════════════════════════════
    //  EMPLOYEE LOADING
    // ════════════════════════════════════════════════════════════════════════
    frappe.call({
        method: "saral_hr.saral_hr.page.mark_attendance.mark_attendance.get_active_employees",
        callback: function (r) {
            if (!r.message) return;
            r.message.forEach(function (row) {
                var opt = document.createElement("option");
                opt.value = row.name;
                opt.text  = row.full_name + (row.aadhaar_number ? " (" + row.aadhaar_number + ")" : "");
                employeeSel.appendChild(opt);
                employeeCompanyMap[row.name]    = row.company;
                employeeWeeklyOffMap[row.name]  = row.weekly_off
                    ? [row.weekly_off.trim().toLowerCase()] : [];
            });
            allEmployees = Array.from(employeeSel.options)
                .filter(function (o) { return o.value; })
                .map(function (o) {
                    var row = r.message.find(function (e) { return e.name === o.value; }) || {};
                    return {
                        value: o.value, name: o.text.trim(),
                        emp_id: row.employee || o.value, company: row.company || ""
                    };
                });
            var seen = {};
            r.message.forEach(function (row) {
                if (row.company && !seen[row.company]) {
                    seen[row.company] = true;
                    var opt = document.createElement("option");
                    opt.value = row.company; opt.text = row.company;
                    companySel.appendChild(opt);
                }
            });
            employees = [];
            updateScrollHeight();
        }
    });

    companySel.addEventListener("change", function () {
        var sel = companySel.value;
        searchInput.value = ""; employeeSel.value = "";
        clearBtn.classList.remove("show"); searchResults.classList.remove("show");
        document.getElementById("ma_weekly_off").value = "";
        tableEl.style.display = "none";
        attendanceTableData = {}; originalAttendanceData = {}; dirtyDates.clear();
        updateCounts();
        applySubtypeVisibility(false);
        if (!sel) { searchInput.disabled = true; employees = []; return; }
        employees = allEmployees.filter(function (e) { return e.company === sel; });
        searchInput.disabled = false;
    });

    // ════════════════════════════════════════════════════════════════════════
    //  SEARCH
    // ════════════════════════════════════════════════════════════════════════
    function localSearch(term) {
        if (!term) return employees;
        var lower = term.toLowerCase();
        return employees.filter(function (e) {
            return e.name.toLowerCase().includes(lower) || e.emp_id.toLowerCase().includes(lower);
        });
    }
    function apiSearch(term, callback) {
        frappe.call({
            method: "saral_hr.saral_hr.page.mark_attendance.mark_attendance.search_employees",
            args: { query: term, company: companySel.value || "" }, freeze: false,
            callback: function (r) {
                callback(r.message ? r.message.map(function (row) {
                    return {
                        value: row.name, name: row.full_name,
                        emp_id: row.emp_id || row.employee || row.name,
                        company: row.company, weekly_off: row.weekly_off,
                        aadhaar_number: row.aadhaar_number
                    };
                }) : []);
            },
            error: function () { callback([]); }
        });
    }
    function mergeResults(local, api) {
        var seen = new Set(), merged = [];
        api.forEach(function (e)   { if (!seen.has(e.value)) { seen.add(e.value); merged.push(e); } });
        local.forEach(function (e) { if (!seen.has(e.value)) { seen.add(e.value); merged.push(e); } });
        return merged;
    }
    function handleSearch(term) {
        var localResults = localSearch(term);
        filteredEmployees = localResults; showResults(localResults, term);
        clearTimeout(searchDebounceTimer);
        if (term.length >= 2) {
            searchDebounceTimer = setTimeout(function () {
                apiSearch(term, function (apiResults) {
                    filteredEmployees = mergeResults(localResults, apiResults);
                    showResults(filteredEmployees, term);
                });
            }, 300);
        }
    }
    function escapeHtml(text) {
        if (!text) return "";
        return text.replace(/[&<>"']/g, function (m) {
            return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[m];
        });
    }
    function highlightMatch(text, term) {
        if (!term) return escapeHtml(text);
        var escaped = escapeHtml(text);
        var et = term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        return escaped.replace(new RegExp("(" + et + ")", "gi"), '<span class="ma-highlight">$1</span>');
    }
    function showResults(results, term) {
        if (!results.length) {
            searchResults.innerHTML = '<div class="ma-no-results">No employee found</div>';
            searchResults.classList.add("show"); selectedIndex = -1; return;
        }
        searchResults.innerHTML = results.map(function (emp, i) {
            return '<div class="ma-result-item" data-index="' + i + '" data-value="' + emp.value + '">' +
                '<div class="ma-result-name">' + highlightMatch(emp.name, term) + '</div>' +
                '<div class="ma-result-id">' + highlightMatch(emp.emp_id, term) + '</div>' +
                '</div>';
        }).join("");
        searchResults.classList.add("show");
        searchResults.querySelectorAll(".ma-result-item").forEach(function (item) {
            item.addEventListener("click", function () {
                var emp = filteredEmployees.find(function (e) { return e.value === item.dataset.value; })
                    || employees.find(function (e) { return e.value === item.dataset.value; });
                if (emp) selectEmployee(emp);
            });
            item.addEventListener("mouseenter", function () {
                selectedIndex = parseInt(item.dataset.index); highlightResult();
            });
        });
    }
    function highlightResult() {
        var items = searchResults.querySelectorAll(".ma-result-item");
        items.forEach(function (item, i) { item.classList.toggle("selected", i === selectedIndex); });
        if (items[selectedIndex]) items[selectedIndex].scrollIntoView({ block: "nearest" });
    }

    // ── NEW: load category has_subtype for an employee, then proceed ────────
    function loadEmployeeSubtypeAndProceed(empName, afterLoad) {
        if (employeeHasSubtypeMap[empName] !== undefined) {
            applySubtypeVisibility(employeeHasSubtypeMap[empName]);
            afterLoad();
            return;
        }
        // Fetch category linked on the Company Link record
        frappe.call({
            method: "frappe.client.get_value",
            args: {
                doctype: "Company Link",
                filters: { name: empName },
                fieldname: "category"
            },
            callback: function (r) {
                var category = r.message && r.message.category;
                if (!category) {
                    employeeHasSubtypeMap[empName] = false;
                    applySubtypeVisibility(false);
                    afterLoad();
                    return;
                }
                frappe.call({
                    method: "frappe.client.get_value",
                    args: {
                        doctype: "Category",
                        filters: { name: category },
                        fieldname: "has_subtype"
                    },
                    callback: function (r2) {
                        var hasSubtype = !!(r2.message && r2.message.has_subtype);
                        employeeHasSubtypeMap[empName] = hasSubtype;
                        applySubtypeVisibility(hasSubtype);
                        afterLoad();
                    },
                    error: function () {
                        employeeHasSubtypeMap[empName] = false;
                        applySubtypeVisibility(false);
                        afterLoad();
                    }
                });
            },
            error: function () {
                employeeHasSubtypeMap[empName] = false;
                applySubtypeVisibility(false);
                afterLoad();
            }
        });
    }

    function selectEmployee(emp) {
        searchInput.value = emp.name; employeeSel.value = emp.value;
        searchResults.classList.remove("show"); selectedIndex = -1;
        clearBtn.classList.add("show"); clearTimeout(searchDebounceTimer);
        if (emp.company    !== undefined) employeeCompanyMap[emp.value]   = emp.company;
        if (emp.weekly_off !== undefined) employeeWeeklyOffMap[emp.value] =
            emp.weekly_off ? [emp.weekly_off.trim().toLowerCase()] : [];
        document.getElementById("ma_weekly_off").value =
            (employeeWeeklyOffMap[emp.value] || [])
                .map(function (d) { return d.charAt(0).toUpperCase() + d.slice(1); }).join(", ");

        // Fetch joining/left date if needed, then load subtype, then render table
        function proceed() {
            loadEmployeeSubtypeAndProceed(emp.value, function () {
                generateTable();
                loadCompOffBalance(emp.value);
            });
        }

        if (joiningDateMap[emp.value] !== undefined) {
            proceed();
        } else {
            frappe.call({
                method: "saral_hr.saral_hr.page.mark_attendance.mark_attendance.get_employee_joining_date",
                args: { employee: emp.value },
                callback: function (r) {
                    var data = r.message || {};
                    joiningDateMap[emp.value] = data.joining_date || null;
                    leftDateMap[emp.value]    = data.left_date    || null;
                    proceed();
                }
            });
        }
    }

    function clearSearch() {
        searchInput.value = ""; employeeSel.value = "";
        document.getElementById("ma_weekly_off").value = "";
        clearBtn.classList.remove("show"); searchResults.classList.remove("show");
        tableEl.style.display = "none";
        attendanceTableData = {}; originalAttendanceData = {}; dirtyDates.clear();
        clearTimeout(searchDebounceTimer); updateCounts(); clearCompOffBalance();
        applySubtypeVisibility(false);
    }

    clearBtn.addEventListener("click", clearSearch);
    searchInput.addEventListener("focus", function () {
        var term = searchInput.value.trim().toLowerCase();
        filteredEmployees = term ? localSearch(term) : employees;
        showResults(filteredEmployees, term);
    });
    searchInput.addEventListener("input", function () {
        var term = searchInput.value.trim();
        clearBtn.classList.toggle("show", searchInput.value.length > 0);
        if (!term) {
            filteredEmployees = employees;
            if (searchInput === document.activeElement) showResults(filteredEmployees, "");
            selectedIndex = -1; clearTimeout(searchDebounceTimer); return;
        }
        handleSearch(term.toLowerCase()); selectedIndex = -1;
    });
    searchInput.addEventListener("keydown", function (e) {
        if (!searchResults.classList.contains("show")) return;
        if (e.key === "ArrowDown") {
            e.preventDefault();
            selectedIndex = (selectedIndex + 1) % filteredEmployees.length; highlightResult();
        } else if (e.key === "ArrowUp") {
            e.preventDefault();
            selectedIndex = (selectedIndex - 1 + filteredEmployees.length) % filteredEmployees.length; highlightResult();
        } else if (e.key === "Enter" && selectedIndex >= 0) {
            e.preventDefault(); selectEmployee(filteredEmployees[selectedIndex]);
        } else if (e.key === "Escape") {
            searchResults.classList.remove("show");
        }
    });
    document.addEventListener("click", function (e) {
        if (!searchInput.contains(e.target) && !searchResults.contains(e.target) && !clearBtn.contains(e.target))
            searchResults.classList.remove("show");
    });

    // ════════════════════════════════════════════════════════════════════════
    //  DATE HELPERS
    // ════════════════════════════════════════════════════════════════════════
    function updateDatesFromMonthYear() {
        if (!yearSel.value || monthSel.value === "") return;
        var year = yearSel.value, month = Number(monthSel.value);
        var lastDay = new Date(year, month + 1, 0);
        startDateInput.value = year + "-" + String(month + 1).padStart(2, "0") + "-01";
        endDateInput.value   = year + "-" + String(month + 1).padStart(2, "0") + "-" +
            String(lastDay.getDate()).padStart(2, "0");
        generateTable();
        var emp = employeeSel.value;
        if (emp) loadCompOffBalance(emp);
    }
    yearSel.addEventListener("change",  updateDatesFromMonthYear);
    monthSel.addEventListener("change", updateDatesFromMonthYear);

    function parseDateLocal(str) {
        if (!str) return null;
        var p = str.split("-");
        var d = new Date(parseInt(p[0]), parseInt(p[1]) - 1, parseInt(p[2]));
        d.setHours(0, 0, 0, 0); return d;
    }

    // ════════════════════════════════════════════════════════════════════════
    //  WEEKLY OFF LIMIT
    // ════════════════════════════════════════════════════════════════════════
    function calcMaxWeeklyOffInMonth() {
        var employee = employeeSel.value;
        if (!yearSel.value || monthSel.value === "") return 0;
        var year = parseInt(yearSel.value), month = parseInt(monthSel.value);
        var weeklyOffDays = employeeWeeklyOffMap[employee] || [];
        if (!weeklyOffDays.length) return 0;
        var joiningDate  = parseDateLocal(joiningDateMap[employee]);
        var leftDate     = parseDateLocal(leftDateMap[employee]);
        var count = 0, daysInMonth = new Date(year, month + 1, 0).getDate();
        for (var d = 1; d <= daysInMonth; d++) {
            var cd = new Date(year, month, d); cd.setHours(0, 0, 0, 0);
            if (joiningDate && cd < joiningDate) continue;
            if (leftDate    && cd > leftDate)    continue;
            var dn = cd.toLocaleDateString("en-US", { weekday: "long" }).toLowerCase();
            if (weeklyOffDays.includes(dn)) count++;
        }
        return count;
    }
    function countCurrentWeeklyOff() {
        var count = 0;
        Object.values(attendanceTableData).forEach(function (rec) {
            if (rec && rec.mode === "full" && rec.status === "Weekly Off") count++;
        });
        return count;
    }

    // ════════════════════════════════════════════════════════════════════════
    //  COUNT UPDATE
    // ════════════════════════════════════════════════════════════════════════
    function updateCounts() {
        var cnt = { present: 0, regular: 0, ontour: 0, eco: 0, absent: 0, el: 0, cl: 0, coff: 0, lwp: 0, holiday: 0, wo: 0, hd_total: 0 };
        Object.values(attendanceTableData).forEach(function (rec) {
            if (!rec) return;
            if (rec.mode === "half") {
                cnt.hd_total++;
                [rec.first_half, rec.second_half].forEach(function (h) {
                    if (!h) return;
                    if (h === "Present")          { cnt.present += 0.5; cnt.regular += 0.5; }
                    else if (h === "On Tour")     { cnt.present += 0.5; cnt.ontour  += 0.5; }
                    else if (h === "Earned Comp Off") { cnt.present += 0.5; cnt.eco  += 0.5; }
                    else if (h === "Absent")      cnt.absent += 0.5;
                    else if (h === "Earned Leave") cnt.el    += 0.5;
                    else if (h === "Casual Leave") cnt.cl    += 0.5;
                    else if (h === "Comp Off")    cnt.coff   += 0.5;
                    else if (h === "LWP")         cnt.lwp    += 0.5;
                });
            } else {
                var s = rec.status || "";
                if (s === "Present")          { cnt.present++; cnt.regular++; }
                else if (s === "On Tour")     { cnt.present++; cnt.ontour++;  }
                else if (s === "Earned Comp Off") { cnt.present++; cnt.eco++; }
                else if (s === "Absent")      cnt.absent++;
                else if (s === "Earned Leave") cnt.el++;
                else if (s === "Casual Leave") cnt.cl++;
                else if (s === "Comp Off")    cnt.coff++;
                else if (s === "LWP")         cnt.lwp++;
                else if (s === "Holiday")     cnt.holiday++;
                else if (s === "Weekly Off")  cnt.wo++;
            }
        });
        function fmt(n) { return (n % 1 === 0) ? String(n) : n.toFixed(1); }
        document.getElementById("ma_cnt_regular").textContent   = fmt(cnt.regular);
        document.getElementById("ma_cnt_ontour").textContent    = fmt(cnt.ontour);
        document.getElementById("ma_cnt_eco").textContent       = fmt(cnt.eco);
        document.getElementById("ma_cnt_absent").textContent    = fmt(cnt.absent);
        document.getElementById("ma_cnt_el").textContent        = fmt(cnt.el);
        document.getElementById("ma_cnt_cl").textContent        = fmt(cnt.cl);
        document.getElementById("ma_cnt_coff").textContent      = fmt(cnt.coff);
        document.getElementById("ma_cnt_lwp").textContent       = fmt(cnt.lwp);
        document.getElementById("ma_cnt_holiday").textContent   = fmt(cnt.holiday);
        document.getElementById("ma_cnt_wo").textContent        = fmt(cnt.wo);
        document.getElementById("ma_cnt_hd_total").textContent  = fmt(cnt.hd_total);
    }

    // ════════════════════════════════════════════════════════════════════════
    //  DIRTY TRACKING
    // ════════════════════════════════════════════════════════════════════════
    function markDirty(dateKey) {
        dirtyDates.add(dateKey);
        var row = document.querySelector('tr[data-date="' + dateKey + '"]');
        if (row) row.classList.add("ma-row-dirty");
        refreshDotDirty(dateKey);
    }
    function refreshDotDirty(dateKey) {
        var row = document.querySelector('tr[data-date="' + dateKey + '"]');
        if (!row) return;
        var isDirty = dirtyDates.has(dateKey);
        row.querySelectorAll(".ma-col-dot").forEach(function (dot) {
            dot.classList.toggle("ma-dot-dirty", isDirty);
        });
    }
    function clearDirtyAll() {
        dirtyDates.clear();
        document.querySelectorAll(".ma-row-dirty").forEach(function (r) { r.classList.remove("ma-row-dirty"); });
        document.querySelectorAll(".ma-dot-dirty").forEach(function (d) { d.classList.remove("ma-dot-dirty"); });
    }

    // ════════════════════════════════════════════════════════════════════════
    //  HALF-DAY PANEL
    // ════════════════════════════════════════════════════════════════════════
    function buildHdOption(status, currentVal, half) {
        var dotColor  = HD_DOT_COLOR[status] || "#aaa";
        var isSelected = (currentVal === status);
        var div = document.createElement("div");
        div.className = "ma-hd-opt" + (isSelected ? " ma-hd-opt-selected" : "");
        div.innerHTML =
            '<span class="ma-hd-opt-dot" style="background:' + dotColor + '"></span>' +
            '<span class="ma-hd-opt-label">' + status + '</span>' +
            '<span class="ma-hd-opt-radio' + (isSelected ? " ma-hd-opt-radio-on" : "") + '"></span>';
        div.addEventListener("click", function () {
            if (half === "first")  { hdPanelFirstVal  = isSelected ? "" : status; }
            else                   { hdPanelSecondVal = isSelected ? "" : status; }
            renderHdPanelOptions();
        });
        return div;
    }

    function renderHdPanelOptions() {
        var firstContainer  = document.getElementById("ma_hd_opts_first");
        var secondContainer = document.getElementById("ma_hd_opts_second");
        if (!firstContainer || !secondContainer) return;
        firstContainer.innerHTML  = "";
        secondContainer.innerHTML = "";
        // Use the current HALF_OPTIONS (which respects subtype visibility)
        HALF_OPTIONS.forEach(function (status) {
            firstContainer.appendChild(buildHdOption(status,  hdPanelFirstVal,  "first"));
            secondContainer.appendChild(buildHdOption(status, hdPanelSecondVal, "second"));
        });
    }

    function openHdPanel(dateKey, dayLabel, dateLabel) {
        var rec = attendanceTableData[dateKey] || {};
        hdPanelTarget  = { dateKey: dateKey };
        hdPanelFirstVal  = (rec.mode === "half") ? (rec.first_half  || "") : "";
        hdPanelSecondVal = (rec.mode === "half") ? (rec.second_half || "") : "";
        document.getElementById("ma_hd_panel_title").textContent = dateLabel;
        document.getElementById("ma_hd_panel_date").textContent  = dayLabel;
        renderHdPanelOptions();
        hdPanel.style.display = "flex";
    }

    function closeHdPanel() {
        hdPanel.style.display = "none";
        hdPanelTarget = null;
    }

    function applyHdPanel() {
        if (!hdPanelTarget) return;
        var dateKey = hdPanelTarget.dateKey;
        attendanceTableData[dateKey] = {
            mode:        "half",
            first_half:  hdPanelFirstVal,
            second_half: hdPanelSecondVal,
        };
        markDirty(dateKey);
        refreshRowVisuals(dateKey);
        updateCounts();
        closeHdPanel();
    }

    function clearHdPanel() {
        hdPanelFirstVal  = "";
        hdPanelSecondVal = "";
        renderHdPanelOptions();
    }

    document.getElementById("ma_hd_panel_close").addEventListener("click", closeHdPanel);
    document.getElementById("ma_hd_apply_btn").addEventListener("click",   applyHdPanel);
    document.getElementById("ma_hd_clear_btn").addEventListener("click",   clearHdPanel);
    hdPanel.addEventListener("click", function (e) {
        if (e.target === hdPanel) closeHdPanel();
    });

    // ════════════════════════════════════════════════════════════════════════
    //  HALF-DAY PILL HELPER
    // ════════════════════════════════════════════════════════════════════════
    function hdPillHtml(status) {
        if (!status) {
            return '<span class="ma-hd-pill ma-hd-pill-empty">Set half</span>';
        }
        var cls      = HD_PILL_CLASS[status] || "";
        var dotColor = HD_DOT_COLOR[status]  || "#aaa";
        return '<span class="ma-hd-pill ' + cls + '">' +
            '<span class="ma-hd-pill-dot" style="background:' + dotColor + '"></span>' +
            status +
            '</span>';
    }

    // ════════════════════════════════════════════════════════════════════════
    //  DOT / BADGE HELPERS
    // ════════════════════════════════════════════════════════════════════════
    function getDotClass(status) {
        if (PRESENT_TYPE.has(status)) return "active present-dot";
        if (ABSENT_TYPE.has(status))  return "active absent-dot";
        if (status === "Weekly Off")  return "active wo-dot";
        if (status === "Holiday")     return "active holiday-dot";
        return "active";
    }

    // ════════════════════════════════════════════════════════════════════════
    //  CELL ENABLE / DISABLE
    // ════════════════════════════════════════════════════════════════════════
    function setAllStatusCellsEnabled(row, enabled) {
        if (enabled) {
            row.classList.remove("ma-status-cells-disabled");
        } else {
            row.classList.add("ma-status-cells-disabled");
        }
    }

    // ════════════════════════════════════════════════════════════════════════
    //  ROW VISUAL REFRESH
    // ════════════════════════════════════════════════════════════════════════
    function refreshRowVisuals(dateKey) {
        var row = document.querySelector('tr[data-date="' + dateKey + '"]');
        if (!row) return;
        var rec = attendanceTableData[dateKey] || {};

        row.classList.remove("ma-row-halfday", "ma-row-override");

        if (rec.mode === "half") {
            row.classList.add("ma-row-halfday");
            var hd1Cell = row.querySelector(".ma-hd1-cell");
            var hd2Cell = row.querySelector(".ma-hd2-cell");
            if (hd1Cell) hd1Cell.innerHTML = hdPillHtml(rec.first_half);
            if (hd2Cell) hd2Cell.innerHTML = hdPillHtml(rec.second_half);
            row.querySelectorAll(".ma-col-dot").forEach(function (dot) { dot.className = "ma-col-dot"; });
        } else {
            var s = rec.status || "";
            row.querySelectorAll(".ma-col-dot").forEach(function (dot) {
                dot.className = "ma-col-dot" + (dot.dataset.status === s ? " " + getDotClass(s) : "");
            });
            var hd1Cell = row.querySelector(".ma-hd1-cell");
            var hd2Cell = row.querySelector(".ma-hd2-cell");
            if (hd1Cell) hd1Cell.innerHTML = hdPillHtml("");
            if (hd2Cell) hd2Cell.innerHTML = hdPillHtml("");
        }

        var toggle = row.querySelector(".ma-override-toggle");
        if (toggle) {
            var restStatus     = toggle.dataset.reststatus;
            var currentIsRest  = (rec.mode === "full") && (rec.status === restStatus);
            toggle.checked = currentIsRest;
            toggle.closest("label").title = currentIsRest
                ? "Click to override " + restStatus
                : "Click to restore "  + restStatus;
            row.classList.remove("ma-row-wo", "ma-row-holiday");
            if (currentIsRest) {
                if (restStatus === "Holiday")    row.classList.add("ma-row-holiday");
                if (restStatus === "Weekly Off") row.classList.add("ma-row-wo");
            } else {
                if (rec.mode === "full" && !rec.status) row.classList.add("ma-row-override");
            }
            setAllStatusCellsEnabled(row, !currentIsRest);
        }
        refreshDotDirty(dateKey);
    }

    // ════════════════════════════════════════════════════════════════════════
    //  KEYBOARD NAVIGATION
    // ════════════════════════════════════════════════════════════════════════
    function getRowByIdx(rowIdx) {
        return tbody.querySelector('tr[data-rowidx="' + rowIdx + '"]');
    }
    function getCellAt(rowIdx, colIdx) {
        var row = getRowByIdx(rowIdx);
        if (!row) return null;
        return row.querySelector('[data-colidx="' + colIdx + '"]');
    }
    function setFocusCell(rowIdx, colIdx) {
        tbody.querySelectorAll(".ma-cell-focused").forEach(function (el) { el.classList.remove("ma-cell-focused"); });
        focusedCell = { rowIdx: rowIdx, colIdx: colIdx };
        var td = getCellAt(rowIdx, colIdx);
        if (td) { td.classList.add("ma-cell-focused"); td.scrollIntoView({ block: "nearest", inline: "nearest" }); }
    }
    tbody.addEventListener("keydown", function (e) {
        if (!focusedCell) return;
        var r = focusedCell.rowIdx, c = focusedCell.colIdx;
        var maxRow = tbody.querySelectorAll("tr[data-rowidx]").length - 1;
        var maxCol = TOTAL_STATUS_COLS - 1;
        if (e.key === "ArrowDown") {
            e.preventDefault(); if (r < maxRow) setFocusCell(r + 1, c);
        } else if (e.key === "ArrowUp") {
            e.preventDefault(); if (r > 0) setFocusCell(r - 1, c);
        } else if (e.key === "ArrowRight") {
            e.preventDefault();
            if (c < maxCol) setFocusCell(r, c + 1); else if (r < maxRow) setFocusCell(r + 1, 0);
        } else if (e.key === "ArrowLeft") {
            e.preventDefault();
            if (c > 0) setFocusCell(r, c - 1); else if (r > 0) setFocusCell(r - 1, maxCol);
        } else if (e.key === "Tab") {
            e.preventDefault();
            if (!e.shiftKey) { if (c < maxCol) setFocusCell(r, c + 1); else if (r < maxRow) setFocusCell(r + 1, 0); }
            else             { if (c > 0) setFocusCell(r, c - 1);       else if (r > 0)      setFocusCell(r - 1, maxCol); }
        } else if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            var td = getCellAt(r, c); if (td) td.click();
        }
    });

    // ════════════════════════════════════════════════════════════════════════
    //  BUILD ROW
    // ════════════════════════════════════════════════════════════════════════
    function buildRow(dateKey, dayName, currentDate, savedRec, isHoliday, isDefaultWeeklyOff, isFuture, isOutsideTenure, rowIdx) {
        var row = document.createElement("tr");
        row.setAttribute("data-date",   dateKey);
        row.setAttribute("data-rowidx", rowIdx);

        var effectiveIsHoliday   = isHoliday           && !isOutsideTenure;
        var effectiveIsWeeklyOff = isDefaultWeeklyOff  && !isOutsideTenure;

        var isRestDay  = effectiveIsHoliday || effectiveIsWeeklyOff;
        var restStatus = effectiveIsHoliday ? "Holiday" : (effectiveIsWeeklyOff ? "Weekly Off" : "");
        var isRestMode = isRestDay && savedRec.mode === "full" &&
            (savedRec.status === "Holiday" || savedRec.status === "Weekly Off");

        rowMetaMap[dateKey] = {
            isRestDay: isRestDay, restStatus: restStatus,
            isHoliday: effectiveIsHoliday, isDefaultWeeklyOff: effectiveIsWeeklyOff,
            isOutsideTenure: isOutsideTenure
        };

        var cellsLocked = isFuture || isOutsideTenure || (isRestDay && isRestMode);

        if (isFuture || isOutsideTenure) {
            row.classList.add("ma-future-row");
            if (isOutsideTenure && !isFuture) row.classList.add("ma-before-joining-row");
        } else if (savedRec.mode === "full") {
            if (savedRec.status === "Weekly Off") row.classList.add("ma-row-wo");
            if (savedRec.status === "Holiday")    row.classList.add("ma-row-holiday");
            if (isRestDay && !isRestMode)         row.classList.add("ma-row-override");
        } else if (savedRec.mode === "half") {
            row.classList.add("ma-row-halfday");
        }
        if (cellsLocked) row.classList.add("ma-status-cells-disabled");

        var day       = currentDate.getDate();
        var dateLabel = String(day).padStart(2, "0") + " " +
            currentDate.toLocaleDateString("en-US", { month: "long" }) + " " +
            currentDate.getFullYear();

        // Date cell
        var dateTd = document.createElement("td");
        dateTd.className = "ma-date-cell";
        if (effectiveIsWeeklyOff && !effectiveIsHoliday) dateTd.classList.add("ma-date-wo");
        else if (effectiveIsHoliday) dateTd.classList.add("ma-date-holiday");
        dateTd.textContent = dateLabel;
        row.appendChild(dateTd);

        // Day cell
        var dayTd = document.createElement("td");
        dayTd.className = "ma-day-cell";
        if (effectiveIsWeeklyOff && !effectiveIsHoliday) dayTd.classList.add("ma-date-wo");
        else if (effectiveIsHoliday) dayTd.classList.add("ma-date-holiday");
        dayTd.textContent = dayName;
        row.appendChild(dayTd);

        // Override toggle
        var overrideTd = document.createElement("td");
        overrideTd.className = "ma-override-cell";
        if (isRestDay && !isFuture && !isOutsideTenure) {
            var lbl = document.createElement("label");
            lbl.className = "ma-toggle" + (restStatus === "Holiday" ? " ma-toggle-holiday" : "");
            lbl.title = isRestMode ? "Click to override " + restStatus : "Click to restore " + restStatus;
            var chk = document.createElement("input");
            chk.type      = "checkbox";
            chk.className = "ma-override-toggle";
            chk.checked   = isRestMode;
            chk.dataset.isrestday  = "true";
            chk.dataset.reststatus = restStatus;
            chk.dataset.datekey    = dateKey;
            chk.addEventListener("change", function () {
                var nowChecked = this.checked;
                if (nowChecked) {
                    if (restStatus === "Weekly Off") {
                        var limit   = calcMaxWeeklyOffInMonth();
                        var current = countCurrentWeeklyOff();
                        if (limit > 0 && current + 1 > limit) {
                            this.checked = false;
                            frappe.show_alert({ message: "Weekly Off cannot exceed <b>" + limit + " days</b> in this month.", indicator: "red" });
                            return;
                        }
                    }
                    attendanceTableData[dateKey] = { mode: "full", status: restStatus };
                } else {
                    attendanceTableData[dateKey] = { mode: "full", status: "" };
                }
                markDirty(dateKey);
                refreshRowVisuals(dateKey);
                updateCounts();
            });
            var slider = document.createElement("span");
            slider.className = "ma-toggle-slider";
            lbl.appendChild(chk); lbl.appendChild(slider);
            overrideTd.appendChild(lbl);
        } else {
            overrideTd.innerHTML = '<span class="ma-no-override">—</span>';
        }
        row.appendChild(overrideTd);

        // ── Full-day status columns (uses current FULL_DAY_STATUSES) ────────
        FULL_DAY_STATUSES.forEach(function (status, colIdx) {
            var td = document.createElement("td");
            td.className = "ma-status-cell ma-cell-" + status.toLowerCase().replace(/ /g, "_");
            td.setAttribute("data-status", status);
            td.setAttribute("data-colidx", colIdx);

            var isActive = (savedRec.mode === "full" && savedRec.status === status);
            var dot = document.createElement("div");
            dot.className = "ma-col-dot" + (isActive ? " " + getDotClass(status) : "");
            dot.setAttribute("data-status", status);

            if (!isActive) {
                if (status === "Weekly Off" && effectiveIsWeeklyOff) dot.classList.add("ma-dot-wo-hint");
                if (status === "Holiday"    && effectiveIsHoliday)   dot.classList.add("ma-dot-holiday-hint");
            }

            td.addEventListener("click", function () {
                var parentRow = td.closest("tr");
                if (parentRow && parentRow.classList.contains("ma-status-cells-disabled")) return;
                onFullDayClick(dateKey, status, effectiveIsHoliday, effectiveIsWeeklyOff);
            });
            td.addEventListener("mousedown", function () { setFocusCell(rowIdx, colIdx); });
            td.appendChild(dot);
            row.appendChild(td);
        });

        // Half Day – First Half
        var hd1Td = document.createElement("td");
        hd1Td.className = "ma-status-cell ma-hd-cell ma-hd1-cell";
        hd1Td.setAttribute("data-colidx", FULL_DAY_STATUSES.length);
        var h1Val = (savedRec.mode === "half") ? savedRec.first_half  : "";
        var h2Val = (savedRec.mode === "half") ? savedRec.second_half : "";
        hd1Td.innerHTML = hdPillHtml(h1Val);
        hd1Td.addEventListener("click", function (e) {
            e.stopPropagation();
            var parentRow = hd1Td.closest("tr");
            if (parentRow && parentRow.classList.contains("ma-status-cells-disabled")) return;
            ensureHalfDayMode(dateKey);
            openHdPanel(dateKey, dayName, dateLabel);
        });
        hd1Td.addEventListener("mousedown", function () { setFocusCell(rowIdx, FULL_DAY_STATUSES.length); });
        row.appendChild(hd1Td);

        // Half Day – Second Half
        var hd2Td = document.createElement("td");
        hd2Td.className = "ma-status-cell ma-hd-cell ma-hd2-cell";
        hd2Td.setAttribute("data-colidx", FULL_DAY_STATUSES.length + 1);
        hd2Td.innerHTML = hdPillHtml(h2Val);
        hd2Td.addEventListener("click", function (e) {
            e.stopPropagation();
            var parentRow = hd2Td.closest("tr");
            if (parentRow && parentRow.classList.contains("ma-status-cells-disabled")) return;
            ensureHalfDayMode(dateKey);
            openHdPanel(dateKey, dayName, dateLabel);
        });
        hd2Td.addEventListener("mousedown", function () { setFocusCell(rowIdx, FULL_DAY_STATUSES.length + 1); });
        row.appendChild(hd2Td);

        return row;
    }

    // ════════════════════════════════════════════════════════════════════════
    //  CLICK HANDLERS
    // ════════════════════════════════════════════════════════════════════════
    function onFullDayClick(dateKey, status, isHoliday, isDefaultWeeklyOff) {
        var rec = attendanceTableData[dateKey] || {};

        if (status === "Weekly Off") {
            var limit   = calcMaxWeeklyOffInMonth();
            var cur     = countCurrentWeeklyOff();
            var alreadyWo = (rec.mode === "full" && rec.status === "Weekly Off");
            if (limit > 0 && !alreadyWo && cur + 1 > limit) {
                frappe.show_alert({ message: "Weekly Off cannot exceed <b>" + limit + " days</b> in this month.", indicator: "red" });
                return;
            }
        }

        if (rec.mode === "half") {
            attendanceTableData[dateKey] = { mode: "full", status: status };
            markDirty(dateKey); refreshRowVisuals(dateKey); updateCounts(); return;
        }

        if (rec.mode === "full" && rec.status === status) {
            var def = isHoliday ? "Holiday" : (isDefaultWeeklyOff ? "Weekly Off" : "");
            attendanceTableData[dateKey] = def ? { mode: "full", status: def } : { mode: "full", status: "" };
        } else {
            attendanceTableData[dateKey] = { mode: "full", status: status };
        }
        markDirty(dateKey); refreshRowVisuals(dateKey); updateCounts();
    }

    function ensureHalfDayMode(dateKey) {
        var rec = attendanceTableData[dateKey] || {};
        if (rec.mode === "half") return;
        attendanceTableData[dateKey] = { mode: "half", first_half: "", second_half: "" };
        markDirty(dateKey); refreshRowVisuals(dateKey); updateCounts();
    }

    // ════════════════════════════════════════════════════════════════════════
    //  COMP OFF BALANCE
    // ════════════════════════════════════════════════════════════════════════
    function loadCompOffBalance(employee) {
        var ecoAvailable = document.getElementById("ma_eco_available");
        var ecoEarned    = document.getElementById("ma_eco_earned");
        var ecoUsed      = document.getElementById("ma_eco_used");
        var ecoBalance   = document.getElementById("ma_eco_balance");
        var elTaken      = document.getElementById("ma_el_taken");
        var clTaken      = document.getElementById("ma_cl_taken");
        if (!ecoEarned) return;
        [ecoAvailable, ecoEarned, ecoUsed, ecoBalance, elTaken, clTaken].forEach(function (el) { if (el) el.textContent = "…"; });
        frappe.call({
            method: "saral_hr.saral_hr.page.mark_attendance.mark_attendance.get_comp_off_balance",
            args: { employee: employee, year: yearSel.value, month: monthSel.value },
            callback: function (r) {
                var data = (r && r.message) ? r.message : { available: 0, earned: 0, used: 0, balance: 0, el_taken: 0, cl_taken: 0 };
                if (ecoAvailable) ecoAvailable.textContent = data.available || 0;
                ecoEarned.textContent  = data.earned  || 0;
                ecoUsed.textContent    = data.used     || 0;
                ecoBalance.textContent = data.balance  || 0;
                if (elTaken) elTaken.textContent = data.el_taken || 0;
                if (clTaken) clTaken.textContent = data.cl_taken || 0;
            },
            error: function () {
                [ecoAvailable, ecoEarned, ecoUsed, ecoBalance, elTaken, clTaken].forEach(function (el) { if (el) el.textContent = "0"; });
            }
        });
    }
    function clearCompOffBalance() {
        ["ma_eco_available", "ma_eco_earned", "ma_eco_used", "ma_eco_balance", "ma_el_taken", "ma_cl_taken"]
            .forEach(function (id) { var el = document.getElementById(id); if (el) el.textContent = "0"; });
    }

    // ════════════════════════════════════════════════════════════════════════
    //  LOADING
    // ════════════════════════════════════════════════════════════════════════
    function showTableLoading() { tableEl.style.display = "none"; tableLoading.style.display = "flex"; }
    function hideTableLoading() {
        tableLoading.style.display = "none";
        tableEl.style.display = "table";
        setTimeout(updateScrollHeight, 50);
    }

    // ════════════════════════════════════════════════════════════════════════
    //  GENERATE TABLE
    // ════════════════════════════════════════════════════════════════════════
    function resolveInitialRec(rawStatus, isHoliday, isDefaultWeeklyOff, isOutsideTenure) {
        if (!rawStatus) {
            if (!isOutsideTenure) {
                if (isHoliday)          return { mode: "full", status: "Holiday"    };
                if (isDefaultWeeklyOff) return { mode: "full", status: "Weekly Off" };
            }
            return { mode: "full", status: "" };
        }
        if (typeof rawStatus === "object" && rawStatus.mode === "half") return rawStatus;
        return { mode: "full", status: rawStatus };
    }

    function generateTable() {
        var employee  = employeeSel.value;
        var startDate = startDateInput.value;
        var endDate   = endDateInput.value;
        if (!employee || !startDate || !endDate) { tableLoading.style.display = "none"; return; }

        var weeklyOffDays = employeeWeeklyOffMap[employee] || [];
        var company       = employeeCompanyMap[employee];
        var joiningDate   = parseDateLocal(joiningDateMap[employee]);
        var leftDate      = parseDateLocal(leftDateMap[employee]);

        focusedCell = null; rowMetaMap = {};
        showTableLoading();

        frappe.call({
            method: "saral_hr.saral_hr.page.mark_attendance.mark_attendance.get_holidays_between_dates",
            args: { company: company, start_date: startDate, end_date: endDate },
            callback: function (holidayRes) {
                holidayDates = {};
                (holidayRes.message || []).forEach(function (h) { holidayDates[h] = true; });

                frappe.call({
                    method: "saral_hr.saral_hr.page.mark_attendance.mark_attendance.get_attendance_between_dates",
                    args: { employee: employee, start_date: startDate, end_date: endDate },
                    callback: function (res) {
                        var attendanceMap = res.message || {};
                        attendanceTableData = {}; originalAttendanceData = {};
                        dirtyDates.clear(); tbody.innerHTML = "";

                        var current = new Date(startDate);
                        var end     = new Date(endDate);
                        var today   = new Date(); today.setHours(0, 0, 0, 0);
                        var rowIdx  = 0;

                        while (current <= end) {
                            var cd = new Date(current); cd.setHours(0, 0, 0, 0);
                            var dayName = cd.toLocaleDateString("en-US", { weekday: "long" });
                            var dateKey = cd.getFullYear() + "-" +
                                String(cd.getMonth() + 1).padStart(2, "0") + "-" +
                                String(cd.getDate()).padStart(2, "0");

                            var isDefaultWeeklyOff = weeklyOffDays.includes(dayName.toLowerCase());
                            var isHoliday          = holidayDates[dateKey] === true;
                            var isFuture           = cd > today;
                            var isBeforeJoining    = joiningDate ? (cd < joiningDate) : false;
                            var isAfterLeft        = leftDate    ? (cd > leftDate)    : false;
                            var isOutsideTenure    = isBeforeJoining || isAfterLeft;

                            var raw      = attendanceMap[dateKey];
                            var savedRec = resolveInitialRec(raw, isHoliday, isDefaultWeeklyOff, isOutsideTenure);

                            attendanceTableData[dateKey] = savedRec;
                            if (raw) originalAttendanceData[dateKey] = JSON.parse(JSON.stringify(savedRec));

                            tbody.appendChild(buildRow(
                                dateKey, dayName, cd, savedRec,
                                isHoliday, isDefaultWeeklyOff,
                                isFuture, isOutsideTenure, rowIdx++
                            ));
                            current.setDate(current.getDate() + 1);
                        }

                        // ── After building rows, hide ECO/Coff td cells in body ──
                        applySubtypeColumnsToBdy();

                        hideTableLoading();
                        updateCounts();
                        updateScrollHeight();
                    },
                    error: function () { hideTableLoading(); }
                });
            },
            error: function () { hideTableLoading(); }
        });
    }

    /**
     * After the tbody is populated, hide or show the td cells that correspond
     * to "Earned Comp Off" and "Comp Off" columns based on currentEmployeeHasSubtype.
     */
    function applySubtypeColumnsToBdy() {
        tbody.querySelectorAll("td[data-status='Earned Comp Off'], td[data-status='Comp Off']").forEach(function (td) {
            td.style.display = currentEmployeeHasSubtype ? "none" : "";
        });
    }

    // ════════════════════════════════════════════════════════════════════════
    //  BULK MARK
    // ════════════════════════════════════════════════════════════════════════
    function bulkMark(status) {
        var employee = employeeSel.value;
        if (!employee || !startDateInput.value) {
            frappe.show_alert({ message: "Please select an employee and month first", indicator: "orange" }); return;
        }
        Object.keys(attendanceTableData).forEach(function (dateKey) {
            if (originalAttendanceData[dateKey]) return;
            var rec = attendanceTableData[dateKey] || {};
            var cur = rec.mode === "full" ? rec.status : null;
            if (cur === "Weekly Off" || cur === "Holiday") return;
            var rowEl = document.querySelector('tr[data-date="' + dateKey + '"]');
            if (rowEl && rowEl.classList.contains("ma-future-row")) return;

            attendanceTableData[dateKey] = status === "Half Day"
                ? { mode: "half", first_half: "", second_half: "" }
                : { mode: "full", status: status };
            markDirty(dateKey);
            refreshRowVisuals(dateKey);
        });
        // Re-hide ECO/Coff columns after bulk refresh
        applySubtypeColumnsToBdy();
        updateCounts();
    }

    document.getElementById("ma_mark_present").onclick  = function () { bulkMark("Present"); };
    document.getElementById("ma_mark_absent").onclick   = function () { bulkMark("Absent");  };
    document.getElementById("ma_mark_halfday").onclick  = function () { bulkMark("Half Day"); };
    document.getElementById("ma_mark_lwp").onclick      = function () { bulkMark("LWP");     };

    // ════════════════════════════════════════════════════════════════════════
    //  SAVE
    // ════════════════════════════════════════════════════════════════════════
    function playSaveSound() {
        try { var audio = document.getElementById("ma-sound-click"); if (audio) { audio.volume = 0.2; audio.play(); } } catch (e) { }
    }
    function recsAreEqual(a, b) {
        if (!a && !b) return true;
        if (!a || !b) return false;
        if (a.mode !== b.mode) return false;
        if (a.mode === "full") return a.status === b.status;
        return a.first_half === b.first_half && a.second_half === b.second_half;
    }
    function doSave() {
        if (isSaving) return;
        var employee = employeeSel.value;
        if (!employee) { frappe.show_alert({ message: "Please select an employee first", indicator: "orange" }); return; }
        if (!startDateInput.value || !endDateInput.value) { frappe.show_alert({ message: "Please select a year and month first", indicator: "orange" }); return; }

        var changedData = [], unchangedCnt = 0;
        Object.entries(attendanceTableData).forEach(function (entry) {
            var dateKey = entry[0], rec = entry[1];
            if (!rec) return;
            var orig = originalAttendanceData[dateKey];
            if (recsAreEqual(rec, orig)) { unchangedCnt++; return; }
            if (rec.mode === "full") {
                if (!rec.status) return;
                changedData.push({ employee: employee, attendance_date: dateKey, mode: "full", status: rec.status });
            } else if (rec.mode === "half") {
                changedData.push({ employee: employee, attendance_date: dateKey, mode: "half", first_half: rec.first_half || "", second_half: rec.second_half || "" });
            }
        });

        if (!changedData.length) {
            frappe.show_alert({ message: unchangedCnt > 0 ? "No changes to save." : "Nothing to save.", indicator: unchangedCnt > 0 ? "blue" : "orange" });
            return;
        }

        isSaving = true; playSaveSound();
        var scrollPos = tableScroll ? tableScroll.scrollTop : 0;

        frappe.call({
            method: "saral_hr.saral_hr.page.mark_attendance.mark_attendance.save_attendance_batch",
            args: { attendance_data: changedData },
            callback: function (r) {
                isSaving = false;
                if (r.message && r.message.success) {
                    var saved  = r.message.saved_count || changedData.length;
                    var errors = r.message.errors;
                    frappe.show_alert({
                        message: errors && errors.length
                            ? saved + " record(s) saved. " + errors.length + " failed."
                            : saved + " attendance record" + (saved === 1 ? "" : "s") + " saved successfully.",
                        indicator: errors && errors.length ? "yellow" : "green"
                    });
                    setTimeout(function () {
                        generateTable(); loadCompOffBalance(employee);
                        setTimeout(function () { if (tableScroll) tableScroll.scrollTop = scrollPos; }, 100);
                    }, 300);
                } else {
                    frappe.show_alert({ message: (r.message && r.message.error) || "Error saving attendance", indicator: "red" });
                }
            },
            error: function () { isSaving = false; frappe.show_alert({ message: "Error saving attendance. Please try again.", indicator: "red" }); }
        });
    }

    var saveBtn = document.getElementById("ma_save_attendance");
    saveBtn.addEventListener("mousedown", function (e) { e.preventDefault(); });
    saveBtn.addEventListener("click", doSave);

    document.getElementById("ma_goto_attendance").addEventListener("click", function (e) {
        e.preventDefault();
        window.open(frappe.urllib.get_full_url("/app/attendance"), "_blank");
    });

    // ════════════════════════════════════════════════════════════════════════
    //  CALENDAR MODAL
    // ════════════════════════════════════════════════════════════════════════
    function normalizeDateKey(dateStr) {
        if (!dateStr) return null;
        if (dateStr instanceof Date) {
            return dateStr.getFullYear() + "-" + String(dateStr.getMonth() + 1).padStart(2, "0") + "-" + String(dateStr.getDate()).padStart(2, "0");
        }
        var parts = dateStr.toString().split("-");
        if (parts.length === 3) return parts[0] + "-" + parts[1].padStart(2, "0") + "-" + parts[2].padStart(2, "0");
        return dateStr;
    }
    function openCalendarModal() {
        var employee = employeeSel.value;
        if (!employee) { frappe.show_alert({ message: "Please select an employee first", indicator: "orange" }); return; }
        document.getElementById("ma_cal_modal").classList.add("show");
        currentCalendarYear = parseInt(yearSel.value) || new Date().getFullYear();
        document.getElementById("ma_cal_year").textContent = currentCalendarYear;
        loadYearAttendance();
    }
    function closeCalendarModal() { document.getElementById("ma_cal_modal").classList.remove("show"); }
    function changeYear(dir) { currentCalendarYear += dir; document.getElementById("ma_cal_year").textContent = currentCalendarYear; loadYearAttendance(); }
    function loadYearAttendance() {
        var employee = employeeSel.value, company = employeeCompanyMap[employee];
        if (!employee) return;
        var cacheKey = employee + "|" + currentCalendarYear;
        if (calendarCache[cacheKey]) {
            yearHolidayData    = calendarCache[cacheKey].holidays;
            yearAttendanceData = calendarCache[cacheKey].attendance;
            renderMonthsGrid(); return;
        }
        var startDate = currentCalendarYear + "-01-01", endDate = currentCalendarYear + "-12-31";
        frappe.call({
            method: "saral_hr.saral_hr.page.mark_attendance.mark_attendance.get_holidays_between_dates",
            args: { company: company, start_date: startDate, end_date: endDate },
            callback: function (holidayRes) {
                var holidays = {};
                (holidayRes.message || []).forEach(function (h) { var n = normalizeDateKey(h); if (n) holidays[n] = true; });
                frappe.call({
                    method: "saral_hr.saral_hr.page.mark_attendance.mark_attendance.get_attendance_between_dates",
                    args: { employee: employee, start_date: startDate, end_date: endDate },
                    callback: function (res) {
                        var attendance = {};
                        Object.entries(res.message || {}).forEach(function (entry) {
                            var n = normalizeDateKey(entry[0]);
                            if (n) { var val = entry[1]; attendance[n] = (typeof val === "object" && val.mode === "half") ? "Half Day" : val; }
                        });
                        calendarCache[cacheKey] = { holidays: holidays, attendance: attendance };
                        yearHolidayData    = holidays;
                        yearAttendanceData = attendance;
                        renderMonthsGrid();
                    }
                });
            }
        });
    }
    function invalidateCalendarCache() {
        var employee = employeeSel.value;
        var year     = parseInt(yearSel.value) || new Date().getFullYear();
        delete calendarCache[employee + "|" + year];
    }
    function renderMonthsGrid() {
        var employee     = employeeSel.value;
        var weeklyOffDays = employeeWeeklyOffMap[employee] || [];
        var joiningDate  = parseDateLocal(joiningDateMap[employee]);
        var leftDate     = parseDateLocal(leftDateMap[employee]);
        var monthsGrid   = document.getElementById("ma_months_grid");
        var monthNames   = ["January","February","March","April","May","June","July","August","September","October","November","December"];
        var dayNames     = ["S","M","T","W","T","F","S"];
        monthsGrid.innerHTML = "";
        monthNames.forEach(function (monthName, monthIndex) {
            var card = document.createElement("div");
            card.className = "ma-month-card";
            card.onclick = function () { selectMonth(monthIndex); };
            var firstDay    = new Date(currentCalendarYear, monthIndex, 1);
            var lastDay     = new Date(currentCalendarYear, monthIndex + 1, 0);
            var startDay    = firstDay.getDay();
            var daysInMonth = lastDay.getDate();
            var html = '<div class="ma-month-name">' + monthName + '</div><div class="ma-mini-cal">';
            dayNames.forEach(function (d) { html += '<div class="ma-mini-hdr">' + d + '</div>'; });
            for (var i = 0; i < startDay; i++) html += '<div class="ma-mini-day empty"></div>';
            var today = new Date();
            for (var day = 1; day <= daysInMonth; day++) {
                var date = new Date(currentCalendarYear, monthIndex, day); date.setHours(0, 0, 0, 0);
                var dateKey        = normalizeDateKey(date);
                var isToday        = date.toDateString() === today.toDateString();
                var isBeforeJoining = joiningDate ? (date < joiningDate) : false;
                var isAfterLeft     = leftDate    ? (date > leftDate)    : false;
                var isOutsideTenure = isBeforeJoining || isAfterLeft;
                var dn              = date.toLocaleDateString("en-US", { weekday: "long" }).toLowerCase();
                var effectiveIsWeeklyOff = !isOutsideTenure && weeklyOffDays.includes(dn);
                var effectiveIsHoliday   = !isOutsideTenure && yearHolidayData[dateKey] === true;
                var status = yearAttendanceData[dateKey];
                var cls    = "ma-mini-day";
                if (isToday)              cls += " today";
                else if (isOutsideTenure) cls += " outside-tenure";
                else if (effectiveIsHoliday  || status === "Holiday")  cls += " holiday";
                else if (status === "Present" || status === "Regular") cls += " present";
                else if (status === "On Tour")         cls += " on-tour";
                else if (status === "Earned Comp Off") cls += " eco";
                else if (status === "Absent")          cls += " absent";
                else if (status === "Half Day")        cls += " halfday";
                else if (status === "LWP")             cls += " lwp";
                else if (status === "Earned Leave")    cls += " el";
                else if (status === "Casual Leave")    cls += " cl";
                else if (status === "Comp Off")        cls += " coff";
                else if (status === "Weekly Off" || effectiveIsWeeklyOff) cls += " weekend";
                html += '<div class="' + cls + '">' + day + '</div>';
            }
            html += '</div>';
            card.innerHTML = html; monthsGrid.appendChild(card);
        });
    }
    function selectMonth(monthIndex) {
        yearSel.value = currentCalendarYear; monthSel.value = monthIndex;
        monthSel.dispatchEvent(new Event("change")); closeCalendarModal();
    }

    document.getElementById("ma_get_info").addEventListener("click",    openCalendarModal);
    document.getElementById("ma_cal_close").addEventListener("click",   closeCalendarModal);
    document.getElementById("ma_year_prev").addEventListener("click",   function () { changeYear(-1); });
    document.getElementById("ma_year_next").addEventListener("click",   function () { changeYear(+1); });
    document.getElementById("ma_cal_modal").addEventListener("click",   function (e) { if (e.target === this) closeCalendarModal(); });

    document.addEventListener("keydown", function (e) {
        if (e.key === "Escape") { closeCalendarModal(); closeHdPanel(); }
        if ((e.ctrlKey || e.metaKey) && e.key === "s") { e.preventDefault(); doSave(); }
    });

    var _origGenerateTable = generateTable;
    generateTable = function () { invalidateCalendarCache(); _origGenerateTable(); };
}

// ════════════════════════════════════════════════════════════════════════════
//  AUDIO
// ════════════════════════════════════════════════════════════════════════════
function inject_ma_audio() {
    if (document.getElementById("ma-sound-click")) return;
    ["click", "submit", "cancel"].forEach(function (name) {
        var audio = document.createElement("audio");
        audio.id  = "ma-sound-" + name;
        audio.src = "/assets/frappe/sounds/" + name + ".mp3";
        audio.preload = "auto"; audio.style.display = "none"; document.body.appendChild(audio);
    });
}

// ════════════════════════════════════════════════════════════════════════════
//  STYLES
// ════════════════════════════════════════════════════════════════════════════
function inject_ma_styles() {
    if (document.getElementById("ma-styles")) return;
    var style = document.createElement("style");
    style.id = "ma-styles";
    style.innerHTML = `

        /* ══════════════════════════════════════════════════════
           CSS VARIABLES
           ══════════════════════════════════════════════════════ */
        :root {
            --ma-sticky-bar-h: 120px;
            --ma-thead-row1-h: 52px;
        }

        .ma-wrap {
            padding: 0 4px;
            display: flex;
            flex-direction: column;
            height: 100%;
        }
        .ma-sticky {
            flex-shrink: 0;
            background: var(--card-bg, #fff);
            padding-bottom: 12px;
            border-bottom: 1px solid var(--border-color, #e5e7eb);
            margin-bottom: 0;
            z-index: 100;
        }

        .ma-header-actions { display:flex; align-items:center; gap:10px; margin-left:20px; }
        .ma-link { font-size:12px; color:var(--text-on-light-blue); cursor:pointer; text-decoration:underline; text-underline-offset:2px; background:none; border:none; padding:0; font-weight:500; transition:color 0.2s; white-space:nowrap; }
        .ma-link:hover { color:var(--blue-600); }
        .ma-link-sep { color:var(--text-muted); font-size:12px; }

        .ma-btn { background:var(--control-bg,#f4f5f6); color:var(--text-color); border:1px solid var(--border-color,#d1d8dd); border-radius:5px; padding:6px 14px; font-weight:500; cursor:pointer; transition:background 0.15s; font-size:13px; white-space:nowrap; user-select:none; }
        .ma-btn-primary { background:var(--primary) !important; color:#fff !important; border-color:var(--primary) !important; }
        .ma-btn-primary:hover { opacity:0.88; }
        .ma-btn-primary:focus, .ma-btn-primary:active { outline:none; background:var(--primary) !important; color:#fff !important; border-color:var(--primary) !important; opacity:1; box-shadow:none; }
        .ma-btn:hover:not(.ma-btn-primary) { background:var(--control-bg-on-gray,#eee); }
        .ma-btn:active:not(.ma-btn-primary) { transform:scale(0.98); }

        .ma-top-wrap { display:flex; gap:14px; align-items:stretch; }
        .ma-left-block { flex:1; min-width:0; display:flex; flex-direction:column; gap:10px; }
        .ma-row1 { display:flex; gap:14px; align-items:flex-end; flex:1; }
        .ma-r1-employee { flex:2; min-width:0; position:relative; }
        .ma-r1-company { flex:2; min-width:0; position:relative; }
        .ma-r1-weeklyoff { flex:1; min-width:120px; }
        .ma-row2 { display:flex; gap:14px; align-items:flex-end; }
        .ma-r2-year { flex:0 0 110px; }
        .ma-r2-month { flex:0 0 150px; }
        .ma-r2-buttons { flex:0 0 auto; }
        .ma-r1-leave { flex:0 0 auto; display:flex; align-items:stretch; }
        .ma-wrap .ma-label, label.ma-label { display:block !important; font-size:11px !important; font-weight:500 !important; color:var(--text-muted) !important; margin-bottom:4px !important; text-transform:uppercase !important; letter-spacing:0.04em !important; line-height:1.4 !important; }
        .ma-input { width:100%; padding:0 10px; height:32px; line-height:32px; border:1px solid var(--border-color,#d1d8dd); border-radius:4px; font-size:13px; background:var(--card-bg,#fff); color:var(--text-color); box-sizing:border-box; }
        .ma-input:focus { outline:none; border-color:var(--primary); box-shadow:0 0 0 2px rgba(var(--primary-rgb,45,108,223),0.12); }
        .ma-input[readonly] { background:var(--control-bg,#f8f9fa); color:var(--text-muted); }

        .ma-search-wrapper { position:relative; }
        .ma-search-input { padding-right:30px; }
        .ma-clear-btn { position:absolute; right:8px; top:50%; transform:translateY(-50%); width:18px; height:18px; border-radius:50%; background:var(--text-muted); border:none; color:#fff; font-size:11px; cursor:pointer; display:none; align-items:center; justify-content:center; transition:all 0.2s; padding:0; line-height:1; }
        .ma-clear-btn::before { content:'\\2715'; }
        .ma-clear-btn.show { display:flex !important; }
        .ma-clear-btn:hover { background:var(--text-color); }
        .ma-search-dropdown { display:none; position:absolute; top:100%; left:0; right:0; background:var(--card-bg,#fff); border:1px solid var(--border-color,#d1d8dd); border-top:none; border-radius:0 0 4px 4px; max-height:280px; overflow-y:auto; z-index:1000; box-shadow:0 4px 12px rgba(0,0,0,0.08); }
        .ma-search-dropdown.show { display:block; }
        .ma-result-item { padding:8px 14px; cursor:pointer; border-bottom:1px solid var(--border-color,#f0f0f0); transition:background 0.1s; }
        .ma-result-item:last-child { border-bottom:none; }
        .ma-result-item:hover, .ma-result-item.selected { background:var(--control-bg,#f4f5f6); }
        .ma-result-name { font-size:13px; font-weight:500; color:var(--text-color); }
        .ma-result-id { font-size:11px; color:var(--text-muted); margin-top:1px; }
        .ma-highlight { font-weight:700; color:var(--text-color); }
        .ma-no-results { padding:12px 14px; font-size:13px; color:var(--text-muted); text-align:center; }
        .ma-bulk-btns { display:flex; align-items:center; gap:6px; flex-wrap:wrap; }

        /* ══════════════════════════════════════════════════════
           TABLE SCROLL CONTAINER
           ══════════════════════════════════════════════════════ */
        .ma-table-scroll {
            flex: 1 1 auto;
            overflow-x: auto;
            overflow-y: auto;
            min-height: 200px;
            border-top: 1px solid var(--border-color, #e5e7eb);
            position: relative;
        }

        .ma-table { width:100%; border-collapse:collapse; font-size:12px; }
        .ma-table td { border:1px solid var(--border-color,#d1d8dd); padding:5px 7px; background:transparent; }
        .ma-table tbody tr:nth-child(even) td { background:rgba(0,0,0,0.013); }

        .ma-table-loading { display:flex; flex-direction:column; align-items:center; justify-content:center; padding:48px 0; gap:14px; }
        .ma-spinner { width:32px; height:32px; border:3px solid var(--border-color,#e5e7eb); border-top-color:var(--primary,#2d2d2d); border-radius:50%; animation:ma-spin 0.7s linear infinite; }
        @keyframes ma-spin { to { transform:rotate(360deg); } }
        .ma-loading-text { font-size:13px; color:var(--text-muted); }

        .ma-table thead tr.ma-thead-row th {
            position: sticky; top: 0; z-index: 50;
            background: var(--control-bg, #f7f7f7);
            border: 1px solid var(--border-color, #d1d8dd);
            box-shadow: 0 1px 0 var(--border-color, #d1d8dd);
        }
        .ma-table thead tr.ma-thead-row2 th {
            position: sticky; top: var(--ma-thead-row1-h, 52px); z-index: 49;
            background: var(--control-bg, #f7f7f7);
            border: 1px solid var(--border-color, #d1d8dd);
            box-shadow: 0 1px 0 var(--border-color, #d1d8dd);
        }

        .ma-table thead th { padding:0; text-align:center; vertical-align:middle; }
        .ma-th-inner { display:flex; flex-direction:column; align-items:center; justify-content:space-between; height:var(--ma-thead-row1-h, 52px); padding:7px 6px 5px; box-sizing:border-box; }
        .ma-th-left { align-items:flex-start; padding-left:10px; }
        .ma-th-sub  { height:28px; justify-content:center; padding:4px 6px; }
        .ma-th-hd-group { min-width:240px; border-bottom:none !important; }
        .ma-th-hd-top-wrap { display:flex; flex-direction:column; align-items:center; justify-content:space-between; height:var(--ma-thead-row1-h, 52px); padding:7px 6px 5px; box-sizing:border-box; }
        .ma-th-label { font-size:11px; font-weight:600; color:var(--text-muted); line-height:1.3; text-align:center; white-space:normal; }
        .ma-col-count { font-size:11px; font-weight:700; color:var(--text-color); line-height:1; }

        .ma-th-date     { width:148px; min-width:148px; }
        .ma-th-day      { width:100px; min-width:100px; }
        .ma-th-override { width:80px;  min-width:80px; }
        .ma-th-status   { width:66px;  min-width:66px; }
        .ma-th-hd1, .ma-th-hd2 { width:120px; min-width:120px; border-top:none !important; }

        /* ══════════════════════════════════════════════════════
           ROW STATES
           ══════════════════════════════════════════════════════ */
        .ma-date-wo { color:#b8860b !important; font-weight:600 !important; }
        .ma-dot-wo-hint { border-color:#d4a017 !important; background:rgba(212,160,23,0.12) !important; }
        .ma-date-holiday { color:#c05800 !important; font-weight:600 !important; }
        .ma-dot-holiday-hint { border-color:#e09a2a !important; background:rgba(224,154,42,0.12) !important; }
        .ma-row-halfday td { background:rgba(59,130,246,0.035) !important; }
        .ma-table tbody tr.ma-future-row td { opacity:0.4; }
        .ma-table tbody tr.ma-before-joining-row td { opacity:0.35; background:rgba(156,163,175,0.08) !important; }
        .ma-row-dirty td { background:rgba(245,158,11,0.07) !important; }
        .ma-row-dirty:nth-child(even) td { background:rgba(245,158,11,0.1) !important; }
        .ma-row-override td { background:rgba(139,92,246,0.04) !important; }
        .ma-status-cells-disabled .ma-status-cell { opacity:0.2 !important; pointer-events:none !important; cursor:default !important; }

        .ma-status-cell { text-align:center; padding:4px 3px !important; vertical-align:middle; cursor:pointer; }
        .ma-status-cell:not(.ma-hd-cell):hover { background:rgba(0,0,0,0.04) !important; }
        .ma-col-dot { width:14px; height:14px; border-radius:50%; border:2px solid #c0c6cc; margin:0 auto; transition:all 0.12s; background:transparent; box-sizing:border-box; }
        .ma-col-dot.active        { border-color:transparent; }
        .ma-col-dot.present-dot   { background:#28a745; border-color:#28a745; }
        .ma-col-dot.absent-dot    { background:#e74c3c; border-color:#e74c3c; }
        .ma-col-dot.wo-dot        { background:#b8860b; border-color:#b8860b; }
        .ma-col-dot.holiday-dot   { background:#e09a2a; border-color:#e09a2a; }
        .ma-col-dot.ma-dot-dirty.active { box-shadow:0 0 0 2px var(--card-bg,#fff), 0 0 0 4px #f59e0b; }
        .ma-cell-focused { outline:2px solid var(--primary,#2d6adf) !important; outline-offset:-2px; background:rgba(45,106,223,0.06) !important; }

        .ma-date-cell { font-size:12px; font-weight:500; padding:5px 10px !important; white-space:nowrap; min-width:140px; color:var(--text-color); }
        .ma-day-cell  { font-size:12px; color:var(--text-muted); padding:5px 8px !important; white-space:nowrap; min-width:100px; }

        /* ══════════════════════════════════════════════════════
           HALF-DAY PILL
           ══════════════════════════════════════════════════════ */
        .ma-hd-cell { width:120px; min-width:110px; cursor:pointer; padding:4px 6px !important; }
        .ma-hd-cell:hover { background:rgba(0,0,0,0.04) !important; }

        .ma-hd-pill {
            display: inline-flex;
            align-items: center;
            gap: 5px;
            padding: 3px 9px 3px 7px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: 500;
            white-space: nowrap;
            border: 1px solid transparent;
            transition: box-shadow 0.12s;
            cursor: pointer;
            max-width: 100%;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .ma-hd-pill-dot {
            width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0;
        }
        .ma-hd-pill-empty {
            background: var(--control-bg, #f3f4f6);
            color: var(--text-muted);
            border: 1px dashed var(--border-color, #d1d5db);
            font-size: 11px;
            font-style: italic;
        }
        .ma-hd-pill-present   { background:#eafaf1; color:#1a7a3c; border-color:#a3d9b1; }
        .ma-hd-pill-ontour    { background:#e8f8ef; color:#1a6e40; border-color:#89d4aa; }
        .ma-hd-pill-eco       { background:#e0f7f1; color:#0d6e56; border-color:#5dcaa5; }
        .ma-hd-pill-absent    { background:#fdf3f2; color:#c0392b; border-color:#f5b7b1; }
        .ma-hd-pill-el        { background:#e8f2fb; color:#1558a0; border-color:#90bce8; }
        .ma-hd-pill-cl        { background:#edf4fb; color:#1960a8; border-color:#9fc5e8; }
        .ma-hd-pill-coff      { background:#f3f4f6; color:#4b5563; border-color:#d1d5db; }
        .ma-hd-pill-lwp       { background:#fffbeb; color:#92660a; border-color:#fcd34d; }
        .ma-hd-cell:hover .ma-hd-pill { box-shadow:0 0 0 2px var(--border-color,#d1d8dd); }

        /* ══════════════════════════════════════════════════════
           HALF-DAY PANEL
           ══════════════════════════════════════════════════════ */
        .ma-hd-panel {
            position: fixed;
            inset: 0;
            z-index: 2500;
            background: rgba(0,0,0,0.42);
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .ma-hd-panel-inner {
            background: var(--card-bg, #fff);
            border-radius: 10px;
            width: 95%;
            max-width: 560px;
            box-shadow: 0 12px 40px rgba(0,0,0,0.18);
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }
        .ma-hd-panel-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 14px 18px 12px;
            border-bottom: 1px solid var(--border-color, #e5e7eb);
            background: var(--control-bg, #f8f9fa);
        }
        .ma-hd-panel-header-info { display:flex; flex-direction:column; gap:2px; }
        .ma-hd-panel-title { font-size:14px; font-weight:600; color:var(--text-color); }
        .ma-hd-panel-date  { font-size:12px; color:var(--text-muted); }
        .ma-hd-panel-close {
            width: 26px; height: 26px; border-radius: 50%;
            background: var(--control-bg-on-gray, #e5e7eb);
            border: none; color: var(--text-muted); font-size:13px;
            cursor: pointer; display:flex; align-items:center; justify-content:center;
            transition: background 0.15s;
        }
        .ma-hd-panel-close:hover { background:var(--border-color); color:var(--text-color); }

        .ma-hd-panel-body {
            display: grid;
            grid-template-columns: 1fr auto 1fr;
            gap: 0;
            padding: 16px 20px;
        }
        .ma-hd-divider {
            width: 1px;
            background: var(--border-color, #e5e7eb);
            margin: 0 16px;
            border-radius: 1px;
        }
        .ma-hd-col {}
        .ma-hd-col-label {
            font-size: 11px; font-weight: 600; text-transform: uppercase;
            letter-spacing: 0.05em; color: var(--text-muted);
            margin-bottom: 10px; padding-bottom: 8px;
            border-bottom: 1px solid var(--border-color, #e5e7eb);
        }
        .ma-hd-options { display:flex; flex-direction:column; gap:3px; }

        .ma-hd-opt {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 8px 10px;
            border-radius: 7px;
            cursor: pointer;
            transition: background 0.1s;
            border: 1px solid transparent;
        }
        .ma-hd-opt:hover { background: var(--control-bg, #f4f5f6); }
        .ma-hd-opt-selected {
            background: rgba(45,108,223,0.06);
            border-color: rgba(45,108,223,0.2);
        }
        .ma-hd-opt-selected .ma-hd-opt-label {
            color: var(--primary, #2d6adf);
            font-weight: 600;
        }
        .ma-hd-opt-dot {
            width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0;
        }
        .ma-hd-opt-label {
            font-size: 13px; color: var(--text-color); flex: 1;
        }
        .ma-hd-opt-radio {
            width: 16px; height: 16px; border-radius: 50%;
            border: 1.5px solid var(--border-color, #d1d8dd);
            flex-shrink: 0; display:flex; align-items:center; justify-content:center;
            background: var(--card-bg, #fff);
            transition: border-color 0.12s;
        }
        .ma-hd-opt-radio-on {
            border-color: var(--primary, #2d6adf);
            background: var(--primary, #2d6adf);
            box-shadow: inset 0 0 0 3px var(--card-bg, #fff);
        }
        .ma-hd-opt:hover .ma-hd-opt-radio { border-color: var(--primary, #2d6adf); }

        .ma-hd-panel-footer {
            display: flex; align-items:center; justify-content:flex-end; gap:8px;
            padding: 12px 20px;
            border-top: 1px solid var(--border-color, #e5e7eb);
            background: var(--control-bg, #f8f9fa);
        }

        /* ── Override toggle ── */
        .ma-override-cell { text-align:center; vertical-align:middle; width:80px; min-width:80px; }
        .ma-no-override { color:var(--border-color); font-size:15px; }
        .ma-toggle { position:relative; display:inline-block; width:38px; height:20px; margin:0; cursor:pointer; }
        .ma-toggle input { opacity:0; width:0; height:0; }
        .ma-toggle-slider { position:absolute; top:0; left:0; right:0; bottom:0; background:var(--control-bg-on-gray,#d1d5db); border-radius:20px; border:1px solid var(--border-color); transition:0.2s; }
        .ma-toggle-slider:before { position:absolute; content:""; height:14px; width:14px; left:2px; bottom:2px; background:#fff; border-radius:50%; transition:0.2s; box-shadow:0 1px 3px rgba(0,0,0,0.2); }
        .ma-toggle input:checked + .ma-toggle-slider { background:#28a745; border-color:#28a745; }
        .ma-toggle input:checked + .ma-toggle-slider:before { transform:translateX(18px); }
        .ma-toggle input:not(:checked) + .ma-toggle-slider { background:#f0ad4e; border-color:#e09a2a; }
        .ma-toggle-holiday input:not(:checked) + .ma-toggle-slider { background:#e74c3c; border-color:#c0392b; }

        /* ── Calendar modal ── */
        .ma-cal-modal { display:none; position:fixed; z-index:2000; left:0; top:0; width:100%; height:100%; background:rgba(0,0,0,0.5); backdrop-filter:blur(3px); }
        .ma-cal-modal.show { display:flex; align-items:center; justify-content:center; }
        .ma-cal-content { background:var(--card-bg,#fff); border-radius:10px; width:95%; max-width:900px; max-height:85vh; overflow:hidden; box-shadow:0 16px 48px rgba(0,0,0,0.2); position:relative; }
        .ma-cal-close { position:absolute; top:10px; right:10px; z-index:10; background:var(--control-bg,#e5e7eb); border:none; color:var(--text-muted); width:26px; height:26px; border-radius:50%; font-size:13px; cursor:pointer; display:flex; align-items:center; justify-content:center; transition:background 0.15s; }
        .ma-cal-close:hover { background:var(--border-color); color:var(--text-color); }
        .ma-cal-body { padding:20px 16px; overflow-y:auto; max-height:85vh; }
        .ma-year-selector { display:flex; align-items:center; justify-content:center; gap:16px; margin-bottom:14px; }
        .ma-year-center { display:flex; flex-direction:column; align-items:center; min-width:90px; }
        .ma-year-num { font-size:22px; font-weight:700; color:var(--text-color); line-height:1.1; }
        .ma-year-sub { font-size:10px; color:var(--text-muted); font-weight:400; letter-spacing:0.03em; margin-top:1px; }
        .ma-year-nav { background:var(--control-bg,#f3f4f6); border:1px solid var(--border-color); width:28px; height:28px; border-radius:50%; font-size:18px; cursor:pointer; display:flex; align-items:center; justify-content:center; color:var(--text-muted); transition:all 0.15s; flex-shrink:0; }
        .ma-year-nav:hover { background:var(--primary); color:#fff; border-color:var(--primary); }
        .ma-cal-legend { display:flex; gap:12px; justify-content:center; margin-bottom:16px; flex-wrap:wrap; font-size:12px; }
        .ma-legend-item { display:flex; align-items:center; gap:5px; color:var(--text-muted); }
        .ma-legend-dot { width:12px; height:12px; border-radius:3px; display:inline-block; box-sizing:border-box; }
        .ma-legend-dot.present  { background:#28a745; border-radius:50%; }
        .ma-legend-dot.on-tour  { background:#28a745; border-radius:50%; opacity:0.65; }
        .ma-legend-dot.eco      { background:#20c997; border-radius:50%; }
        .ma-legend-dot.absent   { background:#e74c3c; border-radius:50%; }
        .ma-legend-dot.halfday  { background:#f0ad4e; border-radius:50%; }
        .ma-legend-dot.lwp      { background:#e74c3c; border-radius:50%; opacity:0.6; }
        .ma-legend-dot.el       { background:#e74c3c; border-radius:50%; opacity:0.75; }
        .ma-legend-dot.cl       { background:#e74c3c; border-radius:50%; opacity:0.85; }
        .ma-legend-dot.coff     { background:#868e96; border-radius:50%; }
        .ma-legend-dot.holiday  { background:#fff8f0; border:2px solid #e09a2a; }
        .ma-legend-dot.weekend  { background:var(--control-bg); border:1px solid var(--border-color); }
        .ma-months-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; }
        .ma-month-card { background:var(--card-bg,#fff); border:1px solid var(--border-color,#e5e7eb); border-radius:6px; padding:12px; cursor:pointer; transition:all 0.15s; }
        .ma-month-card:hover { border-color:var(--primary); box-shadow:0 2px 8px rgba(0,0,0,0.08); transform:translateY(-1px); }
        .ma-month-name { font-size:14px; font-weight:600; color:var(--text-color); margin-bottom:8px; }
        .ma-mini-cal { display:grid; grid-template-columns:repeat(7,1fr); gap:1px; }
        .ma-mini-hdr { font-size:9px; font-weight:600; color:var(--text-muted); text-align:center; padding:2px; }
        .ma-mini-day { font-size:10px; text-align:center; padding:3px 1px; color:var(--text-color); border-radius:2px; }
        .ma-mini-day.empty          { visibility:hidden; }
        .ma-mini-day.outside-tenure { opacity:0.25; background:var(--control-bg) !important; color:var(--text-muted) !important; }
        .ma-mini-day.today   { background:var(--primary,#2d2d2d) !important; color:#fff !important; font-weight:700; border-radius:3px; }
        .ma-mini-day.present { background:#28a745 !important; color:#fff !important; font-weight:700; border-radius:50%; }
        .ma-mini-day.on-tour { background:#28a745 !important; color:#fff !important; font-weight:700; border-radius:50%; opacity:0.7; }
        .ma-mini-day.eco     { background:#20c997 !important; color:#fff !important; font-weight:700; border-radius:50%; }
        .ma-mini-day.absent  { background:#e74c3c !important; color:#fff !important; font-weight:700; border-radius:50%; }
        .ma-mini-day.halfday { background:#f0ad4e !important; color:#fff !important; font-weight:700; border-radius:50%; }
        .ma-mini-day.lwp     { background:#e74c3c !important; color:#fff !important; font-weight:700; border-radius:50%; opacity:0.6; }
        .ma-mini-day.el      { background:#e74c3c !important; color:#fff !important; font-weight:700; border-radius:50%; opacity:0.75; }
        .ma-mini-day.cl      { background:#e74c3c !important; color:#fff !important; font-weight:700; border-radius:50%; opacity:0.85; }
        .ma-mini-day.coff    { background:#868e96 !important; color:#fff !important; font-weight:700; border-radius:50%; }
        .ma-mini-day.holiday { background:#fff8f0 !important; color:#8a3a00 !important; font-weight:700; border:1px solid #e09a2a !important; border-radius:2px; box-sizing:border-box; }
        .ma-mini-day.weekend { background:var(--control-bg) !important; color:var(--text-muted) !important; border-radius:2px; }
        .page-head-content { padding:8px 17px 0px 0px !important; }

        /* ── Leave balance table ── */
        .ma-leave-table { border-collapse:collapse; height:100%; }
        .ma-leave-th { background:var(--control-bg,#f7f7f7); border:1px solid var(--border-color,#d1d8dd); padding:4px 12px; font-size:11px; font-weight:600; text-align:center; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.03em; white-space:nowrap; }
        .ma-leave-th.ma-leave-type-hdr { background:transparent; border:1px solid var(--border-color); border-right:none; font-size:11px; font-weight:500; color:var(--text-muted); text-align:left; padding:4px 10px; white-space:nowrap; }
        .ma-leave-row-label { font-size:11px; font-weight:500; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.03em; padding:4px 10px; border:1px solid var(--border-color); border-right:none; background:var(--control-bg,#f7f7f7); white-space:nowrap; }
        .ma-leave-val { text-align:center; font-size:13px; font-weight:700; color:var(--text-color); border:1px solid var(--border-color); padding:4px 12px; background:var(--card-bg,#fff); min-width:48px; }
        .ma-leave-bal { color:var(--text-muted); font-weight:500; font-size:12px; }
        .ma-leave-eco-hdr { background:var(--control-bg) !important; }
    `;
    document.head.appendChild(style);
}