// Copyright (c) 2026, sj and contributors
frappe.ui.form.on("Leave Application", {
    refresh(frm) {
        frm.set_intro(frm.doc.status === "Approved" ? "This leave has been approved." : "");
    },
    from_date(frm) {
        calculate_total_days(frm);
    },
    to_date(frm) {
        calculate_total_days(frm);
    }
});

function calculate_total_days(frm) {
    if (frm.doc.from_date && frm.doc.to_date) {
        let from = frappe.datetime.str_to_obj(frm.doc.from_date);
        let to = frappe.datetime.str_to_obj(frm.doc.to_date);
        let diff = frappe.datetime.get_diff(to, from) + 1;
        frm.set_value("total_days", diff);
    }
}