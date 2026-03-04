// ─── Form Events ──────────────────────────────────────────────────────────────

frappe.ui.form.on("Salary Slip", {
    refresh(frm) {
        if (!frm.doc.currency) {
            frm.set_value("currency", "INR");
        }
        frm.set_query("employee", () => ({
            filters: { is_active: 1 }
        }));
    },

    employee(frm) {
        if (!frm.doc.employee) return;
        reset_form(frm);

        frappe.db.get_value("Company Link", frm.doc.employee, "category", (r) => {
            if (r && r.category) {
                frappe.db.get_value("Category", r.category, "salary_calculation_based_on", (cat) => {
                    if (cat && cat.salary_calculation_based_on) {
                        frm.set_value("working_days_calculation_method", cat.salary_calculation_based_on);
                    }
                    if (frm.doc.start_date) {
                        check_duplicate_and_fetch(frm);
                    }
                });
            } else {
                if (frm.doc.start_date) {
                    check_duplicate_and_fetch(frm);
                }
            }
        });
    },

    start_date(frm) {
        if (!frm.doc.start_date) return;
        set_end_date(frm);
        if (frm.doc.employee) {
            check_duplicate_and_fetch(frm);
        }
    },

    working_days_calculation_method(frm) {
        if (!frm.doc.employee || !frm.doc.start_date) return;
        frappe.call({
            method: "saral_hr.saral_hr.doctype.salary_slip.salary_slip.get_attendance_and_days",
            args: {
                employee: frm.doc.employee,
                start_date: frm.doc.start_date,
                working_days_calculation_method: frm.doc.working_days_calculation_method
            },
            callback(r) {
                if (!r.message) return;
                apply_attendance(frm, r.message);
            }
        });
    }
});

frappe.ui.form.on("Salary Details", {
    amount(frm)           { recalculate_salary(frm); },
    earnings_remove(frm)  { recalculate_salary(frm); },
    deductions_remove(frm){ recalculate_salary(frm); }
});

// ─── Core Form Functions ──────────────────────────────────────────────────────

function check_duplicate_and_fetch(frm) {
    frappe.call({
        method: "saral_hr.saral_hr.doctype.salary_slip.salary_slip.check_duplicate_salary_slip",
        args: {
            employee:    frm.doc.employee,
            start_date:  frm.doc.start_date,
            current_doc: frm.doc.name || ""
        },
        callback(r) {
            if (r.message && r.message.status === "duplicate") {
                frappe.msgprint({
                    title:   __("Duplicate Salary Slip"),
                    message: r.message.message,
                    indicator: "red"
                });
                frm.set_value("start_date", "");
                return;
            }
            fetch_and_validate_all(frm);
        }
    });
}

function set_end_date(frm) {
    const start = frappe.datetime.str_to_obj(frm.doc.start_date);
    const end   = new Date(start.getFullYear(), start.getMonth() + 1, 0);
    frm.set_value("end_date", frappe.datetime.obj_to_str(end));
}

function fetch_and_validate_all(frm) {
    frm.page.btn_primary.prop("disabled", false);
    frm.clear_table("earnings");
    frm.clear_table("deductions");

    let salary_data     = null;
    let attendance_data = null;
    let vpa_status      = null;
    let vpa_percentage  = 0;

    let pending = 3;

    function try_finalize() {
        if (--pending > 0) return;

        const unmet = [];

        if (!salary_data) {
            unmet.push("No Salary Structure has been assigned for the selected payroll period.");
        }
        if (vpa_status && vpa_status.status === "missing") {
            unmet.push(vpa_status.message.replace(/<[^>]+>/g, ""));
        }
        if (!attendance_data) {
            unmet.push("Attendance data could not be retrieved for the selected period. Please verify attendance records.");
        } else if (attendance_data.attendance_count === 0) {
            unmet.push("No attendance has been recorded for this employee in the selected month.");
        }

        if (unmet.length > 0) {
            const bullets = unmet
                .map(e => `<li style="margin-bottom:6px;">${e}</li>`)
                .join("");
            frappe.msgprint({
                title:   __("Payroll Processing Requirements Not Met"),
                message: `
                    <div style="margin-bottom:8px;font-weight:600;">
                        Please resolve the following before saving this salary slip:
                    </div>
                    <ul style="margin:0;padding-left:18px;line-height:1.7;">${bullets}</ul>
                `,
                indicator: "red"
            });
            frm.page.btn_primary.prop("disabled", true);
            return;
        }

        apply_salary_structure(frm, salary_data);
        apply_attendance(frm, attendance_data, flt(vpa_percentage) / 100);
        frm.page.btn_primary.prop("disabled", false);
    }

    frappe.call({
        method: "saral_hr.saral_hr.doctype.salary_slip.salary_slip.get_salary_structure_for_employee",
        args: { employee: frm.doc.employee, start_date: frm.doc.start_date },
        callback(r) { salary_data = r.message || null; try_finalize(); },
        error()     { salary_data = null; try_finalize(); }
    });

    frappe.call({
        method: "saral_hr.saral_hr.doctype.salary_slip.salary_slip.check_variable_pay_assignment",
        args: { employee: frm.doc.employee, start_date: frm.doc.start_date },
        callback(r) {
            vpa_status = r.message || { status: "ok" };
            if (vpa_status.status === "ok") {
                frappe.call({
                    method: "saral_hr.saral_hr.doctype.salary_slip.salary_slip.get_variable_pay_percentage",
                    args: { employee: frm.doc.employee, start_date: frm.doc.start_date },
                    callback(vr) { vpa_percentage = flt(vr.message || 0); try_finalize(); },
                    error()      { vpa_percentage = 0; try_finalize(); }
                });
            } else {
                try_finalize();
            }
        },
        error() { vpa_status = { status: "ok" }; try_finalize(); }
    });

    frappe.call({
        method: "saral_hr.saral_hr.doctype.salary_slip.salary_slip.get_attendance_and_days",
        args: {
            employee:    frm.doc.employee,
            start_date:  frm.doc.start_date,
            working_days_calculation_method: frm.doc.working_days_calculation_method
        },
        callback(r) { attendance_data = r.message || null; try_finalize(); },
        error()     { attendance_data = null; try_finalize(); }
    });
}

// ─── Helpers to Apply Fetched Data ───────────────────────────────────────────

function apply_salary_structure(frm, data) {
    frm.set_value("salary_structure", data.salary_structure);
    frm.clear_table("earnings");
    frm.clear_table("deductions");

    (data.earnings || []).forEach(row => {
        const e = frm.add_child("earnings");
        Object.assign(e, row);
        e.base_amount = row.amount;
    });

    (data.deductions || []).forEach(row => {
        const d = frm.add_child("deductions");
        Object.assign(d, row);
        d.base_amount = row.amount;
    });

    frm.refresh_fields(["earnings", "deductions"]);
}

function apply_attendance(frm, d, variable_pay_pct) {
    frm.set_value({
        total_working_days: d.working_days,
        payment_days:       d.payment_days,
        present_days:       d.present_days,
        absent_days:        d.absent_days,
        weekly_offs_count:  d.weekly_offs,
        total_half_days:    d.total_half_days,
        total_lwp:          d.total_lwp      || 0,
        total_holidays:     d.total_holidays || 0
    });

    if (variable_pay_pct !== undefined) {
        frm.variable_pay_percentage = variable_pay_pct;
    }

    recalculate_salary(frm, d.working_days, d.payment_days);
}

// ─── Salary Calculation ───────────────────────────────────────────────────────

function recalculate_salary(frm, wd_override, pd_override) {
    let total_earnings = 0;
    let total_deductions = 0;
    let total_basic_da = 0;
    let total_employer_contribution = 0;
    let retention = 0;

    const wd = flt(wd_override !== undefined ? wd_override : frm.doc.total_working_days);
    const pd = flt(pd_override !== undefined ? pd_override : frm.doc.payment_days);
    const variable_pct = flt(frm.variable_pay_percentage || 0);

    const is_worker = (frm.doc.category || "").toLowerCase() === "worker";

    const PF_WAGE_CEILING = 15000; // EPFO statutory wage ceiling

    let basic_amount      = 0;
    let da_amount         = 0;
    let conveyance_amount = 0;
    let special_allowance = 0;

    (frm.doc.earnings || []).forEach(row => {
        const base = flt(row.base_amount || row.amount || 0);
        row.base_amount = base;

        let amount = 0;
        const comp = (row.salary_component || "").toLowerCase();

        if (comp.includes("variable")) {
            amount = (wd > 0 && row.depends_on_payment_days)
                ? (base / wd) * pd * variable_pct
                : base * variable_pct;

        } else if (row.is_daily_rate) {
            amount = base * pd;

        } else if (row.depends_on_payment_days && wd > 0) {
            amount = (base / wd) * pd;

        } else {
            amount = base;
        }

        row.amount = flt(amount, 2);
        total_earnings += row.amount;

        if (comp.includes("basic"))                            basic_amount      = row.amount;
        if (comp.includes("da") || comp.includes("dearness")) da_amount         = row.amount;
        if (comp.includes("conveyance"))                       conveyance_amount = row.amount;
        if (comp.includes("special"))                          special_allowance = row.amount;
    });

    total_basic_da = basic_amount + da_amount;

    (frm.doc.deductions || []).forEach(row => {
        const base = flt(row.base_amount || row.amount || 0);
        row.base_amount = base;

        let amount = 0;
        const comp = (row.salary_component || "").toLowerCase();

        if (comp.includes("esic") && !comp.includes("employer")) {
            amount = (base > 0 && total_earnings < 21000)
                ? flt((total_earnings - conveyance_amount) * 0.0075, 2)
                : 0;

        } else if (comp.includes("esic") && comp.includes("employer")) {
            amount = (base > 0 && total_earnings < 21000)
                ? flt((total_earnings - conveyance_amount) * 0.0325, 2)
                : 0;

        } else if (comp.includes("pf") || comp.includes("provident")) {
            const pf_base = is_worker
                ? (basic_amount + special_allowance)
                : (basic_amount + da_amount);
            const capped_pf_base = Math.min(pf_base, PF_WAGE_CEILING); // ← ₹15,000 cap
            amount = base > 0 ? flt(capped_pf_base * 0.12, 2) : 0;

        } else if (row.is_daily_rate) {
            amount = base * pd;

        } else if (row.depends_on_payment_days && wd > 0 && base > 0) {
            amount = (base / wd) * pd;

        } else {
            amount = base;
        }

        row.amount = flt(amount, 2);

        if (row.employer_contribution) {
            total_employer_contribution += row.amount;
        } else {
            total_deductions += row.amount;
        }

        if (comp.includes("retention")) retention += row.amount;
    });

    frm.set_value({
        total_earnings:              flt(total_earnings, 2),
        total_deductions:            flt(total_deductions, 2),
        net_salary:                  flt(total_earnings - total_deductions, 2),
        total_basic_da:              flt(total_basic_da, 2),
        total_employer_contribution: flt(total_employer_contribution, 2),
        retention:                   flt(retention, 2)
    });

    frm.refresh_fields(["earnings", "deductions"]);
}

function reset_form(frm) {
    frm.clear_table("earnings");
    frm.clear_table("deductions");

    frm.set_value({
        total_working_days:          0,
        payment_days:                0,
        present_days:                0,
        absent_days:                 0,
        weekly_offs_count:           0,
        total_half_days:             0,
        total_lwp:                   0,
        total_holidays:              0,
        total_earnings:              0,
        total_deductions:            0,
        net_salary:                  0,
        total_basic_da:              0,
        total_employer_contribution: 0,
        retention:                   0,
        working_days_calculation_method: ""
    });

    frm.variable_pay_percentage = 0;
    frm.page.btn_primary.prop("disabled", false);
    frm.refresh_fields();
}