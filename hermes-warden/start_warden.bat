@echo off
chcp 65001 >nul 2>&1
title HermesWarden - Task Daemon

REM Set Warden home directory
set "WARDEN_HOME=%~dp0"
set "WARDEN_HOME=%WARDEN_HOME:~0,-1%"

REM Load .env
if exist "%WARDEN_HOME%\.env" (
    for /f "usebackq tokens=1,2 delims==" %%a in ("%WARDEN_HOME%\.env") do (
        if not "%%a"=="" if not "%%a"=="#" if not "%%a:~0,1%"=="#" set "%%a=%%b"
    )
)

echo ========================================
echo   HermesWarden v1.1 - Task Daemon
echo   WARDEN_HOME: %WARDEN_HOME%
echo ========================================

REM Use same Python as hermes-agent venv
set "PYTHON_EXE=%WARDEN_HOME%\..\hermes-agent\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"

echo Starting Warden daemon...
"%PYTHON_EXE%" "%WARDEN_HOME%\warden_daemon.py" %*

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Warden exited with code %ERRORLEVEL%
    pause
)