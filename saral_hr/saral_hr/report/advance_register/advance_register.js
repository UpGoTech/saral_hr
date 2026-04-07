// Copyright (c) 2026, sj and contributors
// For license information, please see license.txt

frappe.query_reports["Advance Register"] = {
    "filters": [
        {
            "fieldname": "company",
            "label": __("Company"),
            "fieldtype": "Link",
            "options": "Company",
            "reqd": 0,
            "on_change": function() {
                frappe.query_report.set_filter_value("employee", "");
                frappe.query_report.refresh();
            }
        },
        {
            "fieldname": "employee",
            "label": __("Employee"),
            "fieldtype": "Link",
            "options": "Employee",
            "get_query": function () {
                const company = frappe.query_report.get_filter_value("company");
                return {
                    query: "saral_hr.saral_hr.report.advance_register.advance_register.get_employees_with_advances",
                    filters: {
                        company: company || ""
                    }
                };
            }
        },
        {
            "fieldname": "year",
            "label": __("Year"),
            "fieldtype": "Select",
            "options": (function () {
                let years = [""];
                let current = new Date().getFullYear();
                for (let y = current + 1; y >= current - 2; y--) years.push(String(y));
                return years.join("\n");
            })(),
            // no default — empty on load
        },
        {
            "fieldname": "month",
            "label": __("Month"),
            "fieldtype": "Select",
            "options": [
                "", "January", "February", "March", "April",
                "May", "June", "July", "August",
                "September", "October", "November", "December"
            ].join("\n"),
            // no default — empty on load
        },
    ],
    onload(report) {
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
            method: "saral_hr.saral_hr.report.advance_register.advance_register.print_report",
            args: {
                filters: JSON.stringify({
                    year:     f.year     || "",
                    month:    f.month    || "",
                    company:  f.company  || "",
                    employee: f.employee || "",
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

    "formatter": function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (!data) return value;

        const money_cols = ["total_advance", "recovered_advance", "pending_advance"];

        if (money_cols.includes(column.fieldname)) {
            const num = parseFloat(data[column.fieldname] || 0);
            if (isNaN(num)) return value;
            const fmt = "₹ " + num.toLocaleString("en-IN", {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            });
            if (column.fieldname === "pending_advance" && num > 0)
                return `<span style="color:#C62828;font-weight:600;">${fmt}</span>`;
            if (column.fieldname === "pending_advance" && num === 0)
                return `<span style="color:#2E7D32;font-weight:500;">${fmt}</span>`;
            if (column.fieldname === "recovered_advance" && num > 0)
                return `<span style="color:#1E40AF;font-weight:600;">${fmt}</span>`;
            return fmt;
        }

        return value;
    }
};