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
                    let auto_process = d.get_value("auto_process");
                    d.hide();
                    start_live_fetch(selected_list, auto_process, listview);
                }
            });

            d.show();

            function render_cards() {
                let container = d.fields_dict.machines_html.$wrapper;
                container.empty();
                let cards = machines.map((m, idx) => {
                    let sync_label = m.last_sync_time ? frappe.datetime.prettyDate(m.last_sync_time) : "Never synced";
                    let status_color = m.connection_status === "Connected" ? "#2ecc71" : m.connection_status === "Failed" ? "#e74c3c" : "#95a5a6";
                    let is_checked = selected[m.name] ? "checked" : "";
                    return `
                        <div style="border:1px solid var(--border-color);border-radius:8px;padding:12px 14px;margin-bottom:10px;background:var(--fg-color);">
                            <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
                                <span style="font-size:13px;font-weight:600;color:var(--text-muted);min-width:20px;">${idx + 1}.</span>
                                <span style="font-size:14px;font-weight:600;flex:1;">${m.machine_name}</span>
                                <span style="width:10px;height:10px;border-radius:50%;background:${status_color};display:inline-block;"></span>
                                <span style="font-size:12px;color:var(--text-muted);">${m.connection_status || "Never Tested"}</span>
                            </div>
                            <div style="display:flex;align-items:center;gap:10px;">
                                <input type="checkbox" data-machine="${m.name}" class="machine-checkbox" style="width:16px;height:16px;cursor:pointer;" ${is_checked} />
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
                        </div>
                        ${cards}
                    </div>`);
                container.find(".machine-checkbox").on("change", function () { selected[$(this).data("machine")] = this.checked; });
                container.find(".sel-all").on("click", function (e) { e.preventDefault(); machines.forEach(m => selected[m.name] = true); render_cards(); });
                container.find(".desel-all").on("click", function (e) { e.preventDefault(); machines.forEach(m => selected[m.name] = false); render_cards(); });
            }
            render_cards();
        }
    });
}

// ─────────────────────────────────────────────────────────
// LIVE FETCH — Row-by-row terminal-style log
//
// Progress rows show: batch / count / bar / % / saved / invalid
// Invalid employee rows appear inline (orange warning rows)
// Final summary shows all unmapped device IDs at the end
// ─────────────────────────────────────────────────────────
function start_live_fetch(machine_names, auto_process, listview) {

    // ── Per-machine state ──
    let state = {};
    machine_names.forEach(mid => {
        state[mid] = {
            name:         mid,
            display_name: mid,
            total:        0,
            done:         false,
            error:        null,
            // Collect ALL unmapped IDs across all batches for this machine
            all_invalid_ids: []
        };
    });

    // ─────────────────────────────────────────
    // STEP 1: Attach realtime BEFORE dialog renders. Buffer events.
    // ─────────────────────────────────────────
    let event_buffer = [];
    let dom_ready    = false;

    function on_realtime_event(data) {
        if (dom_ready) {
            process_event(data);
        } else {
            event_buffer.push(data);
        }
    }

    frappe.realtime.on("biometric_fetch_progress", on_realtime_event);

    // ─────────────────────────────────────────
    // STEP 2: Build the dialog
    // ─────────────────────────────────────────
    let dlg = new frappe.ui.Dialog({
        title: __("⟳ Fetching Records — Live Progress"),
        fields: [{ fieldname: "progress_html", fieldtype: "HTML" }],
        size: "large",
    });
    dlg.show();
    dlg.get_close_btn().hide();

    let $root = dlg.fields_dict.progress_html.$wrapper;
    $root.html(`
        <style>
            @keyframes bp-blink { 0%,100%{opacity:1} 50%{opacity:0.2} }
            .bp-blink     { animation: bp-blink 1.1s ease-in-out infinite; }
            .bp-table     { width:100%; border-collapse:collapse; font-family:'Courier New',monospace; font-size:12.5px; }
            .bp-table td  { padding:4px 8px; border-bottom:1px solid var(--border-color); vertical-align:middle; }
            .bp-table tr:last-child td { border-bottom:none; }
            .bp-bar       { height:7px; border-radius:10px; background:var(--gray-200); overflow:hidden; min-width:90px; }
            .bp-bar-fill  { height:100%; border-radius:10px; }
            .bp-scroll    { max-height:360px; overflow-y:auto; }
            .bp-block     { border:1px solid var(--border-color); border-radius:8px; margin-bottom:14px; overflow:hidden; }
            .bp-hdr       { background:var(--gray-100); padding:8px 14px; display:flex; justify-content:space-between; align-items:center; }
            .bp-inv-row   { background:#fff8f0; }
            .bp-inv-row td{ color:#e67e22 !important; font-style:italic; }
            .bp-summary   { background:#fff8f0; border:1px solid #f39c12; border-radius:6px; padding:10px 14px; margin-top:8px; font-size:12px; }
            .bp-summary-title { font-weight:700; color:#c0392b; margin-bottom:6px; }
            .bp-summary-id { display:inline-block; background:#fde8cc; border:1px solid #f39c12; border-radius:4px;
                             padding:1px 7px; margin:2px 3px; font-family:'Courier New',monospace; font-size:12px; color:#c0392b; }
        </style>
        <div class="bp-machines"></div>
        <div class="bp-action" style="margin-top:12px;text-align:center;"></div>
    `);

    // ─────────────────────────────────────────
    // STEP 3: Render empty machine blocks (skeleton)
    // ─────────────────────────────────────────
    function render_skeleton() {
        let html = machine_names.map(mid => `
            <div class="bp-block" data-machine="${mid}">
                <div class="bp-hdr">
                    <span style="font-weight:600;font-size:13px;" class="bp-name">${state[mid].display_name}</span>
                    <span class="bp-total" style="font-size:11px;color:var(--text-muted);">Connecting…</span>
                    <span class="bp-status" style="font-size:12px;">
                        <span class="bp-blink" style="color:#3498db;">● Running</span>
                    </span>
                </div>
                <div class="bp-scroll">
                    <table class="bp-table">
                        <tbody class="bp-tbody" data-machine="${mid}">
                            <tr class="bp-wait">
                                <td colspan="7" style="color:var(--text-muted);font-style:italic;padding:12px 8px;">
                                    <span class="bp-blink" style="color:#3498db;">●</span>
                                    &nbsp;Connecting to device — rows appear here as records are fetched…
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                <!-- invalid summary shown here after fetch completes -->
                <div class="bp-inv-summary" data-machine="${mid}" style="display:none;"></div>
            </div>`).join("");
        $root.find(".bp-machines").html(html);
    }

    render_skeleton();

    // ─────────────────────────────────────────
    // STEP 4: DOM ready — flush buffer
    // ─────────────────────────────────────────
    dom_ready = true;
    event_buffer.forEach(data => process_event(data));
    event_buffer = [];

    // ─────────────────────────────────────────
    // Helpers
    // ─────────────────────────────────────────
    function pad(n, w) { return String(n).padStart(w, " "); }

    function get_tbody(mid) {
        return $root.find(`.bp-tbody[data-machine="${mid}"]`);
    }

    // Build one new progress <tr>
    function build_progress_row(data) {
        let total   = data.total_in_batch || 1;
        let done_n  = data.processed || 0;
        let pct     = Math.min(100, Math.round((done_n / total) * 100));
        let is_last = (done_n >= total);
        let color   = is_last ? "#2ecc71" : "#3498db";

        let icon = is_last
            ? `<span style="color:#2ecc71;font-weight:700;">✓</span>`
            : `<span class="bp-blink" style="color:#3498db;">●</span>`;

        let new_txt = `<span style="color:#27ae60;">${data.saved} new</span>`;
        let ex_txt  = data.already_exists > 0
            ? ` <span style="color:#95a5a6;">${data.already_exists} existed</span>`
            : "";
        let inv_txt = (data.invalid_ids && data.invalid_ids.length > 0)
            ? ` <span style="color:#e67e22;">⚠ ${data.invalid_ids.length} unmapped</span>`
            : "";

        return `<tr>
            <td style="color:#e67e22;font-weight:600;white-space:nowrap;">Batch ${data.batch_num}</td>
            <td style="white-space:nowrap;">→&nbsp;${pad(done_n,4)} / ${pad(total,4)}</td>
            <td style="min-width:100px;">
                <div class="bp-bar">
                    <div class="bp-bar-fill" style="width:${pct}%;background:${color};"></div>
                </div>
            </td>
            <td style="color:${color};font-weight:700;white-space:nowrap;min-width:40px;">${pct}%</td>
            <td style="text-align:center;width:22px;">${icon}</td>
            <td>${new_txt}${ex_txt}</td>
            <td>${inv_txt}</td>
        </tr>`;
    }

    // Build inline warning row for newly discovered invalid IDs
    // Shows only the NEW IDs seen in this emit event (delta)
    function build_invalid_inline_row(new_invalid_ids) {
        if (!new_invalid_ids || !new_invalid_ids.length) return "";
        let id_chips = new_invalid_ids
            .map(id => `<span style="background:#fde8cc;border:1px solid #f39c12;border-radius:3px;padding:0 5px;margin:0 2px;font-weight:600;">${id}</span>`)
            .join(" ");
        return `<tr class="bp-inv-row">
            <td colspan="7" style="padding:5px 8px;">
                ⚠ &nbsp;Device ID not mapped to any employee: ${id_chips}
                &nbsp;<span style="font-size:11px;color:#999;">— saved as <b>Invalid Employee</b> — set Attendance Device ID on Employee record to fix</span>
            </td>
        </tr>`;
    }

    // Append rows and scroll to bottom
    function append_rows(mid, progress_html, invalid_html) {
        let $tbody = get_tbody(mid);
        if (!$tbody.length) return;
        $tbody.find(".bp-wait").remove();
        $tbody.append(progress_html);
        if (invalid_html) $tbody.append(invalid_html);
        let $scroll = $tbody.closest(".bp-scroll");
        $scroll.scrollTop($scroll[0].scrollHeight);
    }

    function update_header(mid) {
        let ms     = state[mid];
        let $block = $root.find(`.bp-block[data-machine="${mid}"]`);
        if (!$block.length) return;
        $block.find(".bp-name").text(ms.display_name);
        $block.find(".bp-total").text(ms.total > 0 ? `${ms.total} total records` : "Connecting…");
        $block.find(".bp-status").html(
            ms.error  ? `<span style="color:#e74c3c;">✗ Error</span>` :
            ms.done   ? `<span style="color:#2ecc71;font-weight:600;">✓ Complete</span>` :
                        `<span class="bp-blink" style="color:#3498db;">● Running</span>`
        );
    }

    // Show final invalid summary block below the machine's log table
    function show_invalid_summary(mid) {
        let ms = state[mid];
        if (!ms.all_invalid_ids || !ms.all_invalid_ids.length) return;

        let $summary = $root.find(`.bp-inv-summary[data-machine="${mid}"]`);
        let id_chips = ms.all_invalid_ids
            .map(id => `<span class="bp-summary-id">${id}</span>`)
            .join("");

        $summary.html(`
            <div class="bp-summary">
                <div class="bp-summary-title">
                    ⚠ ${ms.all_invalid_ids.length} Device ID(s) not mapped to any Frappe Employee
                </div>
                <div style="margin-bottom:6px;color:#7f4f00;">
                    These records were saved as <b>"Invalid Employee"</b> in the Biometric Attendance Log.
                    To fix: open each Employee → set <b>Attendance Device ID</b> to the correct Device ID below.
                </div>
                <div>${id_chips}</div>
            </div>`).show();
    }

    // ─────────────────────────────────────────
    // Process one realtime event
    // ─────────────────────────────────────────
    // Track last seen invalid_ids per machine to compute delta
    let last_invalid_ids = {};

    function process_event(data) {
        let mid = data.machine_id;
        let ms  = state[mid];
        if (!ms) return;

        ms.display_name = data.machine || ms.display_name;
        ms.total        = data.total;

        // Compute which IDs are NEW since last emit (delta)
        let prev      = last_invalid_ids[mid] || [];
        let curr      = data.invalid_ids || [];
        let new_ids   = curr.filter(id => !prev.includes(id));
        last_invalid_ids[mid] = curr;

        // Merge into the machine's full invalid list
        curr.forEach(id => {
            if (!ms.all_invalid_ids.includes(id)) ms.all_invalid_ids.push(id);
        });

        let progress_html = build_progress_row(data);
        // Only show inline warning row if NEW unmapped IDs appeared in this emit
        let invalid_html  = new_ids.length > 0 ? build_invalid_inline_row(new_ids) : "";

        append_rows(mid, progress_html, invalid_html);
        update_header(mid);
    }

    // ─────────────────────────────────────────
    // Action buttons
    // ─────────────────────────────────────────
    function show_continue(label, on_click) {
        $root.find(".bp-action").html(`
            <div style="padding:8px 0;">
                <div style="font-size:12px;color:#e67e22;margin-bottom:8px;">⚠ ${label}</div>
                <button class="btn btn-warning btn-sm" style="padding:6px 20px;">▶&nbsp; Continue Fetching</button>
            </div>`);
        $root.find(".bp-action button").on("click", () => {
            $root.find(".bp-action").empty();
            on_click();
        });
    }

    function show_done() {
        // Show invalid summary for each machine that has unmapped IDs
        machine_names.forEach(mid => show_invalid_summary(mid));

        $root.find(".bp-action").html(`
            <div style="padding:10px 0;color:#2ecc71;font-weight:600;font-size:13px;">
                ✓ All machines fetched successfully
            </div>`);
        dlg.get_close_btn().show();
        if (listview) listview.refresh();
    }

    // ─────────────────────────────────────────
    // Core fetch runner
    // ─────────────────────────────────────────
    function run_fetch(machine_list, offsets) {

        let promises = machine_list.map(machine_id => new Promise(resolve => {
            frappe.call({
                method: "saral_hr.utils.biometric_sync.sync_selected_machines",
                args: {
                    machine_names: [machine_id],
                    auto_process:  auto_process,
                    offset:        offsets[machine_id] || 0
                },
                freeze: false,
                callback(r) {
                    resolve({ machine_id, results: r.message || [] });
                },
                error() {
                    resolve({ machine_id, results: [{
                        machine_id,
                        machine: state[machine_id].display_name,
                        status:  "error",
                        error:   "Request timed out — click Continue to retry"
                    }]});
                }
            });
        }));

        Promise.all(promises).then(all => {
            frappe.realtime.off("biometric_fetch_progress");

            let has_remaining   = false;
            let next_machines   = [];
            let next_offsets    = {};
            let total_remaining = 0;

            all.forEach(({ machine_id, results }) => {
                results.forEach(res => {
                    let ms = state[res.machine_id || machine_id];
                    if (!ms) return;

                    ms.display_name = res.machine || ms.display_name;
                    get_tbody(machine_id).find(".bp-wait").remove();

                    // Merge invalid IDs from API response into machine state
                    if (res.invalid_ids && res.invalid_ids.length) {
                        res.invalid_ids.forEach(id => {
                            if (!ms.all_invalid_ids.includes(id)) ms.all_invalid_ids.push(id);
                        });
                    }

                    if (res.status === "ok") {
                        ms.total = res.total;
                        if (res.remaining > 0) {
                            has_remaining = true;
                            total_remaining += res.remaining;
                            next_machines.push(machine_id);
                            next_offsets[machine_id] = res.next_offset;
                        } else {
                            ms.done = true;
                        }
                    } else {
                        ms.error = res.error || "Unknown error";
                        ms.done  = true;
                        let $tbody = get_tbody(machine_id);
                        if (!$tbody.find("tr:not(.bp-wait)").length) {
                            $tbody.append(`<tr>
                                <td colspan="7" style="color:#e74c3c;padding:10px 8px;">✗ ${ms.error}</td>
                            </tr>`);
                        }
                    }
                    update_header(machine_id);
                });
            });

            if (has_remaining) {
                // Re-attach for the next batch
                frappe.realtime.on("biometric_fetch_progress", on_realtime_event);
                show_continue(
                    `${total_remaining} records remaining — saved so far. Click Continue to fetch next batch.`,
                    () => run_fetch(next_machines, next_offsets)
                );
            } else {
                show_done();
            }
        });
    }

    // ─────────────────────────────────────────
    // Kick off the first batch
    // ─────────────────────────────────────────
    let initial_offsets = {};
    machine_names.forEach(mid => initial_offsets[mid] = 0);
    run_fetch(machine_names, initial_offsets);
}