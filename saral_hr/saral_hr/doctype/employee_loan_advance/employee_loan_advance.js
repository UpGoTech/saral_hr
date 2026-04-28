// ============================================================
//  Employee Loan Advance — Client Script
// ============================================================

let _reverting_deferred   = false;
let _salary_slip_msg_lock = false;
let _manual_changes_made  = false;
let _reverting_amount     = false;  // ✅ Blocks handler re-entry during field revert

const _auto_adjusted_rows = new Set();

// ================================================================== //
//  Main Form Events                                                   //
// ================================================================== //

frappe.ui.form.on('Employee Loan Advance', {
    refresh(frm) {
        lock_protected_rows(frm);

        frm.doc.__saved_schedule_amounts = {};
        (frm.doc.schedule || []).forEach(row => {
            frm.doc.__saved_schedule_amounts[row.name] = row.deduction_amount;
        });

        if (frm.doc.type === 'Loan') {
            const $grid = $(frm.fields_dict['schedule'].grid.wrapper);
            $grid.find('.btn-add-next-month').remove();
            const $add_row_btn = $grid.find('.grid-add-row');
            const $btn = $(`
                <button class="btn btn-xs btn-default btn-add-next-month"
                    style="margin-left:10px;">
                    + Add Next Month
                </button>
            `);
            $btn.on('click', function(e) {
                e.stopPropagation();
                add_extra_month(frm);
            });
            $add_row_btn.after($btn);

            $grid.find('.grid-body').off('keydown.preventEnter').on('keydown.preventEnter', function(e) {
                if (e.key === "Enter") {
                    e.preventDefault();
                    e.stopPropagation();
                    if ($(e.target).is('input, textarea')) {
                        $(e.target).blur();
                    }
                }
            });
        } else {
            $(frm.fields_dict['schedule'].grid.wrapper)
                .find('.btn-add-next-month').remove();
        }
    },

    amount:          frm => trigger_generate(frm),
    tenure_months:   frm => trigger_generate(frm),
    date:            frm => trigger_generate(frm),
    start_month:     frm => trigger_generate(frm),
    start_year:      frm => trigger_generate(frm),
    installment_gap: frm => trigger_generate(frm),

    type(frm) {
        if (frm.doc.type === 'Loan') {
            const has_rows = frm.doc.schedule && frm.doc.schedule.some(r => r.month && r.month.trim() !== '');
            if (!has_rows) trigger_generate(frm);
        } else {
            frm.clear_table('schedule');
            frm.refresh_field('schedule');
        }
        frm.trigger('refresh');
    }
});

// ================================================================== //
//  Message Helper                                                     //
//  Uses frappe.ui.Dialog (NOT frappe.msgprint).                       //
//  msgprint shares a global dialog — any Frappe-internal set_value   //
//  call can close/replace it instantly. A new Dialog instance is     //
//  fully isolated and stays open until the user clicks OK.           //
// ================================================================== //

function show_salary_slip_message(title, month) {
    if (_salary_slip_msg_lock) return;   // already showing one — do nothing
    _salary_slip_msg_lock = true;

    const dlg = new frappe.ui.Dialog({
        title: title,
        fields: [{
            fieldtype: 'HTML',
            fieldname: 'body',
            options: `
                <div style="padding:8px 2px 10px; font-size:14px; line-height:1.75;">
                    <p style="margin:0;">
                        The Salary Slip for <b>${month}</b> has already been
                        submitted and deducted.
                    </p>
                    <p style="margin:12px 0 0;">
                        Please <b>cancel the Salary Slip</b> for <b>${month}</b>
                        first, then try again.
                    </p>
                </div>`
        }],
        primary_action_label: 'OK',
        primary_action() { dlg.hide(); }
    });

    dlg.show();

    // Reset lock only when user explicitly closes the dialog
    dlg.onhide = () => { _salary_slip_msg_lock = false; };
}

// ================================================================== //
//  Child Table Events                                                 //
// ================================================================== //

frappe.ui.form.on('Employee Loan Advance Schedule', {

    deduction_amount(frm, cdt, cdn) {

        // ✅ KEY FIX: If WE are currently reverting this field, exit immediately.
        // Without this, set_value() fires this handler again → opens a second
        // dialog that closes the first one, making the message flash and disappear.
        if (_reverting_amount) return;

        const row = locals[cdt][cdn];

        if (!row.month || row.month.trim() === '') return;

        // Skip programmatic adjustments (deferral logic)
        if (_auto_adjusted_rows.has(cdn)) {
            _auto_adjusted_rows.delete(cdn);
            return;
        }

        const original_amt = (frm.doc.__saved_schedule_amounts &&
                              frm.doc.__saved_schedule_amounts[cdn] !== undefined)
            ? frm.doc.__saved_schedule_amounts[cdn]
            : null;

        if (row.is_deducted) {
            // Set flag ON → revert → set flag OFF
            // Any re-trigger of this handler during set_value() exits at the top guard
            _reverting_amount = true;
            if (original_amt !== null) {
                frappe.model.set_value(cdt, cdn, 'deduction_amount', original_amt);
            }
            _reverting_amount = false;

            // Now safe to show message — no more re-triggers possible
            show_salary_slip_message('Edit Not Allowed', row.month);
            return;
        }

        if (original_amt !== null) {
            frm.doc.__saved_schedule_amounts[cdn] = row.deduction_amount;
        }
    },

    is_deferred(frm, cdt, cdn) {
        if (_reverting_deferred) return;

        const row = locals[cdt][cdn];

        if (row.is_deducted) {
            _reverting_deferred = true;
            frappe.model.set_value(cdt, cdn, 'is_deferred', 0);
            _reverting_deferred = false;
            show_salary_slip_message('Deferral Not Allowed', row.month);
            return;
        }

        if (row.is_deferred) {
            check_salary_slip_for_month(frm, row, 'defer', cdt, cdn, row.deduction_amount);
        } else {
            undo_deferral(frm, cdt, cdn, row.deduction_amount);
        }
    }
});

$(document).on('keydown', function(e) {
    if (e.key === "Enter" && $(e.target).closest('.grid-body').length) {
        e.stopPropagation();
    }
});

// ================================================================== //
//  Salary Slip Check — used for deferral                             //
// ================================================================== //

let _checking_salary_slip = false;

function check_salary_slip_for_month(frm, row, action, cdt, cdn, emi, on_success) {
    if (_checking_salary_slip) return;
    _checking_salary_slip = true;

    frappe.call({
        method: 'saral_hr.saral_hr.doctype.employee_loan_advance.employee_loan_advance.get_submitted_slip_for_month',
        args: {
            employee:   frm.doc.employee,
            month_name: row.month
        },
        callback(r) {
            const slip_name = r && r.message;

            if (slip_name) {
                frappe.msgprint({
                    title: 'Action Not Allowed',
                    indicator: 'red',
                    message: `Salary Slip <b>${slip_name}</b> for <b>${row.month}</b> is already submitted.`
                           + `<br><br>You cannot defer this installment.`
                           + `<br><br>Please <b>cancel Salary Slip ${slip_name}</b> first, then try again.`
                });

                if (action === 'defer') {
                    _reverting_deferred = true;
                    frappe.model.set_value(cdt, cdn, 'is_deferred', 0);
                    _reverting_deferred = false;
                }
            } else {
                if (action === 'defer') apply_deferral(frm, cdt, cdn, emi);
                if (action === 'edit' && on_success) on_success();
            }

            _checking_salary_slip = false;
        }
    });
}

// ================================================================== //
//  Deferral Helpers                                                   //
// ================================================================== //

function undo_deferral(frm, cdt, cdn, emi) {
    const row = locals[cdt][cdn];

    if (row.deferred_to) {
        const target_row = frm.doc.schedule.find(r => r.month === row.deferred_to);

        const deferred_amt = (frm.doc.__deferred_amounts && frm.doc.__deferred_amounts[cdn] !== undefined)
            ? frm.doc.__deferred_amounts[cdn]
            : emi;

        if (target_row) {
            const live_target        = locals['Employee Loan Advance Schedule'][target_row.name];
            const current_target_amt  = live_target ? live_target.deduction_amount : target_row.deduction_amount;
            const restored_target_amt = Math.round((current_target_amt - deferred_amt) * 100) / 100;

            _auto_adjusted_rows.add(target_row.name);
            frappe.model.set_value(
                'Employee Loan Advance Schedule',
                target_row.name,
                'deduction_amount',
                restored_target_amt
            );

            if (frm.doc.__saved_schedule_amounts) {
                frm.doc.__saved_schedule_amounts[target_row.name] = restored_target_amt;
            }
        }

        frappe.model.set_value(cdt, cdn, 'deduction_amount', deferred_amt);

        if (frm.doc.__saved_schedule_amounts) {
            frm.doc.__saved_schedule_amounts[cdn] = deferred_amt;
        }

        if (frm.doc.__deferred_amounts) {
            delete frm.doc.__deferred_amounts[cdn];
        }
    }

    frappe.model.set_value(cdt, cdn, 'deferred_to', '');
    frappe.model.set_value(cdt, cdn, 'is_deducted', 0);
    frm.refresh_field('schedule');
}

function apply_deferral(frm, cdt, cdn, emi) {
    const row        = locals[cdt][cdn];
    const actual_emi = row.deduction_amount;

    const MONTHS = ['January','February','March','April','May','June',
                    'July','August','September','October','November','December'];
    const YEARS  = ['2023','2024','2025','2026','2027'];

    const now          = new Date();
    let selected_year  = String(now.getFullYear());
    let selected_month = MONTHS[now.getMonth()];

    const d = new frappe.ui.Dialog({
        title: __('Select Defer Month'),
        fields: [{
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
                        <button data-year="${y}" class="defer-year-btn"
                          style="padding:6px 16px;border-radius:4px;border:1px solid #d1d8dd;
                            background:${y === selected_year ? '#171717' : '#fff'};
                            color:${y === selected_year ? '#fff' : '#333'};
                            cursor:pointer;font-size:13px;font-weight:500;">
                          ${y}
                        </button>`).join('')}
                    </div>
                  </div>
                  <div>
                    <label style="font-size:12px;color:#888;display:block;margin-bottom:6px">
                      Month <span style="color:red">*</span>
                    </label>
                    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px" id="month-btns">
                      ${MONTHS.map(m => `
                        <button data-month="${m}" class="defer-month-btn"
                          style="padding:6px 4px;border-radius:4px;border:1px solid #d1d8dd;
                            background:${m === selected_month ? '#171717' : '#fff'};
                            color:${m === selected_month ? '#fff' : '#333'};
                            cursor:pointer;font-size:12px;">
                          ${m.slice(0,3)}
                        </button>`).join('')}
                    </div>
                  </div>
                </div>`
        }],
        primary_action_label: __('Confirm'),
        primary_action() {
            const target_month = `${selected_month} ${selected_year}`;
            d.hide();

            if (!frm.doc.__deferred_amounts) frm.doc.__deferred_amounts = {};
            frm.doc.__deferred_amounts[cdn] = actual_emi;

            frappe.model.set_value(cdt, cdn, 'deferred_to', target_month);
            frappe.model.set_value(cdt, cdn, 'deduction_amount', 0);

            if (frm.doc.__saved_schedule_amounts) {
                frm.doc.__saved_schedule_amounts[cdn] = 0;
            }

            const existing_row = frm.doc.schedule.find(r => r.month === target_month);

            if (existing_row) {
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
                const new_row            = frm.add_child('schedule');
                new_row.month            = target_month;
                new_row.deduction_amount = actual_emi;
                new_row.is_deducted      = 0;
                new_row.is_deferred      = 0;
                new_row.deferred_to      = '';
                if (frm.doc.__saved_schedule_amounts) {
                    frm.doc.__saved_schedule_amounts[new_row.name] = actual_emi;
                }
            }

            frm.refresh_field('schedule');
            frappe.show_alert({ message: __(`Deferred ₹${actual_emi} to ${target_month}`), indicator: 'green' }, 5);
        }
    });

    d.show();

    setTimeout(() => {
        d.$wrapper.find('.defer-year-btn').on('click', function () {
            selected_year = $(this).data('year');
            d.$wrapper.find('.defer-year-btn').each(function () {
                const active = $(this).data('year') === selected_year;
                $(this).css({ background: active ? '#171717' : '#fff', color: active ? '#fff' : '#333' });
            });
        });
        d.$wrapper.find('.defer-month-btn').on('click', function () {
            selected_month = $(this).data('month');
            d.$wrapper.find('.defer-month-btn').each(function () {
                const active = $(this).data('month') === selected_month;
                $(this).css({ background: active ? '#171717' : '#fff', color: active ? '#fff' : '#333' });
            });
        });
    }, 100);
}

// ================================================================== //
//  Helper Functions                                                   //
// ================================================================== //

function lock_protected_rows(frm) {
    if (!frm.doc.schedule) return;
    frm.refresh_field('schedule');
}

function trigger_generate(frm) {
    if (frm.doc.type !== 'Loan') return;
    if (!frm.doc.amount || !frm.doc.tenure_months || !frm.doc.start_month || !frm.doc.start_year || !frm.doc.installment_gap) return;
    if (_manual_changes_made) return;

    const has_rows = frm.doc.schedule && frm.doc.schedule.length > 0;
    if (has_rows) return;

    generate_schedule(frm);
}

function generate_schedule(frm) {
    const MONTHS  = ['January','February','March','April','May','June',
                     'July','August','September','October','November','December'];
    const GAP_MAP = { 'Monthly': 1, '2 Month Gap': 3, '3 Month Gap': 4 };
    const gap      = GAP_MAP[frm.doc.installment_gap] || 1;

    const tenure     = parseInt(frm.doc.tenure_months);
    const start_idx  = MONTHS.indexOf(frm.doc.start_month);
    const start_year = parseInt(frm.doc.start_year);
    const total_amt  = frm.doc.amount;

    const base_emi = Math.floor((total_amt / tenure) * 100) / 100;
    const last_emi = Math.round((total_amt - base_emi * (tenure - 1)) * 100) / 100;

    frm.set_value('monthly_deduction', base_emi);
    frm.clear_table('schedule');

    for (let i = 0; i < tenure; i++) {
        const d          = new Date(start_year, start_idx + (i * gap), 1);
        const month_name = MONTHS[d.getMonth()] + ' ' + d.getFullYear();
        const emi        = (i === tenure - 1) ? last_emi : base_emi;

        const row            = frm.add_child('schedule');
        row.month            = month_name;
        row.deduction_amount = emi;
        row.is_deducted      = 0;
        row.is_deferred      = 0;
        row.deferred_to      = '';
    }
    frm.refresh_field('schedule');
}

// ================================================================== //
//  Add Next Month                                                    //
// ================================================================== //

function add_extra_month(frm) {
    const schedule = frm.doc.schedule || [];

    if (schedule.length === 0) {
        frappe.msgprint(__('No existing schedule found.'));
        return;
    }

    const last_row       = schedule[schedule.length - 1];
    const last_month_str = last_row.month;

    if (!last_month_str) {
        frappe.msgprint(__('Invalid last month found.'));
        return;
    }

    const parts           = last_month_str.split(' ');
    const last_month_name = parts[0];
    const last_year       = parseInt(parts[1]);

    const MONTHS = ['January','February','March','April','May','June',
                    'July','August','September','October','November','December'];

    let last_month_index = MONTHS.indexOf(last_month_name);
    let next_month_index = last_month_index + 1;
    let next_year        = last_year;

    if (next_month_index >= 12) {
        next_month_index = 0;
        next_year++;
    }

    const next_month_str = `${MONTHS[next_month_index]} ${next_year}`;

    const new_row            = frm.add_child('schedule');
    new_row.month            = next_month_str;
    new_row.deduction_amount = 0;
    new_row.is_deducted      = 0;
    new_row.is_deferred      = 0;
    new_row.deferred_to      = '';

    if (!frm.doc.__saved_schedule_amounts) frm.doc.__saved_schedule_amounts = {};
    frm.doc.__saved_schedule_amounts[new_row.name] = 0;

    frm.refresh_field('schedule');
    frappe.show_alert({ message: __(`Added ${next_month_str}`), indicator: 'green' }, 3);
}