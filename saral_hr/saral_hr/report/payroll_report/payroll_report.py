import frappe, json, calendar, io, copy
from frappe import _
from frappe.utils import flt
from frappe.utils.pdf import get_pdf

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

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
    "loan_register":             "saral_hr.saral_hr.report.loan_register.loan_register",
    "advance_register":          "saral_hr.saral_hr.report.advance_register.advance_register",
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
# Excel styling constants
# ---------------------------------------------------------------------------

_XL_TITLE_FG  = "CC0000"
_XL_TITLE_BG  = "FFFFFF"
_XL_SUB_FG    = "333333"
_XL_SUB_BG    = "FFFFFF"
_XL_HDR_FG    = "000000"
_XL_HDR_BG    = "FFFF00"
_XL_ROW_BG    = "FFFFFF"
_XL_ALT_BG    = "F2F2F2"
_XL_TOT_BG    = "D9E1F2"
_XL_TOT_FG    = "1F3864"
_XL_BDR       = "BFBFBF"

_MAR_COLORS = {
    "P":   "C6EFCE",
    "A":   "FFC7CE",
    "HD":  "FFEB9C",
    "T":   "D9D9D9",
    "H":   "C6EFCE",
    "WO":  "BDD7EE",
    "LWP": "E2CCFF",
    "EL":  "FCE4D6",
    "CL":  "CCFFEE",
    "CO":  "EDEDED",
    "ECO": "F4CCCC",
}
_MAR_FG = {
    "P":   "1A6B1A",
    "A":   "C0392B",
    "HD":  "7B4800",
    "T":   "2C3E50",
    "H":   "1A6B1A",
    "WO":  "1A4F7A",
    "LWP": "5B2D8E",
    "EL":  "7D3400",
    "CL":  "0E6655",
    "CO":  "555555",
    "ECO": "7B1818",
}


def _border(color=_XL_BDR, style="thin"):
    s = Side(style=style, color=color)
    return Border(left=s, right=s, top=s, bottom=s)


def _xl_cell(ws, row, col, value,
             bold=False, fg="000000", bg=None,
             align="left", num_fmt=None, wrap=False, italic=False):
    cell = ws.cell(row=row, column=col, value=value)
    cell.font      = Font(name="Arial", size=9, bold=bold, color=fg, italic=italic)
    cell.alignment = Alignment(horizontal=align, vertical="center", wrap_text=wrap)
    cell.border    = _border()
    if bg:
        cell.fill = PatternFill("solid", start_color=bg, fgColor=bg)
    if num_fmt:
        cell.number_format = num_fmt
    return cell


def _is_numeric(col_def):
    ft = (col_def.get("fieldtype") or "").lower()
    fn = (col_def.get("fieldname") or "").lower()
    return ft in ("float", "currency", "int") or fn in (
        "net_salary", "income_tax", "amount", "ded_amount", "oth_amount",
        "gross_salary", "basic", "hra", "pf_amount", "esi_amount",
        "pt_amount", "lwf_amount", "variable_pay",
    )


def _to_num(v):
    if v is None or v == "": return None
    if isinstance(v, (int, float)): return float(v)
    try:
        return float(str(v).replace(",", ""))
    except (ValueError, TypeError):
        return v


def _col_width(col_def):
    lbl = col_def.get("label", "")
    ft  = (col_def.get("fieldtype") or "").lower()
    fn  = (col_def.get("fieldname") or "").lower()
    w   = max(len(lbl) + 3, 10)
    if ft in ("float", "currency", "int"):
        w = max(w, 14)
    if ft == "data" and col_def.get("width", 0) > 200:
        w = max(w, 26)
    if fn.startswith("day_"):
        w = 4
    return min(w, 50)


# ---------------------------------------------------------------------------
# Transaction checklist extra-args helper
# ---------------------------------------------------------------------------

def _register_tc_extra(filters):
    import importlib
    mod = importlib.import_module(
        "saral_hr.saral_hr.report.transaction_checklist.transaction_checklist"
    )
    p = {}
    s, e = mod._date_range(filters)
    if not s:
        return {"earn_comps": [], "emp_ded_comps": [], "empr_comps": []}

    p.update(start_date=s, end_date=e)
    conds = [
        "ss.docstatus=1",
        "ss.start_date>=%(start_date)s",
        "ss.end_date<=%(end_date)s",
    ]
    co = mod._parse_list(filters.get("company"))
    if co:
        p["companies"] = tuple(co)
        conds.append("ss.company IN %(companies)s")

    em_filter = mod._parse_list(filters.get("employee"))
    if em_filter:
        p["employees"] = tuple(em_filter)
        conds.append("ss.employee IN %(employees)s")

    cat = filters.get("category")
    catj = ""
    if cat:
        p["category"] = cat
        catj = ("INNER JOIN `tabCompany Link` cl_cat "
                "ON cl_cat.name=ss.employee AND cl_cat.category=%(category)s")

    divs = mod._parse_list(filters.get("division"))
    if divs:
        p["divisions"] = tuple(divs)
        conds.append(
            "ss.employee IN (SELECT name FROM `tabCompany Link` "
            "WHERE division IN %(divisions)s OR department IN %(divisions)s)"
        )

    w = " AND ".join(conds)
    earn_comps, emp_ded_comps, empr_comps = mod._get_components(w, p)
    return {
        "earn_comps":    earn_comps,
        "emp_ded_comps": emp_ded_comps,
        "empr_comps":    empr_comps,
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
        return importlib.import_module(mod_path)
    except ImportError as e:
        frappe.log_error("_load_module({0}): {1}".format(mode, e), "Payroll Report")
        return None


def _import_execute(mode):
    mod = _load_module(mode)
    return getattr(mod, "execute", None) if mod else None


def _import_build_html(mode):
    mod = _load_module(mode)
    return getattr(mod, "_build_html", None) if mod else None


# ---------------------------------------------------------------------------
# FIX: safe single-report runner that deep-copies results to prevent any
# module-level mutable state from leaking between consecutive calls.
# ---------------------------------------------------------------------------

def _run_report_safe(mode, filters):
    """
    Execute a sub-report and return (columns, data) with deep-copied results.

    Deep-copying is the key fix: if any sub-report module accumulates rows in
    a list defined at module scope (a common pattern in older Frappe reports),
    copy.deepcopy() ensures our caller gets a completely independent snapshot.
    Subsequent calls therefore start clean and never see stale/doubled rows.
    """
    fn = _import_execute(mode)
    if not fn:
        return [], []
    # Always pass a fresh dict so the callee cannot mutate our filters object
    f = dict(filters, report_mode=mode)
    cols, data = fn(f)
    return copy.deepcopy(cols), copy.deepcopy(data)


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

_SIG = """
<!--SIG_START-->
<table style="width:100%;border-collapse:collapse;margin-top:32px;">
  <tr>
    <td style="width:33.33%;text-align:center;padding:0 20px;border:none;">
      <div style="width:160px;margin:0 auto;border-top:1px solid #000;padding-top:5px;
                  font-size:10px;color:#333;">Prepared By</div>
    </td>
    <td style="width:33.33%;text-align:center;padding:0 20px;border:none;">
      <div style="width:160px;margin:0 auto;border-top:1px solid #000;padding-top:5px;
                  font-size:10px;color:#333;">Checked By</div>
    </td>
    <td style="width:33.33%;text-align:center;padding:0 20px;border:none;">
      <div style="width:160px;margin:0 auto;border-top:1px solid #000;padding-top:5px;
                  font-size:10px;color:#333;">Authorised Signatory</div>
    </td>
  </tr>
</table>
<!--SIG_END-->
"""

_SIG_MARKERS = [
    "<!--SIG_START-->",
    '<div class="sig">',
    '<div style="width:100%;margin-top:30px;display:table;">',
]


def _strip_sig(html):
    import re
    body_match = re.search(r'<body[^>]*>(.*)</body>', html, re.DOTALL | re.IGNORECASE)
    if body_match:
        html = body_match.group(1)
    for marker in _SIG_MARKERS:
        idx = html.rfind(marker)
        if idx != -1:
            html = html[:idx]
            break
    return html.strip()


def _render_section(mode, cols, data, co, mo, yr, filters=None):
    build_fn = _import_build_html(mode)

    if build_fn:
        try:
            if mode == "transaction_checklist":
                extra = {}
                if filters:
                    try:
                        extra = _register_tc_extra(filters)
                    except Exception as ex:
                        frappe.log_error(
                            "payroll_report._register_tc_extra: {0}".format(ex),
                            "Payroll Report"
                        )
                raw = build_fn(
                    cols, data, co, mo, yr,
                    extra.get("earn_comps"),
                    extra.get("emp_ded_comps"),
                    extra.get("empr_comps"),
                )
            else:
                raw = build_fn(cols, data, co, mo, yr)

            return _strip_sig(raw)

        except Exception as ex:
            frappe.log_error(
                "payroll_report._render_section({0}): {1}".format(mode, ex),
                "Payroll Report"
            )

    label = REPORT_LABELS.get(mode, mode)
    hdr = (
        '<div class="hdr">'
        '<div class="co">{co}</div>'
        '<div class="ttl">{lbl}</div>'
        '<div class="per">For the Month of {mo} {yr}</div>'
        '</div>'
    ).format(co=co, lbl=label, mo=mo, yr=yr)

    if not cols or not data:
        return hdr + '<p class="nd">No data for this period.</p>'

    thead = "<tr>" + "".join(
        '<th>{0}</th>'.format(c.get("label", c.get("fieldname", "")))
        for c in cols
    ) + "</tr>"

    tbody = ""
    for row in data:
        is_tot = bool(row.get("bold"))
        cls = ' class="tot"' if is_tot else ""
        tbody += "<tr{0}>".format(cls)
        for c in cols:
            fn  = c.get("fieldname", "")
            val = row.get(fn, "")
            tbody += "<td>{0}</td>".format(val if val is not None else "")
        tbody += "</tr>"

    return hdr + "<table><thead>{0}</thead><tbody>{1}</tbody></table>".format(thead, tbody)


def _build_all_html(sections, co, mo, yr, filters=None):
    parts = []
    for i, s in enumerate(sections):
        inner = _render_section(
            s["mode"], s["cols"], s["data"], co, mo, yr, filters=filters
        )
        pb = (
            '<div style="page-break-before:always;font-size:0;line-height:0;height:0;">'
            '</div>'
            if i > 0 else ""
        )
        parts.append(
            '{pb}<div style="page-break-inside:avoid-if-possible;">'
            '{inner}{sig}</div>'.format(pb=pb, inner=inner, sig=_SIG)
        )
    return (
        '<!DOCTYPE html><html>'
        '<head><meta charset="UTF-8">{css}</head>'
        '<body>{body}</body></html>'
    ).format(css=_CSS, body="".join(parts))


def _save_pdf(html, prefix):
    pdf = get_pdf(html, options={
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
    fn  = "{0}_{1}.pdf".format(prefix, ts)
    with open(frappe.utils.get_files_path(fn, is_private=0), "wb") as fh:
        fh.write(pdf)
    doc = frappe.get_doc({
        "doctype":    "File",
        "file_name":  fn,
        "is_private": 0,
        "file_url":   "/files/{0}".format(fn),
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return doc.file_url


# ---------------------------------------------------------------------------
# Whitelisted API methods — PDF
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_all_reports_data(filters):
    """
    FIX: Removed ThreadPoolExecutor entirely.

    Threading was the root cause of the row-doubling bug:
      - Frappe's DB layer (frappe.db) is not thread-safe without explicit
        connection-per-thread management.
      - Sub-reports that accumulate rows into a module-level list shared
        their state across threads, causing N workers × 1 report = N copies
        of rows appearing in the result.

    Sequential execution is safe, predictable, and fast enough for ~16
    reports run once on filter change (prefetch). Each call to
    _run_report_safe() deep-copies its result to fully isolate state.
    """
    if isinstance(filters, str):
        filters = json.loads(filters)

    out = {}
    for mode in REPORTS:
        try:
            cols, data = _run_report_safe(mode, filters)
            out[mode]  = {"columns": cols, "result": data}
        except Exception:
            frappe.log_error(
                "get_all_reports_data: {0}".format(mode), "Payroll Report"
            )
            out[mode] = {"columns": [], "result": []}

    return out


@frappe.whitelist()
def print_single_report(filters):
    if isinstance(filters, str):
        filters = json.loads(filters)

    mode = filters.get("report_mode", "salary_summary")
    cols, data = _run_report_safe(mode, filters)

    if not cols and not data:
        frappe.throw("Unknown report mode or no data: {0}".format(mode))

    co = _company_label(filters)
    mo = filters.get("month", "")
    yr = filters.get("year",  "")

    inner = _render_section(mode, cols, data, co, mo, yr, filters=filters)
    html = (
        '<!DOCTYPE html><html>'
        '<head><meta charset="UTF-8">{css}</head>'
        '<body>{inner}{sig}</body></html>'
    ).format(css=_CSS, inner=inner, sig=_SIG)

    return _save_pdf(html, "Payroll_{0}".format(mode))


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
        try:
            cols, data = _run_report_safe(mode, filters)
        except Exception:
            frappe.log_error(
                "print_selected_reports: {0}".format(mode), "Payroll Report"
            )
            cols, data = [], []
        sections.append({"mode": mode, "cols": cols, "data": data})

    html = _build_all_html(sections, co, mo, yr, filters=filters)
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
        try:
            cols, data = _run_report_safe(mode, filters)
        except Exception:
            frappe.log_error(
                "print_all_reports: {0}".format(mode), "Payroll Report"
            )
            cols, data = [], []
        sections.append({"mode": mode, "cols": cols, "data": data})

    html = _build_all_html(sections, co, mo, yr, filters=filters)
    return _save_pdf(html, "Payroll_All_Reports")


# ---------------------------------------------------------------------------
# Whitelisted API methods — Excel
# ---------------------------------------------------------------------------

@frappe.whitelist()
def excel_single_report(filters):
    if isinstance(filters, str):
        filters = json.loads(filters)

    mode  = filters.get("report_mode", "salary_summary")
    cols, data = _run_report_safe(mode, filters)

    co    = _company_label(filters)
    mo    = filters.get("month", "")
    yr    = filters.get("year",  "")
    label = REPORT_LABELS.get(mode, mode)

    wb = Workbook()
    ws = wb.active
    ws.title = label[:31]
    _write_xl_sheet(ws, cols, data, co, mo, yr, label, mode)

    return _save_excel(wb, "Payroll_{0}".format(mode))


@frappe.whitelist()
def excel_selected_reports(filters):
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

    wb          = Workbook()
    first_sheet = True

    for mode in selected:
        try:
            cols, data = _run_report_safe(mode, filters)
        except Exception:
            frappe.log_error(
                "excel_selected_reports: {0}".format(mode), "Payroll Report"
            )
            cols, data = [], []

        label = REPORT_LABELS.get(mode, mode)
        if first_sheet:
            ws = wb.active
            ws.title = label[:31]
            first_sheet = False
        else:
            ws = wb.create_sheet(title=label[:31])

        _write_xl_sheet(ws, cols, data, co, mo, yr, label, mode)

    return _save_excel(wb, "Payroll_Excel_Reports")


# ---------------------------------------------------------------------------
# Excel sheet writer
# ---------------------------------------------------------------------------

def _write_xl_sheet(ws, cols, data, co, mo, yr, label, mode=""):
    nc = max(len(cols), 1)

    # ── Row 1: Company ──────────────────────────────────────────────────────
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=nc)
    c1 = ws.cell(row=1, column=1, value=(co.upper() if co else ""))
    c1.font      = Font(name="Arial", size=14, bold=True, color=_XL_TITLE_FG)
    c1.fill      = PatternFill("solid", start_color=_XL_TITLE_BG, fgColor=_XL_TITLE_BG)
    c1.alignment = Alignment(horizontal="center", vertical="center")
    c1.border    = Border(bottom=Side(style="medium", color="CC0000"))
    ws.row_dimensions[1].height = 22

    # ── Row 2: Report title ─────────────────────────────────────────────────
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=nc)
    c2 = ws.cell(row=2, column=1, value=label)
    c2.font      = Font(name="Arial", size=11, bold=True, color=_XL_SUB_FG)
    c2.fill      = PatternFill("solid", start_color=_XL_SUB_BG, fgColor=_XL_SUB_BG)
    c2.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[2].height = 18

    # ── Row 3: Period ───────────────────────────────────────────────────────
    ws.merge_cells(start_row=3, start_column=1, end_row=3, end_column=nc)
    c3 = ws.cell(row=3, column=1,
                 value="For the Month of {mo} {yr}".format(mo=mo, yr=yr))
    c3.font      = Font(name="Arial", size=9, color="555555")
    c3.fill      = PatternFill("solid", start_color=_XL_SUB_BG, fgColor=_XL_SUB_BG)
    c3.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[3].height = 14

    # ── Row 4: spacer ───────────────────────────────────────────────────────
    ws.row_dimensions[4].height = 4

    # ── Row 5: Column headers ───────────────────────────────────────────────
    HDR_ROW = 5
    thick_bottom = Border(
        left=Side(style="thin",     color=_XL_BDR),
        right=Side(style="thin",    color=_XL_BDR),
        top=Side(style="thin",      color=_XL_BDR),
        bottom=Side(style="medium", color="000000"),
    )
    for ci, col in enumerate(cols, 1):
        lbl  = col.get("label", col.get("fieldname", ""))
        fn   = col.get("fieldname", "")
        if fn.startswith("day_"):
            lbl = fn.replace("day_", "")
        cell = ws.cell(row=HDR_ROW, column=ci, value=lbl)
        cell.font      = Font(name="Arial", size=9, bold=True, color=_XL_HDR_FG)
        cell.fill      = PatternFill("solid", start_color=_XL_HDR_BG, fgColor=_XL_HDR_BG)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border    = thick_bottom
    ws.row_dimensions[HDR_ROW].height = 28

    # ── Rows 6+: Data ───────────────────────────────────────────────────────
    is_attendance = (mode == "monthly_attendance")

    if not data:
        ws.merge_cells(start_row=6, start_column=1, end_row=6, end_column=nc)
        c = ws.cell(row=6, column=1, value="No data for this period.")
        c.font      = Font(name="Arial", size=9, italic=True, color="888888")
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.fill      = PatternFill("solid", start_color="FAFAFA", fgColor="FAFAFA")
        ws.row_dimensions[6].height = 20
    else:
        for ri, row in enumerate(data, 6):
            is_tot  = bool(row.get("bold"))
            row_bg  = _XL_TOT_BG if is_tot else (_XL_ALT_BG if ri % 2 == 0 else _XL_ROW_BG)
            row_fg  = _XL_TOT_FG if is_tot else "000000"

            for ci, col in enumerate(cols, 1):
                fn  = col.get("fieldname", "")
                val = row.get(fn, "")

                if is_attendance and fn.startswith("day_"):
                    sval    = str(val).strip() if val else ""
                    cell_bg = _MAR_COLORS.get(sval, row_bg)
                    cell_fg = _MAR_FG.get(sval, row_fg)
                    c = ws.cell(row=ri, column=ci, value=sval if sval else "")
                    c.font      = Font(name="Arial", size=8, bold=bool(sval), color=cell_fg)
                    c.fill      = PatternFill("solid", start_color=cell_bg, fgColor=cell_bg)
                    c.alignment = Alignment(horizontal="center", vertical="center")
                    c.border    = _border()
                    continue

                if fn == "sr_no":
                    _xl_cell(ws, ri, ci,
                             "" if (is_tot or not val) else val,
                             bold=is_tot, fg=row_fg, bg=row_bg, align="center")

                elif _is_numeric(col):
                    nv = _to_num(val)
                    if val == "On Hold":
                        _xl_cell(ws, ri, ci, "On Hold",
                                 bold=False, fg="C0392B", bg=row_bg,
                                 align="center", italic=True)
                    elif isinstance(nv, float):
                        _xl_cell(ws, ri, ci, nv,
                                 bold=is_tot, fg=row_fg, bg=row_bg,
                                 align="right", num_fmt="#,##0.00")
                    else:
                        _xl_cell(ws, ri, ci,
                                 nv if nv is not None else "",
                                 bold=is_tot, fg=row_fg, bg=row_bg, align="right")

                else:
                    _xl_cell(ws, ri, ci,
                             val if val is not None else "",
                             bold=is_tot, fg=row_fg, bg=row_bg, align="left")

            ws.row_dimensions[ri].height = 13 if is_attendance else 15

    # ── Column widths ────────────────────────────────────────────────────────
    for ci, col in enumerate(cols, 1):
        ws.column_dimensions[get_column_letter(ci)].width = _col_width(col)

    # ── Freeze panes below header ────────────────────────────────────────────
    ws.freeze_panes = "A6"

    # ── Sheet tab colour ─────────────────────────────────────────────────────
    TAB_COLORS = {
        "salary_summary":   "2563EB",
        "provident_fund":   "16A34A",
        "esi_register":     "DC2626",
        "professional_tax": "7C3AED",
        "monthly_attendance": "D97706",
        "home_bank_advice": "0891B2",
        "other_bank_advice":"0891B2",
        "income_tax":       "BE123C",
    }
    tc = TAB_COLORS.get(mode)
    if tc:
        ws.sheet_properties.tabColor = tc

    # ── Auto-filter on header row ────────────────────────────────────────────
    if cols:
        ws.auto_filter.ref = "{a}5:{b}5".format(
            a=get_column_letter(1),
            b=get_column_letter(nc),
        )


def _save_excel(wb, prefix):
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    ts  = frappe.utils.now_datetime().strftime("%Y%m%d_%H%M%S")
    fn  = "{prefix}_{ts}.xlsx".format(prefix=prefix, ts=ts)
    with open(frappe.utils.get_files_path(fn, is_private=0), "wb") as fh:
        fh.write(buf.read())

    doc = frappe.get_doc({
        "doctype":    "File",
        "file_name":  fn,
        "is_private": 0,
        "file_url":   "/files/{fn}".format(fn=fn),
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return doc.file_url