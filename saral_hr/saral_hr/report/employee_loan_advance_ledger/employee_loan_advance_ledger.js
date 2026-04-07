frappe.query_reports["Employee Loan Advance Ledger"] = {

    filters: [
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Company",
            on_change: function () {
                frappe.query_report.set_filter_value("employee", "");
                frappe.query_report.refresh();
            },
        },
 {
    fieldname: "employee",
    label: __("Employee"),
    fieldtype: "Link",
    options: "Company Link",   // ← was "Employee", must match the actual DocType
    only_select: 1,
    get_query: function () {
        const company = frappe.query_report.get_filter_value("company");
        const filters = {};
        if (company) filters.company = company;
        return {
            query: "saral_hr.saral_hr.report.employee_loan_advance_ledger.employee_loan_advance_ledger.get_employees_with_loans",
            filters: filters,
        };
    },
},
{
            fieldname: "type",
            label: __("Loan Type"),
            fieldtype: "Select",
            options: "\nLoan\nAdvance",
        },
        {
            fieldname: "status",
            label: __("Status"),
            fieldtype: "Select",
            options: "\nActive\nCompleted",
        },
    ],

  onload(report) {
    const emp_field = report.get_filter("employee");
    if (emp_field && emp_field.df) emp_field.df.only_select = 1;
    setTimeout(() => frappe.query_report.refresh(), 300);

    report.page.set_primary_action(__("Print"), function () {
        const f = report.get_values();

        if (!f.company) {
            frappe.msgprint({
                title:     __("Missing Filters"),
                message:   __("Please select Company before printing."),
                indicator: "orange",
            });
            return;
        }

        frappe.dom.freeze(__("Generating PDF…"));

        frappe.call({
            method: "saral_hr.saral_hr.report.employee_loan_advance_ledger.employee_loan_advance_ledger.print_report",
            args: {
                filters: JSON.stringify({
                    company:  f.company  || "",
                    employee: f.employee || "",
                    type:     f.type     || "",
                    status:   f.status   || "",
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
},
    formatter(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (!data) return value;

        if (data.loan_id === "TOTAL") {
            const cf = ["amount", "total_paid", "outstanding"];
            if (cf.includes(column.fieldname)) {
                const num = parseFloat(data[column.fieldname] || 0);
                const fmt = "₹\u00A0" + num.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
                if (column.fieldname === "outstanding" && num > 0)
                    return `<strong style="color:#C62828;">${fmt}</strong>`;
                return `<strong>${fmt}</strong>`;
            }
            if (column.fieldname === "loan_id") return `<strong style="font-size:13px;">TOTAL</strong>`;
            return `<strong>${value}</strong>`;
        }

        const cf = ["amount", "total_paid", "outstanding"];
        if (cf.includes(column.fieldname)) {
            const raw = data[column.fieldname];
            if (raw === "" || raw === undefined || raw === null) return "";
            const num = parseFloat(raw);
            const fmt = "₹\u00A0" + num.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
            if (column.fieldname === "outstanding" && num > 0)
                return `<span style="color:#C62828;font-weight:600;">${fmt}</span>`;
            if (column.fieldname === "outstanding" && num === 0)
                return `<span style="color:#2E7D32;font-weight:500;">${fmt}</span>`;
            return fmt;
        }

        if (column.fieldname === "status" && data.status) {
            const cfg = {
                "Active":    { color: "#B45309", bg: "#FEF3C7", dot: "#F59E0B" },
                "Completed": { color: "#065F46", bg: "#D1FAE5", dot: "#10B981" },
            };
            const c = cfg[data.status] || { color: "#374151", bg: "#F3F4F6", dot: "#9CA3AF" };
            return `<span style="display:inline-flex;align-items:center;gap:5px;color:${c.color};
                        background:${c.bg};padding:3px 10px;border-radius:20px;
                        font-size:11px;font-weight:600;white-space:nowrap;">
                        <span style="width:6px;height:6px;border-radius:50%;
                            background:${c.dot};display:inline-block;"></span>
                        ${data.status}
                    </span>`;
        }

        if (column.fieldname === "detail_btn" && data.detail_btn) {
            const lid  = data.detail_btn;
            const safe = lid.replace(/[^a-zA-Z0-9_-]/g, "_");
            return `<button
                        id="detbtn_${safe}"
                        onclick="window._show_loan_modal(event,'${lid}')"
                        style="display:inline-flex;align-items:center;gap:5px;
                               padding:4px 12px;font-size:11px;font-weight:500;
                               background:#1E40AF;color:#fff;border:none;
                               border-radius:6px;cursor:pointer;white-space:nowrap;
                               letter-spacing:0.2px;">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
                             stroke="currentColor" stroke-width="2.5"
                             style="flex-shrink:0;">
                          <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2"/>
                          <rect x="9" y="3" width="6" height="4" rx="1"/>
                          <line x1="9" y1="12" x2="15" y2="12"/>
                          <line x1="9" y1="16" x2="13" y2="16"/>
                        </svg>
                        Schedule
                    </button>`;
        }

        return value;
    },
};

// ── Inject global CSS once ──────────────────────────────────────────────────
(function () {
    if (document.getElementById("_ela_modal_style")) return;
    const s = document.createElement("style");
    s.id = "_ela_modal_style";
    s.textContent = `
        #_ela_overlay {
            position: fixed; inset: 0; z-index: 1050;
            background: rgba(15,23,42,0.45);
            display: flex; align-items: center; justify-content: center;
            padding: 24px;
            animation: _ela_fadein 0.15s ease;
        }
        @keyframes _ela_fadein { from { opacity:0 } to { opacity:1 } }
        @keyframes _ela_slidein { from { opacity:0; transform:translateY(12px) } to { opacity:1; transform:translateY(0) } }

        #_ela_modal {
            background: #fff;
            border-radius: 12px;
            width: 100%;
            max-width: 860px;
            max-height: 85vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            box-shadow: 0 20px 60px rgba(0,0,0,0.2), 0 4px 16px rgba(0,0,0,0.1);
            animation: _ela_slidein 0.18s ease;
        }

        #_ela_modal_head {
            background: linear-gradient(135deg, #1E3A8A 0%, #1E40AF 100%);
            padding: 18px 22px;
            flex-shrink: 0;
        }

        #_ela_modal_meta {
            background: #F8FAFC;
            border-bottom: 1px solid #E2E8F0;
            padding: 12px 22px;
            display: flex;
            flex-wrap: wrap;
            gap: 20px;
            flex-shrink: 0;
        }

        #_ela_modal_body {
            overflow-y: auto;
            flex: 1;
        }

        #_ela_sched_table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }

        #_ela_sched_table thead th {
            background: #F1F5F9;
            color: #475569;
            font-weight: 600;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.6px;
            padding: 10px 16px;
            border-bottom: 1.5px solid #CBD5E1;
            white-space: nowrap;
            position: sticky;
            top: 0;
        }

        #_ela_sched_table tbody tr {
            border-bottom: 1px solid #F1F5F9;
            transition: background 0.1s;
        }

        #_ela_sched_table tbody tr:hover {
            background: #F8FAFF !important;
        }

        #_ela_sched_table tbody td {
            padding: 11px 16px;
            font-size: 13px;
            color: #1E293B;
        }

        #_ela_sched_table tfoot tr {
            background: #EFF6FF;
            border-top: 2px solid #BFDBFE;
        }

        #_ela_sched_table tfoot td {
            padding: 11px 16px;
            font-weight: 600;
            font-size: 13px;
        }

        ._ela_badge {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 3px 10px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: 600;
            white-space: nowrap;
        }

        ._ela_dot {
            width: 6px; height: 6px;
            border-radius: 50%;
            display: inline-block;
            flex-shrink: 0;
        }
    `;
    document.head.appendChild(s);
})();

// ── Helpers ─────────────────────────────────────────────────────────────────
window._ela_fmt = (n) => {
    if (n === "" || n === undefined || n === null) return "—";
    return "₹\u00A0" + parseFloat(n).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

window._ela_badge = (s) => {
    const cfg = {
        "Deducted": { color:"#065F46", bg:"#D1FAE5", dot:"#10B981" },
        "Pending":  { color:"#92400E", bg:"#FEF3C7", dot:"#F59E0B" },
        "Deferred": { color:"#1E3A8A", bg:"#DBEAFE", dot:"#3B82F6" },
    };
    const c = cfg[s] || { color:"#374151", bg:"#F3F4F6", dot:"#9CA3AF" };
    return `<span class="_ela_badge" style="color:${c.color};background:${c.bg};">
                <span class="_ela_dot" style="background:${c.dot};"></span>${s}
            </span>`;
};

window._ela_close_modal = function () {
    const overlay = document.getElementById("_ela_overlay");
    if (overlay) overlay.remove();
};

// ── Main modal function ──────────────────────────────────────────────────────
window._show_loan_modal = function (event, loan_id) {
    event.stopPropagation();

    // Remove existing overlay
    const old = document.getElementById("_ela_overlay");
    if (old) old.remove();

    // Build overlay + modal shell
    const overlay = document.createElement("div");
    overlay.id = "_ela_overlay";
    overlay.onclick = function (e) {
        if (e.target === overlay) window._ela_close_modal();
    };

    overlay.innerHTML = `
        <div id="_ela_modal">

            <!-- Header -->
            <div id="_ela_modal_head">
                <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;">
                    <div style="display:flex;align-items:center;gap:10px;">
                        <div style="width:34px;height:34px;border-radius:8px;
                                    background:rgba(255,255,255,0.15);
                                    display:flex;align-items:center;justify-content:center;flex-shrink:0;">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
                                 stroke="white" stroke-width="2" stroke-linecap="round">
                                <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2"/>
                                <rect x="9" y="3" width="6" height="4" rx="1"/>
                                <line x1="9" y1="12" x2="15" y2="12"/>
                                <line x1="9" y1="16" x2="13" y2="16"/>
                            </svg>
                        </div>
                        <div>
                            <div style="color:rgba(255,255,255,0.6);font-size:11px;
                                        text-transform:uppercase;letter-spacing:0.8px;
                                        font-weight:600;margin-bottom:2px;">
                                Repayment Schedule
                            </div>
                            <div style="color:#fff;font-size:15px;font-weight:600;
                                        letter-spacing:0.2px;">
                                ${loan_id}
                            </div>
                        </div>
                    </div>
                    <div style="display:flex;align-items:center;gap:8px;">
                        <button onclick="window._ela_print_schedule('${loan_id}')"
                                style="display:inline-flex;align-items:center;gap:6px;
                                       padding:6px 14px;border-radius:6px;
                                       background:rgba(255,255,255,0.15);border:1px solid rgba(255,255,255,0.25);
                                       cursor:pointer;color:#fff;font-size:12px;font-weight:600;
                                       letter-spacing:0.3px;">
                            <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
                                 stroke="white" stroke-width="2.5" stroke-linecap="round">
                                <polyline points="6 9 6 2 18 2 18 9"/>
                                <path d="M6 18H4a2 2 0 01-2-2v-5a2 2 0 012-2h16a2 2 0 012 2v5a2 2 0 01-2 2h-2"/>
                                <rect x="6" y="14" width="12" height="8"/>
                            </svg>
                            Print
                        </button>
                        <button onclick="window._ela_close_modal()"
                                style="width:30px;height:30px;border-radius:6px;
                                       background:rgba(255,255,255,0.12);border:none;
                                       cursor:pointer;display:flex;align-items:center;
                                       justify-content:center;flex-shrink:0;">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                                 stroke="white" stroke-width="2.5" stroke-linecap="round">
                                <line x1="18" y1="6" x2="6" y2="18"/>
                                <line x1="6" y1="6" x2="18" y2="18"/>
                            </svg>
                        </button>
                    </div>
                </div>
            </div>

            <!-- Meta bar -->
            <div id="_ela_modal_meta">
                <div style="font-size:12px;color:#64748B;display:flex;flex-direction:column;gap:2px;">
                    <span style="font-size:10px;text-transform:uppercase;letter-spacing:0.6px;
                                 font-weight:600;color:#94A3B8;">Employee Name</span>
                    <span id="_ela_m_emp" style="color:#1E293B;font-weight:500;">—</span>
                </div>
                <div style="width:1px;background:#E2E8F0;"></div>
                <div style="font-size:12px;color:#64748B;display:flex;flex-direction:column;gap:2px;">
                    <span style="font-size:10px;text-transform:uppercase;letter-spacing:0.6px;
                                 font-weight:600;color:#94A3B8;">Company</span>
                    <span id="_ela_m_co" style="color:#1E293B;font-weight:500;">—</span>
                </div>
                <div style="width:1px;background:#E2E8F0;"></div>
                <div style="font-size:12px;color:#64748B;display:flex;flex-direction:column;gap:2px;">
                    <span style="font-size:10px;text-transform:uppercase;letter-spacing:0.6px;
                                 font-weight:600;color:#94A3B8;">Type</span>
                    <span id="_ela_m_type" style="color:#1E293B;font-weight:500;">—</span>
                </div>
                <div style="width:1px;background:#E2E8F0;"></div>
                <div style="font-size:12px;color:#64748B;display:flex;flex-direction:column;gap:2px;">
                    <span style="font-size:10px;text-transform:uppercase;letter-spacing:0.6px;
                                 font-weight:600;color:#94A3B8;">Loan Amount</span>
                    <span id="_ela_m_amt" style="color:#1E40AF;font-weight:600;">—</span>
                </div>
                <div style="width:1px;background:#E2E8F0;"></div>
                <div style="font-size:12px;color:#64748B;display:flex;flex-direction:column;gap:2px;">
                    <span style="font-size:10px;text-transform:uppercase;letter-spacing:0.6px;
                                 font-weight:600;color:#94A3B8;">Taken On</span>
                    <span id="_ela_m_taken_on" style="color:#1E293B;font-weight:500;">—</span>
                </div>
                <div style="width:1px;background:#E2E8F0;"></div>
                <div style="font-size:12px;color:#64748B;display:flex;flex-direction:column;gap:2px;">
                    <span style="font-size:10px;text-transform:uppercase;letter-spacing:0.6px;
                                 font-weight:600;color:#94A3B8;">Status</span>
                    <span id="_ela_m_status">—</span>
                </div>
            </div>

            <!-- Body -->
            <div id="_ela_modal_body">
                <div style="padding:40px;text-align:center;color:#94A3B8;">
                    <div style="width:32px;height:32px;border:2.5px solid #BFDBFE;
                                border-top-color:#1E40AF;border-radius:50%;
                                animation:_ela_fadein 0.3s linear infinite;
                                margin:0 auto 12px;">
                    </div>
                    <div style="font-size:13px;">Loading repayment schedule…</div>
                </div>
            </div>

        </div>
    `;

    document.body.appendChild(overlay);

    // Inject spinner animation separately
    const spinEl = overlay.querySelector("#_ela_modal_body div > div");
    if (spinEl) {
        spinEl.style.animation = "none";
        spinEl.style.border = "2.5px solid #BFDBFE";
        spinEl.style.borderTopColor = "#1E40AF";
        spinEl.style.borderRadius = "50%";
        spinEl.style.width = "32px";
        spinEl.style.height = "32px";
        let deg = 0;
        const spinInterval = setInterval(() => {
            if (!document.getElementById("_ela_overlay")) { clearInterval(spinInterval); return; }
            deg = (deg + 8) % 360;
            if (spinEl) spinEl.style.transform = `rotate(${deg}deg)`;
        }, 16);
    }

    // ── Fetch data ──────────────────────────────────────────────────────────
    frappe.call({
        method: "saral_hr.saral_hr.report.employee_loan_advance_ledger.employee_loan_advance_ledger.get_loan_detail",
        args: { loan_id: loan_id },
        freeze: false,

        callback(r) {
            const body = document.getElementById("_ela_modal_body");
            if (!body) return;

            if (!r.message || !r.message.rows || !r.message.rows.length) {
                body.innerHTML = `
                    <div style="padding:48px;text-align:center;color:#94A3B8;">
                        <div style="font-size:32px;margin-bottom:12px;">📭</div>
                        <div style="font-size:14px;font-weight:500;color:#64748B;">No repayment schedule found</div>
                        <div style="font-size:12px;margin-top:4px;">for ${loan_id}</div>
                    </div>`;
                return;
            }

            const d   = r.message;
            const fmt = window._ela_fmt;

            // Fill meta bar - show employee name with ID
            const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
            
            // Display employee name with ID in parentheses
            const employeeDisplay = d.employee_name ? `${d.employee_name} (${d.employee || "—"})` : (d.employee || "—");
            set("_ela_m_emp", employeeDisplay);
            set("_ela_m_co",       d.company || "—");
            set("_ela_m_type",     d.type || "—");
            set("_ela_m_amt",      fmt(d.amount));
            set("_ela_m_taken_on", d.taken_on || "—");

            const statusEl = document.getElementById("_ela_m_status");
            if (statusEl) {
                const isActive = d.status === "Active";
                statusEl.innerHTML = `<span class="_ela_badge"
                    style="color:${isActive ? '#92400E' : '#065F46'};
                           background:${isActive ? '#FEF3C7' : '#D1FAE5'};">
                    <span class="_ela_dot" style="background:${isActive ? '#F59E0B' : '#10B981'};"></span>
                    ${d.status}
                </span>`;
            }

            // Build table rows
            let ts = 0, ta = 0, rows_html = "";
            d.rows.forEach((item) => {
                ts += parseFloat(item.scheduled_amt || 0);
                ta += parseFloat(item.actual_amt    || 0);

                const rb  = parseFloat(item.running_bal || 0);
                const rb_style = rb === 0
                    ? "color:#059669;font-weight:600;"
                    : "color:#DC2626;font-weight:500;";

                const def_html = item.deferred_to
                    ? `<span style="color:#1E40AF;font-size:12px;">→ ${item.deferred_to}</span>`
                    : `<span style="color:#CBD5E1;">—</span>`;

                rows_html += `
                    <tr>
                        <td style="text-align:left;">${item.month || "—"}<\/td>
                        <td style="text-align:right;">${fmt(item.scheduled_amt)}<\/td>
                        <td style="text-align:right;">${fmt(item.actual_amt)}<\/td>
                        <td style="text-align:center;">${window._ela_badge(item.status)}<\/td>
                        <td style="text-align:center;">${def_html}<\/td>
                        <td style="text-align:right;${rb_style}">${fmt(item.running_bal)}<\/td>
                    <\/tr>
                `;
            });

            const fr  = d.rows[d.rows.length - 1].running_bal;
            const frn = parseFloat(fr || 0);
            const frs = frn > 0
                ? "color:#DC2626;" : "color:#059669;";

            body.innerHTML = `
                <table id="_ela_sched_table">
                    <thead>
                        <tr>
                            <th style="text-align:left;width:120px;">Month</th>
                            <th style="text-align:right;">Base EMI</th>
                            <th style="text-align:right;">Actual Deducted</th>
                            <th style="text-align:center;">Status</th>
                            <th style="text-align:center;">Deferred To</th>
                            <th style="text-align:right;">Running Balance</th>
                        <\/tr>
                    </thead>
                    <tbody>${rows_html}</tbody>
                    <tfoot>
                        <tr>
                            <td style="font-weight:600;">TOTAL<\/td>
                            <td style="text-align:right;font-weight:600;">${fmt(ts)}<\/td>
                            <td style="text-align:right;font-weight:600;">${fmt(ta)}<\/td>
                            <td><\/td>
                            <td><\/td>
                            <td style="text-align:right;${frs}">${fmt(fr)}<\/td>
                        <\/tr>
                    </tfoot>
                <\/table>`;
        },

        error(xhr) {
            const body = document.getElementById("_ela_modal_body");
            if (!body) return;
            const status = xhr && xhr.status ? xhr.status : "?";
            let detail = "";
            try {
                const resp = JSON.parse(xhr.responseText || "{}");
                detail = resp.exception || resp._error_message || "";
            } catch(e) { detail = (xhr.responseText || "").substring(0, 300); }

            body.innerHTML = `
                <div style="padding:28px 24px;">
                    <div style="background:#FEF2F2;border:1px solid #FECACA;border-radius:8px;padding:16px 20px;">
                        <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
                                 stroke="#DC2626" stroke-width="2" stroke-linecap="round">
                                <circle cx="12" cy="12" r="10"/>
                                <line x1="12" y1="8" x2="12" y2="12"/>
                                <line x1="12" y1="16" x2="12.01" y2="16"/>
                            </svg>
                            <span style="font-weight:600;font-size:13px;color:#991B1B;">
                                HTTP ${status} — Request failed
                            </span>
                        </div>
                        <ul style="margin:0;padding-left:18px;font-size:12px;color:#7F1D1D;line-height:1.8;">
                            <li>Ensure <code>@frappe.whitelist()</code> is on <code>get_loan_detail</code></li>
                            <li>Argument name must be exactly <code>loan_id</code></li>
                            <li>Run <code>bench clear-cache</code> after changes</li>
                        </ul>
                        ${detail ? `<div style="margin-top:10px;font-size:11px;color:#9CA3AF;
                            word-break:break-all;">${detail}</div>` : ""}
                    </div>
                </div>`;
        },
    });

   window._ela_print_schedule = function(loan_id) {
    frappe.dom.freeze(__("Generating PDF…"));
    frappe.call({
        method: "saral_hr.saral_hr.report.employee_loan_advance_ledger.employee_loan_advance_ledger.print_loan_schedule",
        args: { loan_id: loan_id },
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
            frappe.msgprint({ title: __("Error"), message: __("Failed to generate PDF."), indicator: "red" });
        }
    });
};
};