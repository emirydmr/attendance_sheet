"""Create clearly fictitious offline PDF for local layout QA."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from browser_fixture import smoke_profile
from document import print_pdf
from test_production import fixture


def main():
    target = Path(__file__).resolve().parents[2] / "work" / "DEMO001_长安大学国际学生考勤册.pdf"
    profile = smoke_profile()
    target.parent.mkdir(parents=True, exist_ok=True)
    print_pdf(profile, fixture(), target)
    print(target)


if __name__ == "__main__":
    main()
