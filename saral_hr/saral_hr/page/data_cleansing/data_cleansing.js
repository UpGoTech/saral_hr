frappe.pages["data-cleansing"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Data Cleansing"),
		single_column: true,
	});
	wrapper._dc_page = page;
};

frappe.pages["data-cleansing"].on_page_show = function (wrapper) {
	inject_dc_styles();
	const $main = $(wrapper).find(".layout-main-section");
	$main.html(dc_shell_html());
	init_data_cleansing($main, wrapper._dc_page);
};

function inject_dc_styles() {
	if (document.getElementById("dc-styles")) return;
	const s = document.createElement("style");
	s.id = "dc-styles";
	s.innerHTML = `
		.dc-root { padding: 0 20px 40px; font-family: var(--font-stack); color: var(--text-color); }
		.dc-filter-bar { display: flex; align-items: flex-end; gap: 12px; flex-wrap: wrap; padding: 16px 0 12px; }
		.dc-field { display: flex; flex-direction: column; gap: 4px; min-width: 140px; }
		.dc-field label { font-size: 11px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.04em; }
		.dc-field .frappe-control { margin-bottom: 0 !important; }
		.dc-btn {
			height: 30px; padding: 0 14px; background: var(--primary); color: #fff;
			border: none; border-radius: var(--border-radius); font-size: 12px; font-weight: 600; cursor: pointer;
		}
		.dc-btn:disabled { opacity: 0.5; cursor: not-allowed; }
		.dc-btn-outline {
			height: 28px; padding: 0 10px; background: transparent; color: var(--text-color);
			border: 1px solid var(--border-color); border-radius: var(--border-radius); font-size: 12px; cursor: pointer;
		}
		.dc-btn-danger { background: var(--red-500, #e03131); color: #fff; border: none; }
		.dc-meta { font-size: 13px; color: var(--text-muted); margin-bottom: 12px; }
		.dc-table { width: 100%; border-collapse: collapse; font-size: 13px; }
		.dc-table th, .dc-table td { border-bottom: 1px solid var(--border-color); padding: 8px 10px; text-align: left; vertical-align: top; }
		.dc-table th { font-size: 11px; text-transform: uppercase; color: var(--text-muted); font-weight: 600; }
		.dc-table tr:hover td { background: var(--fg-hover, rgba(0,0,0,0.02)); }
		.dc-flag {
			display: inline-block; margin: 1px 4px 1px 0; padding: 1px 7px; border-radius: 10px;
			font-size: 11px; background: var(--bg-light-gray, #f1f3f5); color: var(--text-color);
		}
		.dc-flag.warn { background: #fff3bf; color: #5c4800; }
		.dc-flag.bad { background: #ffe3e3; color: #c92a2a; }
		.dc-empty { padding: 24px 0; color: var(--text-muted); }
		.dc-detail { margin-top: 20px; border: 1px solid var(--border-color); border-radius: 8px; padding: 14px 16px; }
		.dc-detail h4 { margin: 0 0 10px; font-size: 14px; }
		.dc-detail-actions { display: flex; gap: 8px; flex-wrap: wrap; margin: 10px 0 14px; }
		.dc-att-list { max-height: 280px; overflow: auto; border: 1px solid var(--border-color); border-radius: 6px; }
		.dc-att-row { display: flex; align-items: center; gap: 10px; padding: 6px 10px; border-bottom: 1px solid var(--border-color); font-size: 13px; }
		.dc-att-row:last-child { border-bottom: none; }
		.dc-slip-row { display: flex; align-items: center; gap: 10px; padding: 8px 0; border-bottom: 1px solid var(--border-color); font-size: 13px; }
		.dc-mode-toggle {
			display: inline-flex; border: 1px solid var(--border-color); border-radius: var(--border-radius);
			overflow: hidden; height: 30px; align-self: flex-end;
		}
		.dc-mode-toggle button {
			border: none; background: transparent; padding: 0 12px; font-size: 12px; font-weight: 600;
			cursor: pointer; color: var(--text-muted); height: 100%;
		}
		.dc-mode-toggle button.active { background: var(--primary); color: #fff; }
		.dc-period-fields.dc-disabled { opacity: 0.45; pointer-events: none; }
	`;
	document.head.appendChild(s);
}

function dc_shell_html() {
	return `
		<div class="dc-root">
			<div class="dc-filter-bar">
				<div class="dc-field" style="min-width:260px"><label>${__("Employee")}</label><div class="dc-employee"></div></div>
				<div class="dc-mode-toggle" title="${__("Period scan uses From–To. Whole data search lists every month with attendance or slips.")}">
					<button type="button" class="dc-mode-btn" data-mode="period">${__("Period scan")}</button>
					<button type="button" class="dc-mode-btn active" data-mode="all">${__("Whole data search")}</button>
				</div>
				<div class="dc-period-fields dc-disabled" style="display:flex;gap:12px;flex-wrap:wrap;align-items:flex-end;">
					<div class="dc-field"><label>${__("From Year")}</label><input type="number" class="form-control dc-from-year" min="1950" max="2099"></div>
					<div class="dc-field"><label>${__("From Month")}</label><select class="form-control dc-from-month"></select></div>
					<div class="dc-field"><label>${__("To Year")}</label><input type="number" class="form-control dc-to-year" min="1950" max="2099"></div>
					<div class="dc-field"><label>${__("To Month")}</label><select class="form-control dc-to-month"></select></div>
				</div>
				<button class="dc-btn dc-load">${__("Load")}</button>
			</div>
			<div class="dc-meta"></div>
			<div class="dc-matrix"></div>
			<div class="dc-detail-wrap"></div>
		</div>
	`;
}

const DC_MONTHS = [
	"January","February","March","April","May","June",
	"July","August","September","October","November","December"
];

function init_data_cleansing($main) {
	const now = new Date();
	const year = now.getFullYear();
	const month = now.getMonth() + 1;

	const $fromMonth = $main.find(".dc-from-month");
	const $toMonth = $main.find(".dc-to-month");
	DC_MONTHS.forEach((label, i) => {
		$fromMonth.append(`<option value="${i + 1}">${label}</option>`);
		$toMonth.append(`<option value="${i + 1}">${label}</option>`);
	});
	$main.find(".dc-from-year").val(year);
	$main.find(".dc-to-year").val(year);
	$fromMonth.val(1);
	$toMonth.val(month);

	const employee_control = frappe.ui.form.make_control({
		parent: $main.find(".dc-employee"),
		df: {
			fieldtype: "Link",
			options: "Company Link",
			fieldname: "employee",
			placeholder: __("Select Company Link"),
			only_select: 1,
		},
		render_input: true,
	});
	employee_control.refresh();

	const state = {
		employee_control,
		matrix: null,
		detail: null,
		can_mutate: false,
		scan_mode: "all",
	};

	function sync_mode_ui() {
		$main.find(".dc-mode-btn").removeClass("active");
		$main.find(`.dc-mode-btn[data-mode="${state.scan_mode}"]`).addClass("active");
		$main.find(".dc-period-fields").toggleClass("dc-disabled", state.scan_mode !== "period");
	}

	$main.find(".dc-mode-btn").on("click", function () {
		state.scan_mode = $(this).data("mode");
		sync_mode_ui();
	});
	sync_mode_ui();

	$main.find(".dc-load").on("click", () => load_matrix($main, state));
}

function load_matrix($main, state, after) {
	const employee = state.employee_control.get_value();
	if (!employee) {
		frappe.msgprint(__("Please select an employee"));
		return;
	}
	const args = {
		employee,
		scan_mode: state.scan_mode || "all",
	};
	if (args.scan_mode === "period") {
		args.from_year = cint($main.find(".dc-from-year").val());
		args.from_month = cint($main.find(".dc-from-month").val());
		args.to_year = cint($main.find(".dc-to-year").val());
		args.to_month = cint($main.find(".dc-to-month").val());
	}

	$main.find(".dc-matrix").html(`<div class="dc-empty">${__("Loading…")}</div>`);
	if (!after) $main.find(".dc-detail-wrap").empty();

	frappe.call({
		method: "saral_hr.saral_hr.page.data_cleansing.data_cleansing.get_employee_month_matrix",
		args,
		callback(r) {
			state.matrix = r.message || {};
			state.can_mutate = !!state.matrix.can_mutate;
			render_matrix($main, state);
			if (typeof after === "function") after();
		},
	});
}

function flag_class(flag) {
	if (flag === "Partial coverage" || flag === "Draft slip") return "warn";
	return "bad";
}

function render_matrix($main, state) {
	const m = state.matrix;
	const tenure = [
		m.date_of_joining ? `${__("Joined")} ${frappe.datetime.str_to_user(m.date_of_joining)}` : null,
		m.left_date ? `${__("Left")} ${frappe.datetime.str_to_user(m.left_date)}` : null,
	].filter(Boolean).join(" · ");

	const mode_label = m.scan_mode === "all"
		? __("Whole data search")
		: __("Period scan");

	$main.find(".dc-meta").html(
		`<strong>${frappe.utils.escape_html(m.employee_name || m.employee)}</strong>`
		+ ` · ${frappe.utils.escape_html(m.company || "")}`
		+ (tenure ? ` · ${tenure}` : "")
		+ ` · ${mode_label}`
		+ ` · ${(m.months || []).length} ${__("month(s) with data")}`
		+ (state.can_mutate ? "" : ` · <span class="text-muted">${__("View only")}</span>`)
	);

	const rows = m.months || [];
	if (!rows.length) {
		$main.find(".dc-matrix").html(`<div class="dc-empty">${__("No attendance or salary slips in this range.")}</div>`);
		return;
	}

	let html = `<table class="dc-table"><thead><tr>
		<th>${__("Month")}</th><th>${__("Att days")}</th><th>${__("Expected")}</th>
		<th>${__("Coverage")}</th><th>${__("Slip")}</th><th>${__("Slip status")}</th>
		<th>${__("Flags")}</th><th></th>
	</tr></thead><tbody>`;

	rows.forEach((row) => {
		const flags = (row.flags || []).map(
			(f) => `<span class="dc-flag ${flag_class(f)}">${frappe.utils.escape_html(f)}</span>`
		).join("");
		html += `<tr data-year="${row.year}" data-month="${row.month}">
			<td>${frappe.utils.escape_html(row.month_label)}</td>
			<td>${row.attendance_days}</td>
			<td>${row.expected_days}</td>
			<td>${frappe.utils.escape_html(row.coverage)}</td>
			<td>${frappe.utils.escape_html(row.slip_names)}</td>
			<td>${frappe.utils.escape_html(row.slip_status)}</td>
			<td>${flags || "—"}</td>
			<td><button class="dc-btn-outline dc-view">${__("View")}</button></td>
		</tr>`;
	});
	html += "</tbody></table>";
	$main.find(".dc-matrix").html(html);

	$main.find(".dc-matrix .dc-view").on("click", function () {
		const $tr = $(this).closest("tr");
		load_detail($main, state, cint($tr.data("year")), cint($tr.data("month")));
	});
}

function load_detail($main, state, year, month) {
	frappe.call({
		method: "saral_hr.saral_hr.page.data_cleansing.data_cleansing.get_month_detail",
		args: { employee: state.matrix.employee, year, month },
		callback(r) {
			state.detail = r.message;
			render_detail($main, state);
		},
	});
}

function render_detail($main, state) {
	const d = state.detail;
	if (!d) return;
	const can = state.can_mutate;
	const summary = d.summary || {};
	const label = summary.month_label || `${d.month_start}`;

	let actions = "";
	if (can) {
		if ((d.slips || []).length) {
			actions += `<span class="text-muted" style="font-size:12px">${__("Delete attendance is blocked until all slips for this month are removed.")}</span>`;
		} else if ((d.attendance || []).length) {
			actions += `<button class="dc-btn dc-btn-danger dc-del-month">${__("Delete all attendance this month")}</button>`;
			actions += `<button class="dc-btn-outline dc-del-selected">${__("Delete selected days")}</button>`;
		}
	}

	let slips_html = "";
	(d.slips || []).forEach((s) => {
		let btns = `<a href="/app/salary-slip/${encodeURIComponent(s.name)}" target="_blank">${frappe.utils.escape_html(s.name)}</a>`;
		btns += ` · ${frappe.utils.escape_html(s.status)}`;
		if (can && s.docstatus === 1) {
			btns += ` <button class="dc-btn-outline dc-cancel-slip" data-name="${frappe.utils.escape_html(s.name)}">${__("Cancel")}</button>`;
		}
		if (can && s.docstatus !== 1) {
			btns += ` <button class="dc-btn-outline dc-del-slip" data-name="${frappe.utils.escape_html(s.name)}">${__("Delete")}</button>`;
		}
		slips_html += `<div class="dc-slip-row">${btns}</div>`;
	});
	if (!slips_html) slips_html = `<div class="text-muted">${__("No salary slips")}</div>`;

	let att_html = "";
	(d.attendance || []).forEach((a) => {
		const cb = can && !(d.slips || []).length
			? `<input type="checkbox" class="dc-att-cb" value="${frappe.utils.escape_html(a.name)}">`
			: "";
		att_html += `<div class="dc-att-row">${cb}
			<span style="width:110px">${frappe.datetime.str_to_user(a.attendance_date)}</span>
			<span>${frappe.utils.escape_html(a.status)}</span>
			<a class="text-muted" href="/app/attendance/${encodeURIComponent(a.name)}" target="_blank">${frappe.utils.escape_html(a.name)}</a>
		</div>`;
	});
	if (!att_html) att_html = `<div class="dc-empty">${__("No attendance rows")}</div>`;

	$main.find(".dc-detail-wrap").html(`
		<div class="dc-detail">
			<h4>${__("Detail")} — ${frappe.utils.escape_html(label)}</h4>
			<div class="dc-detail-actions">${actions}</div>
			<div style="margin-bottom:8px;font-weight:600">${__("Salary Slips")}</div>
			${slips_html}
			<div style="margin:14px 0 8px;font-weight:600">${__("Attendance")} (${(d.attendance || []).length})</div>
			<div class="dc-att-list">${att_html}</div>
		</div>
	`);

	$main.find(".dc-cancel-slip").on("click", function () {
		const name = $(this).data("name");
		frappe.confirm(__("Cancel salary slip {0}?", [name]), () => {
			frappe.call({
				method: "saral_hr.saral_hr.page.data_cleansing.data_cleansing.cancel_salary_slip",
				args: { name },
				callback() {
					frappe.show_alert({ message: __("Cancelled"), indicator: "green" });
					reload_after_mutate($main, state, summary.year, summary.month);
				},
			});
		});
	});

	$main.find(".dc-del-slip").on("click", function () {
		const name = $(this).data("name");
		frappe.confirm(__("Delete salary slip {0}? This cannot be undone.", [name]), () => {
			frappe.call({
				method: "saral_hr.saral_hr.page.data_cleansing.data_cleansing.delete_salary_slip",
				args: { name },
				callback() {
					frappe.show_alert({ message: __("Deleted"), indicator: "green" });
					reload_after_mutate($main, state, summary.year, summary.month);
				},
			});
		});
	});

	$main.find(".dc-del-month").on("click", () => {
		const n = (d.attendance || []).length;
		frappe.confirm(
			__("Delete {0} attendance row(s) for {1}?", [n, label]),
			() => {
				frappe.call({
					method: "saral_hr.saral_hr.page.data_cleansing.data_cleansing.delete_attendance",
					args: {
						employee: state.matrix.employee,
						year: summary.year,
						month: summary.month,
					},
					callback(r) {
						frappe.show_alert({
							message: __("Deleted {0} attendance row(s)", [r.message.count]),
							indicator: "green",
						});
						reload_after_mutate($main, state, summary.year, summary.month);
					},
				});
			}
		);
	});

	$main.find(".dc-del-selected").on("click", () => {
		const names = $main.find(".dc-att-cb:checked").map(function () { return this.value; }).get();
		if (!names.length) {
			frappe.msgprint(__("Select at least one day"));
			return;
		}
		frappe.confirm(__("Delete {0} selected attendance day(s)?", [names.length]), () => {
			frappe.call({
				method: "saral_hr.saral_hr.page.data_cleansing.data_cleansing.delete_attendance",
				args: { employee: state.matrix.employee, names },
				callback(r) {
					frappe.show_alert({
						message: __("Deleted {0} attendance row(s)", [r.message.count]),
						indicator: "green",
					});
					reload_after_mutate($main, state, summary.year, summary.month);
				},
			});
		});
	});
}

function reload_after_mutate($main, state, year, month) {
	load_matrix($main, state, () => {
		if (year && month) load_detail($main, state, year, month);
	});
}
