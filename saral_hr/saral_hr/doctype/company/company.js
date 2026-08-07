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
        '[data-fieldname="pf_dependent_component"] .no-data-message,',
        '[data-fieldname="pt_periods"] .grid-row,',
        '[data-fieldname="pt_periods"] .grid-heading-row,',
        '[data-fieldname="pt_periods"] .grid-footer,',
        '[data-fieldname="pt_periods"] .grid-add-row,',
        '[data-fieldname="pt_periods"] .form-grid-container,',
        '[data-fieldname="pt_periods"] .frappe-control,',
        '[data-fieldname="pt_periods"] .grid-body,',
        '[data-fieldname="pt_periods"] .no-data-message',
        '{ display: none !important; }'
    ].join(" ");
    $("head").append('<style id="esic-pf-grid-hide-style">' + css + '</style>');
});

frappe.ui.form.on("Company", {
    refresh(frm) {
        render_esic_period_ui(frm);
        render_pf_period_ui(frm);
        render_pt_period_ui(frm);
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
                   title="Locked — a Salary Structure Assignment exists in this period. Set To Date to close it, then Add Period with the updated wage components.">🔒</span>
               <span class="edit-todate" data-idx="${i}"
                   style="cursor:pointer;color:${border_color};font-size:13px"
                   title="Close period (edit To Date), then add a new period to change components">✏</span>`
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

    const any_locked = rows.some(row => _is_period_locked(row, ssa_dates));
    const lock_hint = any_locked
        ? `<div style="font-size:11px;color:#b45309;background:#fffbeb;border:0.5px solid #f59e0b55;
                border-radius:4px;padding:6px 8px;margin:0 0 8px 0;line-height:1.45">
                Locked periods cannot change wage components (an SSA exists in that date range).
                To include a new component (e.g. Production Incentive): set <b>To Date</b> on the
                locked period, then click <b>+ New ${label} Period</b> from the next day with the
                updated components.
           </div>`
        : "";

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
           </table>${lock_hint}`
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
//  Professional Tax UI
// ─────────────────────────────────────────────────────────────

const MAHARASHTRA_PT_SLABS = [
    { gender: "Male", from_amount: 0, to_amount: 7500, tax_amount: 0, february_amount: null },
    { gender: "Male", from_amount: 7501, to_amount: 10000, tax_amount: 175, february_amount: 275 },
    { gender: "Male", from_amount: 10001, to_amount: null, tax_amount: 200, february_amount: 300 },
    { gender: "Female", from_amount: 0, to_amount: 25000, tax_amount: 0, february_amount: null },
    { gender: "Female", from_amount: 25001, to_amount: null, tax_amount: 200, february_amount: null },
];

function parse_pt_slabs(row) {
    try {
        const arr = JSON.parse(row.slabs || "[]");
        return Array.isArray(arr) ? arr : [];
    } catch (e) {
        return [];
    }
}

function _pt_slab_summary(slabs) {
    if (!slabs.length) {
        return `<span style="color:#ccc;font-size:11px">—</span>`;
    }
    return slabs.map(s => {
        const to = s.to_amount == null || s.to_amount === "" ? "∞" : s.to_amount;
        const feb = s.february_amount == null || s.february_amount === ""
            ? ""
            : ` (Feb ₹${s.february_amount})`;
        return `<span style="display:inline-block;background:#f3e5f5;border:0.5px solid #7b1fa255;
            color:#4a148c;border-radius:3px;padding:2px 8px;font-size:11px;margin:1px 2px 1px 0">
            ${frappe.utils.escape_html(s.gender)}: ₹${s.from_amount}–${to} → ₹${s.tax_amount}${feb}
        </span>`;
    }).join("");
}

function _pt_slab_editor_html(slabs) {
    const rows = (slabs && slabs.length ? slabs : [{}]).map((s, i) => `
        <tr data-slab-idx="${i}">
            <td style="padding:4px">
                <select class="pt-slab-gender" style="width:100%;font-size:12px;padding:4px;border:0.5px solid #ccc;border-radius:4px">
                    <option value="Male" ${s.gender === "Male" ? "selected" : ""}>Male</option>
                    <option value="Female" ${s.gender === "Female" ? "selected" : ""}>Female</option>
                </select>
            </td>
            <td style="padding:4px">
                <input type="number" class="pt-slab-from" value="${s.from_amount ?? ""}"
                    style="width:100%;font-size:12px;padding:4px;border:0.5px solid #ccc;border-radius:4px;box-sizing:border-box">
            </td>
            <td style="padding:4px">
                <input type="number" class="pt-slab-to" value="${s.to_amount == null ? "" : s.to_amount}"
                    placeholder="open"
                    style="width:100%;font-size:12px;padding:4px;border:0.5px solid #ccc;border-radius:4px;box-sizing:border-box">
            </td>
            <td style="padding:4px">
                <input type="number" class="pt-slab-tax" value="${s.tax_amount ?? ""}"
                    style="width:100%;font-size:12px;padding:4px;border:0.5px solid #ccc;border-radius:4px;box-sizing:border-box">
            </td>
            <td style="padding:4px">
                <input type="number" class="pt-slab-feb" value="${s.february_amount == null ? "" : s.february_amount}"
                    placeholder="—"
                    style="width:100%;font-size:12px;padding:4px;border:0.5px solid #ccc;border-radius:4px;box-sizing:border-box">
            </td>
            <td style="padding:4px;text-align:center">
                <span class="pt-remove-slab" style="cursor:pointer;color:#e53935;font-size:13px" title="Remove">✕</span>
            </td>
        </tr>`).join("");

    return `
        <table style="width:100%;border-collapse:collapse;margin-bottom:6px">
            <thead><tr style="background:#f5f5f5">
                <th style="padding:4px 6px;font-size:11px;color:#666;text-align:left">Gender</th>
                <th style="padding:4px 6px;font-size:11px;color:#666;text-align:left">From (₹)</th>
                <th style="padding:4px 6px;font-size:11px;color:#666;text-align:left">To (₹)</th>
                <th style="padding:4px 6px;font-size:11px;color:#666;text-align:left">Tax (₹)</th>
                <th style="padding:4px 6px;font-size:11px;color:#666;text-align:left">Feb (₹)</th>
                <th style="width:28px"></th>
            </tr></thead>
            <tbody class="pt-slab-tbody">${rows}</tbody>
        </table>
        <button type="button" class="pt-add-slab"
            style="padding:3px 8px;font-size:11px;border:0.5px dashed #aaa;border-radius:4px;
                   background:transparent;cursor:pointer;color:#6a1b9a">+ Add Slab</button>`;
}

function _collect_pt_slabs($form) {
    const slabs = [];
    $form.find(".pt-slab-tbody tr").each(function () {
        const $tr = $(this);
        const toVal = $tr.find(".pt-slab-to").val().trim();
        const febVal = $tr.find(".pt-slab-feb").val().trim();
        slabs.push({
            gender: $tr.find(".pt-slab-gender").val() || "Male",
            from_amount: parseFloat($tr.find(".pt-slab-from").val()) || 0,
            to_amount: toVal === "" ? null : parseFloat(toVal),
            tax_amount: parseFloat($tr.find(".pt-slab-tax").val()) || 0,
            february_amount: febVal === "" ? null : parseFloat(febVal),
        });
    });
    return slabs;
}

function render_pt_period_ui(frm) {
    _fetch_ssa_dates(frm).then(ssa_dates => {
        const fieldname = "pt_periods";
        const field = frm.fields_dict[fieldname];
        if (!field) return;

        field.grid.wrapper.hide();
        const $wrapper = field.$wrapper;
        const uid = `${fieldname}-period-ui`;
        $wrapper.find(`#${uid}`).remove();

        const border_color = "#6a1b9a";
        const bg_color = "#f3e5f5";
        const text_color = "#4a148c";
        const rows = frm.doc[fieldname] || [];

        let tbody_html = "";
        rows.forEach((row, i) => {
            const slabs = parse_pt_slabs(row);
            const locked = _is_period_locked(row, ssa_dates);
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
                <td style="padding:6px 8px;border:0.5px solid #e0e0e0;color:#999;font-size:12px;vertical-align:top">${i + 1}</td>
                <td style="padding:6px 8px;border:0.5px solid #e0e0e0;font-size:12px;white-space:nowrap;vertical-align:top">${to_display(row.from_date) || "—"}</td>
                <td style="padding:6px 8px;border:0.5px solid #e0e0e0;font-size:12px;white-space:nowrap;vertical-align:top">${to_display(row.to_date) || "—"}</td>
                <td style="padding:6px 8px;border:0.5px solid #e0e0e0;font-size:12px;vertical-align:top">${row.age_exempt_years || 65}</td>
                <td style="padding:6px 8px;border:0.5px solid #e0e0e0;vertical-align:top">${_pt_slab_summary(slabs)}</td>
                <td style="padding:6px 8px;border:0.5px solid #e0e0e0;text-align:center;white-space:nowrap;vertical-align:top">${action_html}</td>
            </tr>`;
        });

        const table_html = tbody_html
            ? `<table style="width:100%;border-collapse:collapse;margin-bottom:6px">
                <thead><tr style="background:#f5f5f5">
                    <th style="padding:6px 8px;border:0.5px solid #e0e0e0;font-size:11px;font-weight:500;color:#666;width:36px">No.</th>
                    <th style="padding:6px 8px;border:0.5px solid #e0e0e0;font-size:11px;font-weight:500;color:#666;width:100px">From</th>
                    <th style="padding:6px 8px;border:0.5px solid #e0e0e0;font-size:11px;font-weight:500;color:#666;width:100px">To</th>
                    <th style="padding:6px 8px;border:0.5px solid #e0e0e0;font-size:11px;font-weight:500;color:#666;width:70px">Age Exempt</th>
                    <th style="padding:6px 8px;border:0.5px solid #e0e0e0;font-size:11px;font-weight:500;color:#666">Slabs</th>
                    <th style="padding:6px 8px;border:0.5px solid #e0e0e0;width:55px"></th>
                </tr></thead>
                <tbody>${tbody_html}</tbody>
               </table>`
            : `<div style="font-size:12px;color:#999;margin-bottom:8px">No Professional Tax periods configured yet.</div>`;

        const $ui = $(`
        <div id="${uid}" style="margin:8px 0 12px 0">
            <div style="font-size:12px;color:#6c757d;margin-bottom:8px">
                Configure Maharashtra (or custom) Professional Tax slabs by period. Optional February amount is per slab (Female taxable has none).
            </div>
            <div class="period-table-wrap">${table_html}</div>

            <button class="add-period-btn"
                style="display:flex;align-items:center;gap:5px;padding:5px 10px;
                       border:0.5px dashed #aaa;border-radius:5px;color:${border_color};
                       font-size:12px;cursor:pointer;background:transparent;margin-top:4px">
                + New Professional Tax Period
            </button>

            <div class="add-period-form" style="display:none;border:1.5px solid ${border_color};
                 border-radius:7px;padding:14px 16px;margin-top:8px;background:#fff">

                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
                    <div style="font-size:12px;font-weight:600;color:${border_color}">
                        New Professional Tax Period
                    </div>
                    <button type="button" class="pt-load-defaults"
                        style="padding:4px 10px;font-size:11px;border:0.5px solid ${border_color};
                               border-radius:4px;background:${bg_color};color:${text_color};cursor:pointer">
                        Load Maharashtra defaults
                    </button>
                </div>

                <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:12px">
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
                    <div>
                        <div style="font-size:11px;color:#888;margin-bottom:3px">Age Exempt Years</div>
                        <input type="number" class="pt-age-exempt" value="65"
                            style="width:100%;border:0.5px solid #ccc;border-radius:4px;
                                   padding:5px 8px;font-size:12px;box-sizing:border-box">
                    </div>
                </div>

                <div style="border:0.5px solid ${border_color}44;border-radius:5px;
                            padding:10px 12px;margin-bottom:12px;background:${bg_color}55">
                    <div style="font-size:11px;font-weight:600;color:${text_color};margin-bottom:8px">
                        Gender Slabs
                    </div>
                    <div class="pt-slab-editor">${_pt_slab_editor_html(MAHARASHTRA_PT_SLABS)}</div>
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

        $ui.find(".period-from-date, .period-to-date").datepicker({
            language: frappe.boot.lang || "en",
            autoClose: true,
            dateFormat: "dd-mm-yyyy"
        });

        function refresh_slab_editor(slabs) {
            $ui.find(".pt-slab-editor").html(_pt_slab_editor_html(slabs));
            bind_slab_editor();
        }

        function bind_slab_editor() {
            $ui.find(".pt-add-slab").off("click").on("click", function () {
                const slabs = _collect_pt_slabs($ui);
                slabs.push({ gender: "Male", from_amount: 0, to_amount: null, tax_amount: 0, february_amount: null });
                refresh_slab_editor(slabs);
            });
            $ui.find(".pt-remove-slab").off("click").on("click", function () {
                const idx = parseInt($(this).closest("tr").data("slab-idx"));
                const slabs = _collect_pt_slabs($ui);
                slabs.splice(idx, 1);
                refresh_slab_editor(slabs.length ? slabs : [{}]);
            });
        }
        bind_slab_editor();

        $ui.find(".add-period-btn").on("click", function () {
            $(this).hide();
            $ui.find(".add-period-form").slideDown(150);
        });

        $ui.find(".cancel-period-btn").on("click", () => {
            $ui.find(".add-period-form").slideUp(150, function () {
                $ui.find(".add-period-btn").show();
                $ui.find(".period-from-date, .period-to-date").val("");
                $ui.find(".pt-age-exempt").val(65);
                refresh_slab_editor(MAHARASHTRA_PT_SLABS);
            });
        });

        $ui.find(".pt-load-defaults").on("click", function () {
            $ui.find(".pt-age-exempt").val(65);
            refresh_slab_editor(MAHARASHTRA_PT_SLABS);
            frappe.show_alert({ message: __("Maharashtra defaults loaded"), indicator: "green" });
        });

        $ui.find(".save-period-btn").on("click", function () {
            const slabs = _collect_pt_slabs($ui);
            if (!slabs.length) {
                frappe.msgprint(__("Please add at least one slab."));
                return;
            }
            const row = frappe.model.add_child(frm.doc, "Professional Tax Period", fieldname);
            row.from_date = to_backend($ui.find(".period-from-date").val().trim()) || null;
            row.to_date = to_backend($ui.find(".period-to-date").val().trim()) || null;
            row.age_exempt_years = parseInt($ui.find(".pt-age-exempt").val(), 10) || 65;
            row.slabs = JSON.stringify(slabs);
            frm.dirty();
            frm.refresh_field(fieldname);
            render_pt_period_ui(frm);
        });

        $ui.find(".delete-period").on("click", function () {
            const idx = parseInt($(this).data("idx"));
            frappe.confirm(__("Delete this Professional Tax period?"), () => {
                frm.doc[fieldname].splice(idx, 1);
                frm.dirty();
                frm.refresh_field(fieldname);
                render_pt_period_ui(frm);
            });
        });

        $ui.find(".edit-period").on("click", function () {
            const idx = parseInt($(this).data("idx"));
            const row = (frm.doc[fieldname] || [])[idx];
            if (!row) return;
            const slabs = parse_pt_slabs(row);
            frm.doc[fieldname].splice(idx, 1);
            frm.refresh_field(fieldname);

            $ui.find(".period-from-date").val(to_display(row.from_date));
            $ui.find(".period-to-date").val(to_display(row.to_date));
            $ui.find(".pt-age-exempt").val(row.age_exempt_years != null ? row.age_exempt_years : 65);
            refresh_slab_editor(slabs.length ? slabs : MAHARASHTRA_PT_SLABS);

            $ui.find(".add-period-btn").hide();
            $ui.find(".add-period-form").slideDown(150);
        });

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
                    render_pt_period_ui(frm);
                },
                __("Edit To Date — Professional Tax Period"),
                __("Update")
            );
        });
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