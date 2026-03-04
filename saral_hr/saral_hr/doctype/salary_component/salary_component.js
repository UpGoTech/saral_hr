frappe.ui.form.on('Salary Component', {

    refresh(frm) {
        if (frm.doc.is_special_component) {
            lock_month_table(frm);
        }
    },

    is_special_component(frm) {
        if (frm.doc.is_special_component) {
            populate_all_months(frm);
            lock_month_table(frm);
        } else {
            frm.clear_table('enter_amount_according_to_months');
            frm.refresh_field('enter_amount_according_to_months');
        }
    },

    is_daily_rate(frm) {
        if (frm.doc.is_daily_rate) {
            if (frm.doc.depends_on_payment_days) {
                frm.set_value('depends_on_payment_days', 0);
            }
            if (frm.doc.depends_on_physical_working_days) {
                frm.set_value('depends_on_physical_working_days', 0);
            }
            frappe.show_alert({
                message: __('Other payment day flags have been unchecked. A component can only have one calculation mode.'),
                indicator: 'orange'
            });
        }
    },

    depends_on_payment_days(frm) {
        if (frm.doc.depends_on_payment_days) {
            if (frm.doc.is_daily_rate) {
                frm.set_value('is_daily_rate', 0);
            }
            if (frm.doc.depends_on_physical_working_days) {
                frm.set_value('depends_on_physical_working_days', 0);
            }
            frappe.show_alert({
                message: __('Other payment day flags have been unchecked. A component can only have one calculation mode.'),
                indicator: 'orange'
            });
        }
    },

    depends_on_physical_working_days(frm) {
        if (frm.doc.depends_on_physical_working_days) {
            if (frm.doc.is_daily_rate) {
                frm.set_value('is_daily_rate', 0);
            }
            if (frm.doc.depends_on_payment_days) {
                frm.set_value('depends_on_payment_days', 0);
            }
            frappe.show_alert({
                message: __('Other payment day flags have been unchecked. A component can only have one calculation mode.'),
                indicator: 'orange'
            });
        }
    }
});

const MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
];

function populate_all_months(frm) {
    // Preserve amounts the user already typed
    let existing = {};
    (frm.doc.enter_amount_according_to_months || []).forEach(r => {
        if (r.month) existing[r.month] = r.amount;
    });

    frm.clear_table('enter_amount_according_to_months');

    MONTHS.forEach(month => {
        let row = frm.add_child('enter_amount_according_to_months');
        row.month  = month;
        row.amount = existing[month] || 0;
    });

    frm.refresh_field('enter_amount_according_to_months');
}

function lock_month_table(frm) {
    frappe.after_ajax(() => {
        const field = frm.get_field('enter_amount_according_to_months');
        if (!field || !field.grid) return;

        const grid = field.grid;
        grid.cannot_add_rows    = true;
        grid.cannot_delete_rows = true;

        grid.wrapper.find('.grid-add-row').hide();
        grid.wrapper.find('.grid-remove-rows').hide();
        grid.wrapper.find('.grid-row-check').hide();
        grid.wrapper.find('.grid-delete-row').hide();
    });
}