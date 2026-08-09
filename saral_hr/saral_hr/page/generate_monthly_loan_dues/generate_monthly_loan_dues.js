frappe.pages["generate-monthly-loan-dues"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Generate Monthly Loan Dues"),
		single_column: true,
	});
	wrapper._gld_page = page;
};

frappe.pages["generate-monthly-loan-dues"].on_page_show = function (wrapper) {
	// Keep standard Desk chrome (workspace sidebar) — do not go full-bleed
	$("body").removeClass("full-width");
	gld_set_breadcrumbs();
	if (wrapper._gld_page) {
		wrapper._gld_page.set_title(__("Generate Monthly Loan Dues"));
	}
	inject_gld_styles();
	const $main = $(wrapper).find(".layout-main-section");
	$main.html(gld_shell_html());
	init_generate_loan_dues($main, wrapper._gld_page);
};

function gld_set_breadcrumbs() {
	const $nb = $("#navbar-breadcrumbs");
	if (!$nb.length) return;
	$nb.empty().append(
		`<li><a href="/app/saral-hr">${__("Saral HR")}</a></li>`,
		`<li><a href="/app/generate-monthly-loan-dues">${__("Generate Monthly Loan Dues")}</a></li>`
	);
	document.title = __("Generate Monthly Loan Dues");
}

function inject_gld_styles() {
	$("#gld-styles, #gld-styles-v1, #gld-styles-v2").remove();
	const s = document.createElement("style");
	s.id = "gld-styles-v2";
	s.innerHTML = `
		.gld-root { padding: 8px 0 40px; color: var(--text-color); max-width: 100%; }
		.gld-filter-card {
			background: var(--card-bg, var(--fg-color));
			border: 1px solid var(--border-color);
			border-radius: 8px;
			margin-bottom: 12px;
			padding: 14px 16px;
			max-width: 100%;
			overflow: visible;
			position: relative;
			z-index: 20;
		}
		.gld-filter-row {
			display: flex;
			flex-wrap: wrap;
			align-items: flex-end;
			gap: 12px 14px;
		}
		.gld-fg {
			display: flex;
			flex-direction: column;
			gap: 5px;
			min-width: 0;
		}
		.gld-fg-company { flex: 1 1 200px; min-width: 180px; max-width: 280px; }
		.gld-fg-employee { flex: 1 1 200px; min-width: 180px; max-width: 280px; }
		.gld-fg-period { flex: 0 0 130px; width: 130px; }
		.gld-fg-action { flex: 0 0 auto; }
		.gld-fg-label {
			font-size: 11px; font-weight: 700; color: var(--text-muted);
			text-transform: uppercase; letter-spacing: .04em; margin: 0; line-height: 1.2;
			min-height: 14px;
		}
		.gld-link-wrap .frappe-control,
		.gld-link-wrap .form-group { margin-bottom: 0 !important; }
		.gld-link-wrap .control-label,
		.gld-link-wrap .help-box,
		.gld-link-wrap .clearfix {
			display: none !important; height: 0 !important; margin: 0 !important; padding: 0 !important;
		}
		.gld-link-wrap .control-input-wrapper,
		.gld-link-wrap .awesomplete,
		.gld-link-wrap .awesomplete > input { width: 100% !important; }
		.gld-link-wrap .awesomplete { position: relative; z-index: 30; }
		.gld-link-wrap .awesomplete > ul {
			z-index: 40 !important;
			max-height: 240px;
			overflow-y: auto;
		}
		.gld-link-wrap input.input-with-feedback,
		.gld-fg .form-control,
		.gld-fg select {
			height: 32px !important; min-height: 32px !important;
			font-size: 13px; border-radius: 6px; margin: 0; width: 100%;
		}
		.gld-btn {
			height: 32px; padding: 0 16px; border: none; border-radius: 6px;
			background: var(--primary); color: #fff; font-size: 13px; font-weight: 600; cursor: pointer;
			white-space: nowrap;
		}
		.gld-btn:hover { filter: brightness(.96); }
		.gld-btn:disabled { opacity: .45; cursor: not-allowed; filter: none; }
		.gld-btn-ghost {
			height: 32px; padding: 0 14px; border: 1px solid var(--border-color); border-radius: 6px;
			background: transparent; color: var(--text-color); font-size: 13px; font-weight: 600; cursor: pointer;
		}
		.gld-btn-ghost:hover { background: var(--subtle-fg, rgba(0,0,0,.03)); }
		.gld-btn-ghost:disabled { opacity: .45; cursor: not-allowed; }
		.gld-btn-success {
			height: 32px; padding: 0 14px; border: none; border-radius: 6px;
			background: var(--green-500, #2f9e44); color: #fff; font-size: 13px; font-weight: 600; cursor: pointer;
		}
		.gld-btn-success:disabled { opacity: .45; cursor: not-allowed; }
		.gld-banner {
			margin-top: 10px; font-size: 12px; color: var(--text-muted);
			min-height: 16px;
		}
		.gld-banner.locked { color: var(--orange-600, #e67700); font-weight: 600; }
		.gld-results-card {
			background: var(--card-bg, var(--fg-color));
			border: 1px solid var(--border-color);
			border-radius: 8px;
			margin-bottom: 12px;
			max-width: 100%;
			overflow: hidden;
			position: relative;
			z-index: 1;
		}
		.gld-table-wrap { overflow-x: auto; padding: 0; }
		.gld-table {
			width: 100%; border-collapse: collapse; margin: 0; font-size: 13px;
		}
		.gld-table th, .gld-table td {
			padding: 8px 10px; border-bottom: 1px solid var(--border-color);
			vertical-align: middle;
		}
		.gld-table th {
			font-size: 11px; text-transform: uppercase; letter-spacing: .03em;
			color: var(--text-muted); font-weight: 700; background: var(--subtle-fg, #f8f9fa);
			white-space: nowrap;
		}
		.gld-table tbody tr:hover td { background: var(--highlight-color, rgba(0,0,0,.02)); }
		.gld-table .form-control {
			height: 30px !important; min-height: 30px !important; font-size: 13px;
		}
		.gld-empty { padding: 40px 20px; text-align: center; color: var(--text-muted); font-size: 13px; }
		.gld-cards { display: none; padding: 10px 12px 12px; }
		.gld-card {
			border: 1px solid var(--border-color); border-radius: 8px; padding: 12px;
			margin-bottom: 10px; background: var(--card-bg, var(--fg-color));
		}
		.gld-card:last-child { margin-bottom: 0; }
		.gld-card-title { font-size: 13px; font-weight: 700; margin-bottom: 8px; }
		.gld-card-grid {
			display: grid; grid-template-columns: 1fr 1fr; gap: 8px 12px; font-size: 12px;
		}
		.gld-card-grid .k { color: var(--text-muted); font-weight: 600; text-transform: uppercase; font-size: 10px; }
		.gld-card-grid .v { font-weight: 600; margin-top: 2px; word-break: break-word; }
		.gld-card-full { grid-column: 1 / -1; }
		@media (max-width: 720px) {
			.gld-filter-row { flex-direction: column; align-items: stretch; }
			.gld-fg-company, .gld-fg-employee, .gld-fg-period, .gld-fg-action {
				flex: 1 1 auto; width: 100%; max-width: none;
			}
			.gld-fg-action .gld-btn,
			.gld-fg-action .gld-btn-ghost,
			.gld-fg-action .gld-btn-success { width: 100%; }
			.gld-fg-action { display: grid; gap: 8px; }
		}
		@media (max-width: 900px) {
			.gld-table-wrap { display: none; }
			.gld-cards { display: block; }
		}
		@media (min-width: 901px) {
			.gld-table-wrap { display: block; }
			.gld-cards { display: none; }
		}
	`;
	document.head.appendChild(s);
}

function gld_shell_html() {
	const years = [];
	const cy = new Date().getFullYear();
	for (let y = cy - 3; y <= cy + 2; y++) years.push(String(y));
	const months = [
		"January","February","March","April","May","June",
		"July","August","September","October","November","December"
	];
	const now = new Date();
	return `
	<div class="gld-root">
		<div class="gld-filter-card">
			<div class="gld-filter-row">
				<div class="gld-fg gld-fg-company">
					<div class="gld-fg-label">${__("Company")}</div>
					<div class="gld-link-wrap"><div class="gld-company"></div></div>
				</div>
				<div class="gld-fg gld-fg-period">
					<div class="gld-fg-label">${__("Month")}</div>
					<select class="form-control gld-month">
						${months.map((m,i)=>`<option value="${m}" ${i===now.getMonth()?"selected":""}>${__(m)}</option>`).join("")}
					</select>
				</div>
				<div class="gld-fg gld-fg-period">
					<div class="gld-fg-label">${__("Year")}</div>
					<select class="form-control gld-year">
						${years.map(y=>`<option value="${y}" ${y===String(cy)?"selected":""}>${y}</option>`).join("")}
					</select>
				</div>
				<div class="gld-fg gld-fg-employee">
					<div class="gld-fg-label">${__("Employee")}</div>
					<div class="gld-link-wrap"><div class="gld-employee"></div></div>
				</div>
				<div class="gld-fg gld-fg-action">
					<div class="gld-fg-label">&nbsp;</div>
					<button type="button" class="gld-btn gld-open">${__("Load")}</button>
				</div>
				<div class="gld-fg gld-fg-action">
					<div class="gld-fg-label">&nbsp;</div>
					<button type="button" class="gld-btn-success gld-save">${__("Save")}</button>
				</div>
				<div class="gld-fg gld-fg-action">
					<div class="gld-fg-label">&nbsp;</div>
					<button type="button" class="gld-btn-ghost gld-add">${__("Add Row")}</button>
				</div>
			</div>
			<div class="gld-banner"></div>
		</div>
		<div class="gld-results-card">
			<div class="gld-table-wrap">
				<div class="gld-empty">${__("Select company and month, then Load.")}</div>
			</div>
			<div class="gld-cards"></div>
		</div>
	</div>`;
}

function gld_fmt_currency(v) {
	const n = flt(v);
	if (typeof format_currency === "function") {
		try { return format_currency(n); } catch (e) { /* fall through */ }
	}
	return frappe.format(n, { fieldtype: "Currency" });
}

function init_generate_loan_dues($main) {
	const state = { rows: [], loading: false, period_locked: false };

	const company = frappe.ui.form.make_control({
		parent: $main.find(".gld-company"),
		df: {
			fieldtype: "Link",
			options: "Company",
			fieldname: "company",
			label: __("Company"),
			placeholder: __("Company"),
			only_select: 1,
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
			label: __("Employee"),
			placeholder: __("Optional"),
			only_select: 1,
		},
		render_input: true,
	});
	employee.refresh();

	// Link control ships its own label — hide so field-group labels stay aligned
	$main.find(".gld-company .control-label, .gld-company .help-box, .gld-employee .control-label, .gld-employee .help-box").hide();

	function filters() {
		return {
			company: company.get_value(),
			month: $main.find(".gld-month").val(),
			year: $main.find(".gld-year").val(),
			employee: employee.get_value() || "",
		};
	}

	function set_actions_enabled() {
		const locked = !!state.period_locked;
		$main.find(".gld-save, .gld-add").prop("disabled", locked);
	}

	function set_banner(msg, locked) {
		const $b = $main.find(".gld-banner");
		$b.text(msg || "").toggleClass("locked", !!locked);
	}

	function amount_input(r, idx, locked) {
		return `<input type="number" step="0.01" class="form-control input-sm gld-amount"
			data-idx="${idx}" value="${flt(r.amount)}" ${locked ? "disabled" : ""} />`;
	}

	function remarks_input(r, idx, locked) {
		return `<input type="text" class="form-control input-sm gld-remarks"
			data-idx="${idx}" value="${frappe.utils.escape_html(r.remarks || "")}" ${locked ? "disabled" : ""} />`;
	}

	function render() {
		const $wrap = $main.find(".gld-table-wrap");
		const $cards = $main.find(".gld-cards");
		set_actions_enabled();
		if (!state.rows.length) {
			$wrap.html(`<div class="gld-empty">${__("No dues for this period.")}</div>`);
			$cards.empty();
			return;
		}
		const periodLocked = !!state.period_locked;
		let html = `<table class="gld-table">
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
		let cards = "";
		state.rows.forEach((r, idx) => {
			const locked = periodLocked || !!r.salary_slip || !!r.locked;
			const slip = r.salary_slip
				? `<a href="/app/salary-slip/${encodeURIComponent(r.salary_slip)}">${frappe.utils.escape_html(r.salary_slip)}</a>`
				: "—";
			const loan = `<a href="/app/employee-loan/${encodeURIComponent(r.loan)}">${frappe.utils.escape_html(r.loan || "")}</a>`;
			html += `<tr data-idx="${idx}">
				<td>${frappe.utils.escape_html(r.employee || "")}</td>
				<td>${frappe.utils.escape_html(r.full_name || "")}</td>
				<td>${loan}</td>
				<td style="text-align:right;">${gld_fmt_currency(r.outstanding_amount || 0)}</td>
				<td style="text-align:right;max-width:130px;">${amount_input(r, idx, locked)}</td>
				<td>${frappe.utils.escape_html(r.status || "")}</td>
				<td>${slip}</td>
				<td>${remarks_input(r, idx, locked)}</td>
			</tr>`;
			cards += `<div class="gld-card" data-idx="${idx}">
				<div class="gld-card-title">${frappe.utils.escape_html(r.full_name || r.employee || "")} · ${loan}</div>
				<div class="gld-card-grid">
					<div><div class="k">${__("Outstanding")}</div><div class="v">${gld_fmt_currency(r.outstanding_amount || 0)}</div></div>
					<div><div class="k">${__("Status")}</div><div class="v">${frappe.utils.escape_html(r.status || "")}</div></div>
					<div class="gld-card-full"><div class="k">${__("Amount")}</div><div class="v">${amount_input(r, idx, locked)}</div></div>
					<div class="gld-card-full"><div class="k">${__("Salary Slip")}</div><div class="v">${slip}</div></div>
					<div class="gld-card-full"><div class="k">${__("Remarks")}</div><div class="v">${remarks_input(r, idx, locked)}</div></div>
				</div>
			</div>`;
		});
		html += "</tbody></table>";
		$wrap.html(html);
		$cards.html(cards);
	}

	function collect() {
		$main.find(".gld-amount").each(function () {
			const idx = cint($(this).attr("data-idx"));
			if (state.rows[idx]) state.rows[idx].amount = flt($(this).val());
		});
		$main.find(".gld-remarks").each(function () {
			const idx = cint($(this).attr("data-idx"));
			if (state.rows[idx]) state.rows[idx].remarks = $(this).val();
		});
		return state.rows;
	}

	function open_period() {
		const f = filters();
		if (!f.company) return frappe.msgprint(__("Select Company"));
		if (state.loading) return;
		state.loading = true;
		frappe.call({
			method: "saral_hr.saral_hr.page.generate_monthly_loan_dues.generate_monthly_loan_dues.open_period",
			args: f,
			freeze: true,
			freeze_message: __("Loading…"),
			callback(r) {
				state.loading = false;
				const msg = r.message || {};
				state.rows = msg.rows || [];
				state.period_locked = !!msg.period_locked;
				if (state.period_locked) {
					set_banner(__("Period locked — submitted salary slips exist for this month. View only."), true);
				} else if (msg.created) {
					set_banner(__("Loaded existing dues and added {0} missing.", [msg.created]), false);
				} else {
					set_banner(__("Loaded existing dues for {0}.", [msg.month || ""]), false);
				}
				render();
			},
			error() {
				state.loading = false;
			},
		});
	}

	// Replacing HTML on each show leaves delegated handlers on $main stacked.
	$main.off(".gld");

	$main.on("click.gld", ".gld-open", () => open_period());

	$main.on("click.gld", ".gld-save", () => {
		if (state.period_locked) {
			return frappe.msgprint(__("This period is locked because salary slips already exist."));
		}
		const f = filters();
		const rows = collect();
		frappe.call({
			method: "saral_hr.saral_hr.page.generate_monthly_loan_dues.generate_monthly_loan_dues.save_dues",
			args: {
				rows,
				company: f.company,
				month: f.month,
				year: f.year,
			},
			freeze: true,
			callback(r) {
				frappe.show_alert({
					message: __("Saved {0} row(s)", [r.message.updated]),
					indicator: "green",
				});
				open_period();
			},
		});
	});

	$main.on("click.gld", ".gld-add", () => {
		if (state.period_locked) {
			return frappe.msgprint(__("This period is locked because salary slips already exist."));
		}
		const f = filters();
		if (!f.company) return frappe.msgprint(__("Select Company"));
		open_add_due_dialog(f, open_period);
	});
}

function open_add_due_dialog(f, on_done) {
	const loan_map = {};
	let selected_loan = null;

	const d = new frappe.ui.Dialog({
		title: __("Add Loan Due"),
		size: "large",
		fields: [
			{
				fieldname: "employee",
				fieldtype: "Link",
				options: "Company Link",
				label: __("Employee"),
				default: f.employee || "",
				get_query: () => ({ filters: { company: f.company } }),
				description: __("Optional — narrow the loan list"),
				onchange() {
					selected_loan = null;
					load_loans();
				},
			},
			{
				fieldname: "loan_list",
				fieldtype: "HTML",
				label: __("Loans"),
			},
			{
				fieldname: "loan",
				fieldtype: "Data",
				hidden: 1,
				reqd: 1,
			},
			{
				fieldname: "loan_info",
				fieldtype: "HTML",
			},
			{
				fieldname: "amount",
				fieldtype: "Currency",
				label: __("Due Amount"),
				reqd: 1,
			},
			{
				fieldname: "remarks",
				fieldtype: "Small Text",
				label: __("Remarks"),
			},
		],
		primary_action_label: __("Add"),
		primary_action(values) {
			const loan_name = selected_loan || values.loan;
			if (!loan_name) {
				frappe.msgprint(__("Select a loan from the list"));
				return;
			}
			const month = `${f.month} ${f.year}`;
			frappe.call({
				method: "saral_hr.saral_hr.page.generate_monthly_loan_dues.generate_monthly_loan_dues.save_dues",
				args: {
					rows: [{
						loan: loan_name,
						month,
						year: cint(f.year),
						amount: values.amount,
						remarks: values.remarks || "",
					}],
					company: f.company,
					month: f.month,
					year: f.year,
				},
				freeze: true,
				callback() {
					d.hide();
					on_done();
				},
			});
		},
	});

	function render_loan_info(loan) {
		const $wrap = d.fields_dict.loan_info.$wrapper;
		if (!loan) {
			$wrap.html("");
			return;
		}
		$wrap.html(`
			<div style="border:1px solid var(--border-color);border-radius:8px;padding:12px 14px;margin:4px 0 8px;background:var(--subtle-fg,#f8f9fa);">
				<div style="font-weight:700;margin-bottom:8px;">${frappe.utils.escape_html(loan.name)}</div>
				<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px 16px;font-size:12px;">
					<div><div class="text-muted">${__("Employee")}</div><div style="font-weight:600;">${frappe.utils.escape_html(loan.employee)} — ${frappe.utils.escape_html(loan.full_name || "")}</div></div>
					<div><div class="text-muted">${__("Loan Date")}</div><div style="font-weight:600;">${frappe.utils.escape_html(String(loan.loan_date || ""))}</div></div>
					<div><div class="text-muted">${__("Principal")}</div><div style="font-weight:600;">${gld_fmt_currency(loan.amount)}</div></div>
					<div><div class="text-muted">${__("Outstanding")}</div><div style="font-weight:600;">${gld_fmt_currency(loan.outstanding_amount)}</div></div>
					<div><div class="text-muted">${__("Expected EMI")}</div><div style="font-weight:600;">${gld_fmt_currency(loan.expected_emi)}</div></div>
					<div><div class="text-muted">${__("Start")}</div><div style="font-weight:600;">${frappe.utils.escape_html(loan.start || "")}</div></div>
					<div><div class="text-muted">${__("Tenure")}</div><div style="font-weight:600;">${loan.proposed_tenure_months || "—"} ${__("months")}</div></div>
					<div style="grid-column:1/-1;"><div class="text-muted">${__("Reason")}</div><div style="font-weight:600;">${frappe.utils.escape_html(loan.reason || "—")}</div></div>
				</div>
			</div>
		`);
	}

	function select_loan(name) {
		selected_loan = name;
		d.set_value("loan", name || "");
		const loan = name ? loan_map[name] : null;
		render_loan_info(loan);
		if (loan) {
			d.set_value("amount", loan.suggested_amount);
		}
		d.fields_dict.loan_list.$wrapper.find(".gld-loan-row").removeClass("selected");
		if (name) {
			d.fields_dict.loan_list.$wrapper
				.find(`.gld-loan-row[data-loan="${CSS.escape(name)}"]`)
				.addClass("selected");
		}
	}

	function render_loan_list(rows) {
		const $wrap = d.fields_dict.loan_list.$wrapper;
		if (!rows.length) {
			$wrap.html(
				`<div class="text-muted" style="padding:10px 0;">${__("No eligible active loans without a due for this month.")}</div>`
			);
			return;
		}
		let html = `
			<style>
				.gld-loan-pick { border:1px solid var(--border-color); border-radius:8px; overflow:hidden; max-height:240px; overflow-y:auto; }
				.gld-loan-row { display:grid; grid-template-columns:1.1fr 1.2fr 1fr .9fr .9fr; gap:8px; padding:10px 12px; border-bottom:1px solid var(--border-color); cursor:pointer; font-size:12px; }
				.gld-loan-row:last-child { border-bottom:none; }
				.gld-loan-row:hover { background: var(--highlight-color, rgba(0,0,0,.03)); }
				.gld-loan-row.selected { background: rgba(37,99,235,.08); outline:1px solid var(--primary); }
				.gld-loan-row .k { color:var(--text-muted); font-size:10px; text-transform:uppercase; font-weight:600; }
				.gld-loan-row .v { font-weight:600; margin-top:2px; word-break:break-word; }
				.gld-loan-head { background:var(--subtle-fg,#f8f9fa); font-size:10px; text-transform:uppercase; letter-spacing:.03em; color:var(--text-muted); font-weight:700; cursor:default; }
				.gld-loan-head:hover { background:var(--subtle-fg,#f8f9fa); }
				@media (max-width:720px) {
					.gld-loan-row { grid-template-columns:1fr 1fr; }
					.gld-loan-head { display:none; }
				}
			</style>
			<div class="gld-loan-pick">
				<div class="gld-loan-row gld-loan-head">
					<div>${__("Employee")}</div>
					<div>${__("Loan")}</div>
					<div>${__("Reason")}</div>
					<div>${__("Outstanding")}</div>
					<div>${__("EMI")}</div>
				</div>
		`;
		rows.forEach((row) => {
			html += `
				<div class="gld-loan-row" data-loan="${frappe.utils.escape_html(row.name)}">
					<div><div class="k">${__("Employee")}</div><div class="v">${frappe.utils.escape_html(row.employee)}<br>${frappe.utils.escape_html(row.full_name || "")}</div></div>
					<div><div class="k">${__("Loan")}</div><div class="v">${frappe.utils.escape_html(row.name)}</div></div>
					<div><div class="k">${__("Reason")}</div><div class="v">${frappe.utils.escape_html(row.reason || "—")}</div></div>
					<div><div class="k">${__("Outstanding")}</div><div class="v">${gld_fmt_currency(row.outstanding_amount)}</div></div>
					<div><div class="k">${__("EMI")}</div><div class="v">${gld_fmt_currency(row.expected_emi)}</div></div>
				</div>
			`;
		});
		html += "</div>";
		$wrap.html(html);
		$wrap.find(".gld-loan-row[data-loan]").on("click", function () {
			select_loan($(this).attr("data-loan"));
		});
	}

	function load_loans() {
		const emp = (d.get_value("employee") || "").trim();
		frappe.call({
			method: "saral_hr.saral_hr.page.generate_monthly_loan_dues.generate_monthly_loan_dues.search_loans_for_due",
			args: {
				company: f.company,
				month: f.month,
				year: f.year,
				employee: emp,
			},
			freeze: true,
			freeze_message: __("Loading loans…"),
			callback(r) {
				const rows = r.message || [];
				Object.keys(loan_map).forEach((k) => delete loan_map[k]);
				rows.forEach((row) => {
					loan_map[row.name] = row;
				});
				render_loan_list(rows);
				if (selected_loan && loan_map[selected_loan]) {
					select_loan(selected_loan);
				} else {
					select_loan(null);
					d.set_value("amount", "");
				}
			},
		});
	}

	d.show();
	// Link default / awesomplete may not fire field onchange — bind + initial load
	d.fields_dict.employee.$input.on("awesomplete-selectcomplete change", () => {
		setTimeout(load_loans, 50);
	});
	setTimeout(load_loans, 0);
}
