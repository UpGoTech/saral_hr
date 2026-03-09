// ─── Form Events ──────────────────────────────────────────────────────────────

frappe.ui.form.on("Salary Slip", {

    refresh(frm) {
        if (!frm.doc.currency) frm.set_value("currency", "INR");
        frm.set_query("employee", () => ({ filters: { is_active: 1 } }));
    },

    employee(frm) {
        if (!frm.doc.employee) return;
        reset_form(frm);

        frappe.db.get_value("Company Link", frm.doc.employee, "category", (r) => {
            if (r && r.category) {
                frappe.db.get_value("Category", r.category, "salary_calculation_based_on", (cat) => {
                    if (cat && cat.salary_calculation_based_on)
                        frm.set_value("working_days_calculation_method", cat.salary_calculation_based_on);
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
    amount(frm)           { recalculate_salary(frm); },
    earnings_remove(frm)  { recalculate_salary(frm); },
    deductions_remove(frm){ recalculate_salary(frm); }
});

// ─── DA component detection (matches Python _is_da_component) ─────────────────

function is_da_component(comp_name, abbr) {
    const name = (comp_name || '').toLowerCase();
    const ab   = (abbr || '').toLowerCase().trim();
    return (
        name.includes('dearness')
        || name === 'da'
        || ab === 'da'
        || ab.startsWith('da-')
        || ab.startsWith('da ')
        || ab === 'da - dr'
        || ab.startsWith('da-dr')
    );
}

// ─── Core Form Functions ──────────────────────────────────────────────────────

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
    let additional_data = { earnings: [], deductions: [] };

    // pending covers 4 parallel calls; vpa_check may bump it to 5 via nested call
    let pending = 4;

    function try_finalize() {
        if (--pending > 0) return;

        const unmet = [];
        if (!salary_data)
            unmet.push("No Salary Structure has been assigned for the selected payroll period.");
        if (vpa_status && vpa_status.status === "missing")
            unmet.push(vpa_status.message.replace(/<[^>]+>/g, ""));
        if (!attendance_data)
            unmet.push("Attendance data could not be retrieved for the selected period. Please verify attendance records.");
        else if (attendance_data.attendance_count === 0)
            unmet.push("No attendance has been recorded for this employee in the selected month.");

        if (unmet.length > 0) {
            frappe.msgprint({
                title:   __("Payroll Processing Requirements Not Met"),
                message: `<div style="margin-bottom:8px;font-weight:600;">Please resolve the following before saving this salary slip:</div>
                          <ul style="margin:0;padding-left:18px;line-height:1.7;">${unmet.map(e => `<li style="margin-bottom:6px;">${e}</li>`).join("")}</ul>`,
                indicator: "red"
            });
            frm.page.btn_primary.prop("disabled", true);
            return;
        }

        apply_salary_structure(frm, salary_data);

        // Inject additional earnings (end of table — fixed, no proration)
        (additional_data.earnings || []).forEach(row => {
            const e = frm.add_child("earnings");
            e.salary_component                 = row.salary_component;
            e.abbr                             = row.abbr;
            e.amount                           = flt(row.amount);
            e.base_amount                      = flt(row.amount);
            e.depends_on_payment_days          = row.depends_on_payment_days          || 0;
            e.is_daily_rate                    = row.is_daily_rate                    || 0;
            e.depends_on_physical_working_days = row.depends_on_physical_working_days || 0;
            e.is_special_component             = row.is_special_component             || 0;
        });

        // Inject additional deductions (end of table — fixed, no proration)
        (additional_data.deductions || []).forEach(row => {
            const d = frm.add_child("deductions");
            d.salary_component                 = row.salary_component;
            d.abbr                             = row.abbr;
            d.amount                           = flt(row.amount);
            d.base_amount                      = flt(row.amount);
            d.employer_contribution            = row.employer_contribution            || 0;
            d.depends_on_payment_days          = row.depends_on_payment_days          || 0;
            d.is_daily_rate                    = row.is_daily_rate                    || 0;
            d.depends_on_physical_working_days = row.depends_on_physical_working_days || 0;
            d.is_special_component             = row.is_special_component             || 0;
        });

        frm.refresh_fields(["earnings", "deductions"]);
        apply_attendance(frm, attendance_data, flt(vpa_percentage) / 100);
        frm.page.btn_primary.prop("disabled", false);
    }

    // Call 1: salary structure
    frappe.call({
        method: "saral_hr.saral_hr.doctype.salary_slip.salary_slip.get_salary_structure_for_employee",
        args:   { employee: frm.doc.employee, start_date: frm.doc.start_date },
        callback(r) { salary_data = r.message || null; try_finalize(); },
        error()     { salary_data = null;              try_finalize(); }
    });

    // Call 2: variable pay check (may spawn a 5th nested call)
    frappe.call({
        method: "saral_hr.saral_hr.doctype.salary_slip.salary_slip.check_variable_pay_assignment",
        args:   { employee: frm.doc.employee, start_date: frm.doc.start_date },
        callback(r) {
            vpa_status = r.message || { status: "ok" };
            if (vpa_status.status === "ok") {
                pending++; // bump BEFORE issuing nested call
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

    // Call 3: attendance
    frappe.call({
        method: "saral_hr.saral_hr.doctype.salary_slip.salary_slip.get_attendance_and_days",
        args:   { employee: frm.doc.employee, start_date: frm.doc.start_date, working_days_calculation_method: frm.doc.working_days_calculation_method },
        callback(r) { attendance_data = r.message || null; try_finalize(); },
        error()     { attendance_data = null;              try_finalize(); }
    });

    // Call 4: additional components
    frappe.call({
        method: "saral_hr.saral_hr.doctype.salary_slip.salary_slip.get_additional_components_api",
        args:   { employee: frm.doc.employee, start_date: frm.doc.start_date },
        callback(r) { additional_data = r.message || { earnings: [], deductions: [] }; try_finalize(); },
        error()     { additional_data = { earnings: [], deductions: [] };               try_finalize(); }
    });
}

// ─── Apply Fetched Data ───────────────────────────────────────────────────────

function apply_salary_structure(frm, data) {
    frm.set_value("salary_structure", data.salary_structure);
    frm.clear_table("earnings");
    frm.clear_table("deductions");

    (data.earnings || []).forEach(row => {
        const e = frm.add_child("earnings");
        Object.assign(e, row);
        e.base_amount = row.base_amount !== undefined ? row.base_amount : row.amount;
    });

    (data.deductions || []).forEach(row => {
        const d = frm.add_child("deductions");
        Object.assign(d, row);
        d.base_amount = row.base_amount !== undefined ? row.base_amount : row.amount;
    });

    frm.refresh_fields(["earnings", "deductions"]);
}

function apply_attendance(frm, d, variable_pay_pct) {
    frm.set_value({
        total_working_days:    d.working_days,
        payment_days:          d.payment_days,
        physical_working_days: d.physical_working_days || 0,
        present_days:          d.present_days,
        absent_days:           d.absent_days,
        weekly_offs_count:     d.weekly_offs,
        total_half_days:       d.total_half_days,
        total_lwp:             d.total_lwp           || 0,
        total_holidays:        d.total_holidays      || 0,
        total_earned_leaves:   d.total_earned_leaves || 0,
        total_casual_leaves:   d.total_casual_leaves || 0,
        total_on_tour:         d.total_on_tour       || 0,
        total_comp_off:        d.total_comp_off      || 0
    });

    if (variable_pay_pct !== undefined) frm.variable_pay_percentage = variable_pay_pct;

    recalculate_salary(frm, d.working_days, d.payment_days, d.physical_working_days);
}

// ─── Salary Calculation ───────────────────────────────────────────────────────
//
// Mirrors calculate_salary_slip_amounts_exact() in salary_slip.py exactly.
// PF/ESIC are computed from component flags (is_pf_component, pf_percentage,
// pf_cap_amount, pf_calculation_based_on) — NOT hardcoded rates.
//
// Two gross values are tracked:
//   prorated_gross  — total earnings after proration (includes additional)
//   ssa_gross       — raw sum of base_amounts for SSA rows only
//                     (approximated here as the base_amount sum of all earnings,
//                      since additional rows carry base_amount = 0 from the server)
//
// "Gross from Salary Structure Assignment" basis uses ssa_gross.
// "Prorated Gross" (or blank) uses prorated_gross.

function recalculate_salary(frm, wd_override, pd_override, phd_override) {
    const wd           = flt(wd_override  !== undefined ? wd_override  : frm.doc.total_working_days);
    const pd           = flt(pd_override  !== undefined ? pd_override  : frm.doc.payment_days);
    const phd          = flt(phd_override !== undefined ? phd_override : frm.doc.physical_working_days);
    const variable_pct = flt(frm.variable_pay_percentage || 0);

    let total_earnings              = 0;
    let total_deductions            = 0;
    let total_employer_contribution = 0;
    let total_basic_da              = 0;
    let retention                   = 0;
    let basic_amount                = 0;
    let da_amount                   = 0;
    let ssa_gross                   = 0; // sum of base_amounts (unprorated SSA rows)

    // ── Pass 1: earnings ──────────────────────────────────────────────────────
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

        } else if (row.is_daily_rate) {
            amount = base * pd;

        } else if (row.depends_on_payment_days && wd > 0) {
            amount = (base / wd) * pd;

        } else {
            amount = base; // fixed / additional
        }

        row.amount      = flt(amount, 2);
        total_earnings += row.amount;
        ssa_gross      += base; // base_amount tracks the unprorated figure

        if (comp.includes("basic"))                             basic_amount = row.amount;
        if (is_da_component(row.salary_component, row.abbr))   da_amount    = row.amount;
    });

    total_basic_da = basic_amount + da_amount;
    const prorated_gross = total_earnings;

    // ── Pass 2: deductions ────────────────────────────────────────────────────
    (frm.doc.deductions || []).forEach(row => {
        const base = flt(row.base_amount != null ? row.base_amount : row.amount);
        row.base_amount = base;
        const comp = (row.salary_component || "").toLowerCase();

        let amount;

        if (row.is_pf_component) {
            // Fully flag-driven PF
            const pf_pct   = flt(row.pf_percentage  || 0);
            const pf_cap   = flt(row.pf_cap_amount   || 0);
            const pf_basis = (row.pf_calculation_based_on || "").trim();
            const gross_for_pf = (pf_basis === "Gross from Salary Structure Assignment") ? ssa_gross : prorated_gross;

            amount = pf_pct > 0 ? flt(gross_for_pf * pf_pct / 100, 2) : 0;
            if (pf_cap > 0 && amount > pf_cap) amount = pf_cap;

        } else if (row.is_esic_component) {
            // Fully flag-driven ESIC (ceiling: no deduction when gross ≥ ₹21,000)
            const esic_pct   = flt(row.esic_percentage  || 0);
            const esic_cap   = flt(row.esic_cap_amount   || 0);
            const esic_basis = (row.esic_calculation_based_on || "").trim();
            const gross_for_esic = (esic_basis === "Gross from Salary Structure Assignment") ? ssa_gross : prorated_gross;

            if (esic_pct <= 0 || prorated_gross >= 21000) {
                amount = 0;
            } else {
                amount = flt(gross_for_esic * esic_pct / 100, 2);
                if (esic_cap > 0 && amount > esic_cap) amount = esic_cap;
            }

        } else if (row.depends_on_physical_working_days && wd > 0 && base > 0) {
            amount = (base / wd) * phd;

        } else if (row.is_daily_rate) {
            amount = base * pd;

        } else if (row.depends_on_payment_days && wd > 0 && base > 0) {
            amount = (base / wd) * pd;

        } else {
            amount = base; // fixed / additional
        }

        row.amount = flt(amount, 2);

        if (row.employer_contribution) total_employer_contribution += row.amount;
        else                           total_deductions            += row.amount;

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

// ─── Reset ────────────────────────────────────────────────────────────────────

function reset_form(frm) {
    frm.clear_table("earnings");
    frm.clear_table("deductions");
    frm.set_value({
        total_working_days: 0, payment_days: 0, physical_working_days: 0,
        present_days: 0, absent_days: 0, weekly_offs_count: 0,
        total_half_days: 0, total_lwp: 0, total_holidays: 0,
        total_earned_leaves: 0, total_casual_leaves: 0,
        total_earnings: 0, total_deductions: 0, net_salary: 0,
        total_basic_da: 0, total_employer_contribution: 0, retention: 0,
        total_on_tour: 0, total_comp_off: 0,
        working_days_calculation_method: ""
    });
    frm.variable_pay_percentage = 0;
    frm.page.btn_primary.prop("disabled", false);
    frm.refresh_fields();
}