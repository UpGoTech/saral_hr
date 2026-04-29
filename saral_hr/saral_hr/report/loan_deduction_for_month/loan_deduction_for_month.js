frappe.query_reports["Loan Deduction For Month"] = {

    onload(report) {
        const co = frappe.defaults.get_user_default("Company")
            || frappe.defaults.get_global_default("Company");
        if (co) {
            setTimeout(() => {
                report.set_filter_value("company", co);
                const now = new Date();
                const months = ["January", "February", "March", "April", "May", "June",
                    "July", "August", "September", "October", "November", "December"];
                report.set_filter_value("month", months[now.getMonth()]);
                report.set_filter_value("year", String(now.getFullYear()));
                setTimeout(() => report.refresh(), 300);
            }, 150);
        }
    },

    filters: [
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Company",
            on_change() {
                frappe.query_report.set_filter_value("employee", "");
                frappe.query_report.refresh();
            }
        },
        {
            fieldname: "employee",
            label: __("Employee"),
            fieldtype: "Link",
            options: "Employee",
            get_query() {
                const company = frappe.query_report.get_filter_value("company");
                return {
                    query: "saral_hr.saral_hr.report.loan_register.loan_register.get_employees_with_loans",
                    filters: { company: company || "" }
                };
            }
        },
        {
            fieldname: "loan_type",
            label: __("Type"),
            fieldtype: "Select",
            options: "\nLoan\nAdvance"
        },
        {
            fieldname: "month",
            label: __("Month"),
            fieldtype: "Select",
            options: "\nJanuary\nFebruary\nMarch\nApril\nMay\nJune\nJuly\nAugust\nSeptember\nOctober\nNovember\nDecember"
        },
        {
            fieldname: "year",
            label: __("Year"),
            fieldtype: "Select",
            options: "2023\n2024\n2025\n2026\n2027\n2028",
            default: String(new Date().getFullYear())
        }
    ],

    formatter(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (!data) return value;

        if (["total_amount", "emi_amount"].includes(column.fieldname)) {
            const n = parseFloat(data[column.fieldname] || 0);
            return "₹ " + n.toLocaleString("en-IN", {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            });
        }

        if (column.fieldname === "type") {
            const map = {
                "Loan":    { color: "#1E3A8A", bg: "#DBEAFE", dot: "#3B82F6" },
                "Advance": { color: "#065F46", bg: "#D1FAE5", dot: "#10B981" }
            };
            const c = map[data.type] || { color: "#374151", bg: "#F3F4F6", dot: "#9CA3AF" };
            return `<span style="display:inline-flex;align-items:center;gap:5px;
                        color:${c.color};background:${c.bg};
                        padding:3px 10px;border-radius:20px;
                        font-size:11px;font-weight:600;">
                        <span style="width:6px;height:6px;border-radius:50%;
                            background:${c.dot};display:inline-block;"></span>
                        ${data.type}
                    </span>`;
        }

        if (column.fieldname === "status") {
            const map = {
                "Deducted": { color: "#065F46", bg: "#D1FAE5", dot: "#10B981" },
                "Pending":  { color: "#92400E", bg: "#FEF3C7", dot: "#F59E0B" },
                "Deferred": { color: "#1E3A8A", bg: "#DBEAFE", dot: "#3B82F6" }
            };
            const c = map[data.status] || { color: "#374151", bg: "#F3F4F6", dot: "#9CA3AF" };
            return `<span style="display:inline-flex;align-items:center;gap:5px;
                        color:${c.color};background:${c.bg};
                        padding:3px 10px;border-radius:20px;
                        font-size:11px;font-weight:600;">
                        <span style="width:6px;height:6px;border-radius:50%;
                            background:${c.dot};display:inline-block;"></span>
                        ${data.status}
                    </span>`;
        }

        return value;
    }
};