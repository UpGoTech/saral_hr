// Print and PDF use window.open. When the browser blocks that, open the
// same URL without a popup so the desk does not ask to enable pop-ups.
(function () {
	function hidden_frame(url) {
		let frame = document.getElementById("saral-print-frame");
		if (!frame) {
			frame = document.createElement("iframe");
			frame.id = "saral-print-frame";
			frame.setAttribute("aria-hidden", "true");
			frame.style.cssText = "position:fixed;width:0;height:0;border:0;visibility:hidden";
			document.body.appendChild(frame);
		}
		frame.src = url;
	}

	function open_url(url, printit) {
		const popup = window.open(url, "_blank");
		if (popup) {
			return;
		}
		if (printit || url.indexOf("download_pdf") !== -1) {
			hidden_frame(url);
			return;
		}
		window.location.href = url;
	}

	function patch() {
		const PrintView = frappe.ui && frappe.ui.form && frappe.ui.form.PrintView;
		if (!PrintView || PrintView.prototype._saral_print_open) {
			return !!PrintView;
		}
		PrintView.prototype.render_page = function (method, printit = false) {
			const url = frappe.urllib.get_full_url(
				method +
					"doctype=" +
					encodeURIComponent(this.frm.doc.doctype) +
					"&name=" +
					encodeURIComponent(this.frm.doc.name) +
					(printit ? "&trigger_print=1" : "") +
					"&format=" +
					encodeURIComponent(this.selected_format()) +
					"&no_letterhead=" +
					(this.with_letterhead() ? "0" : "1") +
					"&letterhead=" +
					encodeURIComponent(this.get_letterhead()) +
					"&settings=" +
					encodeURIComponent(JSON.stringify(this.additional_settings)) +
					(this.lang_code ? "&_lang=" + this.lang_code : "")
			);
			open_url(url, printit);
		};
		PrintView.prototype._saral_print_open = true;
		return true;
	}

	const timer = setInterval(function () {
		if (patch()) {
			clearInterval(timer);
		}
	}, 400);
})();
