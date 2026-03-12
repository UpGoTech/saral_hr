// Copyright (c) 2026, sj and contributors
// For license information, please see license.txt

// ─────────────────────────────────────────────────────────────
//  Exact Salary Component names (must match DB)
// ─────────────────────────────────────────────────────────────

const SC = {
    // ESIC
    EMP_ESIC:   "Employee ESIC",
    EMPR_ESIC:  "Employer ESIC",

    // PF
    EMP_PF:     "Employee PF",
    EMPR_PF:    "Employer PF",
    EMPR_EPS:   "Employer EPS",
    EMPR_EDLI:  "Employer EDLI",
    EMPR_PFADM: "Employer PF Admin Charges",

    // PT
    PT:         "Professional Tax",

    // LWF
    EMP_LWF:    "Employee Labour Welfare Fund",
    EMPR_LWF:   "Employer Labour Welfare Fund",
};

const STATUTORY_DEDUCTION  = [SC.EMP_ESIC, SC.EMP_PF, SC.PT, SC.EMP_LWF];
const STATUTORY_EMPLOYER   = [SC.EMPR_ESIC, SC.EMPR_PF, SC.EMPR_EPS, SC.EMPR_EDLI, SC.EMPR_PFADM, SC.EMPR_LWF];
const ALL_STATUTORY        = [...STATUTORY_DEDUCTION, ...STATUTORY_EMPLOYER];

// ─────────────────────────────────────────────────────────────
//  Main form events
// ─────────────────────────────────────────────────────────────

frappe.ui.form.on("Salary Structure Assignment", {

    refresh(frm) {
        toggle_fields(frm);
        render_statutory_controls(frm);
        if (frm.doc.salary_structure) {
            toggle_salary_sections(frm);
            calculate_salary(frm);
        }
    },

    setup(frm) {
        frm.set_query("employee", () => ({ filters: { is_active: 1 } }));
        frm.set_query("salary_structure", () => ({
            filters: { company: frm.doc.company || "", is_active: "Yes" }
        }));
    },

    employee(frm) {
        if (!frm.doc.employee || frm._checking_employee === frm.doc.employee) {
            toggle_fields(frm);
            return;
        }
        frm._checking_employee = frm.doc.employee;

        frappe.call({
            method: "saral_hr.saral_hr.doctype.salary_structure_assignment.salary_structure_assignment.get_existing_assignments",
            args: { employee: frm.doc.employee },
            callback(r) {
                frm._has_existing = !!(r.message && r.message.length);
                if (frm._has_existing) {
                    const lines = r.message.map(rec =>
                        `<a href="/app/salary-structure-assignment/${rec.name}" target="_blank">${rec.name}</a>`
                        + ` (${rec.from_date} to ${rec.to_date || "Ongoing"})`
                    ).join("<br>");
                    frappe.msgprint({
                        title: __("Assignment Already Exists"),
                        indicator: "orange",
                        message: `An active Salary Structure Assignment already exists for this employee.`
                            + ` Please cancel it before creating a new one.<br><br>${lines}`
                    });
                }
                toggle_fields(frm);
                render_statutory_controls(frm);
            }
        });
    },

    from_date(frm) {
        toggle_fields(frm);
        if (frm.doc.from_date && frm.doc.to_date) check_overlap(frm);
        if (frm.doc.salary_structure) refresh_statutory_rows(frm);
    },

    to_date(frm) {
        toggle_fields(frm);
        if (frm.doc.from_date && frm.doc.to_date) check_overlap(frm);
    },

    salary_structure(frm) {
        toggle_salary_sections(frm);
        if (!frm.doc.salary_structure) {
            clear_all_tables(frm);
            render_statutory_controls(frm);
            return;
        }
        load_salary_structure(frm);
    },
});

// ─────────────────────────────────────────────────────────────
//  Salary Details — live recalc when earnings amount changes
// ─────────────────────────────────────────────────────────────

frappe.ui.form.on("Salary Details", {
    amount(frm, cdt, cdn) {
        const row = frappe.get_doc(cdt, cdn);
        if (row && row.parentfield === "earnings") {
            refresh_statutory_rows(frm);
        } else {
            calculate_salary_silent(frm);
        }
    },
    salary_details_remove(frm) {
        calculate_salary_silent(frm);
    }
});

// ─────────────────────────────────────────────────────────────
//  Statutory controls — plain Frappe-style, no colours
// ─────────────────────────────────────────────────────────────

function render_statutory_controls(frm) {
    const f = frm.fields_dict["statutory_info_html"];
    if (!f || !f.$wrapper) return;

    f.$wrapper.empty();

    if (!frm.doc.salary_structure) {
        f.$wrapper.html(`<p class="text-muted small">Select a Salary Structure to configure statutory applicability.</p>`);
        return;
    }

    const editable = frm.doc.docstatus === 0;
    const esic     = !!frm.doc.is_esic_applicable;
    const pf       = !!frm.doc.is_pf_applicable;
    const pftype   = frm.doc.pf_applicable || "";
    const pt       = !!frm.doc.is_pt_applicable;
    const lwf      = !!frm.doc.is_lwf_applicable;
    const daily    = !!frm.doc.is_daily_wage_employee;

    const cb = (id, label, checked) => `
        <div class="checkbox" style="display:inline-flex;align-items:center;margin:0 14px 0 0;">
            <label style="font-weight:normal;margin:0;cursor:${editable ? "pointer" : "default"};">
                <input type="checkbox" id="${id}"
                    ${checked ? "checked" : ""}
                    ${editable ? "" : "disabled"}
                    style="margin-right:5px;vertical-align:middle;" />
                ${__(label)}
            </label>
        </div>`;

    // PF dropdown — only visible when PF is checked
    const pf_select = pf ? `
        <select id="ssa-pf-type" ${editable ? "" : "disabled"}
            style="margin-left:4px;margin-right:14px;
                   height:26px;padding:0 8px;font-size:12px;
                   border:1px solid var(--border-color,#d1d8dd);
                   border-radius:4px;background:#fff;
                   cursor:${editable ? "pointer" : "default"};">
            <option value=""           ${!pftype                 ? "selected" : ""}>${__("Select type")}</option>
            <option value="Limited PF" ${pftype === "Limited PF" ? "selected" : ""}>${__("Limited PF")}</option>
            <option value="Full PF"    ${pftype === "Full PF"    ? "selected" : ""}>${__("Full PF")}</option>
        </select>` : `<span style="margin-right:14px;"></span>`;

    f.$wrapper.html(`
        <div style="padding:4px 0 8px 0;display:flex;flex-wrap:wrap;align-items:center;">
            ${cb("ssa-esic",  "ESIC",       esic)}
            ${cb("ssa-pf",    "PF",         pf)}
            ${pf_select}
            ${cb("ssa-pt",    "PT",         pt)}
            ${cb("ssa-lwf",   "LWF",        lwf)}
            ${cb("ssa-daily", "Daily Wage", daily)}
        </div>
    `);

    if (!editable) return;

    f.$wrapper.find("#ssa-esic").on("change", function () {
        frm.set_value("is_esic_applicable", this.checked ? 1 : 0);
        refresh_statutory_rows(frm);
        render_statutory_controls(frm);
    });

    f.$wrapper.find("#ssa-pf").on("change", function () {
        frm.set_value("is_pf_applicable", this.checked ? 1 : 0);
        if (!this.checked) frm.set_value("pf_applicable", "");
        refresh_statutory_rows(frm);
        render_statutory_controls(frm);
    });

    f.$wrapper.find("#ssa-pf-type").on("change", function () {
        frm.set_value("pf_applicable", this.value);
        refresh_statutory_rows(frm);
        // No re-render needed — dropdown already shows correct value
    });

    f.$wrapper.find("#ssa-pt").on("change", function () {
        frm.set_value("is_pt_applicable", this.checked ? 1 : 0);
        refresh_statutory_rows(frm);
        render_statutory_controls(frm);
    });

    f.$wrapper.find("#ssa-lwf").on("change", function () {
        frm.set_value("is_lwf_applicable", this.checked ? 1 : 0);
        refresh_statutory_rows(frm);
        render_statutory_controls(frm);
    });

    f.$wrapper.find("#ssa-daily").on("change", function () {
        frm.set_value("is_daily_wage_employee", this.checked ? 1 : 0);
        render_statutory_controls(frm);
    });
}



// ─────────────────────────────────────────────────────────────
//  Load salary structure rows
// ─────────────────────────────────────────────────────────────

function load_salary_structure(frm) {
    frappe.call({
        method: "frappe.client.get",
        args: { doctype: "Salary Structure", name: frm.doc.salary_structure },
        callback(r) {
            if (!r.message) return;
            const structure = r.message;

            clear_all_tables(frm);

            // Copy earnings
            (structure.earnings || []).forEach(row => copy_row(frm.add_child("earnings"), row));

            // Copy deductions — skip statutory, split by employer_contribution
            (structure.deductions || []).forEach(row => {
                const name = (row.salary_component || "").trim();
                if (ALL_STATUTORY.includes(name)) return;
                if (parseInt(row.employer_contribution)) {
                    copy_row(frm.add_child("employer_share"), row);
                } else {
                    copy_row(frm.add_child("deductions"), row);
                }
            });

            frm.set_value("currency", structure.currency || "INR");
            frm.refresh_fields(["earnings", "deductions", "employer_share"]);

            render_statutory_controls(frm);
            refresh_statutory_rows(frm);
        }
    });
}

// ─────────────────────────────────────────────────────────────
//  Refresh statutory rows
// ─────────────────────────────────────────────────────────────

function refresh_statutory_rows(frm) {
    if (!frm.doc.salary_structure || !frm.doc.company) return;

    // Strip existing statutory rows from both tables
    frm.doc.deductions = (frm.doc.deductions || [])
        .filter(r => !ALL_STATUTORY.includes((r.salary_component || "").trim()));
    frm.doc.employer_share = (frm.doc.employer_share || [])
        .filter(r => !ALL_STATUTORY.includes((r.salary_component || "").trim()));
    frm.refresh_fields(["deductions", "employer_share"]);

    const any_on = frm.doc.is_esic_applicable || frm.doc.is_pf_applicable
        || frm.doc.is_pt_applicable || frm.doc.is_lwf_applicable;

    if (!any_on) {
        calculate_salary(frm);
        return;
    }

    // Build {component_name: amount} map from actual SSA earnings rows.
    // This lets the server compute ESIC/PF wage basis using real component
    // amounts instead of using gross_salary as a proxy for everything.
    const earnings_map = _earnings_map(frm);

    frappe.call({
        method: "saral_hr.saral_hr.doctype.salary_structure_assignment.salary_structure_assignment.get_statutory_components",
        args: {
            company:            frm.doc.company,
            gross_salary:       _sum_earnings(frm),
            earnings_map:       JSON.stringify(earnings_map),
            from_date:          frm.doc.from_date || "",
            is_esic_applicable: frm.doc.is_esic_applicable ? 1 : 0,
            is_pf_applicable:   frm.doc.is_pf_applicable   ? 1 : 0,
            pf_type:            frm.doc.pf_applicable       || "",
            is_pt_applicable:   frm.doc.is_pt_applicable   ? 1 : 0,
            is_lwf_applicable:  frm.doc.is_lwf_applicable  ? 1 : 0,
        },
        callback(r) {
            if (!r.message) return;

            (r.message.deductions || []).forEach(d => {
                const child = frm.add_child("deductions");
                frappe.model.set_value(child.doctype, child.name, {
                    salary_component:      d.salary_component,
                    abbr:                  d.abbr || "",
                    amount:                flt(d.amount),
                    base_amount:           flt(d.amount),
                    employer_contribution: 0,
                });
            });

            (r.message.employer_share || []).forEach(d => {
                const child = frm.add_child("employer_share");
                frappe.model.set_value(child.doctype, child.name, {
                    salary_component:      d.salary_component,
                    abbr:                  d.abbr || "",
                    amount:                flt(d.amount),
                    base_amount:           flt(d.amount),
                    employer_contribution: 1,
                });
            });

            frm.refresh_fields(["deductions", "employer_share"]);
            calculate_salary(frm);
        }
    });
}

// ─────────────────────────────────────────────────────────────
//  Field visibility
// ─────────────────────────────────────────────────────────────

function toggle_fields(frm) {
    const ok = !frm._has_existing;
    frm.toggle_display("assignment_section", ok);
    frm.toggle_display("from_date",          ok);
    frm.toggle_display("to_date",            ok);
    frm.toggle_display("salary_structure",   ok);
    toggle_salary_sections(frm);
}

function toggle_salary_sections(frm) {
    const s = !!frm.doc.salary_structure;
    frm.toggle_display("earnings_and_deductions_section", s);
    frm.toggle_display("employer_share_section",          s);
    frm.toggle_display("calculations_section",            s);
}

// ─────────────────────────────────────────────────────────────
//  Overlap check
// ─────────────────────────────────────────────────────────────

function check_overlap(frm) {
    if (!frm.doc.employee || !frm.doc.from_date || !frm.doc.to_date) return;
    frappe.call({
        method: "saral_hr.saral_hr.doctype.salary_structure_assignment.salary_structure_assignment.check_overlap",
        args: {
            employee:      frm.doc.employee,
            from_date:     frm.doc.from_date,
            to_date:       frm.doc.to_date,
            employee_name: frm.doc.employee_name || frm.doc.employee,
            current_name:  frm.doc.__islocal ? null : frm.doc.name,
        },
        callback(r) {
            if (!r.message) return;
            const rec = r.message;
            frappe.msgprint({
                title:     __("Date Range Overlap"),
                indicator: "red",
                message:   `This date range overlaps with: `
                    + `<a href="/app/salary-structure-assignment/${rec.name}" target="_blank">${rec.name}</a>`
                    + ` (${rec.from_date} to ${rec.to_date || "Ongoing"})`
            });
        }
    });
}

// ─────────────────────────────────────────────────────────────
//  Salary calculation
// ─────────────────────────────────────────────────────────────

function calculate_salary()        { _do_calculate(arguments[0], false); }
function calculate_salary_silent() { _do_calculate(arguments[0], true);  }

function _do_calculate(frm, silent) {
    const gross    = _sum_earnings(frm);
    let emp_ded    = 0;
    let empr_cont  = 0;

    (frm.doc.deductions || []).forEach(d => {
        const live = frappe.get_doc(d.doctype, d.name);
        emp_ded += flt(live ? live.amount : d.amount);
    });

    (frm.doc.employer_share || []).forEach(d => {
        const live = frappe.get_doc(d.doctype, d.name);
        empr_cont += flt(live ? live.amount : d.amount);
    });

    const values = {
        gross_salary:                gross,
        total_deductions:            emp_ded,
        total_employer_contribution: empr_cont,
        net_salary:                  gross - emp_ded,
        monthly_ctc:                 gross + empr_cont,
        annual_ctc:                  (gross + empr_cont) * 12,
    };

    if (silent) {
        Object.assign(frm.doc, values);
        Object.keys(values).forEach(fn => {
            const field = frm.get_field(fn);
            if (!field) return;
            const el = field.$input || (field.$wrapper && field.$wrapper.find(".like-disabled-input, .control-value"));
            if (el) el.val ? el.val(format_number(values[fn], null, 2)) : el.text(format_number(values[fn], null, 2));
        });
    } else {
        frm.set_value(values);
        frm.refresh_fields(["gross_salary", "total_deductions",
            "total_employer_contribution", "net_salary", "monthly_ctc", "annual_ctc"]);
    }
}

function _sum_earnings(frm) {
    let t = 0;
    (frm.doc.earnings || []).forEach(r => {
        const live = frappe.get_doc(r.doctype, r.name);
        t += flt(live ? live.amount : r.amount);
    });
    return t;
}

// Build {salary_component: amount} for every earning row in the SSA.
// Passed to get_statutory_components so ESIC/PF wage basis uses real
// amounts (actual Basic, HRA, DA etc.) instead of gross as a proxy.
function _earnings_map(frm) {
    const map = {};
    (frm.doc.earnings || []).forEach(r => {
        const live = frappe.get_doc(r.doctype, r.name);
        const comp = (r.salary_component || "").trim();
        if (comp) map[comp] = flt(live ? live.amount : r.amount);
    });
    return map;
}

// ─────────────────────────────────────────────────────────────
//  Utilities
// ─────────────────────────────────────────────────────────────

function clear_all_tables(frm) {
    frm.clear_table("earnings");
    frm.clear_table("deductions");
    frm.clear_table("employer_share");
    frm.set_value({
        gross_salary: 0, total_deductions: 0,
        total_employer_contribution: 0,
        net_salary: 0, monthly_ctc: 0, annual_ctc: 0
    });
    frm.refresh_fields();
}

function copy_row(target, source) {
    const skip = ["name", "parent", "parenttype", "parentfield",
                  "idx", "docstatus", "creation", "modified", "modified_by", "owner"];
    Object.keys(source).forEach(k => { if (!skip.includes(k)) target[k] = source[k]; });
}