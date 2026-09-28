"""Bilingual input help based on the portal controls captured in the PoC."""
TIMETABLE_URL = 'https://yjs.chd.edu.cn/py/page/student/grkcb.htm'
HELP = {
    'year': (
        'Academic start year is the portal URL parameter xn. For 2026–2027 enter 2026, even when the current calendar year is 2027. In 培养 → 我的课表, select the desired academic year and semester; read xn from the updated address. Changing this field invalidates retrieved results.',
        '学年起始年对应门户网址参数 xn。例如 2026–2027 学年填写 2026，即使当前日历年份为 2027。在“培养 → 我的课表”选择所需学年和学期后，从更新的网址读取 xn。更改此项会使已获取的信息失效。'),
    'term': (
        'Choose First semester, Second semester or Short semester from the dropdown. The app automatically sends the portal URL parameter xj: 11 = first semester (第一学期), 12 = second semester (第二学期), 13 = short semester (短学期). To verify, open 培养 → 我的课表, select the desired academic year AND semester, then read xj from the address: ...?zc=1&xj=11&xn=2026. Changing the semester clears retrieved results.',
        '在下拉菜单选择第一学期、第二学期或短学期。应用会自动使用门户网址参数 xj：11＝第一学期，12＝第二学期，13＝短学期。如需核对，打开“培养 → 我的课表”，选择所需学年和学期后，从网址读取 xj，例如 ...?zc=1&xj=11&xn=2026。更改学期会清除已获取的信息。'),
    'first': (
        'First teaching week to retrieve, inclusive (1–20). These are the portal’s academic weeks, not calendar/ISO week numbers. In 我的课表 the URL parameter zc is the selected week. First week must not exceed last week.',
        '需要获取的起始教学周，包含该周（1–20）。此处为门户的教学周次，不是日历周或 ISO 周。在“我的课表”中，网址参数 zc 表示所选周次。起始周不能晚于结束周。'),
    'last': (
        'Last teaching week to retrieve, inclusive (1–20). The default is 18; use the actual portal/course range. Empty weeks are valid. A failed or incomplete range cannot be exported; changing the range clears the previous timetable result.',
        '需要获取的结束教学周，包含该周（1–20）。默认值为 18，请按实际课表范围设置。空白周属于有效结果。获取失败或范围不完整时不能导出；修改范围会清除旧课表结果。'),
    'omit_empty_weeks': (
        'The portal is still scanned for every week from the first through the last week. Weeks containing no classes are omitted from the PDF/HTML and summary table. Original week numbers are preserved.',
        '仍会获取从起始周到结束周的每一周课表。没有课程的周不会出现在 PDF/HTML 或汇总表中，其余周保留原周次。'),
    'chinese_name': (
        '中文名 printed on the cover.',
        '封面上的中文名。'),
    'passport_name': (
        '护照名 printed on the cover. The portal does not display the passport name correctly, so this field must be filled in manually.',
        '封面上的护照名。门户无法正确显示护照名，因此须手动填写此项。'),
    'major': (
        '专业 printed on the cover.',
        '封面上的专业。'),
    'teacher': (
        'The advisor responsible for the student. This setting is retained between student sessions; edit it if needed.',
        '负责该学生的班主任。此设置在不同学生会话间保留；如有需要，请修改。'),
    'phone': (
        'The advisor’s contact number, printed on the cover. This setting is retained between student sessions.',
        '封面上的班主任联系电话。此设置在不同学生会话间保留。'),
    'issue_date': (
        'Date of preparing the book, in YYYY-MM-DD format. Defaults to today when the app opens; edit it to use a custom date. It is used only for the year and month printed on the cover (例如 2026年9月制) and has no effect on the timetable semester or teaching weeks.',
        '制表日期，格式为 YYYY-MM-DD。打开应用时默认当天，也可修改为自定义日期。此日期仅用于封面上的年和月，例如“2026年9月制”，与课表学期或教学周无关。'),
    'photo': (
        'Import the portrait manually: choose a file, drop one local image, or use Chrome Copy image and paste while the photo popup is focused. PNG/JPEG/WebP/BMP/TIFF/GIF are supported, up to 20 MB. Copy image address is not supported. Cancel preserves the previous photo.',
        '人工添加照片：选择文件、拖入一张本地图片，或在 Chrome 中“复制图片”后，在照片弹窗获得焦点时粘贴。支持 PNG/JPEG/WebP/BMP/TIFF/GIF，最大 20 MB。不支持“复制图片地址”。取消会保留原照片。'),
}


def description(key, chinese=False):
    return HELP[key][int(chinese)]
