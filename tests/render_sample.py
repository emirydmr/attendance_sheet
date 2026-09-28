"""Create clearly fictitious offline PDF for local layout QA."""
from pathlib import Path
import sys
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from document import print_pdf
from test_production import fixture

target = Path(__file__).resolve().parents[1] / "work" / "DEMO001_长安大学国际学生考勤册.pdf"
with sync_playwright() as pw:
    print_pdf(pw, "chrome", fixture(), target)
print(target)
