// Copyright (c) 2026, sj and contributors
// For license information, please see license.txt

frappe.listview_settings["Salary Structure Assignment"] = {
	onload(listview) {
		listview.page.add_inner_button(__("Import"), () => show_ssa_import_dialog(listview));
	},
};

function show_ssa_import_dialog(listview) {
	const dialog = new frappe.ui.Dialog({
		title: __("Import Salary Structure Assignments"),
		size: "large",
		fields: [
			{
				fieldname: "salary_structure",
				fieldtype: "Link",
				label: __("Salary Structure"),
				options: "Salary Structure",
				reqd: 1,
				get_query: () => ({ filters: { is_active: "Yes" } }),
				onchange() {
					load_ssa_mapping_preview(dialog);
				},
			},
			{
				fieldname: "excel_file",
				fieldtype: "Attach",
				label: __("Excel File"),
				reqd: 1,
				onchange() {
					load_ssa_mapping_preview(dialog);
				},
			},
			{
				fieldname: "mapping_preview",
				fieldtype: "HTML",
			},
		],
		secondary_action_label: __("Download Template"),
		secondary_action() {
			const salary_structure = dialog.get_value("salary_structure");
			if (!salary_structure) {
				frappe.msgprint(__("Select Salary Structure first."));
				return;
			}
			open_url_post(
				"/api/method/saral_hr.saral_hr.doctype.salary_structure_assignment.ssa_excel_import.download_ssa_import_template",
				{ salary_structure }
			);
		},
		primary_action_label: __("Import"),
		primary_action(values) {
			if (!values.salary_structure || !values.excel_file) {
				frappe.msgprint(__("Select Salary Structure and attach the Excel file."));
				return;
			}
			const missing = ssa_unmapped_required_fields(dialog);
			if (missing.length) {
				frappe.msgprint({
					title: __("Map Columns"),
					indicator: "red",
					message:
						__("Map each field before Import.") +
						`<ul>${missing.map((n) => `<li>${frappe.utils.escape_html(n)}</li>`).join("")}</ul>`,
				});
				return;
			}
			dialog.hide();
			frappe.call({
				method:
					"saral_hr.saral_hr.doctype.salary_structure_assignment.ssa_excel_import.import_ssa_excel",
				args: {
					salary_structure: values.salary_structure,
					file_url: values.excel_file,
					column_map: dialog.ssa_column_map || {},
				},
				freeze: true,
				freeze_message: __("Importing SSAs…"),
				callback(r) {
					show_ssa_import_result(r.message || {});
					listview.refresh();
				},
			});
		},
	});
	dialog.ssa_column_map = {};
	dialog.show();
}

function ssa_import_log_link(data_import) {
	if (!data_import) {
		return "";
	}
	const href = `/app/data-import/${encodeURIComponent(data_import)}`;
	return `<p><a href="${href}">${__("Open import log")}</a></p>`;
}

function show_ssa_import_result(msg) {
	const created = (msg && msg.created) || [];
	const errors = (msg && msg.errors) || [];
	const log_link = ssa_import_log_link(msg && msg.data_import);
	let indicator = "green";
	let html = "";

	if (created.length && !errors.length) {
		html = `<p>${__("Import completed successfully.")}</p>
			<p>${__("{0} Salary Structure Assignment(s) created.", [created.length])}</p>`;
	} else if (created.length && errors.length) {
		indicator = "orange";
		html = `<p>${__("Import completed with errors.")}</p>
			<p>${__("{0} created, {1} failed.", [created.length, errors.length])}</p>
			<p>${__("Open the import log to see which rows failed.")}</p>${log_link}`;
		if (!log_link && errors.length) {
			html += `<ul>${errors
				.map((e) => `<li>${frappe.utils.escape_html(e)}</li>`)
				.join("")}</ul>`;
		}
	} else {
		indicator = "red";
		html = `<p>${__("Import failed.")}</p>
			<p>${__("Go to the import log to see the error details.")}</p>${log_link}`;
		if (!log_link && errors.length) {
			html += `<ul>${errors
				.map((e) => `<li>${frappe.utils.escape_html(e)}</li>`)
				.join("")}</ul>`;
		}
	}

	frappe.msgprint({
		title: __("SSA Import"),
		indicator,
		message: html,
	});
}

function load_ssa_mapping_preview(dialog) {
	const wrap = dialog.get_field("mapping_preview").$wrapper;
	const salary_structure = dialog.get_value("salary_structure");
	const file_url = dialog.get_value("excel_file");
	dialog.ssa_column_map = {};
	dialog.ssa_preview = null;
	if (!salary_structure || !file_url) {
		wrap.html("");
		return;
	}
	wrap.html(`<span class="text-muted">${__("Loading import file...")}</span>`);
	frappe.call({
		method:
			"saral_hr.saral_hr.doctype.salary_structure_assignment.ssa_excel_import.preview_ssa_excel",
		args: { salary_structure, file_url },
		callback(r) {
			const data = r.message || {};
			dialog.ssa_preview = data;
			const split = ssa_split_exact_matches(data.fields || [], data.columns || []);
			dialog.ssa_column_map = Object.assign({}, split.auto_map);
			let html = "";
			if (split.unmatched_fields.length) {
				html += `<button type="button" class="btn btn-sm btn-default ssa-open-mapper">${__(
					"Map Columns"
				)}</button>`;
			}
			if (split.matched_labels.length) {
				html += `<div class="text-muted" style="margin-top:8px;">${__(
					"Already matched"
				)}: <b>${frappe.utils.escape_html(split.matched_labels.join(", "))}</b></div>`;
			}
			wrap.html(html);
			wrap.find(".ssa-open-mapper").on("click", () => show_ssa_map_columns_dialog(dialog, file_url));
			if (split.unmatched_fields.length) {
				show_ssa_map_columns_dialog(dialog, file_url);
			}
		},
		error() {
			wrap.html(`<span class="text-muted">${__("Could not load preview.")}</span>`);
		},
	});
}

function show_ssa_map_columns_dialog(parent, file_url) {
	const data = parent.ssa_preview || {};
	const cols = data.columns || [];
	const fields = data.fields || [];
	const split = ssa_split_exact_matches(fields, cols);
	if (!split.unmatched_fields.length) {
		frappe.show_alert({
			message: __("All columns are already matched."),
			indicator: "green",
		});
		return;
	}
	const options = [
		{
			label: __("Don't Import"),
			value: "Don't Import",
		},
	].concat(
		fields.map((f) => ({
			label: __(f.label),
			value: f.value,
			description: f.fieldname,
		}))
	);

	const filename = ssa_file_name(file_url || parent.get_value("excel_file"));
	const parts = [frappe.utils.escape_html(filename).bold(), __("Salary Structure Assignment").bold()];
	let mapper_fields = [
		{
			fieldtype: "HTML",
			fieldname: "heading",
			options: `
					<div class="margin-top text-muted">
					${__("Map columns from {0} to fields in {1}", parts)}
					</div>
				`,
		},
		{
			fieldtype: "Section Break",
		},
	];

	split.unmatched_fields.forEach((f, i) => {
		mapper_fields.push(
			{
				label: "",
				fieldtype: "Data",
				default: f.label,
				fieldname: `Column ${i}`,
				read_only: 1,
			},
			{
				fieldtype: "Column Break",
			},
			{
				fieldtype: "Autocomplete",
				fieldname: i,
				label: "",
				max_items: Infinity,
				options,
				default: f.value,
			},
			{
				fieldtype: "Section Break",
			}
		);
	});

	if (parent.ssa_mapper) {
		parent.ssa_mapper.hide();
	}

	ssa_ensure_map_columns_style();

	const mapper = new frappe.ui.Dialog({
		title: __("Map Columns"),
		fields: mapper_fields,
		primary_action(values) {
			const map = Object.assign({}, split.auto_map);
			split.unmatched_fields.forEach((left_field, i) => {
				const selected = values[i] || values[String(i)];
				if (!selected || selected === "Don't Import") {
					return;
				}
				const excel_idx = ssa_excel_idx_for_field(cols, selected, fields);
				if (excel_idx !== -1) {
					map[String(excel_idx)] = left_field.value;
				}
			});
			parent.ssa_column_map = map;
			mapper.hide();
		},
	});
	mapper.$body.addClass("map-columns");
	parent.ssa_mapper = mapper;
	mapper.show();
	ssa_bind_map_column_autocomplete(mapper, split.unmatched_fields, options);
}

function ssa_ensure_map_columns_style() {
	if (document.getElementById("ssa-map-columns-css")) {
		return;
	}
	const style = document.createElement("style");
	style.id = "ssa-map-columns-css";
	style.textContent = `
		.modal-body.map-columns {
			overflow: visible;
		}
		.modal-dialog:has(.map-columns) {
			max-width: 640px;
		}
		.modal-dialog:has(.map-columns) .modal-content {
			overflow: visible;
		}
		.map-columns .control-label,
		.map-columns .help-box,
		.map-columns .clearfix {
			display: none;
		}
		.map-columns .frappe-control {
			margin-bottom: 0;
			position: relative;
		}
		.map-columns .form-section {
			padding: 10px 8px !important;
			border-top: none;
		}
		.map-columns .form-section:not(:first-child) {
			border-top: 1px solid var(--border-color) !important;
		}
		.map-columns .form-column:first-child {
			padding-right: 20px;
		}
		.map-columns .form-column:last-child {
			padding-left: 20px;
		}
		.map-columns .awesomplete {
			display: block;
			position: relative;
		}
		.map-columns .awesomplete > ul {
			z-index: 20;
			min-width: 100%;
		}
	`;
	document.head.appendChild(style);
}

function ssa_bind_map_column_autocomplete(mapper, unmatched_fields, options) {
	(unmatched_fields || []).forEach((f, i) => {
		const field = mapper.get_field(i) || mapper.get_field(String(i));
		if (!field || !field.$input) {
			return;
		}
		if (field.set_data) {
			field.set_data(options);
		}
		if (field.set_value) {
			field.set_value(f.value);
		}
		const open_list = () => {
			if (!field.awesomplete) {
				return;
			}
			field.awesomplete.minChars = 0;
			field.awesomplete.evaluate();
		};
		field.$input.on("focus input keyup", open_list);
	});
}

function ssa_excel_idx_for_field(cols, field_value, fields) {
	const field = (fields || []).find((f) => f.value === field_value);
	for (let i = 0; i < (cols || []).length; i++) {
		const col = cols[i];
		if (col && col.value === field_value) {
			return i;
		}
		if (field && ssa_excel_exact_name_match(col, field)) {
			return i;
		}
	}
	return -1;
}

function ssa_split_exact_matches(fields, cols) {
	const reserved = {};
	const auto_map = {};
	const matched_labels = [];
	(fields || []).forEach((f) => {
		let exact_idx = -1;
		(cols || []).forEach((c, idx) => {
			if (exact_idx !== -1 || reserved[idx]) {
				return;
			}
			if (ssa_excel_exact_name_match(c, f)) {
				exact_idx = idx;
			}
		});
		if (exact_idx !== -1) {
			reserved[exact_idx] = true;
			auto_map[String(exact_idx)] = f.value;
			matched_labels.push(f.label);
		}
	});
	const unmatched_fields = (fields || []).filter(
		(f) => Object.values(auto_map).indexOf(f.value) === -1
	);
	return { auto_map, matched_labels, unmatched_fields };
}

function ssa_file_name(file_url) {
	if (!file_url) {
		return "";
	}
	try {
		return decodeURIComponent(String(file_url).split("/").pop() || file_url);
	} catch (e) {
		return String(file_url).split("/").pop() || file_url;
	}
}

function ssa_unmapped_required_fields(dialog) {
	const mapped = Object.values(dialog.ssa_column_map || {}).filter(Boolean);
	const required = [
		{ value: "meta:employee_name", label: __("Employee Name") },
		{ value: "meta:from_date", label: __("From Date") },
		{ value: "meta:to_date", label: __("To Date") },
	];
	return required.filter((f) => mapped.indexOf(f.value) === -1).map((f) => f.label);
}

function ssa_norm_key(value) {
	return String(value || "")
		.trim()
		.toLowerCase()
		.replace(/\s+/g, " ");
}

function ssa_col_header(col) {
	if (col == null) {
		return "";
	}
	if (typeof col !== "object") {
		return String(col).trim();
	}
	return String(col.label || col.header_title || "").trim();
}

function ssa_excel_exact_name_match(col, field) {
	const header = ssa_norm_key(ssa_col_header(col));
	if (!header || !field) {
		return false;
	}
	return header === ssa_norm_key(field.label) || header === ssa_norm_key(field.fieldname);
}
