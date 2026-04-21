// Copyright (c) 2026, sj and contributors
// For license information, please see license.txt

frappe.ui.form.on("Attendance", {

	refresh(frm) {
		if (frm.doc.__islocal && !frm.doc.attendance_date) {
			frm.set_value("attendance_date", frappe.datetime.get_today());
		}

		frm.set_query("employee", () => {
			return { filters: { is_active: 1 } };
		});

		toggle_half_day_fields(frm);

		// Check salary slip lock whenever the form is refreshed
		// (covers both new records and opening existing ones)
		check_salary_slip_lock(frm);
	},

	employee(frm) {
		check_salary_slip_lock(frm);
	},

	attendance_date(frm) {
		check_salary_slip_lock(frm);
	},

	status(frm) {
		toggle_half_day_fields(frm);

		// Clear half-day fields when switching away from Half Day
		if (frm.doc.status !== "Half Day") {
			frm.set_value("custom_first_half",  "");
			frm.set_value("custom_second_half", "");
		}
	},

	custom_first_half(frm) {
		validate_half_combination(frm);
	},

	custom_second_half(frm) {
		validate_half_combination(frm);
	},
});

// ── Salary Slip Lock ──────────────────────────────────────────────────────────

/**
 * Checks whether a submitted (or draft) salary slip exists for the
 * employee + month of this attendance record.
 *
 * - Submitted slip  → full read-only lock with red Frappe alert banner
 * - Draft slip      → orange Frappe alert banner (editable, but user is warned)
 */
function check_salary_slip_lock(frm) {
	// Remove any previously injected banners so we don't stack them
	frm.dashboard.clear_headline();

	if (!frm.doc.employee || !frm.doc.attendance_date) {
		unlock_form(frm);
		return;
	}

	var att_date    = frappe.datetime.str_to_obj(frm.doc.attendance_date);
	var month_start = frappe.datetime.obj_to_str(
		new Date(att_date.getFullYear(), att_date.getMonth(), 1)
	);
	var month_label = att_date.toLocaleDateString("en-US", { month: "long", year: "numeric" });

	// Check submitted slip first
	frappe.db.get_value(
		"Salary Slip",
		{ employee: frm.doc.employee, start_date: month_start, docstatus: 1 },
		"name",
		function (submitted) {
			if (submitted && submitted.name) {
				lock_form_submitted(frm, submitted.name, month_label);
				return;
			}

			// No submitted slip — check for a draft slip
			frappe.db.get_value(
				"Salary Slip",
				{ employee: frm.doc.employee, start_date: month_start, docstatus: 0 },
				"name",
				function (draft) {
					if (draft && draft.name) {
						show_draft_warning(frm, draft.name, month_label);
					} else {
						unlock_form(frm);
					}
				}
			);
		}
	);
}

/**
 * Make the entire form read-only and show a native Frappe red locked banner.
 */
function lock_form_submitted(frm, slip_name, month_label) {
	// Make every field read-only
	frm.fields.forEach(function (field) {
		frm.set_df_property(field.df.fieldname, "read_only", 1);
	});
	frm.disable_save();

	var slip_url = "/app/salary-slip/" + encodeURIComponent(slip_name);

	// Use Frappe's native dashboard headline alert (renders in the standard
	// blue/red/orange indicator bar at the top of the form body)
	frm.dashboard.set_headline_alert(
		`<div class="row">
			<div class="col d-flex align-items-center" style="gap:8px;">
				<span class="indicator-pill red no-indicator-dot" style="flex-shrink:0;">
					<i class="fa fa-lock" style="margin-right:4px;"></i>${__("Locked")}
				</span>
				<span style="font-size:var(--text-sm); color:var(--text-color);">
					${__("Salary Slip")}
					<a href="${slip_url}" class="font-weight-bold" target="_blank"
						style="color:var(--red-600);">${slip_name}</a>
					${__("has been")} <strong>${__("submitted")}</strong>
					${__("for")} ${month_label}.
					${__("Cancel the salary slip first to modify attendance.")}
				</span>
			</div>
		</div>`,
		"red"
	);
}

/**
 * Show a native Frappe orange warning banner but keep the form editable.
 */
function show_draft_warning(frm, slip_name, month_label) {
	unlock_form(frm); // ensure fields are not locked from a prior check

	var slip_url = "/app/salary-slip/" + encodeURIComponent(slip_name);

	frm.dashboard.set_headline_alert(
		`<div class="row">
			<div class="col d-flex align-items-center" style="gap:8px;">
				<span class="indicator-pill orange no-indicator-dot" style="flex-shrink:0;">
					<i class="fa fa-exclamation-triangle" style="margin-right:4px;"></i>${__("Draft Slip")}
				</span>
				<span style="font-size:var(--text-sm); color:var(--text-color);">
					${__("Salary Slip")}
					<a href="${slip_url}" class="font-weight-bold" target="_blank"
						style="color:var(--orange-600);">${slip_name}</a>
					${__("is in")} <strong>${__("Draft")}</strong>
					${__("for")} ${month_label}.
					${__("Attendance changes will not reflect until the salary slip is regenerated.")}
				</span>
			</div>
		</div>`,
		"orange"
	);
}

/**
 * Restore all fields to their natural editable state.
 */
function unlock_form(frm) {
	frm.fields.forEach(function (field) {
		var original_ro = field.df.read_only_depends_on || field.df.__original_read_only;
		if (original_ro === undefined) {
			field.df.__original_read_only = field.df.read_only || 0;
		}
		frm.set_df_property(
			field.df.fieldname,
			"read_only",
			field.df.__original_read_only || 0
		);
	});
	frm.enable_save();
}


// ── Half Day helpers ──────────────────────────────────────────────────────────

/**
 * Show the half-day section and fields only when status === "Half Day".
 */
function toggle_half_day_fields(frm) {
	var is_half = frm.doc.status === "Half Day";
	frm.toggle_display("half_day_section",   is_half);
	frm.toggle_display("custom_first_half",  is_half);
	frm.toggle_display("custom_second_half", is_half);
}

/**
 * Client-side hint: if both halves are the same status,
 * suggest using a full-day status.
 */
function validate_half_combination(frm) {
	var fh = frm.doc.custom_first_half  || "";
	var sh = frm.doc.custom_second_half || "";

	if (!fh || !sh) return;

	if (fh === sh) {
		frappe.show_alert({
			message: __("Both halves are <b>{0}</b>. Consider using a full-day status.", [fh]),
			indicator: "orange"
		});
	}
}


// ── List view indicators ──────────────────────────────────────────────────────
frappe.listview_settings["Attendance"] = {

	onload(list_view) {
		list_view.page.add_inner_button(__("Mark Attendance"), function () {
			window.location.href = frappe.urllib.get_full_url("app/mark-attendance");
		});
	},

	get_indicator: function (doc) {
		const map = {
			"Present":          [__("Present"),          "green",       "status,=,Present"],
			"Earned Comp Off":  [__("Earned Comp Off"),  "green",       "status,=,Earned Comp Off"],
			"On Tour":          [__("On Tour"),          "green",       "status,=,On Tour"],
			"Absent":           [__("Absent"),           "red",         "status,=,Absent"],
			"Half Day":         [__("Half Day"),         "yellow",      "status,=,Half Day"],
			"Holiday":          [__("Holiday"),          "orange",      "status,=,Holiday"],
			"Weekly Off":       [__("Weekly Off"),       "blue",        "status,=,Weekly Off"],
			"LWP":              [__("LWP"),              "purple",      "status,=,LWP"],
			"Earned Leave":     [__("Earned Leave"),     "light-blue",  "status,=,Earned Leave"],
			"Casual Leave":     [__("Casual Leave"),     "cyan",        "status,=,Casual Leave"],
			"Comp Off":         [__("Comp Off"),         "purple",      "status,=,Comp Off"],
			"On Leave":         [__("On Leave"),         "grey",        "status,=,On Leave"],
			"Work From Home":   [__("WFH"),              "green",       "status,=,Work From Home"],
		};
		return map[doc.status] || [doc.status, "grey", "status,=," + doc.status];
	}
};