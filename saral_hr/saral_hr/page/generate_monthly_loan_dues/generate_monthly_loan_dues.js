frappe.pages["generate-monthly-loan-dues"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Generate Monthly Loan Dues"),
		single_column: true,
	});
	wrapper._gld_page = page;
};

frappe.pages["generate-monthly-loan-dues"].on_page_show = function (wrapper) {
	$("body").removeClass("full-width");
	const $nb = $("#navbar-breadcrumbs");
	if ($nb.length) {
		$nb.empty().append(
			`<li><a href="/app/saral-hr">${__("Saral HR")}</a></li>`,
			`<li><a href="/app/generate-monthly-loan-dues">${__("Generate Monthly Loan Dues")}</a></li>`
		);
	}
	document.title = __("Generate Monthly Loan Dues");
	if (wrapper._gld_page) {
		wrapper._gld_page.set_title(__("Generate Monthly Loan Dues"));
	}
	const $main = $(wrapper).find(".layout-main-section");
	$main.html(gld_shell_html());
	init_generate_loan_dues($main, wrapper._gld_page);
};

function gld_shell_html() {
	const years = [];
	const cy = new Date().getFullYear();
	// Cover historical payroll months (loans often start in prior FY).
	for (let y = cy - 3; y <= cy + 2; y++) years.push(String(y));
	const months = [
		"January","February","March","April","May","June",
		"July","August","September","October","November","December"
	];
	const now = new Date();
	return `
	<div class="gld-root" style="padding:8px 0 40px;">
		<div class="frappe-card" style="padding:14px 16px;margin-bottom:12px;">
			<div style="display:flex;flex-wrap:wrap;gap:12px;align-items:flex-end;">
				<div>
					<label class="control-label">${__("Company")}</label>
					<div class="gld-company"></div>
				</div>
				<div>
					<label class="control-label">${__("Month")}</label>
					<select class="form-control gld-month" style="width:140px;">
						${months.map((m,i)=>`<option value="${m}" ${i===now.getMonth()?"selected":""}>${m}</option>`).join("")}
					</select>
				</div>
				<div>
					<label class="control-label">${__("Year")}</label>
					<select class="form-control gld-year" style="width:100px;">
						${years.map(y=>`<option value="${y}" ${y===String(cy)?"selected":""}>${y}</option>`).join("")}
					</select>
				</div>
				<div>
					<label class="control-label">${__("Employee")}</label>
					<div class="gld-employee"></div>
				</div>
				<button class="btn btn-default btn-sm gld-load">${__("Load")}</button>
				<button class="btn btn-primary btn-sm gld-generate">${__("Generate")}</button>
				<button class="btn btn-success btn-sm gld-save">${__("Save")}</button>
				<button class="btn btn-default btn-sm gld-add">${__("Add Row")}</button>
			</div>
		</div>
		<div class="frappe-card gld-table-wrap" style="padding:12px;overflow:auto;">
			<div class="text-muted">${__("Select company and month, then Generate or Load.")}</div>
		</div>
	</div>`;
}

function init_generate_loan_dues($main, page) {
	const state = { rows: [], generating: false };

	const company = frappe.ui.form.make_control({
		parent: $main.find(".gld-company"),
		df: {
			fieldtype: "Link",
			options: "Company",
			fieldname: "company",
			placeholder: __("Company"),
			default: frappe.defaults.get_user_default("Company"),
		},
		render_input: true,
	});
	company.refresh();

	const employee = frappe.ui.form.make_control({
		parent: $main.find(".gld-employee"),
		df: {
			fieldtype: "Link",
			options: "Company Link",
			fieldname: "employee",
			placeholder: __("Optional"),
		},
		render_input: true,
	});
	employee.refresh();

	function filters() {
		return {
			company: company.get_value(),
			month: $main.find(".gld-month").val(),
			year: $main.find(".gld-year").val(),
			employee: employee.get_value() || "",
		};
	}

	function render() {
		const $wrap = $main.find(".gld-table-wrap");
		if (!state.rows.length) {
			$wrap.html(`<div class="text-muted">${__("No dues for this period.")}</div>`);
			return;
		}
		let html = `<table class="table table-bordered" style="margin:0;">
			<thead><tr>
				<th>${__("Employee")}</th>
				<th>${__("Name")}</th>
				<th>${__("Loan")}</th>
				<th style="text-align:right;">${__("Outstanding")}</th>
				<th style="text-align:right;">${__("Amount")}</th>
				<th>${__("Status")}</th>
				<th>${__("Salary Slip")}</th>
				<th>${__("Remarks")}</th>
			</tr></thead><tbody>`;
		state.rows.forEach((r, idx) => {
			const locked = !!r.salary_slip;
			html += `<tr data-idx="${idx}">
				<td>${frappe.utils.escape_html(r.employee || "")}</td>
				<td>${frappe.utils.escape_html(r.full_name || "")}</td>
				<td><a href="/app/employee-loan/${encodeURIComponent(r.loan)}">${frappe.utils.escape_html(r.loan || "")}</a></td>
				<td style="text-align:right;">${format_currency(r.outstanding_amount || 0)}</td>
				<td style="text-align:right;">
					<input type="number" step="0.01" class="form-control input-sm gld-amount"
						value="${flt(r.amount)}" ${locked ? "disabled" : ""} style="max-width:120px;margin-left:auto;" />
				</td>
				<td>${frappe.utils.escape_html(r.status || "")}</td>
				<td>${r.salary_slip ? `<a href="/app/salary-slip/${encodeURIComponent(r.salary_slip)}">${frappe.utils.escape_html(r.salary_slip)}</a>` : "—"}</td>
				<td><input type="text" class="form-control input-sm gld-remarks" value="${frappe.utils.escape_html(r.remarks || "")}" ${locked ? "disabled" : ""} /></td>
			</tr>`;
		});
		html += "</tbody></table>";
		$wrap.html(html);
	}

	function collect() {
		$main.find("tbody tr").each(function () {
			const idx = cint($(this).attr("data-idx"));
			if (state.rows[idx]) {
				state.rows[idx].amount = flt($(this).find(".gld-amount").val());
				state.rows[idx].remarks = $(this).find(".gld-remarks").val();
			}
		});
		return state.rows;
	}

	function load_dues() {
		const f = filters();
		if (!f.company) return frappe.msgprint(__("Select Company"));
		frappe.call({
			method: "saral_hr.saral_hr.page.generate_monthly_loan_dues.generate_monthly_loan_dues.get_dues",
			args: f,
			freeze: true,
			callback(r) {
				state.rows = r.message || [];
				render();
			},
		});
	}

	// Replacing HTML on each show leaves delegated handlers on $main stacked —
	// a second Generate click fired in parallel and raced past the exists check.
	$main.off(".gld");

	$main.on("click.gld", ".gld-load", () => load_dues());

	$main.on("click.gld", ".gld-generate", () => {
		const f = filters();
		if (!f.company) return frappe.msgprint(__("Select Company"));
		if (state.generating) return;
		state.generating = true;
		frappe.call({
			method: "saral_hr.saral_hr.page.generate_monthly_loan_dues.generate_monthly_loan_dues.generate_dues",
			args: f,
			freeze: true,
			freeze_message: __("Generating…"),
			callback(r) {
				state.generating = false;
				frappe.show_alert({
					message: __("Created {0}, skipped {1}", [r.message.created, r.message.skipped]),
					indicator: "green",
				});
				load_dues();
			},
			error() {
				state.generating = false;
			},
		});
	});

	$main.on("click.gld", ".gld-save", () => {
		const rows = collect();
		frappe.call({
			method: "saral_hr.saral_hr.page.generate_monthly_loan_dues.generate_monthly_loan_dues.save_dues",
			args: { rows },
			freeze: true,
			callback(r) {
				frappe.show_alert({
					message: __("Saved {0} row(s)", [r.message.updated]),
					indicator: "green",
				});
				load_dues();
			},
		});
	});

	$main.on("click.gld", ".gld-add", () => {
		const f = filters();
		if (!f.company) return frappe.msgprint(__("Select Company"));
		const d = new frappe.ui.Dialog({
			title: __("Add Loan Due"),
			fields: [
				{ fieldname: "loan", fieldtype: "Link", options: "Employee Loan", label: __("Loan"), reqd: 1,
					get_query: () => ({ filters: { docstatus: 1, status: "Active", company: f.company } }) },
				{ fieldname: "amount", fieldtype: "Currency", label: __("Amount"), reqd: 1 },
				{ fieldname: "remarks", fieldtype: "Small Text", label: __("Remarks") },
			],
			primary_action_label: __("Add"),
			primary_action(values) {
				const month = `${f.month} ${f.year}`;
				frappe.call({
					method: "saral_hr.saral_hr.page.generate_monthly_loan_dues.generate_monthly_loan_dues.save_dues",
					args: {
						rows: [{
							loan: values.loan,
							month,
							year: cint(f.year),
							amount: values.amount,
							remarks: values.remarks || "",
						}],
					},
					freeze: true,
					callback() {
						d.hide();
						load_dues();
					},
				});
			},
		});
		d.show();
	});
}
