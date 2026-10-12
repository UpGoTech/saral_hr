// ─── List View Buttons ────────────────────────────────────────────────────────

frappe.listview_settings['Salary Slip'] = {
    onload(listview) {
        listview.page.add_inner_button(__('Bulk Generate Salary Slips'), () => show_bulk_salary_slip_dialog());
        listview.page.add_inner_button(__('Bulk Print Salary Slips'),    () => show_bulk_print_dialog());
        listview.page.add_inner_button(__('Draft to Submit'),            () => show_draft_to_submit_dialog());
    }
};

// ─── Constants ────────────────────────────────────────────────────────────────

const MONTHS = ['January','February','March','April','May','June',
                'July','August','September','October','November','December'];

function get_current_month() { return MONTHS[new Date().getMonth()]; }
function get_current_year()  { return new Date().getFullYear(); }

function clamp_year(value) {
    return saral_hr.period_picker.clamp_period_year(value);
}

function year_field() {
    return saral_hr.period_picker.year_select_field();
}

// ─── Shared icon helpers ──────────────────────────────────────────────────────

const TICK  = `<span style="display:inline-flex;align-items:center;justify-content:center;
    width:18px;height:18px;border-radius:50%;
    background:#d3f9d8;color:#2f9e44;font-size:11px;font-weight:700;flex-shrink:0;">&#10003;</span>`;
const CROSS = `<span style="display:inline-flex;align-items:center;justify-content:center;
    width:18px;height:18px;border-radius:50%;
    background:#ffe3e3;color:#e03131;font-size:11px;font-weight:700;flex-shrink:0;">&#10007;</span>`;
const DONE  = `<span style="display:inline-flex;align-items:center;justify-content:center;
    width:18px;height:18px;border-radius:50%;
    background:#dbe4ff;color:#3b5bdb;font-size:10px;font-weight:700;flex-shrink:0;">&#8635;</span>`;

// ─── Shared utilities ─────────────────────────────────────────────────────────

function _get_dialog_values(dialog, fields) {
    return fields.reduce((acc, f) => { acc[f] = dialog.get_value(f); return acc; }, {});
}

function get_checked_items($wrapper, cls) {
    const items = [];
    $wrapper.find(`.${cls}:checked`).each(function() {
        items.push({ id: $(this).data('id'), name: $(this).data('name') });
    });
    return items;
}

function _loading_html(msg) {
    return `<div class="text-muted" style="padding:24px 0;text-align:center;font-size:12px;">
        ${frappe.utils.icon('loading', 'xs')}&nbsp;&nbsp;${frappe.utils.escape_html(msg)}
    </div>`;
}

function _summary_bar(stats) {
    const items = stats.map(([label, value]) =>
        `<span style="font-size:12px;color:var(--text-muted);">${label}:&nbsp;<strong style="color:var(--text-color);">${value}</strong></span>`
    ).join(`<span style="color:var(--border-color);padding:0 8px;">|</span>`);
    return `<div style="display:flex;align-items:center;flex-wrap:wrap;gap:8px;
        padding:8px 0 10px;margin-bottom:10px;border-bottom:1px solid var(--border-color);">
        ${items}
    </div>`;
}

function _slip_status_badge(s) {
    const map = {
        'Submitted': ['#d3f9d8', '#2f9e44'],
        'Draft':     ['#fff3cd', '#856404'],
        'No Slip':   ['#ffe3e3', '#e03131'],
        'Cancelled': ['#f0f0f0', '#6c757d'],
    };
    const [bg, c] = map[s] || ['#f0f0f0', '#495057'];
    return `<span style="display:inline-block;padding:2px 9px;border-radius:20px;
        font-size:10px;font-weight:700;text-transform:uppercase;
        background:${bg};color:${c};">${frappe.utils.escape_html(s || '—')}</span>`;
}

// ─── Progress helpers ─────────────────────────────────────────────────────────

function _show_progress(title, done, total, msg) {
    frappe.show_progress(title, done, total, msg || '');
}
function _hide_progress() {
    frappe.hide_progress();
}

// ─── Unified searchable table ─────────────────────────────────────────────────

function render_unified_table($wrap, eligible, ineligible, already_generated,
                               print_rows, cls, count_id, search_id, mode, show_vpa) {

    // ── Normalise into flat list ───────────────────────────────────────────
    let all_rows = [];

    if (mode === 'generate') {
        (eligible || []).forEach(e => all_rows.push({
            cb_id:       e.id,
            cb_name:     e.name,
            disp_name:   e.name,
            disp_id:     e.id,
            bucket:      'eligible',
            ok_ss:       true, ok_vpa: true, ok_att: true,
            reasons:     [],
            slip_name:   '', slip_status: ''
        }));
        (already_generated || []).forEach(e => all_rows.push({
            cb_id:       '',
            cb_name:     e.name,
            disp_name:   e.name,
            disp_id:     e.id,
            bucket:      'generated',
            ok_ss:       true, ok_vpa: true, ok_att: true,
            reasons:     [e.slip_info || 'Salary slip already exists for this period'],
            slip_name:   e.slip_name || '',
            slip_status: e.slip_status || 'Submitted'
        }));
        (ineligible || []).forEach(s => {
            const rl = (s.reasons || []).map(x => x.toLowerCase());
            all_rows.push({
                cb_id:       '',
                cb_name:     s.name,
                disp_name:   s.name,
                disp_id:     s.id,
                bucket:      'ineligible',
                ok_ss:      !rl.some(x => x.includes('salary structure')),
                ok_vpa:     !rl.some(x => x.includes('variable pay')),
                ok_att:     !rl.some(x => x.includes('attendance')),
                reasons:     s.reasons || [],
                slip_name:   '', slip_status: ''
            });
        });
    } else {
        (print_rows || []).forEach(p => all_rows.push({
            cb_id:       p.eligible ? (p.slip_name || p.name || '') : '',
            cb_name:     p.employee_name || p.employee || '',
            disp_name:   p.employee_name || p.employee || '',
            disp_id:     p.employee || '',
            bucket:      p.eligible ? 'eligible' : 'ineligible',
            ok_ss:       true, ok_vpa: true, ok_att: true,
            reasons:     p.reasons || [],
            slip_name:   p.slip_name || p.name || '',
            slip_status: p.slip_status || (p.eligible ? 'Submitted' : 'No Slip')
        }));
    }

    const total_elig   = all_rows.filter(r => r.bucket === 'eligible').length;
    const total_gen    = all_rows.filter(r => r.bucket === 'generated').length;
    const total_inelig = all_rows.filter(r => r.bucket === 'ineligible').length;

    // ── Style helpers ─────────────────────────────────────────────────────
    const TH   = `position:sticky;top:0;z-index:2;padding:7px 10px;font-size:10px;font-weight:700;
        text-transform:uppercase;letter-spacing:0.04em;color:var(--text-muted);
        background:var(--subtle-fg,#f3f4f6);border-bottom:2px solid var(--border-color);
        white-space:nowrap;border-right:1px solid var(--border-color);`;
    const TH_L = TH.replace('border-right:1px solid var(--border-color);', '');
    const TD   = `padding:7px 10px;border-bottom:1px solid var(--border-color);
        border-right:1px solid var(--border-color);vertical-align:middle;`;
    const TD_L = TD.replace('border-right:1px solid var(--border-color);', '');

    // ── Column headers ────────────────────────────────────────────────────
    let hdr = '';
    if (mode === 'generate') {
        hdr = `
            <th style="${TH}text-align:center;width:34px;"></th>
            <th style="${TH}">Employee Name</th>
            <th style="${TH}">ID</th>
            <th style="${TH}text-align:center;">Salary Structure</th>
            ${show_vpa ? `<th style="${TH}text-align:center;">Variable Pay</th>` : ''}
            <th style="${TH}text-align:center;">Attendance</th>
            <th style="${TH_L}text-align:center;">Status</th>`;
    } else {
        hdr = `
            <th style="${TH}text-align:center;width:34px;"></th>
            <th style="${TH}">Employee Name</th>
            <th style="${TH}">ID</th>
            <th style="${TH}">Slip Name</th>
            <th style="${TH}text-align:center;">Slip Status</th>
            <th style="${TH_L}text-align:center;">Printable</th>`;
    }

    // ── Row builder ───────────────────────────────────────────────────────
    function build_tbody(rows) {
        if (!rows.length) {
            const cols = mode === 'generate' ? (show_vpa ? 7 : 6) : 6;
            return `<tr><td colspan="${cols}" style="padding:20px;text-align:center;
                color:var(--text-muted);">No employees found.</td></tr>`;
        }
        return rows.map((row, i) => {
            const stripe = i % 2 === 1 ? 'background:var(--subtle-fg,#f9fafb);' : '';
            const tip    = frappe.utils.escape_html((row.reasons || []).join(' | '));

            let cb;
            if (row.bucket === 'eligible') {
                cb = `<input type="checkbox" class="${cls}"
                       data-id="${frappe.utils.escape_html(row.cb_id)}"
                       data-name="${frappe.utils.escape_html(row.cb_name)}"
                       style="cursor:pointer;">`;
            } else {
                cb = `<input type="checkbox" disabled title="${tip}"
                       style="cursor:not-allowed;opacity:0.35;">`;
            }

            if (mode === 'generate') {
                let status_cell;
                if (row.bucket === 'eligible') {
                    status_cell = `<td style="${TD_L}text-align:center;">${TICK}</td>`;
                } else if (row.bucket === 'generated') {
                    const slink = row.slip_name
                        ? `<a href="/app/salary-slip/${encodeURIComponent(row.slip_name)}"
                               target="_blank" style="font-size:10px;color:var(--primary);">
                               ${frappe.utils.escape_html(row.slip_name)}</a>`
                        : _slip_status_badge(row.slip_status || 'Submitted');
                    status_cell = `<td style="${TD_L}text-align:center;white-space:nowrap;" title="${tip}">
                        ${DONE}&nbsp;${slink}</td>`;
                } else {
                    status_cell = `<td style="${TD_L}text-align:center;" title="${tip}">${CROSS}</td>`;
                }
                return `<tr style="${stripe}">
                    <td style="${TD}text-align:center;">${cb}</td>
                    <td style="${TD}font-weight:600;font-size:12px;">${frappe.utils.escape_html(row.disp_name)}</td>
                    <td style="${TD}font-size:11px;color:var(--text-muted);">${frappe.utils.escape_html(row.disp_id)}</td>
                    <td style="${TD}text-align:center;">${row.ok_ss  ? TICK : CROSS}</td>
                    ${show_vpa ? `<td style="${TD}text-align:center;">${row.ok_vpa ? TICK : CROSS}</td>` : ''}
                    <td style="${TD}text-align:center;">${row.ok_att ? TICK : CROSS}</td>
                    ${status_cell}
                </tr>`;
            } else {
                const sname = row.slip_name
                    ? `<a href="/app/salary-slip/${encodeURIComponent(row.slip_name)}" target="_blank"
                           style="font-size:11px;color:var(--primary);">${frappe.utils.escape_html(row.slip_name)}</a>`
                    : `<span style="color:var(--text-muted);font-size:11px;">—</span>`;
                return `<tr style="${stripe}">
                    <td style="${TD}text-align:center;">${cb}</td>
                    <td style="${TD}font-weight:600;font-size:12px;">${frappe.utils.escape_html(row.disp_name)}</td>
                    <td style="${TD}font-size:11px;color:var(--text-muted);">${frappe.utils.escape_html(row.disp_id)}</td>
                    <td style="${TD}">${sname}</td>
                    <td style="${TD}text-align:center;">${_slip_status_badge(row.slip_status)}</td>
                    <td style="${TD_L}text-align:center;" title="${tip}">${row.bucket === 'eligible' ? TICK : CROSS}</td>
                </tr>`;
            }
        }).join('');
    }

    // ── Filter pills ──────────────────────────────────────────────────────
    let pills_html = '';
    if (mode === 'generate') {
        pills_html = `
            <button class="btn btn-xs btn-default _fp_btn" data-f="eligible"
                style="border-radius:20px;padding:2px 12px;">
                ${TICK}&nbsp;Eligible&nbsp;(${total_elig})</button>
            <button class="btn btn-xs btn-default _fp_btn" data-f="generated"
                style="border-radius:20px;padding:2px 12px;">
                ${DONE}&nbsp;Generated&nbsp;(${total_gen})</button>
            <button class="btn btn-xs btn-default _fp_btn" data-f="ineligible"
                style="border-radius:20px;padding:2px 12px;">
                ${CROSS}&nbsp;Not Eligible&nbsp;(${total_inelig})</button>`;
    } else {
        pills_html = `
            <button class="btn btn-xs btn-default _fp_btn" data-f="eligible"
                style="border-radius:20px;padding:2px 12px;">
                ${TICK}&nbsp;Printable&nbsp;(${total_elig})</button>
            <button class="btn btn-xs btn-default _fp_btn" data-f="ineligible"
                style="border-radius:20px;padding:2px 12px;">
                ${CROSS}&nbsp;Not Printable&nbsp;(${total_inelig})</button>`;
    }

    $wrap.html(`
        <div style="margin-bottom:10px;display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
            <input id="${search_id}" type="text" class="form-control"
                placeholder="Search by name or ID…"
                style="flex:1;min-width:160px;max-width:280px;font-size:12px;">
            <div style="display:flex;gap:4px;flex-wrap:wrap;">
                ${pills_html}
            </div>
            <div style="display:flex;gap:6px;align-items:center;margin-left:auto;">
                <button class="btn btn-xs btn-default" id="${search_id}_sel_all">Select All</button>
                <button class="btn btn-xs btn-default" id="${search_id}_desel">Deselect All</button>
                <span id="${count_id}" class="text-muted" style="font-size:12px;white-space:nowrap;">0 selected</span>
            </div>
        </div>
        <div style="border:1px solid var(--border-color);border-radius:var(--border-radius,6px);overflow:hidden;">
            <div style="overflow-x:auto;max-height:340px;overflow-y:auto;">
                <table style="width:100%;border-collapse:collapse;min-width:480px;">
                    <thead><tr>${hdr}</tr></thead>
                    <tbody id="${search_id}_tbody">${build_tbody(all_rows)}</tbody>
                </table>
            </div>
        </div>
        <div style="margin-top:6px;font-size:11px;color:var(--text-muted);display:flex;gap:14px;flex-wrap:wrap;">
            <span>${TICK}&nbsp;= eligible / printable</span>
            ${mode === 'generate' ? `<span>${DONE}&nbsp;= already generated — hover for slip link</span>` : ''}
            <span>${CROSS}&nbsp;= not eligible — hover for reason</span>
        </div>
    `);

    // ── State & interaction ───────────────────────────────────────────────
    let active_f = 'eligible';
    let q        = '';

    function get_visible() {
        return all_rows.filter(row => {
            const q_ok = !q
                || row.disp_name.toLowerCase().includes(q)
                || row.disp_id.toLowerCase().includes(q);
            const f_ok = active_f === 'eligible'   ? row.bucket === 'eligible'
                       : active_f === 'generated'  ? row.bucket === 'generated'
                       : row.bucket === 'ineligible';
            return q_ok && f_ok;
        });
    }

    function redraw() {
        $wrap.find(`#${search_id}_tbody`).html(build_tbody(get_visible()));
        bind();
    }

    function upd() {
        $wrap.find(`#${count_id}`).text($wrap.find(`.${cls}:checked`).length + ' selected');
    }

    function bind() {
        $wrap.find(`.${cls}`).off('change').on('change', upd);
        upd();
    }

    function set_active_pill(f) {
        $wrap.find('._fp_btn').css({ 'font-weight': '400', 'border-color': 'var(--border-color)', 'color': '' });
        $wrap.find(`._fp_btn[data-f="${f}"]`).css({
            'font-weight': '700',
            'border-color': 'var(--primary,#5e64ff)',
            'color': 'var(--primary,#5e64ff)'
        });
        active_f = f;
        redraw();
    }

    $wrap.find('._fp_btn').on('click', function() { set_active_pill($(this).data('f')); });

    set_active_pill('eligible');

    $wrap.find(`#${search_id}`).on('input', function() {
        q = $(this).val().toLowerCase().trim();
        redraw();
    });

    $wrap.find(`#${search_id}_sel_all`).on('click', () => {
        $wrap.find(`.${cls}:not(:disabled)`).prop('checked', true); upd();
    });
    $wrap.find(`#${search_id}_desel`).on('click', () => {
        $wrap.find(`.${cls}`).prop('checked', false); upd();
    });

    bind();
}

// ─── Bulk Generate ────────────────────────────────────────────────────────────

function show_bulk_salary_slip_dialog() {
    const d = new frappe.ui.Dialog({
        title: __('Bulk Generate Salary Slips'),
        size:  'large',
        fields: [
            { fieldname:'company',    fieldtype:'Link',   label:'Company', options:'Company', reqd:1 },
            { fieldname:'cb1',        fieldtype:'Column Break' },
            year_field(),
            { fieldname:'cb2',        fieldtype:'Column Break' },
            { fieldname:'month',      fieldtype:'Select', label:'Month',   options:MONTHS, reqd:1, default:get_current_month() },
            { fieldname:'sb_filters', fieldtype:'Section Break', label:'Optional Filters' },
            { fieldname:'category',   fieldtype:'Link',   label:'Category', options:'Category',
              description:'Leave blank to include all categories.' },
            { fieldname:'cb3',        fieldtype:'Column Break' },
            { fieldname:'division',   fieldtype:'Link',   label:'Division', options:'Division',
              description:'Leave blank to include all divisions.' },
            { fieldname:'sb1',        fieldtype:'Section Break' },
            { fieldname:'fetch_btn',  fieldtype:'Button', label:'Get Employees',
              click: () => fetch_generate_employees(d) },
            { fieldname:'sb2',        fieldtype:'Section Break' },
            { fieldname:'emp_html',   fieldtype:'HTML' }
        ],
        primary_action_label: __('Generate Salary Slips'),
        primary_action: () => generate_bulk_salary_slips(d)
    });
    d.show();
}

function fetch_generate_employees(dialog) {
    let { company, year, month, category, division } =
        _get_dialog_values(dialog, ['company','year','month','category','division']);

    if (!company)        { frappe.msgprint(__('Please select Company'));        return; }
    if (!year || !month) { frappe.msgprint(__('Please select Year and Month')); return; }

    year = clamp_year(year);
    dialog.set_value('year', year);

    const wrapper = dialog.fields_dict.emp_html.$wrapper;
    wrapper.html(_loading_html('Retrieving employee payroll eligibility…'));

    frappe.call({
        method: 'saral_hr.saral_hr.doctype.salary_slip.salary_slip.get_eligible_employees_for_salary_slip',
        args:   { company, year, month, category: category || '', division: division || '' },
        callback(r) {
            if (!r.message) {
                wrapper.html('<div class="text-muted" style="padding:16px 0;text-align:center;">Unable to retrieve employee data.</div>');
                return;
            }

            const {
                eligible          = [],
                skipped           = [],
                already_generated = [],
                total_active,
                total_eligible,
                category_requires_variable_pay
            } = r.message;

            wrapper.html(
                _summary_bar([
                    ['Active', total_active],
                    ['Eligible',          total_eligible],
                    ['Already Generated', already_generated.length],
                    ['Not Eligible',      skipped.length]
                ]) + '<div id="gen_tbl"></div>'
            );

            render_unified_table(
                wrapper.find('#gen_tbl'),
                eligible.map(e => ({ id: e.name, name: e.employee_name || e.name })),
                skipped,
                already_generated,
                [],
                'gen-emp-chk',
                'gen_sel_count',
                'gen_srch',
                'generate',
                !!category_requires_variable_pay
            );
        }
    });
}

function generate_bulk_salary_slips(dialog) {
    const $wrap    = dialog.fields_dict.emp_html.$wrapper;
    const selected = get_checked_items($wrap, 'gen-emp-chk');

    if (!selected.length) {
        frappe.msgprint(__('Please select at least one employee'));
        return;
    }

    frappe.confirm(`Generate salary slips for <b>${selected.length}</b> employee(s)?`, () => {
        dialog.hide();

        const total = selected.length;

        // Defer so dialog fully closes before progress bar renders
        setTimeout(() => {
            _show_progress(__('Generating Salary Slips'), 0, total, 'Starting…');

            function process_next(idx) {
                if (idx >= total) {
                    // ── All done: just hide progress and refresh list ──────
                    _show_progress(__('Generating Salary Slips'), total, total, 'Done!');
                    setTimeout(() => {
                        _hide_progress();
                        if (cur_list) cur_list.refresh();
                    }, 600);
                    return;
                }

                const emp = selected[idx];
                _show_progress(
                    __('Generating Salary Slips'),
                    idx + 1,
                    total,
                    `Generating slip for ${frappe.utils.escape_html(emp.name)} (${idx + 1} / ${total})`
                );

                frappe.call({
                    method: 'saral_hr.saral_hr.doctype.salary_slip.salary_slip.bulk_generate_salary_slips',
                    args: {
                        employees: [{ employee: emp.id, employee_name: emp.name }],
                        year:   clamp_year(dialog.get_value('year')),
                        month:  dialog.get_value('month')
                    },
                    callback(r) { process_next(idx + 1); },
                    error()     { process_next(idx + 1); }
                });
            }

            process_next(0);
        }, 300);
    });
}

// ─── Bulk Print ───────────────────────────────────────────────────────────────

function show_bulk_print_dialog() {
    const d = new frappe.ui.Dialog({
        title: __('Bulk Print Salary Slips'),
        size:  'large',
        fields: [
            { fieldname:'company',    fieldtype:'Link',   label:'Company', options:'Company', reqd:1 },
            { fieldname:'cb1',        fieldtype:'Column Break' },
            year_field(),
            { fieldname:'cb2',        fieldtype:'Column Break' },
            { fieldname:'month',      fieldtype:'Select', label:'Month',   options:MONTHS, reqd:1, default:get_current_month() },
            { fieldname:'sb_filters', fieldtype:'Section Break', label:'Optional Filters' },
            { fieldname:'category',   fieldtype:'Link',   label:'Category', options:'Category',
              description:'Leave blank to include all categories.' },
            { fieldname:'cb3',        fieldtype:'Column Break' },
            { fieldname:'division',   fieldtype:'Link',   label:'Division', options:'Division',
              description:'Leave blank to include all divisions.' },
            { fieldname:'sb1',        fieldtype:'Section Break' },
            { fieldname:'fetch_btn',  fieldtype:'Button', label:'Get Salary Slips',
              click: () => fetch_print_slips(d) },
            { fieldname:'sb2',        fieldtype:'Section Break' },
            { fieldname:'slip_html',  fieldtype:'HTML' }
        ],
        primary_action_label: __('Print Selected Slips'),
        primary_action: () => print_selected_salary_slips(d)
    });
    d.show();
}

function fetch_print_slips(dialog) {
    let { company, year, month, category, division } =
        _get_dialog_values(dialog, ['company','year','month','category','division']);

    if (!company)        { frappe.msgprint(__('Please select Company'));        return; }
    if (!year || !month) { frappe.msgprint(__('Please select Year and Month')); return; }

    year = clamp_year(year);
    dialog.set_value('year', year);

    const wrapper = dialog.fields_dict.slip_html.$wrapper;
    wrapper.html(_loading_html('Retrieving submitted salary slips…'));

    frappe.call({
        method: 'saral_hr.saral_hr.doctype.salary_slip.salary_slip.get_salary_slips_print_summary',
        args:   { company, year, month, category: category || '', division: division || '' },
        callback(r) {
            if (!r.message) {
                wrapper.html('<div class="text-muted" style="padding:16px 0;text-align:center;">Unable to retrieve data.</div>');
                return;
            }

            const { submitted=[], not_printable=[], total_active, total_submitted } = r.message;

            const print_rows = [
                ...submitted.map(s => ({
                    employee:      s.employee,
                    employee_name: s.employee_name || s.employee,
                    name:          s.name,
                    slip_name:     s.name,
                    slip_status:   'Submitted',
                    eligible:      true,
                    reasons:       []
                })),
                ...not_printable.map(s => ({
                    employee:      s.employee,
                    employee_name: s.employee_name || s.employee,
                    name:          s.slip_name || '',
                    slip_name:     s.slip_name || '',
                    slip_status:   s.slip_status || 'No Slip',
                    eligible:      false,
                    reasons:       s.reasons || []
                }))
            ];

            wrapper.html(
                _summary_bar([
                    ['Active', total_active],
                    ['Submitted Slips', total_submitted],
                    ['Cannot Print',    not_printable.length]
                ]) + '<div id="print_tbl"></div>'
            );

            render_unified_table(
                wrapper.find('#print_tbl'),
                [], [],
                [],
                print_rows,
                'print-slip-chk',
                'print_sel_count',
                'print_srch',
                'print',
                false
            );
        }
    });
}

function print_selected_salary_slips(dialog) {
    const $wrap    = dialog.fields_dict.slip_html.$wrapper;
    const selected = get_checked_items($wrap, 'print-slip-chk');

    if (!selected.length) {
        frappe.msgprint(__('Please select at least one salary slip to print'));
        return;
    }

    frappe.confirm(`Print <b>${selected.length}</b> salary slip(s)?`, () => {
        dialog.hide();

        const total = selected.length;

        setTimeout(() => {
            // ── Step 1: show merging progress ─────────────────────────────
            _show_progress(__('Preparing PDF'), 1, total + 1, `Merging ${total} slip(s)…`);

            frappe.call({
                method: 'saral_hr.saral_hr.doctype.salary_slip.salary_slip.bulk_print_salary_slips',
                args:   { salary_slip_names: selected.map(s => s.id) },
                callback(r) {
                    // ── Step 2: finalising progress ───────────────────────
                    _show_progress(__('Preparing PDF'), total, total + 1, 'Finalising PDF…');
                    setTimeout(() => {
                        // ── Step 3: complete ──────────────────────────────
                        _show_progress(__('Preparing PDF'), total + 1, total + 1, 'Done!');
                        setTimeout(() => {
                            _hide_progress();
                            if (r.message && r.message.pdf_url) {
                                const a = document.createElement('a');
                                a.href   = r.message.pdf_url;
                                a.target = '_blank';
                                a.rel    = 'noopener noreferrer';
                                document.body.appendChild(a);
                                a.click();
                                document.body.removeChild(a);
                            }
                        }, 500);
                    }, 600);
                },
                error() {
                    _hide_progress();
                    frappe.msgprint({ title:__('Error'), message:__('Failed to generate PDF.'), indicator:'red' });
                }
            });
        }, 300);
    });
}

// ─── Draft to Submit ──────────────────────────────────────────────────────────

function show_draft_to_submit_dialog() {
    const d = new frappe.ui.Dialog({
        title: __('Submit Draft Salary Slips'),
        fields: [
            { fieldname:'company',      fieldtype:'Link',   label:'Company', options:'Company', reqd:1 },
            { fieldname:'cb1',          fieldtype:'Column Break' },
            year_field(),
            { fieldname:'cb2',          fieldtype:'Column Break' },
            { fieldname:'month',        fieldtype:'Select', label:'Month',   options:MONTHS, reqd:1, default:get_current_month() },
            { fieldname:'sb1',          fieldtype:'Section Break' },
            { fieldname:'fetch_drafts', fieldtype:'Button', label:'Fetch Draft Salary Slips',
              click: () => fetch_draft_salary_slips(d) },
            { fieldname:'sb2',          fieldtype:'Section Break' },
            { fieldname:'drafts_html',  fieldtype:'HTML' }
        ],
        primary_action_label: __('Submit Selected Slips'),
        primary_action: () => submit_selected_salary_slips(d)
    });
    d.show();
}

function fetch_draft_salary_slips(dialog) {
    let { company, year, month } = _get_dialog_values(dialog, ['company','year','month']);
    if (!company)        { frappe.msgprint(__('Please select Company'));        return; }
    if (!year || !month) { frappe.msgprint(__('Please select Year and Month')); return; }
    year = clamp_year(year);
    dialog.set_value('year', year);
    frappe.call({
        method: 'saral_hr.saral_hr.doctype.salary_slip.salary_slip.get_draft_salary_slips',
        args: { company, year, month },
        callback(r) {
            if (r.message && r.message.length) {
                render_card_grid(
                    dialog, 'drafts_html', 'draft-card-chk', 'draft_count', 'draft_srch',
                    r.message.map(s => ({ id: s.name, name: s.employee_name || s.employee }))
                );
            } else {
                dialog.fields_dict.drafts_html.$wrapper.html(
                    '<div class="text-muted" style="padding:20px;text-align:center;">No draft salary slips found.</div>'
                );
            }
        }
    });
}

function submit_selected_salary_slips(dialog) {
    const $wrap    = dialog.fields_dict.drafts_html.$wrapper;
    const selected = get_checked_items($wrap, 'draft-card-chk');
    if (!selected.length) {
        frappe.msgprint(__('Please select at least one salary slip to submit'));
        return;
    }

    frappe.confirm(`Submit <b>${selected.length}</b> salary slip(s)? This cannot be undone.`, () => {
        dialog.hide();

        const total   = selected.length;
        const results = { success: 0, failed: 0, errors: [] };

        setTimeout(() => {
            _show_progress(__('Submitting Salary Slips'), 0, total, 'Starting…');

            function process_next(idx) {
                if (idx >= total) {
                    _show_progress(__('Submitting Salary Slips'), total, total, 'Done!');
                    setTimeout(() => {
                        _hide_progress();
                        if (cur_list) cur_list.refresh();
                    }, 600);
                    return;
                }

                const slip = selected[idx];
                _show_progress(
                    __('Submitting Salary Slips'),
                    idx + 1,
                    total,
                    `Submitting ${frappe.utils.escape_html(slip.name)} (${idx + 1} / ${total})`
                );

                frappe.call({
                    method: 'saral_hr.saral_hr.doctype.salary_slip.salary_slip.bulk_submit_salary_slips',
                    args:   { salary_slip_names: [slip.id] },
                    callback(r) { process_next(idx + 1); },
                    error()     { process_next(idx + 1); }
                });
            }

            process_next(0);
        }, 300);
    });
}

// ─── Card grid (Draft to Submit) ─────────────────────────────────────────────

function build_cards(items, cls) {
    if (!items || !items.length)
        return `<div class="text-muted" style="padding:20px;width:100%;text-align:center;">No employees available.</div>`;
    return items.map(item => `
        <label style="display:flex;flex-direction:column;align-items:flex-start;
            width:calc(33.33% - 8px);min-width:140px;
            border:1px solid var(--border-color,#d1d8dd);border-radius:6px;
            padding:10px 12px;cursor:pointer;background:var(--card-bg,#fff);
            transition:border-color .15s,box-shadow .15s;box-sizing:border-box;gap:4px;"
            onmouseover="this.style.borderColor='var(--primary,#5e64ff)';this.style.boxShadow='0 0 0 2px var(--primary-light,#eef0ff)'"
            onmouseout="this.style.borderColor='var(--border-color,#d1d8dd)';this.style.boxShadow='none'">
            <div style="display:flex;align-items:center;gap:8px;width:100%;">
                <input type="checkbox" class="${cls}"
                    data-id="${frappe.utils.escape_html(item.id)}"
                    data-name="${frappe.utils.escape_html(item.name)}"
                    style="cursor:pointer;margin:0;flex-shrink:0;">
                <span style="font-weight:600;font-size:12px;color:var(--text-color,#1f272e);
                    white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%;">
                    ${frappe.utils.escape_html(item.name)}
                </span>
            </div>
            <span style="font-size:11px;color:var(--text-muted,#8d99a6);padding-left:22px;">
                ${frappe.utils.escape_html(item.id)}
            </span>
        </label>`).join('');
}

function render_card_grid(dialog, html_field, cls, count_id, search_id, items) {
    dialog._card_items             = dialog._card_items || {};
    dialog._card_items[html_field] = items;
    const wrapper = dialog.fields_dict[html_field].$wrapper;
    wrapper.html(`
        <div style="margin-bottom:10px;display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
            <input id="${search_id}" type="text" class="form-control"
                placeholder="Search by name or Employee ID…"
                style="flex:1;min-width:160px;max-width:320px;">
            <button class="btn btn-xs btn-default" id="${search_id}_sel_all">${__('Select All')}</button>
            <button class="btn btn-xs btn-default" id="${search_id}_desel_all">${__('Deselect All')}</button>
            <span id="${count_id}" class="text-muted" style="font-size:12px;">0 selected</span>
        </div>
        <div id="${search_id}_grid" style="display:flex;flex-wrap:wrap;gap:10px;max-height:380px;overflow-y:auto;padding:4px 2px;">
            ${build_cards(items, cls)}
        </div>`);

    const upd  = () => wrapper.find(`#${count_id}`).text(wrapper.find(`.${cls}:checked`).length + ' selected');
    const bind = () => { wrapper.find(`.${cls}`).off('change').on('change', upd); upd(); };

    wrapper.find(`#${search_id}`).on('input', function() {
        const q = $(this).val().toLowerCase().trim();
        wrapper.find(`#${search_id}_grid`).html(build_cards(
            q ? dialog._card_items[html_field].filter(i =>
                    i.id.toLowerCase().includes(q) || i.name.toLowerCase().includes(q))
              : dialog._card_items[html_field], cls));
        bind();
    });
    wrapper.find(`#${search_id}_sel_all`).on('click',   () => { wrapper.find(`.${cls}`).prop('checked', true);  upd(); });
    wrapper.find(`#${search_id}_desel_all`).on('click', () => { wrapper.find(`.${cls}`).prop('checked', false); upd(); });
    bind();
}