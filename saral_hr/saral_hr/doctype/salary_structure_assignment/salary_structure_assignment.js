frappe.ui.form.on("Salary Structure Assignment", {

    refresh(frm) {
        toggle_fields(frm);
        if (frm.doc.salary_structure) {
            toggle_salary_sections(frm);
            calculate_salary(frm);
            render_statutory_bar(frm);
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

        if (!frm.doc.salary_structure) {
            clear_salary_tables(frm);
            clear_statutory_bar(frm);
            return;
        }

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
                render_statutory_bar(frm);
            }
        });
    }
});

frappe.ui.form.on("Salary Details", {
    amount(frm, cdt, cdn) {
        const row = frappe.get_doc(cdt, cdn);
        if (row) row.amount = flt(row.amount);
        calculate_salary_silent(frm);
    },
    salary_details_remove(frm) {
        calculate_salary_silent(frm);
    }
});

// ── Statutory one-line badge bar ──────────────────────────────────────────────

function clear_statutory_bar(frm) {
    const f = frm.fields_dict.statutory_info_html;
    if (f && f.$wrapper) f.$wrapper.html("");
    frm.toggle_display("statutory_section_bar", false);
}

function render_statutory_bar(frm) {
    if (!frm.doc.employee) return;

    frappe.db.get_value(
        "Company Link",
        frm.doc.employee,
        ["is_esic_applicable", "is_pf_applicable", "pf_applicable"],
        (r) => {
            const f = frm.fields_dict.statutory_info_html;
            if (!f || !f.$wrapper || !r) return;

            const esic_on = parseInt(r.is_esic_applicable);
            const pf_on   = parseInt(r.is_pf_applicable);
            const pf_val  = r.pf_applicable || "No PF";

            const badge = (label, color, bg, border) =>
                `<span style="
                    display:inline-flex; align-items:center; gap:6px;
                    background:${bg}; color:${color};
                    border:1px solid ${border}; border-radius:20px;
                    padding:4px 12px; font-size:12px; font-weight:600;
                    letter-spacing:0.2px; white-space:nowrap;">
                    <span style="width:7px;height:7px;border-radius:50%;
                        background:${color};display:inline-block;flex-shrink:0;"></span>
                    ${label}
                </span>`;

            const badges = [];

            // ESIC
            if (esic_on) {
                badges.push(badge("ESIC Applicable", "#1e7e34", "#eaf7ee", "#b7dfc7"));
            } else {
                badges.push(badge("ESIC Not Applicable", "#6c757d", "#f4f5f6", "#dee2e6"));
            }

            // PF
            if (pf_on) {
                const pfColor = {
                    "Full PF":    ["#1e7e34", "#eaf7ee", "#b7dfc7"],
                    "Limited PF": ["#856404", "#fff8e1", "#ffe082"],
                    "No PF":      ["#b71c1c", "#fdecea", "#f5c6cb"],
                }[pf_val] || ["#b71c1c", "#fdecea", "#f5c6cb"];
                badges.push(badge(`PF: ${__(pf_val)}`, pfColor[0], pfColor[1], pfColor[2]));
            } else {
                badges.push(badge("PF Not Applicable", "#6c757d", "#f4f5f6", "#dee2e6"));
            }

            f.$wrapper.html(`
                <div style="display:flex;flex-wrap:wrap;align-items:center;
                    gap:8px;padding:6px 0 14px 0;">
                    ${badges.join("")}
                </div>
            `);
            frm.toggle_display("statutory_section_bar", true);
        }
    );
}

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

function calculate_salary(frm) { _do_calculate(frm, false); }
function calculate_salary_silent(frm) { _do_calculate(frm, true); }

function _do_calculate(frm, silent) {
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
            const cm = {};
            (res.message || []).forEach(c => { cm[c.name] = c; });
            let emp_ded = 0, empr_cont = 0;
            deductions.forEach(d => {
                const lr  = frappe.get_doc(d.doctype, d.name);
                const amt = flt(lr ? lr.amount : d.amount);
                const c   = cm[d.salary_component];
                if (!c || !parseInt(c.employer_contribution)) emp_ded   += amt;
                else                                           empr_cont += amt;
            });
            set_salary_totals(frm, gross_salary, emp_ded, empr_cont, silent);
        }
    });
}

function set_salary_totals(frm, gross, emp_ded, empr, silent) {
    const values = {
        gross_salary:                gross,
        total_deductions:            emp_ded,
        total_employer_contribution: empr,
        net_salary:                  gross - emp_ded,
        monthly_ctc:                 (gross + empr),
        annual_ctc:                  (gross + empr) * 12
    };
    if (silent) {
        Object.assign(frm.doc, values);
        Object.keys(values).forEach(fn => {
            const field = frm.get_field(fn);
            if (!field) return;
            if (field.$input) field.$input.val(format_number(values[fn], null, 2));
            else if (field.$wrapper) field.$wrapper.find(".like-disabled-input, .control-value").text(format_number(values[fn], null, 2));
        });
    } else {
        frm.set_value(values);
        frm.refresh_fields(["gross_salary","total_deductions","total_employer_contribution","net_salary","monthly_ctc","annual_ctc"]);
    }
}

function clear_salary_tables(frm) {
    frm.clear_table("earnings");
    frm.clear_table("deductions");
    frm.set_value({ gross_salary:0, total_deductions:0, total_employer_contribution:0, net_salary:0, monthly_ctc:0, annual_ctc:0 });
    frm.refresh_fields();
}

function copy_row(target, source) {
    const skip = ["name","parent","parenttype","parentfield","idx","docstatus","creation","modified","modified_by","owner"];
    Object.keys(source).forEach(k => { if (!skip.includes(k)) target[k] = source[k]; });
}