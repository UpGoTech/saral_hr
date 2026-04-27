# Copyright (c) 2026, sj and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class DailyRatesWorker(Document):

    def validate(self):
        self.validate_dates()
        self.validate_duplicate()

    def validate_dates(self):
        """End date must be strictly greater than start date."""
        if self.start_date and self.end_date:
            if self.end_date <= self.start_date:
                frappe.throw(
                    _("End Date {0} must be greater than Start Date {1}.").format(
                        frappe.bold(self.end_date), frappe.bold(self.start_date)
                    ),
                    title=_("Invalid Date Range"),
                )

    def validate_duplicate(self):
        """
        No two records for the same employee should have overlapping date ranges.
        Overlap condition:  existing.start_date <= new.end_date
                        AND existing.end_date   >= new.start_date
        """
        if not (self.employee and self.start_date and self.end_date):
            return

        filters = [
            ["employee",   "=",  self.employee],
            ["start_date", "<=", self.end_date],
            ["end_date",   ">=", self.start_date],
        ]

        if not self.is_new():
            filters.append(["name", "!=", self.name])

        overlapping = frappe.get_all(
            "Daily Rates Worker",
            filters=filters,
            fields=["name", "start_date", "end_date"],
            limit=1,
        )

        if overlapping:
            rec = overlapping[0]
            frappe.throw(
                _(
                    "A record already exists for employee {0} that overlaps "
                    "with the selected date range.<br><br>"
                    "Existing record: <b>{1}</b> "
                    "(Start: {2} — End: {3})"
                ).format(
                    frappe.bold(self.employee),
                    rec["name"],
                    frappe.bold(rec["start_date"]),
                    frappe.bold(rec["end_date"]),
                ),
                title=_("Duplicate Record"),
            )


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_employee_query(doctype, txt, searchfield, start, page_len, filters):
    """
    Custom search query for the Employee field.
    Returns Company Link records where:
      - company  = selected company
      - is_active = 1
      - category.has_subtype = 1  (joined via tabCategory)
    """
    company = filters.get("company") if filters else None

    conditions = []
    values = {}

    if company:
        conditions.append("cl.company = %(company)s")
        values["company"] = company

    conditions.append("cl.is_active = 1")

    # Join Category to filter has_subtype
    conditions.append("cat.has_subtype = 1")

    # Search across employee id and full name
    if txt:
        conditions.append(
            "(cl.employee LIKE %(txt)s OR cl.full_name LIKE %(txt)s)"
        )
        values["txt"] = f"%{txt}%"

    where_clause = " AND ".join(conditions)

    return frappe.db.sql(
        f"""
        SELECT
            cl.name,
            cl.full_name,
            cl.company,
            cl.category
        FROM
            `tabCompany Link` cl
            INNER JOIN `tabCategory` cat ON cat.name = cl.category
        WHERE
            {where_clause}
        ORDER BY
            cl.full_name ASC
        LIMIT %(start)s, %(page_len)s
        """,
        {**values, "start": start, "page_len": page_len},
    )