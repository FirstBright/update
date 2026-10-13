@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================
echo   코레일 자동예매 프로그램 - 최초 설치
echo   (인터넷 연결이 필요합니다)
echo ============================================
echo.

set "PYCMD="
set "PYARGS="

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 --version >nul 2>nul
    if !errorlevel!==0 (
        set "PYCMD=py"
        set "PYARGS=-3"
        goto :have_python
    )
)

for /f "delims=" %%P in ('where python 2^>nul') do (
    echo %%P | findstr /i "WindowsApps" >nul
    if errorlevel 1 (
        "%%P" --version >nul 2>nul
        if !errorlevel!==0 (
            set "PYCMD=%%P"
            set "PYARGS="
            goto :have_python
        )
    )
)

echo Python이 설치되어 있지 않습니다. 자동으로 내려받아 설치합니다...
set "PY_VERSION=3.14.7"
set "PY_INSTALLER=%TEMP%\python-installer.exe"

curl -L -o "%PY_INSTALLER%" "https://www.python.org/ftp/python/%PY_VERSION%/python-%PY_VERSION%-amd64.exe"
if not exist "%PY_INSTALLER%" (
    echo.
    echo [오류] Python 설치 파일을 내려받지 못했습니다.
    echo 인터넷 연결을 확인하거나 https://www.python.org 에서 직접 설치한 뒤 다시 실행해주세요.
    pause
    exit /b 1
)

echo Python을 설치하는 중입니다. 잠시만 기다려주세요...
"%PY_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_test=0
del "%PY_INSTALLER%"

set "PYCMD=%LocalAppData%\Programs\Python\Python314\python.exe"
if not exist "%PYCMD%" (
    echo.
    echo [오류] Python 설치를 확인하지 못했습니다.
    echo https://www.python.org 에서 직접 설치한 뒤 이 파일을 다시 실행해주세요.
    pause
    exit /b 1
)
echo Python 설치 완료.
echo.

:have_python
if exist ".venv\Scripts\python.exe" (
    echo 기존 가상환경을 재사용합니다. 패키지를 최신 호환 버전으로 맞춥니다...
) else (
    echo 가상환경을 준비하는 중입니다...
    "%PYCMD%" %PYARGS% -m venv .venv
    if errorlevel 1 (
        echo.
        echo [오류] 가상환경 생성에 실패했습니다.
        pause
        exit /b 1
    )
)

echo 필요한 패키지를 설치하는 중입니다... (수 분 정도 걸릴 수 있습니다)
".venv\Scripts\python.exe" -m pip install --upgrade pip
rem --upgrade: requirements.txt 범위 안에서 최신 버전으로 맞춥니다 (메이저 업그레이드는 하지 않음).
rem --upgrade-strategy eager: 하위 의존성도 함께 맞춰 버전 조합이 어긋나지 않게 합니다.
".venv\Scripts\python.exe" -m pip install --upgrade --upgrade-strategy eager -r requirements.txt
if errorlevel 1 (
    echo.
    echo [오류] 패키지 설치에 실패했습니다. 인터넷 연결을 확인하고 다시 시도해주세요.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m pip check
if errorlevel 1 (
    echo.
    echo [오류] 설치된 패키지끼리 버전이 맞지 않습니다. 위 메시지를 확인해주세요.
    echo .venv 폴더를 지운 뒤 이 파일을 다시 실행하면 깨끗하게 재설치됩니다.
    pause
    exit /b 1
)

if not exist "korail_credentials.txt" (
    (
        echo # Keep this file private. Do not share your password.
        echo KORAIL_ID=
        echo KORAIL_PASSWORD=
        echo.
        echo # Optional ntfy topic for phone notifications.
        echo NTFY_TOPIC=
    ) > "korail_credentials.txt"
    if errorlevel 1 (
        echo [오류] 계정 설정 파일을 만들지 못했습니다. 담당자에게 문의해주세요.
        pause
        exit /b 1
    )
    echo.
    echo korail_credentials.txt 파일을 만들었습니다.
    echo 메모장으로 열어서 본인의 코레일 아이디와 비밀번호를 입력한 뒤 저장해주세요.
)

echo.
echo ============================================
echo   설치가 완료되었습니다!
echo   korail_credentials.txt에 본인의 아이디와 비밀번호를 저장해주세요.
echo   계정 입력 후 "2_실행.bat" 파일을 더블클릭하면 됩니다.
echo ============================================
pause
