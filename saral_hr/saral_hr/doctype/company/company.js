// Copyright (c) 2026, sj and contributors
// For license information, please see license.txt

// ─────────────────────────────────────────────────────────────
//  CSS injection — permanently hides the native Frappe grid
//  Production-safe: works whether rows exist or not
//  Injected once per page-change event, persists until browser reload
// ─────────────────────────────────────────────────────────────
$(document).on("page-change", function () {
    if ($("#esic-pf-grid-hide-style").length) return; // Style already injected — skip
    var css = [
        // Hide all native grid elements for both child table fields
        '[data-fieldname="esic_dependent_component"] .grid-row,',
        '[data-fieldname="esic_dependent_component"] .grid-heading-row,',
        '[data-fieldname="esic_dependent_component"] .grid-footer,',
        '[data-fieldname="esic_dependent_component"] .grid-add-row,',
        '[data-fieldname="esic_dependent_component"] .form-grid-container,',
        '[data-fieldname="esic_dependent_component"] .frappe-control,',
        '[data-fieldname="esic_dependent_component"] .grid-body,',
        '[data-fieldname="esic_dependent_component"] .no-data-message,',
        '[data-fieldname="pf_dependent_component"] .grid-row,',
        '[data-fieldname="pf_dependent_component"] .grid-heading-row,',
        '[data-fieldname="pf_dependent_component"] .grid-footer,',
        '[data-fieldname="pf_dependent_component"] .grid-add-row,',
        '[data-fieldname="pf_dependent_component"] .form-grid-container,',
        '[data-fieldname="pf_dependent_component"] .frappe-control,',
        '[data-fieldname="pf_dependent_component"] .grid-body,',
        '[data-fieldname="pf_dependent_component"] .no-data-message',
        '{ display: none !important; }'
    ].join(" ");
    $("head").append('<style id="esic-pf-grid-hide-style">' + css + '</style>');
});

frappe.ui.form.on("Company", {
    refresh(frm) {
        render_esic_period_ui(frm);
        render_pf_period_ui(frm);
        render_salary_calc_description(frm);
        render_salary_calc_preview(frm);
    },
    salary_calculation_based_on(frm) {
        render_salary_calc_description(frm);
        render_salary_calc_preview(frm);
    }
});

// ─────────────────────────────────────────────────────────────
//  Date helpers
// ─────────────────────────────────────────────────────────────

function to_display(date_str) {
    if (!date_str) return "";
    return frappe.datetime.str_to_user(date_str);
}

function to_backend(display_str) {
    if (!display_str) return null;
    return frappe.datetime.user_to_str(display_str);
}

function parse_components(row) {
    try {
        const arr = JSON.parse(row.wage_components || "[]");
        return Array.isArray(arr) ? arr : [];
    } catch(e) { return []; }
}

// ─────────────────────────────────────────────────────────────
//  SSA lock helpers
// ─────────────────────────────────────────────────────────────

function _fetch_ssa_dates(frm) {
    return frappe.db.get_list("Salary Structure Assignment", {
        filters: { company: frm.doc.company, docstatus: 1 },
        fields: ["from_date"],
        limit: 0
    }).then(rows => rows.map(r => r.from_date));
}

function _is_period_locked(row, ssa_dates) {
    if (!ssa_dates || !ssa_dates.length) return false;
    // Period is locked if any submitted SSA from_date falls within this period's date range
    return ssa_dates.some(d => {
        const from_ok = !row.from_date || d >= row.from_date;
        const to_ok   = !row.to_date   || d <= row.to_date;
        return from_ok && to_ok;
    });
}

// ─────────────────────────────────────────────────────────────
//  ESIC UI
// ─────────────────────────────────────────────────────────────

function render_esic_period_ui(frm) {
    _fetch_ssa_dates(frm).then(ssa_dates => render_period_ui(frm, {
        fieldname:         "esic_dependent_component",
        label:             "ESIC",
        border_color:      "#1565c0",
        bg_color:          "#e3f2fd",
        text_color:        "#0d47a1",
        description:       "Add the Earning components used to compute the ESIC wage basis. Formula: sum of all listed components (e.g. Basic + DA + HRA). No cap is applied — esic_wage_limit is for reference only.",
        rates_title:       "ESIC Rates & Limit",
        rates_description: "Reference only — ESIC wage limit is NOT used in calculation. Contribution percentages below are applied to the full sum of listed components.",
        rate_groups: [
            {
                fields: [
                    { key: "esic_wage_limit",      label: "ESIC Wage Limit (Reference Only)", placeholder: "21000", suffix: "₹" },
                    { key: "employee_contribution", label: "Employee %",                       placeholder: "0.75",  suffix: "%" },
                    { key: "employer_contribution", label: "Employer %",                       placeholder: "3.25",  suffix: "%" }
                ]
            }
        ]
    }, ssa_dates));
}

// ─────────────────────────────────────────────────────────────
//  PF UI
// ─────────────────────────────────────────────────────────────

function render_pf_period_ui(frm) {
    _fetch_ssa_dates(frm).then(ssa_dates => render_period_ui(frm, {
        fieldname:         "pf_dependent_component",
        label:             "PF",
        border_color:      "#2e7d32",
        bg_color:          "#e8f5e9",
        text_color:        "#1b5e20",
        description:       "Add the Earning components used to compute the PF wage basis. Formula: sum of all listed components. For Limited PF employees the result is capped at the wage limit below.",
        rates_title:       "PF Rates & Limit",
        rates_description: "Wage limit applies only for Limited PF employees. Leave blank for no cap (Full PF).",
        rate_groups: [
            {
                fields: [
                    { key: "pf_wage_limit",    label: "Limited PF Wage Limit", placeholder: "15000", suffix: "₹" }
                ]
            },
            {
                fields: [
                    { key: "employee_percent", label: "Employee PF %",          placeholder: "12",    suffix: "%" }
                ]
            },
            {
                fields: [
                    { key: "employer_epf",     label: "Employer EPF %",         placeholder: "3.67",  suffix: "%" },
                    { key: "employer_eps",     label: "Employer EPS %",         placeholder: "8.33",  suffix: "%" }
                ]
            },
            {
                fields: [
                    { key: "edli_insurance",   label: "Employee EDLI Insurance %", placeholder: "0.5", suffix: "%" },
                    { key: "admin_charges",    label: "Employer Admin Charges %",  placeholder: "0.5", suffix: "%" }
                ]
            }
        ]
    }, ssa_dates));
}

// ─────────────────────────────────────────────────────────────
//  Generic renderer — 1 child row = 1 complete period
// ─────────────────────────────────────────────────────────────

function render_period_ui(frm, cfg, ssa_dates = []) {
    const { fieldname, label, border_color, bg_color, text_color, description, rates_title, rates_description, rate_groups } = cfg;

    const field = frm.fields_dict[fieldname];
    if (!field) return;

    // Always hide the native Frappe grid wrapper — regardless of whether rows exist
    field.grid.wrapper.hide();

    const $wrapper = field.$wrapper;

    const uid = `${fieldname}-period-ui`;
    $wrapper.find(`#${uid}`).remove();

    const rows = frm.doc[fieldname] || [];

    // Flat list of all rate fields across all rate groups
    const all_rate_fields = rate_groups.flatMap(g => g.fields);

    // Build rate summary HTML for display in the table cell
    function rate_summary(row) {
        const parts = all_rate_fields
            .filter(f => row[f.key])
            .map(f => {
                const val = f.suffix === "₹"
                    ? `₹${parseFloat(row[f.key] || 0).toLocaleString("en-IN", {minimumFractionDigits:2, maximumFractionDigits:2})}`
                    : `${parseFloat(row[f.key] || 0)}%`;
                return `<span style="white-space:nowrap;font-size:11px">
                            <b style="color:#888">${f.label}:</b> ${val}
                        </span>`;
            });
        return parts.length
            ? `<div style="display:flex;flex-wrap:wrap;gap:3px 10px">${parts.join("")}</div>`
            : `<span style="color:#ccc;font-size:11px">—</span>`;
    }

    // Build table row HTML for each period
    let tbody_html = "";
    rows.forEach((row, i) => {
        const components = parse_components(row);
        const locked     = _is_period_locked(row, ssa_dates);

        const tags = components.map(c =>
            `<span style="display:inline-block;background:${bg_color};
                border:0.5px solid ${border_color}55;color:${text_color};
                border-radius:3px;padding:2px 8px;font-size:11px;margin:1px 2px 1px 0">
                ${frappe.utils.escape_html(c)}</span>`
        ).join("") || `<span style="color:#ccc;font-size:11px">—</span>`;

        const action_html = locked
            ? `<span style="color:#f59e0b;font-size:14px;margin-right:4px"
                   title="Locked — Salary Structure Assignment exists">🔒</span>
               <span class="edit-todate" data-idx="${i}"
                   style="cursor:pointer;color:${border_color};font-size:13px"
                   title="Edit To Date only">✏</span>`
            : `<span class="edit-period" data-idx="${i}"
                   style="cursor:pointer;color:${border_color};font-size:13px;margin-right:6px"
                   title="Edit">✏</span>
               <span class="delete-period" data-idx="${i}"
                   style="cursor:pointer;color:#e53935;font-size:13px"
                   title="Delete">✕</span>`;

        const row_bg = locked ? "background:#fffbeb" : "";

        tbody_html += `
        <tr style="${row_bg}">
            <td style="padding:6px 8px;border:0.5px solid #e0e0e0;color:#999;
                       font-size:12px;vertical-align:top">${i + 1}</td>
            <td style="padding:6px 8px;border:0.5px solid #e0e0e0;font-size:12px;
                       white-space:nowrap;vertical-align:top">${to_display(row.from_date) || "—"}</td>
            <td style="padding:6px 8px;border:0.5px solid #e0e0e0;font-size:12px;
                       white-space:nowrap;vertical-align:top">${to_display(row.to_date) || "—"}</td>
            <td style="padding:6px 8px;border:0.5px solid #e0e0e0;vertical-align:top">${tags}</td>
            <td style="padding:6px 8px;border:0.5px solid #e0e0e0;vertical-align:top">
                ${rate_summary(row)}
            </td>
            <td style="padding:6px 8px;border:0.5px solid #e0e0e0;text-align:center;
                       white-space:nowrap;vertical-align:top">
                ${action_html}
            </td>
        </tr>`;
    });

    const table_html = tbody_html
        ? `<table style="width:100%;border-collapse:collapse;margin-bottom:6px">
            <thead><tr style="background:#f5f5f5">
                <th style="padding:6px 8px;border:0.5px solid #e0e0e0;font-size:11px;font-weight:500;color:#666;width:36px">No.</th>
                <th style="padding:6px 8px;border:0.5px solid #e0e0e0;font-size:11px;font-weight:500;color:#666;width:100px">From</th>
                <th style="padding:6px 8px;border:0.5px solid #e0e0e0;font-size:11px;font-weight:500;color:#666;width:100px">To</th>
                <th style="padding:6px 8px;border:0.5px solid #e0e0e0;font-size:11px;font-weight:500;color:#666">Components</th>
                <th style="padding:6px 8px;border:0.5px solid #e0e0e0;font-size:11px;font-weight:500;color:#666">Rates</th>
                <th style="padding:6px 8px;border:0.5px solid #e0e0e0;width:55px"></th>
            </tr></thead>
            <tbody>${tbody_html}</tbody>
           </table>`
        : `<div style="font-size:12px;color:#999;margin-bottom:8px">No periods configured yet.</div>`;

    // Build rate input fields HTML — flat 3-column grid layout
    const all_flat_fields = rate_groups.flatMap(g => g.fields);
    const rates_html = `
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px 12px">
            ${all_flat_fields.map(f => `
                <div>
                    <div style="font-size:11px;color:#888;margin-bottom:3px">
                        ${f.label} <span style="color:#bbb">(${f.suffix})</span>
                    </div>
                    <input type="number" step="0.01" class="rate-field" data-key="${f.key}"
                           placeholder="${f.placeholder}"
                           style="width:100%;border:0.5px solid #ccc;border-radius:4px;
                                  padding:5px 8px;font-size:12px;box-sizing:border-box">
                </div>`).join("")}
        </div>`;

    // Render the complete custom period UI
    const $ui = $(`
    <div id="${uid}" style="margin:8px 0 12px 0">
        ${description ? `<div style="font-size:12px;color:#6c757d;margin-bottom:8px">${description}</div>` : ""}
        <div class="period-table-wrap">${table_html}</div>

        <button class="add-period-btn"
            style="display:flex;align-items:center;gap:5px;padding:5px 10px;
                   border:0.5px dashed #aaa;border-radius:5px;color:${border_color};
                   font-size:12px;cursor:pointer;background:transparent;margin-top:4px">
            + New ${label} Period
        </button>

        <div class="add-period-form" style="display:none;border:1.5px solid ${border_color};
             border-radius:7px;padding:14px 16px;margin-top:8px;background:#fff">

            <div style="font-size:12px;font-weight:600;color:${border_color};margin-bottom:12px">
                📅 New ${label} Period
            </div>

            <!-- Dates -->
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:12px">
                <div>
                    <div style="font-size:11px;color:#888;margin-bottom:3px">From Date</div>
                    <input type="text" class="period-from-date" placeholder="DD-MM-YYYY"
                        style="width:100%;border:0.5px solid #ccc;border-radius:4px;
                               padding:5px 8px;font-size:12px;box-sizing:border-box">
                </div>
                <div>
                    <div style="font-size:11px;color:#888;margin-bottom:3px">To Date</div>
                    <input type="text" class="period-to-date" placeholder="DD-MM-YYYY"
                        style="width:100%;border:0.5px solid #ccc;border-radius:4px;
                               padding:5px 8px;font-size:12px;box-sizing:border-box">
                </div>
            </div>

            <!-- Components -->
            <div style="border:0.5px solid #e0e0e0;border-radius:5px;
                        padding:8px 10px;margin-bottom:12px">
                <div style="font-size:11px;font-weight:600;color:${text_color};margin-bottom:6px">
                    Wage Components
                </div>
                <div class="checkbox-list" style="font-size:12px;color:#999">Loading...</div>
            </div>

            <!-- Rates -->
            <div style="border:0.5px solid ${border_color}44;border-radius:5px;
                        padding:10px 12px;margin-bottom:12px;background:${bg_color}55">
                <div style="font-size:11px;font-weight:600;color:${text_color};margin-bottom:4px">
                    ${rates_title || "Rates & Limits"}
                </div>
                ${rates_description ? `<div style="font-size:11px;color:#888;margin-bottom:10px">${rates_description}</div>` : ""}
                ${rates_html}
            </div>

            <div style="display:flex;gap:8px;justify-content:flex-end">
                <button class="cancel-period-btn"
                    style="padding:5px 13px;border-radius:4px;font-size:12px;cursor:pointer;
                           border:0.5px solid #ccc;background:transparent;color:#666">Cancel</button>
                <button class="save-period-btn"
                    style="padding:5px 13px;border-radius:4px;font-size:12px;cursor:pointer;
                           border:0.5px solid ${border_color};background:${border_color};color:#fff">
                    Save Period</button>
            </div>
        </div>
    </div>`);

    $wrapper.append($ui);

    // Initialize datepicker on date input fields
    $ui.find(".period-from-date, .period-to-date").datepicker({
        language: frappe.boot.lang || "en",
        autoClose: true,
        dateFormat: "dd-mm-yyyy"
    });

    // Load all Earning type Salary Components into the checkbox list
    frappe.db.get_list("Salary Component", {
        filters: { type: "Earning" }, fields: ["name"], limit: 0
    }).then(results => {
        const $list = $ui.find(".checkbox-list");
        $list.empty();
        $list.css({ display: "grid", "grid-template-columns": "repeat(auto-fill,minmax(180px,1fr))", gap: "3px" });
        results.forEach(r => {
            $list.append(`
                <label style="display:flex;align-items:center;gap:6px;font-size:12px;
                              cursor:pointer;color:#444;padding:2px 0">
                    <input type="checkbox" value="${frappe.utils.escape_html(r.name)}"
                           style="accent-color:${border_color}">
                    ${frappe.utils.escape_html(r.name)}
                </label>`);
        });
    });

    // Show the add period form when the button is clicked
    $ui.find(".add-period-btn").on("click", function () {
        $(this).hide();
        $ui.find(".add-period-form").slideDown(150);
    });

    // Hide the form and reset all inputs on cancel
    $ui.find(".cancel-period-btn").on("click", () => _reset_form($ui));

    // Collect form values and add a new child row to the document
    $ui.find(".save-period-btn").on("click", function () {
        const selected = [];
        $ui.find(".checkbox-list input:checked").each(function () {
            selected.push($(this).val());
        });

        if (!selected.length) {
            frappe.msgprint(__("Please select at least one Wage Component."));
            return;
        }

        const row = frappe.model.add_child(frm.doc, "Statutory Wage Component", fieldname);
        row.from_date       = to_backend($ui.find(".period-from-date").val().trim()) || null;
        row.to_date         = to_backend($ui.find(".period-to-date").val().trim())   || null;
        row.wage_components = JSON.stringify(selected);

        $ui.find(".rate-field").each(function () {
            const key = $(this).data("key");
            const val = $(this).val();
            if (val !== "") row[key] = parseFloat(val) || 0;
        });

        frm.dirty();
        frm.refresh_field(fieldname);
        render_period_ui(frm, cfg, ssa_dates);
    });

    // Remove the period row at the given index
    $ui.find(".delete-period").on("click", function () {
        const idx = parseInt($(this).data("idx"));
        frappe.confirm(__("Delete this {0} period?", [label]), () => {
            frm.doc[fieldname].splice(idx, 1);
            frm.dirty();
            frm.refresh_field(fieldname);
            render_period_ui(frm, cfg, ssa_dates);
        });
    });

    // Populate form with existing row data for editing
    $ui.find(".edit-period").on("click", function () {
        const idx = parseInt($(this).data("idx"));
        const row = (frm.doc[fieldname] || [])[idx];
        if (!row) return;

        const components = parse_components(row);
        frm.doc[fieldname].splice(idx, 1);
        frm.refresh_field(fieldname);

        $ui.find(".period-from-date").val(to_display(row.from_date));
        $ui.find(".period-to-date").val(to_display(row.to_date));

        const comp_set = new Set(components);
        setTimeout(() => {
            $ui.find(".checkbox-list input").each(function () {
                $(this).prop("checked", comp_set.has($(this).val()));
            });
        }, 300);

        $ui.find(".rate-field").each(function () {
            const key = $(this).data("key");
            if (row[key]) $(this).val(row[key]);
        });

        $ui.find(".add-period-btn").hide();
        $ui.find(".add-period-form").slideDown(150);
    });

    // For locked rows: allow editing only the To Date field via a prompt dialog
    $ui.find(".edit-todate").on("click", function () {
        const idx = parseInt($(this).data("idx"));
        const row = (frm.doc[fieldname] || [])[idx];
        if (!row) return;

        frappe.prompt(
            [{
                label: __("To Date"),
                fieldname: "to_date",
                fieldtype: "Date",
                default: row.to_date || ""
            }],
            (values) => {
                row.to_date = values.to_date || null;
                frm.dirty();
                frm.refresh_field(fieldname);
                render_period_ui(frm, cfg, ssa_dates);
            },
            __("Edit To Date — {0} Period", [label]),
            __("Update")
        );
    });
}

// ─────────────────────────────────────────────────────────────
//  Reset form
// ─────────────────────────────────────────────────────────────

function _reset_form($ui) {
    $ui.find(".add-period-form").slideUp(150, function () {
        $ui.find(".add-period-btn").show();
        $ui.find(".period-from-date, .period-to-date").val("");
        $ui.find(".checkbox-list input").prop("checked", false);
        $ui.find(".rate-field").val("");
    });
}

// ─────────────────────────────────────────────────────────────
//  Salary Calculation description (highlight selected option)
// ─────────────────────────────────────────────────────────────

const SALARY_CALC_DESCRIPTIONS = {
    exclude: {
        title: "Exclude Weekly Offs (Working Days)",
        body: "Payment days = Working days in month − Weekly offs − Absences. E.g. Jan 2026: 31 days, 4 Sundays → 27 working days − 1 absent = 26 payment days.",
    },
    include: {
        title: "Include Weekly Offs (Calendar Days)",
        body: "Payment days = Total calendar days − Absences. E.g. Jan 2026: 31 days − 1 absent = 30 payment days.",
    },
};

function render_salary_calc_description(frm) {
    const f = frm.fields_dict["salary_calculation_based_on"];
    if (!f || !f.$wrapper) return;

    const val = frm.doc.salary_calculation_based_on || "";
    const selected = val.includes("Include") ? "include" : "exclude";

    const blocks = ["exclude", "include"].map((key) => {
        const d = SALARY_CALC_DESCRIPTIONS[key];
        const active = key === selected;
        return `
            <div data-salary-desc="${key}" style="
                margin: 4px 0;
                padding: 8px 10px;
                border-radius: 4px;
                font-size: 12px;
                line-height: 1.55;
                background: ${active ? 'var(--bg-light-gray, #f3f3f3)' : 'transparent'};
                color: ${active ? 'var(--text-color, #1f272e)' : 'var(--text-muted, #6c757d)'};
                opacity: ${active ? 1 : 0.75};
            ">
                <b>${d.title}:</b> ${d.body}
            </div>`;
    }).join("");

    let $host = f.$wrapper.find("#salary-calc-description");
    if (!$host.length) {
        $host = $('<div id="salary-calc-description" style="margin-top:6px;"></div>');
        f.$wrapper.append($host);
    }
    $host.html(blocks);
}

// ─────────────────────────────────────────────────────────────
//  Salary Calculation preview banner
// ─────────────────────────────────────────────────────────────

function render_salary_calc_preview(frm) {
    const f = frm.fields_dict["salary_calculation_example"];
    if (!f || !f.$wrapper) return;

    const val     = frm.doc.salary_calculation_based_on || "";
    const include = val.includes("Include");
    const color   = include ? "#e8f5e9" : "#e3f2fd";
    const border  = include ? "#2e7d32" : "#1565c0";
    const tcol    = include ? "#1b5e20" : "#0d47a1";

    const example = include
        ? `Jan 2026 (31 days, 4 Sundays, 1 absent):<br>Payment days = 31 − 1 absent = <b>30</b>`
        : `Jan 2026 (31 days, 4 Sundays, 1 absent):<br>Working days = 31 − 4 Sundays = 27<br>Payment days = 27 − 1 absent = <b>26</b>`;

    f.$wrapper.html(`
        <div id="salary-calc-preview" style="margin:6px 0 10px 0;padding:9px 13px;
            background:${color};border-left:3px solid ${border};border-radius:4px;
            font-size:12px;color:${tcol};line-height:1.7;">
            <b>Example</b> &nbsp;·&nbsp; ${example}
        </div>`);
}