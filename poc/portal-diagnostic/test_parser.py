"""Offline parser checks; these do not claim portal authentication works."""
import unittest

from app import PortalError, Selection, assert_match, parse_timetable


def fixture(week=1, student="2026000001", courses=False):
    fields = '<div class="control-group">'
    for label, value in (("学号", student), ("学院", "示例学院"), ("专业", "示例专业")):
        fields += f"<label>{label}：</label><span>{value}</span>"
    fields += "</div><h3>2026-2027学年 第一学期 课表</h3>"
    for name, value in (("xn", 2026), ("xj", 11), ("zc", week)):
        fields += f'<select id="{name}"><option value="{value}" selected>{value}</option></select>'
    table = '<table class="table-course"><tr><th colspan="2">时间</th>'
    for day in ("一", "二", "三", "四", "五", "六", "日"):
        table += f"<th>星期{day}</th>"
    table += "</tr>"
    for period in range(1, 13):
        table += "<tr>"
        if period in (1, 5, 9):
            table += '<td rowspan="4">时段</td>'
        table += f"<td>第{period}节</td>"
        for day in range(1, 8):
            if courses and day == 1 and period == 4:
                continue  # Occupied by the preceding merged course.
            if courses and day == 1 and period == 3:
                table += '<td rowspan="2">课程甲<br>教室一</td>'
            elif courses and day == 6 and period == 12:
                table += '<td>周末课程</td>'
            else:
                table += '<td></td>'
        table += "</tr>"
    return fields + table + "</table>"


class ParserTests(unittest.TestCase):
    def test_blank_week_is_valid_with_identity(self):
        parsed = parse_timetable(fixture(), Selection())
        self.assertEqual(parsed["classes"], [])
        self.assertEqual(len(parsed["periods"]), 12)

    def test_login_page_is_not_an_empty_week(self):
        with self.assertRaises(PortalError):
            parse_timetable('<form><input name="password"></form>', Selection())

    def test_wrong_week_is_rejected(self):
        with self.assertRaises(PortalError):
            parse_timetable(fixture(week=2), Selection(week=1))

    def test_merged_course_and_weekend_survive(self):
        parsed = parse_timetable(fixture(courses=True), Selection())
        self.assertEqual(parsed["classes"], [
            {"day": 1, "day_span": 1, "first_period": 3,
             "period_count": 2, "text": "课程甲 教室一"},
            {"day": 6, "day_span": 1, "first_period": 12,
             "period_count": 1, "text": "周末课程"},
        ])

    def test_student_switch_cannot_match_an_old_baseline(self):
        baseline = parse_timetable(fixture(), Selection())
        next_student = parse_timetable(fixture(student="2026000002"), Selection())
        with self.assertRaises(PortalError):
            assert_match(next_student, baseline)

    def test_missing_identity_is_rejected(self):
        with self.assertRaises(PortalError):
            parse_timetable(fixture(student=""), Selection())

    def test_incomplete_grid_is_rejected(self):
        html = fixture().replace('<td></td>', '', 1)
        with self.assertRaises(PortalError):
            parse_timetable(html, Selection())


if __name__ == "__main__":
    unittest.main()
