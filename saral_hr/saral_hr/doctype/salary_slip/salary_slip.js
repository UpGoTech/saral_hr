// Copyright (c) 2026, sj and contributors
// For license information, please see license.txt

frappe.ui.form.on("Salary Slip", {

    refresh(frm) {
        if (!frm.doc.currency) frm.set_value("currency", "INR");
        frm.set_query("employee", () => ({ filters: { is_active: 1 } }));
    },

    employee(frm) {
        if (!frm.doc.employee) return;
        reset_form(frm);
        frappe.db.get_value("Company Link", frm.doc.employee, "company", (r) => {
            if (r && r.company) {
                frappe.db.get_value("Company", r.company, "salary_calculation_based_on", (comp) => {
                    if (comp && comp.salary_calculation_based_on)
                        frm.set_value("working_days_calculation_method", comp.salary_calculation_based_on);
                    if (frm.doc.start_date) check_duplicate_and_fetch(frm);
                });
            } else {
                if (frm.doc.start_date) check_duplicate_and_fetch(frm);
            }
        });
    },

    start_date(frm) {
        if (!frm.doc.start_date) return;
        set_end_date(frm);
        if (frm.doc.employee) check_duplicate_and_fetch(frm);
    },

    working_days_calculation_method(frm) {
        if (!frm.doc.employee || !frm.doc.start_date) return;
        frappe.call({
            method: "saral_hr.saral_hr.doctype.salary_slip.salary_slip.get_attendance_and_days",
            args: {
                employee:                        frm.doc.employee,
                start_date:                      frm.doc.start_date,
                working_days_calculation_method: frm.doc.working_days_calculation_method
            },
            callback(r) { if (r.message) apply_attendance(frm, r.message); }
        });
    }
});

frappe.ui.form.on("Salary Details", {
    amount(frm)                  { recalculate_salary(frm); },
    earnings_remove(frm)         { recalculate_salary(frm); },
    deductions_remove(frm)       { recalculate_salary(frm); },
    employer_share_remove(frm)   { recalculate_salary(frm); }
});

// ─── DA detection ─────────────────────────────────────────────────────────────

function is_da_component(comp_name, abbr) {
    const n = (comp_name || '').toLowerCase();
    const a = (abbr     || '').toLowerCase().trim();
    return n.includes('dearness') || n === 'da'
        || a === 'da' || a.startsWith('da-') || a.startsWith('da ')
        || a === 'da - dr' || a.startsWith('da-dr');
}

// ─── Statutory component detection ───────────────────────────────────────────

const STATUTORY_NAMES = new Set([
    "Employee ESIC", "Employer ESIC",
    "Employee PF", "Employer PF",
    "Employer EPS", "Employer EDLI", "Employer PF Admin Charges",
    "Professional Tax",
    "Employee Labour Welfare Fund", "Employer Labour Welfare Fund"
]);

function is_statutory(comp_name) {
    return STATUTORY_NAMES.has((comp_name || "").trim());
}

function is_pt(comp_name) {
    return (comp_name || "").trim() === "Professional Tax";
}

// ─── Duplicate check + full fetch ─────────────────────────────────────────────

function check_duplicate_and_fetch(frm) {
    frappe.call({
        method: "saral_hr.saral_hr.doctype.salary_slip.salary_slip.check_duplicate_salary_slip",
        args: { employee: frm.doc.employee, start_date: frm.doc.start_date, current_doc: frm.doc.name || "" },
        callback(r) {
            if (r.message && r.message.status === "duplicate") {
                frappe.msgprint({ title: __("Duplicate Salary Slip"), message: r.message.message, indicator: "red" });
                frm.set_value("start_date", "");
                return;
            }
            fetch_and_validate_all(frm);
        }
    });
}

function set_end_date(frm) {
    const s = frappe.datetime.str_to_obj(frm.doc.start_date);
    frm.set_value("end_date", frappe.datetime.obj_to_str(new Date(s.getFullYear(), s.getMonth() + 1, 0)));
}

// ─── Parallel data fetch + validation ────────────────────────────────────────

function fetch_and_validate_all(frm) {
    frm.page.btn_primary.prop("disabled", false);
    frm.clear_table("earnings");
    frm.clear_table("deductions");
    frm.clear_table("employer_share");

    let attendance_data = null;
    let vpa_status      = null;
    let vpa_percentage  = 0;
    let additional_data = { earnings: [], deductions: [] };
    let pending         = 3;

    function try_finalize() {
        if (--pending > 0) return;

        const att_args = attendance_data ? {
            working_days:            attendance_data.working_days,
            payment_days:            attendance_data.payment_days,
            physical_working_days:   attendance_data.physical_working_days || 0,
            variable_pay_percentage: vpa_percentage
        } : {};

        frappe.call({
            method: "saral_hr.saral_hr.doctype.salary_slip.salary_slip.get_salary_structure_for_employee",
            args: Object.assign(
                { employee: frm.doc.employee, start_date: frm.doc.start_date },
                att_args
            ),
            callback(r) {
                const salary_data = r.message || null;

                const unmet = [];
                if (!salary_data)
                    unmet.push("No Salary Structure has been assigned for the selected payroll period.");
                if (vpa_status && vpa_status.status === "missing")
                    unmet.push(vpa_status.message.replace(/<[^>]+>/g, ""));
                if (!attendance_data)
                    unmet.push("Attendance data could not be retrieved. Please verify attendance records.");
                else if (attendance_data.attendance_count === 0)
                    unmet.push("No attendance has been recorded for this employee in the selected month.");

                if (unmet.length) {
                    frappe.msgprint({
                        title: __("Payroll Processing Requirements Not Met"),
                        message: `<div style="margin-bottom:8px;font-weight:600;">Please resolve the following before saving:</div>
                            <ul style="margin:0;padding-left:18px;line-height:1.7;">
                                ${unmet.map(e => `<li style="margin-bottom:6px;">${e}</li>`).join("")}
                            </ul>`,
                        indicator: "red"
                    });
                    frm.page.btn_primary.prop("disabled", true);
                    return;
                }

                apply_salary_structure(frm, salary_data);

                (additional_data.earnings || []).forEach(row => {
                    const e = frm.add_child("earnings");
                    e.salary_component                 = row.salary_component;
                    e.abbr                             = row.abbr || "";
                    e.amount                           = flt(row.amount);
                    e.base_amount                      = flt(row.amount);
                    e.depends_on_payment_days          = 0;
                    e.depends_on_physical_working_days = 0;
                    e._is_additional                   = true;
                });

                (additional_data.deductions || []).forEach(row => {
                    const d = frm.add_child("deductions");
                    d.salary_component                 = row.salary_component;
                    d.abbr                             = row.abbr || "";
                    d.amount                           = flt(row.amount);
                    d.base_amount                      = flt(row.amount);
                    d.employer_contribution            = 0;
                    d.depends_on_payment_days          = 0;
                    d.depends_on_physical_working_days = 0;
                    d._is_additional                   = true;
                });

                frm.refresh_fields(["earnings", "deductions", "employer_share"]);
                apply_attendance(frm, attendance_data, flt(vpa_percentage) / 100);
                frm.page.btn_primary.prop("disabled", false);
            },
            error() {
                frappe.msgprint({ title: __("Error"), message: "Failed to fetch salary structure.", indicator: "red" });
                frm.page.btn_primary.prop("disabled", true);
            }
        });
    }

    // ── VPA check ────────────────────────────────────────────────────────
    frappe.call({
        method: "saral_hr.saral_hr.doctype.salary_slip.salary_slip.check_variable_pay_assignment",
        args:   { employee: frm.doc.employee, start_date: frm.doc.start_date },
        callback(r) {
            vpa_status = r.message || { status: "ok" };
            if (vpa_status.status === "ok") {
                pending++;
                frappe.call({
                    method: "saral_hr.saral_hr.doctype.salary_slip.salary_slip.get_variable_pay_percentage",
                    args:   { employee: frm.doc.employee, start_date: frm.doc.start_date },
                    callback(vr) { vpa_percentage = flt(vr.message || 0); try_finalize(); },
                    error()      { vpa_percentage = 0;                    try_finalize(); }
                });
            }
            try_finalize();
        },
        error() { vpa_status = { status: "ok" }; try_finalize(); }
    });

    // ── Attendance ───────────────────────────────────────────────────────
    frappe.call({
        method: "saral_hr.saral_hr.doctype.salary_slip.salary_slip.get_attendance_and_days",
        args:   {
            employee:                        frm.doc.employee,
            start_date:                      frm.doc.start_date,
            working_days_calculation_method: frm.doc.working_days_calculation_method
        },
        callback(r) { attendance_data = r.message || null; try_finalize(); },
        error()     { attendance_data = null;              try_finalize(); }
    });

    // ── Additional components ─────────────────────────────────────────────
    frappe.call({
        method: "saral_hr.saral_hr.doctype.salary_slip.salary_slip.get_additional_components_api",
        args:   { employee: frm.doc.employee, start_date: frm.doc.start_date },
        callback(r) { additional_data = r.message || { earnings: [], deductions: [] }; try_finalize(); },
        error()     { additional_data = { earnings: [], deductions: [] };               try_finalize(); }
    });
}

// ─── Apply SSA rows to form ───────────────────────────────────────────────────

function apply_salary_structure(frm, data) {
    frm.set_value("salary_structure", data.salary_structure);
    frm.clear_table("earnings");
    frm.clear_table("deductions");
    frm.clear_table("employer_share");

    (data.earnings || []).forEach(row => {
        const e = frm.add_child("earnings");
        Object.assign(e, row);
        e.base_amount    = row.base_amount !== undefined ? row.base_amount : row.amount;
        e._is_additional = false;
    });

    (data.deductions || []).forEach(row => {
        const d = frm.add_child("deductions");
        Object.assign(d, row);
        d.base_amount    = row.base_amount !== undefined ? row.base_amount : row.amount;
        d._is_additional = false;
    });

    (data.employer_share || []).forEach(row => {
        const s = frm.add_child("employer_share");
        Object.assign(s, row);
        s.base_amount           = row.base_amount !== undefined ? row.base_amount : row.amount;
        s.employer_contribution = 1;
        s._is_additional        = false;
    });

    frm.refresh_fields(["earnings", "deductions", "employer_share"]);
}

// ─── Apply attendance to form fields ─────────────────────────────────────────

function apply_attendance(frm, d, variable_pay_pct) {
    frm.set_value({
        month_days:            d.total_days            || 0,
        weekly_offs_count:     d.weekly_offs            || 0,
        total_holidays:        d.total_holidays         || 0,
        present_days:          d.present_days           || 0,
        total_on_tour:         d.total_on_tour          || 0,
        total_half_days:       d.total_half_days        || 0,
        total_earned_leaves:   d.total_earned_leaves    || 0,
        total_casual_leaves:   d.total_casual_leaves    || 0,
        total_comp_off:        d.total_comp_off         || 0,
        total_earned_comp_off: d.total_earned_comp_off  || 0,
        absent_days:           d.absent_days            || 0,
        total_lwp:             d.total_lwp              || 0,
        total_working_days:    d.working_days,
        payment_days:          d.payment_days,
        physical_working_days: d.physical_working_days  || 0,
        total_unpaid_days:     d.total_unpaid_days      || 0,
    });

    if (variable_pay_pct !== undefined) frm.variable_pay_percentage = variable_pay_pct;
    recalculate_salary(frm, d.working_days, d.payment_days, d.physical_working_days);
}

// ─── Salary Calculation ───────────────────────────────────────────────────────

function recalculate_salary(frm, wd_override, pd_override, phd_override) {
    const wd           = flt(wd_override  !== undefined ? wd_override  : frm.doc.total_working_days);
    const pd           = flt(pd_override  !== undefined ? pd_override  : frm.doc.payment_days);
    const phd          = flt(phd_override !== undefined ? phd_override : frm.doc.physical_working_days);
    const variable_pct = flt(frm.variable_pay_percentage || 0);

    let slip_month = null;
    if (frm.doc.start_date) {
        slip_month = parseInt(frm.doc.start_date.split('-')[1], 10);
    }

    let total_earnings              = 0;
    let total_deductions            = 0;
    let total_employer_contribution = 0;
    let basic_amount                = 0;
    let da_amount                   = 0;
    let retention                   = 0;

    (frm.doc.earnings || []).forEach(row => {
        const base = flt(row.base_amount != null ? row.base_amount : row.amount);
        row.base_amount = base;
        const comp = (row.salary_component || "").toLowerCase();

        let amount;
        if (comp.includes("variable")) {
            amount = pd === 0 ? 0
                : (wd > 0 && row.depends_on_payment_days) ? (base / wd) * pd * variable_pct
                : base * variable_pct;
        } else if (row.depends_on_physical_working_days && wd > 0) {
            amount = (base / wd) * phd;
        } else if (row.depends_on_payment_days && wd > 0) {
            amount = (base / wd) * pd;
        } else {
            amount = base;
        }

        row.amount      = flt(amount, 2);
        total_earnings += row.amount;

        if (comp.includes("basic"))                               basic_amount = row.amount;
        if (is_da_component(row.salary_component, row.abbr))     da_amount    = row.amount;
    });

    (frm.doc.deductions || []).forEach(row => {
        const base      = flt(row.base_amount != null ? row.base_amount : row.amount);
        row.base_amount = base;
        const statutory = is_statutory(row.salary_component);
        const pt        = is_pt(row.salary_component);

        let amount;
        if (pt) {
            amount = slip_month === 2 ? 300 : 200;
        } else if (statutory) {
            amount = base;
        } else if (row.depends_on_physical_working_days && wd > 0 && base > 0) {
            amount = (base / wd) * phd;
        } else if (row.depends_on_payment_days && wd > 0 && base > 0) {
            amount = (base / wd) * pd;
        } else {
            amount = base;
        }

        row.amount        = flt(amount, 2);
        total_deductions += row.amount;

        if ((row.salary_component || "").toLowerCase().includes("retention")) retention += row.amount;
    });

    (frm.doc.employer_share || []).forEach(row => {
        const base = flt(row.base_amount != null ? row.base_amount : row.amount);
        row.base_amount = base;
        row.amount      = flt(base, 2);
        total_employer_contribution += row.amount;
    });

    frm.set_value({
        total_earnings:              flt(total_earnings, 2),
        total_deductions:            flt(total_deductions, 2),
        net_salary:                  flt(total_earnings - total_deductions, 2),
        total_basic_da:              flt(basic_amount + da_amount, 2),
        total_employer_contribution: flt(total_employer_contribution, 2),
        retention:                   flt(retention, 2)
    });

    frm.refresh_fields(["earnings", "deductions", "employer_share"]);
}

// ─── Reset ────────────────────────────────────────────────────────────────────

function reset_form(frm) {
    frm.clear_table("earnings");
    frm.clear_table("deductions");
    frm.clear_table("employer_share");
    frm.set_value({
        month_days:            0,
        weekly_offs_count:     0,
        total_holidays:        0,
        present_days:          0,
        total_on_tour:         0,
        total_half_days:       0,
        total_earned_leaves:   0,
        total_casual_leaves:   0,
        total_comp_off:        0,
        total_earned_comp_off: 0,
        absent_days:           0,
        total_lwp:             0,
        total_working_days:    0,
        payment_days:          0,
        physical_working_days: 0,
        total_unpaid_days:     0,
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