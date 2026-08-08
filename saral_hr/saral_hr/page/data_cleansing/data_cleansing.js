frappe.pages["data-cleansing"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Data Cleansing"),
		single_column: true,
	});
};

frappe.pages["data-cleansing"].on_page_show = function (wrapper) {
	const $main = $(wrapper).find(".layout-main-section");
	$main.html(`
		<div class="text-muted" style="padding: 1.5rem;">
			<p>${__("Employee attendance & salary audit / cleanse.")}</p>
			<p>${__("Implementation in progress — see specs/007-data-cleansing.md.")}</p>
		</div>
	`);
};
