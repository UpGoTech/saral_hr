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

            // ── Store last_sync_time PER machine BEFORE any fetch starts ──
            // This is passed to ALL batches so they filter from the same cutoff
            let original_sync_times = {};
            machines.forEach(m => { original_sync_times[m.name] = m.last_sync_time || null; });

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
                    start_live_fetch(selected_list, d.get_value("auto_process"), listview, original_sync_times);
                }
            });
            d.show();

            function render_cards() {
                let container = d.fields_dict.machines_html.$wrapper;
                container.empty();
                let cards = machines.map((m, idx) => {
                    let sync_label   = m.last_sync_time ? frappe.datetime.prettyDate(m.last_sync_time) : "Never synced";
                    let status_color = m.connection_status === "Connected" ? "#2ecc71" : m.connection_status === "Failed" ? "#e74c3c" : "#95a5a6";
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
// Each batch shows a clear breakdown:
//   Batch 1 of 5  →  40 records scanned
//       ✓  3   — newly saved to database
//       ⟳  6   — already existed (skipped)
//       ✗  31  — device ID not mapped to any employee (not saved)
//
// FIX: original_sync_times is passed to every batch call so Python
//      filters from the same cutoff for all 5 batches.
// ─────────────────────────────────────────────────────────
function start_live_fetch(machine_names, auto_process, listview, original_sync_times) {

    const NUM_BATCHES = 5;

    let state = {};
    machine_names.forEach(mid => {
        state[mid] = {
            display_name:    mid,
            total:           0,
            all_invalid_ids: [],
            grand_saved:     0,
            grand_invalid:   0,
            grand_existed:   0,
            done:            false,
            error:           null,
        };
    });

    // Realtime: only updates the live counter on the running batch line
    frappe.realtime.on("biometric_fetch_progress", function(data) {
        let mid = data.machine_id;
        if (!state[mid]) return;
        state[mid].display_name = data.machine || state[mid].display_name;
        let $hdr = $("#bp-batchhdr-" + safe(mid) + "-b" + data.batch_num);
        if ($hdr.length && !$hdr.hasClass("finalised")) {
            $hdr.html(hdr_running(data.batch_num, NUM_BATCHES, data.fetched, data.batch_size));
        }
    });

    // ── Dialog ──
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
                        border-top:1px solid var(--border-color); padding-top:10px; margin-top:6px; }
            .bp-inv-box   { margin-top:14px; background:#fff8f0; border:1px solid #f39c12;
                            border-radius:6px; padding:10px 14px; font-family:var(--font-stack); font-size:12px; }
            .bp-inv-title { font-weight:600; color:#c0392b; margin-bottom:4px; }
            .bp-inv-sub   { color:#7f4f00; font-size:11px; margin-bottom:8px; }
            .bp-chip      { display:inline-block; background:#fde8cc; border:1px solid #f39c12;
                            border-radius:4px; padding:1px 8px; margin:2px 3px;
                            font-family:'Courier New',monospace; font-size:11px; color:#c0392b; }
            .bp-action    { margin-top:14px; display:flex; align-items:center; gap:12px; flex-wrap:wrap; }
            .bp-done      { color:#27ae60; font-weight:600; font-size:13px; font-family:var(--font-stack); }
        </style>
        <div class="bp-log" id="bp-log">
            <div id="bp-machines"></div>
            <div class="bp-action" id="bp-action"></div>
        </div>
    `);

    // Skeleton
    machine_names.forEach(mid => {
        $root.find("#bp-machines").append(`
            <div id="bp-block-${safe(mid)}" style="margin-bottom:18px;">
                <div class="bp-mhdr">
                    <span class="bp-mname">${mid}</span>
                    <span class="bp-mstatus t-blue"><span class="bp-blink">●</span> Connecting…</span>
                </div>
                <div id="bp-lines-${safe(mid)}">
                    <div class="bp-bhdr t-muted" id="bp-waiting-${safe(mid)}" style="font-style:italic;">
                        <span class="bp-blink t-blue">●</span> &nbsp;Fetching data from device…
                    </div>
                </div>
                <div id="bp-grand-${safe(mid)}" class="bp-grand" style="display:none;"></div>
            </div>`);
    });

    // ── Helpers ──
    function safe(str) { return str.replace(/[^a-z0-9]/gi, "_"); }

    function hdr_running(bn, bt, fetched, batch_size) {
        return `<span class="t-muted">Batch ${bn} of ${bt} &nbsp;→&nbsp;</span>` +
               `<span class="t-blue bp-blink">fetching…</span>` +
               (batch_size ? ` <span class="t-blue">${fetched}/${batch_size}</span> records` : "");
    }

    function hdr_done(bn, bt, scanned) {
        return `<span class="t-muted">Batch ${bn} of ${bt} &nbsp;→&nbsp;</span>` +
               `<span class="t-green">${scanned} records scanned</span>`;
    }

    // Sub-lines: saved + existed + invalid always adds up to scanned
    function sub_lines(saved, existed, invalid) {
        return `<div class="bp-bsub"><span class="t-green">✓ &nbsp;${saved}</span>` +
                   `<span class="t-muted"> &nbsp;— newly saved to database</span></div>` +
               `<div class="bp-bsub"><span class="t-gray">⟳ &nbsp;${existed}</span>` +
                   `<span class="t-muted"> &nbsp;— already existed in database (skipped)</span></div>` +
               `<div class="bp-bsub"><span class="t-orange">✗ &nbsp;${invalid}</span>` +
                   `<span class="t-muted"> &nbsp;— device ID not mapped to any employee (not saved)</span></div>`;
    }

    // Render or replace a full batch block
    function render_batch(mid, bn, bt, scanned, saved, existed, invalid) {
        let blk_id = "bp-batchblk-" + safe(mid) + "-b" + bn;
        let hdr_id = "bp-batchhdr-" + safe(mid) + "-b" + bn;

        let html = `
            <div id="${blk_id}">
                <div class="bp-bhdr finalised" id="${hdr_id}">${hdr_done(bn, bt, scanned)}</div>
                <div>${sub_lines(saved, existed, invalid)}</div>
                <div class="bp-sep"></div>
            </div>`;

        $("#bp-waiting-" + safe(mid)).remove();
        let $existing = $("#" + blk_id);
        if ($existing.length) {
            $existing.replaceWith(html);
        } else {
            $("#bp-lines-" + safe(mid)).append(html);
        }
    }

    // Update grand total line
    function update_grand(mid, total) {
        let ms = state[mid];
        let scanned = ms.grand_saved + ms.grand_existed + ms.grand_invalid;
        let rem     = Math.max(0, total - scanned);
        $("#bp-grand-" + safe(mid)).show().html(
            `<b>${scanned}</b> scanned so far = ` +
            `<b style="color:#27ae60;">${ms.grand_saved}</b> saved + ` +
            `<b style="color:#7f8c8d;">${ms.grand_existed}</b> existed + ` +
            `<b style="color:#e67e22;">${ms.grand_invalid}</b> unmapped` +
            (rem > 0 ? ` &nbsp;|&nbsp; <b style="color:#e74c3c;">${rem}</b> remaining on device` : "") +
            ` &nbsp;|&nbsp; Device total: <b>${total}</b>`
        );
    }

    function update_mstatus(mid, status) {
        let ms = state[mid];
        $("#bp-block-" + safe(mid)).find(".bp-mname").text(ms.display_name);
        let html = status === "done"  ? `<span class="t-green">✓ Complete</span>` :
                   status === "error" ? `<span class="t-red">✗ Error</span>` :
                                        `<span class="t-blue bp-blink">● Running</span>`;
        $("#bp-block-" + safe(mid)).find(".bp-mstatus").html(html);
    }

    function show_invalid_chips(mid) {
        let ms = state[mid];
        if (!ms.all_invalid_ids.length) return;
        let chips = ms.all_invalid_ids.map(id => `<span class="bp-chip">${id}</span>`).join("");
        $("#bp-block-" + safe(mid)).append(`
            <div class="bp-inv-box">
                <div class="bp-inv-title">⚠ ${ms.all_invalid_ids.length} Device ID(s) not mapped to any Employee — not saved</div>
                <div class="bp-inv-sub">Fix: open Employee → set <b>Attendance Device ID</b> to the value below → re-fetch</div>
                ${chips}
            </div>`);
    }

    function show_continue(next_machines, next_offsets, next_batches, next_sync_times, total_remaining) {
        $root.find("#bp-action").html(`
            <span style="font-size:12px;color:#e67e22;font-family:var(--font-stack);">
                ⚠ ${total_remaining} records remaining
            </span>
            <button class="btn btn-sm btn-warning" id="bp-continue-btn" style="padding:5px 20px;font-weight:600;">
                ▶ &nbsp;Continue &amp; Fetch
            </button>`);
        $("#bp-continue-btn").on("click", function () {
            $root.find("#bp-action").empty();
            run_fetch(next_machines, next_offsets, next_batches, next_sync_times);
        });
    }

    function show_all_done() {
        machine_names.forEach(mid => show_invalid_chips(mid));
        $root.find("#bp-action").html(
            `<div class="bp-done">✓ &nbsp;All machines fetched successfully</div>`);
        dlg.get_close_btn().show();
        if (listview) listview.refresh();
    }

    // ─────────────────────────────────────
    // CORE RUNNER
    // sync_times = { machine_id: original_sync_time_string }
    // ─────────────────────────────────────
    function run_fetch(machine_list, offsets, batch_nums, sync_times) {

        // Show "Batch N → fetching…" immediately
        machine_list.forEach(mid => {
            let bn     = batch_nums[mid] || 1;
            let blk_id = "bp-batchblk-" + safe(mid) + "-b" + bn;
            let hdr_id = "bp-batchhdr-" + safe(mid) + "-b" + bn;
            if (!$("#" + blk_id).length) {
                $("#bp-waiting-" + safe(mid)).remove();
                $("#bp-lines-" + safe(mid)).append(`
                    <div id="${blk_id}">
                        <div class="bp-bhdr" id="${hdr_id}">
                            ${hdr_running(bn, NUM_BATCHES, 0, "?")}
                        </div>
                    </div>`);
            }
            update_mstatus(mid, "running");
        });

        let promises = machine_list.map(machine_id =>
            new Promise(resolve => {
                frappe.call({
                    method: "saral_hr.utils.biometric_sync.sync_selected_machines",
                    args: {
                        machine_names:       [machine_id],
                        auto_process:        auto_process,
                        offset:              offsets[machine_id]    || 0,
                        batch_num:           batch_nums[machine_id] || 1,
                        total_batches:       NUM_BATCHES,
                        // Pass original sync time so Python uses same filter cutoff
                        original_sync_time:  sync_times[machine_id] || null,
                    },
                    freeze: false,
                    callback(r) { resolve({ machine_id, results: r.message || [] }); },
                    error() {
                        resolve({ machine_id, results: [{
                            machine_id, machine: state[machine_id].display_name,
                            status: "error", error: "Request timed out",
                            batch_num: batch_nums[machine_id] || 1,
                            total_batches: NUM_BATCHES,
                            fetched: 0, batch_size: 0,
                            saved: 0, already_exists: 0,
                            invalid_count: 0, invalid_ids: [],
                            remaining_records: 0,
                        }]});
                    }
                });
            })
        );

        Promise.all(promises).then(all => {
            let next_machines    = [];
            let next_offsets     = {};
            let next_batches     = {};
            let next_sync_times  = {};
            let total_remaining  = 0;

            all.forEach(({ machine_id, results }) => {
                (results || []).forEach(res => {
                    let ms = state[res.machine_id || machine_id];
                    if (!ms) return;

                    ms.display_name = res.machine || ms.display_name;

                    if (res.status === "ok") {
                        let saved   = res.saved          || 0;
                        let existed = res.already_exists || 0;
                        let invalid = res.invalid_count  || 0;
                        let scanned = res.batch_size     || 0;

                        ms.grand_saved   += saved;
                        ms.grand_existed += existed;
                        ms.grand_invalid += invalid;
                        ms.total          = res.total || ms.total;

                        (res.invalid_ids || []).forEach(id => {
                            if (!ms.all_invalid_ids.includes(id)) ms.all_invalid_ids.push(id);
                        });

                        // Render the finalised batch block
                        render_batch(machine_id, res.batch_num, res.total_batches,
                                     scanned, saved, existed, invalid);
                        update_grand(machine_id, ms.total);

                        if (res.remaining_records > 0 && res.next_offset !== null) {
                            next_machines.push(machine_id);
                            next_offsets[machine_id]    = res.next_offset;
                            next_batches[machine_id]    = res.next_batch_num;
                            // Keep the SAME original_sync_time for next batch
                            next_sync_times[machine_id] = sync_times[machine_id] || res.original_sync_time || null;
                            total_remaining += res.remaining_records;
                            update_mstatus(machine_id, "running");
                        } else {
                            ms.done = true;
                            update_mstatus(machine_id, "done");
                        }

                    } else {
                        ms.error = res.error || "Unknown error";
                        ms.done  = true;
                        let blk_id = "bp-batchblk-" + safe(machine_id) + "-b" + (res.batch_num || 1);
                        let hdr_id = "bp-batchhdr-" + safe(machine_id) + "-b" + (res.batch_num || 1);
                        if (!$("#" + blk_id).length) {
                            $("#bp-waiting-" + safe(machine_id)).remove();
                            $("#bp-lines-" + safe(machine_id)).append(
                                `<div id="${blk_id}"><div class="bp-bhdr finalised" id="${hdr_id}"></div></div>`);
                        }
                        $("#" + hdr_id).html(
                            `<span class="t-muted">Batch ${res.batch_num || 1} of ${NUM_BATCHES} &nbsp;→&nbsp;</span>` +
                            `<span class="t-red">✗ ${ms.error}</span>`);
                        update_mstatus(machine_id, "error");
                    }
                });
            });

            if (next_machines.length > 0) {
                show_continue(next_machines, next_offsets, next_batches, next_sync_times, total_remaining);
            } else {
                show_all_done();
            }
        });
    }

    // Kick off batch 1 with original_sync_times
    let init_offsets = {}, init_batches = {};
    machine_names.forEach(mid => { init_offsets[mid] = 0; init_batches[mid] = 1; });
    run_fetch(machine_names, init_offsets, init_batches, original_sync_times);
}