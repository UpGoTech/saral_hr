frappe.ui.form.on('Salary Component', {


    is_daily_rate(frm) {
        if (frm.doc.is_daily_rate) {
            if (frm.doc.depends_on_payment_days)          frm.set_value('depends_on_payment_days', 0);
            if (frm.doc.depends_on_physical_working_days) frm.set_value('depends_on_physical_working_days', 0);
            frappe.show_alert({ message: __('Other payment day flags have been unchecked. A component can only have one calculation mode.'), indicator: 'orange' });
        }
    },

    depends_on_payment_days(frm) {
        if (frm.doc.depends_on_payment_days) {
            if (frm.doc.is_daily_rate)                    frm.set_value('is_daily_rate', 0);
            if (frm.doc.depends_on_physical_working_days) frm.set_value('depends_on_physical_working_days', 0);
            frappe.show_alert({ message: __('Other payment dFesicay flags have been unchecked. A component can only have one calculation mode.'), indicator: 'orange' });
        }
    },

    depends_on_physical_working_days(frm) {
        if (frm.doc.depends_on_physical_working_days) {
            if (frm.doc.is_daily_rate)           frm.set_value('is_daily_rate', 0);
            if (frm.doc.depends_on_payment_days) frm.set_value('depends_on_payment_days', 0);
            frappe.show_alert({ message: __('Other payment day flags have been unchecked. A component can only have one calculation mode.'), indicator: 'orange' });
        }
    },

    // ── ESIC handlers ─────────────────────────────────────────────────────────

    is_esic_component(frm) {
        if (!frm.doc.is_esic_component) {
            frm.set_value('esic_calculation_based_on', '');
            frm.set_value('esic_percentage', 0);
            frm.set_value('esic_cap_amount', null);
        }
    },

    // ── PF handlers ───────────────────────────────────────────────────────────

    is_pf_component(frm) {
        if (!frm.doc.is_pf_component) {
            frm.set_value('pf_calculation_based_on', '');
            frm.set_value('pf_percentage', 0);
            frm.set_value('pf_cap_amount', null);
        }
    },

    // ── PT handlers ───────────────────────────────────────────────────────────

    is_pt_component(frm) {
        if (!frm.doc.is_pt_component) {
            // Clear PT description only if it was auto-set
            const desc = frm.doc.description || '';
            if (desc.includes('Professional Tax')) {
                frm.set_value('description', '');
            }
        }
    },
});