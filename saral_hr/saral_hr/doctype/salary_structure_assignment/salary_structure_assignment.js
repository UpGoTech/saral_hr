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
                // Use refresh_field (singular) on just the tables — avoids full form re-render
                frm.refresh_field("earnings");
                frm.refresh_field("deductions");
                // Calculate AFTER rows are rendered, not during
                calculate_salary(frm);
            }
        });
    }
});

frappe.ui.form.on("Salary Details", {
    amount(frm, cdt, cdn) {
        // Only recalculate totals — do NOT refresh the entire form or tables
        calculate_salary_silent(frm);
    },
    salary_details_remove(frm) {
        calculate_salary_silent(frm);
    }
});

// ── Field visibility ─────────────────────────────────────────────────────────

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

// Called on initial load / salary_structure change — safe to use here
function calculate_salary(frm) {
    _do_calculate(frm, false);
}

// Called when user edits an amount cell — must NOT call frm.refresh_fields()
// or frm.refresh_field() on the earnings/deductions tables, as that would
// destroy the active input and move focus away from the cell being edited.
function calculate_salary_silent(frm) {
    _do_calculate(frm, true);
}

function _do_calculate(frm, silent) {
    let gross_salary = 0;
    (frm.doc.earnings || []).forEach(row => { gross_salary += flt(row.amount); });

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
                const comp   = component_map[d.salary_component];
                const amount = flt(d.amount);
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

    frm.set_value({
        gross_salary:                gross,
        total_deductions:            employee_deductions,
        total_employer_contribution: employer,
        net_salary,
        monthly_ctc,
        annual_ctc
    });

    // KEY FIX: Only refresh the calculation fields, NEVER the earnings/deductions
    // tables while a user may be actively editing a cell inside them.
    if (!silent) {
        frm.refresh_fields([
            "gross_salary", "total_deductions", "total_employer_contribution",
            "net_salary", "monthly_ctc", "annual_ctc"
        ]);
    }
    // In silent mode frm.set_value() already updates the display for scalar fields,
    // so no explicit refresh is needed and we avoid disrupting the active row.
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