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

    employee(frm) {
        // Auto-fetch employee details when employee is selected
        if (frm.doc.employee) {
            frappe.db.get_value("Employee", frm.doc.employee, ["employee_name", "company", "department"], (r) => {
                if (r) {
                    frm.set_value("employee_name", r.employee_name);
                    frm.set_value("company", r.company);
                    frm.set_value("department", r.department);
                }
            });
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