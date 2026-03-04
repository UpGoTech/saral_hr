frappe.ui.form.on("Company Link", {

    refresh(frm) {
        if (frm.doc.is_active) {
            frm.page.set_indicator(__("Active"), "green");
        } else {
            frm.page.set_indicator(__("Inactive"), "gray");
        }

        if (frm.doc.employee && !frm.is_new()) {
            frm.add_custom_button(__("View All Records"), function () {
                frappe.set_route("List", "Company Link", {
                    employee: frm.doc.employee
                });
            });
        }

        if (!frm.is_new()) {
            refresh_company_fields(frm);
        }
    },

    company(frm) {
        if (!frm.is_new()) {
            refresh_company_fields(frm);
        }
    },

    employee(frm) {
        const selected_employee = frm.doc.employee;
        if (!selected_employee || !frm.is_new()) return;

        // Frappe fires the trigger twice on Link field select (value + fetch).
        // Guard so we only warn once per unique employee selection.
        if (frm._last_warned_employee === selected_employee) return;
        frm._last_warned_employee = selected_employee;

        check_and_warn_transfer(frm, selected_employee);
    },

    date_of_joining(frm) {
        if (!frm.is_new() || !frm.doc.employee || !frm.doc.date_of_joining) return;

        find_active_record(frm.doc.employee).then(record => {
            if (record) {
                const leaving = frappe.datetime.add_days(frm.doc.date_of_joining, -1);
                frappe.msgprint({
                    title: __("Transfer Preview"),
                    indicator: "blue",
                    message: __(
                        "On save, the active record at {0} will be archived with leaving date {1}. "
                        + "This record will become active.",
                        [record.company, leaving]
                    )
                });
            }
        });
    },

    left_date(frm) {
        if (frm.doc.left_date && frm.doc.is_active) {
            frappe.msgprint({
                title: __("Record will be Deactivated"),
                indicator: "orange",
                message: __(
                    "Left date has been set to {0}. On save, this record will be marked as Inactive.",
                    [frm.doc.left_date]
                )
            });
            frm.set_value("is_active", 0);
        }
    }
});

function find_active_record(employee) {
    return frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: "Company Link",
            filters: [
                ["employee", "=", employee],
                ["is_active", "=", 1]
            ],
            fields: ["name", "company", "employee", "is_active"],
            limit: 5
        }
    }).then(r => {
        if (r.message && r.message.length > 0) {
            return r.message[0];
        }
        return null;
    });
}

function check_and_warn_transfer(frm, employee) {
    find_active_record(employee).then(record => {
        if (record) {
            frappe.msgprint({
                title: __("Employee Currently Active"),
                indicator: "orange",
                message: __(
                    "<b>{0}</b> is currently active at <b>{1}</b> (Record: {2}).<br><br>"
                    + "Saving this record will archive that record and set its leaving date "
                    + "to one day before the new joining date.<br><br>"
                    + "Please make sure the <b>Date of Joining</b> is correct before saving.",
                    [employee, record.company, record.name]
                )
            });
        }
    }).catch(err => {
        console.error("Transfer check error:", err);
    });
}

function refresh_company_fields(frm) {
    if (!frm.doc.company || frm.is_new()) return;

    frappe.db.get_value(
        "Company",
        frm.doc.company,
        ["default_holiday_list"],
        (r) => {
            if (!r) return;

            if (r.default_holiday_list &&
                r.default_holiday_list !== frm.doc.holiday_list) {

                frm.set_value("holiday_list", r.default_holiday_list);

                setTimeout(() => {
                    if (frm.is_dirty()) {
                        frm.save().then(() => {
                            frappe.msgprint({
                                title: __("Holiday List Updated"),
                                indicator: "green",
                                message: __(
                                    "Holiday list has been updated to {0} based on company settings.",
                                    [r.default_holiday_list]
                                )
                            });
                        });
                    }
                }, 500);
            }
        }
    );
}