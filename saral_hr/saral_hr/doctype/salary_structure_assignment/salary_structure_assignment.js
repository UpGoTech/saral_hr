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
            if (frm.doc.docstatus !== 1) {
                // On refresh, statutory rows are already saved in DB
                // suppress refresh to avoid double-loading
                frm._suppress_statutory_refresh = true;
                setTimeout(() => {
                    calculate_salary(frm);
                    maybe_render_daily_wage_panel(frm);
                }, 150);
            } else {
                // Submitted doc — only render daily wage panel, no recalc
                setTimeout(() => maybe_render_daily_wage_panel(frm), 150);
            }
        }
        _bind_live_amount_inputs(frm);
    },

    setup(frm) {
        frm.set_query("employee", () => ({ filters: { is_active: 1 } }));
        frm.set_query("salary_structure", () => ({
            filters: { company: frm.doc.company || "", is_active: "Yes" }
        }));
        frm.set_query("salary_component", "earnings", () => ({
            filters: { type: "Earning", is_additional_only: 0 }
        }));
        frm.set_query("salary_component", "deductions", () => ({
            filters: { type: "Deduction", is_additional_only: 0 }
        }));
        frm.set_query("salary_component", "employer_share", () => ({
            filters: { type: "Deduction", is_additional_only: 0 }
        }));
    },

    employee(frm) {
        if (!frm.doc.employee || frm._checking_employee === frm.doc.employee) {
            toggle_fields(frm);
            return;
        }
        // Do not reload/reset on submitted doc employee trigger
        if (frm.doc.docstatus === 1) return;
        frm._checking_employee = frm.doc.employee;

        frappe.call({
            method: "saral_hr.saral_hr.doctype.salary_structure_assignment.salary_structure_assignment.get_existing_assignments",
            args: { employee: frm.doc.employee },
            callback(r) {
                // Store assignments but don\'t show error yet — wait for dates
                frm._existing_assignments = (r.message && r.message.length) ? r.message : [];
                frm._has_existing = false;
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

        // Submitted doc: no overlap check — original is cancelled after amend
        // Only validate SRR, no salary recalc (avoid float drift)
        if (frm.doc.docstatus === 1) {
            check_srr_and_apply_validate_only(frm);
            return;
        }

        if (frm.doc.from_date && frm.doc.to_date) check_overlap(frm);
        // After refresh, statutory rows are already in DB — avoid double load
        if (frm.doc.salary_structure) {
            frm._suppress_statutory_refresh = false;  // allow fresh recalc on date change
            refresh_statutory_rows(frm);
        }
        check_srr_and_apply_validate_only(frm);
    },

    to_date(frm) {
        toggle_fields(frm);
        if (frm.doc.docstatus === 1) return;  // no overlap check on submitted doc
        if (frm.doc.from_date && frm.doc.to_date) check_overlap(frm);
    },

    salary_structure(frm) {
        toggle_salary_sections(frm);
        if (frm.doc.docstatus === 1) return;  // no reload on submitted doc
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

        // Sync latest value directly into frm.doc row
        // to prevent grid re-render from wiping dw amounts
        if (row) {
            const all = [
                ...(frm.doc.earnings       || []),
                ...(frm.doc.deductions     || []),
                ...(frm.doc.employer_share || []),
            ];
            const doc_row = all.find(r => r.name === row.name);
            if (doc_row && !parseInt(doc_row.daily_wage_component)) {
                doc_row.amount      = flt(row.amount);
                doc_row.base_amount = flt(row.amount);
            }
        }

        setTimeout(() => calculate_salary(frm), 50);
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
    if (frm.doc.docstatus === 1) return;  // no live recalc binding on submitted doc

    const AMOUNT_SEL = ".grid-row input[data-fieldname=\'amount\']";

    // On Enter/ArrowDown: block grid row re-render and move to next row
    $(frm.wrapper).on("keydown.live_amount", AMOUNT_SEL, function (e) {
        if (e.key === "Enter" || e.key === "ArrowDown" || e.key === "ArrowUp") {
            e.stopPropagation();

            // Set value directly in frm.doc
            const rowname = $(this).closest("[data-name]").attr("data-name");
            const val     = flt($(this).val());
            if (rowname) {
                const all = [...(frm.doc.earnings||[]), ...(frm.doc.deductions||[]), ...(frm.doc.employer_share||[])];
                const row = all.find(r => r.name === rowname);
                if (row) { row.amount = val; row.base_amount = val; }
            }

            // Move focus to next/prev amount input
            const $all_inputs = $(frm.wrapper).find(AMOUNT_SEL + ":visible");
            const idx = $all_inputs.index(this);
            if (e.key === "ArrowUp") {
                if (idx > 0) $all_inputs.eq(idx - 1).focus();
            } else {
                if (idx < $all_inputs.length - 1) $all_inputs.eq(idx + 1).focus();
            }

            setTimeout(() => calculate_salary(frm), 50);
        }
    });

    $(frm.wrapper).on("change.live_amount", AMOUNT_SEL, function () {
        if (frm._computing_daily_wage) return;
        const rowname     = $(this).closest("[data-name]").attr("data-name");
        if (!rowname) return;
        const in_earnings = !!(frm.doc.earnings || []).find(r => r.name === rowname);
        if (!in_earnings) return;
        _debounced_recalc(frm, calculate_salary, 150);
    });
}

// ─────────────────────────────────────────────────────────────
//  Daily Wage Panel
// ─────────────────────────────────────────────────────────────

function maybe_render_daily_wage_panel(frm) {
    // Submitted doc: panel already rendered, saved values shown
    // Rebuilding would zero out dw amounts
    if (frm.doc.docstatus === 1 && $(frm.wrapper).find(".dw-panel").length) return;
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
                    ${is_readonly ? "disabled readonly tabindex=\'-1\'" : ""}
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
            .dw-grid-label { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; }
            .dw-grid-label-text { font-size: 12px; font-weight: 600; color: var(--text-muted, #8d99a6); text-transform: uppercase; letter-spacing: 0.04em; }
            .dw-grid-label-meta { font-size: 11px; font-weight: 400; color: var(--text-muted, #adb5bd); margin-left: 8px; text-transform: none; letter-spacing: 0; }
            .dw-grid-actions { display: flex; gap: 6px; }
            .dw-grid-wrap { border: 1px solid var(--border-color, #d1d8dd); border-radius: var(--border-radius, 6px); overflow: hidden; }
            .dw-grid-table { width: 100%; border-collapse: collapse; font-size: 13px; table-layout: fixed; }
            .dw-grid-table thead tr { background: var(--datatable-header-background, #f3f4f6); border-bottom: 1px solid var(--border-color, #d1d8dd); }
            .dw-grid-table thead th { padding: 7px 10px; font-size: 11px; font-weight: 600; color: var(--text-muted, #6b7280); text-transform: uppercase; letter-spacing: 0.04em; text-align: left; white-space: nowrap; border-right: 1px solid var(--border-color, #e5e7eb); }
            .dw-grid-table thead th:last-child { border-right: none; }
            .dw-th-right { text-align: right !important; }
            .dw-data-row { border-bottom: 1px solid var(--border-color, #f0f0f0); transition: background 0.1s; }
            .dw-data-row:last-child { border-bottom: none; }
            .dw-data-row:hover { background: var(--fg-hover-color, #f9fafb); }
            .dw-data-row td { padding: 6px 10px; vertical-align: middle; border-right: 1px solid var(--border-color, #f0f0f0); }
            .dw-data-row td:last-child { border-right: none; }
            .dw-td-sr { width: 40px; text-align: center; color: var(--text-muted, #adb5bd); font-size: 11px; }
            .dw-td-component { width: auto; }
            .dw-td-perday { width: 180px; }
            .dw-td-monthly { width: 150px; text-align: right; }
            .dw-comp-name { font-size: 13px; font-weight: 500; color: var(--text-color, #1f2937); line-height: 1.3; }
            .dw-comp-abbr { font-size: 11px; color: var(--text-muted, #8d99a6); margin-top: 1px; }
            .dw-rate-input { width: 100%; height: 28px; padding: 0 8px; font-size: 13px; color: var(--text-color, #1f2937); background: transparent; border: 1px solid transparent; border-radius: var(--border-radius-sm, 4px); outline: none; text-align: right; transition: border-color 0.15s; box-sizing: border-box; }
            .dw-rate-input:hover { border-color: var(--border-color, #d1d8dd); }
            .dw-rate-input:focus { border-color: var(--primary, #5e64ff); background: var(--control-bg, #fff); box-shadow: 0 0 0 2px rgba(94,100,255,0.12); }
            .dw-rate-input.dw-error { border-color: var(--red-500, #ef4444) !important; background: #fff5f5; }
            .dw-rate-input::placeholder { color: var(--text-muted, #d1d5db); }
            .dw-rate-input.dw-readonly, .dw-rate-input[disabled] { background: transparent !important; border-color: transparent !important; box-shadow: none !important; cursor: default !important; color: var(--text-color, #1f2937); pointer-events: none; }
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

    $panel.on("keydown", ".dw-rate-input", function (e) {
        if (e.key === "Enter" || e.key === "ArrowDown" || e.key === "ArrowUp") {
            e.preventDefault();
            e.stopPropagation();
            const $inputs = $panel.find(".dw-rate-input:not([disabled])");
            const idx     = $inputs.index(this);
            if (e.key === "ArrowUp") {
                if (idx > 0) $inputs.eq(idx - 1).focus();
            } else {
                if (idx < $inputs.length - 1) $inputs.eq(idx + 1).focus();
            }
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
            const per_day   = flt($(this).val());
            const monthly   = flt(per_day * multiplier, 2);
            const rname     = $(this).data("rowname");

            const all_rows  = [
                ...(frm.doc.earnings || []),
                ...(frm.doc.deductions || []),
                ...(frm.doc.employer_share || [])
            ];
            let match = all_rows.find(r => r.name === rname);
            if (!match) {
                const panel_comp = $(this).closest("tr").find(".dw-comp-name").text().trim();
                match = all_rows.find(r => r.salary_component === panel_comp && parseInt(r.daily_wage_component));
            }

            if (match) {
                match.amount       = monthly;
                match.base_amount  = monthly;
                match.per_day_rate = per_day;
                match._dw_per_day  = per_day;
            }

            const $val = $panel.find(`.dw-computed-val[data-rowname="${rname}"]`);
            $val.text(monthly.toLocaleString("en-IN", {minimumFractionDigits:2, maximumFractionDigits:2}));
            $val.addClass("has-value");
        });

        frm._computing_daily_wage = false;

        frm.refresh_fields(["earnings", "deductions", "employer_share"]);
        calculate_salary(frm);
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
        calculate_salary(frm);
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

    // ── FIXED: set value directly on frm.doc (synchronous) instead of frm.set_value (async)
    //           and reset inflight flags so refresh_statutory_rows always runs immediately ──

    f.$wrapper.find("#ssa-esic").on("change", function () {
        frm.doc.is_esic_applicable = this.checked ? 1 : 0;
        frm.dirty();
        _statutory_inflight             = false;
        _statutory_pending              = false;
        frm._suppress_statutory_refresh = false;  // clear suppress flag — user action always runs
        refresh_statutory_rows(frm);
        render_statutory_controls(frm);
    });

    f.$wrapper.find("#ssa-pf").on("change", function () {
        frm.doc.is_pf_applicable = this.checked ? 1 : 0;
        if (!this.checked) frm.doc.pf_applicable = "";
        frm.dirty();
        _statutory_inflight             = false;
        _statutory_pending              = false;
        frm._suppress_statutory_refresh = false;
        refresh_statutory_rows(frm);
        render_statutory_controls(frm);
    });

    f.$wrapper.find("#ssa-pf-type").on("change", function () {
        frm.doc.pf_applicable = this.value;
        frm.dirty();
        _statutory_inflight             = false;
        _statutory_pending              = false;
        frm._suppress_statutory_refresh = false;
        refresh_statutory_rows(frm);
    });

    f.$wrapper.find("#ssa-pt").on("change", function () {
        frm.doc.is_pt_applicable = this.checked ? 1 : 0;
        frm.dirty();
        _statutory_inflight             = false;
        _statutory_pending              = false;
        frm._suppress_statutory_refresh = false;
        refresh_statutory_rows(frm);
        render_statutory_controls(frm);
    });

    f.$wrapper.find("#ssa-lwf").on("change", function () {
        frm.doc.is_lwf_applicable = this.checked ? 1 : 0;
        frm.dirty();
        _statutory_inflight             = false;
        _statutory_pending              = false;
        frm._suppress_statutory_refresh = false;
        refresh_statutory_rows(frm);
        render_statutory_controls(frm);
    });
}

// ─────────────────────────────────────────────────────────────
//  Show/hide skill_type
// ─────────────────────────────────────────────────────────────

function toggle_skill_type(frm) {
    if (!frm.doc.category) {
        frm.get_field("skill_type").df.hidden = 1;
        frm.refresh_field("skill_type");
        return;
    }
    frappe.db.get_value("Category", frm.doc.category, "has_subtype", (r) => {
        const show = r && !!r.has_subtype;
        frm.get_field("skill_type").df.hidden = show ? 0 : 1;
        frm.refresh_field("skill_type");
    });
}

// ─────────────────────────────────────────────────────────────
//  SRR validate only — for submitted doc date edit
//  Only checks if SRR exists for new from_date, no amount apply
// ─────────────────────────────────────────────────────────────

function check_srr_and_apply_validate_only(frm) {
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
                                + `before updating this assignment.`
                            ),
                            indicator: "red"
                        });
                    }
                }
            });
        });
    });
}

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
                        return;
                    }
                    apply_srr_to_earnings(frm, res.message);
                }
            });
        });
    });
}

function apply_srr_to_earnings(frm, srr) {
    if (frm.doc.docstatus === 1) return;
    if (!frm.doc.earnings || !frm.doc.earnings.length) return;

    // Save daily wage amounts — restore after SRR apply
    const dw_saved = {};
    (frm.doc.earnings || [])
        .filter(r => parseInt(r.daily_wage_component))
        .forEach(r => { dw_saved[r.salary_component] = { amount: r.amount, base_amount: r.base_amount, per_day_rate: r.per_day_rate }; });

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

    // Restore daily wage amounts — SRR only changes Basic/VDA
    (frm.doc.earnings || [])
        .filter(r => parseInt(r.daily_wage_component) && dw_saved[r.salary_component])
        .forEach(r => {
            r.amount       = dw_saved[r.salary_component].amount;
            r.base_amount  = dw_saved[r.salary_component].base_amount;
            r.per_day_rate = dw_saved[r.salary_component].per_day_rate;
        });

    frm.refresh_field("earnings");
    if (vda_row_name) frm._locked_vda_row = vda_row_name;
    calculate_salary(frm);
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
    if (frm.doc.docstatus === 1) return;

    const dw_amounts = {};
    [...(frm.doc.earnings || []), ...(frm.doc.deductions || []), ...(frm.doc.employer_share || [])]
        .filter(r => parseInt(r.daily_wage_component))
        .forEach(r => { dw_amounts[r.salary_component] = { amount: flt(r.amount), base_amount: flt(r.base_amount), per_day_rate: flt(r.per_day_rate) }; });

    const earn_snap = (frm.doc.earnings || []).map(r => ({ ...r }));

    const keep_ded  = (frm.doc.deductions    || []).filter(r => !ALL_STATUTORY.includes((r.salary_component || "").trim()));
    const keep_empr = (frm.doc.employer_share || []).filter(r => !ALL_STATUTORY.includes((r.salary_component || "").trim()));

    const snap_ded  = keep_ded.map(r => ({ ...r }));
    const snap_empr = keep_empr.map(r => ({ ...r }));

    frm.clear_table("deductions");
    frm.clear_table("employer_share");

    snap_ded.forEach(snap => { const child = frm.add_child("deductions"); copy_row(child, snap); });
    snap_empr.forEach(snap => { const child = frm.add_child("employer_share"); copy_row(child, snap); });

    (frm.doc.earnings || []).forEach(r => {
        const saved = earn_snap.find(s => s.salary_component === r.salary_component);
        if (saved) {
            r.amount       = saved.amount;
            r.base_amount  = saved.base_amount;
            r.per_day_rate = saved.per_day_rate;
        }
    });

    [...(frm.doc.deductions || []), ...(frm.doc.employer_share || [])]
        .filter(r => parseInt(r.daily_wage_component) && dw_amounts[r.salary_component])
        .forEach(r => {
            r.amount       = dw_amounts[r.salary_component].amount;
            r.base_amount  = dw_amounts[r.salary_component].base_amount;
            r.per_day_rate = dw_amounts[r.salary_component].per_day_rate;
        });

    frm.refresh_fields(["deductions", "employer_share"]);
}

function refresh_statutory_rows(frm) {
    if (!frm.doc.salary_structure || !frm.doc.company) return;
    if (frm.doc.docstatus === 1) return;
    if (frm._suppress_statutory_refresh) { frm._suppress_statutory_refresh = false; return; }

    // Note: _statutory_inflight is reset by checkbox handlers before calling this
    // so user-triggered calls always go through immediately
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
            employee:           frm.doc.employee           || "",
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

function _set_hidden(frm, fieldname, hidden) {
    const f = frm.get_field(fieldname);
    if (!f) return;
    f.df.hidden = hidden ? 1 : 0;
    frm.refresh_field(fieldname);
}

function toggle_fields(frm) {
    const ok = !frm._has_existing;
    _set_hidden(frm, "assignment_section", !ok);
    _set_hidden(frm, "from_date",          !ok);
    _set_hidden(frm, "to_date",            !ok);
    _set_hidden(frm, "salary_structure",   !ok);
    toggle_salary_sections(frm);
}

function toggle_salary_sections(frm) {
    const s = !!frm.doc.salary_structure;
    _set_hidden(frm, "earnings_and_deductions_section", !s);
    _set_hidden(frm, "employer_share_section",          !s);
    _set_hidden(frm, "calculations_section",            !s);
    if (frm.fields_dict["daily_wage_html"]) {
        _set_hidden(frm, "daily_wage_html", !s);
    }
}

// ─────────────────────────────────────────────────────────────
//  Overlap check
// ─────────────────────────────────────────────────────────────

function check_overlap(frm) {
    if (!frm.doc.employee || !frm.doc.from_date || !frm.doc.to_date) return;

    const existing = frm._existing_assignments || [];
    if (existing.length) {
        const FAR_FUTURE = "9999-12-31";
        const a_start = frm.doc.from_date;
        const a_end   = frm.doc.to_date;

        for (const rec of existing) {
            if (rec.name === frm.doc.name) continue;
            const b_start = rec.from_date;
            const b_end   = rec.to_date || FAR_FUTURE;
            if (a_start <= b_end && b_start <= a_end) {
                frappe.msgprint({
                    title:     __("Date Range Overlap"),
                    indicator: "red",
                    message:   `This date range overlaps with an existing assignment: `
                        + `<a href="/app/salary-structure-assignment/${rec.name}" target="_blank">${rec.name}</a>`
                        + ` (${rec.from_date} to ${rec.to_date || "Ongoing"})`
                });
                return;
            }
        }
    }

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

function _calculate_excluding_row(frm, deleted_cdn) {
    const gross       = flt(_sum_earnings_excluding(frm, deleted_cdn), 2);
    let emp_ded       = 0;
    let empr_cont     = 0;
    let empr_cont_ctc = 0;

    (frm.doc.deductions || []).forEach(d => { if (d.name !== deleted_cdn) emp_ded += flt(d.amount); });
    (frm.doc.employer_share || []).forEach(d => {
        if (d.name !== deleted_cdn) {
            empr_cont += flt(d.amount);
            if (!d.exclude_from_ctc) empr_cont_ctc += flt(d.amount);
        }
    });

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

    Object.assign(frm.doc, values);
    frm.refresh_fields(["gross_salary", "total_deductions",
        "total_employer_contribution", "net_salary", "monthly_ctc", "annual_ctc", "total_basic_da"]);
}

function _sum_earnings_excluding(frm, excluded_cdn) {
    let t = 0;
    (frm.doc.earnings || []).forEach(r => { if (r.name !== excluded_cdn) t += flt(r.amount); });
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
    if (frm.doc.docstatus === 1) return;
    const gross       = flt(_sum_earnings(frm), 2);
    let emp_ded       = 0;
    let empr_cont     = 0;
    let empr_cont_ctc = 0;

    (frm.doc.deductions || []).forEach(d => { emp_ded += flt(d.amount); });
    (frm.doc.employer_share || []).forEach(d => {
        empr_cont += flt(d.amount);
        if (!d.exclude_from_ctc) empr_cont_ctc += flt(d.amount);
    });

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
        Object.assign(frm.doc, values);
        frm.refresh_fields(["gross_salary", "total_deductions",
            "total_employer_contribution", "net_salary", "monthly_ctc", "annual_ctc", "total_basic_da"]);
    }
}

function _sum_earnings(frm) {
    let t = 0;
    (frm.doc.earnings || []).forEach(r => { t += flt(r.amount); });
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