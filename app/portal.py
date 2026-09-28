"""Production portal parsers promoted from the verified diagnostic."""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlencode, urlparse

from bs4 import BeautifulSoup

BASE = "https://yjs.chd.edu.cn"
TIMETABLE = BASE + "/py/page/student/grkcb.htm"
PROFILE_PAGES = (
    ("我的学籍信息", "/gl/page/student/studentBaseOne.htm"),
    ("学籍异动申请", "/gl/page/student/studentException.htm"),
    ("个人信息", "/allogene/page/userinfo.htm"),
)
PROFILE_FIELDS = {
    "student_number": ("学号",),
    "recorded_name": ("姓名", "学生姓名"),
    "chinese_name": ("中文名", "中文姓名"),
    "english_name": ("英文名", "英文姓名", "外文姓名", "外文名"),
    "passport_name": ("护照名", "护照姓名"),
    "major": ("专业", "专业名称", "学科专业", "所学专业"),
    "college": ("学院", "院系", "所属学院", "学院名称"),
    "research_direction": ("研究方向", "方向"),
    "grade": ("年级", "入学年份", "入学年度"),
    "academic_supervisor": ("导师", "导师姓名", "指导教师", "指导老师"),
}


def canonical_label(text):
    text = re.split(r"[（(]", text, maxsplit=1)[0]
    return re.sub(r"[\s*：:]", "", text)


def profile_fields(html):
    """Extract only requested academic/name fields, plus a value-free structure map."""
    soup = BeautifulSoup(html, "html.parser")
    aliases = {label: key for key, labels in PROFILE_FIELDS.items() for label in labels}
    details, sources = {}, {}

    def value_of(element):
        if element is None:
            return "", None
        control = element if element.name in ("input", "select", "textarea") else element.find(
            ["input", "select", "textarea"])
        if control:
            if control.name == "input":
                if control.get("type", "").lower() in ("password", "hidden"):
                    return "", None
                value = control.get("value", "").strip()
            elif control.name == "select":
                option = control.find("option", selected=True)
                value = clean_text(option) if option else ""
            else:
                value = clean_text(control)
            return value, {"tag": control.name, "name": control.get("name", ""),
                           "id": control.get("id", "")}
        return clean_text(element), {"tag": element.name}

    candidates = soup.select("label, .control-label, th, td")
    for label in candidates:
        original = clean_text(label)
        key = aliases.get(canonical_label(original))
        if key is None:
            continue
        target = soup.find(id=label.get("for")) if label.get("for") else None
        if target is None:
            target = label.find_next_sibling()
        if target is None and label.parent:
            target = label.parent.select_one(".controls, input, select, textarea")
        value, locator = value_of(target)
        if locator is not None:
            sources.setdefault(key, []).append({"label": original, **locator,
                                               "value_present": bool(value)})
        if value and key not in details:
            details[key] = value
    # Some read-only pages print label and value together inside one cell.
    for element in soup.select("td, .control-group, .form-group"):
        text = clean_text(element)
        for alias, key in aliases.items():
            match = re.fullmatch(re.escape(alias) + r"\s*[：:]\s*(.+)", text)
            if match and key not in details and len(match.group(1)) <= 100:
                details[key] = match.group(1).strip()
                sources.setdefault(key, []).append({"label": alias, "tag": element.name,
                                                   "value_present": True})
    controls = [{"tag": c.name, "name": c.get("name", ""), "id": c.get("id", ""),
                 "type": c.get("type", "")} for c in soup.select("input, select, textarea")
                if c.get("type", "").lower() not in ("password", "hidden")]
    links = []
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        parsed = urlparse(href)
        if (not parsed.hostname or parsed.hostname == "yjs.chd.edu.cn") and parsed.path.startswith(
                ("/gl/page/student/", "/allogene/page/")):
            links.append({"text": clean_text(a), "path": parsed.path})
    return details, {"fields": sources, "controls": controls, "links": links}


class PortalError(Exception):
    """A public error message containing no session headers or response body."""


@dataclass(frozen=True)
class Selection:
    year: int = 2026
    term: int = 11
    week: int = 1

    def __post_init__(self):
        if not (2003 <= self.year <= 2100 and self.term in (11, 12, 13)
                and 1 <= self.week <= 20):
            raise PortalError("Invalid academic year, semester, or week.")

    @property
    def url(self):
        return TIMETABLE + "?" + urlencode(
            {"zc": self.week, "xj": self.term, "xn": self.year})


def clean_text(element):
    return " ".join(element.get_text(" ", strip=True).split())


def parse_timetable(html, selection):
    """Require a student identity and the exact selected timetable.

    Blank course cells are valid. A login/error page is never an empty schedule.
    Expand row/column spans so a merged class retains its day and periods.
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table.table-course")
    if table is None:
        raise PortalError("No timetable found; sign in or complete portal authorization.")
    identity = {}
    for label in soup.select(".control-group label"):
        value = label.find_next_sibling("span")
        if value is not None:
            identity[clean_text(label).rstrip("：:")] = clean_text(value)
    if not identity.get("学号") or not identity.get("专业"):
        raise PortalError("Timetable identity is missing; refusing to accept this response.")
    for name, expected in (("xn", selection.year), ("xj", selection.term),
                           ("zc", selection.week)):
        select = soup.select_one(f"select#{name}")
        option = select.select_one("option[selected]") if select else None
        if option is None or option.get("value") != str(expected):
            raise PortalError("Response has different year/semester/week selections.")
    rows = table.find_all("tr")
    if len(rows) != 13:
        raise PortalError("Unexpected timetable row count; parser needs inspection.")
    header = [clean_text(c) for c in rows[0].find_all(["th", "td"], recursive=False)]
    days = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    if header[-7:] != days:
        raise PortalError("Unexpected weekday headers; parser needs inspection.")
    occupied = set()
    classes = []
    periods = []
    for ri, row in enumerate(rows):
        col = 0
        for cell in row.find_all(["th", "td"], recursive=False):
            while (ri, col) in occupied:
                col += 1
            rs, cs = int(cell.get("rowspan", 1)), int(cell.get("colspan", 1))
            if rs < 1 or cs < 1 or col + cs > 9 or ri + rs > 13:
                raise PortalError("Unexpected timetable cell span.")
            for rr in range(ri, ri + rs):
                for cc in range(col, col + cs):
                    if (rr, cc) in occupied:
                        raise PortalError("Overlapping timetable cell spans.")
                    occupied.add((rr, cc))
            text = clean_text(cell)
            if ri and col == 1:
                periods.append(text)
            if ri and col >= 2 and text:
                classes.append({"day": col - 1, "day_span": cs,
                                "first_period": ri, "period_count": rs,
                                "text": text})
            col += cs
    if len(occupied) != 13 * 9 or len(periods) != 12:
        raise PortalError("Incomplete timetable grid; refusing partial extraction.")
    heading = soup.find("h3")
    return {"identity": identity, "heading": clean_text(heading) if heading else "",
            "selection": {"year": selection.year, "semester": selection.term,
                          "week": selection.week}, "periods": periods, "classes": classes}


def assert_match(actual, baseline):
    if actual != baseline:
        raise PortalError("Response differs from the visible timetable baseline.")


def read_http(context, selection):
    response = context.request.get(selection.url, timeout=25000)
    try:
        if response.status != 200 or urlparse(response.url).hostname != "yjs.chd.edu.cn":
            raise PortalError("HTTP retrieval was redirected or rejected by the portal.")
        return parse_timetable(response.text(), selection)
    finally:
        response.dispose()

