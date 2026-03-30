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

/**
 * Show the half-day section and fields only when status === "Half Day".
 */
function toggle_half_day_fields(frm) {
	var is_half = frm.doc.status === "Half Day";
	frm.toggle_display("half_day_section",    is_half);
	frm.toggle_display("custom_first_half",  is_half);
	frm.toggle_display("custom_second_half", is_half);
}

/**
 * Client-side hint: if both halves are the same "full present" status,
 * suggest using a full-day status.
 */
var PRESENT_LIKE = ["Present", "On Tour", "Earned Comp Off"];

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