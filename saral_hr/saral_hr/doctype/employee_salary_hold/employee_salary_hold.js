frappe.ui.form.on("Employee Salary Hold", {

    setup(frm) {
        frm.set_query("employee", () => ({
            filters: { is_active: 1 }
        }));
    },

    refresh(frm) {
        frm.trigger("set_field_visibility");
        frm.trigger("add_custom_buttons");
        frm.trigger("set_status_indicator");
    },

    employee(frm) {
        if (!frm.doc.employee) {
            frm.set_value("employee_name", "");
            frm.set_value("company",       "");
            frm.set_value("department",    "");
            frm.set_value("designation",   "");
            frm.set_value("branch",        "");
            return;
        }

        // Company Link is named by employee field value, so name = employee ID
        frappe.db.get_value(
            "Company Link",
            frm.doc.employee,
            ["full_name", "company", "department", "designation", "branch"],
            (r) => {
                if (r) {
                    frm.set_value("employee_name", r.full_name    || "");
                    frm.set_value("company",       r.company      || "");
                    frm.set_value("department",    r.department   || "");
                    frm.set_value("designation",   r.designation  || "");
                    frm.set_value("branch",        r.branch       || "");
                }
            }
        );

        const now = new Date();
        const months = ["January","February","March","April","May","June",
                        "July","August","September","October","November","December"];
        frm.set_value("month", months[now.getMonth()]);
        frm.set_value("year", String(now.getFullYear()));
    },

    status(frm) {
        frm.trigger("set_field_visibility");
        frm.trigger("set_status_indicator");
    },

    set_field_visibility(frm) {
        const is_released = frm.doc.status === "Released";
        frm.toggle_display("release_date",   is_released);
        frm.toggle_display("release_reason", is_released);
        frm.toggle_reqd("release_date",      is_released);
        frm.toggle_reqd("release_reason",    is_released);
    },

    set_status_indicator(frm) {
        if (!frm.doc.__islocal) {
            let color = "red";
            if (frm.doc.status === "Released")    color = "green";
            if (frm.doc.status === "Was On Hold") color = "orange";
            frm.page.set_indicator(__(frm.doc.status), color);
        }
    },

    add_custom_buttons(frm) {
        frm.clear_custom_buttons();

        if (frm.doc.docstatus === 1 && frm.doc.status === "On Hold") {
            frm.add_custom_button(__("Release Hold"), () => {
                frm.trigger("show_release_dialog");
            }, __("Actions")).addClass("btn-success");
        }
    },

    show_release_dialog(frm) {
        const d = new frappe.ui.Dialog({
            title: __("Release Salary Hold"),
            fields: [
                {
                    fieldname: "release_date",
                    fieldtype: "Date",
                    label: __("Release Date"),
                    default: frappe.datetime.get_today(),
                    reqd: 1
                },
                {
                    fieldname: "release_reason",
                    fieldtype: "Small Text",
                    label: __("Reason for Release"),
                    reqd: 1
                }
            ],
            primary_action_label: __("Release"),
            primary_action({ release_date, release_reason }) {
                frappe.call({
                    method: "saral_hr.saral_hr.doctype.employee_salary_hold.employee_salary_hold.release_salary_hold",
                    args: {
                        hold_name: frm.doc.name,
                        release_date,
                        release_reason
                    },
                    freeze: true,
                    freeze_message: __("Releasing salary hold..."),
                    callback(r) {
                        d.hide();
                        if (r.message) {
                            frappe.show_alert({
                                message: __("Salary hold released. Record: {0}", [r.message]),
                                indicator: "green"
                            });
                            frappe.set_route("Form", "Employee Salary Hold", r.message);
                        }
                    }
                });
            }
        });
        d.show();
    }
});


frappe.listview_settings["Employee Salary Hold"] = {
    add_fields: ["status", "docstatus"],

    get_indicator(doc) {
        if (doc.status === "Was On Hold") return [__("Was On Hold"), "orange", "status,=,Was On Hold"];
        if (doc.status === "On Hold")     return [__("On Hold"),     "red",    "status,=,On Hold"];
        if (doc.status === "Released")    return [__("Released"),    "green",  "status,=,Released"];
    },

    onload(listview) {
        listview.page.add_action_item(__("Release Selected"), () => {
            const selected = listview.get_checked_items();
            if (!selected.length) {
                frappe.msgprint(__("Please select at least one record."));
                return;
            }

            const on_hold = selected.filter(r => r.status === "On Hold" && r.docstatus === 1);
            if (!on_hold.length) {
                frappe.msgprint(__("No submitted 'On Hold' records selected."));
                return;
            }

            const d = new frappe.ui.Dialog({
                title: __("Bulk Release Salary Hold"),
                fields: [
                    {
                        fieldname: "release_date",
                        fieldtype: "Date",
                        label: __("Release Date"),
                        default: frappe.datetime.get_today(),
                        reqd: 1
                    },
                    {
                        fieldname: "release_reason",
                        fieldtype: "Small Text",
                        label: __("Reason for Release"),
                        reqd: 1
                    }
                ],
                primary_action_label: __("Release All"),
                primary_action({ release_date, release_reason }) {
                    d.hide();
                    const promises = on_hold.map(rec =>
                        frappe.call({
                            method: "saral_hr.saral_hr.doctype.employee_salary_hold.employee_salary_hold.release_salary_hold",
                            args: { hold_name: rec.name, release_date, release_reason }
                        })
                    );
                    Promise.all(promises).then(() => {
                        frappe.show_alert({
                            message: __("{0} hold(s) released successfully.", [on_hold.length]),
                            indicator: "green"
                        });
                        listview.refresh();
                    });
                }
            });
            d.show();
        });
    }
};