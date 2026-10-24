@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"
title 코레일 자동예매

echo ============================================
echo   코레일 자동예매 프로그램
echo   (설치 / 업데이트 / 실행을 자동으로 합니다)
echo ============================================
echo.

if exist ".venv\Scripts\python.exe" goto :have_venv

echo 처음 실행이라 설치를 진행합니다. (인터넷 연결이 필요합니다)
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
echo 가상환경을 준비하는 중입니다...
"%PYCMD%" %PYARGS% -m venv .venv
if errorlevel 1 (
    echo.
    echo [오류] 가상환경 생성에 실패했습니다.
    pause
    exit /b 1
)

:have_venv
rem The updater may replace this file; cmd has already read the whole block below.
(
    ".venv\Scripts\python.exe" korail_update.py --auto
    echo.
    ".venv\Scripts\python.exe" korail_launcher.py
    echo.
    echo 프로그램이 종료되었습니다.
    pause
    exit /b 0
)
