frappe.query_reports["Company Enrollment Summary"] = {

    filters: [
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Company",
            default: frappe.defaults.get_user_default("Company"),
        },
        {
            fieldname: "category",
            label: __("Category"),
            fieldtype: "Select",
            options: "\nStaff\nWorker",
        },
    ],

    datatable_options: {
        serialNoColumn: true,
        columnMinWidth: 50,
    },

    onload(report) {
        if (!document.getElementById("ces-global-style")) {
            const s = document.createElement("style");
            s.id = "ces-global-style";
            s.textContent = `
    .dt-cell--col-0,
    .dt-cell--col-0 .dt-cell__content,
    .dt-header--col-0,
    .dt-header--col-0 .dt-cell__content {
        width: 52px !important;
        min-width: 52px !important;
        max-width: 52px !important;
    }
    .dt-cell--col-0 .dt-cell__content {
        overflow: visible !important;
        text-overflow: unset !important;
        white-space: normal !important;
    }
    .page-form.flex { display: none !important; }
    .dt-scrollable {
        padding-bottom: 8px !important;
        box-sizing: border-box !important;
    }
    .dt-scrollable .dt-row:last-child .dt-cell__content,
    .dt-body .dt-row:last-child { margin-bottom: 8px !important; }
    .report-summary { display: none !important; }

    /* ── KPI bar ──────────────────────────────────────── */
    #ces-kpi-bar {
        display: flex;
        gap: 8px;
        padding: 10px 12px;
        flex-wrap: wrap;
        background: transparent;
        margin: 0;
    }

    /* ── Main report KPI cards ─── */
    .ces-sc-card {
        flex: 1;
        min-width: 120px;
        background: var(--card-bg);
        border-radius: var(--border-radius-md, 6px);
        padding: 10px 14px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        border: 1px solid var(--border-color);
        transition: box-shadow 0.15s ease, border-color 0.15s ease;
        cursor: default;
        box-sizing: border-box;
        gap: 4px;
        text-align: center;
    }
    .ces-sc-card.ces-sc-clickable { cursor: pointer; }
    .ces-sc-card.ces-sc-clickable:hover {
        box-shadow: var(--shadow-sm);
        border-color: var(--primary);
    }
    .ces-sc-lbl {
        display: block;
        font-size: 10px;
        font-weight: 600;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.6px;
        line-height: 1.3;
        text-align: center;
    }
    .ces-sc-val {
        display: block;
        font-size: 20px;
        font-weight: 700;
        line-height: 1.2;
        white-space: nowrap;
        margin-top: 2px;
        text-align: center;
        color: var(--text-color);
    }

    /* ── Popup KPI cards ── */
    .ces-kpi-card {
        flex: 0 0 auto;
        min-width: 90px;
        background: var(--card-bg);
        border: 1px solid var(--border-color);
        border-radius: var(--border-radius-md, 6px);
        padding: 8px 16px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 3px;
        transition: box-shadow 0.15s ease, border-color 0.15s ease;
        box-sizing: border-box;
        text-align: center;
    }
    .ces-kpi-card.clickable { cursor: pointer; }
    .ces-kpi-card.clickable:hover {
        box-shadow: var(--shadow-sm);
        border-color: var(--primary);
    }
    .ces-kpi-card.active-filter {
        border-color: var(--primary);
        box-shadow: 0 0 0 2px var(--primary-light, rgba(67,97,238,0.10));
        background: var(--bg-blue, #f0f3ff);
    }
    .ces-kpi-card.ces-ctc-card {
        min-width: 130px;
    }
    .ces-kpi-lbl {
        display: block;
        font-size: 10px;
        font-weight: 600;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: .6px;
        white-space: nowrap;
        line-height: 1.2;
        text-align: center;
    }
    .ces-kpi-val {
        display: block;
        font-size: 17px;
        font-weight: 700;
        line-height: 1.2;
        white-space: nowrap;
        margin-top: 2px;
        text-align: center;
        color: var(--text-color);
    }
    .ces-kpi-val.ces-ctc-val {
        font-size: 13px;
        font-weight: 600;
        color: var(--text-color);
    }

    /* ── Tables ─────────────────────────────────────────── */
    .ces-tbl, .ces-all-tbl {
        width: 100%;
        border-collapse: collapse;
        table-layout: fixed;
        font-size: 13px;
    }
    .ces-tbl thead tr,
    .ces-all-tbl thead tr {
        background: var(--control-bg);
        border-bottom: 2px solid var(--border-color);
        position: sticky;
        top: 0;
        z-index: 1;
    }
    .ces-tbl thead th,
    .ces-all-tbl thead th {
        padding: 9px 12px;
        color: var(--text-muted);
        font-size: 11px;
        font-weight: 600;
        text-align: left;
        letter-spacing: .5px;
        text-transform: uppercase;
        white-space: nowrap;
        user-select: none;
    }
    .ces-tbl thead th.th-sr,
    .ces-all-tbl thead th.th-sr { text-align: center; padding: 9px 0; }
    .ces-tbl thead th.th-ctc,
    .ces-all-tbl thead th.th-ctc { text-align: right; }
    .ces-tbl tbody tr,
    .ces-all-tbl tbody tr {
        transition: background 0.1s ease;
    }
    .ces-tbl tbody tr:hover,
    .ces-all-tbl tbody tr:hover { background: var(--fg-color) !important; }

    /* ── Fade-in animation ──────────────────────────────── */
    @keyframes ces-fade-in {
        from { opacity: 0; transform: translateY(4px); }
        to   { opacity: 1; transform: translateY(0); }
    }
    .ces-popup-body {
        animation: ces-fade-in 0.18s ease forwards;
    }

    /* ── Toolbar ─────────────────────────────────────────── */
    .ces-toolbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        margin-bottom: 10px;
        flex-wrap: wrap;
    }
    .ces-toolbar-left {
        font-size: 12px;
        color: var(--text-muted);
        font-weight: 500;
    }
    .ces-toolbar-left strong {
        color: var(--text-color);
        font-weight: 600;
    }

    /* ── Search box ──────────────────────────────────────── */
    .ces-search-wrap {
        position: relative;
        width: 360px;
        flex-shrink: 0;
    }
    .ces-search-wrap .ces-search-icon {
        position: absolute;
        left: 9px;
        top: 50%;
        transform: translateY(-50%);
        color: var(--text-muted);
        pointer-events: none;
        display: flex;
        align-items: center;
    }
    .ces-search-box {
        width: 100%;
        padding: 6px 10px 6px 30px;
        border: 1px solid var(--border-color);
        border-radius: var(--border-radius, 5px);
        font-size: 12px;
        background: var(--card-bg);
        color: var(--text-color);
        box-sizing: border-box;
        outline: none;
        transition: border-color 0.15s, box-shadow 0.15s;
        height: 30px;
        font-family: inherit;
    }
    .ces-search-box:focus {
        border-color: var(--primary);
        box-shadow: 0 0 0 2px var(--primary-light, rgba(67,97,238,0.08));
    }
    .ces-search-box::placeholder {
        color: var(--text-muted);
        font-size: 12px;
    }

    /* ── Table scroll container ──────────────────────────── */
    .ces-table-scroll {
        max-height: 400px;
        overflow-y: auto;
        border: 1px solid var(--border-color);
        border-radius: var(--border-radius-md, 6px);
        background: var(--card-bg);
        scrollbar-width: thin;
        scrollbar-color: var(--border-color) transparent;
    }
    .ces-table-scroll::-webkit-scrollbar { width: 4px; }
    .ces-table-scroll::-webkit-scrollbar-thumb {
        background: var(--border-color);
        border-radius: 3px;
    }

    /* ── Footer ─────────────────────────────────────────── */
    .ces-popup-footer {
        margin-top: 8px;
        font-size: 11px;
        color: var(--text-color);
        padding: 2px 0;
    }

    /* ── Card group container ────────────────────────────── */
    .ces-card-group {
        border: 1px solid var(--border-color);
        border-radius: var(--border-radius-md, 7px);
        background: var(--card-bg);
        padding: 10px 12px 12px 12px;
        margin-bottom: 12px;
        box-sizing: border-box;
    }
    .ces-card-group-label {
        font-size: 12px;
        font-weight: 700;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: .8px;
        margin-bottom: 8px;
        padding-left: 1px;
        display: block;
    }
    .ces-card-group-row {
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
    }
`;
            document.head.appendChild(s);
        }

        // Event delegation for KPI bar clicks
        $(document).off("click.ces-kpi").on("click.ces-kpi", ".ces-sc-clickable[data-ces-action]", function () {
            const action = $(this).attr("data-ces-action");
            _load_all_employees_popup(action);
        });
    },

    after_datatable_render(datatable) {
        _ces_inject_kpi_bar();
    },

    formatter(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (!data) return value;

        // All columns use Frappe default text-color; only "problem" values get accent colors
        if (column.fieldname === "company") {
            return `<span class="ces-company-link"
                         data-company="${frappe.utils.escape_html(data.company)}"
                         style="font-weight:600;color:var(--text-color);font-size:13px;cursor:pointer;">
                         ${data.company}
                    </span>`;
        }
        if (column.fieldname === "total_employees") {
            return `<span style="font-weight:600;color:var(--text-color);font-size:13px;">${data.total_employees || 0}</span>`;
        }
        if (column.fieldname === "total_staff") {
            return `<span style="font-weight:600;color:var(--text-color);font-size:13px;">${data.total_staff || 0}</span>`;
        }
        if (column.fieldname === "total_workers") {
            return `<span style="font-weight:600;color:var(--text-color);font-size:13px;">${data.total_workers || 0}</span>`;
        }
        if (column.fieldname === "salary_structure_assigned") {
            return `<span style="font-weight:600;color:var(--text-color);font-size:13px;">${data.salary_structure_assigned || 0}</span>`;
        }
        if (column.fieldname === "salary_structure_unassigned") {
            const v = data.salary_structure_unassigned || 0;
            // Only unassigned > 0 gets a warning color — everything else is default
            const color = v > 0 ? "var(--red-500, #e74c3c)" : "var(--text-color)";
            return `<span style="color:${color};font-weight:600;font-size:13px;">${v}</span>`;
        }
        if (column.fieldname === "total_ctc") {
            const v = parseFloat(data.total_ctc || 0);
            return `<span style="font-weight:600;color:var(--text-color);font-size:13px;">&#8377; ${ces_fmt(v)}</span>`;
        }
        return value;
    },
};

// ── Indian number formatter ──────────────────────────────────────────────────
function ces_fmt(num) {
    return parseFloat(num || 0).toLocaleString("en-IN", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    });
}

// ── Freeze / unfreeze helpers ────────────────────────────────────────────────
function _ces_freeze(msg) {
    try {
        if (typeof frappe.freeze === "function") frappe.freeze(msg || __("Loading…"));
        else if (frappe.ui?.freeze) frappe.ui.freeze(msg || __("Loading…"));
        else {
            if (!document.getElementById("ces-freeze-overlay")) {
                const el = document.createElement("div");
                el.id = "ces-freeze-overlay";
                el.style.cssText = "position:fixed;inset:0;z-index:9999;background:rgba(255,255,255,0.55);display:flex;align-items:center;justify-content:center;font-size:15px;font-weight:600;color:var(--primary);";
                el.textContent = msg || __("Loading…");
                document.body.appendChild(el);
            }
        }
    } catch (e) { console.warn("[CES] freeze failed:", e); }
}

function _ces_unfreeze() {
    try {
        if (typeof frappe.unfreeze === "function") frappe.unfreeze();
        else if (frappe.ui?.unfreeze) frappe.ui.unfreeze();
        else document.getElementById("ces-freeze-overlay")?.remove();
    } catch (e) { console.warn("[CES] unfreeze failed:", e); }
}

// ── KPI bar (main report page) ───────────────────────────────────────────────
function _ces_inject_kpi_bar() {
    const report_data = frappe.query_report.data || [];
    const companies = report_data.length;

    _ces_render_kpi_bar({ companies, employees: "…", staff: "…", workers: "…", salary_unassigned: "…", company_unassigned: "…" });

    frappe.call({
        method: "saral_hr.saral_hr.report.company_enrollment_summary.company_enrollment_summary.get_total_active_employee_count",
        callback(r) { _ces_update_kpi_card("number of employees", parseInt(r.message) || 0); },
    });
    frappe.call({
        method: "saral_hr.saral_hr.report.company_enrollment_summary.company_enrollment_summary.get_category_employee_count",
        args: { category: "Staff" },
        callback(r) { _ces_update_kpi_card("number of staff", parseInt(r.message) || 0); },
    });
    frappe.call({
        method: "saral_hr.saral_hr.report.company_enrollment_summary.company_enrollment_summary.get_category_employee_count",
        args: { category: "Worker" },
        callback(r) { _ces_update_kpi_card("number of workers", parseInt(r.message) || 0); },
    });
    frappe.call({
        method: "saral_hr.saral_hr.report.company_enrollment_summary.company_enrollment_summary.get_salary_unassigned_employee_count",
        callback(r) { _ces_update_kpi_card("unassigned salary structure", parseInt(r.message) || 0); },
    });
    frappe.call({
        method: "saral_hr.saral_hr.report.company_enrollment_summary.company_enrollment_summary.get_unlinked_employee_count",
        callback(r) { _ces_update_kpi_card("company unassigned", parseInt(r.message) || 0); },
    });
}

function _ces_update_kpi_card(label_substring, value) {
    $("#ces-kpi-bar .ces-sc-card").each(function () {
        const lbl = $(this).find(".ces-sc-lbl").text().toLowerCase();
        if (lbl.includes(label_substring)) {
            $(this).find(".ces-sc-val").text(value);
        }
    });
}

function _ces_render_kpi_bar({ companies, employees, staff, workers, salary_unassigned, company_unassigned }) {
    // No hardcoded colors — all values use Frappe default text-color via CSS class
    // Only "problem" cards (unassigned) get a red accent via inline style
    const cards = [
        { label: "Number of Companies",        value: companies,          warn: false, action: null                },
        { label: "Number of Employees",         value: employees,          warn: false, action: "all"               },
        { label: "Number of Staff",             value: staff,              warn: false, action: "staff"             },
        { label: "Number of Workers",           value: workers,            warn: false, action: "worker"            },
        { label: "Unassigned Salary Structure", value: salary_unassigned,  warn: true,  action: "salary_unassigned" },
        { label: "Company Unassigned",          value: company_unassigned, warn: true,  action: "company_unassigned"},
    ];

    const cards_html = cards.map(c => `
        <div class="ces-sc-card${c.action ? " ces-sc-clickable" : ""}"
             ${c.action ? `data-ces-action="${c.action}"` : ""}>
            <span class="ces-sc-lbl">${c.label}</span>
            <span class="ces-sc-val"${c.warn ? ' style="color:var(--red-500,#e74c3c);"' : ""}>${c.value}</span>
        </div>
    `).join("");

    $("#ces-kpi-bar").remove();
    const $bar = $(`<div id="ces-kpi-bar">${cards_html}</div>`);

    const $target = $(".report-wrapper, .datatable-wrapper, .frappe-datatable").first();
    if ($target.length) $target.before($bar);
    else $(".page-content .report-area, .report-area, .page-content").first().prepend($bar);
}

// ── Company row click → per-company popup ────────────────────────────────────
$(document).on("click", ".ces-company-link", function (e) {
    e.preventDefault();
    const company = $(this).data("company");
    const category = frappe.query_report.get_filter_value("category") || null;
    _load_company_popup(company, category, null, null);
});

// ── Persistent dialog references ────────────────────────────────────────────
let _ces_company_dialog = null;
let _ces_all_dialog = null;

// ── Per-company popup ────────────────────────────────────────────────────────
function _load_company_popup(company, category, filter_mode, cat_filter) {
    frappe.call({
        method: "saral_hr.saral_hr.report.company_enrollment_summary.company_enrollment_summary.get_company_employees",
        args: { company, category },
        freeze: true,
        freeze_message: __("Fetching employees…"),
        callback(r) {
            if (r.exc) { frappe.msgprint(__("Error loading employees.")); return; }
            _show_company_popup(company, r.message || [], filter_mode, cat_filter);
        },
    });
}

function _show_company_popup(company, all_employees, filter_mode, cat_filter) {
    const total = all_employees.length;
    const assigned = all_employees.filter(e => e.salary_structure !== "Not Assigned").length;
    const unassigned = total - assigned;
    const total_annual_ctc = all_employees.reduce((s, e) => s + (parseFloat(e.annual_ctc) || 0), 0);
    const total_monthly_ctc = all_employees.reduce((s, e) => s + (parseFloat(e.monthly_ctc) || 0), 0);
    const total_staff = all_employees.filter(e => e.category === "Staff").length;
    const total_workers = all_employees.filter(e => e.category === "Worker").length;

    let employees = all_employees;
    if (filter_mode === "assigned")   employees = employees.filter(e => e.salary_structure !== "Not Assigned");
    if (filter_mode === "unassigned") employees = employees.filter(e => e.salary_structure === "Not Assigned");
    if (cat_filter === "staff")       employees = employees.filter(e => e.category === "Staff");
    if (cat_filter === "worker")      employees = employees.filter(e => e.category === "Worker");

    const body_html = _build_company_popup_body(
        company, employees, total, assigned, unassigned,
        total_annual_ctc, total_monthly_ctc,
        total_staff, total_workers,
        filter_mode, cat_filter
    );

    if (_ces_company_dialog && _ces_company_dialog.$wrapper?.is(":visible")) {
        _ces_company_dialog.set_title(`${company} — Employee Details`);
        _ces_swap_content(_ces_company_dialog, body_html);
        setTimeout(() => _bind_company_popup_clicks(_ces_company_dialog, company, all_employees), 200);
        return;
    }

    const d = new frappe.ui.Dialog({
        title: `${company} — Employee Details`,
        size: "extra-large",
        fields: [{ fieldtype: "HTML", fieldname: "content", options: body_html }],
        primary_action_label: __("Close"),
        primary_action() { d.hide(); },
    });
    d.show();
    _ces_company_dialog = d;

    d.$wrapper.on("hide.bs.modal", () => { _ces_company_dialog = null; });

    setTimeout(() => {
        _ces_style_modal(d);
        _bind_company_popup_clicks(d, company, all_employees);
    }, 60);
}

function _bind_company_popup_clicks(dialog, company, all_employees) {
    dialog.$wrapper.find(".ces-kpi-card[data-filter]").off("click.ces").on("click.ces", function () {
        const f = $(this).data("filter");
        const cat_f = $(dialog.$wrapper).find(".ces-kpi-card[data-cat].active-filter").data("cat") || null;
        _show_company_popup(company, all_employees, f === "all" ? null : f, cat_f);
    });
    dialog.$wrapper.find(".ces-kpi-card[data-cat]").off("click.ces-cat").on("click.ces-cat", function () {
        const cat = $(this).data("cat");
        const fil_f = $(dialog.$wrapper).find(".ces-kpi-card[data-filter].active-filter").data("filter") || null;
        _show_company_popup(company, all_employees, fil_f === "all" ? null : fil_f, cat === "all" ? null : cat);
    });
}

function _build_company_popup_body(
    company, employees, total, assigned, unassigned,
    total_annual_ctc, total_monthly_ctc,
    total_staff, total_workers,
    filter_mode, cat_filter
) {
    const rows_html = employees.length
        ? employees.map((emp, i) => {
            const annual_str = emp.annual_ctc
                ? `&#8377; ${ces_fmt(emp.annual_ctc)}`
                : `<span style="color:var(--red-500,#e74c3c);font-weight:600;">—</span>`;

            const monthly_str = emp.monthly_ctc
                ? `&#8377; ${ces_fmt(emp.monthly_ctc)}`
                : `<span style="color:var(--red-500,#e74c3c);font-weight:600;">—</span>`;

            const badge = emp.salary_structure === "Not Assigned"
                ? `<span onclick="event.stopPropagation();"
                         style="background:var(--bg-red,#fff5f5);color:var(--red-500,#e74c3c);
                                border:1px solid var(--red-200,#ffd5d5);
                                padding:3px 10px;border-radius:4px;font-size:11px;font-weight:500;
                                white-space:nowrap;display:inline-flex;align-items:center;gap:4px;">
                               <svg width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M2 2l6 6M8 2l-6 6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
                               Not Assigned</span>`
                : `<span onclick="event.stopPropagation(); window.open('/app/salary-structure-assignment?employee=${emp.employee}','_blank');"
                         title="Open Salary Structure Assignment"
                         style="background:var(--bg-green,#eafaf1);color:var(--green-500,#27ae60);
                                border:1px solid var(--green-200,#c3e6cb);
                                padding:3px 10px;border-radius:4px;font-size:11px;font-weight:500;
                                white-space:nowrap;display:inline-flex;align-items:center;gap:4px;cursor:pointer;">
                               <svg width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M1.5 5l3 3 4-4.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
                               ${emp.salary_structure}</span>`;

            const row_bg = i % 2 === 0 ? "var(--card-bg)" : "var(--control-bg-input)";
            return `
            <tr class="ces-emp-row"
                onclick="window.open('/app/employee-profile/${emp.employee}','_blank')"
                style="background:${row_bg};border-bottom:1px solid var(--border-color);cursor:pointer;">
                <td style="padding:10px 0;color:var(--text-muted);font-size:12px;width:44px;text-align:center;vertical-align:middle;">${i + 1}</td>
                <td style="padding:10px 14px;vertical-align:middle;overflow:hidden;">
                    <div style="font-weight:600;color:var(--primary);font-size:13px;line-height:1.4;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${emp.full_name}</div>
                    <div style="font-size:11px;color:var(--text-muted);margin-top:2px;">${emp.employee}</div>
                </td>
                <td style="padding:10px 14px;white-space:nowrap;vertical-align:middle;">
                    <span style="background:var(--control-bg);color:var(--text-muted);padding:3px 10px;border-radius:4px;font-size:11px;font-weight:600;border:1px solid var(--border-color);">${emp.category}</span>
                </td>
                <td style="padding:10px 14px;white-space:nowrap;vertical-align:middle;">${badge}</td>
                <td style="padding:10px 14px;text-align:right;font-weight:600;color:var(--text-color);font-size:13px;white-space:nowrap;vertical-align:middle;">${monthly_str}</td>
                <td style="padding:10px 14px;text-align:right;font-weight:600;color:var(--text-color);font-size:13px;white-space:nowrap;vertical-align:middle;">${annual_str}</td>
            </tr>`;
        }).join("")
        : `<tr><td colspan="6" style="text-align:center;padding:48px 20px;color:var(--text-muted);font-size:13px;">
               <svg width="32" height="32" viewBox="0 0 24 24" fill="none" style="display:block;margin:0 auto 10px;opacity:0.35"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="1.5"/><path d="M8 12h8M12 8v8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
               No employees found</td></tr>`;

    return `
    <div class="ces-popup-body">

        <!-- Group 1: Salary Structure -->
        <div class="ces-card-group">
            <span class="ces-card-group-label">Salary Structure</span>
            <div class="ces-card-group-row">
                <div class="ces-kpi-card clickable ${!filter_mode ? "active-filter" : ""}" data-filter="all" title="Show all">
                    <span class="ces-kpi-lbl">Total Employees</span>
                    <span class="ces-kpi-val">${total}</span>
                </div>
                <div class="ces-kpi-card clickable ${filter_mode === "assigned" ? "active-filter" : ""}" data-filter="assigned" title="Show assigned only">
                    <span class="ces-kpi-lbl">Assigned</span>
                    <span class="ces-kpi-val">${assigned}</span>
                </div>
                <div class="ces-kpi-card clickable ${filter_mode === "unassigned" ? "active-filter" : ""}" data-filter="unassigned" title="Show unassigned only">
                    <span class="ces-kpi-lbl">Unassigned</span>
                    <span class="ces-kpi-val" style="color:var(--red-500,#e74c3c);">${unassigned}</span>
                </div>
                <div class="ces-kpi-card ces-ctc-card">
                    <span class="ces-kpi-lbl">Monthly CTC</span>
                    <span class="ces-kpi-val ces-ctc-val">&#8377; ${ces_fmt(total_monthly_ctc)}</span>
                </div>
                <div class="ces-kpi-card ces-ctc-card">
                    <span class="ces-kpi-lbl">Annual CTC</span>
                    <span class="ces-kpi-val ces-ctc-val">&#8377; ${ces_fmt(total_annual_ctc)}</span>
                </div>
            </div>
        </div>

        <!-- Group 2: Category -->
        <div class="ces-card-group">
            <span class="ces-card-group-label">Category</span>
            <div class="ces-card-group-row">
                <div class="ces-kpi-card clickable ${!cat_filter ? "active-filter" : ""}" data-cat="all" title="All categories">
                    <span class="ces-kpi-lbl">All Categories</span>
                    <span class="ces-kpi-val">${total}</span>
                </div>
                <div class="ces-kpi-card clickable ${cat_filter === "staff" ? "active-filter" : ""}" data-cat="staff" title="Staff only">
                    <span class="ces-kpi-lbl">Staff</span>
                    <span class="ces-kpi-val">${total_staff}</span>
                </div>
                <div class="ces-kpi-card clickable ${cat_filter === "worker" ? "active-filter" : ""}" data-cat="worker" title="Workers only">
                    <span class="ces-kpi-lbl">Workers</span>
                    <span class="ces-kpi-val">${total_workers}</span>
                </div>
            </div>
        </div>

        <!-- Toolbar: count left, search right -->
        <div class="ces-toolbar">
            <div class="ces-toolbar-left">
                Showing <strong>${employees.length}</strong> employee(s) for <strong>${company}</strong>
            </div>
            <div class="ces-search-wrap">
                <span class="ces-search-icon">
                    <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><circle cx="6.5" cy="6.5" r="5" stroke="currentColor" stroke-width="1.5"/><path d="M10.5 10.5L14 14" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
                </span>
                <input type="text" class="ces-search-box" placeholder="Search by name or ID…" oninput="ces_filter_table(this)">
            </div>
        </div>

        <!-- Table with scroll -->
        <div class="ces-table-scroll">
            <table class="ces-tbl">
                <colgroup>
                    <col style="width:44px">
                    <col>
                    <col style="width:100px">
                    <col style="width:200px">
                    <col style="width:150px">
                    <col style="width:150px">
                </colgroup>
                <thead><tr>
                    <th class="th-sr">#</th>
                    <th>Employee</th>
                    <th>Category</th>
                    <th>Salary Structure</th>
                    <th class="th-ctc">Monthly CTC</th>
                    <th class="th-ctc">Annual CTC</th>
                </tr></thead>
                <tbody>${rows_html}</tbody>
            </table>
        </div>

        <div id="ces-popup-footer" class="ces-popup-footer" style="display:none;"></div>
    </div>`;
}

// ── All-employees popup (from main KPI bar) ──────────────────────────────────
function _load_all_employees_popup(action) {
    const category = frappe.query_report.get_filter_value("category") || null;
    const company_filter = frappe.query_report.get_filter_value("company") || null;

    if (action === "salary_unassigned") {
        _ces_freeze(__("Fetching employees…"));
        frappe.call({
            method: "saral_hr.saral_hr.report.company_enrollment_summary.company_enrollment_summary.get_salary_unassigned_employees",
            args: { category },
            callback(r) {
                _ces_unfreeze();
                _show_all_employees_popup(r.message || [], "salary_unassigned");
            },
        });
        return;
    }

    if (action === "company_unassigned") {
        _ces_freeze(__("Fetching employees…"));
        frappe.call({
            method: "saral_hr.saral_hr.report.company_enrollment_summary.company_enrollment_summary.get_company_unassigned_employees",
            callback(r) {
                _ces_unfreeze();
                _show_all_employees_popup(r.message || [], "company_unassigned");
            },
        });
        return;
    }

    const report_data = frappe.query_report.data || [];
    let companies = [];
    if (company_filter) {
        companies = [company_filter];
    } else if (report_data.length) {
        companies = [...new Set(
            report_data.map(r => r.company || r.company_name || null).filter(Boolean)
        )];
    }

    if (!companies.length) {
        frappe.msgprint(__("No companies found in the report data. Please run the report first."));
        return;
    }

    const cat_filter = action === "staff"  ? "Staff"
                     : action === "worker" ? "Worker"
                     : category;

    _ces_freeze(__("Fetching employees…"));

    const promises = companies.map(c =>
        new Promise(resolve => {
            frappe.call({
                method: "saral_hr.saral_hr.report.company_enrollment_summary.company_enrollment_summary.get_company_employees",
                args: { company: c, category: cat_filter },
                callback(r) { resolve((r.message || []).map(e => ({ ...e, company: c }))); },
            });
        })
    );

    Promise.all(promises).then(results => {
        _ces_unfreeze();
        const all_employees = results.flat();
        _show_all_employees_popup(all_employees, action);
    }).catch(err => {
        _ces_unfreeze();
        console.error("[CES] Error fetching employees:", err);
        frappe.msgprint(__("Error fetching employees. Please try again."));
    });
}

function _show_all_employees_popup(all_employees, action) {
    const total = all_employees.length;
    const total_ctc = all_employees.reduce((s, e) => s + (parseFloat(e.annual_ctc) || 0), 0);
    const total_monthly = all_employees.reduce((s, e) => s + (parseFloat(e.monthly_ctc) || 0), 0);

    const title_map = {
        all:                __("All Employees"),
        staff:              __("Staff Employees"),
        worker:             __("Worker Employees"),
        salary_unassigned:  __("Unassigned Salary Structure"),
        company_unassigned: __("Company Unassigned Employees"),
    };
    const popup_title = title_map[action] || __("All Employees");

    const rows_html = all_employees.length
        ? all_employees.map((emp, i) => {
            const annual_str = emp.annual_ctc
                ? `&#8377; ${ces_fmt(emp.annual_ctc)}`
                : `<span style="color:var(--red-500,#e74c3c);font-weight:600;">—</span>`;

            const monthly_str = emp.monthly_ctc
                ? `&#8377; ${ces_fmt(emp.monthly_ctc)}`
                : `<span style="color:var(--red-500,#e74c3c);font-weight:600;">—</span>`;

            const badge = emp.salary_structure === "Not Assigned"
                ? `<span onclick="event.stopPropagation();"
                         style="background:var(--bg-red,#fff5f5);color:var(--red-500,#e74c3c);
                                border:1px solid var(--red-200,#ffd5d5);
                                padding:3px 10px;border-radius:4px;font-size:11px;font-weight:500;
                                white-space:nowrap;display:inline-flex;align-items:center;gap:4px;">
                               <svg width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M2 2l6 6M8 2l-6 6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
                               Not Assigned</span>`
                : `<span onclick="event.stopPropagation(); window.open('/app/salary-structure-assignment?employee=${emp.employee}','_blank');"
                         title="Open Salary Structure Assignment"
                         style="background:var(--bg-green,#eafaf1);color:var(--green-500,#27ae60);
                                border:1px solid var(--green-200,#c3e6cb);
                                padding:3px 10px;border-radius:4px;font-size:11px;font-weight:500;
                                white-space:nowrap;display:inline-flex;align-items:center;gap:4px;cursor:pointer;">
                               <svg width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M1.5 5l3 3 4-4.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
                               ${emp.salary_structure}</span>`;

            const row_bg = i % 2 === 0 ? "var(--card-bg)" : "var(--control-bg-input)";
            return `
            <tr class="ces-emp-row"
                onclick="window.open('/app/employee-profile/${emp.employee}','_blank')"
                style="background:${row_bg};border-bottom:1px solid var(--border-color);cursor:pointer;">
                <td style="padding:10px 0;color:var(--text-muted);font-size:12px;width:44px;text-align:center;vertical-align:middle;">${i + 1}</td>
                <td style="padding:10px 14px;vertical-align:middle;overflow:hidden;">
                    <div style="font-weight:600;color:var(--primary);font-size:13px;line-height:1.4;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${emp.full_name}</div>
                    <div style="font-size:11px;color:var(--text-muted);margin-top:2px;">${emp.employee}</div>
                </td>
                <td style="padding:10px 14px;vertical-align:middle;white-space:nowrap;overflow:hidden;">
                    <span style="background:var(--control-bg);color:var(--text-muted);padding:3px 10px;border-radius:4px;font-size:11px;font-weight:600;border:1px solid var(--border-color);display:inline-block;max-width:150px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${emp.company || "—"}</span>
                </td>
                <td style="padding:10px 14px;vertical-align:middle;white-space:nowrap;">
                    <span style="background:var(--control-bg);color:var(--text-muted);padding:3px 10px;border-radius:4px;font-size:11px;font-weight:600;border:1px solid var(--border-color);">${emp.category}</span>
                </td>
                <td style="padding:10px 14px;white-space:nowrap;vertical-align:middle;">${badge}</td>
                <td style="padding:10px 14px;text-align:right;font-weight:600;color:var(--text-color);font-size:13px;white-space:nowrap;vertical-align:middle;">${monthly_str}</td>
                <td style="padding:10px 14px;text-align:right;font-weight:600;color:var(--text-color);font-size:13px;white-space:nowrap;vertical-align:middle;">${annual_str}</td>
            </tr>`;
        }).join("")
        : `<tr><td colspan="7" style="text-align:center;padding:48px 20px;color:var(--text-muted);font-size:13px;">
               <svg width="32" height="32" viewBox="0 0 24 24" fill="none" style="display:block;margin:0 auto 10px;opacity:0.35"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="1.5"/><path d="M8 12h8M12 8v8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
               No employees found</td></tr>`;

    const summary_html = `
    <div class="ces-card-group">
        <span class="ces-card-group-label">Summary</span>
        <div class="ces-card-group-row">
            <div class="ces-kpi-card">
                <span class="ces-kpi-lbl">Total Employees</span>
                <span class="ces-kpi-val">${total}</span>
            </div>
            <div class="ces-kpi-card ces-ctc-card">
                <span class="ces-kpi-lbl">Monthly CTC</span>
                <span class="ces-kpi-val ces-ctc-val">&#8377; ${ces_fmt(total_monthly)}</span>
            </div>
            <div class="ces-kpi-card ces-ctc-card">
                <span class="ces-kpi-lbl">Annual CTC</span>
                <span class="ces-kpi-val ces-ctc-val">&#8377; ${ces_fmt(total_ctc)}</span>
            </div>
        </div>
    </div>`;

    const body_html = `
    <div class="ces-popup-body">
        ${summary_html}
        <div class="ces-toolbar">
            <div class="ces-toolbar-left">
                Showing <strong>${total}</strong> employee(s)
            </div>
            <div class="ces-search-wrap">
                <span class="ces-search-icon">
                    <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><circle cx="6.5" cy="6.5" r="5" stroke="currentColor" stroke-width="1.5"/><path d="M10.5 10.5L14 14" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
                </span>
                <input type="text" class="ces-search-box" placeholder="Search by name or ID…" oninput="ces_filter_table(this)">
            </div>
        </div>
        <div class="ces-table-scroll">
            <table class="ces-all-tbl">
                <colgroup>
                    <col style="width:44px">
                    <col>
                    <col style="width:155px">
                    <col style="width:88px">
                    <col style="width:175px">
                    <col style="width:138px">
                    <col style="width:138px">
                </colgroup>
                <thead><tr>
                    <th class="th-sr">#</th>
                    <th>Employee Name</th>
                    <th>Company</th>
                    <th>Category</th>
                    <th>Salary Structure</th>
                    <th class="th-ctc">Monthly CTC</th>
                    <th class="th-ctc">Annual CTC</th>
                </tr></thead>
                <tbody id="ces-all-tbody">${rows_html}</tbody>
            </table>
        </div>
        <div id="ces-all-footer" class="ces-popup-footer" style="display:none;"></div>
    </div>`;

    if (_ces_all_dialog && _ces_all_dialog.$wrapper?.is(":visible")) {
        _ces_all_dialog.set_title(popup_title);
        _ces_swap_content(_ces_all_dialog, body_html);
        return;
    }

    const d = new frappe.ui.Dialog({
        title: popup_title,
        size: "extra-large",
        fields: [{ fieldtype: "HTML", fieldname: "content", options: body_html }],
        primary_action_label: __("Close"),
        primary_action() { d.hide(); },
    });
    d.show();
    _ces_all_dialog = d;

    d.$wrapper.on("hide.bs.modal", () => { _ces_all_dialog = null; });

    setTimeout(() => _ces_style_modal(d), 60);
}

// ── Live search / filter inside popup tables ─────────────────────────────────
function ces_filter_table(input) {
    const query = input.value.toLowerCase().trim();
    const $rows = $(input).closest(".ces-popup-body").find(".ces-emp-row");
    let visible = 0;

    $rows.each(function () {
        const text = $(this).text().toLowerCase();
        const show = !query || text.includes(query);
        $(this).toggle(show);
        if (show) visible++;
    });

    const $toolbar_left = $(input).closest(".ces-popup-body").find(".ces-toolbar-left");
    if ($toolbar_left.length) {
        const total = $rows.length;
        if (query) {
            $toolbar_left.html(
                `Showing <strong>${visible}</strong> of <strong>${total}</strong> employee(s)`
            );
        } else {
            $toolbar_left.html(`Showing <strong>${total}</strong> employee(s)`);
        }
    }
}

// ── Helper: swap dialog HTML content with a smooth fade ─────────────────────
function _ces_swap_content(dialog, new_html) {
    const $body = dialog.$wrapper.find("[data-fieldname='content']");
    $body.css({ opacity: 0, transition: "opacity 0.15s ease" });

    setTimeout(() => {
        dialog.fields_dict.content.$wrapper.html(new_html);
        _ces_style_modal(dialog);
        const el = dialog.$wrapper.find(".ces-popup-body")[0];
        if (el) { el.style.animation = "none"; el.offsetHeight; el.style.animation = ""; }
        $body.css({ opacity: 1 });
    }, 160);
}

// ── Helper: style the modal body ─────────────────────────────────────────────
function _ces_style_modal(dialog) {
    dialog.$wrapper.find(".modal-body").css({
        padding:    "16px 20px",
        background: "var(--bg-color)",
    });
}