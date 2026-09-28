import unittest

from app import profile_fields


class ProfileTests(unittest.TestCase):
    def test_readonly_name_and_major_are_retrieved(self):
        fields, structure = profile_fields('''
        <div class="control-group"><label for="xm">姓名：</label>
        <input id="xm" name="xm" value="EXAMPLE STUDENT" disabled></div>
        <table><tr><td>专业：</td><td>计算机科学与技术</td>
        <td>研究方向：</td><td>计算机网络与信息安全</td></tr></table>
        ''')
        self.assertEqual(fields["recorded_name"], "EXAMPLE STUDENT")
        self.assertEqual(fields["major"], "计算机科学与技术")
        self.assertEqual(fields["research_direction"], "计算机网络与信息安全")
        self.assertNotIn("chinese_name", fields)
        self.assertEqual(structure["fields"]["recorded_name"][0]["id"], "xm")

    def test_unrequested_identifiers_and_passwords_are_not_exported(self):
        fields, structure = profile_fields('''
        <table><tr><td>中文姓名：</td><td>示例姓名</td>
        <td>护照号码：</td><td>NOT_FOR_EXPORT</td></tr></table>
        <input name="password" type="password" value="SECRET">
        ''')
        self.assertEqual(fields, {"chinese_name": "示例姓名"})
        self.assertNotIn("SECRET", str((fields, structure)))
        self.assertNotIn("NOT_FOR_EXPORT", str((fields, structure)))

    def test_selected_academic_field(self):
        fields, _ = profile_fields('''
        <label for="major">专业名称：</label><select id="major">
        <option value="1">其他专业</option>
        <option value="2" selected>示例专业</option></select>''')
        self.assertEqual(fields["major"], "示例专业")


if __name__ == "__main__":
    unittest.main()
