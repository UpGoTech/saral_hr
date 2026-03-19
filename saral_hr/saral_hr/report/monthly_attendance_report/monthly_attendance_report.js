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
    },

    formatter(value, row, column, data, default_formatter) {
        if (!data) return default_formatter(value, row, column, data);

        const fn  = column.fieldname;
        const def = v => default_formatter(v, row, column, data);

        // Colour-code day cells — only statuses that exist in your doctype
        if (fn && fn.startsWith("day_")) {
            if (!value || value === "-") {
                return '<span style="color:#ccc;">-</span>';
            }
            const colors = {
                P:   "#1a6b1a",   // Present       – dark green
                A:   "#c0392b",   // Absent        – red
                HD:  "#e67e22",   // Half Day      – orange
                T:   "#2c3e50",   // On Tour       – dark slate
                H:   "#27ae60",   // Holiday       – green
                WO:  "#2980b9",   // Weekly Off    – blue
                LWP: "#8e44ad",   // LWP           – purple
                EL:  "#d35400",   // Earned Leave  – burnt orange
                CL:  "#16a085",   // Casual Leave  – teal
                CO:  "#7f8c8d",   // Comp Off      – grey
                ECO: "#c0392b",   // Earned Comp Off – dark red
            };
            const color = colors[value] || "#1a202c";
            return `<span style="font-weight:700;color:${color};">${value}</span>`;
        }

        return def(value);
    },
};