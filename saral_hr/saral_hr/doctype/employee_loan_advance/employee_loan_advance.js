// ============================================================
//  Employee Loan Advance — Client Script
// ============================================================

frappe.ui.form.on('Employee Loan Advance', {

    // Called every time the form is loaded or refreshed
    refresh(frm) {
        // Lock rows where is_deducted = 1 (Salary Slip already processed)
        lock_protected_rows(frm);

        // Snapshot original deduction amounts so we can revert if blocked
        frm.doc.__saved_schedule_amounts = {};
        (frm.doc.schedule || []).forEach(row => {
            frm.doc.__saved_schedule_amounts[row.name] = row.deduction_amount;
        });
    },

    amount: frm => trigger_generate(frm),
    tenure_months: frm => trigger_generate(frm),
    date: frm => trigger_generate(frm),
    start_month: frm => trigger_generate(frm),
    start_year: frm => trigger_generate(frm),
    installment_gap: frm => trigger_generate(frm),

    type(frm) {
        if (frm.doc.type === 'Loan-I' || frm.doc.type === 'Loan-II' || frm.doc.type === 'Loan') {
            trigger_generate(frm);
        } else {
            frm.clear_table('schedule');
            frm.refresh_field('schedule');
        }
    }
});

// ------------------------------------------------------------------ //
//  Child Table Events                                                 //
// ------------------------------------------------------------------ //

// FIX: This flag prevents the is_deferred event from firing twice.
// When code calls frappe.model.set_value(cdt, cdn, 'is_deferred', 0) to revert
// the checkbox, Frappe automatically re-triggers the is_deferred event.
// Setting this flag true before that call makes the handler exit immediately,
// so the blocking message only ever appears once.
let _reverting_deferred = false;
// ✅ ADD THIS HERE
let _checking_salary_slip = false;
let _salary_slip_msg_lock = false;
let _original_deduction_amount = null;  // ← NEW: stores value before user edits          // ← NEW: prevents chain reaction on auto-adjust
const _auto_adjusted_rows = new Set(); // ← prevents chain reaction on auto-adjust
let _auto_adjusting = false;           // ← FIX: was missing, caused ReferenceError
function show_salary_slip_message_once(title, month) {
    if (_salary_slip_msg_lock) return;

    _salary_slip_msg_lock = true;

    frappe.msgprint({
        title: __(title),
        indicator: 'red',
        message: __(
            `The Salary Slip for <b>${month}</b> has already been submitted and deducted.<br><br>` +
            `Please <b>cancel the Salary Slip</b> for <b>${month}</b> first, then try again.`
        )
    });

    setTimeout(() => {
        _salary_slip_msg_lock = false;
    }, 400);
}

frappe.ui.form.on('Employee Loan Advance Schedule', {

    // ← NEW: Captures original value BEFORE user starts typing
    deduction_amount_on_form_rendered(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        _original_deduction_amount = row.deduction_amount;
    },

    // Fires when user changes the deduction_amount field on any row
deduction_amount(frm, cdt, cdn) {
    const row = locals[cdt][cdn];

    // If this row was auto-adjusted by our code — skip entirely, don't chain
    if (_auto_adjusted_rows.has(cdn)) {
        _auto_adjusted_rows.delete(cdn);
        return;
    }

    // Capture original amount from snapshot RIGHT NOW
    const original_amt = frm.doc.__saved_schedule_amounts !== undefined
        && frm.doc.__saved_schedule_amounts[cdn] !== undefined
        ? frm.doc.__saved_schedule_amounts[cdn]
        : null;

    // If already deducted — revert and block
    if (row.is_deducted) {
        if (original_amt !== null) {
            frappe.model.set_value(cdt, cdn, 'deduction_amount', original_amt);
            frm.refresh_field('schedule');
        }
        show_salary_slip_message_once('Edit Not Allowed', row.month);
        return;
    }

    // Auto-adjust next month immediately — no server call needed here
    // Server check only needed to block if salary slip exists
    if (original_amt !== null) {
        auto_adjust_next_month(frm, cdt, cdn, original_amt);
        // Update snapshot to new value
        frm.doc.__saved_schedule_amounts[cdn] = row.deduction_amount;
    }

    // Still check server to block if salary slip submitted for this month
    check_salary_slip_for_month(frm, row, 'edit', cdt, cdn, null, null);
},
    // Fires when user toggles the "Is Deferred" checkbox on any row
    is_deferred(frm, cdt, cdn) {
        // FIX: Code is reverting the checkbox — exit immediately to prevent the second message
        if (_reverting_deferred) return;

        const row = locals[cdt][cdn];
        const emi = row.deduction_amount;

        // If already deducted, block immediately (no server call needed)
        if (row.is_deducted) {
            show_salary_slip_message_once('Deferral Not Allowed', row.month);
            // FIX: Revert checkbox with flag so the event does not fire again
            _reverting_deferred = true;
            frappe.model.set_value(cdt, cdn, 'is_deferred', 0);
            _reverting_deferred = false;
            return;
        }

        // If checkbox is being unchecked → undo the deferral
        if (!row.is_deferred) {
            undo_deferral(frm, cdt, cdn, emi);
            return;
        }

        // Checkbox is being checked → verify no Salary Slip before proceeding
        check_salary_slip_for_month(frm, row, 'defer', cdt, cdn, emi);
    }
});

// ================================================================== //
//  Salary Slip Check — Single Source of Truth for the Message        //
// ================================================================== //

/**
 * Calls the server to check if a submitted Salary Slip exists for the
 * given schedule row's month and employee.
 *
 * This is the ONLY place that shows the "Salary Slip already submitted"
 * message, which completely eliminates the double-message problem.
 *
 * Behaviour:
 *   - Salary Slip EXISTS   → show ONE clear blocking message, revert UI change
 *   - No Salary Slip       → proceed with defer or allow edit
 *
 * @param {object}      frm       Parent form
 * @param {object}      row       Current child schedule row
 * @param {string}      action    'defer' | 'edit'
 * @param {string}      cdt       Child doctype
 * @param {string}      cdn       Child row name
 * @param {number|null} emi       EMI amount (required for defer, null for edit)
 * @param {function}    on_success  Optional callback when no slip found and action = edit
 */
function check_salary_slip_for_month(frm, row, action, cdt, cdn, emi, on_success) {

    // 🚫 STOP if already running
    if (_checking_salary_slip) return;

    _checking_salary_slip = true;

    frappe.call({
        method: 'saral_hr.saral_hr.doctype.employee_loan_advance.employee_loan_advance.get_submitted_slip_for_month',
        args: {
            employee: frm.doc.employee,
            month_name: row.month
        },
        callback(r) {
            const slip_name = r && r.message;

            if (slip_name) {
                // Revert amount back to saved value
                if (action === 'edit') {
                    const saved_row = frm.doc.__saved_schedule_amounts && frm.doc.__saved_schedule_amounts[cdn];
                    if (saved_row !== undefined) {
                        frappe.model.set_value(cdt, cdn, 'deduction_amount', saved_row);
                        frm.refresh_field('schedule');
                    }
                }

                frappe.msgprint({
                    title: __('Action Not Allowed'),
                    indicator: 'red',
                    message: __(
                        `Salary Slip <b>${slip_name}</b> for <b>${row.month}</b> is already submitted.<br><br>` +
                        `You cannot ${action === 'defer' ? 'defer' : 'edit the amount of'} this installment.<br><br>` +
                        `Please <b>cancel Salary Slip ${slip_name}</b> first, then try again.`
                    )
                });

                if (action === 'defer') {
                    _reverting_deferred = true;
                    frappe.model.set_value(cdt, cdn, 'is_deferred', 0);
                    _reverting_deferred = false;
                } else {
                    frm.refresh_field('schedule');
                }

            } else {
                // ✅ No salary slip found — allow action to proceed
                if (action === 'defer') {
                    apply_deferral(frm, cdt, cdn, emi);
                }
                // ← NEW: For edit — call on_success callback if provided
                if (action === 'edit' && on_success) {
                    on_success();
                }
            }

            // ✅ ALWAYS reset flag
            _checking_salary_slip = false;
        }
    });
}

// ================================================================== //
//  Deferral Helpers                                                  //
// ================================================================== //

/**
 * Undoes a previously applied deferral:
 *   - Subtracts the EMI from the target month that received it
 *   - Restores the original EMI to this row
 *   - Clears the deferred_to field
 */
function undo_deferral(frm, cdt, cdn, emi) {
    const row = locals[cdt][cdn];

    if (row.deferred_to) {
        const target_row = frm.doc.schedule.find(r => r.month === row.deferred_to);

        // ✅ FIX: Use exact amount that was deferred
        const deferred_amt = (frm.doc.__deferred_amounts && frm.doc.__deferred_amounts[cdn] !== undefined)
            ? frm.doc.__deferred_amounts[cdn]
            : emi;

        if (target_row) {
            // ✅ FIX: Read LIVE value from locals, not from frm.doc.schedule
            const live_target = locals['Employee Loan Advance Schedule'][target_row.name];
            const current_target_amt = live_target ? live_target.deduction_amount : target_row.deduction_amount;

            const restored_target_amt = Math.round((current_target_amt - deferred_amt) * 100) / 100;

            // ✅ Mark as auto-adjusted so deduction_amount event doesn't chain-react
            _auto_adjusted_rows.add(target_row.name);

            frappe.model.set_value(
                'Employee Loan Advance Schedule',
                target_row.name,
                'deduction_amount',
                restored_target_amt
            );

            // ✅ Update snapshot for target row
            if (frm.doc.__saved_schedule_amounts) {
                frm.doc.__saved_schedule_amounts[target_row.name] = restored_target_amt;
            }
        }

        // ✅ Restore deferred row back to what it was
        frappe.model.set_value(cdt, cdn, 'deduction_amount', deferred_amt);

        // ✅ Update snapshot for this row too
        if (frm.doc.__saved_schedule_amounts) {
            frm.doc.__saved_schedule_amounts[cdn] = deferred_amt;
        }

        // Cleanup
        if (frm.doc.__deferred_amounts) {
            delete frm.doc.__deferred_amounts[cdn];
        }
    }

    frappe.model.set_value(cdt, cdn, 'deferred_to', '');
    frappe.model.set_value(cdt, cdn, 'is_deducted', 0);
    frm.refresh_field('schedule');
}

/**
 * Shows a dialog for the user to pick a target month, then:
 *   - Sets deduction_amount = 0 on the current row
 *   - Adds the EMI on top of the target month's existing amount
 */
function apply_deferral(frm, cdt, cdn, emi) {
    const row = locals[cdt][cdn];
    const actual_emi = row.deduction_amount;

    const MONTHS = ['January','February','March','April','May','June',
                    'July','August','September','October','November','December'];
    const YEARS  = ['2023','2024','2025','2026','2027'];

    // Pre-select current month/year as default
    const now = new Date();
    let selected_year  = String(now.getFullYear());
    let selected_month = MONTHS[now.getMonth()];

    const d = new frappe.ui.Dialog({
        title: __('Select Defer Month'),
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'picker_html',
                options: `
                <div id="defer-picker" style="padding:4px 0 8px">

                  <div style="margin-bottom:14px">
                    <label style="font-size:12px;color:#888;display:block;margin-bottom:6px">
                      Year <span style="color:red">*</span>
                    </label>
                    <div style="display:flex;gap:8px;flex-wrap:wrap" id="year-btns">
                      ${YEARS.map(y => `
                        <button
                          data-year="${y}"
                          class="defer-year-btn"
                          style="
                            padding:6px 16px;border-radius:4px;
                            border:1px solid #d1d8dd;
                            background:${y === selected_year ? '#171717' : '#fff'};
                            color:${y === selected_year ? '#fff' : '#333'};
                            cursor:pointer;font-size:13px;font-weight:500;
                          "
                        >${y}</button>
                      `).join('')}
                    </div>
                  </div>

                  <div>
                    <label style="font-size:12px;color:#888;display:block;margin-bottom:6px">
                      Month <span style="color:red">*</span>
                    </label>
                    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px" id="month-btns">
                      ${MONTHS.map(m => `
                        <button
                          data-month="${m}"
                          class="defer-month-btn"
                          style="
                            padding:6px 4px;border-radius:4px;
                            border:1px solid #d1d8dd;
                            background:${m === selected_month ? '#171717' : '#fff'};
                            color:${m === selected_month ? '#fff' : '#333'};
                            cursor:pointer;font-size:12px;
                          "
                        >${m.slice(0,3)}</button>
                      `).join('')}
                    </div>
                  </div>

                </div>`
            }
        ],
        primary_action_label: __('Confirm'),
        primary_action() {
            const target_month = `${selected_month} ${selected_year}`;

            d.hide();

            if (!frm.doc.__deferred_amounts) frm.doc.__deferred_amounts = {};
            frm.doc.__deferred_amounts[cdn] = actual_emi;

            // Mark current row as deferred with 0 amount
            frappe.model.set_value(cdt, cdn, 'deferred_to', target_month);
            frappe.model.set_value(cdt, cdn, 'deduction_amount', 0);

            if (frm.doc.__saved_schedule_amounts) {
                frm.doc.__saved_schedule_amounts[cdn] = 0;
            }

            // Check if target month already exists in schedule
            const existing_row = frm.doc.schedule.find(r => r.month === target_month);

            if (existing_row) {
                // Add to existing row's amount
                const new_amt = Math.round((existing_row.deduction_amount + actual_emi) * 100) / 100;
                _auto_adjusted_rows.add(existing_row.name);
                frappe.model.set_value(
                    'Employee Loan Advance Schedule',
                    existing_row.name,
                    'deduction_amount',
                    new_amt
                );
                if (frm.doc.__saved_schedule_amounts) {
                    frm.doc.__saved_schedule_amounts[existing_row.name] = new_amt;
                }
            } else {
                // Add a NEW row for the selected month with same EMI amount
                const new_row = frm.add_child('schedule');
                new_row.month           = target_month;
                new_row.deduction_amount = actual_emi;
                new_row.is_deducted     = 0;
                new_row.is_deferred     = 0;
                new_row.deferred_to     = '';

                if (frm.doc.__saved_schedule_amounts) {
                    frm.doc.__saved_schedule_amounts[new_row.name] = actual_emi;
                }
            }

            frm.refresh_field('schedule');

            frappe.show_alert({
                message: __(`Deferred ₹${actual_emi} to ${target_month}`),
                indicator: 'green'
            }, 5);
        }
    });

    d.show();

    // Wire up button clicks AFTER dialog is in the DOM
    setTimeout(() => {
        d.$wrapper.find('.defer-year-btn').on('click', function () {
            selected_year = $(this).data('year');
            d.$wrapper.find('.defer-year-btn').each(function () {
                const active = $(this).data('year') === selected_year;
                $(this).css({
                    background: active ? '#171717' : '#fff',
                    color:      active ? '#fff'    : '#333'
                });
            });
        });

        d.$wrapper.find('.defer-month-btn').on('click', function () {
            selected_month = $(this).data('month');
            d.$wrapper.find('.defer-month-btn').each(function () {
                const active = $(this).data('month') === selected_month;
                $(this).css({
                    background: active ? '#171717' : '#fff',
                    color:      active ? '#fff'    : '#333'
                });
            });
        });
    }, 100);
}
// ================================================================== //
//  Auto Adjust Next Month — NEW                                      //
// ================================================================== //

/**
 * When user manually changes deduction_amount of a row,
 * the difference is automatically added to the next pending month.
 *
 * Example:
 *   January: 6666.66 → 2000  →  difference = 4666.66  →  February += 4666.66
 *   January: 2000 → 3000     →  difference = -1000    →  February -= 1000
 *   Last row changed          →  shows warning, no next month available
 */
function auto_adjust_next_month(frm, cdt, cdn, original_amount) {
    const row = locals[cdt][cdn];

    if (original_amount === null || original_amount === undefined) return;
    if (_auto_adjusting) return;  // ← NEW: stop chain reaction

    const new_amount = row.deduction_amount;
    const difference = Math.round((original_amount - new_amount) * 100) / 100;

    if (difference === 0) return;

    // Find the next pending (not deducted) row after current row
    const current_idx = frm.doc.schedule.findIndex(r => r.name === cdn);
    const next_row = frm.doc.schedule.find(
        (r, idx) => idx > current_idx && !r.is_deducted
    );

    if (!next_row) {
        frappe.msgprint({
            title: __('No Next Month Available'),
            indicator: 'orange',
            message: __(
                `Could not find a next pending installment to adjust the difference of ₹${Math.abs(difference)}.<br><br>` +
                `Please adjust the remaining months manually to ensure total matches loan amount.`
            )
        });
        return;
    }

    const adjusted_amount = Math.round((next_row.deduction_amount + difference) * 100) / 100;

    _auto_adjusted_rows.add(next_row.name);  // ← mark next row before changing it
    frappe.model.set_value(
        'Employee Loan Advance Schedule',
        next_row.name,
        'deduction_amount',
        adjusted_amount
    );  // ← NEW: reset flag after

    frm.refresh_field('schedule');

    // Update snapshot so next edit on this row captures correct original
    if (frm.doc.__saved_schedule_amounts) {
        frm.doc.__saved_schedule_amounts[cdn] = row.deduction_amount;
        frm.doc.__saved_schedule_amounts[next_row.name] = adjusted_amount;
    }

    frappe.show_alert({
        message: __(`₹${Math.abs(difference)} ${difference > 0 ? 'added to' : 'subtracted from'} ${next_row.month} (now ₹${adjusted_amount})`),
        indicator: 'green'
    }, 5);
}

// ================================================================== //
//  Helper Functions                                                  //
// ================================================================== //

/**
 * Locks rows in the schedule grid where is_deducted = 1.
 * All other rows remain fully editable.
 */
function lock_protected_rows(frm) {
    if (!frm.doc.schedule) return;
    frm.doc.schedule.forEach(row => {
        if (row.is_deducted) {
            const grid_row = frm.fields_dict.schedule.grid.get_row(row.name);
            if (grid_row) grid_row.toggle_editable(false);
        }
    });
    frm.refresh_field('schedule');
}

/**
 * Validates preconditions and generates the repayment schedule.
 */
function trigger_generate(frm) {
    if (frm.doc.type !== 'Loan-I' && frm.doc.type !== 'Loan-II' && frm.doc.type !== 'Loan') return;
    if (!frm.doc.amount || !frm.doc.tenure_months || !frm.doc.start_month || !frm.doc.start_year || !frm.doc.installment_gap) return;

    const has_deduction = frm.doc.schedule && frm.doc.schedule.some(row => row.is_deducted);
    if (has_deduction) {
        frappe.msgprint({
            title: __('Cannot Regenerate Schedule'),
            indicator: 'orange',
            message: __('Some installments have already been deducted via Salary Slip. The schedule cannot be regenerated.')
        });
        return;
    }
    generate_schedule(frm);
}

/**
 * Builds the repayment schedule rows.
 * Base EMI is floored; last EMI absorbs rounding difference.
 *
 * ✅ GAP LOGIC:
 *   Monthly     = step 1 → Jan, Feb, Mar ...
 *   2 Month Gap = step 3 → Jan, Apr, Jul ...
 *                          (Jan kata, Feb+Mar gap, Apr kata)
 *   3 Month Gap = step 4 → Jan, May, Sep ...
 *                          (Jan kata, Feb+Mar+Apr gap, May kata)
 */
function generate_schedule(frm) {
    const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

    const GAP_MAP = { 'Monthly': 1, '2 Month Gap': 3, '3 Month Gap': 4 };

    const gap = GAP_MAP[frm.doc.installment_gap] || 1;

    const tenure = parseInt(frm.doc.tenure_months);
    const start_idx = MONTHS.indexOf(frm.doc.start_month);
    const start_year = parseInt(frm.doc.start_year);
    const total_amt = frm.doc.amount;

    const base_emi = Math.floor((total_amt / tenure) * 100) / 100;
    const last_emi = Math.round((total_amt - base_emi * (tenure - 1)) * 100) / 100;

    frm.set_value('monthly_deduction', base_emi);
    frm.clear_table('schedule');

    for (let i = 0; i < tenure; i++) {
        const d = new Date(start_year, start_idx + (i * gap), 1);
        const month_name = MONTHS[d.getMonth()] + ' ' + d.getFullYear();
        const emi = (i === tenure - 1) ? last_emi : base_emi;

        const row = frm.add_child('schedule');
        row.month = month_name;
        row.deduction_amount = emi;
        row.is_deducted = 0;
        row.is_deferred = 0;
        row.deferred_to = '';
    }
    frm.refresh_field('schedule');
}