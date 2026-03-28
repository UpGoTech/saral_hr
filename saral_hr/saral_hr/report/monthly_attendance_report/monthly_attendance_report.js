frappe.query_reports["Monthly Attendance Report"] = {
    filters: [
        {
            fieldname: "year",
            label: __("Year"),
            fieldtype: "Select",
            reqd: 1,
            default: String(new Date().getFullYear()),
            options: (function () {
                const y = new Date().getFullYear(), opts = [""];
                for (let i = y - 2; i <= y + 2; i++) opts.push(String(i));
                return opts;
            })(),
        },
        {
            fieldname: "month",
            label: __("Month"),
            fieldtype: "Select",
            reqd: 1,
            default: "",
            options: [
                "", "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December",
            ],
        },
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "MultiSelectList",
            reqd: 1,
            get_data: txt => frappe.db.get_link_options("Company", txt),
        },
        {
            fieldname: "category",
            label: __("Category"),
            fieldtype: "Link",
            options: "Category",
            default: "",
        },
        {
            fieldname: "division",
            label: __("Division"),
            fieldtype: "MultiSelectList",
            get_data: txt => frappe.db.get_link_options("Division", txt),
        },
        {
            fieldname: "employee",
            label: __("Employee"),
            fieldtype: "MultiSelectList",
            get_data: txt => frappe.db.get_link_options("Company Link", txt),
        },
    ],

    onload(report) {
        // ── Print button ──────────────────────────────────────────────
        report.page.set_primary_action(__("Print"), function () {
            const f = report.get_values();
            if (!f.year || !f.month || !f.company?.length) {
                frappe.msgprint({
                    title: __("Missing Filters"),
                    message: __("Please select Year, Month and Company before printing."),
                    indicator: "orange",
                });
                return;
            }
            frappe.dom.freeze(__("Generating PDF…"));
            frappe.call({
                method: "saral_hr.saral_hr.report.monthly_attendance_report.monthly_attendance_report.print_report",
                args: {
                    filters: JSON.stringify({
                        year:     f.year     || "",
                        month:    f.month    || "",
                        company:  JSON.stringify(f.company  || []),
                        category: f.category || "",
                        division: JSON.stringify(f.division || []),
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

        // ── Legend injection via MutationObserver ─────────────────────
        // Watch for the datatable appearing in the DOM — most reliable
        // method across all Frappe versions since wrapper is undefined here.
        const $page = $("#page-query-report");

        function _do_inject() {
            $page.find("#mar-legend-bar").remove();
            const bar  = _mar_build_legend();
            const $dt  = $page.find(".dt-wrapper, .frappe-datatable").first();
            if ($dt.length) {
                $dt.before(bar);
            } else {
                $page.find(".report-wrapper, .layout-main-section").first().prepend(bar);
            }
        }

        // MutationObserver fires whenever the datatable is added/updated
        let _legendTimer = null;
        const _legendObserver = new MutationObserver(() => {
            const $dt = $page.find(".dt-wrapper, .frappe-datatable").first();
            if (!$dt.length) return;
            if ($page.find("#mar-legend-bar").length) return; // already present
            clearTimeout(_legendTimer);
            _legendTimer = setTimeout(_do_inject, 200);
        });

        _legendObserver.observe(
            document.getElementById("page-query-report") || document.body,
            { childList: true, subtree: true }
        );

        // Also fire on after_refresh as a belt-and-suspenders approach
        $(frappe.query_report).on("after_refresh", () => {
            setTimeout(_do_inject, 300);
        });
    },

    formatter(value, row, column, data, default_formatter) {
        if (!data) return default_formatter(value, row, column, data);

        const fn  = column.fieldname;
        const def = v => default_formatter(v, row, column, data);

        if (fn && fn.startsWith("day_")) {
            if (!value || value === "-") {
                return '<span style="color:#ccc;">-</span>';
            }
            const colors = {
                P:   "#1a6b1a",
                A:   "#c0392b",
                HD:  "#e67e22",
                T:   "#2c3e50",
                H:   "#27ae60",
                WO:  "#2980b9",
                LWP: "#8e44ad",
                EL:  "#d35400",
                CL:  "#16a085",
                CO:  "#7f8c8d",
                ECO: "#a93226",
            };
            const color = colors[value] || "#1a202c";
            return `<span style="font-weight:700;color:${color};">${value}</span>`;
        }

        return def(value);
    },
};

// ── Legend builder (shared constant, defined once at module level) ────────────

function _mar_build_legend() {
    const LEGEND = [
        { code:"P",   label:"Present",          color:"#1a6b1a" },
        { code:"A",   label:"Absent",           color:"#c0392b" },
        { code:"HD",  label:"Half Day",         color:"#e67e22" },
        { code:"T",   label:"On Tour",          color:"#2c3e50" },
        { code:"H",   label:"Holiday",          color:"#27ae60" },
        { code:"WO",  label:"Weekly Off",       color:"#2980b9" },
        { code:"LWP", label:"Leave Without Pay",color:"#8e44ad" },
        { code:"EL",  label:"Earned Leave",     color:"#d35400" },
        { code:"CL",  label:"Casual Leave",     color:"#16a085" },
        { code:"CO",  label:"Comp Off",         color:"#7f8c8d" },
        { code:"ECO", label:"Earned Comp Off",  color:"#a93226" },
    ];
    const items = LEGEND.map(({ code, label, color }) =>
        `<span style="display:inline-flex;align-items:center;gap:4px;
                      margin-right:12px;margin-bottom:2px;white-space:nowrap;">
            <span style="font-weight:700;font-size:12px;color:${color};">${code}</span>
            <span style="font-size:12px;color:#444;">– ${label}</span>
        </span>`
    ).join("");
    return `
        <div id="mar-legend-bar" style="
            display:flex;flex-wrap:wrap;align-items:center;
            padding:7px 12px;margin:0 0 8px 0;
            background:#f4f5f6;border:1px solid #d1d8dd;
            border-radius:6px;font-family:inherit;">
            <span style="font-weight:600;font-size:12px;color:#6c7680;
                         margin-right:12px;white-space:nowrap;">Legend :</span>
            ${items}
        </div>`;
}