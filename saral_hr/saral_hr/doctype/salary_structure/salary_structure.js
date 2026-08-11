// Copyright (c) 2026, sj and contributors
// For license information, please see license.txt

frappe.ui.form.on("Salary Structure", {
    refresh(frm) {
        // No totals calculation — % components keep Amount at 0
    }
});

frappe.ui.form.on("Salary Details", {
    earnings_add: function(frm, cdt, cdn) {
        set_salary_component_filter(frm, cdt, cdn, "Earning");
    },

    deductions_add: function(frm, cdt, cdn) {
        set_salary_component_filter(frm, cdt, cdn, "Deduction");
    },

    salary_component: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];

        if (!row.salary_component) return;

        frappe.db.get_value(
            "Salary Component",
            row.salary_component,
            [
                "salary_component_abbr",
                "percent_on_total_earning",
                "percent_of_total_earning",
            ],
            (r) => {
                if (!r) return;
                frappe.model.set_value(cdt, cdn, "abbr", r.salary_component_abbr || "");
                frappe.model.set_value(
                    cdt,
                    cdn,
                    "percent_on_total_earning",
                    cint(r.percent_on_total_earning)
                );
                frappe.model.set_value(
                    cdt,
                    cdn,
                    "percent_of_total_earning",
                    flt(r.percent_of_total_earning)
                );
                if (cint(r.percent_on_total_earning) && row.parentfield === "deductions") {
                    frappe.model.set_value(cdt, cdn, "amount", 0);
                    frappe.model.set_value(cdt, cdn, "base_amount", 0);
                }
            }
        );
    },

    form_render(frm, cdt, cdn) {
        if (frm.doctype !== "Salary Structure") return;
        const row = locals[cdt][cdn];
        if (!row || !cint(row.percent_on_total_earning)) return;
        const grid = frm.fields_dict[row.parentfield] && frm.fields_dict[row.parentfield].grid;
        if (!grid) return;
        const grid_row = grid.grid_rows_by_docname[cdn];
        if (grid_row) grid_row.toggle_editable("amount", false);
    },
});

function set_salary_component_filter(frm, cdt, cdn, component_type) {
    let row = locals[cdt][cdn];
    let table_name = component_type === "Earning" ? "earnings" : "deductions";
    let selected_components = [];

    if (frm.doc[table_name]) {
        frm.doc[table_name].forEach(function(d) {
            if (d.salary_component && d.name !== row.name) {
                selected_components.push(d.salary_component);
            }
        });
    }

    frm.fields_dict[table_name].grid
        .get_field("salary_component")
        .get_query = function() {
            return {
                filters: {
                    type: component_type,
                    is_additional_only: 0,
                    name: ["not in", selected_components]
                }
            };
        };
}
