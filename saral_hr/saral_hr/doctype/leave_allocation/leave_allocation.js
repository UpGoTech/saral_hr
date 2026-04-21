// Copyright (c) 2026, sj and contributors
// For license information, please see license.txt

frappe.ui.form.on("Leave Allocation", {

	refresh(frm) {
		render_all_ledgers(frm);
	},

	employee(frm) {
		if (frm.doc.employee) {
			load_all_leave_types(frm);
		}
	},

	from_date(frm) {
		if (frm.doc.employee && frm.doc.from_date) {
			load_all_leave_types(frm);
		}
	},

	leave_allocation_details_add(frm) {
		render_all_ledgers(frm);
	},

	leave_allocation_details_remove(frm) {
		render_all_ledgers(frm);
	},
});

frappe.ui.form.on("Leave Allocation Detail", {
	allocated_leaves(frm) {
		render_all_ledgers(frm);
	},
});

// ── Load All Leave Types into Child Table ────────────────────────────────────

function load_all_leave_types(frm) {
	// On a saved doc with existing rows — don't overwrite
	if (!frm.doc.__islocal && (frm.doc.leave_allocation_details || []).length > 0) {
		return;
	}

	frappe.call({
		method: "saral_hr.saral_hr.doctype.leave_allocation.leave_allocation.get_all_leave_types",
		callback(r) {
			if (!r.message) return;

			const existing = (frm.doc.leave_allocation_details || []).map(row => row.leave_type);

			r.message.forEach(lt => {
				if (!existing.includes(lt.name)) {
					let row = frm.add_child("leave_allocation_details");
					row.leave_type       = lt.name;
					row.leave_type_abbr  = lt.abbr;
					row.allocated_leaves = 0;
					row.used_leaves      = 0;
					row.remaining_leaves = 0;
				}
			});

			frm.refresh_field("leave_allocation_details");
			render_all_ledgers(frm);
		}
	});
}

// ── Render All Ledgers Horizontally ─────────────────────────────────────────

function render_all_ledgers(frm) {
	const container = frm.fields_dict["leave_ledger_html"].$wrapper;

	const employee  = frm.doc.employee;
	const from_date = frm.doc.from_date;
	const to_date   = frm.doc.to_date;
	const rows      = frm.doc.leave_allocation_details || [];

	if (!employee || !from_date || !to_date || !rows.length) {
		container.html(placeholder_html("Save the form with employee, period, and leave types to view the ledger."));
		return;
	}

	container.html(`<div style="padding:16px 0; color:var(--text-muted); font-size:13px;">Loading ledgers…</div>`);

	const promises = rows.map(row =>
		frappe.call({
			method: "saral_hr.saral_hr.doctype.leave_allocation.leave_allocation.get_leave_ledger",
			args: {
				employee,
				leave_type: row.leave_type,
				from_date,
				to_date
			}
		}).then(r => ({
			leave_type: row.leave_type,
			allocated:  row.allocated_leaves || 0,
			entries:    (r && r.message) ? r.message : []
		}))
	);

	Promise.all(promises).then(results => {
		container.html(build_all_ledgers_html(results));
	}).catch(() => {
		container.html(placeholder_html("Error loading ledgers. Please save the document first and try again."));
	});
}

// ── HTML Builders ────────────────────────────────────────────────────────────

function placeholder_html(msg) {
	return `
		<div style="
			padding: 20px 16px;
			text-align: center;
			color: var(--text-muted, #888);
			font-size: 13px;
			border: 1px dashed var(--border-color, #ddd);
			border-radius: 8px;
			margin: 8px 0;
		">${msg}</div>`;
}

function build_all_ledgers_html(results) {
	if (!results.length) return placeholder_html("No leave types found.");

	const cards = results.map(r =>
		build_single_ledger_card(r.leave_type, r.allocated, r.entries)
	).join("");

	return `
		<div style="
			display: flex;
			flex-direction: row;
			gap: 16px;
			overflow-x: auto;
			padding: 4px 2px 14px 2px;
			align-items: flex-start;
		">
			${cards}
		</div>`;
}

function build_single_ledger_card(leave_type, allocated, entries) {
	// Final balance: last entry's balance, or allocated if no entries
	let final_balance = allocated;
	if (entries.length) {
		final_balance = entries[entries.length - 1].balance;
	}

	const balance_color = final_balance > 0 ? "#1a73e8" : (final_balance < 0 ? "#c5221f" : "#888");
	const balance_bg    = final_balance > 0 ? "#e8f0fe" : (final_balance < 0 ? "#fce8e6" : "#f1f3f4");

	let rows_html = "";

	if (!entries.length) {
		// No activity — show balance row only
		rows_html = `
			<tr>
				<td colspan="6" style="
					padding: 18px 12px;
					text-align: center;
					color: var(--text-muted, #888);
					font-size: 12px;
					font-style: italic;
				">No activity — Balance: ${allocated}</td>
			</tr>`;
	} else {
		rows_html = entries.map((e, i) => {
			const is_added   = e.status === "Added";
			const is_expired = e.status === "Expired";
			const is_used    = e.status === "Used";

			const badge_style = is_added
				? "background:#d4edda; color:#155724;"
				: is_expired
				? "background:#fff3cd; color:#856404;"
				: "background:#f8d7da; color:#721c24;";

			const row_bg  = i % 2 === 0 ? "#ffffff" : "#f9fafb";

			const in_val  = e.leaves_in  !== "-"
				? `<span style="color:#28a745; font-weight:600;">+${e.leaves_in}</span>`
				: `<span style="color:#bbb;">—</span>`;
			const out_val = e.leaves_out !== "-"
				? `<span style="color:#dc3545; font-weight:600;">−${e.leaves_out}</span>`
				: `<span style="color:#bbb;">—</span>`;
			const bal_col = e.balance > 0 ? "#1a73e8" : (e.balance === 0 ? "#888" : "#c5221f");

			return `
				<tr style="background:${row_bg}; border-bottom:1px solid #edf2f7;">
					<td style="padding:8px 10px; font-size:12px; white-space:nowrap; color:#374151;">${e.date}</td>
					<td style="padding:8px 10px; font-size:12px; color:#6b7280; white-space:nowrap;">${e.day || ""}</td>
					<td style="padding:8px 10px;">
						<span style="
							display:inline-block; padding:1px 8px;
							border-radius:10px; font-size:11px; font-weight:600;
							${badge_style}
						">${e.status}</span>
					</td>
					<td style="padding:8px 10px; text-align:right; font-size:12px;">${in_val}</td>
					<td style="padding:8px 10px; text-align:right; font-size:12px;">${out_val}</td>
					<td style="padding:8px 10px; text-align:right; font-size:12px; font-weight:700; color:${bal_col};">${e.balance}</td>
				</tr>`;
		}).join("");
	}

	return `
		<div style="
			min-width: 480px;
			flex-shrink: 0;
			border: 1px solid var(--border-color, #e2e8f0);
			border-radius: 8px;
			overflow: hidden;
			background: #fff;
			box-shadow: 0 1px 4px rgba(0,0,0,0.07);
		">
			<div style="
				display: flex;
				align-items: center;
				justify-content: space-between;
				padding: 10px 14px;
				background: #f8fafc;
				border-bottom: 2px solid var(--border-color, #e2e8f0);
			">
				<span style="font-size:13px; font-weight:600; color:var(--heading-color, #1a202c);">
					${frappe.utils.escape_html(leave_type)}
				</span>
				<span style="
					font-size:12px; font-weight:700;
					background:${balance_bg}; color:${balance_color};
					padding:3px 12px; border-radius:20px;
				">Balance: ${final_balance}</span>
			</div>

			<table style="width:100%; border-collapse:collapse;">
				<thead>
					<tr style="background:#f1f5f9;">
						<th style="${th()}">Date</th>
						<th style="${th()}">Day</th>
						<th style="${th()}">Status</th>
						<th style="${th('right')}">In</th>
						<th style="${th('right')}">Out</th>
						<th style="${th('right')}">Balance</th>
					</tr>
				</thead>
				<tbody>${rows_html}</tbody>
			</table>
		</div>`;
}

function th(align) {
	return `
		padding: 7px 10px;
		text-align: ${align || "left"};
		font-size: 11px;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.4px;
		color: var(--text-muted, #6b7280);
		border-bottom: 1px solid var(--border-color, #e2e8f0);
		white-space: nowrap;
	`;
}