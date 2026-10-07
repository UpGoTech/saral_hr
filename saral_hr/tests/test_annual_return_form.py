from datetime import date

from frappe.tests.utils import FrappeTestCase

from saral_hr.saral_hr.report.annual_return_form.annual_return_form import (
	age_band,
	assemble,
	eligible_for_annual_leave,
	on_rolls,
	worked_weight,
)


class TestAnnualReturnForm(FrappeTestCase):
	def test_half_day_is_half_a_working_day(self):
		self.assertEqual(worked_weight("Present"), 1)
		self.assertEqual(worked_weight("Half Day"), 0.5)
		self.assertEqual(worked_weight("Weekly Off"), 0)
		self.assertEqual(worked_weight("Earned Leave"), 0)

	def test_left_before_the_year_is_not_on_rolls(self):
		self.assertFalse(on_rolls(date(2020, 1, 1), date(2024, 12, 31), date(2025, 1, 1), date(2025, 12, 31)))
		self.assertTrue(on_rolls(date(2020, 1, 1), date(2025, 3, 1), date(2025, 1, 1), date(2025, 12, 31)))

	def test_age_bands_on_the_last_day_of_the_year(self):
		on = date(2025, 12, 31)
		self.assertEqual(age_band(date(1990, 1, 1), on), "adult")
		self.assertEqual(age_band(date(2010, 1, 1), on), "adolescent")
		self.assertEqual(age_band(date(2011, 6, 1), on), "child")
		self.assertEqual(age_band(None, on), "adult")

	def test_annual_leave_uses_240_days_or_two_thirds_after_joining(self):
		self.assertTrue(eligible_for_annual_leave(date(2020, 1, 1), 240, 2025))
		self.assertFalse(eligible_for_annual_leave(date(2020, 1, 1), 239, 2025))
		self.assertTrue(eligible_for_annual_leave(date(2025, 12, 1), 21, 2025))
		self.assertFalse(eligible_for_annual_leave(date(2025, 12, 1), 20, 2025))

	def test_assemble_builds_the_five_sheets(self):
		employees = [
			{
				"name": "HR-EMP-00001",
				"full_name": "Adult Worker",
				"designation": "HELPER",
				"date_of_joining": date(2020, 1, 1),
				"left_date": None,
				"category": "Worker",
				"weekly_off": "Sunday",
				"gender": "Male",
				"date_of_birth": date(1990, 1, 1),
			},
			{
				"name": "HR-EMP-00002",
				"full_name": "Young Worker",
				"designation": "HELPER",
				"date_of_joining": date(2025, 6, 1),
				"left_date": date(2025, 11, 15),
				"category": "Worker",
				"weekly_off": "Sunday",
				"gender": "Female",
				"date_of_birth": date(2010, 1, 1),
			},
			{
				"name": "HR-EMP-00003",
				"full_name": "Farm Hand",
				"designation": "HELPER",
				"date_of_joining": date(2020, 1, 1),
				"left_date": None,
				"category": "Agriculture Team",
				"weekly_off": "Sunday",
				"gender": "Male",
				"date_of_birth": date(1992, 1, 1),
			},
			{
				"name": "HR-EMP-00004",
				"full_name": "Already Left",
				"designation": "HELPER",
				"date_of_joining": date(2020, 1, 1),
				"left_date": date(2024, 12, 31),
				"category": "Worker",
				"weekly_off": "Sunday",
				"gender": "Male",
				"date_of_birth": date(1992, 1, 1),
			},
		]
		attendance = [
			{"employee": "HR-EMP-00001", "attendance_date": date(2025, 1, 1), "status": "Present"},
			{"employee": "HR-EMP-00001", "attendance_date": date(2025, 1, 2), "status": "Half Day"},
			{"employee": "HR-EMP-00001", "attendance_date": date(2025, 1, 3), "status": "Earned Leave"},
			{"employee": "HR-EMP-00001", "attendance_date": date(2025, 1, 14), "status": "Holiday"},
			{"employee": "HR-EMP-00002", "attendance_date": date(2025, 6, 2), "status": "Present"},
			{"employee": "HR-EMP-00003", "attendance_date": date(2025, 1, 1), "status": "Present"},
		]
		daily = [
			{"employee": "HR-EMP-00001", "attendance_date": date(2025, 1, 1), "status": "Present", "ot_hours": 2.5}
		]
		pack = assemble(employees, attendance, daily, 2025)

		self.assertEqual([row["employee"] for row in pack["working"]], ["HR-EMP-00001", "HR-EMP-00002"])
		adult = pack["working"][0]
		self.assertEqual(adult["months"][0], 1.5)
		self.assertEqual(adult["total"], 1.5)

		self.assertEqual(pack["groups"][("adult", "male")]["on_duty"], 1)
		self.assertEqual(pack["groups"][("adult", "male")]["sanctioned"], 1)
		self.assertEqual(pack["groups"][("adult", "male")]["ot"], 2.5)
		self.assertEqual(pack["groups"][("adolescent", "female")]["on_duty"], 1)
		self.assertEqual(pack["groups"][("adolescent", "female")]["left"], 1)
		self.assertEqual(pack["groups"][("adult", "female")]["on_duty"], 0)

		self.assertEqual(len(pack["manpower"]), 12)
		self.assertEqual(pack["manpower"][0]["male_mandays"], 1.5)
		self.assertEqual(pack["manpower"][0]["ot"], 2.5)
		self.assertEqual(pack["manpower"][0]["male"], 1)
		self.assertEqual(pack["manpower"][5]["female"], 1)
		self.assertEqual(pack["manpower"][0]["total_days"], 31)
		self.assertGreater(pack["plant"]["weekly_offs"], 50)
		self.assertEqual(pack["plant"]["holidays"], 1)
		self.assertEqual(pack["plant"]["operation_days"], pack["plant"]["year_days"] - pack["plant"]["weekly_offs"] - 1)

		self.assertEqual(len(pack["left"]), 1)
		self.assertEqual(pack["left"][0]["employee"], "HR-EMP-00002")
		self.assertEqual(pack["left"][0]["month"], 11)
