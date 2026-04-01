import frappe
from frappe import _


# ==================================================================
#  execute — entry point
# ==================================================================

def execute(filters=None):
    filters = filters or {}

    # ── Permission Check ──────────────────────────────────────────
    user_roles = frappe.get_roles(frappe.session.user)
    is_hr      = bool({"Saral HR Manager", "Saral HR User", "System Manager"} & set(user_roles))

    if not is_hr:
        user_employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
        if user_employee:
            filters["employee"] = user_employee
        else:
            frappe.throw(_("No Employee record linked to your user account."))

    columns = get_summary_columns()
    data    = get_summary_data(filters)
    return columns, data


# ==================================================================
#  Employee Link filter — only employees who have loans in that company
# ==================================================================

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_employees_with_loans(doctype, txt, searchfield, start, page_len, filters):
    company_cond = ""
    params = {
        "txt": f"%{txt}%",
        "start": start,
        "page_len": page_len,
    }

    if filters and filters.get("company"):
        company_cond = "AND ela.company = %(company)s"
        params["company"] = filters["company"]

    results = frappe.db.sql("""
        SELECT DISTINCT
            cl.name,
            cl.full_name
        FROM `tabCompany Link` cl
        INNER JOIN `tabEmployee Loan Advance` ela ON ela.employee = cl.name
        WHERE ela.docstatus = 1
            {company_cond}
            AND (cl.name LIKE %(txt)s OR cl.full_name LIKE %(txt)s)
        ORDER BY cl.full_name
        LIMIT %(page_len)s OFFSET %(start)s
    """.format(company_cond=company_cond), params)

    return results

# ==================================================================
#  SUMMARY — columns
# ==================================================================

def get_summary_columns():
    return [
        {"label": _("Loan ID"),       "fieldname": "loan_id",       "fieldtype": "Link",  "options": "Employee Loan Advance", "width": 200},
        {"label": _("Employee ID"),   "fieldname": "employee",      "fieldtype": "Link",  "options": "Employee",              "width": 130},
        {"label": _("Employee Name"), "fieldname": "employee_name", "fieldtype": "Data",                                      "width": 170},
        {"label": _("Loan Type"),     "fieldname": "type",          "fieldtype": "Data",                                      "width": 90},
        {"label": _("Taken On"),      "fieldname": "taken_on",      "fieldtype": "Date",                                      "width": 120},
        {"label": _("Frequency"),     "fieldname": "frequency",     "fieldtype": "Data",                                      "width": 100},
        {"label": _("Loan Amount"),   "fieldname": "amount",        "fieldtype": "Float",                                     "width": 130},
        {"label": _("Total Paid"),    "fieldname": "total_paid",    "fieldtype": "Float",                                     "width": 130},
        {"label": _("Outstanding"),   "fieldname": "outstanding",   "fieldtype": "Float",                                     "width": 130},
        {"label": _("Status"),        "fieldname": "status",        "fieldtype": "Data",                                      "width": 110},
        {"label": _("Details"),       "fieldname": "detail_btn",    "fieldtype": "Data",                                      "width": 100},
    ]


# ==================================================================
#  SUMMARY — data
# ==================================================================

def get_summary_data(filters):
    conditions = build_conditions(filters)

    loans = frappe.db.sql("""
        SELECT
            ela.name              AS loan_id,
            ela.employee          AS employee,
            ela.company           AS company,
            ela.type              AS type,
            ela.amount            AS amount,
            ela.monthly_deduction AS base_emi,
            ela.installment_gap   AS frequency,
            ela.is_deducted       AS is_deducted,
            ela.date              AS date,
            ela.start_month       AS start_month,
            ela.start_year        AS start_year,
            ela.full_name         AS employee_name
        FROM  `tabEmployee Loan Advance` ela
        INNER JOIN `tabEmployee` e ON e.name = ela.employee
        WHERE ela.docstatus = 1
              {conditions}
        ORDER BY ela.company, ela.employee, ela.type, ela.creation
    """.format(conditions=conditions), filters, as_dict=True)

    rows              = []
    grand_amount      = 0.0
    grand_paid        = 0.0
    grand_outstanding = 0.0

    for loan in loans:
        lid       = loan.loan_id
        emp_name  = loan.employee_name or loan.employee
        has_sched = has_schedule(lid)

        total_paid  = get_schedule_paid(lid) if has_sched else (float(loan.amount) if loan.is_deducted else 0.0)
        total_paid  = round(float(total_paid), 2)
        outstanding = round(float(loan.amount) - total_paid, 2)
        status      = "Completed" if outstanding <= 0 else "Active"

        # ── Taken On: always use ela.date directly ────────────────
        taken_on = loan.date if loan.date else None

        grand_amount      += float(loan.amount)
        grand_paid        += total_paid
        grand_outstanding += outstanding

        rows.append({
            "loan_id":       lid,
            "employee":      loan.employee,
            "employee_name": emp_name,
            "company":       loan.company or "",
            "type":          loan.type,
            "amount":        float(loan.amount),
            "frequency":     loan.frequency or ("One-Time" if not has_sched else ""),
            "taken_on":      taken_on,
            "total_paid":    total_paid,
            "outstanding":   outstanding,
            "status":        status,
            "detail_btn":    lid,
        })

    if rows:
        rows.append({
            "loan_id":       "TOTAL",
            "employee":      "",
            "employee_name": "",
            "company":       "",
            "type":          "",
            "amount":        round(grand_amount, 2),
            "frequency":     "",
            "taken_on":      None,
            "total_paid":    round(grand_paid, 2),
            "outstanding":   round(grand_outstanding, 2),
            "status":        "",
            "detail_btn":    "",
        })

    return rows


# ==================================================================
#  DETAIL — fetched on demand via whitelist call
# ==================================================================

@frappe.whitelist()
def get_loan_detail(loan_id):
    loan = frappe.db.sql("""
        SELECT
            ela.name              AS loan_id,
            ela.employee          AS employee,
            ela.company           AS company,
            ela.type              AS type,
            ela.amount            AS amount,
            ela.monthly_deduction AS base_emi,
            ela.is_deducted       AS is_deducted,
            ela.date              AS date,
            ela.start_month       AS start_month,
            ela.start_year        AS start_year,
            ela.full_name         AS employee_name
        FROM  `tabEmployee Loan Advance` ela
        INNER JOIN `tabEmployee` e ON e.name = ela.employee
        WHERE ela.name = %s AND ela.docstatus = 1
        LIMIT 1
    """, loan_id, as_dict=True)

    if not loan:
        frappe.throw(_("Loan record not found or not submitted."))

    loan = loan[0]
    rows = []

    if has_schedule(loan_id):
        schedule = frappe.db.sql("""
            SELECT month, deduction_amount, is_deducted,
                   is_deferred, deferred_to, idx
            FROM   `tabEmployee Loan Advance Schedule`
            WHERE  parent = %s
            ORDER  BY idx
        """, loan_id, as_dict=True)

        running_bal = float(loan.amount)
        paid_so_far = 0.0

        for row in schedule:
            if row.is_deducted:
                status      = "Deducted"
                paid_so_far = round(paid_so_far + float(row.deduction_amount), 2)
                running_bal = round(float(loan.amount) - paid_so_far, 2)
                actual_amt  = float(row.deduction_amount)
            elif row.is_deferred:
                status     = "Deferred"
                actual_amt = 0.0
            else:
                status     = "Pending"
                actual_amt = 0.0

            rows.append({
                "month":         row.month or "",
                "scheduled_amt": float(loan.base_emi or 0),
                "actual_amt":    actual_amt,
                "status":        status,
                "deferred_to":   row.deferred_to or "",
                "running_bal":   running_bal,
            })

    else:
        if loan.date:
            month_label = frappe.utils.formatdate(loan.date, "MMMM yyyy")
        elif loan.start_month or loan.start_year:
            month_label = "{} {}".format(loan.start_month or "", loan.start_year or "").strip()
        else:
            month_label = "—"

        if loan.is_deducted:
            status      = "Deducted"
            actual_amt  = float(loan.amount)
            running_bal = 0.0
        else:
            status      = "Pending"
            actual_amt  = 0.0
            running_bal = float(loan.amount)

        rows.append({
            "month":         month_label,
            "scheduled_amt": float(loan.amount),
            "actual_amt":    actual_amt,
            "status":        status,
            "deferred_to":   "",
            "running_bal":   running_bal,
        })

    # Format taken_on date for display in the modal
    taken_on_display = frappe.utils.formatdate(loan.date, "dd-MM-yyyy") if loan.date else "—"

    # Derive status from rows
    total_paid  = sum(r["actual_amt"] for r in rows)
    outstanding = round(float(loan.amount) - total_paid, 2)
    status      = "Completed" if outstanding <= 0 else "Active"

    return {
        "loan_id":       loan.loan_id,
        "employee":      loan.employee,
        "employee_name": loan.employee_name or loan.employee,
        "company":       loan.company or "",
        "type":          loan.type,
        "amount":        float(loan.amount),
        "taken_on":      taken_on_display,
        "status":        status,
        "rows":          rows,
    }


# ==================================================================
#  Helpers
# ==================================================================

def has_schedule(loan_id):
    return frappe.db.sql("""
        SELECT COUNT(*) FROM `tabEmployee Loan Advance Schedule` WHERE parent = %s
    """, loan_id)[0][0] > 0


def get_schedule_paid(loan_id):
    result = frappe.db.sql("""
        SELECT COALESCE(SUM(deduction_amount), 0)
        FROM   `tabEmployee Loan Advance Schedule`
        WHERE  parent = %s AND is_deducted = 1
    """, loan_id)[0][0]
    return float(result or 0)


# ==================================================================
#  SQL Conditions
# ==================================================================

def build_conditions(filters):
    conditions = ""

    if filters.get("company"):
        conditions += " AND ela.company = %(company)s"

    if filters.get("employee"):
        employee_value = filters["employee"]
        # Extract ID from "Name (ID)" format
        if " (" in employee_value:
            employee_id = employee_value.split(" (")[-1].rstrip(")")
        else:
            employee_id = employee_value
        conditions += " AND ela.employee = %(employee_id)s"
        filters["employee_id"] = employee_id

    if filters.get("type"):
        conditions += " AND ela.type = %(type)s"

    if filters.get("status"):
        if filters["status"] == "Active":
            conditions += """
                AND (
                    CASE
                        WHEN (SELECT COUNT(*) FROM `tabEmployee Loan Advance Schedule` s2
                              WHERE s2.parent = ela.name) > 0
                        THEN (SELECT COALESCE(SUM(s2.deduction_amount), 0)
                              FROM `tabEmployee Loan Advance Schedule` s2
                              WHERE s2.parent = ela.name AND s2.is_deducted = 1) < ela.amount
                        ELSE ela.is_deducted = 0
                    END
                )
            """
        elif filters["status"] == "Completed":
            conditions += """
                AND (
                    CASE
                        WHEN (SELECT COUNT(*) FROM `tabEmployee Loan Advance Schedule` s2
                              WHERE s2.parent = ela.name) > 0
                        THEN (SELECT COALESCE(SUM(s2.deduction_amount), 0)
                              FROM `tabEmployee Loan Advance Schedule` s2
                              WHERE s2.parent = ela.name AND s2.is_deducted = 1) >= ela.amount
                        ELSE ela.is_deducted = 1
                    END
                )
            """

    return conditions


# ==================================================================
#  Print Loan Schedule
# ==================================================================

@frappe.whitelist()
def print_loan_schedule(loan_id):
    data     = get_loan_detail(loan_id)
    html     = _build_schedule_html(data)
    return   _save_schedule_pdf(html, loan_id)


def _fmt_amt(v):
    if v is None or v == "":
        return "—"
    try:
        return f"₹ {float(v):,.2f}"
    except (TypeError, ValueError):
        return str(v)


_SCHEDULE_CSS = """<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Arial,sans-serif;font-size:14px;color:#000;background:#fff}
.hdr{text-align:center;border-bottom:2px solid #000;padding:10px 6px 6px;margin-bottom:10px}
.hdr .co{font-size:26px;font-weight:900;letter-spacing:1px;text-transform:uppercase}
.hdr .ttl{font-size:18px;font-weight:700;margin-top:2px}
.meta{width:100%;border-collapse:collapse;margin-bottom:14px}
.meta td{padding:8px 20px;font-size:13px;border:none;vertical-align:top;background:#fff}
.meta .lbl{font-size:10px;text-transform:uppercase;letter-spacing:0.6px;font-weight:700;color:#666;display:block;margin-bottom:3px}
.meta .val{font-size:13px;font-weight:600;color:#000;display:block}
table{width:100%;border-collapse:collapse;margin-top:8px}
th{border:1px solid #000;padding:9px 12px;font-size:13px;font-weight:700;
   background:#f0f0f0;color:#000;white-space:nowrap}
td{border:1px solid #000;padding:9px 12px;font-size:13px;vertical-align:middle;color:#000}
tr.tot td{background:#e8e8e8;font-weight:700}
.sig{display:flex;justify-content:space-between;margin-top:20px;padding-top:8px}
.sig-b{text-align:center;width:180px}
.sig-l{border-top:1px solid #000;margin-bottom:4px}
.sig-t{font-size:13px;color:#333}
</style>"""

_SCHEDULE_SIG = '<div class="sig">' + "".join(
    f'<div class="sig-b"><div class="sig-l"></div><div class="sig-t">{l}</div></div>'
    for l in ["Prepared By", "Checked By", "Authorised Signatory"]
) + '</div>'


def _build_schedule_html(data):
    co       = data.get("company", "")
    emp_name = data.get("employee_name", "")
    emp_id   = data.get("employee", "")
    ltype    = data.get("type", "")
    amount   = data.get("amount", 0)
    taken_on = data.get("taken_on", "—")
    status   = data.get("status", "")
    loan_id  = data.get("loan_id", "")
    rows     = data.get("rows", [])

    is_advance = ltype == "Advance"

    hdr = (
        f'<div class="hdr">'
        f'<div class="co">{co}</div>'
        f'<div class="ttl">Repayment Schedule — {loan_id}</div>'
        f'</div>'
    )

    meta = (
        f'<table class="meta"><tr>'
        f'<td><span class="lbl">Employee</span><span class="val">{emp_name} ({emp_id})</span></td>'
        f'<td><span class="lbl">Type</span><span class="val">{ltype}</span></td>'
        f'<td><span class="lbl">Loan Amount</span><span class="val">{_fmt_amt(amount)}</span></td>'
        f'<td><span class="lbl">Taken On</span><span class="val">{taken_on}</span></td>'
        f'<td><span class="lbl">Status</span><span class="val">{status}</span></td>'
        f'</tr></table>'
    )

    thead = (
        "<thead><tr>"
        "<th style='text-align:left;'>Month</th>"
        "<th style='text-align:right;'>Base EMI</th>"
        "<th style='text-align:right;'>Actual Deducted</th>"
        "<th style='text-align:center;'>Status</th>"
        + ("" if is_advance else "<th style='text-align:center;'>Deferred To</th>") +
        "<th style='text-align:right;'>Running Balance</th>"
        "</tr></thead>"
    )

    tbody        = "<tbody>"
    total_base   = 0.0
    total_actual = 0.0

    for row in rows:
        total_base   += float(row.get("scheduled_amt") or 0)
        total_actual += float(row.get("actual_amt") or 0)
        rb            = float(row.get("running_bal") or 0)
        rb_style      = "color:#059669;font-weight:600;" if rb == 0 else "color:#DC2626;"
        deferred      = row.get("deferred_to") or "—"
        tbody += (
            f"<tr>"
            f"<td style='text-align:left;'>{row.get('month','—')}</td>"
            f"<td style='text-align:right;'>{_fmt_amt(row.get('scheduled_amt'))}</td>"
            f"<td style='text-align:right;'>{_fmt_amt(row.get('actual_amt'))}</td>"
            f"<td style='text-align:center;'>{row.get('status','')}</td>"
            + ("" if is_advance else f"<td style='text-align:center;'>{deferred}</td>") +
            f"<td style='text-align:right;{rb_style}'>{_fmt_amt(rb)}</td>"
            f"</tr>"
        )
    tbody += "</tbody>"

    final_bal   = float(rows[-1].get("running_bal") or 0) if rows else 0
    final_style = "color:#DC2626;" if final_bal > 0 else "color:#059669;"
    tfoot = (
        f"<tfoot><tr class='tot'>"
        f"<td style='text-align:left;'>TOTAL</td>"
        f"<td style='text-align:right;'>{_fmt_amt(total_base)}</td>"
        f"<td style='text-align:right;'>{_fmt_amt(total_actual)}</td>"
        f"<td></td>"
        + ("" if is_advance else "<td></td>") +
        f"<td style='text-align:right;{final_style}'>{_fmt_amt(final_bal)}</td>"
        f"</tr></tfoot>"
    )

    table = f"<table>{thead}{tbody}{tfoot}</table>"

    return (
        f'<!DOCTYPE html><html><head><meta charset="UTF-8">{_SCHEDULE_CSS}</head>'
        f'<body>{hdr}{meta}{table}{_SCHEDULE_SIG}</body></html>'
    )


def _save_schedule_pdf(html, loan_id):
    from frappe.utils.pdf import get_pdf
    pdf = get_pdf(html, options={
        "page-size":     "A4",
        "orientation":   "Portrait",
        "margin-top":    "8mm",
        "margin-right":  "8mm",
        "margin-bottom": "8mm",
        "margin-left":   "8mm",
        "encoding":      "UTF-8",
        "no-outline":    None,
    })
    ts  = frappe.utils.now_datetime().strftime("%Y%m%d_%H%M%S")
    fn  = f"Repayment_Schedule_{loan_id}_{ts}.pdf"
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


# ==================================================================
#  Print Report (Summary)
# ==================================================================

@frappe.whitelist()
def print_report(filters):
    import json
    if isinstance(filters, str):
        filters = json.loads(filters)

    cols, data = execute(filters)
    co         = filters.get("company", "")
    html       = _build_report_html(cols, data, co)
    return     _save_report_pdf(html)


_REPORT_CSS = """<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Arial,sans-serif;font-size:14px;color:#000;background:#fff}
.hdr{text-align:center;border-bottom:2px solid #000;padding:10px 6px 6px;margin-bottom:10px}
.hdr .co{font-size:26px;font-weight:900;letter-spacing:1px;text-transform:uppercase}
.hdr .ttl{font-size:18px;font-weight:700;margin-top:2px}
table{width:100%;border-collapse:collapse;margin-top:8px}
th{border:1px solid #000;padding:9px 12px;font-size:13px;font-weight:700;
   background:#f0f0f0;color:#000;white-space:nowrap;text-align:left}
td{border:1px solid #000;padding:9px 12px;font-size:13px;vertical-align:middle;color:#000}
tr.tot td{background:#e8e8e8;font-weight:700}
.nd{text-align:center;padding:12px;color:#888}
.sig{display:flex;justify-content:space-between;margin-top:20px;padding-top:8px}
.sig-b{text-align:center;width:180px}
.sig-l{border-top:1px solid #000;margin-bottom:4px}
.sig-t{font-size:13px;color:#333}
</style>"""

_REPORT_SIG = '<div class="sig">' + "".join(
    f'<div class="sig-b"><div class="sig-l"></div><div class="sig-t">{l}</div></div>'
    for l in ["Prepared By", "Checked By", "Authorised Signatory"]
) + '</div>'

# Skip these columns in print — detail_btn is UI only
_SKIP_COLS = {"detail_btn"}

# Float columns for right-align
_MONEY_COLS = {"amount", "total_paid", "outstanding"}


def _build_report_html(cols, data, co):
    print_cols = [c for c in cols if c.get("fieldname") not in _SKIP_COLS]

    hdr = (
        f'<div class="hdr">'
        f'<div class="co">{co}</div>'
        f'<div class="ttl">Employee Loan Advance Ledger</div>'
        f'</div>'
    )

    def _th():
        return "<tr>" + "".join(
            f'<th style="text-align:{"right" if c["fieldname"] in _MONEY_COLS else "left"};">'
            f'{c.get("label","")}</th>'
            for c in print_cols
        ) + "</tr>"

    def _dr(row):
        if row.get("loan_id") == "TOTAL":
            return _tr(row)
        h = "<tr>"
        for c in print_cols:
            fn  = c.get("fieldname", "")
            val = row.get(fn, "")
            if fn in _MONEY_COLS:
                h += f'<td style="text-align:right;">{_fmt_amt(val)}</td>'
            elif fn == "taken_on" and val:
                import datetime
                if isinstance(val, (datetime.date, datetime.datetime)):
                    val = val.strftime("%d-%m-%Y")
                h += f'<td>{val}</td>'
            else:
                h += f'<td>{val or ""}</td>'
        return h + "</tr>"

    def _tr(row):
        h = '<tr class="tot">'
        for c in print_cols:
            fn = c.get("fieldname", "")
            if fn == "loan_id":
                h += "<td><strong>TOTAL</strong></td>"
            elif fn in _MONEY_COLS:
                h += f'<td style="text-align:right;">{_fmt_amt(row.get(fn,""))}</td>'
            else:
                h += "<td></td>"
        return h + "</tr>"

    detail_rows = [r for r in data if r.get("loan_id") != "TOTAL"]
    ncols       = len(print_cols) or 1

    if not detail_rows:
        body = f'<tr><td colspan="{ncols}" class="nd">No data found</td></tr>'
    else:
        body = "".join(_dr(r) for r in detail_rows)
        total_row = next((r for r in data if r.get("loan_id") == "TOTAL"), None)
        if total_row:
            body += _tr(total_row)

    html = (
        f'<!DOCTYPE html><html><head><meta charset="UTF-8">{_REPORT_CSS}</head>'
        f'<body>{hdr}'
        f'<table><thead>{_th()}</thead><tbody>{body}</tbody></table>'
        f'{_REPORT_SIG}</body></html>'
    )
    return html


def _save_report_pdf(html):
    from frappe.utils.pdf import get_pdf
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
    fn  = f"Employee_Loan_Advance_Ledger_{ts}.pdf"
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