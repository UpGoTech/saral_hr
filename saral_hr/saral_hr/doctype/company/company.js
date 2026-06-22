// Copyright (c) 2026, sj and contributors
// For license information, please see license.txt

frappe.ui.form.on("Company", {
    refresh(frm) {
        render_esic_period_ui(frm);
        render_pf_period_ui(frm);
        render_salary_calc_preview(frm);
    },
    salary_calculation_based_on(frm) {
        render_salary_calc_preview(frm);
    }
});

// ─────────────────────────────────────────────────────────────
//  Group child rows by (from_date, to_date) → period-wise display
// ─────────────────────────────────────────────────────────────

function group_by_period(rows) {
    const groups = {};
    const order  = [];
    (rows || []).forEach(row => {
        if (!row.wage_components) return;
        const key = `${row.from_date || ""}||${row.to_date || ""}`;
        if (!groups[key]) {
            groups[key] = {
                from_date:  row.from_date || "",
                to_date:    row.to_date   || "",
                components: []
            };
            order.push(key);
        }
        groups[key].components.push(row.wage_components);
    });
    return order.map(k => groups[k]);
}

// ─────────────────────────────────────────────────────────────
//  Date format helpers  (backend = yyyy-mm-dd, display = dd-mm-yyyy)
// ─────────────────────────────────────────────────────────────

function to_display(date_str) {
    // "2026-04-01"  →  "01-04-2026"
    if (!date_str) return "";
    return frappe.datetime.str_to_user(date_str);
}

function to_backend(display_str) {
    // "01-04-2026"  →  "2026-04-01"
    if (!display_str) return null;
    return frappe.datetime.user_to_str(display_str);
}

// ─────────────────────────────────────────────────────────────
//  ESIC Period UI
// ─────────────────────────────────────────────────────────────

function render_esic_period_ui(frm) {
    render_period_ui(frm, "esic_dependent_component", "ESIC", "#1565c0", "#e3f2fd", "#0d47a1");
}

// ─────────────────────────────────────────────────────────────
//  PF Period UI
// ─────────────────────────────────────────────────────────────

function render_pf_period_ui(frm) {
    render_period_ui(frm, "pf_dependent_component", "PF", "#2e7d32", "#e8f5e9", "#1b5e20");
}

// ─────────────────────────────────────────────────────────────
//  Shared Period UI renderer
// ─────────────────────────────────────────────────────────────

function render_period_ui(frm, fieldname, label, border_color, bg_color, text_color) {
    const field = frm.fields_dict[fieldname];
    if (!field) return;

    const $wrapper = field.$wrapper;

    // Hide Frappe default grid
    $(field.grid.wrapper).hide();

    // Remove previous custom UI
    const uid = `${fieldname}-period-ui`;
    $wrapper.find(`#${uid}`).remove();

    const periods = group_by_period(frm.doc[fieldname]);

    // ── Table rows HTML ──
    let tbody_html = "";
    periods.forEach((p, i) => {
        const tags = p.components.map(c =>
            `<span style="display:inline-block;background:${bg_color};
                border:0.5px solid ${border_color}55;color:${text_color};
                border-radius:3px;padding:2px 8px;font-size:11px;margin:1px 2px 1px 0">
                ${frappe.utils.escape_html(c)}</span>`
        ).join("");

        // ── Display dates in dd-mm-yyyy ──
        const disp_from = to_display(p.from_date) || "—";
        const disp_to   = to_display(p.to_date)   || "—";

        tbody_html += `
        <tr>
            <td style="padding:6px 8px;border:0.5px solid #e0e0e0;color:#999;font-size:12px">${i + 1}</td>
            <td style="padding:6px 8px;border:0.5px solid #e0e0e0;font-size:12px">${disp_from}</td>
            <td style="padding:6px 8px;border:0.5px solid #e0e0e0;font-size:12px">${disp_to}</td>
            <td style="padding:6px 8px;border:0.5px solid #e0e0e0">${tags}</td>
            <td style="padding:6px 8px;border:0.5px solid #e0e0e0;text-align:center;white-space:nowrap">
                <span class="edit-period" data-idx="${i}"
                    style="cursor:pointer;color:${border_color};font-size:13px;margin-right:6px"
                    title="Edit">✏</span>
                <span class="delete-period" data-idx="${i}"
                    style="cursor:pointer;color:#e53935;font-size:13px"
                    title="Delete">✕</span>
            </td>
        </tr>`;
    });

    const table_html = tbody_html
        ? `<table style="width:100%;border-collapse:collapse;margin-bottom:6px">
            <thead>
                <tr style="background:#f5f5f5">
                    <th style="padding:6px 8px;border:0.5px solid #e0e0e0;font-size:11px;
                        font-weight:500;color:#666;width:36px">No.</th>
                    <th style="padding:6px 8px;border:0.5px solid #e0e0e0;font-size:11px;
                        font-weight:500;color:#666;width:115px">From Date</th>
                    <th style="padding:6px 8px;border:0.5px solid #e0e0e0;font-size:11px;
                        font-weight:500;color:#666;width:115px">To Date</th>
                    <th style="padding:6px 8px;border:0.5px solid #e0e0e0;font-size:11px;
                        font-weight:500;color:#666">Wage Components</th>
                    <th style="padding:6px 8px;border:0.5px solid #e0e0e0;width:55px"></th>
                </tr>
            </thead>
            <tbody>${tbody_html}</tbody>
           </table>`
        : `<div style="font-size:12px;color:#999;margin-bottom:8px">
               No periods configured yet.
           </div>`;

    // ── Full UI HTML ──
    const $ui = $(`
    <div id="${uid}" style="margin:8px 0 12px 0">

        <div class="period-table-wrap">${table_html}</div>

        <button class="add-period-btn"
            style="display:flex;align-items:center;gap:5px;padding:5px 10px;
                   border:0.5px dashed #aaa;border-radius:5px;color:${border_color};
                   font-size:12px;cursor:pointer;background:transparent;margin-top:4px">
            + New ${label} Period
        </button>

        <div class="add-period-form" style="display:none;border:1.5px solid ${border_color};
             border-radius:7px;padding:12px 14px;margin-top:8px;background:#fff">

            <div style="font-size:12px;font-weight:500;color:${border_color};margin-bottom:10px">
                📅 New ${label} Period
            </div>

            <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px">
                <div>
                    <div style="font-size:11px;color:#888;margin-bottom:3px">From Date</div>
                    <input type="text" class="period-from-date" placeholder="DD-MM-YYYY"
                        style="width:100%;border:0.5px solid #ccc;border-radius:4px;
                               padding:5px 8px;font-size:12px">
                </div>
                <div>
                    <div style="font-size:11px;color:#888;margin-bottom:3px">To Date</div>
                    <input type="text" class="period-to-date" placeholder="DD-MM-YYYY"
                        style="width:100%;border:0.5px solid #ccc;border-radius:4px;
                               padding:5px 8px;font-size:12px">
                </div>
            </div>

            <div style="border:0.5px solid #e0e0e0;border-radius:5px;
                        padding:8px 10px;margin-bottom:10px">
                <div style="font-size:11px;font-weight:500;color:${text_color};margin-bottom:6px">
                    Wage Components (${label})
                </div>
                <div class="checkbox-list" style="font-size:12px;color:#999">Loading...</div>
            </div>

            <div style="display:flex;gap:8px;justify-content:flex-end">
                <button class="cancel-period-btn"
                    style="padding:5px 13px;border-radius:4px;font-size:12px;cursor:pointer;
                           border:0.5px solid #ccc;background:transparent;color:#666">
                    Cancel
                </button>
                <button class="save-period-btn"
                    style="padding:5px 13px;border-radius:4px;font-size:12px;cursor:pointer;
                           border:0.5px solid ${border_color};background:${border_color};color:#fff">
                    Save
                </button>
            </div>
        </div>

    </div>`);

    $wrapper.append($ui);

    // ── Frappe datepicker apply (dd-mm-yyyy format) ──
    $ui.find(".period-from-date, .period-to-date").datepicker({
        language:   frappe.boot.lang || "en",
        autoClose:  true,
        dateFormat: "dd-mm-yyyy",
        onSelect: function() {
            // nothing extra needed — value already set in input
        }
    });

    // ── Load Earning components as checkboxes ──
    frappe.db.get_list("Salary Component", {
        filters: { type: "Earning" },
        fields: ["name"],
        limit: 0
    }).then(results => {
        const $list = $ui.find(".checkbox-list");
        $list.empty();
        results.forEach(r => {
            $list.append(`
                <label style="display:flex;align-items:center;gap:6px;
                              margin-bottom:4px;font-size:12px;cursor:pointer;color:inherit">
                    <input type="checkbox" value="${frappe.utils.escape_html(r.name)}"
                           style="accent-color:${border_color}">
                    ${frappe.utils.escape_html(r.name)}
                </label>`);
        });
    });

    // ── Add button ──
    $ui.find(".add-period-btn").on("click", function () {
        $(this).hide();
        $ui.find(".add-period-form").slideDown(150);
    });

    // ── Cancel button ──
    $ui.find(".cancel-period-btn").on("click", function () {
        _reset_form($ui);
    });

    // ── Save button ──
    $ui.find(".save-period-btn").on("click", function () {
        const from_display = $ui.find(".period-from-date").val();
        const to_display   = $ui.find(".period-to-date").val();

        // dd-mm-yyyy → yyyy-mm-dd for backend storage
        const from_date = to_backend(from_display);
        const to_date   = to_backend(to_display);

        const selected = [];
        $ui.find(".checkbox-list input[type=checkbox]:checked").each(function () {
            selected.push($(this).val());
        });

        if (!selected.length) {
            frappe.msgprint(__("Please select at least one Wage Component."));
            return;
        }

        selected.forEach(comp => {
            const row = frappe.model.add_child(
                frm.doc, "Statutory Wage Component", fieldname
            );
            row.wage_components = comp;
            row.from_date       = from_date;
            row.to_date         = to_date;
        });

        frm.dirty();
        frm.refresh_field(fieldname);
        render_period_ui(frm, fieldname, label, border_color, bg_color, text_color);
    });

    // ── Delete period ──
    $ui.find(".delete-period").on("click", function () {
        const idx    = parseInt($(this).data("idx"));
        const period = group_by_period(frm.doc[fieldname])[idx];
        if (!period) return;

        frappe.confirm(__("Delete this period config?"), () => {
            const comp_set = new Set(period.components);
            frm.doc[fieldname] = (frm.doc[fieldname] || []).filter(row =>
                !(  (row.from_date || "") === (period.from_date || "") &&
                    (row.to_date   || "") === (period.to_date   || "") &&
                    comp_set.has(row.wage_components)
                )
            );
            frm.dirty();
            frm.refresh_field(fieldname);
            render_period_ui(frm, fieldname, label, border_color, bg_color, text_color);
        });
    });

    // ── Edit period — rows delete + form pre-fill ──
    $ui.find(".edit-period").on("click", function () {
        const idx    = parseInt($(this).data("idx"));
        const period = group_by_period(frm.doc[fieldname])[idx];
        if (!period) return;

        const comp_set = new Set(period.components);

        frm.doc[fieldname] = (frm.doc[fieldname] || []).filter(row =>
            !(  (row.from_date || "") === (period.from_date || "") &&
                (row.to_date   || "") === (period.to_date   || "") &&
                comp_set.has(row.wage_components)
            )
        );
        frm.refresh_field(fieldname);

        // Pre-fill dates in dd-mm-yyyy display format
        $ui.find(".period-from-date").val(to_display(period.from_date));
        $ui.find(".period-to-date").val(to_display(period.to_date));

        setTimeout(() => {
            $ui.find(".checkbox-list input[type=checkbox]").each(function () {
                $(this).prop("checked", comp_set.has($(this).val()));
            });
        }, 300);

        $ui.find(".add-period-btn").hide();
        $ui.find(".add-period-form").slideDown(150);
    });
}

// ── Reset add-period form ──
function _reset_form($ui) {
    $ui.find(".add-period-form").slideUp(150, function () {
        $ui.find(".add-period-btn").show();
        $ui.find(".period-from-date, .period-to-date").val("");
        $ui.find(".checkbox-list input[type=checkbox]").prop("checked", false);
    });
}

// ─────────────────────────────────────────────────────────────
//  Salary Calculation Method — live example banner (unchanged)
// ─────────────────────────────────────────────────────────────

function render_salary_calc_preview(frm) {
    const f = frm.fields_dict["salary_calculation_based_on"];
    if (!f || !f.$wrapper) return;

    f.$wrapper.find("#salary-calc-preview").remove();

    const val     = frm.doc.salary_calculation_based_on || "";
    const include = val.includes("Include");

    const color  = include ? "#e8f5e9" : "#e3f2fd";
    const border = include ? "#2e7d32" : "#1565c0";
    const tcol   = include ? "#1b5e20" : "#0d47a1";

    const example = include
        ? `Jan 2026 (31 days, 4 Sundays, 1 absent):<br>
           Payment days = 31 − 1 absent = <b>30</b>`
        : `Jan 2026 (31 days, 4 Sundays, 1 absent):<br>
           Working days = 31 − 4 Sundays = 27<br>
           Payment days = 27 − 1 absent = <b>26</b>`;

    f.$wrapper.append(`
        <div id="salary-calc-preview" style="
            margin:6px 0 10px 0; padding:9px 13px;
            background:${color}; border-left:3px solid ${border};
            border-radius:4px; font-size:12px; color:${tcol}; line-height:1.7;">
            <b>Example</b> &nbsp;·&nbsp; ${example}
        </div>`);
}