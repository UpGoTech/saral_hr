// Copyright (c) 2026, sj and contributors
// For license information, please see license.txt

frappe.ui.form.on("Daily Rates Worker", {

    refresh(frm) {
        frm.trigger("set_employee_query");
    },

    company(frm) {
        // Clear stale employee whenever company changes
        frm.set_value("employee", "");
        frm.set_value("employee_name", "");
        frm.trigger("set_employee_query");
    },

    // ── Employee query via server-side method (joins Company Link → Category) ──
    set_employee_query(frm) {
        frm.set_query("employee", () => {
            if (!frm.doc.company) {
                // Show nothing until a company is chosen
                return { filters: { name: "__none__" } };
            }
            return {
                query: "saral_hr.saral_hr.doctype.daily_rates_worker.daily_rates_worker.get_employee_query",
                filters: {
                    company: frm.doc.company,
                },
            };
        });
    },

    // ── Immediate duplicate check when employee is selected ──────────────────
    employee(frm) {
        if (!frm.doc.employee) return;
        if (frm.doc.start_date && frm.doc.end_date) {
            frm.trigger("check_duplicate");
        }
    },

    start_date(frm) {
        frm.trigger("validate_dates");
        if (frm.doc.employee && frm.doc.end_date) {
            frm.trigger("check_duplicate");
        }
    },

    end_date(frm) {
        frm.trigger("validate_dates");
        if (frm.doc.employee && frm.doc.start_date) {
            frm.trigger("check_duplicate");
        }
    },

    // ── Client-side date validation ──────────────────────────────────────────
    validate_dates(frm) {
        if (frm.doc.start_date && frm.doc.end_date) {
            if (frm.doc.end_date <= frm.doc.start_date) {
                frappe.msgprint({
                    title: __("Invalid Date Range"),
                    message: __("End Date must be greater than Start Date."),
                    indicator: "red",
                });
                frm.set_value("end_date", "");
            }
        }
    },

    // ── Real-time duplicate/overlap check ────────────────────────────────────
    check_duplicate(frm) {
        frappe.call({
            method: "frappe.client.get_list",
            args: {
                doctype: "Daily Rates Worker",
                filters: [
                    ["employee",   "=",  frm.doc.employee],
                    ["start_date", "<=", frm.doc.end_date],
                    ["end_date",   ">=", frm.doc.start_date],
                    ...(frm.doc.name && !frm.doc.__islocal
                        ? [["name", "!=", frm.doc.name]]
                        : []),
                ],
                fields: ["name", "start_date", "end_date"],
                limit: 1,
            },
            callback(r) {
                if (r.message && r.message.length > 0) {
                    const rec = r.message[0];
                    frappe.msgprint({
                        title: __("Duplicate Record Found"),
                        message: __(
                            "A record already exists for employee <b>{0}</b> "
                            + "that overlaps this date range.<br><br>"
                            + "Existing record: <b>{1}</b> "
                            + "(Start: {2} — End: {3})<br><br>"
                            + "Please choose a different date range.",
                            [
                                frm.doc.employee,
                                rec.name,
                                rec.start_date,
                                rec.end_date,
                            ]
                        ),
                        indicator: "red",
                    });
                    frm.set_value("start_date", "");
                    frm.set_value("end_date", "");
                }
            },
        });
    },
});