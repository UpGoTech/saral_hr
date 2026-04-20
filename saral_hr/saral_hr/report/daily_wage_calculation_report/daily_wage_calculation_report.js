// Copyright (c) 2026, sj and contributors
// For license information, please see license.txt

frappe.query_reports["Daily Wage Calculation Report"] = {

    filters: [
        {
            fieldname: "year",
            label:     __("Year"),
            fieldtype: "Select",
            reqd:      1,
            default:   String(new Date().getFullYear()),
            options:   (function () {
                const y = new Date().getFullYear();
                const opts = [""];
                for (let i = y - 2; i <= y + 2; i++) opts.push(String(i));
                return opts;
            })(),
        },
        {
            fieldname: "month",
            label:     __("Month"),
            fieldtype: "Select",
            reqd:      1,
            default:   "",
            options:   [
                "", "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December",
            ],
        },
        {
            fieldname: "company",
            label:     __("Company"),
            fieldtype: "MultiSelectList",
            reqd:      1,
            get_data:  txt => frappe.db.get_link_options("Company", txt),
        },
        {
            fieldname: "employee",
            label:     __("Employee"),
            fieldtype: "MultiSelectList",
            get_data:  txt => frappe.db.get_link_options("Company Link", txt),
        },
    ],

    // ── Page load hook ──────────────────────────────────────────────────
    onload(report) {

        // ── Inject CSS once ──────────────────────────────────────────
        _dwr_inject_css();

        // ── Print button ─────────────────────────────────────────────
        report.page.set_primary_action(__("Print"), function () {
            const f = report.get_values();
            if (!f.year || !f.month || !f.company?.length) {
                frappe.msgprint({
                    title:     __("Missing Filters"),
                    message:   __("Please select Year, Month and Company before printing."),
                    indicator: "orange",
                });
                return;
            }

            frappe.dom.freeze(__("Generating PDF…"));
            frappe.call({
                method: "saral_hr.saral_hr.report.daily_wage_calculation_report.daily_wage_calculation_report.print_report",
                args: {
                    filters: JSON.stringify({
                        year:     f.year    || "",
                        month:    f.month   || "",
                        company:  JSON.stringify(f.company  || []),
                        employee: JSON.stringify(f.employee || []),
                    }),
                },
                callback(r) {
                    frappe.dom.unfreeze();
                    if (r.message) {
                        const a = Object.assign(document.createElement("a"), {
                            href:   frappe.urllib.get_full_url(r.message),
                            target: "_blank",
                            rel:    "noopener noreferrer",
                        });
                        document.body.appendChild(a);
                        a.click();
                        document.body.removeChild(a);
                    }
                },
                error() {
                    frappe.dom.unfreeze();
                    frappe.msgprint({
                        title:     __("Error"),
                        message:   __("Failed to generate PDF."),
                        indicator: "red",
                    });
                },
            });
        }, "printer");

        // ── Legend + summary bar injection ───────────────────────────
        const $page = $("#page-query-report");

        function _do_inject() {
            $page.find("#dwr-legend-bar").remove();
            $page.find("#dwr-summary-bar").remove();
            const bar = _dwr_build_legend();
            const $dt = $page.find(".dt-wrapper, .frappe-datatable").first();
            if ($dt.length) {
                $dt.before(bar);
            } else {
                $page.find(".report-wrapper, .layout-main-section").first().prepend(bar);
            }
            _dwr_inject_summary_bar($page, report);
        }

        let _legendTimer = null;
        const _legendObserver = new MutationObserver(() => {
            const $dt = $page.find(".dt-wrapper, .frappe-datatable").first();
            if (!$dt.length) return;
            if ($page.find("#dwr-legend-bar").length) return;
            clearTimeout(_legendTimer);
            _legendTimer = setTimeout(_do_inject, 200);
        });

        _legendObserver.observe(
            document.getElementById("page-query-report") || document.body,
            { childList: true, subtree: true }
        );

        $(frappe.query_report).on("after_refresh", () => {
            setTimeout(_do_inject, 300);
        });
    },

    // ── Column formatter ────────────────────────────────────────────────
    formatter(value, row, column, data, default_formatter) {
        if (!data) return default_formatter(value, row, column, data);

        const fn  = column.fieldname;
        const def = v => default_formatter(v, row, column, data);

        // ── Total row ────────────────────────────────────────────────
        if (data._total || data.employee_name === "TOTAL") {
            const skip = ["sr_no", "employee", "ot_hours", "daily_rate"];
            if (skip.includes(fn) || fn.startsWith("day_")) return "";
            if (fn === "gross_pay") {
                return `<strong style="color:#198754;font-size:12px;">${def(value) || ""}</strong>`;
            }
            if (fn === "net_actual") {
                return `<strong style="color:#0d6efd;font-size:12px;">${def(value) || ""}</strong>`;
            }
            return `<strong style="color:#1a1a2e;">${def(value) || ""}</strong>`;
        }

        // ── Day cells ────────────────────────────────────────────────
        if (fn && fn.startsWith("day_")) {
            if (!value || value === "-") {
                return '<span style="color:#ddd;font-size:10px;">·</span>';
            }
            const color = _DWR_DAY_COLORS[value] || "#1a1a2e";
            const fw    = value === "HD" ? "600" : "700";
            const bg    = _DWR_DAY_BG[value] || "transparent";
            return `<span style="font-weight:${fw};color:${color};font-size:11px;background:${bg};border-radius:3px;padding:1px 3px;">${value}</span>`;
        }

        // ── Sr No ─────────────────────────────────────────────────────
        if (fn === "sr_no") {
            return `<span style="font-size:11px;color:#888;text-align:center;">${value || ""}</span>`;
        }

        // ── Employee name ─────────────────────────────────────────────
        if (fn === "employee_name") {
            return `<span style="font-weight:600;font-size:12px;color:#1a1a2e;">${value || ""}</span>`;
        }

        // ── Employee ID ───────────────────────────────────────────────
        if (fn === "employee") {
            return `<span style="font-size:11px;color:#666;font-family:monospace;">${value || ""}</span>`;
        }

        // ── Payment days ──────────────────────────────────────────────
        if (fn === "payment_days" && value) {
            return `<span style="font-weight:700;color:#0d6efd;">${def(value)}</span>`;
        }

        // ── Present days ──────────────────────────────────────────────
        if (fn === "present_days" && value) {
            return `<span style="font-weight:600;color:#1a6b1a;">${def(value)}</span>`;
        }

        // ── Absent days ───────────────────────────────────────────────
        if (fn === "absent_days" && value) {
            return `<span style="color:#c0392b;">${def(value)}</span>`;
        }

        // ── Daily rate ────────────────────────────────────────────────
        if (fn === "daily_rate" && value) {
            return `<span style="color:#0ea5e9;font-weight:600;">₹${parseFloat(value).toLocaleString("en-IN",{minimumFractionDigits:2,maximumFractionDigits:2})}</span>`;
        }

        // ── OT hours ──────────────────────────────────────────────────
        if (fn === "ot_hours" && value) {
            return `<span style="color:#0ea5e9;font-weight:600;font-size:11px;">${value}</span>`;
        }

        // ── Base pay ──────────────────────────────────────────────────
        if (fn === "base_pay" && value) {
            return `<span style="color:#0d6efd;font-weight:600;">${def(value)}</span>`;
        }

        // ── OT pay ────────────────────────────────────────────────────
        if (fn === "ot_pay" && value) {
            return `<span style="color:#b45309;font-weight:600;">${def(value)}</span>`;
        }

        // ── Gross pay ─────────────────────────────────────────────────
        if (fn === "gross_pay" && value) {
            return `<span class="dwr-gross-chip">₹${parseFloat(value).toLocaleString("en-IN",{minimumFractionDigits:2,maximumFractionDigits:2})}</span>`;
        }

        // ── SSA deduction columns ─────────────────────────────────────
        if (fn && fn.startsWith("ssa_ded_") && value) {
            return `<span style="color:#92400e;font-size:11.5px;">₹${parseFloat(value).toLocaleString("en-IN",{minimumFractionDigits:2,maximumFractionDigits:2})}</span>`;
        }

        // ── Runtime deduction columns ─────────────────────────────────
        if (fn && fn.startsWith("rt_ded_") && value) {
            return `<span style="color:#c0392b;font-weight:600;font-size:11.5px;">₹${parseFloat(value).toLocaleString("en-IN",{minimumFractionDigits:2,maximumFractionDigits:2})}</span>`;
        }

        // ── Total SSA deduction ───────────────────────────────────────
        if (fn === "total_ssa_ded" && value) {
            return `<span style="color:#92400e;font-weight:700;">−₹${parseFloat(value).toLocaleString("en-IN",{minimumFractionDigits:2,maximumFractionDigits:2})}</span>`;
        }

        // ── Total runtime deduction ───────────────────────────────────
        if (fn === "total_rt_ded" && value) {
            return `<span style="color:#c0392b;font-weight:700;">−₹${parseFloat(value).toLocaleString("en-IN",{minimumFractionDigits:2,maximumFractionDigits:2})}</span>`;
        }

        // ── Net SSA ───────────────────────────────────────────────────
        if (fn === "net_ssa" && value) {
            return `<span style="color:#b45309;font-weight:600;">₹${parseFloat(value).toLocaleString("en-IN",{minimumFractionDigits:2,maximumFractionDigits:2})}</span>`;
        }

        // ── Net actual ────────────────────────────────────────────────
        if (fn === "net_actual" && value) {
            return `<span class="dwr-net-chip">₹${parseFloat(value).toLocaleString("en-IN",{minimumFractionDigits:2,maximumFractionDigits:2})}</span>`;
        }

        return def(value);
    },
};

// ── Shared colour map ─────────────────────────────────────────────────────────
const _DWR_DAY_COLORS = {
    "P":  "#1a6b1a",
    "A":  "#c0392b",
    "HD": "#e67e22",
    "T":  "#2c3e50",
    "H":  "#27ae60",
    "H✓": "#0d6efd",
};

const _DWR_DAY_BG = {
    "P":  "rgba(26,107,26,0.08)",
    "A":  "rgba(192,57,43,0.08)",
    "HD": "rgba(230,126,34,0.10)",
    "T":  "rgba(44,62,80,0.07)",
    "H":  "rgba(39,174,96,0.08)",
    "H✓": "rgba(13,110,253,0.10)",
};

// ── CSS injection ─────────────────────────────────────────────────────────────
function _dwr_inject_css() {
    if (document.getElementById("dwr-report-styles")) return;
    const style = document.createElement("style");
    style.id = "dwr-report-styles";
    style.innerHTML = `
        /* Gross chip */
        .dwr-gross-chip {
            display: inline-block;
            font-weight: 700;
            color: #198754;
            font-size: 12px;
            background: linear-gradient(135deg, #f0fdf4, #dcfce7);
            border: 1px solid #86efac;
            border-radius: 5px;
            padding: 1px 7px;
        }

        /* Net actual chip */
        .dwr-net-chip {
            display: inline-block;
            font-weight: 800;
            color: #0d6efd;
            font-size: 12px;
            background: linear-gradient(135deg, #eff6ff, #dbeafe);
            border: 1px solid #93c5fd;
            border-radius: 5px;
            padding: 1px 7px;
        }

        /* Summary bar */
        #dwr-summary-bar {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            padding: 10px 0 8px;
            margin-bottom: 6px;
            border-bottom: 1px solid #e5e7eb;
        }
        .dwr-sum-card {
            flex: 1;
            min-width: 110px;
            background: #fff;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 8px 12px;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 2px;
        }
        .dwr-sum-val {
            font-size: 17px;
            font-weight: 800;
            line-height: 1;
        }
        .dwr-sum-lbl {
            font-size: 10px;
            font-weight: 600;
            color: #6b7280;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            text-align: center;
        }
        .dwr-sum-emp   .dwr-sum-val { color: #1a1a2e; }
        .dwr-sum-days  .dwr-sum-val { color: #0d6efd; }
        .dwr-sum-gross .dwr-sum-val { color: #198754; font-size: 15px; }
        .dwr-sum-rtded .dwr-sum-val { color: #c0392b; font-size: 15px; }
        .dwr-sum-net   {
            border: 2px solid #93c5fd !important;
            background: linear-gradient(135deg, #eff6ff, #dbeafe) !important;
        }
        .dwr-sum-net   .dwr-sum-val { color: #0d6efd; font-size: 15px; }
        .dwr-sum-net   .dwr-sum-lbl { color: #1d4ed8; font-weight: 700; }

        /* Legend bar */
        #dwr-legend-bar {
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            padding: 6px 10px;
            margin: 0 0 6px;
            background: linear-gradient(90deg, #f8f9ff, #eef2ff);
            border: 1px solid #c7d2fe;
            border-radius: 6px;
            font-family: inherit;
            gap: 4px;
        }
        .dwr-lgd-item {
            display: inline-flex;
            align-items: center;
            gap: 3px;
            margin-right: 10px;
            white-space: nowrap;
        }
        .dwr-lgd-code {
            font-weight: 700;
            font-size: 11.5px;
            border-radius: 3px;
            padding: 1px 4px;
        }
        .dwr-lgd-label {
            font-size: 11.5px;
            color: #444;
        }
        .dwr-lgd-note {
            margin-left: auto;
            font-size: 10.5px;
            color: #6366f1;
            font-weight: 500;
            white-space: nowrap;
        }

        /* Breakdown popup */
        .dwr-popup-overlay {
            position: fixed;
            inset: 0;
            background: rgba(0,0,0,0.35);
            z-index: 10000;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .dwr-popup {
            background: #fff;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.18);
            min-width: 440px;
            max-width: 600px;
            width: 90vw;
            max-height: 90vh;
            overflow-y: auto;
            font-family: inherit;
        }
        .dwr-popup-hdr {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 14px 18px 10px;
            border-bottom: 1px solid #e5e7eb;
            background: linear-gradient(90deg, #f8f9ff, #eef2ff);
            border-radius: 12px 12px 0 0;
        }
        .dwr-popup-title {
            font-size: 14px;
            font-weight: 700;
            color: #1a1a2e;
        }
        .dwr-popup-sub {
            font-size: 11px;
            color: #6b7280;
            margin-top: 2px;
        }
        .dwr-popup-close {
            background: none;
            border: none;
            font-size: 18px;
            cursor: pointer;
            color: #6b7280;
            line-height: 1;
            padding: 2px 6px;
            border-radius: 4px;
            transition: background 0.12s;
        }
        .dwr-popup-close:hover { background: #f1f5f9; }
        .dwr-popup-body { padding: 14px 18px 18px; }

        /* Gross → Net flow inside popup */
        .dwr-flow {
            display: flex;
            align-items: center;
            gap: 6px;
            flex-wrap: wrap;
            margin-bottom: 14px;
            padding: 10px 14px;
            background: #f8faff;
            border: 1px solid #c7d2fe;
            border-radius: 8px;
        }
        .dwr-flow-block {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 2px;
        }
        .dwr-flow-val {
            font-size: 16px;
            font-weight: 800;
            line-height: 1;
        }
        .dwr-flow-lbl {
            font-size: 9.5px;
            font-weight: 600;
            color: #6b7280;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }
        .dwr-flow-arrow {
            font-size: 16px;
            color: #94a3b8;
            font-weight: 300;
        }
        .dwr-flow-gross  .dwr-flow-val { color: #198754; }
        .dwr-flow-ded    .dwr-flow-val { color: #c0392b; }
        .dwr-flow-net    .dwr-flow-val { color: #0d6efd; }
        .dwr-flow-net {
            background: linear-gradient(135deg,#eff6ff,#dbeafe);
            border: 1.5px solid #93c5fd;
            border-radius: 7px;
            padding: 6px 12px;
        }

        /* Component breakdown table inside popup */
        .dwr-breakdown-tbl {
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
        }
        .dwr-breakdown-tbl th {
            background: #eef2ff;
            color: #4338ca;
            font-size: 10px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            padding: 6px 10px;
            border-bottom: 2px solid #c7d2fe;
            text-align: left;
        }
        .dwr-breakdown-tbl th.r { text-align: right; }
        .dwr-breakdown-tbl td {
            padding: 7px 10px;
            border-bottom: 1px solid #f0f0f0;
            vertical-align: middle;
        }
        .dwr-breakdown-tbl tr:last-child td { border-bottom: none; }
        .dwr-breakdown-tbl tr:hover td { background: #f8f9ff; }
        .dwr-bd-ssa  { text-align: right; color: #92400e; font-size: 12px; }
        .dwr-bd-rt   { text-align: right; color: #c0392b; font-weight: 600; font-size: 12px; }
        .dwr-bd-diff { text-align: right; font-size: 10px; font-weight: 700; }
        .dwr-bd-diff.up { color: #c0392b; }
        .dwr-bd-diff.dn { color: #16a34a; }
        .dwr-bd-type-badge {
            font-size: 9.5px;
            font-weight: 700;
            padding: 1px 6px;
            border-radius: 20px;
        }
        .dwr-bd-type-calc    { background: #ede9fe; color: #7c3aed; border: 1px solid #c4b5fd; }
        .dwr-bd-type-fixed   { background: #f0f9ff; color: #0369a1; border: 1px solid #bae6fd; }
        .dwr-bd-type-special { background: #fdf4ff; color: #a21caf; border: 1px solid #e879f9; }
        .dwr-bd-abbr {
            display: inline-block;
            font-size: 9.5px;
            font-weight: 700;
            color: #6366f1;
            background: rgba(99,102,241,0.10);
            border-radius: 3px;
            padding: 1px 4px;
            margin-right: 3px;
        }
        .dwr-bd-total-row td {
            background: #eef2ff !important;
            font-weight: 700;
            border-top: 2px solid #c7d2fe;
        }
        .dwr-bd-net-row td {
            background: linear-gradient(90deg,#eff6ff,#dbeafe) !important;
            font-weight: 800;
            border-top: 2px solid #93c5fd;
            font-size: 13px;
        }
        .dwr-bd-net-row .dwr-bd-rt { color: #0d6efd !important; }
    `;
    document.head.appendChild(style);
}

// ── Summary bar ───────────────────────────────────────────────────────────────
function _dwr_inject_summary_bar($page, report) {
    $page.find("#dwr-summary-bar").remove();
    if (!report || !report.data || !report.data.length) return;

    const rows = report.data.filter(r => !r._total && r.employee_name !== "TOTAL");
    if (!rows.length) return;

    const sum = (fn) => rows.reduce((s, r) => s + (parseFloat(r[fn]) || 0), 0);
    const fmt = (n) => "₹" + n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

    const empCount    = rows.length;
    const totalDays   = sum("payment_days");
    const totalGross  = sum("gross_pay");
    const totalRtDed  = sum("total_rt_ded");
    const totalNet    = sum("net_actual");

    const bar = $(`
        <div id="dwr-summary-bar">
            <div class="dwr-sum-card dwr-sum-emp">
                <div class="dwr-sum-val">${empCount}</div>
                <div class="dwr-sum-lbl">Employees</div>
            </div>
            <div class="dwr-sum-card dwr-sum-days">
                <div class="dwr-sum-val">${totalDays % 1 === 0 ? totalDays : totalDays.toFixed(1)}</div>
                <div class="dwr-sum-lbl">Payment Days</div>
            </div>
            <div class="dwr-sum-card dwr-sum-gross">
                <div class="dwr-sum-val">${fmt(totalGross)}</div>
                <div class="dwr-sum-lbl">Total Gross</div>
            </div>
            <div class="dwr-sum-card dwr-sum-rtded">
                <div class="dwr-sum-val">−${fmt(totalRtDed)}</div>
                <div class="dwr-sum-lbl">Total Deductions (Actual)</div>
            </div>
            <div class="dwr-sum-card dwr-sum-net">
                <div class="dwr-sum-val">${fmt(totalNet)}</div>
                <div class="dwr-sum-lbl">Total Net Payable</div>
            </div>
        </div>
    `);

    const $legend = $page.find("#dwr-legend-bar");
    if ($legend.length) {
        $legend.after(bar);
    } else {
        const $dt = $page.find(".dt-wrapper, .frappe-datatable").first();
        if ($dt.length) $dt.before(bar);
    }
}

// ── Legend builder ─────────────────────────────────────────────────────────────
function _dwr_build_legend() {
    const LEGEND = [
        { code: "P",  color: "#1a6b1a", bg: "rgba(26,107,26,0.08)",   label: "Present"          },
        { code: "A",  color: "#c0392b", bg: "rgba(192,57,43,0.08)",   label: "Absent"           },
        { code: "HD", color: "#e67e22", bg: "rgba(230,126,34,0.10)",  label: "Half Day"         },
        { code: "T",  color: "#2c3e50", bg: "rgba(44,62,80,0.07)",    label: "On Tour"          },
        { code: "H",  color: "#27ae60", bg: "rgba(39,174,96,0.08)",   label: "Holiday (unpaid)" },
        { code: "H✓", color: "#0d6efd", bg: "rgba(13,110,253,0.10)", label: "Holiday (paid)"   },
    ];

    const items = LEGEND.map(({ code, color, bg, label }) =>
        `<span class="dwr-lgd-item">
            <span class="dwr-lgd-code" style="color:${color};background:${bg};">${code}</span>
            <span class="dwr-lgd-label">– ${label}</span>
        </span>`
    ).join("");

    const note = `
        <span class="dwr-lgd-note">
            SSA = Salary Structure Assignment (fixed) &nbsp;|&nbsp;
            Actual = Runtime deduction on live gross &nbsp;|&nbsp;
            <strong>Click any row</strong> to view breakdown
        </span>
    `;

    return $(
        `<div id="dwr-legend-bar">
            <span style="font-weight:700;font-size:11.5px;color:#6c7680;margin-right:8px;white-space:nowrap;">Legend :</span>
            ${items}
            ${note}
        </div>`
    );
}

// ── Row click → breakdown popup ───────────────────────────────────────────────
$(document).on("click", "#page-query-report .dt-row", function () {
    // Find the row index
    const $row = $(this);
    const report = frappe.query_report;
    if (!report || !report.data) return;

    // Get employee name from the row cells
    const cells = $row.find(".dt-cell__content");
    if (!cells.length) return;

    // Try to find employee from rendered text
    let empName = "";
    cells.each(function () {
        const txt = $(this).text().trim();
        if (txt && txt.length > 2 && !txt.match(/^[\d₹,.\-+:]+$/) && !txt.match(/^[PAHTD✓·]+$/)) {
            empName = txt;
            return false;
        }
    });

    if (!empName) return;

    const rowData = report.data.find(r =>
        r.employee_name === empName && !r._total && r.employee_name !== "TOTAL"
    );
    if (!rowData) return;

    _dwr_show_breakdown_popup(rowData, report.columns || []);
});

function _dwr_show_breakdown_popup(data, columns) {
    // Remove existing popup
    $(".dwr-popup-overlay").remove();

    const ssaCols = columns.filter(c => c.fieldname && c.fieldname.startsWith("ssa_ded_"));
    const rtCols  = columns.filter(c => c.fieldname && c.fieldname.startsWith("rt_ded_"));

    const gross    = parseFloat(data.gross_pay   || 0);
    const rtDed    = parseFloat(data.total_rt_ded || 0);
    const ssaDed   = parseFloat(data.total_ssa_ded || 0);
    const netActual = parseFloat(data.net_actual  || 0);
    const netSsa   = parseFloat(data.net_ssa      || 0);

    const fmt = (n) => "₹" + (parseFloat(n) || 0).toLocaleString("en-IN", {
        minimumFractionDigits: 2, maximumFractionDigits: 2
    });
    const fmtDays = (n) => {
        const v = parseFloat(n) || 0;
        return v === Math.floor(v) ? String(v) : v.toFixed(1);
    };

    // Build component rows
    let compRows = "";
    if (ssaCols.length) {
        ssaCols.forEach((sc) => {
            const safe    = sc.fieldname.replace("ssa_ded_", "");
            const rtFn    = "rt_ded_" + safe;
            const ssaAmt  = parseFloat(data[sc.fieldname] || 0);
            const rtAmt   = parseFloat(data[rtFn] || 0);
            const diff    = rtAmt - ssaAmt;

            const lbl     = (sc.label || sc.fieldname).replace("SSA: ", "").replace("Actual: ", "");

            // Guess type from name
            const lower = lbl.toLowerCase();
            let typeBadge;
            if (lower.includes("pf") || lower.includes("esic") || lower.includes("esi")) {
                typeBadge = '<span class="dwr-bd-type-badge dwr-bd-type-calc">Calc</span>';
            } else if (lower.includes("pt") || lower.includes("lwf") || lower.includes("labour")) {
                typeBadge = '<span class="dwr-bd-type-badge dwr-bd-type-special">Special</span>';
            } else {
                typeBadge = '<span class="dwr-bd-type-badge dwr-bd-type-fixed">Fixed</span>';
            }

            const abbr = (sc.label || "").replace("SSA: ", "").substring(0, 6);

            let diffHtml = "";
            if (Math.abs(diff) > 0.01) {
                const sign  = diff > 0 ? "+" : "";
                const cls   = diff > 0 ? "up" : "dn";
                diffHtml    = `<span class="dwr-bd-diff ${cls}">${sign}${fmt(diff)}</span>`;
            } else {
                diffHtml = `<span style="color:#94a3b8;font-size:10px;">=</span>`;
            }

            compRows += `
                <tr>
                    <td><span class="dwr-bd-abbr">${abbr}</span>${lbl}</td>
                    <td style="text-align:center;">${typeBadge}</td>
                    <td class="dwr-bd-ssa">${ssaAmt > 0 ? fmt(ssaAmt) : '<span style="color:#ccc;">—</span>'}</td>
                    <td class="dwr-bd-rt">${rtAmt > 0 ? fmt(rtAmt) : '<span style="color:#ccc;">—</span>'}</td>
                    <td class="dwr-bd-diff">${diffHtml}</td>
                </tr>
            `;
        });
    } else {
        compRows = `<tr><td colspan="5" style="text-align:center;color:#94a3b8;padding:14px;">No deduction components found</td></tr>`;
    }

    const month_str = (frappe.query_report.get_values() || {}).month || "";
    const year_str  = (frappe.query_report.get_values() || {}).year  || "";

    const popup = $(`
        <div class="dwr-popup-overlay">
            <div class="dwr-popup">
                <div class="dwr-popup-hdr">
                    <div>
                        <div class="dwr-popup-title">💰 Runtime Salary Breakdown</div>
                        <div class="dwr-popup-sub">
                            ${data.employee_name || ""} &nbsp;|&nbsp; ${data.employee || ""}
                            &nbsp;|&nbsp; ${month_str} ${year_str}
                        </div>
                    </div>
                    <button class="dwr-popup-close" title="Close">✕</button>
                </div>
                <div class="dwr-popup-body">

                    <!-- Attendance snapshot -->
                    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px;">
                        <div style="flex:1;min-width:80px;background:#f8f9ff;border:1px solid #e5e7eb;border-radius:6px;padding:7px 10px;text-align:center;">
                            <div style="font-size:15px;font-weight:800;color:#0d6efd;">${fmtDays(data.payment_days)}</div>
                            <div style="font-size:9px;font-weight:600;color:#6b7280;text-transform:uppercase;">Payment Days</div>
                        </div>
                        <div style="flex:1;min-width:80px;background:#f0fdf4;border:1px solid #bbf7d0;border-radius:6px;padding:7px 10px;text-align:center;">
                            <div style="font-size:15px;font-weight:800;color:#1a6b1a;">${fmtDays(data.present_days)}</div>
                            <div style="font-size:9px;font-weight:600;color:#6b7280;text-transform:uppercase;">Present</div>
                        </div>
                        <div style="flex:1;min-width:80px;background:#fff5f5;border:1px solid #fecaca;border-radius:6px;padding:7px 10px;text-align:center;">
                            <div style="font-size:15px;font-weight:800;color:#c0392b;">${fmtDays(data.absent_days)}</div>
                            <div style="font-size:9px;font-weight:600;color:#6b7280;text-transform:uppercase;">Absent</div>
                        </div>
                        <div style="flex:1;min-width:80px;background:#fffbeb;border:1px solid #fde68a;border-radius:6px;padding:7px 10px;text-align:center;">
                            <div style="font-size:15px;font-weight:800;color:#b45309;">${fmtDays(data.half_days)}</div>
                            <div style="font-size:9px;font-weight:600;color:#6b7280;text-transform:uppercase;">Half Day</div>
                        </div>
                        <div style="flex:1;min-width:80px;background:#f0fdf4;border:1px solid #a3d9b1;border-radius:6px;padding:7px 10px;text-align:center;">
                            <div style="font-size:15px;font-weight:800;color:#27ae60;">${fmtDays(data.holiday_days)}</div>
                            <div style="font-size:9px;font-weight:600;color:#6b7280;text-transform:uppercase;">Holiday</div>
                        </div>
                        ${data.ot_hours ? `
                        <div style="flex:1;min-width:80px;background:#f0f9ff;border:1px solid #bae6fd;border-radius:6px;padding:7px 10px;text-align:center;">
                            <div style="font-size:15px;font-weight:800;color:#0ea5e9;">${data.ot_hours}</div>
                            <div style="font-size:9px;font-weight:600;color:#6b7280;text-transform:uppercase;">OT Hours</div>
                        </div>` : ""}
                    </div>

                    <!-- Gross → Deduction → Net flow -->
                    <div class="dwr-flow">
                        <div class="dwr-flow-block dwr-flow-gross">
                            <div class="dwr-flow-val">${fmt(gross)}</div>
                            <div class="dwr-flow-lbl">Gross Pay</div>
                        </div>
                        <div class="dwr-flow-arrow">−</div>
                        <div class="dwr-flow-block dwr-flow-ded">
                            <div class="dwr-flow-val">${fmt(rtDed)}</div>
                            <div class="dwr-flow-lbl">Actual Deductions</div>
                        </div>
                        <div class="dwr-flow-arrow">=</div>
                        <div class="dwr-flow-block dwr-flow-net">
                            <div class="dwr-flow-val">${fmt(netActual)}</div>
                            <div class="dwr-flow-lbl">Net Actual</div>
                        </div>
                        <div style="margin-left:auto;text-align:right;padding-left:10px;border-left:1px solid #c7d2fe;">
                            <div style="font-size:11px;color:#92400e;font-weight:600;">SSA Ded: −${fmt(ssaDed)}</div>
                            <div style="font-size:12px;color:#b45309;font-weight:700;margin-top:3px;">Net SSA: ${fmt(netSsa)}</div>
                        </div>
                    </div>

                    <!-- Component table -->
                    <div style="font-size:11px;font-weight:700;color:#4338ca;margin-bottom:6px;text-transform:uppercase;letter-spacing:0.05em;">
                        Deduction Components
                    </div>
                    <table class="dwr-breakdown-tbl">
                        <thead>
                            <tr>
                                <th>Component</th>
                                <th style="text-align:center;">Type</th>
                                <th class="r">SSA Fixed</th>
                                <th class="r">Actual (Runtime)</th>
                                <th class="r">Diff</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${compRows}
                        </tbody>
                        <tfoot>
                            <tr class="dwr-bd-total-row">
                                <td colspan="2">Total Deductions</td>
                                <td class="dwr-bd-ssa">−${fmt(ssaDed)}</td>
                                <td class="dwr-bd-rt">−${fmt(rtDed)}</td>
                                <td></td>
                            </tr>
                            <tr class="dwr-bd-net-row">
                                <td colspan="2">Net Payable</td>
                                <td class="dwr-bd-ssa" style="color:#b45309 !important;">${fmt(netSsa)}</td>
                                <td class="dwr-bd-rt" style="color:#0d6efd !important;font-size:14px;">${fmt(netActual)}</td>
                                <td></td>
                            </tr>
                        </tfoot>
                    </table>

                </div>
            </div>
        </div>
    `);

    popup.find(".dwr-popup-close").on("click", () => popup.remove());
    popup.on("click", function (e) {
        if ($(e.target).hasClass("dwr-popup-overlay")) popup.remove();
    });

    $("body").append(popup);
}