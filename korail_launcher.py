"""Started by 코레일_실행.bat after the update check: sync packages, then run the app."""

from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import sys
import webbrowser

from korail_update import AppRunningError, update_lock

ROOT = Path(__file__).resolve().parent
REQUIREMENTS = ROOT / "requirements.txt"
# Lives inside .venv so a fresh environment always installs again.
REQUIREMENTS_STAMP = Path(sys.prefix) / ".korail-requirements"
APP_URL = "http://localhost:8501"


def pip(*args: str) -> int:
    return subprocess.call([sys.executable, "-m", "pip", "--disable-pip-version-check", *args])


def sync_packages() -> bool:
    """Install requirements only when requirements.txt or Python changed."""
    digest = hashlib.sha256(REQUIREMENTS.read_bytes() + sys.version.encode()).hexdigest()
    if REQUIREMENTS_STAMP.is_file() and REQUIREMENTS_STAMP.read_text().strip() == digest:
        return True
    print("필요한 패키지를 설치하는 중입니다... (처음에는 수 분 정도 걸릴 수 있습니다)", flush=True)
    pip("install", "--quiet", "--upgrade", "pip")
    # --upgrade-strategy eager: 하위 의존성도 함께 맞춰 버전 조합이 어긋나지 않게 합니다.
    if pip("install", "--upgrade", "--upgrade-strategy", "eager", "-r", str(REQUIREMENTS)) != 0:
        print("[오류] 패키지 설치에 실패했습니다. 인터넷 연결을 확인해주세요.")
        return False
    if pip("check") != 0:
        print("[오류] 설치된 패키지끼리 버전이 맞지 않습니다.")
        print(".venv 폴더를 지운 뒤 다시 실행하면 깨끗하게 재설치됩니다.")
        return False
    REQUIREMENTS_STAMP.write_text(digest + "\n")
    return True


def skip_streamlit_email_prompt() -> None:
    # Streamlit asks for an email on its very first run; an empty answer is what Enter saves.
    credentials = Path.home() / ".streamlit" / "credentials.toml"
    if not credentials.exists():
        credentials.parent.mkdir(exist_ok=True)
        credentials.write_text('[general]\nemail = ""\n', encoding="utf-8")


def main() -> int:
    try:
        with update_lock(ROOT):
            if not sync_packages():
                try:
                    import streamlit  # noqa: F401
                except ImportError:
                    return 1
                print("기존에 설치된 패키지로 실행합니다.")
            skip_streamlit_email_prompt()
            print()
            print("프로그램을 실행합니다. 잠시 후 브라우저 창이 열립니다...")
            print("프로그램을 끝내려면 이 검은 창을 닫으세요.")
            print()
            return subprocess.call(
                [sys.executable, "-m", "streamlit", "run", "app.py",
                 "--browser.gatherUsageStats", "false"],
                cwd=ROOT,
            )
    except AppRunningError:
        print("프로그램이 이미 실행 중입니다. 열려 있는 브라우저 창을 사용해주세요.")
        webbrowser.open(APP_URL)
        return 0
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
