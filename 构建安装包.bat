@echo off
chcp 65001 >nul 2>&1
echo ========================================
echo   Hermes WebUI v3.1.0 安装包构建脚本
echo ========================================
echo.

:: 检查 Inno Setup 是否安装
set "ISCC_PATH="
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    set "ISCC_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
) else if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    set "ISCC_PATH=C:\Program Files\Inno Setup 6\ISCC.exe"
) else (
    echo [错误] 未找到 Inno Setup 6
    echo.
    echo 请先安装 Inno Setup 6:
    echo https://jrsoftware.org/isinfo.php
    echo.
    pause
    exit /b 1
)

echo [信息] 找到 Inno Setup: %ISCC_PATH%
echo.

:: 检查优化文件是否存在
echo [检查] 验证优化文件...
if not exist "design-system.css" (
    echo [错误] design-system.css 不存在
    pause
    exit /b 1
)
if not exist "ui-components.css" (
    echo [错误] ui-components.css 不存在
    pause
    exit /b 1
)
if not exist "ui-components.js" (
    echo [错误] ui-components.js 不存在
    pause
    exit /b 1
)
if not exist "loading.html" (
    echo [错误] loading.html 不存在
    pause
    exit /b 1
)
if not exist "hermes_desktop.py" (
    echo [错误] hermes_desktop.py 不存在
    pause
    exit /b 1
)
echo [成功] 所有优化文件已就位
echo.

:: 创建输出目录
if not exist "dist" mkdir "dist"

:: 构建安装包
echo [构建] 开始构建安装包...
echo.
"%ISCC_PATH%" build_installer.iss

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo   构建成功！
    echo ========================================
    echo.
    echo 安装包位置: dist\HermesWebUI_Setup_v3.1.0.exe
    echo.
    echo 优化内容:
    echo   - 性能优化（Python路径缓存、日志系统优化）
    echo   - UI/UX重构（设计系统、UI组件库、Loading过渡页）
    echo   - 代码重构（配置常量提取、改进错误弹窗）
    echo.
) else (
    echo.
    echo [错误] 构建失败，请检查错误信息
    echo.
)

pause
