frappe.query_reports["Company Enrollment Summary"] = {

    filters: [
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Company",
            default: frappe.defaults.get_user_default("Company"),
        },
        {
            fieldname: "category",
            label: __("Category"),
            fieldtype: "Select",
            options: "\nStaff\nWorker",
        },
    ],

    datatable_options: {
        serialNoColumn: true,
        columnMinWidth: 50,
    },

    onload(report) {
        if (!document.getElementById("ces-global-style")) {
            const s = document.createElement("style");
            s.id = "ces-global-style";
            s.textContent = `
                /* Sr.No column width fix */
                .dt-cell--col-0,
                .dt-cell--col-0 .dt-cell__content,
                .dt-header--col-0,
                .dt-header--col-0 .dt-cell__content {
                    width: 52px !important;
                    min-width: 52px !important;
                    max-width: 52px !important;
                }
                .dt-cell--col-0 .dt-cell__content {
                    overflow: visible !important;
                    text-overflow: unset !important;
                    white-space: normal !important;
                }
                /* Hide filter bar */
                .page-form.flex {
                    display: none !important;
                }
                /* Scrollable padding */
                .dt-scrollable {
                    padding-bottom: 8px !important;
                    box-sizing: border-box !important;
                }
                .dt-scrollable .dt-row:last-child .dt-cell__content,
                .dt-body .dt-row:last-child {
                    margin-bottom: 8px !important;
                }

                /* ── Summary card overhaul ─────────────────────────── */
                .report-summary {
                    display: flex !important;
                    gap: 12px !important;
                    padding: 14px 16px !important;
                    flex-wrap: wrap !important;
                    background: #f1f3f5 !important;
                    border: none !important;
                    border-radius: 0 !important;
                    box-shadow: none !important;
                    margin: 0 !important;
                }

                /* Target both .summary-card AND .report-summary-item (Frappe v14/v15 differ) */
                .report-summary .summary-card,
                .report-summary .report-summary-item {
                    flex: 1 !important;
                    min-width: 140px !important;
                    background: #ffffff !important;
                    border: 1.5px solid #e2e8f0 !important;
                    border-radius: 10px !important;
                    padding: 14px 18px 12px !important;
                    text-align: center !important;
                    box-shadow: 0 1px 4px rgba(0,0,0,0.07) !important;
                    transition: box-shadow .18s, transform .18s !important;
                    margin: 0 !important;
                    display: flex !important;
                    flex-direction: column !important;
                    align-items: center !important;
                    justify-content: center !important;
                    cursor: default !important;
                }
                .report-summary .summary-card:hover,
                .report-summary .report-summary-item:hover {
                    box-shadow: 0 4px 14px rgba(0,0,0,0.13) !important;
                    transform: translateY(-2px) !important;
                }

                /* Label — always on top */
                .report-summary .summary-card .summary-label,
                .report-summary .report-summary-item .summary-label,
                .report-summary .summary-card .report-summary-label,
                .report-summary .report-summary-item .report-summary-label {
                    display: block !important;
                    order: -1 !important;
                    font-size: 10px !important;
                    font-weight: 700 !important;
                    color: #6b7280 !important;
                    text-transform: uppercase !important;
                    letter-spacing: 0.8px !important;
                    margin-bottom: 6px !important;
                    margin-top: 0 !important;
                    white-space: nowrap !important;
                }

                /* Value */
                .report-summary .summary-card .summary-value,
                .report-summary .report-summary-item .summary-value,
                .report-summary .summary-card .report-summary-value,
                .report-summary .report-summary-item .report-summary-value {
                    display: block !important;
                    font-size: 30px !important;
                    font-weight: 800 !important;
                    line-height: 1.1 !important;
                    margin-top: 0 !important;
                }
            `;
            document.head.appendChild(s);
        }
    },

    after_datatable_render(datatable) {
        _ces_style_summary_cards();
    },

    formatter(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (!data) return value;

        if (column.fieldname === "company") {
            return `<span class="ces-company-link"
                         data-company="${frappe.utils.escape_html(data.company)}"
                         style="font-weight:600;color:var(--text-color,#1f272e);
                                font-size:13px;cursor:pointer;">
                         ${data.company}
                    </span>`;
        }
        if (column.fieldname === "total_employees") {
            return `<span style="font-weight:600;color:var(--text-color,#1f272e);
                                 font-size:13px;">${data.total_employees || 0}</span>`;
        }
        if (column.fieldname === "salary_structure_assigned") {
            const v = data.salary_structure_assigned || 0;
            return `<span style="color:#28a745;font-weight:600;font-size:13px;">${v}</span>`;
        }
        if (column.fieldname === "salary_structure_unassigned") {
            const v = data.salary_structure_unassigned || 0;
            const color = v > 0 ? "#e03e3e" : "#28a745";
            return `<span style="color:${color};font-weight:600;font-size:13px;">${v}</span>`;
        }
        if (column.fieldname === "total_ctc") {
            const v = parseFloat(data.total_ctc || 0);
            return `<span style="font-weight:600;color:var(--text-color,#1f272e);
                                 font-size:13px;">&#8377; ${ces_fmt(v)}</span>`;
        }
        return value;
    },
};

// ── Indian number formatter ───────────────────────────────────────────────────
function ces_fmt(num) {
    return parseFloat(num || 0).toLocaleString("en-IN", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    });
}

// ── Company name click → per-company popup ────────────────────────────────────
$(document).on("click", ".ces-company-link", function (e) {
    e.preventDefault();
    const company  = $(this).data("company");
    const category = frappe.query_report.get_filter_value("category") || null;
    load_employee_popup(company, category, null);
});

function load_employee_popup(company, category, filter_mode) {
    frappe.call({
        method: "saral_hr.saral_hr.report.company_enrollment_summary.company_enrollment_summary.get_company_employees",
        args: { company, category },
        freeze: true,
        freeze_message: __("Fetching employees\u2026"),
        callback(r) {
            if (r.exc) { frappe.msgprint(__("Error loading employees.")); return; }
            show_company_popup(company, r.message || [], filter_mode);
        },
    });
}

function show_company_popup(company, all_employees, filter_mode) {
    const total      = all_employees.length;
    const assigned   = all_employees.filter(e => e.salary_structure !== "Not Assigned").length;
    const unassigned = total - assigned;
    const total_ctc  = all_employees.reduce((s, e) => s + (parseFloat(e.annual_ctc) || 0), 0);

    let employees = all_employees;
    if (filter_mode === "assigned")   employees = all_employees.filter(e => e.salary_structure !== "Not Assigned");
    if (filter_mode === "unassigned") employees = all_employees.filter(e => e.salary_structure === "Not Assigned");

    const html = _build_company_popup_html(
        company, employees, total, assigned, unassigned, total_ctc, filter_mode
    );

    const d = new frappe.ui.Dialog({
        title: `${company} \u2014 Employee Details`,
        size: "extra-large",
        fields: [{ fieldtype: "HTML", fieldname: "content", options: html }],
        primary_action_label: __("Close"),
        primary_action() { d.hide(); },
    });
    d.show();

    setTimeout(() => {
        d.$wrapper.find(".modal-body").css({ padding: "16px 20px", background: "var(--bg-color,#f8f9fa)" });

        d.$wrapper.find(".ces-kpi-card[data-filter]").on("click", function () {
            const f = $(this).data("filter");
            d.hide();
            show_company_popup(company, all_employees, f === "all" ? null : f);
        });
    }, 50);
}

function _build_company_popup_html(company, employees, total, assigned, unassigned, total_ctc, filter_mode) {
    const rows_html = employees.length
        ? employees.map((emp, i) => {
            const ctc_str = emp.annual_ctc
                ? `&#8377; ${ces_fmt(emp.annual_ctc)}`
                : `<span style="color:#e03e3e;font-weight:600;">\u2014</span>`;

            const badge = emp.salary_structure === "Not Assigned"
                ? `<span style="background:#fff5f5;color:#e03e3e;border:1px solid #ffd5d5;
                               padding:2px 10px;border-radius:4px;font-size:11px;font-weight:500;
                               white-space:nowrap;">\u2715&nbsp;Not Assigned</span>`
                : `<span style="background:#eafaf1;color:#28a745;border:1px solid #c3e6cb;
                               padding:2px 10px;border-radius:4px;font-size:11px;font-weight:500;
                               white-space:nowrap;">\u2713&nbsp;${emp.salary_structure}</span>`;

            const row_bg = i % 2 === 0 ? "#fff" : "#f8fafc";
            return `
            <tr style="background:${row_bg};border-bottom:1px solid var(--border-color,#d1d8dd);">
                <td style="padding:9px 0;color:#8d99a6;font-size:12px;width:44px;min-width:44px;max-width:44px;text-align:center;vertical-align:middle;">${i + 1}</td>
                <td style="padding:9px 14px;vertical-align:middle;">
                    <div style="font-weight:500;color:var(--text-color,#1f272e);font-size:13px;line-height:1.4;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${emp.full_name}</div>
                    <div style="font-size:11px;color:#8d99a6;margin-top:1px;">${emp.employee}</div>
                </td>
                <td style="padding:9px 14px;white-space:nowrap;vertical-align:middle;">
                    <span style="background:var(--control-bg,#f0f2f5);color:var(--text-muted,#6c7680);padding:2px 9px;border-radius:4px;font-size:11px;font-weight:500;border:1px solid var(--border-color,#d1d8dd);">${emp.category}</span>
                </td>
                <td style="padding:9px 14px;white-space:nowrap;vertical-align:middle;">${badge}</td>
                <td style="padding:9px 14px;text-align:right;font-weight:500;color:var(--text-color,#1f272e);font-size:13px;white-space:nowrap;vertical-align:middle;">${ctc_str}</td>
            </tr>`;
        }).join("")
        : `<tr><td colspan="5" style="text-align:center;padding:40px;color:#8d99a6;font-size:13px;">No employees found</td></tr>`;

    const filter_label = filter_mode === "assigned"
        ? `<span style="background:#eafaf1;color:#28a745;border:1px solid #c3e6cb;padding:1px 10px;border-radius:10px;font-size:11px;font-weight:500;margin-left:8px;">Assigned only</span>`
        : filter_mode === "unassigned"
        ? `<span style="background:#fff5f5;color:#e03e3e;border:1px solid #ffd5d5;padding:1px 10px;border-radius:10px;font-size:11px;font-weight:500;margin-left:8px;">Unassigned only</span>`
        : "";

    return `${_popup_shared_styles()}
    <div style="font-family:var(--font-stack,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif);">
        <div style="display:flex;gap:10px;margin-bottom:16px;flex-wrap:wrap;">
            <div class="ces-kpi-card clickable ${!filter_mode ? 'active-filter' : ''}" data-filter="all" title="Show all">
                <span class="ces-kpi-lbl">Total</span>
                <span class="ces-kpi-val" style="color:#4361ee;">${total}</span>
            </div>
            <div class="ces-kpi-card clickable ${filter_mode === 'assigned' ? 'active-filter' : ''}" data-filter="assigned" title="Show assigned only">
                <span class="ces-kpi-lbl">Assigned</span>
                <span class="ces-kpi-val" style="color:#28a745;">${assigned}</span>
            </div>
            <div class="ces-kpi-card clickable ${filter_mode === 'unassigned' ? 'active-filter' : ''}" data-filter="unassigned" title="Show unassigned only">
                <span class="ces-kpi-lbl">Unassigned</span>
                <span class="ces-kpi-val" style="color:#e03e3e;">${unassigned}</span>
            </div>
            <div class="ces-kpi-card" style="flex:2;min-width:180px;">
                <span class="ces-kpi-lbl">Total Annual CTC</span>
                <span class="ces-kpi-val" style="color:var(--text-color,#1f272e);font-size:20px;">&#8377;&nbsp;${ces_fmt(total_ctc)}</span>
            </div>
        </div>
        <div style="display:flex;align-items:center;margin-bottom:8px;">
            <span style="font-size:11px;font-weight:700;color:#4b5563;text-transform:uppercase;letter-spacing:.6px;">Employees</span>
            ${filter_label}
        </div>
        <div style="border:1px solid var(--border-color,#d1d8dd);border-radius:6px;overflow:hidden;background:#fff;">
            <table class="ces-tbl">
                <colgroup><col style="width:44px"><col style="width:260px"><col style="width:110px"><col style="width:200px"><col style="width:150px"></colgroup>
                <thead><tr>
                    <th class="th-sr">#</th>
                    <th>Employee</th>
                    <th>Category</th>
                    <th>Salary Structure</th>
                    <th class="th-ctc">Annual CTC</th>
                </tr></thead>
                <tbody>${rows_html}</tbody>
            </table>
        </div>
        <div style="margin-top:10px;font-size:11px;color:#8d99a6;">
            Showing <strong style="color:var(--text-color,#1f272e);">${employees.length}</strong>
            of <strong style="color:var(--text-color,#1f272e);">${total}</strong>
            employee(s) for <strong style="color:var(--text-color,#1f272e);">${company}</strong>
        </div>
    </div>`;
}

// ── Shared popup CSS ──────────────────────────────────────────────────────────
function _popup_shared_styles() {
    return `<style>
        .ces-kpi-card {
            flex: 1; min-width: 110px;
            background: #fff;
            border: 1.5px solid #e2e8f0;
            border-radius: 10px;
            padding: 14px 18px;
            text-align: center;
            transition: box-shadow .15s, border-color .15s;
        }
        .ces-kpi-card.clickable { cursor: pointer; }
        .ces-kpi-card.clickable:hover {
            box-shadow: 0 4px 14px rgba(0,0,0,0.12);
            border-color: #4361ee;
        }
        .ces-kpi-card.active-filter {
            border-color: #4361ee;
            box-shadow: 0 0 0 3px rgba(67,97,238,0.12);
        }
        .ces-kpi-lbl {
            display: block;
            font-size: 10px; font-weight: 700;
            color: #6b7280;
            text-transform: uppercase; letter-spacing: .8px;
            margin-bottom: 6px;
        }
        .ces-kpi-val {
            display: block;
            font-size: 28px; font-weight: 800;
            line-height: 1.15;
        }
        .ces-tbl { width:100%; border-collapse:collapse; table-layout:fixed; }
        .ces-tbl thead tr { background:var(--control-bg,#f0f2f5); border-bottom:2px solid var(--border-color,#d1d8dd); }
        .ces-tbl thead th { padding:9px 14px; color:#4b5563; font-size:11px; font-weight:700; text-align:left; letter-spacing:.4px; text-transform:uppercase; white-space:nowrap; }
        .ces-tbl thead th.th-sr  { text-align:center; padding:9px 0; }
        .ces-tbl thead th.th-ctc { text-align:right; }
        .ces-tbl tbody tr:hover  { background:#eef2ff !important; }

        .ces-all-tbl { width:100%; border-collapse:collapse; table-layout:fixed; }
        .ces-all-tbl thead tr { background:var(--control-bg,#f0f2f5); border-bottom:2px solid var(--border-color,#d1d8dd); }
        .ces-all-tbl thead th { padding:9px 14px; color:#4b5563; font-size:11px; font-weight:700; text-align:left; letter-spacing:.4px; text-transform:uppercase; white-space:nowrap; }
        .ces-all-tbl thead th.th-sr  { text-align:center; padding:9px 0; }
        .ces-all-tbl thead th.th-ctc { text-align:right; }
        .ces-all-tbl tbody tr:hover  { background:#eef2ff !important; }
    </style>`;
}

// ── Style summary cards to match popup KPI card look ─────────────────────────
function _ces_style_summary_cards() {
    // Colors per card index: Companies, Employees, Staff, Workers, Unassigned
    const card_configs = [
        { value_color: "#4361ee", border_color: "#4361ee", clickable: false },
        { value_color: "#2ec4b6", border_color: "#2ec4b6", clickable: true  },
        { value_color: "#7b2d8b", border_color: "#7b2d8b", clickable: false },
        { value_color: "#f4a261", border_color: "#f4a261", clickable: false },
        { value_color: "#e63946", border_color: "#e63946", clickable: false },
    ];

    // Retry up to 10 times (every 200ms = 2s total) to handle slow render
    let attempts = 0;
    const MAX_ATTEMPTS = 10;

    function _try_apply() {
        attempts++;

        // Support both Frappe v14 (.summary-card) and v15 (.report-summary-item)
        const $cards = $(".report-summary .summary-card, .report-summary .report-summary-item");

        if (!$cards.length) {
            if (attempts < MAX_ATTEMPTS) {
                setTimeout(_try_apply, 200);
            }
            return;
        }

        $cards.each(function (i) {
            const cfg   = card_configs[i] || { value_color: "#6b7280", border_color: "#6b7280", clickable: false };
            const $card = $(this);

            // Avoid re-applying if already styled
            if ($card.data("ces-styled")) return;
            $card.data("ces-styled", true);

            // Move label before value so it appears on top
            const $label = $card.find(".summary-label, .report-summary-label").first().detach();
            $card.prepend($label);

            // Card base styles
            $card.css({
                "flex":           "1",
                "min-width":      "140px",
                "background":     "#ffffff",
                "border":         `1.5px solid ${cfg.border_color}`,
                "border-radius":  "10px",
                "padding":        "14px 18px 12px",
                "text-align":     "center",
                "box-shadow":     "0 1px 4px rgba(0,0,0,0.08)",
                "transition":     "box-shadow .18s, transform .18s",
                "cursor":         cfg.clickable ? "pointer" : "default",
                "margin":         "0",
                "display":        "flex",
                "flex-direction": "column",
                "align-items":    "center",
                "justify-content":"center",
            });

            // Label styles
            $card.find(".summary-label, .report-summary-label").css({
                "display":        "block",
                "font-size":      "10px",
                "font-weight":    "700",
                "color":          "#6b7280",
                "text-transform": "uppercase",
                "letter-spacing": "0.8px",
                "margin-bottom":  "6px",
                "margin-top":     "0",
                "white-space":    "nowrap",
            });

            // Value styles
            $card.find(".summary-value, .report-summary-value").css({
                "display":     "block",
                "font-size":   "30px",
                "font-weight": "800",
                "line-height": "1.1",
                "color":       cfg.value_color,
                "margin-top":  "0",
            });

            // Remove stray icons
            $card.find(".ces-sc-icon").remove();

            // Hover effects
            $card.off("mouseenter.ces mouseleave.ces");
            $card.on("mouseenter.ces", function () {
                $(this).css({ "box-shadow": "0 6px 18px rgba(0,0,0,0.14)", "transform": "translateY(-2px)" });
            }).on("mouseleave.ces", function () {
                $(this).css({ "box-shadow": "0 1px 4px rgba(0,0,0,0.08)", "transform": "translateY(0)" });
            });

            // Click handler — only "Number of Employees" card (index 1)
            $card.off("click.ces");
            if (cfg.clickable) {
                $card.on("click.ces", function () {
                    _load_all_employees_popup();
                });
            }
        });
    }

    // Start first attempt immediately, then retry if cards not yet in DOM
    _try_apply();
}

// ── All-Employees popup (triggered from "Number of Employees" summary card) ───
function _load_all_employees_popup() {
    const category = frappe.query_report.get_filter_value("category") || null;
    const company  = frappe.query_report.get_filter_value("company")  || null;

    const report_data = frappe.query_report.data || [];
    const companies   = company
        ? [company]
        : report_data.map(r => r.company).filter(Boolean);

    if (!companies.length) {
        frappe.msgprint(__("No companies found in report."));
        return;
    }

    frappe.freeze(__("Fetching all employees\u2026"));

    const promises = companies.map(c =>
        new Promise((resolve) => {
            frappe.call({
                method: "saral_hr.saral_hr.report.company_enrollment_summary.company_enrollment_summary.get_company_employees",
                args: { company: c, category },
                callback(r) {
                    resolve((r.message || []).map(e => ({ ...e, company: c })));
                },
            });
        })
    );

    Promise.all(promises).then(results => {
        frappe.unfreeze();
        _show_all_employees_popup(results.flat());
    });
}
function _show_all_employees_popup(all_employees) {
    const total      = all_employees.length;
    const assigned   = all_employees.filter(e => e.salary_structure !== "Not Assigned").length;
    const unassigned = total - assigned;
    const total_ctc  = all_employees.reduce((s, e) => s + (parseFloat(e.annual_ctc) || 0), 0);

    const rows_html = all_employees.length
        ? all_employees.map((emp, i) => {
            const ctc_str = emp.annual_ctc
                ? `&#8377; ${ces_fmt(emp.annual_ctc)}`
                : `<span style="color:#e03e3e;font-weight:600;">&#8212;</span>`;

            const badge = emp.salary_structure === "Not Assigned"
                ? `<span style="background:#fff5f5;color:#e03e3e;border:1px solid #ffd5d5;
                               padding:2px 10px;border-radius:4px;font-size:11px;font-weight:500;
                               white-space:nowrap;">&#x2715;&nbsp;Not Assigned</span>`
                : `<span style="background:#eafaf1;color:#28a745;border:1px solid #c3e6cb;
                               padding:2px 10px;border-radius:4px;font-size:11px;font-weight:500;
                               white-space:nowrap;">&#x2713;&nbsp;${emp.salary_structure}</span>`;

            const row_bg = i % 2 === 0 ? "#fff" : "#f8fafc";
            return `
            <tr style="background:${row_bg};border-bottom:1px solid var(--border-color,#d1d8dd);">
                <td style="padding:9px 0;color:#8d99a6;font-size:12px;width:44px;min-width:44px;max-width:44px;text-align:center;vertical-align:middle;">${i + 1}</td>
                <td style="padding:9px 14px;vertical-align:middle;">
                    <div style="font-weight:500;color:var(--text-color,#1f272e);font-size:13px;line-height:1.4;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${emp.full_name}</div>
                    <div style="font-size:11px;color:#8d99a6;margin-top:1px;">${emp.employee}</div>
                </td>
                <td style="padding:9px 14px;vertical-align:middle;white-space:nowrap;">
                    <span style="background:var(--control-bg,#f0f2f5);color:var(--text-muted,#6c7680);padding:2px 9px;border-radius:4px;font-size:11px;font-weight:500;border:1px solid var(--border-color,#d1d8dd);">${emp.company}</span>
                </td>
                <td style="padding:9px 14px;vertical-align:middle;white-space:nowrap;">
                    <span style="background:var(--control-bg,#f0f2f5);color:var(--text-muted,#6c7680);padding:2px 9px;border-radius:4px;font-size:11px;font-weight:500;border:1px solid var(--border-color,#d1d8dd);">${emp.category}</span>
                </td>
                <td style="padding:9px 14px;white-space:nowrap;vertical-align:middle;">${badge}</td>
                <td style="padding:9px 14px;text-align:right;font-weight:500;color:var(--text-color,#1f272e);font-size:13px;white-space:nowrap;vertical-align:middle;">${ctc_str}</td>
            </tr>`;
        }).join("")
        : `<tr><td colspan="6" style="text-align:center;padding:40px;color:#8d99a6;font-size:13px;">No employees found</td></tr>`;

    const html = `${_popup_shared_styles()}
    <div style="font-family:var(--font-stack,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif);">

        <div style="display:flex;gap:10px;margin-bottom:16px;flex-wrap:wrap;">
            <div class="ces-kpi-card">
                <span class="ces-kpi-lbl">Total</span>
                <span class="ces-kpi-val" style="color:#4361ee;">${total}</span>
            </div>
            <div class="ces-kpi-card">
                <span class="ces-kpi-lbl">Assigned</span>
                <span class="ces-kpi-val" style="color:#28a745;">${assigned}</span>
            </div>
            <div class="ces-kpi-card">
                <span class="ces-kpi-lbl">Unassigned</span>
                <span class="ces-kpi-val" style="color:#e63946;">${unassigned}</span>
            </div>
            <div class="ces-kpi-card" style="flex:2;min-width:180px;">
                <span class="ces-kpi-lbl">Total Annual CTC</span>
                <span class="ces-kpi-val" style="color:var(--text-color,#1f272e);font-size:20px;">&#8377;&nbsp;${ces_fmt(total_ctc)}</span>
            </div>
        </div>

        <div style="margin-bottom:8px;">
            <span style="font-size:11px;font-weight:700;color:#4b5563;text-transform:uppercase;letter-spacing:.6px;">All Employees</span>
        </div>

        <div style="border:1px solid var(--border-color,#d1d8dd);border-radius:6px;overflow:hidden;background:#fff;">
            <table class="ces-all-tbl">
                <colgroup>
                    <col style="width:44px">
                    <col style="width:210px">
                    <col style="width:160px">
                    <col style="width:90px">
                    <col style="width:180px">
                    <col style="width:130px">
                </colgroup>
                <thead><tr>
                    <th class="th-sr">#</th>
                    <th>Employee</th>
                    <th>Company</th>
                    <th>Category</th>
                    <th>Salary Structure</th>
                    <th class="th-ctc">Annual CTC</th>
                </tr></thead>
                <tbody>${rows_html}</tbody>
            </table>
        </div>

        <div style="margin-top:10px;font-size:11px;color:#8d99a6;">
            Showing <strong style="color:var(--text-color,#1f272e);">${total}</strong>
            employee(s) across all companies
        </div>
    </div>`;

    const d = new frappe.ui.Dialog({
        title: __("All Employees"),
        size: "extra-large",
        fields: [{ fieldtype: "HTML", fieldname: "content", options: html }],
        primary_action_label: __("Close"),
        primary_action() { d.hide(); },
    });
    d.show();

    setTimeout(() => {
        d.$wrapper.find(".modal-body").css({
            padding:    "16px 20px",
            background: "var(--bg-color,#f8f9fa)",
        });
    }, 50);
}