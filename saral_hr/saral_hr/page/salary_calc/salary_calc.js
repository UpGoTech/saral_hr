frappe.pages["salary-calc"].on_page_load = function (wrapper) {
    frappe.ui.make_app_page({ parent: wrapper, title: "Salary Calculator" });
    inject_calc_styles();
};

frappe.pages["salary-calc"].on_page_show = function (wrapper) {
    var $main = $(wrapper).find(".layout-main-section");
    render_calc($main);
};

function inject_calc_styles() {
    if (document.getElementById("sc-styles")) return;
    var s = document.createElement("style");
    s.id = "sc-styles";
    s.innerHTML = `
        /* ── Reset Frappe chrome ── */
        .layout-main-section { padding: 0 !important; }
        .layout-side-section:empty, .layout-side-section { display: none !important; }
        .layout-main-section-wrapper { width: 100% !important; }

        /* ── Root ── */
        .sc-root {
            padding: 12px 20px 40px;
            font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            color: #111;
            width: 100%;
            box-sizing: border-box;
        }

        /* ── Page heading ── */
        .sc-page-title {
            font-size: 20px;
            font-weight: 700;
            color: #111;
            margin: 0 0 14px 0;
            letter-spacing: -0.3px;
        }

        /* ── Two-column layout ── */
        .sc-layout {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
            align-items: start;
        }
        @media (max-width: 720px) {
            .sc-layout { grid-template-columns: 1fr; }
        }

        .sc-col { display: flex; flex-direction: column; gap: 12px; }

        /* ── Card / section ── */
        .sc-section {
            border: 1px solid #e8e8e8;
            border-radius: 10px;
            padding: 14px 16px;
            background: #fff;
        }

        .sc-section-title {
            font-size: 10px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: #999;
            margin-bottom: 10px;
        }

        /* ── Grid helpers ── */
        .sc-row-2 {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }

        /* ── Fields ── */
        .sc-field { display: flex; flex-direction: column; gap: 3px; }

        .sc-label {
            font-size: 11px;
            font-weight: 500;
            color: #666;
        }

        .sc-input, .sc-select {
            height: 34px;
            padding: 0 9px;
            border: 1px solid #ddd;
            border-radius: 7px;
            font-size: 13px;
            font-family: inherit;
            color: #111;
            background: #fafafa;
            outline: none;
            width: 100%;
            box-sizing: border-box;
            transition: border-color 0.15s, background 0.15s;
        }
        .sc-input:focus, .sc-select:focus {
            border-color: #111;
            background: #fff;
        }
        .sc-input[readonly] {
            background: #f4f4f4;
            color: #555;
            cursor: default;
            border-color: #e8e8e8;
        }

        /* ── Toggle / radio buttons ── */
        .sc-radio-group { display: flex; gap: 6px; flex-wrap: wrap; }
        .sc-radio-btn {
            padding: 6px 13px;
            border: 1px solid #ddd;
            border-radius: 7px;
            font-size: 12px;
            font-weight: 500;
            color: #555;
            cursor: pointer;
            background: #fafafa;
            transition: all 0.12s;
            font-family: inherit;
            line-height: 1;
        }
        .sc-radio-btn:hover { border-color: #aaa; color: #111; }
        .sc-radio-btn.active { background: #111; border-color: #111; color: #fff; }

        /* ── Hint text ── */
        .sc-hint {
            font-size: 10px;
            color: #bbb;
            margin-top: 1px;
        }

        /* ── Period info chips ── */
        .sc-info-chips {
            display: flex;
            gap: 7px;
            flex-wrap: wrap;
            margin-top: 8px;
        }
        .sc-chip {
            font-size: 11px;
            color: #555;
            background: #f2f2f2;
            border-radius: 5px;
            padding: 3px 8px;
        }
        .sc-chip strong { color: #111; font-weight: 600; }

        /* ── Calculate button ── */
        .sc-calc-btn {
            height: 38px;
            width: 100%;
            padding: 0 18px;
            background: #111;
            color: #fff;
            border: none;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 600;
            font-family: inherit;
            cursor: pointer;
            transition: opacity 0.15s, transform 0.1s;
            margin-top: 14px;
            letter-spacing: 0.01em;
        }
        .sc-calc-btn:hover { opacity: 0.82; }
        .sc-calc-btn:active { transform: scale(0.99); }

        /* ── Error ── */
        .sc-error {
            color: #c00;
            font-size: 11px;
            margin-top: 6px;
            display: none;
        }

        /* ── Result card: green ── */
        .sc-result {
            display: none;
            background: #ecfdf2;
            border: 1.5px solid #a3e6b8;
            border-radius: 10px;
            padding: 18px 16px 16px;
            animation: sc-pop 0.22s ease;
        }
        @keyframes sc-pop {
            from { opacity: 0; transform: translateY(6px); }
            to   { opacity: 1; transform: translateY(0); }
        }

        .sc-result-label {
            font-size: 10px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: #2e8a50;
            margin-bottom: 4px;
        }

        .sc-result-amount {
            font-size: 38px;
            font-weight: 800;
            color: #1a6636;
            letter-spacing: -1.5px;
            font-variant-numeric: tabular-nums;
            line-height: 1.1;
        }

        /* ── Breakdown inside result ── */
        .sc-result-breakdown {
            margin-top: 14px;
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 1px;
            background: #c3e8d0;
            border-radius: 8px;
            overflow: hidden;
        }
        .sc-result-cell {
            background: #f4fdf7;
            padding: 8px 10px;
        }
        .sc-result-cell-label {
            font-size: 9.5px;
            color: #5a9e72;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 2px;
        }
        .sc-result-cell-val {
            font-size: 12.5px;
            font-weight: 700;
            color: #1a6636;
            font-variant-numeric: tabular-nums;
        }
    `;
    document.head.appendChild(s);
}

function render_calc($main) {
    var MONTHS = ['January','February','March','April','May','June',
                  'July','August','September','October','November','December'];
    var DAY_NAMES = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];

    var now = new Date();
    var cur_year  = now.getFullYear();
    var cur_month = now.getMonth();

    function get_calendar_days(month_name, year) {
        var m = MONTHS.indexOf(month_name);
        return new Date(year, m + 1, 0).getDate();
    }

    function get_weekly_off_count(month_name, year, off_days) {
        if (!off_days || off_days.length === 0) return 0;
        var m = MONTHS.indexOf(month_name);
        var days = new Date(year, m + 1, 0).getDate();
        var count = 0;
        for (var d = 1; d <= days; d++) {
            var dow = new Date(year, m, d).getDay();
            if (off_days.indexOf(dow) !== -1) count++;
        }
        return count;
    }

    function fmt_inr(v) {
        v = parseFloat(v) || 0;
        return v.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    function get_selected_weekly_offs() {
        var offs = [];
        $main.find('.sc-woff-btn.active').each(function() {
            offs.push(parseInt($(this).data('day')));
        });
        return offs;
    }

    function get_working_days() {
        var month = $main.find('#sc-month').val();
        var year  = parseInt($main.find('#sc-year').val());
        if (!month || !year) return 0;
        var cal      = get_calendar_days(month, year);
        var off_days = get_selected_weekly_offs();
        var weekly   = (basis === 'exclude') ? get_weekly_off_count(month, year, off_days) : 0;
        return Math.max(0, cal - weekly);
    }

    var year_opts = [cur_year - 1, cur_year, cur_year + 1].map(function(y) {
        return '<option value="' + y + '"' + (y === cur_year ? ' selected' : '') + '>' + y + '</option>';
    }).join('');

    var month_opts = MONTHS.map(function(m, i) {
        return '<option value="' + m + '"' + (i === cur_month ? ' selected' : '') + '>' + m + '</option>';
    }).join('');

    var woff_btns = DAY_NAMES.map(function(d, i) {
        return '<button class="sc-radio-btn sc-woff-btn' + (i === 0 ? ' active' : '') + '" data-day="' + i + '">' + d.substring(0,3) + '</button>';
    }).join('');

    $main.html(`
        <div class="sc-root">
      

            <div class="sc-layout">
                <!-- LEFT COLUMN -->
                <div class="sc-col">

                    <!-- 1. Attendance basis -->
                    <div class="sc-section">
                        <div class="sc-section-title">Attendance basis</div>
                        <div class="sc-radio-group" style="margin-bottom:10px;">
                            <button class="sc-radio-btn active" data-basis="exclude">Exclude weekly offs</button>
                            <button class="sc-radio-btn" data-basis="include">Include weekly offs</button>
                        </div>
                        <div id="sc-woff-picker">
                            <div class="sc-label" style="margin-bottom:5px;">Weekly off days</div>
                            <div class="sc-radio-group">${woff_btns}</div>
                        </div>
                    </div>

                    <!-- 2. Pay period -->
                    <div class="sc-section">
                        <div class="sc-section-title">Pay period</div>
                        <div class="sc-row-2">
                            <div class="sc-field">
                                <span class="sc-label">Month</span>
                                <select class="sc-select" id="sc-month">${month_opts}</select>
                            </div>
                            <div class="sc-field">
                                <span class="sc-label">Year</span>
                                <select class="sc-select" id="sc-year">${year_opts}</select>
                            </div>
                        </div>
                        <div class="sc-info-chips" id="sc-period-info"></div>
                    </div>

                </div>

                <!-- RIGHT COLUMN -->
                <div class="sc-col">

                    <!-- 3. Rate & payment -->
                    <div class="sc-section">
                        <div class="sc-section-title">Rate &amp; payment</div>

                        <div class="sc-radio-group" style="margin-bottom:12px;">
                            <button class="sc-radio-btn active" data-rate="monthly">Monthly amount</button>
                            <button class="sc-radio-btn" data-rate="daily">Daily rate</button>
                        </div>

                        <!-- Monthly mode -->
                        <div id="sc-monthly-fields">
                            <div class="sc-row-2" style="margin-bottom:10px;">
                                <div class="sc-field">
                                    <span class="sc-label">Monthly amount (&#8377;)</span>
                                    <input type="number" class="sc-input" id="sc-monthly-amt" min="0" placeholder="e.g. 25000">
                                </div>
                                <div class="sc-field">
                                    <span class="sc-label">Per-day rate (auto)</span>
                                    <input type="text" class="sc-input" id="sc-perday" readonly placeholder="—">
                                    <span class="sc-hint">Monthly ÷ working days</span>
                                </div>
                            </div>
                        </div>

                        <!-- Daily mode -->
                        <div class="sc-field" id="sc-daily-wrap" style="display:none; margin-bottom:10px;">
                            <span class="sc-label">Daily rate (&#8377;)</span>
                            <input type="number" class="sc-input" id="sc-daily-rate" min="0" placeholder="e.g. 850">
                        </div>

                        <!-- Payment days + Working days -->
                        <div class="sc-row-2">
                            <div class="sc-field">
                                <span class="sc-label">Payment days</span>
                                <input type="number" class="sc-input" id="sc-pay-days" min="0" placeholder="Days to pay for">
                            </div>
                            <div class="sc-field">
                                <span class="sc-label">Working days (auto)</span>
                                <input type="text" class="sc-input" id="sc-working-days-display" readonly placeholder="—">
                                <span class="sc-hint">Calendar − weekly offs</span>
                            </div>
                        </div>

                        <div class="sc-error" id="sc-err">Please fill all required fields.</div>
                        <button class="sc-calc-btn" id="sc-calculate">Calculate Pay</button>
                    </div>

                    <!-- Result -->
                    <div class="sc-result" id="sc-result">
    <div class="sc-result-label">Total payable amount</div>
    <div class="sc-result-amount" id="sc-result-amt">&#8377;0.00</div>
    
    <!--  FORMULA -->
    <div class="sc-hint" id="sc-result-formula" style="margin-top:6px;"></div>

    
</div>

                </div>
            </div>
        </div>
    `);

    var basis     = 'exclude';
    var rate_type = 'monthly';

    function update_period_info() {
        var month = $main.find('#sc-month').val();
        var year  = parseInt($main.find('#sc-year').val());
        if (!month || !year) return;

        var cal      = get_calendar_days(month, year);
        var off_days = get_selected_weekly_offs();
        var weekly   = (basis === 'exclude') ? get_weekly_off_count(month, year, off_days) : 0;
        var working  = Math.max(0, cal - weekly);

        var parts = [
            '<span class="sc-chip">Calendar <strong>' + cal + '</strong></span>',
            (basis === 'exclude' && off_days.length > 0)
                ? '<span class="sc-chip">Weekly offs <strong>' + weekly + '</strong></span>' : '',
            '<span class="sc-chip">Working days <strong>' + working + '</strong></span>',
        ];
        $main.find('#sc-period-info').html(parts.filter(Boolean).join(''));
        $main.find('#sc-working-days-display').val(working > 0 ? working : '');

        update_perday_rate();
    }

    function update_perday_rate() {
        if (rate_type !== 'monthly') return;
        var working = get_working_days();
        var amt     = parseFloat($main.find('#sc-monthly-amt').val()) || 0;
        $main.find('#sc-perday').val(amt > 0 && working > 0 ? fmt_inr(amt / working) : '');
    }

    $main.find('.sc-radio-btn[data-basis]').on('click', function() {
        basis = $(this).data('basis');
        $main.find('.sc-radio-btn[data-basis]').removeClass('active');
        $(this).addClass('active');
        $main.find('#sc-woff-picker').toggle(basis === 'exclude');
        update_period_info();
    });

    $main.find('.sc-woff-btn').on('click', function() {
    $main.find('.sc-woff-btn').removeClass('active'); // remove from all
    $(this).addClass('active'); // add only to clicked
    update_period_info();
    });

    $main.find('.sc-radio-btn[data-rate]').on('click', function() {
        rate_type = $(this).data('rate');
        $main.find('.sc-radio-btn[data-rate]').removeClass('active');
        $(this).addClass('active');
        if (rate_type === 'monthly') {
            $main.find('#sc-monthly-fields').show();
            $main.find('#sc-daily-wrap').hide();
            update_perday_rate();
        } else {
            $main.find('#sc-monthly-fields').hide();
            $main.find('#sc-daily-wrap').show();
        }
    });

    $main.find('#sc-month, #sc-year').on('change input', update_period_info);
    $main.find('#sc-monthly-amt').on('input', update_perday_rate);

    $main.find('#sc-calculate').on('click', function() {
    var pay_days = parseFloat($main.find('#sc-pay-days').val()) || 0;
    var working  = get_working_days();
    var payable  = 0, per_day = 0, err = false;

    // 🔹 CALCULATION
    if (rate_type === 'monthly') {
        var monthly = parseFloat($main.find('#sc-monthly-amt').val()) || 0;
        if (!monthly || !pay_days) { 
            err = true; 
        } else {
            per_day = monthly / working;
            payable = per_day * pay_days;
        }
    } else {
        var daily = parseFloat($main.find('#sc-daily-rate').val()) || 0;
        if (!daily || !pay_days) { 
            err = true; 
        } else {
            per_day = daily;
            payable = daily * pay_days;
        }
    }

    if (err) { 
        $main.find('#sc-err').show(); 
        return; 
    }
    $main.find('#sc-err').hide();

    // 🔹 FORMULA TEXT (NEW ✅)
    var formula_text = '';
    if (rate_type === 'monthly') {
        formula_text = 'Monthly ÷ Working Days × Payment Days';
    } else {
        formula_text = 'Daily Rate × Payment Days';
    }

    // 🔹 EXTRA DATA (existing)
    var month    = $main.find('#sc-month').val();
    var year     = parseInt($main.find('#sc-year').val());
    var off_days = get_selected_weekly_offs();

    var off_label = basis === 'exclude' && off_days.length > 0
        ? off_days.map(function(d){ return ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'][d]; }).join(', ')
        : '\u2014';

    // 🔹 RESULT BREAKDOWN (existing)
    var cells = [
        { label: 'Period',       val: month.substring(0,3) + ' ' + year },
        { label: 'Working days', val: working },
        { label: 'Payment days', val: pay_days },
        { label: 'Per-day rate', val: '\u20b9' + fmt_inr(per_day) },
        { label: 'Weekly offs',  val: off_label },
        { label: 'Basis',        val: basis === 'exclude' ? 'Excl. offs' : 'Incl. offs' },
    ];

    $main.find('#sc-result-breakdown').html(
        cells.map(function(c) {
            return '<div class="sc-result-cell">'
                + '<div class="sc-result-cell-label">' + c.label + '</div>'
                + '<div class="sc-result-cell-val">'   + c.val   + '</div>'
                + '</div>';
        }).join('')
    );

    // 🔹 SET RESULT AMOUNT
    $main.find('#sc-result-amt').text('\u20b9' + fmt_inr(payable));

    // 🔹 SET FORMULA (NEW ✅)
    $main.find('#sc-result-formula').text('Formula: ' + formula_text);

    // 🔹 SHOW RESULT
    var $res = $main.find('#sc-result');
    $res.removeClass('sc-result-visible').hide();
    setTimeout(function() { $res.show(); }, 10);
});

    update_period_info();
}