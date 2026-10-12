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
            <button id="dwa_save_btn" class="dwa-btn dwa-btn-primary">Save Attendance</button>
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
                        placeholder="Search employee..." autocomplete="off" />
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
                <div class="dwa-card-val" id="dwa_cnt_hours">0.00</div>
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

        <!-- ══════════════════════════════════════════════════════════════
             RUNTIME SALARY PANEL — SSA vs Actual side-by-side tabular
        ══════════════════════════════════════════════════════════════════ -->
        <div class="dwa-runtime-panel" id="dwa_runtime_panel" style="display:none;">
            <button class="dwa-ded-toggle dwa-runtime-toggle" id="dwa_runtime_toggle" type="button">
                <span class="dwa-ded-toggle-icon" id="dwa_runtime_icon">&#9654;</span>
                <span class="dwa-ded-toggle-title">Runtime Salary Calculation</span>
                <span class="dwa-ded-toggle-sub dwa-runtime-sub-label" id="dwa_runtime_sub_label">SSA vs Actual Deductions</span>
                <span class="dwa-ded-toggle-totals" id="dwa_runtime_totals"></span>
            </button>
            <div class="dwa-ded-body-wrap" id="dwa_runtime_body_wrap" style="display:none;">

                <!-- Editable override inputs -->
                <div class="dwa-rt-override-bar">
                    <div class="dwa-rt-override-group">
                        <label class="dwa-rt-ovr-label">Override Gross (&#8377;)</label>
                        <input type="number" id="dwa_rt_gross_override" class="dwa-rt-ovr-input" placeholder="Auto from attendance" min="0" step="0.01" />
                        <button class="dwa-rt-ovr-reset" id="dwa_rt_gross_reset" title="Reset to attendance gross">&#8635;</button>
                    </div>
                    <div class="dwa-rt-pf-limit-info" id="dwa_rt_pf_limit_info" style="display:none;"></div>
                </div>

                <div class="dwa-rt-note">
                    <span class="dwa-rt-note-icon">&#8505;</span>
                    Side-by-side comparison: <strong>SSA Fixed</strong> (amounts from Salary Structure Assignment) vs <strong>Actual Runtime</strong> (PF calculated as 12% of Gross capped at &#8377;15,000; ESIC recalculated on live Gross using SSA-derived rate; <strong>Special components</strong> (PT, LWF) use their month-specific amount; other fixed components use SSA value).
                </div>

                <!-- Side-by-side breakdown table: SSA Fixed | Actual Runtime -->
                <div class="dwa-rt-table-wrap">
                    <table class="dwa-rt-table">
                        <thead>
                            <tr>
                                <th class="dwa-rt-th-comp">Component</th>
                                <th class="dwa-rt-th-type">Type</th>
                                <th class="dwa-rt-th-ssa">SSA Fixed</th>
                                <th class="dwa-rt-th-actual">Actual (Runtime)</th>
                                <th class="dwa-rt-th-note">Note</th>
                            </tr>
                        </thead>
                        <tbody id="dwa_rt_tbody"></tbody>
                        <tfoot id="dwa_rt_tfoot"></tfoot>
                    </table>
                </div>

                <!-- Net salary cards -->
                <div class="dwa-rt-net-cards" id="dwa_rt_net_cards" style="display:none;">
                    <div class="dwa-rt-net-card dwa-rt-net-runtime">
                        <div class="dwa-rt-net-lbl">Net (Actual Runtime)</div>
                        <div class="dwa-rt-net-val" id="dwa_rt_net_runtime">&#8377;0</div>
                        <div class="dwa-rt-net-sub">Gross &minus; Actual Deductions</div>
                    </div>
                    <div class="dwa-rt-net-card dwa-rt-net-ssa">
                        <div class="dwa-rt-net-lbl">Net (SSA Fixed)</div>
                        <div class="dwa-rt-net-val" id="dwa_rt_net_ssa">&#8377;—</div>
                        <div class="dwa-rt-net-sub">Gross &minus; Fixed SSA deductions</div>
                    </div>
                </div>

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
                        <th class="dwa-th dwa-th-remarks">Remarks</th>
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
    return saral_hr.period_picker.get_period_year_options(false).map(function (y) {
        var cur = new Date().getFullYear();
        return '<option value="' + y + '"' + (parseInt(y, 10) === cur ? " selected" : "") + ">" + y + "</option>";
    }).join("");
}

// ════════════════════════════════════════════════════════════════════════════
//  MONTH NAME HELPER
// ════════════════════════════════════════════════════════════════════════════
var MONTH_NAMES = [
    "January","February","March","April","May","June",
    "July","August","September","October","November","December"
];

// ════════════════════════════════════════════════════════════════════════════
//  OT HELPERS  — decimal hours (4 = 4h, 4.5 = 4h30m)
// ════════════════════════════════════════════════════════════════════════════

/** Parse user input → decimal float (e.g. "4.5" → 4.5, "4" → 4, "" → 0) */
function parseOtDecimal(raw) {
    if (!raw) return 0;
    var v = parseFloat(raw.trim());
    return isNaN(v) || v < 0 ? 0 : v;
}

/** decimal float → total minutes (4.5 → 270) */
function otDecimalToMinutes(dec) {
    var whole = Math.floor(dec);
    var mins  = Math.round((dec - whole) * 60);
    return whole * 60 + mins;
}

/** decimal float → display string  "4.50 hrs" */
function formatOtDisplay(dec) {
    if (!dec || dec <= 0) return "0.00";
    return dec.toFixed(2);
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
//  RUNTIME DEDUCTION ENGINE
//  PF: always 12% of min(gross, 15000) — no wage-limit suppression
//  ESIC: rate derived from SSA, applied on live gross
// ════════════════════════════════════════════════════════════════════════════
var PF_RATE      = 0.12;
var PF_BASIC_CAP = 15000;

function classifyComponent(comp) {
    var name = ((comp.salary_component || "") + " " + (comp.abbr || "")).toLowerCase();
    if (name.match(/\bpf\b|provident.fund|emp.?pf|employee.?pf/)) return "pf";
    if (name.match(/\besic\b|esi\b|emp.?esi|employee.?esi|emp.?esic/)) return "esic";
    return "fixed";
}

function calcRuntimeDeductionsFromSSA(gross, ssaDeductions, companyPfWageLimit, ssaBase, specialMonthlyAmounts, currentMonthName) {
    var results    = [];
    var totalActual = 0;

    ssaDeductions.forEach(function (comp) {
        var kind      = classifyComponent(comp);
        var ssaAmount = parseFloat(comp.amount || 0);
        var actualAmount = 0;
        var basis     = "";
        var rateLabel = "";
        var applicable = true;
        var note      = "";
        var isSpecial = !!(specialMonthlyAmounts && specialMonthlyAmounts[comp.salary_component]);

        if (kind === "pf") {
            // Always calculate PF on gross — capped at ₹15,000 basic
            var pfCapped = Math.min(gross, PF_BASIC_CAP);
            actualAmount = pfCapped * PF_RATE;
            applicable   = true;
            basis        = "Basic \u20b9" + pfCapped.toLocaleString("en-IN", { maximumFractionDigits: 2 }) +
                           (pfCapped < gross ? " (capped \u20b915,000)" : "");
            rateLabel    = (PF_RATE * 100).toFixed(2) + "%";
            note         = "";

        } else if (kind === "esic") {
            var base = parseFloat(ssaBase || 0);
            var esicRate = (base > 0 && ssaAmount > 0)
                ? (ssaAmount / base)
                : 0.0075;

            actualAmount = gross * esicRate;
            applicable   = true;
            basis        = "Gross \u20b9" + gross.toLocaleString("en-IN", { maximumFractionDigits: 2 });
            rateLabel    = (esicRate * 100).toFixed(4).replace(/\.?0+$/, "") + "%";
            note         = "";

        } else {
            if (isSpecial && currentMonthName) {
                var monthAmounts = specialMonthlyAmounts[comp.salary_component];
                var monthAmt     = (monthAmounts && monthAmounts[currentMonthName] !== undefined)
                                    ? parseFloat(monthAmounts[currentMonthName])
                                    : ssaAmount;
                actualAmount = monthAmt;
                basis        = "Special \u00b7 " + currentMonthName;
                rateLabel    = "\u20b9" + monthAmt.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
                applicable   = monthAmt > 0;
                if (Math.abs(monthAmt - ssaAmount) > 0.01) {
                    note = "Month-specific: SSA has \u20b9" + ssaAmount.toLocaleString("en-IN", { maximumFractionDigits: 2 });
                }
            } else {
                actualAmount = ssaAmount;
                basis        = "Fixed (SSA)";
                rateLabel    = "\u20b9" + ssaAmount.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
                applicable   = ssaAmount > 0;
            }
        }

        if (applicable) totalActual += actualAmount;

        results.push({
            salary_component: comp.salary_component,
            abbr:             comp.abbr || comp.salary_component,
            kind:             kind,
            isSpecial:        isSpecial,
            basis:            basis,
            rateLabel:        rateLabel,
            ssaAmount:        ssaAmount,
            actualAmount:     actualAmount,
            applicable:       applicable,
            note:             note,
        });
    });

    var totalSsa = ssaDeductions.reduce(function (s, r) { return s + parseFloat(r.amount || 0); }, 0);
    return {
        components:  results,
        totalActual: totalActual,
        totalSsa:    totalSsa,
        netActual:   gross - totalActual,
        netSsa:      gross - totalSsa,
    };
}

// ════════════════════════════════════════════════════════════════════════════
//  INIT
// ════════════════════════════════════════════════════════════════════════════
function init_daily_wage_attendance($main) {

    var allEmployees      = [];
    var filteredEmps      = [];
    var selectedIndex     = -1;
    var searchTimer       = null;
    var isSaving          = false;
    var attendanceData    = {};
    var originalData      = {};
    var otDecimalData     = {};   // dk → decimal float (4.5 = 4h30m)
    var remarksData       = {};   // dk → string
    var dirtyDates        = new Set();
    var holidayDates      = {};
    var joiningDate       = null;
    var leftDate          = null;
    var dailyRateMap      = {};
    var currentLockState  = null;
    var sandwichEligible  = {};
    var sandwichUnpaid    = {};
    var ssaDeductions     = [];
    var ssaTotalDed       = 0;
    var ssaBase           = 0;
    var runtimeOpen       = false;

    var specialMonthlyAmounts = {};
    var currentMonthName      = "";
    var companyPfWageLimit    = 0;
    var rtGrossOverride       = null;

    var FULL_STATUSES    = ["Present", "On Tour", "Absent", "Holiday"];
    var STATUS_DOT_CLASS = { "Present": "present-dot", "On Tour": "present-dot", "Absent": "absent-dot", "Holiday": "holiday-dot" };

    // DOM refs
    var companySel      = document.getElementById("dwa_company");
    var searchInput     = document.getElementById("dwa_employee_search");
    var searchResults   = document.getElementById("dwa_search_results");
    var clearEmpBtn     = document.getElementById("dwa_clear_employee");
    var employeeSel     = document.getElementById("dwa_employee_sel");
    var yearSel         = document.getElementById("dwa_year");
    var monthSel        = document.getElementById("dwa_month");
    var loadBtn         = document.getElementById("dwa_load_btn");
    var clearBtn        = document.getElementById("dwa_clear_btn");
    var loadingTable    = document.getElementById("dwa_loading_table");
    var tableScroll     = document.getElementById("dwa_table_scroll");
    var tbody           = document.getElementById("dwa_tbody");
    var emptyEl         = document.getElementById("dwa_empty");
    var summaryBar      = document.getElementById("dwa_summary_bar");
    var bulkBar         = document.getElementById("dwa_bulk_bar");
    var saveBtn         = document.getElementById("dwa_save_btn");
    var slipBanner      = document.getElementById("dwa_slip_banner");
    var sandwichBanner  = document.getElementById("dwa_sandwich_banner");
    var infoPanel       = document.getElementById("dwa_info_panel");

    // Runtime panel DOM refs
    var runtimePanel    = document.getElementById("dwa_runtime_panel");
    var runtimeToggle   = document.getElementById("dwa_runtime_toggle");
    var runtimeBodyWrap = document.getElementById("dwa_runtime_body_wrap");
    var runtimeIcon     = document.getElementById("dwa_runtime_icon");
    var runtimeTotals   = document.getElementById("dwa_runtime_totals");
    var runtimeSubLabel = document.getElementById("dwa_runtime_sub_label");
    var rtTbody         = document.getElementById("dwa_rt_tbody");
    var rtTfoot         = document.getElementById("dwa_rt_tfoot");
    var rtNetCards      = document.getElementById("dwa_rt_net_cards");
    var rtNetRuntime    = document.getElementById("dwa_rt_net_runtime");
    var rtNetSsa        = document.getElementById("dwa_rt_net_ssa");
    var rtGrossInput    = document.getElementById("dwa_rt_gross_override");
    var rtGrossReset    = document.getElementById("dwa_rt_gross_reset");
    var rtPfLimitInfo   = document.getElementById("dwa_rt_pf_limit_info");

    // ── Collapsible: Runtime panel ───────────────────────────────────────
    runtimeToggle.addEventListener("click", function () {
        runtimeOpen = !runtimeOpen;
        runtimeBodyWrap.style.display = runtimeOpen ? "block" : "none";
        runtimeIcon.innerHTML = runtimeOpen ? "&#9660;" : "&#9654;";
    });

    // ── Runtime override inputs ──────────────────────────────────────────
    rtGrossInput.addEventListener("input", function () {
        var v = parseFloat(this.value);
        rtGrossOverride = (!this.value || isNaN(v)) ? null : v;
        renderRuntimePanel();
    });
    rtGrossReset.addEventListener("click", function () {
        rtGrossInput.value = "";
        rtGrossOverride = null;
        renderRuntimePanel();
    });

    // ════════════════════════════════════════════════════════════════════════
    //  FETCH COMPANY PF WAGE LIMIT (kept for display info only — no longer
    //  used to suppress PF calculation)
    // ════════════════════════════════════════════════════════════════════════
    function loadCompanyPfWageLimit(company) {
        companyPfWageLimit = 0;
        if (rtPfLimitInfo) rtPfLimitInfo.style.display = "none";
        if (!company) return;

        frappe.call({
            method: "frappe.client.get_value",
            args: {
                doctype:  "Company",
                fieldname: "pf_wage_limit",
                filters:  { name: company }
            },
            callback: function (r) {
                var limit = (r && r.message && r.message.pf_wage_limit) ? parseFloat(r.message.pf_wage_limit) : 0;
                companyPfWageLimit = limit || 0;
                // PF limit info badge removed — PF always applies now
                renderRuntimePanel();
            },
            error: function () { companyPfWageLimit = 0; }
        });
    }

    // ════════════════════════════════════════════════════════════════════════
    //  INFO PANEL HELPERS
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
        loadCompanyPfWageLimit(companySel.value);
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
    //  SSA DEDUCTIONS
    // ════════════════════════════════════════════════════════════════════════
    function loadSsaDeductions(employee, startDate) {
        ssaDeductions = []; ssaTotalDed = 0; ssaBase = 0;
        specialMonthlyAmounts = {};
        runtimePanel.style.display = "none";
        runtimeOpen = false; runtimeBodyWrap.style.display = "none"; runtimeIcon.innerHTML = "&#9654;";

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
                if (!rows.length) {
                    _infoFlags.noSsa = true;
                    renderInfoPanel();
                    return;
                }

                if (runtimeSubLabel) {
                    runtimeSubLabel.textContent = rows[0].salary_structure + " \u2014 SSA vs Actual";
                }

                frappe.call({
                    method: "frappe.client.get",
                    args: { doctype: "Salary Structure Assignment", name: rows[0].name },
                    callback: function (dr) {
                        var doc = dr && dr.message;
                        if (!doc) return;

                        ssaBase = parseFloat(doc.base || 0);

                        ssaDeductions = (doc.deductions || [])
                            .filter(function (row) { return !parseInt(row.employer_contribution || 0); })
                            .map(function (row) {
                                return {
                                    salary_component: row.salary_component || "",
                                    abbr:             row.abbr || "",
                                    amount:           parseFloat(row.amount || 0),
                                };
                            });

                        ssaTotalDed = ssaDeductions.reduce(function (s, r) { return s + r.amount; }, 0);

                        var fixedCompNames = ssaDeductions
                            .filter(function (c) { return classifyComponent(c) === "fixed"; })
                            .map(function (c) { return c.salary_component; });

                        if (fixedCompNames.length) {
                            frappe.call({
                                method: "saral_hr.saral_hr.page.daily_wage_attendance.daily_wage_attendance.get_special_component_monthly_amounts",
                                args: { component_names: fixedCompNames },
                                callback: function (sr) {
                                    specialMonthlyAmounts = (sr && sr.message) ? sr.message : {};
                                    renderRuntimePanel();
                                },
                                error: function () {
                                    specialMonthlyAmounts = {};
                                    renderRuntimePanel();
                                }
                            });
                        } else {
                            renderRuntimePanel();
                        }
                    }, error: function () {}
                });
            }, error: function () {}
        });
    }

    // ════════════════════════════════════════════════════════════════════════
    //  RUNTIME SALARY PANEL
    // ════════════════════════════════════════════════════════════════════════
    function getAttendanceGross() {
        var payableText = (document.getElementById("dwa_cnt_payable") || {}).textContent || "0";
        return parseFloat(payableText.replace(/[^\d.]/g, "")) || 0;
    }

    function renderRuntimePanel() {
        if (!ssaDeductions.length) {
            runtimePanel.style.display = "none";
            return;
        }

        var gross = (rtGrossOverride !== null) ? rtGrossOverride : getAttendanceGross();
        runtimePanel.style.display = "block";

        var d = calcRuntimeDeductionsFromSSA(
            gross,
            ssaDeductions,
            companyPfWageLimit,
            ssaBase,
            specialMonthlyAmounts,
            currentMonthName
        );

        var fmtINR = function (n) {
            return "\u20b9" + n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        };

        runtimeTotals.innerHTML =
            '<span class="dwa-ded-badge dwa-ded-badge-ded">&minus;' + fmtINR(d.totalActual) + ' Actual</span>' +
            '<span class="dwa-ded-badge dwa-ded-badge-net">Net&nbsp;' + fmtINR(d.netActual) + '</span>';

        rtTbody.innerHTML = d.components.map(function (comp) {
            var typeBadge;
            if (comp.kind === "pf" || comp.kind === "esic") {
                typeBadge = '<span class="dwa-rt-type-badge dwa-rt-type-calc">Calc</span>';
            } else if (comp.isSpecial) {
                typeBadge = '<span class="dwa-rt-type-badge dwa-rt-type-special">Special</span>';
            } else {
                typeBadge = '<span class="dwa-rt-type-badge dwa-rt-type-fixed">Fixed</span>';
            }

            var ssaCellHtml = comp.ssaAmount > 0
                ? '<span class="dwa-rt-ssa-val">' + fmtINR(comp.ssaAmount) + '</span>'
                : '<span class="dwa-rt-na">\u2014</span>';

            var actualCellHtml;
            if (comp.kind === "fixed" || comp.isSpecial) {
                if (!comp.applicable) {
                    actualCellHtml = '<span class="dwa-rt-na">\u2014</span>';
                } else if (comp.isSpecial && Math.abs(comp.actualAmount - comp.ssaAmount) > 0.01) {
                    actualCellHtml = '<span class="dwa-rt-amt-val dwa-rt-amt-special">' + fmtINR(comp.actualAmount) + '</span>';
                } else {
                    actualCellHtml = comp.actualAmount > 0
                        ? '<span class="dwa-rt-amt-val">' + fmtINR(comp.actualAmount) + '</span>'
                        : '<span class="dwa-rt-na">\u2014</span>';
                }
            } else if (!comp.applicable) {
                actualCellHtml = '<span class="dwa-rt-na dwa-rt-zero">\u20b90.00</span>';
            } else {
                actualCellHtml = '<span class="dwa-rt-amt-val dwa-rt-amt-active">' + fmtINR(comp.actualAmount) + '</span>';
            }

            var diffHtml = "";
            if ((comp.kind === "pf" || comp.kind === "esic" || comp.isSpecial) && comp.ssaAmount > 0) {
                var diff = comp.actualAmount - comp.ssaAmount;
                if (Math.abs(diff) > 0.01) {
                    var sign = diff > 0 ? "+" : "";
                    var cls  = diff > 0 ? "dwa-rt-diff-up" : "dwa-rt-diff-dn";
                    diffHtml = '<span class="dwa-rt-diff ' + cls + '">' + sign + fmtINR(diff) + '</span>';
                } else if (comp.kind !== "fixed" || comp.isSpecial) {
                    diffHtml = '<span class="dwa-rt-diff dwa-rt-diff-eq">=</span>';
                }
            }

            var noteHtml = comp.note
                ? '<div class="dwa-rt-row-note">' + comp.note + '</div>'
                : '';

            var rowClass = !comp.applicable ? "dwa-rt-row-na" : "";

            return '<tr class="' + rowClass + '">' +
                '<td class="dwa-rt-td dwa-rt-name">' +
                    '<span class="dwa-rt-comp-abbr">' + escHtml(comp.abbr) + '</span> ' +
                    escHtml(comp.salary_component) +
                    noteHtml +
                '</td>' +
                '<td class="dwa-rt-td dwa-rt-status">' + typeBadge + '</td>' +
                '<td class="dwa-rt-td dwa-rt-ssa-col">' + ssaCellHtml + '</td>' +
                '<td class="dwa-rt-td dwa-rt-actual-col">' + actualCellHtml + diffHtml + '</td>' +
                '<td class="dwa-rt-td dwa-rt-note-col">' +
                    (comp.kind !== "fixed" || comp.isSpecial
                        ? '<span class="dwa-rt-basis-text">' + comp.basis +
                          (comp.rateLabel && comp.kind !== "fixed" ? ' @ ' + comp.rateLabel : '') +
                          '</span>'
                        : '') +
                '</td>' +
            '</tr>';
        }).join("");

        rtTfoot.innerHTML =
            '<tr class="dwa-rt-total-row">' +
                '<td class="dwa-rt-td dwa-rt-total-lbl" colspan="2">Gross Payable</td>' +
                '<td class="dwa-rt-td dwa-rt-ssa-col dwa-rt-total-val">' + fmtINR(gross) + '</td>' +
                '<td class="dwa-rt-td dwa-rt-actual-col dwa-rt-total-val">' + fmtINR(gross) + '</td>' +
                '<td class="dwa-rt-td"></td>' +
            '</tr>' +
            '<tr class="dwa-rt-deductions-row">' +
                '<td class="dwa-rt-td dwa-rt-total-lbl" colspan="2">Total Deductions</td>' +
                '<td class="dwa-rt-td dwa-rt-ssa-col dwa-rt-ded-val">&minus;' + fmtINR(d.totalSsa) + '</td>' +
                '<td class="dwa-rt-td dwa-rt-actual-col dwa-rt-ded-val">&minus;' + fmtINR(d.totalActual) + '</td>' +
                '<td class="dwa-rt-td"></td>' +
            '</tr>' +
            '<tr class="dwa-rt-net-row">' +
                '<td class="dwa-rt-td dwa-rt-total-lbl" colspan="2">Net Payable</td>' +
                '<td class="dwa-rt-td dwa-rt-ssa-col dwa-rt-net-val">' + fmtINR(d.netSsa) + '</td>' +
                '<td class="dwa-rt-td dwa-rt-actual-col dwa-rt-net-val dwa-rt-net-highlight">' + fmtINR(d.netActual) + '</td>' +
                '<td class="dwa-rt-td"></td>' +
            '</tr>';

        rtNetCards.style.display = "flex";
        rtNetRuntime.innerHTML = fmtINR(d.netActual);
        rtNetSsa.innerHTML     = fmtINR(d.netSsa);
    }

    // ════════════════════════════════════════════════════════════════════════
    //  LOAD ATTENDANCE
    // ════════════════════════════════════════════════════════════════════════
    loadBtn.addEventListener("click", loadAttendance);
    yearSel.addEventListener("change", loadAttendance);
    monthSel.addEventListener("change", loadAttendance);

    function loadAttendance() {
        var company = companySel.value || "\u2014";
        var year    = yearSel.value;
        var month   = monthSel.value;
        if (!year || month === "") { frappe.show_alert({ message: "Please select Year and Month.", indicator: "orange" }); return; }

        var monthNum  = parseInt(month) + 1;
        var lastDay   = new Date(parseInt(year), parseInt(month) + 1, 0).getDate();
        var startDate = year + "-" + String(monthNum).padStart(2, "0") + "-01";
        var endDate   = year + "-" + String(monthNum).padStart(2, "0") + "-" + String(lastDay).padStart(2, "0");

        currentMonthName = MONTH_NAMES[parseInt(month)] || "";

        tableScroll.style.display = "none"; loadingTable.style.display = "flex";
        emptyEl.style.display = "none"; summaryBar.style.display = "none";
        bulkBar.style.display = "none"; slipBanner.style.display = "none";
        sandwichBanner.style.display = "none";
        runtimePanel.style.display = "none";

        clearInfoPanel();

        attendanceData = {}; originalData = {}; otDecimalData = {}; remarksData = {};
        dirtyDates.clear();
        holidayDates = {}; dailyRateMap = {}; joiningDate = null; leftDate = null;
        sandwichEligible = {}; sandwichUnpaid = {}; ssaDeductions = []; ssaTotalDed = 0; ssaBase = 0;
        specialMonthlyAmounts = {};

        rtGrossOverride = null;
        if (rtGrossInput) rtGrossInput.value = "";

        if (companySel.value) {
            loadCompanyPfWageLimit(companySel.value);
        }

        var employee = employeeSel.value;
        var loadFlags = { holidays: false, joining: false, adr: false };

        function checkAllDone() {
            if (loadFlags.holidays && loadFlags.joining && loadFlags.adr) {
                finaliseLoad();
            }
        }

        function finaliseLoad() {
            recomputeSandwich();

            tbody.querySelectorAll("tr[data-date]").forEach(function (row) {
                var dk = row.getAttribute("data-date");

                var oi = row.querySelector(".dwa-hours-input");
                if (oi) {
                    var dec = otDecimalData[dk] || 0;
                    oi.value = dec > 0 ? String(dec) : "";
                }

                var rc = row.querySelector(".dwa-rate-cell");
                if (rc) {
                    var r = dailyRateMap[dk] || 0;
                    rc.textContent = r ? "\u20b9" + parseFloat(r).toFixed(2) : "\u2014";
                }

                var rmk = row.querySelector(".dwa-remarks-input");
                if (rmk) rmk.value = remarksData[dk] || "";

                refreshRowVisuals(dk);
                refreshRowAmount(dk);
            });

            updateSummary();
        }

        renderTable(startDate, endDate);

        if (!employee) return;

        loadSsaDeductions(employee, startDate);

        frappe.call({
            method: "saral_hr.saral_hr.page.mark_attendance.mark_attendance.get_holidays_between_dates",
            args: { company: company, start_date: startDate, end_date: endDate },
            callback: function (hr) {
                holidayDates = {};
                (hr.message || []).forEach(function (h) { holidayDates[h] = true; });
                Object.keys(holidayDates).forEach(function (dk) {
                    if (attendanceData[dk] && attendanceData[dk].mode === "full" && !attendanceData[dk].status) {
                        attendanceData[dk] = { mode: "full", status: "Holiday" };
                    }
                });
                loadFlags.holidays = true;
                checkAllDone();
            },
            error: function () { loadFlags.holidays = true; checkAllDone(); }
        });

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
                loadFlags.joining = true;
                checkAllDone();
            },
            error: function () { loadFlags.joining = true; checkAllDone(); }
        });

        frappe.call({
            method: "saral_hr.saral_hr.page.daily_wage_attendance.daily_wage_attendance.get_daily_wage_data",
            args: { employee: employee, start_date: startDate, end_date: endDate },
            callback: function (dr) {
                var dData = dr.message || {};
                dailyRateMap = dData.daily_rates || {};
                var adrRecords = dData.adr_records || {};

                if (!Object.keys(dailyRateMap).length) {
                    _infoFlags.noRate = true;
                    renderInfoPanel();
                }

                Object.keys(adrRecords).forEach(function (dk) {
                    var adr = adrRecords[dk];
                    var rec = adr.status === "Half Day"
                        ? { mode: "half" }
                        : { mode: "full", status: adr.status || "" };
                    attendanceData[dk] = rec;
                    originalData[dk]   = JSON.parse(JSON.stringify(rec));
                    if (adr.ot_hours) {
                        otDecimalData[dk] = parseFloat(adr.ot_hours) || 0;
                    }
                    if (adr.remarks) {
                        remarksData[dk] = adr.remarks;
                    }
                });

                loadFlags.adr = true;
                checkAllDone();
            },
            error: function () { loadFlags.adr = true; checkAllDone(); }
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
        var rate    = parseFloat(dailyRateMap[dk] || 0);
        var otDec   = otDecimalData[dk] || 0;
        var rec     = attendanceData[dk] || {};
        var base    = 0;
        if (rec.mode === "full") {
            var s = rec.status || "";
            if (s === "Present" || s === "On Tour") base = rate;
            else if (s === "Holiday" && sandwichEligible[dk]) base = rate;
        } else if (rec.mode === "half") {
            base = rate / 2;
        }
        var ot = (rate > 0 ? rate / 8 : 0) * otDec;
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
        emptyEl.style.display = "none";
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

        // ── OT Hours — decimal input (4, 4.5, 7.5 …) ───────────────────
        var hoursTd = document.createElement("td");
        hoursTd.className = "dwa-td dwa-hours-cell";
        var hoursInput = document.createElement("input");
        hoursInput.type = "text"; hoursInput.className = "dwa-hours-input";
        hoursInput.placeholder = "0"; hoursInput.maxLength = 6;
        var savedDec = otDecimalData[dk] || 0;
        hoursInput.value = savedDec > 0 ? String(savedDec) : "";
        if (cellsDisabled) { hoursInput.disabled = true; hoursInput.style.opacity = "0.4"; }
        hoursInput.addEventListener("blur", function () {
            var dec = parseOtDecimal(this.value);
            otDecimalData[dk] = dec;
            this.value = dec > 0 ? String(dec) : "";
            markDirty(dk); refreshRowAmount(dk); updateSummary();
        });
        hoursInput.addEventListener("keypress", function (e) { if (!/[\d.]/.test(e.key)) e.preventDefault(); });
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

        // ── Remarks ──────────────────────────────────────────────────────
        var rmkTd = document.createElement("td");
        rmkTd.className = "dwa-td dwa-remarks-cell";
        var rmkInput = document.createElement("input");
        rmkInput.type = "text"; rmkInput.className = "dwa-remarks-input";
        rmkInput.placeholder = "Note…"; rmkInput.maxLength = 140;
        rmkInput.value = remarksData[dk] || "";
        if (cellsDisabled) { rmkInput.disabled = true; rmkInput.style.opacity = "0.4"; }
        rmkInput.addEventListener("blur", function () {
            remarksData[dk] = this.value.trim();
            markDirty(dk);
        });
        rmkTd.appendChild(rmkInput); row.appendChild(rmkTd);

        return row;
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
            var dl = dateTd.textContent.replace(/\s*\uD83E\uDD6A\s*/, "").trim();
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
        var totalOtDec = 0, totalBase = 0, totalOtPay = 0;

        tbody.querySelectorAll("tr[data-date]").forEach(function (row) {
            if (row.classList.contains("dwa-future-row")) return;
            cnt.total++;
            var dk   = row.getAttribute("data-date");
            var rec  = attendanceData[dk] || {};
            var rate = parseFloat(dailyRateMap[dk] || 0);
            var otD  = otDecimalData[dk] || 0;
            totalOtDec += otD;
            if (rate > 0 && otD > 0) totalOtPay += (rate / 8) * otD;

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
        // OT Hours summary shows decimal (e.g. "12.50")
        document.getElementById("dwa_cnt_hours").textContent    = totalOtDec > 0 ? totalOtDec.toFixed(2) : "0.00";
        document.getElementById("dwa_cnt_basepay").textContent   = fmtINR(totalBase);
        document.getElementById("dwa_cnt_otpayable").textContent = fmtINR(totalOtPay);
        document.getElementById("dwa_cnt_payable").textContent   = fmtINR(totalPay);

        tbody.querySelectorAll("tr[data-date]").forEach(function (r) { refreshRowAmount(r.getAttribute("data-date")); });
        renderRuntimePanel();
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
        sandwichBanner.style.display = "none";
        runtimePanel.style.display = "none";
        attendanceData = {}; originalData = {}; otDecimalData = {}; remarksData = {};
        dirtyDates.clear();
        holidayDates = {}; dailyRateMap = {}; joiningDate = null; leftDate = null;
        sandwichEligible = {}; sandwichUnpaid = {}; ssaDeductions = []; ssaTotalDed = 0; ssaBase = 0;
        specialMonthlyAmounts = {}; currentMonthName = "";
        runtimeOpen = false; runtimeBodyWrap.style.display = "none"; runtimeIcon.innerHTML = "&#9654;";
        rtGrossOverride = null;
        if (rtGrossInput) rtGrossInput.value = "";
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
                employee:        employee,
                attendance_date: dk,
                ot_hours:        otDecimalData[dk] || 0,   // decimal float
                daily_rate:      dailyRateMap[dk] || 0,
                remarks:         remarksData[dk] || "",
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
                isSaving = false; saveBtn.textContent = "Save Attendance";
                if (r.message && r.message.success) {
                    frappe.show_alert({ message: (r.message.saved_count || records.length) + " record(s) saved.", indicator: "green" });
                    setTimeout(loadAttendance, 400);
                } else {
                    frappe.show_alert({ message: (r.message && r.message.error) || "Error saving.", indicator: "red" });
                }
            },
            error: function () { isSaving = false; saveBtn.textContent = "Save Attendance"; frappe.show_alert({ message: "Error saving.", indicator: "red" }); }
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

        /* ── Summary bar ─────────────────────────────────────────────── */
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

        /* ── Runtime Salary Panel ────────────────────────────────────── */
        .dwa-runtime-panel { border:1px solid #c7d2fe; border-radius:8px; margin:8px 0 0; overflow:hidden; background:#fafbff; }
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
        .dwa-runtime-toggle { background:linear-gradient(90deg,#eef2ff,#f5f3ff) !important; }
        .dwa-runtime-toggle:hover { background:linear-gradient(90deg,#e0e7ff,#ede9fe) !important; }
        .dwa-runtime-sub-label { font-size:11px; color:#6366f1; margin-left:4px; font-weight:500; }

        .dwa-rt-override-bar { display:flex; gap:16px; flex-wrap:wrap; align-items:center; padding:12px 16px 8px; border-bottom:1px dashed #c7d2fe; background:#f5f3ff; }
        .dwa-rt-override-group { display:flex; align-items:center; gap:6px; }
        .dwa-rt-ovr-label { font-size:11px; font-weight:600; color:#6366f1; white-space:nowrap; text-transform:uppercase; letter-spacing:0.04em; }
        .dwa-rt-ovr-input { width:130px; height:28px; border:1px solid #a5b4fc; border-radius:4px; padding:0 8px; font-size:13px; background:#fff; color:var(--text-color); box-sizing:border-box; }
        .dwa-rt-ovr-input:focus { outline:none; border-color:#6366f1; box-shadow:0 0 0 2px rgba(99,102,241,0.15); }
        .dwa-rt-ovr-reset { background:none; border:1px solid #a5b4fc; border-radius:4px; width:26px; height:28px; cursor:pointer; color:#6366f1; font-size:14px; display:flex; align-items:center; justify-content:center; transition:background 0.12s; }
        .dwa-rt-ovr-reset:hover { background:#e0e7ff; }
        .dwa-rt-pf-limit-info { display:flex; align-items:center; }
        .dwa-pf-limit-badge { font-size:11.5px; font-weight:500; color:#7c3aed; background:#ede9fe; border:1px solid #c4b5fd; border-radius:20px; padding:3px 12px; white-space:nowrap; }
        .dwa-pf-limit-badge strong { font-weight:700; }

        .dwa-rt-note { display:flex; align-items:flex-start; gap:6px; padding:8px 16px; font-size:11.5px; color:#4338ca; background:#eef2ff; border-bottom:1px solid #c7d2fe; }
        .dwa-rt-note-icon { font-size:13px; flex-shrink:0; margin-top:1px; }
        .dwa-rt-note strong { font-weight:700; }

        .dwa-rt-table-wrap { overflow-x:auto; padding:12px 16px 0; }
        .dwa-rt-table { width:100%; border-collapse:collapse; font-size:12px; }
        .dwa-rt-table thead tr { background:#eef2ff; }
        .dwa-rt-table th { padding:8px 10px; text-align:left; font-size:10.5px; font-weight:700; color:#4338ca; text-transform:uppercase; letter-spacing:0.05em; border-bottom:2px solid #c7d2fe; }
        .dwa-rt-th-comp   { min-width:160px; }
        .dwa-rt-th-type   { min-width:70px; text-align:center; }
        .dwa-rt-th-ssa    { min-width:110px; text-align:right; background:#fff8e1; color:#92400e !important; border-left:2px solid #fcd34d; }
        .dwa-rt-th-actual { min-width:130px; text-align:right; background:#f0fdf4; color:#15803d !important; border-left:2px solid #86efac; }
        .dwa-rt-th-note   { min-width:140px; color:#6366f1 !important; }
        .dwa-rt-td { padding:8px 10px; border-bottom:1px solid #e8eaff; vertical-align:middle; }
        .dwa-rt-name { font-weight:600; color:var(--text-color); }
        .dwa-rt-comp-abbr { display:inline-block; font-size:10px; font-weight:700; color:#6366f1; background:rgba(99,102,241,0.1); border-radius:3px; padding:1px 5px; margin-right:3px; vertical-align:middle; }
        .dwa-rt-status { text-align:center; }
        .dwa-rt-row-na .dwa-rt-td { opacity:0.6; }
        .dwa-rt-row-note { font-size:10.5px; color:#818cf8; font-weight:400; margin-top:2px; }
        .dwa-rt-ssa-col { text-align:right; background:#fffbeb; border-left:2px solid #fde68a; }
        .dwa-rt-ssa-val { font-size:13px; font-weight:600; color:#92400e; }
        .dwa-rt-actual-col { text-align:right; background:#f0fdf4; border-left:2px solid #bbf7d0; }
        .dwa-rt-amt-val { font-size:13px; font-weight:600; color:var(--text-muted); }
        .dwa-rt-amt-active  { color:#c0392b !important; font-weight:700 !important; }
        .dwa-rt-amt-special { color:#7c3aed !important; font-weight:700 !important; }
        .dwa-rt-zero { font-size:13px; font-weight:700; color:#6366f1; }
        .dwa-rt-na   { font-size:12px; color:#94a3b8; }
        .dwa-rt-diff { font-size:10px; font-weight:700; margin-left:4px; padding:1px 5px; border-radius:10px; }
        .dwa-rt-diff-up { background:#fef2f2; color:#c0392b; }
        .dwa-rt-diff-dn { background:#f0fdf4; color:#16a34a; }
        .dwa-rt-diff-eq { background:#f1f5f9; color:#94a3b8; }
        .dwa-rt-note-col { }
        .dwa-rt-basis-text { font-size:11px; color:var(--text-muted); }
        .dwa-rt-type-badge { font-size:10px; font-weight:700; padding:2px 7px; border-radius:20px; letter-spacing:0.02em; }
        .dwa-rt-type-calc    { background:#ede9fe; color:#7c3aed; border:1px solid #c4b5fd; }
        .dwa-rt-type-fixed   { background:#f0f9ff; color:#0369a1; border:1px solid #bae6fd; }
        .dwa-rt-type-special { background:#fdf4ff; color:#a21caf; border:1px solid #e879f9; }
        .dwa-rt-total-row .dwa-rt-td, .dwa-rt-deductions-row .dwa-rt-td, .dwa-rt-net-row .dwa-rt-td { border-top:2px solid #c7d2fe; }
        .dwa-rt-total-lbl { font-size:12px; font-weight:600; color:var(--text-muted); }
        .dwa-rt-total-val { font-size:13px; font-weight:700; color:var(--text-color); }
        .dwa-rt-ded-val   { font-size:13px; font-weight:700; color:#c0392b; }
        .dwa-rt-net-val   { font-size:14px; font-weight:700; color:#16a34a; }
        .dwa-rt-net-highlight { font-size:16px !important; background:#dcfce7 !important; }
        .dwa-rt-deductions-row .dwa-rt-ssa-col  { background:#fff3cd; }
        .dwa-rt-deductions-row .dwa-rt-actual-col { background:#fef2f2; }
        .dwa-rt-net-row .dwa-rt-ssa-col   { background:#fef9c3; }
        .dwa-rt-net-row .dwa-rt-actual-col { background:#dcfce7; }
        .dwa-rt-total-row .dwa-rt-ssa-col, .dwa-rt-total-row .dwa-rt-actual-col { background:#f1f5f9; color:var(--text-color); font-weight:600; }
        .dwa-rt-net-cards { display:flex; gap:12px; padding:12px 16px 16px; flex-wrap:wrap; }
        .dwa-rt-net-card { flex:1; min-width:200px; border-radius:10px; padding:14px 18px; display:flex; flex-direction:column; gap:4px; }
        .dwa-rt-net-runtime { background:linear-gradient(135deg,#f0fdf4,#dcfce7); border:2px solid #86efac; }
        .dwa-rt-net-ssa { background:linear-gradient(135deg,#fffbeb,#fef3c7); border:2px solid #fcd34d; }
        .dwa-rt-net-lbl { font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:0.06em; color:var(--text-muted); }
        .dwa-rt-net-val { font-size:22px; font-weight:800; color:#16a34a; line-height:1.1; }
        .dwa-rt-net-ssa .dwa-rt-net-val { color:#92400e; }
        .dwa-rt-net-sub { font-size:10.5px; color:var(--text-muted); margin-top:2px; }

        /* ── Sandwich banner ─────────────────────────────────────────── */
        .dwa-sandwich-banner { display:flex; gap:12px; align-items:flex-start; background:#fff8f0; border:1px solid #f59e0b; border-left:4px solid #f59e0b; border-radius:6px; padding:12px 16px; margin:10px 0 0; }
        .dwa-sw-icon { font-size:18px; flex-shrink:0; margin-top:1px; }
        .dwa-sw-content { display:flex; flex-direction:column; gap:4px; }
        .dwa-sw-title { font-size:13px; font-weight:600; color:#92400e; }
        .dwa-sw-sub   { font-size:12px; color:#a16207; line-height:1.5; }
        .dwa-sw-dates { display:flex; flex-wrap:wrap; gap:6px; margin-top:6px; }
        .dwa-sw-date-chip { background:#fef3c7; border:1px solid #fcd34d; border-radius:4px; padding:3px 8px; font-size:11px; font-weight:500; color:#92400e; }

        /* ── Bulk bar ────────────────────────────────────────────────── */
        .dwa-bulk-bar { display:flex; align-items:center; gap:8px; padding:8px 0; flex-wrap:wrap; border-bottom:1px solid var(--border-color,#e5e7eb); }
        .dwa-bulk-label { font-size:12px; color:var(--text-muted); font-weight:500; margin-right:4px; }
        .dwa-pill-btn { border:none; border-radius:20px; padding:4px 14px; font-size:12px; font-weight:600; cursor:pointer; transition:opacity 0.15s; color:#fff; }
        .dwa-pill-present { background:#28a745; } .dwa-pill-absent { background:#e74c3c; }
        .dwa-pill-btn:hover { opacity:0.85; }

        /* ── Loading ─────────────────────────────────────────────────── */
        .dwa-loading { display:flex; align-items:center; justify-content:center; gap:12px; padding:48px 0; }
        .dwa-spinner { width:28px; height:28px; border:3px solid var(--border-color,#e5e7eb); border-top-color:var(--primary); border-radius:50%; animation:dwa-spin 0.7s linear infinite; }
        @keyframes dwa-spin { to { transform:rotate(360deg); } }
        .dwa-loading-text { font-size:13px; color:var(--text-muted); }

        /* ── Table ───────────────────────────────────────────────────── */
        .dwa-table-scroll { overflow-x:auto; border-top:1px solid var(--border-color,#e5e7eb); }
        .dwa-table { width:100%; border-collapse:collapse; font-size:12px; }
        .dwa-th { background:var(--control-bg,#f7f7f7); border:1px solid var(--border-color,#d1d8dd); padding:8px; font-size:11px; font-weight:600; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.04em; white-space:nowrap; position:sticky; top:0; z-index:10; text-align:center; }
        .dwa-th-date   { text-align:left; min-width:150px; }
        .dwa-th-day    { text-align:left; min-width:90px; }
        .dwa-th-status { min-width:64px; }
        .dwa-th-hours  { min-width:80px; }
        .dwa-th-rate   { min-width:100px; }
        .dwa-th-rowamt { min-width:130px; }
        .dwa-th-remarks { min-width:180px; text-align:left; }
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
        .dwa-hours-input { width:64px; border:1px solid var(--border-color,#d1d8dd); border-radius:4px; padding:3px 6px; font-size:13px; text-align:center; background:var(--card-bg,#fff); color:var(--text-color); box-sizing:border-box; font-variant-numeric:tabular-nums; }
        .dwa-hours-input:focus { outline:none; border-color:var(--primary); box-shadow:0 0 0 2px rgba(45,108,223,0.10); }
        .dwa-hours-input::placeholder { color:#b0b8c4; }
        .dwa-rate-cell   { text-align:right; font-size:12px; font-weight:600; color:#0ea5e9; white-space:nowrap; }
        .dwa-rowamt-cell { text-align:right; font-size:12px; font-weight:500; color:var(--text-muted); white-space:nowrap; }
        .dwa-rowamt-cell.dwa-rowamt-has { color:#16a34a; font-weight:600; }
        .dwa-ot-extra    { font-size:11px; color:#b45309; font-weight:500; }

        /* ── Remarks ─────────────────────────────────────────────────── */
        .dwa-remarks-cell { }
        .dwa-remarks-input { width:100%; min-width:160px; border:1px solid var(--border-color,#d1d8dd); border-radius:4px; padding:3px 7px; font-size:12px; background:var(--card-bg,#fff); color:var(--text-color); box-sizing:border-box; }
        .dwa-remarks-input:focus { outline:none; border-color:var(--primary); box-shadow:0 0 0 2px rgba(45,108,223,0.10); }
        .dwa-remarks-input::placeholder { color:#b0b8c4; }

        /* ── Empty ───────────────────────────────────────────────────── */
        .dwa-empty { display:flex; flex-direction:column; align-items:center; justify-content:center; padding:64px 0; gap:10px; }
        .dwa-empty-icon  { font-size:40px; }
        .dwa-empty-title { font-size:16px; font-weight:600; color:var(--text-color); }
        .dwa-empty-sub   { font-size:13px; color:var(--text-muted); }

        .page-head-content { padding:8px 17px 0 0 !important; }
    `;
    document.head.appendChild(style);
}