// ─── CTC Calculator Page ──────────────────────────────────────────────────────
// File: saral_hr/saral_hr/page/ctc_calculator/ctc_calculator.js

frappe.pages['ctc_calculator'].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent:    wrapper,
        title:     'CTC Calculator',
        single_column: true,
    });

    frappe.ctc_calc = new CTCCalculator(page, wrapper);
};

frappe.pages['ctc_calculator'].on_page_show = function (wrapper) {
    if (frappe.ctc_calc) frappe.ctc_calc.refresh();
};

// ─── Main class ───────────────────────────────────────────────────────────────

class CTCCalculator {
    constructor(page, wrapper) {
        this.page    = page;
        this.wrapper = wrapper;
        this.state   = {
            company:          '',
            salary_structure: '',
            annual_ctc:       0,
            include_pf:       false,
            include_esic:     false,
            include_pt:       false,
            result:           null,
        };

        this._PF_COMPONENTS   = new Set([
            'Employee PF',
            'Employer PF (ERPF)',
            'Employer EPS',
            'Employer EDLI',
            'PF Admin Charges',
        ]);
        this._ESIC_COMPONENTS = new Set([
            'Employee ESIC',
            'Employer ESIC',
        ]);
        this._PT_COMPONENTS   = new Set([
            'Professional Tax',
        ]);

        this._render_shell();
        this._load_companies();
    }

    refresh() { /* nothing needed on re-show */ }

    _$(sel) { return $(this.wrapper).find(sel); }

    _current_month() {
        return ['January','February','March','April','May','June',
                'July','August','September','October','November','December'][new Date().getMonth()];
    }

    // ── Shell HTML ────────────────────────────────────────────────────────────

    _render_shell() {
        $(this.wrapper).find('.page-content').html(`
<div class="ctc-page" id="ctc-root">

  <!-- ── Input panel ── -->
  <div class="ctc-card ctc-input-panel">
    <div class="ctc-grid-main">

      <!-- Row 1: Company | Structure | Annual CTC -->
      <div class="ctc-field">
        <label class="ctc-label">Company <span class="ctc-req">*</span></label>
        <select id="ctc-company" class="ctc-select">
          <option value="">— Select company —</option>
        </select>
      </div>

      <div class="ctc-field">
        <label class="ctc-label">Salary Structure <span class="ctc-req">*</span></label>
        <select id="ctc-structure" class="ctc-select" disabled>
          <option value="">— Select structure —</option>
        </select>
      </div>

      <div class="ctc-field">
        <label class="ctc-label">Annual CTC (₹) <span class="ctc-req">*</span></label>
        <div class="ctc-input-wrap">
          <span class="ctc-input-prefix">₹</span>
          <input id="ctc-annual" type="number" min="0" step="1000"
                 class="ctc-input" placeholder="e.g. 720000" />
        </div>
        <div class="ctc-hint" id="ctc-monthly-hint"></div>
      </div>

    </div>

    <!-- Row 2: Toggles + Button in one compact bar -->
    <div class="ctc-toggle-bar">

      <div class="ctc-toggle-group">
        <span class="ctc-label">Include PF</span>
        <label class="ctc-toggle">
          <input type="checkbox" id="ctc-pf" />
          <span class="ctc-toggle-track"><span class="ctc-toggle-knob"></span></span>
          <span class="ctc-toggle-label" id="ctc-pf-label">No</span>
        </label>
        <div class="ctc-toggle-info" id="ctc-pf-info" style="display:none;">
          <div class="ctc-info-line"><span class="ctc-info-dot ctc-dot-blue"></span>Emp PF: min(Basic+DA, ₹15k) × 12%</div>
          <div class="ctc-info-line"><span class="ctc-info-dot ctc-dot-blue"></span>ERPF: min(Basic+DA, ₹15k) × 3.67%</div>
          <div class="ctc-info-line"><span class="ctc-info-dot ctc-dot-blue"></span>EPS: min(Basic+DA, ₹15k) × 8.33%</div>
          <div class="ctc-info-line"><span class="ctc-info-dot ctc-dot-blue"></span>EDLI + Admin: × 0.5% each</div>
        </div>
      </div>

      <div class="ctc-toggle-group">
        <span class="ctc-label">Include ESIC</span>
        <label class="ctc-toggle">
          <input type="checkbox" id="ctc-esic" />
          <span class="ctc-toggle-track"><span class="ctc-toggle-knob"></span></span>
          <span class="ctc-toggle-label" id="ctc-esic-label">No</span>
        </label>
        <div class="ctc-toggle-info" id="ctc-esic-info" style="display:none;">
          <div class="ctc-info-line"><span class="ctc-info-dot ctc-dot-teal"></span>Emp ESIC: Gross × 0.75%</div>
          <div class="ctc-info-line"><span class="ctc-info-dot ctc-dot-teal"></span>Employer ESIC: Gross × 3.25%</div>
          <div class="ctc-info-line ctc-info-note">Applicable if Gross ≤ ₹21,000/month</div>
        </div>
      </div>

      <div class="ctc-toggle-group">
        <span class="ctc-label">Include PT</span>
        <label class="ctc-toggle">
          <input type="checkbox" id="ctc-pt" />
          <span class="ctc-toggle-track"><span class="ctc-toggle-knob"></span></span>
          <span class="ctc-toggle-label" id="ctc-pt-label">No</span>
        </label>
        <div class="ctc-toggle-info" id="ctc-pt-info" style="display:none;">
          <div class="ctc-info-line"><span class="ctc-info-dot ctc-dot-orange"></span>PT: ₹200/month (₹300 in February)</div>
        </div>
      </div>

      <div class="ctc-bar-actions">
        <button id="ctc-calc-btn" class="ctc-btn-primary" disabled>Calculate Breakdown</button>
        <button id="ctc-reset-btn" class="ctc-btn-ghost">Reset</button>
      </div>

    </div>
  </div>
  <div class="ctc-spacer" id="ctc-spacer"></div>

  <!-- ── Error bar ── -->
  <div id="ctc-error" class="ctc-error-bar" style="display:none;"></div>

  <!-- ── Results ── -->
  <div id="ctc-results" style="display:none;">

    <!-- Summary KPI row -->
    <div class="ctc-kpi-row" id="ctc-kpi-row"></div>

    <!-- Three breakdown cards -->
    <div class="ctc-breakdown-row">

      <div class="ctc-card ctc-breakdown-card">
        <div class="ctc-section-title ctc-title-earn">
          <i class="ti ti-plus-circle"></i> Earnings
          <span class="ctc-badge ctc-badge-earn" id="ctc-earn-total"></span>
        </div>
        <table class="ctc-table" id="ctc-earn-table">
          <thead><tr><th>Component</th><th>Abbr</th><th class="ctc-right">Amount (₹)</th></tr></thead>
          <tbody></tbody>
          <tfoot></tfoot>
        </table>
      </div>

      <div class="ctc-card ctc-breakdown-card">
        <div class="ctc-section-title ctc-title-ded">
          <i class="ti ti-minus-circle"></i> Employee Deductions
          <span class="ctc-badge ctc-badge-ded" id="ctc-ded-total"></span>
        </div>
        <table class="ctc-table" id="ctc-ded-table">
          <thead><tr><th>Component</th><th>Type</th><th class="ctc-right">Amount (₹)</th></tr></thead>
          <tbody></tbody>
          <tfoot></tfoot>
        </table>
        <!-- Net salary block -->
        <div class="ctc-net-block" id="ctc-net-block"></div>
      </div>

      <div class="ctc-card ctc-breakdown-card">
        <div class="ctc-section-title ctc-title-emp">
          <i class="ti ti-building-community"></i> Employer Share
          <span class="ctc-badge ctc-badge-emp" id="ctc-emp-total"></span>
        </div>
        <table class="ctc-table" id="ctc-emp-table">
          <thead><tr><th>Component</th><th>In CTC</th><th class="ctc-right">Amount (₹)</th></tr></thead>
          <tbody></tbody>
          <tfoot></tfoot>
        </table>
      </div>

    </div>

  </div>

  <!-- ── Empty state ── -->
  <div id="ctc-empty" class="ctc-empty">
    <div class="ctc-empty-icon">₹</div>
    <div class="ctc-empty-title">No breakdown yet</div>
    <div class="ctc-empty-sub">Select a company, salary structure and enter an annual CTC to get started.</div>
  </div>

</div>

${this._styles()}
`);

        this._bind_events();
        this._init_sticky();
    }

    _init_sticky() {
        const $panel   = this._$('.ctc-input-panel');
        const $spacer  = this._$('#ctc-spacer');

        // Frappe's main scrollable area
        const $scroller = $(this.wrapper).closest('.page-content').first();
        const scroller  = $scroller.length ? $scroller[0] : window;

        // Frappe navbar is always 48px; read it dynamically in case theme changes
        const navbarH = () => parseInt($('.navbar, .nav-bar, [class*="navbar"]').first().outerHeight()) || 48;

        const onScroll = () => {
            const panelH  = $panel.outerHeight(true);
            const scrollTop = scroller === window ? window.scrollY : scroller.scrollTop;
            const nh = navbarH();

            if (scrollTop > 10) {
                if (!$panel.hasClass('ctc-pinned')) {
                    $panel.addClass('ctc-pinned');
                    $panel.css('top', nh + 'px');
                    $spacer.css({ display: 'block', height: panelH + 'px' });
                }
            } else {
                $panel.removeClass('ctc-pinned');
                $panel.css('top', '');
                $spacer.css({ display: 'none' });
            }
        };

        $(scroller).on('scroll.ctc', onScroll);
        $(window).on('scroll.ctc', onScroll);   // catch window scroll too
        $(this.wrapper).one('hide.ctc', () => {
            $(scroller).off('scroll.ctc');
            $(window).off('scroll.ctc');
        });
    }

    // ── Events ────────────────────────────────────────────────────────────────

    _bind_events() {
        const $ = window.$;

        $('#ctc-company').on('change', (e) => {
            this.state.company = e.target.value;
            this.state.salary_structure = '';
            $('#ctc-structure').prop('disabled', true).html('<option value="">— loading… —</option>');
            this._check_calc_ready();
            if (this.state.company) this._load_structures(this.state.company);
        });

        $('#ctc-structure').on('change', (e) => {
            this.state.salary_structure = e.target.value;
            this._check_calc_ready();
        });



        $('#ctc-annual').on('input', (e) => {
            const v = parseFloat(e.target.value) || 0;
            this.state.annual_ctc = v;
            if (v > 0) {
                $('#ctc-monthly-hint').text(`Monthly CTC: ₹ ${this._fmt(v / 12)}`);
            } else {
                $('#ctc-monthly-hint').text('');
            }
            this._check_calc_ready();
        });

        // ── PF toggle ──
        $(this.wrapper).on('change', '#ctc-pf', (e) => {
            this.state.include_pf = e.target.checked;
            $('#ctc-pf-label').text(e.target.checked ? 'Yes' : 'No');
            $('#ctc-pf-info').toggle(e.target.checked);
            if (this.state.result) this._recalculate_and_render();
        });

        // ── ESIC toggle ──
        $(this.wrapper).on('change', '#ctc-esic', (e) => {
            this.state.include_esic = e.target.checked;
            $('#ctc-esic-label').text(e.target.checked ? 'Yes' : 'No');
            $('#ctc-esic-info').toggle(e.target.checked);
            if (this.state.result) this._recalculate_and_render();
        });

        // ── PT toggle ──
        $(this.wrapper).on('change', '#ctc-pt', (e) => {
            this.state.include_pt = e.target.checked;
            $('#ctc-pt-label').text(e.target.checked ? 'Yes' : 'No');
            $('#ctc-pt-info').toggle(e.target.checked);
            if (this.state.result) this._recalculate_and_render();
        });

        $('#ctc-calc-btn').on('click', () => this._calculate());
        $('#ctc-reset-btn').on('click', () => this._reset());
    }

    _check_calc_ready() {
        const ok = this.state.company && this.state.salary_structure && this.state.annual_ctc > 0;
        $('#ctc-calc-btn').prop('disabled', !ok);
    }

    // ── Data loaders ──────────────────────────────────────────────────────────

    _load_companies() {
        frappe.call({
            method: 'saral_hr.saral_hr.page.ctc_calculator.ctc_calculator.get_companies',
            callback: (r) => {
                if (!r.message) return;
                const opts = r.message.map(c => `<option value="${frappe.utils.escape_html(c)}">${frappe.utils.escape_html(c)}</option>`).join('');
                $('#ctc-company').append(opts);
            }
        });
    }

    _load_structures(company) {
        frappe.call({
            method: 'saral_hr.saral_hr.page.ctc_calculator.ctc_calculator.get_salary_structures',
            args:   { company },
            callback: (r) => {
                if (!r.message || !r.message.length) {
                    $('#ctc-structure').prop('disabled', false).html('<option value="">— No structures found —</option>');
                    return;
                }
                const opts = r.message.map(s =>
                    `<option value="${frappe.utils.escape_html(s)}">${frappe.utils.escape_html(s)}</option>`
                ).join('');
                $('#ctc-structure').prop('disabled', false).html('<option value="">— Select structure —</option>' + opts);
            }
        });
    }

    // ── Calculate ─────────────────────────────────────────────────────────────

    _calculate() {
        const btn = $('#ctc-calc-btn');
        btn.prop('disabled', true).html('<i class="ti ti-loader ctc-spin"></i> Calculating…');
        $('#ctc-error').hide();

        const pf_on   = this._$('#ctc-pf').is(':checked');
        const esic_on = this._$('#ctc-esic').is(':checked');
        const pt_on   = this._$('#ctc-pt').is(':checked');
        this.state.include_pf   = pf_on;
        this.state.include_esic = esic_on;
        this.state.include_pt   = pt_on;

        frappe.call({
            method: 'saral_hr.saral_hr.page.ctc_calculator.ctc_calculator.calculate_ctc_breakdown',
            args: {
                company:          this.state.company,
                salary_structure: this.state.salary_structure,
                annual_ctc:       this.state.annual_ctc,
                month:            this._current_month(),
                include_pf:       pf_on   ? "1" : "0",
                include_esic:     esic_on ? "1" : "0",
                include_pt:       pt_on   ? "1" : "0",
            },
            callback: (r) => {
                btn.prop('disabled', false).html('Calculate Breakdown');
                if (!r.message) {
                    this._show_error('No data returned from server.');
                    return;
                }
                this.state.result = r.message;
                this._render_results(r.message);
            },
            error: (r) => {
                btn.prop('disabled', false).html('Calculate Breakdown');
                this._show_error(r._server_messages || r.message || 'Calculation failed.');
            }
        });
    }

    // ── Toggle re-render (client-side, no server call) ────────────────────────

    _recalculate_and_render() {
        const raw = this.state.result;
        if (!raw) return;

        const pf_on   = this.state.include_pf;
        const esic_on = this.state.include_esic;
        const pt_on   = this.state.include_pt;

        // Filter employee deductions
        const deductions = raw.deductions.filter(row => {
            if (this._PF_COMPONENTS.has(row.salary_component))   return pf_on;
            if (this._ESIC_COMPONENTS.has(row.salary_component)) return esic_on;
            if (this._PT_COMPONENTS.has(row.salary_component))   return pt_on;
            return true;
        });

        // Filter employer share
        const employer_share = raw.employer_share.filter(row => {
            if (this._PF_COMPONENTS.has(row.salary_component))   return pf_on;
            if (this._ESIC_COMPONENTS.has(row.salary_component)) return esic_on;
            return true;
        });

        const total_deductions   = parseFloat((deductions.reduce((s, r) => s + r.amount, 0)).toFixed(2));
        const net_salary         = Math.round(raw.gross - total_deductions);
        const total_employer_ctc = parseFloat(
            (employer_share.filter(e => e.in_ctc).reduce((s, r) => s + r.amount, 0)).toFixed(2)
        );

        this._render_results({
            ...raw,
            deductions,
            employer_share,
            total_deductions,
            net_salary,
            total_employer_ctc,
            flags: { ...raw.flags, is_pf: pf_on, is_esic: esic_on, is_pt: pt_on },
        });
    }

    _reset() {
        this.state.result       = null;
        this.state.annual_ctc   = 0;
        this.state.include_pf   = false;
        this.state.include_esic = false;
        this.state.include_pt   = false;
        $('#ctc-annual').val('');
        $('#ctc-monthly-hint').text('');
        $('#ctc-pf').prop('checked', false);
        $('#ctc-esic').prop('checked', false);
        $('#ctc-pt').prop('checked', false);
        $('#ctc-pf-label').text('No');
        $('#ctc-esic-label').text('No');
        $('#ctc-pt-label').text('No');
        $('#ctc-pf-info').hide();
        $('#ctc-esic-info').hide();
        $('#ctc-pt-info').hide();
        $('#ctc-results').hide();
        $('#ctc-empty').show();
        $('#ctc-error').hide();
        this._check_calc_ready();
    }

    // ── Render results ────────────────────────────────────────────────────────

    _render_results(d) {
        $('#ctc-empty').hide();
        $('#ctc-error').hide();

        // KPI row
        const kpis = [
            { label: 'Annual CTC',    value: '₹ ' + this._fmt(d.annual_ctc),      color: 'purple' },
            { label: 'Monthly CTC',   value: '₹ ' + this._fmt(d.monthly_ctc),     color: 'blue'   },
            { label: 'Monthly Gross', value: '₹ ' + this._fmt(d.gross),           color: 'teal'   },
            { label: 'Deductions',    value: '₹ ' + this._fmt(d.total_deductions), color: 'coral'  },
            { label: 'Net Salary',    value: '₹ ' + this._fmt(d.net_salary),       color: 'green'  },
        ];
        $('#ctc-kpi-row').html(kpis.map(k => `
            <div class="ctc-kpi ctc-kpi-${k.color}">
                <div class="ctc-kpi-val">${frappe.utils.escape_html(k.value)}</div>
                <div class="ctc-kpi-lbl">${frappe.utils.escape_html(k.label)}</div>
            </div>
        `).join(''));

        // Earnings table
        this._render_table('#ctc-earn-table', d.earnings, (row) => [
            `<td>${frappe.utils.escape_html(row.salary_component)}${row.is_variable ? ' <span class="ctc-tag ctc-tag-var">Variable</span>' : ''}${row.is_others ? ' <span class="ctc-tag ctc-tag-oth">Remainder</span>' : ''}</td>`,
            `<td class="ctc-muted">${frappe.utils.escape_html(row.abbr || '')}</td>`,
            `<td class="ctc-right ctc-mono">${this._fmt(row.amount)}</td>`,
        ], d.gross, 'Gross Total');
        $('#ctc-earn-total').text('₹ ' + this._fmt(d.gross));

        // Deductions table
        this._render_table('#ctc-ded-table', d.deductions, (row) => [
            `<td>${frappe.utils.escape_html(row.salary_component)}${row.note ? ` <span class="ctc-hint-inline">${frappe.utils.escape_html(row.note)}</span>` : ''}</td>`,
            `<td><span class="ctc-tag ${row.statutory ? 'ctc-tag-stat' : 'ctc-tag-oth'}">${row.statutory ? 'Statutory' : 'Other'}</span></td>`,
            `<td class="ctc-right ctc-mono">${this._fmt(row.amount)}</td>`,
        ], d.total_deductions, 'Total Deductions');
        $('#ctc-ded-total').text('₹ ' + this._fmt(d.total_deductions));

        // Net salary block
        $('#ctc-net-block').html(`
            <div class="ctc-net-row">
                <span class="ctc-net-lbl">Gross</span>
                <span class="ctc-net-val">₹ ${this._fmt(d.gross)}</span>
            </div>
            <div class="ctc-net-row ctc-net-minus">
                <span class="ctc-net-lbl">− Total Deductions</span>
                <span class="ctc-net-val">₹ ${this._fmt(d.total_deductions)}</span>
            </div>
            <div class="ctc-net-row ctc-net-result">
                <span class="ctc-net-lbl">Net Take-Home</span>
                <span class="ctc-net-val ctc-net-big">₹ ${this._fmt(d.net_salary)}</span>
            </div>
        `);

        // Employer share table
        this._render_table('#ctc-emp-table', d.employer_share, (row) => [
            `<td>${frappe.utils.escape_html(row.salary_component)}${row.note ? ` <span class="ctc-hint-inline">${frappe.utils.escape_html(row.note)}</span>` : ''}</td>`,
            `<td>${row.in_ctc ? '<span class="ctc-tag ctc-tag-stat">In CTC</span>' : '<span class="ctc-tag ctc-tag-oth">Excl.</span>'}</td>`,
            `<td class="ctc-right ctc-mono">${this._fmt(row.amount)}</td>`,
        ], d.total_employer_ctc, 'Total In CTC');
        $('#ctc-emp-total').text('₹ ' + this._fmt(d.total_employer_ctc));

        $('#ctc-results').show();
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    _render_table(selector, rows, row_fn, total, total_label) {
        const $table = $(selector);
        const tbody_html = (rows || []).map(row => `<tr>${row_fn(row).join('')}</tr>`).join('')
            || `<tr><td colspan="3" class="ctc-empty-row">No components</td></tr>`;
        $table.find('tbody').html(tbody_html);
        $table.find('tfoot').html(`
            <tr class="ctc-tfoot-row">
                <td colspan="2"><strong>${frappe.utils.escape_html(total_label)}</strong></td>
                <td class="ctc-right ctc-mono"><strong>₹ ${this._fmt(total)}</strong></td>
            </tr>
        `);
    }

    _fmt(n) {
        return (parseFloat(n) || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    _show_error(msg) {
        let text = msg;
        if (typeof msg === 'string' && msg.startsWith('[')) {
            try { text = JSON.parse(msg).map(m => m.message || m).join(' '); } catch(e) {}
        }
        $('#ctc-error').text(text).show();
    }

    // ── Styles ────────────────────────────────────────────────────────────────

    _styles() {
        return `<style>
/* ── Root ── */
.ctc-page { font-family: var(--font-sans, sans-serif); padding: 16px 24px 48px; max-width: 1280px; margin: 0 auto; }

/* ── Card ── */
.ctc-card { background: var(--card-bg, #fff); border: 1px solid var(--border-color); border-radius: 10px; padding: 16px 20px; margin-bottom: 16px; }
.ctc-input-panel { position: relative; z-index: 100; background: var(--card-bg, #fff); transition: box-shadow .2s; }
.ctc-input-panel.ctc-pinned { position: fixed; top: 48px; left: 0; right: 0; border-radius: 0; border-left: none; border-right: none; border-top: none; box-shadow: 0 3px 12px rgba(0,0,0,0.12); margin-bottom: 0; padding-left: 24px; padding-right: 24px; }
.ctc-spacer { display: none; }

/* ── Section title ── */
.ctc-section-title { font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-muted); margin-bottom: 16px; display: flex; align-items: center; gap: 7px; }
.ctc-title-earn { color: #2f9e44; }
.ctc-title-ded  { color: #e03131; }
.ctc-title-emp  { color: #1971c2; }

/* ── Input grid (3 cols: Company | Structure | Annual CTC) ── */
.ctc-grid-main { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 14px 16px; margin-bottom: 14px; }
.ctc-field { display: flex; flex-direction: column; gap: 5px; }

/* ── Toggle bar (row 2: PF | ESIC | PT | Button) ── */
.ctc-toggle-bar { display: flex; align-items: flex-start; gap: 0; border-top: 1px solid var(--border-color); padding-top: 14px; flex-wrap: wrap; }
.ctc-toggle-group { display: flex; flex-direction: column; gap: 6px; padding: 0 20px 0 0; border-right: 1px solid var(--border-color); margin-right: 20px; min-width: 120px; }
.ctc-toggle-group:last-of-type { border-right: none; }
.ctc-bar-actions { display: flex; align-items: center; gap: 8px; margin-left: auto; padding-top: 18px; }

.ctc-label { font-size: 12px; font-weight: 600; color: var(--text-muted); letter-spacing: 0.03em; }
.ctc-req   { color: var(--red, #e03131); }
.ctc-hint  { font-size: 11px; color: var(--primary, #5e64ff); font-weight: 500; min-height: 16px; }
.ctc-hint-inline { font-size: 10px; color: var(--text-muted); font-style: italic; }

.ctc-select, .ctc-input {
    width: 100%; padding: 8px 12px; border: 1px solid var(--border-color); border-radius: 6px;
    background: var(--control-bg, #f8f9fa); color: var(--text-color);
    font-size: 13px; outline: none; transition: border-color .15s, box-shadow .15s;
}
.ctc-select:focus, .ctc-input:focus {
    border-color: var(--primary, #5e64ff);
    box-shadow: 0 0 0 2px rgba(94,100,255,.12);
}
.ctc-select:disabled { opacity: 0.5; cursor: not-allowed; }

.ctc-input-wrap  { position: relative; display: flex; align-items: center; }
.ctc-input-prefix { position: absolute; left: 10px; font-size: 14px; color: var(--text-muted); pointer-events: none; }
.ctc-input-wrap .ctc-input { padding-left: 24px; }

/* ── Toggle ── */
.ctc-toggle { display: flex; align-items: center; gap: 10px; cursor: pointer; user-select: none; }
.ctc-toggle input { display: none; }
.ctc-toggle-track { width: 36px; height: 20px; border-radius: 10px; background: var(--border-color); position: relative; transition: background .2s; flex-shrink: 0; }
.ctc-toggle input:checked + .ctc-toggle-track { background: var(--primary, #5e64ff); }
.ctc-toggle-knob { position: absolute; top: 2px; left: 2px; width: 16px; height: 16px; border-radius: 50%; background: #fff; transition: transform .2s; box-shadow: 0 1px 3px rgba(0,0,0,.2); }
.ctc-toggle input:checked ~ .ctc-toggle-track .ctc-toggle-knob { transform: translateX(16px); }
.ctc-toggle-label { font-size: 12px; font-weight: 600; color: var(--text-muted); min-width: 24px; }

/* ── Buttons ── */
.ctc-btn-primary { padding: 9px 20px; background: var(--primary, #5e64ff); color: #fff; border: none; border-radius: 6px; font-size: 13px; font-weight: 600; cursor: pointer; transition: opacity .15s, box-shadow .15s; display: flex; align-items: center; gap: 6px; justify-content: center; }
.ctc-btn-primary:hover:not(:disabled) { opacity: .88; box-shadow: 0 2px 8px rgba(94,100,255,.35); }
.ctc-btn-primary:disabled { opacity: .45; cursor: not-allowed; }
.ctc-btn-ghost { padding: 7px 16px; background: transparent; border: 1px solid var(--border-color); border-radius: 6px; font-size: 12px; color: var(--text-muted); cursor: pointer; transition: border-color .15s; }
.ctc-btn-ghost:hover { border-color: var(--primary, #5e64ff); color: var(--primary, #5e64ff); }

/* ── Spin ── */
@keyframes ctc-spin { to { transform: rotate(360deg); } }
.ctc-spin { display: inline-block; animation: ctc-spin .8s linear infinite; }

/* ── Error bar ── */
.ctc-error-bar { background: #fff5f5; border: 1px solid #ffc9c9; border-radius: 8px; padding: 10px 16px; color: #c92a2a; font-size: 13px; margin-bottom: 14px; }

/* ── KPI row ── */
.ctc-kpi-row { display: flex; gap: 14px; margin-bottom: 18px; flex-wrap: wrap; }
.ctc-kpi { flex: 1; min-width: 140px; border-radius: 10px; padding: 16px 18px; border: 1px solid transparent; }
.ctc-kpi-val { font-size: 20px; font-weight: 700; letter-spacing: -0.02em; margin-bottom: 4px; }
.ctc-kpi-lbl { font-size: 11px; font-weight: 500; text-transform: uppercase; letter-spacing: 0.05em; opacity: .7; }
.ctc-kpi-purple { background: #f3f0ff; border-color: #d0bfff; color: #6741d9; }
.ctc-kpi-blue   { background: #e7f5ff; border-color: #a5d8ff; color: #1864ab; }
.ctc-kpi-teal   { background: #e6fcf5; border-color: #96f2d7; color: #0f6e56; }
.ctc-kpi-coral  { background: #fff5f5; border-color: #ffc9c9; color: #c92a2a; }
.ctc-kpi-green  { background: #ebfbee; border-color: #b2f2bb; color: #2b8a3e; }

/* ── Breakdown row ── */
.ctc-breakdown-row { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; margin-bottom: 18px; }
.ctc-breakdown-card { display: flex; flex-direction: column; }

/* ── Table ── */
.ctc-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.ctc-table thead th { padding: 7px 10px; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; color: var(--text-muted); border-bottom: 2px solid var(--border-color); text-align: left; }
.ctc-table tbody td { padding: 8px 10px; border-bottom: 1px solid var(--border-color); vertical-align: middle; color: var(--text-color); }
.ctc-table tbody tr:last-child td { border-bottom: none; }
.ctc-table tbody tr:hover { background: var(--subtle-fg, #f9fafb); }
.ctc-table tfoot .ctc-tfoot-row td { padding: 9px 10px; border-top: 2px solid var(--border-color); background: var(--subtle-fg, #f3f4f6); font-size: 13px; }
.ctc-right   { text-align: right; }
.ctc-mono    { font-variant-numeric: tabular-nums; }
.ctc-muted   { color: var(--text-muted); }
.ctc-empty-row { text-align: center; color: var(--text-muted); padding: 20px; }

/* ── Tags / badges ── */
.ctc-badge { font-size: 12px; font-weight: 700; margin-left: auto; }
.ctc-badge-earn { color: #2f9e44; }
.ctc-badge-ded  { color: #e03131; }
.ctc-badge-emp  { color: #1971c2; }

.ctc-tag { display: inline-block; padding: 1px 7px; border-radius: 10px; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; margin-left: 4px; }
.ctc-tag-stat { background: #e7f5ff; color: #1864ab; }
.ctc-tag-var  { background: #fff9db; color: #864e00; }
.ctc-tag-oth  { background: #f3f0ff; color: #6741d9; }

/* ── Net block ── */
.ctc-net-block { margin-top: 14px; border-top: 1px solid var(--border-color); padding-top: 12px; }
.ctc-net-row   { display: flex; justify-content: space-between; align-items: center; padding: 5px 0; font-size: 13px; }
.ctc-net-minus .ctc-net-val { color: #c92a2a; }
.ctc-net-result { border-top: 1px solid var(--border-color); margin-top: 4px; padding-top: 8px; }
.ctc-net-big { font-size: 18px; font-weight: 700; color: #2b8a3e; }

/* ── Empty state ── */
.ctc-empty { text-align: center; padding: 64px 24px; }
.ctc-empty-icon  { font-size: 52px; color: var(--border-color); margin-bottom: 12px; line-height: 1; }
.ctc-empty-title { font-size: 18px; font-weight: 600; color: var(--text-color); margin-bottom: 8px; }
.ctc-empty-sub   { font-size: 13px; color: var(--text-muted); max-width: 360px; margin: 0 auto; line-height: 1.6; }

/* ── Toggle info panel ── */
.ctc-toggle-info { margin-top: 8px; background: var(--subtle-fg, #f3f4f6); border: 1px solid var(--border-color); border-radius: 6px; padding: 8px 10px; display: flex; flex-direction: column; gap: 4px; }
.ctc-info-line { display: flex; align-items: center; gap: 7px; font-size: 11px; color: var(--text-muted); }
.ctc-info-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.ctc-dot-blue   { background: #1971c2; }
.ctc-dot-teal   { background: #0f6e56; }
.ctc-dot-orange { background: #e67700; }
.ctc-info-note { font-style: italic; color: var(--text-muted); padding-left: 13px; }

/* ── Responsive ── */
@media (max-width: 1024px) {
    .ctc-grid-main     { grid-template-columns: 1fr 1fr; }
    .ctc-breakdown-row { grid-template-columns: 1fr; }
    .ctc-bar-actions   { margin-left: 0; width: 100%; padding-top: 12px; }
}
@media (max-width: 640px) {
    .ctc-grid-main     { grid-template-columns: 1fr; }
    .ctc-kpi-row       { flex-direction: column; }
    .ctc-page          { padding: 10px; }
    .ctc-toggle-bar    { flex-direction: column; gap: 12px; }
    .ctc-toggle-group  { border-right: none; padding-right: 0; margin-right: 0; }
}
</style>`;
    }
}