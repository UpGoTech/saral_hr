// Copyright (c) 2026, sj and contributors
// For license information, please see license.txt

const MONTH_NUM = {
    January: 1,
    February: 2,
    March: 3,
    April: 4,
    May: 5,
    June: 6,
    July: 7,
    August: 8,
    September: 9,
    October: 10,
    November: 11,
    December: 12
};

frappe.ui.form.on("Skill Rate Revision", {
    refresh(frm) {
        if (!frm.doc.currency) frm.set_value("currency", "INR");
        set_year_options(frm);
        calculate_totals(frm);

        if (frm.doc.__islocal) {
            const y = String(new Date().getFullYear());
            if (!frm.doc.from_year) frm.set_value("from_year", y);
            if (!frm.doc.to_year) frm.set_value("to_year", y);
        }
    },

    from_month(frm) { validate_period(frm); },
    from_year(frm)  { validate_period(frm); },
    to_month(frm)   { validate_period(frm); },
    to_year(frm)    { validate_period(frm); },

    vbasic_skilled(frm)      { calculate_totals(frm); },
    vbasic_semi_skilled(frm) { calculate_totals(frm); },
    vbasic_unskilled(frm)    { calculate_totals(frm); },
    vda_skilled(frm)         { calculate_totals(frm); },
    vda_semi_skilled(frm)    { calculate_totals(frm); },
    vda_unskilled(frm)       { calculate_totals(frm); },
});

function validate_period(frm) {
    const { from_month, from_year, to_month, to_year } = frm.doc;

    if (!from_month || !from_year || !to_month || !to_year) return;

    const from_val = parseInt(from_year, 10) * 12 + MONTH_NUM[from_month];
    const to_val   = parseInt(to_year,   10) * 12 + MONTH_NUM[to_month];

    if (to_val < from_val) {
        frappe.msgprint({
            title:     __("Invalid Period"),
            message:   __("'To' period cannot be earlier than 'From' period."),
            indicator: "red"
        });
        frm.set_value("to_month", "");
        frm.set_value("to_year",  "");
        return;
    }

    const month_diff = to_val - from_val;
    if (month_diff > 6) {
        frappe.warn(
            __("Warning"),
            __("The selected period is more than 6 months."),
            () => { console.log("User saw the warning"); },
            __("Continue")
        );
    }
}
function set_year_options(frm) {
    const current = new Date().getFullYear();
    const years   = [];
    for (let y = current - 5; y <= current + 5; y++) {
        years.push(String(y));
    }
    const opts = "\n" + years.join("\n");
    frm.set_df_property("from_year", "options", opts);
    frm.set_df_property("to_year",   "options", opts);
    frm.refresh_fields(["from_year", "to_year"]);
}

function calculate_totals(frm) {
    const skilled      = flt(frm.doc.vbasic_skilled)      + flt(frm.doc.vda_skilled);
    const semi_skilled = flt(frm.doc.vbasic_semi_skilled) + flt(frm.doc.vda_semi_skilled);
    const unskilled    = flt(frm.doc.vbasic_unskilled)    + flt(frm.doc.vda_unskilled);

    frm.set_value("total_skilled",      flt(skilled,      2));
    frm.set_value("total_semi_skilled", flt(semi_skilled, 2));
    frm.set_value("total_unskilled",    flt(unskilled,    2));
}