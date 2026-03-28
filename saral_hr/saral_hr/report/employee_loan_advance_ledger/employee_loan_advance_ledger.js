frappe.query_reports["Employee Loan Advance Ledger"] = {

    // ----------------------------------------------------------------
    //  Filters
    // ----------------------------------------------------------------
    filters: [
        {
            fieldname: "employee",
            label: __("Employee"),
            fieldtype: "Link",
            options: "Employee",
            default: frappe.defaults.get_default("employee") || "",
            get_query: function() {
                const company = frappe.query_report.get_filter_value("company");

                // Get all employees who have at least one submitted loan
                // Then filter by company if selected
                // We use a direct SQL-style frappe query via filters on Employee
                // scoped to those present in Employee Loan Advance
                return {
                    query: "saral_hr.saral_hr.report.employee_loan_advance_ledger.employee_loan_advance_ledger.get_employees_with_loans",
                    filters: {
                        company: company || ""
                    }
                };
            },
        },
        {
            fieldname: "type",
            label: __("Loan Type"),
            fieldtype: "Select",
            options: "\nLoan-I\nLoan-II\nAdvance",
        },
        {
            fieldname: "status",
            label: __("Status"),
            fieldtype: "Select",
            options: "\nActive\nCompleted",
        },
        {
            fieldname: "view",
            label: __("View"),
            fieldtype: "Select",
            options: "Summary\nDetail",
            default: "Summary",
            reqd: 1,
        },
    ],

    // ----------------------------------------------------------------
    //  On Load
    // ----------------------------------------------------------------
    onload(report) {
        report.page.add_inner_button(__("🔍 Show Detail"), function () {
            frappe.query_report.set_filter_value("view", "Detail");
            frappe.query_report.refresh();
        });

        report.page.add_inner_button(__("📋 Show Summary"), function () {
            frappe.query_report.set_filter_value("view", "Summary");
            frappe.query_report.refresh();
        });
    },

    // ----------------------------------------------------------------
    //  Formatter
    // ----------------------------------------------------------------
    formatter(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        if (!data) return value;

        const numeric_fields = ["amount", "total_paid", "outstanding", "scheduled_amt", "actual_amt", "running_bal"];
        if (data.is_group_row && numeric_fields.includes(column.fieldname)) {
            return "";
        }

        const currency_fields = ["amount", "total_paid", "outstanding", "scheduled_amt", "actual_amt", "running_bal"];
        if (currency_fields.includes(column.fieldname) && value !== "" && value !== undefined) {
            const num = parseFloat((data[column.fieldname] || 0));
            const formatted = "₹ " + num.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

            if (column.fieldname === "outstanding" && num > 0) {
                return `<span style="color:red; font-weight:600">${formatted}</span>`;
            }
            if (column.fieldname === "running_bal" && num === 0) {
                return `<span style="color:green; font-weight:600">${formatted}</span>`;
            }
            if (data.loan_id === "TOTAL") {
                return `<strong>${formatted}</strong>`;
            }
            return formatted;
        }

        if (data.loan_id === "TOTAL") {
            return `<strong style="font-size:13px">${value}</strong>`;
        }

        if (data.is_group_row) {
            return `<strong style="color:#1a73e8">${value}</strong>`;
        }

        if (column.fieldname === "status") {
            const colors = { "Active": "orange", "Completed": "green", "Deducted": "green", "Deferred": "#1a73e8", "Pending": "grey" };
            const icons  = { "Active": "🔄", "Completed": "✅", "Deducted": "✅", "Deferred": "↪", "Pending": "⏳" };
            const color  = colors[data.status] || "black";
            const icon   = icons[data.status]  || "";
            return `<span style="color:${color}; font-weight:600">${icon} ${data.status || ""}</span>`;
        }

        if (column.fieldname === "deferred_to" && data.deferred_to) {
            return `<span style="color:#1a73e8">→ ${data.deferred_to}</span>`;
        }

        return value;
    },

    get_datatable_options(options) {
        return Object.assign(options, {
            events: {
                onCheckRow(data) {
                    if (!data) return;
                    const current_view = frappe.query_report.get_filter_value("view");
                    if (current_view !== "Summary") return;
                    const employee_cell = data.find(cell => cell && cell.column && cell.column.fieldname === "employee");
                    if (employee_cell && employee_cell.content) {
                        frappe.query_report.set_filter_value("employee", employee_cell.content);
                    }
                    frappe.query_report.set_filter_value("view", "Detail");
                    frappe.query_report.refresh();
                }
            }
        });
    },
};