frappe.listview_settings['Salary Slip'] = {
    onload: function(listview) {
        listview.page.add_inner_button(__('Bulk Generate Salary Slips'), () => show_bulk_salary_slip_dialog());
        listview.page.add_inner_button(__('Bulk Print Salary Slips'), () => show_bulk_print_dialog());
        listview.page.add_inner_button(__('Draft to Submit'), () => show_draft_to_submit_dialog());
    }
};

// ─── Shared Helpers ───────────────────────────────────────────────────────────

function get_year_options() {
    const y = new Date().getFullYear();
    return [y - 2, y - 1, y, y + 1].map(String);
}

function get_current_month() {
    return ['January','February','March','April','May','June',
            'July','August','September','October','November','December'][new Date().getMonth()];
}

const MONTHS = ['January','February','March','April','May','June',
                'July','August','September','October','November','December'];

// ── FIX: detect DA component by name OR abbreviation ─────────────────────────
function is_da_component(comp_name, abbr) {
    const name = (comp_name || '').toLowerCase();
    const ab   = (abbr || '').toLowerCase().trim();
    return (
        name.includes('dearness')
        || name === 'da'
        || ab === 'da'
        || ab.startsWith('da-')
        || ab.startsWith('da ')
        || ab === 'da - dr'
        || ab.startsWith('da-dr')
    );
}

// ─── Card Grid ───────────────────────────────────────────────────────────────

function build_cards(items, card_class) {
    if (!items || !items.length)
        return `<div class="text-muted" style="padding:20px;width:100%;text-align:center;">No employees available for the selected period.</div>`;

    return items.map(item => `
        <label style="display:flex;flex-direction:column;align-items:flex-start;
            width:calc(33.33% - 8px);min-width:140px;
            border:1px solid var(--border-color,#d1d8dd);
            border-radius:6px;padding:10px 12px;cursor:pointer;
            background:var(--card-bg,#fff);
            transition:border-color 0.15s,box-shadow 0.15s;box-sizing:border-box;gap:4px;"
            onmouseover="this.style.borderColor='var(--primary,#5e64ff)';this.style.boxShadow='0 0 0 2px var(--primary-light,#eef0ff)'"
            onmouseout="this.style.borderColor='var(--border-color,#d1d8dd)';this.style.boxShadow='none'">
            <div style="display:flex;align-items:center;gap:8px;width:100%;">
                <input type="checkbox" class="${card_class}"
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

function render_card_grid(dialog, html_field, card_class, count_id, search_id, items) {
    dialog._card_items = dialog._card_items || {};
    dialog._card_items[html_field] = items;

    const wrapper = dialog.fields_dict[html_field].$wrapper;
    wrapper.html(`
        <div style="margin-bottom:10px;display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
            <input id="${search_id}" type="text" class="form-control"
                placeholder="Search by name or Employee ID..."
                style="flex:1;min-width:160px;max-width:320px;">
            <button class="btn btn-xs btn-default" id="${search_id}_select_all">${__('Select All')}</button>
            <button class="btn btn-xs btn-default" id="${search_id}_deselect_all">${__('Deselect All')}</button>
            <span id="${count_id}" class="text-muted" style="font-size:12px;">0 selected</span>
        </div>
        <div id="${search_id}_grid"
            style="display:flex;flex-wrap:wrap;gap:10px;max-height:380px;overflow-y:auto;padding:4px 2px;">
            ${build_cards(items, card_class)}
        </div>`);

    const update = () => update_count(wrapper, card_class, count_id);
    const bind   = () => {
        wrapper.find(`.${card_class}`).off('change').on('change', update);
        update();
    };

    wrapper.find(`#${search_id}`).on('input', function() {
        const q = $(this).val().toLowerCase().trim();
        const filtered = q
            ? dialog._card_items[html_field].filter(i => i.id.toLowerCase().includes(q) || i.name.toLowerCase().includes(q))
            : dialog._card_items[html_field];
        wrapper.find(`#${search_id}_grid`).html(build_cards(filtered, card_class));
        bind();
    });

    wrapper.find(`#${search_id}_select_all`).on('click', () => {
        wrapper.find(`.${card_class}`).prop('checked', true); update();
    });
    wrapper.find(`#${search_id}_deselect_all`).on('click', () => {
        wrapper.find(`.${card_class}`).prop('checked', false); update();
    });

    bind();
}

function update_count(wrapper, card_class, count_id) {
    wrapper.find(`#${count_id}`).text(wrapper.find(`.${card_class}:checked`).length + ' selected');
}

function get_checked_ids(dialog, html_field, card_class) {
    const ids = [];
    dialog.fields_dict[html_field].$wrapper.find(`.${card_class}:checked`).each(function() {
        ids.push({ id: $(this).data('id'), name: $(this).data('name') });
    });
    return ids;
}

// ─── Bulk Generate ────────────────────────────────────────────────────────────

function show_bulk_salary_slip_dialog() {
    let d = new frappe.ui.Dialog({
        title: __('Bulk Generate Salary Slips'),
        fields: [
            { fieldname: 'company', fieldtype: 'Link', label: 'Company', options: 'Company', reqd: 1 },
            { fieldname: 'cb1', fieldtype: 'Column Break' },
            { fieldname: 'year', fieldtype: 'Select', label: 'Year', options: get_year_options(), reqd: 1, default: new Date().getFullYear().toString() },
            { fieldname: 'cb2', fieldtype: 'Column Break' },
            { fieldname: 'month', fieldtype: 'Select', label: 'Month', options: MONTHS, reqd: 1, default: get_current_month() },
            { fieldname: 'sb_category', fieldtype: 'Section Break', label: 'Filter by Category' },
            {
                fieldname: 'category',
                fieldtype: 'Link',
                label: 'Category',
                options: 'Category',
                reqd: 1,
                description: 'Salary slips will only be generated for employees belonging to this category.'
            },
            { fieldname: 'sb1', fieldtype: 'Section Break' },
            { fieldname: 'fetch_employees', fieldtype: 'Button', label: 'Fetch Eligible Employees', click: function() { fetch_eligible_employees(d); } },
            { fieldname: 'sb2', fieldtype: 'Section Break' },
            { fieldname: 'employees_html', fieldtype: 'HTML' }
        ],
        primary_action_label: __('Generate Salary Slips'),
        primary_action: () => generate_bulk_salary_slips(d)
    });
    d.show();
}

function fetch_eligible_employees(dialog) {
    const company  = dialog.get_value('company');
    const year     = dialog.get_value('year');
    const month    = dialog.get_value('month');
    const category = dialog.get_value('category');

    if (!company)        { frappe.msgprint(__('Please select Company')); return; }
    if (!year || !month) { frappe.msgprint(__('Please select Year and Month')); return; }
    if (!category)       { frappe.msgprint(__('Please select a Category')); return; }

    const wrapper = dialog.fields_dict.employees_html.$wrapper;
    wrapper.html(`<div class="text-muted" style="padding:16px 0;text-align:center;font-size:12px;">
        ${frappe.utils.icon('loading','xs')} &nbsp;Retrieving employee payroll eligibility...
    </div>`);

    frappe.call({
        method: 'saral_hr.saral_hr.doctype.salary_slip.salary_slip.get_eligible_employees_for_salary_slip',
        args: { company, year, month, category },
        callback: function(r) {
            if (!r.message) {
                wrapper.html('<div class="text-muted" style="padding:16px 0;text-align:center;">Unable to retrieve employee data. Please try again.</div>');
                return;
            }

            const {
                eligible,
                skipped,
                total_active,
                total_eligible,
                category_requires_variable_pay
            } = r.message;

            const ineligible_list = skipped || [];

            dialog._card_items = dialog._card_items || {};
            dialog._card_items['employees_html'] = (eligible || []).map(emp => ({
                id:   emp.name,
                name: emp.employee_name || emp.name
            }));
            dialog._ineligible_employees = ineligible_list;

            const ineligible_btn = ineligible_list.length > 0
                ? `<button class="btn btn-default btn-sm" id="btn_view_ineligible"
                        style="margin-left:auto;">
                        ${__('View Ineligibility Details')} (${ineligible_list.length})
                   </button>`
                : '';

            const summary = `
                <div style="display:flex;align-items:center;flex-wrap:wrap;gap:16px;
                    padding:8px 0;margin-bottom:12px;font-size:12px;
                    border-bottom:1px solid var(--border-color);">
                    <span style="color:var(--text-muted);">
                        Active Employees <em style="font-size:10px;">(${frappe.utils.escape_html(category)})</em>:
                        <strong style="color:var(--text-color);">${total_active}</strong>
                    </span>
                    <span style="color:var(--border-color);">|</span>
                    <span style="color:var(--text-muted);">
                        Eligible for Processing: <strong style="color:var(--text-color);">${total_eligible}</strong>
                    </span>
                    <span style="color:var(--border-color);">|</span>
                    <span style="color:var(--text-muted);">
                        Excluded: <strong style="color:var(--text-color);">${ineligible_list.length}</strong>
                    </span>
                    ${ineligible_btn}
                </div>`;

            let grid_html = '';
            if (eligible && eligible.length > 0) {
                grid_html = `
                    <div style="margin-bottom:10px;display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
                        <input id="emp_search" type="text" class="form-control"
                            placeholder="Search by name or Employee ID..."
                            style="flex:1;min-width:160px;max-width:300px;font-size:12px;">
                        <button class="btn btn-xs btn-default" id="emp_search_select_all">${__('Select All')}</button>
                        <button class="btn btn-xs btn-default" id="emp_search_deselect_all">${__('Deselect All')}</button>
                        <span id="emp_selected_count" class="text-muted" style="font-size:12px;">0 selected</span>
                    </div>
                    <div id="emp_search_grid"
                        style="display:flex;flex-wrap:wrap;gap:10px;max-height:300px;overflow-y:auto;padding:4px 2px;">
                        ${build_cards(dialog._card_items['employees_html'], 'emp-card-check')}
                    </div>`;
            } else {
                grid_html = `<div class="text-muted" style="padding:20px 0;text-align:center;font-size:12px;">
                    No employees are eligible for payroll processing in the selected period.</div>`;
            }

            wrapper.html(summary + grid_html);

            if (ineligible_list.length > 0) {
                wrapper.find('#btn_view_ineligible').on('click', () =>
                    show_ineligible_employees_dialog(dialog._ineligible_employees, month, year, category_requires_variable_pay));
            }

            if (eligible && eligible.length > 0) {
                const update = () => update_count(wrapper, 'emp-card-check', 'emp_selected_count');
                const bind   = () => { wrapper.find('.emp-card-check').off('change').on('change', update); update(); };

                wrapper.find('#emp_search').on('input', function() {
                    const q = $(this).val().toLowerCase().trim();
                    const all = dialog._card_items['employees_html'];
                    const filtered = q ? all.filter(i => i.id.toLowerCase().includes(q) || i.name.toLowerCase().includes(q)) : all;
                    wrapper.find('#emp_search_grid').html(build_cards(filtered, 'emp-card-check'));
                    bind();
                });

                wrapper.find('#emp_search_select_all').on('click', () => {
                    wrapper.find('.emp-card-check').prop('checked', true); update();
                });
                wrapper.find('#emp_search_deselect_all').on('click', () => {
                    wrapper.find('.emp-card-check').prop('checked', false); update();
                });

                bind();
            }
        }
    });
}

// ─── Ineligible Employees Dialog ──────────────────────────────────────────────

function show_ineligible_employees_dialog(ineligible_list, month, year, show_variable_pay) {

    function parse_reasons(reasons) {
        const f = { no_salary_structure: false, no_variable_pay: false, no_attendance: false };
        (reasons || []).forEach(r => {
            const l = r.toLowerCase();
            if (l.includes('salary structure')) f.no_salary_structure = true;
            if (l.includes('variable pay'))     f.no_variable_pay     = true;
            if (l.includes('attendance'))       f.no_attendance       = true;
        });
        return f;
    }

    const ICON_FAIL = `<span style="display:inline-flex;align-items:center;justify-content:center;
        width:20px;height:20px;border-radius:50%;
        background:var(--red-100,#fde8e8);color:var(--red-500,#e03131);
        font-size:13px;font-weight:700;">&#x2715;</span>`;

    const ICON_OK = `<span style="display:inline-flex;align-items:center;justify-content:center;
        width:20px;height:20px;border-radius:50%;
        background:var(--green-100,#ebfbee);color:var(--green-600,#2f9e44);
        font-size:13px;font-weight:700;">&#x2713;</span>`;

    const total_cols = show_variable_pay ? 4 : 3;

    function build_rows(source) {
        if (!source || !source.length) {
            return `<tr><td colspan="${total_cols}" class="text-muted" style="padding:20px;text-align:center;">No matching employees found.</td></tr>`;
        }
        return source.map((s, idx) => {
            const f  = parse_reasons(s.reasons || []);
            const bg = idx % 2 !== 0 ? 'background:var(--subtle-accent-bg,#f9fafb);' : '';
            return `<tr style="${bg}">
                <td style="padding:8px 10px;border-bottom:1px solid var(--border-color);border-right:1px solid var(--border-color);vertical-align:middle;white-space:nowrap;">
                    <div style="font-size:12px;font-weight:600;color:var(--text-color);">${frappe.utils.escape_html(s.name)}</div>
                    <div style="font-size:11px;color:var(--text-muted);margin-top:1px;">${frappe.utils.escape_html(s.id)}</div>
                </td>
                <td style="padding:8px 10px;border-bottom:1px solid var(--border-color);border-right:1px solid var(--border-color);text-align:center;vertical-align:middle;">${f.no_salary_structure ? ICON_FAIL : ICON_OK}</td>
                ${show_variable_pay ? `<td style="padding:8px 10px;border-bottom:1px solid var(--border-color);border-right:1px solid var(--border-color);text-align:center;vertical-align:middle;">${f.no_variable_pay ? ICON_FAIL : ICON_OK}</td>` : ''}
                <td style="padding:8px 10px;border-bottom:1px solid var(--border-color);text-align:center;vertical-align:middle;">${f.no_attendance ? ICON_FAIL : ICON_OK}</td>
            </tr>`;
        }).join('');
    }

    const th = (label, last) => `<th style="
        position:sticky;top:0;z-index:1;
        padding:8px 10px;text-align:center;font-size:11px;font-weight:600;
        text-transform:uppercase;letter-spacing:0.04em;
        color:var(--text-muted);background:var(--subtle-accent-bg,#f5f6f7);
        border-bottom:2px solid var(--border-color);
        ${last ? '' : 'border-right:1px solid var(--border-color);'}
        white-space:normal;line-height:1.4;">${label}</th>`;

    const legend = `
        <div style="display:flex;align-items:center;gap:16px;margin-bottom:10px;font-size:11px;color:var(--text-muted);">
            <span style="display:flex;align-items:center;gap:5px;">
                <span style="display:inline-flex;align-items:center;justify-content:center;width:18px;height:18px;border-radius:50%;
                    background:var(--red-100,#fde8e8);color:var(--red-500,#e03131);font-size:11px;font-weight:700;">&#x2715;</span>
                Criterion not met
            </span>
            <span style="display:flex;align-items:center;gap:5px;">
                <span style="display:inline-flex;align-items:center;justify-content:center;width:18px;height:18px;border-radius:50%;
                    background:var(--green-100,#ebfbee);color:var(--green-600,#2f9e44);font-size:11px;font-weight:700;">&#x2713;</span>
                Criterion met
            </span>
        </div>`;

    const content = `
        <p style="margin-bottom:12px;font-size:12px;color:var(--text-color);">
            <strong>${ineligible_list.length}</strong> employee(s) have been excluded from payroll processing for
            <strong>${month} ${year}</strong> as they do not meet one or more eligibility criteria.
        </p>
        ${legend}
        <div style="margin-bottom:10px;">
            <input id="ineligible_search" type="text" class="form-control"
                placeholder="Search by name or Employee ID..."
                style="max-width:320px;font-size:12px;">
        </div>
        <div style="border:1px solid var(--border-color);border-radius:var(--border-radius);overflow:hidden;">
            <div style="overflow-x:auto;max-height:400px;overflow-y:auto;">
                <table id="ineligible_table" style="width:100%;border-collapse:collapse;min-width:${show_variable_pay ? '460px' : '360px'};">
                    <thead>
                        <tr>
                            <th style="position:sticky;top:0;z-index:1;padding:8px 10px;text-align:left;
                                font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.04em;
                                color:var(--text-muted);background:var(--subtle-accent-bg,#f5f6f7);
                                border-bottom:2px solid var(--border-color);border-right:1px solid var(--border-color);
                                width:32%;">Employee</th>
                            ${th('Salary Structure<br>Assigned', !show_variable_pay)}
                            ${show_variable_pay ? th('Variable Pay<br>Configured', false) : ''}
                            ${th('Attendance<br>Recorded', true)}
                        </tr>
                    </thead>
                    <tbody id="ineligible_tbody">${build_rows(ineligible_list)}</tbody>
                </table>
            </div>
        </div>`;

    let ineligible_dialog = new frappe.ui.Dialog({
        title: __('Payroll Eligibility Review \u2014 ' + month + ' ' + year),
        size: 'large',
        fields: [{ fieldname: 'ineligible_html', fieldtype: 'HTML' }]
    });

    ineligible_dialog.fields_dict.ineligible_html.$wrapper.html(
        `<div style="padding-bottom:4px;">${content}</div>`
    );
    ineligible_dialog.show();

    ineligible_dialog.fields_dict.ineligible_html.$wrapper.find('#ineligible_search').on('input', function() {
        const q      = $(this).val().toLowerCase().trim();
        const tbody  = ineligible_dialog.fields_dict.ineligible_html.$wrapper.find('#ineligible_tbody');
        const source = q
            ? ineligible_list.filter(s => s.id.toLowerCase().includes(q) || s.name.toLowerCase().includes(q))
            : ineligible_list;
        tbody.html(build_rows(source));
    });
}

function generate_bulk_salary_slips(dialog) {
    const company  = dialog.get_value('company');
    const year     = dialog.get_value('year');
    const month    = dialog.get_value('month');
    const category = dialog.get_value('category');
    const selected = get_checked_ids(dialog, 'employees_html', 'emp-card-check');

    if (!category)        { frappe.msgprint(__('Please select a Category')); return; }
    if (!selected.length) { frappe.msgprint(__('Please select at least one employee to proceed')); return; }

    frappe.confirm(`Are you sure you want to generate salary slips for <b>${selected.length}</b> employee(s)?`, function() {
        dialog.hide();
        frappe.dom.freeze(__('Generating Salary Slips... Please wait...'));

        frappe.call({
            method: 'saral_hr.saral_hr.doctype.salary_slip.salary_slip.bulk_generate_salary_slips',
            args: { employees: selected.map(s => ({ employee: s.id, employee_name: s.name })), year, month },
            callback: function(r) {
                frappe.dom.unfreeze();
                if (r.message) {
                    show_result_dialog(__('Bulk Generation Result'), r.message, 'Successfully Created');
                    if (cur_list) cur_list.refresh();
                }
            },
            error: function() {
                frappe.dom.unfreeze();
                frappe.msgprint({ title: __('Error'), message: __('Failed to generate salary slips. Please try again or contact your system administrator.'), indicator: 'red' });
            }
        });
    });
}

// ─── Bulk Print ───────────────────────────────────────────────────────────────

function show_bulk_print_dialog() {
    let d = new frappe.ui.Dialog({
        title: __('Bulk Print Salary Slips'),
        fields: [
            { fieldname: 'company', fieldtype: 'Link', label: 'Company', options: 'Company', reqd: 1 },
            { fieldname: 'cb1', fieldtype: 'Column Break' },
            { fieldname: 'year', fieldtype: 'Select', label: 'Year', options: get_year_options(), reqd: 1, default: new Date().getFullYear().toString() },
            { fieldname: 'cb2', fieldtype: 'Column Break' },
            { fieldname: 'month', fieldtype: 'Select', label: 'Month', options: MONTHS, reqd: 1, default: get_current_month() },
            { fieldname: 'sb_category', fieldtype: 'Section Break', label: 'Filter by Category' },
            {
                fieldname: 'category',
                fieldtype: 'Link',
                label: 'Category',
                options: 'Category',
                reqd: 1,
                description: 'Only salary slips for employees belonging to this category will be shown.'
            },
            { fieldname: 'sb1', fieldtype: 'Section Break' },
            { fieldname: 'fetch_slips', fieldtype: 'Button', label: 'Fetch Submitted Salary Slips', click: function() { fetch_submitted_salary_slips(d); } },
            { fieldname: 'sb2', fieldtype: 'Section Break' },
            { fieldname: 'slips_html', fieldtype: 'HTML' }
        ],
        primary_action_label: __('Print Selected Slips'),
        primary_action: () => print_selected_salary_slips(d)
    });
    d.show();
}

function fetch_submitted_salary_slips(dialog) {
    const company  = dialog.get_value('company');
    const year     = dialog.get_value('year');
    const month    = dialog.get_value('month');
    const category = dialog.get_value('category');

    if (!company)        { frappe.msgprint(__('Please select Company')); return; }
    if (!year || !month) { frappe.msgprint(__('Please select Year and Month')); return; }
    if (!category)       { frappe.msgprint(__('Please select a Category')); return; }

    const wrapper = dialog.fields_dict.slips_html.$wrapper;
    wrapper.html(`<div class="text-muted" style="padding:16px 0;text-align:center;font-size:12px;">
        ${frappe.utils.icon('loading','xs')} &nbsp;Retrieving submitted salary slips...
    </div>`);

    frappe.call({
        method: 'saral_hr.saral_hr.doctype.salary_slip.salary_slip.get_salary_slips_print_summary',
        args: { company, year, month, category },
        callback: function(r) {
            if (!r.message) {
                wrapper.html('<div class="text-muted" style="padding:16px 0;text-align:center;">Unable to retrieve data. Please try again.</div>');
                return;
            }

            const {
                submitted     = [],
                not_printable = [],
                total_active,
                total_submitted
            } = r.message;

            dialog._not_printable_slips = not_printable;

            const excl_btn = not_printable.length > 0
                ? `<button class="btn btn-default btn-sm" id="btn_view_print_exclusions"
                        style="margin-left:auto;">
                        ${__('View Exclusion Details')} (${not_printable.length})
                   </button>`
                : '';

            const summary = `
                <div style="display:flex;align-items:center;flex-wrap:wrap;gap:16px;
                    padding:8px 0;margin-bottom:12px;font-size:12px;
                    border-bottom:1px solid var(--border-color);">
                    <span style="color:var(--text-muted);">
                        Active Employees <em style="font-size:10px;">(${frappe.utils.escape_html(category)})</em>:
                        <strong style="color:var(--text-color);">${total_active}</strong>
                    </span>
                    <span style="color:var(--border-color);">|</span>
                    <span style="color:var(--text-muted);">
                        Submitted Slips: <strong style="color:var(--text-color);">${total_submitted}</strong>
                    </span>
                    <span style="color:var(--border-color);">|</span>
                    <span style="color:var(--text-muted);">
                        Excluded from Print: <strong style="color:var(--text-color);">${not_printable.length}</strong>
                    </span>
                    ${excl_btn}
                </div>`;

            let grid_html = '';
            if (submitted && submitted.length > 0) {
                const items = submitted.map(s => ({ id: s.name, name: s.employee_name || s.employee }));
                dialog._card_items = dialog._card_items || {};
                dialog._card_items['slips_html'] = items;

                grid_html = `
                    <div style="margin-bottom:10px;display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
                        <input id="slip_search" type="text" class="form-control"
                            placeholder="Search by name or Employee ID..."
                            style="flex:1;min-width:160px;max-width:320px;">
                        <button class="btn btn-xs btn-default" id="slip_search_select_all">${__('Select All')}</button>
                        <button class="btn btn-xs btn-default" id="slip_search_deselect_all">${__('Deselect All')}</button>
                        <span id="slip_selected_count" class="text-muted" style="font-size:12px;">0 selected</span>
                    </div>
                    <div id="slip_search_grid"
                        style="display:flex;flex-wrap:wrap;gap:10px;max-height:380px;overflow-y:auto;padding:4px 2px;">
                        ${build_cards(items, 'slip-card-check')}
                    </div>`;
            } else {
                grid_html = `<div class="text-muted" style="padding:20px;text-align:center;">No submitted salary slips found for the selected payroll period.</div>`;
            }

            wrapper.html(summary + grid_html);

            if (not_printable.length > 0) {
                wrapper.find('#btn_view_print_exclusions').on('click', () =>
                    show_print_exclusions_dialog(dialog._not_printable_slips, month, year));
            }

            if (submitted && submitted.length > 0) {
                const items = dialog._card_items['slips_html'];
                const update = () => update_count(wrapper, 'slip-card-check', 'slip_selected_count');
                const bind   = () => { wrapper.find('.slip-card-check').off('change').on('change', update); update(); };

                wrapper.find('#slip_search').on('input', function() {
                    const q = $(this).val().toLowerCase().trim();
                    const filtered = q ? items.filter(i => i.id.toLowerCase().includes(q) || i.name.toLowerCase().includes(q)) : items;
                    wrapper.find('#slip_search_grid').html(build_cards(filtered, 'slip-card-check'));
                    bind();
                });
                wrapper.find('#slip_search_select_all').on('click', () => { wrapper.find('.slip-card-check').prop('checked', true); update(); });
                wrapper.find('#slip_search_deselect_all').on('click', () => { wrapper.find('.slip-card-check').prop('checked', false); update(); });
                bind();
            }
        }
    });
}

// ─── Print Exclusion Details Dialog ──────────────────────────────────────────

function show_print_exclusions_dialog(not_printable_list, month, year) {

    function slip_status_badge(status) {
        const cfg = {
            'Draft':     { bg: '#fff3cd', color: '#856404', label: 'Draft'     },
            'No Slip':   { bg: '#fde8e8', color: '#e03131', label: 'No Slip'   },
            'Cancelled': { bg: '#f0f0f0', color: '#6c757d', label: 'Cancelled' },
        };
        const s = cfg[status] || { bg: '#f0f0f0', color: '#495057', label: status };
        return `<span style="
            display:inline-block;padding:2px 10px;border-radius:20px;
            font-size:10px;font-weight:700;letter-spacing:0.04em;text-transform:uppercase;
            background:${s.bg};color:${s.color};border:1px solid ${s.color}33;">
            ${s.label}
        </span>`;
    }

    function reason_pill(text) {
        return `<span style="
            display:inline-block;padding:2px 8px;border-radius:4px;margin:2px 2px 2px 0;
            font-size:10px;background:var(--subtle-accent-bg,#f5f6f7);
            color:var(--text-muted,#8d99a6);border:1px solid var(--border-color,#d1d8dd);">
            ${frappe.utils.escape_html(text)}
        </span>`;
    }

    function build_rows(source) {
        if (!source.length) {
            return `<tr><td colspan="4" class="text-muted" style="padding:20px;text-align:center;">No matching employees found.</td></tr>`;
        }
        return source.map((s, idx) => {
            const bg = idx % 2 !== 0 ? 'background:var(--subtle-accent-bg,#f9fafb);' : '';
            const pills = (s.reasons || []).map(reason_pill).join('');
            return `<tr style="${bg}">
                <td style="padding:8px 10px;border-bottom:1px solid var(--border-color);border-right:1px solid var(--border-color);vertical-align:middle;white-space:nowrap;">
                    <div style="font-size:12px;font-weight:600;color:var(--text-color);">${frappe.utils.escape_html(s.employee_name || s.name)}</div>
                    <div style="font-size:11px;color:var(--text-muted);margin-top:1px;">${frappe.utils.escape_html(s.employee)}</div>
                </td>
                <td style="padding:8px 10px;border-bottom:1px solid var(--border-color);border-right:1px solid var(--border-color);text-align:center;vertical-align:middle;">
                    ${s.slip_name
                        ? `<div style="font-size:11px;font-weight:600;color:var(--text-color);">${frappe.utils.escape_html(s.slip_name)}</div>`
                        : `<span style="font-size:11px;color:var(--text-muted);">\u2014</span>`}
                </td>
                <td style="padding:8px 10px;border-bottom:1px solid var(--border-color);border-right:1px solid var(--border-color);text-align:center;vertical-align:middle;">
                    ${slip_status_badge(s.slip_status)}
                </td>
                <td style="padding:8px 10px;border-bottom:1px solid var(--border-color);vertical-align:middle;">
                    <div style="line-height:1.8;">${pills}</div>
                </td>
            </tr>`;
        }).join('');
    }

    const th_left = (label, extra='') => `<th style="
        position:sticky;top:0;z-index:1;
        padding:8px 10px;text-align:left;font-size:11px;font-weight:600;
        text-transform:uppercase;letter-spacing:0.04em;
        color:var(--text-muted);background:var(--subtle-accent-bg,#f5f6f7);
        border-bottom:2px solid var(--border-color);
        border-right:1px solid var(--border-color);
        white-space:normal;line-height:1.4;${extra}">${label}</th>`;

    const th_center = (label, last=false) => `<th style="
        position:sticky;top:0;z-index:1;
        padding:8px 10px;text-align:center;font-size:11px;font-weight:600;
        text-transform:uppercase;letter-spacing:0.04em;
        color:var(--text-muted);background:var(--subtle-accent-bg,#f5f6f7);
        border-bottom:2px solid var(--border-color);
        ${last ? '' : 'border-right:1px solid var(--border-color);'}
        white-space:normal;line-height:1.4;">${label}</th>`;

    const legend = `
        <div style="display:flex;align-items:center;gap:16px;margin-bottom:12px;flex-wrap:wrap;">
            <strong style="color:var(--text-color);font-size:12px;white-space:nowrap;">Status Key:</strong>
            <span style="display:inline-flex;align-items:center;gap:6px;">
                <span style="display:inline-block;padding:2px 10px;border-radius:20px;font-size:10px;font-weight:700;
                    background:#fff3cd;color:#856404;border:1px solid #856404;">Draft</span>
                <span style="font-size:11px;color:var(--text-muted);">Slip exists but not yet submitted</span>
            </span>
            <span style="display:inline-flex;align-items:center;gap:6px;">
                <span style="display:inline-block;padding:2px 10px;border-radius:20px;font-size:10px;font-weight:700;
                    background:#fde8e8;color:#e03131;border:1px solid #e03131;">No Slip</span>
                <span style="font-size:11px;color:var(--text-muted);">Salary slip not created yet</span>
            </span>
            <span style="display:inline-flex;align-items:center;gap:6px;">
                <span style="display:inline-block;padding:2px 10px;border-radius:20px;font-size:10px;font-weight:700;
                    background:#f0f0f0;color:#6c757d;border:1px solid #6c757d;">Cancelled</span>
                <span style="font-size:11px;color:var(--text-muted);">Slip was cancelled</span>
            </span>
        </div>`;

    const content = `
        <p style="margin-bottom:12px;font-size:12px;color:var(--text-color);">
            <strong>${not_printable_list.length}</strong> employee(s) cannot be included in the bulk print for
            <strong>${month} ${year}</strong>. Only <strong>Submitted</strong> salary slips can be printed.
        </p>
        ${legend}
        <div style="margin-bottom:10px;">
            <input id="print_excl_search" type="text" class="form-control"
                placeholder="Search by name or Employee ID..."
                style="max-width:320px;font-size:12px;">
        </div>
        <div style="border:1px solid var(--border-color);border-radius:var(--border-radius);overflow:hidden;">
            <div style="overflow-x:auto;max-height:420px;overflow-y:auto;">
                <table style="width:100%;border-collapse:collapse;min-width:580px;">
                    <thead>
                        <tr>
                            ${th_left('Employee', 'width:28%;')}
                            ${th_center('Salary Slip')}
                            ${th_center('Slip Status')}
                            ${th_center('Reason(s)', true)}
                        </tr>
                    </thead>
                    <tbody id="print_excl_tbody">${build_rows(not_printable_list)}</tbody>
                </table>
            </div>
        </div>`;

    let excl_dialog = new frappe.ui.Dialog({
        title: __('Print Exclusion Review \u2014 ' + month + ' ' + year),
        size: 'large',
        fields: [{ fieldname: 'excl_html', fieldtype: 'HTML' }]
    });

    excl_dialog.fields_dict.excl_html.$wrapper.html(`<div style="padding-bottom:4px;">${content}</div>`);
    excl_dialog.show();

    excl_dialog.fields_dict.excl_html.$wrapper.find('#print_excl_search').on('input', function() {
        const q      = $(this).val().toLowerCase().trim();
        const tbody  = excl_dialog.fields_dict.excl_html.$wrapper.find('#print_excl_tbody');
        const source = q
            ? not_printable_list.filter(s =>
                (s.employee || '').toLowerCase().includes(q) ||
                (s.employee_name || '').toLowerCase().includes(q))
            : not_printable_list;
        tbody.html(build_rows(source));
    });
}

function print_selected_salary_slips(dialog) {
    const selected = get_checked_ids(dialog, 'slips_html', 'slip-card-check');
    if (!selected.length) { frappe.msgprint(__('Please select at least one salary slip to print')); return; }

    frappe.confirm(`Are you sure you want to print <b>${selected.length}</b> salary slip(s)?`, function() {
        dialog.hide();
        frappe.dom.freeze(__('Preparing PDF for printing... Please wait...'));

        frappe.call({
            method: 'saral_hr.saral_hr.doctype.salary_slip.salary_slip.bulk_print_salary_slips',
            args: { salary_slip_names: selected.map(s => s.id) },
            callback: function(r) {
                frappe.dom.unfreeze();
                if (r.message) {
                    window.open(r.message.pdf_url, '_blank');
                    frappe.msgprint({ title: __('Print Ready'), message: `${selected.length} salary slip(s) have been prepared for printing.`, indicator: 'green' });
                }
            },
            error: function() {
                frappe.dom.unfreeze();
                frappe.msgprint({ title: __('Error'), message: __('Failed to generate PDF. Please try again or contact your system administrator.'), indicator: 'red' });
            }
        });
    });
}

// ─── Draft to Submit ──────────────────────────────────────────────────────────

function show_draft_to_submit_dialog() {
    let d = new frappe.ui.Dialog({
        title: __('Submit Draft Salary Slips'),
        fields: [
            { fieldname: 'company', fieldtype: 'Link', label: 'Company', options: 'Company', reqd: 1 },
            { fieldname: 'cb1', fieldtype: 'Column Break' },
            { fieldname: 'year', fieldtype: 'Select', label: 'Year', options: get_year_options(), reqd: 1, default: new Date().getFullYear().toString() },
            { fieldname: 'cb2', fieldtype: 'Column Break' },
            { fieldname: 'month', fieldtype: 'Select', label: 'Month', options: MONTHS, reqd: 1, default: get_current_month() },
            { fieldname: 'sb1', fieldtype: 'Section Break' },
            { fieldname: 'fetch_drafts', fieldtype: 'Button', label: 'Fetch Draft Salary Slips', click: function() { fetch_draft_salary_slips(d); } },
            { fieldname: 'sb2', fieldtype: 'Section Break' },
            { fieldname: 'drafts_html', fieldtype: 'HTML' }
        ],
        primary_action_label: __('Submit Selected Slips'),
        primary_action: () => submit_selected_salary_slips(d)
    });
    d.show();
}

function fetch_draft_salary_slips(dialog) {
    const company = dialog.get_value('company');
    const year    = dialog.get_value('year');
    const month   = dialog.get_value('month');

    if (!company)        { frappe.msgprint(__('Please select Company')); return; }
    if (!year || !month) { frappe.msgprint(__('Please select Year and Month')); return; }

    frappe.call({
        method: 'saral_hr.saral_hr.doctype.salary_slip.salary_slip.get_draft_salary_slips',
        args: { company, year, month },
        callback: function(r) {
            if (r.message && r.message.length) {
                render_card_grid(dialog, 'drafts_html', 'draft-card-check', 'draft_selected_count', 'draft_search',
                    r.message.map(s => ({ id: s.name, name: s.employee_name || s.employee })));
            } else {
                dialog.fields_dict.drafts_html.$wrapper.html(
                    '<div class="text-muted" style="padding:20px;text-align:center;">No draft salary slips found for the selected payroll period.</div>');
            }
        }
    });
}

function submit_selected_salary_slips(dialog) {
    const selected = get_checked_ids(dialog, 'drafts_html', 'draft-card-check');
    if (!selected.length) { frappe.msgprint(__('Please select at least one salary slip to submit')); return; }

    frappe.confirm(`Are you sure you want to submit <b>${selected.length}</b> salary slip(s)? This action cannot be undone.`, function() {
        dialog.hide();
        frappe.dom.freeze(__('Submitting salary slips... Please wait...'));

        frappe.call({
            method: 'saral_hr.saral_hr.doctype.salary_slip.salary_slip.bulk_submit_salary_slips',
            args: { salary_slip_names: selected.map(s => s.id) },
            callback: function(r) {
                frappe.dom.unfreeze();
                if (r.message) {
                    show_result_dialog(__('Bulk Submission Result'), r.message, 'Successfully Submitted');
                    if (cur_list) cur_list.refresh();
                }
            },
            error: function() {
                frappe.dom.unfreeze();
                frappe.msgprint({ title: __('Error'), message: __('Failed to submit salary slips. Please try again or contact your system administrator.'), indicator: 'red' });
            }
        });
    });
}

// ─── Result Dialog ────────────────────────────────────────────────────────────

function show_result_dialog(title, result, success_label) {
    let msg = `
        <table class="table table-bordered" style="margin-bottom:0;">
            <tr><td><strong>${success_label}:</strong></td>
                <td style="color:var(--green);font-weight:bold;">${result.success}</td></tr>
            <tr><td><strong>Failed:</strong></td>
                <td style="color:var(--red);font-weight:bold;">${result.failed}</td></tr>
        </table>`;

    if (result.errors && result.errors.length) {
        msg += '<div style="margin-top:12px;"><strong>Details:</strong><ul style="margin-top:4px;">';
        result.errors.forEach(e => { msg += `<li>${e}</li>`; });
        msg += '</ul></div>';
    }

    frappe.msgprint({ title, message: msg, indicator: result.failed > 0 ? 'orange' : 'green' });
}

// ─── Form Events ──────────────────────────────────────────────────────────────

frappe.ui.form.on("Salary Slip", {
    refresh(frm) {
        if (!frm.doc.currency) {
            frm.set_value("currency", "INR");
        }
        frm.set_query("employee", () => ({
            filters: { is_active: 1 }
        }));
    },

    employee(frm) {
        if (!frm.doc.employee) return;
        reset_form(frm);

        frappe.db.get_value("Company Link", frm.doc.employee, "category", (r) => {
            if (r && r.category) {
                frappe.db.get_value("Category", r.category, "salary_calculation_based_on", (cat) => {
                    if (cat && cat.salary_calculation_based_on) {
                        frm.set_value("working_days_calculation_method", cat.salary_calculation_based_on);
                    }
                    if (frm.doc.start_date) {
                        check_duplicate_and_fetch(frm);
                    }
                });
            } else {
                if (frm.doc.start_date) {
                    check_duplicate_and_fetch(frm);
                }
            }
        });
    },

    start_date(frm) {
        if (!frm.doc.start_date) return;
        set_end_date(frm);
        if (frm.doc.employee) {
            check_duplicate_and_fetch(frm);
        }
    },

    working_days_calculation_method(frm) {
        if (!frm.doc.employee || !frm.doc.start_date) return;
        frappe.call({
            method: "saral_hr.saral_hr.doctype.salary_slip.salary_slip.get_attendance_and_days",
            args: {
                employee: frm.doc.employee,
                start_date: frm.doc.start_date,
                working_days_calculation_method: frm.doc.working_days_calculation_method
            },
            callback(r) {
                if (!r.message) return;
                apply_attendance(frm, r.message);
            }
        });
    }
});

frappe.ui.form.on("Salary Details", {
    amount(frm)           { recalculate_salary(frm); },
    earnings_remove(frm)  { recalculate_salary(frm); },
    deductions_remove(frm){ recalculate_salary(frm); }
});

// ─── Core Form Functions ──────────────────────────────────────────────────────

function check_duplicate_and_fetch(frm) {
    frappe.call({
        method: "saral_hr.saral_hr.doctype.salary_slip.salary_slip.check_duplicate_salary_slip",
        args: {
            employee:    frm.doc.employee,
            start_date:  frm.doc.start_date,
            current_doc: frm.doc.name || ""
        },
        callback(r) {
            if (r.message && r.message.status === "duplicate") {
                frappe.msgprint({
                    title:   __("Duplicate Salary Slip"),
                    message: r.message.message,
                    indicator: "red"
                });
                frm.set_value("start_date", "");
                return;
            }
            fetch_and_validate_all(frm);
        }
    });
}

function set_end_date(frm) {
    const start = frappe.datetime.str_to_obj(frm.doc.start_date);
    const end   = new Date(start.getFullYear(), start.getMonth() + 1, 0);
    frm.set_value("end_date", frappe.datetime.obj_to_str(end));
}

function fetch_and_validate_all(frm) {
    frm.page.btn_primary.prop("disabled", false);
    frm.clear_table("earnings");
    frm.clear_table("deductions");

    let salary_data     = null;
    let attendance_data = null;
    let vpa_status      = null;
    let vpa_percentage  = 0;
    let additional_data = { earnings: [], deductions: [] };

    // pending covers: salary, vpa_check, attendance, additional_components
    // (vpa_check may fire a 5th nested call and bump pending to 5 before decrementing)
    let pending = 4;

    function try_finalize() {
        if (--pending > 0) return;

        const unmet = [];

        if (!salary_data) {
            unmet.push("No Salary Structure has been assigned for the selected payroll period.");
        }
        if (vpa_status && vpa_status.status === "missing") {
            unmet.push(vpa_status.message.replace(/<[^>]+>/g, ""));
        }
        if (!attendance_data) {
            unmet.push("Attendance data could not be retrieved for the selected period. Please verify attendance records.");
        } else if (attendance_data.attendance_count === 0) {
            unmet.push("No attendance has been recorded for this employee in the selected month.");
        }

        if (unmet.length > 0) {
            const bullets = unmet
                .map(e => `<li style="margin-bottom:6px;">${e}</li>`)
                .join("");
            frappe.msgprint({
                title:   __("Payroll Processing Requirements Not Met"),
                message: `
                    <div style="margin-bottom:8px;font-weight:600;">
                        Please resolve the following before saving this salary slip:
                    </div>
                    <ul style="margin:0;padding-left:18px;line-height:1.7;">${bullets}</ul>
                `,
                indicator: "red"
            });
            frm.page.btn_primary.prop("disabled", true);
            return;
        }

        apply_salary_structure(frm, salary_data);

        // ── Inject additional earnings at end of earnings table ───────────────
        (additional_data.earnings || []).forEach(row => {
            const e = frm.add_child("earnings");
            e.salary_component                 = row.salary_component;
            e.abbr                             = row.abbr;
            e.amount                           = flt(row.amount);
            e.base_amount                      = flt(row.amount);
            e.depends_on_payment_days          = row.depends_on_payment_days || 0;
            e.is_daily_rate                    = row.is_daily_rate || 0;
            e.depends_on_physical_working_days = row.depends_on_physical_working_days || 0;
            e.is_special_component             = row.is_special_component || 0;
        });

        // ── Inject additional deductions at end of deductions table ───────────
        (additional_data.deductions || []).forEach(row => {
            const d = frm.add_child("deductions");
            d.salary_component                 = row.salary_component;
            d.abbr                             = row.abbr;
            d.amount                           = flt(row.amount);
            d.base_amount                      = flt(row.amount);
            d.employer_contribution            = row.employer_contribution || 0;
            d.depends_on_payment_days          = row.depends_on_payment_days || 0;
            d.is_daily_rate                    = row.is_daily_rate || 0;
            d.depends_on_physical_working_days = row.depends_on_physical_working_days || 0;
            d.is_special_component             = row.is_special_component || 0;
        });

        frm.refresh_fields(["earnings", "deductions"]);

        apply_attendance(frm, attendance_data, flt(vpa_percentage) / 100);
        frm.page.btn_primary.prop("disabled", false);
    }

    // ── Call 1: salary structure ──────────────────────────────────────────────
    frappe.call({
        method: "saral_hr.saral_hr.doctype.salary_slip.salary_slip.get_salary_structure_for_employee",
        args: { employee: frm.doc.employee, start_date: frm.doc.start_date },
        callback(r) { salary_data = r.message || null; try_finalize(); },
        error()     { salary_data = null; try_finalize(); }
    });

    // ── Call 2: variable pay check (may fire a nested call 5) ────────────────
    frappe.call({
        method: "saral_hr.saral_hr.doctype.salary_slip.salary_slip.check_variable_pay_assignment",
        args: { employee: frm.doc.employee, start_date: frm.doc.start_date },
        callback(r) {
            vpa_status = r.message || { status: "ok" };
            if (vpa_status.status === "ok") {
                pending++;   // bump BEFORE issuing nested call
                frappe.call({
                    method: "saral_hr.saral_hr.doctype.salary_slip.salary_slip.get_variable_pay_percentage",
                    args: { employee: frm.doc.employee, start_date: frm.doc.start_date },
                    callback(vr) { vpa_percentage = flt(vr.message || 0); try_finalize(); },
                    error()      { vpa_percentage = 0; try_finalize(); }
                });
            }
            try_finalize();
        },
        error() { vpa_status = { status: "ok" }; try_finalize(); }
    });

    // ── Call 3: attendance ────────────────────────────────────────────────────
    frappe.call({
        method: "saral_hr.saral_hr.doctype.salary_slip.salary_slip.get_attendance_and_days",
        args: {
            employee:    frm.doc.employee,
            start_date:  frm.doc.start_date,
            working_days_calculation_method: frm.doc.working_days_calculation_method
        },
        callback(r) { attendance_data = r.message || null; try_finalize(); },
        error()     { attendance_data = null; try_finalize(); }
    });

    // ── Call 4: additional salary & deduction components ─────────────────────
    frappe.call({
        method: "saral_hr.saral_hr.doctype.salary_slip.salary_slip.get_additional_components_api",
        args: { employee: frm.doc.employee, start_date: frm.doc.start_date },
        callback(r) {
            additional_data = r.message || { earnings: [], deductions: [] };
            try_finalize();
        },
        error() {
            additional_data = { earnings: [], deductions: [] };
            try_finalize();
        }
    });
}

// ─── Helpers to Apply Fetched Data ───────────────────────────────────────────

function apply_salary_structure(frm, data) {
    frm.set_value("salary_structure", data.salary_structure);
    frm.clear_table("earnings");
    frm.clear_table("deductions");

    (data.earnings || []).forEach(row => {
        const e = frm.add_child("earnings");
        Object.assign(e, row);
        e.base_amount = row.base_amount !== undefined ? row.base_amount : row.amount;
    });

    (data.deductions || []).forEach(row => {
        const d = frm.add_child("deductions");
        Object.assign(d, row);
        d.base_amount = row.base_amount !== undefined ? row.base_amount : row.amount;
    });

    frm.refresh_fields(["earnings", "deductions"]);
}

function apply_attendance(frm, d, variable_pay_pct) {
    frm.set_value({
        total_working_days:    d.working_days,
        payment_days:          d.payment_days,
        physical_working_days: d.physical_working_days || 0,
        present_days:          d.present_days,
        absent_days:           d.absent_days,
        weekly_offs_count:     d.weekly_offs,
        total_half_days:       d.total_half_days,
        total_lwp:             d.total_lwp            || 0,
        total_holidays:        d.total_holidays       || 0,
        total_earned_leaves:   d.total_earned_leaves  || 0,
        total_casual_leaves:   d.total_casual_leaves  || 0
    });

    if (variable_pay_pct !== undefined) {
        frm.variable_pay_percentage = variable_pay_pct;
    }

    recalculate_salary(frm, d.working_days, d.payment_days, d.physical_working_days);
}

// ─── Salary Calculation ───────────────────────────────────────────────────────

function recalculate_salary(frm, wd_override, pd_override, phd_override) {
    let total_earnings              = 0;
    let total_deductions            = 0;
    let total_basic_da              = 0;
    let total_employer_contribution = 0;
    let retention                   = 0;

    const wd           = flt(wd_override  !== undefined ? wd_override  : frm.doc.total_working_days);
    const pd           = flt(pd_override  !== undefined ? pd_override  : frm.doc.payment_days);
    const phd          = flt(phd_override !== undefined ? phd_override : frm.doc.physical_working_days);
    const variable_pct = flt(frm.variable_pay_percentage || 0);

    const PF_MAX = 1800;

    let basic_amount = 0;
    let da_amount    = 0;

    // ── Pass 1: compute all earnings first so gross is known for ESIC/PF ─────
    (frm.doc.earnings || []).forEach(row => {
        const base = flt(
            (row.base_amount !== null && row.base_amount !== undefined)
                ? row.base_amount
                : ((row.amount !== null && row.amount !== undefined) ? row.amount : 0)
        );
        row.base_amount = base;

        let amount = 0;
        const comp = (row.salary_component || "").toLowerCase();

        if (comp.includes("variable")) {
            if (pd === 0) {
                amount = 0;
            } else if (wd > 0 && row.depends_on_payment_days) {
                amount = (base / wd) * pd * variable_pct;
            } else {
                amount = base * variable_pct;
            }

        } else if (row.depends_on_physical_working_days && wd > 0) {
            amount = base * phd;

        } else if (row.is_daily_rate) {
            amount = base * pd;

        } else if (row.depends_on_payment_days && wd > 0) {
            amount = (base / wd) * pd;

        } else {
            // Fixed amount — includes additional salary components
            amount = base;
        }

        row.amount      = flt(amount, 2);
        total_earnings += row.amount;

        if (comp.includes("basic"))
            basic_amount = row.amount;

        if (is_da_component(row.salary_component, row.abbr))
            da_amount = row.amount;
    });

    total_basic_da = basic_amount + da_amount;

    // ── Pass 2: compute deductions using final gross salary ───────────────────
    (frm.doc.deductions || []).forEach(row => {
        const base = flt(
            (row.base_amount !== null && row.base_amount !== undefined)
                ? row.base_amount
                : ((row.amount !== null && row.amount !== undefined) ? row.amount : 0)
        );
        row.base_amount = base;

        let amount = 0;
        const comp = (row.salary_component || "").toLowerCase();

        if (comp.includes("esic") && !comp.includes("employer")) {
            amount = (base === 0 || total_earnings >= 21000)
                ? 0
                : flt(total_earnings * 0.0075, 2);

        } else if (comp.includes("esic") && comp.includes("employer")) {
            amount = (base === 0 || total_earnings >= 21000)
                ? 0
                : flt(total_earnings * 0.0325, 2);

        } else if (comp.includes("pf") || comp.includes("provident")) {
            amount = base === 0 ? 0 : Math.min(flt(total_earnings * 0.12, 2), PF_MAX);

        } else if (row.depends_on_physical_working_days && wd > 0 && base > 0) {
            amount = base * phd;

        } else if (row.is_daily_rate) {
            amount = base * pd;

        } else if (row.depends_on_payment_days && wd > 0 && base > 0) {
            amount = (base / wd) * pd;

        } else {
            // Fixed amount — includes additional deduction components
            amount = base;
        }

        row.amount = flt(amount, 2);

        if (row.employer_contribution) {
            total_employer_contribution += row.amount;
        } else {
            total_deductions += row.amount;
        }

        if (comp.includes("retention")) retention += row.amount;
    });

    frm.set_value({
        total_earnings:              flt(total_earnings, 2),
        total_deductions:            flt(total_deductions, 2),
        net_salary:                  flt(total_earnings - total_deductions, 2),
        total_basic_da:              flt(total_basic_da, 2),
        total_employer_contribution: flt(total_employer_contribution, 2),
        retention:                   flt(retention, 2)
    });

    frm.refresh_fields(["earnings", "deductions"]);
}

function reset_form(frm) {
    frm.clear_table("earnings");
    frm.clear_table("deductions");

    frm.set_value({
        total_working_days:          0,
        payment_days:                0,
        physical_working_days:       0,
        present_days:                0,
        absent_days:                 0,
        weekly_offs_count:           0,
        total_half_days:             0,
        total_lwp:                   0,
        total_holidays:              0,
        total_earned_leaves:         0,
        total_casual_leaves:         0,
        total_earnings:              0,
        total_deductions:            0,
        net_salary:                  0,
        total_basic_da:              0,
        total_employer_contribution: 0,
        retention:                   0,
        working_days_calculation_method: ""
    });

    frm.variable_pay_percentage = 0;
    frm.page.btn_primary.prop("disabled", false);
    frm.refresh_fields();
}