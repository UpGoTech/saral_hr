// ─── Debounce timers ──────────────────────────────────────────────────────────
let _ctc_timer        = null;
let _ctc_monthly_timer = null;
let _ctc_frm_ref      = null;
let _ctc_syncing      = false;

frappe.ui.form.on('Ctc Calculator Record', {

    refresh(frm) {
        _ctc_frm_ref = frm;
        _apply_styles(frm);
        _render_statutory_info(frm);
        const has_data = frm.doc.earnings_json && frm.doc.earnings_json !== '[]';
        if (has_data) {
            setTimeout(() => _render_ui(frm), 150);
        }
    },

    include_pf(frm)        { _render_statutory_info(frm); _recalculate(frm); },
    include_esic(frm)      { _render_statutory_info(frm); _recalculate(frm); },
    include_pt(frm)        { _render_statutory_info(frm); _recalculate(frm); },
    include_retention(frm) { _render_statutory_info(frm); _recalculate(frm); },
    pf_type(frm)           { if (frm.doc.include_pf) _recalculate(frm); },
    month(frm)             { if (frm.doc.include_pt) _recalculate(frm); }, // ✅ NEW

    annual_ctc(frm) {
        if (_ctc_syncing) return;
        clearTimeout(_ctc_timer);
        _ctc_timer = setTimeout(() => {
            const annual = frm.doc.annual_ctc || 0;
            if (annual > 0) {
                _ctc_syncing = true;
                frm.set_value('monthly_ctc_input', _r2(annual / 12));
                _ctc_syncing = false;
            }
            if (annual > 0 && frm.doc.company && frm.doc.salary_structure)
                _recalculate(frm);
        }, 600);
    },

    monthly_ctc_input(frm) {
        if (_ctc_syncing) return;
        clearTimeout(_ctc_monthly_timer);
        _ctc_monthly_timer = setTimeout(() => {
            const monthly = frm.doc.monthly_ctc_input || 0;
            if (monthly > 0) {
                const annual = _r2(monthly * 12);
                _ctc_syncing = true;
                frm.set_value('annual_ctc', annual);
                _ctc_syncing = false;
                if (frm.doc.company && frm.doc.salary_structure)
                    _recalculate(frm);
            }
        }, 600);
    },

    company(frm) {
        _render_statutory_info(frm);
        if (frm.doc.annual_ctc > 0 && frm.doc.salary_structure) _recalculate(frm);
    },
    salary_structure(frm) {
        if (frm.doc.annual_ctc > 0 && frm.doc.company) _recalculate(frm);
    },
});

$(document).on('frappe.form.refresh', function() {
    if (_ctc_frm_ref) {
        const has_data = _ctc_frm_ref.doc.earnings_json &&
                         _ctc_frm_ref.doc.earnings_json !== '[]';
        if (has_data) setTimeout(() => _render_ui(_ctc_frm_ref), 200);
    }
});

function _get_container(frm) {
    const inner_selectors = ['.form-layout', '.form-page', '.layout-main-section', '.page-content'];
    for (const sel of inner_selectors) {
        const $el = $(frm.wrapper).find(sel);
        if ($el.length) return $el.last();
    }
    const outer_selectors = ['.layout-main-section', '.form-layout', '.page-content'];
    for (const sel of outer_selectors) {
        const $el = $(sel).last();
        if ($el.length) return $el;
    }
    return $(frm.wrapper);
}

function _r2(v)  { return Math.round((parseFloat(v)||0)*100)/100; }
function _r0(v)  { return Math.round(parseFloat(v)||0); }
function _fmt(n) {
    return '\u20B9\u00A0' + (parseFloat(n)||0).toLocaleString('en-IN',
        {minimumFractionDigits:2, maximumFractionDigits:2});
}
function _current_month() {
    return ['January','February','March','April','May','June','July',
            'August','September','October','November','December'][new Date().getMonth()];
}
function _get_data(frm, field) {
    try { return JSON.parse(frm.doc[field] || '[]'); } catch(e) { return []; }
}
function _save_data(frm, field, data) {
    frappe.model.set_value(frm.doctype, frm.docname, field, JSON.stringify(data));
}

// ─── Statutory info boxes ─────────────────────────────────────────────────────
function _render_statutory_info(frm) {
    $(frm.wrapper).find('.ctc-stat-wrap').remove();
    $('.ctc-stat-wrap').remove();

    const d = frm.doc;
    if (!d.include_pf && !d.include_esic && !d.include_pt && !d.include_retention) return;
    if (!d.company) return;

    frappe.call({
        method: 'saral_hr.saral_hr.doctype.ctc_calculator_record.ctc_calculator_record.get_company_statutory_config',
        args: { company: d.company },
        callback(r) {
            const cfg = r.message || {};
            _build_statutory_boxes(frm, cfg);
        }
    });
}

function _build_statutory_boxes(frm, cfg) {
    $(frm.wrapper).find('.ctc-stat-wrap').remove();
    $('.ctc-stat-wrap').remove();

    const d = frm.doc;
    const pf_limit   = cfg.pf_wage_limit             || 15000;
    const pf_emp     = cfg.pf_employee_percent        || 12;
    const pf_epf     = cfg.pf_employer_epf            || 3.67;
    const pf_eps     = cfg.pf_employer_eps            || 8.33;
    const pf_edli    = cfg.pf_edli_insurance          || 0.5;
    const pf_adm     = cfg.pf_admin_charges           || 0.5;
    const esic_limit = cfg.esic_wage_limit            || 21000;
    const esic_emp   = cfg.esic_employee_contribution || 0.75;
    const esic_emr   = cfg.esic_employer_contribution || 3.25;
    const cur_pf_type = d.pf_type || '';
    const sel_month  = d.month || _current_month();
    const pt_amt     = sel_month === 'February' ? '₹300' : '₹200';

    let boxes = '';

    if (d.include_pf) {
        const cap_note = cur_pf_type === 'Full PF'
            ? 'Full PF &mdash; no wage cap'
            : `Limited PF &mdash; wage capped at \u20B9${Number(pf_limit).toLocaleString('en-IN')}`;
        boxes += `
        <div class="ctc-stat-box ctc-stat-pf">
            <div class="ctc-stat-hdr">
                <span class="ctc-dot ctc-dot-blue"></span>
                <strong>INCLUDE PF</strong>
            </div>
            <div class="ctc-stat-lines">
                <div>Emp PF: wage &times; ${pf_emp}%</div>
                <div>ERPF &times; ${pf_epf}% &nbsp;&middot;&nbsp; EPS &times; ${pf_eps}%</div>
                <div>EDLI &times; ${pf_edli}% &nbsp;&middot;&nbsp; Admin &times; ${pf_adm}%</div>
                <div class="ctc-stat-note">${cap_note}</div>
            </div>
        </div>`;
    }

    if (d.include_esic) {
        boxes += `
        <div class="ctc-stat-box ctc-stat-esic">
            <div class="ctc-stat-hdr">
                <span class="ctc-dot ctc-dot-teal"></span>
                <strong>INCLUDE ESIC</strong>
            </div>
            <div class="ctc-stat-lines">
                <div>Emp ${esic_emp}% &nbsp;&middot;&nbsp; Employer ${esic_emr}% of Gross</div>
                <div class="ctc-stat-note">Applicable if Gross &le; \u20B9${Number(esic_limit).toLocaleString('en-IN')}/month</div>
            </div>
        </div>`;
    }

    if (d.include_pt) {
        boxes += `
        <div class="ctc-stat-box ctc-stat-pt">
            <div class="ctc-stat-hdr">
                <span class="ctc-dot ctc-dot-orange"></span>
                <strong>INCLUDE PT</strong>
            </div>
            <div class="ctc-stat-lines">
                <div>${pt_amt}/month for <b>${sel_month}</b></div>
                <div class="ctc-stat-note">\u20B9200/month (\u20B9300 in February)</div>
            </div>
        </div>`;
    }

    if (d.include_retention) {
        boxes += `
        <div class="ctc-stat-box ctc-stat-ret">
            <div class="ctc-stat-hdr">
                <span class="ctc-dot ctc-dot-purple"></span>
                <strong>INCLUDE RETENTION</strong>
            </div>
            <div class="ctc-stat-lines">
                <div>Basic+DA &times; 2%</div>
                <div class="ctc-stat-note">Deducted from employee salary</div>
            </div>
        </div>`;
    }

    const $wrap = $(`<div class="ctc-stat-wrap">${boxes}</div>`);
    const $root = $(frm.wrapper).find('.ctc-ui-root');
    if ($root.length) {
        $root.before($wrap);
    } else {
        _get_container(frm).append($wrap);
    }
}

// ─── Recalculate ──────────────────────────────────────────────────────────────
function _recalculate(frm) {
    const d = frm.doc;
    if (!d.company || !d.salary_structure || !d.annual_ctc) return;

    let $root = $(frm.wrapper).find('.ctc-ui-root');
    if (!$root.length) {
        $root = $('<div class="ctc-ui-root" style="padding:0 15px 24px;"></div>');
        let $target = $(frm.wrapper).find('.form-layout');
        if (!$target.length) $target = $(frm.wrapper).find('.form-page');
        if (!$target.length) $target = $('.layout-main-section').last();
        if (!$target.length) $target = $(frm.wrapper);
        $target.append($root);
    }

    frappe.call({
        method: 'saral_hr.saral_hr.doctype.ctc_calculator_record.ctc_calculator_record.calculate_ctc_breakdown',
        args: {
            company:           d.company,
            salary_structure:  d.salary_structure,
            annual_ctc:        d.annual_ctc,
            month:             d.month || _current_month(), // ✅ from form field
            include_pf:        d.include_pf        ? "1" : "0",
            include_esic:      d.include_esic      ? "1" : "0",
            include_pt:        d.include_pt        ? "1" : "0",
            include_retention: d.include_retention ? "1" : "0",
            pf_type:           d.pf_type           || "",
        },
        callback(r) {
            if (r.message) _populate(frm, r.message);
        },
        error() {
            $(frm.wrapper).find('.ctc-ui-root').html(
                '<div class="ctc-error">Calculation failed. Check console for details.</div>'
            );
        }
    });
}

// ─── Populate ─────────────────────────────────────────────────────────────────
function _populate(frm, data) {
    const gross = data.gross || 0;

    const earnings = (data.earnings || []).map(r => ({
        salary_component: r.salary_component,
        amount:           _r2(r.amount),
        percentage:       gross ? _r2(r.amount / gross * 100) : 0,
        is_variable:      r.is_variable || false,
        is_others:        r.is_others   || false,
    }));

    const deductions = (data.deductions || []).map(r => ({
        salary_component: r.salary_component,
        amount:           _r2(r.amount),
        percentage:       gross ? _r2(r.amount / gross * 100) : 0,
        statutory:        r.statutory || false,
    }));

    const employer_share = (data.employer_share || []).map(r => ({
        salary_component: r.salary_component,
        amount:           _r2(r.amount),
        percentage:       gross ? _r2(r.amount / gross * 100) : 0,
        in_ctc:           r.in_ctc !== false,
    }));

    _save_data(frm, 'earnings_json',       earnings);
    _save_data(frm, 'deductions_json',     deductions);
    _save_data(frm, 'employer_share_json', employer_share);

    const total_ded = _r2(deductions.reduce((s,r) => s + r.amount, 0));

    frm.set_value('monthly_ctc',      data.monthly_ctc);
    frm.set_value('gross_salary',     gross);
    frm.set_value('total_deductions', total_ded);
    frm.set_value('net_salary',       _r0(gross - total_ded));

    if (!_ctc_syncing) {
        _ctc_syncing = true;
        frm.set_value('monthly_ctc_input', _r2(data.monthly_ctc || 0));
        _ctc_syncing = false;
    }

    _render_ui(frm);
}

// ─── Render UI ────────────────────────────────────────────────────────────────
function _render_ui(frm) {
    const d          = frm.doc;
    const earnings   = _get_data(frm, 'earnings_json');
    const deductions = _get_data(frm, 'deductions_json');
    const employer   = _get_data(frm, 'employer_share_json');
    const annual     = d.annual_ctc           || 0;
    const monthly    = d.monthly_ctc_input    || _r2(annual / 12);
    const gross      = d.gross_salary         || 0;
    const total_ded  = d.total_deductions     || 0;
    const net        = d.net_salary           || 0;
    const total_emp  = _r2(employer.filter(r=>r.in_ctc).reduce((s,r)=>s+r.amount, 0));

    if (!earnings.length && !deductions.length && !employer.length) {
        $(frm.wrapper).find('.ctc-ui-root').html('');
        return;
    }

    const kpi = `
    <div class="ctc-kpi-row">
        <div class="ctc-kpi ctc-kpi-purple"><div class="ctc-kpi-val">${_fmt(annual)}</div><div class="ctc-kpi-lbl">ANNUAL CTC</div></div>
        <div class="ctc-kpi ctc-kpi-blue">  <div class="ctc-kpi-val">${_fmt(monthly)}</div><div class="ctc-kpi-lbl">MONTHLY CTC</div></div>
        <div class="ctc-kpi ctc-kpi-teal">  <div class="ctc-kpi-val">${_fmt(gross)}</div><div class="ctc-kpi-lbl">MONTHLY GROSS</div></div>
        <div class="ctc-kpi ctc-kpi-coral"> <div class="ctc-kpi-val ctc-upd-ded">${_fmt(total_ded)}</div><div class="ctc-kpi-lbl">DEDUCTIONS</div></div>
        <div class="ctc-kpi ctc-kpi-green"> <div class="ctc-kpi-val ctc-upd-net">${_fmt(net)}</div><div class="ctc-kpi-lbl">NET SALARY</div></div>
    </div>`;

    const _rows = (rows, tbl, cls) => rows.map((r, i) => `
    <tr data-i="${i}" data-tbl="${tbl}" data-gross="${gross}">
        <td class="ctc-td-name">
            ${frappe.utils.escape_html(r.salary_component)}
            ${r.is_variable?'<span class="ctc-tag ctc-tag-var">Variable</span>':''}
            ${r.is_others  ?'<span class="ctc-tag ctc-tag-oth">Remainder</span>':''}
            ${r.in_ctc===false?'<span class="ctc-tag ctc-tag-excl">Excl.</span>':''}
        </td>
        <td class="ctc-td-pct">
            <div class="ctc-inp-grp">
                <input class="ctc-pct" type="number" value="${r.percentage}" min="0" step="0.01"
                    ${r.statutory?'readonly':''}/>
                <span class="ctc-pct-sym">%</span>
            </div>
        </td>
        <td class="ctc-td-amt">
            <input class="ctc-amt ${cls}" type="number" value="${r.amount}" min="0" step="1"
                ${r.statutory?'readonly':''}/>
        </td>
    </tr>`).join('');

    const breakdown = `
    <div class="ctc-cols">
        <div class="ctc-card ctc-card-earn">
            <div class="ctc-card-hdr">
                <span class="ctc-card-ttl ctc-ttl-earn">EARNINGS</span>
                <span class="ctc-earn-total ctc-card-sum">${_fmt(gross)}</span>
            </div>
            <table class="ctc-tbl">
                <thead><tr><th class="ctc-th-n">Component</th><th class="ctc-th-p">%</th><th class="ctc-th-a">Amount (₹)</th></tr></thead>
                <tbody>${_rows(earnings,'earnings_json','ctc-c-earn')||'<tr><td colspan="3" class="ctc-nil">No earnings</td></tr>'}</tbody>
            </table>
        </div>

        <div class="ctc-card ctc-card-ded">
            <div class="ctc-card-hdr">
                <span class="ctc-card-ttl ctc-ttl-ded">EMPLOYEE DEDUCTIONS</span>
                <span class="ctc-ded-total ctc-card-sum">${_fmt(total_ded)}</span>
            </div>
            <table class="ctc-tbl">
                <thead><tr><th class="ctc-th-n">Component</th><th class="ctc-th-p">%</th><th class="ctc-th-a">Amount (₹)</th></tr></thead>
                <tbody>${_rows(deductions,'deductions_json','ctc-c-ded')||'<tr><td colspan="3" class="ctc-nil">No deductions</td></tr>'}</tbody>
            </table>
        </div>

        <div class="ctc-card ctc-card-emp">
            <div class="ctc-card-hdr">
                <span class="ctc-card-ttl ctc-ttl-emp">EMPLOYER SHARE</span>
                <span class="ctc-emp-total ctc-card-sum">${_fmt(total_emp)}</span>
            </div>
            <table class="ctc-tbl">
                <thead><tr><th class="ctc-th-n">Component</th><th class="ctc-th-p">%</th><th class="ctc-th-a">Amount (₹)</th></tr></thead>
                <tbody>${_rows(employer,'employer_share_json','ctc-c-emp')||'<tr><td colspan="3" class="ctc-nil">No employer share</td></tr>'}</tbody>
            </table>
        </div>
    </div>

    <div class="ctc-summary-bar">
        <div class="ctc-sum-item">
            <span class="ctc-sum-lbl">Gross Total</span>
            <span class="ctc-earn-total ctc-sum-val">${_fmt(gross)}</span>
        </div>
        <div class="ctc-sum-item">
            <span class="ctc-sum-lbl">Total Deductions</span>
            <span class="ctc-ded-total ctc-upd-ded ctc-sum-val">${_fmt(total_ded)}</span>
        </div>
        <div class="ctc-sum-item">
            <span class="ctc-sum-lbl">Employer Share</span>
            <span class="ctc-emp-total ctc-sum-val">${_fmt(total_emp)}</span>
        </div>
    </div>`;

    const _inject = () => {
        let $root = $(frm.wrapper).find('.ctc-ui-root');
        if (!$root.length) {
            $root = $('<div class="ctc-ui-root" style="padding:0 15px 24px;"></div>');
            let $target = $(frm.wrapper).find('.form-layout');
            if (!$target.length) $target = $(frm.wrapper).find('.form-page');
            if (!$target.length) $target = $('.layout-main-section').last();
            if (!$target.length) $target = $(frm.wrapper);
            $target.append($root);
        }
        $root.html(kpi + breakdown);
        _bind(frm);
    };

    setTimeout(_inject, 100);
}

// ─── Two-way sync ─────────────────────────────────────────────────────────────
function _bind(frm) {
    const $root = $(frm.wrapper).find('.ctc-ui-root');
    $root.off('.ctc')
    .on('change.ctc', '.ctc-amt', function() {
        const $tr   = $(this).closest('tr');
        const i     = parseInt($tr.data('i'));
        const tbl   = $tr.data('tbl');
        const gross = parseFloat($tr.data('gross')) || 0;
        const amt   = parseFloat($(this).val()) || 0;
        const pct   = gross ? _r2(amt / gross * 100) : 0;
        $tr.find('.ctc-pct').val(pct);
        _upd(frm, tbl, i, amt, pct);
        _totals(frm);
    })
    .on('change.ctc', '.ctc-pct', function() {
        const $tr   = $(this).closest('tr');
        const i     = parseInt($tr.data('i'));
        const tbl   = $tr.data('tbl');
        const gross = parseFloat($tr.data('gross')) || 0;
        const pct   = parseFloat($(this).val()) || 0;
        const amt   = _r2(pct / 100 * gross);
        $tr.find('.ctc-amt').val(amt);
        _upd(frm, tbl, i, amt, pct);
        _totals(frm);
    });
}

function _upd(frm, tbl, i, amt, pct) {
    const data = _get_data(frm, tbl);
    if (data[i]) { data[i].amount = amt; data[i].percentage = pct; }
    _save_data(frm, tbl, data);
}

function _totals(frm) {
    const $root = $(frm.wrapper).find('.ctc-ui-root');
    const gross = frm.doc.gross_salary || 0;

    let ded = 0;
    $root.find('[data-tbl="deductions_json"] .ctc-amt').each(function() { ded += parseFloat($(this).val())||0; });
    ded = _r2(ded);
    const net = _r0(gross - ded);

    $root.find('.ctc-ded-total').text(_fmt(ded));
    $root.find('.ctc-ded-disp').text(_fmt(ded));
    $root.find('.ctc-net-disp').text(_fmt(net));
    $root.find('.ctc-upd-ded').text(_fmt(ded));
    $root.find('.ctc-upd-net').text(_fmt(net));

    const emp = _get_data(frm, 'employer_share_json');
    const emp_total = _r2(emp.filter(r=>r.in_ctc).reduce((s,r)=>s+r.amount,0));
    $root.find('.ctc-emp-total').text(_fmt(emp_total));

    frm.set_value('total_deductions', ded);
    frm.set_value('net_salary', net);
}

// ─── Styles ───────────────────────────────────────────────────────────────────
function _apply_styles(frm) {
    if ($('#ctc-sty').length) return;
    $('head').append(`<style id="ctc-sty">
.ctc-loading{display:flex;align-items:center;gap:12px;padding:32px 16px;color:var(--text-muted);font-size:13px;}
.ctc-spinner{width:18px;height:18px;border:2px solid var(--border-color);border-top-color:var(--primary,#5e64ff);border-radius:50%;animation:ctc-spin .7s linear infinite;flex-shrink:0;}
@keyframes ctc-spin{to{transform:rotate(360deg);}}
.ctc-error{padding:16px;color:#c92a2a;font-size:13px;background:#fff5f5;border-radius:8px;border:1px solid #ffc9c9;}

.ctc-stat-wrap{display:flex;gap:14px;flex-wrap:wrap;margin:10px 0 16px;padding:0 15px;}
.ctc-stat-box{flex:1;min-width:200px;border:1px solid var(--border-color);border-radius:8px;padding:10px 14px;background:var(--card-bg,#fff);}
.ctc-stat-hdr{display:flex;align-items:center;gap:8px;margin-bottom:8px;font-size:12px;font-weight:700;color:var(--text-color);}
.ctc-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0;}
.ctc-dot-blue{background:#1971c2;} .ctc-dot-teal{background:#0f6e56;} .ctc-dot-orange{background:#e67700;} .ctc-dot-purple{background:#6741d9;}
.ctc-stat-lines{font-size:12px;color:var(--text-muted);display:flex;flex-direction:column;gap:3px;}
.ctc-stat-note{font-size:11px;font-style:italic;margin-top:2px;}

.ctc-kpi-row{display:flex;gap:12px;margin:14px 0 18px;flex-wrap:wrap;}
.ctc-kpi{flex:1;min-width:120px;border-radius:10px;padding:14px 16px;border:1px solid transparent;}
.ctc-kpi-val{font-size:18px;font-weight:700;margin-bottom:4px;}
.ctc-kpi-lbl{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;opacity:.8;}
.ctc-kpi-purple{background:#f3f0ff;border-color:#d0bfff;color:#6741d9;}
.ctc-kpi-blue  {background:#e7f5ff;border-color:#a5d8ff;color:#1864ab;}
.ctc-kpi-teal  {background:#e6fcf5;border-color:#96f2d7;color:#0f6e56;}
.ctc-kpi-coral {background:#fff5f5;border-color:#ffc9c9;color:#c92a2a;}
.ctc-kpi-green {background:#ebfbee;border-color:#b2f2bb;color:#2b8a3e;}

.ctc-cols{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px;margin-bottom:12px;}
.ctc-card{background:var(--card-bg,#fff);border:1px solid var(--border-color);border-radius:10px;overflow:hidden;}
.ctc-card-hdr{display:flex;align-items:center;justify-content:space-between;padding:12px 14px 10px;border-bottom:2px solid var(--border-color);}
.ctc-card-ttl{font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;}
.ctc-card-sum{font-size:13px;font-weight:700;}
.ctc-ttl-earn{color:#2f9e44;} .ctc-card-earn .ctc-card-sum{color:#2f9e44;}
.ctc-ttl-ded {color:#e03131;} .ctc-card-ded  .ctc-card-sum{color:#e03131;}
.ctc-ttl-emp {color:#1971c2;} .ctc-card-emp  .ctc-card-sum{color:#1971c2;}

.ctc-tbl{width:100%;border-collapse:collapse;font-size:13px;}
.ctc-tbl thead th{padding:7px 10px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;color:var(--text-muted);border-bottom:1px solid var(--border-color);background:var(--subtle-fg,#f8f9fa);}
.ctc-th-n{text-align:left;width:48%;} .ctc-th-p{text-align:center;width:22%;} .ctc-th-a{text-align:right;width:30%;}
.ctc-tbl tbody tr{border-bottom:1px solid var(--border-color,#eee);}
.ctc-tbl tbody tr:last-child{border-bottom:none;}
.ctc-tbl tbody tr:hover{background:var(--subtle-fg,#f9fafb);}
.ctc-td-name{padding:8px 10px;color:var(--text-color);font-weight:500;vertical-align:middle;}
.ctc-td-pct{padding:4px 6px;text-align:center;vertical-align:middle;}
.ctc-td-amt{padding:4px 10px;text-align:right;vertical-align:middle;}

.ctc-inp-grp{display:inline-flex;align-items:center;gap:2px;}
.ctc-pct{width:48px;text-align:right;padding:3px 4px;font-size:12px;color:var(--text-muted);border:1px solid transparent;border-radius:4px;background:transparent;outline:none;transition:border-color .15s,background .15s;}
.ctc-pct:hover{border-color:var(--border-color);} .ctc-pct:focus{border-color:var(--primary,#5e64ff);background:#fff;}
.ctc-pct[readonly]{color:var(--text-muted);pointer-events:none;}
.ctc-pct-sym{font-size:11px;color:var(--text-muted);}
.ctc-amt{width:88px;text-align:right;padding:3px 6px;font-size:13px;font-weight:600;border:1px solid transparent;border-radius:4px;background:transparent;outline:none;transition:border-color .15s,background .15s;}
.ctc-c-earn{color:#2f9e44;} .ctc-c-ded{color:#e03131;} .ctc-c-emp{color:#1971c2;}
.ctc-amt:hover{border-color:var(--border-color);} .ctc-amt:focus{border-color:var(--primary,#5e64ff);background:#fff;color:var(--text-color);}
.ctc-amt[readonly]{pointer-events:none;}

.ctc-tag{display:inline-block;padding:1px 6px;border-radius:8px;font-size:10px;font-weight:700;text-transform:uppercase;margin-left:4px;}
.ctc-tag-var{background:#fff9db;color:#864e00;} .ctc-tag-oth{background:#f3f0ff;color:#6741d9;} .ctc-tag-excl{background:#fff5f5;color:#c92a2a;}

.ctc-nil{text-align:center;color:var(--text-muted);padding:18px;font-size:12px;}

.ctc-summary-bar{display:grid;grid-template-columns:1fr 1fr 1fr;border:1px solid var(--border-color,#d1d8dd);border-radius:6px;overflow:hidden;margin-bottom:24px;background:var(--card-bg,#fff);}
.ctc-sum-item{display:flex;flex-direction:row;align-items:center;justify-content:space-between;padding:10px 16px;border-right:1px solid var(--border-color,#d1d8dd);gap:12px;}
.ctc-sum-item:last-child{border-right:none;}
.ctc-sum-lbl{font-size:13px;font-weight:600;color:var(--text-color,#36414c);}
.ctc-sum-val{font-size:13px;font-weight:400;color:var(--text-muted,#8d99a6);text-align:right;white-space:nowrap;}

@media(max-width:1024px){.ctc-cols{grid-template-columns:1fr;}.ctc-summary-bar{grid-template-columns:1fr;}}
</style>`);
}