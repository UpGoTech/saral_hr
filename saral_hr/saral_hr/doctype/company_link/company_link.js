// Copyright (c) 2026, sj and contributors
// For license information, please see license.txt

frappe.ui.form.on("Company Link", {

    refresh(frm) {
        frm.set_df_property("skill_type", "reqd",   0);
        frm.set_df_property("skill_type", "hidden", 1);
        frm.refresh_field("skill_type");
        toggle_skill_type(frm);
    },

    employee(frm) {
        if (!frm.is_new() || !frm.doc.employee) {
            frm._active_conflict = null;
            frm._last_checked_employee = null;
            return;
        }

        // If we already checked this exact employee value, skip
        if (frm._last_checked_employee === frm.doc.employee) return;
        frm._last_checked_employee = frm.doc.employee;

        frappe.db.get_list("Company Link", {
            filters: {
                employee: frm.doc.employee,
                is_active: 1
            },
            fields: ["name", "company", "date_of_joining"],
            limit: 1
        }).then(results => {
            if (!results || results.length === 0) {
                frm._active_conflict = null;
                return;
            }

            const existing = results[0];
            const empName = frm.doc.full_name || frm.doc.employee;

            frm._active_conflict = existing;

            frappe.msgprint({
                title: __("Employee Already Active"),
                indicator: "orange",
                message: `<b>${empName}</b> is currently active in <b>${existing.company}</b>.<br><br>
                    You can still save this record. On save:<br>
                    &bull; The existing record will be archived<br>
                    &bull; Their leaving date will be set to <b>one day before</b> the Date of Joining you enter here`
            });
        });
    },

    category(frm) {
        frm.set_value("skill_type", "");
        frm.set_df_property("skill_type", "reqd",   0);
        frm.set_df_property("skill_type", "hidden", 1);
        frm.refresh_field("skill_type");
        toggle_skill_type(frm);
    },

    immediate_reporting(frm) {
        if (frm.doc.immediate_reporting) {
            frappe.db.get_value("Employee", frm.doc.immediate_reporting, "employee", (r) => {
                frm.set_value("immediate_reporting_name", r && r.employee ? r.employee : "");
            });
        } else {
            frm.set_value("immediate_reporting_name", "");
        }
    },

    final_reporting(frm) {
        if (frm.doc.final_reporting) {
            frappe.db.get_value("Employee", frm.doc.final_reporting, "employee", (r) => {
                frm.set_value("final_reporting_name", r && r.employee ? r.employee : "");
            });
        } else {
            frm.set_value("final_reporting_name", "");
        }
    },

    before_save(frm) {
        if (!frm.is_new() || !frm._active_conflict) return;
        if (!frm.doc.employee || !frm.doc.date_of_joining) return;

        const existing = frm._active_conflict;
        const leftDate = frappe.datetime.add_days(frm.doc.date_of_joining, -1);
        const leftDateFormatted = frappe.datetime.str_to_user(leftDate);
        const empName = frm.doc.full_name || frm.doc.employee;

        return new Promise((resolve, reject) => {
            frappe.confirm(
                `<b>${empName}</b> is currently active in <b>${existing.company}</b>.<br><br>
                Proceeding will:<br>
                &bull; Archive the existing record<br>
                &bull; Set their leaving date to <b>${leftDateFormatted}</b><br><br>
                Do you want to continue?`,
                () => resolve(),
                () => reject("Transfer cancelled.")
            );
        });
    }
});

function toggle_skill_type(frm) {
    if (!frm.doc.category) {
        frm.set_df_property("skill_type", "hidden", 1);
        frm.set_df_property("skill_type", "reqd",   0);
        frm.refresh_field("skill_type");
        return;
    }

    frappe.db.get_value("Category", frm.doc.category, "has_subtype", (r) => {
        const show = r && !!r.has_subtype;
        frm.set_df_property("skill_type", "hidden", show ? 0 : 1);
        frm.set_df_property("skill_type", "reqd",   show ? 1 : 0);
        frm.refresh_field("skill_type");
    });
}