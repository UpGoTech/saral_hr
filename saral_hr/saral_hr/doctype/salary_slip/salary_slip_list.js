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

function get_year_options() { const y = new Date().getFullYear(); return [y-2,y-1,y,y+1].map(String); }
function get_current_month() { return MONTHS[new Date().getMonth()]; }

// ─── Card grid helpers ────────────────────────────────────────────────────────

function build_cards(items, cls) {
    if (!items || !items.length)
        return `<div class="text-muted" style="padding:20px;width:100%;text-align:center;">No employees available for the selected period.</div>`;
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

// Render a card grid with search + select-all controls inside a dialog HTML field
function render_card_grid(dialog, html_field, cls, count_id, search_id, items) {
    dialog._card_items             = dialog._card_items || {};
    dialog._card_items[html_field] = items;
    const wrapper = dialog.fields_dict[html_field].$wrapper;
    wrapper.html(`
        <div style="margin-bottom:10px;display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
            <input id="${search_id}" type="text" class="form-control"
                placeholder="Search by name or Employee ID..."
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
            q ? dialog._card_items[html_field].filter(i => i.id.toLowerCase().includes(q) || i.name.toLowerCase().includes(q))
              : dialog._card_items[html_field], cls));
        bind();
    });
    wrapper.find(`#${search_id}_sel_all`).on('click',   () => { wrapper.find(`.${cls}`).prop('checked', true);  upd(); });
    wrapper.find(`#${search_id}_desel_all`).on('click', () => { wrapper.find(`.${cls}`).prop('checked', false); upd(); });
    bind();
}

function get_checked_ids(dialog, html_field, cls) {
    const ids = [];
    dialog.fields_dict[html_field].$wrapper.find(`.${cls}:checked`).each(function() {
        ids.push({ id: $(this).data('id'), name: $(this).data('name') });
    });
    return ids;
}

function show_result_dialog(title, result, success_label) {
    let msg = `<table class="table table-bordered" style="margin-bottom:0;">
        <tr><td><strong>${success_label}:</strong></td><td style="color:var(--green);font-weight:bold;">${result.success}</td></tr>
        <tr><td><strong>Failed:</strong></td><td style="color:var(--red);font-weight:bold;">${result.failed}</td></tr>
    </table>`;
    if (result.errors && result.errors.length) {
        msg += '<div style="margin-top:12px;"><strong>Details:</strong><ul style="margin-top:4px;">';
        result.errors.forEach(e => { msg += `<li>${e}</li>`; });
        msg += '</ul></div>';
    }
    frappe.msgprint({ title, message: msg, indicator: result.failed > 0 ? 'orange' : 'green' });
}

// ─── Bulk Generate ────────────────────────────────────────────────────────────

function show_bulk_salary_slip_dialog() {
    const d = new frappe.ui.Dialog({
        title: __('Bulk Generate Salary Slips'),
        fields: [
            { fieldname:'company',        fieldtype:'Link',   label:'Company', options:'Company', reqd:1 },
            { fieldname:'cb1',            fieldtype:'Column Break' },
            { fieldname:'year',           fieldtype:'Select', label:'Year',  options:get_year_options(), reqd:1, default:new Date().getFullYear().toString() },
            { fieldname:'cb2',            fieldtype:'Column Break' },
            { fieldname:'month',          fieldtype:'Select', label:'Month', options:MONTHS, reqd:1, default:get_current_month() },
            { fieldname:'sb_cat',         fieldtype:'Section Break', label:'Filter by Category' },
            { fieldname:'category',       fieldtype:'Link', label:'Category', options:'Category', reqd:1,
              description:'Salary slips will only be generated for employees in this category.' },
            { fieldname:'sb1',            fieldtype:'Section Break' },
            { fieldname:'fetch_employees',fieldtype:'Button', label:'Fetch Eligible Employees', click:() => fetch_eligible_employees(d) },
            { fieldname:'sb2',            fieldtype:'Section Break' },
            { fieldname:'employees_html', fieldtype:'HTML' }
        ],
        primary_action_label: __('Generate Salary Slips'),
        primary_action: () => generate_bulk_salary_slips(d)
    });
    d.show();
}

function fetch_eligible_employees(dialog) {
    const { company, year, month, category } = _get_dialog_values(dialog, ['company','year','month','category']);
    if (!company)        { frappe.msgprint(__('Please select Company'));        return; }
    if (!year || !month) { frappe.msgprint(__('Please select Year and Month')); return; }
    if (!category)       { frappe.msgprint(__('Please select a Category'));     return; }

    const wrapper = dialog.fields_dict.employees_html.$wrapper;
    wrapper.html(`<div class="text-muted" style="padding:16px 0;text-align:center;font-size:12px;">
        ${frappe.utils.icon('loading','xs')} &nbsp;Retrieving employee payroll eligibility...
    </div>`);

    frappe.call({
        method: 'saral_hr.saral_hr.doctype.salary_slip.salary_slip.get_eligible_employees_for_salary_slip',
        args: { company, year, month, category },
        callback(r) {
            if (!r.message) { wrapper.html('<div class="text-muted" style="padding:16px 0;text-align:center;">Unable to retrieve employee data.</div>'); return; }

            const { eligible=[], skipped=[], total_active, total_eligible, category_requires_variable_pay } = r.message;
            dialog._card_items                   = dialog._card_items || {};
            dialog._card_items['employees_html'] = eligible.map(e => ({ id:e.name, name:e.employee_name||e.name }));
            dialog._ineligible_employees         = skipped;

            const ineligible_btn = skipped.length
                ? `<button class="btn btn-default btn-sm" id="btn_view_ineligible" style="margin-left:auto;">
                       ${__('View Ineligibility Details')} (${skipped.length})
                   </button>` : '';

            const summary = _summary_bar([
                [`Active Employees <em style="font-size:10px;">(${frappe.utils.escape_html(category)})</em>`, total_active],
                ['Eligible for Processing', total_eligible],
                ['Excluded', skipped.length]
            ], ineligible_btn);

            let grid_html = eligible.length
                ? _search_grid_html('emp_search', 'emp-card-check', 'emp_count', dialog._card_items['employees_html'])
                : `<div class="text-muted" style="padding:20px 0;text-align:center;font-size:12px;">No employees eligible for the selected period.</div>`;

            wrapper.html(summary + grid_html);

            if (skipped.length)
                wrapper.find('#btn_view_ineligible').on('click', () =>
                    show_ineligible_employees_dialog(dialog._ineligible_employees, month, year, category_requires_variable_pay));

            if (eligible.length)
                _bind_inline_grid(wrapper, 'emp_search', 'emp-card-check', 'emp_count', dialog._card_items['employees_html']);
        }
    });
}

function generate_bulk_salary_slips(dialog) {
    const selected = get_checked_ids(dialog, 'employees_html', 'emp-card-check');
    const category = dialog.get_value('category');
    if (!category)        { frappe.msgprint(__('Please select a Category'));            return; }
    if (!selected.length) { frappe.msgprint(__('Please select at least one employee')); return; }

    frappe.confirm(`Generate salary slips for <b>${selected.length}</b> employee(s)?`, () => {
        dialog.hide();
        frappe.dom.freeze(__('Generating Salary Slips...'));
        frappe.call({
            method: 'saral_hr.saral_hr.doctype.salary_slip.salary_slip.bulk_generate_salary_slips',
            args: { employees: selected.map(s => ({ employee:s.id, employee_name:s.name })), year:dialog.get_value('year'), month:dialog.get_value('month') },
            callback(r) { frappe.dom.unfreeze(); if (r.message) { show_result_dialog(__('Bulk Generation Result'), r.message, 'Successfully Created'); if (cur_list) cur_list.refresh(); } },
            error()     { frappe.dom.unfreeze(); frappe.msgprint({ title:__('Error'), message:__('Failed to generate salary slips.'), indicator:'red' }); }
        });
    });
}

// ─── Ineligible Employees Dialog ──────────────────────────────────────────────

function show_ineligible_employees_dialog(list, month, year, show_vpa) {
    const FAIL = `<span style="display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;border-radius:50%;background:var(--red-100,#fde8e8);color:var(--red-500,#e03131);font-size:13px;font-weight:700;">&#x2715;</span>`;
    const OK   = `<span style="display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;border-radius:50%;background:var(--green-100,#ebfbee);color:var(--green-600,#2f9e44);font-size:13px;font-weight:700;">&#x2713;</span>`;
    const cols = show_vpa ? 4 : 3;

    function flags(reasons) {
        const r = reasons || [];
        return {
            ss:  r.some(x => x.toLowerCase().includes('salary structure')),
            vpa: r.some(x => x.toLowerCase().includes('variable pay')),
            att: r.some(x => x.toLowerCase().includes('attendance'))
        };
    }

    function build_rows(source) {
        if (!source || !source.length) return `<tr><td colspan="${cols}" class="text-muted" style="padding:20px;text-align:center;">No matching employees found.</td></tr>`;
        return source.map((s, i) => {
            const f  = flags(s.reasons);
            const bg = i % 2 ? 'background:var(--subtle-accent-bg,#f9fafb);' : '';
            return `<tr style="${bg}">
                <td style="padding:8px 10px;border-bottom:1px solid var(--border-color);border-right:1px solid var(--border-color);white-space:nowrap;">
                    <div style="font-size:12px;font-weight:600;">${frappe.utils.escape_html(s.name)}</div>
                    <div style="font-size:11px;color:var(--text-muted);">${frappe.utils.escape_html(s.id)}</div>
                </td>
                <td style="padding:8px 10px;border-bottom:1px solid var(--border-color);border-right:1px solid var(--border-color);text-align:center;">${f.ss  ? FAIL : OK}</td>
                ${show_vpa ? `<td style="padding:8px 10px;border-bottom:1px solid var(--border-color);border-right:1px solid var(--border-color);text-align:center;">${f.vpa ? FAIL : OK}</td>` : ''}
                <td style="padding:8px 10px;border-bottom:1px solid var(--border-color);text-align:center;">${f.att ? FAIL : OK}</td>
            </tr>`;
        }).join('');
    }

    const th = (l, last=false) => `<th style="position:sticky;top:0;z-index:1;padding:8px 10px;text-align:center;font-size:11px;font-weight:600;text-transform:uppercase;color:var(--text-muted);background:var(--subtle-accent-bg,#f5f6f7);border-bottom:2px solid var(--border-color);${last?'':'border-right:1px solid var(--border-color);'}white-space:normal;line-height:1.4;">${l}</th>`;

    const legend = `<div style="display:flex;gap:16px;margin-bottom:10px;font-size:11px;color:var(--text-muted);">
        <span style="display:flex;align-items:center;gap:5px;">${FAIL} Criterion not met</span>
        <span style="display:flex;align-items:center;gap:5px;">${OK} Criterion met</span>
    </div>`;

    const dlg = new frappe.ui.Dialog({ title:__(`Payroll Eligibility Review — ${month} ${year}`), size:'large', fields:[{fieldname:'html',fieldtype:'HTML'}] });
    dlg.fields_dict.html.$wrapper.html(`<div style="padding-bottom:4px;">
        <p style="margin-bottom:12px;font-size:12px;"><strong>${list.length}</strong> employee(s) excluded from payroll for <strong>${month} ${year}</strong>.</p>
        ${legend}
        <div style="margin-bottom:10px;"><input id="inel_search" type="text" class="form-control" placeholder="Search..." style="max-width:320px;font-size:12px;"></div>
        <div style="border:1px solid var(--border-color);border-radius:var(--border-radius);overflow:hidden;">
        <div style="overflow-x:auto;max-height:400px;overflow-y:auto;">
        <table style="width:100%;border-collapse:collapse;min-width:${show_vpa?'460px':'360px'};">
        <thead><tr>
            <th style="position:sticky;top:0;z-index:1;padding:8px 10px;text-align:left;font-size:11px;font-weight:600;text-transform:uppercase;color:var(--text-muted);background:var(--subtle-accent-bg,#f5f6f7);border-bottom:2px solid var(--border-color);border-right:1px solid var(--border-color);width:32%;">Employee</th>
            ${th('Salary Structure<br>Assigned', !show_vpa)}
            ${show_vpa ? th('Variable Pay<br>Configured', false) : ''}
            ${th('Attendance<br>Recorded', true)}
        </tr></thead>
        <tbody id="inel_tbody">${build_rows(list)}</tbody>
        </table></div></div>
    </div>`);
    dlg.show();
    dlg.fields_dict.html.$wrapper.find('#inel_search').on('input', function() {
        const q = $(this).val().toLowerCase().trim();
        dlg.fields_dict.html.$wrapper.find('#inel_tbody').html(build_rows(
            q ? list.filter(s => s.id.toLowerCase().includes(q) || s.name.toLowerCase().includes(q)) : list));
    });
}

// ─── Bulk Print ───────────────────────────────────────────────────────────────

function show_bulk_print_dialog() {
    const d = new frappe.ui.Dialog({
        title: __('Bulk Print Salary Slips'),
        fields: [
            { fieldname:'company',    fieldtype:'Link',   label:'Company', options:'Company', reqd:1 },
            { fieldname:'cb1',        fieldtype:'Column Break' },
            { fieldname:'year',       fieldtype:'Select', label:'Year',  options:get_year_options(), reqd:1, default:new Date().getFullYear().toString() },
            { fieldname:'cb2',        fieldtype:'Column Break' },
            { fieldname:'month',      fieldtype:'Select', label:'Month', options:MONTHS, reqd:1, default:get_current_month() },
            { fieldname:'sb_cat',     fieldtype:'Section Break', label:'Filter by Category' },
            { fieldname:'category',   fieldtype:'Link', label:'Category', options:'Category', reqd:1,
              description:'Only salary slips for employees in this category will be shown.' },
            { fieldname:'sb1',        fieldtype:'Section Break' },
            { fieldname:'fetch_slips',fieldtype:'Button', label:'Fetch Submitted Salary Slips', click:() => fetch_submitted_salary_slips(d) },
            { fieldname:'sb2',        fieldtype:'Section Break' },
            { fieldname:'slips_html', fieldtype:'HTML' }
        ],
        primary_action_label: __('Print Selected Slips'),
        primary_action: () => print_selected_salary_slips(d)
    });
    d.show();
}

function fetch_submitted_salary_slips(dialog) {
    const { company, year, month, category } = _get_dialog_values(dialog, ['company','year','month','category']);
    if (!company)        { frappe.msgprint(__('Please select Company'));        return; }
    if (!year || !month) { frappe.msgprint(__('Please select Year and Month')); return; }
    if (!category)       { frappe.msgprint(__('Please select a Category'));     return; }

    const wrapper = dialog.fields_dict.slips_html.$wrapper;
    wrapper.html(`<div class="text-muted" style="padding:16px 0;text-align:center;font-size:12px;">${frappe.utils.icon('loading','xs')} &nbsp;Retrieving submitted salary slips...</div>`);

    frappe.call({
        method: 'saral_hr.saral_hr.doctype.salary_slip.salary_slip.get_salary_slips_print_summary',
        args: { company, year, month, category },
        callback(r) {
            if (!r.message) { wrapper.html('<div class="text-muted" style="padding:16px 0;text-align:center;">Unable to retrieve data.</div>'); return; }

            const { submitted=[], not_printable=[], total_active, total_submitted } = r.message;
            dialog._not_printable_slips = not_printable;

            const excl_btn = not_printable.length
                ? `<button class="btn btn-default btn-sm" id="btn_view_excl" style="margin-left:auto;">${__('View Exclusion Details')} (${not_printable.length})</button>` : '';

            const summary = _summary_bar([
                [`Active <em style="font-size:10px;">(${frappe.utils.escape_html(category)})</em>`, total_active],
                ['Submitted Slips', total_submitted],
                ['Excluded from Print', not_printable.length]
            ], excl_btn);

            let grid_html = '';
            if (submitted.length) {
                const items = submitted.map(s => ({ id:s.name, name:s.employee_name||s.employee }));
                dialog._card_items             = dialog._card_items || {};
                dialog._card_items['slips_html'] = items;
                grid_html = _search_grid_html('slip_search', 'slip-card-check', 'slip_count', items);
            } else {
                grid_html = `<div class="text-muted" style="padding:20px;text-align:center;">No submitted salary slips found.</div>`;
            }

            wrapper.html(summary + grid_html);

            if (not_printable.length)
                wrapper.find('#btn_view_excl').on('click', () => show_print_exclusions_dialog(dialog._not_printable_slips, month, year));

            if (submitted.length)
                _bind_inline_grid(wrapper, 'slip_search', 'slip-card-check', 'slip_count', dialog._card_items['slips_html']);
        }
    });
}

function print_selected_salary_slips(dialog) {
    const selected = get_checked_ids(dialog, 'slips_html', 'slip-card-check');
    if (!selected.length) { frappe.msgprint(__('Please select at least one salary slip to print')); return; }

    frappe.confirm(`Print <b>${selected.length}</b> salary slip(s)?`, () => {
        dialog.hide();
        frappe.dom.freeze(__('Preparing PDF...'));
        frappe.call({
            method: 'saral_hr.saral_hr.doctype.salary_slip.salary_slip.bulk_print_salary_slips',
            args: { salary_slip_names: selected.map(s => s.id) },
            callback(r) { frappe.dom.unfreeze(); if (r.message) { window.open(r.message.pdf_url, '_blank'); frappe.msgprint({ title:__('Print Ready'), message:`${selected.length} slip(s) prepared.`, indicator:'green' }); } },
            error()     { frappe.dom.unfreeze(); frappe.msgprint({ title:__('Error'), message:__('Failed to generate PDF.'), indicator:'red' }); }
        });
    });
}

// ─── Print Exclusions Dialog ──────────────────────────────────────────────────

function show_print_exclusions_dialog(list, month, year) {
    function status_badge(s) {
        const cfg = { Draft:{bg:'#fff3cd',c:'#856404'}, 'No Slip':{bg:'#fde8e8',c:'#e03131'}, Cancelled:{bg:'#f0f0f0',c:'#6c757d'} };
        const x = cfg[s] || {bg:'#f0f0f0',c:'#495057'};
        return `<span style="display:inline-block;padding:2px 10px;border-radius:20px;font-size:10px;font-weight:700;text-transform:uppercase;background:${x.bg};color:${x.c};border:1px solid ${x.c}33;">${s}</span>`;
    }
    function pill(t) { return `<span style="display:inline-block;padding:2px 8px;border-radius:4px;margin:2px 2px 2px 0;font-size:10px;background:var(--subtle-accent-bg,#f5f6f7);color:var(--text-muted);border:1px solid var(--border-color);">${frappe.utils.escape_html(t)}</span>`; }

    function build_rows(source) {
        if (!source.length) return `<tr><td colspan="4" class="text-muted" style="padding:20px;text-align:center;">No matching employees found.</td></tr>`;
        return source.map((s, i) => {
            const bg = i%2 ? 'background:var(--subtle-accent-bg,#f9fafb);' : '';
            return `<tr style="${bg}">
                <td style="padding:8px 10px;border-bottom:1px solid var(--border-color);border-right:1px solid var(--border-color);white-space:nowrap;">
                    <div style="font-size:12px;font-weight:600;">${frappe.utils.escape_html(s.employee_name||s.name)}</div>
                    <div style="font-size:11px;color:var(--text-muted);">${frappe.utils.escape_html(s.employee)}</div>
                </td>
                <td style="padding:8px 10px;border-bottom:1px solid var(--border-color);border-right:1px solid var(--border-color);text-align:center;">
                    ${s.slip_name ? `<div style="font-size:11px;font-weight:600;">${frappe.utils.escape_html(s.slip_name)}</div>` : `<span style="color:var(--text-muted);">—</span>`}
                </td>
                <td style="padding:8px 10px;border-bottom:1px solid var(--border-color);border-right:1px solid var(--border-color);text-align:center;">${status_badge(s.slip_status)}</td>
                <td style="padding:8px 10px;border-bottom:1px solid var(--border-color);"><div style="line-height:1.8;">${(s.reasons||[]).map(pill).join('')}</div></td>
            </tr>`;
        }).join('');
    }

    const th = (l, last=false) => `<th style="position:sticky;top:0;z-index:1;padding:8px 10px;text-align:center;font-size:11px;font-weight:600;text-transform:uppercase;color:var(--text-muted);background:var(--subtle-accent-bg,#f5f6f7);border-bottom:2px solid var(--border-color);${last?'':'border-right:1px solid var(--border-color);'}white-space:normal;line-height:1.4;">${l}</th>`;

    const dlg = new frappe.ui.Dialog({ title:__(`Print Exclusion Review — ${month} ${year}`), size:'large', fields:[{fieldname:'html',fieldtype:'HTML'}] });
    dlg.fields_dict.html.$wrapper.html(`<div style="padding-bottom:4px;">
        <p style="margin-bottom:12px;font-size:12px;"><strong>${list.length}</strong> employee(s) cannot be printed for <strong>${month} ${year}</strong>. Only Submitted slips can be printed.</p>
        <div style="margin-bottom:10px;"><input id="pexcl_search" type="text" class="form-control" placeholder="Search..." style="max-width:320px;font-size:12px;"></div>
        <div style="border:1px solid var(--border-color);border-radius:var(--border-radius);overflow:hidden;">
        <div style="overflow-x:auto;max-height:420px;overflow-y:auto;">
        <table style="width:100%;border-collapse:collapse;min-width:580px;">
        <thead><tr>
            <th style="position:sticky;top:0;z-index:1;padding:8px 10px;text-align:left;font-size:11px;font-weight:600;text-transform:uppercase;color:var(--text-muted);background:var(--subtle-accent-bg,#f5f6f7);border-bottom:2px solid var(--border-color);border-right:1px solid var(--border-color);width:28%;">Employee</th>
            ${th('Salary Slip')}${th('Slip Status')}${th('Reason(s)',true)}
        </tr></thead>
        <tbody id="pexcl_tbody">${build_rows(list)}</tbody>
        </table></div></div>
    </div>`);
    dlg.show();
    dlg.fields_dict.html.$wrapper.find('#pexcl_search').on('input', function() {
        const q = $(this).val().toLowerCase().trim();
        dlg.fields_dict.html.$wrapper.find('#pexcl_tbody').html(build_rows(
            q ? list.filter(s => (s.employee||'').toLowerCase().includes(q)||(s.employee_name||'').toLowerCase().includes(q)) : list));
    });
}

// ─── Draft to Submit ──────────────────────────────────────────────────────────

function show_draft_to_submit_dialog() {
    const d = new frappe.ui.Dialog({
        title: __('Submit Draft Salary Slips'),
        fields: [
            { fieldname:'company',      fieldtype:'Link',   label:'Company', options:'Company', reqd:1 },
            { fieldname:'cb1',          fieldtype:'Column Break' },
            { fieldname:'year',         fieldtype:'Select', label:'Year',  options:get_year_options(), reqd:1, default:new Date().getFullYear().toString() },
            { fieldname:'cb2',          fieldtype:'Column Break' },
            { fieldname:'month',        fieldtype:'Select', label:'Month', options:MONTHS, reqd:1, default:get_current_month() },
            { fieldname:'sb1',          fieldtype:'Section Break' },
            { fieldname:'fetch_drafts', fieldtype:'Button', label:'Fetch Draft Salary Slips', click:() => fetch_draft_salary_slips(d) },
            { fieldname:'sb2',          fieldtype:'Section Break' },
            { fieldname:'drafts_html',  fieldtype:'HTML' }
        ],
        primary_action_label: __('Submit Selected Slips'),
        primary_action: () => submit_selected_salary_slips(d)
    });
    d.show();
}

function fetch_draft_salary_slips(dialog) {
    const { company, year, month } = _get_dialog_values(dialog, ['company','year','month']);
    if (!company)        { frappe.msgprint(__('Please select Company'));        return; }
    if (!year || !month) { frappe.msgprint(__('Please select Year and Month')); return; }
    frappe.call({
        method: 'saral_hr.saral_hr.doctype.salary_slip.salary_slip.get_draft_salary_slips',
        args: { company, year, month },
        callback(r) {
            if (r.message && r.message.length) {
                render_card_grid(dialog, 'drafts_html', 'draft-card-check', 'draft_count', 'draft_search',
                    r.message.map(s => ({ id:s.name, name:s.employee_name||s.employee })));
            } else {
                dialog.fields_dict.drafts_html.$wrapper.html('<div class="text-muted" style="padding:20px;text-align:center;">No draft salary slips found.</div>');
            }
        }
    });
}

function submit_selected_salary_slips(dialog) {
    const selected = get_checked_ids(dialog, 'drafts_html', 'draft-card-check');
    if (!selected.length) { frappe.msgprint(__('Please select at least one salary slip to submit')); return; }

    frappe.confirm(`Submit <b>${selected.length}</b> salary slip(s)? This cannot be undone.`, () => {
        dialog.hide();
        frappe.dom.freeze(__('Submitting salary slips...'));
        frappe.call({
            method: 'saral_hr.saral_hr.doctype.salary_slip.salary_slip.bulk_submit_salary_slips',
            args: { salary_slip_names: selected.map(s => s.id) },
            callback(r) { frappe.dom.unfreeze(); if (r.message) { show_result_dialog(__('Bulk Submission Result'), r.message, 'Successfully Submitted'); if (cur_list) cur_list.refresh(); } },
            error()     { frappe.dom.unfreeze(); frappe.msgprint({ title:__('Error'), message:__('Failed to submit salary slips.'), indicator:'red' }); }
        });
    });
}

// ─── Private UI helpers ───────────────────────────────────────────────────────

function _get_dialog_values(dialog, fields) {
    return fields.reduce((acc, f) => { acc[f] = dialog.get_value(f); return acc; }, {});
}

function _summary_bar(stats, trailing_html = '') {
    const items = stats.map(([label, value]) =>
        `<span style="color:var(--text-muted);">${label}: <strong style="color:var(--text-color);">${value}</strong></span>`
    ).join(`<span style="color:var(--border-color);">|</span>`);
    return `<div style="display:flex;align-items:center;flex-wrap:wrap;gap:16px;
        padding:8px 0;margin-bottom:12px;font-size:12px;border-bottom:1px solid var(--border-color);">
        ${items}${trailing_html ? trailing_html : ''}
    </div>`;
}

function _search_grid_html(search_id, cls, count_id, items) {
    return `<div style="margin-bottom:10px;display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
        <input id="${search_id}" type="text" class="form-control"
            placeholder="Search by name or Employee ID..."
            style="flex:1;min-width:160px;max-width:320px;">
        <button class="btn btn-xs btn-default" id="${search_id}_sel_all">${__('Select All')}</button>
        <button class="btn btn-xs btn-default" id="${search_id}_desel_all">${__('Deselect All')}</button>
        <span id="${count_id}" class="text-muted" style="font-size:12px;">0 selected</span>
    </div>
    <div id="${search_id}_grid" style="display:flex;flex-wrap:wrap;gap:10px;max-height:300px;overflow-y:auto;padding:4px 2px;">
        ${build_cards(items, cls)}
    </div>`;
}

function _bind_inline_grid(wrapper, search_id, cls, count_id, all_items) {
    const upd  = () => wrapper.find(`#${count_id}`).text(wrapper.find(`.${cls}:checked`).length + ' selected');
    const bind = () => { wrapper.find(`.${cls}`).off('change').on('change', upd); upd(); };

    wrapper.find(`#${search_id}`).on('input', function() {
        const q = $(this).val().toLowerCase().trim();
        wrapper.find(`#${search_id}_grid`).html(build_cards(
            q ? all_items.filter(i => i.id.toLowerCase().includes(q) || i.name.toLowerCase().includes(q)) : all_items, cls));
        bind();
    });
    wrapper.find(`#${search_id}_sel_all`).on('click',   () => { wrapper.find(`.${cls}`).prop('checked', true);  upd(); });
    wrapper.find(`#${search_id}_desel_all`).on('click', () => { wrapper.find(`.${cls}`).prop('checked', false); upd(); });
    bind();
}