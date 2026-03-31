frappe.query_reports["Loan Register"] = {
    filters: [
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Company",
            on_change: function() {
                frappe.query_report.set_filter_value("employee", "");
                frappe.query_report.refresh();
            }
        },
        {
            fieldname: "employee",
            label: __("Employee"),
            fieldtype: "Link",
            options: "Employee",
            get_query: function () {
                const company = frappe.query_report.get_filter_value("company");
                return {
                    query: "saral_hr.saral_hr.report.loan_register.loan_register.get_employees_with_loans",
                    filters: {
                        company: company || ""
                    }
                };
            },
        },
        {
            fieldname: "year",
            label: __("Year"),
            fieldtype: "Select",
            options: (function () {
                let years = [""];
                let current = new Date().getFullYear();
                for (let y = current + 1; y >= current - 5; y--) years.push(String(y));
                return years.join("\n");
            })(),
            // no default — empty on load
        },
        {
            fieldname: "month",
            label: __("Month"),
            fieldtype: "Select",
            options: [
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

        if (!f.year || !f.month || !f.company) {
            frappe.msgprint({
                title:     __("Missing Filters"),
                message:   __("Please select Year, Month and Company before printing."),
                indicator: "orange",
            });
            return;
        }

        frappe.dom.freeze(__("Generating PDF…"));

        frappe.call({
            method: "saral_hr.saral_hr.report.loan_register.loan_register.print_report",
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

    formatter(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (!data) return value;

        const money_cols = ["total_loan", "recovered_this_month", "loan_balance"];

        if (data.employee === "TOTAL") {
            if (money_cols.includes(column.fieldname)) {
                const num = parseFloat(data[column.fieldname] || 0);
                const fmt = "₹\u00A0" + num.toLocaleString("en-IN", {
                    minimumFractionDigits: 2, maximumFractionDigits: 2
                });
                if (column.fieldname === "loan_balance" && num > 0)
                    return `<strong style="color:#C62828;">${fmt}</strong>`;
                return `<strong>${fmt}</strong>`;
            }
            if (column.fieldname === "employee")
                return `<strong style="font-size:13px;">TOTAL</strong>`;
            return `<strong>${value}</strong>`;
        }

        if (money_cols.includes(column.fieldname)) {
            const num = parseFloat(data[column.fieldname] ?? "");
            if (isNaN(num)) return value;
            const fmt = "₹\u00A0" + num.toLocaleString("en-IN", {
                minimumFractionDigits: 2, maximumFractionDigits: 2
            });
            if (column.fieldname === "loan_balance" && num > 0)
                return `<span style="color:#C62828;font-weight:600;">${fmt}</span>`;
            if (column.fieldname === "loan_balance" && num === 0)
                return `<span style="color:#2E7D32;font-weight:500;">${fmt}</span>`;
            if (column.fieldname === "recovered_this_month" && num > 0)
                return `<span style="color:#1E40AF;font-weight:600;">${fmt}</span>`;
            return fmt;
        }

        return value;
    },
};