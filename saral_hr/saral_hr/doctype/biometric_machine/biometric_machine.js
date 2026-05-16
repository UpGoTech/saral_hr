// Copyright (c) 2026, sj and contributors
// For license information, please see license.txt

frappe.ui.form.on("Biometric machine", {
    refresh(frm) {
        if (frm.is_new()) return;
        frm.add_custom_button(__("Test Connection"), function () {
            if (!frm.doc.ip_address) {
                frappe.msgprint({ message: __("Please enter an IP Address before testing."), indicator: "orange" });
                return;
            }
            frappe.call({
                method: "saral_hr.utils.biometric_sync.test_connection",
                args: { machine_name: frm.doc.name },
                freeze: true,
                freeze_message: __("Connecting to device..."),
                callback(r) {
                    if (r.message && r.message.success) {
                        frappe.show_alert({ message: __("✓ Connection Successful"), indicator: "green" }, 5);
                    } else {
                        frappe.show_alert({
                            message: __("✗ Connection Failed: ") + (r.message ? r.message.message : "Unknown error"),
                            indicator: "red"
                        }, 7);
                    }
                    frm.reload_doc();
                }
            });
        }).addClass("btn-primary");
    }
});

// ── List View ──
frappe.listview_settings["Biometric machine"] = {
    onload(listview) {
        frappe.after_ajax(() => {
            listview.page.wrapper.find(".btn-fetch-records").remove();
            let $btn = $(`<button class="btn btn-primary btn-sm btn-fetch-records" style="margin-right:8px;">
                ⬇ ${__("Fetch Records")}
            </button>`);
            $btn.on("click", () => show_fetch_dialog(listview));
            listview.page.wrapper.find(".page-actions").prepend($btn);
        });
    },
    refresh(listview) {
        frappe.after_ajax(() => {
            if (!listview.page.wrapper.find(".btn-fetch-records").length) {
                let $btn = $(`<button class="btn btn-primary btn-sm btn-fetch-records" style="margin-right:8px;">
                    ⬇ ${__("Fetch Records")}
                </button>`);
                $btn.on("click", () => show_fetch_dialog(listview));
                listview.page.wrapper.find(".page-actions").prepend($btn);
            }
        });
    }
};

// ── Machine Selection Dialog ──
function show_fetch_dialog(listview) {
    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: "Biometric machine",
            filters: { is_active: 1 },
            fields: ["name", "machine_name", "ip_address", "connection_status", "last_sync_time"],
            limit_page_length: 100,
            order_by: "machine_name asc"
        },
        callback(r) {
            let machines = r.message || [];
            if (!machines.length) {
                frappe.msgprint({ title: __("No Machines Found"), message: __("No active Biometric machines found."), indicator: "orange" });
                return;
            }
            let selected = {};
            machines.forEach(m => selected[m.name] = true);

            let d = new frappe.ui.Dialog({
                title: __("Fetch Records from Biometric Machines"),
                fields: [
                    { fieldname: "machines_html", fieldtype: "HTML" },
                    { fieldname: "auto_process", fieldtype: "Check", label: __("Auto Process to Checkin after fetch"), default: 0 }
                ],
                primary_action_label: __("Fetch Selected Machines"),
                primary_action() {
                    let selected_list = Object.keys(selected).filter(k => selected[k]);
                    if (!selected_list.length) {
                        frappe.show_alert({ message: __("Please select at least one machine."), indicator: "orange" }, 4);
                        return;
                    }
                    d.hide();
                    start_live_fetch(selected_list, d.get_value("auto_process"), listview);
                }
            });
            d.show();

            function render_cards() {
                let container = d.fields_dict.machines_html.$wrapper;
                container.empty();
                let cards = machines.map((m, idx) => {
                    let sync_label   = m.last_sync_time ? frappe.datetime.prettyDate(m.last_sync_time) : "Never synced";
                    let status_color = m.connection_status === "Connected" ? "#2ecc71"
                                     : m.connection_status === "Failed"    ? "#e74c3c" : "#95a5a6";
                    return `
                        <div style="border:1px solid var(--border-color);border-radius:8px;padding:12px 14px;margin-bottom:10px;background:var(--fg-color);">
                            <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
                                <span style="font-size:13px;font-weight:600;color:var(--text-muted);min-width:20px;">${idx + 1}.</span>
                                <span style="font-size:14px;font-weight:600;flex:1;">${m.machine_name}</span>
                                <span style="width:10px;height:10px;border-radius:50%;background:${status_color};display:inline-block;"></span>
                                <span style="font-size:12px;color:var(--text-muted);">${m.connection_status || "Never Tested"}</span>
                            </div>
                            <div style="display:flex;align-items:center;gap:10px;">
                                <input type="checkbox" data-machine="${m.name}" class="machine-checkbox" style="width:16px;height:16px;cursor:pointer;" ${selected[m.name] ? "checked" : ""} />
                                <label style="cursor:pointer;margin:0;font-size:12px;color:var(--text-muted);">Select this machine</label>
                                <span style="margin-left:auto;font-size:11px;color:var(--text-muted);background:var(--gray-100);padding:2px 8px;border-radius:10px;">⏱ Last Sync: ${sync_label}</span>
                            </div>
                        </div>`;
                }).join("");
                container.html(`
                    <div>
                        <div style="display:flex;justify-content:flex-end;gap:12px;margin-bottom:12px;">
                            <a href="#" class="sel-all" style="font-size:12px;cursor:pointer;">✓ Select All</a>
                            <a href="#" class="desel-all" style="font-size:12px;cursor:pointer;">✗ Deselect All</a>
                        </div>${cards}
                    </div>`);
                container.find(".machine-checkbox").on("change", function () { selected[$(this).data("machine")] = this.checked; });
                container.find(".sel-all").on("click",   e => { e.preventDefault(); machines.forEach(m => selected[m.name] = true);  render_cards(); });
                container.find(".desel-all").on("click", e => { e.preventDefault(); machines.forEach(m => selected[m.name] = false); render_cards(); });
            }
            render_cards();
        }
    });
}

// ─────────────────────────────────────────────────────────
// LIVE FETCH
//
// NO REALTIME — 100% reliable.
// Python returns full batch results in the API response.
// JS draws all batch lines from response data.
//
// Display:
//   Batch 1 of 5  →  40 records scanned
//       ✓  9   — newly saved to database
//       ⟳  0   — already existed in database (skipped)
//       ✗  31  — device ID not mapped to any employee (not saved)
//   ...
// ─────────────────────────────────────────────────────────
function start_live_fetch(machine_names, auto_process, listview) {

    function safe(str) { return str.replace(/[^a-z0-9]/gi, "_"); }

    // ── Build progress dialog (shown immediately with "Fetching…" skeleton) ──
    let dlg = new frappe.ui.Dialog({
        title: __("Fetching Records — Live Progress"),
        fields: [{ fieldname: "log_html", fieldtype: "HTML" }],
        size: "large",
    });
    dlg.show();
    dlg.get_close_btn().hide();

    let $root = dlg.fields_dict.log_html.$wrapper;
    $root.html(`
        <style>
            .bp-log   { font-family:'Courier New',monospace; font-size:13px; }
            .bp-mhdr  { font-family:var(--font-stack); font-weight:600; font-size:13px;
                        color:var(--text-color); border-bottom:1px solid var(--border-color);
                        padding:6px 0; margin-bottom:10px;
                        display:flex; justify-content:space-between; align-items:center; }
            .bp-mhdr + div { margin-bottom:16px; }
            .bp-bhdr  { padding:3px 0; line-height:2; }
            .bp-bsub  { padding:1px 0 1px 20px; line-height:1.8; font-size:12.5px; }
            .bp-sep   { height:8px; }
            .t-muted  { color:var(--text-muted); }
            .t-green  { color:#27ae60; font-weight:600; }
            .t-orange { color:#e67e22; font-weight:600; }
            .t-red    { color:#e74c3c; font-weight:600; }
            .t-blue   { color:#2980b9; }
            .t-gray   { color:#7f8c8d; }
            @keyframes bp-blink { 0%,100%{opacity:1} 50%{opacity:0.2} }
            .bp-blink { animation:bp-blink 1.1s ease-in-out infinite; }
            .bp-grand { font-family:var(--font-stack); font-size:12px; color:var(--text-muted);
                        border-top:1px solid var(--border-color); padding-top:10px; margin-top:4px; }
            .bp-inv-box   { margin-top:14px; background:#fff8f0; border:1px solid #f39c12;
                            border-radius:6px; padding:10px 14px;
                            font-family:var(--font-stack); font-size:12px; }
            .bp-inv-title { font-weight:600; color:#c0392b; margin-bottom:4px; }
            .bp-inv-sub   { color:#7f4f00; font-size:11px; margin-bottom:8px; }
            .bp-chip      { display:inline-block; background:#fde8cc; border:1px solid #f39c12;
                            border-radius:4px; padding:1px 8px; margin:2px 3px;
                            font-family:'Courier New',monospace; font-size:11px; color:#c0392b; }
            .bp-action    { margin-top:14px; }
            .bp-done      { color:#27ae60; font-weight:600; font-size:13px; font-family:var(--font-stack); }
        </style>
        <div class="bp-log" id="bp-log">
            <div id="bp-machines"></div>
            <div class="bp-action" id="bp-action"></div>
        </div>`);

    // Skeleton — one block per machine showing "Fetching…"
    machine_names.forEach(mid => {
        $root.find("#bp-machines").append(`
            <div id="bp-block-${safe(mid)}" style="margin-bottom:18px;">
                <div class="bp-mhdr">
                    <span class="bp-mname">${mid}</span>
                    <span class="bp-mstatus t-blue">
                        <span class="bp-blink">●</span> Connecting…
                    </span>
                </div>
                <div id="bp-lines-${safe(mid)}">
                    <div class="bp-bhdr t-muted" style="font-style:italic;">
                        <span class="bp-blink t-blue">●</span>
                        &nbsp;Fetching data from device…
                    </div>
                </div>
                <div id="bp-grand-${safe(mid)}" class="bp-grand" style="display:none;"></div>
            </div>`);
    });

    // ── Helper: render one batch block ──
    function render_batch_block(mid, bn, bt, b_size, saved, existed, invalid) {
        let hdr = `<span class="t-muted">Batch ${bn} of ${bt} &nbsp;→&nbsp;</span>` +
                  `<span class="t-green">${b_size} records scanned</span>`;
        let subs = `<div class="bp-bsub"><span class="t-green">✓ &nbsp;${saved}</span>` +
                       `<span class="t-muted"> &nbsp;— newly saved to database</span></div>` +
                   `<div class="bp-bsub"><span class="t-gray">⟳ &nbsp;${existed}</span>` +
                       `<span class="t-muted"> &nbsp;— already existed in database (skipped)</span></div>` +
                   `<div class="bp-bsub"><span class="t-orange">✗ &nbsp;${invalid}</span>` +
                       `<span class="t-muted"> &nbsp;— device ID not mapped to any employee (not saved)</span></div>`;
        return `<div><div class="bp-bhdr">${hdr}</div><div>${subs}</div><div class="bp-sep"></div></div>`;
    }

    // ── Helper: render grand total ──
    function render_grand(total, grand_saved, grand_existed, grand_invalid) {
        let scanned = grand_saved + grand_existed + grand_invalid;
        let not_yet = Math.max(0, total - scanned);
        return `<b>${total}</b> total on device &nbsp;=&nbsp; ` +
               `<b style="color:#27ae60;">${grand_saved}</b> newly saved` +
               ` &nbsp;+&nbsp; <b style="color:#7f8c8d;">${grand_existed}</b> already existed` +
               ` &nbsp;+&nbsp; <b style="color:#e67e22;">${grand_invalid}</b> no employee mapping` +
               (not_yet > 0
                   ? ` &nbsp;+&nbsp; <b style="color:#e74c3c;">${not_yet}</b> not yet fetched`
                   : ` &nbsp;<span style="color:#27ae60;">— all ${total} processed ✓</span>`);
    }

    // ── Fire ONE API call per machine ──
    let promises = machine_names.map(machine_id =>
        new Promise(resolve => {
            frappe.call({
                method: "saral_hr.utils.biometric_sync.sync_selected_machines",
                args: { machine_names: [machine_id], auto_process: auto_process },
                freeze: false,
                callback(r) { resolve({ machine_id, result: r.message || [] }); },
                error()     { resolve({ machine_id, result: null }); }
            });
        })
    );

    Promise.all(promises).then(all => {
        // Draw all batch lines from the response
        all.forEach(({ machine_id, result }) => {
            let $lines  = $root.find("#bp-lines-" + safe(machine_id));
            let $grand  = $root.find("#bp-grand-"  + safe(machine_id));
            let $mstatus = $root.find("#bp-block-" + safe(machine_id) + " .bp-mstatus");
            let $mname   = $root.find("#bp-block-" + safe(machine_id) + " .bp-mname");

            // Clear "Fetching…" placeholder
            $lines.empty();

            if (!result) {
                $mstatus.html(`<span class="t-red">✗ Request failed</span>`);
                $lines.html(`<div class="bp-bhdr t-red">✗ Request timed out or failed</div>`);
                return;
            }

            // Frappe can return array or object — handle both
            // Also: machine_names=[machine_id] so result always has exactly 1 entry
            let result_list = Array.isArray(result) ? result : [result];
            let res = result_list.find(r => r.machine_id === machine_id)
                   || result_list.find(r => r.machine_id !== undefined)
                   || result_list.find(r => r.status !== undefined)
                   || result_list[0]
                   || {};

            if (!res || res.status === "error") {
                let err = res ? res.error : "Unknown error";
                $mstatus.html(`<span class="t-red">✗ Error</span>`);
                $lines.html(`<div class="bp-bhdr t-red">✗ ${err}</div>`);
                return;
            }

            // Update machine name if available
            if (res.machine) $mname.text(res.machine);

            let total         = res.total              || 0;
            let batches       = res.batches            || [];
            let all_inv_ids   = res.all_invalid_ids    || res.invalid_ids || [];

            // Debug: log what we got
            console.log("[Biometric Fetch] machine:", machine_id, "result:", res);
            let grand_saved   = 0;
            let grand_existed = 0;
            let grand_invalid = 0;

            if (total === 0) {
                // Nothing new to fetch
                $lines.html(`<div class="bp-bhdr t-muted">No new records found on device.</div>`);
                $mstatus.html(`<span class="t-green">✓ Complete</span>`);
                return;
            }

            // Draw each batch block
            if (batches && batches.length > 0) {
                batches.forEach(b => {
                    grand_saved   += b.saved          || 0;
                    grand_existed += b.already_exists || 0;
                    grand_invalid += b.invalid_count  || 0;
                    $lines.append(render_batch_block(
                        machine_id,
                        b.batch_num, b.total_batches || 5,
                        b.batch_size,
                        b.saved          || 0,
                        b.already_exists || 0,
                        b.invalid_count  || 0
                    ));
                });
            } else {
                // Fallback: no batch breakdown available, show single summary line
                let total_saved   = res.saved          || 0;
                let total_existed = res.already_exists || 0;
                let total_invalid = (res.all_invalid_ids || res.invalid_ids || []).length;
                grand_saved   = total_saved;
                grand_existed = total_existed;
                grand_invalid = total_invalid;
                $lines.append(render_batch_block(machine_id, 1, 1, total, total_saved, total_existed, total_invalid));
            }

            // Grand total
            $grand.show().html(render_grand(total, grand_saved, grand_existed, grand_invalid));

            // Invalid chips
            if (all_inv_ids.length) {
                let chips = all_inv_ids.map(id => `<span class="bp-chip">${id}</span>`).join("");
                $root.find("#bp-block-" + safe(machine_id)).append(`
                    <div class="bp-inv-box">
                        <div class="bp-inv-title">
                            ⚠ ${all_inv_ids.length} Device ID(s) not mapped to any Employee — not saved
                        </div>
                        <div class="bp-inv-sub">
                            Fix: open Employee → set <b>Attendance Device ID</b> to the value below → re-fetch
                        </div>
                        ${chips}
                    </div>`);
            }

            $mstatus.html(`<span class="t-green">✓ Complete</span>`);
        });

        // Done
        $root.find("#bp-action").html(
            `<div class="bp-done">✓ &nbsp;All machines fetched successfully</div>`);
        dlg.get_close_btn().show();
        if (listview) listview.refresh();
    });
}