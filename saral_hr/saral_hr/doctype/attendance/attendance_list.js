frappe.listview_settings["Attendance"] = {

	onload(list_view) {
		list_view.page.add_inner_button(__('Mark Attendance'), function () {
			const url = "app/mark-attendance";
			window.location.href = frappe.urllib.get_full_url(url);
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