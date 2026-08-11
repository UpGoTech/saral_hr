// Copyright (c) 2026, sj and contributors
// For license information, please see license.txt

const MONTHS = [
    "January", "February", "March", "April",
    "May", "June", "July", "August",
    "September", "October", "November", "December"
];

frappe.ui.form.on('Salary Component', {

    refresh(frm) {
        if (frm.doc.is_special_component) {
            ensure_all_months(frm);
        }
        toggle_percent_lock(frm);
    },

    is_special_component(frm) {
        if (frm.doc.is_special_component) {
            if (frm.doc.is_additional_only) {
                frm.set_value("is_additional_only", 0);
                frappe.show_alert({
                    message: __("Is Additional Only was unchecked. A component cannot be both Special and Additional Only."),
                    indicator: "orange",
                });
            }
            if (frm.doc.percent_on_total_earning) {
                frm.set_value("percent_on_total_earning", 0);
                frappe.show_alert({
                    message: __("% on Total Earning was unchecked — it cannot combine with Special Component."),
                    indicator: "orange",
                });
            }
            ensure_all_months(frm);
        } else {
            frm.clear_table("monthly_amounts");
            frm.refresh_field("monthly_amounts");
        }
    },

    is_additional_only(frm) {
        if (frm.doc.is_additional_only && frm.doc.is_special_component) {
            frm.set_value("is_special_component", 0);
            frm.clear_table("monthly_amounts");
            frm.refresh_field("monthly_amounts");
            frappe.show_alert({
                message: __("Is Special Component was unchecked. A component cannot be both Special and Additional Only."),
                indicator: "orange",
            });
        }
        if (frm.doc.is_additional_only && frm.doc.percent_on_total_earning) {
            frm.set_value("percent_on_total_earning", 0);
            frappe.show_alert({
                message: __("% on Total Earning was unchecked — it cannot combine with Additional Only."),
                indicator: "orange",
            });
        }
    },

    percent_on_total_earning(frm) {
        if (!frm.doc.percent_on_total_earning) {
            frm.set_value("percent_of_total_earning", 0);
            return;
        }
        const clear = [];
        if (frm.doc.depends_on_payment_days) {
            frm.set_value("depends_on_payment_days", 0);
            clear.push("Depends on Payment Days");
        }
        if (frm.doc.depends_on_physical_working_days) {
            frm.set_value("depends_on_physical_working_days", 0);
            clear.push("Depends on Physical Working Days");
        }
        if (frm.doc.daily_wage_component) {
            frm.set_value("daily_wage_component", 0);
            clear.push("Daily Wage Component");
        }
        if (frm.doc.is_special_component) {
            frm.set_value("is_special_component", 0);
            frm.clear_table("monthly_amounts");
            frm.refresh_field("monthly_amounts");
            clear.push("Is Special Component");
        }
        if (frm.doc.is_additional_only) {
            frm.set_value("is_additional_only", 0);
            clear.push("Is Additional Only");
        }
        if (frm.doc.employer_contribution) {
            frm.set_value("employer_contribution", 0);
            clear.push("Employer Contribution");
        }
        if (clear.length) {
            frappe.show_alert({
                message: __("Unchecked incompatible flags: {0}", [clear.join(", ")]),
                indicator: "orange",
            });
        }
    },

    depends_on_payment_days(frm) {
        if (frm.doc.depends_on_payment_days && frm.doc.depends_on_physical_working_days) {
            frm.set_value('depends_on_physical_working_days', 0);
            frappe.show_alert({
                message: __('Depends on Physical Working Days has been unchecked. A component can only have one calculation mode.'),
                indicator: 'orange'
            });
        }
        if (frm.doc.depends_on_payment_days && frm.doc.percent_on_total_earning) {
            frm.set_value("percent_on_total_earning", 0);
            frappe.show_alert({
                message: __("% on Total Earning was unchecked — incompatible with payment-day proration."),
                indicator: "orange",
            });
        }
    },

    depends_on_physical_working_days(frm) {
        if (frm.doc.depends_on_physical_working_days && frm.doc.depends_on_payment_days) {
            frm.set_value('depends_on_payment_days', 0);
            frappe.show_alert({
                message: __('Depends on Payment Days has been unchecked. A component can only have one calculation mode.'),
                indicator: 'orange'
            });
        }
        if (frm.doc.depends_on_physical_working_days && frm.doc.percent_on_total_earning) {
            frm.set_value("percent_on_total_earning", 0);
            frappe.show_alert({
                message: __("% on Total Earning was unchecked — incompatible with physical working days."),
                indicator: "orange",
            });
        }
    },

    daily_wage_component(frm) {
        if (frm.doc.daily_wage_component && frm.doc.percent_on_total_earning) {
            frm.set_value("percent_on_total_earning", 0);
            frappe.show_alert({
                message: __("% on Total Earning was unchecked — incompatible with Daily Wage."),
                indicator: "orange",
            });
        }
    },

    employer_contribution(frm) {
        if (frm.doc.employer_contribution && frm.doc.percent_on_total_earning) {
            frm.set_value("percent_on_total_earning", 0);
            frappe.show_alert({
                message: __("% on Total Earning was unchecked — incompatible with Employer Contribution."),
                indicator: "orange",
            });
        }
    },
});

function toggle_percent_lock(frm) {
    if (frm.is_new() || !frm.doc.name) {
        frm.set_df_property("percent_on_total_earning", "read_only", 0);
        frm.set_df_property("percent_of_total_earning", "read_only", 0);
        return;
    }
    frappe.call({
        method: "saral_hr.saral_hr.doctype.salary_component.salary_component.is_percent_of_total_earning_locked",
        args: { component_name: frm.doc.name },
        callback(r) {
            const locked = !!r.message;
            frm.set_df_property("percent_on_total_earning", "read_only", locked ? 1 : 0);
            frm.set_df_property("percent_of_total_earning", "read_only", locked ? 1 : 0);
            if (locked) {
                frm.dashboard.set_headline_alert(
                    __("Percent is locked because this component is used on a Salary Structure Assignment."),
                    "blue"
                );
            }
        },
    });
}

function ensure_all_months(frm) {
    const existing = {};
    (frm.doc.monthly_amounts || []).forEach(r => {
        if (r.month) existing[r.month] = r.amount || 0;
    });

    const current_months = (frm.doc.monthly_amounts || []).map(r => r.month);
    const already_ok = MONTHS.every((m, i) => current_months[i] === m)
        && current_months.length === 12;

    if (already_ok) return;

    frm.clear_table("monthly_amounts");
    MONTHS.forEach(month => {
        const row = frm.add_child("monthly_amounts");
        frappe.model.set_value(row.doctype, row.name, {
            month:  month,
            amount: existing[month] || 0,
        });
    });

    frm.refresh_field("monthly_amounts");
}
