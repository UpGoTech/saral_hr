import frappe, json, calendar, math
from frappe import _
from frappe.utils import flt, getdate, add_months
from frappe.utils.pdf import get_pdf

# ============================================================
# CONSTANTS
# ============================================================

MONTH_MAP = {
    "January":1,"February":2,"March":3,"April":4,"May":5,"June":6,
    "July":7,"August":8,"September":9,"October":10,"November":11,"December":12
}

PT_SLABS = [
    {"label":"Upto Rs. 2,000",          "min":0,     "max":2000,  "rate":0},
    {"label":"Rs. 2,001 to Rs. 2,500",  "min":2001,  "max":2500,  "rate":0},
    {"label":"Rs. 2,501 to Rs. 3,500",  "min":2501,  "max":3500,  "rate":60},
    {"label":"Rs. 3,501 to Rs. 7,500",  "min":3501,  "max":7500,  "rate":120},
    {"label":"Rs. 7,501 to Rs. 10,000", "min":7501,  "max":10000, "rate":175},
    {"label":"Above Rs. 10,000",        "min":10001, "max":None,  "rate":200},
]

PF_WAGE_CEILING = 15000.0

EARNING_COMPONENTS = [
    ("Basic","BASIC"),("Dearness Allowance","DA"),("House Rent Allowance","HRA"),
    ("Conveyance Allowance","CONV"),("Medical Allowance","MED"),("Education Allowance","EDU"),
    ("Other Allowance","OA"),("Variable Pay","VAR"),("Arrears","ARREARS"),
]

DEDUCTION_COMPONENTS = [
    ("Employee -  PF","PF"),("Employer -  PF","EPF"),("Employee - ESIC","ESI"),
    ("Employer -  ESIC","EESI"),("Professional Tax","PT"),
    ("Employee -Labour Welfare Fund","Employee - LWF"),("Employer - Labour Welfare Fund","Employer - LWF"),
    ("Employee -Bonus","BONUS"),("Employer - Bonus","Employer - bonus"),
    ("Employer - Gratuity","GRAT"),("Loan","Loan"),("Advance","ADV"),
    ("Retention","RET"),("Other Deduction - 1","OD -1"),
]

# bank_advice removed; home/other kept as first-class reports
REPORTS = [
    "home_bank_advice",
    "other_bank_advice",
    "educational_allowance","esi_register","labour_welfare_fund",
    "professional_tax","provident_fund","retention_deposit","salary_summary",
    "salary_summary_individual","transaction_checklist","variable_pay","monthly_attendance",
]

REPORT_LABELS = {
    "home_bank_advice":          "Home Bank Advice",
    "other_bank_advice":         "Other Bank Advice",
    "educational_allowance":     "Educational Allowance Register",
    "esi_register":              "ESI Register",
    "labour_welfare_fund":       "Labour Welfare Fund Register",
    "professional_tax":          "Professional Tax Register",
    "provident_fund":            "Provident Fund Register",
    "retention_deposit":         "Retention Deposit Register",
    "salary_summary":            "Salary Summary",
    "salary_summary_individual": "Salary Summary — Individual",
    "transaction_checklist":     "Transaction Checklist",
    "variable_pay":              "Variable Pay Register",
    "monthly_attendance":        "Monthly Attendance Report",
}

# ============================================================
# ATTENDANCE PAGE LAYOUT CONSTANTS — A4 @ 96dpi, margin 15mm
# ============================================================
PAGE_H_PX      = 1122
PAGE_MARGIN_TB = 114
H_CO_BLOCK     = 100
H_LEGEND       = 29
H_COL_HDR      = 35
H_HEADER       = H_CO_BLOCK + H_LEGEND + H_COL_HDR
H_EMP_ROW      = 58
H_TOTAL_ROW    = 30
BODY_PX        = PAGE_H_PX - PAGE_MARGIN_TB - H_HEADER
ROWS_FIRST_PAGE  = math.floor((BODY_PX - H_TOTAL_ROW) / H_EMP_ROW)
ROWS_OTHER_PAGES = math.floor(BODY_PX / H_EMP_ROW)


# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def _parse_list(value):
    if not value: return []
    if isinstance(value, list): return value
    try:
        p = json.loads(value)
        if isinstance(p, list): return p
    except Exception: pass
    return [v.strip() for v in value.split(",") if v.strip()]

def _sanitize(abbr):
    return abbr.strip().lower().replace(" ","_").replace("-","_").replace("__","_")

def _fmt(val):
    if val is None or val == "" or val is False: return ""
    try: return f"{float(val):,.2f}"
    except (TypeError, ValueError): return str(val)

def _company_label(filters):
    c = _parse_list(filters.get("company"))
    return ", ".join(c) if c else (frappe.defaults.get_global_default("company") or "")

def _start_date(filters):
    m = MONTH_MAP.get(filters.get("month", ""))
    y = filters.get("year", "")
    return f"{y}-{m:02d}-01" if m and y else None

def _date_range(filters):
    m = MONTH_MAP.get(filters.get("month", ""))
    y = int(filters.get("year", 0) or 0)
    if not m or not y: return None, None
    return f"{y}-{m:02d}-01", f"{y}-{m:02d}-{calendar.monthrange(y, m)[1]:02d}"

def _base_conditions(filters, params, alias="ss"):
    conds = [f"{alias}.docstatus = 1"]
    sd = _start_date(filters)
    if sd:
        params["start_date"] = sd
        conds.append(f"{alias}.start_date = %(start_date)s")
    companies = _parse_list(filters.get("company"))
    if companies:
        params["companies"] = tuple(companies)
        conds.append(f"{alias}.company IN %(companies)s")
    employees = _parse_list(filters.get("employee"))
    if employees:
        params["employees"] = tuple(employees)
        conds.append(f"{alias}.employee IN %(employees)s")
    return " AND ".join(conds)

def _category_join(filters, params, emp_col="ss.employee"):
    cat = filters.get("category")
    if not cat: return ""
    params["category"] = cat
    return f"INNER JOIN `tabCompany Link` cl_cat ON cl_cat.name = {emp_col} AND cl_cat.category = %(category)s"

def _division_condition(filters, params):
    divs = _parse_list(filters.get("division"))
    if not divs: return ""
    params["divisions"] = tuple(divs)
    return " AND ss.employee IN (SELECT name FROM `tabCompany Link` WHERE division IN %(divisions)s OR department IN %(divisions)s)"

def _pt_slab(gross):
    for s in PT_SLABS:
        if s["max"] is None and gross >= s["min"]: return s
        if s["max"] and s["min"] <= gross <= s["max"]: return s
    return PT_SLABS[0]

def _col(label, fieldname, fieldtype="Data", width=130, **kw):
    return {"label": _(label), "fieldname": fieldname, "fieldtype": fieldtype, "width": width, **kw}

def _get_company_bank_map(companies):
    if not companies: return {}
    return {
        r.name: (r.bank_name or "").strip().lower()
        for r in frappe.db.get_all(
            "Company",
            filters={"name": ["in", list(companies)]},
            fields=["name", "bank_name"]
        )
    }

def _get_on_hold_employees(filters):
    """Return set of employee IDs that are on salary hold for the given month/year."""
    month, year = filters.get("month", ""), filters.get("year", "")
    if not month or not year: return set()
    records = frappe.db.sql("""
        SELECT employee FROM `tabEmployee Salary Hold`
        WHERE status = 'On Hold' AND docstatus = 1
          AND month = %(month)s AND year = %(year)s
    """, {"month": month, "year": year}, as_dict=1)
    return {r.employee for r in records}

def _fetch_slip_components(slip_names, parentfield):
    """Bulk-fetch salary component amounts for a list of slip names."""
    if not slip_names: return {}
    result = {}
    for r in frappe.db.sql(
        "SELECT sd.parent AS slip, sd.salary_component AS comp, sd.amount "
        "FROM `tabSalary Details` sd "
        "WHERE sd.parent IN %(sn)s AND sd.parentfield = %(pf)s",
        {"sn": tuple(slip_names), "pf": parentfield}, as_dict=1
    ):
        result.setdefault(r["slip"], {})[r["comp"]] = r["amount"]
    return result


# ============================================================
# MAIN ENTRY POINTS
# ============================================================

def execute(filters=None):
    filters = filters or {}
    fn = ROUTER.get(filters.get("report_mode", "home_bank_advice"))
    return fn(filters) if fn else ([], [])


@frappe.whitelist()
def print_single_report(filters):
    if isinstance(filters, str): filters = json.loads(filters)
    mode = filters.get("report_mode", "home_bank_advice")
    fn   = ROUTER.get(mode)
    if not fn: frappe.throw(f"Unknown report mode: {mode}")
    cols, data = fn(filters)
    html = _build_print_html(
        [{"title": REPORT_LABELS.get(mode, mode), "columns": cols, "data": data, "mode": mode}],
        _company_label(filters), filters.get("month", ""), filters.get("year", "")
    )
    page_size = "A3" if mode in ("monthly_attendance","provident_fund","salary_summary_individual","transaction_checklist") else "A4"
    return _save_pdf(html, f"Payroll_{mode}", page_size)


@frappe.whitelist()
def get_all_reports_data(filters):
    if isinstance(filters, str): filters = json.loads(filters)
    out = {}
    try:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def run_report(mode):
            fn = ROUTER.get(mode)
            if not fn: return mode, {"columns": [], "result": []}
            try:
                frappe.db.connect()
                cols, data = fn(dict(filters, report_mode=mode))
                return mode, {"columns": cols, "result": data}
            except Exception:
                frappe.log_error(f"Error in get_all_reports_data (parallel): {mode}", "Payroll Report")
                return mode, {"columns": [], "result": []}

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(run_report, mode): mode for mode in REPORTS}
            for future in as_completed(futures):
                mode, result = future.result()
                out[mode] = result
    except Exception:
        for mode in REPORTS:
            fn = ROUTER.get(mode)
            if not fn:
                out[mode] = {"columns": [], "result": []}
                continue
            try:
                cols, data = fn(dict(filters, report_mode=mode))
                out[mode] = {"columns": cols, "result": data}
            except Exception:
                frappe.log_error(f"Error in get_all_reports_data: {mode}", "Payroll Report")
                out[mode] = {"columns": [], "result": []}
    return out


@frappe.whitelist()
def print_all_reports(filters):
    if isinstance(filters, str): filters = json.loads(filters)
    company, month, year = _company_label(filters), filters.get("month", ""), filters.get("year", "")
    sections = []
    for mode in REPORTS:
        fn = ROUTER.get(mode)
        if not fn: continue
        try:
            cols, data = fn(dict(filters, report_mode=mode))
        except Exception:
            frappe.log_error(f"Error running report {mode}", "Payroll Print All")
            cols, data = [], []
        sections.append({"title": REPORT_LABELS.get(mode, mode), "columns": cols, "data": data, "mode": mode})
    has_wide = any(s["mode"] in ("monthly_attendance","provident_fund","salary_summary_individual","transaction_checklist") for s in sections)
    page_size = "A3" if has_wide else "A4"
    return _save_pdf(_build_print_html(sections, company, month, year), "Payroll_All_Reports", page_size)


# ============================================================
# PDF SAVE
# ============================================================

def _save_pdf(html, name_prefix, page_size="A4"):
    pdf = get_pdf(html, options={
        "page-size": page_size, "orientation": "Landscape",
        "margin-top": "8mm", "margin-right": "6mm",
        "margin-bottom": "8mm", "margin-left": "6mm",
        "encoding": "UTF-8", "no-outline": None,
    })
    ts       = frappe.utils.now_datetime().strftime("%Y%m%d_%H%M%S")
    filename = f"{name_prefix}_{ts}.pdf"
    with open(frappe.utils.get_files_path(filename, is_private=0), "wb") as f:
        f.write(pdf)
    doc = frappe.get_doc({
        "doctype": "File", "file_name": filename,
        "is_private": 0, "file_url": f"/files/{filename}"
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return doc.file_url


# ============================================================
# HTML / CSS
# ============================================================

_BASE_CSS = """<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Arial,sans-serif;font-size:8px;color:#000}
.report-section{page-break-after:always;padding:8px}
.report-section:last-child{page-break-after:avoid}
.rpt-header{text-align:center;border-bottom:2px solid #000;padding:10px 4px 6px;margin-bottom:8px;background:#fff}
.rpt-header .co-name{font-size:26px;font-weight:900;letter-spacing:1px;text-transform:uppercase;color:#000}
.rpt-header .rpt-title{font-size:16px;font-weight:700;margin-top:4px;color:#000}
.rpt-header .rpt-period{font-size:13px;color:#000;margin-top:3px}
.rpt-tbl{width:100%;border-collapse:collapse;margin-top:6px;font-size:7.5px}
.rpt-tbl th{border:1px solid #000;padding:3px 4px;text-align:center;font-size:7px;font-weight:700;background:#ffffff;white-space:nowrap}
.rpt-tbl td{border:1px solid #ccc;padding:2.5px 4px}
.rpt-tbl .r{text-align:right}.rpt-tbl .c{text-align:center}
.rpt-tbl tr.tot td{border-top:1.5px solid #000;border-bottom:1.5px solid #000;font-weight:700;background:#ffffff}
.rpt-tbl tr:nth-child(even):not(.tot){background:#ffffff}
.ss-wrap{display:table;width:100%;border-spacing:6px 0}
.ss-col{display:table-cell;width:50%;vertical-align:top}
.ss-head{font-size:8px;font-weight:700;text-align:center;border:1px solid #000;background:#ffffff;padding:3px}
.ss-gt{display:flex;justify-content:space-between;border:1px solid #000;background:#ffffff;padding:3px 5px;font-size:8px;font-weight:700}
.ss-other-head{font-size:8px;font-weight:700;border:1px solid #000;background:#ffffff;padding:3px 5px;margin-top:8px}
.sig-strip{display:flex;justify-content:space-between;margin-top:30px}
.sig-box{text-align:center;width:150px}
.sig-line{border-top:1px solid #000;margin-bottom:3px}
.sig-label{font-size:13px;color:#555}
</style>"""

_SELF_HEADER_MODES = {"monthly_attendance", "home_bank_advice", "other_bank_advice"}


def _build_print_html(sections, company, month, year):
    sig_html = "".join(
        f'<div class="sig-box"><div class="sig-line"></div><div class="sig-label">{l}</div></div>'
        for l in ["Prepared By", "Checked By", "Authorised Signatory"]
    )
    parts = []
    for s in sections:
        inner = _render_section(s["mode"], s["columns"], s["data"], company, month, year)
        if s["mode"] in _SELF_HEADER_MODES:
            shell = f'{inner}<div class="sig-strip">{sig_html}</div>'
        else:
            shell = (
                f'<div class="rpt-header">'
                f'<div class="co-name">{company}</div>'
                f'<div class="rpt-title">{s["title"]}</div>'
                f'<div class="rpt-period">For the Month of {month} {year}</div>'
                f'</div>{inner}<div class="sig-strip">{sig_html}</div>'
            )
        parts.append(f'<div class="report-section">{shell}</div>')
    return (
        f"<!DOCTYPE html><html><head><meta charset='UTF-8'>{_BASE_CSS}</head>"
        f"<body>{''.join(parts)}</body></html>"
    )


def _render_section(mode, columns, data, company="", month="", year=""):
    dispatch = {
        "professional_tax":          lambda c, d: _render_large_table(c, d, skip_total_cols={"pt_rate"}),
        "provident_fund":            lambda c, d: _render_pf(c, d),
        "salary_summary":            _render_salary_summary,
        "salary_summary_individual": lambda c, d: _render_salary_summary_individual(c, d),
        "transaction_checklist":     lambda c, d: _render_transaction_checklist(c, d),
        "home_bank_advice":          lambda c, d: _render_bank_advice(c, d, company, month, year, "Home Bank Advice"),
        "other_bank_advice":         lambda c, d: _render_bank_advice(c, d, company, month, year, "Other Bank Advice"),
        "monthly_attendance":        lambda c, d: _render_attendance(c, d, company, month, year),
        "educational_allowance":     lambda c, d: _render_large_table(c, d),
        "esi_register":              lambda c, d: _render_large_table(c, d),
        "labour_welfare_fund":       lambda c, d: _render_large_table(c, d),
        "retention_deposit":         lambda c, d: _render_large_table(c, d),
        "variable_pay":              lambda c, d: _render_large_table(c, d),
    }
    return dispatch.get(mode, _render_generic)(columns, data)


# ============================================================
# GENERIC TABLE HELPERS
# ============================================================

def _tbl(thead, rows):
    return f'<table class="rpt-tbl"><thead>{thead}</thead><tbody>{"".join(rows)}</tbody></table>'

def _thead(columns):
    return "<tr>" + "".join(f'<th>{c.get("label","")}</th>' for c in columns) + "</tr>"

def _td_val(c, val):
    if val is None or val == "": return "<td></td>"
    if c.get("fieldtype") in ("Float","Currency","Int","Percent"):
        return f'<td class="r">{_fmt(val)}</td>'
    return f'<td>{val}</td>'

def _render_generic(columns, data):
    if not data:
        return '<p style="color:#888;padding:10px;font-size:8px;text-align:center;">No data</p>'
    rows = []
    for i, row in enumerate(data):
        is_tot = row.get("bold") or row.get("_row_type") in ("total", "grand_total")
        cls    = ' class="tot"' if is_tot else (' style="background:#ffffff"' if i % 2 else "")
        cells  = "".join(_td_val(c, row.get(c.get("fieldname", ""))) for c in columns)
        rows.append(f"<tr{cls}>{cells}</tr>")
    return _tbl(_thead(columns), rows)


# ============================================================
# SPECIFIC RENDERERS
# ============================================================

def _render_pf(columns, data):
    if not data:
        return '<p style="color:#888;padding:10px;font-size:8px;text-align:center;">No data</p>'

    SKIP_TOTAL    = {"pf_no","uan_no","days","absent","date_of_joining","date_of_birth"}
    NUMERIC_TYPES = ("Float","Currency","Int","Percent")
    display_cols  = [c for c in columns if c["fieldname"] != "employee_id"]

    th_l = "border:1px solid #999;padding:6px 8px;font-size:13px;font-weight:700;background:#fff;color:#000;text-align:left;white-space:nowrap;"
    th_r = "border:1px solid #999;padding:6px 8px;font-size:13px;font-weight:700;background:#fff;color:#000;text-align:right;white-space:nowrap;"
    td_l = "border:1px solid #ccc;padding:6px 8px;font-size:14px;vertical-align:middle;color:#000;text-align:left;"
    td_r = "border:1px solid #ccc;padding:6px 8px;font-size:14px;vertical-align:middle;color:#000;text-align:right;"
    ts_l = "border:1px solid #888;padding:12px 8px;font-size:14px;font-weight:700;background:#ffffff;color:#000;text-align:left;"
    ts_r = "border:1px solid #888;padding:12px 8px;font-size:14px;font-weight:700;background:#ffffff;color:#000;text-align:right;"

    thead = '<tr style="background:#fff;">'
    for c in display_cols:
        fn, label = c.get("fieldname",""), c.get("label","")
        is_num    = c.get("fieldtype") in NUMERIC_TYPES
        if fn == "employee_name":
            thead += (
                f'<th style="{th_l}min-width:160px;">Employee Name'
                f'<div style="font-size:11px;font-weight:600;color:#555;margin-top:3px;">Employee ID</div></th>'
            )
        elif fn in ("date_of_joining","date_of_birth"):
            thead += f'<th style="{th_l}min-width:100px;white-space:nowrap;">{label}</th>'
        else:
            thead += f'<th style="{th_r if is_num else th_l}">{label}</th>'
    thead += '</tr>'

    rows_html = ""
    for row in data:
        is_tot = row.get("bold") or row.get("_row_type") in ("total","grand_total")
        tr = ""
        for c in display_cols:
            fn, val   = c.get("fieldname",""), row.get(c.get("fieldname",""), "")
            is_num    = c.get("fieldtype") in NUMERIC_TYPES
            tl, tr_s  = (ts_l, ts_r) if is_tot else (td_l, td_r)
            if fn == "employee_name":
                emp_id = row.get("employee_id","")
                if is_tot:
                    tr += f'<td style="{ts_l}font-weight:700;">{val or ""}</td>'
                else:
                    tr += (
                        f'<td style="{tl}"><span style="font-weight:700;">{val or ""}</span>'
                        f'<div style="font-size:13px;font-weight:500;color:#444;margin-top:3px;">{emp_id}</div></td>'
                    )
            elif is_tot and fn in SKIP_TOTAL:
                tr += f'<td style="{tr_s}"></td>'
            elif fn in ("date_of_joining","date_of_birth"):
                tr += f'<td style="{tl}min-width:100px;white-space:nowrap;">{val or ""}</td>'
            elif is_num:
                tr += f'<td style="{tr_s}">{_fmt(val) if val not in ("",None) else ""}</td>'
            else:
                tr += f'<td style="{tl}">{val or ""}</td>'
        rows_html += f'<tr>{tr}</tr>'

    return (
        '<table style="width:100%;border-collapse:collapse;table-layout:auto;margin-top:8px;">'
        '<thead>' + thead + '</thead><tbody>' + rows_html + '</tbody></table>'
    )


def _render_salary_summary(columns, data):
    if not data: return ""

    earn_rows = [r for r in data if r.get("_row_type") == "component" and r.get("description")]
    ded_rows  = [r for r in data if r.get("_row_type") == "component" and r.get("ded_description")]
    grand     = next((r for r in data if r.get("_row_type") == "grand_total"), {})
    others    = [r for r in data if r.get("_row_type") == "other"]

    sec_head = "background:#000;color:#fff;font-size:16px;font-weight:700;text-align:center;padding:8px 10px;border:1px solid #000;"
    th_l     = "border:1px solid #999;padding:8px 10px;font-size:15px;font-weight:700;background:#ffffff;color:#000;text-align:left;"
    th_r     = "border:1px solid #999;padding:8px 10px;font-size:15px;font-weight:700;background:#ffffff;color:#000;text-align:right;width:160px;"
    td_l     = "border:1px solid #ccc;padding:7px 10px;font-size:14px;color:#000;text-align:left;"
    td_r     = "border:1px solid #ccc;padding:7px 10px;font-size:14px;color:#000;text-align:right;"
    tot_l    = "border:1px solid #888;padding:8px 10px;font-size:15px;font-weight:700;background:#ffffff;color:#000;text-align:left;"
    tot_r    = "border:1px solid #888;padding:8px 10px;font-size:15px;font-weight:700;background:#ffffff;color:#000;text-align:right;"
    oth_head = "background:#000;color:#fff;font-size:16px;font-weight:700;text-align:center;padding:8px 10px;border:1px solid #000;width:100%;"

    def mini_table(rows_data, desc_key, amt_key, grand_amt):
        header = f'<thead><tr><th style="{th_l}">Description</th><th style="{th_r}">Amount</th></tr></thead>'
        body   = "".join(
            f'<tr><td style="{td_l}">{r.get(desc_key) or ""}</td>'
            f'<td style="{td_r}">{_fmt(r.get(amt_key)) if r.get(amt_key) is not None else ""}</td></tr>'
            for r in rows_data
        )
        body += f'<tr><td style="{tot_l}">Grand Total</td><td style="{tot_r}">{_fmt(grand_amt)}</td></tr>'
        return f'<table style="width:100%;border-collapse:collapse;">{header}<tbody>{body}</tbody></table>'

    other_body = "".join(
        f'<tr><td style="{td_l}">{r.get("description") or ""}</td>'
        f'<td style="{td_r}">{_fmt(r.get("amount")) if r.get("amount") is not None else ""}</td></tr>'
        for r in others
    )
    earn_tbl = mini_table(earn_rows, "description",     "amount",     grand.get("amount"))
    ded_tbl  = mini_table(ded_rows,  "ded_description", "ded_amount", grand.get("ded_amount"))

    return f"""
<table style="width:100%;border-collapse:collapse;margin-top:8px;">
  <thead><tr>
    <th style="{sec_head}">EARNINGS</th>
    <th style="width:20px;border:none;background:#fff;"></th>
    <th style="{sec_head}">DEDUCTIONS</th>
  </tr></thead>
  <tbody><tr>
    <td style="vertical-align:top;padding:0;border:none;">{earn_tbl}</td>
    <td style="width:20px;border:none;background:#fff;"></td>
    <td style="vertical-align:top;padding:0;border:none;">{ded_tbl}</td>
  </tr></tbody>
</table>
<div style="display:flex;justify-content:center;margin-top:20px;">
  <table style="width:50%;border-collapse:collapse;">
    <thead>
      <tr><th colspan="2" style="{oth_head}">OTHER DETAILS</th></tr>
      <tr><th style="{th_l}">Description</th><th style="{th_r}">Amount</th></tr>
    </thead>
    <tbody>{other_body}</tbody>
  </table>
</div>
"""


def _render_large_table(columns, data, skip_total_cols=None):
    if not data:
        return '<p style="color:#888;padding:10px;font-size:8px;text-align:center;">No data</p>'

    skip_total_cols = skip_total_cols or set()
    NUMERIC_TYPES   = ("Float","Currency","Int","Percent")

    th_l = "border:1px solid #999;padding:8px 10px;font-size:16px;font-weight:700;background:#fff;color:#000;text-align:left;"
    th_r = "border:1px solid #999;padding:8px 10px;font-size:16px;font-weight:700;background:#fff;color:#000;text-align:right;"
    td_l = "border:1px solid #ccc;padding:8px 10px;font-size:15px;vertical-align:middle;color:#000;text-align:left;"
    td_r = "border:1px solid #ccc;padding:8px 10px;font-size:15px;vertical-align:middle;color:#000;text-align:right;"
    ts_l = "border:1px solid #888;padding:8px 10px;font-size:15px;font-weight:700;background:#ffffff;color:#000;text-align:left;"
    ts_r = "border:1px solid #888;padding:8px 10px;font-size:15px;font-weight:700;background:#ffffff;color:#000;text-align:right;"

    thead = '<tr style="background:#fff;">' + "".join(
        f'<th style="{th_r if c.get("fieldtype") in NUMERIC_TYPES else th_l}">{c.get("label","")}</th>'
        for c in columns
    ) + '</tr>'

    rows_html = ""
    for row in data:
        is_tot = row.get("bold") or row.get("_row_type") in ("total","grand_total")
        tr = ""
        for c in columns:
            fn, val = c.get("fieldname",""), row.get(c.get("fieldname",""), "")
            is_num  = c.get("fieldtype") in NUMERIC_TYPES
            tl, ts  = (ts_l, ts_r) if is_tot else (td_l, td_r)
            if is_tot and fn in skip_total_cols:
                tr += f'<td style="{ts}"></td>'
            elif is_num:
                tr += f'<td style="{ts}">{_fmt(val) if val not in ("",None) else ""}</td>'
            else:
                tr += f'<td style="{tl}">{val or ""}</td>'
        rows_html += f'<tr>{tr}</tr>'

    return (
        '<table style="width:100%;border-collapse:collapse;table-layout:auto;margin-top:8px;">'
        '<thead>' + thead + '</thead><tbody>' + rows_html + '</tbody></table>'
    )


# ============================================================
# _render_salary_summary_individual
# ============================================================

_LABEL_SHORT = {
    "Basic": "Basic", "Dearness Allowance": "DA", "House Rent Allowance": "HRA",
    "Conveyance Allowance": "Conv.", "Medical Allowance": "Medical",
    "Education Allowance": "Edu. Allow.", "Other Allowance": "Other Allow.",
    "Variable Pay": "Var. Pay", "Arrears": "Arrears",
    "Employee -  PF": "Emp. PF", "Employer -  PF": "Empr. PF",
    "Employee - ESIC": "Emp. ESIC", "Employer -  ESIC": "Empr. ESIC",
    "Professional Tax": "Prof. Tax",
    "Employee -Labour Welfare Fund": "Emp. LWF",
    "Employer - Labour Welfare Fund": "Empr. LWF",
    "Employee -Bonus": "Emp. Bonus", "Employer - Bonus": "Empr. Bonus",
    "Variable Pay (VAR %)": "Var. Pay",
}

def _short_label(label):
    base = label.split('(')[0].strip()
    return _LABEL_SHORT.get(base, base) or "&nbsp;"

_SSI_STYLE_TH   = "border:1px solid #000;padding:8px 2px;font-size:13px;font-weight:700;text-align:center;background:#fff;line-height:1.4;"
_SSI_STYLE_TD   = "border:1px solid #000;padding:8px 4px;font-size:15px;vertical-align:middle;background:#fff;line-height:1.4;"
_SSI_DIV_SUB    = "margin-top:12px;font-size:15px;"
_SSI_DIV_SUB_TH = "margin-top:8px;font-size:13px;"

_SSI_HIDE_FIELDS = {
    "earn_grat","ded_grat","ded_loan","ded_adv","ded_ret",
    "net_salary","total_earnings","total_deductions","absent_days",
}

def _render_salary_summary_individual(columns, data):
    if not data: return ""

    od1_fn = next(
        (c["fieldname"] for c in columns
         if "other" in c["label"].lower() and "deduction" in c["label"].lower()),
        None
    )
    hide = _SSI_HIDE_FIELDS | ({od1_fn} if od1_fn else set())
    filtered  = [c for c in columns if c["fieldname"] not in hide]
    earn_cols = [c for c in filtered if c["fieldname"].startswith("earn_")]
    ded_cols  = [c for c in filtered if c["fieldname"].startswith("ded_")]
    max_pairs = max(len(earn_cols), len(ded_cols))

    html  = '<table style="width:100%;border-collapse:collapse;border:1px solid #000;table-layout:fixed;">'
    html += '<thead><tr>'
    html += f'<th style="{_SSI_STYLE_TH} width:230px;">Employee Name<div style="{_SSI_DIV_SUB_TH}">Employee ID</div></th>'
    html += f'<th style="{_SSI_STYLE_TH} width:70px;">Days</th>'
    html += f'<th style="{_SSI_STYLE_TH} width:70px;">Absent<div style="{_SSI_DIV_SUB_TH}">LWP</div></th>'
    for i in range(max_pairs):
        e_lbl = _short_label(earn_cols[i]["label"]) if i < len(earn_cols) else "&nbsp;"
        d_lbl = _short_label(ded_cols[i]["label"])  if i < len(ded_cols)  else "&nbsp;"
        html += f'<th style="{_SSI_STYLE_TH} min-width:65px;">{e_lbl}<div style="{_SSI_DIV_SUB_TH}">{d_lbl}</div></th>'
    html += f'<th style="{_SSI_STYLE_TH} width:130px;">Empr. Gratuity<div style="{_SSI_DIV_SUB_TH}">Loan</div></th>'
    html += f'<th style="{_SSI_STYLE_TH} width:95px;">Advance<div style="{_SSI_DIV_SUB_TH}">Retention</div></th>'
    html += f'<th style="{_SSI_STYLE_TH} width:110px;">Other Ded. - 1<div style="{_SSI_DIV_SUB_TH}">Net Salary</div></th>'
    html += f'<th style="{_SSI_STYLE_TH} width:150px;">Total Earnings<div style="{_SSI_DIV_SUB_TH}">Total Deductions</div></th>'
    html += '</tr></thead><tbody>'

    for row in data:
        is_tot = row.get("bold") == 1
        fw = "font-weight:bold;" if is_tot else ""
        html += f'<tr style="{fw}">'
        html += (
            f'<td style="{_SSI_STYLE_TD}">'
            f'<span style="font-weight:700;">{row.get("employee_name","")}</span>'
            f'<div style="{_SSI_DIV_SUB}">{row.get("employee","")}</div></td>'
        )
        html += f'<td style="{_SSI_STYLE_TD} text-align:center;">{row.get("payment_days","")}</td>'
        html += (
            f'<td style="{_SSI_STYLE_TD} text-align:center;">'
            f'{row.get("absent_days") or "0"}'
            f'<div style="{_SSI_DIV_SUB}">{_fmt(row.get("total_lwp")) or "0"}</div></td>'
        )
        for i in range(max_pairs):
            e_val = _fmt(row.get(earn_cols[i]["fieldname"])) if i < len(earn_cols) else ""
            d_val = _fmt(row.get(ded_cols[i]["fieldname"]))  if i < len(ded_cols)  else ""
            html += (
                f'<td style="{_SSI_STYLE_TD} text-align:right;">'
                f'{e_val or "&nbsp;"}<div style="{_SSI_DIV_SUB}">{d_val or "&nbsp;"}</div></td>'
            )
        html += (
            f'<td style="{_SSI_STYLE_TD} text-align:right;">'
            f'{_fmt(row.get("earn_grat")) or "&nbsp;"}'
            f'<div style="{_SSI_DIV_SUB}">{_fmt(row.get("ded_loan")) or "&nbsp;"}</div></td>'
        )
        html += (
            f'<td style="{_SSI_STYLE_TD} text-align:right;">'
            f'{_fmt(row.get("ded_adv")) or "&nbsp;"}'
            f'<div style="{_SSI_DIV_SUB}">{_fmt(row.get("ded_ret")) or "&nbsp;"}</div></td>'
        )
        od1_val = _fmt(row.get(od1_fn)) if od1_fn else ""
        html += (
            f'<td style="{_SSI_STYLE_TD} text-align:right;">'
            f'{od1_val or "&nbsp;"}'
            f'<div style="{_SSI_DIV_SUB}">{_fmt(row.get("net_salary"))}</div></td>'
        )
        html += (
            f'<td style="{_SSI_STYLE_TD} text-align:right;">'
            f'{_fmt(row.get("total_earnings"))}'
            f'<div style="{_SSI_DIV_SUB}">{_fmt(row.get("total_deductions"))}</div></td>'
        )
        html += '</tr>'

    return html + "</tbody></table>"


def _render_transaction_checklist(columns, data):
    if not data: return ""

    od1_fn = next(
        (c["fieldname"] for c in columns
         if c["fieldname"].startswith("ded_") and "od" in c["fieldname"]),
        None
    )
    LAST_FIELDS = {"earn_grat","ded_grat","ded_loan","ded_adv","ded_ret","net_salary","total_earnings","total_deductions"}
    if od1_fn: LAST_FIELDS.add(od1_fn)

    earn_cols = [c for c in columns if c["fieldname"].startswith("earn_") and c["fieldname"] not in LAST_FIELDS]
    ded_cols  = [c for c in columns if c["fieldname"].startswith("ded_")  and c["fieldname"] not in LAST_FIELDS]
    max_pairs = max(len(earn_cols), len(ded_cols))

    colgroup  = '<colgroup><col style="width:230px"/><col style="width:70px"/><col style="width:55px"/>'
    colgroup += "".join('<col/>' for _ in range(max_pairs))
    colgroup += '<col style="width:130px"/><col style="width:95px"/><col style="width:110px"/><col style="width:150px"/></colgroup>'

    html  = '<table style="width:100%;border-collapse:collapse;border:1px solid #000;table-layout:fixed;">'
    html += colgroup + '<thead><tr>'
    html += f'<th style="{_SSI_STYLE_TH}">Employee Name<div style="{_SSI_DIV_SUB_TH}">Employee ID</div></th>'
    html += f'<th style="{_SSI_STYLE_TH}">Days</th>'
    html += f'<th style="{_SSI_STYLE_TH}">Absent<div style="{_SSI_DIV_SUB_TH}">LWP</div></th>'
    for i in range(max_pairs):
        e_lbl = _short_label(earn_cols[i]["label"]) if i < len(earn_cols) else "&nbsp;"
        d_lbl = _short_label(ded_cols[i]["label"])  if i < len(ded_cols)  else "&nbsp;"
        html += f'<th style="{_SSI_STYLE_TH}">{e_lbl}<div style="{_SSI_DIV_SUB_TH}">{d_lbl}</div></th>'
    html += f'<th style="{_SSI_STYLE_TH}">Empr. Gratuity<div style="{_SSI_DIV_SUB_TH}">Loan</div></th>'
    html += f'<th style="{_SSI_STYLE_TH}">Advance<div style="{_SSI_DIV_SUB_TH}">Retention</div></th>'
    html += f'<th style="{_SSI_STYLE_TH}">Other Ded. - 1<div style="{_SSI_DIV_SUB_TH}">Net Salary</div></th>'
    html += f'<th style="{_SSI_STYLE_TH}">Total Earnings<div style="{_SSI_DIV_SUB_TH}">Total Deductions</div></th>'
    html += '</tr></thead><tbody>'

    for row in data:
        is_tot = row.get("bold") == 1
        fw = "font-weight:bold;" if is_tot else ""
        html += f'<tr style="{fw}">'
        html += (
            f'<td style="{_SSI_STYLE_TD}">'
            f'<span style="font-weight:700;">{row.get("employee_name","")}</span>'
            f'<div style="{_SSI_DIV_SUB}">{row.get("employee","")}</div></td>'
        )
        html += f'<td style="{_SSI_STYLE_TD} text-align:center;">{row.get("payment_days","")}</td>'
        html += (
            f'<td style="{_SSI_STYLE_TD} text-align:center;">'
            f'{row.get("absent_days") or "0"}'
            f'<div style="{_SSI_DIV_SUB}">{_fmt(row.get("total_lwp")) or "0"}</div></td>'
        )
        for i in range(max_pairs):
            e_fn  = earn_cols[i]["fieldname"] if i < len(earn_cols) else None
            d_fn  = ded_cols[i]["fieldname"]  if i < len(ded_cols)  else None
            e_val = _fmt(row.get(e_fn)) if e_fn else ""
            d_val = _fmt(row.get(d_fn)) if d_fn else ""
            html += (
                f'<td style="{_SSI_STYLE_TD} text-align:right;">'
                f'{e_val or "&nbsp;"}<div style="{_SSI_DIV_SUB}">{d_val or "&nbsp;"}</div></td>'
            )
        html += (
            f'<td style="{_SSI_STYLE_TD} text-align:right;">'
            f'{_fmt(row.get("earn_grat")) or "&nbsp;"}'
            f'<div style="{_SSI_DIV_SUB}">{_fmt(row.get("ded_loan")) or "&nbsp;"}</div></td>'
        )
        html += (
            f'<td style="{_SSI_STYLE_TD} text-align:right;">'
            f'{_fmt(row.get("ded_adv")) or "&nbsp;"}'
            f'<div style="{_SSI_DIV_SUB}">{_fmt(row.get("ded_ret")) or "&nbsp;"}</div></td>'
        )
        od1_val = _fmt(row.get(od1_fn)) if od1_fn else ""
        html += (
            f'<td style="{_SSI_STYLE_TD} text-align:right;">'
            f'{od1_val or "&nbsp;"}'
            f'<div style="{_SSI_DIV_SUB}">{_fmt(row.get("net_salary"))}</div></td>'
        )
        html += (
            f'<td style="{_SSI_STYLE_TD} text-align:right;">'
            f'{_fmt(row.get("total_earnings"))}'
            f'<div style="{_SSI_DIV_SUB}">{_fmt(row.get("total_deductions"))}</div></td>'
        )
        html += '</tr>'

    return html + "</tbody></table>"


def _render_bank_advice(columns, data, company="", month="", year="", report_title="Bank Advice"):
    if not data:
        return '<p style="color:#888;padding:10px;font-size:8px;text-align:center;">No data</p>'

    rows      = [r for r in data if not r.get("bold")]
    total_row = next((r for r in data if r.get("bold")), {})

    COL_WIDTHS = {
        "employee_id": 90, "employee_name": 180, "ifsc_code": 110,
        "account_number": 160, "net_salary": 100, "bank_name": 150,
    }
    colgroup = "<colgroup>" + "".join(
        f'<col style="width:{COL_WIDTHS.get(c.get("fieldname",""), c.get("width",120))}px"/>'
        for c in columns
    ) + "</colgroup>"

    th_l = "border:1px solid #999;padding:8px 10px;font-size:16px;font-weight:700;background:#fff;color:#000;text-align:left;"
    th_r = "border:1px solid #999;padding:8px 10px;font-size:16px;font-weight:700;background:#fff;color:#000;text-align:right;"
    td_l = "border:1px solid #ccc;padding:8px 10px;font-size:15px;vertical-align:middle;color:#000;text-align:left;"
    td_r = "border:1px solid #ccc;padding:8px 10px;font-size:15px;vertical-align:middle;color:#000;text-align:right;font-weight:600;"
    ts_l = "border:1px solid #888;padding:8px 10px;font-size:15px;font-weight:700;background:#ffffff;color:#000;text-align:left;"
    ts_r = "border:1px solid #888;padding:8px 10px;font-size:15px;font-weight:700;background:#ffffff;color:#000;text-align:right;"

    def _header_block():
        return (
            f'<div style="text-align:center;padding:10px 4px 6px;border-bottom:2px solid #000;background:#fff;">'
            f'<div style="font-size:26px;font-weight:900;letter-spacing:1px;text-transform:uppercase;color:#000;">{company}</div>'
            f'<div style="font-size:16px;font-weight:700;margin-top:4px;color:#000;">{report_title}</div>'
            f'<div style="font-size:13px;color:#000;margin-top:3px;">For the Month of {month} {year}</div>'
            f'</div>'
        )

    def _col_header_row():
        return '<tr style="background:#fff;">' + "".join(
            f'<th style="{th_r if c.get("fieldname") == "net_salary" else th_l}">{c.get("label","")}</th>'
            for c in columns
        ) + '</tr>'

    def _data_row(row):
        tr = ""
        for c in columns:
            fn, val = c.get("fieldname",""), row.get(c.get("fieldname",""), "")
            if fn == "net_salary":
                if val == "On Hold":
                    tr += f'<td style="{td_r}color:#c0392b;font-style:italic;">On Hold</td>'
                else:
                    tr += f'<td style="{td_r}">{_fmt(val)}</td>'
            else:
                tr += f'<td style="{td_l}">{val or ""}</td>'
        return f'<tr>{tr}</tr>'

    def _total_html():
        tr = "".join(
            (f'<td style="{ts_r}">{_fmt(total_row.get(c.get("fieldname",""), ""))}</td>'
             if c.get("fieldname") == "net_salary"
             else f'<td style="{ts_l}">{"Total" if c.get("fieldname") == "employee_name" else ""}</td>')
            for c in columns
        )
        return f'<tr>{tr}</tr>'

    BANK_ROWS_FIRST = 20
    BANK_ROWS_OTHER = 25
    pages, idx, first = [], 0, True
    while idx < len(rows):
        limit = BANK_ROWS_FIRST if first else BANK_ROWS_OTHER
        pages.append(rows[idx: idx + limit])
        idx += limit; first = False
    if not pages: pages = [[]]

    html = ""
    for page_no, page_rows in enumerate(pages):
        is_last = (page_no == len(pages) - 1)
        if page_no > 0:
            html += '<div style="page-break-before:always;-webkit-page-break-before:always;"></div>'
        html += _header_block()
        html += (
            '<table style="width:100%;border-collapse:collapse;table-layout:fixed;margin-top:8px;">'
            + colgroup + '<thead>' + _col_header_row() + '</thead><tbody>'
        )
        for row in page_rows:
            html += _data_row(row)
        if is_last and total_row:
            html += _total_html()
        html += '</tbody></table>'
    return html


def _render_attendance(columns, data, company="", month="", year=""):
    if not data:
        return '<p style="color:#888;padding:10px;font-size:8px;text-align:center;">No data</p>'

    rows      = [r for r in data if not r.get("_is_total")]
    total_row = next((r for r in data if r.get("_is_total")), {})
    day_cols  = [c for c in columns if c["fieldname"].startswith("day_")]

    SUMM_GROUPS  = [
        ("present_days","absent_days","half_days"),
        ("working_days","weekly_off_days","holiday_days"),
        ("lwp_days","absent_lwp",None),
    ]
    GROUP_HEADERS = ["P / A / HD", "WD / WO / H", "LWP / A+LWP"]

    def _sv(row, fn):
        if fn is None: return ""
        v = row.get(fn)
        if v is None or v == "" or v == 0 or v == 0.0: return ""
        return str(int(v)) if isinstance(v, float) and v == int(v) else str(v)

    def _summ_cell(row, grp, bg, is_total=False):
        base  = "border:1px solid #888;background:#ffffff;" if is_total else f"border:1px solid #ccc;background:{bg};"
        lines = "".join(
            (f'<div style="font-size:13px;line-height:{H_EMP_ROW//3}px;">&nbsp;</div>' if fn is None
             else f'<div style="font-size:13px;font-weight:900;color:#000;text-align:center;line-height:{H_EMP_ROW//3}px;">'
                  f'{_sv(row, fn) or "–"}</div>')
            for fn in grp
        )
        return (
            f'<td style="{base}height:{H_EMP_ROW}px;vertical-align:middle;padding:0 1px;text-align:center;overflow:hidden;">'
            f'{lines}</td>'
        )

    colgroup  = '<colgroup><col style="width:118px"/>'
    colgroup += "".join('<col style="width:22px"/>' for _ in day_cols)
    colgroup += "".join('<col style="width:38px"/>' for _ in range(3))
    colgroup += '</colgroup>'

    TH   = "border:1px solid #999;padding:2px 1px;text-align:center;font-weight:700;background:#fff;"
    TH_N = "border:1px solid #999;padding:2px 5px;text-align:left;font-weight:700;background:#fff;"

    def _header_block():
        co = (
            f'<div style="text-align:center;padding:10px 4px 6px;border-bottom:2px solid #000;background:#fff;">'
            f'<div style="font-size:26px;font-weight:900;letter-spacing:1px;text-transform:uppercase;color:#000;">{company}</div>'
            f'<div style="font-size:16px;font-weight:700;margin-top:4px;color:#000;">Monthly Attendance Report</div>'
            f'<div style="font-size:13px;color:#000;margin-top:3px;">For the Month of {month} {year}</div></div>'
        )
        legend = "".join(
            f'<span style="display:inline-block;margin-right:18px;font-size:13px;font-weight:600;color:#000;">'
            f'<b>{k}</b><span style="font-weight:400;"> – {lbl}</span></span>'
            for k, lbl in [("P","Present"),("A","Absent"),("WO","Weekly Off"),("H","Holiday"),("LWP","LWP"),("HD","Half Day")]
        )
        return co + f'<div style="padding:7px 10px;border-bottom:2px solid #000;background:#fff;">{legend}</div>'

    def _col_header_row():
        r  = '<tr style="background:#fff;">'
        r += (
            f'<th style="{TH_N}vertical-align:middle;">'
            f'<div style="font-size:12px;font-weight:700;line-height:1.2;">Employee Name</div>'
            f'<div style="font-size:11px;font-weight:600;color:#000;margin-top:1px;line-height:1.2;">Employee ID</div></th>'
        )
        for c in day_cols:
            r += f'<th style="{TH}font-size:11px;">{c["label"]}</th>'
        for gh in GROUP_HEADERS:
            inner = "".join(
                f'<div style="font-size:10px;font-weight:700;line-height:1.5;text-align:center;">{p}</div>'
                for p in gh.split(" / ")
            )
            r += f'<th style="{TH}vertical-align:middle;padding:2px 1px;">{inner}</th>'
        return r + '</tr>'

    CELL_BASE = f"border:1px solid #ccc;padding:0;text-align:center;vertical-align:middle;height:{H_EMP_ROW}px;overflow:hidden;"

    def _emp_row(row, bg):
        name_td = (
            f'<td style="border:1px solid #ccc;padding:2px 5px;text-align:left;background:{bg};'
            f'vertical-align:middle;height:{H_EMP_ROW}px;overflow:hidden;">'
            f'<div style="font-size:14px;font-weight:800;color:#000;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.3;">'
            f'{row.get("employee_name","")}</div>'
            f'<div style="font-size:11px;font-weight:500;color:#444;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.3;">'
            f'{row.get("employee","")}</div></td>'
        )
        tr  = name_td
        tr += "".join(
            f'<td style="{CELL_BASE}background:{bg};font-size:12px;font-weight:700;color:#000;">{row.get(c["fieldname"],"–") or "–"}</td>'
            for c in day_cols
        )
        tr += "".join(_summ_cell(row, grp, bg) for grp in SUMM_GROUPS)
        return f'<tr style="height:{H_EMP_ROW}px;">{tr}</tr>'

    def _total_row_html():
        TS = f"border:1px solid #888;padding:3px;font-weight:700;background:#ffffff;height:{H_TOTAL_ROW}px;"
        t  = f'<td style="{TS}text-align:right;font-size:11px;vertical-align:middle;">Total</td>'
        t += "".join(f'<td style="{TS}"></td>' for _ in day_cols)
        t += "".join(_summ_cell(total_row, grp, "#ffffff", is_total=True) for grp in SUMM_GROUPS)
        return f'<tr style="height:{H_TOTAL_ROW}px;">{t}</tr>'

    pages, idx, first = [], 0, True
    while idx < len(rows):
        limit = ROWS_FIRST_PAGE if first else ROWS_OTHER_PAGES
        pages.append(rows[idx: idx + limit])
        idx += limit; first = False

    html = ""
    for page_no, page_rows in enumerate(pages):
        is_last = (page_no == len(pages) - 1)
        if page_no > 0:
            html += '<div style="page-break-before:always;-webkit-page-break-before:always;"></div>'
        html += _header_block()
        html += (
            '<table style="width:100%;border-collapse:collapse;table-layout:fixed;">'
            + colgroup + '<thead>' + _col_header_row() + '</thead><tbody>'
        )
        for i, row in enumerate(page_rows):
            html += _emp_row(row, "#ffffff")
        if is_last:
            html += _total_row_html()
        html += '</tbody></table>'
    return html


# ============================================================
# REPORT DATA FUNCTIONS
# ============================================================

def _build_bank_advice_data(filters, mode="home"):
    """
    mode='home'  → employees whose bank matches company's home bank
    mode='other' → employees whose bank does NOT match company's home bank
    """
    cols = [
        _col("Employee ID",    "employee_id"),
        _col("Employee Name",  "employee_name", width=180),
        _col("IFSC Code",      "ifsc_code"),
        _col("Account Number", "account_number", width=160),
        _col("Net Salary",     "net_salary", "Data", 130),
        _col("Bank Name",      "bank_name",  width=150),
    ]
    start, end = _date_range(filters)
    if not start: return cols, []

    params = {"start_date2": start, "end_date2": end}
    cond   = "ss.docstatus=1 AND ss.start_date>=%(start_date2)s AND ss.end_date<=%(end_date2)s"

    companies = _parse_list(filters.get("company"))
    if companies:
        params["companies"] = tuple(companies)
        cond += " AND ss.company IN %(companies)s"

    employees = _parse_list(filters.get("employee"))
    if employees:
        params["employees"] = tuple(employees)
        cond += " AND ss.employee IN %(employees)s"

    catj = _category_join(filters, params)
    divc = _division_condition(filters, params)

    slips = frappe.db.sql(f"""
        SELECT ss.employee, ss.employee_name, ss.company, ss.net_salary,
               emp.bank_name, emp.account_number, emp.ifsc_code
        FROM `tabSalary Slip` ss
        INNER JOIN `tabCompany Link` cl_active
            ON cl_active.name = ss.employee AND cl_active.is_active = 1
        LEFT JOIN `tabEmployee` emp ON emp.name = ss.employee
        {catj}
        WHERE {cond}{divc}
        ORDER BY ss.employee_name
    """, params, as_dict=1)

    if not slips: return cols, []

    on_hold    = _get_on_hold_employees(filters)
    co_list    = list({s.company for s in slips if s.company})
    home_map   = _get_company_bank_map(co_list)

    data, total = [], 0.0
    for s in slips:
        emp_bank  = (s.bank_name or "").strip().lower()
        home_bank = home_map.get(s.company, "")
        is_home   = home_bank and emp_bank == home_bank

        if mode == "home"  and not is_home: continue
        if mode == "other" and is_home:     continue

        if s.employee in on_hold:
            data.append({
                "employee_id":   s.employee,
                "employee_name": s.employee_name,
                "ifsc_code":     "On Hold",
                "account_number":"On Hold",
                "net_salary":    "On Hold",
                "bank_name":     s.bank_name or "-",
            })
        else:
            net = flt(s.net_salary, 2)
            total += net
            data.append({
                "employee_id":   s.employee,
                "employee_name": s.employee_name,
                "ifsc_code":     s.ifsc_code or "-",
                "account_number":s.account_number or "-",
                "net_salary":    f"{net:,.2f}",
                "bank_name":     s.bank_name or "-",
            })

    if data:
        data.append({
            "employee_id":"", "employee_name":"Total",
            "ifsc_code":"", "account_number":"",
            "net_salary": f"{flt(total,2):,.2f}",
            "bank_name": "", "bold": 1,
        })
    return cols, data


def _home_bank_advice(filters):
    return _build_bank_advice_data(filters, mode="home")

def _other_bank_advice(filters):
    return _build_bank_advice_data(filters, mode="other")


def _educational_allowance(filters):
    cols = [
        _col("Employee ID","employee_id"),
        _col("Employee Name","employee_name",width=200),
        _col("Educational Allowance","educational_allowance","Float",180,precision=2),
    ]
    if not filters.get("company"): return cols, []
    params = {}; cond = _base_conditions(filters, params)
    catj = _category_join(filters, params); divc = _division_condition(filters, params)
    slips = frappe.db.sql(f"""
        SELECT ss.name AS salary_slip, ss.employee, ss.employee_name, cl.employee AS employee_id
        FROM `tabSalary Slip` ss LEFT JOIN `tabCompany Link` cl ON cl.name=ss.employee
        {catj} WHERE {cond}{divc} ORDER BY ss.employee_name
    """, params, as_dict=1)
    if not slips: return cols, []
    sn = tuple(s.salary_slip for s in slips)
    ea_map = {}
    for r in frappe.db.sql(
        "SELECT sd.parent AS salary_slip, sd.amount FROM `tabSalary Details` sd "
        "WHERE sd.parent IN %(sn)s AND sd.parentfield='earnings' "
        "AND LOWER(sd.salary_component) LIKE '%%education%%' AND sd.amount>0",
        {"sn": sn}, as_dict=1
    ):
        ea_map[r.salary_slip] = ea_map.get(r.salary_slip, 0.0) + flt(r.amount)
    data, grand = [], 0.0
    for s in slips:
        ea = flt(ea_map.get(s.salary_slip, 0))
        if not ea: continue
        grand += ea
        data.append({"employee_id": s.employee_id or s.employee, "employee_name": s.employee_name, "educational_allowance": ea})
    if data:
        data.append({"employee_id":"","employee_name":"Total","educational_allowance":flt(grand,2),"bold":1})
    return cols, data


def _esi_register(filters):
    cols = [
        _col("ESI Number","esic_number",width=150),
        _col("Employee ID","employee_id",width=120),
        _col("Employee Name","employee_name",width=200),
        _col("Days Paid","days_paid","Float",100,precision=2),
        _col("Gross Salary","gross_salary","Float",140,precision=2),
        _col("ESI Contribution","total_esi","Float",140,precision=2),
        _col("Join Date","date_of_joining","Date",110),
        _col("Birth Date","date_of_birth","Date",110),
    ]
    if not filters.get("company"): return cols, []
    params = {}; cond = _base_conditions(filters, params)
    catj = _category_join(filters, params); divc = _division_condition(filters, params)
    slips = frappe.db.sql(f"""
        SELECT ss.name AS salary_slip, ss.employee, ss.employee_name,
               ss.payment_days AS days_paid, ss.total_earnings AS gross_salary,
               emp.name AS employee_id, cl.date_of_joining, emp.date_of_birth, emp.esic_number
        FROM `tabSalary Slip` ss
        LEFT JOIN `tabEmployee` emp ON emp.name=ss.employee
        LEFT JOIN `tabCompany Link` cl ON cl.name=ss.employee
        {catj} WHERE {cond}{divc} ORDER BY ss.employee_name
    """, params, as_dict=1)
    if not slips: return cols, []
    sn = tuple(s.salary_slip for s in slips)
    esi_map = {}
    for r in frappe.db.sql(
        "SELECT sd.parent AS salary_slip, sd.amount FROM `tabSalary Details` sd "
        "WHERE sd.parent IN %(sn)s AND sd.parentfield='deductions' "
        "AND LOWER(sd.salary_component) LIKE '%%esic%%' AND sd.amount>0",
        {"sn": sn}, as_dict=1
    ):
        esi_map[r.salary_slip] = esi_map.get(r.salary_slip, 0) + flt(r.amount)
    data, gg, ge = [], 0.0, 0.0
    for s in slips:
        esi = flt(esi_map.get(s.salary_slip, 0))
        if esi <= 0: continue
        gg += flt(s.gross_salary, 2); ge += esi
        data.append({
            "esic_number": s.esic_number or "-", "employee_id": s.employee_id or s.employee,
            "employee_name": s.employee_name, "days_paid": flt(s.days_paid, 2),
            "gross_salary": flt(s.gross_salary, 2), "total_esi": esi,
            "date_of_joining": s.date_of_joining, "date_of_birth": s.date_of_birth
        })
    if data:
        data.append({"esic_number":"","employee_id":"","employee_name":"Total","days_paid":"",
                     "gross_salary":flt(gg,2),"total_esi":flt(ge,2),"date_of_joining":"","date_of_birth":"","bold":1})
    return cols, data


def _labour_welfare_fund(filters):
    cols = [
        _col("Employee ID","employee_id"),
        _col("Employee Name","employee_name",width=200),
        _col("Net Salary","net_salary","Float",130,precision=2),
        _col("LWF Amount","lwf_amount","Float",120,precision=2),
    ]
    if not filters.get("company"): return cols, []
    params = {}; cond = _base_conditions(filters, params)
    catj = _category_join(filters, params); divc = _division_condition(filters, params)
    slips = frappe.db.sql(f"""
        SELECT ss.name AS salary_slip, ss.employee, ss.employee_name, ss.net_salary, cl.employee AS employee_id
        FROM `tabSalary Slip` ss LEFT JOIN `tabCompany Link` cl ON cl.name=ss.employee
        {catj} WHERE {cond}{divc} ORDER BY ss.employee_name
    """, params, as_dict=1)
    if not slips: return cols, []
    sn = tuple(s.salary_slip for s in slips)
    lwf_map = {r.salary_slip: flt(r.lwf_amount) for r in frappe.db.sql(
        "SELECT sd.parent AS salary_slip, SUM(sd.amount) AS lwf_amount FROM `tabSalary Details` sd "
        "WHERE sd.parent IN %(sn)s AND sd.parentfield='deductions' "
        "AND LOWER(sd.salary_component) LIKE '%%welfare%%' AND sd.amount>0 GROUP BY sd.parent",
        {"sn": sn}, as_dict=1
    )}
    data, gn, gl = [], 0.0, 0.0
    for s in slips:
        lwf = flt(lwf_map.get(s.salary_slip, 0))
        if lwf <= 0: continue
        net = flt(s.net_salary, 2); gn += net; gl += lwf
        data.append({"employee_id": s.employee_id or s.employee, "employee_name": s.employee_name,
                     "net_salary": net, "lwf_amount": flt(lwf, 2)})
    if data:
        data.append({"employee_id":"","employee_name":"Total","net_salary":flt(gn,2),"lwf_amount":flt(gl,2),"bold":1})
    return cols, data


def _professional_tax(filters):
    cols = [
        _col("Salary Range","salary_range",width=220),
        _col("PT Rate (Rs.)","pt_rate","Float",130,precision=2),
        _col("No. of Employees","employee_count","Int",150),
        _col("Total Earnings","total_earnings","Float",160,precision=2),
        _col("PT Amount (Rs.)","pt_amount","Float",150,precision=2),
    ]
    empty = [{"salary_range":s["label"],"pt_rate":flt(s["rate"],2),"employee_count":0,
              "total_earnings":0.0,"pt_amount":0.0,"_row_type":"slab"} for s in PT_SLABS]
    empty.append({"salary_range":"Total","pt_rate":None,"employee_count":0,
                  "total_earnings":0.0,"pt_amount":0.0,"bold":1,"_row_type":"total"})
    if not filters.get("company"): return cols, empty
    params = {}; cond = _base_conditions(filters, params)
    catj = _category_join(filters, params); divc = _division_condition(filters, params)
    rows = frappe.db.sql(
        f"SELECT ss.employee AS employee_id, ss.total_earnings AS gross FROM `tabSalary Slip` ss {catj} WHERE {cond}{divc}",
        params, as_dict=1
    )
    if not rows: return cols, empty
    pp = dict(params, pt_like="%professional tax%")
    pt_map = {r.employee: flt(r.pt_amount) for r in frappe.db.sql(f"""
        SELECT ss.employee, SUM(sd.amount) AS pt_amount FROM `tabSalary Slip` ss
        INNER JOIN `tabSalary Details` sd ON sd.parent=ss.name AND sd.parenttype='Salary Slip'
            AND sd.parentfield='deductions' AND LOWER(sd.salary_component) LIKE %(pt_like)s
        {catj} WHERE {cond}{divc} GROUP BY ss.employee
    """, pp, as_dict=1)}
    sd = {s["label"]: {"rate":s["rate"],"count":0,"earnings":0.0,"amount":0.0} for s in PT_SLABS}
    for row in rows:
        pt = pt_map.get(row.employee_id, 0.0)
        if pt <= 0: continue
        gross = flt(row.gross, 2); sl = _pt_slab(gross)
        sd[sl["label"]]["count"]   += 1
        sd[sl["label"]]["earnings"] += gross
        sd[sl["label"]]["amount"]   += pt
    data = []; ge = gc = gp = 0.0
    for s in PT_SLABS:
        info = sd[s["label"]]; ge += info["earnings"]; gc += info["count"]; gp += info["amount"]
        data.append({"salary_range":s["label"],"pt_rate":flt(s["rate"],2),"employee_count":info["count"],
                     "total_earnings":flt(info["earnings"],2),"pt_amount":flt(info["amount"],2),"_row_type":"slab"})
    data.append({"salary_range":"Total","pt_rate":None,"employee_count":gc,
                 "total_earnings":flt(ge,2),"pt_amount":flt(gp,2),"bold":1,"_row_type":"total"})
    return cols, data


def _provident_fund(filters):
    cols = [
        _col("PF No.","pf_no",width=110),_col("UAN No.","uan_no",width=110),
        _col("Employee ID","employee_id",width=120),_col("Employee Name","employee_name",width=180),
        _col("Days (LWP+ABS)","days","Float",60,precision=1),_col("Absent","absent","Float",55,precision=1),
        _col("Gross Salary","gross","Float",110,precision=2),_col("BS+DA","basic_da","Float",110,precision=2),
        _col("Emp PF 12%","emp_pf","Float",110,precision=2),_col("Empr. EPS 8.33%","employer_eps","Float",130,precision=2),
        _col("Empr. PF 3.67%","employer_pf","Float",130,precision=2),_col("Total","total_amount","Float",105,precision=2),
        _col("Non-Cont.","non_contrib","Float",100,precision=2),_col("Vol. PF","vol_pf","Float",80,precision=2),
        _col("Cumul. PF","cumul_pf","Float",95,precision=2),_col("Cumul. EPS","cumul_eps","Float",95,precision=2),
        _col("Total","total_amount2","Float",105,precision=2),
        _col("DOJ","date_of_joining","Date",130),_col("DOB","date_of_birth","Date",130),
    ]
    if not filters.get("company"): return cols, []
    params = {}; cond = _base_conditions(filters, params)
    catj = _category_join(filters, params); divc = _division_condition(filters, params)
    slips = frappe.db.sql(f"""
        SELECT ss.name AS slip_name, ss.employee AS employee_id, ss.employee_name,
               ss.payment_days AS days, ss.absent_days AS absent, ss.total_earnings AS gross
        FROM `tabSalary Slip` ss {catj} WHERE {cond}{divc} ORDER BY ss.employee_name
    """, params, as_dict=1)
    if not slips: return cols, []
    sn   = tuple(s.slip_name for s in slips)
    eids = tuple(s.employee_id for s in slips)
    bda_map = {r.slip_name: flt(r.basic_da) for r in frappe.db.sql("""
        SELECT sd.parent AS slip_name, SUM(sd.amount) AS basic_da FROM `tabSalary Details` sd
        WHERE sd.parent IN %(sn)s AND sd.parenttype='Salary Slip' AND sd.parentfield='earnings'
          AND (LOWER(sd.salary_component) LIKE '%%basic%%'
            OR LOWER(sd.salary_component) LIKE '%%dearness%%'
            OR LOWER(sd.salary_component) LIKE '%% da')
        GROUP BY sd.parent
    """, {"sn": sn}, as_dict=1)}
    vpf_map = {r.slip_name: flt(r.vol_pf) for r in frappe.db.sql("""
        SELECT sd.parent AS slip_name, SUM(sd.amount) AS vol_pf FROM `tabSalary Details` sd
        WHERE sd.parent IN %(sn)s AND sd.parenttype='Salary Slip' AND sd.parentfield='deductions'
          AND LOWER(sd.salary_component) LIKE '%%voluntary%%' GROUP BY sd.parent
    """, {"sn": sn}, as_dict=1)}
    emp_map = {r.name: r for r in frappe.db.sql("""
        SELECT e.name, e.employee_pf_account AS pf_no, e.pf_uan_number AS uan_no,
               e.date_of_birth, cl.date_of_joining
        FROM `tabEmployee` e LEFT JOIN `tabCompany Link` cl ON cl.name=e.name
        WHERE e.name IN %(ids)s
    """, {"ids": eids}, as_dict=1)}
    data = []
    t = {k: 0.0 for k in ["gross","basic_da","emp_pf","er_eps","er_pf","total","nc","vpf","cpf","ceps","total2"]}
    for s in slips:
        emp   = emp_map.get(s.employee_id, frappe._dict())
        gross = flt(s.gross, 2); bda = flt(bda_map.get(s.slip_name, 0.0), 2)
        pfw   = min(bda, PF_WAGE_CEILING)
        epf   = flt(round(pfw * 0.12), 2)
        ereps = flt(round(epf * 0.6944), 2)
        erpf  = flt(round(epf * 0.3056), 2)
        tota  = flt(epf + epf, 2)
        nc    = flt(max(0.0, bda - PF_WAGE_CEILING), 2)
        vpf   = flt(vpf_map.get(s.slip_name, 0.0), 2)
        cpf   = flt(epf + erpf, 2)
        for k, v in [("gross",gross),("basic_da",bda),("emp_pf",epf),("er_eps",ereps),
                     ("er_pf",erpf),("total",tota),("nc",nc),("vpf",vpf),("cpf",cpf),
                     ("ceps",ereps),("total2",tota)]:
            t[k] += v
        data.append({
            "pf_no":emp.get("pf_no") or "","uan_no":emp.get("uan_no") or "",
            "employee_id":s.employee_id,"employee_name":s.employee_name,
            "days":flt(s.days,1),"absent":flt(s.absent,1),"gross":gross,"basic_da":bda,
            "emp_pf":epf,"employer_eps":ereps,"employer_pf":erpf,"total_amount":tota,
            "non_contrib":nc,"vol_pf":vpf if vpf else None,"cumul_pf":cpf,
            "cumul_eps":ereps,"total_amount2":tota,
            "date_of_joining":emp.get("date_of_joining") or "",
            "date_of_birth":emp.get("date_of_birth") or "","_row_type":"detail",
        })
    data.append({
        "pf_no":"","uan_no":"","employee_id":"","employee_name":"Total",
        "days":None,"absent":None,"gross":flt(t["gross"],2),"basic_da":flt(t["basic_da"],2),
        "emp_pf":flt(t["emp_pf"],2),"employer_eps":flt(t["er_eps"],2),"employer_pf":flt(t["er_pf"],2),
        "total_amount":flt(t["total"],2),"non_contrib":flt(t["nc"],2),
        "vol_pf":flt(t["vpf"],2) if t["vpf"] else None,
        "cumul_pf":flt(t["cpf"],2),"cumul_eps":flt(t["ceps"],2),"total_amount2":flt(t["total2"],2),
        "date_of_joining":"","date_of_birth":"","bold":1,"_row_type":"total",
    })
    return cols, data


def _retention_deposit(filters):
    cols = [
        _col("Employee ID","employee_id",width=160),
        _col("Employee Name","employee_name",width=220),
        _col("Date of Joining","date_of_joining","Date",150),
        _col("Deduction Upto (3 Years)","ded_upto","Date",180),
        _col("Retention Deposit","retention_amount","Float",180,precision=2),
    ]
    if not filters.get("company"): return cols, []
    params = {"component":"Retention"}; cond = _base_conditions(filters, params)
    catj = _category_join(filters, params); divc = _division_condition(filters, params)
    rows = frappe.db.sql(f"""
        SELECT ss.employee AS employee_id, ss.employee_name, sd.amount AS retention_amount
        FROM `tabSalary Slip` ss
        INNER JOIN `tabSalary Details` sd ON sd.parent=ss.name AND sd.parenttype='Salary Slip'
            AND sd.parentfield='deductions' AND sd.salary_component=%(component)s AND sd.amount>0
        {catj} WHERE {cond}{divc} ORDER BY ss.employee_name
    """, params, as_dict=1)
    if not rows: return cols, []
    cl_map = {r["name"]: r["date_of_joining"] for r in frappe.db.sql(
        "SELECT name, date_of_joining FROM `tabCompany Link` WHERE name IN %(ids)s",
        {"ids": tuple({r.employee_id for r in rows})}, as_dict=1
    )}
    data, grand = [], 0.0
    for row in rows:
        doj = cl_map.get(row.employee_id); ded_upto = None
        if doj:
            try: ded_upto = add_months(getdate(doj), 36)
            except Exception: pass
        ret = flt(row.retention_amount, 2); grand += ret
        data.append({"employee_id":row.employee_id,"employee_name":row.employee_name,
                     "date_of_joining":doj,"ded_upto":ded_upto,"retention_amount":ret})
    if data:
        data.append({"employee_id":"","employee_name":"Total","date_of_joining":None,
                     "ded_upto":None,"retention_amount":flt(grand,2),"bold":1})
    return cols, data


def _salary_summary(filters):
    cols = [
        _col("Earnings — Description","description",width=250),
        _col("Earnings — Amount","amount","Float",160,precision=2),
        {"label":" ","fieldname":"spacer","fieldtype":"Data","width":40},
        _col("Deductions — Description","ded_description",width=250),
        _col("Deductions — Amount","ded_amount","Float",160,precision=2),
    ]
    if not filters.get("company"): return cols, []
    params = {}; conds = ["ss.docstatus=1"]
    sd = _start_date(filters)
    if sd: params["start_date"] = sd; conds.append("ss.start_date=%(start_date)s")
    companies = _parse_list(filters.get("company"))
    if companies: params["companies"] = tuple(companies); conds.append("ss.company IN %(companies)s")
    cat = filters.get("category")
    if cat: params["category"] = cat; conds.append("ss.employee IN (SELECT name FROM `tabCompany Link` WHERE category=%(category)s)")
    divs = _parse_list(filters.get("division"))
    if divs: params["divisions"] = tuple(divs); conds.append("ss.employee IN (SELECT name FROM `tabCompany Link` WHERE division IN %(divisions)s OR department IN %(divisions)s)")
    where = " AND ".join(conds)

    def _comps(field, extra_join=""):
        return [r[0] for r in frappe.db.sql(f"""
            SELECT DISTINCT sd.salary_component FROM `tabSalary Slip` ss
            INNER JOIN `tabSalary Details` sd ON sd.parent=ss.name AND sd.parenttype='Salary Slip' AND sd.parentfield='{field}'
            {extra_join} WHERE {where} ORDER BY sd.salary_component
        """, params, as_list=1)]

    def _totals(field, extra_join=""):
        return {r.component: flt(r.total) for r in frappe.db.sql(f"""
            SELECT sd.salary_component AS component, SUM(sd.amount) AS total
            FROM `tabSalary Slip` ss
            INNER JOIN `tabSalary Details` sd ON sd.parent=ss.name AND sd.parenttype='Salary Slip' AND sd.parentfield='{field}'
            {extra_join} WHERE {where} GROUP BY sd.salary_component
        """, params, as_dict=1)}

    ded_join  = "INNER JOIN `tabSalary Component` sc ON sc.name=sd.salary_component AND sc.employer_contribution=0"
    earn_comp = _comps("earnings"); ded_comp = _comps("deductions", ded_join)
    earn_tot  = _totals("earnings"); ded_tot  = _totals("deductions", ded_join)
    earn_rows = [(c, earn_tot.get(c, 0.0)) for c in earn_comp]
    ded_rows  = [(c, ded_tot.get(c, 0.0))  for c in ded_comp]
    ge, gd    = sum(v for _, v in earn_rows), sum(v for _, v in ded_rows)

    stats = (frappe.db.sql(f"""
        SELECT COUNT(DISTINCT ss.employee) AS total_employees, SUM(ss.net_salary) AS total_net_salary,
               SUM(ss.total_lwp) AS total_lwp, SUM(ss.absent_days) AS total_absent,
               SUM(ss.total_holidays) AS total_holidays, SUM(ss.payment_days) AS total_payment_days
        FROM `tabSalary Slip` ss WHERE {where}
    """, params, as_dict=1) or [{}])[0]

    data = []
    for i in range(max(len(earn_rows), len(ded_rows), 1)):
        ec, ea = earn_rows[i] if i < len(earn_rows) else ("", None)
        dc, da = ded_rows[i]  if i < len(ded_rows)  else ("", None)
        data.append({"description":ec,"amount":flt(ea,2) if ec else None,"spacer":"",
                     "ded_description":dc,"ded_amount":flt(da,2) if dc else None,"_row_type":"component"})
    data.append({"description":"Grand Total","amount":flt(ge,2),"spacer":"",
                 "ded_description":"Grand Total","ded_amount":flt(gd,2),"bold":1,"_row_type":"grand_total"})
    data.append({"description":"","amount":None,"spacer":"","ded_description":"","ded_amount":None,"_row_type":"separator"})
    data.append({"description":"Other Details","amount":None,"spacer":"","ded_description":"","ded_amount":None,"bold":1,"_row_type":"section_header"})
    for label, value in [
        ("Total Employees",    stats.get("total_employees") or 0),
        ("Total Net Salary",   flt(stats.get("total_net_salary"), 2)),
        ("Total LWP Days",     flt(stats.get("total_lwp"), 2)),
        ("Total Absent Days",  flt(stats.get("total_absent"), 2)),
        ("Total Holidays",     flt(stats.get("total_holidays"), 2)),
        ("Total Payment Days", flt(stats.get("total_payment_days"), 2)),
    ]:
        data.append({"description":label,"amount":value,"spacer":"","ded_description":"","ded_amount":None,"_row_type":"other"})
    return cols, data


def _salary_summary_individual(filters):
    cols = [
        _col("Employee Name","employee_name",width=180),
        _col("Days","payment_days","Float",60,precision=2),
        _col("Absent","absent_days","Float",60,precision=2),
        _col("LWP","total_lwp","Float",60,precision=2),
    ]
    for lbl, abbr in EARNING_COMPONENTS:
        cols.append(_col(f"{lbl} ({abbr})", f"earn_{_sanitize(abbr)}", "Float", 150, precision=2))
    for lbl, abbr in DEDUCTION_COMPONENTS:
        cols.append(_col(f"{lbl} ({abbr})", f"ded_{_sanitize(abbr)}", "Float", 150, precision=2))
    cols += [
        _col("Total Earnings","total_earnings","Float",140,precision=2),
        _col("Total Deductions","total_deductions","Float",140,precision=2),
        _col("Net Salary","net_salary","Float",140,precision=2),
    ]
    if not filters.get("company"): return cols, []
    params = {}; start, end = _date_range(filters)
    if not start: return cols, []
    params.update(start_date=start, end_date=end)
    conds = ["ss.docstatus=1","ss.start_date>=%(start_date)s","ss.end_date<=%(end_date)s"]
    companies = _parse_list(filters.get("company"))
    if companies: params["companies"] = tuple(companies); conds.append("ss.company IN %(companies)s")
    catj = ""
    cat = filters.get("category")
    if cat: params["category"] = cat; catj = "INNER JOIN `tabCompany Link` cl_cat ON cl_cat.name=ss.employee AND cl_cat.category=%(category)s"
    where = " AND ".join(conds)
    slips = frappe.db.sql(
        f"SELECT ss.name AS salary_slip, ss.employee, ss.employee_name, "
        f"ss.payment_days, ss.absent_days, ss.total_lwp, ss.net_salary "
        f"FROM `tabSalary Slip` ss {catj} WHERE {where} ORDER BY ss.employee_name",
        params, as_dict=1
    )
    if not slips: return cols, []
    sn   = [s["salary_slip"] for s in slips]
    emap = _fetch_slip_components(sn, "earnings")
    dmap = _fetch_slip_components(sn, "deductions")

    data  = []
    grand = {f"earn_{_sanitize(a)}": 0 for _, a in EARNING_COMPONENTS}
    grand.update({f"ded_{_sanitize(a)}": 0 for _, a in DEDUCTION_COMPONENTS})
    grand.update(total_earnings=0, total_deductions=0, net_salary=0, absent_days=0, total_lwp=0)

    for s in slips:
        se = emap.get(s["salary_slip"], {}); sd_ = dmap.get(s["salary_slip"], {})
        row = {
            "employee":      s["employee"],
            "employee_name": s["employee_name"],
            "payment_days":  flt(s["payment_days"], 2),
            "absent_days":   flt(s["absent_days"], 2),
            "total_lwp":     flt(s["total_lwp"], 2),
            "net_salary":    flt(s["net_salary"], 2),
        }
        te = td = 0.0
        for lbl, abbr in EARNING_COMPONENTS:
            amt = se.get(lbl)
            if amt is not None:
                v = flt(amt, 2); row[f"earn_{_sanitize(abbr)}"] = v; te += v; grand[f"earn_{_sanitize(abbr)}"] += v
        row["total_earnings"] = flt(te, 2); grand["total_earnings"] += te
        for lbl, abbr in DEDUCTION_COMPONENTS:
            amt = sd_.get(lbl)
            if amt is not None:
                v = flt(amt, 2); row[f"ded_{_sanitize(abbr)}"] = v; td += v; grand[f"ded_{_sanitize(abbr)}"] += v
        row["total_deductions"] = flt(td, 2); grand["total_deductions"] += td
        grand["net_salary"]  += flt(s["net_salary"], 2)
        grand["absent_days"] += flt(s["absent_days"], 2)
        grand["total_lwp"]   += flt(s["total_lwp"], 2)
        data.append(row)

    data.append({"employee":"","employee_name":"Total","payment_days":"","bold":1,**grand})
    return cols, data


def _transaction_checklist(filters):
    cols = [
        _col("Employee","employee",width=120),
        _col("Employee Name","employee_name",width=160),
        _col("Payment Days","payment_days","Float",110,precision=2),
        _col("Absent","absent_days","Float",60,precision=2),
        _col("LWP","total_lwp","Float",100,precision=2),
    ]
    for lbl, abbr in EARNING_COMPONENTS:
        fn = f"earn_{_sanitize(abbr)}"
        cols.append(_col("Variable Pay (VAR %)", fn, "Data", 150) if abbr == "VAR" else _col(f"{lbl} ({abbr})", fn, "Float", 150, precision=2))
    for lbl, abbr in DEDUCTION_COMPONENTS:
        cols.append(_col(f"{lbl} ({abbr})", f"ded_{_sanitize(abbr)}", "Float", 150, precision=2))
    cols += [
        _col("Total Earnings","total_earnings","Float",140,precision=2),
        _col("Total Deductions","total_deductions","Float",140,precision=2),
        _col("Net Salary","net_salary","Float",140,precision=2),
    ]
    if not filters.get("company"): return cols, []
    params = {}; start, end = _date_range(filters)
    if not start: return cols, []
    params.update(start_date=start, end_date=end)
    conds = ["ss.docstatus=1","ss.start_date>=%(start_date)s","ss.end_date<=%(end_date)s"]
    companies = _parse_list(filters.get("company"))
    if companies: params["companies"] = tuple(companies); conds.append("ss.company IN %(companies)s")
    catj = _category_join(filters, params)
    divc = _division_condition(filters, params)
    where = " AND ".join(conds)
    slips = frappe.db.sql(
        f"SELECT ss.name AS salary_slip, ss.employee, ss.employee_name, ss.payment_days, "
        f"ss.absent_days, ss.total_lwp, ss.net_salary "
        f"FROM `tabSalary Slip` ss {catj} WHERE {where}{divc} ORDER BY ss.employee_name",
        params, as_dict=1
    )
    if not slips: return cols, []
    sn   = [s["salary_slip"] for s in slips]
    eids = [s["employee"] for s in slips]
    month, year = filters.get("month",""), filters.get("year","")
    vpa_name = f"{year} - {month}"; vp_map = {}
    if frappe.db.exists("Variable Pay Assignment", vpa_name):
        vp_map = {r.division: flt(r.percentage) for r in frappe.db.sql(
            "SELECT division, percentage FROM `tabVariable Pay Detail Table` WHERE parent=%(v)s AND parenttype='Variable Pay Assignment'",
            {"v": vpa_name}, as_dict=1
        )}
    div_map = {r.company_link_name: r.division for r in frappe.db.sql(
        "SELECT cl.name AS company_link_name, cl.division FROM `tabCompany Link` cl WHERE cl.name IN %(ids)s",
        {"ids": tuple(eids)}, as_dict=1
    )} if eids else {}
    emap = _fetch_slip_components(sn, "earnings")
    dmap = _fetch_slip_components(sn, "deductions")

    data  = []
    grand = {f"earn_{_sanitize(a)}": 0.0 for _, a in EARNING_COMPONENTS}
    grand.update({f"ded_{_sanitize(a)}": 0.0 for _, a in DEDUCTION_COMPONENTS})
    grand.update(total_earnings=0.0, total_deductions=0.0, net_salary=0.0,
                 payment_days=0.0, absent_days=0.0, total_lwp=0.0)

    for s in slips:
        se  = emap.get(s["salary_slip"], {}); sd_ = dmap.get(s["salary_slip"], {})
        div = div_map.get(s["employee"], "")
        row = {
            "employee":     s["employee"], "employee_name": s["employee_name"],
            "payment_days": flt(s["payment_days"], 2),
            "absent_days":  flt(s.get("absent_days") or 0, 2),
            "total_lwp":    flt(s["total_lwp"] or 0, 2),
            "net_salary":   flt(s["net_salary"], 2)
        }
        te = td = 0.0
        for lbl, abbr in EARNING_COMPONENTS:
            if abbr == "VAR":
                pct = vp_map.get(div)
                row["earn_var"] = f"{pct}%" if pct is not None else ""
                if (a := se.get(lbl)): te += a; grand["earn_var"] += a
            elif (a := se.get(lbl)) is not None:
                v = flt(a, 2); row[f"earn_{_sanitize(abbr)}"] = v; te += v; grand[f"earn_{_sanitize(abbr)}"] += v
        row["total_earnings"] = flt(te, 2); grand["total_earnings"] += te
        for lbl, abbr in DEDUCTION_COMPONENTS:
            if (a := sd_.get(lbl)) is not None:
                v = flt(a, 2); row[f"ded_{_sanitize(abbr)}"] = v; td += v; grand[f"ded_{_sanitize(abbr)}"] += v
        row["total_deductions"] = flt(td, 2); grand["total_deductions"] += td
        grand["net_salary"]   += flt(s["net_salary"], 2)
        grand["payment_days"] += flt(s["payment_days"], 2)
        grand["absent_days"]  += flt(s.get("absent_days") or 0, 2)
        grand["total_lwp"]    += flt(s["total_lwp"] or 0, 2)
        data.append(row)

    if data:
        data.append({"employee":"","employee_name":"Total","bold":1,
                     **{k: v for k, v in grand.items() if k != "payment_days"}})
    return cols, data


def _variable_pay(filters):
    cols = [
        _col("Employee ID","employee_id",width=160),
        _col("Employee Name","employee_name",width=220),
        _col("Division","division",width=150),
        _col("Monthly Variable Pay","monthly_variable_pay","Float",180,precision=2),
        _col("Variable Pay %","variable_pay_percentage","Percent",130),
        _col("Variable Pay Amount","variable_pay_amount","Float",180,precision=2),
    ]
    if not filters.get("company"): return cols, []
    params = {"variable_like": "%variable%"}; cond = _base_conditions(filters, params)
    catj = _category_join(filters, params, emp_col="ss.employee"); divc = _division_condition(filters, params)
    rows = frappe.db.sql(f"""
        SELECT ss.name AS slip_name, ss.employee AS employee_id, ss.employee_name,
               cl.division, COALESCE(sd.amount,0) AS variable_pay_amount
        FROM `tabSalary Slip` ss
        LEFT JOIN `tabCompany Link` cl ON cl.name=ss.employee
        LEFT JOIN `tabSalary Details` sd ON sd.parent=ss.name AND sd.parenttype='Salary Slip'
            AND sd.parentfield='earnings' AND LOWER(sd.salary_component) LIKE %(variable_like)s
        {catj} WHERE {cond}{divc}
          AND EXISTS (
              SELECT 1 FROM `tabSalary Structure Assignment` ssa
              INNER JOIN `tabSalary Details` ssa_sd ON ssa_sd.parent=ssa.name
                  AND ssa_sd.parenttype='Salary Structure Assignment'
                  AND ssa_sd.parentfield='earnings'
                  AND LOWER(ssa_sd.salary_component) LIKE %(variable_like)s AND ssa_sd.amount>0
              WHERE ssa.employee=ss.employee AND ssa.from_date<=%(start_date)s
                AND (ssa.to_date IS NULL OR ssa.to_date>=%(start_date)s))
        ORDER BY ss.employee_name
    """, params, as_dict=1)
    if not rows: return cols, []
    month, year = filters.get("month",""), filters.get("year","")
    vpa_name = f"{year} - {month}"; vpa_map = {}
    if frappe.db.exists("Variable Pay Assignment", vpa_name):
        vpa_map = {r.division: flt(r.percentage) for r in frappe.db.sql(
            "SELECT division, percentage FROM `tabVariable Pay Detail Table` WHERE parent=%(v)s AND parenttype='Variable Pay Assignment'",
            {"v": vpa_name}, as_dict=1
        )}
    emp_ids = list({r.employee_id for r in rows}); mv_map = {}
    if emp_ids:
        for r in frappe.db.sql(
            "SELECT ssa.employee, ssa_sd.amount AS monthly_variable_pay "
            "FROM `tabSalary Structure Assignment` ssa "
            "INNER JOIN `tabSalary Details` ssa_sd ON ssa_sd.parent=ssa.name "
            "    AND ssa_sd.parenttype='Salary Structure Assignment' "
            "    AND ssa_sd.parentfield='earnings' "
            "    AND LOWER(ssa_sd.salary_component) LIKE %(vl)s AND ssa_sd.amount>0 "
            "WHERE ssa.employee IN %(ids)s AND ssa.from_date<=%(sd)s "
            "    AND (ssa.to_date IS NULL OR ssa.to_date>=%(sd)s) "
            "ORDER BY ssa.from_date DESC",
            {"ids": tuple(emp_ids), "sd": params.get("start_date",""), "vl": "%variable%"}, as_dict=1
        ):
            if r.employee not in mv_map: mv_map[r.employee] = flt(r.monthly_variable_pay)
    data = []; tmv = tva = 0.0
    for row in rows:
        div = row.division or ""; pct = vpa_map.get(div, 0.0)
        mv  = mv_map.get(row.employee_id, 0.0); vpa = flt(row.variable_pay_amount, 2)
        tmv += mv; tva += vpa
        data.append({"employee_id":row.employee_id,"employee_name":row.employee_name,
                     "division":div,"monthly_variable_pay":flt(mv,2),
                     "variable_pay_percentage":flt(pct,2),"variable_pay_amount":vpa})
    if data:
        data.append({"employee_id":"","employee_name":"Total","division":"",
                     "monthly_variable_pay":flt(tmv,2),"variable_pay_percentage":None,
                     "variable_pay_amount":flt(tva,2),"bold":1})
    return cols, data


def _monthly_attendance(filters):
    month_str, year_str = filters.get("month",""), filters.get("year","")
    month_num = MONTH_MAP.get(month_str)
    cols = [_col("Employee ID","employee",width=130), _col("Employee Name","employee_name",width=180)]
    if not month_num or not year_str: return cols, []
    year_int  = int(year_str); last = calendar.monthrange(year_int, month_num)[1]
    from_date = f"{year_int}-{month_num:02d}-01"
    to_date   = f"{year_int}-{month_num:02d}-{last:02d}"
    for d in range(1, last + 1):
        cols.append({"label": str(d), "fieldname": f"day_{d}", "fieldtype": "Data", "width": 28})
    cols += [
        _col("WD","working_days","Int",40), _col("P","present_days","Float",45,precision=2),
        _col("HD","half_days","Float",40,precision=2), _col("A","absent_days","Float",40,precision=2),
        _col("WO","weekly_off_days","Int",40), _col("H","holiday_days","Int",35),
        _col("LWP","lwp_days","Int",40), _col("A+LWP","absent_lwp","Float",50,precision=2),
    ]
    companies = _parse_list(filters.get("company"))
    if not companies: return cols, []
    co = tuple(companies) if len(companies) > 1 else (companies[0], companies[0])
    params = {"from_date": from_date, "to_date": to_date, "companies": co}
    cat = filters.get("category"); cat_join = ""
    if cat: params["category"] = cat; cat_join = "INNER JOIN `tabCompany Link` cl ON cl.name=a.employee AND cl.category=%(category)s"
    emp_cond = ""
    se = _parse_list(filters.get("employee"))
    if se: params["employees"] = tuple(se) if len(se) > 1 else (se[0], se[0]); emp_cond = "AND a.employee IN %(employees)s"
    div_cond = ""
    divs = _parse_list(filters.get("division"))
    if divs: params["divisions"] = tuple(divs) if len(divs) > 1 else (divs[0], divs[0]); div_cond = "AND a.employee IN (SELECT name FROM `tabCompany Link` WHERE division IN %(divisions)s OR department IN %(divisions)s)"
    records = frappe.db.sql(f"""
        SELECT a.employee, a.employee_name, a.attendance_date, a.status
        FROM `tabAttendance` a {cat_join}
        WHERE a.company IN %(companies)s
          AND a.attendance_date BETWEEN %(from_date)s AND %(to_date)s
          {emp_cond} {div_cond}
        ORDER BY a.employee_name, a.attendance_date
    """, params, as_dict=1)
    if not records: return cols, []

    STATUS_MAP = {
        "Present":    ("present_days",   1, "P"),
        "Absent":     ("absent_days",    1, "A"),
        "Weekly Off": ("weekly_off_days",1, "WO"),
        "Holiday":    ("holiday_days",   1, "H"),
        "LWP":        ("lwp_days",       1, "LWP"),
    }
    emp_dict = {}; emp_order = []
    for row in records:
        emp = row.employee
        day = row.attendance_date.day if hasattr(row.attendance_date, "day") else int(str(row.attendance_date)[8:10])
        if emp not in emp_dict:
            emp_order.append(emp)
            emp_dict[emp] = {"employee":emp,"employee_name":row.employee_name or "","working_days":last,
                             "present_days":0.0,"half_days":0.0,"absent_days":0.0,
                             "weekly_off_days":0,"holiday_days":0,"lwp_days":0,"absent_lwp":0.0}
        st = row.status
        if st == "Half Day":
            emp_dict[emp]["half_days"]    += 1
            emp_dict[emp]["present_days"] += 0.5
            emp_dict[emp]["absent_days"]  += 0.5
            emp_dict[emp][f"day_{day}"]    = "HD"
        elif st in STATUS_MAP:
            k, v, code = STATUS_MAP[st]
            emp_dict[emp][k]            += v
            emp_dict[emp][f"day_{day}"]  = code
            if st in ("Absent","LWP"): emp_dict[emp]["absent_lwp"] += 1
        else:
            emp_dict[emp][f"day_{day}"] = "-"

    for emp in emp_dict:
        for d in range(1, last + 1): emp_dict[emp].setdefault(f"day_{d}", "-")

    data = [emp_dict[e] for e in emp_order]
    if data:
        totals = {"employee":"","employee_name":"Total","_is_total":True,"working_days":0,
                  "present_days":0.0,"half_days":0.0,"absent_days":0.0,
                  "weekly_off_days":0,"holiday_days":0,"lwp_days":0,"absent_lwp":0.0}
        for d in range(1, last + 1): totals[f"day_{d}"] = ""
        for r in data:
            for k in ["working_days","present_days","half_days","absent_days",
                      "weekly_off_days","holiday_days","lwp_days","absent_lwp"]:
                totals[k] = round(flt(totals[k]) + flt(r.get(k, 0)), 2)
        data.append(totals)
    return cols, data


# ============================================================
# ROUTER
# ============================================================

ROUTER = {
    "home_bank_advice":          _home_bank_advice,
    "other_bank_advice":         _other_bank_advice,
    "educational_allowance":     _educational_allowance,
    "esi_register":              _esi_register,
    "labour_welfare_fund":       _labour_welfare_fund,
    "professional_tax":          _professional_tax,
    "provident_fund":            _provident_fund,
    "retention_deposit":         _retention_deposit,
    "salary_summary":            _salary_summary,
    "salary_summary_individual": _salary_summary_individual,
    "transaction_checklist":     _transaction_checklist,
    "variable_pay":              _variable_pay,
    "monthly_attendance":        _monthly_attendance,
}


# ============================================================
# EMPLOYEE FILTER HELPER
# ============================================================

@frappe.whitelist()
def get_employees_for_filter(companies=None, category=None, txt=""):
    companies = _parse_list(companies); params = {"txt": f"%{txt}%"}
    conds = ["ss.docstatus=1","(ss.employee LIKE %(txt)s OR ss.employee_name LIKE %(txt)s)"]
    catj  = ""
    if companies: params["companies"] = tuple(companies); conds.append("ss.company IN %(companies)s")
    if category:  params["category"]  = category; catj = "INNER JOIN `tabCompany Link` cl_cat ON cl_cat.name=ss.employee AND cl_cat.category=%(category)s"
    return frappe.db.sql(
        f"SELECT DISTINCT ss.employee, ss.employee_name FROM `tabSalary Slip` ss {catj} "
        f"WHERE {' AND '.join(conds)} ORDER BY ss.employee_name LIMIT 50",
        params, as_dict=1
    )