// Copyright (c) 2026, sj and contributors
// For license information, please see license.txt

frappe.ui.form.on("Company Link", {

    refresh(frm) {
        toggle_skill_type(frm);
    },

    category(frm) {
        // Clear skill_type when category changes
        frm.set_value('skill_type', '');
        toggle_skill_type(frm);
    }
});

function toggle_skill_type(frm) {
    if (!frm.doc.category) {
        frm.set_df_property('skill_type', 'hidden', 1);
        frm.refresh_field('skill_type');
        return;
    }

    frappe.db.get_value('Category', frm.doc.category, 'has_subtype', (r) => {
        const show = r && !!r.has_subtype;
        frm.set_df_property('skill_type', 'hidden', show ? 0 : 1);
        frm.refresh_field('skill_type');
    });
}