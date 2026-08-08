frappe.pages["data-cleansing"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Data Cleansing"),
		single_column: true,
	});
	wrapper._dc_page = page;
};

frappe.pages["data-cleansing"].on_page_show = function (wrapper) {
	// Keep standard Desk chrome (workspace sidebar) — do not go full-bleed
	$("body").removeClass("full-width");
	dc_set_breadcrumbs();
	if (wrapper._dc_page) {
		wrapper._dc_page.set_title(__("Data Cleansing"));
	}
	inject_dc_styles();
	const $main = $(wrapper).find(".layout-main-section");
	$main.html(dc_shell_html());
	init_data_cleansing($main, wrapper._dc_page);
};

function dc_set_breadcrumbs() {
	const $nb = $("#navbar-breadcrumbs");
	if (!$nb.length) return;
	$nb.empty().append(
		`<li><a href="/app/saral-hr">${__("Saral HR")}</a></li>`,
		`<li><a href="/app/data-cleansing">${__("Data Cleansing")}</a></li>`
	);
	document.title = __("Data Cleansing");
}

function inject_dc_styles() {
	$("#dc-styles, #dc-styles-v2, #dc-styles-v3, #dc-styles-v4, #dc-styles-v5").remove();
	const s = document.createElement("style");
	s.id = "dc-styles-v5";
	s.innerHTML = `
		.dc-root { padding: 8px 0 40px; color: var(--text-color); }
		.dc-filter-card, .dc-emp-card, .dc-results-card {
			background: var(--card-bg, var(--fg-color));
			border: 1px solid var(--border-color);
			border-radius: 8px;
			margin-bottom: 12px;
		}
		.dc-filter-card { padding: 14px 16px; }
		.dc-filter-grid {
			display: grid;
			grid-template-columns: minmax(220px, 1.1fr) max-content repeat(4, 108px) auto;
			column-gap: 12px;
			row-gap: 6px;
			align-items: center;
		}
		.dc-filter-grid > .dc-filter-label {
			grid-row: 1;
			font-size: 11px; font-weight: 700; color: var(--text-muted);
			text-transform: uppercase; letter-spacing: .04em; margin: 0; line-height: 1.2;
		}
		.dc-filter-grid > .dc-filter-control { grid-row: 2; min-width: 0; }
		.dc-employee-wrap .frappe-control,
		.dc-employee-wrap .form-group { margin-bottom: 0 !important; }
		.dc-employee-wrap .control-label,
		.dc-employee-wrap .help-box,
		.dc-employee-wrap .clearfix { display: none !important; height: 0 !important; margin: 0 !important; padding: 0 !important; }
		.dc-employee-wrap .control-input-wrapper,
		.dc-employee-wrap .awesomplete,
		.dc-employee-wrap .awesomplete > input { width: 100% !important; }
		.dc-employee-wrap input.input-with-feedback,
		.dc-filter-grid .form-control,
		.dc-filter-grid select,
		.dc-filter-grid input[type=number] {
			height: 32px !important; min-height: 32px !important;
			font-size: 13px; border-radius: 6px; margin: 0; width: 100%;
		}
		.dc-period-fields.dc-disabled,
		.dc-period-disabled { opacity: .4; pointer-events: none; }
		@media (max-width: 1100px) {
			.dc-filter-grid {
				grid-template-columns: repeat(2, minmax(160px, 1fr));
			}
			.dc-filter-grid > .dc-filter-label,
			.dc-filter-grid > .dc-filter-control { grid-row: auto; }
		}
		.dc-mode-toggle {
			display: inline-flex; border: 1px solid var(--border-color); border-radius: 6px;
			overflow: hidden; height: 32px; background: var(--control-bg, var(--bg-color));
		}
		.dc-mode-toggle button {
			border: none; background: transparent; padding: 0 12px; font-size: 12px; font-weight: 600;
			cursor: pointer; color: var(--text-muted); height: 100%; white-space: nowrap;
		}
		.dc-mode-toggle button.active {
			background: var(--fg-color); color: var(--text-color);
			box-shadow: inset 0 0 0 1px var(--border-color);
		}
		.dc-period-fields.dc-disabled { opacity: .4; pointer-events: none; }
		.dc-btn {
			height: 32px; padding: 0 18px; border: none; border-radius: 6px;
			background: var(--primary); color: #fff; font-size: 13px; font-weight: 600; cursor: pointer;
			white-space: nowrap;
		}
		.dc-btn:hover { filter: brightness(.96); }
		.dc-btn-ghost {
			height: 28px; padding: 0 10px; border: 1px solid var(--border-color); border-radius: 6px;
			background: transparent; color: var(--text-color); font-size: 12px; font-weight: 600; cursor: pointer;
		}
		.dc-btn-ghost:hover { background: var(--subtle-fg, rgba(0,0,0,.03)); }
		.dc-btn-danger {
			height: 28px; padding: 0 12px; border: none; border-radius: 6px;
			background: var(--red-500, #e03131); color: #fff; font-size: 12px; font-weight: 600; cursor: pointer;
		}
		.dc-flag-filter {
			display: inline-flex; border: 1px solid var(--border-color); border-radius: 6px; overflow: hidden; height: 28px;
		}
		.dc-flag-filter button {
			border: none; background: transparent; padding: 0 11px; font-size: 12px; font-weight: 600;
			color: var(--text-muted); cursor: pointer; height: 100%;
		}
		.dc-flag-filter button.active { background: var(--subtle-fg, #f1f3f5); color: var(--text-color); }

		.dc-emp-card { display: none; padding: 16px 18px; }
		.dc-emp-card.visible { display: block; }
		.dc-emp-top { display: flex; gap: 14px; align-items: center; }
		.dc-avatar {
			width: 44px; height: 44px; border-radius: 50%; flex-shrink: 0;
			display: flex; align-items: center; justify-content: center;
			font-size: 14px; font-weight: 700; color: #fff; background: var(--text-muted);
		}
		.dc-emp-name { font-size: 16px; font-weight: 700; line-height: 1.25; margin: 0 0 2px; }
		.dc-emp-id { font-size: 12px; color: var(--text-muted); }
		.dc-emp-meta {
			display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
			gap: 10px 16px; margin-top: 14px; padding-top: 14px;
			border-top: 1px solid var(--border-color);
		}
		.dc-emp-meta-item .k { font-size: 11px; color: var(--text-muted); font-weight: 600; text-transform: uppercase; letter-spacing: .03em; }
		.dc-emp-meta-item .v { font-size: 13px; font-weight: 600; margin-top: 2px; }
		.dc-pill {
			display: inline-flex; align-items: center; height: 22px; padding: 0 8px;
			border-radius: 11px; font-size: 11px; font-weight: 600;
			background: var(--subtle-fg, #f1f3f5); color: var(--text-muted);
		}
		.dc-pill.warn { background: #fff3bf; color: #5c4800; }
		.dc-pill.ok { background: #d3f9d8; color: #2b8a3e; }

		.dc-results-header {
			display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap;
			padding: 12px 16px; border-bottom: 1px solid var(--border-color);
		}
		.dc-results-title { font-size: 13px; font-weight: 700; }
		.dc-results-sub { font-size: 12px; color: var(--text-muted); font-weight: 500; }
		.dc-table-wrap { overflow: visible; max-height: none; }
		.dc-table { width: 100%; border-collapse: collapse; font-size: 13px; }
		.dc-table thead th {
			padding: 9px 14px; text-align: left; font-size: 11px; font-weight: 700;
			color: var(--text-muted); text-transform: uppercase; letter-spacing: .03em;
			background: var(--subtle-fg, #f8f9fa); border-bottom: 1px solid var(--border-color);
			white-space: nowrap;
		}
		.dc-table tbody td {
			padding: 11px 14px; border-bottom: 1px solid var(--border-color);
			vertical-align: middle;
		}
		.dc-table tbody tr:last-child td { border-bottom: none; }
		.dc-table tbody tr:hover td { background: var(--highlight-color, rgba(0,0,0,.02)); }
		.dc-table tbody tr.dc-has-flags td { background: rgba(255, 224, 102, .08); }
		.dc-flag {
			display: inline-block; margin: 1px 4px 1px 0; padding: 2px 8px; border-radius: 10px;
			font-size: 11px; font-weight: 600; background: var(--subtle-fg); color: var(--text-color);
		}
		.dc-flag.warn { background: #fff3bf; color: #5c4800; }
		.dc-flag.bad { background: #ffe3e3; color: #c92a2a; }
		.dc-empty { padding: 40px 20px; text-align: center; color: var(--text-muted); font-size: 13px; }
		.dc-empty-title { font-weight: 600; color: var(--text-color); margin-bottom: 4px; }

		.dc-dialog-body { padding: 4px 2px 8px; }
		.dc-dialog-summary {
			display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px;
			margin-bottom: 14px;
		}
		.dc-dialog-stat {
			border: 1px solid var(--border-color); border-radius: 8px; padding: 10px 12px;
			background: var(--subtle-fg, #f8f9fa);
		}
		.dc-dialog-stat .k { font-size: 11px; color: var(--text-muted); font-weight: 600; text-transform: uppercase; }
		.dc-dialog-stat .v { font-size: 14px; font-weight: 700; margin-top: 3px; }
		.dc-section-label {
			font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: .04em;
			color: var(--text-muted); margin: 14px 0 8px;
		}
		.dc-slip-row, .dc-att-row {
			display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
			padding: 8px 0; border-bottom: 1px solid var(--border-color); font-size: 13px;
		}
		.dc-slip-row:last-child, .dc-att-row:last-child { border-bottom: none; }
		.dc-att-list {
			max-height: 280px; overflow: auto; border: 1px solid var(--border-color);
			border-radius: 8px; padding: 4px 10px;
		}
		.dc-dialog-actions { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin: 4px 0 8px; }
		.dc-hint { font-size: 12px; color: var(--text-muted); }
		@media (max-width: 720px) {
			.dc-dialog-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
			.dc-field-employee { width: 100%; flex: 1 1 100%; }
		}
	`;
	document.head.appendChild(s);
}

function dc_shell_html() {
	return `
		<div class="dc-root">
			<div class="dc-filter-card">
				<div class="dc-filter-grid">
					<div class="dc-filter-label">${__("Employee")}</div>
					<div class="dc-filter-label">${__("Scan mode")}</div>
					<div class="dc-filter-label dc-period-label">${__("From Year")}</div>
					<div class="dc-filter-label dc-period-label">${__("From Month")}</div>
					<div class="dc-filter-label dc-period-label">${__("To Year")}</div>
					<div class="dc-filter-label dc-period-label">${__("To Month")}</div>
					<div class="dc-filter-label">&nbsp;</div>

					<div class="dc-filter-control dc-employee-wrap"><div class="dc-employee"></div></div>
					<div class="dc-filter-control">
						<div class="dc-mode-toggle" title="${__("Period scan uses From–To. Whole data search lists every month with attendance or slips.")}">
							<button type="button" class="dc-mode-btn" data-mode="period">${__("Period scan")}</button>
							<button type="button" class="dc-mode-btn active" data-mode="all">${__("Whole data search")}</button>
						</div>
					</div>
					<div class="dc-filter-control dc-period-field"><input type="number" class="form-control dc-from-year" min="1950" max="2099"></div>
					<div class="dc-filter-control dc-period-field"><select class="form-control dc-from-month"></select></div>
					<div class="dc-filter-control dc-period-field"><input type="number" class="form-control dc-to-year" min="1950" max="2099"></div>
					<div class="dc-filter-control dc-period-field"><select class="form-control dc-to-month"></select></div>
					<div class="dc-filter-control"><button type="button" class="dc-btn dc-load">${__("Scan")}</button></div>
				</div>
			</div>
			<div class="dc-emp-card"></div>
			<div class="dc-results-card">
				<div class="dc-results-header">
					<div>
						<div class="dc-results-title">${__("Months with data")}</div>
						<div class="dc-results-sub dc-results-hint">${__("Select an employee and scan to begin")}</div>
					</div>
					<div class="dc-flag-filter" title="${__("Filter months by flags")}">
						<button type="button" class="dc-flag-btn active" data-filter="all">${__("All")}</button>
						<button type="button" class="dc-flag-btn" data-filter="flagged">${__("Flagged")}</button>
						<button type="button" class="dc-flag-btn" data-filter="unflagged">${__("Unflagged")}</button>
					</div>
				</div>
				<div class="dc-matrix"><div class="dc-empty">${__("No scan yet.")}</div></div>
			</div>
		</div>
	`;
}

const DC_MONTHS = [
	"January","February","March","April","May","June",
	"July","August","September","October","November","December"
];

function dc_initials(name) {
	const parts = String(name || "").trim().split(/\s+/).filter(Boolean);
	if (!parts.length) return "?";
	if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
	return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function init_data_cleansing($main) {
	const now = new Date();
	const year = now.getFullYear();
	const month = now.getMonth() + 1;

	const $fromMonth = $main.find(".dc-from-month");
	const $toMonth = $main.find(".dc-to-month");
	DC_MONTHS.forEach((label, i) => {
		$fromMonth.append(`<option value="${i + 1}">${__(label)}</option>`);
		$toMonth.append(`<option value="${i + 1}">${__(label)}</option>`);
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
			label: __("Employee"),
			placeholder: __("Search employee / Company Link"),
			only_select: 1,
			hidden: 0,
			change() {
				const val = employee_control.get_value();
				if (!val) {
					$main.find(".dc-emp-card").removeClass("visible").empty();
				}
			},
		},
		render_input: true,
	});
	employee_control.refresh();
	// Link control ships its own label — hide it so our grid labels stay aligned
	$main.find(".dc-employee .control-label, .dc-employee .help-box").hide();

	const state = {
		employee_control,
		matrix: null,
		detail: null,
		can_mutate: false,
		scan_mode: "all",
		flag_filter: "all",
		dialog: null,
	};

	function sync_mode_ui() {
		$main.find(".dc-mode-btn").removeClass("active");
		$main.find(`.dc-mode-btn[data-mode="${state.scan_mode}"]`).addClass("active");
		const period = state.scan_mode === "period";
		$main.find(".dc-period-field, .dc-period-label").toggleClass("dc-period-disabled", !period);
	}

	$main.find(".dc-mode-btn").on("click", function () {
		state.scan_mode = $(this).data("mode");
		sync_mode_ui();
	});
	sync_mode_ui();

	$main.find(".dc-flag-btn").on("click", function () {
		state.flag_filter = $(this).data("filter");
		$main.find(".dc-flag-btn").removeClass("active");
		$(this).addClass("active");
		render_matrix($main, state);
	});

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

	$main.find(".dc-matrix").html(`<div class="dc-empty">${__("Scanning…")}</div>`);
	$main.find(".dc-results-hint").text(__("Loading…"));

	frappe.call({
		method: "saral_hr.saral_hr.page.data_cleansing.data_cleansing.get_employee_month_matrix",
		args,
		callback(r) {
			state.matrix = r.message || {};
			state.can_mutate = !!state.matrix.can_mutate;
			render_employee_card($main, state);
			render_matrix($main, state);
			if (typeof after === "function") after();
		},
	});
}

function render_employee_card($main, state) {
	const m = state.matrix || {};
	const name = m.employee_name || m.employee || "";
	const mode_label = m.scan_mode === "all" ? __("Whole data search") : __("Period scan");
	const months = (m.months || []).length;
	const flagged = (m.months || []).filter((row) => (row.flags || []).length).length;

	$main.find(".dc-emp-card").addClass("visible").html(`
		<div class="dc-emp-top">
			<div class="dc-avatar">${frappe.utils.escape_html(dc_initials(name))}</div>
			<div style="flex:1;min-width:0">
				<div class="dc-emp-name">${frappe.utils.escape_html(name)}</div>
				<div class="dc-emp-id">${frappe.utils.escape_html(m.employee || "")}</div>
			</div>
			<span class="dc-pill ${state.can_mutate ? "ok" : "warn"}">
				${state.can_mutate ? __("Can cleanse") : __("View only")}
			</span>
		</div>
		<div class="dc-emp-meta">
			<div class="dc-emp-meta-item"><div class="k">${__("Company")}</div><div class="v">${frappe.utils.escape_html(m.company || "—")}</div></div>
			<div class="dc-emp-meta-item"><div class="k">${__("Joined")}</div><div class="v">${m.date_of_joining ? frappe.datetime.str_to_user(m.date_of_joining) : "—"}</div></div>
			<div class="dc-emp-meta-item"><div class="k">${__("Left")}</div><div class="v">${m.left_date ? frappe.datetime.str_to_user(m.left_date) : __("Active")}</div></div>
			<div class="dc-emp-meta-item"><div class="k">${__("Scan")}</div><div class="v">${frappe.utils.escape_html(mode_label)}</div></div>
			<div class="dc-emp-meta-item"><div class="k">${__("Months found")}</div><div class="v">${months}</div></div>
			<div class="dc-emp-meta-item"><div class="k">${__("Flagged")}</div><div class="v">${flagged}</div></div>
		</div>
	`);
}

function flag_class(flag) {
	if (flag === "Partial coverage" || flag === "Draft slip") return "warn";
	return "bad";
}

function filtered_rows(state) {
	const rows = (state.matrix && state.matrix.months) || [];
	const f = state.flag_filter || "all";
	if (f === "flagged") return rows.filter((r) => (r.flags || []).length > 0);
	if (f === "unflagged") return rows.filter((r) => !(r.flags || []).length);
	return rows;
}

function render_matrix($main, state) {
	const m = state.matrix || {};
	const all_rows = m.months || [];
	const rows = filtered_rows(state);
	const mode_label = m.scan_mode === "all" ? __("Whole data search") : __("Period scan");
	const filter_label = {
		all: __("All"),
		flagged: __("Flagged"),
		unflagged: __("Unflagged"),
	}[state.flag_filter || "all"];

	$main.find(".dc-results-hint").text(
		__("{0} · showing {1} of {2} · {3}", [mode_label, rows.length, all_rows.length, filter_label])
	);

	if (!all_rows.length) {
		$main.find(".dc-matrix").html(`
			<div class="dc-empty">
				<div class="dc-empty-title">${__("No attendance or salary slips found")}</div>
				<div>${__("Try Whole data search, or widen the period.")}</div>
			</div>
		`);
		return;
	}

	if (!rows.length) {
		$main.find(".dc-matrix").html(`
			<div class="dc-empty">
				<div class="dc-empty-title">${__("No months match this filter")}</div>
				<div>${__("Switch to All or another flag filter.")}</div>
			</div>
		`);
		return;
	}

	let html = `<div class="dc-table-wrap"><table class="dc-table"><thead><tr>
		<th>${__("Month")}</th>
		<th>${__("Att days")}</th>
		<th>${__("Expected")}</th>
		<th>${__("Coverage")}</th>
		<th>${__("Slip")}</th>
		<th>${__("Status")}</th>
		<th>${__("Flags")}</th>
		<th style="width:88px"></th>
	</tr></thead><tbody>`;

	rows.forEach((row) => {
		const flags = (row.flags || []).map(
			(f) => `<span class="dc-flag ${flag_class(f)}">${frappe.utils.escape_html(f)}</span>`
		).join("");
		const has_flags = (row.flags || []).length > 0;
		html += `<tr class="${has_flags ? "dc-has-flags" : ""}" data-year="${row.year}" data-month="${row.month}">
			<td><strong>${frappe.utils.escape_html(row.month_label)}</strong></td>
			<td>${row.attendance_days}</td>
			<td>${row.expected_days}</td>
			<td>${frappe.utils.escape_html(row.coverage)}</td>
			<td>${frappe.utils.escape_html(row.slip_names)}</td>
			<td>${frappe.utils.escape_html(row.slip_status)}</td>
			<td>${flags || "—"}</td>
			<td><button type="button" class="dc-btn-ghost dc-view">${__("View")}</button></td>
		</tr>`;
	});
	html += "</tbody></table></div>";
	$main.find(".dc-matrix").html(html);

	$main.find(".dc-matrix .dc-view").on("click", function () {
		const $tr = $(this).closest("tr");
		open_month_dialog($main, state, cint($tr.data("year")), cint($tr.data("month")));
	});
}

function open_month_dialog($main, state, year, month) {
	frappe.call({
		method: "saral_hr.saral_hr.page.data_cleansing.data_cleansing.get_month_detail",
		args: { employee: state.matrix.employee, year, month },
		freeze: true,
		freeze_message: __("Loading month…"),
		callback(r) {
			state.detail = r.message;
			show_month_dialog($main, state);
		},
	});
}

function show_month_dialog($main, state) {
	const d = state.detail;
	if (!d) return;
	const can = state.can_mutate;
	const summary = d.summary || {};
	const label = summary.month_label || d.month_start;
	const emp_name = state.matrix.employee_name || state.matrix.employee;

	if (state.dialog) {
		state.dialog.hide();
		state.dialog = null;
	}

	const dialog = new frappe.ui.Dialog({
		title: __("{0} — {1}", [emp_name, label]),
		size: "large",
		fields: [{ fieldtype: "HTML", fieldname: "body" }],
		primary_action_label: can ? __("Close") : __("Done"),
		primary_action() {
			dialog.hide();
		},
	});
	state.dialog = dialog;

	const $body = $(dialog.fields_dict.body.wrapper);
	$body.html(build_dialog_body_html(d, can, label));
	bind_dialog_actions($body, $main, state, dialog, d, label);
	dialog.show();
}

function build_dialog_body_html(d, can, label) {
	const summary = d.summary || {};
	const flags = (summary.flags || []).map(
		(f) => `<span class="dc-flag ${flag_class(f)}">${frappe.utils.escape_html(f)}</span>`
	).join("") || "—";

	let actions = `<div class="dc-dialog-actions">`;
	if (can) {
		if ((d.slips || []).length) {
			actions += `<span class="dc-hint">${__("Remove all slips for this month before deleting attendance.")}</span>`;
		} else if ((d.attendance || []).length) {
			actions += `<button type="button" class="dc-btn-danger dc-del-month">${__("Delete all attendance")}</button>`;
			actions += `<button type="button" class="dc-btn-ghost dc-del-selected">${__("Delete selected days")}</button>`;
		}
	} else {
		actions += `<span class="dc-hint">${__("View only — ask a Manager to cleanse.")}</span>`;
	}
	actions += `</div>`;

	let slips_html = "";
	(d.slips || []).forEach((s) => {
		let row = `<a href="/app/salary-slip/${encodeURIComponent(s.name)}" target="_blank">${frappe.utils.escape_html(s.name)}</a>`;
		row += ` <span class="dc-pill">${frappe.utils.escape_html(s.status)}</span>`;
		if (can && s.docstatus === 1) {
			row += ` <button type="button" class="dc-btn-ghost dc-cancel-slip" data-name="${frappe.utils.escape_html(s.name)}">${__("Cancel")}</button>`;
		}
		if (can && s.docstatus !== 1) {
			row += ` <button type="button" class="dc-btn-ghost dc-del-slip" data-name="${frappe.utils.escape_html(s.name)}">${__("Delete")}</button>`;
		}
		slips_html += `<div class="dc-slip-row">${row}</div>`;
	});
	if (!slips_html) slips_html = `<div class="dc-hint">${__("No salary slips")}</div>`;

	let att_html = "";
	(d.attendance || []).forEach((a) => {
		const cb = can && !(d.slips || []).length
			? `<input type="checkbox" class="dc-att-cb" value="${frappe.utils.escape_html(a.name)}">`
			: "";
		att_html += `<div class="dc-att-row">${cb}
			<span style="width:110px;flex-shrink:0">${frappe.datetime.str_to_user(a.attendance_date)}</span>
			<span style="min-width:100px">${frappe.utils.escape_html(a.status)}</span>
			<a class="text-muted" href="/app/attendance/${encodeURIComponent(a.name)}" target="_blank">${frappe.utils.escape_html(a.name)}</a>
		</div>`;
	});
	if (!att_html) att_html = `<div class="dc-hint" style="padding:10px 0">${__("No attendance rows")}</div>`;

	return `
		<div class="dc-dialog-body">
			<div class="dc-dialog-summary">
				<div class="dc-dialog-stat"><div class="k">${__("Attendance")}</div><div class="v">${summary.attendance_days || 0}</div></div>
				<div class="dc-dialog-stat"><div class="k">${__("Expected")}</div><div class="v">${summary.expected_days || 0}</div></div>
				<div class="dc-dialog-stat"><div class="k">${__("Coverage")}</div><div class="v">${frappe.utils.escape_html(summary.coverage || "—")}</div></div>
				<div class="dc-dialog-stat"><div class="k">${__("Flags")}</div><div class="v" style="font-weight:500">${flags}</div></div>
			</div>
			${actions}
			<div class="dc-section-label">${__("Salary Slips")}</div>
			${slips_html}
			<div class="dc-section-label">${__("Attendance")} (${(d.attendance || []).length})</div>
			<div class="dc-att-list">${att_html}</div>
		</div>
	`;
}

function bind_dialog_actions($body, $main, state, dialog, d, label) {
	const summary = d.summary || {};

	$body.find(".dc-cancel-slip").on("click", function () {
		const name = $(this).data("name");
		frappe.confirm(__("Cancel salary slip {0}?", [name]), () => {
			frappe.call({
				method: "saral_hr.saral_hr.page.data_cleansing.data_cleansing.cancel_salary_slip",
				args: { name },
				callback() {
					frappe.show_alert({ message: __("Cancelled"), indicator: "green" });
					reload_after_mutate($main, state, dialog, summary.year, summary.month);
				},
			});
		});
	});

	$body.find(".dc-del-slip").on("click", function () {
		const name = $(this).data("name");
		frappe.confirm(__("Delete salary slip {0}? This cannot be undone.", [name]), () => {
			frappe.call({
				method: "saral_hr.saral_hr.page.data_cleansing.data_cleansing.delete_salary_slip",
				args: { name },
				callback() {
					frappe.show_alert({ message: __("Deleted"), indicator: "green" });
					reload_after_mutate($main, state, dialog, summary.year, summary.month);
				},
			});
		});
	});

	$body.find(".dc-del-month").on("click", () => {
		const n = (d.attendance || []).length;
		frappe.confirm(__("Delete {0} attendance row(s) for {1}?", [n, label]), () => {
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
					reload_after_mutate($main, state, dialog, summary.year, summary.month);
				},
			});
		});
	});

	$body.find(".dc-del-selected").on("click", () => {
		const names = $body.find(".dc-att-cb:checked").map(function () { return this.value; }).get();
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
					reload_after_mutate($main, state, dialog, summary.year, summary.month);
				},
			});
		});
	});
}

function reload_after_mutate($main, state, dialog, year, month) {
	load_matrix($main, state, () => {
		if (!(year && month)) {
			if (dialog) dialog.hide();
			return;
		}
		frappe.call({
			method: "saral_hr.saral_hr.page.data_cleansing.data_cleansing.get_month_detail",
			args: { employee: state.matrix.employee, year, month },
			callback(r) {
				state.detail = r.message;
				if (!state.detail || (!(state.detail.attendance || []).length && !(state.detail.slips || []).length)) {
					if (dialog) dialog.hide();
					frappe.show_alert({ message: __("Month cleared"), indicator: "blue" });
					return;
				}
				show_month_dialog($main, state);
			},
		});
	});
}
