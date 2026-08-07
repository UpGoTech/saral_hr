// ─── Additional Deductions Form ───────────────────────────────────────────────

const AD_YEAR_OPTIONS = (() => {
    const y = new Date().getFullYear();
    return [y - 2, y - 1, y, y + 1].map(String);
})();

const AD_MONTHS = [
    'January','February','March','April','May','June',
    'July','August','September','October','November','December'
];

frappe.ui.form.on('Additional Deductions', {

    onload(frm) {
        const year_field = frm.fields_dict['year'];
        if (year_field) {
            year_field.df.options = AD_YEAR_OPTIONS.join('\n');
            year_field.refresh();
        }
        if (frm.is_new()) {
            frm.set_value('year',     String(new Date().getFullYear()));
            frm.set_value('month',    AD_MONTHS[new Date().getMonth()]);
            frm.set_value('currency', 'INR');
        }
    },

    refresh(frm) {
        if (!frm.doc.currency) frm.set_value('currency', 'INR');
        frm.set_query('employee', () => ({ filters: { is_active: 1 } }));
        frm.set_query('component_type', 'deductions', () => ({
            filters: { type: 'Deduction', is_additional_only: 1 }
        }));
    },

    employee(frm) {
        frm.refresh_field('employee_name');
    }
});

frappe.ui.form.on('Additional Deduction Component', {
    amount(frm)           { ad_recalculate_total(frm); },
    deductions_remove(frm){ ad_recalculate_total(frm); }
});

function ad_recalculate_total(frm) {
    let total = 0;
    (frm.doc.deductions || []).forEach(row => { total += flt(row.amount || 0); });
    frm.set_value('total_deduction_amount', flt(total, 2));
}