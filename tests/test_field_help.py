from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from field_help import HELP, TIMETABLE_URL, description


class HelpTests(unittest.TestCase):
    def test_every_input_has_bilingual_help(self):
        for key in ('year', 'term', 'first', 'last', 'chinese_name', 'passport_name',
                    'major', 'teacher', 'phone', 'issue_date', 'photo', 'omit_empty_weeks'):
            self.assertTrue(description(key))
            self.assertTrue(description(key, True))
            self.assertNotEqual(*HELP[key])

    def test_no_language_switching_hints(self):
        self.assertNotIn('language', HELP)
        self.assertNotIn('switching the interface language', description('term'))
        self.assertNotIn('切换界面语言', description('term', True))

    def test_revised_descriptions(self):
        self.assertEqual(HELP['chinese_name'], ('中文名 printed on the cover.', '封面上的中文名。'))
        self.assertEqual(HELP['major'], ('专业 printed on the cover.', '封面上的专业。'))
        self.assertNotIn('No code entry is needed', description('term'))
        self.assertNotIn('无需手动填写代码', description('term', True))
        self.assertIn('default is 18', description('last'))
        self.assertIn('默认值为 18', description('last', True))
        self.assertIn('filled in manually', description('passport_name'))
        self.assertIn('手动填写', description('passport_name', True))
        self.assertIn('advisor', description('teacher'))
        self.assertIn('advisor', description('phone'))
        self.assertIn('has no effect', description('issue_date'))

    def test_semester_codes_and_navigation(self):
        text = description('term')
        for value in ('11', '12', '13', 'xj', 'xn=2026', 'AND semester'):
            self.assertIn(value, text)
        self.assertEqual(TIMETABLE_URL, 'https://yjs.chd.edu.cn/py/page/student/grkcb.htm')

    def test_academic_not_calendar_week(self):
        self.assertIn('not calendar', description('first'))
        self.assertIn('2026–2027', description('year'))
