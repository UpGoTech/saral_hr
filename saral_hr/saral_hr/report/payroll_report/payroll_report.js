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

        // MutationObserver: hide serial number on ANY bold/total row, always
        const observer = new MutationObserver(() => _hide_total_serials());
        observer.observe(document.body, { childList: true, subtree: true, characterData: true });

        frappe.after_ajax(() => {
            _inject_nav(report);
            if (!report.page.wrapper.find(".pr-select-print-btn").length) {
                _set_print_buttons(report);
            }
        });
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

        return data.bold ? bold(value) : def(value);
    }
};

// ─── Hide serial numbers on all bold/total rows ────────────────────────────

function _hide_total_serials() {
    document.querySelectorAll(".dt-row").forEach(row => {
        // A total/bold row contains at least one <strong> element
        const hasStrong = row.querySelector("strong");
        if (!hasStrong) return;

        // Find the serial number cell (always col-index 0) and blank it
        const srCell = row.querySelector('[data-col-index="0"] .dt-cell__content');
        if (srCell && srCell.textContent.trim() !== "") {
            srCell.textContent = "";
        }
    });
}

// ─── Report list ───────────────────────────────────────────────────────────────

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
];

let _idx = 0, _cache = {}, _debounce_timer = null, _prefetch_xhr = null, _loading_key = null;

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

function _ensure_styles() {
    if (document.getElementById("pr-style")) return;
    const s = document.createElement("style");
    s.id = "pr-style";
    s.textContent = `
        .pr-nav-bar {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 10px 16px;
            background: var(--card-bg, #fff);
            border-top: 1px solid var(--border-color, #e2e8f0);
            border-bottom: 1px solid var(--border-color, #e2e8f0);
        }
        .pr-nav-label {
            font-size: 11px;
            font-weight: 700;
            color: var(--text-muted, #6b7280);
            text-transform: uppercase;
            letter-spacing: 0.4px;
            white-space: nowrap;
            flex-shrink: 0;
        }
        .pr-select-wrap {
            flex: 1;
            max-width: 320px;
            position: relative;
        }
        .pr-report-select {
            width: 100%;
            height: 34px;
            padding: 0 34px 0 10px;
            font-size: 13px;
            font-weight: 500;
            color: var(--text-color, #1a202c);
            background: var(--control-bg, #f8fafc);
            border: 1.5px solid var(--border-color, #e2e8f0);
            border-radius: 6px;
            outline: none;
            cursor: pointer;
            appearance: none;
            -webkit-appearance: none;
            transition: border-color .15s, box-shadow .15s;
        }
        .pr-report-select:focus {
            border-color: var(--primary, #2563eb);
            box-shadow: 0 0 0 3px rgba(37,99,235,.12);
        }
        .pr-select-arrow {
            position: absolute;
            right: 10px;
            top: 50%;
            transform: translateY(-50%);
            pointer-events: none;
            color: var(--text-muted, #6b7280);
        }
        .pr-arrow-btn {
            width: 34px;
            height: 34px;
            display: flex;
            align-items: center;
            justify-content: center;
            border: 1.5px solid var(--border-color, #e2e8f0);
            border-radius: 6px;
            background: var(--control-bg, #f8fafc);
            color: var(--text-color, #374151);
            cursor: pointer;
            font-size: 16px;
            flex-shrink: 0;
            transition: all .15s;
            user-select: none;
            line-height: 1;
        }
        .pr-arrow-btn:hover {
            border-color: var(--primary, #2563eb);
            color: var(--primary, #2563eb);
            background: #eff6ff;
        }
        .pr-on-hold-note {
            font-size: 11px;
            color: #c0392b;
            padding: 5px 16px;
            background: #fff5f5;
            border-bottom: 1px solid #fecaca;
            display: none;
        }
    `;
    document.head.appendChild(s);
}

function _inject_nav(report) {
    if (report.page.wrapper.find(".pr-nav-bar").length) return;
    _ensure_styles();

    const options = REPORTS.map((r, i) =>
        `<option value="${i}">${r.label}</option>`
    ).join("");

    const nav = $(`
        <div class="pr-nav-bar">
            <span class="pr-nav-label">Report</span>
            <div class="pr-select-wrap">
                <select class="pr-report-select">
                    ${options}
                </select>
                <svg class="pr-select-arrow" width="14" height="14" viewBox="0 0 24 24"
                     fill="none" stroke="currentColor" stroke-width="2.5"
                     stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="6 9 12 15 18 9"/>
                </svg>
            </div>
            <button class="pr-arrow-btn pr-prev" title="${__("Previous report")}">&#8249;</button>
            <button class="pr-arrow-btn pr-next" title="${__("Next report")}">&#8250;</button>
        </div>
        <div class="pr-on-hold-note" id="pr-on-hold-note"></div>
    `);

    const targets = [".frappe-report-filters-section",".filter-section",".standard-filter-section",".page-form"];
    let inserted = false;
    for (const sel of targets) {
        const el = report.page.wrapper.find(sel).first();
        if (el.length) { el.after(nav); inserted = true; break; }
    }
    if (!inserted) report.page.wrapper.find(".report-wrapper").prepend(nav);

    nav.find(".pr-report-select").on("change", function () {
        _go(report, +this.value);
    });
    nav.find(".pr-prev").on("click", () => _go(report, (_idx - 1 + REPORTS.length) % REPORTS.length));
    nav.find(".pr-next").on("click", () => _go(report, (_idx + 1) % REPORTS.length));

    report.page.wrapper.on("change.pr", ".frappe-control input, .frappe-control select", function () {
        if ($(this).hasClass("pr-report-select")) return;
        _cache       = {};
        _loading_key = null;
        if (_prefetch_xhr) { _prefetch_xhr.abort?.(); _prefetch_xhr = null; }
        clearTimeout(_debounce_timer);
        _debounce_timer = setTimeout(() => {
            if (!report._filters_filled()) return;
            _prefetch_all(report);
        }, 1500);
    });

    _bind_refresh_listener(report);

    $(frappe.query_report).one("after_refresh.pr_init", () => {
        _prefetch_all(report);
    });
}

function _sync(report) {
    report.page.wrapper.find(".pr-report-select").val(_idx);
    const label = REPORTS[_idx].label;
    report.page.wrapper.find(".title-text").text(label);
    document.title = label + " — Frappe";
}

function _go(report, idx) {
    if (!report._filters_filled || !report._filters_filled()) {
        frappe.msgprint({
            title:     __("Missing Filters"),
            message:   __("Please select Company, Year and Month first."),
            indicator: "orange",
        });
        report.page.wrapper.find(".pr-report-select").val(_idx);
        return;
    }

    _idx = idx;
    const modeKey = REPORTS[idx].key;
    _sync(report);
    frappe.query_report.set_filter_value("report_mode", modeKey);

    const fk     = _filter_key(report);
    const cached = _cache[fk]?.[modeKey];
    if (cached) {
        _render_cached(cached);
        _update_on_hold_note(cached.result);
        return;
    }

    _loading_key = `${fk}::${modeKey}`;
    frappe.query_report.refresh();
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

function _bind_refresh_listener(report) {
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
    });
}

function _prefetch_all(report) {
    const fk = _filter_key(report);
    const f  = report._live_filters ? report._live_filters() : (frappe.query_report.get_values() || {});
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
            if (!res.message) return;
            if (fk !== _filter_key(report)) return;
            if (!_cache[fk]) _cache[fk] = {};
            Object.assign(_cache[fk], res.message);
        },
        error() { _prefetch_xhr = null; }
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

function _set_print_buttons(report) {
    report.page.wrapper.find(".pr-select-print-btn").remove();
    const btnSel = $(`<button class="btn btn-default btn-sm pr-select-print-btn" style="margin-left:8px;">
        <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"
             stroke-linejoin="round" style="margin-right:4px;vertical-align:-1px;">
          <polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
        </svg>${__("Select & Print")}</button>`);
    report.page.wrapper.find(".page-actions").prepend(btnSel);
    btnSel.on("click", () => _show_select_print_dialog(report, btnSel));
    report.page.set_primary_action(__("Print"), () => _print_current(report), "printer");
}

function _print_current(report) {
    if (!_validate(report)) return;
    const label = REPORTS[_idx]?.label || "Report";
    _run_with_progress(
        "saral_hr.saral_hr.report.payroll_report.payroll_report.print_single_report",
        { filters: JSON.stringify(_server_filters(report)) },
        `Generating PDF: ${label}`
    );
}

function _show_select_print_dialog(report, triggerBtn) {
    if (!_validate(report)) return;

    const half  = Math.ceil(REPORTS.length / 2);
    const left  = REPORTS.slice(0, half);
    const right = REPORTS.slice(half);

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

    const leftHtml  = left.map((r, i) => _chkRow(r, i)).join("");
    const rightHtml = right.map((r, i) => _chkRow(r, i + half)).join("");

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
            <div>${leftHtml}</div>
            <div>${rightHtml}</div>
          </div>
        </div>
    `;

    const d = new frappe.ui.Dialog({
        title: __("Select Reports to Print"),
        fields: [{ fieldtype: "HTML", fieldname: "report_list", options: body }],
        primary_action_label: __("Generate PDF"),
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
            _print_selected(report, selected, triggerBtn);
        },
    });
    d.show();
}

function _print_selected(report, selectedKeys, btn) {
    const orig = btn.html();
    btn.prop("disabled", true);
    const count = selectedKeys.length;
    const f = _server_filters(report); delete f.report_mode;
    f.selected_reports = JSON.stringify(selectedKeys);
    _run_with_progress(
        "saral_hr.saral_hr.report.payroll_report.payroll_report.print_selected_reports",
        { filters: JSON.stringify(f) },
        `Compiling ${count} ${count === 1 ? "report" : "reports"}`,
        () => { btn.prop("disabled", false).html(orig); }
    );
}

function _run_with_progress(method, args, label, onDone) {
    let pct = 0, done = false, phaseIdx = 0, phaseStart = Date.now(), rafId = null;

    const PHASES = [
        { target: 15, duration: 400  },
        { target: 40, duration: 1200 },
        { target: 65, duration: 2000 },
        { target: 82, duration: 4000 },
        { target: 88, duration: 6000 },
    ];

    frappe.show_progress(__("Generating PDF"), 0, 100, `${__(label)}…`);

    function _tick() {
        if (done) return;
        const phase = PHASES[phaseIdx];
        if (!phase) { rafId = requestAnimationFrame(_tick); return; }
        const elapsed  = Date.now() - phaseStart;
        const progress = Math.min(elapsed / phase.duration, 1);
        const eased    = 1 - Math.pow(1 - progress, 2);
        const prevTarget = phaseIdx === 0 ? 0 : PHASES[phaseIdx - 1].target;
        pct = prevTarget + eased * (phase.target - prevTarget);
        frappe.show_progress(__("Generating PDF"), Math.round(pct), 100, `${__(label)}…`);
        if (progress >= 1) { phaseIdx++; phaseStart = Date.now(); }
        rafId = requestAnimationFrame(_tick);
    }
    rafId = requestAnimationFrame(_tick);

    frappe.call({
        method, args,
        callback(r) {
            done = true;
            if (rafId) cancelAnimationFrame(rafId);
            frappe.show_progress(__("Generating PDF"), 100, 100, __("Done!"));
            setTimeout(() => {
                frappe.hide_progress();
                if (onDone) onDone();
                if (r.message) _open_pdf(r.message);
                else frappe.msgprint({ title:__("Error"), message:__("Failed to generate PDF."), indicator:"red" });
            }, 600);
        },
        error() {
            done = true;
            if (rafId) cancelAnimationFrame(rafId);
            frappe.hide_progress();
            if (onDone) onDone();
            frappe.msgprint({ title:__("Error"), message:__("Failed to generate PDF."), indicator:"red" });
        }
    });
}

function _open_pdf(url) {
    const a = Object.assign(document.createElement("a"), {
        href: frappe.urllib.get_full_url(url), target: "_blank", rel: "noopener noreferrer"
    });
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
}