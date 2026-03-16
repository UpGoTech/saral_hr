import frappe, json, calendar
from frappe import _
from frappe.utils import flt
from frappe.utils.pdf import get_pdf

# ---------------------------------------------------------------------------
# Report registry — maps mode key → (report module path, execute function name)
# Each sub-report is its own standalone script report.
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
}

# Order used for Print All — matches the nav pill sequence
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
    """
    Load a sub-report module using Frappe's import mechanism.
    Falls back to importlib if frappe.get_attr is unavailable.
    """
    mod_path = REPORT_MODULE_MAP.get(mode)
    if not mod_path:
        return None
    try:
        # frappe.get_attr resolves dotted paths correctly inside apps
        # We just need the module, so strip the function name if present
        import importlib
        mod = importlib.import_module(mod_path)
        return mod
    except ImportError as e:
        frappe.log_error(f"_load_module({mode}): {e}", "Payroll Report")
        return None


def _import_execute(mode):
    """Return the execute() function for a sub-report module."""
    mod = _load_module(mode)
    return getattr(mod, "execute", None) if mod else None


def _import_print_html(mode):
    """Return the _build_html() function for a sub-report module."""
    mod = _load_module(mode)
    return getattr(mod, "_build_html", None) if mod else None

def _run_report(mode, filters):
    """Run a sub-report's execute() and return (cols, data). Safe — never raises."""
    fn = _import_execute(mode)
    if not fn:
        return [], []
    try:
        return fn(dict(filters, report_mode=mode))
    except Exception:
        frappe.log_error(f"payroll_report: {mode}", "Payroll Report")
        return [], []


# ---------------------------------------------------------------------------
# Frappe report entry-point
# ---------------------------------------------------------------------------

def execute(filters=None):
    f    = filters or {}
    mode = f.get("report_mode", "home_bank_advice")
    fn   = _import_execute(mode)
    if not fn:
        return [], []
    return fn(f)


# ---------------------------------------------------------------------------
# PDF CSS + signature (shared across all sub-report PDFs)
# ---------------------------------------------------------------------------

_CSS = """<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Arial,sans-serif;font-size:10px;color:#000;background:#fff}
.sec{page-break-after:always;padding:6px 4px}
.sec:last-child{page-break-after:avoid}
.hdr{text-align:center;border-bottom:2px solid #000;padding:8px 4px 6px;margin-bottom:6px}
.hdr .co{font-size:18px;font-weight:900;letter-spacing:1px;text-transform:uppercase}
.hdr .ttl{font-size:13px;font-weight:700;margin-top:3px}
.hdr .per{font-size:11px;margin-top:2px}
.sig{display:flex;justify-content:space-between;margin-top:24px;padding-top:6px}
.sig-b{text-align:center;width:160px}
.sig-l{border-top:1px solid #000;margin-bottom:3px}
.sig-t{font-size:10px;color:#333}
table{width:100%;border-collapse:collapse;margin-top:6px}
th{border:1px solid #000;padding:5px 7px;font-size:10px;font-weight:700;background:#f0f0f0;color:#000;white-space:nowrap}
td{border:1px solid #000;padding:5px 7px;font-size:10px;vertical-align:middle;color:#000}
tr.tot td{background:#e8e8e8;font-weight:700}
.r{text-align:right}.l{text-align:left}.c{text-align:center}
.nd{text-align:center;padding:18px;color:#888;font-size:10px}
.hold{color:#c0392b;font-style:italic}
</style>"""

_SIG = '<div class="sig">' + "".join(
    f'<div class="sig-b"><div class="sig-l"></div><div class="sig-t">{l}</div></div>'
    for l in ["Prepared By", "Checked By", "Authorised Signatory"]
) + '</div>'


_SIG_MARKER = '<div class="sig">'


def _strip_sig(html):
    """
    Remove the standalone signature block + outer HTML shell from a sub-report's
    _build_html() output so the payroll wrapper can add exactly one _SIG per section.
    """
    import re
    # Pull body content out of full HTML document if present
    body_match = re.search(r'<body[^>]*>(.*)</body>', html, re.DOTALL | re.IGNORECASE)
    if body_match:
        html = body_match.group(1)
    # Chop off the last sig block (and everything after it)
    idx = html.rfind(_SIG_MARKER)
    if idx != -1:
        html = html[:idx]
    return html.strip()


def _render_section(mode, cols, data, co, mo, yr):
    """Delegate rendering to the sub-report's _build_html(), then strip its shell/sig."""
    build_fn = _import_print_html(mode)
    if build_fn:
        try:
            raw = build_fn(cols, data, co, mo, yr)
            return _strip_sig(raw)
        except Exception:
            frappe.log_error(f"payroll_report._render_section: {mode}", "Payroll Report")
    return f'<p style="color:#888;padding:12px;">Could not render {REPORT_LABELS.get(mode, mode)}</p>'


def _build_all_html(sections, co, mo, yr):
    parts = []
    for s in sections:
        inner = _render_section(s["mode"], s["cols"], s["data"], co, mo, yr)
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
# Whitelisted API methods called from payroll_report.js
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_all_reports_data(filters):
    """
    Pre-fetch data for all sub-reports in parallel (falls back to sequential).
    Returns dict: { mode: { columns, result } }
    """
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
            from concurrent.futures import as_completed
            for fut in as_completed(futures):
                mode, res = fut.result()
                out[mode]  = res

    except Exception:
        # Sequential fallback
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
    """Generate a PDF for the currently active sub-report tab."""
    if isinstance(filters, str):
        filters = json.loads(filters)

    mode = filters.get("report_mode", "home_bank_advice")
    fn   = _import_execute(mode)
    if not fn:
        frappe.throw(f"Unknown report mode: {mode}")

    cols, data = fn(filters)
    co = _company_label(filters)
    mo = filters.get("month", "")
    yr = filters.get("year",  "")

    # _render_section strips the sub-report shell + its own _SIG
    inner = _render_section(mode, cols, data, co, mo, yr)
    html  = (
        f'<!DOCTYPE html><html>'
        f'<head><meta charset="UTF-8">{_CSS}</head>'
        f'<body>{inner}{_SIG}</body></html>'
    )

    return _save_pdf(html, f"Payroll_{mode}")


@frappe.whitelist()
def print_selected_reports(filters):
    """Generate a single PDF for a user-chosen subset of reports."""
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
    """Generate a single PDF containing every sub-report, one per page."""
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