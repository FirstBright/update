"""Download changed app files; preserve all other local files and folders."""

from __future__ import annotations

import ast
from contextlib import contextmanager
import datetime
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile

REPOSITORY = "FirstBright/update"
# Never replace credentials, maintainer scripts, Git settings, or environments.
APP_FILES = (
    "README.md",
    "ROADMAP.md",
    "코레일_실행.bat",
    "korail_launcher.py",
    "korail_update.py",
    "requirements.txt",
    "korail_credentials.example.txt",
    "app.py",
    "korail_common.py",
    "korail_desktop_alert.py",
    "korail_notify.py",
    "korail_reserve.py",
    "korail_result_ui.py",
)
VERSION_FILE = ".korail-version"
MAX_DOWNLOAD = 20 * 1024 * 1024


class AppRunningError(RuntimeError):
    """Another launcher or update holds the lock."""


def download(url: str, timeout: float = 60) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "Korail-App-Updater"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read(MAX_DOWNLOAD + 1)
    if len(data) > MAX_DOWNLOAD:
        raise ValueError("업데이트 파일이 허용 크기를 초과했습니다.")
    return data


def read_app_files(archive: bytes, commit: str) -> dict[str, bytes]:
    """Read exact members without extracting arbitrary archive paths."""
    prefix = f"update-{commit}/"
    result = {}
    with zipfile.ZipFile(io.BytesIO(archive)) as package:
        for filename in APP_FILES:
            member = package.getinfo(prefix + filename)
            if member.file_size > MAX_DOWNLOAD:
                raise ValueError(f"업데이트 파일 크기 오류: {filename}")
            result[filename] = package.read(member)
            if sum(map(len, result.values())) > MAX_DOWNLOAD:
                raise ValueError("압축 해제된 업데이트가 너무 큽니다.")
            if filename.endswith(".py"):
                ast.parse(result[filename].decode("utf-8-sig"), filename=filename)
    return result


@contextmanager
def update_lock(root: Path):
    # OS releases the lock on exit or crash; leaving the lock file is intentional.
    with (root / ".korail-update.lock").open("a+b") as lock:
        lock.seek(0)
        lock.write(b"0")
        lock.flush()
        lock.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise AppRunningError("프로그램이 이미 실행 중입니다.") from error
        yield


def install_files(root: Path, files: dict[str, bytes], commit: str) -> tuple[int, Path | None]:
    if set(files) != set(APP_FILES):
        raise ValueError("업데이트 파일 목록이 올바르지 않습니다.")
    desired = {**files, VERSION_FILE: (commit + "\n").encode("ascii")}
    original = {}
    replacements = {}
    for name, data in desired.items():
        target = root / name
        if target.is_symlink() or (target.exists() and not target.is_file()):
            raise ValueError(f"일반 파일이 아닌 업데이트 대상: {name}")
        previous = target.read_bytes() if target.exists() else None
        if previous != data:
            original[name] = previous
            replacements[name] = data
    if not replacements:
        return 0, None

    backup_parent = root / "output" / "updates"
    backup_parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-")
    backup = Path(tempfile.mkdtemp(prefix=stamp, dir=backup_parent))
    # Complete backup before replacing any app files.
    for name, data in original.items():
        if data is not None:
            (backup / name).write_bytes(data)
    (backup / "backup-info.json").write_text(
        json.dumps({"new_commit": commit, "previously_absent": [
            name for name, data in original.items() if data is None
        ]}, indent=2), encoding="utf-8",
    )
    temp_parent = root / "tmp"
    temp_parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="korail-update-", dir=temp_parent,
                                     ignore_cleanup_errors=True) as work:
        staged = Path(work)
        for name, data in replacements.items():
            (staged / name).write_bytes(data)
        installed = []
        try:
            for name in replacements:
                os.replace(staged / name, root / name)
                installed.append(name)
        except OSError as error:
            rollback_errors = []
            for name in reversed(installed):
                try:
                    if original[name] is None:
                        (root / name).unlink()
                    else:
                        (staged / name).write_bytes(original[name])
                        os.replace(staged / name, root / name)
                except OSError:
                    rollback_errors.append(name)
            if rollback_errors:
                raise RuntimeError(f"일부 파일 복구 실패: {rollback_errors}. 백업: {backup}") from error
            raise RuntimeError("업데이트 실패. 기존 앱 파일을 복구했습니다.") from error
    return len(set(replacements) - {VERSION_FILE}), backup


def is_current(root: Path, commit: str) -> bool:
    version = root / VERSION_FILE
    return (
        version.is_file()
        and version.read_text(encoding="ascii", errors="replace").strip() == commit
        and all((root / name).is_file() for name in APP_FILES)
    )


def main(argv: list[str] | None = None) -> int:
    # --auto: called by 코레일_실행.bat before every start; failures only skip the update.
    auto = "--auto" in (sys.argv[1:] if argv is None else argv)
    root = Path(__file__).resolve().parent
    if auto and (root / ".git").exists():
        # Maintainer's working copy: never overwrite unpublished edits automatically.
        print("개발용 폴더(.git)라 자동 업데이트를 건너뜁니다.")
        return 0
    try:
        with update_lock(root):
            print("GitHub에서 최신 버전을 확인합니다...", flush=True)
            info = json.loads(download(
                f"https://api.github.com/repos/{REPOSITORY}/commits/main",
                timeout=10 if auto else 60,
            ))
            commit = info["sha"]
            if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
                raise ValueError("GitHub 버전 응답이 올바르지 않습니다.")
            if is_current(root, commit):
                print(f"최신 버전입니다 ({commit[:12]}).")
                return 0
            archive = download(f"https://codeload.github.com/{REPOSITORY}/zip/{commit}")
            files = read_app_files(archive, commit)
            count, backup = install_files(root, files, commit)
            print(f"업데이트 완료: {count}개 앱 파일 변경 ({commit[:12]}).")
            if backup:
                print(f"기존 파일 백업: {backup}")
            if not auto:
                print('"코레일_실행.bat"으로 다시 실행해주세요. 필요한 패키지는 실행 시 설치됩니다.')
        return 0
    except AppRunningError:
        print("프로그램이 실행 중이라 업데이트하지 않았습니다. 실행 중인 검은 창을 닫고 다시 시도해주세요.")
        return 1
    except urllib.error.HTTPError as error:
        if error.code in (404, 409, 422):
            print("아직 업데이트가 게시되지 않았거나 저장소에 접근할 수 없습니다. 담당자에게 문의해주세요.")
        elif error.code in (403, 429):
            print("GitHub 요청 제한입니다. 잠시 후 다시 시도해주세요.")
        else:
            print(f"다운로드 실패 (HTTP {error.code}). 기존 앱으로 다시 실행해주세요.")
    except Exception as error:
        print(f"업데이트 오류: {error}")
    if auto:
        print("업데이트를 건너뛰고 현재 버전으로 실행합니다.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
