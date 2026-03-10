frappe.ui.form.on("Employee", {
    refresh(frm) {
        set_employee_name(frm);

        frm.add_custom_button(__("View Dashboard"), function() {
            frappe.set_route("employee-profile", frm.doc.name);
        });

        create_sidebar_image(frm);
        update_sidebar_image(frm);

        // Active Company - Company Link se fetch
        if (frm.doc.name) {
            frappe.call({
                method: 'frappe.client.get_list',
                args: {
                    doctype: 'Company Link',
                    filters: [
                        ['employee', '=', frm.doc.name],
                        ['is_active', '=', 1]
                    ],
                    fields: ['company'],
                    limit: 50
                },
                callback: function(r) {
                    if (r.message && r.message.length > 0) {
                        let companies = r.message
                            .map(d => d.company)
                            .join('\n');
                        frm.doc.active_company = companies;
                    } else {
                        frm.doc.active_company = 'No Active Company';
                    }
                    frm.refresh_field('active_company');
                    frm.doc.__unsaved = 0;
                    frm.page.clear_indicator();
                }
            });
        }
    },

    onload(frm) {
        create_sidebar_image(frm);
        update_sidebar_image(frm);
    },

    first_name(frm) { set_employee_name(frm); },
    middle_name(frm) { set_employee_name(frm); },
    last_name(frm) { set_employee_name(frm); },

    employee_image(frm) {
        update_sidebar_image(frm);
    },

    current_address(frm) {
        if (frm.doc.same_as_permanent_address) {
            frm.set_value("permanent_address", frm.doc.current_address);
        }
    },

    same_as_permanent_address(frm) {
        if (frm.doc.same_as_permanent_address) {
            if (!frm.doc.current_address) {
                frappe.msgprint({
                    title: __("No Address"),
                    indicator: "orange",
                    message: __("Please enter the current address first.")
                });
                frm.set_value("same_as_permanent_address", 0);
                return;
            }
            frm.set_value("permanent_address", frm.doc.current_address);
            frm.set_df_property("permanent_address", "read_only", 1);
        } else {
            frm.set_df_property("permanent_address", "read_only", 0);
        }
    }
});

function set_employee_name(frm) {
    let first = frm.doc.first_name || "";
    let middle = frm.doc.middle_name || "";
    let last = frm.doc.last_name || "";
    let full_name = [first, middle, last].filter(Boolean).join(" ");
    frm.set_value("employee", full_name);
}

function create_sidebar_image(frm) {
    const sidebar = frm.page.sidebar;
    if (!sidebar) return;
    if (sidebar.find(".employee-image-section").length) return;

    let html = `
        <div class="employee-image-section" style="padding:12px;text-align:center;">
            <div class="employee-image-circle" style="
                width:120px;
                height:120px;
                border-radius:50%;
                overflow:hidden;
                background:#f5f5f5;
                display:flex;
                align-items:center;
                justify-content:center;
                font-size:48px;
                color:#888;
                cursor:pointer;
                position:relative;
                margin:auto;
            ">
                <img class="employee-img" src="" style="width:100%; height:100%; object-fit:cover; display:none;">
                <div class="employee-initial" style="display:flex; align-items:center; justify-content:center; width:100%; height:100%;"></div>
                <div class="image-upload-overlay" style="
                    position:absolute;
                    inset:0;
                    background:rgba(0,0,0,0.5);
                    color:#fff;
                    font-size:14px;
                    display:flex;
                    align-items:center;
                    justify-content:center;
                    opacity:0;
                    pointer-events:none;
                    transition:opacity 0.2s;
                    border-radius:50%;
                ">Change</div>
                <input type="file" accept="image/*" style="display:none;">
            </div>
        </div>
    `;

    sidebar.prepend(html);

    const container = sidebar.find(".employee-image-circle");
    const overlay = container.find(".image-upload-overlay");
    const fileInput = container.find("input[type=file]");

    container.off("mouseenter mouseleave click").on({
        mouseenter: () => overlay.css({ opacity: 1, pointerEvents: "auto" }),
        mouseleave: () => overlay.css({ opacity: 0, pointerEvents: "none" }),
        click: () => {
            if (fileInput.length && fileInput[0]) {
                fileInput[0].click();
            }
        }
    });

    let isUploading = false;
    fileInput.off("change").on("change", (e) => {
        if (isUploading) return;
        const file = e.target.files[0];
        if (!file) return;
        isUploading = true;
        manual_upload(file, frm, fileInput, () => {
            isUploading = false;
        });
    });
}

function update_sidebar_image(frm) {
    const sidebar = frm.page.sidebar;
    if (!sidebar) return;

    const container = sidebar.find(".employee-image-circle");
    const img = container.find(".employee-img");
    const initial = container.find(".employee-initial");

    if (frm.doc.employee_image) {
        const src = frm.doc.employee_image + "?t=" + Date.now();
        img.off("load").on("load", () => {
            img.show();
            initial.hide();
        });
        img.attr("src", src);
    } else {
        img.hide();
        initial
            .text((frm.doc.employee || "E").charAt(0).toUpperCase())
            .show();
    }
}

function manual_upload(file, frm, fileInput, done) {
    const data = new FormData();
    data.append("file", file);
    data.append("folder", "Home/Attachments");
    data.append("is_private", 0);

    fetch("/api/method/upload_file", {
        method: "POST",
        body: data,
        credentials: "same-origin",
        headers: {
            "X-Frappe-CSRF-Token": frappe.csrf_token
        }
    })
    .then(res => {
        if (!res.ok) throw new Error(res.status);
        return res.json();
    })
    .then(r => {
        if (!r.message || !r.message.file_url) {
            throw new Error("No file URL");
        }
        const file_url = r.message.file_url;
        frm.doc.employee_image = file_url;
        update_sidebar_image(frm);
        return frappe.call({
            method: "frappe.client.set_value",
            args: {
                doctype: frm.doctype,
                name: frm.doc.name,
                fieldname: "employee_image",
                value: file_url
            }
        });
    })
    .then(() => {
        fileInput[0].value = "";
        done();
    })
    .catch(err => {
        console.error(err);
        frappe.msgprint("Image upload failed");
        done();
    });
}