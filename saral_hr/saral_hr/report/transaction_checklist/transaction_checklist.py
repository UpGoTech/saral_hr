import frappe
import json

from frappe import _
from frappe.utils import flt
from frappe.utils.pdf import get_pdf

MONTH_MAP = {
    "January":1,"February":2,"March":3,"April":4,"May":5,"June":6,
    "July":7,"August":8,"September":9,"October":10,"November":11,"December":12,
}

EARNING_COMPONENTS = [
    ("Basic",                "BASIC"),
    ("Dearness Allowance",   "DA"),
    ("House Rent Allowance", "HRA"),
    ("Conveyance Allowance", "CONV"),
    ("Medical Allowance",    "MED"),
    ("Education Allowance",  "EDU"),
    ("Other Allowance",      "OA"),
    ("Variable Pay",         "VAR"),
    ("Arrears",              "ARREARS"),
]

DEDUCTION_COMPONENTS = [
    ("Employee -  PF",                 "PF"),
    ("Employer -  PF",                 "EPF"),
    ("Employee - ESIC",                "ESI"),
    ("Employer -  ESIC",               "EESI"),
    ("Professional Tax",               "PT"),
    ("Employee -Labour Welfare Fund",  "Employee - LWF"),
    ("Employer - Labour Welfare Fund", "Employer - LWF"),
    ("Employee -Bonus",                "BONUS"),
    ("Employer - Bonus",               "Employer - bonus"),
    ("Employer - Gratuity",            "GRAT"),
    ("Loan",                           "Loan"),
    ("Advance",                        "ADV"),
    ("Retention",                      "RET"),
    ("Other Deduction - 1",            "OD -1"),
]

B = "1px solid #000"

_CSS = """<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Arial,sans-serif;font-size:11px;color:#000;background:#fff}
.hdr{text-align:center;border-bottom:2px solid #000;padding:10px 6px 6px;margin-bottom:6px}
.hdr .co{font-size:22px;font-weight:900;letter-spacing:1px;text-transform:uppercase}
.hdr .ttl{font-size:16px;font-weight:700;margin-top:2px}
.hdr .per{font-size:13px;margin-top:2px}
.sig{display:flex;justify-content:space-between;margin-top:16px;padding-top:8px}
.sig-b{text-align:center;width:180px}
.sig-l{border-top:1px solid #000;margin-bottom:4px}
.sig-t{font-size:13px;color:#333}
table{width:100%;border-collapse:collapse;margin-top:8px;table-layout:fixed}
th{border:1px solid #000;padding:3px 3px;font-size:10px;font-weight:700;background:#f0f0f0;color:#000;white-space:nowrap}
td{border:1px solid #000;padding:3px 3px;font-size:11px;vertical-align:middle;color:#000}
tr.tot td{background:#e8e8e8;font-weight:700}
.nd{text-align:center;padding:10px;color:#888;font-size:11px}
</style>"""

_SIG = '<div class="sig">' + "".join(
    f'<div class="sig-b"><div class="sig-l"></div><div class="sig-t">{l}</div></div>'
    for l in ["Prepared By", "Checked By", "Authorised Signatory"]
) + '</div>'

_SL = {
    "Basic":"Basic","Dearness Allowance":"DA","House Rent Allowance":"HRA",
    "Conveyance Allowance":"Conv","Medical Allowance":"Med",
    "Education Allowance":"Edu","Other Allowance":"OA",
    "Variable Pay":"Var Pay","Arrears":"Arrears",
    "Employee -  PF":"Emp PF","Employer -  PF":"Empr PF",
    "Employee - ESIC":"Emp ESI","Employer -  ESIC":"Empr ESI",
    "Professional Tax":"PT",
    "Employee -Labour Welfare Fund":"Emp LWF",
    "Employer - Labour Welfare Fund":"Empr LWF",
    "Employee -Bonus":"Emp Bonus","Employer - Bonus":"Empr Bonus",
    "Employer - Gratuity":"Grat","Loan":"Loan","Advance":"Adv",
    "Retention":"Ret","Other Deduction - 1":"OD-1",
}

def _sl(lbl):
    return _SL.get(lbl.split("(")[0].strip(), lbl.split("(")[0].strip()) or "&nbsp;"

def _sanitize(a):
    return a.strip().lower().replace(" ", "_").replace("-", "_").replace("__", "_")


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

def _date_range(f):
    import calendar
    m = MONTH_MAP.get(f.get("month", ""))
    y = int(f.get("year", 0) or 0)
    if not m or not y:
        return None, None
    return f"{y}-{m:02d}-01", f"{y}-{m:02d}-{calendar.monthrange(y, m)[1]:02d}"

def _company_label(f):
    c = _parse_list(f.get("company"))
    return ", ".join(c) if c else (frappe.defaults.get_global_default("company") or "")

def _fmt(v):
    if v is None or v == "": return ""
    try: return f"{float(v):,.2f}"
    except (TypeError, ValueError): return str(v)

def _fetch_comps(sn, pf):
    if not sn: return {}
    r = {}
    for x in frappe.db.sql(
        "SELECT sd.parent AS slip, sd.salary_component AS comp, sd.amount "
        "FROM `tabSalary Details` sd "
        "WHERE sd.parent IN %(sn)s AND sd.parentfield=%(pf)s",
        {"sn": tuple(sn), "pf": pf}, as_dict=1
    ):
        r.setdefault(x["slip"], {})[x["comp"]] = x["amount"]
    return r


def _get_data(f):
    cols = [
        _col("Employee",      "employee",      w=110),
        _col("Employee Name", "employee_name", w=150),
        _col("Payment Days",  "payment_days",  "Float", 90,  precision=2),
        _col("Absent",        "absent_days",   "Float", 55,  precision=2),
        _col("LWP",           "total_lwp",     "Float", 55,  precision=2),
    ]
    for lbl, abbr in EARNING_COMPONENTS:
        fn = f"earn_{_sanitize(abbr)}"
        if abbr == "VAR":
            cols.append(_col("Variable Pay (VAR %)", fn, "Data", 120))
        else:
            cols.append(_col(f"{lbl} ({abbr})", fn, "Float", 130, precision=2))
    for lbl, abbr in DEDUCTION_COMPONENTS:
        cols.append(_col(f"{lbl} ({abbr})", f"ded_{_sanitize(abbr)}", "Float", 130, precision=2))
    cols += [
        _col("Total Earnings",   "total_earnings",   "Float", 120, precision=2),
        _col("Total Deductions", "total_deductions", "Float", 120, precision=2),
        _col("Net Salary",       "net_salary",       "Float", 120, precision=2),
    ]

    if not f.get("company"):
        return cols, []

    p = {}
    s, e = _date_range(f)
    if not s:
        return cols, []

    p.update(start_date=s, end_date=e)
    conds = [
        "ss.docstatus=1",
        "ss.start_date>=%(start_date)s",
        "ss.end_date<=%(end_date)s",
    ]

    co = _parse_list(f.get("company"))
    if co:
        p["companies"] = tuple(co)
        conds.append("ss.company IN %(companies)s")

    em_filter = _parse_list(f.get("employee"))
    if em_filter:
        p["employees"] = tuple(em_filter)
        conds.append("ss.employee IN %(employees)s")

    catj = ""
    cat  = f.get("category")
    if cat:
        p["category"] = cat
        catj = "INNER JOIN `tabCompany Link` cl_cat ON cl_cat.name=ss.employee AND cl_cat.category=%(category)s"

    divs = _parse_list(f.get("division"))
    if divs:
        p["divisions"] = tuple(divs)
        conds.append(
            "ss.employee IN (SELECT name FROM `tabCompany Link` "
            "WHERE division IN %(divisions)s OR department IN %(divisions)s)"
        )

    w = " AND ".join(conds)

    slips = frappe.db.sql(
        f"""
        SELECT ss.name AS slip, ss.employee, ss.employee_name,
               ss.payment_days, ss.absent_days, ss.total_lwp, ss.net_salary
        FROM `tabSalary Slip` ss {catj}
        WHERE {w}
        ORDER BY ss.employee_name
        """,
        p, as_dict=1
    )
    if not slips:
        return cols, []

    sn   = [sl["slip"]     for sl in slips]
    eids = [sl["employee"] for sl in slips]

    mo, yr  = f.get("month", ""), f.get("year", "")
    vpa_key = f"{yr} - {mo}"
    vpm     = {}
    if frappe.db.exists("Variable Pay Assignment", vpa_key):
        vpm = {
            r.division: flt(r.percentage)
            for r in frappe.db.sql(
                "SELECT division, percentage FROM `tabVariable Pay Detail Table` "
                "WHERE parent=%(v)s AND parenttype='Variable Pay Assignment'",
                {"v": vpa_key}, as_dict=1
            )
        }

    dm2 = {}
    if eids:
        for r in frappe.db.sql(
            "SELECT cl.name AS cln, cl.division AS division_name "
            "FROM `tabCompany Link` cl WHERE cl.name IN %(ids)s",
            {"ids": tuple(eids)}, as_dict=1
        ):
            dm2[r.cln] = r.division_name

    em   = _fetch_comps(sn, "earnings")
    dmap = _fetch_comps(sn, "deductions")

    data  = []
    grand = {f"earn_{_sanitize(a)}": 0.0 for _, a in EARNING_COMPONENTS}
    grand.update({f"ded_{_sanitize(a)}": 0.0 for _, a in DEDUCTION_COMPONENTS})
    grand.update(
        total_earnings=0.0, total_deductions=0.0, net_salary=0.0,
        payment_days=0.0, absent_days=0.0, total_lwp=0.0,
    )

    for sl in slips:
        se  = em.get(sl["slip"],   {})
        sd  = dmap.get(sl["slip"], {})
        div = dm2.get(sl["employee"], "")
        row = {
            "employee":      sl["employee"],
            "employee_name": sl["employee_name"],
            "payment_days":  flt(sl["payment_days"],         2),
            "absent_days":   flt(sl.get("absent_days") or 0, 2),
            "total_lwp":     flt(sl["total_lwp"] or 0,       2),
            "net_salary":    flt(sl["net_salary"],            2),
        }
        te = td = 0.0

        for lbl, abbr in EARNING_COMPONENTS:
            if abbr == "VAR":
                pct = vpm.get(div)
                row["earn_var"] = f"{pct}%" if pct is not None else ""
                amt = se.get(lbl)
                if amt:
                    te += amt
                    grand["earn_var"] += amt
            else:
                amt = se.get(lbl)
                if amt is not None:
                    v = flt(amt, 2)
                    row[f"earn_{_sanitize(abbr)}"] = v
                    te += v
                    grand[f"earn_{_sanitize(abbr)}"] += v

        row["total_earnings"]    = flt(te, 2)
        grand["total_earnings"] += te

        for lbl, abbr in DEDUCTION_COMPONENTS:
            amt = sd.get(lbl)
            if amt is not None:
                v = flt(amt, 2)
                row[f"ded_{_sanitize(abbr)}"] = v
                td += v
                grand[f"ded_{_sanitize(abbr)}"] += v

        row["total_deductions"]    = flt(td, 2)
        grand["total_deductions"] += td

        grand["net_salary"]   += flt(sl["net_salary"],           2)
        grand["payment_days"] += flt(sl["payment_days"],         2)
        grand["absent_days"]  += flt(sl.get("absent_days") or 0, 2)
        grand["total_lwp"]    += flt(sl["total_lwp"] or 0,       2)
        data.append(row)

    if data:
        data.append({
            "employee":      "",
            "employee_name": "Total",
            "bold":          1,
            **{k: v for k, v in grand.items() if k != "payment_days"},
        })

    return cols, data


def execute(filters=None):
    return _get_data(filters or {})


TH_C = f"border:{B};padding:3px 3px;font-size:11px;font-weight:700;text-align:center;background:#f0f0f0;"
TH_R = f"border:{B};padding:3px 3px;font-size:11px;font-weight:700;text-align:right;background:#f0f0f0;"
TH_L = f"border:{B};padding:3px 3px;font-size:11px;font-weight:700;text-align:left;background:#f0f0f0;"
TD_S = f"border:{B};padding:3px 3px;font-size:11px;vertical-align:middle;"
TS_S = f"border:{B};padding:3px 3px;font-size:11px;font-weight:700;background:#e8e8e8;vertical-align:middle;"
SUB  = f"font-size:10px;display:block;margin-top:1px;"


def _build_html(cols, data, co, mo, yr):
    hdr = (
        f'<div class="hdr">'
        f'<div class="co">{co}</div>'
        f'<div class="ttl">Transaction Checklist</div>'
        f'<div class="per">For the Month of {mo} {yr}</div>'
        f'</div>'
    )

    if not data:
        return (
            f'<!DOCTYPE html><html><head><meta charset="UTF-8">{_CSS}</head>'
            f'<body>{hdr}<p class="nd">No data for this period</p>{_SIG}</body></html>'
        )

    LAST = {
        "earn_grat", "ded_grat", "ded_loan", "ded_adv", "ded_ret",
        "net_salary", "total_earnings", "total_deductions",
    }
    od1_fn = next(
        (c["fieldname"] for c in cols
         if c["fieldname"].startswith("ded_") and "od" in c["fieldname"]),
        None
    )
    if od1_fn:
        LAST.add(od1_fn)

    ec = [c for c in cols if c["fieldname"].startswith("earn_") and c["fieldname"] not in LAST]
    dc = [c for c in cols if c["fieldname"].startswith("ded_")  and c["fieldname"] not in LAST]
    mp = max(len(ec), len(dc))

    def _thead():
        h  = f'<table style="width:100%;border-collapse:collapse;table-layout:fixed;">'
        h += f'<thead><tr>'
        h += f'<th style="{TH_L}width:110px;">Employee<br><span style="{SUB}">Name</span></th>'
        h += f'<th style="{TH_C}width:45px;">Days</th>'
        h += f'<th style="{TH_C}width:45px;">Abs<br><span style="{SUB}">LWP</span></th>'
        for i in range(mp):
            el = _sl(ec[i]["label"]) if i < len(ec) else "&nbsp;"
            dl = _sl(dc[i]["label"]) if i < len(dc) else "&nbsp;"
            h += f'<th style="{TH_R}min-width:55px;">{el}<br><span style="{SUB}">{dl}</span></th>'
        h += f'<th style="{TH_R}width:70px;">Grat<br><span style="{SUB}">Loan</span></th>'
        h += f'<th style="{TH_R}width:60px;">Adv<br><span style="{SUB}">Ret</span></th>'
        h += f'<th style="{TH_R}width:70px;">OD-1<br><span style="{SUB}">Net Sal</span></th>'
        h += f'<th style="{TH_R}width:80px;">Earn<br><span style="{SUB}">Ded</span></th>'
        h += f'</tr></thead>'
        return h

    def _build_rows(rows):
        h = "<tbody>"
        for row in rows:
            is_tot = row.get("bold") == 1
            td     = TS_S if is_tot else TD_S
            h += "<tr>"
            emp_sub = "" if is_tot else f'<span style="{SUB}color:#555;">{row.get("employee","")}</span>'
            h += f'<td style="{td}text-align:left;"><strong>{row.get("employee_name","")}</strong>{emp_sub}</td>'
            h += f'<td style="{td}text-align:center;">{row.get("payment_days","")}</td>'
            h += (
                f'<td style="{td}text-align:center;">'
                f'{row.get("absent_days") or "0"}'
                f'<span style="{SUB}">{_fmt(row.get("total_lwp")) or "0"}</span>'
                f'</td>'
            )
            for i in range(mp):
                ev = _fmt(row.get(ec[i]["fieldname"])) if i < len(ec) else ""
                dv = _fmt(row.get(dc[i]["fieldname"])) if i < len(dc) else ""
                if i < len(ec) and ec[i]["fieldname"] == "earn_var":
                    ev = row.get("earn_var") or ""
                h += (
                    f'<td style="{td}text-align:right;">'
                    f'{ev or "&nbsp;"}'
                    f'<span style="{SUB}">{dv or "&nbsp;"}</span>'
                    f'</td>'
                )
            h += (
                f'<td style="{td}text-align:right;">'
                f'{_fmt(row.get("earn_grat")) or "&nbsp;"}'
                f'<span style="{SUB}">{_fmt(row.get("ded_loan")) or "&nbsp;"}</span>'
                f'</td>'
            )
            h += (
                f'<td style="{td}text-align:right;">'
                f'{_fmt(row.get("ded_adv")) or "&nbsp;"}'
                f'<span style="{SUB}">{_fmt(row.get("ded_ret")) or "&nbsp;"}</span>'
                f'</td>'
            )
            h += (
                f'<td style="{td}text-align:right;">'
                f'{(_fmt(row.get(od1_fn)) if od1_fn else "") or "&nbsp;"}'
                f'<span style="{SUB}">{_fmt(row.get("net_salary"))}</span>'
                f'</td>'
            )
            h += (
                f'<td style="{td}text-align:right;">'
                f'{_fmt(row.get("total_earnings"))}'
                f'<span style="{SUB}">{_fmt(row.get("total_deductions"))}</span>'
                f'</td>'
            )
            h += "</tr>"
        h += "</tbody></table>"
        return h

    detail_rows = [r for r in data if not r.get("bold")]
    total_row   = [r for r in data if r.get("bold")]

    FIRST, OTHER = 20, 25
    pages, idx, first = [], 0, True
    while idx < len(detail_rows):
        lim = FIRST if first else OTHER
        pages.append(detail_rows[idx: idx + lim])
        idx += lim
        first = False

    parts = []
    for pn, pr in enumerate(pages):
        pb   = '<div style="page-break-before:always;"></div>' if pn > 0 else ""
        last = (pn == len(pages) - 1)
        rows = pr + (total_row if last else [])
        parts.append(pb + hdr + _thead() + _build_rows(rows))

    return (
        f'<!DOCTYPE html><html><head><meta charset="UTF-8">{_CSS}</head>'
        f'<body>{"".join(parts)}{_SIG}</body></html>'
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
    co   = _company_label(filters)
    mo   = filters.get("month", "")
    yr   = filters.get("year",  "")
    html = _build_html(cols, data, co, mo, yr)
    return _save_pdf(html, "Transaction_Checklist")