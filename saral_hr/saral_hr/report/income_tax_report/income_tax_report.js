frappe.query_reports["Income Tax Report"] = {
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
            options: ["","January","February","March","April","May","June",
                      "July","August","September","October","November","December"],
        },
        
        {
            fieldname: "employee",
            label: __("Employee"),
            fieldtype: "MultiSelectList",
            get_data: txt => frappe.db.get_link_options("Employee", txt),
        },
    ],

    onload(report) {
        report.page.set_primary_action(__("Print"), function () {
            const f = report.get_values();

            if (!f.year || !f.month || !f.company?.length) {
                frappe.msgprint({
                    title: __("Missing Filters"),
                    message: __("Please select Company, Year and Month."),
                    indicator: "orange",
                });
                return;
            }

            frappe.dom.freeze(__("Generating PDF..."));

            frappe.call({
                method: "saral_hr.saral_hr.report.income_tax_report.income_tax_report.print_report",
                args: {
                    filters: JSON.stringify(f),
                },
                callback(r) {
                    frappe.dom.unfreeze();
                    if (r.message) {
                        const a = Object.assign(document.createElement("a"), {
                            href: frappe.urllib.get_full_url(r.message),
                            target: "_blank",
                        });
                        document.body.appendChild(a);
                        a.click();
                        document.body.removeChild(a);
                    }
                },
                error() {
                    frappe.dom.unfreeze();
                    frappe.msgprint(__("Failed to generate PDF"));
                }
            });
        }, "printer");
    },

    formatter(value, row, column, data, default_formatter) {
        if (!data) return default_formatter(value, row, column, data);
        const def = v => default_formatter(v, row, column, data);
        return data.bold ? `<strong>${def(value)}</strong>` : def(value);
    }
};