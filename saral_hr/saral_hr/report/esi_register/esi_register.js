frappe.query_reports["ESI Register"] = {
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
                "July", "August", "September", "October", "November", "December"
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
                method: "saral_hr.saral_hr.report.esi_register.esi_register.print_report",
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
                    frappe.msgprint({ title: __("Error"), message: __("Failed to generate PDF."), indicator: "red" });
                },
            });
        }, "printer");
    },

    formatter(value, row, column, data, default_formatter) {
        if (!data) return default_formatter(value, row, column, data);
        const fn   = column.fieldname;
        const def  = v => default_formatter(v, row, column, data);
        const bold = v => `<strong>${def(v)}</strong>`;

        if (data.bold) {
            // Suppress identity/days cols on total row; show all numeric totals including total_esi
            const skip = ["esic_number", "days_paid"];
            if (skip.includes(fn)) return "";
            return bold(value);
        }
        return def(value);
    },
};