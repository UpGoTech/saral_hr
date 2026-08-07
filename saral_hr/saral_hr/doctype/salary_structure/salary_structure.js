// Copyright (c) 2026, sj and contributors
// For license information, please see license.txt

frappe.ui.form.on("Salary Structure", {
    refresh(frm) {
        // No totals calculation
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

        if (row.salary_component) {
            frappe.call({
                method: "frappe.client.get",
                args: {
                    doctype: "Salary Component",
                    name: row.salary_component
                },
                callback: function(r) {
                    if (r.message) {
                        frappe.model.set_value(
                            cdt,
                            cdn,
                            "abbr",
                            r.message.salary_component_abbr
                        );
                    }
                }
            });
        }
    }
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
