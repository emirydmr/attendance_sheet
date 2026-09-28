"""Escaped, offline attendance-book layout for Chromium PDF printing.

The HTML/CSS template is authoritative for both PDF and browser printing.
The archived LaTeX draft is not a runtime dependency.
"""
from __future__ import annotations

from datetime import date
from base64 import b64encode
from html import escape
import os
from pathlib import Path
import re
from string import Template
import sys
import tempfile
import webbrowser

TITLE = "长安大学国际学生考勤册"
DAY_NAMES = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
CN_INSTRUCTIONS = [
    "考勤签字栏由代课老师亲自如实填写；",
    "若学生请假必须向代课老师出示国际教育学院办公室开出的请假条，并粘贴至指定位置；",
    "每月1日和15日汇总考勤册（如遇假期顺延），学生将考勤册交至班主任处，由班主任汇总；",
    "一年内，未经请假旷课达到18学时以上的，给予警告处分；达到30学时以上的，给予严重警告处分；达到54学时以上，给予留校察看处分；连续旷课两周的，按照学校学籍管理的有关规定处理；",
    "该考勤册需保存至学期末，期末交由班主任归档，作为该生来华学习的重要学习资料。如学期中间有损毁或遗失，请及时联系班主任补办；",
    "代课老师若有任何关于学生学习的事情均可联系其班主任。",
]
EN_INSTRUCTIONS = [
    "The attendance signature needs to be filled in by the substitute teacher themself;",
    "If students take leave, they must present the slip issued by international education, to the respective teachers;",
    "Every month on the 1st and 15th, students have to submit the attendance books to the head teacher’s office, who will then summarize them;",
    "Warning will be given to the students who are absent for more than 18 class hours in a year; serious warning will be given to those who are absent for more than 30 class hours; academic probation will be given to those who are absent for more than 54 class hours;",
    "The attendance book should be kept until the end of the semester and filed by the head teacher, as an important learning material for the student. If the attendance book is damaged or lost during the semester, please contact the head teacher for a replacement;",
    "Lecturers can contact the head teacher whenever there is anything regarding the student’s performance and studies.",
]


def resource_root():
    """Locate resources both in source and PyInstaller's one-file extraction."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def font_css():
    """Embed the bundled, licensed Chinese font; never fetch fonts at runtime."""
    font = resource_root() / "assets" / "fonts" / "AttendanceCJK.otf"
    if not font.is_file():
        if getattr(sys, "frozen", False):
            raise ValueError("Bundled Chinese font is missing. This build is incomplete.")
        return ""  # Development preview only: use available system fonts.
    encoded = b64encode(font.read_bytes()).decode("ascii")
    return "@font-face{font-family:'Attendance CJK';src:url(data:font/otf;base64," + encoded + ") format('opentype');font-weight:normal;font-style:normal;font-display:block;}"


def pdf_filename(student_id):
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(student_id)).strip(" .")
    if not safe:
        raise ValueError("Student number is required.")
    return f"{safe}_{TITLE}.pdf"


def validate_book(data):
    for key in ("student_id", "chinese_name", "passport_name", "major", "teacher", "phone"):
        if not str(data.get(key, "")).strip():
            raise ValueError(f"Missing field: {key}")
    date.fromisoformat(data["issue_date"])
    weeks = data.get("weeks", [])
    if not weeks:
        raise ValueError("Retrieve timetables first.")
    numbers = [w["selection"]["week"] for w in weeks]
    if numbers != list(range(data["first_week"], data["last_week"] + 1)):
        raise ValueError("Timetable range is incomplete or stale.")
    for week in weeks:
        if week["identity"]["学号"] != data["student_id"]:
            raise ValueError("Timetables belong to a different student.")
        if week["identity"]["专业"] != data["portal_major"]:
            raise ValueError("Timetable major differs from retrieved identity.")
        if (week["selection"]["year"], week["selection"]["semester"]) != (data["year"], data["term"]):
            raise ValueError("Timetable year/semester is stale.")


def weekly_grid(week):
    starts, covered = {}, set()
    for c in week["classes"]:
        d, p, ds, ps = c["day"], c["first_period"], c["day_span"], c["period_count"]
        if not (1 <= d <= 7 and 1 <= p <= 12 and ds >= 1 and ps >= 1
                and d + ds <= 8 and p + ps <= 13):
            raise ValueError("Course position is outside the timetable grid.")
        for row in range(p, p + ps):
            for day in range(d, d + ds):
                if (row, day) in covered:
                    raise ValueError("Overlapping course blocks.")
                covered.add((row, day))
        starts[p, d] = c
    header = "<tr><th class='period'>节次</th>" + "".join(f"<th>{d}</th>" for d in DAY_NAMES) + "</tr>"
    rows = []
    for p in range(1, 13):
        cells = [f"<th class='period'>{p}</th>"]
        for d in range(1, 8):
            c = starts.get((p, d))
            if c:
                cells.append(f"<td rowspan='{c['period_count']}' colspan='{c['day_span']}'><div class='course'>{escape(c['text'])}</div></td>")
            elif (p, d) not in covered:
                cells.append("<td></td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return "<table class='schedule'>" + header + "".join(rows) + "</table>"


def book_html(data):
    validate_book(data)
    e = lambda k: escape(str(data[k]))
    issued = date.fromisoformat(data["issue_date"])
    photo = data.get("photo")
    portrait = f"<div class='portrait'><img alt='Student photo / 学生照片' src='{photo.data_url}'></div>" if photo else "<div class='portrait placeholder'>照片 / Photo</div>"
    pages = [f"""<section class='page cover'><h1>{TITLE}</h1>
      <h2>International Student Attendance Book</h2>
      {portrait}
      <table class='identity'><tr><th>中文名：</th><td>{e('chinese_name')}</td><th>护照名：</th><td>{e('passport_name')}</td></tr>
      <tr><th>专业：</th><td>{e('major')}</td><th>学号：</th><td>{e('student_id')}</td></tr>
      <tr><th>班主任：</th><td>{e('teacher')}</td><th>联系电话：</th><td>{e('phone')}</td></tr></table>
      <p class='issue'>{issued.year}年{issued.month}月制</p></section>"""]
    for title, instructions in ((TITLE + "使用说明", CN_INSTRUCTIONS),
                                ("International Student Attendance Book Instructions", EN_INSTRUCTIONS)):
        pages.append(f"<section class='page instructions'><h2>{title}</h2><ol>" +
                     "".join(f"<li>{escape(x)}</li>" for x in instructions) + "</ol></section>")
    for week in data["weeks"]:
        number = week["selection"]["week"]
        pages.append(f"<section class='page weekly'><h2>{TITLE}（第{number}周）</h2>" +
                     weekly_grid(week) + "</section>")
    headers = ["周次", "缺课（课时）", "请假（课时）", "统计时间", "班主任签字", "备注"]
    rows = "".join(f"<tr><td>{w['selection']['week']}</td>" + "<td></td>" * 5 + "</tr>" for w in data["weeks"])
    pages.append("<section class='page'><h2>长安大学国际学生考勤汇总表（由班主任填写）</h2>" +
                 "<table class='summary'><tr>" + "".join(f"<th>{h}</th>" for h in headers) +
                 "</tr>" + rows + "<tr><td>总计</td>" + "<td></td>" * 5 + "</tr></table></section>")
    pages.append("<section class='page'><h2>请假条粘贴处</h2><div class='leave'></div></section>")
    watermark = ".page:after{content:'DEMO / 示例';position:absolute;bottom:7mm;right:15mm;color:#777;font-size:11pt;}" if data.get("demo") else ""
    pages = [part[:part.index('>')+1] + "<div class='page-content'>" + part[part.index('>')+1:-len('</section>')] + "</div></section>" for part in pages]
    template = Template((resource_root() / "templates" / "attendance_blueprint.html").read_text(encoding="utf-8"))
    script = (resource_root() / "templates" / "layout.js").read_text(encoding="utf-8")
    return template.substitute(font_css=font_css(), watermark=watermark, pages="".join(pages), layout_script=script)


def browser_html(data):
    """Self-contained document for the device's default browser and print dialog."""
    html = book_html(data)
    policy = "default-src 'none'; img-src data:; font-src data:; style-src 'unsafe-inline'; script-src 'nonce-attendanceprint'; base-uri 'none'; form-action 'none'"
    html = html.replace("<meta charset='utf-8'>", "<meta charset='utf-8'><meta http-equiv='Content-Security-Policy' content=\"" + policy + "\">")
    toolbar = "<div class='print-toolbar'><button id='print-book'>Print / Save as PDF · 打印 / 另存为PDF</button><span>This file contains student information and photo. / 本文件包含学生信息和照片。</span><span id='layout-warning' class='layout-warning'></span></div>"
    html = html.replace("<body>", "<body>" + toolbar)
    return html


def save_browser_document(data, path):
    Path(path).write_text(browser_html(data), encoding="utf-8")
    return webbrowser.open(Path(path).resolve().as_uri())


def print_pdf(playwright, channel, data, path):
    html = book_html(data)
    from browser_config import launch_browser
    browser = launch_browser(playwright, channel, headless=True)
    try:
        page = browser.new_page()
        page.emulate_media(media="print")
        # Offline document only; neither portal resources nor external URLs allowed.
        page.route("**/*", lambda route: route.abort())
        page.set_content(html, wait_until="load")
        page.evaluate("document.fonts.ready")
        if not page.evaluate("Array.from(document.fonts).every(f => f.status === 'loaded')"):
            raise ValueError("Bundled Chinese font did not load. PDF export was stopped.")
        if not page.evaluate("Array.from(document.images).every(i => i.complete && i.naturalWidth > 0)"):
            raise ValueError("Photo did not render / 照片未能正确渲染。")
        layout = page.evaluate("window.fitAttendanceBook()")
        overflow = [item for item in layout if item['overflow']]
        if overflow:
            affected = "; ".join(f"Page / 页 {item['page']}: {item['title']}" for item in overflow)
            raise ValueError("Content exceeds printable margins / 内容超出打印边距。 " + affected + ". Text was not clipped; adjust the layout / 未裁剪文字，请调整布局。")
        pdf = page.pdf(prefer_css_page_size=True, print_background=True)
        # Render completely before replacing a user-selected destination.
        destination = Path(path)
        staging = None
        try:
            with tempfile.NamedTemporaryFile(dir=destination.parent, suffix=".pdf", delete=False) as stream:
                staging = Path(stream.name)
                stream.write(pdf)
            os.replace(staging, destination)
            staging = None
        finally:
            if staging is not None:
                staging.unlink(missing_ok=True)
    finally:
        browser.close()
