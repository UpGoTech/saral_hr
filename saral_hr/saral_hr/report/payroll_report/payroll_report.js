frappe.query_reports["Payroll Report"] = {
    filters: [
        {
            fieldname: "company",
            label:     __("Company"),
            fieldtype: "Link",
            options:   "Company",
            reqd:      1,
        },
        {
            fieldname: "year",
            label:     __("Year"),
            fieldtype: "Select",
            reqd:      1,
            default:   String(new Date().getFullYear()),
            options:   (function () {
                const y = new Date().getFullYear(), opts = [""];
                for (let i = y - 2; i <= y + 2; i++) opts.push(String(i));
                return opts;
            })(),
        },
        {
            fieldname: "month",
            label:     __("Month"),
            fieldtype: "Select",
            reqd:      1,
            default:   "",
            options:   ["","January","February","March","April","May","June",
                        "July","August","September","October","November","December"],
        },
        { fieldname: "report_mode", label: __("Report"), fieldtype: "Data", hidden: 1, default: "salary_summary" },
        { fieldname: "category",    label: __("Category"), fieldtype: "Link", options: "Category", default: "" },
        {
            fieldname: "division",
            label:     __("Division"),
            fieldtype: "MultiSelectList",
            get_data:  txt => frappe.db.get_link_options("Division", txt),
        },
    ],

    onload(report) {
        function _live_filters() {
            const vals = {};
            (report.filters || []).forEach(f => {
                try { vals[f.df.fieldname] = f.get_value(); } catch(e) {}
            });
            return vals;
        }

        function _filters_filled(f) {
            f = f || _live_filters();
            return !!(f.company && f.year && f.month);
        }

        report._live_filters   = _live_filters;
        report._filters_filled = _filters_filled;

        const _originalRefresh = report.refresh.bind(report);
        report.refresh = function () {
            setTimeout(() => {
                if (!_filters_filled()) {
                    report.page.wrapper.find(".report-wrapper").html(
                        `<div style="text-align:center;padding:40px;color:#888;font-size:13px;">
                            Please select <strong>Company</strong>, <strong>Year</strong>, and
                            <strong>Month</strong> to load the report.
                        </div>`
                    );
                    return;
                }
                _originalRefresh();
            }, 0);
        };

        const observer = new MutationObserver(() => _hide_total_serials());
        observer.observe(document.body, { childList: true, subtree: true, characterData: true });

        frappe.after_ajax(() => {
            _inject_nav(report);
            if (!report.page.wrapper.find(".pr-split-pdf").length) {
                _set_action_buttons(report);
            }
        });

        const _patchLegend = () => {
            const qr = frappe.query_report;
            if (!qr || qr.__pr_legend_patched) return;
            qr.__pr_legend_patched = true;

            const _origRender = qr.render_report?.bind(qr);
            if (_origRender) {
                qr.render_report = function(...args) {
                    const result = _origRender(...args);
                    setTimeout(() => _maybe_inject_legend(report), 300);
                    return result;
                };
            }
            $(qr).on("after_refresh.pr_legend", () => {
                setTimeout(() => _maybe_inject_legend(report), 300);
            });
        };

        _patchLegend();
        setTimeout(_patchLegend, 1000);
    },

    formatter(value, row, column, data, default_formatter) {
        if (!data) return default_formatter(value, row, column, data);
        const mode = frappe.query_report.get_filter_value("report_mode");
        const fn   = column.fieldname, rt = data._row_type;
        const def  = v => default_formatter(v, row, column, data);
        const bold = v => `<strong>${def(v)}</strong>`;

        if (mode === "professional_tax" && rt === "total")
            return fn === "pt_rate" ? "" : bold(value);

        if (mode === "provident_fund" && rt === "total")
            return ["pf_no","uan_no","days","absent","date_of_joining","date_of_birth"].includes(fn) ? "" : bold(value);

        if (mode === "salary_summary") {
            if (fn === "spacer" || fn === "spacer2") return "";
            if (rt === "grand_total") return bold(value);
            if ((fn === "amount" || fn === "ded_amount" || fn === "oth_amount") && (value === null || value === undefined || value === "")) return "";
        }

        if ((mode === "home_bank_advice" || mode === "other_bank_advice") && data.bold) {
            if (fn === "net_salary" || fn === "employee_name") return bold(value);
            return "";
        }

        if (mode === "esi_register" && data.bold)
            return ["esic_number","days_paid","date_of_joining","date_of_birth"].includes(fn) ? "" : bold(value);

        if (mode === "retention_deposit" && data.bold)
            return ["date_of_joining","ded_upto"].includes(fn) ? "" : bold(value);

        if (mode === "variable_pay" && data.bold)
            return ["division","variable_pay_percentage"].includes(fn) ? "" : bold(value);

        if ((mode === "home_bank_advice" || mode === "other_bank_advice") && value === "On Hold" && fn === "net_salary")
            return `<span style="color:#c0392b;font-style:italic;">On Hold</span>`;

        if (mode === "monthly_attendance" && fn && fn.startsWith("day_")) {
            if (!value || value === "-") return '<span style="color:#ccc;">-</span>';
            const colors = {
                P:"#1a6b1a", A:"#c0392b", HD:"#e67e22", T:"#2c3e50",
                H:"#27ae60", WO:"#2980b9", LWP:"#8e44ad", EL:"#d35400",
                CL:"#16a085", CO:"#7f8c8d", ECO:"#a93226",
            };
            const color = colors[value] || "#1a202c";
            return `<span style="font-weight:700;color:${color};">${value}</span>`;
        }

        return data.bold ? bold(value) : def(value);
    }
};

// ── Legend ────────────────────────────────────────────────────────────────────

const _MAR_LEGEND = [
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

function _build_legend_bar() {
    const items = _MAR_LEGEND.map(({ code, label, color }) =>
        `<span style="display:inline-flex;align-items:center;gap:4px;
                      margin-right:12px;margin-bottom:2px;white-space:nowrap;">
            <span style="font-weight:700;font-size:12px;color:${color};">${code}</span>
            <span style="font-size:12px;color:#444;">– ${label}</span>
        </span>`
    ).join("");
    return `
        <div id="mar-legend-bar" style="
            display:flex;flex-wrap:wrap;align-items:center;
            padding:7px 12px;margin:0 0 8px 0;
            background:#f4f5f6;border:1px solid #d1d8dd;
            border-radius:6px;font-family:inherit;">
            <span style="font-weight:600;font-size:12px;color:#6c7680;
                         margin-right:12px;white-space:nowrap;">Legend :</span>
            ${items}
        </div>`;
}

function _maybe_inject_legend(report) {
    const mode = frappe.query_report.get_filter_value
        ? frappe.query_report.get_filter_value("report_mode")
        : "";
    const $w = report.page.wrapper;
    $w.find("#mar-legend-bar").remove();
    if (mode !== "monthly_attendance") return;
    const bar = _build_legend_bar();
    const $dt = $w.find(".dt-wrapper, .frappe-datatable").first();
    $dt.length ? $dt.before(bar) : $w.find(".report-wrapper").prepend(bar);
}

// ── Hide serial on bold/total rows ────────────────────────────────────────────

function _hide_total_serials() {
    document.querySelectorAll(".dt-row").forEach(row => {
        if (!row.querySelector("strong")) return;
        const srCell = row.querySelector('[data-col-index="0"] .dt-cell__content');
        if (srCell && srCell.textContent.trim() !== "") srCell.textContent = "";
    });
}

// ── Report list ───────────────────────────────────────────────────────────────

const REPORTS = [
    { key:"salary_summary",            label:"Salary Summary"            },
    { key:"transaction_checklist",     label:"Transaction Checklist"     },
    { key:"salary_summary_individual", label:"Salary Summary Individual" },
    { key:"provident_fund",            label:"Provident Fund Register"   },
    { key:"esi_register",              label:"ESI Register"              },
    { key:"professional_tax",          label:"Professional Tax Register" },
    { key:"retention_deposit",         label:"Retention Deposit"         },
    { key:"educational_allowance",     label:"Educational Allowance"     },
    { key:"variable_pay",              label:"Variable Pay Register"     },
    { key:"labour_welfare_fund",       label:"Labour Welfare Fund"       },
    { key:"other_bank_advice",         label:"Other Bank Advice"         },
    { key:"home_bank_advice",          label:"Home Bank Advice"          },
    { key:"monthly_attendance",        label:"Monthly Attendance"        },
    { key:"income_tax",                label:"Income Tax"                },
    { key:"loan_register",             label:"Loan Register"             },
    { key:"advance_register",          label:"Advance Register"          },
];

// ── State ─────────────────────────────────────────────────────────────────────
// _prefetch_gen: increments on every filter change so stale callbacks self-discard
// _action_gen:   increments on every Print/Export click so duplicate clicks are ignored

let _idx            = 0;
let _cache          = {};
let _debounce_timer = null;
let _prefetch_xhr   = null;
let _loading_key    = null;
let _prefetch_gen   = 0;      // FIX: generation counter for stale prefetch results
let _action_gen     = 0;      // FIX: generation counter for debouncing action buttons
let _action_timer   = null;   // FIX: timer for action button debounce

// ── Filter helpers ────────────────────────────────────────────────────────────

function _filter_key(report) {
    const f = report._live_filters ? report._live_filters() : (frappe.query_report.get_values() || {});
    return JSON.stringify([f.year, f.month, f.company || "", f.category || "", JSON.stringify(f.division || [])]);
}

function _validate(report) {
    const f = report._live_filters ? report._live_filters() : (frappe.query_report.get_values() || {});
    if (!f.company) {
        frappe.msgprint({ title:__("Missing Filters"), message:__("Please select a Company."), indicator:"orange" });
        return false;
    }
    if (!f.year) {
        frappe.msgprint({ title:__("Missing Filters"), message:__("Please select a Year."), indicator:"orange" });
        return false;
    }
    if (!f.month) {
        frappe.msgprint({ title:__("Missing Filters"), message:__("Please select a Month."), indicator:"orange" });
        return false;
    }
    return true;
}

// ── Styles ────────────────────────────────────────────────────────────────────

function _ensure_styles() {
    if (document.getElementById("pr-style")) return;
    const s = document.createElement("style");
    s.id = "pr-style";
    s.textContent = `
        .pr-nav-bar {
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 6px;
            padding: 10px 16px;
            background: var(--card-bg, #fff);
            border-top: 1px solid var(--border-color, #e2e8f0);
            border-bottom: 1px solid var(--border-color, #e2e8f0);
        }
        .pr-tab-btn {
            height: 32px;
            padding: 0 14px;
            font-size: 12.5px;
            font-weight: 500;
            color: var(--text-color, #374151);
            background: var(--control-bg, #f8fafc);
            border: 1.5px solid var(--border-color, #e2e8f0);
            border-radius: 6px;
            cursor: pointer;
            white-space: nowrap;
            transition: all .15s ease;
            outline: none;
            line-height: 1;
            font-family: inherit;
        }
        .pr-tab-btn:hover {
            border-color: var(--primary, #2563eb);
            color: var(--primary, #2563eb);
            background: #eff6ff;
        }
        .pr-tab-btn.active {
            background: var(--primary, #2563eb);
            border-color: var(--primary, #2563eb);
            color: #fff;
            font-weight: 600;
            box-shadow: 0 1px 4px rgba(37,99,235,.25);
        }
        .pr-on-hold-note {
            font-size: 11px;
            color: #c0392b;
            padding: 5px 16px;
            background: #fff5f5;
            border-bottom: 1px solid #fecaca;
            display: none;
        }

        /* ── Split button wrapper ── */
        .pr-split-wrap {
            display: inline-flex;
            align-items: stretch;
            border-radius: 6px;
            overflow: visible;
            margin-left: 6px;
            position: relative;
        }

        /* ── Main action part ── */
        .pr-split-main {
            height: 30px;
            padding: 0 12px;
            font-size: 12px;
            font-weight: 600;
            border: none;
            border-radius: 6px 0 0 6px;
            cursor: pointer;
            white-space: nowrap;
            font-family: inherit;
            display: inline-flex;
            align-items: center;
            gap: 5px;
            transition: filter .15s ease;
            outline: none;
        }
        .pr-split-main:hover { filter: brightness(0.93); }
        .pr-split-main:disabled,
        .pr-split-arrow:disabled {
            opacity: 0.55;
            cursor: not-allowed;
            filter: none;
        }

        /* ── Chevron toggle part ── */
        .pr-split-arrow {
            height: 30px;
            width: 26px;
            border: none;
            border-left: 1px solid rgba(255,255,255,0.35);
            border-radius: 0 6px 6px 0;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-family: inherit;
            transition: filter .15s ease;
            outline: none;
            flex-shrink: 0;
        }
        .pr-split-arrow:hover { filter: brightness(0.88); }

        /* PDF button — black */
        .pr-split-pdf .pr-split-main,
        .pr-split-pdf .pr-split-arrow {
            background: #000000;
            color: #fff;
        }

        /* Excel button — green */
        .pr-split-excel .pr-split-main,
        .pr-split-excel .pr-split-arrow {
            background: #26a354;
            color: #fff;
        }

        /* ── Dropdown menu ── */
        .pr-split-menu {
            display: none;
            position: absolute;
            top: calc(100% + 4px);
            right: 0;
            min-width: 180px;
            background: #fff;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            box-shadow: 0 8px 24px rgba(0,0,0,.12);
            z-index: 9999;
            overflow: hidden;
            padding: 4px 0;
        }
        .pr-split-menu.open { display: block; }

        .pr-split-menu-item {
            display: flex;
            align-items: center;
            gap: 9px;
            padding: 9px 14px;
            font-size: 12.5px;
            font-weight: 500;
            color: #1e293b;
            cursor: pointer;
            transition: background .1s ease;
            white-space: nowrap;
            font-family: inherit;
            border: none;
            background: none;
            width: 100%;
            text-align: left;
        }
        .pr-split-menu-item:hover { background: #f1f5f9; }
        .pr-split-menu-item .pr-menu-icon {
            width: 16px;
            height: 16px;
            flex-shrink: 0;
            opacity: 0.75;
        }
        .pr-split-menu-divider {
            height: 1px;
            background: #e2e8f0;
            margin: 3px 0;
        }
    `;
    document.head.appendChild(s);
}

// ── Nav bar ───────────────────────────────────────────────────────────────────

function _inject_nav(report) {
    if (report.page.wrapper.find(".pr-nav-bar").length) return;
    _ensure_styles();

    const buttons = REPORTS.map((r, i) =>
        `<button class="pr-tab-btn${i === _idx ? " active" : ""}" data-idx="${i}">${r.label}</button>`
    ).join("");

    const nav = $(`
        <div class="pr-nav-bar">${buttons}</div>
        <div class="pr-on-hold-note" id="pr-on-hold-note"></div>
    `);

    const targets = [".frappe-report-filters-section",".filter-section",".standard-filter-section",".page-form"];
    let inserted = false;
    for (const sel of targets) {
        const el = report.page.wrapper.find(sel).first();
        if (el.length) { el.after(nav); inserted = true; break; }
    }
    if (!inserted) report.page.wrapper.find(".report-wrapper").prepend(nav);

    nav.find(".pr-tab-btn").on("click", function () {
        _go(report, +$(this).data("idx"));
    });

    // FIX: cancel in-flight prefetch and reset generation counter on filter change
    report.page.wrapper.on("change.pr", ".frappe-control input, .frappe-control select", function () {
        _cache       = {};
        _loading_key = null;
        _prefetch_gen++;   // invalidate any in-flight prefetch callback

        if (_prefetch_xhr && typeof _prefetch_xhr.abort === "function") {
            _prefetch_xhr.abort();
        }
        _prefetch_xhr = null;

        clearTimeout(_debounce_timer);
        _debounce_timer = setTimeout(() => {
            if (!report._filters_filled()) return;
            _cache = {};   // clear again — filters may have changed mid-wait
            _prefetch_all(report);
        }, 1500);
    });

    // FIX: use .off() before .on() so re-injection never stacks listeners
    _bind_refresh_listener(report);

    $(frappe.query_report).one("after_refresh.pr_init", () => {
        _prefetch_all(report);
    });
}

// ── Tab sync ──────────────────────────────────────────────────────────────────

function _sync(report) {
    report.page.wrapper.find(".pr-tab-btn").each(function () {
        $(this).toggleClass("active", +$(this).data("idx") === _idx);
    });
    const label = REPORTS[_idx].label;
    report.page.wrapper.find(".title-text").text(label);
    document.title = label + " — Frappe";
}

function _go(report, idx) {
    if (!report._filters_filled || !report._filters_filled()) {
        frappe.msgprint({ title:__("Missing Filters"), message:__("Please select Company, Year and Month first."), indicator:"orange" });
        return;
    }

    _idx = idx;
    const modeKey = REPORTS[idx].key;
    _sync(report);
    frappe.query_report.set_filter_value("report_mode", modeKey);
    report.page.wrapper.find("#mar-legend-bar").remove();

    const fk     = _filter_key(report);
    const cached = _cache[fk]?.[modeKey];
    if (cached) {
        _render_cached(cached);
        _update_on_hold_note(cached.result);
        if (modeKey === "monthly_attendance") setTimeout(() => _maybe_inject_legend(report), 350);
        return;
    }

    _loading_key = `${fk}::${modeKey}`;
    frappe.query_report.refresh();
    if (modeKey === "monthly_attendance") setTimeout(() => _maybe_inject_legend(report), 1200);
}

function _render_cached(cached) {
    const qr = frappe.query_report;
    qr.columns = cached.columns;
    qr.data    = cached.result;
    try {
        qr.render_datatable();
    } catch (_) {
        try {
            if (qr.datatable) qr.datatable.refresh(cached.result, cached.columns);
            else qr.refresh();
        } catch (__) { qr.refresh(); }
    }
}

// FIX: always call .off() before .on() to prevent listener accumulation
// across multiple _inject_nav calls (e.g. route changes, Frappe re-renders)
function _bind_refresh_listener(report) {
    $(frappe.query_report).off("after_refresh.pr");
    $(frappe.query_report).on("after_refresh.pr", () => {
        const fk      = _filter_key(report);
        const modeKey = frappe.query_report.get_filter_value("report_mode");
        const thisKey = `${fk}::${modeKey}`;
        if (_loading_key && _loading_key !== thisKey) return;
        _loading_key = null;
        if (!_cache[fk]) _cache[fk] = {};
        _cache[fk][modeKey] = {
            columns: frappe.query_report.columns,
            result:  frappe.query_report.data,
        };
        _update_on_hold_note(frappe.query_report.data);
        setTimeout(() => _maybe_inject_legend(report), 300);
    });
}

// FIX: capture generation at call time; discard result if filters changed
// while the request was in flight
function _prefetch_all(report) {
    const fk      = _filter_key(report);
    const myGen   = ++_prefetch_gen;
    const f       = report._live_filters ? report._live_filters() : (frappe.query_report.get_values() || {});
    if (!f.company || !f.year || !f.month) return;

    _prefetch_xhr = frappe.call({
        method: "saral_hr.saral_hr.report.payroll_report.payroll_report.get_all_reports_data",
        args: {
            filters: JSON.stringify({
                year:     f.year     || "",
                month:    f.month    || "",
                company:  f.company  || "",
                category: f.category || "",
                division: JSON.stringify(f.division || []),
            })
        },
        callback(res) {
            _prefetch_xhr = null;
            // FIX: discard stale result if filters changed while in-flight
            if (myGen !== _prefetch_gen) return;
            if (!res.message) return;
            if (fk !== _filter_key(report)) return;
            if (!_cache[fk]) _cache[fk] = {};
            Object.assign(_cache[fk], res.message);
        },
        error() {
            _prefetch_xhr = null;
        }
    });
}

function _update_on_hold_note(data) {
    const note = $("#pr-on-hold-note");
    if (!note.length) return;
    const mode = frappe.query_report.get_filter_value("report_mode");
    if (mode !== "home_bank_advice" && mode !== "other_bank_advice") { note.hide().text(""); return; }
    const holdCount = (data || []).filter(r => r.net_salary === "On Hold").length;
    holdCount > 0
        ? note.text(`⚠ ${holdCount} employee${holdCount > 1 ? "s are" : " is"} On Hold and excluded from the total.`).show()
        : note.hide().text("");
}

function _server_filters(report) {
    const f = report && report._live_filters ? report._live_filters() : (frappe.query_report.get_values() || {});
    return {
        year:        f.year     || "",
        month:       f.month    || "",
        company:     f.company  || "",
        category:    f.category || "",
        division:    JSON.stringify(f.division || []),
        report_mode: frappe.query_report.get_filter_value("report_mode") || "salary_summary",
    };
}

// ── SVG icons ─────────────────────────────────────────────────────────────────

const _ICON_PDF = `<svg class="pr-menu-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"
    fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
    <polyline points="14 2 14 8 20 8"/>
    <line x1="16" y1="13" x2="8" y2="13"/>
    <line x1="16" y1="17" x2="8" y2="17"/>
    <polyline points="10 9 9 9 8 9"/>
</svg>`;

const _ICON_EXCEL = `<svg class="pr-menu-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"
    fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <rect x="2" y="3" width="20" height="18" rx="2"/>
    <line x1="8" y1="3" x2="8" y2="21"/>
    <line x1="2" y1="9" x2="22" y2="9"/>
    <line x1="2" y1="15" x2="22" y2="15"/>
</svg>`;

const _ICON_MULTI = `<svg class="pr-menu-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"
    fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>
    <rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>
</svg>`;

const _ICON_CHEVRON = `<svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24"
    fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
    <polyline points="6 9 12 15 18 9"/>
</svg>`;

const _ICON_PDF_BTN = `<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24"
    fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
    <polyline points="14 2 14 8 20 8"/>
</svg>`;

const _ICON_XL_BTN = `<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24"
    fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
    <rect x="2" y="3" width="20" height="18" rx="2"/>
    <line x1="8" y1="3" x2="8" y2="21"/>
    <line x1="2" y1="9" x2="22" y2="9"/>
    <line x1="2" y1="15" x2="22" y2="15"/>
</svg>`;

// ── Build a split-button ──────────────────────────────────────────────────────

function _make_split_btn(mainLabel, mainIcon, mainAction, menuItems, colorClass) {
    const $wrap = $(`
        <div class="pr-split-wrap ${colorClass}">
            <button class="pr-split-main">${mainIcon} ${mainLabel}</button>
            <button class="pr-split-arrow" title="More options">${_ICON_CHEVRON}</button>
            <div class="pr-split-menu">
                ${menuItems.map((item, i) => `
                    ${i > 0 && item.divider ? '<div class="pr-split-menu-divider"></div>' : ''}
                    <button class="pr-split-menu-item" data-item-idx="${i}">
                        ${item.icon}
                        <span>${item.label}</span>
                    </button>
                `).join("")}
            </div>
        </div>
    `);

    $wrap.find(".pr-split-main").on("click", function(e) {
        e.stopPropagation();
        $wrap.find(".pr-split-menu").removeClass("open");
        mainAction();
    });

    $wrap.find(".pr-split-arrow").on("click", function(e) {
        e.stopPropagation();
        const $menu = $wrap.find(".pr-split-menu");
        const wasOpen = $menu.hasClass("open");
        $(".pr-split-menu.open").removeClass("open");
        if (!wasOpen) $menu.addClass("open");
    });

    $wrap.find(".pr-split-menu-item").on("click", function(e) {
        e.stopPropagation();
        $wrap.find(".pr-split-menu").removeClass("open");
        const idx = +$(this).data("item-idx");
        menuItems[idx].action();
    });

    return $wrap;
}

// ── Close dropdowns when clicking outside ─────────────────────────────────────

$(document).on("click.pr-split", function() {
    $(".pr-split-menu.open").removeClass("open");
});

// ── Action buttons (two split-buttons) ───────────────────────────────────────

function _set_action_buttons(report) {
    report.page.wrapper.find(
        ".pr-split-wrap, .pr-select-print-btn, .pr-select-excel-btn, .pr-excel-cur-btn, .pr-excel-btn"
    ).remove();

    const actions = report.page.wrapper.find(".page-actions");

    const $pdfBtn = _make_split_btn(
        __("Print PDF"),
        _ICON_PDF_BTN,
        () => _debounced_action(() => _print_current(report)),
        [
            {
                icon:   _ICON_PDF,
                label:  __("Current Report"),
                action: () => _debounced_action(() => _print_current(report)),
            },
            {
                icon:    _ICON_MULTI,
                label:   __("Select Reports…"),
                action:  () => _show_select_dialog(report, $pdfBtn, "pdf"),
                divider: true,
            },
        ],
        "pr-split-pdf"
    );

    const $xlBtn = _make_split_btn(
        __("Export Excel"),
        _ICON_XL_BTN,
        () => _debounced_action(() => _excel_current(report)),
        [
            {
                icon:   _ICON_EXCEL,
                label:  __("Current Report"),
                action: () => _debounced_action(() => _excel_current(report)),
            },
            {
                icon:    _ICON_MULTI,
                label:   __("Select Reports…"),
                action:  () => _show_select_dialog(report, $xlBtn, "excel"),
                divider: true,
            },
        ],
        "pr-split-excel"
    );

    actions.prepend($xlBtn);
    actions.prepend($pdfBtn);
}

// ── Debounced action wrapper ──────────────────────────────────────────────────
// FIX: prevents double-click / rapid re-click from firing duplicate backend jobs.
// Disables all action buttons for 2 s after the first click.

function _debounced_action(fn) {
    const myGen = ++_action_gen;
    // Disable buttons immediately to give visual feedback
    $(".pr-split-main, .pr-split-arrow").prop("disabled", true);

    clearTimeout(_action_timer);
    _action_timer = setTimeout(() => {
        // Only proceed if no newer click has superseded this one
        if (myGen === _action_gen) {
            fn();
        }
        // Re-enable buttons regardless (the progress bar takes over UX from here)
        $(".pr-split-main, .pr-split-arrow").prop("disabled", false);
    }, 400);   // 400 ms absorbs accidental double-clicks; feels instant to users
}

// ── Print / Excel current tab ─────────────────────────────────────────────────

function _print_current(report) {
    if (!_validate(report)) return;
    const label = REPORTS[_idx]?.label || "Report";
    _run_with_progress(
        "saral_hr.saral_hr.report.payroll_report.payroll_report.print_single_report",
        { filters: JSON.stringify(_server_filters(report)) },
        `Generating PDF: ${label}`
    );
}

function _excel_current(report) {
    if (!_validate(report)) return;
    const label = REPORTS[_idx]?.label || "Report";
    _run_with_progress(
        "saral_hr.saral_hr.report.payroll_report.payroll_report.excel_single_report",
        { filters: JSON.stringify(_server_filters(report)) },
        `Exporting Excel: ${label}`
    );
}

// ── Select dialog (shared by PDF and Excel) ───────────────────────────────────

function _show_select_dialog(report, triggerBtn, mode) {
    if (!_validate(report)) return;

    const half  = Math.ceil(REPORTS.length / 2);
    const left  = REPORTS.slice(0, half);
    const right = REPORTS.slice(half);

    const title       = mode === "excel" ? __("Select Reports to Export (Excel)") : __("Select Reports to Print");
    const actionLabel = mode === "excel" ? __("Export Excel") : __("Generate PDF");

    function _chkRow(r, i) {
        return `
        <div class="pr-chk-row" style="display:flex;align-items:center;gap:8px;
             padding:6px 8px;border-radius:6px;cursor:pointer;transition:background .1s;"
             onmouseenter="this.style.background='#f1f5f9'"
             onmouseleave="this.style.background='transparent'"
             onclick="document.getElementById('pr-chk-${i}').click()">
          <input type="checkbox" id="pr-chk-${i}" data-key="${r.key}" checked
                 style="width:15px;height:15px;flex-shrink:0;cursor:pointer;accent-color:#2563eb;"
                 onclick="event.stopPropagation()">
          <label for="pr-chk-${i}"
                 style="cursor:pointer;font-size:12.5px;color:#1e293b;margin:0;font-weight:500;line-height:1.3;">
            ${r.label}
          </label>
        </div>`;
    }

    const body = `
        <div style="padding:4px 0 8px;">
          <div style="display:flex;gap:8px;padding:0 8px 10px;border-bottom:1px solid #e2e8f0;margin-bottom:8px;">
            <button class="btn btn-xs btn-default" onclick="
                document.querySelectorAll('.pr-chk-row input[type=checkbox]').forEach(c=>c.checked=true)
            ">${__("Select All")}</button>
            <button class="btn btn-xs btn-default" onclick="
                document.querySelectorAll('.pr-chk-row input[type=checkbox]').forEach(c=>c.checked=false)
            ">${__("Unselect All")}</button>
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:0 12px;padding:0 4px;">
            <div>${left.map((r, i) => _chkRow(r, i)).join("")}</div>
            <div>${right.map((r, i) => _chkRow(r, i + half)).join("")}</div>
          </div>
        </div>
    `;

    const d = new frappe.ui.Dialog({
        title,
        fields: [{ fieldtype: "HTML", fieldname: "report_list", options: body }],
        primary_action_label: actionLabel,
        primary_action() {
            const selected = [];
            document.querySelectorAll(".pr-chk-row input[type=checkbox]").forEach(chk => {
                if (chk.checked) selected.push(chk.dataset.key);
            });
            if (!selected.length) {
                frappe.msgprint({ title:__("Nothing Selected"), message:__("Please select at least one report."), indicator:"orange" });
                return;
            }
            d.hide();
            if (mode === "excel") {
                _export_selected_excel(report, selected);
            } else {
                _print_selected(report, selected);
            }
        },
    });
    d.show();
}

// ── Export selected as Excel ──────────────────────────────────────────────────

function _export_selected_excel(report, selectedKeys) {
    const count = selectedKeys.length;
    const f     = _server_filters(report);
    delete f.report_mode;
    f.selected_reports = JSON.stringify(selectedKeys);

    _run_with_progress(
        "saral_hr.saral_hr.report.payroll_report.payroll_report.excel_selected_reports",
        { filters: JSON.stringify(f) },
        `Exporting ${count} ${count === 1 ? "report" : "reports"} to Excel`
    );
}

// ── Print selected as PDF ─────────────────────────────────────────────────────

function _print_selected(report, selectedKeys) {
    const count = selectedKeys.length;
    const f     = _server_filters(report);
    delete f.report_mode;
    f.selected_reports = JSON.stringify(selectedKeys);

    _run_with_progress(
        "saral_hr.saral_hr.report.payroll_report.payroll_report.print_selected_reports",
        { filters: JSON.stringify(f) },
        `Compiling ${count} ${count === 1 ? "report" : "reports"}`
    );
}

// ── Progress runner ───────────────────────────────────────────────────────────

function _run_with_progress(method, args, label, onDone) {
    let pct = 0, done = false, phaseIdx = 0, phaseStart = Date.now(), rafId = null;

    const PHASES = [
        { target: 15, duration: 400  },
        { target: 40, duration: 1200 },
        { target: 65, duration: 2000 },
        { target: 82, duration: 4000 },
        { target: 88, duration: 6000 },
    ];

    frappe.show_progress(__("Processing"), 0, 100, `${__(label)}…`);

    function _tick() {
        if (done) return;
        const phase = PHASES[phaseIdx];
        if (!phase) { rafId = requestAnimationFrame(_tick); return; }
        const elapsed  = Date.now() - phaseStart;
        const progress = Math.min(elapsed / phase.duration, 1);
        const eased    = 1 - Math.pow(1 - progress, 2);
        const prevTarget = phaseIdx === 0 ? 0 : PHASES[phaseIdx - 1].target;
        pct = prevTarget + eased * (phase.target - prevTarget);
        frappe.show_progress(__("Processing"), Math.round(pct), 100, `${__(label)}…`);
        if (progress >= 1) { phaseIdx++; phaseStart = Date.now(); }
        rafId = requestAnimationFrame(_tick);
    }
    rafId = requestAnimationFrame(_tick);

    frappe.call({
        method, args,
        callback(r) {
            done = true;
            if (rafId) cancelAnimationFrame(rafId);
            frappe.show_progress(__("Processing"), 100, 100, __("Done!"));
            setTimeout(() => {
                frappe.hide_progress();
                if (onDone) onDone();
                if (r.message) _open_file(r.message);
                else frappe.msgprint({ title:__("Error"), message:__("Failed to generate file."), indicator:"red" });
            }, 600);
        },
        error() {
            done = true;
            if (rafId) cancelAnimationFrame(rafId);
            frappe.hide_progress();
            if (onDone) onDone();
            frappe.msgprint({ title:__("Error"), message:__("Failed to generate file."), indicator:"red" });
        }
    });
}

function _open_file(url) {
    const a = Object.assign(document.createElement("a"), {
        href: frappe.urllib.get_full_url(url), target: "_blank", rel: "noopener noreferrer"
    });
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
}