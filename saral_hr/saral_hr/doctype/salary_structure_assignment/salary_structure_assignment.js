frappe.ui.form.on("Salary Structure Assignment", {

    refresh(frm) {
        toggle_fields(frm);
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
                        `<a href="/app/salary-structure-assignment/${rec.name}" target="_blank">${rec.name}</a> (${rec.from_date} to ${rec.to_date || "Ongoing"})`
                    ).join("<br>");
                    frappe.msgprint({
                        title: __("Assignment Already Exists"),
                        indicator: "orange",
                        message: `An active Salary Structure Assignment already exists for this employee. Please cancel it before creating a new one.<br><br>${lines}`
                    });
                }

                toggle_fields(frm);
            }
        });
    },

    from_date(frm) {
        toggle_fields(frm);
        if (frm.doc.from_date && frm.doc.to_date) check_overlap(frm);
    },

    to_date(frm) {
        toggle_fields(frm);
        if (frm.doc.from_date && frm.doc.to_date) check_overlap(frm);
    },

    salary_structure(frm) {
        toggle_salary_sections(frm);
        if (!frm.doc.salary_structure) { clear_salary_tables(frm); return; }

        frappe.call({
            method: "frappe.client.get",
            args: { doctype: "Salary Structure", name: frm.doc.salary_structure },
            callback(r) {
                if (!r.message) return;
                clear_salary_tables(frm);
                (r.message.earnings   || []).forEach(row => copy_row(frm.add_child("earnings"),   row));
                (r.message.deductions || []).forEach(row => copy_row(frm.add_child("deductions"), row));
                frm.set_value("currency", r.message.currency || "INR");
                frm.refresh_field("earnings");
                frm.refresh_field("deductions");
                calculate_salary(frm);
            }
        });
    }
});

frappe.ui.form.on("Salary Details", {
    amount(frm, cdt, cdn) {
        // ── FIX: read the value directly from the active row in locals,
        // which Frappe updates before firing the trigger, rather than
        // relying on frm.doc which may not yet reflect the typed value.
        const row = frappe.get_doc(cdt, cdn);
        if (row) {
            row.amount = flt(row.amount);
        }
        calculate_salary_silent(frm);
    },
    salary_details_remove(frm) {
        calculate_salary_silent(frm);
    }
});

// ── Field visibility ──────────────────────────────────────────────────────────

function toggle_fields(frm) {
    const can_create = !frm._has_existing;

    frm.toggle_display("assignment_section", can_create);
    frm.toggle_display("from_date",          can_create);
    frm.toggle_display("to_date",            can_create);
    frm.toggle_display("salary_structure",   can_create);

    toggle_salary_sections(frm);
}

function toggle_salary_sections(frm) {
    const s = !!frm.doc.salary_structure;
    frm.toggle_display("earnings_and_deductions_section", s);
    frm.toggle_display("calculations_section",            s);
}

// ── Overlap check ─────────────────────────────────────────────────────────────

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
                message:   `This date range overlaps with: <a href="/app/salary-structure-assignment/${rec.name}" target="_blank">${rec.name}</a> (${rec.from_date} to ${rec.to_date || "Ongoing"})`
            });
        }
    });
}

// ── Salary calculation ────────────────────────────────────────────────────────

// Called on initial load / salary_structure change — safe to use full refresh here
function calculate_salary(frm) {
    _do_calculate(frm, false);
}

// Called when user edits an amount cell — must NOT call frm.refresh_field()
// on the earnings/deductions tables, as that would destroy the active input
// and move focus away from the cell being edited.
function calculate_salary_silent(frm) {
    _do_calculate(frm, true);
}

function _do_calculate(frm, silent) {
    // ── FIX: sum amounts directly from frappe.model.locals (the in-memory
    // store that Frappe updates synchronously when a child row value changes),
    // NOT from frm.doc.earnings which may still hold stale values at trigger time.
    let gross_salary = 0;
    (frm.doc.earnings || []).forEach(row => {
        const live_row = frappe.get_doc(row.doctype, row.name);
        gross_salary += flt(live_row ? live_row.amount : row.amount);
    });

    const deductions = frm.doc.deductions || [];
    if (!deductions.length) {
        set_salary_totals(frm, gross_salary, 0, 0, silent);
        return;
    }

    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: "Salary Component",
            fields: ["name", "employer_contribution"],
            filters: { name: ["in", deductions.map(d => d.salary_component)] }
        },
        callback(res) {
            const component_map = {};
            (res.message || []).forEach(c => { component_map[c.name] = c; });

            let employee_deductions = 0, employer_contribution = 0;

            deductions.forEach(d => {
                const live_row = frappe.get_doc(d.doctype, d.name);
                const amount   = flt(live_row ? live_row.amount : d.amount);
                const comp     = component_map[d.salary_component];
                if (!comp || !parseInt(comp.employer_contribution)) {
                    employee_deductions   += amount;
                } else {
                    employer_contribution += amount;
                }
            });

            set_salary_totals(frm, gross_salary, employee_deductions, employer_contribution, silent);
        }
    });
}

function set_salary_totals(frm, gross, employee_deductions, employer, silent) {
    const net_salary  = gross - employee_deductions;
    const annual_ctc  = (gross + employer) * 12;
    const monthly_ctc = annual_ctc / 12;

    const values = {
        gross_salary:                gross,
        total_deductions:            employee_deductions,
        total_employer_contribution: employer,
        net_salary,
        monthly_ctc,
        annual_ctc
    };

    if (silent) {
        // Write directly to frm.doc — bypasses set_value()'s internal refresh
        // which would re-render the grid and destroy the active input cell focus
        Object.assign(frm.doc, values);

        // Manually update only the display of each read-only calculation field
        // without touching the earnings/deductions tables at all
        Object.keys(values).forEach(fieldname => {
            const field = frm.get_field(fieldname);
            if (!field) return;

            if (field.$input) {
                field.$input.val(format_number(values[fieldname], null, 2));
            } else if (field.$wrapper) {
                // read_only fields are rendered as static text
                field.$wrapper
                    .find(".like-disabled-input, .control-value")
                    .text(format_number(values[fieldname], null, 2));
            }
        });
    } else {
        // Normal mode (initial load / structure change) — safe to use set_value + refresh
        frm.set_value(values);
        frm.refresh_fields([
            "gross_salary", "total_deductions", "total_employer_contribution",
            "net_salary", "monthly_ctc", "annual_ctc"
        ]);
    }
}

function clear_salary_tables(frm) {
    frm.clear_table("earnings");
    frm.clear_table("deductions");
    frm.set_value({
        gross_salary: 0, total_deductions: 0, total_employer_contribution: 0,
        net_salary: 0, monthly_ctc: 0, annual_ctc: 0
    });
    frm.refresh_fields();
}

function copy_row(target, source) {
    const skip = ["name","parent","parenttype","parentfield","idx","docstatus","creation","modified","modified_by","owner"];
    Object.keys(source).forEach(key => { if (!skip.includes(key)) target[key] = source[key]; });
}