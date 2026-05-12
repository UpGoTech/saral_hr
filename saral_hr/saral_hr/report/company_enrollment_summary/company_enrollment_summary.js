frappe.query_reports["Company Enrollment Summary"] = {

    filters: [
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Company",
            width: "220px",
            default: frappe.defaults.get_user_default("Company"),
        },
        {
            fieldname: "category",
            label: __("Category"),
            fieldtype: "Select",
            options: "\nStaff\nWorker",
            width: "160px",
        },
    ],

    onload(report) {
        frappe.query_report.page.wrapper.find(".page-title").css("font-weight", "700");
        style_filter_bar();
    },

    after_datatable_render(datatable) {
        inject_card_styles();
    },

    formatter(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (!data) return value;

        if (column.fieldname === "company") {
            return `<span class="ces-company-link"
                         data-company="${frappe.utils.escape_html(data.company)}"
                         style="font-weight:700;color:#1e293b;font-size:13px;
                                cursor:pointer;letter-spacing:0.2px;">
                         🏢 ${data.company}
                    </span>`;
        }
        if (column.fieldname === "total_employees") {
            return `<span style="font-weight:700;color:#2563eb;font-size:13px;">${data.total_employees || 0}</span>`;
        }
        if (column.fieldname === "salary_structure_assigned") {
            const v = data.salary_structure_assigned || 0;
            return `<span style="color:#16a34a;font-weight:700;font-size:13px;">${v}</span>`;
        }
        if (column.fieldname === "salary_structure_unassigned") {
            const v = data.salary_structure_unassigned || 0;
            const color = v > 0 ? "#dc2626" : "#16a34a";
            return `<span style="color:${color};font-weight:700;font-size:13px;">${v}</span>`;
        }
        if (column.fieldname === "total_ctc") {
            const v = parseFloat(data.total_ctc || 0);
            return `<span style="font-weight:700;color:#7c3aed;font-size:13px;">₹ ${ces_fmt(v)}</span>`;
        }
        return value;
    },
};

// ── Style filter bar ──────────────────────────────────────────────────────────
function style_filter_bar() {
    setTimeout(() => {
        $(".page-form.flex").css({
            "background": "transparent",
            "border":     "none",
            "box-shadow": "none",
            "padding":    "12px 4px",
        });

        $(".page-form .form-group, .page-form .frappe-control").each(function () {
            $(this).css({
                "background":    "#fff",
                "border":        "1.5px solid #e2e8f0",
                "border-radius": "10px",
                "padding":       "4px 12px",
                "box-shadow":    "0 1px 4px rgba(0,0,0,0.06)",
                "margin-right":  "10px",
                "transition":    "box-shadow .2s, border-color .2s",
            });
            $(this).hover(
                function () { $(this).css({ "border-color": "#2563eb", "box-shadow": "0 2px 10px rgba(37,99,235,0.12)" }); },
                function () { $(this).css({ "border-color": "#e2e8f0", "box-shadow": "0 1px 4px rgba(0,0,0,0.06)"    }); }
            );
        });

        $(".page-form label").css({
            "font-size":      "10px",
            "font-weight":    "700",
            "color":          "#2563eb",
            "text-transform": "uppercase",
            "letter-spacing": "0.7px",
            "margin-bottom":  "2px",
        });

        $(".page-form input, .page-form select").css({
            "border":      "none",
            "outline":     "none",
            "box-shadow":  "none",
            "font-size":   "13px",
            "font-weight": "600",
            "color":       "#1e293b",
            "background":  "transparent",
            "padding":     "2px 0",
        });
    }, 300);
}

// ── Indian number formatter ───────────────────────────────────────────────────
function ces_fmt(num) {
    return parseFloat(num || 0).toLocaleString("en-IN", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    });
}

// ── Company name click → popup ────────────────────────────────────────────────
$(document).on("click", ".ces-company-link", function (e) {
    e.preventDefault();
    const company  = $(this).data("company");
    const category = frappe.query_report.get_filter_value("category") || null;
    load_employee_popup(company, category);
});

function load_employee_popup(company, category) {
    frappe.call({
        method: "saral_hr.saral_hr.report.company_enrollment_summary.company_enrollment_summary.get_company_employees",
        args: { company, category },
        freeze: true,
        freeze_message: __("Fetching employees…"),
        callback(r) {
            if (r.exc) { frappe.msgprint(__("Error loading employees.")); return; }
            show_popup(company, r.message || []);
        },
    });
}

function show_popup(company, employees) {
    const total      = employees.length;
    const assigned   = employees.filter(e => e.salary_structure !== "Not Assigned").length;
    const unassigned = total - assigned;
    const total_ctc  = employees.reduce((s, e) => s + (parseFloat(e.annual_ctc) || 0), 0);

    const rows_html = employees.length
        ? employees.map((emp, i) => {
            const ctc_str = emp.annual_ctc
                ? `₹ ${ces_fmt(emp.annual_ctc)}`
                : `<span style="color:#dc2626;font-weight:700;">—</span>`;

            const badge = emp.salary_structure === "Not Assigned"
                ? `<span style="background:#fef2f2;color:#dc2626;padding:4px 12px;border-radius:20px;
                               font-size:11px;font-weight:600;border:1px solid #fecaca;">
                       ✕ Not Assigned</span>`
                : `<span style="background:#f0fdf4;color:#16a34a;padding:4px 12px;border-radius:20px;
                               font-size:11px;font-weight:600;border:1px solid #bbf7d0;">
                       ✓ ${emp.salary_structure}</span>`;

            const row_bg = i % 2 === 0 ? "#ffffff" : "#f8fafc";
            return `
            <tr style="background:${row_bg};border-bottom:1px solid #f1f5f9;">
                <td style="padding:12px 14px;color:#94a3b8;font-size:12px;font-weight:600;">${i + 1}</td>
                <td style="padding:12px 14px;">
                    <div style="font-weight:600;color:#1e293b;font-size:13px;">${emp.full_name}</div>
                    <div style="font-size:11px;color:#94a3b8;margin-top:2px;">${emp.employee}</div>
                </td>
                
                <td style="padding:12px 14px;">
                    <span style="background:#eff6ff;color:#2563eb;padding:3px 10px;
                                 border-radius:20px;font-size:11px;font-weight:600;border:1px solid #bfdbfe;">
                        ${emp.category}
                    </span>
                </td>
                <td style="padding:12px 14px;">${badge}</td>
                <td style="padding:12px 14px;text-align:right;font-weight:700;
                           color:#1e293b;font-size:13px;">${ctc_str}</td>
            </tr>`;
        }).join("")
        : `<tr><td colspan="5" style="text-align:center;padding:50px;color:#cbd5e1;font-size:14px;">
               No employees found
           </td></tr>`;

    const html = `
    <style>
        .ces-pc {
            flex:1; min-width:120px; background:#fff; border-radius:10px;
            padding:14px 16px; text-align:center;
            box-shadow:0 1px 6px rgba(0,0,0,0.08);
            border:1px solid #e2e8f0;
            transition:transform .18s, box-shadow .18s;
        }
        .ces-pc:hover { transform:translateY(-3px); box-shadow:0 6px 18px rgba(0,0,0,0.11); }
        .ces-pc .vl  { font-size:26px; font-weight:800; line-height:1.15; margin-bottom:4px; }
        .ces-pc .lb  { font-size:10px; color:#94a3b8; text-transform:uppercase;
                       letter-spacing:.8px; font-weight:700; }
        .ces-tbl     { width:100%; border-collapse:collapse; font-family:'Inter',sans-serif; }
        .ces-tbl thead tr { background:#1e40af; }
        .ces-tbl thead th { padding:11px 14px; color:#fff; font-weight:600;
                            font-size:12px; text-align:left; letter-spacing:.3px; }
        .ces-tbl thead th:last-child { text-align:right; }
        .ces-tbl tbody tr:hover { background:#eff6ff !important; }
    </style>

    <div style="font-family:'Inter',sans-serif;">

        <!-- KPI stat row -->
        <div style="display:flex;gap:12px;margin-bottom:18px;flex-wrap:wrap;">

            <div class="ces-pc" style="border-left:4px solid #2563eb;">
                <div class="vl" style="color:#2563eb;">${total}</div>
                <div class="lb">Total Employees</div>
            </div>

            <div class="ces-pc" style="border-left:4px solid #16a34a;">
                <div class="vl" style="color:#16a34a;">${assigned}</div>
                <div class="lb">Assigned</div>
            </div>

            <div class="ces-pc" style="border-left:4px solid #dc2626;">
                <div class="vl" style="color:#dc2626;">${unassigned}</div>
                <div class="lb">Unassigned</div>
            </div>

            <div class="ces-pc" style="border-left:4px solid #0369a1; flex:2; min-width:200px;">
                <div class="vl" style="color:#0369a1; font-size:20px;">₹ ${ces_fmt(total_ctc)}</div>
                <div class="lb">Total Annual CTC</div>
            </div>

        </div>

        <!-- Table -->
        <div style="border-radius:12px;overflow:hidden;border:1px solid #e2e8f0;
                    box-shadow:0 2px 10px rgba(0,0,0,0.05);">
            <table class="ces-tbl">
                <thead>
                    <tr>
                        <th style="width:40px;">#</th>
                        <th>Employee</th>
                        
                        <th>Category</th>
                        <th>Salary Structure</th>
                        <th style="text-align:right;">Annual CTC</th>
                    </tr>
                </thead>
                <tbody>${rows_html}</tbody>
            </table>
        </div>

        <div style="margin-top:12px;text-align:right;font-size:12px;color:#94a3b8;">
            Showing ${total} employee(s) for <strong style="color:#1e293b;">${company}</strong>
        </div>
    </div>`;

    const d = new frappe.ui.Dialog({
        title: `🏢 &nbsp;${company}`,
        size: "extra-large",
        fields: [{ fieldtype: "HTML", options: html }],
        primary_action_label: __("Close"),
        primary_action() { d.hide(); },
    });

    setTimeout(() => {
        d.$wrapper.find(".modal-content").css({
            "border-radius": "16px",
            "overflow":      "hidden",
            "box-shadow":    "0 20px 60px rgba(0,0,0,0.18)",
        });
        d.$wrapper.find(".modal-header").css({
            "background":    "linear-gradient(90deg,#1e40af 0%,#2563eb 100%)",
            "padding":       "20px 28px",
            "border-bottom": "none",
        });
        d.$wrapper.find(".modal-title").css({
            "color":       "#fff",
            "font-size":   "17px",
            "font-weight": "700",
        });
        d.$wrapper.find(".btn-modal-close").css({
            "color":   "#fff",
            "opacity": "0.8",
        });
        d.$wrapper.find(".modal-body").css({ "padding": "24px 28px", "background": "#f8fafc" });
        d.$wrapper.find(".modal-footer").css({
            "border-top": "1px solid #e2e8f0",
            "padding":    "14px 28px",
            "background": "#fff",
        });
        d.$wrapper.find(".btn-primary").css({
            "background":    "linear-gradient(90deg,#1e40af,#2563eb)",
            "border":        "none",
            "border-radius": "8px",
            "font-weight":   "600",
            "box-shadow":    "0 2px 8px rgba(37,99,235,0.25)",
        });
    }, 50);

    d.show();
}

// ── Inject KPI card styles into report summary ────────────────────────────────
function inject_card_styles() {
    setTimeout(() => {
        const $summary = $(".report-summary");
        if (!$summary.length) return;

        $summary.css({
            display:      "flex",
            gap:          "16px",
            padding:      "24px 28px 8px",
            "flex-wrap":  "wrap",
            background:   "transparent",
        });

        const card_configs = [
            { color: "#2563eb", icon: "🏢" },
            { color: "#0ea5e9", icon: "👥" },
            { color: "#7c3aed", icon: "💼" },
            { color: "#d97706", icon: "🔧" },
            { color: "#dc2626", icon: "⚠️" },
        ];

        $summary.find(".summary-card").each(function (i) {
            const cfg = card_configs[i] || { color: "#475569", icon: "📊" };

            $(this).css({
                flex:            "1",
                "min-width":     "160px",
                background:      "#fff",
                border:          "1px solid #e2e8f0",
                "border-top":    `4px solid ${cfg.color}`,
                "border-radius": "14px",
                padding:         "20px 18px 18px",
                "text-align":    "center",
                "box-shadow":    "0 2px 12px rgba(0,0,0,0.06)",
                transition:      "transform .2s, box-shadow .2s",
                cursor:          "default",
            });

            // icon
            if (!$(this).find(".ces-sc-icon").length) {
                $(this).prepend(`<div class="ces-sc-icon" style="font-size:26px;margin-bottom:8px;">${cfg.icon}</div>`);
            }

            $(this).find(".summary-value").css({
                "font-size":   "36px",
                "font-weight": "800",
                "line-height": "1.1",
                "color":       cfg.color,
            });

            $(this).find(".summary-label").css({
                "font-size":      "10px",
                "color":          "#94a3b8",
                "text-transform": "uppercase",
                "letter-spacing": "0.9px",
                "margin-top":     "6px",
                "font-weight":    "700",
                "display":        "block",
            });
        });

        $summary.find(".summary-card").hover(
            function () { $(this).css({ transform: "translateY(-5px)", "box-shadow": "0 10px 28px rgba(0,0,0,0.12)" }); },
            function () { $(this).css({ transform: "translateY(0)",    "box-shadow": "0 2px 12px rgba(0,0,0,0.06)"  }); }
        );

    }, 400);
}