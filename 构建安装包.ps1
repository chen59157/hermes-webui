# Hermes WebUI v3.1.0 安装包构建脚本
# 使用方法：右键点击此文件 -> 使用 PowerShell 运行

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Hermes WebUI v3.1.0 安装包构建脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查 Inno Setup 是否安装
$ISCCPaths = @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
)

$ISCCPath = $null
foreach ($path in $ISCCPaths) {
    if (Test-Path $path) {
        $ISCCPath = $path
        break
    }
}

if (-not $ISCCPath) {
    Write-Host "[错误] 未找到 Inno Setup 6" -ForegroundColor Red
    Write-Host ""
    Write-Host "请先安装 Inno Setup 6:" -ForegroundColor Yellow
    Write-Host "https://jrsoftware.org/isinfo.php" -ForegroundColor Blue
    Write-Host ""
    Write-Host "安装完成后重新运行此脚本" -ForegroundColor Yellow
    Read-Host "按 Enter 键退出"
    exit 1
}

Write-Host "[信息] 找到 Inno Setup: $ISCCPath" -ForegroundColor Green
Write-Host ""

# 检查优化文件是否存在
Write-Host "[检查] 验证优化文件..." -ForegroundColor Yellow

$requiredFiles = @(
    "design-system.css",
    "ui-components.css",
    "ui-components.js",
    "loading.html",
    "hermes_desktop.py",
    "build_installer.iss"
)

$allFilesExist = $true
foreach ($file in $requiredFiles) {
    if (Test-Path $file) {
        Write-Host "  ✓ $file" -ForegroundColor Green
    } else {
        Write-Host "  ✗ $file (不存在)" -ForegroundColor Red
        $allFilesExist = $false
    }
}

if (-not $allFilesExist) {
    Write-Host ""
    Write-Host "[错误] 部分优化文件缺失，请检查" -ForegroundColor Red
    Read-Host "按 Enter 键退出"
    exit 1
}

Write-Host ""
Write-Host "[成功] 所有优化文件已就位" -ForegroundColor Green
Write-Host ""

# 创建输出目录
if (-not (Test-Path "dist")) {
    New-Item -ItemType Directory -Path "dist" | Out-Null
}

# 构建安装包
Write-Host "[构建] 开始构建安装包..." -ForegroundColor Yellow
Write-Host ""

try {
    $process = Start-Process -FilePath $ISCCPath -ArgumentList "build_installer.iss" -Wait -PassThru -NoNewWindow

    if ($process.ExitCode -eq 0) {
        Write-Host ""
        Write-Host "========================================" -ForegroundColor Green
        Write-Host "  构建成功！" -ForegroundColor Green
        Write-Host "========================================" -ForegroundColor Green
        Write-Host ""
        Write-Host "安装包位置: dist\HermesWebUI_Setup_v3.1.0.exe" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "优化内容:" -ForegroundColor Yellow
        Write-Host "  - 性能优化（Python路径缓存、日志系统优化）" -ForegroundColor White
        Write-Host "  - UI/UX重构（设计系统、UI组件库、Loading过渡页）" -ForegroundColor White
        Write-Host "  - 代码重构（配置常量提取、改进错误弹窗）" -ForegroundColor White
        Write-Host ""

        # 询问是否打开输出目录
        $openDir = Read-Host "是否打开安装包所在目录？(Y/N)"
        if ($openDir -eq "Y" -or $openDir -eq "y") {
            Invoke-Item "dist"
        }
    } else {
        Write-Host ""
        Write-Host "[错误] 构建失败，退出码: $($process.ExitCode)" -ForegroundColor Red
        Write-Host "请检查 Inno Setup 输出的错误信息" -ForegroundColor Yellow
    }
} catch {
    Write-Host ""
    Write-Host "[错误] 构建过程发生异常: $_" -ForegroundColor Red
}

Write-Host ""
Read-Host "按 Enter 键退出"
