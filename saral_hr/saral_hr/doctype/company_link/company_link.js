// Copyright (c) 2026, sj and contributors
// For license information, please see license.txt

frappe.ui.form.on("Company", {
    refresh(frm) {
        render_esic_formula(frm);
        render_pf_formula(frm);
    }
});

frappe.ui.form.on("Statutory Wage Component", {
    // Fires when any row is added, removed, or changed in either child table
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
//  ESIC  —  wage basis = A + B + C + …
// ─────────────────────────────────────────────────────────────

function render_esic_formula(frm) {
    const wrapper_id = "esic-formula-preview";
    const $section   = frm.fields_dict["esic_dependent_component"].$wrapper;

    const rows = (frm.doc.esic_dependent_component || [])
        .map(r => r.wage_components)
        .filter(Boolean);

    render_formula_banner($section, wrapper_id, rows, "sum", "ESIC");
}

// ─────────────────────────────────────────────────────────────
//  PF  —  wage basis = A − B − C − …
// ─────────────────────────────────────────────────────────────

function render_pf_formula(frm) {
    const wrapper_id = "pf-formula-preview";
    const $section   = frm.fields_dict["pf_dependent_component"].$wrapper;

    const rows = (frm.doc.pf_dependent_component || [])
        .map(r => r.wage_components)
        .filter(Boolean);

    render_formula_banner($section, wrapper_id, rows, "subtract", "PF");
}

// ─────────────────────────────────────────────────────────────
//  Shared banner renderer
// ─────────────────────────────────────────────────────────────

function render_formula_banner($section, id, components, mode, label) {
    // Remove old banner
    $section.find(`#${id}`).remove();

    if (!components.length) return;

    const operator  = mode === "sum" ? " + " : " − ";
    const formula   = components.map(c => `<b>${frappe.utils.escape_html(c)}</b>`).join(operator);
    const color     = mode === "sum" ? "#e6f4ea" : "#fff3e0";
    const border    = mode === "sum" ? "#2d8a4e" : "#e65100";
    const text_col  = mode === "sum" ? "#1b5e20" : "#bf360c";
    const icon      = mode === "sum" ? "✚" : "−";
    const verb      = mode === "sum" ? "Added" : "Subtracted (first − rest)";

    const hint = components.length === 1 && mode === "subtract"
        ? `<span style="color:#e65100; margin-left:8px;">⚠ Add more components to enable subtraction.</span>`
        : "";

    $section.append(`
        <div id="${id}" style="
            margin: 6px 0 10px 0;
            padding: 8px 12px;
            background: ${color};
            border-left: 3px solid ${border};
            border-radius: 4px;
            font-size: 12px;
            color: ${text_col};
            line-height: 1.6;
        ">
            <span style="font-weight:600;">${icon} ${label} Wage Basis</span>
            &nbsp;·&nbsp;
            <span style="color:#555; font-size:11px;">${verb}</span>
            <br/>
            <span style="font-family: monospace; font-size: 12px;">${formula}</span>
            ${hint}
        </div>
    `);
}