// Copyright (c) 2026, sj and contributors

frappe.ui.form.on("Leave Application", {

    refresh(frm) {
        set_status_intro(frm);
        render_leave_balance_table(frm);
    },

    employee(frm) {
        render_leave_balance_table(frm);
        check_weekly_off_warning(frm);
    },

    leave_type(frm) {
        fetch_single_balance(frm);
    },

    from_date(frm) {
        calculate_total_days(frm);
        fetch_single_balance(frm);
        render_leave_balance_table(frm);
        check_weekly_off_warning(frm);
        check_overlap(frm);
    },

    to_date(frm) {
        calculate_total_days(frm);
        check_weekly_off_warning(frm);
        check_overlap(frm);
    },

    half_day(frm) {
        calculate_total_days(frm);
    },

    half_day_date(frm) {
        calculate_total_days(frm);
    }

});


// ─── Status intro banner ──────────────────────────────────────────────────────

function set_status_intro(frm) {
    if (frm.doc.status === "Approved") {
        frm.set_intro(__("This leave has been approved."), "green");
    } else if (frm.doc.status === "Rejected") {
        frm.set_intro(__("This leave has been rejected."), "red");
    } else {
        frm.set_intro("");
    }
}


// ─── Total days calculation ───────────────────────────────────────────────────

function calculate_total_days(frm) {
    if (!frm.doc.from_date || !frm.doc.to_date) return;

    let diff = frappe.datetime.get_diff(frm.doc.to_date, frm.doc.from_date) + 1;

    if (diff <= 0) {
        frappe.msgprint(__("To Date must be on or after From Date."));
        frm.set_value("to_date", "");
        frm.set_value("total_days", 0);
        return;
    }

    let total = diff;

    if (frm.doc.half_day && frm.doc.half_day_date) {
        let hd = frm.doc.half_day_date;
        let fd = frm.doc.from_date;
        let td = frm.doc.to_date;
        if (hd >= fd && hd <= td) {
            // Half day inside range — that day = 0.5 instead of 1
            total = diff - 0.5;
        } else {
            // Half day outside range — extra partial day
            total = diff + 0.5;
        }
    } else if (frm.doc.half_day) {
        total = diff + 0.5;
    }

    frm.set_value("total_days", total);
}


// ─── Single balance fetch ─────────────────────────────────────────────────────

function fetch_single_balance(frm) {
    if (!frm.doc.employee || !frm.doc.leave_type || !frm.doc.from_date) return;

    frappe.db.get_value(
        "Leave Allocation",
        {
            employee: frm.doc.employee,
            leave_type: frm.doc.leave_type,
            from_date: ["<=", frm.doc.from_date],
            to_date: [">=", frm.doc.from_date]
        },
        "remaining_leaves",
        (r) => {
            frm.set_value(
                "leave_balance",
                (r && r.remaining_leaves != null) ? r.remaining_leaves : 0
            );
        }
    );
}


// ─── Weekly Off warning ───────────────────────────────────────────────────────

function check_weekly_off_warning(frm) {
    if (!frm.doc.employee || !frm.doc.from_date || !frm.doc.to_date) return;

    frappe.call({
        method: "saral_hr.saral_hr.doctype.leave_application.leave_application.get_weekly_off_days_in_range",
        args: {
            employee: frm.doc.employee,
            from_date: frm.doc.from_date,
            to_date: frm.doc.to_date,
        },
        callback(r) {
            if (!r.message || !r.message.length) return;

            let dates = r.message.join(", ");
            frappe.show_alert({
                message: __(
                    "Your leave range includes {0} Weekly Off day(s): {1}. " +
                    "These days will be overridden with the leave status in Attendance.",
                    [r.message.length, dates]
                ),
                indicator: "orange"
            }, 8);
        }
    });
}


// ─── Overlap check ────────────────────────────────────────────────────────────

function check_overlap(frm) {
    if (!frm.doc.employee || !frm.doc.from_date || !frm.doc.to_date) return;

    frappe.db.get_value(
        "Leave Application",
        {
            employee: frm.doc.employee,
            status: "Approved",
            name: ["!=", frm.doc.name || ""],
            from_date: ["<=", frm.doc.to_date],
            to_date: [">=", frm.doc.from_date],
        },
        "name",
        (r) => {
            if (r && r.name) {
                frappe.show_alert({
                    message: __(
                        "Warning: An approved leave {0} already exists that overlaps with these dates.",
                        [r.name]
                    ),
                    indicator: "red"
                }, 8);
            }
        }
    );
}


// ─── Full balance table ───────────────────────────────────────────────────────

function render_leave_balance_table(frm) {
    let $wrapper = frm.fields_dict["leave_balance_html"].$wrapper;

    $wrapper.html(
        `<p class="text-muted" style="padding: 4px 0;">${__("Loading leave balances...")}</p>`
    );

    if (!frm.doc.employee) {
        $wrapper.html(
            `<p class="text-muted" style="padding: 4px 0;">${__("Select an employee to view leave balances.")}</p>`
        );
        return;
    }

    let date = frm.doc.from_date || frappe.datetime.get_today();

    frappe.call({
        method: "saral_hr.saral_hr.doctype.leave_application.leave_application.get_employee_leave_balances",
        args: { employee: frm.doc.employee, date: date },
        callback(r) {
            if (!r.message || !r.message.length) {
                $wrapper.html(
                    `<p class="text-muted" style="padding: 4px 0;">${__("No leave allocations found for this employee.")}</p>`
                );
                return;
            }

            let rows = r.message.map(d => {
                let bal_color = d.remaining <= 0
                    ? "color: var(--red-500); font-weight: 600;"
                    : "color: var(--green-600); font-weight: 600;";

                // Warn row if balance will go to zero after this application
                let row_bg = "";
                if (
                    frm.doc.leave_type === d.leave_type &&
                    frm.doc.total_days &&
                    (d.remaining - frm.doc.total_days) <= 0
                ) {
                    row_bg = "background: var(--yellow-highlight-color, #fff8e1);";
                }

                return `
                    <tr style="${row_bg}">
                        <td style="padding: 7px 12px; border-bottom: 1px solid var(--border-color);">
                            ${d.leave_type}
                        </td>
                        <td style="padding: 7px 12px; text-align: center; border-bottom: 1px solid var(--border-color);">
                            ${d.allocated}
                        </td>
                        <td style="padding: 7px 12px; text-align: center; border-bottom: 1px solid var(--border-color);">
                            ${d.used}
                        </td>
                        <td style="padding: 7px 12px; text-align: center; border-bottom: 1px solid var(--border-color); ${bal_color}">
                            ${d.remaining}
                        </td>
                    </tr>
                `;
            }).join("");

            let html = `
                <table style="
                    width: 100%;
                    border-collapse: collapse;
                    font-size: var(--text-sm);
                    border: 1px solid var(--border-color);
                    border-radius: var(--border-radius);
                    overflow: hidden;
                    background: var(--card-bg);
                ">
                    <thead>
                        <tr style="background: var(--subtle-fg);">
                            <th style="padding: 8px 12px; text-align: left; font-weight: 600; color: var(--text-muted); border-bottom: 1px solid var(--border-color);">
                                Leave Type
                            </th>
                            <th style="padding: 8px 12px; text-align: center; font-weight: 600; color: var(--text-muted); border-bottom: 1px solid var(--border-color);">
                                Allocated
                            </th>
                            <th style="padding: 8px 12px; text-align: center; font-weight: 600; color: var(--text-muted); border-bottom: 1px solid var(--border-color);">
                                Used
                            </th>
                            <th style="padding: 8px 12px; text-align: center; font-weight: 600; color: var(--text-muted); border-bottom: 1px solid var(--border-color);">
                                Balance
                            </th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            `;

            $wrapper.html(html);
        }
    });
}