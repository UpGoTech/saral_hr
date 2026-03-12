// Copyright (c) 2026, sj and contributors
// For license information, please see license.txt

frappe.ui.form.on("Company", {
    refresh(frm) {
        render_esic_formula(frm);
        render_pf_formula(frm);
        render_salary_calc_preview(frm);
    },

    salary_calculation_based_on(frm) {
        render_salary_calc_preview(frm);
    }
});

frappe.ui.form.on("Statutory Wage Component", {
    // Fires when any row's wage_components value changes
    wage_components(frm) {
        render_esic_formula(frm);
        render_pf_formula(frm);
    },
    esic_dependent_component_remove(frm) {
        render_esic_formula(frm);
    },
    pf_dependent_component_remove(frm) {
        render_pf_formula(frm);
    }
});

// ─────────────────────────────────────────────────────────────
//  ESIC  —  wage basis = A − B − C …  capped at ESIC Wage Limit
// ─────────────────────────────────────────────────────────────

function render_esic_formula(frm) {
    const $section = frm.fields_dict["esic_dependent_component"].$wrapper;
    const rows = (frm.doc.esic_dependent_component || [])
        .map(r => r.wage_components)
        .filter(Boolean);
    const limit = frm.doc.esic_wage_limit;
    render_formula_banner($section, "esic-formula-preview", rows, "subtract", "ESIC", limit);
}

// ─────────────────────────────────────────────────────────────
//  PF  —  wage basis = A + B + C …  capped at PF Wage Limit
// ─────────────────────────────────────────────────────────────

function render_pf_formula(frm) {
    const $section = frm.fields_dict["pf_dependent_component"].$wrapper;
    const rows = (frm.doc.pf_dependent_component || [])
        .map(r => r.wage_components)
        .filter(Boolean);
    const limit = frm.doc.pf_wage_limit;
    render_formula_banner($section, "pf-formula-preview", rows, "sum", "PF", limit);
}

// ─────────────────────────────────────────────────────────────
//  Shared banner renderer
// ─────────────────────────────────────────────────────────────

function render_formula_banner($section, id, components, mode, label, wage_limit) {
    $section.find(`#${id}`).remove();
    if (!components.length) return;

    const is_sum     = mode === "sum";
    const operator   = is_sum ? " + " : " − ";
    const color      = is_sum ? "#e8f5e9" : "#e3f2fd";
    const border     = is_sum ? "#2e7d32" : "#1565c0";
    const text_col   = is_sum ? "#1b5e20" : "#0d47a1";
    const icon       = is_sum ? "∑" : "−";
    const verb       = is_sum ? "Sum of all components" : "First component minus the rest";

    const formula = components
        .map((c, i) => {
            const name = `<b>${frappe.utils.escape_html(c)}</b>`;
            if (i === 0) return name;
            return (is_sum ? " + " : " − ") + name;
        })
        .join("");

    // Warn if subtract mode has only 1 component
    const single_warn = (!is_sum && components.length === 1)
        ? `<div style="margin-top:5px; color:#e65100; font-size:11px;">
               ⚠ Add more components to enable subtraction.
           </div>`
        : "";

    // Show wage limit cap if set
    const limit_html = wage_limit
        ? `<div style="margin-top:5px; font-size:11px; color:${text_col};">
               <b>Cap:</b> Result is capped at
               <b>₹${frappe.utils.format_number(wage_limit, null, 0)}</b>
               (${label} Wage Limit)
           </div>`
        : `<div style="margin-top:5px; font-size:11px; color:#888;">
               No wage limit set — full computed value will be used.
           </div>`;

    $section.append(`
        <div id="${id}" style="
            margin: 6px 0 10px 0;
            padding: 9px 13px;
            background: ${color};
            border-left: 3px solid ${border};
            border-radius: 4px;
            font-size: 12px;
            color: ${text_col};
            line-height: 1.7;
        ">
            <div>
                <span style="font-weight:700;">${icon} ${label} Wage Basis</span>
                &nbsp;·&nbsp;
                <span style="color:#555; font-size:11px;">${verb}</span>
            </div>
            <div style="font-family: monospace; font-size: 12.5px; margin-top:3px;">
                = ${formula}
            </div>
            ${limit_html}
            ${single_warn}
        </div>
    `);
}

// ─────────────────────────────────────────────────────────────
//  Salary Calculation Method — live example banner
// ─────────────────────────────────────────────────────────────

function render_salary_calc_preview(frm) {
    const f = frm.fields_dict["salary_calculation_based_on"];
    if (!f || !f.$wrapper) return;

    f.$wrapper.find("#salary-calc-preview").remove();

    const val = frm.doc.salary_calculation_based_on || "";
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