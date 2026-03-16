import frappe
import json
import calendar

from frappe import _
from frappe.utils import flt
from frappe.utils.pdf import get_pdf

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MONTH_MAP = {
    "January":1,"February":2,"March":3,"April":4,"May":5,"June":6,
    "July":7,"August":8,"September":9,"October":10,"November":11,"December":12,
}

PF_EMP_COMP   = "Employee PF"
PF_EMPR_COMP  = "Employer PF"
PF_EPS_COMP   = "Employer EPS"
PF_EDLI_COMP  = "Employer EDLI"
PF_ADMIN_COMP = "Employer PF Admin Charges"

B     = "1px solid #000"
TH_L  = f"border:{B};padding:5px 7px;font-size:10px;font-weight:700;background:#f0f0f0;color:#000;text-align:left;white-space:nowrap;"
TH_R  = f"border:{B};padding:5px 7px;font-size:10px;font-weight:700;background:#f0f0f0;color:#000;text-align:right;white-space:nowrap;"
TD_L  = f"border:{B};padding:5px 7px;font-size:10px;vertical-align:middle;color:#000;text-align:left;"
TD_R  = f"border:{B};padding:5px 7px;font-size:10px;vertical-align:middle;color:#000;text-align:right;"
TS_L  = f"border:{B};padding:5px 7px;font-size:10px;font-weight:700;background:#e8e8e8;color:#000;text-align:left;"
TS_R  = f"border:{B};padding:5px 7px;font-size:10px;font-weight:700;background:#e8e8e8;color:#000;text-align:right;"

_CSS = """<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Arial,sans-serif;font-size:10px;color:#000;background:#fff}
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
</style>"""

_SIG = '<div class="sig">' + "".join(
    f'<div class="sig-b"><div class="sig-l"></div><div class="sig-t">{l}</div></div>'
    for l in ["Prepared By", "Checked By", "Authorised Signatory"]
) + '</div>'


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

def _col(label, fn, ft="Data", w=120, **kw):
    return {"label": _(label), "fieldname": fn, "fieldtype": ft, "width": w, **kw}

def _start_date(f):
    m = MONTH_MAP.get(f.get("month", ""))
    y = f.get("year", "")
    return f"{y}-{m:02d}-01" if m and y else None

def _base_cond(f, p):
    c = ["ss.docstatus=1"]
    sd = _start_date(f)
    if sd: p["start_date"] = sd; c.append("ss.start_date=%(start_date)s")
    co = _parse_list(f.get("company"))
    if co: p["companies"] = tuple(co); c.append("ss.company IN %(companies)s")
    em = _parse_list(f.get("employee"))
    if em: p["employees"] = tuple(em); c.append("ss.employee IN %(employees)s")
    return " AND ".join(c)

def _cat_join(f, p):
    cat = f.get("category")
    if not cat: return ""
    p["category"] = cat
    return "INNER JOIN `tabCompany Link` cl_cat ON cl_cat.name=ss.employee AND cl_cat.category=%(category)s"

def _div_cond(f, p):
    d = _parse_list(f.get("division"))
    if not d: return ""
    p["divisions"] = tuple(d)
    return " AND ss.employee IN (SELECT name FROM `tabCompany Link` WHERE division IN %(divisions)s OR department IN %(divisions)s)"

def _company_label(f):
    c = _parse_list(f.get("company"))
    return ", ".join(c) if c else (frappe.defaults.get_global_default("company") or "")

def _fmt(v):
    if v is None or v == "": return ""
    try: return f"{float(v):,.2f}"
    except (TypeError, ValueError): return str(v)


# ---------------------------------------------------------------------------
# Core data function
# ---------------------------------------------------------------------------

def _get_data(f):
    cols = [
        _col("PF No.",          "pf_no",          w=100),
        _col("UAN No.",         "uan_no",          w=100),
        _col("Employee Name",   "employee_name",   w=180),
        _col("Employee ID",     "employee_id",     w=110),
        _col("Days (LWP+ABS)",  "days",    "Float", 75,  precision=1),
        _col("Absent",          "absent",  "Float", 60,  precision=1),
        _col("Gross Salary",    "gross",   "Float", 110, precision=2),
        _col("Basic + DA",      "basic_da","Float", 110, precision=2),
        _col("Emp PF",          "emp_pf",  "Float", 90,  precision=2),
        _col("Empr. EPS",       "employer_eps",   "Float", 90, precision=2),
        _col("Empr. PF",        "employer_pf",    "Float", 90, precision=2),
        _col("Empr. EDLI",      "employer_edli",  "Float", 90, precision=2),
        _col("PF Admin",        "employer_admin",  "Float", 90, precision=2),
        _col("Total",           "total_amount",    "Float", 90, precision=2),
        _col("DOJ",             "date_of_joining", "Date", 100),
        _col("DOB",             "date_of_birth",   "Date", 100),
    ]

    if not f.get("company"):
        return cols, []

    p = {}
    cond = _base_cond(f, p)
    catj = _cat_join(f, p)
    divc = _div_cond(f, p)

    slips = frappe.db.sql(
        f"""
        SELECT ss.name AS slip_name, ss.employee AS eid, ss.employee_name,
               ss.payment_days AS days, ss.absent_days AS absent,
               ss.total_earnings AS gross
        FROM `tabSalary Slip` ss
        {catj}
        WHERE {cond}{divc}
        ORDER BY ss.employee_name
        """,
        p, as_dict=1
    )
    if not slips: return cols, []

    sn   = tuple(s.slip_name for s in slips)
    eids = tuple(s.eid for s in slips)

    # Basic + DA
    bda = {
        r.slip_name: flt(r.v)
        for r in frappe.db.sql(
            """SELECT sd.parent AS slip_name, SUM(sd.amount) AS v
               FROM `tabSalary Details` sd
               WHERE sd.parent IN %(sn)s
                 AND sd.parenttype='Salary Slip'
                 AND sd.parentfield='earnings'
                 AND (LOWER(sd.salary_component) LIKE '%%basic%%'
                      OR LOWER(sd.salary_component) LIKE '%%dearness%%'
                      OR LOWER(sd.salary_component) LIKE '%% da'
                      OR sd.salary_component='DA')
               GROUP BY sd.parent""",
            {"sn": sn}, as_dict=1
        )
    }

    # Employee PF (deductions)
    ep = {
        r.slip_name: flt(r.v)
        for r in frappe.db.sql(
            """SELECT sd.parent AS slip_name, SUM(sd.amount) AS v
               FROM `tabSalary Details` sd
               WHERE sd.parent IN %(sn)s
                 AND sd.parenttype='Salary Slip'
                 AND sd.parentfield='deductions'
                 AND sd.salary_component=%(c)s
               GROUP BY sd.parent""",
            {"sn": sn, "c": PF_EMP_COMP}, as_dict=1
        )
    }

    def _fe(comp):
        return {
            r.slip_name: flt(r.v)
            for r in frappe.db.sql(
                """SELECT sd.parent AS slip_name, SUM(sd.amount) AS v
                   FROM `tabSalary Details` sd
                   WHERE sd.parent IN %(sn)s
                     AND sd.parenttype='Salary Slip'
                     AND sd.parentfield='employer_share'
                     AND sd.salary_component=%(c)s
                   GROUP BY sd.parent""",
                {"sn": sn, "c": comp}, as_dict=1
            )
        }

    erpf  = _fe(PF_EMPR_COMP)
    ereps = _fe(PF_EPS_COMP)
    eredli= _fe(PF_EDLI_COMP)
    eradm = _fe(PF_ADMIN_COMP)

    em = {
        r.name: r
        for r in frappe.db.sql(
            """SELECT e.name, e.employee_pf_account AS pf_no,
                      e.pf_uan_number AS uan_no, e.date_of_birth,
                      cl.date_of_joining
               FROM `tabEmployee` e
               LEFT JOIN `tabCompany Link` cl ON cl.name=e.name
               WHERE e.name IN %(ids)s""",
            {"ids": eids}, as_dict=1
        )
    }

    data = []
    tot  = {k: 0.0 for k in ["gross","basic_da","emp_pf","employer_eps","employer_pf","employer_edli","employer_admin","total_amount"]}

    for s in slips:
        emp  = em.get(s.eid, frappe._dict())
        sn_  = s.slip_name
        g    = flt(s.gross,   2)
        b    = flt(bda.get(sn_, 0), 2)
        epf  = flt(ep.get(sn_,  0), 2)
        erp  = flt(erpf.get(sn_, 0), 2)
        ere  = flt(ereps.get(sn_,0), 2)
        erd  = flt(eredli.get(sn_,0),2)
        era  = flt(eradm.get(sn_,0), 2)
        tol  = flt(epf + erp + ere + erd + era, 2)

        for k, v in [("gross",g),("basic_da",b),("emp_pf",epf),
                     ("employer_eps",ere),("employer_pf",erp),
                     ("employer_edli",erd),("employer_admin",era),("total_amount",tol)]:
            tot[k] += v

        data.append({
            "pf_no":           emp.get("pf_no")  or "",
            "uan_no":          emp.get("uan_no") or "",
            "employee_name":   s.employee_name,
            "employee_id":     s.eid,
            "days":            flt(s.days,   1),
            "absent":          flt(s.absent, 1),
            "gross":           g,
            "basic_da":        b,
            "emp_pf":          epf,
            "employer_eps":    ere,
            "employer_pf":     erp,
            "employer_edli":   erd,
            "employer_admin":  era,
            "total_amount":    tol,
            "date_of_joining": emp.get("date_of_joining") or "",
            "date_of_birth":   emp.get("date_of_birth")   or "",
            "_row_type":       "detail",
        })

    data.append({
        "pf_no": "", "uan_no": "", "employee_name": "Total", "employee_id": "",
        "days": None, "absent": None,
        **{k: flt(v, 2) for k, v in tot.items()},
        "date_of_joining": "", "date_of_birth": "",
        "bold": 1, "_row_type": "total",
    })

    return cols, data


# ---------------------------------------------------------------------------
# Frappe report entry-point
# ---------------------------------------------------------------------------

def execute(filters=None):
    return _get_data(filters or {})


# ---------------------------------------------------------------------------
# PDF helpers
# ---------------------------------------------------------------------------

# Columns whose cells are blanked on the total row
_SKIP_ON_TOTAL = {"pf_no", "uan_no", "days", "absent", "date_of_joining", "date_of_birth"}

# Columns that are right-aligned (numeric)
_NUMERIC_FT = ("Float", "Currency", "Int", "Percent")


def _build_html(cols, data, co, mo, yr):
    hdr = (
        f'<div class="hdr">'
        f'<div class="co">{co}</div>'
        f'<div class="ttl">Provident Fund Register</div>'
        f'<div class="per">For the Month of {mo} {yr}</div>'
        f'</div>'
    )

    # thead
    thead = "<tr>"
    for c in cols:
        is_n = c.get("fieldtype", "") in _NUMERIC_FT
        thead += f'<th class="{"r" if is_n else "l"}">{c.get("label","")}</th>'
    thead += "</tr>"

    # tbody
    if not data:
        ncols = len(cols)
        tbody = f'<tr><td colspan="{ncols}" class="nd">No data for this period</td></tr>'
    else:
        tbody = ""
        for row in data:
            is_tot = bool(row.get("bold") or row.get("_row_type") == "total")
            cls    = ' class="tot"' if is_tot else ""
            tbody += f"<tr{cls}>"
            for c in cols:
                fn   = c.get("fieldname", "")
                val  = row.get(fn, "")
                is_n = c.get("fieldtype", "") in _NUMERIC_FT
                if is_tot and fn in _SKIP_ON_TOTAL:
                    tbody += f'<td class="{"r" if is_n else "l"}"></td>'
                elif is_n:
                    tbody += f'<td class="r">{_fmt(val) if val not in ("", None) else ""}</td>'
                else:
                    tbody += f'<td class="l">{val or ""}</td>'
            tbody += "</tr>"

    table = f"<table><thead>{thead}</thead><tbody>{tbody}</tbody></table>"
    return (
        f'<!DOCTYPE html><html><head><meta charset="UTF-8">{_CSS}</head>'
        f'<body>{hdr}{table}{_SIG}</body></html>'
    )


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


@frappe.whitelist()
def print_report(filters):
    if isinstance(filters, str):
        filters = json.loads(filters)
    cols, data = _get_data(filters)
    co = _company_label(filters)
    mo = filters.get("month", "")
    yr = filters.get("year",  "")
    html = _build_html(cols, data, co, mo, yr)
    return _save_pdf(html, "Provident_Fund_Register")