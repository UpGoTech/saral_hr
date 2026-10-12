frappe.provide("saral_hr.period_picker");

(function () {
	const MIN = 2024;

	function max_year() {
		return new Date().getFullYear() + 1;
	}

	function clamp(value) {
		let year = parseInt(value, 10);
		if (isNaN(year)) return new Date().getFullYear();
		if (year < MIN) return MIN;
		if (year > max_year()) return max_year();
		return year;
	}

	function options(include_blank) {
		const opts = include_blank !== false ? [""] : [];
		for (let y = MIN; y <= max_year(); y++) opts.push(String(y));
		return opts;
	}

	function options_newline() {
		return options(false).join("\n");
	}

	function year_select_field(overrides) {
		return Object.assign(
			{
				fieldname: "year",
				fieldtype: "Select",
				label: __("Year"),
				reqd: 1,
				default: String(new Date().getFullYear()),
				options: options(),
			},
			overrides || {}
		);
	}

	function apply_form_year_select(frm, fieldname) {
		fieldname = fieldname || "year";
		const field = frm.fields_dict[fieldname];
		if (!field) return;
		field.df.options = options_newline();
		field.refresh();
	}

	function reset_year_if_invalid(frm, fieldname) {
		fieldname = fieldname || "year";
		const raw = frm.doc[fieldname];
		if (!raw) return;
		const y = parseInt(raw, 10);
		if (isNaN(y) || y < MIN || y > max_year()) {
			frm.set_value(fieldname, "");
			frappe.show_alert(
				{
					message: __("Year reset — select {0} or later", [MIN]),
					indicator: "orange",
				},
				5
			);
		}
	}

	saral_hr.period_picker.PERIOD_YEAR_MIN = MIN;
	saral_hr.period_picker.get_period_year_max = max_year;
	saral_hr.period_picker.clamp_period_year = clamp;
	saral_hr.period_picker.get_period_year_options = options;
	saral_hr.period_picker.get_period_year_options_newline = options_newline;
	saral_hr.period_picker.year_select_field = year_select_field;
	saral_hr.period_picker.apply_form_year_select = apply_form_year_select;
	saral_hr.period_picker.reset_year_if_invalid = reset_year_if_invalid;
})();
