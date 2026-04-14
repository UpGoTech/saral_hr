# Copyright (c) 2026, sj and contributors
# For license information, please see license.txt

import frappe
import calendar
import json
from datetime import datetime
from frappe.utils.pdf import get_pdf

B = "1px solid #000"
ROWS_FIRST_PAGE = 21
ROWS_OTHER_PAGE = 23


def execute(filters=None):
    filters = filters or {}
    return get_columns(), get_data(filters)


def get_columns():
    return [
        {"fieldname": "sr_no",            "label": "Sr",               "fieldtype": "Int",   "width":  50},
        {"fieldname": "employee",         "label": "Employee ID",      "fieldtype": "Link",  "options": "Employee",             "width": 140},
        {"fieldname": "employee_name",    "label": "Employee Name",    "fieldtype": "Data",                                     "width": 220},
        {"fieldname": "advance_id",       "label": "Advance ID",       "fieldtype": "Link",  "options": "Employee Loan Advance","width": 200},
        {"fieldname": "total_advance",    "label": "Total Advance",    "fieldtype": "Float",                                    "width": 150},
        {"fieldname": "recovered_advance","label": "Recovered Advance","fieldtype": "Float",                                    "width": 150},
        {"fieldname": "pending_advance",  "label": "Pending Advance",  "fieldtype": "Float",                                    "width": 150},
    ]


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_employees_with_advances(doctype, txt, searchfield, start, page_len, filters):
    company = filters.get("company") if filters else None
    params  = {"txt": f"%{txt}%", "start": start, "page_len": page_len}
    company_cond = ""
    if company:
        company_cond = "AND ela.company = %(company)s"
        params["company"] = company
    results = frappe.db.sql("""
        SELECT DISTINCT ela.employee,
               COALESCE(e.employee_name, ela.full_name, ela.employee) AS employee_name
        FROM `tabEmployee Loan Advance` ela
        INNER JOIN `tabEmployee` e ON e.name = ela.employee
        WHERE ela.docstatus = 1 AND ela.type = 'Advance'
              {company_cond}
              AND (ela.employee LIKE %(txt)s OR e.employee_name LIKE %(txt)s)
        ORDER BY ela.employee ASC
        LIMIT %(page_len)s OFFSET %(start)s
    """.format(company_cond=company_cond), params)
    return [[r[0], r[1] or r[0]] for r in results]


def build_conditions(filters):
    conditions, values = "", {}
    if filters.get("company"):
        conditions += " AND ela.company = %(company)s"
        values["company"] = filters["company"]
    if filters.get("employee"):
        conditions += " AND ela.employee = %(employee)s"
        values["employee"] = filters["employee"]
    if filters.get("year") or filters.get("month"):
        date_from, date_to = get_date_range(filters)
        if date_from and date_to:
            conditions += " AND ela.date BETWEEN %(date_from)s AND %(date_to)s"
            values["date_from"] = date_from
            values["date_to"]   = date_to
    return conditions, values


def get_date_range(filters):
    year  = filters.get("year")
    month = filters.get("month")
    if year and month:
        try:
            dt       = datetime.strptime(f"{month} {year}", "%B %Y")
            last_day = calendar.monthrange(dt.year, dt.month)[1]
            return dt.strftime("%Y-%m-01"), dt.strftime(f"%Y-%m-{last_day:02d}")
        except Exception:
            return None, None
    elif year:
        return f"{year}-01-01", f"{year}-12-31"
    return None, None


def get_data(filters):
    conditions, values = build_conditions(filters)

    rows = frappe.db.sql(
        f"""
        SELECT
            ela.name AS advance_id,
            ela.employee,
            ela.full_name AS employee_name,
            SUM(ela.amount) AS total_advance,
            SUM(CASE WHEN ela.is_deducted = 1 THEN ela.amount ELSE 0 END) AS recovered_advance,
            SUM(CASE WHEN ela.is_deducted = 0 THEN ela.amount ELSE 0 END) AS pending_advance
        FROM `tabEmployee Loan Advance` ela
        WHERE ela.type = 'Advance' AND ela.docstatus = 1
              {conditions}
        GROUP BY ela.name, ela.employee, ela.full_name
        ORDER BY ela.employee ASC
        """,
        values, as_dict=True,
    )

    if not rows:
        return []

    # add serial numbers
    for i, r in enumerate(rows, 1):
        r["sr_no"] = i

    total_row = {
        "sr_no":            "",
        "employee":         "",
        "employee_name":    "Total",
        "advance_id":       "",
        "total_advance":    round(sum(r.get("total_advance",     0) or 0 for r in rows), 2),
        "recovered_advance":round(sum(r.get("recovered_advance", 0) or 0 for r in rows), 2),
        "pending_advance":  round(sum(r.get("pending_advance",   0) or 0 for r in rows), 2),
        "bold":             1,
    }
    rows.append(total_row)
    return rows


# ---------------------------------------------------------------------------
# HTML builder — Other Bank Advice structure
# ---------------------------------------------------------------------------

_CSS = """<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Arial,sans-serif;font-size:10px;color:#000;background:#fff}
.hdr{text-align:center;border-bottom:2px solid #000;padding:6px 6px 5px;margin-bottom:4px;}
.hdr .co{font-size:18px;font-weight:900;letter-spacing:1px;text-transform:uppercase}
.hdr .ttl{font-size:13px;font-weight:700;margin-top:2px}
.hdr .per{font-size:11px;margin-top:2px}
.cont-hdr{text-align:center;font-size:9px;color:#555;margin-bottom:3px;border-bottom:1px solid #000;padding-bottom:2px;}
table.data-tbl{width:100%;border-collapse:collapse;table-layout:fixed;}
table.data-tbl th{border:1px solid #000;padding:4px 6px;font-size:10px;font-weight:700;background:#f0f0f0;color:#000;white-space:nowrap;text-align:center;vertical-align:middle;}
table.data-tbl td{border:1px solid #000;padding:4px 6px;font-size:10px;vertical-align:middle;}
.nd{text-align:center;padding:14px;color:#888;font-size:10px}
.pg-foot{text-align:right;font-size:8.5px;color:#555;margin-top:2px;}
.sig{display:flex;justify-content:space-between;width:100%;margin-top:18px;padding-top:6px;}
.sig-b{text-align:center;width:170px}
.sig-l{border-top:1px solid #000;margin-bottom:3px}
.sig-t{font-size:10px;color:#333}
.sig-d{font-size:9px;color:#555;margin-top:5px}
</style>"""

_NUMERIC = {"total_advance", "recovered_advance", "pending_advance"}


def _sig_html():
    labels = ["Prepared By", "Checked By", "Authorised Signatory"]
    blocks = "".join(
        '<div class="sig-b"><div class="sig-l"></div>'
        '<div class="sig-t">{l}</div>'
        '<div class="sig-d">Date: ___________</div></div>'.format(l=l)
        for l in labels
    )
    return '<div class="sig">{}</div>'.format(blocks)


def _fmt(v):
    if v is None or v == "": return ""
    try: return "{:,.2f}".format(float(v))
    except: return str(v)


def _build_html(cols, data, co, mo, yr):
    col_pct = {
        "sr_no":            "4%",
        "employee":         "12%",
        "employee_name":    "28%",
        "advance_id":       "20%",
        "total_advance":    "12%",
        "recovered_advance":"12%",
        "pending_advance":  "12%",
    }
    cg = "<colgroup>" + "".join(
        '<col style="width:{w};"/>'.format(w=col_pct.get(c["fieldname"], "12%"))
        for c in cols
    ) + "</colgroup>"

    period = "For the Month of {mo} {yr}".format(mo=mo, yr=yr) if mo and yr else ("For the Year {yr}".format(yr=yr) if yr else "All Records")

    page1_hdr = (
        '<div class="hdr"><div class="co">{co}</div>'
        '<div class="ttl">Advance Register</div>'
        '<div class="per">{period}</div></div>'
    ).format(co=co, period=period)

    cont_hdr = (
        '<div class="cont-hdr">{co} &mdash; Advance Register &mdash; {period} (contd.)</div>'
    ).format(co=co, period=period)

    TH = "border:{B};padding:4px 6px;font-size:10px;font-weight:700;background:#f0f0f0;text-align:center;vertical-align:middle;".format(B=B)
    header_tr = "<tr>" + "".join(
        '<th style="{th}">{lbl}</th>'.format(th=TH, lbl=c["label"]) for c in cols
    ) + "</tr>"

    def _row_html(row, idx):
        is_tot = bool(row.get("bold"))
        bg     = "#e8e8e8" if is_tot else ("#f9f9f9" if idx % 2 else "#ffffff")
        fw     = "font-weight:700;" if is_tot else ""
        html   = "<tr>"
        for c in cols:
            fn  = c["fieldname"]
            val = row.get(fn, "")
            if fn == "sr_no":
                html += '<td style="border:{B};text-align:center;background:{bg};font-size:9px;color:#555;{fw}">{v}</td>'.format(
                    B=B, bg=bg, fw=fw, v="" if val == "" else val)
            elif fn in _NUMERIC:
                html += '<td style="border:{B};text-align:right;background:{bg};{fw}">{v}</td>'.format(
                    B=B, bg=bg, fw=fw, v=_fmt(val) if val not in ("", None) else "")
            else:
                html += '<td style="border:{B};text-align:left;background:{bg};{fw}">{v}</td>'.format(
                    B=B, bg=bg, fw=fw, v=val or "")
        html += "</tr>"
        return html

    def _page_table(rows, start_idx):
        tbody = "<tbody>" + "".join(
            _row_html(row, start_idx + j) for j, row in enumerate(rows)
        ) + "</tbody>"
        return '<table class="data-tbl">{cg}<thead>{hdr}</thead>{tbody}</table>'.format(
            cg=cg, hdr=header_tr, tbody=tbody)

    emp_rows = [r for r in data if not r.get("bold")]
    tot_rows = [r for r in data if r.get("bold")]

    if not emp_rows:
        pages, has_data = [[]], False
    else:
        has_data = True
        pages, idx, first = [], 0, True
        while idx < len(emp_rows):
            lim = ROWS_FIRST_PAGE if first else ROWS_OTHER_PAGE
            pages.append(emp_rows[idx: idx + lim])
            idx += lim; first = False
        if tot_rows:
            pages[-1] = pages[-1] + tot_rows

    total_pages = len(pages)
    parts, row_counter = [], 0

    for pn, page_rows in enumerate(pages):
        pb       = '<div style="page-break-before:always;"></div>' if pn > 0 else ""
        is_last  = (pn == total_pages - 1)
        page_hdr = page1_hdr if pn == 0 else cont_hdr

        if not has_data:
            nc  = len(cols)
            tbl = '<table class="data-tbl">{cg}<thead>{hdr}</thead><tbody><tr><td colspan="{nc}" class="nd">No data for this period</td></tr></tbody></table>'.format(
                cg=cg, hdr=header_tr, nc=nc)
        else:
            tbl = _page_table(page_rows, row_counter)
            row_counter += len([r for r in page_rows if not r.get("bold")])

        pg_foot = '<div class="pg-foot">Page {p} of {t}</div>'.format(p=pn+1, t=total_pages)
        sig     = _sig_html() if is_last else ""
        parts.append("{pb}{hdr}{tbl}{foot}{sig}".format(pb=pb, hdr=page_hdr, tbl=tbl, foot=pg_foot, sig=sig))

    return '<!DOCTYPE html><html><head><meta charset="UTF-8">{css}</head><body>{body}</body></html>'.format(
        css=_CSS, body="".join(parts))


def _save_pdf(html, prefix):
    pdf = get_pdf(html, options={
        "page-size": "A4", "orientation": "Landscape",
        "margin-top": "7mm", "margin-right": "6mm",
        "margin-bottom": "9mm", "margin-left": "6mm",
        "encoding": "UTF-8", "no-outline": None,
    })
    ts  = frappe.utils.now_datetime().strftime("%Y%m%d_%H%M%S")
    fn  = "{prefix}_{ts}.pdf".format(prefix=prefix, ts=ts)
    with open(frappe.utils.get_files_path(fn, is_private=0), "wb") as fh:
        fh.write(pdf)
    doc = frappe.get_doc({"doctype": "File", "file_name": fn, "is_private": 0, "file_url": "/files/{fn}".format(fn=fn)})
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return doc.file_url


@frappe.whitelist()
def print_report(filters):
    if isinstance(filters, str):
        filters = json.loads(filters)
    cols, data = execute(filters)
    html = _build_html(cols, data, filters.get("company", ""), filters.get("month", ""), filters.get("year", ""))
    return _save_pdf(html, "Advance_Register")