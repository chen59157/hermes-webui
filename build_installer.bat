@echo off
chcp 65001 >nul 2>&1
title Hermes WebUI 安装包构建工具

echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║            Hermes WebUI 安装包构建工具              ║
echo  ╚══════════════════════════════════════════════════════╝
echo.

:: 检查 Inno Setup
if not exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    echo 错误：未找到 Inno Setup 6
    echo 请从 https://jrsoftware.org/isdl.php 下载并安装 Inno Setup 6
    pause
    exit /b 1
)

:: 清理临时文件
echo [1/4] 清理临时文件...
if exist "D:\桌面\非~主要\Hermes-WebUI\__pycache__" rmdir /s /q "D:\桌面\非~主要\Hermes-WebUI\__pycache__" 2>nul
if exist "D:\桌面\非~主要\Hermes-WebUI\*.log" del "D:\桌面\非~主要\Hermes-WebUI\*.log" 2>nul
if exist "D:\桌面\非~主要\Hermes-WebUI\dist" rmdir /s /q "D:\桌面\非~主要\Hermes-WebUI\dist" 2>nul

:: 检查必要文件
echo [2/4] 检查项目文件...
if not exist "D:\桌面\非~主要\Hermes-WebUI\hermes_desktop.py" (
    echo 错误：缺少 hermes_desktop.py
    pause
    exit /b 1
)
if not exist "D:\桌面\非~主要\Hermes-WebUI\hermes-webui-cn" (
    echo 错误：缺少 hermes-webui-cn 目录
    pause
    exit /b 1
)
if not exist "D:\桌面\非~主要\Hermes-WebUI\hermes-agent" (
    echo 错误：缺少 hermes-agent 目录
    pause
    exit /b 1
)

:: 编译安装包
echo [3/4] 编译安装包...
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" "D:\桌面\非~主要\Hermes-WebUI\build_installer.iss"

:: 检查结果
echo [4/4] 验证安装包...
if exist "D:\桌面\非~主要\Hermes-WebUI\dist\HermesWebUI_Setup_v3.1.0.exe" (
    echo.
    echo  ✓ 安装包构建成功！
    echo.
    echo  安装包位置: D:\桌面\非~主要\Hermes-WebUI\dist\HermesWebUI_Setup_v3.1.0.exe
    echo  大小: %~z0
    echo.
    echo  安装包特性：
    echo  - 支持自定义安装路径
    echo  - 自动修复 Python 环境
    echo  - 创建桌面快捷方式
    echo  - 注册卸载程序
    echo  - 中文安装界面
    echo.
    echo  测试建议：
    echo  1. 在干净 Win11 虚拟机测试安装
    echo  2. 选择不同安装路径（C盘/D盘）
    echo  3. 验证启动和功能
    echo.
    set /p OPEN=  是否打开安装包目录？(Y/N): 
    if /i "%OPEN%"=="Y" explorer "D:\桌面\非~主要\Hermes-WebUI\dist"
) else (
    echo.
    echo  ✗ 安装包构建失败！
    echo  请检查 Inno Setup 错误日志
    pause
    exit /b 1
)

pause