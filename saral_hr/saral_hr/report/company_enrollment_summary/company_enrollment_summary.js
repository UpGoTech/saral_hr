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

                #ces-kpi-bar {
                    display: flex;
                    gap: 12px;
                    padding: 14px 16px;
                    flex-wrap: wrap;
                    background: transparent;
                    margin: 0;
                }
                .ces-sc-card {
                    flex: 1;
                    min-width: 140px;
                    background: var(--card-bg, #ffffff);
                    border-radius: 8px;
                    padding: 14px 18px 12px;
                    text-align: center;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    border: 1px solid var(--border-color, #d1d8dd);
                    box-shadow: var(--card-shadow, 0 1px 3px rgba(0,0,0,0.06));
                    transition: box-shadow 0.2s ease, transform 0.2s ease, border-color 0.2s ease;
                    cursor: default;
                    box-sizing: border-box;
                }
                .ces-sc-card.ces-sc-clickable {
                    cursor: pointer;
                }
                .ces-sc-card.ces-sc-clickable:hover {
                    box-shadow: 0 4px 16px rgba(0,0,0,0.13);
                    transform: translateY(-2px);
                    border-color: var(--primary, #4361ee);
                }
                .ces-sc-lbl {
                    display: block;
                    font-size: 10px;
                    font-weight: 700;
                    color: var(--text-muted, #6b7280);
                    text-transform: uppercase;
                    letter-spacing: 0.8px;
                    margin-bottom: 6px;
                    white-space: nowrap;
                }
                .ces-sc-val {
                    display: block;
                    font-size: 28px;
                    font-weight: 800;
                    line-height: 1.1;
                }

                /* ── Shared popup styles ─────────────────────────────── */
                .ces-kpi-card {
                    flex: 1;
                    min-width: 110px;
                    background: var(--card-bg, #ffffff);
                    border: 1px solid var(--border-color, #d1d8dd);
                    border-radius: 8px;
                    padding: 14px 18px;
                    text-align: center;
                    transition: box-shadow 0.18s ease, border-color 0.18s ease;
                    box-sizing: border-box;
                }
                .ces-kpi-card.clickable { cursor: pointer; }
                .ces-kpi-card.clickable:hover {
                    box-shadow: 0 4px 14px rgba(0,0,0,0.10);
                    border-color: var(--primary, #4361ee);
                }
                .ces-kpi-card.active-filter {
                    border-color: var(--primary, #4361ee);
                    box-shadow: 0 0 0 3px var(--primary-light, rgba(67,97,238,0.12));
                }
                .ces-kpi-lbl {
                    display: block;
                    font-size: 10px;
                    font-weight: 700;
                    color: var(--text-muted, #6b7280);
                    text-transform: uppercase;
                    letter-spacing: .8px;
                    margin-bottom: 6px;
                }
                .ces-kpi-val {
                    display: block;
                    font-size: 26px;
                    font-weight: 800;
                    line-height: 1.15;
                }

                /* ── Tables ─────────────────────────────────────────── */
                .ces-tbl, .ces-all-tbl {
                    width: 100%;
                    border-collapse: collapse;
                    table-layout: fixed;
                }
                .ces-tbl thead tr,
                .ces-all-tbl thead tr {
                    background: var(--control-bg, #f0f2f5);
                    border-bottom: 2px solid var(--border-color, #d1d8dd);
                }
                .ces-tbl thead th,
                .ces-all-tbl thead th {
                    padding: 9px 14px;
                    color: var(--text-muted, #4b5563);
                    font-size: 11px;
                    font-weight: 700;
                    text-align: left;
                    letter-spacing: .4px;
                    text-transform: uppercase;
                    white-space: nowrap;
                }
                .ces-tbl thead th.th-sr,
                .ces-all-tbl thead th.th-sr  { text-align: center; padding: 9px 0; }
                .ces-tbl thead th.th-ctc,
                .ces-all-tbl thead th.th-ctc { text-align: right; }
                .ces-tbl tbody tr:hover,
                .ces-all-tbl tbody tr:hover  { background: var(--bg-blue, #eef2ff) !important; }

                /* ── Smooth fade-in for popup body content ──────────── */
                @keyframes ces-fade-in {
                    from { opacity: 0; transform: translateY(6px); }
                    to   { opacity: 1; transform: translateY(0); }
                }
                .ces-popup-body {
                    animation: ces-fade-in 0.22s ease forwards;
                }
            `;
            document.head.appendChild(s);
        }

        // Event delegation — works even after KPI bar is re-injected on refresh
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

        if (column.fieldname === "company") {
            return `<span class="ces-company-link"
                         data-company="${frappe.utils.escape_html(data.company)}"
                         style="font-weight:600;color:var(--text-color,#1f272e);font-size:13px;cursor:pointer;">
                         ${data.company}
                    </span>`;
        }
        if (column.fieldname === "total_employees") {
            return `<span style="font-weight:600;color:var(--text-color,#1f272e);font-size:13px;">${data.total_employees || 0}</span>`;
        }
        if (column.fieldname === "salary_structure_assigned") {
            const v = data.salary_structure_assigned || 0;
            return `<span style="color:var(--green,#28a745);font-weight:600;font-size:13px;">${v}</span>`;
        }
        if (column.fieldname === "salary_structure_unassigned") {
            const v = data.salary_structure_unassigned || 0;
            const color = v > 0 ? "var(--red,#e03e3e)" : "var(--green,#28a745)";
            return `<span style="color:${color};font-weight:600;font-size:13px;">${v}</span>`;
        }
        if (column.fieldname === "total_ctc") {
            const v = parseFloat(data.total_ctc || 0);
            return `<span style="font-weight:600;color:var(--text-color,#1f272e);font-size:13px;">&#8377; ${ces_fmt(v)}</span>`;
        }
        return value;
    },
};

// ── Indian number formatter ───────────────────────────────────────────────────
function ces_fmt(num) {
    return parseFloat(num || 0).toLocaleString("en-IN", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    });
}

// ── Freeze / unfreeze helpers ─────────────────────────────────────────────────
function _ces_freeze(msg) {
    try {
        if (typeof frappe.freeze === "function") frappe.freeze(msg || __("Loading…"));
        else if (frappe.ui?.freeze)              frappe.ui.freeze(msg || __("Loading…"));
        else {
            if (!document.getElementById("ces-freeze-overlay")) {
                const el = document.createElement("div");
                el.id = "ces-freeze-overlay";
                el.style.cssText = "position:fixed;inset:0;z-index:9999;background:rgba(255,255,255,0.55);display:flex;align-items:center;justify-content:center;font-size:15px;font-weight:600;color:var(--primary,#4361ee);";
                el.textContent = msg || __("Loading…");
                document.body.appendChild(el);
            }
        }
    } catch (e) { console.warn("[CES] freeze failed:", e); }
}

function _ces_unfreeze() {
    try {
        if (typeof frappe.unfreeze === "function") frappe.unfreeze();
        else if (frappe.ui?.unfreeze)              frappe.ui.unfreeze();
        else document.getElementById("ces-freeze-overlay")?.remove();
    } catch (e) { console.warn("[CES] unfreeze failed:", e); }
}

// ── KPI bar (main report page) ────────────────────────────────────────────────
function _ces_inject_kpi_bar() {
    const summary     = frappe.query_report.report_summary || [];
    const report_data = frappe.query_report.data || [];

    let companies = 0, employees = 0, staff = 0, workers = 0, unassigned = 0;

    if (summary.length) {
        summary.forEach(item => {
            const lbl = (item.label || "").toLowerCase();
            const val = parseInt(item.value) || 0;
            if (lbl.includes("compan"))   companies  = val;
            if (lbl.includes("employee")) employees  = val;
            if (lbl.includes("staff"))    staff      = val;
            if (lbl.includes("worker"))   workers    = val;
            if (lbl.includes("unassign")) unassigned = val;
        });
    }

    if (!companies && report_data.length) {
        companies  = report_data.length;
        employees  = report_data.reduce((s, r) => s + (r.total_employees || 0), 0);
        staff      = report_data.reduce((s, r) => s + (r.total_staff || 0), 0);
        workers    = report_data.reduce((s, r) => s + (r.total_workers || 0), 0);
        unassigned = report_data.reduce((s, r) => s + (r.salary_structure_unassigned || 0), 0);
    }

    const cards = [
        { label: "Number of Companies",  value: companies,  color: "var(--primary,#4361ee)",    action: null },
        { label: "Number of Employees",  value: employees,  color: "var(--teal,#2ec4b6)",        action: "all" },
        { label: "Number of Staff",      value: staff,      color: "var(--purple,#7b2d8b)",      action: "staff" },
        { label: "Number of Workers",    value: workers,    color: "var(--orange,#f4a261)",      action: "worker" },
        { label: "Unassigned Employees", value: unassigned, color: "var(--red-avatar,#e63946)",  action: "unassigned" },
    ];

    const cards_html = cards.map(c => `
        <div class="ces-sc-card${c.action ? " ces-sc-clickable" : ""}"
             ${c.action ? `data-ces-action="${c.action}"` : ""}>
            <span class="ces-sc-lbl">${c.label}</span>
            <span class="ces-sc-val" style="color:${c.color};">${c.value}</span>
        </div>
    `).join("");

    $("#ces-kpi-bar").remove();
    const $bar = $(`<div id="ces-kpi-bar">${cards_html}</div>`);

    const $target = $(".report-wrapper, .datatable-wrapper, .frappe-datatable").first();
    if ($target.length) $target.before($bar);
    else $(".page-content .report-area, .report-area, .page-content").first().prepend($bar);
}

// ── Company row click → per-company popup ─────────────────────────────────────
$(document).on("click", ".ces-company-link", function (e) {
    e.preventDefault();
    const company  = $(this).data("company");
    const category = frappe.query_report.get_filter_value("category") || null;
    _load_company_popup(company, category, null);
});

// ── Persistent dialog references (prevents close/reopen jumps) ───────────────
let _ces_company_dialog = null;
let _ces_all_dialog     = null;

// ── Per-company popup ─────────────────────────────────────────────────────────
function _load_company_popup(company, category, filter_mode) {
    frappe.call({
        method: "saral_hr.saral_hr.report.company_enrollment_summary.company_enrollment_summary.get_company_employees",
        args: { company, category },
        freeze: true,
        freeze_message: __("Fetching employees…"),
        callback(r) {
            if (r.exc) { frappe.msgprint(__("Error loading employees.")); return; }
            _show_company_popup(company, r.message || [], filter_mode);
        },
    });
}

function _show_company_popup(company, all_employees, filter_mode) {
    const total      = all_employees.length;
    const assigned   = all_employees.filter(e => e.salary_structure !== "Not Assigned").length;
    const unassigned = total - assigned;
    const total_ctc  = all_employees.reduce((s, e) => s + (parseFloat(e.annual_ctc) || 0), 0);

    let employees = all_employees;
    if (filter_mode === "assigned")   employees = all_employees.filter(e => e.salary_structure !== "Not Assigned");
    if (filter_mode === "unassigned") employees = all_employees.filter(e => e.salary_structure === "Not Assigned");

    const body_html = _build_company_popup_body(
        company, employees, total, assigned, unassigned, total_ctc, filter_mode
    );

    // ── If dialog open: swap content in-place (no close/reopen = no jump) ────
    if (_ces_company_dialog && _ces_company_dialog.$wrapper?.is(":visible")) {
        _ces_company_dialog.set_title(`${company} — Employee Details`);
        _ces_swap_content(_ces_company_dialog, body_html);

        // Re-bind KPI card clicks after swap
        setTimeout(() => _bind_company_kpi_clicks(_ces_company_dialog, company, all_employees), 200);
        return;
    }

    // ── Fresh dialog ──────────────────────────────────────────────────────────
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
        _bind_company_kpi_clicks(d, company, all_employees);
    }, 60);
}

function _bind_company_kpi_clicks(dialog, company, all_employees) {
    dialog.$wrapper.find(".ces-kpi-card[data-filter]").off("click.ces").on("click.ces", function () {
        const f = $(this).data("filter");
        _show_company_popup(company, all_employees, f === "all" ? null : f);
    });
}

function _build_company_popup_body(company, employees, total, assigned, unassigned, total_ctc, filter_mode) {
    const rows_html = employees.length
        ? employees.map((emp, i) => {
            const ctc_str = emp.annual_ctc
                ? `&#8377; ${ces_fmt(emp.annual_ctc)}`
                : `<span style="color:var(--red,#e03e3e);font-weight:600;">—</span>`;

            const badge = emp.salary_structure === "Not Assigned"
                ? `<span style="background:var(--red-highlight,#fff5f5);color:var(--red,#e03e3e);
                               border:1px solid var(--red-border,#ffd5d5);
                               padding:2px 10px;border-radius:4px;font-size:11px;font-weight:500;white-space:nowrap;">
                               ✕ Not Assigned</span>`
                : `<span style="background:var(--green-highlight,#eafaf1);color:var(--green,#28a745);
                               border:1px solid var(--green-border,#c3e6cb);
                               padding:2px 10px;border-radius:4px;font-size:11px;font-weight:500;white-space:nowrap;">
                               ✓ ${emp.salary_structure}</span>`;

            const row_bg = i % 2 === 0 ? "var(--card-bg,#fff)" : "var(--control-bg-input,#f8fafc)";
            return `
            <tr style="background:${row_bg};border-bottom:1px solid var(--border-color,#d1d8dd);">
                <td style="padding:9px 0;color:var(--text-muted,#8d99a6);font-size:12px;width:44px;text-align:center;vertical-align:middle;">${i + 1}</td>
                <td style="padding:9px 14px;vertical-align:middle;max-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">
                    <div style="font-weight:500;color:var(--text-color,#1f272e);font-size:13px;line-height:1.4;">${emp.full_name}</div>
                    <div style="font-size:11px;color:var(--text-muted,#8d99a6);margin-top:1px;">${emp.employee}</div>
                </td>
                <td style="padding:9px 14px;white-space:nowrap;vertical-align:middle;">
                    <span style="background:var(--control-bg,#f0f2f5);color:var(--text-muted,#6c7680);padding:2px 9px;border-radius:4px;font-size:11px;font-weight:500;border:1px solid var(--border-color,#d1d8dd);">${emp.category}</span>
                </td>
                <td style="padding:9px 14px;white-space:nowrap;vertical-align:middle;">${badge}</td>
                <td style="padding:9px 14px;text-align:right;font-weight:500;color:var(--text-color,#1f272e);font-size:13px;white-space:nowrap;vertical-align:middle;">${ctc_str}</td>
            </tr>`;
        }).join("")
        : `<tr><td colspan="5" style="text-align:center;padding:40px;color:var(--text-muted,#8d99a6);font-size:13px;">No employees found</td></tr>`;

    const filter_label = filter_mode === "assigned"
        ? `<span style="background:var(--green-highlight,#eafaf1);color:var(--green,#28a745);border:1px solid var(--green-border,#c3e6cb);padding:1px 10px;border-radius:10px;font-size:11px;font-weight:500;margin-left:8px;">Assigned only</span>`
        : filter_mode === "unassigned"
        ? `<span style="background:var(--red-highlight,#fff5f5);color:var(--red,#e03e3e);border:1px solid var(--red-border,#ffd5d5);padding:1px 10px;border-radius:10px;font-size:11px;font-weight:500;margin-left:8px;">Unassigned only</span>`
        : "";

    return `
    <div class="ces-popup-body">
        <div style="display:flex;gap:10px;margin-bottom:16px;flex-wrap:wrap;">
            <div class="ces-kpi-card clickable ${!filter_mode ? "active-filter" : ""}" data-filter="all" title="Show all">
                <span class="ces-kpi-lbl">Total</span>
                <span class="ces-kpi-val" style="color:var(--primary,#4361ee);">${total}</span>
            </div>
            <div class="ces-kpi-card clickable ${filter_mode === "assigned" ? "active-filter" : ""}" data-filter="assigned" title="Show assigned only">
                <span class="ces-kpi-lbl">Assigned</span>
                <span class="ces-kpi-val" style="color:var(--green,#28a745);">${assigned}</span>
            </div>
            <div class="ces-kpi-card clickable ${filter_mode === "unassigned" ? "active-filter" : ""}" data-filter="unassigned" title="Show unassigned only">
                <span class="ces-kpi-lbl">Unassigned</span>
                <span class="ces-kpi-val" style="color:var(--red,#e03e3e);">${unassigned}</span>
            </div>
            <div class="ces-kpi-card" style="flex:2;min-width:180px;">
                <span class="ces-kpi-lbl">Total Annual CTC</span>
                <span class="ces-kpi-val" style="color:var(--text-color,#1f272e);font-size:20px;">&#8377; ${ces_fmt(total_ctc)}</span>
            </div>
        </div>
        <div style="display:flex;align-items:center;margin-bottom:8px;">
            <span style="font-size:11px;font-weight:700;color:var(--text-muted,#4b5563);text-transform:uppercase;letter-spacing:.6px;">Employees</span>
            ${filter_label}
        </div>
        <div style="border:1px solid var(--border-color,#d1d8dd);border-radius:6px;overflow:hidden;background:var(--card-bg,#fff);">
            <table class="ces-tbl">
                <colgroup>
                    <col style="width:44px">
                    <col>
                    <col style="width:110px">
                    <col style="width:210px">
                    <col style="width:150px">
                </colgroup>
                <thead><tr>
                    <th class="th-sr">#</th>
                    <th>Employee</th>
                    <th>Category</th>
                    <th>Salary Structure</th>
                    <th class="th-ctc">Annual CTC</th>
                </tr></thead>
                <tbody>${rows_html}</tbody>
            </table>
        </div>
        <div style="margin-top:10px;font-size:11px;color:var(--text-muted,#8d99a6);">
            Showing <strong style="color:var(--text-color,#1f272e);">${employees.length}</strong>
            of <strong style="color:var(--text-color,#1f272e);">${total}</strong>
            employee(s) for <strong style="color:var(--text-color,#1f272e);">${company}</strong>
        </div>
    </div>`;
}

// ── All-employees popup (from main KPI bar) ───────────────────────────────────
function _load_all_employees_popup(action) {
    const category       = frappe.query_report.get_filter_value("category") || null;
    const company_filter = frappe.query_report.get_filter_value("company") || null;
    const report_data    = frappe.query_report.data || [];

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
        let all_employees = results.flat();
        if (action === "unassigned") {
            all_employees = all_employees.filter(e => e.salary_structure === "Not Assigned");
        }
        _show_all_employees_popup(all_employees, action);
    }).catch(err => {
        _ces_unfreeze();
        console.error("[CES] Error fetching employees:", err);
        frappe.msgprint(__("Error fetching employees. Please try again."));
    });
}

function _show_all_employees_popup(all_employees, action) {
    const total     = all_employees.length;
    const total_ctc = all_employees.reduce((s, e) => s + (parseFloat(e.annual_ctc) || 0), 0);

    const title_map = {
        all:        __("All Employees"),
        staff:      __("Staff Employees"),
        worker:     __("Worker Employees"),
        unassigned: __("Unassigned Employees"),
    };
    const popup_title = title_map[action] || __("All Employees");

    const rows_html = all_employees.length
        ? all_employees.map((emp, i) => {
            const ctc_str = emp.annual_ctc
                ? `&#8377; ${ces_fmt(emp.annual_ctc)}`
                : `<span style="color:var(--red,#e03e3e);font-weight:600;">—</span>`;

            const badge = emp.salary_structure === "Not Assigned"
                ? `<span style="background:var(--red-highlight,#fff5f5);color:var(--red,#e03e3e);
                               border:1px solid var(--red-border,#ffd5d5);
                               padding:2px 10px;border-radius:4px;font-size:11px;font-weight:500;white-space:nowrap;">
                               ✕ Not Assigned</span>`
                : `<span style="background:var(--green-highlight,#eafaf1);color:var(--green,#28a745);
                               border:1px solid var(--green-border,#c3e6cb);
                               padding:2px 10px;border-radius:4px;font-size:11px;font-weight:500;white-space:nowrap;">
                               ✓ ${emp.salary_structure}</span>`;

            const row_bg = i % 2 === 0 ? "var(--card-bg,#fff)" : "var(--control-bg-input,#f8fafc)";
            return `
            <tr style="background:${row_bg};border-bottom:1px solid var(--border-color,#d1d8dd);">
                <td style="padding:9px 0;color:var(--text-muted,#8d99a6);font-size:12px;width:44px;text-align:center;vertical-align:middle;">${i + 1}</td>
                <td style="padding:9px 14px;vertical-align:middle;max-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">
                    <div style="font-weight:500;color:var(--text-color,#1f272e);font-size:13px;line-height:1.4;">${emp.full_name}</div>
                    <div style="font-size:11px;color:var(--text-muted,#8d99a6);margin-top:1px;">${emp.employee}</div>
                </td>
                <td style="padding:9px 14px;vertical-align:middle;white-space:nowrap;">
                    <span style="background:var(--control-bg,#f0f2f5);color:var(--text-muted,#6c7680);padding:2px 9px;border-radius:4px;font-size:11px;font-weight:500;border:1px solid var(--border-color,#d1d8dd);">${emp.company}</span>
                </td>
                <td style="padding:9px 14px;vertical-align:middle;white-space:nowrap;">
                    <span style="background:var(--control-bg,#f0f2f5);color:var(--text-muted,#6c7680);padding:2px 9px;border-radius:4px;font-size:11px;font-weight:500;border:1px solid var(--border-color,#d1d8dd);">${emp.category}</span>
                </td>
                <td style="padding:9px 14px;white-space:nowrap;vertical-align:middle;">${badge}</td>
                <td style="padding:9px 14px;text-align:right;font-weight:500;color:var(--text-color,#1f272e);font-size:13px;white-space:nowrap;vertical-align:middle;">${ctc_str}</td>
            </tr>`;
        }).join("")
        : `<tr><td colspan="6" style="text-align:center;padding:40px;color:var(--text-muted,#8d99a6);font-size:13px;">No employees found</td></tr>`;

    const body_html = `
    <div class="ces-popup-body">
        <div style="display:flex;align-items:center;margin-bottom:10px;gap:10px;">
            <span style="font-size:11px;font-weight:700;color:var(--text-muted,#4b5563);text-transform:uppercase;letter-spacing:.6px;">${popup_title}</span>
            <span style="font-size:11px;color:var(--text-muted,#8d99a6);">
                — <strong style="color:var(--text-color,#1f272e);">${total}</strong> employee(s)
                &nbsp;|&nbsp; Total CTC: <strong style="color:var(--text-color,#1f272e);">&#8377; ${ces_fmt(total_ctc)}</strong>
            </span>
        </div>
        <div style="border:1px solid var(--border-color,#d1d8dd);border-radius:6px;overflow:hidden;background:var(--card-bg,#fff);">
            <table class="ces-all-tbl">
                <colgroup>
                    <col style="width:44px">
                    <col>
                    <col style="width:160px">
                    <col style="width:90px">
                    <col style="width:180px">
                    <col style="width:130px">
                </colgroup>
                <thead><tr>
                    <th class="th-sr">#</th>
                    <th>Employee Name</th>
                    <th>Company</th>
                    <th>Category</th>
                    <th>Salary Structure</th>
                    <th class="th-ctc">Annual CTC</th>
                </tr></thead>
                <tbody>${rows_html}</tbody>
            </table>
        </div>
    </div>`;

    // ── In-place update if dialog already open (no jump) ─────────────────────
    if (_ces_all_dialog && _ces_all_dialog.$wrapper?.is(":visible")) {
        _ces_all_dialog.set_title(popup_title);
        _ces_swap_content(_ces_all_dialog, body_html);
        return;
    }

    // ── Fresh dialog ──────────────────────────────────────────────────────────
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

// ── Helper: swap dialog HTML content with a smooth fade ──────────────────────
function _ces_swap_content(dialog, new_html) {
    const $body = dialog.$wrapper.find("[data-fieldname='content']");
    $body.css({ opacity: 0, transition: "opacity 0.15s ease" });

    setTimeout(() => {
        dialog.fields_dict.content.$wrapper.html(new_html);
        _ces_style_modal(dialog);
        // Force animation replay
        const el = dialog.$wrapper.find(".ces-popup-body")[0];
        if (el) { el.style.animation = "none"; el.offsetHeight; el.style.animation = ""; }
        $body.css({ opacity: 1 });
    }, 160);
}

// ── Helper: style the modal body ──────────────────────────────────────────────
function _ces_style_modal(dialog) {
    dialog.$wrapper.find(".modal-body").css({
        padding:    "16px 20px",
        background: "var(--bg-color, #f8f9fa)",
    });
}