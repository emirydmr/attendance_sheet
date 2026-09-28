# Verified retrieval map

Observed September 28, 2026 using the student's authorized temporary Chrome
session. Only read-only GETs to observed portal pages were used: no hidden API,
other student's identifier, application submission or access bypass. Technical
success does not establish the university's automation policy.

| Information | Source | Verified status |
| --- | --- | --- |
| Recorded name / 姓名 | `/allogene/page/userinfo.htm` | Extracted from authenticated HTTP response |
| Student number / 学号 | `/py/page/student/grkcb.htm` | Extracted and checked across timetable responses |
| College / 学院 | Same timetable page | Extracted via HTTP |
| Major / 专业 | Same timetable page | Extracted via HTTP |
| Weekly timetable | Same page with `xn`, `xj`, `zc` | Visible, HTTP, headless-rendered and headless HTTP results matched |
| Academic year/term | Timetable dropdowns | Checked against requested selection |
| Chinese name / 中文名 | Not established | Editable field needed; do not reinterpret 姓名 |
| Passport name / 护照名 | Not established | Editable field needed; recorded name is not verified passport spelling |
| Research direction / 研究方向 | Not established | Distinct from major; additional mapping needed |
| Academic supervisor / 导师 | Not established | Distinct from fixed 班主任 in the reference form |
| Issue year/month | Local or custom date | No portal retrieval needed |
| 班主任 / 联系电话 | Reference form and GUI settings | Fixed defaults, optionally editable |

## Timetable requests

`https://yjs.chd.edu.cn/py/page/student/grkcb.htm?zc=3&xj=11&xn=2026`

`xn` is the academic-year start; `xj` is semester (observed 11/12/13); `zc` is
week (observed 1–20). The inspected JavaScript navigates using serialized form
parameters. No all-weeks endpoint was found in that script. Each selected week
can be fetched directly without menu clicks. All 20 weeks have not been tested.

Week 1 was legitimately empty. Week 3 contained five course blocks; HTTP,
headless-rendered and headless HTTP comparisons all passed with installed Mac
Chrome. The embedded Windows Chromium build still requires testing.

## Additional profile pages

| Label | Direct path | Current state |
| --- | --- | --- |
| 我的学籍信息 | `/gl/page/student/studentBaseOne.htm` | Readable HTTP 200; controls include `xh`, `xm`, `xmpy`, `cym`, `nj`, `xz`; values need label mapping |
| 学籍异动申请 | `/gl/page/student/studentException.htm` | Readable HTTP 200; values need mapping; never submit the form |
| 个人信息 | `/allogene/page/userinfo.htm` | Readable HTTP 200; recorded-name extraction succeeded |

Control identifiers are structural evidence, not verified value meanings.
Academic-page identity matching is not yet implemented for those forms;
timetable session identity is checked before fetching them.

## Workflow and remaining work

Let the student log in manually in a temporary visible browser, then reuse the
browser context's cookie jar for HTTP retrieval. Headless session replay worked
for the tested timetable. End the session before the next student. Do not export
passwords, raw HTML, cookies or storage-state files. Reports retain structural
metadata and comparison results; profile field values are shown to the operator.

This is a retrieval prototype, not the finished attendance-book generator.
Windows one-file packaging, PDF renderer, Chinese fonts, course-status handling
and the reference form's 16-week/weekday layout still need verification.
