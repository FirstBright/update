#!/bin/bash
# macOS version of 코레일_실행.bat: double-click in Finder to install, update and run.
cd "$(dirname "$0")" || exit 1
printf '\033]0;코레일 자동예매\007'

echo "============================================"
echo "  코레일 자동예매 프로그램 (Mac)"
echo "  (설치 / 업데이트 / 실행을 자동으로 합니다)"
echo "============================================"
echo

finish() {
    echo
    read -r -p "엔터를 누르면 창이 닫힙니다..." _
    exit "$1"
}

PY_VERSION="3.14.7"

# python.org and Homebrew installs first; the Xcode /usr/bin/python3 is often too old.
find_python() {
    local candidate
    for candidate in \
        /Library/Frameworks/Python.framework/Versions/3.1[0-9]/bin/python3 \
        /opt/homebrew/bin/python3 /usr/local/bin/python3 \
        "$(command -v python3 2>/dev/null)"; do
        [ -x "$candidate" ] || continue
        # pykorail needs Python 3.11+.
        if "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null; then
            PYCMD="$candidate"
            return 0
        fi
    done
    return 1
}

if [ ! -x ".venv/bin/python" ]; then
    echo "처음 실행이라 설치를 진행합니다. (인터넷 연결이 필요합니다)"
    echo
    if ! find_python; then
        echo "Python 3.11 이상이 설치되어 있지 않습니다. 설치 파일을 내려받습니다..."
        installer="${TMPDIR:-/tmp}/python-$PY_VERSION-macos11.pkg"
        if ! curl -fL -o "$installer" "https://www.python.org/ftp/python/$PY_VERSION/python-$PY_VERSION-macos11.pkg"; then
            echo
            echo "[오류] Python 설치 파일을 내려받지 못했습니다."
            echo "인터넷 연결을 확인하거나 https://www.python.org 에서 직접 설치한 뒤 다시 실행해주세요."
            finish 1
        fi
        echo "열리는 설치 창에서 '계속'을 눌러 설치를 끝내주세요. (Mac 암호가 필요할 수 있습니다)"
        open -W "$installer"
        rm -f "$installer"
        if ! find_python; then
            echo
            echo "[오류] Python 설치를 확인하지 못했습니다."
            echo "설치를 마친 뒤 이 파일을 다시 실행해주세요."
            finish 1
        fi
        echo "Python 설치 완료."
        echo
    fi
    echo "가상환경을 준비하는 중입니다..."
    if ! "$PYCMD" -m venv .venv; then
        echo
        echo "[오류] 가상환경 생성에 실패했습니다."
        finish 1
    fi
fi

# The updater may replace this file; bash has already read the whole block below.
{
    .venv/bin/python korail_update.py --auto
    echo
    # caffeinate keeps the Mac awake while reservations are polling (Windows does this in Python).
    caffeinate -i .venv/bin/python korail_launcher.py
    echo
    echo "프로그램이 종료되었습니다."
    finish 0
}
