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
		check_salary_slip_lock(frm);
		check_leave_allocation(frm);
	},

	employee(frm) {
		check_salary_slip_lock(frm);
		check_leave_allocation(frm);
		check_holiday_status(frm);        // ✅ ADD
	},

	attendance_date(frm) {
		check_salary_slip_lock(frm);
		check_leave_allocation(frm);
		check_holiday_status(frm);        // ✅ ADD
	},

	status(frm) {
		toggle_half_day_fields(frm);

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

// ── Leave Allocation Guard ────────────────────────────────────────────────────

var LEAVE_STATUSES = ["Earned Leave", "Casual Leave", "Comp Off"];

function check_leave_allocation(frm) {
	if (!frm.doc.employee || !frm.doc.attendance_date) {
		set_leave_options_enabled(frm, true);
		return;
	}

	frappe.db.get_value(
		"Leave Allocation",
		{
			employee:  frm.doc.employee,
			from_date: ["<=", frm.doc.attendance_date],
			to_date:   [">=", frm.doc.attendance_date],
			docstatus: ["<", 2],
		},
		"name",
		function (r) {
			var has_alloc = !!(r && r.name);
			set_leave_options_enabled(frm, has_alloc);

			if (!has_alloc) {
				if (LEAVE_STATUSES.includes(frm.doc.status)) {
					frm.set_value("status", "");
					frappe.show_alert({
						message: __("No active Leave Allocation found for this date. Earned Leave, Casual Leave, and Comp Off have been disabled."),
						indicator: "orange"
					});
				}
				if (LEAVE_STATUSES.includes(frm.doc.custom_first_half)) {
					frm.set_value("custom_first_half", "");
				}
				if (LEAVE_STATUSES.includes(frm.doc.custom_second_half)) {
					frm.set_value("custom_second_half", "");
				}
			}
		}
	);
}

function set_leave_options_enabled(frm, enabled) {
	var full_status_options = [
		"",
		"Present",
		"Earned Comp Off",
		"On Tour",
		"Absent",
		"Half Day",
		"Holiday",
		"Weekly Off",
		"LWP",
		"Earned Leave",
		"Casual Leave",
		"Comp Off",
	];

	var half_options = [
		"",
		"Present",
		"On Tour",
		"Earned Comp Off",
		"Absent",
		"Earned Leave",
		"Casual Leave",
		"Comp Off",
		"LWP",
	];

	var filtered_full = enabled
		? full_status_options
		: full_status_options.filter(function (o) { return !LEAVE_STATUSES.includes(o); });

	var filtered_half = enabled
		? half_options
		: half_options.filter(function (o) { return !LEAVE_STATUSES.includes(o); });

	frm.set_df_property("status",              "options", filtered_full.join("\n"));
	frm.set_df_property("custom_first_half",   "options", filtered_half.join("\n"));
	frm.set_df_property("custom_second_half",  "options", filtered_half.join("\n"));

	frm.refresh_field("status");
	frm.refresh_field("custom_first_half");
	frm.refresh_field("custom_second_half");
}


// ── Salary Slip Lock ──────────────────────────────────────────────────────────

function check_salary_slip_lock(frm) {
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

	frappe.db.get_value(
		"Salary Slip",
		{ employee: frm.doc.employee, start_date: month_start, docstatus: 1 },
		"name",
		function (submitted) {
			if (submitted && submitted.name) {
				lock_form_submitted(frm, submitted.name, month_label);
				return;
			}

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

function lock_form_submitted(frm, slip_name, month_label) {
	frm.fields.forEach(function (field) {
		frm.set_df_property(field.df.fieldname, "read_only", 1);
	});
	frm.disable_save();

	var slip_url = "/app/salary-slip/" + encodeURIComponent(slip_name);

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

function show_draft_warning(frm, slip_name, month_label) {
	unlock_form(frm);

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

function toggle_half_day_fields(frm) {
	var is_half = frm.doc.status === "Half Day";
	frm.toggle_display("half_day_section",   is_half);
	frm.toggle_display("custom_first_half",  is_half);
	frm.toggle_display("custom_second_half", is_half);
}

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


// ── Holiday Auto Check ────────────────────────────────────────────────────────  ✅ NEW

function check_holiday_status(frm) {
	if (!frm.doc.employee || !frm.doc.attendance_date) return;

	frappe.call({
		method: "saral_hr.utils.holiday_utils.check_is_holiday",
		args: {
			employee: frm.doc.employee,
			attendance_date: frm.doc.attendance_date
		},
		callback: function(r) {
			if (r.message) {
				frm.set_value("status", "Holiday");
				frappe.show_alert({
					message: __("Holiday: ") + r.message,
					indicator: "orange"
				}, 5);
			}
		}
	});
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