frappe.query_reports["Employee Salary History"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			reqd: 1,
			on_change() {
				frappe.query_report.set_filter_value("employee", "");
			},
		},
		{
			fieldname: "employee",
			label: __("Employee"),
			fieldtype: "Link",
			options: "Company Link",
			reqd: 1,
			get_query() {
				const company = frappe.query_report.get_filter_value("company");
				if (!company) return { filters: { name: ["=", ""] } };
				return { filters: { company } };
			},
		},
		{
			fieldname: "show",
			label: __("Show"),
			fieldtype: "Select",
			options: "Full\nSelect Period",
			default: "Full",
			reqd: 1,
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			depends_on: "eval:doc.show=='Select Period'",
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			depends_on: "eval:doc.show=='Select Period'",
		},
	],

	onload(report) {
		report.page.add_inner_button(__("Download PDF"), () => {
			_export(report, "print_report", __("Generating PDF…"));
		});
		report.page.add_inner_button(__("Download Excel"), () => {
			_export(report, "excel_report", __("Generating Excel…"));
		});
	},

	after_datatable_render(datatable) {
		_paint_group_header(datatable);
	},

	formatter(value, row, column, data, default_formatter) {
		if (!data) return default_formatter(value, row, column, data);
		if (column.fieldtype === "Currency" && value !== null && value !== undefined && value !== "") {
			const shown = format_number(value, null, 2);
			const html = `<div style="text-align: right">₹ ${shown}</div>`;
			return data._is_total ? `<strong>${html}</strong>` : html;
		}
		const formatted = default_formatter(value, row, column, data);
		if (data._is_total) return `<strong>${formatted}</strong>`;
		if (column.fieldname === "month_year" && data.salary_slip) {
			const name = data.salary_slip;
			const label = frappe.utils.escape_html(value || "");
			return `<a href="/app/salary-slip/${encodeURIComponent(name)}" data-doctype="Salary Slip" data-name="${frappe.utils.escape_html(name)}">${label}</a>`;
		}
		if (column.fieldname === "paid_days" && value !== null && value !== undefined && value !== "") {
			const n = flt(value);
			const shown = Math.abs(n - Math.round(n)) < 1e-9 ? String(Math.round(n)) : String(flt(n, 1));
			const html = `<div style="text-align: right">${shown}</div>`;
			return data._is_total ? `<strong>${html}</strong>` : html;
		}
		return formatted;
	},
};

function _paint_group_header(datatable) {
	const header = datatable.wrapper && datatable.wrapper.querySelector(".dt-header > div");
	if (!header) return;
	const previous = header.querySelector(".esh-group-row");
	if (previous) previous.remove();

	const columns = datatable.datamanager.getColumns();
	const cells = header.querySelectorAll(".dt-cell--header");
	const groups = [];
	columns.forEach((col, i) => {
		const name = col.esh_group || "";
		const width = (cells[i] && cells[i].offsetWidth) || parseInt(col.width, 10) || 100;
		const prev = groups[groups.length - 1];
		if (prev && prev.name === name) {
			prev.width += width;
		} else {
			groups.push({ name, width });
		}
	});

	const row = document.createElement("div");
	row.className = "dt-row esh-group-row";
	columns.forEach((col, i) => {
		const tone = _group_tone(col.esh_group);
		if (tone && cells[i]) cells[i].classList.add("esh-sub", tone);
	});
	groups.forEach((group) => {
		const cell = document.createElement("div");
		const tone = _group_tone(group.name);
		cell.className = "dt-cell dt-cell--header esh-group-cell" + (tone ? " " + tone : "");
		cell.style.width = group.width + "px";
		cell.style.flex = "0 0 " + group.width + "px";
		cell.innerHTML =
			'<div class="dt-cell__content">' + frappe.utils.escape_html(group.name || "") + "</div>";
		row.appendChild(cell);
	});
	header.insertBefore(row, header.firstChild);
	_ensure_group_header_styles();
}

function _group_tone(name) {
	if (name === "Actual Earning") return "esh-actual";
	if (name === "Calculated Earning") return "esh-calc";
	if (name === "Additional Salary") return "esh-add-earn";
	if (name === "Deduction") return "esh-ded";
	if (name === "Additional Deduction") return "esh-add-ded";
	if (name === "Months" || name === "Paid Days" || name === "Net Payable") return "esh-plain";
	return "";
}

function _ensure_group_header_styles() {
	const old = document.getElementById("esh-group-header-styles");
	if (old) old.remove();
	const style = document.createElement("style");
	style.id = "esh-group-header-styles";
	style.textContent = `
		.esh-group-row { border-bottom: 1px solid var(--border-color, #d1d8dd); }
		.esh-group-cell .dt-cell__content,
		.dt-cell--header.esh-sub .dt-cell__content {
			text-align: center;
			font-weight: 700;
			font-size: 12px;
			overflow-wrap: normal;
			word-break: normal;
		}
		.esh-plain { background: #f8fafc; }
		.esh-actual { background: #fff7ed; }
		.esh-calc { background: #f0fdf4; }
		.esh-add-earn { background: #eff6ff; }
		.esh-ded { background: #fef2f2; }
		.esh-add-ded { background: #faf5ff; }
		.dt-cell--header.esh-sub.esh-add-earn .dt-cell__content,
		.dt-cell--header.esh-sub.esh-add-ded .dt-cell__content {
			font-size: 10px;
			font-weight: 600;
			line-height: 1.15;
			white-space: normal !important;
		}
	`;
	document.head.appendChild(style);
}

function _export(report, method, freeze_msg) {
	const f = report.get_values();
	if (!f.company || !f.employee) {
		frappe.msgprint({
			title: __("Missing Filters"),
			message: __("Please select Company and Employee."),
			indicator: "orange",
		});
		return;
	}
	if (f.show === "Select Period" && (!f.from_date || !f.to_date)) {
		frappe.msgprint({
			title: __("Missing Filters"),
			message: __("Please select From Date and To Date."),
			indicator: "orange",
		});
		return;
	}
	frappe.dom.freeze(freeze_msg);
	frappe.call({
		method: `saral_hr.saral_hr.report.employee_salary_history.employee_salary_history.${method}`,
		args: { filters: f },
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
