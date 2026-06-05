# 打包与分发指南

> 本文档说明如何将 Hermes WebUI Desktop Client 打包为可分发的安装程序。

---

## 1. 打包策略概述

| 方式 | 产物 | 适用场景 | Python 依赖 |
|------|------|---------|-------------|
| Portable 便携版 | 文件夹 + .bat 启动脚本 | 开发测试、U 盘携带 | 需要用户安装 Python |
| PyInstaller 打包 | 单个 .exe 文件 | 分发、用户无需安装 Python | 内嵌 Python |
| NSIS/Inno Setup | .exe 安装包 | 正式发布 | 内嵌 Python |

当前项目使用 **Portable 便携版** 方案（参考 `Hermes-WebUI-Portable/` 目录）。

---

## 2. Portable 便携版打包

### 2.1 目录结构

```
Hermes-WebUI-Portable/
├── Hermes WebUI.lnk          # 快捷方式
├── hermes-icon.ico           # 图标
├── portable_app.py           # 便携版启动器
├── 启动 Hermes WebUI.bat     # 启动脚本
├── 使用说明.txt              # 用户文档
├── hermes-agent/             # Agent 核心（含 .venv）
├── hermes-webui-cn/          # Web UI（含 .venv）
└── .hermes/                  # 预置配置目录
```

### 2.2 打包步骤

#### Step 1: 准备虚拟环境

```powershell
# hermes-agent 虚拟环境
cd hermes-agent
python -m venv .venv
.venv\Scripts\activate
pip install -e .
deactivate

# hermes-webui-cn 虚拟环境
cd ..\hermes-webui-cn
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
deactivate
cd ..
```

#### Step 2: 组装目录

```powershell
$PORTABLE_DIR = "Hermes-WebUI-Portable"

# 创建目录
New-Item -ItemType Directory -Path $PORTABLE_DIR -Force

# 复制核心文件
Copy-Item "hermes_desktop.py" "$PORTABLE_DIR\"
Copy-Item "hermes-icon.ico" "$PORTABLE_DIR\"
Copy-Item "启动 Hermes WebUI.bat" "$PORTABLE_DIR\"
Copy-Item "使用说明.txt" "$PORTABLE_DIR\"

# 复制子项目（含 .venv）
Copy-Item "hermes-agent" "$PORTABLE_DIR\hermes-agent" -Recurse
Copy-Item "hermes-webui-cn" "$PORTABLE_DIR\hermes-webui-cn" -Recurse

# 清理不必要的文件
Remove-Item "$PORTABLE_DIR\hermes-agent\.git" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "$PORTABLE_DIR\hermes-webui-cn\.git" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "$PORTABLE_DIR\hermes-agent\tests" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "$PORTABLE_DIR\hermes-webui-cn\tests" -Recurse -Force -ErrorAction SilentlyContinue

# 创建 .hermes 预置目录
New-Item -ItemType Directory -Path "$PORTABLE_DIR\.hermes" -Force
```

#### Step 3: 创建便携启动器 port_app.py

便携版启动器 `portable_app.py` 的关键逻辑：

```python
import os
import sys
import subprocess
import webview

# 动态定位 Python（便携版特有）
APP_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_PY = os.path.join(APP_DIR, "hermes-agent", ".venv", "Scripts", "python.exe")

if not os.path.isfile(VENV_PY):
    print("错误: 虚拟环境不存在，请重新安装")
    sys.exit(1)

# 启动后端服务
server_script = os.path.join(APP_DIR, "hermes-webui-cn", "server.py")
process = subprocess.Popen(
    [VENV_PY, server_script],
    cwd=os.path.join(APP_DIR, "hermes-webui-cn"),
    env={**os.environ, "HERMES_PORT": "8787"}
)

# 创建窗口...
```

#### Step 4: 创建压缩包

```powershell
# 使用 PowerShell
Compress-Archive -Path "Hermes-WebUI-Portable" -DestinationPath "Hermes-WebUI-Portable-v2.0.zip"

# 或使用 7-Zip
7z a -tzip "Hermes-WebUI-Portable-v2.0.zip" "Hermes-WebUI-Portable\"
```

---

## 3. PyInstaller 打包（高级方案）

### 3.1 安装 PyInstaller

```powershell
pip install pyinstaller
```

### 3.2 创建 .spec 文件

`hermes_desktop.spec`:

```python
# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['hermes_desktop.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('hermes-icon.ico', '.'),
        ('hermes-webui-cn', 'hermes-webui-cn'),
        ('hermes-agent', 'hermes-agent'),
        ('settings.json', '.'),
    ],
    hiddenimports=[
        'webview',
        'webview.platforms.winforms',
        'clr',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy.tests',
    ],
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Hermes WebUI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='hermes-icon.ico',
)
```

### 3.3 执行打包

```powershell
pyinstaller hermes_desktop.spec --clean --noconfirm
```

产物位于 `dist/Hermes WebUI/`。

### 3.4 PyInstaller 注意事项

| 问题 | 解决方案 |
|------|---------|
| pywebview 找不到 | 确保 `hiddenimports` 包含 webview 相关模块 |
| 子进程路径错误 | 使用 `sys._MEIPASS` 获取 PyInstaller 临时目录 |
| .venv 无法打包 | 需在 PyInstaller 打包前将依赖安装到系统 Python 而非虚拟环境 |
| 文件体积过大 | 排除不需要的模块（tkinter, matplotlib 等） |

---

## 4. 安装包制作（NSIS）

### 4.1 NSIS 脚本模板

`installer.nsi`:

```nsis
!define PRODUCT_NAME "Hermes WebUI"
!define PRODUCT_VERSION "2.0"
!define PRODUCT_PUBLISHER "Hermes WebUI Team"

Name "${PRODUCT_NAME} ${PRODUCT_VERSION}"
OutFile "Hermes-WebUI-Setup-${PRODUCT_VERSION}.exe"
InstallDir "$PROGRAMFILES\${PRODUCT_NAME}"
RequestExecutionLevel admin

Section "Install"
    SetOutPath "$INSTDIR"
    File /r "dist\Hermes WebUI\*"
    
    CreateShortCut "$DESKTOP\${PRODUCT_NAME}.lnk" "$INSTDIR\Hermes WebUI.exe"
    CreateDirectory "$SMPROGRAMS\${PRODUCT_NAME}"
    CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\${PRODUCT_NAME}.lnk" "$INSTDIR\Hermes WebUI.exe"
    
    WriteUninstaller "$INSTDIR\uninstall.exe"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "DisplayName" "${PRODUCT_NAME}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "UninstallString" "$INSTDIR\uninstall.exe"
SectionEnd

Section "Uninstall"
    Delete "$DESKTOP\${PRODUCT_NAME}.lnk"
    RMDir /r "$SMPROGRAMS\${PRODUCT_NAME}"
    RMDir /r "$INSTDIR"
    DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
SectionEnd
```

---

## 5. 版本管理

### 5.1 版本号规范

遵循 [Semantic Versioning 2.0.0](https://semver.org/lang/zh-CN/)：

```
主版本号.次版本号.修订号
   MAJOR . MINOR . PATCH

示例:
- 2.0.0  # 初始发布
- 2.0.1  # Bug 修复
- 2.1.0  # 向后兼容的新功能
- 3.0.0  # 不兼容的 API 变更
```

### 5.2 更新版本号的位置

| 文件 | 字段 |
|------|------|
| `hermes_desktop.py` | 文件头部文档注释 |
| `CHANGELOG.md` | 添加新版本条目 |
| `使用说明.txt` | 更新版本号和日期 |
| 安装脚本 | `!define PRODUCT_VERSION` |

---

## 6. 发布检查清单

- [ ] `CHANGELOG.md` 已更新
- [ ] `使用说明.txt` 版本和日期已更新
- [ ] Hermes Agent 子模块已更新到最新稳定版
- [ ] Hermes WebUI 子模块已更新到最新稳定版
- [ ] 清理了开发文件（`.git`、`tests/`、`__pycache__/`）
- [ ] 虚拟环境依赖完整（`pip list` 无缺失）
- [ ] 在干净环境测试启动流程
- [ ] 检查 `.env` API Key 已移除
- [ ] ZIP 包完整性验证
- [ ] Git tag 已创建：`git tag -a v2.0.0 -m "Release v2.0.0"`

---

*更新于 2026-05-24*