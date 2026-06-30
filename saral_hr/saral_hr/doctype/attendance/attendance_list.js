// Copyright (c) 2026, sj and contributors
// For license information, please see license.txt

frappe.listview_settings["Attendance"] = {

	onload(list_view) {
		list_view.page.add_inner_button(__('Mark Attendance'), function () {
			const url = "app/mark-attendance";
			window.location.href = frappe.urllib.get_full_url(url);
		});

		// ✅ NEW: Bulk date range attendance button
		list_view.page.add_inner_button(__("Apply Leave / Status"), function () {
			show_bulk_attendance_dialog(list_view);
		});
	},

	get_indicator: function (doc) {
		if (doc.status === "Present") {
			return [__("Present"), "green", "status,=,Present"];
		}
		if (doc.status === "Earned Comp Off") {
			return [__("Earned Comp Off"), "green", "status,=,Earned Comp Off"];
		}
		if (doc.status === "On Tour") {
			return [__("On Tour"), "green", "status,=,On Tour"];
		}
		if (doc.status === "Absent") {
			return [__("Absent"), "red", "status,=,Absent"];
		}
		if (doc.status === "Half Day") {
			return [__("Half Day"), "yellow", "status,=,Half Day"];
		}
		if (doc.status === "Holiday") {
			return [__("Holiday"), "orange", "status,=,Holiday"];
		}
		if (doc.status === "Weekly Off") {
			return [__("Weekly Off"), "blue", "status,=,Weekly Off"];
		}
		if (doc.status === "LWP") {
			return [__("LWP"), "purple", "status,=,LWP"];
		}
		if (doc.status === "Earned Leave") {
			return [__("Earned Leave"), "light-blue", "status,=,Earned Leave"];
		}
		if (doc.status === "Casual Leave") {
			return [__("Casual Leave"), "cyan", "status,=,Casual Leave"];
		}
		if (doc.status === "On Leave") {
			return [__("On Leave"), "grey", "status,=,On Leave"];
		}
		if (doc.status === "Work From Home") {
			return [__("WFH"), "green", "status,=,Work From Home"];
		}
	}
};


// ── Bulk Date Range Attendance ────────────────────────────────────────────────

function show_bulk_attendance_dialog(list_view) {
	let d = new frappe.ui.Dialog({
		title: __("Apply Attendance for Date Range"),
		fields: [
			{
				fieldtype: "Link", fieldname: "employee", label: "Employee",
				options: "Employee", reqd: 1,
				get_query: () => ({})
			},
			{ fieldtype: "Column Break" },
			{
				fieldtype: "Select", fieldname: "status", label: "Status", reqd: 1,
				options: "\nPresent\nAbsent\nCasual Leave\nEarned Leave\nComp Off\nLWP\nOn Tour\nHalf Day\nHoliday\nWeekly Off"
			},
			{ fieldtype: "Section Break" },
			{
				fieldtype: "Date", fieldname: "from_date", label: "From Date",
				reqd: 1, default: frappe.datetime.get_today()
			},
			{ fieldtype: "Column Break" },
			{
				fieldtype: "Date", fieldname: "to_date", label: "To Date",
				reqd: 1, default: frappe.datetime.get_today()
			},
		],
		primary_action_label: __("Apply"),
		primary_action(values) {
			if (frappe.datetime.str_to_obj(values.to_date) < frappe.datetime.str_to_obj(values.from_date)) {
				frappe.msgprint(__("To Date cannot be before From Date."));
				return;
			}
			frappe.confirm(
				__("Apply <b>{0}</b> for <b>{1}</b> from <b>{2}</b> to <b>{3}</b>?", [
					values.status, values.employee, values.from_date, values.to_date
				]),
				() => {
					d.hide();
					frappe.call({
						method: "saral_hr.saral_hr.doctype.attendance.attendance.bulk_apply_attendance",
						args: {
							employee:  values.employee,
							from_date: values.from_date,
							to_date:   values.to_date,
							status:    values.status,
						},
						freeze: true,
						freeze_message: __("Creating attendance records..."),
						callback(r) {
							if (r.message) {
								frappe.msgprint({ title: __("Done"), message: r.message, indicator: "green" });
								list_view.refresh();
							}
						}
					});
				}
			);
		}
	});
	d.show();
}