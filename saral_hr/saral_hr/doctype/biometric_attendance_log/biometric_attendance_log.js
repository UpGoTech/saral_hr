frappe.ui.form.on("Biometric attendance log", {
    refresh(frm) {
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
                                    frappe.show_alert({ message: __("✓ Employee Checkin created successfully"), indicator: "green" }, 5);
                                    frm.reload_doc();
                                } else {
                                    frappe.show_alert({ message: __("✗ Failed: ") + (r.message ? r.message.message : "Unknown error"), indicator: "red" }, 7);
                                }
                            }
                        });
                    }
                );
            }).addClass("btn-primary");
        }
    }
});

frappe.listview_settings["Biometric attendance log"] = {
    onload(listview) {

        listview.page.add_inner_button(__("Process to Checkin"), function () {
            let d = new frappe.ui.Dialog({
                title: __("Process Attendance Logs to Employee Checkin"),
                fields: [
                    { fieldname: "start_date", fieldtype: "Date", label: __("Start Date"), reqd: 1, default: frappe.datetime.add_days(frappe.datetime.get_today(), -1) },
                    { fieldname: "end_date",   fieldtype: "Date", label: __("End Date"),   reqd: 1, default: frappe.datetime.get_today() },
                    { fieldname: "employee",   fieldtype: "Link", label: __("Employee"),   options: "Employee", description: __("Leave blank to process all employees") },
                    { fieldname: "punch_type", fieldtype: "Select", label: __("Punch Type"), options: "\nIN\nOUT\nUnknown", description: __("Leave blank for all punch types") }
                ],
                primary_action_label: __("Process"),
                primary_action(values) {
                    d.hide();
                    frappe.call({
                        method: "saral_hr.utils.biometric_sync.process_logs_by_date",
                        args: { start_date: values.start_date, end_date: values.end_date, employee: values.employee || null, punch_type: values.punch_type || null },
                        freeze: true,
                        freeze_message: __("Processing attendance logs..."),
                        callback(r) {
                            if (r.message) {
                                let res = r.message;
                                if (res.success) {
                                    frappe.msgprint({ title: __("Processing Complete"), message: __("✓ Processed: <b>{0}</b><br>✗ Failed: <b>{1}</b><br>⟳ Already Done: <b>{2}</b>", [res.processed, res.failed, res.skipped]), indicator: "green" });
                                    listview.refresh();
                                } else {
                                    frappe.msgprint({ title: __("Error"), message: res.message, indicator: "red" });
                                }
                            }
                        }
                    });
                }
            });
            d.show();
        }, __("Actions"));

        listview.page.add_inner_button(__("View Device Employees"), function () {
            show_device_employees_dialog();
        }, __("Actions"));

        listview.page.add_inner_button(__("Attendance Report"), function () {
            show_attendance_report_dialog();
        }, __("Actions"));
    }
};

function show_device_employees_dialog() {
    let machine_dialog = new frappe.ui.Dialog({
        title: __("Select Biometric Machine"),
        fields: [
            {
                fieldname: "machine",
                fieldtype: "Link",
                label: __("Machine"),
                options: "Biometric machine",
                reqd: 1,
                filters: { is_active: 1 },
                description: __("Select the machine to view its registered employees")
            }
        ],
        primary_action_label: __("Fetch Employees"),
        primary_action(values) {
            machine_dialog.hide();
            fetch_and_show_device_employees(values.machine);
        }
    });
    machine_dialog.show();
}

function fetch_and_show_device_employees(machine_name) {
    frappe.call({
        method: "saral_hr.utils.biometric_sync.get_device_employees",
        args: { machine_name },
        freeze: true,
        freeze_message: __("Fetching employee list from device..."),
        callback(r) {
            if (!r.message || !r.message.success) {
                frappe.msgprint({ title: __("Error"), message: r.message ? r.message.message : "Unknown error", indicator: "red" });
                return;
            }

            let users    = r.message.users;
            let total    = r.message.total;
            let mapped   = users.filter(u => u.is_mapped).length;
            let unmapped = total - mapped;

            let rows = users.map((u, i) => {
                if (u.is_mapped) {
                    return `<tr>
                        <td style="padding:6px 10px;color:var(--text-muted);font-size:12px;">${i+1}</td>
                        <td style="padding:6px 10px;font-family:monospace;font-weight:600;">${u.device_id}</td>
                        <td style="padding:6px 10px;">${u.device_name || "—"}</td>
                        <td style="padding:6px 10px;">${u.employee_name}</td>
                        <td style="padding:6px 10px;"><span style="background:#d4edda;color:#155724;padding:2px 10px;border-radius:10px;font-size:11px;font-weight:600;">✓ Mapped</span></td>
                    </tr>`;
                } else {
                    return `<tr style="background:#fff8f8;">
                        <td style="padding:6px 10px;color:var(--text-muted);font-size:12px;">${i+1}</td>
                        <td style="padding:6px 10px;font-family:monospace;font-weight:600;color:#c0392b;">${u.device_id}</td>
                        <td style="padding:6px 10px;">${u.device_name || "—"}</td>
                        <td style="padding:6px 10px;color:var(--text-muted);">—</td>
                        <td style="padding:6px 10px;"><span style="background:#f8d7da;color:#721c24;padding:2px 10px;border-radius:10px;font-size:11px;font-weight:600;">✗ Not mapped</span></td>
                    </tr>`;
                }
            }).join("");

            let result_dialog = new frappe.ui.Dialog({
                title: __("Device Employees — {0}", [machine_name]),
                fields: [{ fieldname: "table_html", fieldtype: "HTML" }],
                size: "large"
            });
            result_dialog.show();

            result_dialog.fields_dict.table_html.$wrapper.html(`
                <div style="margin-bottom:12px;display:flex;gap:16px;flex-wrap:wrap;">
                    <div style="background:#e8f5e9;border-radius:8px;padding:8px 16px;text-align:center;">
                        <div style="font-size:22px;font-weight:700;color:#1b5e20;">${total}</div>
                        <div style="font-size:11px;color:#2e7d32;">Total on device</div>
                    </div>
                    <div style="background:#e8f5e9;border-radius:8px;padding:8px 16px;text-align:center;">
                        <div style="font-size:22px;font-weight:700;color:#1b5e20;">${mapped}</div>
                        <div style="font-size:11px;color:#2e7d32;">Mapped ✓</div>
                    </div>
                    <div style="background:#fff3e0;border-radius:8px;padding:8px 16px;text-align:center;">
                        <div style="font-size:22px;font-weight:700;color:#e65100;">${unmapped}</div>
                        <div style="font-size:11px;color:#bf360c;">Not mapped ✗</div>
                    </div>
                    ${unmapped > 0 ? `<div style="background:#fff3e0;border:1px solid #ffb300;border-radius:8px;padding:8px 14px;font-size:12px;color:#7f4f00;flex:1;">
                        ⚠ Fix: Go to HR → Employee → set the <b>Attendance Device ID</b> field for unmapped employees
                    </div>` : ""}
                </div>
                <div style="overflow-x:auto;">
                    <table style="width:100%;border-collapse:collapse;font-size:13px;">
                        <thead>
                            <tr style="border-bottom:2px solid var(--border-color);">
                                <th style="padding:8px 10px;text-align:left;color:var(--text-muted);">#</th>
                                <th style="padding:8px 10px;text-align:left;">Device ID</th>
                                <th style="padding:8px 10px;text-align:left;">Device Name</th>
                                <th style="padding:8px 10px;text-align:left;">ERPNext Employee</th>
                                <th style="padding:8px 10px;text-align:left;">Status</th>
                            </tr>
                        </thead>
                        <tbody>${rows}</tbody>
                    </table>
                </div>
            `);
        }
    });
}

function show_attendance_report_dialog() {
    let today     = frappe.datetime.get_today();
    let cur_month = today.split("-")[1];
    let cur_year  = today.split("-")[0];

    let filter_dialog = new frappe.ui.Dialog({
        title: __("Employee Monthly Attendance Report"),
        fields: [
            { fieldname: "employee", fieldtype: "Link",   label: __("Employee"), options: "Employee", reqd: 1 },
            { fieldname: "month",    fieldtype: "Select", label: __("Month"), reqd: 1,
              options: "01\n02\n03\n04\n05\n06\n07\n08\n09\n10\n11\n12", default: cur_month },
            { fieldname: "year",     fieldtype: "Int",    label: __("Year"), reqd: 1, default: parseInt(cur_year) }
        ],
        primary_action_label: __("Show Report"),
        primary_action(values) {
            filter_dialog.hide();
            fetch_and_show_report(values.employee, values.month, values.year);
        }
    });
    filter_dialog.show();
}

function fetch_and_show_report(employee, month, year) {
    const MONTH_NAMES = {
        "01":"January","02":"February","03":"March","04":"April",
        "05":"May","06":"June","07":"July","08":"August",
        "09":"September","10":"October","11":"November","12":"December"
    };

    frappe.call({
        method: "saral_hr.utils.biometric_sync.get_employee_monthly_report",
        args: { employee, month, year },
        freeze: true,
        freeze_message: __("Fetching attendance data from machine, please wait..."),
        callback(r) {
            if (!r.message) {
                frappe.msgprint({ title: __("Error"), message: "No response received.", indicator: "red" });
                return;
            }

            let res = r.message;

            if (!res.success) {
                if (res.no_device_id) {
                    frappe.msgprint({
                        title: __("Attendance Device ID Not Mapped"),
                        message: `<b>${res.employee_name}</b> does not have an <b>Attendance Device ID</b> mapped.<br><br>
                            Please go to <b>HR → Employee → ${res.employee_name}</b> and set the Attendance Device ID field.`,
                        indicator: "orange"
                    });
                } else {
                    frappe.msgprint({ title: __("Error"), message: res.message, indicator: "red" });
                }
                return;
            }

            let rows = res.rows.map(row => {
                let bg = "";
                let in_style = "", out_style = "";
                if (row.status === "present") {
                    in_style  = "color:#155724;font-weight:600;";
                    out_style = "color:#1565c0;font-weight:600;";
                } else if (row.status === "absent") {
                    bg = "background:#fff8f8;";
                } else {
                    bg = "background:#f9f9f9;";
                }

                let badge = row.status === "present"
                    ? `<span style="background:#d4edda;color:#155724;padding:2px 8px;border-radius:10px;font-size:11px;">Present</span>`
                    : row.status === "weekend"
                    ? `<span style="background:#eeeeee;color:#666;padding:2px 8px;border-radius:10px;font-size:11px;">Weekend</span>`
                    : `<span style="background:#f8d7da;color:#721c24;padding:2px 8px;border-radius:10px;font-size:11px;">Absent</span>`;

                return `<tr style="${bg}border-bottom:1px solid var(--border-color);">
                    <td style="padding:6px 12px;font-weight:500;">${row.day}</td>
                    <td style="padding:6px 12px;${in_style}font-family:monospace;">${row.in_time}</td>
                    <td style="padding:6px 12px;${out_style}font-family:monospace;">${row.out_time}</td>
                    <td style="padding:6px 12px;">${badge}</td>
                </tr>`;
            }).join("");

            let report_dialog = new frappe.ui.Dialog({
                title: __("{0} — {1} {2}", [res.employee_name, MONTH_NAMES[String(month).padStart(2,"0")] || month, year]),
                fields: [{ fieldname: "report_html", fieldtype: "HTML" }],
                size: "large"
            });
            report_dialog.show();

            report_dialog.fields_dict.report_html.$wrapper.html(`
                <div style="margin-bottom:14px;display:flex;gap:12px;flex-wrap:wrap;align-items:center;">
                    <div style="font-size:13px;color:var(--text-muted);">Device ID: <b style="font-family:monospace;">${res.device_id}</b></div>
                    <div style="background:#e8f5e9;border-radius:8px;padding:6px 14px;text-align:center;">
                        <span style="font-size:18px;font-weight:700;color:#1b5e20;">${res.present_days}</span>
                        <span style="font-size:11px;color:#2e7d32;margin-left:4px;">Present</span>
                    </div>
                    <div style="background:#fff3e0;border-radius:8px;padding:6px 14px;text-align:center;">
                        <span style="font-size:18px;font-weight:700;color:#e65100;">${res.absent_days}</span>
                        <span style="font-size:11px;color:#bf360c;margin-left:4px;">Absent</span>
                    </div>
                    <div style="background:#f5f5f5;border-radius:8px;padding:6px 14px;text-align:center;">
                        <span style="font-size:18px;font-weight:700;color:#333;">${res.total_days}</span>
                        <span style="font-size:11px;color:#666;margin-left:4px;">Total days</span>
                    </div>
                </div>
                <table style="width:100%;border-collapse:collapse;font-size:13px;">
                    <thead>
                        <tr style="border-bottom:2px solid var(--border-color);">
                            <th style="padding:8px 12px;text-align:left;font-weight:600;">Date</th>
                            <th style="padding:8px 12px;text-align:left;font-weight:600;color:#155724;">IN Time</th>
                            <th style="padding:8px 12px;text-align:left;font-weight:600;color:#1565c0;">OUT Time</th>
                            <th style="padding:8px 12px;text-align:left;font-weight:600;">Status</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            `);
        }
    });
}