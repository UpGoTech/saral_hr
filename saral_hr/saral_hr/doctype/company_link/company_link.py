import frappe
import datetime
from frappe.model.document import Document
from frappe import _


class CompanyLink(Document):

    def autoname(self):
        if self.employee:
            self.name = self.employee

    def before_insert(self):
        self.handle_employee_transfer()

    def validate(self):
        self.validate_skill_type_if_required()
        self.sync_holiday_list_from_company()
        self.validate_left_date()
        self.validate_unique_active_employee()

    def validate_skill_type_if_required(self):
        """
        Skill Type is mandatory ONLY when the selected Category has has_subtype = 1.
        For categories without sub-types (e.g. Staff), skill_type is not required.
        """
        if not self.category:
            return

        # Explicit int cast — get_value can return "0", 0, 1, "1", or None
        has_subtype = frappe.db.get_value("Category", self.category, "has_subtype")
        if not int(has_subtype or 0):
            # Category does not have subtypes — clear any stale skill_type and return
            return

        # Category has subtypes — skill_type is required
        if not self.skill_type:
            frappe.throw(
                _("Skill Type is mandatory for category <b>{0}</b> "
                  "because it has skill sub-types enabled.").format(self.category),
                title=_("Missing Skill Type")
            )

    def validate_unique_active_employee(self):
        if not self.employee or not self.is_active:
            return

        duplicate = frappe.db.exists(
            "Company Link",
            {
                "employee": self.employee,
                "is_active": 1,
                "name": ("!=", self.name or "")
            }
        )
        if duplicate:
            frappe.throw(
                _("An active Company Link already exists for employee {0}. "
                  "Please archive it before creating a new one.").format(
                    frappe.bold(self.employee)
                )
            )

    def handle_employee_transfer(self):
        if not self.employee:
            return

        if not self.date_of_joining:
            frappe.throw(
                _("Please set the Date of Joining before saving. "
                  "It is needed to calculate the leaving date for the previous company record.")
            )

        existing = frappe.db.sql("""
            SELECT name, company, employee, date_of_joining
            FROM `tabCompany Link`
            WHERE employee = %(employee)s
              AND is_active = 1
            LIMIT 1
        """, {"employee": self.employee}, as_dict=True)

        if not existing:
            self.is_active = 1
            return

        old_record = existing[0]
        old_name = old_record["name"]

        left_date = (
            frappe.utils.getdate(self.date_of_joining)
            - datetime.timedelta(days=1)
        )

        # Step 1: Get the archive name BEFORE renaming
        suffix = self.get_next_archive_suffix(self.employee)
        new_archive_name = "{0}-{1}".format(self.employee, suffix)

        # Step 2: Rename the old record to archived name
        frappe.rename_doc(
            "Company Link",
            old_name,
            new_archive_name,
            force=True,
            merge=False
        )
        frappe.db.commit()

        # Step 3: Direct SQL to correctly set employee back to real ID,
        # deactivate, and set left_date — bypassing cascade side effects
        frappe.db.sql("""
            UPDATE `tabCompany Link`
            SET employee = %(employee)s,
                is_active = 0,
                left_date = %(left_date)s,
                modified = NOW()
            WHERE name = %(archive_name)s
        """, {
            "employee": self.employee,
            "left_date": left_date,
            "archive_name": new_archive_name
        })
        frappe.db.commit()

        frappe.msgprint(
            _("Employee {0} has been transferred from {1} to {2}. "
              "Previous record archived as {3} with leaving date {4}.").format(
                self.employee,
                old_record["company"],
                self.company,
                new_archive_name,
                str(left_date)
            ),
            title=_("Transfer Complete"),
            indicator="green"
        )

        self.is_active = 1

    def get_next_archive_suffix(self, employee):
        """Return the next integer suffix for archived records like HR-EMP-001-1, HR-EMP-001-2 ..."""
        existing_archives = frappe.db.sql("""
            SELECT name FROM `tabCompany Link`
            WHERE name LIKE %(pattern)s
        """, {"pattern": "{0}-%".format(employee)}, as_dict=True)

        if not existing_archives:
            return 1

        suffixes = []
        for rec in existing_archives:
            parts = rec["name"].rsplit("-", 1)
            if len(parts) == 2:
                try:
                    suffixes.append(int(parts[-1]))
                except ValueError:
                    pass

        return max(suffixes) + 1 if suffixes else 1

    def sync_holiday_list_from_company(self):
        if not self.company:
            return

        company_values = frappe.db.get_value(
            "Company",
            self.company,
            ["default_holiday_list"],
            as_dict=True
        )

        if company_values and company_values.default_holiday_list:
            self.holiday_list = company_values.default_holiday_list

    def validate_left_date(self):
        if self.left_date and self.is_active:
            self.is_active = 0