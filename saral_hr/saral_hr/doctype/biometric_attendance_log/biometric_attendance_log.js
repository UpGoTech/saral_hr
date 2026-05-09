// Copyright (c) 2026, sj and contributors
// For license information, please see license.txt

frappe.ui.form.on("Biometric attendance log", {
    refresh(frm) {
        // ── Process to Checkin button (single record) ──
        if (!frm.doc.is_processed && frm.doc.employee) {
            frm.add_custom_button(__("Process to Checkin"), function () {
                frappe.confirm(
                    __("Create Employee Checkin for <b>{0}</b> at {1}?", [
                        frm.doc.employee_name || frm.doc.employee,
                        frm.doc.punch_time
                    ]),
                    function () {
                        frappe.call({
                            method: "saral_hr.utils.biometric_sync.process_single_log",
                            args: { log_name: frm.doc.name },
                            freeze: true,
                            freeze_message: __("Processing..."),
                            callback(r) {
                                if (r.message && r.message.success) {
                                    frappe.show_alert({
                                        message: __("✓ Employee Checkin created successfully"),
                                        indicator: "green"
                                    }, 5);
                                    frm.reload_doc();
                                } else {
                                    frappe.show_alert({
                                        message: __("✗ Failed: ") + (r.message ? r.message.message : "Unknown error"),
                                        indicator: "red"
                                    }, 7);
                                }
                            }
                        });
                    }
                );
            }).addClass("btn-primary");
        }
    }
});

// ── List View: Process by Date Range button ──
frappe.listview_settings["Biometric attendance log"] = {
    onload(listview) {
        listview.page.add_inner_button(__("Process to Checkin"), function () {
            let d = new frappe.ui.Dialog({
                title: __("Process Attendance Logs to Employee Checkin"),
                fields: [
                    {
                        fieldname: "start_date",
                        fieldtype: "Date",
                        label: __("Start Date"),
                        reqd: 1,
                        default: frappe.datetime.add_days(frappe.datetime.get_today(), -1)
                    },
                    {
                        fieldname: "end_date",
                        fieldtype: "Date",
                        label: __("End Date"),
                        reqd: 1,
                        default: frappe.datetime.get_today()
                    },
                    {
                        fieldname: "employee",
                        fieldtype: "Link",
                        label: __("Employee"),
                        options: "Employee",
                        description: __("Leave blank to process all employees")
                    },
                    {
                        fieldname: "punch_type",
                        fieldtype: "Select",
                        label: __("Punch Type"),
                        options: "\nIN\nOUT\nUnknown",
                        description: __("Leave blank for all punch types")
                    }
                ],
                primary_action_label: __("Process"),
                primary_action(values) {
                    d.hide();
                    frappe.call({
                        method: "saral_hr.utils.biometric_sync.process_logs_by_date",
                        args: {
                            start_date: values.start_date,
                            end_date: values.end_date,
                            employee: values.employee || null,
                            punch_type: values.punch_type || null,
                        },
                        freeze: true,
                        freeze_message: __("Processing attendance logs..."),
                        callback(r) {
                            if (r.message) {
                                let res = r.message;
                                if (res.success) {
                                    frappe.msgprint({
                                        title: __("Processing Complete"),
                                        message: __(
                                            "✓ Processed: <b>{0}</b><br>✗ Failed: <b>{1}</b><br>⟳ Already Done: <b>{2}</b>",
                                            [res.processed, res.failed, res.skipped]
                                        ),
                                        indicator: "green"
                                    });
                                    listview.refresh();
                                } else {
                                    frappe.msgprint({
                                        title: __("Error"),
                                        message: res.message,
                                        indicator: "red"
                                    });
                                }
                            }
                        }
                    });
                }
            });
            d.show();
        });
    }
};