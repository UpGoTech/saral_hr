frappe.ui.form.on("Variable Pay Assignment", {
    onload(frm) {
        saral_hr.period_picker.apply_form_year_select(frm);
        saral_hr.period_picker.reset_year_if_invalid(frm);
    },

    refresh(frm) {
        frm.set_df_property("variable_pay", "cannot_add_rows", true);
        frm.set_df_property("variable_pay", "cannot_delete_rows", true);

        if (frm.is_new() && !frm.doc.year) {
            frm.set_value("year", String(new Date().getFullYear()));
        }
    },

    month(frm) {
        if (frm.doc.year && frm.doc.month) {
            check_existing_and_load_divisions(frm);
        }
    },

    year(frm) {
        normalize_year(frm);
        if (frm.doc.year && frm.doc.month) {
            check_existing_and_load_divisions(frm);
        }
    }
});

function normalize_year(frm) {
    if (frm.doc.year === undefined || frm.doc.year === null || frm.doc.year === "") {
        return;
    }
    const year = saral_hr.period_picker.clamp_period_year(frm.doc.year);
    if (String(frm.doc.year) !== String(year)) {
        frm.set_value("year", String(year));
    }
}

function check_existing_and_load_divisions(frm) {
    frappe.call({
        method: "saral_hr.saral_hr.doctype.variable_pay_assignment.variable_pay_assignment.check_existing_assignment",
        args: {
            year: frm.doc.year,
            month: frm.doc.month,
            name: frm.doc.name
        },
        callback(r) {
            if (r.message.exists) {
                frappe.throw(
                    `${frm.doc.month} ${frm.doc.year} Variable Pay Assignment already exists`
                );
            } else {
                load_all_divisions(frm);
            }
        }
    });
}

function load_all_divisions(frm) {
    frappe.call({
        method: "saral_hr.saral_hr.doctype.variable_pay_assignment.variable_pay_assignment.get_all_divisions",
        callback(r) {
            if (!r.message) return;

            frm.clear_table("variable_pay");

            r.message.forEach(div => {
                let row = frm.add_child("variable_pay");
                row.division = div.name;
                row.percentage = 0;
                row.target = 0.00;
                row.achievement = 0.00;
            });

            frm.refresh_field("variable_pay");
        }
    });
}
