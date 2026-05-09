frappe.ui.form.on("Biometric machine", {
    refresh(frm) {
        // ── Test Connection button (top right) ──
        frm.add_custom_button(__("Test Connection"), function () {
            // Block if unsaved
            if (frm.is_new()) {
                frappe.msgprint({
                    title: __("Save Required"),
                    message: __("Please save the record first before testing connection."),
                    indicator: "orange"
                });
                return;
            }

            if (!frm.doc.ip_address) {
                frappe.msgprint({
                    message: __("Please enter an IP Address before testing."),
                    indicator: "orange"
                });
                return;
            }

            frappe.call({
                method: "saral_hr.utils.biometric_sync.test_connection",
                args: { machine_name: frm.doc.name },
                freeze: true,
                freeze_message: __("Connecting to device..."),
                callback(r) {
                    if (r.message && r.message.success) {
                        frappe.show_alert({
                            message: __("✓ Connection Successful"),
                            indicator: "green"
                        }, 5);
                    } else {
                        frappe.show_alert({
                            message: __("✗ Connection Failed: ") + (r.message ? r.message.message : "Unknown error"),
                            indicator: "red"
                        }, 7);
                    }
                    frm.reload_doc();
                }
            });
        }).addClass("btn-primary");

        // ── Fetch Records button (top right) ──
        frm.add_custom_button(__("Fetch Records"), function () {
            // Block if unsaved
            if (frm.is_new()) {
                frappe.msgprint({
                    title: __("Save Required"),
                    message: __("Please save the record first before fetching records."),
                    indicator: "orange"
                });
                return;
            }

            if (!frm.doc.ip_address) {
                frappe.msgprint({
                    message: __("Please enter an IP Address before fetching."),
                    indicator: "orange"
                });
                return;
            }

            frappe.confirm(
                __("Fetch attendance records from <b>{0}</b> ({1})?", [frm.doc.machine_name, frm.doc.ip_address]),
                function () {
                    frappe.call({
                        method: "saral_hr.utils.biometric_sync.sync_all_machines",
                        freeze: true,
                        freeze_message: __("Fetching records from device..."),
                        callback(r) {
                            if (r.message) {
                                let result = r.message.find(m => m.machine === frm.doc.machine_name);
                                if (result) {
                                    if (result.status === "ok") {
                                        frappe.show_alert({
                                            message: __("✓ Fetched {0} new records", [result.saved]),
                                            indicator: "green"
                                        }, 5);
                                    } else {
                                        frappe.show_alert({
                                            message: __("✗ Fetch failed: ") + result.error,
                                            indicator: "red"
                                        }, 7);
                                    }
                                }
                            }
                            frm.reload_doc();
                        }
                    });
                }
            );
        });
    }
});