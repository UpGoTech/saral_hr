import frappe, json, calendar
from frappe import _
from frappe.utils import flt
from frappe.utils.pdf import get_pdf

# ---------------------------------------------------------------------------
# Report registry
# ---------------------------------------------------------------------------

REPORT_MODULE_MAP = {
    "home_bank_advice":          "saral_hr.saral_hr.report.bank_advice.bank_advice",
    "other_bank_advice":         "saral_hr.saral_hr.report.other_bank_advice.other_bank_advice",
    "educational_allowance":     "saral_hr.saral_hr.report.educational_allowance_register.educational_allowance_register",
    "esi_register":              "saral_hr.saral_hr.report.esi_register.esi_register",
    "labour_welfare_fund":       "saral_hr.saral_hr.report.labour_welfare_fund_register.labour_welfare_fund_register",
    "monthly_attendance":        "saral_hr.saral_hr.report.monthly_attendance_report.monthly_attendance_report",
    "professional_tax":          "saral_hr.saral_hr.report.professional_tax_register.professional_tax_register",
    "provident_fund":            "saral_hr.saral_hr.report.provident_fund_register.provident_fund_register",
    "retention_deposit":         "saral_hr.saral_hr.report.retention_deposit_register.retention_deposit_register",
    "salary_summary":            "saral_hr.saral_hr.report.salary_summary.salary_summary",
    "salary_summary_individual": "saral_hr.saral_hr.report.salary_summary_individual_employee.salary_summary_individual_employee",
    "transaction_checklist":     "saral_hr.saral_hr.report.transaction_checklist.transaction_checklist",
    "variable_pay":              "saral_hr.saral_hr.report.variable_pay_register.variable_pay_register",
    "income_tax":                "saral_hr.saral_hr.report.income_tax_report.income_tax_report",
}

REPORT_LABELS = {
    "home_bank_advice":          "Home Bank Advice",
    "other_bank_advice":         "Other Bank Advice",
    "educational_allowance":     "Educational Allowance Register",
    "esi_register":              "ESI Register",
    "labour_welfare_fund":       "Labour Welfare Fund Register",
    "monthly_attendance":        "Monthly Attendance Report",
    "professional_tax":          "Professional Tax Register",
    "provident_fund":            "Provident Fund Register",
    "retention_deposit":         "Retention Deposit Register",
    "salary_summary":            "Salary Summary",
    "salary_summary_individual": "Salary Summary — Individual",
    "transaction_checklist":     "Transaction Checklist",
    "variable_pay":              "Variable Pay Register",
    "income_tax":                "Income Tax Register",
}

REPORTS = [
    "salary_summary",
    "transaction_checklist",
    "salary_summary_individual",
    "provident_fund",
    "esi_register",
    "professional_tax",
    "retention_deposit",
    "educational_allowance",
    "variable_pay",
    "labour_welfare_fund",
    "other_bank_advice",
    "home_bank_advice",
    "monthly_attendance",
    "income_tax",
]

MONTH_MAP = {
    "January":1,"February":2,"March":3,"April":4,"May":5,"June":6,
    "July":7,"August":8,"September":9,"October":10,"November":11,"December":12,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_list(v):
    if not v: return []
    if isinstance(v, list): return v
    try:
        p = json.loads(v)
        if isinstance(p, list): return p
    except Exception: pass
    return [x.strip() for x in v.split(",") if x.strip()]

def _company_label(f):
    c = _parse_list(f.get("company"))
    return ", ".join(c) if c else (frappe.defaults.get_global_default("company") or "")

def _load_module(mode):
    mod_path = REPORT_MODULE_MAP.get(mode)
    if not mod_path:
        return None
    try:
        import importlib
        mod = importlib.import_module(mod_path)
        return mod
    except ImportError as e:
        frappe.log_error(f"_load_module({mode}): {e}", "Payroll Report")
        return None

def _import_execute(mode):
    mod = _load_module(mode)
    return getattr(mod, "execute", None) if mod else None

def _import_print_html(mode):
    mod = _load_module(mode)
    return getattr(mod, "_build_html", None) if mod else None


# ---------------------------------------------------------------------------
# Frappe report entry-point
# ---------------------------------------------------------------------------

def execute(filters=None):
    f    = filters or {}
    mode = f.get("report_mode", "salary_summary")
    fn   = _import_execute(mode)
    if not fn:
        return [], []
    return fn(f)


# ---------------------------------------------------------------------------
# PDF helpers
# ---------------------------------------------------------------------------

_CSS = """<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Arial,sans-serif;font-size:10px;color:#000;background:#fff;width:100%;}
.sec{page-break-after:always;padding:6px 4px}
.sec:last-child{page-break-after:avoid}
.hdr{text-align:center;border-bottom:2px solid #000;padding:8px 4px 6px;margin-bottom:6px}
.hdr .co{font-size:18px;font-weight:900;letter-spacing:1px;text-transform:uppercase}
.hdr .ttl{font-size:13px;font-weight:700;margin-top:3px}
.hdr .per{font-size:11px;margin-top:2px}
table{width:100%;border-collapse:collapse;margin-top:6px}
th{border:1px solid #000;padding:5px 7px;font-size:10px;font-weight:700;background:#f0f0f0;color:#000;white-space:nowrap}
td{border:1px solid #000;padding:5px 7px;font-size:10px;vertical-align:middle;color:#000}
tr.tot td{background:#e8e8e8;font-weight:700}
.r{text-align:right}.l{text-align:left}.c{text-align:center}
.nd{text-align:center;padding:18px;color:#888;font-size:10px}
.hold{color:#c0392b;font-style:italic}
</style>"""

# FIX: use inline styles with a unique sentinel comment so _strip_sig
# can reliably find and remove this block regardless of which report
# generated its own _SIG variant.
_SIG = """
<!--SIG_START-->
<div style="display:flex;justify-content:space-between;
            width:100%;margin-top:24px;padding-top:8px;
            box-sizing:border-box;">
    <div style="text-align:center;width:180px;">
        <div style="border-top:1px solid #000;margin-bottom:4px;"></div>
        <div style="font-size:13px;color:#333;">Prepared By</div>
    </div>
    <div style="text-align:center;width:180px;">
        <div style="border-top:1px solid #000;margin-bottom:4px;"></div>
        <div style="font-size:13px;color:#333;">Checked By</div>
    </div>
    <div style="text-align:center;width:180px;">
        <div style="border-top:1px solid #000;margin-bottom:4px;"></div>
        <div style="font-size:13px;color:#333;">Authorised Signatory</div>
    </div>
</div>
<!--SIG_END-->
"""

# Sentinel used by _strip_sig — works for BOTH old class-based and
# new inline-style _SIG blocks from all sub-reports
_SIG_MARKERS = [
    "<!--SIG_START-->",   # new inline style (this file + updated sub-reports)
    '<div class="sig">',  # old class-based (any sub-report not yet updated)
]


def _strip_sig(html):
    """
    Strip the signature block and everything after it from a sub-report's
    HTML body content. Handles both old class-based and new inline-style sigs.
    """
    import re

    # Extract body content
    body_match = re.search(r'<body[^>]*>(.*)</body>', html, re.DOTALL | re.IGNORECASE)
    if body_match:
        html = body_match.group(1)

    # Try each known sig marker, strip from the last occurrence
    for marker in _SIG_MARKERS:
        idx = html.rfind(marker)
        if idx != -1:
            html = html[:idx]
            break

    return html.strip()


def _render_section(mode, cols, data, co, mo, yr):
    """
    Delegate to sub-report's _build_html(), strip its signature block,
    return clean inner HTML only. payroll_report adds its own _SIG after.
    """
    build_fn = _import_print_html(mode)
    if build_fn:
        try:
            if mode == "income_tax":
                raw = build_fn(cols, data, {"company": co, "month": mo, "year": yr})
            else:
                raw = build_fn(cols, data, co, mo, yr)
            return _strip_sig(raw)
        except Exception:
            frappe.log_error(f"payroll_report._render_section: {mode}", "Payroll Report")
    return f'<p style="color:#888;padding:12px;">Could not render {REPORT_LABELS.get(mode, mode)}</p>'


def _build_all_html(sections, co, mo, yr):
    parts = []
    for s in sections:
        inner = _render_section(s["mode"], s["cols"], s["data"], co, mo, yr)
        # Each section gets exactly ONE signature block
        parts.append(f'<div class="sec">{inner}{_SIG}</div>')
    return (
        f'<!DOCTYPE html><html>'
        f'<head><meta charset="UTF-8">{_CSS}</head>'
        f'<body>{"".join(parts)}</body></html>'
    )


def _save_pdf(html, prefix):
    from frappe.utils.pdf import get_pdf as _get_pdf
    pdf = _get_pdf(html, options={
        "page-size":     "A4",
        "orientation":   "Landscape",
        "margin-top":    "8mm",
        "margin-right":  "8mm",
        "margin-bottom": "8mm",
        "margin-left":   "8mm",
        "encoding":      "UTF-8",
        "no-outline":    None,
    })
    ts  = frappe.utils.now_datetime().strftime("%Y%m%d_%H%M%S")
    fn  = f"{prefix}_{ts}.pdf"
    with open(frappe.utils.get_files_path(fn, is_private=0), "wb") as fh:
        fh.write(pdf)
    doc = frappe.get_doc({
        "doctype":    "File",
        "file_name":  fn,
        "is_private": 0,
        "file_url":   f"/files/{fn}",
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return doc.file_url


# ---------------------------------------------------------------------------
# Whitelisted API methods
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_all_reports_data(filters):
    if isinstance(filters, str):
        filters = json.loads(filters)

    out = {}

    try:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def _run(mode):
            fn = _import_execute(mode)
            if not fn:
                return mode, {"columns": [], "result": []}
            try:
                frappe.db.connect()
                cols, data = fn(dict(filters, report_mode=mode))
                return mode, {"columns": cols, "result": data}
            except Exception:
                frappe.log_error(f"get_all_reports_data: {mode}", "Payroll Report")
                return mode, {"columns": [], "result": []}

        with ThreadPoolExecutor(max_workers=4) as ex:
            futures = {ex.submit(_run, m): m for m in REPORTS}
            for fut in as_completed(futures):
                mode, res = fut.result()
                out[mode]  = res

    except Exception:
        for mode in REPORTS:
            fn = _import_execute(mode)
            if not fn:
                out[mode] = {"columns": [], "result": []}
                continue
            try:
                cols, data = fn(dict(filters, report_mode=mode))
                out[mode]  = {"columns": cols, "result": data}
            except Exception:
                frappe.log_error(f"get_all_reports_data: {mode}", "Payroll Report")
                out[mode]  = {"columns": [], "result": []}

    return out


@frappe.whitelist()
def print_single_report(filters):
    if isinstance(filters, str):
        filters = json.loads(filters)

    mode = filters.get("report_mode", "salary_summary")
    fn   = _import_execute(mode)
    if not fn:
        frappe.throw(f"Unknown report mode: {mode}")

    cols, data = fn(filters)
    co = _company_label(filters)
    mo = filters.get("month", "")
    yr = filters.get("year",  "")

    inner = _render_section(mode, cols, data, co, mo, yr)
    # ONE signature block added here after the stripped content
    html = (
        f'<!DOCTYPE html><html>'
        f'<head><meta charset="UTF-8">{_CSS}</head>'
        f'<body>{inner}{_SIG}</body></html>'
    )

    return _save_pdf(html, f"Payroll_{mode}")


@frappe.whitelist()
def print_selected_reports(filters):
    if isinstance(filters, str):
        filters = json.loads(filters)

    selected = filters.pop("selected_reports", None)
    if selected and isinstance(selected, str):
        selected = json.loads(selected)
    if not selected:
        frappe.throw("No reports selected")

    co = _company_label(filters)
    mo = filters.get("month", "")
    yr = filters.get("year",  "")

    sections = []
    for mode in selected:
        fn = _import_execute(mode)
        if not fn:
            continue
        try:
            cols, data = fn(dict(filters, report_mode=mode))
        except Exception:
            frappe.log_error(f"print_selected_reports: {mode}", "Payroll Report")
            cols, data = [], []
        sections.append({"mode": mode, "cols": cols, "data": data})

    html = _build_all_html(sections, co, mo, yr)
    return _save_pdf(html, "Payroll_Selected_Reports")


@frappe.whitelist()
def print_all_reports(filters):
    if isinstance(filters, str):
        filters = json.loads(filters)

    co = _company_label(filters)
    mo = filters.get("month", "")
    yr = filters.get("year",  "")

    sections = []
    for mode in REPORTS:
        fn = _import_execute(mode)
        if not fn:
            continue
        try:
            cols, data = fn(dict(filters, report_mode=mode))
        except Exception:
            frappe.log_error(f"print_all_reports: {mode}", "Payroll Report")
            cols, data = [], []
        sections.append({"mode": mode, "cols": cols, "data": data})

    html = _build_all_html(sections, co, mo, yr)
    return _save_pdf(html, "Payroll_All_Reports")