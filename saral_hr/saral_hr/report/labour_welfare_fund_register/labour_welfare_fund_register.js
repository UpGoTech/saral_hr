frappe.query_reports["Labour Welfare Fund Register"] = {
    filters: [
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "MultiSelectList",
            reqd: 1,
            get_data: txt => frappe.db.get_link_options("Company", txt),
        },
        {
            fieldname: "year",
            label: __("Year"),
            fieldtype: "Select",
            reqd: 1,
            default: String(new Date().getFullYear()),
            options: saral_hr.period_picker.get_period_year_options(),
        },
        {
            fieldname: "month",
            label: __("Month"),
            fieldtype: "Select",
            reqd: 1,
            default: "",
            options: ["","January","February","March","April","May","June",
                      "July","August","September","October","November","December"],
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
                    message: __("Please select Company, Year and Month before printing."),
                    indicator: "orange",
                });
                return;
            }
            frappe.dom.freeze(__("Generating PDF…"));
            frappe.call({
                method: "saral_hr.saral_hr.report.labour_welfare_fund_register.labour_welfare_fund_register.print_report",
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
                        title: __("Error"),
                        message: __("Failed to generate PDF."),
                        indicator: "red",
                    });
                },
            });
        }, "printer");
    },

    formatter(value, row, column, data, default_formatter) {
        if (!data) return default_formatter(value, row, column, data);
        const def  = v => default_formatter(v, row, column, data);
        const bold = v => `<strong>${def(v)}</strong>`;
        return data.bold ? bold(value) : def(value);
    },
};