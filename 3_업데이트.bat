@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo 먼저 "1_설치.bat"을 실행해주세요.
    pause
    exit /b 1
)
echo 업데이트 전에 실행 중인 프로그램의 검은 창을 닫아주세요.
echo 아이디, 비밀번호와 개인 설정은 그대로 유지됩니다.
pause
rem Keep these commands in memory while the updater replaces this file.
(
    ".venv\Scripts\python.exe" korail_update.py
    if errorlevel 1 (
        echo 업데이트 실패. 위 오류를 확인해주세요.
        pause
        exit /b 1
    )
    pause
    exit /b 0
)
