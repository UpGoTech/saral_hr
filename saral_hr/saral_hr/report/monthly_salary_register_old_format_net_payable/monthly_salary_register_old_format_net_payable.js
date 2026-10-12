frappe.query_reports["Monthly Salary Register Old Format Net Payable"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			reqd: 1,
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
			options: [
				"",
				"January",
				"February",
				"March",
				"April",
				"May",
				"June",
				"July",
				"August",
				"September",
				"October",
				"November",
				"December",
			],
		},
		{
			fieldname: "population",
			label: __("Population"),
			fieldtype: "Select",
			reqd: 1,
			default: "All",
			options: ["All", "Staff", "Worker", "Consultant"].join("\n"),
		},
		{
			fieldname: "format",
			label: __("Format"),
			fieldtype: "Select",
			reqd: 1,
			default: "Full",
			options: ["Full", "Compressed"].join("\n"),
		},
	],

	onload(report) {
		report.page.add_inner_button(__("Download PDF"), () => {
			_export(report, "print_report", __("Generating PDF…"));
		});
		report.page.add_inner_button(__("Download Excel"), () => {
			_export(report, "excel_report", __("Generating Excel…"));
		});
		_ensure_header_wrap_styles();
	},

	formatter(value, row, column, data, default_formatter) {
		if (!data) return default_formatter(value, row, column, data);
		const def = (v) => default_formatter(v, row, column, data);
		const fn = column.fieldname;

		if (data._is_total) {
			const skip = [
				"bank_name",
				"ifsc",
				"bank_account",
				"total_month_day",
				"total_paid_days",
				"sr_no",
			];
			if (skip.includes(fn)) {
				return "";
			}
			return `<strong>${def(value)}</strong>`;
		}

		if (fn === "total_paid_days" && value !== null && value !== undefined && value !== "") {
			const n = flt(value);
			return Math.abs(n - Math.round(n)) < 1e-9 ? String(Math.round(n)) : String(flt(n, 1));
		}

		return def(value);
	},

	after_datatable_render(datatable) {
		_pin_total_row_on_sort(datatable);
		_ensure_header_wrap_styles();
		_widen_serial_column(datatable);
	},
};

function _widen_serial_column(datatable) {
	const dm = datatable && datatable.datamanager;
	if (!dm) return;
	const idx = dm.getColumnIndexById("_rowIndex");
	if (idx < 0) return;
	const col = dm.getColumn(idx);
	col.width = 46;
	datatable.columnmanager.setColumnWidth(idx, 46);
	datatable.columnmanager.setColumnHeaderWidth(idx);
}

function _ensure_header_wrap_styles() {
	const id = "saral-msr-header-wrap";
	let style = document.getElementById(id);
	if (!style) {
		style = document.createElement("style");
		style.id = id;
		document.head.appendChild(style);
	}
	// One-sided horizontal padding — breathing room without overflowing the page.
	style.textContent = `
		.report-wrapper .dt-row-header {
			height: auto !important;
		}
		.report-wrapper .dt-cell--header {
			height: 60px !important;
		}
		.report-wrapper .dt-cell--header .dt-cell__content {
			white-space: normal !important;
			overflow: visible !important;
			text-overflow: clip !important;
			height: 100% !important;
			min-height: 56px !important;
			line-height: 1.3 !important;
			padding: 8px 4px 8px 8px !important;
			display: flex !important;
			flex-direction: column !important;
			justify-content: center !important;
			align-items: center !important;
			text-align: center !important;
			box-sizing: border-box !important;
		}
		.report-wrapper .dt-cell:not(.dt-cell--header) .dt-cell__content {
			padding: 6px 2px 6px 8px !important;
		}
		.report-wrapper .dt-cell__content--col-0,
		.report-wrapper .dt-cell__content--header-0 {
			padding-left: 10px !important;
			padding-right: 2px !important;
			text-align: center !important;
			justify-content: center !important;
		}
		.report-wrapper .dt-scrollable .dt-row:hover .dt-cell {
			background-color: var(--subtle-fg, #edf2f7) !important;
		}
		.report-wrapper .dt-scrollable .dt-row:hover .dt-cell__content {
			background-color: transparent !important;
		}
	`;
}

function _pin_total_row_on_sort(datatable) {
	const dm = datatable && datatable.datamanager;
	if (!dm || dm.__saral_total_sort_patched) return;
	dm.__saral_total_sort_patched = true;
	const orig = dm._sortRows.bind(dm);
	dm._sortRows = function (colIndex, sortOrder) {
		orig(colIndex, sortOrder);
		const name_col = this.getColumnIndexById("employee_name");
		if (name_col < 0) return;
		const totals = [];
		const rest = [];
		for (const idx of this.rowViewOrder) {
			const cell = this.getCell(name_col, idx);
			if (cell && cell.content === "Total") {
				totals.push(idx);
			} else {
				rest.push(idx);
			}
		}
		this.rowViewOrder = rest.concat(totals);
	};
}

function _export(report, method, freeze_msg) {
	const f = report.get_values();
	if (!f.company || !f.year || !f.month) {
		frappe.msgprint({
			title: __("Missing Filters"),
			message: __("Please select Company, Year and Month."),
			indicator: "orange",
		});
		return;
	}
	frappe.dom.freeze(freeze_msg);
	frappe.call({
		method: `saral_hr.saral_hr.report.monthly_salary_register_old_format_net_payable.monthly_salary_register_old_format_net_payable.${method}`,
		args: { filters: JSON.stringify(f) },
		callback(r) {
			frappe.dom.unfreeze();
			if (r.message) {
				const a = Object.assign(document.createElement("a"), {
					href: frappe.urllib.get_full_url(r.message),
					target: "_blank",
					rel: "noopener noreferrer",
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
				message: __("Export failed."),
				indicator: "red",
			});
		},
	});
}
