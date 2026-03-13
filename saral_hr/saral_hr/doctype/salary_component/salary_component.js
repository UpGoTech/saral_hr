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
    },

    is_special_component(frm) {
        if (frm.doc.is_special_component) {
            ensure_all_months(frm);
        } else {
            // Clear the table when unchecked
            frm.clear_table("monthly_amounts");
            frm.refresh_field("monthly_amounts");
        }
    },

    // Only one payment-day mode may be active at a time

    depends_on_payment_days(frm) {
<<<<<<< HEAD
        if (frm.doc.depends_on_payment_days) {
            if (frm.doc.is_daily_rate)                    frm.set_value('is_daily_rate', 0);
            if (frm.doc.depends_on_physical_working_days) frm.set_value('depends_on_physical_working_days', 0);
            frappe.show_alert({ message: __('Other payment dFesicay flags have been unchecked. A component can only have one calculation mode.'), indicator: 'orange' });
=======
        if (frm.doc.depends_on_payment_days && frm.doc.depends_on_physical_working_days) {
            frm.set_value('depends_on_physical_working_days', 0);
            frappe.show_alert({
                message: __('Depends on Physical Working Days has been unchecked. A component can only have one calculation mode.'),
                indicator: 'orange'
            });
>>>>>>> origin/daisy
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
    },
});

// ─────────────────────────────────────────────────────────────
//  Ensure all 12 months exist in Jan→Dec order.
//  Preserves amounts already entered by the user.
// ─────────────────────────────────────────────────────────────

function ensure_all_months(frm) {
    const existing = {};
    (frm.doc.monthly_amounts || []).forEach(r => {
        if (r.month) existing[r.month] = r.amount || 0;
    });

    // Check if all 12 months already present in correct order
    const current_months = (frm.doc.monthly_amounts || []).map(r => r.month);
    const already_ok = MONTHS.every((m, i) => current_months[i] === m)
        && current_months.length === 12;

    if (already_ok) return;

    // Rebuild in Jan→Dec order preserving existing amounts
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