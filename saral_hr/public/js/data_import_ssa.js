// Overlay for SSA Excel import logs stored as Data Import records.
// Does not change the Data Import DocType.

function _ssaExcelImportOptions(frm) {
	try {
		const opts = JSON.parse(frm.doc.template_options || "{}");
		return opts && opts.ssa_excel_import ? opts : null;
	} catch (e) {
		return null;
	}
}

function _wrapSsaDataImportHandlers(frm) {
	if (!frappe.ui.form._ssa_excel_import_wrapped) {
		frappe.ui.form._ssa_excel_import_wrapped = true;

		const wrap = (eventName, ssaHandler) => {
			const list = frappe.ui.form.get_event_handler_list("Data Import", eventName);
			for (let i = 0; i < list.length; i++) {
				const orig = list[i];
				list[i] = function (form, cdt, cdn) {
					if (form && _ssaExcelImportOptions(form)) {
						return ssaHandler(form);
					}
					return orig(form, cdt, cdn);
				};
			}
		};

		wrap("import_file", (form) => _show_ssa_excel_preview(form));
		wrap("start_import", () => {
			frappe.msgprint(
				__(
					"This log is from Salary Structure Assignment Import. Use Import on the SSA list to import again."
				)
			);
		});
		wrap("download_template", (form) => {
			const opts = _ssaExcelImportOptions(form);
			if (opts && opts.salary_structure) {
				open_url_post(
					"/api/method/saral_hr.saral_hr.doctype.salary_structure_assignment.ssa_excel_import.download_ssa_import_template",
					{ salary_structure: opts.salary_structure }
				);
			}
		});
		wrap("export_errored_rows", (form) => {
			open_url_post(
				"/api/method/saral_hr.saral_hr.doctype.salary_structure_assignment.ssa_excel_import.download_ssa_import_errored_rows",
				{ data_import: form.doc.name }
			);
		});
		wrap("update_primary_action", (form) => {
			if (form.is_dirty()) {
				form.enable_save();
				return;
			}
			form.disable_save();
			form.page.clear_primary_action();
		});
	}

	[
		"import_file",
		"start_import",
		"download_template",
		"export_errored_rows",
		"update_primary_action",
	].forEach((name) => {
		const list = frappe.ui.form.get_event_handler_list("Data Import", name);
		if (list.length) {
			frm.events[name] = list[list.length - 1];
		}
	});
}

frappe.ui.form.on("Data Import", {
	setup(frm) {
		_wrapSsaDataImportHandlers(frm);
	},

	refresh(frm) {
		if (!_ssaExcelImportOptions(frm)) {
			return;
		}
		frm.page.clear_primary_action();
		if (frm.doc.status === "Error") {
			frm.add_custom_button(__("Export Errored Rows"), () =>
				frm.trigger("export_errored_rows")
			);
			frm.add_custom_button(__("Go to {0} List", [__("Salary Structure Assignment")]), () =>
				frappe.set_route("List", "Salary Structure Assignment")
			);
		}
	},
});

function _ssaWarningColumns(cols) {
	const frappeCols = [{ header_title: __("Sr. No") }];
	(cols || []).forEach((c) => {
		frappeCols.push({
			header_title: typeof c === "object" ? c.header_title || c.label : c,
		});
	});
	while (frappeCols.length < 40) {
		frappeCols.push({ header_title: "" });
	}
	return frappeCols;
}

function _show_ssa_excel_preview(frm) {
	frm.toggle_display("section_import_preview", true);
	frm.events.show_import_warnings(frm, { columns: _ssaWarningColumns([]), warnings: [] });
	const wrap = frm.get_field("import_preview").$wrapper;
	wrap.html(`<span class="text-muted">${__("Loading import file...")}</span>`);
	frappe.call({
		method:
			"saral_hr.saral_hr.doctype.salary_structure_assignment.ssa_excel_import.get_ssa_data_import_preview",
		args: { data_import: frm.doc.name },
		callback(r) {
			const data = r.message || {};
			const cols = data.columns || [];
			const rows = data.rows || [];
			frm.events.show_import_warnings(frm, { columns: _ssaWarningColumns(cols), warnings: [] });
			let table = "";
			if (data.salary_structure) {
				table += `<p class="text-muted">${__("Salary Structure")}: <b>${frappe.utils.escape_html(
					cstr(data.salary_structure)
				)}</b></p>`;
			}
			table += '<div class="table-responsive"><table class="table table-bordered table-condensed">';
			table += "<thead><tr>";
			cols.forEach((c) => {
				const label = typeof c === "object" ? c.label : c;
				const mapped = typeof c === "object" ? c.mapped : true;
				const maps_to = typeof c === "object" ? c.maps_to : "";
				const dot = mapped
					? '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#98d85b;margin-right:6px;vertical-align:middle;"></span>'
					: '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#ff5858;margin-right:6px;vertical-align:middle;"></span>';
				const title = maps_to
					? ` title="${frappe.utils.escape_html("→ " + maps_to)}"`
					: "";
				table += `<th${title}>${dot}${frappe.utils.escape_html(cstr(label))}</th>`;
			});
			table += "</tr></thead><tbody>";
			rows.forEach((row) => {
				table += "<tr>";
				cols.forEach((_, i) => {
					table += `<td>${frappe.utils.escape_html(cstr(row[i] == null ? "" : row[i]))}</td>`;
				});
				table += "</tr>";
			});
			table += "</tbody></table></div>";
			wrap.html(table);
		},
		error() {
			frm.events.show_import_warnings(frm, { columns: _ssaWarningColumns([]), warnings: [] });
			wrap.html(`<span class="text-muted">${__("Could not load preview.")}</span>`);
		},
	});
}

function cstr(v) {
	return v == null ? "" : String(v);
}
