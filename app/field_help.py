"""Bilingual input help based on the portal controls captured in the PoC."""
TIMETABLE_URL = 'https://yjs.chd.edu.cn/py/page/student/grkcb.htm'
HELP = {
    'year': (
        'Academic start year is the portal URL parameter xn. For 2026–2027 enter 2026, even when the current calendar year is 2027. In 培养 → 我的课表, select the desired academic year and semester; read xn from the updated address. Changing this field invalidates retrieved results.',
        '学年起始年对应门户网址参数 xn。例如 2026–2027 学年填写 2026，即使当前日历年份为 2027。在“培养 → 我的课表”选择所需学年和学期后，从更新的网址读取 xn。更改此项会使已获取的信息失效。'),
    'term': (
        'Choose First semester, Second semester or Short semester from the dropdown. The app automatically sends the portal URL parameter xj: 11 = first semester (第一学期), 12 = second semester (第二学期), 13 = short semester (短学期). No code entry is needed. To verify, open 培养 → 我的课表, select the desired academic year AND semester, then read xj from the address: ...?zc=1&xj=11&xn=2026. Changing the semester clears retrieved results; switching the interface language does not.',
        '在下拉菜单选择第一学期、第二学期或短学期。应用会自动使用门户网址参数 xj：11＝第一学期，12＝第二学期，13＝短学期，无需手动填写代码。如需核对，打开“培养 → 我的课表”，选择所需学年和学期后，从网址读取 xj，例如 ...?zc=1&xj=11&xn=2026。更改学期会清除已获取的信息；切换界面语言不会改变学期或清除信息。'),
    'first': (
        'First teaching week to retrieve, inclusive (1–20). These are the portal’s academic weeks, not calendar/ISO week numbers. In 我的课表 the URL parameter zc is the selected week. First week must not exceed last week.',
        '需要获取的起始教学周，包含该周（1–20）。此处为门户的教学周次，不是日历周或 ISO 周。在“我的课表”中，网址参数 zc 表示所选周次。起始周不能晚于结束周。'),
    'last': (
        'Last teaching week to retrieve, inclusive (1–20). Default 16 follows the reference book; use the actual portal/course range. Empty weeks are valid. A failed or incomplete range cannot be exported; changing the range clears the previous timetable result.',
        '需要获取的结束教学周，包含该周（1–20）。默认 16 来自参考考勤册，请按实际课表范围设置。空白周属于有效结果。获取失败或范围不完整时不能导出；修改范围会清除旧课表结果。'),
    'chinese_name': (
        '中文名 printed on the cover. Confirm the student’s actual Chinese name with the student or approved record. The portal’s 姓名 is shown in retrieved results but is not automatically treated as a Chinese name.',
        '封面上的中文名。请向学生本人或根据认可的记录确认。门户“姓名”会在获取结果中显示，但不会自动认定为中文名。'),
    'passport_name': (
        '护照名 printed on the cover. Enter the spelling and spacing as recorded in the student’s passport. Do not assume the portal’s 姓名 is the passport name; this field is manually confirmed.',
        '封面上的护照名。请按学生护照上的拼写和空格填写，不要默认将门户“姓名”当作护照名；此项须人工确认。'),
    'major': (
        '专业 printed on the cover, initially filled from the timetable’s 专业. You may edit the cover wording after confirmation. A research direction is a different field and is not substituted automatically. Editing this does not change the student’s portal major.',
        '封面上的专业，初始值来自课表“专业”。确认后可修改封面表述。“研究方向”属于不同字段，不会自动替代专业。修改此项不会改变门户中的学生专业。'),
    'teacher': (
        '班主任 (head teacher) is the role used by the reference attendance book, not the academic supervisor 导师. The default is 李冠楠. This setting is retained between student sessions; edit it if another head teacher is responsible.',
        '参考考勤册使用的职务为“班主任”，并非学术导师。默认李冠楠。此设置在不同学生会话间保留；如由其他班主任负责，请修改。'),
    'phone': (
        '联系电话 for the head teacher, printed on the cover. Default 02968578129 follows the reference. Preserve leading zeroes and verify before export. This setting remains between student sessions.',
        '封面上的班主任联系电话。默认 02968578129 来自参考考勤册。请保留开头的 0，并在导出前核对。此设置在不同学生会话间保留。'),
    'issue_date': (
        'Date of preparing the book, in YYYY-MM-DD format. Initialized to today when the app opens; edit for a custom date. The cover prints only its year and month (例如 2026年9月制). This does not select the timetable semester or teaching weeks.',
        '制表日期，格式为 YYYY-MM-DD。打开应用时默认当天，也可自定义。封面仅打印其年和月，例如“2026年9月制”。此日期不会选择课表学期或教学周。'),
    'language': (
        'Switch the interface and field help between English and Chinese. Original Chinese course text and the attendance book’s fixed wording are not translated by this switch.',
        '切换界面和字段说明的中英文。此操作不会翻译课表中的原始中文课程文字或考勤册的固定表述。'),
    'photo': (
        'Import the portrait manually: choose a file, drop one local image, or use Chrome Copy image and paste while the photo popup is focused. PNG/JPEG/WebP/BMP/TIFF/GIF are supported, up to 20 MB. Copy image address is not supported. Cancel preserves the previous photo.',
        '人工添加照片：选择文件、拖入一张本地图片，或在 Chrome 中“复制图片”后，在照片弹窗获得焦点时粘贴。支持 PNG/JPEG/WebP/BMP/TIFF/GIF，最大 20 MB。不支持“复制图片地址”。取消会保留原照片。'),
}


def description(key, chinese=False):
    return HELP[key][int(chinese)]
