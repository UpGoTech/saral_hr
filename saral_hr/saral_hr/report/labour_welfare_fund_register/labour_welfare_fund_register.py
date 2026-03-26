import frappe
import json

from frappe import _
from frappe.utils import flt
from frappe.utils.pdf import get_pdf

MONTH_MAP = {
    "January":1,"February":2,"March":3,"April":4,"May":5,"June":6,
    "July":7,"August":8,"September":9,"October":10,"November":11,"December":12,
}

B = "1px solid #000"

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
.r{text-align:right}.l{text-align:left}
.nd{text-align:center;padding:18px;color:#888;font-size:10px}
</style>"""

_SIG = '<div class="sig">' + "".join(
    f'<div class="sig-b"><div class="sig-l"></div><div class="sig-t">{l}</div></div>'
    for l in ["Prepared By", "Checked By", "Authorised Signatory"]
) + '</div>'

_NUMERIC_FT = ("Float", "Currency", "Int", "Percent")


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


def _get_data(f):
    cols = [
        _col("Employee ID",   "employee_id",  w=200),
        _col("Employee Name", "employee_name", w=300),
        _col("Net Salary",    "net_salary",   "Float", 160, precision=2),
        _col("Emp LWF",       "emp_lwf",      "Float", 190, precision=2),
        _col("Empr LWF",      "empr_lwf",     "Float", 180, precision=2),
        _col("Total LWF",     "total_lwf",    "Float", 180, precision=2),
    ]

    if not f.get("company"):
        return cols, []

    p = {}
    cond = _base_cond(f, p)
    catj = _cat_join(f, p)
    divc = _div_cond(f, p)

    slips = frappe.db.sql(
        f"""SELECT ss.name AS slip, ss.employee, ss.employee_name,
                   ss.net_salary, cl.employee AS eid
            FROM `tabSalary Slip` ss
            LEFT JOIN `tabCompany Link` cl ON cl.name=ss.employee
            {catj}
            WHERE {cond}{divc}
            ORDER BY ss.employee_name""",
        p, as_dict=1
    )
    if not slips: return cols, []

    sn = tuple(s.slip for s in slips)

    def _lm(pf):
        m = {}
        for r in frappe.db.sql(
            f"SELECT sd.parent AS slip, SUM(sd.amount) AS a "
            f"FROM `tabSalary Details` sd "
            f"WHERE sd.parent IN %(sn)s AND sd.parentfield=%(pf)s "
            f"AND LOWER(sd.salary_component) LIKE '%%welfare%%' AND sd.amount>0 "
            f"GROUP BY sd.parent",
            {"sn": sn, "pf": pf}, as_dict=1
        ):
            m[r.slip] = flt(r.a)
        return m

    em  = _lm("deductions")
    erm = _lm("employer_share")

    data = []
    gn = gel = grl = 0.0

    for s in slips:
        el  = flt(em.get(s.slip,  0))
        erl = flt(erm.get(s.slip, 0))
        tot = el + erl
        if tot <= 0: continue
        net = flt(s.net_salary, 2)
        gn += net; gel += el; grl += erl
        data.append({
            "employee_id":   s.eid or s.employee,
            "employee_name": s.employee_name,
            "net_salary":    net,
            "emp_lwf":       flt(el,  2),
            "empr_lwf":      flt(erl, 2),
            "total_lwf":     flt(tot, 2),
        })

    if data:
        data.append({
            "employee_id": "", "employee_name": "Total",
            "net_salary": flt(gn, 2), "emp_lwf": flt(gel, 2),
            "empr_lwf": flt(grl, 2), "total_lwf": flt(gel + grl, 2),
            "bold": 1,
        })

    return cols, data


def execute(filters=None):
    return _get_data(filters or {})


def _build_html(cols, data, co, mo, yr):
    hdr = (
        f'<div class="hdr"><div class="co">{co}</div>'
        f'<div class="ttl">Labour Welfare Fund Register</div>'
        f'<div class="per">For the Month of {mo} {yr}</div></div>'
    )
    thead = "<tr>" + "".join(
        f'<th class="{"r" if c.get("fieldtype","") in _NUMERIC_FT else "l"}">{c.get("label","")}</th>'
        for c in cols
    ) + "</tr>"

    if not data:
        tbody = f'<tr><td colspan="{len(cols)}" class="nd">No data for this period</td></tr>'
    else:
        tbody = ""
        for row in data:
            is_tot = bool(row.get("bold"))
            cls = ' class="tot"' if is_tot else ""
            tbody += f"<tr{cls}>"
            for c in cols:
                fn  = c.get("fieldname", "")
                val = row.get(fn, "")
                is_n = c.get("fieldtype", "") in _NUMERIC_FT
                if is_n:
                    tbody += f'<td class="r">{_fmt(val) if val not in ("",None) else ""}</td>'
                else:
                    tbody += f'<td class="l">{val or ""}</td>'
            tbody += "</tr>"

    return (
        f'<!DOCTYPE html><html><head><meta charset="UTF-8">{_CSS}</head>'
        f'<body>{hdr}<table><thead>{thead}</thead><tbody>{tbody}</tbody></table>{_SIG}</body></html>'
    )


def _save_pdf(html, prefix):
    pdf = get_pdf(html, options={"page-size":"A4","orientation":"Landscape","margin-top":"8mm","margin-right":"8mm","margin-bottom":"8mm","margin-left":"8mm","encoding":"UTF-8","no-outline":None})
    ts = frappe.utils.now_datetime().strftime("%Y%m%d_%H%M%S")
    fn = f"{prefix}_{ts}.pdf"
    with open(frappe.utils.get_files_path(fn, is_private=0), "wb") as fh: fh.write(pdf)
    doc = frappe.get_doc({"doctype":"File","file_name":fn,"is_private":0,"file_url":f"/files/{fn}"})
    doc.insert(ignore_permissions=True); frappe.db.commit()
    return doc.file_url


@frappe.whitelist()
def print_report(filters):
    if isinstance(filters, str): filters = json.loads(filters)
    cols, data = _get_data(filters)
    return _save_pdf(_build_html(cols, data, _company_label(filters), filters.get("month",""), filters.get("year","")), "Labour_Welfare_Fund_Register")