@echo off
:: Hermes WebUI 安装向导启动器
:: 双击运行即可开始安装
title Hermes WebUI 安装向导
cd /d "%~dp0"

:: 检查 Python
if not exist "%~dp0hermes-agent\.venv\Scripts\python.exe" (
    echo 错误：找不到 Python 环境
    echo 请确保 hermes-agent\.venv 目录完整
    pause
    exit /b 1
)

:: 启动安装向导（最小化命令行窗口）
start /min "" "%~dp0hermes-agent\.venv\Scripts\python.exe" "%~dp0setup_wizard.py"
exit