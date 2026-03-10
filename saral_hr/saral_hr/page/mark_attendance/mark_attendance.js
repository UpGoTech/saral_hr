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

// ── Dynamic year options ───────────────────────────────────────────────────
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

        <div class="ma-sticky">
            <div class="ma-top-wrap">
            <div class="ma-left-block">

            <!-- Row 1 -->
            <div class="ma-row1">
                <div class="ma-r1-employee">
                    <label class="ma-label">Employee</label>
                    <div class="ma-search-wrapper">
                        <input type="text" id="ma_employee_search" class="ma-input ma-search-input"
                            placeholder="Search Employee" autocomplete="off" />
                        <button type="button" id="ma_clear_search" class="ma-clear-btn"></button>
                        <div id="ma_search_results" class="ma-search-dropdown"></div>
                    </div>
                    <select id="ma_employee" style="display:none !important; height:0; width:0; position:absolute; visibility:hidden;">
                        <option value="">Select Employee</option>
                    </select>
                </div>
                <div class="ma-r1-company">
                    <label class="ma-label">Company</label>
                    <input type="text" id="ma_company" class="ma-input" readonly>
                </div>
                <div class="ma-r1-weeklyoff">
                    <label class="ma-label">Weekly Off</label>
                    <input type="text" id="ma_weekly_off" class="ma-input" readonly>
                </div>
            </div>

            <!-- Row 2 -->
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

            </div><!-- end ma-left-block -->

            <!-- Leave summary: right side -->
            <div class="ma-r1-leave">
                <table class="ma-leave-table">
                    <thead>
                        <tr>
                            <th class="ma-leave-th ma-leave-type-hdr">Leave Type</th>
                            <th class="ma-leave-th">Earned</th>
                            <th class="ma-leave-th">Casual</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td class="ma-leave-row-label">Taken</td>
                            <td class="ma-leave-val" id="ma_el_taken">0</td>
                            <td class="ma-leave-val" id="ma_cl_taken">0</td>
                        </tr>
                        <tr>
                            <td class="ma-leave-row-label">Balance</td>
                            <td class="ma-leave-val ma-leave-bal">0</td>
                            <td class="ma-leave-val ma-leave-bal">0</td>
                        </tr>
                    </tbody>
                </table>
            </div>

            </div><!-- end ma-top-wrap -->

            <input type="hidden" id="ma_start_date">
            <input type="hidden" id="ma_end_date">
        </div><!-- end ma-sticky -->

        <div class="ma-table-scroll">
            <table class="ma-table" id="ma_table" style="display:none;">
                <thead>
                    <tr>
                        <th rowspan="2">Day</th>
                        <th rowspan="2">Date</th>
                        <th rowspan="2" class="text-center ma-col-override">
                            Override<br>
                            <small class="ma-th-small">Rest Day</small>
                        </th>
                        <th rowspan="2" class="text-center">
                            Half Day<br>
                            <span id="ma_hd_col_count">0</span><br>
                            <small id="ma_hd_col_eq" class="ma-th-small"></small>
                        </th>
                        <!-- Present group -->
                        <th class="ma-present-group-th text-center" colspan="2">
                            <div class="ma-present-group-label">Present <span id="ma_p_col_count" class="ma-group-total">(0)</span></div>

                            <div class="ma-present-sub-row">
                                <div class="ma-present-sub-cell">Regular<br><span id="ma_pr_col_count">0</span></div>
                                <div class="ma-present-sub-cell">On Tour<br><span id="ma_pt_col_count">0</span></div>
                            </div>
                        </th>
                        <!-- Absent group -->
                        <th rowspan="2" class="text-center">
                            Absent<br>
                            <span id="ma_a_col_count">0</span>
                        </th>
                        <th class="ma-absent-group-th" colspan="4">
                            <div class="ma-absent-group-label">Absent Type</div>
                            <div class="ma-absent-sub-row">
                                <div class="ma-absent-sub-cell">LWP<br><span id="ma_lwp_count_col">0</span></div>
                                <div class="ma-absent-sub-cell">Earned Leave<br><span id="ma_el_count_col">0</span></div>
                                <div class="ma-absent-sub-cell">Casual Leave<br><span id="ma_cl_count_col">0</span></div>
                                <div class="ma-absent-sub-cell">Comp Off<br><span id="ma_coff_count_col">0</span></div>
                            </div>
                        </th>
                        <th rowspan="2" class="text-center ma-col-wo">
                            Weekly Off<br>
                            <span id="ma_wo_col_count">0</span>
                        </th>
                        <th rowspan="2" class="text-center ma-col-holiday">
                            Holiday<br>
                            <span id="ma_hol_col_count">0</span>
                        </th>
                    </tr>
                    <!-- second header row is just a spacer to complete the rowspans -->
                    <tr></tr>
                </thead>
                <tbody id="ma_table_body"></tbody>
            </table>

            <div id="ma_table_loading" class="ma-table-loading" style="display:none;">
                <div class="ma-spinner"></div>
                <div class="ma-loading-text">Loading attendance…</div>
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
                    <div class="ma-legend-item"><span class="ma-legend-dot absent"></span>Absent</div>
                    <div class="ma-legend-item"><span class="ma-legend-dot halfday"></span>Half Day</div>
                    <div class="ma-legend-item"><span class="ma-legend-dot lwp"></span>LWP</div>
                    <div class="ma-legend-item"><span class="ma-legend-dot el"></span>Earned Leave</div>
                    <div class="ma-legend-item"><span class="ma-legend-dot cl"></span>Casual Leave</div>
                    <div class="ma-legend-item"><span class="ma-legend-dot coff"></span>Comp Off</div>
                    <div class="ma-legend-item"><span class="ma-legend-dot holiday"></span>Holiday</div>
                    <div class="ma-legend-item"><span class="ma-legend-dot weekend"></span>Weekly Off</div>
                </div>
                <div class="ma-months-grid" id="ma_months_grid"></div>
            </div>
        </div>
    </div>
    `;
}

function init_mark_attendance($main) {

    var employees              = [];
    var filteredEmployees      = [];
    var selectedIndex          = -1;
    var searchDebounceTimer    = null;
    var attendanceTableData    = {};
    var originalAttendanceData = {};
    var holidayDates           = {};
    var isSaving               = false;
    var currentCalendarYear    = new Date().getFullYear();
    var yearAttendanceData     = {};
    var yearHolidayData        = {};
    var employeeCompanyMap     = {};
    var employeeWeeklyOffMap   = {};
    var calendarCache          = {};

    // ── Status sets ────────────────────────────────────────────────────────
    var ABSENT_SUBTYPES   = ["LWP", "Earned Leave", "Casual Leave", "Comp Off"];
    var PRESENT_SUBTYPES  = ["Regular", "On Tour"];

    var searchInput    = document.getElementById("ma_employee_search");
    var searchResults  = document.getElementById("ma_search_results");
    var employeeSel    = document.getElementById("ma_employee");
    var clearBtn       = document.getElementById("ma_clear_search");
    var yearSel        = document.getElementById("ma_year");
    var monthSel       = document.getElementById("ma_month");
    var startDateInput = document.getElementById("ma_start_date");
    var endDateInput   = document.getElementById("ma_end_date");
    var tableLoading   = document.getElementById("ma_table_loading");
    var tableEl        = document.getElementById("ma_table");

    // ── Load employees ─────────────────────────────────────────────────────
    frappe.call({
        method: "saral_hr.saral_hr.page.mark_attendance.mark_attendance.get_active_employees",
        callback: function (r) {
            if (!r.message) return;
            r.message.forEach(function (row) {
                var opt   = document.createElement("option");
                opt.value = row.name;
                opt.text  = row.full_name + (row.aadhaar_number ? " (" + row.aadhaar_number + ")" : "");
                employeeSel.appendChild(opt);
                employeeCompanyMap[row.name]   = row.company;
                employeeWeeklyOffMap[row.name] = row.weekly_off
                    ? [row.weekly_off.trim().toLowerCase()]
                    : [];
            });
            employees = Array.from(employeeSel.options)
                .filter(function (o) { return o.value; })
                .map(function (o) {
                    var row = r.message.find(function (e) { return e.name === o.value; }) || {};
                    return { value: o.value, name: o.text.trim(), emp_id: row.employee || o.value };
                });
        }
    });

    // ── Search ─────────────────────────────────────────────────────────────
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
            args: { query: term },
            freeze: false,
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
        filteredEmployees = localResults;
        showResults(localResults, term);
        clearTimeout(searchDebounceTimer);
        if (term.length >= 2) {
            searchDebounceTimer = setTimeout(function () {
                apiSearch(term, function (apiResults) {
                    var merged = mergeResults(localResults, apiResults);
                    filteredEmployees = merged;
                    showResults(merged, term);
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
        var escaped     = escapeHtml(text);
        var escapedTerm = term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        return escaped.replace(new RegExp("(" + escapedTerm + ")", "gi"), '<span class="ma-highlight">$1</span>');
    }

    function showResults(results, term) {
        if (!results.length) {
            searchResults.innerHTML = '<div class="ma-no-results">No employee found</div>';
            searchResults.classList.add("show");
            selectedIndex = -1;
            return;
        }
        searchResults.innerHTML = results.map(function (emp, i) {
            return '<div class="ma-result-item" data-index="' + i + '" data-value="' + emp.value + '">' +
                '<div class="ma-result-name">' + highlightMatch(emp.name, term) + '</div>' +
                '<div class="ma-result-id">'   + highlightMatch(emp.emp_id, term) + '</div>' +
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
                selectedIndex = parseInt(item.dataset.index);
                highlightResult();
            });
        });
    }

    function highlightResult() {
        var items = searchResults.querySelectorAll(".ma-result-item");
        items.forEach(function (item, i) { item.classList.toggle("selected", i === selectedIndex); });
        if (items[selectedIndex]) items[selectedIndex].scrollIntoView({ block: "nearest" });
    }

    function selectEmployee(emp) {
        searchInput.value = emp.name;
        employeeSel.value = emp.value;
        searchResults.classList.remove("show");
        selectedIndex = -1;
        clearBtn.classList.add("show");
        clearTimeout(searchDebounceTimer);

        if (emp.company    !== undefined) employeeCompanyMap[emp.value]   = emp.company;
        if (emp.weekly_off !== undefined) employeeWeeklyOffMap[emp.value] = emp.weekly_off
            ? [emp.weekly_off.trim().toLowerCase()]
            : [];

        document.getElementById("ma_company").value    = employeeCompanyMap[emp.value] || "";
        document.getElementById("ma_weekly_off").value = (employeeWeeklyOffMap[emp.value] || [])
            .map(function (d) { return d.charAt(0).toUpperCase() + d.slice(1); }).join(", ");

        generateTable();
    }

    function clearSearch() {
        searchInput.value = "";
        employeeSel.value = "";
        document.getElementById("ma_company").value    = "";
        document.getElementById("ma_weekly_off").value = "";
        clearBtn.classList.remove("show");
        searchResults.classList.remove("show");
        tableEl.style.display = "none";
        attendanceTableData    = {};
        originalAttendanceData = {};
        clearTimeout(searchDebounceTimer);
        updateCounts();
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
            selectedIndex = -1;
            clearTimeout(searchDebounceTimer);
            return;
        }
        handleSearch(term.toLowerCase());
        selectedIndex = -1;
    });

    searchInput.addEventListener("keydown", function (e) {
        if (!searchResults.classList.contains("show")) return;
        if (e.key === "ArrowDown") {
            e.preventDefault();
            selectedIndex = (selectedIndex + 1) % filteredEmployees.length;
            highlightResult();
        } else if (e.key === "ArrowUp") {
            e.preventDefault();
            selectedIndex = (selectedIndex - 1 + filteredEmployees.length) % filteredEmployees.length;
            highlightResult();
        } else if (e.key === "Enter" && selectedIndex >= 0) {
            e.preventDefault();
            selectEmployee(filteredEmployees[selectedIndex]);
        } else if (e.key === "Escape") {
            searchResults.classList.remove("show");
        }
    });

    document.addEventListener("click", function (e) {
        if (!searchInput.contains(e.target) && !searchResults.contains(e.target) && !clearBtn.contains(e.target)) {
            searchResults.classList.remove("show");
        }
    });

    // ── Date helpers ───────────────────────────────────────────────────────
    function updateDatesFromMonthYear() {
        if (!yearSel.value || monthSel.value === "") return;
        var year    = yearSel.value;
        var month   = Number(monthSel.value);
        var lastDay = new Date(year, month + 1, 0);
        startDateInput.value = year + "-" + String(month + 1).padStart(2, "0") + "-01";
        endDateInput.value   = year + "-" + String(month + 1).padStart(2, "0") + "-" + String(lastDay.getDate()).padStart(2, "0");
        generateTable();
    }

    yearSel.addEventListener("change",  updateDatesFromMonthYear);
    monthSel.addEventListener("change", updateDatesFromMonthYear);

    function formatHalf(n) {
        return (n % 1 === 0) ? String(n) : n.toFixed(1);
    }

    // ── Status classification ──────────────────────────────────────────────
    function isAbsentSubtype(status)  { return ABSENT_SUBTYPES.includes(status); }
    function isPresentSubtype(status) { return PRESENT_SUBTYPES.includes(status); }
    function isPresent(status)        { return status === "Present" || isPresentSubtype(status); }

    // ── Count update ───────────────────────────────────────────────────────
    function updateCounts() {
        var p = 0, pr = 0, pt = 0, a = 0, h = 0, l = 0, el = 0, cl = 0, coff = 0, wo = 0, hol = 0;
        var totalDays = 0;

        Object.values(attendanceTableData).forEach(function (s) {
            if (!s) return;
            totalDays++;
            if      (s === "Present")      { p++; pr++; }
            else if (s === "Regular")      { p++; pr++; }
            else if (s === "On Tour")      { p++; pt++; }
            else if (s === "Absent")       a++;
            else if (s === "Half Day")     h++;
            else if (s === "LWP")          l++;
            else if (s === "Earned Leave") el++;
            else if (s === "Casual Leave") cl++;
            else if (s === "Comp Off")     coff++;
            else if (s === "Weekly Off")   wo++;
            else if (s === "Holiday")      hol++;
        });

        var totalAbsents = a + l + el + cl + coff;

        document.getElementById("ma_hd_col_count").textContent   = h;
        document.getElementById("ma_p_col_count").textContent    = p;
        document.getElementById("ma_pr_col_count").textContent   = pr;
        document.getElementById("ma_pt_col_count").textContent   = pt;
        document.getElementById("ma_a_col_count").textContent    = a;
        document.getElementById("ma_lwp_count_col").textContent  = l;
        document.getElementById("ma_el_count_col").textContent   = el;
        document.getElementById("ma_cl_count_col").textContent   = cl;
        document.getElementById("ma_coff_count_col").textContent = coff;
        document.getElementById("ma_wo_col_count").textContent   = wo;
        document.getElementById("ma_hol_col_count").textContent  = hol;

        document.getElementById("ma_hd_col_eq").textContent =
            h > 0 ? h + " \u00d7 0.5 = " + formatHalf(h * 0.5) + " day" : "";

        var elTaken = document.getElementById("ma_el_taken");
        var clTaken = document.getElementById("ma_cl_taken");
        if (elTaken) elTaken.textContent = el;
        if (clTaken) clTaken.textContent = cl;
    }

    function resolveStatus(rawStatus, isHoliday, isDefaultWeeklyOff) {
        if (!rawStatus) {
            if (isHoliday)          return "Holiday";
            if (isDefaultWeeklyOff) return "Weekly Off";
            return "";
        }
        return rawStatus;
    }

    // ── Radio helpers ──────────────────────────────────────────────────────
    function disableAllRadios(row, dateKey) {
        row.querySelectorAll(
            'input[name="status_' + dateKey + '"], input[name="p_subtype_' + dateKey + '"], input[name="a_subtype_' + dateKey + '"]'
        ).forEach(function (r) { r.disabled = true; r.checked = false; });
    }

    function enableMainRadios(row, dateKey) {
        row.querySelectorAll('input[name="status_' + dateKey + '"]').forEach(function (r) { r.disabled = false; });
        row.querySelectorAll('input[name="p_subtype_' + dateKey + '"], input[name="a_subtype_' + dateKey + '"]').forEach(function (r) {
            r.disabled = true; r.checked = false;
        });
        // Also re-enable present subtypes since Regular/On Tour are the "present" entry point
        row.querySelectorAll('input[name="p_subtype_' + dateKey + '"]').forEach(function (r) { r.disabled = false; });
    }

    function applyRowClass(row, status) {
        row.classList.remove("ma-holiday-row", "ma-weekly-off-row", "ma-override-row");
        if      (status === "Holiday")    row.classList.add("ma-holiday-row");
        else if (status === "Weekly Off") row.classList.add("ma-weekly-off-row");
    }

    // ── Weekly Off limit helpers ───────────────────────────────────────────
    function countWeeklyOffInMonth() {
        return Object.values(attendanceTableData).filter(function (s) { return s === "Weekly Off"; }).length;
    }

    function maxWeeklyOffInMonth() {
        var employee  = employeeSel.value;
        var year      = parseInt(yearSel.value);
        var month     = parseInt(monthSel.value);
        var weeklyOffDays = employeeWeeklyOffMap[employee] || [];
        if (!weeklyOffDays.length || isNaN(year) || isNaN(month)) return 0;
        var count = 0;
        var daysInMonth = new Date(year, month + 1, 0).getDate();
        for (var d = 1; d <= daysInMonth; d++) {
            var dayName = new Date(year, month, d)
                .toLocaleDateString("en-US", { weekday: "long" }).toLowerCase();
            if (weeklyOffDays.includes(dayName)) count++;
        }
        return count;
    }

    // ── resetRowToPresent: fully reset a row to a present subtype ─────────
    // FIX: This helper correctly wires up a row after switching to present
    // from any previous state (including absent-with-subtype).
    function resetRowToPresent(row, dateKey, subtype) {
        // 1. Uncheck & enable all main status radios, clear them
        row.querySelectorAll('input[name="status_' + dateKey + '"]').forEach(function (r) {
            r.disabled = false;
            r.checked  = false;
        });
        // 2. Enable present subtypes & check the right one
        row.querySelectorAll('input[name="p_subtype_' + dateKey + '"]').forEach(function (r) {
            r.disabled = false;
            r.checked  = (r.value === subtype);
        });
        // 3. Disable & clear absent subtypes
        row.querySelectorAll('input[name="a_subtype_' + dateKey + '"]').forEach(function (r) {
            r.disabled = true;
            r.checked  = false;
        });
        attendanceTableData[dateKey] = subtype;
        applyRowClass(row, "Present");
        row.classList.remove("ma-override-row");
    }

    // ── buildRow ───────────────────────────────────────────────────────────
    function buildRow(dateKey, dayName, currentDate, savedStatus, rawStatus,
                      isHoliday, isDefaultWeeklyOff, isFuture) {

        var row = document.createElement("tr");

        var isRestDay    = isHoliday || isDefaultWeeklyOff;
        var isOverridden = isRestDay && rawStatus && rawStatus !== "Holiday" && rawStatus !== "Weekly Off";

        var toggleChecked  = isRestDay && !isOverridden;
        var radiosDisabled = toggleChecked || isFuture;

        if      (isFuture)                            row.classList.add("ma-future-row");
        else if (isHoliday && toggleChecked)          row.classList.add("ma-holiday-row");
        else if (isDefaultWeeklyOff && toggleChecked) row.classList.add("ma-weekly-off-row");
        else if (isRestDay && !toggleChecked)         row.classList.add("ma-override-row");

        var isPresentStatus = isPresent(savedStatus);
        var presentSubtype  = isPresentSubtype(savedStatus) ? savedStatus : (savedStatus === "Present" ? "Regular" : "");
        // Present subtypes are always enabled on active rows — user must be able to
        // click Regular/On Tour to switch back from Absent at any time.
        var pSubDisabled    = radiosDisabled;

        var isAbsentStatus = savedStatus === "Absent" || isAbsentSubtype(savedStatus);
        var absentSubtype  = isAbsentSubtype(savedStatus) ? savedStatus : "";
        // Absent subtypes enabled when row is Absent; also keep pSub enabled when absent
        // so switching to present is always possible.
        var aSubDisabled   = radiosDisabled || !isAbsentStatus;

        // Toggle cell
        var toggleCell;
        if (isRestDay && !isFuture) {
            var restLabel = isHoliday ? "Holiday" : "Weekly Off";
            toggleCell =
                '<td class="text-center ma-toggle-cell" style="padding:8px;">' +
                '<label class="ma-toggle" title="' + restLabel + ' — uncheck to override">' +
                '<input type="checkbox" class="ma-weekly-off-toggle" data-date="' + dateKey + '"' +
                (toggleChecked ? ' checked' : '') + '>' +
                '<span class="ma-toggle-slider"></span>' +
                '</label></td>';
        } else {
            toggleCell = '<td class="text-center ma-no-toggle-cell">&#8212;</td>';
        }

        row.innerHTML =
            '<td class="ma-day-cell">'  + dayName + '</td>' +
            '<td class="ma-date-cell">' +
                currentDate.getDate() + ' ' +
                currentDate.toLocaleDateString("en-US", { month: "long" }) + ' ' +
                currentDate.getFullYear() +
            '</td>' +
            toggleCell +
            // Half Day
            '<td class="text-center">' +
                '<input type="radio" name="status_' + dateKey + '" value="Half Day"' +
                (savedStatus === "Half Day" ? " checked" : "") + (radiosDisabled ? " disabled" : "") + '>' +
            '</td>' +
            // Present subtype: Regular
            '<td class="text-center ma-psubtype-cell">' +
                '<input type="radio" name="p_subtype_' + dateKey + '" value="Regular"' +
                (presentSubtype === "Regular" ? " checked" : "") + (pSubDisabled ? " disabled" : "") +
                ' class="ma-psubtype-radio">' +
            '</td>' +
            // Present subtype: On Tour
            '<td class="text-center ma-psubtype-cell">' +
                '<input type="radio" name="p_subtype_' + dateKey + '" value="On Tour"' +
                (presentSubtype === "On Tour" ? " checked" : "") + (pSubDisabled ? " disabled" : "") +
                ' class="ma-psubtype-radio">' +
            '</td>' +
            // Absent (main)
            '<td class="text-center">' +
                '<input type="radio" name="status_' + dateKey + '" value="Absent"' +
                (isAbsentStatus ? " checked" : "") + (radiosDisabled ? " disabled" : "") + '>' +
            '</td>' +
            // Absent subtype: LWP
            '<td class="text-center ma-subtype-cell">' +
                '<input type="radio" name="a_subtype_' + dateKey + '" value="LWP"' +
                (absentSubtype === "LWP" ? " checked" : "") + (aSubDisabled ? " disabled" : "") +
                ' class="ma-subtype-radio">' +
            '</td>' +
            // Absent subtype: Earned Leave
            '<td class="text-center ma-subtype-cell">' +
                '<input type="radio" name="a_subtype_' + dateKey + '" value="Earned Leave"' +
                (absentSubtype === "Earned Leave" ? " checked" : "") + (aSubDisabled ? " disabled" : "") +
                ' class="ma-subtype-radio">' +
            '</td>' +
            // Absent subtype: Casual Leave
            '<td class="text-center ma-subtype-cell">' +
                '<input type="radio" name="a_subtype_' + dateKey + '" value="Casual Leave"' +
                (absentSubtype === "Casual Leave" ? " checked" : "") + (aSubDisabled ? " disabled" : "") +
                ' class="ma-subtype-radio">' +
            '</td>' +
            // Absent subtype: Comp Off
            '<td class="text-center ma-subtype-cell">' +
                '<input type="radio" name="a_subtype_' + dateKey + '" value="Comp Off"' +
                (absentSubtype === "Comp Off" ? " checked" : "") + (aSubDisabled ? " disabled" : "") +
                ' class="ma-subtype-radio">' +
            '</td>' +
            // Weekly Off
            '<td class="text-center ma-wo-cell">' +
                '<input type="radio" name="status_' + dateKey + '" value="Weekly Off"' +
                (savedStatus === "Weekly Off" ? " checked" : "") + (radiosDisabled ? " disabled" : "") + '>' +
            '</td>' +
            // Holiday
            '<td class="text-center ma-holiday-cell">' +
                '<input type="radio" name="status_' + dateKey + '" value="Holiday"' +
                (savedStatus === "Holiday" ? " checked" : "") + (radiosDisabled ? " disabled" : "") + '>' +
            '</td>';

        if (!isFuture) {
            // Toggle (override rest day)
            var toggleInput = row.querySelector(".ma-weekly-off-toggle");
            if (toggleInput) {
                toggleInput.addEventListener("change", function () {
                    var isNowChecked = this.checked;
                    if (isNowChecked) {
                        var restStatus = isHoliday ? "Holiday" : "Weekly Off";

                        if (restStatus === "Weekly Off") {
                            var limit     = maxWeeklyOffInMonth();
                            var prevSt    = attendanceTableData[dateKey] || "";
                            var currentWo = countWeeklyOffInMonth();
                            var woAfter   = prevSt === "Weekly Off" ? currentWo : currentWo + 1;

                            if (limit > 0 && woAfter > limit) {
                                this.checked = false;
                                var monthName = new Date(
                                    parseInt(yearSel.value), parseInt(monthSel.value), 1
                                ).toLocaleDateString("en-US", { month: "long" });
                                frappe.show_alert({
                                    message: "Weekly Off limit reached — " + monthName +
                                             " allows a maximum of <strong>" + limit + " Weekly Off" +
                                             (limit === 1 ? "" : "s") + "</strong>.",
                                    indicator: "red"
                                });
                                return;
                            }
                        }

                        disableAllRadios(row, dateKey);
                        var restRadio = row.querySelector('input[name="status_' + dateKey + '"][value="' + restStatus + '"]');
                        if (restRadio) restRadio.checked = true;
                        row.classList.remove("ma-override-row");
                        applyRowClass(row, restStatus);
                        attendanceTableData[dateKey] = restStatus;
                    } else {
                        enableMainRadios(row, dateKey);
                        row.querySelectorAll('input[name="status_' + dateKey + '"]').forEach(function (r) { r.checked = false; });
                        row.classList.remove("ma-holiday-row", "ma-weekly-off-row");
                        row.classList.add("ma-override-row");
                        attendanceTableData[dateKey] = "";
                    }
                    updateCounts();
                });
            }

            // Main status radios (Half Day, Absent, Weekly Off, Holiday)
            row.querySelectorAll('input[name="status_' + dateKey + '"]').forEach(function (inp) {
                inp.addEventListener("change", function () {
                    var val = this.value;

                    var pSubRadios = row.querySelectorAll('input[name="p_subtype_' + dateKey + '"]');
                    var aSubRadios = row.querySelectorAll('input[name="a_subtype_' + dateKey + '"]');

                    if (val === "Absent") {
                        // Enable absent subtypes; keep present subtypes ENABLED (unchecked)
                        // so the user can click Regular/On Tour to switch back to Present
                        aSubRadios.forEach(function (r) { r.disabled = false; });
                        pSubRadios.forEach(function (r) { r.disabled = false; r.checked = false; });
                        var checkedASub = row.querySelector('input[name="a_subtype_' + dateKey + '"]:checked');
                        attendanceTableData[dateKey] = checkedASub ? checkedASub.value : "Absent";
                    } else {
                        // Disable & clear ALL subtypes when switching to Half Day / WO / Holiday
                        pSubRadios.forEach(function (r) { r.disabled = true; r.checked = false; });
                        aSubRadios.forEach(function (r) { r.disabled = true; r.checked = false; });

                        // ── Weekly Off hard limit ──────────────────────────
                        if (val === "Weekly Off") {
                            var limit = maxWeeklyOffInMonth();
                            var prevStatus = attendanceTableData[dateKey] || "";
                            var currentWo  = countWeeklyOffInMonth();
                            var woAfter    = prevStatus === "Weekly Off" ? currentWo : currentWo + 1;

                            if (limit > 0 && woAfter > limit) {
                                this.checked = false;
                                var prevRadio = row.querySelector(
                                    'input[name="status_' + dateKey + '"][value="' + prevStatus + '"]'
                                );
                                if (prevRadio) prevRadio.checked = true;

                                var monthName = new Date(
                                    parseInt(yearSel.value), parseInt(monthSel.value), 1
                                ).toLocaleDateString("en-US", { month: "long" });

                                frappe.show_alert({
                                    message: "Weekly Off limit reached — " + monthName +
                                             " allows a maximum of <strong>" + limit + " Weekly Off" +
                                             (limit === 1 ? "" : "s") + "</strong>.",
                                    indicator: "red"
                                });
                                return;
                            }
                        }

                        attendanceTableData[dateKey] = val;
                    }

                    applyRowClass(row, val);
                    if (val !== "Weekly Off" && val !== "Holiday") {
                        row.classList.remove("ma-override-row");
                    }
                    updateCounts();
                });
            });

            // ── Present subtype radios (Regular / On Tour) ─────────────────
            // These are ALWAYS enabled on active rows.
            // Clicking one switches the row fully to Present, clearing everything else.
            row.querySelectorAll('input[name="p_subtype_' + dateKey + '"]').forEach(function (inp) {
                inp.addEventListener("change", function () {
                    var val = this.value;

                    // Uncheck + re-enable all main status radios
                    row.querySelectorAll('input[name="status_' + dateKey + '"]').forEach(function (r) {
                        r.checked  = false;
                        r.disabled = false;
                    });
                    // Uncheck + re-enable the other present subtype
                    row.querySelectorAll('input[name="p_subtype_' + dateKey + '"]').forEach(function (r) {
                        r.disabled = false;
                        // keep 'this' checked (browser already did it), uncheck others
                        if (r !== inp) r.checked = false;
                    });
                    // Uncheck absent subtypes but keep them enabled
                    // (they'll re-enable properly if user clicks Absent again)
                    row.querySelectorAll('input[name="a_subtype_' + dateKey + '"]').forEach(function (r) {
                        r.checked  = false;
                        r.disabled = true;
                    });

                    attendanceTableData[dateKey] = val;
                    applyRowClass(row, "Present");
                    row.classList.remove("ma-override-row");
                    updateCounts();
                });
            });

            // ── Absent subtype radios (LWP / EL / CL / Comp Off) ───────────
            // NEVER disable pSubRadios here — user must always be able to click
            // Regular/On Tour to switch back to Present.
            row.querySelectorAll('input[name="a_subtype_' + dateKey + '"]').forEach(function (inp) {
                inp.addEventListener("change", function () {
                    // pSubRadios: uncheck but leave ENABLED
                    row.querySelectorAll('input[name="p_subtype_' + dateKey + '"]').forEach(function (r) {
                        r.checked  = false;
                        r.disabled = false;
                    });
                    attendanceTableData[dateKey] = this.value;
                    updateCounts();
                });
            });
        }

        return row;
    }

    // ── Loading ────────────────────────────────────────────────────────────
    function showTableLoading() {
        tableEl.style.display = "none";
        tableLoading.style.display = "flex";
    }

    function hideTableLoading() {
        tableLoading.style.display = "none";
        tableEl.style.display = "table";
    }

    // ── generateTable ──────────────────────────────────────────────────────
    function generateTable() {
        var employee  = employeeSel.value;
        var startDate = startDateInput.value;
        var endDate   = endDateInput.value;
        if (!employee || !startDate || !endDate) return;

        var weeklyOffDays = employeeWeeklyOffMap[employee] || [];
        var company       = employeeCompanyMap[employee];
        var tbody         = document.getElementById("ma_table_body");

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
                        var attendanceMap      = res.message || {};
                        attendanceTableData    = {};
                        originalAttendanceData = {};
                        tbody.innerHTML        = "";

                        var current = new Date(startDate);
                        var end     = new Date(endDate);
                        var today   = new Date();
                        today.setHours(0, 0, 0, 0);

                        while (current <= end) {
                            var currentDate = new Date(current);
                            currentDate.setHours(0, 0, 0, 0);

                            var dayName = currentDate.toLocaleDateString("en-US", { weekday: "long" });
                            var dateKey = currentDate.getFullYear() + "-" +
                                String(currentDate.getMonth() + 1).padStart(2, "0") + "-" +
                                String(currentDate.getDate()).padStart(2, "0");

                            var isDefaultWeeklyOff = weeklyOffDays.includes(dayName.toLowerCase());
                            var isHoliday          = holidayDates[dateKey] === true;
                            var isFuture           = currentDate > today;

                            var rawStatus   = attendanceMap[dateKey] || "";
                            var savedStatus = resolveStatus(rawStatus, isHoliday, isDefaultWeeklyOff);

                            attendanceTableData[dateKey] = savedStatus;
                            if (rawStatus) originalAttendanceData[dateKey] = savedStatus;

                            tbody.appendChild(buildRow(
                                dateKey, dayName, currentDate,
                                savedStatus, rawStatus,
                                isHoliday, isDefaultWeeklyOff, isFuture
                            ));
                            current.setDate(current.getDate() + 1);
                        }

                        hideTableLoading();
                        updateCounts();
                    }
                });
            }
        });
    }

    // ── bulkMark ───────────────────────────────────────────────────────────
    function bulkMark(status) {
        var employee  = employeeSel.value;
        var startDate = startDateInput.value;
        if (!employee || !startDate) {
            frappe.show_alert({ message: "Please select an employee and month first", indicator: "orange" });
            return;
        }

        Object.keys(attendanceTableData).forEach(function (date) {
            if (originalAttendanceData[date]) return;
            var current = attendanceTableData[date];
            if (current === "Weekly Off" || current === "Holiday") return;

            var mainRadios   = document.querySelectorAll('input[name="status_' + date + '"]');
            var pSubRadios   = document.querySelectorAll('input[name="p_subtype_' + date + '"]');
            var aSubRadios   = document.querySelectorAll('input[name="a_subtype_' + date + '"]');
            if (!mainRadios.length || mainRadios[0].disabled) return;

            // ── FIX: Always fully reset all radio groups before applying bulk ──
            mainRadios.forEach(function (r) { r.checked = false; r.disabled = false; });
            pSubRadios.forEach(function (r) { r.checked = false; r.disabled = false; });
            aSubRadios.forEach(function (r) { r.checked = false; r.disabled = true; });

            if (status === "Present" || status === "Regular") {
                // Bulk Present → Regular subtype
                pSubRadios.forEach(function (r) { r.disabled = false; r.checked = (r.value === "Regular"); });
                aSubRadios.forEach(function (r) { r.disabled = true; r.checked = false; });
                attendanceTableData[date] = "Regular";
            } else if (isPresentSubtype(status)) {
                pSubRadios.forEach(function (r) { r.disabled = false; r.checked = (r.value === status); });
                aSubRadios.forEach(function (r) { r.disabled = true; r.checked = false; });
                attendanceTableData[date] = status;
            } else if (isAbsentSubtype(status)) {
                // Absent subtype: check Absent main radio + the subtype
                // Keep pSubRadios ENABLED so user can click Regular/On Tour to switch back
                mainRadios.forEach(function (r) { r.checked = (r.value === "Absent"); });
                pSubRadios.forEach(function (r) { r.disabled = false; r.checked = false; });
                aSubRadios.forEach(function (r) { r.disabled = false; r.checked = (r.value === status); });
                attendanceTableData[date] = status;
            } else if (status === "Absent") {
                mainRadios.forEach(function (r) { r.checked = (r.value === "Absent"); });
                pSubRadios.forEach(function (r) { r.disabled = false; r.checked = false; });
                aSubRadios.forEach(function (r) { r.disabled = false; r.checked = false; });
                attendanceTableData[date] = "Absent";
            } else {
                // Half Day, etc.
                mainRadios.forEach(function (r) { r.checked = (r.value === status); });
                pSubRadios.forEach(function (r) { r.disabled = true; r.checked = false; });
                aSubRadios.forEach(function (r) { r.disabled = true; r.checked = false; });
                attendanceTableData[date] = status;
            }

            var row = mainRadios[0] ? mainRadios[0].closest("tr") : null;
            if (row) applyRowClass(row, status);
        });
        updateCounts();
    }

    document.getElementById("ma_mark_present").onclick  = function () { bulkMark("Regular"); };
    document.getElementById("ma_mark_absent").onclick   = function () { bulkMark("Absent"); };
    document.getElementById("ma_mark_halfday").onclick  = function () { bulkMark("Half Day"); };
    document.getElementById("ma_mark_lwp").onclick      = function () { bulkMark("LWP"); };

    // ── Audio ──────────────────────────────────────────────────────────────
    function playSaveSound() {
        try {
            var audio = document.getElementById("ma-sound-click");
            if (audio) { audio.volume = 0.2; audio.play(); }
        } catch (e) {}
    }

    // ── doSave ─────────────────────────────────────────────────────────────
    function doSave() {
        if (isSaving) return;

        var employee = employeeSel.value;
        if (!employee) {
            frappe.show_alert({ message: "Please select an employee first", indicator: "orange" });
            return;
        }
        if (!startDateInput.value || !endDateInput.value) {
            frappe.show_alert({ message: "Please select a year and month first", indicator: "orange" });
            return;
        }

        var changedData  = [];
        var unchangedCnt = 0;

        Object.entries(attendanceTableData).forEach(function (entry) {
            var date     = entry[0];
            var status   = (entry[1] || "").trim();
            var original = (originalAttendanceData[date] || "").trim();

            if (!status) return;
            if (status === original) { unchangedCnt++; return; }
            changedData.push({ employee: employee, attendance_date: date, status: status });
        });

        if (!changedData.length) {
            frappe.show_alert({
                message: unchangedCnt > 0
                    ? "No changes to save. All attendance is already up to date."
                    : "Nothing to save. Please mark attendance for at least one day.",
                indicator: unchangedCnt > 0 ? "blue" : "orange"
            });
            return;
        }

        isSaving = true;
        playSaveSound();
        var scrollPos = document.querySelector(".ma-table-scroll").scrollTop;

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
                        generateTable();
                        setTimeout(function () {
                            document.querySelector(".ma-table-scroll").scrollTop = scrollPos;
                        }, 100);
                    }, 300);
                } else {
                    var errMsg = (r.message && r.message.error) ? r.message.error : "Error saving attendance";
                    frappe.show_alert({ message: errMsg, indicator: "red" });
                }
            },
            error: function () {
                isSaving = false;
                frappe.show_alert({ message: "Error saving attendance. Please try again.", indicator: "red" });
            }
        });
    }

    document.getElementById("ma_save_attendance").addEventListener("click", doSave);

    document.getElementById("ma_goto_attendance").addEventListener("click", function (e) {
        e.preventDefault();
        window.open(frappe.urllib.get_full_url("/app/attendance"), "_blank");
    });

    // ── Calendar modal ─────────────────────────────────────────────────────
    function normalizeDateKey(dateStr) {
        if (!dateStr) return null;
        if (dateStr instanceof Date) {
            return dateStr.getFullYear() + "-" +
                String(dateStr.getMonth() + 1).padStart(2, "0") + "-" +
                String(dateStr.getDate()).padStart(2, "0");
        }
        var parts = dateStr.toString().split("-");
        if (parts.length === 3) return parts[0] + "-" + parts[1].padStart(2, "0") + "-" + parts[2].padStart(2, "0");
        return dateStr;
    }

    function openCalendarModal() {
        var employee = employeeSel.value;
        if (!employee) {
            frappe.show_alert({ message: "Please select an employee first", indicator: "orange" });
            return;
        }
        document.getElementById("ma_cal_modal").classList.add("show");
        currentCalendarYear = parseInt(yearSel.value) || new Date().getFullYear();
        document.getElementById("ma_cal_year").textContent = currentCalendarYear;
        loadYearAttendance();
    }

    function closeCalendarModal() {
        document.getElementById("ma_cal_modal").classList.remove("show");
    }

    function changeYear(dir) {
        currentCalendarYear += dir;
        document.getElementById("ma_cal_year").textContent = currentCalendarYear;
        loadYearAttendance();
    }

    function loadYearAttendance() {
        var employee  = employeeSel.value;
        var company   = employeeCompanyMap[employee];
        if (!employee) return;

        var cacheKey = employee + "|" + currentCalendarYear;
        if (calendarCache[cacheKey]) {
            yearHolidayData    = calendarCache[cacheKey].holidays;
            yearAttendanceData = calendarCache[cacheKey].attendance;
            renderMonthsGrid();
            return;
        }

        var startDate = currentCalendarYear + "-01-01";
        var endDate   = currentCalendarYear + "-12-31";

        frappe.call({
            method: "saral_hr.saral_hr.page.mark_attendance.mark_attendance.get_holidays_between_dates",
            args: { company: company, start_date: startDate, end_date: endDate },
            callback: function (holidayRes) {
                var holidays = {};
                (holidayRes.message || []).forEach(function (h) {
                    var n = normalizeDateKey(h);
                    if (n) holidays[n] = true;
                });
                frappe.call({
                    method: "saral_hr.saral_hr.page.mark_attendance.mark_attendance.get_attendance_between_dates",
                    args: { employee: employee, start_date: startDate, end_date: endDate },
                    callback: function (res) {
                        var attendance = {};
                        Object.entries(res.message || {}).forEach(function (entry) {
                            var n = normalizeDateKey(entry[0]);
                            if (n) attendance[n] = entry[1];
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
        var employee      = employeeSel.value;
        var weeklyOffDays = employeeWeeklyOffMap[employee] || [];
        var monthsGrid    = document.getElementById("ma_months_grid");
        var monthNames    = ["January","February","March","April","May","June",
                             "July","August","September","October","November","December"];
        var dayNames      = ["S","M","T","W","T","F","S"];
        monthsGrid.innerHTML = "";

        monthNames.forEach(function (monthName, monthIndex) {
            var card = document.createElement("div");
            card.className = "ma-month-card";
            card.onclick   = function () { selectMonth(monthIndex); };

            var firstDay    = new Date(currentCalendarYear, monthIndex, 1);
            var lastDay     = new Date(currentCalendarYear, monthIndex + 1, 0);
            var startDay    = firstDay.getDay();
            var daysInMonth = lastDay.getDate();

            var html = '<div class="ma-month-name">' + monthName + '</div><div class="ma-mini-cal">';
            dayNames.forEach(function (d) { html += '<div class="ma-mini-hdr">' + d + '</div>'; });
            for (var i = 0; i < startDay; i++) html += '<div class="ma-mini-day empty"></div>';

            var today = new Date();
            for (var day = 1; day <= daysInMonth; day++) {
                var date    = new Date(currentCalendarYear, monthIndex, day);
                var dateKey = normalizeDateKey(date);
                var isToday = date.toDateString() === today.toDateString();
                var dayName = date.toLocaleDateString("en-US", { weekday: "long" }).toLowerCase();
                var isDefaultWeeklyOff = weeklyOffDays.includes(dayName);
                var isHoliday          = yearHolidayData[dateKey] === true;
                var status             = yearAttendanceData[dateKey];

                var cls = "ma-mini-day";
                if (isToday)                                             cls += " today";
                if      (isHoliday || status === "Holiday")             cls += " holiday";
                else if (status === "Present" || status === "Regular")  cls += " present";
                else if (status === "On Tour")                          cls += " on-tour";
                else if (status === "Absent")                           cls += " absent";
                else if (status === "Half Day")                         cls += " halfday";
                else if (status === "LWP")                              cls += " lwp";
                else if (status === "Earned Leave")                     cls += " el";
                else if (status === "Casual Leave")                     cls += " cl";
                else if (status === "Comp Off")                         cls += " coff";
                else if (status === "Weekly Off" || isDefaultWeeklyOff) cls += " weekend";

                html += '<div class="' + cls + '">' + day + '</div>';
            }
            html += '</div>';
            card.innerHTML = html;
            monthsGrid.appendChild(card);
        });
    }

    function selectMonth(monthIndex) {
        yearSel.value  = currentCalendarYear;
        monthSel.value = monthIndex;
        monthSel.dispatchEvent(new Event("change"));
        closeCalendarModal();
    }

    document.getElementById("ma_get_info").addEventListener("click", openCalendarModal);
    document.getElementById("ma_cal_close").addEventListener("click", closeCalendarModal);
    document.getElementById("ma_year_prev").addEventListener("click", function () { changeYear(-1); });
    document.getElementById("ma_year_next").addEventListener("click", function () { changeYear(1); });
    document.getElementById("ma_cal_modal").addEventListener("click", function (e) {
        if (e.target === this) closeCalendarModal();
    });

    document.addEventListener("keydown", function (e) {
        if (e.key === "Escape") closeCalendarModal();
        if ((e.ctrlKey || e.metaKey) && e.key === "s") {
            e.preventDefault();
            doSave();
        }
    });

    var _origGenerateTable = generateTable;
    generateTable = function () {
        invalidateCalendarCache();
        _origGenerateTable();
    };
}

// ── Audio injection ────────────────────────────────────────────────────────
function inject_ma_audio() {
    if (document.getElementById("ma-sound-click")) return;
    ["click", "submit", "cancel"].forEach(function (name) {
        var audio = document.createElement("audio");
        audio.id  = "ma-sound-" + name;
        audio.src = "/assets/frappe/sounds/" + name + ".mp3";
        audio.preload = "auto";
        audio.style.display = "none";
        document.body.appendChild(audio);
    });
}

// ── Style injection ────────────────────────────────────────────────────────
function inject_ma_styles() {
    if (document.getElementById("ma-styles")) return;
    var style = document.createElement("style");
    style.id  = "ma-styles";
    style.innerHTML = `
        .ma-wrap { padding: 0 4px; }

        .ma-sticky {
            position: sticky; top: 0;
            background: var(--card-bg, #fff);
            z-index: 100;
            padding-bottom: 12px;
            border-bottom: 1px solid var(--border-color, #e5e7eb);
            margin-bottom: 12px;
        }

        .ma-header-actions { display: flex; align-items: center; gap: 10px; margin-left: 20px; }
        .ma-link {
            font-size: 12px; color: #2d6be4; cursor: pointer;
            text-decoration: underline; text-underline-offset: 2px;
            background: none; border: none; padding: 0;
            font-weight: 500; transition: color 0.2s; white-space: nowrap;
        }
        .ma-link:hover { color: #1a4fb5; }
        .ma-link-sep { color: var(--text-muted); font-size: 12px; }

        .ma-btn           { background: #e6e6e6; color: #222; border: none; border-radius: 4px; padding: 6px 14px; font-weight: 500; cursor: pointer; transition: all 0.2s; font-size: 13px; white-space: nowrap; }
        .ma-btn-primary   { background: #2d2d2d; color: #fff; }
        .ma-btn:hover         { background: #d4d4d4; }
        .ma-btn-primary:hover { background: #1a1a1a; }
        .ma-btn:active        { transform: scale(0.98); }

        /* ── Layout ── */
        .ma-top-wrap     { display: flex; gap: 14px; align-items: stretch; }
        .ma-left-block   { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 10px; }
        .ma-row1         { display: flex; gap: 14px; align-items: flex-end; flex: 1; }
        .ma-r1-employee  { flex: 2; min-width: 0; position: relative; }
        .ma-r1-company   { flex: 2; min-width: 0; }
        .ma-r1-weeklyoff { flex: 1; min-width: 120px; }
        .ma-row2         { display: flex; gap: 14px; align-items: flex-end; }
        .ma-r2-year      { flex: 0 0 110px; }
        .ma-r2-month     { flex: 0 0 150px; }
        .ma-r2-buttons   { flex: 0 0 auto; }
        .ma-r1-leave     { flex: 0 0 auto; display: flex; align-items: stretch; }

        /* ── Labels & inputs ── */
        .ma-wrap .ma-label, label.ma-label {
            display: block !important; font-size: 11px !important; font-weight: 500 !important;
            color: var(--text-muted) !important; margin-bottom: 4px !important;
            text-transform: uppercase !important; letter-spacing: 0.04em !important; line-height: 1.4 !important;
        }
        .ma-input {
            width: 100%; padding: 0 10px; height: 32px; line-height: 32px;
            border: 1px solid var(--border-color, #d1d8dd); border-radius: 4px; font-size: 13px;
            background: var(--card-bg, #fff); color: var(--text-color); box-sizing: border-box;
        }
        .ma-input:focus     { outline: none; border-color: #666; box-shadow: 0 0 0 2px rgba(45,45,45,0.1); }
        .ma-input[readonly] { background: var(--control-bg, #f8f9fa); color: var(--text-muted); }

        /* ── Search dropdown ── */
        .ma-search-wrapper  { position: relative; }
        .ma-search-input    { padding-right: 30px; }
        .ma-clear-btn {
            position: absolute; right: 8px; top: 50%; transform: translateY(-50%);
            width: 18px; height: 18px; border-radius: 50%; background: #999; border: none; color: #fff;
            font-size: 11px; cursor: pointer; display: none; align-items: center; justify-content: center;
            transition: all 0.2s; padding: 0; line-height: 1;
        }
        .ma-clear-btn::before { content: '\\2715'; }
        .ma-clear-btn.show    { display: flex !important; }
        .ma-clear-btn:hover   { background: #666; }

        .ma-search-dropdown {
            display: none; position: absolute; top: 100%; left: 0; right: 0;
            background: var(--card-bg, #fff); border: 1px solid var(--border-color, #d1d8dd);
            border-top: none; border-radius: 0 0 4px 4px; max-height: 280px; overflow-y: auto;
            z-index: 1000; box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }
        .ma-search-dropdown.show { display: block; }
        .ma-result-item { padding: 10px 14px; cursor: pointer; border-bottom: 1px solid var(--border-color, #f0f0f0); transition: background 0.15s; }
        .ma-result-item:last-child { border-bottom: none; }
        .ma-result-item:hover,
        .ma-result-item.selected  { background: var(--control-bg, #f4f5f6); }
        .ma-result-name { font-size: 13px; font-weight: 500; color: var(--text-color); }
        .ma-result-id   { font-size: 11px; color: var(--text-muted); margin-top: 1px; }
        .ma-highlight   { font-weight: 700; color: #2d2d2d; }
        .ma-no-results  { padding: 12px 14px; font-size: 13px; color: var(--text-muted); text-align: center; }

        .ma-bulk-btns { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
        .ma-th-small  { display: block; font-size: 10px; font-weight: 400; color: var(--text-muted); margin-top: 2px; white-space: nowrap; }

        /* ── Attendance table ── */
        .ma-table-scroll { max-height: 520px; overflow-y: auto; overflow-x: auto; position: relative; }
        .ma-table        { width: 100%; border-collapse: collapse; }
        .ma-table td {
            border: 1px solid var(--border-color, #d1d8dd);
            padding: 6px 10px; font-size: 13px;
            background: var(--card-bg, #fff);
        }

        /* Loading overlay */
        .ma-table-loading {
            display: flex; flex-direction: column;
            align-items: center; justify-content: center;
            padding: 48px 0; gap: 14px;
        }
        .ma-spinner {
            width: 36px; height: 36px;
            border: 3px solid var(--border-color, #e5e7eb);
            border-top-color: #2d2d2d;
            border-radius: 50%;
            animation: ma-spin 0.7s linear infinite;
        }
        @keyframes ma-spin { to { transform: rotate(360deg); } }
        .ma-loading-text { font-size: 13px; color: var(--text-muted); }

        /* ── Present group header ── */
        .ma-present-group-th  { background: #f0fdf4 !important; color: #166534 !important; padding: 0 !important; vertical-align: top !important; }
        .ma-present-group-label { font-size: 11px; font-weight: 600; color: #166534; text-align: center; padding: 6px 10px 2px; border-bottom: 1px solid var(--border-color, #d1d8dd); }
        .ma-present-sub-row   { display: flex; width: 100%; }
        .ma-present-sub-cell  { flex: 1; text-align: center; font-size: 11px; font-weight: 600; color: #166534; padding: 5px 4px; border-right: 1px solid var(--border-color, #d1d8dd); }
        .ma-present-sub-cell:last-child { border-right: none; }

        /* Present subtype cells */
        .ma-psubtype-cell     { background: #dcfce7 !important; }
        .ma-psubtype-cell input:disabled { opacity: 0.25; cursor: not-allowed; }
        .ma-group-total { font-size: 11px; font-weight: 400; color: #166534; margin-left: 4px; }

        /* ── Absent group header ── */
        .ma-absent-group-th  { background: #fef3f2 !important; color: #c0392b !important; padding: 0 !important; vertical-align: top !important; }
        .ma-absent-group-label { font-size: 11px; font-weight: 600; color: #c0392b; text-align: center; padding: 6px 10px 4px; border-bottom: 1px solid var(--border-color, #d1d8dd); }
        .ma-absent-sub-row   { display: flex; width: 100%; }
        .ma-absent-sub-cell  { flex: 1; text-align: center; font-size: 11px; font-weight: 600; color: #c0392b; padding: 5px 4px; border-right: 1px solid var(--border-color, #d1d8dd); }
        .ma-absent-sub-cell:last-child { border-right: none; }

        /* Absent subtype cells */
        .ma-subtype-cell              { background: #fef9f9 !important; }
        .ma-subtype-cell input:disabled { opacity: 0.25; cursor: not-allowed; }

        /* Weekly Off / Holiday columns */
        .ma-wo-cell      { background: #eff6ff !important; }
        .ma-holiday-cell { background: #fff7ed !important; }
        .ma-no-toggle-cell { color: var(--text-muted); font-size: 16px; vertical-align: middle; }

        /* ── Row colours ── */
        .ma-holiday-row    td { background: #fff3e0 !important; color: #e65100 !important; font-weight: 500; }
        .ma-weekly-off-row td { background: var(--control-bg, #f5f5f5) !important; color: var(--text-muted) !important; }
        .ma-override-row   td:first-child { border-left: 3px solid #f59e0b !important; }
        .ma-future-row        { opacity: 0.5; }
        .ma-future-row     td { background: var(--control-bg, #f9f9f9) !important; color: var(--text-muted) !important; }

        .text-center { text-align: center; }

        /* ── Sticky thead ── */
        .ma-table thead tr th {
            position: sticky; top: 0; z-index: 50;
            background: var(--control-bg, #f7f7f7); border: 1px solid var(--border-color, #d1d8dd);
            padding: 8px 10px; font-size: 12px; font-weight: 600; vertical-align: middle;
            box-shadow: 0 2px 2px -1px rgba(0,0,0,0.08);
        }
        .ma-col-override { width: 90px; }
        .ma-col-wo       { background: #e8f2ff !important; color: #1e40af !important; }
        .ma-col-holiday  { background: #fff1e6 !important; color: #9a3412 !important; }

        /* ── Toggle switch ── */
        .ma-toggle        { position: relative; display: inline-block; width: 50px; height: 26px; margin: 0; }
        .ma-toggle input  { opacity: 0; width: 0; height: 0; }
        .ma-toggle-slider {
            position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0;
            background: #ccc; border-radius: 26px; border: 1px solid #bbb; transition: 0.3s;
        }
        .ma-toggle-slider:before {
            position: absolute; content: ""; height: 20px; width: 20px;
            left: 2px; bottom: 2px; background: #fff; border-radius: 50%; transition: 0.3s;
        }
        .ma-toggle input:checked + .ma-toggle-slider        { background: #2d2d2d; border-color: #2d2d2d; }
        .ma-toggle input:checked + .ma-toggle-slider:before { transform: translateX(24px); }
        .ma-toggle input:not(:checked) + .ma-toggle-slider  { background: #d1fae5; border-color: #059669; }

        /* ── Calendar Modal ── */
        .ma-cal-modal      { display: none; position: fixed; z-index: 2000; left: 0; top: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.6); backdrop-filter: blur(4px); }
        .ma-cal-modal.show { display: flex; align-items: center; justify-content: center; }
        .ma-cal-content    { background: #fff; border-radius: 12px; width: 95%; max-width: 900px; max-height: 85vh; overflow: hidden; box-shadow: 0 20px 60px rgba(0,0,0,0.3); position: relative; }
        .ma-cal-close      { position: absolute; top: 12px; right: 12px; z-index: 10; background: #e5e7eb; border: none; color: #374151; width: 28px; height: 28px; border-radius: 50%; font-size: 14px; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: background 0.2s; }
        .ma-cal-close:hover { background: #d1d5db; color: #111; }
        .ma-cal-body       { padding: 20px 16px; overflow-y: auto; max-height: 85vh; }

        .ma-year-selector { display: flex; align-items: center; justify-content: center; gap: 16px; margin-bottom: 14px; }
        .ma-year-center   { display: flex; flex-direction: column; align-items: center; min-width: 90px; }
        .ma-year-num      { font-size: 22px; font-weight: 700; color: #111; line-height: 1.1; }
        .ma-year-sub      { font-size: 10px; color: #9ca3af; font-weight: 400; letter-spacing: 0.03em; margin-top: 1px; }
        .ma-year-nav {
            background: var(--control-bg, #f3f4f6); border: 1px solid var(--border-color, #e5e7eb);
            width: 28px; height: 28px; border-radius: 50%; font-size: 18px;
            cursor: pointer; display: flex; align-items: center; justify-content: center;
            color: #374151; transition: all 0.2s; flex-shrink: 0;
        }
        .ma-year-nav:hover { background: #2d2d2d; color: #fff; border-color: #2d2d2d; }

        .ma-cal-legend  { display: flex; gap: 14px; justify-content: center; margin-bottom: 16px; flex-wrap: wrap; font-size: 12px; }
        .ma-legend-item { display: flex; align-items: center; gap: 5px; color: var(--text-muted); }
        .ma-legend-dot  { width: 13px; height: 13px; border-radius: 3px; display: inline-block; box-sizing: border-box; }
        .ma-legend-dot.present  { background: #d1fae5; border: 2px solid #059669; }
        .ma-legend-dot.on-tour  { background: #d1fae5; border: 2px solid #0d9488; border-style: dashed; }
        .ma-legend-dot.absent   { background: #fee2e2; border: 2px solid #dc2626; }
        .ma-legend-dot.halfday  { background: #fef9c3; border: 2px solid #ca8a04; }
        .ma-legend-dot.lwp      { background: #f3e8ff; border: 2px solid #9333ea; }
        .ma-legend-dot.el       { background: #dbeafe; border: 2px solid #2563eb; }
        .ma-legend-dot.cl       { background: #cffafe; border: 2px solid #0891b2; }
        .ma-legend-dot.coff     { background: #fdf4ff; border: 2px solid #a855f7; }
        .ma-legend-dot.holiday  { background: #ffedd5; border: 2px solid #ea580c; }
        .ma-legend-dot.weekend  { background: #eff6ff; border: 2px solid #93c5fd; }

        /* ── Mini calendar grid ── */
        .ma-months-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
        .ma-month-card  { background: #fff; border: 2px solid var(--border-color, #e5e7eb); border-radius: 8px; padding: 12px; cursor: pointer; transition: all 0.2s; }
        .ma-month-card:hover { border-color: #2d2d2d; box-shadow: 0 4px 12px rgba(0,0,0,0.1); transform: translateY(-2px); }
        .ma-month-name  { font-size: 15px; font-weight: 600; color: #111; margin-bottom: 10px; }
        .ma-mini-cal    { display: grid; grid-template-columns: repeat(7,1fr); gap: 1px; }
        .ma-mini-hdr    { font-size: 9px; font-weight: 600; color: #6b7280; text-align: center; padding: 2px; }
        .ma-mini-day    { font-size: 10px; text-align: center; padding: 3px 1px; color: #374151; border-radius: 2px; }
        .ma-mini-day.empty   { visibility: hidden; }
        .ma-mini-day.today   { background: #2d2d2d !important; color: #fff !important; font-weight: 700; border-radius: 3px; }
        .ma-mini-day.present { background: #d1fae5 !important; color: #065f46 !important; font-weight: 700; border: 2px solid #059669 !important; border-radius: 3px; box-sizing: border-box; }
        .ma-mini-day.on-tour { background: #ccfbf1 !important; color: #134e4a !important; font-weight: 700; border: 2px dashed #0d9488 !important; border-radius: 3px; box-sizing: border-box; }
        .ma-mini-day.absent  { background: #fee2e2 !important; color: #991b1b !important; font-weight: 700; border: 2px solid #dc2626 !important; border-radius: 3px; box-sizing: border-box; }
        .ma-mini-day.halfday { background: #fef9c3 !important; color: #854d0e !important; font-weight: 700; border: 2px solid #ca8a04 !important; border-radius: 3px; box-sizing: border-box; }
        .ma-mini-day.lwp     { background: #f3e8ff !important; color: #6b21a8 !important; font-weight: 700; border: 2px solid #9333ea !important; border-radius: 3px; box-sizing: border-box; }
        .ma-mini-day.el      { background: #dbeafe !important; color: #1e40af !important; font-weight: 700; border: 2px solid #2563eb !important; border-radius: 3px; box-sizing: border-box; }
        .ma-mini-day.cl      { background: #cffafe !important; color: #155e75 !important; font-weight: 700; border: 2px solid #0891b2 !important; border-radius: 3px; box-sizing: border-box; }
        .ma-mini-day.coff    { background: #fdf4ff !important; color: #701a75 !important; font-weight: 700; border: 2px solid #a855f7 !important; border-radius: 3px; box-sizing: border-box; }
        .ma-mini-day.holiday { background: #ffedd5 !important; color: #9a3412 !important; font-weight: 700; border: 2px solid #ea580c !important; border-radius: 3px; box-sizing: border-box; }
        .ma-mini-day.weekend { background: #eff6ff !important; color: #1e3a8a !important; font-weight: 600; border: 2px solid #93c5fd !important; border-radius: 3px; box-sizing: border-box; }

        .page-head-content { padding: 8px 17px 0px 0px !important; }

        /* ── Leave Summary ── */
        .ma-leave-table { border-collapse: collapse; height: 100%; }
        .ma-leave-th {
            background: var(--control-bg, #f7f7f7); border: 1px solid var(--border-color, #d1d8dd);
            padding: 4px 14px; font-size: 11px; font-weight: 600; text-align: center;
            color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.03em; white-space: nowrap;
        }
        .ma-leave-th.ma-leave-type-hdr {
            background: transparent; border: 1px solid var(--border-color, #d1d8dd); border-right: none;
            font-size: 11px; font-weight: 500; color: var(--text-muted); text-transform: uppercase;
            letter-spacing: 0.04em; text-align: left; padding: 4px 10px; white-space: nowrap;
        }
        .ma-leave-row-label {
            font-size: 11px; font-weight: 500; color: var(--text-muted); text-transform: uppercase;
            letter-spacing: 0.03em; padding: 4px 10px;
            border: 1px solid var(--border-color, #d1d8dd); border-right: none;
            background: var(--control-bg, #f7f7f7); white-space: nowrap;
        }
        .ma-leave-val { text-align: center; font-size: 13px; font-weight: 700; color: var(--text-color, #333); border: 1px solid var(--border-color, #d1d8dd); padding: 4px 14px; background: var(--card-bg, #fff); min-width: 52px; }
        .ma-leave-bal { color: var(--text-muted); font-weight: 500; font-size: 12px; }
    `;
    document.head.appendChild(style);
}