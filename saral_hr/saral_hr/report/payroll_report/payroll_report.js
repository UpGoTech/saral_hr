frappe.query_reports["Payroll Report"] = {
    filters: [
        { fieldname:"report_mode", label:__("Report"), fieldtype:"Data", hidden:1, default:"bank_advice" },
        { fieldname:"year",    label:__("Year"),    fieldtype:"Select", options:_get_year_options(), reqd:1, default:"" },
        { fieldname:"month",   label:__("Month"),   fieldtype:"Select", reqd:1, default:"",
          options:["","January","February","March","April","May","June","July","August","September","October","November","December"] },
        { fieldname:"company", label:__("Company"), fieldtype:"MultiSelectList", reqd:1,
          get_data: txt => frappe.db.get_link_options("Company", txt) },
        { fieldname:"category", label:__("Category"), fieldtype:"Link", options:"Category", default:"" },
        { fieldname:"division", label:__("Division"), fieldtype:"MultiSelectList",
          get_data: txt => frappe.db.get_link_options("Division", txt) },
    ],

    onload(report) {
        frappe.after_ajax(() => {
            _inject_nav(report);
            _set_print_buttons(report);
        });
    },

    formatter(value, row, column, data, default_formatter) {
        if (!data) return default_formatter(value, row, column, data);
        const mode = frappe.query_report.get_filter_value("report_mode");
        const fn   = column.fieldname, rt = data._row_type;
        const def  = v => default_formatter(v, row, column, data);
        const bold = v => `<strong>${def(v)}</strong>`;

        if (mode==="professional_tax" && rt==="total")
            return fn==="pt_rate" ? "" : bold(value);

        if (mode==="provident_fund") {
            if (rt==="total")
                return ["pf_no","uan_no","days","absent","date_of_joining","date_of_birth"].includes(fn) ? "" : bold(value);
            if (fn==="vol_pf" && (value===null||value===undefined||value==="")) return "";
        }

        if (mode==="salary_summary") {
            if (rt==="grand_total")    return fn==="spacer" ? "" : bold(value);
            if (rt==="section_header" && fn==="description")
                return `<strong style="font-size:12px;border-bottom:2px solid #333;padding-bottom:2px;display:block;">${value||""}</strong>`;
            if (rt==="other") {
                if (fn==="description") return `<span style="font-weight:600;">${value||""}</span>`;
                if (fn==="amount")      return `<span style="font-weight:600;">${frappe.format(value,{fieldtype:"Float",precision:2})}</span>`;
                return "";
            }
            if (rt==="separator") return "";
            if ((fn==="amount"||fn==="ded_amount") && (value===null||value===undefined||value==="")) return "";
            if (fn==="spacer") return "";
        }
        return data.bold ? bold(value) : def(value);
    }
};

// ── REPORT DEFINITIONS ──────────────────────────────────────────────────────
// bank_type field is no longer needed — Home/Other are separate report tabs.
const REPORTS = [
    { key:"bank_advice",               label:"Bank Advice"                    },
    { key:"home_bank_advice",          label:"Home Bank Advice"               },
    { key:"other_bank_advice",         label:"Other Bank Advice"              },
    { key:"educational_allowance",     label:"Educational Allowance Register" },
    { key:"esi_register",              label:"ESI Register"                   },
    { key:"labour_welfare_fund",       label:"Labour Welfare Fund Register"   },
    { key:"professional_tax",          label:"Professional Tax Register"      },
    { key:"provident_fund",            label:"Provident Fund Register"        },
    { key:"retention_deposit",         label:"Retention Deposit Register"     },
    { key:"salary_summary",            label:"Salary Summary"                 },
    { key:"salary_summary_individual", label:"Salary Summary Individual"      },
    { key:"transaction_checklist",     label:"Transaction Checklist"          },
    { key:"variable_pay",              label:"Variable Pay Register"          },
    { key:"monthly_attendance",        label:"Monthly Attendance Report"      },
];

let _idx            = 0;
let _cache          = {};
let _debounce_timer = null;
let _prefetch_xhr   = null;

function _get_year_options() {
    const y = new Date().getFullYear(), opts = [""];
    for (let i = y-2; i <= y+2; i++) opts.push(String(i));
    return opts;
}

function _filter_key() {
    const f = frappe.query_report.get_values() || {};
    return JSON.stringify([f.year, f.month, JSON.stringify(f.company||[]), f.category||"", JSON.stringify(f.division||[])]);
}

function _ensure_styles() {
    if (document.getElementById("pr-style")) return;
    const s = document.createElement("style"); s.id = "pr-style";
    s.textContent = `
        .pr-bar{display:flex;align-items:center;justify-content:center;gap:12px;
            padding:10px 0 6px;border-bottom:1px solid #e0e4e8;margin:0 15px 4px;}
        .pr-sel{position:relative;display:flex;align-items:center;min-width:280px;}
        .pr-input{width:100%;font-size:12px;font-weight:600;color:#2c3e50;
            border:1px solid #d1d5db;border-radius:5px;padding:5px 28px 5px 10px;
            outline:none;background:#fff;cursor:pointer;text-align:center;transition:border-color .15s;}
        .pr-input:focus{border-color:#5c7cfa;box-shadow:0 0 0 2px rgba(92,124,250,.15);}
        .pr-caret{position:absolute;right:8px;top:50%;transform:translateY(-50%);
            pointer-events:none;color:#888;font-size:10px;}
        .pr-drop{position:absolute;top:calc(100% + 4px);left:0;right:0;background:#fff;
            border:1px solid #d1d5db;border-radius:6px;box-shadow:0 6px 20px rgba(0,0,0,.12);
            z-index:9999;max-height:300px;overflow-y:auto;
            opacity:0;transform:translateY(-4px);pointer-events:none;
            transition:opacity .12s,transform .12s;}
        .pr-drop.open{opacity:1;transform:translateY(0);pointer-events:all;}
        .pr-item{padding:7px 12px;font-size:12px;color:#2c3e50;cursor:pointer;
            white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
        .pr-item:hover,.pr-item:focus{background:#f0f4ff;outline:none;}
        .pr-item.active{background:#e8eeff;font-weight:600;color:#3b5bdb;}
        .pr-item.pr-bank-sub{padding-left:24px;color:#555;font-style:italic;}
        .pr-item.hide{display:none;}
        .pr-empty{padding:8px 12px;font-size:12px;color:#aaa;text-align:center;display:none;}
        .pr-status{font-size:10px;color:#16a34a;margin-left:4px;white-space:nowrap;}
    `;
    document.head.appendChild(s);
}

function _inject_nav(report) {
    if (report.page.wrapper.find(".pr-bar").length) return;
    _ensure_styles();

    const items = REPORTS.map((r,i) => {
        // Visually indent the two bank sub-reports
        const sub = (r.key === "home_bank_advice" || r.key === "other_bank_advice")
            ? " pr-bank-sub" : "";
        return `<div class="pr-item${i===0?" active":""}${sub}" data-i="${i}" tabindex="0">${r.label}</div>`;
    }).join("");

    const bar = $(`
        <div class="pr-bar">
            <button class="btn btn-xs btn-default pr-prev" style="font-size:16px;padding:2px 10px;">&lsaquo;</button>
            <div class="pr-sel">
                <input class="pr-input" type="text" autocomplete="off"
                    value="${REPORTS[0].label}" placeholder="Search…"/>
                <span class="pr-caret">▾</span>
                <div class="pr-drop">
                    ${items}
                    <div class="pr-empty">No results</div>
                </div>
            </div>
            <button class="btn btn-xs btn-default pr-next" style="font-size:16px;padding:2px 10px;">&rsaquo;</button>
            <span class="pr-status"></span>
        </div>
    `);

    const targets = [".frappe-report-filters-section",".filter-section",".standard-filter-section",".page-form"];
    let ok = false;
    for (const sel of targets) {
        const el = report.page.wrapper.find(sel).first();
        if (el.length) { el.before(bar); ok = true; break; }
    }
    if (!ok) report.page.wrapper.find(".report-wrapper").prepend(bar);

    const inp  = bar.find(".pr-input");
    const drop = bar.find(".pr-drop");

    inp.on("focus click", ()=>{ inp.select(); _filt(bar,""); drop.addClass("open"); });
    inp.on("input",       ()=>{ _filt(bar, inp.val()); drop.addClass("open"); });

    bar.on("click",".pr-item", function(){ _go(report, +$(this).data("i")); drop.removeClass("open"); });

    $(document).on("click.pr", e=>{
        if (!bar[0].contains(e.target)){
            drop.removeClass("open");
            inp.val(REPORTS[_idx].label);
        }
    });

    inp.on("keydown", function(e){
        const vis = bar.find(".pr-item:not(.hide)");
        if      (e.key==="Escape")    { drop.removeClass("open"); inp.val(REPORTS[_idx].label); }
        else if (e.key==="Enter")     { const f=vis.first(); if(f.length){_go(report,+f.data("i"));drop.removeClass("open");} }
        else if (e.key==="ArrowDown"){ e.preventDefault(); drop.addClass("open"); vis.first().focus(); }
    });

    drop.on("keydown",".pr-item",function(e){
        const vis=bar.find(".pr-item:not(.hide)"), i=vis.index($(this));
        if      (e.key==="ArrowDown") { e.preventDefault(); vis.eq(i+1).focus(); }
        else if (e.key==="ArrowUp")   { e.preventDefault(); i===0?inp.focus():vis.eq(i-1).focus(); }
        else if (e.key==="Enter")     { _go(report,+$(this).data("i")); drop.removeClass("open"); inp.focus(); }
        else if (e.key==="Escape")    { drop.removeClass("open"); inp.val(REPORTS[_idx].label); inp.focus(); }
    });

    bar.find(".pr-prev").on("click", ()=> _go(report, (_idx-1+REPORTS.length)%REPORTS.length));
    bar.find(".pr-next").on("click", ()=> _go(report, (_idx+1)%REPORTS.length));

    report.page.wrapper.on("change.pr", ".frappe-control input, .frappe-control select", ()=>{
        _cache = {};
        bar.find(".pr-status").text("");
        if (_prefetch_xhr) { _prefetch_xhr.abort?.(); _prefetch_xhr = null; }
        clearTimeout(_debounce_timer);
        _debounce_timer = setTimeout(() => _prefetch_all(bar), 1500);
    });

    $(frappe.query_report).one("after_refresh", ()=> {
        const fk = _filter_key();
        if (!_cache[fk]) _cache[fk] = {};
        _cache[fk][REPORTS[_idx].key] = {
            columns: frappe.query_report.columns,
            result:  frappe.query_report.data
        };
        _prefetch_all(bar);
    });
}

function _prefetch_all(bar) {
    const fk  = _filter_key();
    const f   = frappe.query_report.get_values() || {};

    _prefetch_xhr = frappe.call({
        method: "saral_hr.saral_hr.report.payroll_report.payroll_report.get_all_reports_data",
        args: { filters: JSON.stringify({
            year:     f.year     || "",
            month:    f.month    || "",
            company:  JSON.stringify(f.company  || []),
            category: f.category || "",
            division: JSON.stringify(f.division || []),
        })},
        callback(res) {
            _prefetch_xhr = null;
            if (!res.message) return;
            if (fk !== _filter_key()) return;
            if (!_cache[fk]) _cache[fk] = {};
            Object.assign(_cache[fk], res.message);
            bar.find(".pr-status").text("✓ All ready");
        },
        error() { _prefetch_xhr = null; }
    });
}

function _filt(bar, q) {
    q = q.trim().toLowerCase();
    let n = 0;
    bar.find(".pr-item").each(function(){
        const m = !q || $(this).text().toLowerCase().includes(q);
        $(this).toggleClass("hide", !m);
        if (m) n++;
    });
    bar.find(".pr-empty").toggle(n===0);
}

function _sync(report) {
    const r = REPORTS[_idx], bar = report.page.wrapper.find(".pr-bar");
    bar.find(".pr-input").val(r.label);
    bar.find(".pr-item").removeClass("active").filter(`[data-i="${_idx}"]`).addClass("active");
}

function _go(report, idx) {
    _idx = idx;
    _sync(report);
    frappe.query_report.set_filter_value("report_mode", REPORTS[idx].key);

    const fk     = _filter_key();
    const cached = _cache[fk]?.[REPORTS[idx].key];

    if (cached) {
        const qr = frappe.query_report;
        qr.columns = cached.columns;
        qr.data    = cached.result;
        try {
            qr.render_datatable();
        } catch(_) {
            if (qr.datatable) {
                qr.datatable.refresh(cached.result, cached.columns);
            } else {
                frappe.query_report.refresh();
            }
        }
        return;
    }

    frappe.query_report.refresh();

    $(frappe.query_report).one("after_refresh", ()=> {
        const fk2 = _filter_key();
        if (!_cache[fk2]) _cache[fk2] = {};
        _cache[fk2][REPORTS[idx].key] = {
            columns: frappe.query_report.columns,
            result:  frappe.query_report.data
        };
    });
}

function _set_print_buttons(report) {
    report.page.set_primary_action(__("Print"), _print_current, "printer");
    report.page.wrapper.find(".pr-print-all-btn").remove();
    const btn = $(`<button class="btn btn-default btn-sm pr-print-all-btn" style="margin-left:8px;">${__("Print All")}</button>`);
    report.page.wrapper.find(".page-actions").prepend(btn);
    btn.on("click", ()=> _print_all(btn));
}

function _server_filters() {
    const f = frappe.query_report.get_values() || {};
    return {
        year:        f.year      || "",
        month:       f.month     || "",
        company:     JSON.stringify(f.company   || []),
        category:    f.category  || "",
        division:    JSON.stringify(f.division  || []),
        report_mode: frappe.query_report.get_filter_value("report_mode") || "bank_advice",
    };
}

function _validate() {
    const f = frappe.query_report.get_values() || {};
    if (!f.year || !f.month || !f.company?.length) {
        frappe.msgprint({ title:__("Missing Filters"),
            message:__("Please select Year, Month and Company before printing."), indicator:"orange" });
        return false;
    }
    return true;
}

function _print_current() {
    if (!_validate()) return;
    frappe.dom.freeze(__("Generating PDF..."));
    frappe.call({
        method:"saral_hr.saral_hr.report.payroll_report.payroll_report.print_single_report",
        args:{ filters: JSON.stringify(_server_filters()) },
        callback: r=>{ frappe.dom.unfreeze(); if(r.message) _open_pdf(r.message); },
        error:    ()=>{ frappe.dom.unfreeze();
            frappe.msgprint({ title:__("Error"), message:__("Failed to generate PDF."), indicator:"red" }); }
    });
}

function _print_all(btn) {
    if (!_validate()) return;
    const orig = btn.text();
    btn.prop("disabled",true).text(__("Generating..."));
    frappe.dom.freeze(__("Generating all reports PDF…"));
    const f = _server_filters(); delete f.report_mode;
    frappe.call({
        method:"saral_hr.saral_hr.report.payroll_report.payroll_report.print_all_reports",
        args:{ filters: JSON.stringify(f) },
        callback: r=>{ frappe.dom.unfreeze(); btn.prop("disabled",false).text(orig); if(r.message) _open_pdf(r.message); },
        error:    ()=>{ frappe.dom.unfreeze(); btn.prop("disabled",false).text(orig);
            frappe.msgprint({ title:__("Error"), message:__("Failed to generate PDF."), indicator:"red" }); }
    });
}

function _open_pdf(url) {
    const a = Object.assign(document.createElement("a"),
        { href:frappe.urllib.get_full_url(url), target:"_blank", rel:"noopener noreferrer" });
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
}