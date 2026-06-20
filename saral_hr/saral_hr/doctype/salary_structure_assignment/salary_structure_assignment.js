// Copyright (c) 2026, sj and contributors
// For license information, please see license.txt

const SC = {
    EMP_ESIC:   "Employee ESIC",
    EMPR_ESIC:  "Employer ESIC",
    EMP_PF:     "Employee PF",
    EMPR_PF:    "Employer PF",
    EMPR_EPS:   "Employer EPS",
    EMPR_EDLI:  "Employer EDLI",
    EMPR_PFADM: "Employer PF Admin Charges",
    PT:         "Professional Tax",
    EMP_LWF:    "Employee Labour Welfare Fund",
    EMPR_LWF:   "Employer Labour Welfare Fund",
};

const STATUTORY_DEDUCTION  = [SC.EMP_ESIC, SC.EMP_PF, SC.PT, SC.EMP_LWF];
const STATUTORY_EMPLOYER   = [SC.EMPR_ESIC, SC.EMPR_PF, SC.EMPR_EPS, SC.EMPR_EDLI, SC.EMPR_PFADM, SC.EMPR_LWF];
const ALL_STATUTORY        = [...STATUTORY_DEDUCTION, ...STATUTORY_EMPLOYER];

let _statutory_inflight = false;
let _statutory_pending  = false;

let _calc_debounce_timer = null;
function _debounced_recalc(frm, fn, delay = 120) {
    clearTimeout(_calc_debounce_timer);
    _calc_debounce_timer = setTimeout(() => fn(frm), delay);
}

frappe.ui.form.on("Salary Structure Assignment", {

    refresh(frm) {
    toggle_fields(frm);
    render_statutory_controls(frm);
    toggle_skill_type(frm);
    if (frm.doc.salary_structure) {
        toggle_salary_sections(frm);
        setTimeout(() => {
            if (frm.doc.docstatus !== 1) {     // ← ye line add karo
                calculate_salary(frm);
            }
            maybe_render_daily_wage_panel(frm);
        }, 150);
    }
    _bind_live_amount_inputs(frm);
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
                toggle_skill_type(frm);
                check_srr_and_apply(frm);
                maybe_render_daily_wage_panel(frm);
            }
        });
    },

    from_date(frm) {
        toggle_fields(frm);
        if (frm.doc.from_date && frm.doc.to_date) check_overlap(frm);

        // Submitted doc: sirf date allow_on_submit hai, salary/statutory
        // recalc nahi karna — warna total_employer_contribution jaise
        // non-allow-on-submit fields floating-point drift se mismatch ho
        // jaate hain (e.g. 2720.49 -> 2720.4900000000002) aur save fail
        // hota hai "Not allowed to change ... after submission".
        if (frm.doc.docstatus === 1) return;

        if (frm.doc.salary_structure) refresh_statutory_rows(frm);
        check_srr_and_apply(frm);
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
            _remove_daily_wage_panel(frm);
            return;
        }
        load_salary_structure(frm);
    },

    category(frm) {
        toggle_skill_type(frm);
    },
});

// ─────────────────────────────────────────────────────────────
//  Salary Details — live recalc
// ─────────────────────────────────────────────────────────────

frappe.ui.form.on("Salary Details", {
    amount(frm, cdt, cdn) {
        const row = frappe.get_doc(cdt, cdn);

        if (frm._locked_vda_row
            && row
            && row.name === frm._locked_vda_row
            && row.parentfield === "earnings") {
            frappe.show_alert({
                message:   __("V-DA amount is controlled by Skill Rate Revision and cannot be edited."),
                indicator: "orange"
            });
            frappe.model.set_value(cdt, cdn, "amount",      frm._locked_vda_amount || 0);
            frappe.model.set_value(cdt, cdn, "base_amount", frm._locked_vda_amount || 0);
            return;
        }

        if (frm._computing_daily_wage) return;

        setTimeout(() => {
            if (row && row.parentfield === "earnings") {
                refresh_statutory_rows(frm);
            } else {
                calculate_salary(frm);
            }
        }, 50);
    },
    salary_details_remove(frm, cdt, cdn) {
        _calculate_excluding_row(frm, cdn);
    }
});

// ─────────────────────────────────────────────────────────────
//  Live amount input binding
// ─────────────────────────────────────────────────────────────

function _bind_live_amount_inputs(frm) {
    $(frm.wrapper).off(".live_amount");

    const AMOUNT_SEL = ".grid-row input[data-fieldname='amount']";

    $(frm.wrapper).on("change.live_amount", AMOUNT_SEL, function () {
        if (frm._computing_daily_wage) return;
        const rowname     = $(this).closest("[data-name]").attr("data-name");
        if (!rowname) return;
        const in_earnings = !!(frm.doc.earnings || []).find(r => r.name === rowname);
        if (!in_earnings) return;
        _debounced_recalc(frm, refresh_statutory_rows, 150);
    });
}

// ─────────────────────────────────────────────────────────────
//  Daily Wage Panel
// ─────────────────────────────────────────────────────────────

function maybe_render_daily_wage_panel(frm) {
    _remove_daily_wage_panel(frm);
    if (!frm.doc.salary_structure) return;

    const category = frm.doc.category;
    if (category) {
        _check_subtype_and_render(frm, category);
    } else if (frm.doc.employee) {
        frappe.db.get_value("Company Link", frm.doc.employee, "category", (r) => {
            const cat = r && r.category;
            if (!cat) return;
            _check_subtype_and_render(frm, cat);
        });
    }
}

function _check_subtype_and_render(frm, category) {
    frappe.db.get_value("Category", category, "has_subtype", (r) => {
        if (!r || !r.has_subtype) return;

        const dw_rows = _get_daily_wage_rows(frm);
        if (!dw_rows.length) return;

        if (frm.doc.skill_type && frm.doc.from_date) {
            frappe.call({
                method: "saral_hr.saral_hr.doctype.salary_structure_assignment.salary_structure_assignment.get_daily_wage_multiplier",
                args: { start_date: frm.doc.from_date, skill_type: frm.doc.skill_type },
                callback(r) {
                    const multiplier = (r.message && r.message.multiplier) ? flt(r.message.multiplier) : 26;
                    _build_daily_wage_panel(frm, dw_rows, multiplier);
                },
                error() { _build_daily_wage_panel(frm, dw_rows, 26); }
            });
        } else {
            _build_daily_wage_panel(frm, dw_rows, 26);
        }
    });
}

function _get_daily_wage_rows(frm) {
    const all = [
        ...(frm.doc.earnings       || []),
        ...(frm.doc.deductions     || []),
        ...(frm.doc.employer_share || []),
    ];
    return all.filter(r => parseInt(r.daily_wage_component));
}

function _remove_daily_wage_panel(frm) {
    if (frm.wrapper) $(frm.wrapper).find(".dw-panel").remove();
    const f = frm.fields_dict["daily_wage_html"];
    if (f && f.$wrapper) f.$wrapper.empty();
}

function _build_daily_wage_panel(frm, dw_rows, multiplier) {
    if (!dw_rows || !dw_rows.length) return;

    const is_readonly = frm.doc.docstatus !== 0;

    const rows_html = dw_rows.map((row, idx) => {
        const saved_per_day_rate = flt(row.per_day_rate);
        const per_day = flt(row._dw_per_day) > 0
            ? flt(row._dw_per_day)
            : saved_per_day_rate > 0
                ? saved_per_day_rate
                : (flt(row.amount) > 0 ? flt(flt(row.amount) / multiplier, 4) : "");

        const saved_amount = flt(row.amount) || 0;
        const monthly_display = saved_amount > 0
            ? flt(saved_amount, 2).toLocaleString("en-IN", {minimumFractionDigits:2, maximumFractionDigits:2})
            : "";

        return `
        <tr class="dw-data-row" data-rowname="${row.name}" data-parentfield="${row.parentfield}">
            <td class="dw-td-sr">${idx + 1}</td>
            <td class="dw-td-component">
                <div class="dw-comp-name">${frappe.utils.escape_html(row.salary_component || "")}</div>
                <div class="dw-comp-abbr">${frappe.utils.escape_html(row.abbr || "")}</div>
            </td>
            <td class="dw-td-perday">
                <input
                    type="number"
                    class="dw-rate-input${is_readonly ? " dw-readonly" : ""}"
                    data-rowname="${row.name}"
                    min="0"
                    step="0.01"
                    placeholder="0.00"
                    value="${per_day}"
                    ${is_readonly ? "disabled readonly tabindex='-1'" : ""}
                />
            </td>
            <td class="dw-td-monthly">
                <span class="dw-computed-val" data-rowname="${row.name}">${monthly_display}</span>
            </td>
        </tr>`;
    }).join("");

    const panel_html = `
        <div class="dw-panel">
        <style>
            .dw-panel { margin-bottom: 16px; }
            .dw-grid-label {
                display: flex; align-items: center; justify-content: space-between;
                margin-bottom: 6px;
            }
            .dw-grid-label-text {
                font-size: 12px; font-weight: 600;
                color: var(--text-muted, #8d99a6);
                text-transform: uppercase; letter-spacing: 0.04em;
            }
            .dw-grid-label-meta {
                font-size: 11px; font-weight: 400;
                color: var(--text-muted, #adb5bd); margin-left: 8px;
                text-transform: none; letter-spacing: 0;
            }
            .dw-grid-actions { display: flex; gap: 6px; }
            .dw-grid-wrap {
                border: 1px solid var(--border-color, #d1d8dd);
                border-radius: var(--border-radius, 6px); overflow: hidden;
            }
            .dw-grid-table {
                width: 100%; border-collapse: collapse;
                font-size: 13px; table-layout: fixed;
            }
            .dw-grid-table thead tr {
                background: var(--datatable-header-background, #f3f4f6);
                border-bottom: 1px solid var(--border-color, #d1d8dd);
            }
            .dw-grid-table thead th {
                padding: 7px 10px; font-size: 11px; font-weight: 600;
                color: var(--text-muted, #6b7280); text-transform: uppercase;
                letter-spacing: 0.04em; text-align: left; white-space: nowrap;
                border-right: 1px solid var(--border-color, #e5e7eb);
            }
            .dw-grid-table thead th:last-child { border-right: none; }
            .dw-th-right { text-align: right !important; }
            .dw-data-row {
                border-bottom: 1px solid var(--border-color, #f0f0f0);
                transition: background 0.1s;
            }
            .dw-data-row:last-child { border-bottom: none; }
            .dw-data-row:hover { background: var(--fg-hover-color, #f9fafb); }
            .dw-data-row td {
                padding: 6px 10px; vertical-align: middle;
                border-right: 1px solid var(--border-color, #f0f0f0);
            }
            .dw-data-row td:last-child { border-right: none; }
            .dw-td-sr { width: 40px; text-align: center; color: var(--text-muted, #adb5bd); font-size: 11px; }
            .dw-td-component { width: auto; }
            .dw-td-perday  { width: 180px; }
            .dw-td-monthly { width: 150px; text-align: right; }
            .dw-comp-name { font-size: 13px; font-weight: 500; color: var(--text-color, #1f2937); line-height: 1.3; }
            .dw-comp-abbr { font-size: 11px; color: var(--text-muted, #8d99a6); margin-top: 1px; }
            .dw-rate-input {
                width: 100%; height: 28px; padding: 0 8px; font-size: 13px;
                color: var(--text-color, #1f2937); background: transparent;
                border: 1px solid transparent; border-radius: var(--border-radius-sm, 4px);
                outline: none; text-align: right; transition: border-color 0.15s; box-sizing: border-box;
            }
            .dw-rate-input:hover  { border-color: var(--border-color, #d1d8dd); }
            .dw-rate-input:focus  { border-color: var(--primary, #5e64ff); background: var(--control-bg, #fff); box-shadow: 0 0 0 2px rgba(94,100,255,0.12); }
            .dw-rate-input.dw-error { border-color: var(--red-500, #ef4444) !important; background: #fff5f5; }
            .dw-rate-input::placeholder { color: var(--text-muted, #d1d5db); }
            .dw-rate-input.dw-readonly, .dw-rate-input[disabled] {
                background: transparent !important; border-color: transparent !important;
                box-shadow: none !important; cursor: default !important;
                color: var(--text-color, #1f2937); pointer-events: none;
            }
            .dw-computed-val { font-size: 13px; font-weight: 500; color: var(--text-color, #1f2937); }
            .dw-computed-val.has-value { color: var(--primary, #5e64ff); }
            .dw-computed-val:empty::before { content: "—"; color: var(--text-muted, #d1d5db); font-weight: 400; }
        </style>
        <div class="dw-grid-label">
            <div>
                <span class="dw-grid-label-text">Daily Wage Entry</span>
                <span class="dw-grid-label-meta">per-day × ${multiplier} days = monthly</span>
            </div>
            ${is_readonly ? "" : `
            <div class="dw-grid-actions">
                <button class="btn btn-xs btn-default dw-reset-btn">Reset</button>
                <button class="btn btn-xs btn-primary dw-compute-btn">Compute</button>
            </div>`}
        </div>
        <div class="dw-grid-wrap">
            <table class="dw-grid-table">
                <thead>
                    <tr>
                        <th class="dw-td-sr">Sr</th>
                        <th>Component</th>
                        <th class="dw-th-right">Per Day (₹)</th>
                        <th class="dw-th-right">Monthly (₹)</th>
                    </tr>
                </thead>
                <tbody class="dw-tbody">${rows_html}</tbody>
            </table>
        </div>
        </div>
    `;

    const $anchor = frm.fields_dict["daily_wage_html"] &&
                    frm.fields_dict["daily_wage_html"].$wrapper;

    if ($anchor && $anchor.length) {
        $anchor.html(panel_html);
    } else {
        const $ew = frm.fields_dict["earnings"] && frm.fields_dict["earnings"].$wrapper;
        if ($ew && $ew.length) $ew.before(panel_html);
    }

    const $panel = ($anchor && $anchor.length)
        ? $anchor.find(".dw-panel")
        : $(frm.wrapper).find(".dw-panel").last();

    $panel.on("input", ".dw-rate-input", function () {
        const per_day = flt($(this).val());
        const monthly = per_day > 0 ? flt(per_day * multiplier, 2) : 0;
        const rname   = $(this).data("rowname");
        $(this).removeClass("dw-error");
        const $val = $panel.find(`.dw-computed-val[data-rowname="${rname}"]`);
        if (monthly > 0) {
            $val.text(monthly.toLocaleString("en-IN", {minimumFractionDigits:2, maximumFractionDigits:2}));
            $val.addClass("has-value");
        } else {
            $val.text("").removeClass("has-value");
        }
    });

    $panel.find(".dw-compute-btn").on("click", function () {
        let any_missing = false;
        $panel.find(".dw-rate-input").each(function () {
            if ($(this).val() === "" || isNaN(flt($(this).val()))) {
                any_missing = true;
                $(this).addClass("dw-error");
            } else {
                $(this).removeClass("dw-error");
            }
        });

        if (any_missing) {
            frappe.show_alert({ message: __("Please enter a per-day rate for all components."), indicator: "orange" });
            return;
        }

        frm._computing_daily_wage = true;

        $panel.find(".dw-rate-input").each(function () {
            const per_day = flt($(this).val());
            const monthly = flt(per_day * multiplier, 2);
            const rname   = $(this).data("rowname");
            const pfield  = $(this).closest("tr").data("parentfield");

            const table = frm.doc[pfield] || [];
            const match = (table.filter ? table.filter(r => r.name === rname) : [])[0];
            if (match) match._dw_per_day = per_day;

            frappe.model.set_value("Salary Details", rname, "amount",       monthly);
            frappe.model.set_value("Salary Details", rname, "base_amount",  monthly);
            frappe.model.set_value("Salary Details", rname, "per_day_rate", per_day);

            const $val = $panel.find(`.dw-computed-val[data-rowname="${rname}"]`);
            $val.text(monthly.toLocaleString("en-IN", {minimumFractionDigits:2, maximumFractionDigits:2}));
            $val.addClass("has-value");
        });

        frm._computing_daily_wage = false;

        frm.refresh_fields(["earnings", "deductions", "employer_share"]);
        refresh_statutory_rows(frm);
        frappe.show_alert({ message: __("Monthly amounts applied."), indicator: "green" });
    });

    $panel.find(".dw-reset-btn").on("click", function () {
        $panel.find(".dw-rate-input").val("").removeClass("dw-error");
        $panel.find(".dw-computed-val").text("").removeClass("has-value");

        frm._computing_daily_wage = true;
        dw_rows.forEach(row => {
            frappe.model.set_value("Salary Details", row.name, "amount",       0);
            frappe.model.set_value("Salary Details", row.name, "base_amount",  0);
            frappe.model.set_value("Salary Details", row.name, "per_day_rate", 0);
            row._dw_per_day = 0;
        });
        frm._computing_daily_wage = false;

        frm.refresh_fields(["earnings", "deductions", "employer_share"]);
        refresh_statutory_rows(frm);
        frappe.show_alert({ message: __("Daily wage amounts reset."), indicator: "blue" });
    });
}

// ─────────────────────────────────────────────────────────────
//  Statutory controls (HTML checkboxes)
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

    const pf_select = pf ? `
        <select id="ssa-pf-type" ${editable ? "" : "disabled"}
            style="margin-left:4px;margin-right:14px;height:26px;padding:0 8px;font-size:12px;
                   border:1px solid var(--border-color,#d1d8dd);border-radius:4px;background:#fff;
                   cursor:${editable ? "pointer" : "default"};">
            <option value=""           ${!pftype                 ? "selected" : ""}>${__("Select type")}</option>
            <option value="Limited PF" ${pftype === "Limited PF" ? "selected" : ""}>${__("Limited PF")}</option>
            <option value="Full PF"    ${pftype === "Full PF"    ? "selected" : ""}>${__("Full PF")}</option>
        </select>` : `<span style="margin-right:14px;"></span>`;

    f.$wrapper.html(`
        <div style="padding:4px 0 8px 0;display:flex;flex-wrap:wrap;align-items:center;">
            ${cb("ssa-esic", "ESIC", esic)}
            ${cb("ssa-pf",   "PF",   pf)}
            ${pf_select}
            ${cb("ssa-pt",   "PT",   pt)}
            ${cb("ssa-lwf",  "LWF",  lwf)}
        </div>
    `);

    if (!editable) return;

    f.$wrapper.find("#ssa-esic").on("change", function () {
        frm.set_value("is_esic_applicable", this.checked ? 1 : 0);
        refresh_statutory_rows(frm); render_statutory_controls(frm);
    });
    f.$wrapper.find("#ssa-pf").on("change", function () {
        frm.set_value("is_pf_applicable", this.checked ? 1 : 0);
        if (!this.checked) frm.set_value("pf_applicable", "");
        refresh_statutory_rows(frm); render_statutory_controls(frm);
    });
    f.$wrapper.find("#ssa-pf-type").on("change", function () {
        frm.set_value("pf_applicable", this.value);
        refresh_statutory_rows(frm);
    });
    f.$wrapper.find("#ssa-pt").on("change", function () {
        frm.set_value("is_pt_applicable", this.checked ? 1 : 0);
        refresh_statutory_rows(frm); render_statutory_controls(frm);
    });
    f.$wrapper.find("#ssa-lwf").on("change", function () {
        frm.set_value("is_lwf_applicable", this.checked ? 1 : 0);
        refresh_statutory_rows(frm); render_statutory_controls(frm);
    });
}

// ─────────────────────────────────────────────────────────────
//  Show/hide skill_type
// ─────────────────────────────────────────────────────────────

function toggle_skill_type(frm) {
    if (!frm.doc.category) {
        frm.set_df_property("skill_type", "hidden", 1);
        frm.refresh_field("skill_type");
        return;
    }
    frappe.db.get_value("Category", frm.doc.category, "has_subtype", (r) => {
        const show = r && !!r.has_subtype;
        frm.set_df_property("skill_type", "hidden", show ? 0 : 1);
        frm.refresh_field("skill_type");
    });
}

// ─────────────────────────────────────────────────────────────
//  SRR check and apply
// ─────────────────────────────────────────────────────────────

function check_srr_and_apply(frm) {
    if (!frm.doc.employee || !frm.doc.from_date) return;

    frappe.db.get_value("Company Link", frm.doc.employee, ["category", "skill_type"], (emp) => {
        const category   = (emp && emp.category)   || frm.doc.category;
        const skill_type = (emp && emp.skill_type) || frm.doc.skill_type;
        if (!category || !skill_type) return;

        frappe.db.get_value("Category", category, "has_subtype", (r) => {
            if (!r || !r.has_subtype) return;

            frappe.call({
                method: "saral_hr.saral_hr.doctype.salary_structure_assignment.salary_structure_assignment.get_srr_for_ssa",
                args: { start_date: frm.doc.from_date, skill_type: skill_type },
                callback(res) {
                    if (!res.message) {
                        frappe.msgprint({
                            title:     __("Skill Rate Revision Not Found"),
                            message:   __(
                                `Employee <strong>${frm.doc.employee_name || frm.doc.employee}</strong> `
                                + `belongs to category <strong>${category}</strong> `
                                + `with skill type <strong>${skill_type}</strong>.<br><br>`
                                + `No submitted Skill Rate Revision found covering <strong>${frm.doc.from_date}</strong>. `
                                + `Please create and submit a Skill Rate Revision for this period `
                                + `before creating this assignment.`
                            ),
                            indicator: "red"
                        });
                        frm.set_value("from_date", "");
                        return;
                    }
                    apply_srr_to_earnings(frm, res.message);
                }
            });
        });
    });
}

function apply_srr_to_earnings(frm, srr) {
    if (!frm.doc.earnings || !frm.doc.earnings.length) return;

    const has_basic = frm.doc.earnings.some(row => {
        const comp = (row.salary_component || "").toLowerCase();
        const abbr = (row.abbr || "").toLowerCase().trim();
        return comp.includes("basic") || abbr === "basic";
    });
    const has_vda = frm.doc.earnings.some(row => {
        const comp = (row.salary_component || "").toLowerCase();
        const abbr = (row.abbr || "").toLowerCase().trim();
        return comp.includes("dearness") || abbr === "v-da" || abbr === "vda";
    });

    if (!has_basic && !has_vda) return;

    let vda_row_name = null;

    frm.doc.earnings.forEach(row => {
        const comp     = (row.salary_component || "").toLowerCase();
        const abbr     = (row.abbr || "").toLowerCase().trim();
        const is_basic = comp.includes("basic") || abbr === "basic";
        const is_vda   = comp.includes("dearness") || abbr === "v-da" || abbr === "vda";

        if (is_basic) {
            frappe.model.set_value(row.doctype, row.name, "amount",      flt(srr.vbasic, 2));
            frappe.model.set_value(row.doctype, row.name, "base_amount", flt(srr.vbasic, 2));
        }
        if (is_vda) {
            frappe.model.set_value(row.doctype, row.name, "amount",      flt(srr.vda, 2));
            frappe.model.set_value(row.doctype, row.name, "base_amount", flt(srr.vda, 2));
            vda_row_name           = row.name;
            frm._locked_vda_amount = flt(srr.vda, 2);
        }
    });

    frm.refresh_field("earnings");
    if (vda_row_name) frm._locked_vda_row = vda_row_name;
    refresh_statutory_rows(frm);
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

            (structure.earnings || []).forEach(row => copy_row(frm.add_child("earnings"), row));

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
            maybe_render_daily_wage_panel(frm);

            setTimeout(() => check_srr_and_apply(frm), 500);
        }
    });
}

// ─────────────────────────────────────────────────────────────
//  Refresh statutory rows
// ─────────────────────────────────────────────────────────────

function _remove_statutory_rows(frm) {
    const keep_ded  = (frm.doc.deductions    || []).filter(r => !ALL_STATUTORY.includes((r.salary_component || "").trim()));
    const keep_empr = (frm.doc.employer_share || []).filter(r => !ALL_STATUTORY.includes((r.salary_component || "").trim()));

    const snap_ded  = keep_ded.map(r => ({ ...r }));
    const snap_empr = keep_empr.map(r => ({ ...r }));

    frm.clear_table("deductions");
    frm.clear_table("employer_share");

    snap_ded.forEach(snap => {
        const child = frm.add_child("deductions");
        copy_row(child, snap);
    });
    snap_empr.forEach(snap => {
        const child = frm.add_child("employer_share");
        copy_row(child, snap);
    });

    frm.refresh_fields(["deductions", "employer_share"]);
}

function refresh_statutory_rows(frm) {
    if (!frm.doc.salary_structure || !frm.doc.company) return;

    if (_statutory_inflight) {
        _statutory_pending = true;
        return;
    }

    _remove_statutory_rows(frm);

    const any_on = frm.doc.is_esic_applicable || frm.doc.is_pf_applicable
        || frm.doc.is_pt_applicable || frm.doc.is_lwf_applicable;

    if (!any_on) {
        calculate_salary(frm);
        return;
    }

    const earnings_map = _earnings_map(frm);
    _statutory_inflight = true;

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
            _statutory_inflight = false;

            if (r.message) {
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

                // ── CHANGED: exclude_from_ctc is now passed from Python response ──
                (r.message.employer_share || []).forEach(d => {
                    const child = frm.add_child("employer_share");
                    frappe.model.set_value(child.doctype, child.name, {
                        salary_component:      d.salary_component,
                        abbr:                  d.abbr || "",
                        amount:                flt(d.amount),
                        base_amount:           flt(d.amount),
                        employer_contribution: 1,
                        exclude_from_ctc:      d.exclude_from_ctc ? 1 : 0,
                    });
                });

                frm.refresh_fields(["deductions", "employer_share"]);
                calculate_salary(frm);
            }

            if (_statutory_pending) {
                _statutory_pending = false;
                refresh_statutory_rows(frm);
            }
        },
        error() {
            _statutory_inflight = false;
            _statutory_pending  = false;
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
    if (frm.fields_dict["daily_wage_html"]) {
        frm.toggle_display("daily_wage_html", s);
    }
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

// ─────────────────────────────────────────────────────────────
//  Recalc after row deletion, excluding the just-deleted row
// ─────────────────────────────────────────────────────────────

function _calculate_excluding_row(frm, deleted_cdn) {
    const gross       = flt(_sum_earnings_excluding(frm, deleted_cdn), 2);
    let emp_ded       = 0;
    let empr_cont     = 0;
    let empr_cont_ctc = 0;

    (frm.doc.deductions || []).forEach(d => {
        if (d.name !== deleted_cdn) emp_ded += flt(d.amount);
    });
    (frm.doc.employer_share || []).forEach(d => {
        if (d.name !== deleted_cdn) {
            empr_cont += flt(d.amount);
            if (!d.exclude_from_ctc) empr_cont_ctc += flt(d.amount);
        }
    });

    // Round the running totals once, after summation, instead of leaving
    // raw JS floating-point sums (e.g. 2720.4900000000002) in the doc —
    // those silently fail the "no change after submit" check elsewhere.
    emp_ded       = flt(emp_ded, 2);
    empr_cont     = flt(empr_cont, 2);
    empr_cont_ctc = flt(empr_cont_ctc, 2);

    const values = {
        gross_salary:                gross,
        total_deductions:            emp_ded,
        total_employer_contribution: empr_cont,
        net_salary:                  flt(gross - emp_ded, 2),
        monthly_ctc:                 flt(gross + empr_cont_ctc, 2),
        annual_ctc:                  flt((gross + empr_cont_ctc) * 12, 2),
        total_basic_da:              _sum_basic_da_excluding(frm, deleted_cdn),
    };

    frm.set_value(values);
    frm.refresh_fields(["gross_salary", "total_deductions",
        "total_employer_contribution", "net_salary", "monthly_ctc", "annual_ctc", "total_basic_da"]);
}

function _sum_earnings_excluding(frm, excluded_cdn) {
    let t = 0;
    (frm.doc.earnings || []).forEach(r => {
        if (r.name !== excluded_cdn) t += flt(r.amount);
    });
    return t;
}

function _sum_basic_da_excluding(frm, excluded_cdn) {
    let basic = 0, da = 0;
    (frm.doc.earnings || []).forEach(r => {
        if (r.name === excluded_cdn) return;
        const amt  = flt(r.amount);
        const comp = (r.salary_component || "").toLowerCase();
        const abbr = (r.abbr || "").toLowerCase().trim();
        if (comp.includes("basic") || abbr === "basic") basic += amt;
        if (comp.includes("dearness") || comp === "da"
            || abbr === "da" || abbr.startsWith("da-") || abbr.startsWith("da ")
            || abbr === "da - dr" || abbr.startsWith("da-dr")) da += amt;
    });
    return flt(basic + da, 2);
}

function _do_calculate(frm, silent) {
    const gross       = flt(_sum_earnings(frm), 2);
    let emp_ded       = 0;
    let empr_cont     = 0;
    let empr_cont_ctc = 0;

    (frm.doc.deductions || []).forEach(d => {
        emp_ded += flt(d.amount);
    });
    // ── CHANGED: split total employer cost from CTC-eligible portion ──
    (frm.doc.employer_share || []).forEach(d => {
        empr_cont += flt(d.amount);
        if (!d.exclude_from_ctc) empr_cont_ctc += flt(d.amount);
    });

    // Round the running totals once, after summation — JS floating-point
    // addition over the employer_share rows otherwise leaves values like
    // 2720.4900000000002 in total_employer_contribution, which then blocks
    // saving a submitted doc even when nothing actually changed.
    emp_ded       = flt(emp_ded, 2);
    empr_cont     = flt(empr_cont, 2);
    empr_cont_ctc = flt(empr_cont_ctc, 2);

    const values = {
        gross_salary:                gross,
        total_deductions:            emp_ded,
        total_employer_contribution: empr_cont,       // full cost — EDLI + admin included
        net_salary:                  flt(gross - emp_ded, 2),
        monthly_ctc:                 flt(gross + empr_cont_ctc, 2),   // excludes flagged components
        annual_ctc:                  flt((gross + empr_cont_ctc) * 12, 2),
        total_basic_da:              _sum_basic_da(frm),
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
            "total_employer_contribution", "net_salary", "monthly_ctc", "annual_ctc", "total_basic_da"]);
    }
}

function _sum_earnings(frm) {
    let t = 0;
    (frm.doc.earnings || []).forEach(r => {
        t += flt(r.amount);
    });
    return t;
}

function _sum_basic_da(frm) {
    let basic = 0, da = 0;
    (frm.doc.earnings || []).forEach(r => {
        const amt  = flt(r.amount);
        const comp = (r.salary_component || "").toLowerCase();
        const abbr = (r.abbr || "").toLowerCase().trim();
        if (comp.includes("basic") || abbr === "basic") basic += amt;
        if (comp.includes("dearness") || comp === "da"
            || abbr === "da" || abbr.startsWith("da-") || abbr.startsWith("da ")
            || abbr === "da - dr" || abbr.startsWith("da-dr")) da += amt;
    });
    return flt(basic + da, 2);
}

function _earnings_map(frm) {
    const map = {};
    (frm.doc.earnings || []).forEach(r => {
        const comp = (r.salary_component || "").trim();
        if (comp) map[comp] = flt(r.amount);
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