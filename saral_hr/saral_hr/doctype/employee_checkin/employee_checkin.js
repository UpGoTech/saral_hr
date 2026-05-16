frappe.ui.form.on("Employee Checkin", {
    refresh(frm) {
        // Show biometric log link if created from biometric sync
        if (frm.doc.device_id === "Biometric") {
            frm.dashboard.add_comment(
                __("This record was created automatically from Biometric Sync."),
                "blue",
                true
            );
        }
    },

    // NOTE: employee_name, company, and department are auto-fetched
    // via fetch_from in the JSON definition. No manual fetch needed here.
    employee(frm) {
        // Clear dependent fields when employee is changed
        if (!frm.doc.employee) {
            frm.set_value("employee_name", "");
            frm.set_value("company", "");
            frm.set_value("department", "");
        }
    },

    time(frm) {
        // Warn if time is in the future
        if (frm.doc.time) {
            let punch_time = frappe.datetime.str_to_moment(frm.doc.time);
            let now = moment();
            if (punch_time.isAfter(now)) {
                frappe.show_alert({
                    message: __("Warning: Punch time is in the future."),
                    indicator: "orange"
                }, 5);
            }
        }
    }
});