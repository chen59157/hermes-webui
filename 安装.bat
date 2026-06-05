@echo off
chcp 65001 >nul 2>&1
title Hermes WebUI 安装程序
setlocal enabledelayedexpansion

echo.
echo  ╔══════════════════════════════════════╗
echo  ║      Hermes WebUI v2.1 安装程序      ║
echo  ╚══════════════════════════════════════╝
echo.

:: 设置安装目录
set "INSTALL_DIR=%USERPROFILE%\Hermes WebUI"
set "SOURCE_DIR=%~dp0"

echo  安装位置: %INSTALL_DIR%
echo.
set /p CONFIRM=  按 Enter 确认安装，或输入新路径后按 Enter: 
if not "%CONFIRM%"=="" set "INSTALL_DIR=%CONFIRM%"

echo.
echo  正在安装到: %INSTALL_DIR%
echo.

:: 创建安装目录
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

:: 复制文件（排除安装脚本本身和日志）
echo  [1/5] 复制程序文件...
robocopy "%SOURCE_DIR%hermes-agent" "%INSTALL_DIR%\hermes-agent" /E /COPYALL /XD ".git" "__pycache__" /XF "*.pyc" /NFL /NDL /NJH /NJS >nul 2>&1
robocopy "%SOURCE_DIR%hermes-webui-cn" "%INSTALL_DIR%\hermes-webui-cn" /E /COPYALL /XD ".git" "__pycache__" "node_modules" /XF "*.pyc" /NFL /NDL /NJH /NJS >nul 2>&1
robocopy "%SOURCE_DIR%tk_runtime" "%INSTALL_DIR%\tk_runtime" /E /COPYALL /NFL /NDL /NJH /NJS >nul 2>&1
copy /Y "%SOURCE_DIR%hermes_desktop.py" "%INSTALL_DIR%\hermes_desktop.py" >nul
copy /Y "%SOURCE_DIR%hermes-icon.ico" "%INSTALL_DIR%\hermes-icon.ico" >nul
copy /Y "%SOURCE_DIR%使用说明.txt" "%INSTALL_DIR%\使用说明.txt" >nul

:: 修复 venv pyvenv.cfg（重定位 Python 路径）
echo  [2/5] 配置 Python 环境...
set "PYVENV_CFG=%INSTALL_DIR%\hermes-agent\.venv\pyvenv.cfg"
set "VENV_PYTHON=%INSTALL_DIR%\hermes-agent\.venv\Scripts\python.exe"

:: 查找系统 Python
for /f "tokens=*" %%i in ('where python 2^>nul') do (
    set "SYS_PYTHON=%%i"
    goto :found_python
)
for /f "tokens=*" %%i in ('where python3 2^>nul') do (
    set "SYS_PYTHON=%%i"
    goto :found_python
)
:: 常见路径
for %%p in (
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    "C:\Python312\python.exe"
    "C:\Python311\python.exe"
) do (
    if exist %%p (
        set "SYS_PYTHON=%%~p"
        goto :found_python
    )
)
echo  [警告] 未找到 Python，venv 路径配置跳过。如启动失败，请安装 Python 3.10+ 后重试。
goto :skip_python

:found_python
echo  找到 Python: %SYS_PYTHON%
for %%i in ("%SYS_PYTHON%") do set "SYS_PYTHON_DIR=%%~dpi"
set "SYS_PYTHON_DIR=%SYS_PYTHON_DIR:~0,-1%"

:: 获取 Python 版本
for /f "tokens=*" %%v in ('"%SYS_PYTHON%" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')" 2^>nul') do set "PY_VER=%%v"

:: 写入新的 pyvenv.cfg
(
echo home = %SYS_PYTHON_DIR%
echo include-system-site-packages = false
echo version = %PY_VER%
echo executable = %SYS_PYTHON%
) > "%PYVENV_CFG%"
echo  Python 环境配置完成 (v%PY_VER%)

:skip_python

:: 创建启动脚本
echo  [3/5] 创建启动脚本...
set "VENV_PYTHONW=%INSTALL_DIR%\hermes-agent\.venv\Scripts\pythonw.exe"
(
echo @echo off
echo cd /d "%%~dp0"
echo start "" "%VENV_PYTHONW%" "%INSTALL_DIR%\hermes_desktop.py"
) > "%INSTALL_DIR%\启动 Hermes WebUI.bat"

:: 创建桌面快捷方式
echo  [4/5] 创建桌面快捷方式...
set "SHORTCUT=%USERPROFILE%\Desktop\Hermes WebUI.lnk"
powershell -NoProfile -Command "$ws=New-Object -ComObject WScript.Shell; $sc=$ws.CreateShortcut('%SHORTCUT%'); $sc.TargetPath='%VENV_PYTHONW%'; $sc.Arguments='\""%INSTALL_DIR%\hermes_desktop.py"\"'; $sc.WorkingDirectory='%INSTALL_DIR%'; $sc.IconLocation='%INSTALL_DIR%\hermes-icon.ico'; $sc.Save()" >nul 2>&1

:: 创建 settings.json
echo  [5/5] 创建配置文件...
if not exist "%INSTALL_DIR%\settings.json" (
    (
    echo {
    echo   "port": 8787,
    echo   "window_width": 1280,
    echo   "window_height": 800,
    echo   "minimize_to_tray": true,
    echo   "start_minimized": false
    echo }
    ) > "%INSTALL_DIR%\settings.json"
)

echo.
echo  ✓ 安装完成！
echo.
echo  安装位置: %INSTALL_DIR%
echo  桌面快捷方式已创建
echo.
echo  直接双击桌面的 "Hermes WebUI" 图标即可启动。
echo.
pause
