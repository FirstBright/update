@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo 먼저 "1_설치.bat" 파일을 실행해주세요.
    pause
    exit /b 1
)

if not exist "korail_credentials.txt" (
    echo korail_credentials.txt 파일이 없습니다. "1_설치.bat"을 먼저 실행해주세요.
    pause
    exit /b 1
)

rem requirements.txt 범위를 만족하는지 확인합니다. 이미 만족하면 아무것도 내려받지 않습니다.
".venv\Scripts\python.exe" -m pip install --quiet --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
    echo.
    echo [오류] 패키지 버전이 requirements.txt와 맞지 않습니다. "1_설치.bat"을 다시 실행해주세요.
    pause
    exit /b 1
)

echo 프로그램을 실행합니다. 잠시 후 브라우저 창이 열립니다...
echo 최초 실행 시 Email: 입력란이 나오면 아무것도 입력하지 말고 Enter를 눌러주세요.
echo 프로그램을 끝내려면 이 검은 창을 닫으세요.
echo.

".venv\Scripts\python.exe" -m streamlit run app.py

echo.
echo 프로그램이 종료되었습니다.
pause
