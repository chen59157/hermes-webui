#!/usr/bin/env python3
"""
Hermes WebUI 安装向导 v3.0
===========================
基于浏览器的安装向导：启动本地HTTP服务 → 自动打开浏览器 →
用户在网页上操作安装流程。

完全不依赖 tkinter，100% 可靠渲染。
"""

import os
import sys
import json
import shutil
import signal
import threading
import subprocess
import time
import webbrowser
import urllib.request
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

# ============================================================
# 配置
# ============================================================

APP_NAME = "Hermes WebUI"
APP_VERSION = "2.1.0"

# 安装包所在目录
if getattr(sys, "frozen", False):
    SETUP_DIR = os.path.dirname(sys.executable)
else:
    SETUP_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULT_INSTALL_DIR = os.path.expandvars(r"%USERPROFILE%\Hermes WebUI")
SOURCE_DIRS = ["hermes-webui-cn", "hermes-agent", ".hermes"]
SOURCE_FILES = ["hermes_desktop.py", "hermes-icon.ico", "使用说明.txt"]
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\HermesWebUI"

# 安装状态
install_state = {
    "status": "ready",      # ready / installing / done / error
    "progress": 0,
    "message": "",
    "error": "",
    "install_dir": "",
}

# ============================================================
# HTML 页面
# ============================================================

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Hermes WebUI 安装向导</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: -apple-system, "Microsoft YaHei UI", "Segoe UI", sans-serif;
    background: #0f0f1a;
    color: #e2e8f0;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
}
.header {
    background: #1a1a2e;
    padding: 20px 30px;
    display: flex;
    align-items: center;
    gap: 12px;
    border-bottom: 1px solid #2d2d5e;
}
.header .logo { font-size: 20px; font-weight: bold; color: #6366f1; }
.header .title { font-size: 14px; color: #94a3b8; }
.container {
    flex: 1;
    max-width: 600px;
    width: 100%;
    margin: 0 auto;
    padding: 40px 30px;
}
.page { display: none; }
.page.active { display: block; }

/* 欢迎页 */
.welcome-icon {
    width: 80px; height: 80px;
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    border-radius: 20px;
    display: flex; align-items: center; justify-content: center;
    font-size: 36px; margin: 0 auto 24px;
}
.welcome-icon span { color: white; }
h1 { font-size: 28px; font-weight: bold; text-align: center; margin-bottom: 8px; }
.version { text-align: center; color: #94a3b8; margin-bottom: 24px; }
.desc {
    text-align: center; color: #94a3b8; line-height: 1.8;
    margin-bottom: 40px;
}

/* 按钮 */
.btn {
    display: inline-block; padding: 12px 32px;
    border: none; border-radius: 8px; cursor: pointer;
    font-size: 15px; font-weight: 600;
    transition: all 0.2s;
}
.btn-primary {
    background: #6366f1; color: white;
}
.btn-primary:hover { background: #4f46e5; }
.btn-secondary {
    background: #16213e; color: #94a3b8;
    border: 1px solid #2d2d5e;
}
.btn-secondary:hover { background: #1e2a4a; color: #e2e8f0; }
.btn-success { background: #34d399; color: #0f0f1a; }
.btn-success:hover { background: #2cc08a; }
.btn-lg { padding: 14px 48px; font-size: 16px; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-row {
    display: flex; gap: 12px; justify-content: center;
    margin-top: 30px; flex-wrap: wrap;
}

/* 卡片 */
.card {
    background: #16213e; border-radius: 12px;
    padding: 20px; margin-bottom: 16px;
}
.card h3 {
    font-size: 13px; font-weight: 600;
    color: #94a3b8; margin-bottom: 12px;
    text-transform: uppercase; letter-spacing: 0.5px;
}

/* 路径输入 */
.path-row { display: flex; gap: 8px; }
.path-row input {
    flex: 1; padding: 10px 14px;
    background: #0f3460; color: #e2e8f0;
    border: 1px solid #2d2d5e; border-radius: 8px;
    font-size: 14px; outline: none;
}
.path-row input:focus { border-color: #6366f1; }
.path-row button {
    padding: 10px 20px; background: #6366f1; color: white;
    border: none; border-radius: 8px; cursor: pointer;
    font-size: 14px; white-space: nowrap;
}
.path-row button:hover { background: #4f46e5; }
.space-info { font-size: 12px; color: #94a3b8; margin-top: 8px; }

/* 复选框 */
.checkbox-group { display: flex; flex-direction: column; gap: 10px; }
.checkbox-item {
    display: flex; align-items: center; gap: 10px;
    cursor: pointer; font-size: 14px; user-select: none;
}
.checkbox-item input[type="checkbox"] {
    width: 18px; height: 18px; cursor: pointer;
    accent-color: #6366f1;
}
.agree-row {
    margin-top: 16px; padding-top: 16px;
    border-top: 1px solid #2d2d5e;
}
.agree-row .checkbox-item { color: #94a3b8; font-size: 13px; }

/* 进度 */
.progress-bar {
    width: 100%; height: 8px;
    background: #0f3460; border-radius: 4px;
    overflow: hidden; margin-bottom: 16px;
}
.progress-fill {
    height: 100%; background: #6366f1;
    border-radius: 4px; transition: width 0.3s;
    width: 0%;
}
.status-text { font-size: 14px; color: #94a3b8; margin-bottom: 8px; }
.detail-text { font-size: 12px; color: #64748b; }

/* 完成页 */
.done-icon {
    width: 80px; height: 80px;
    background: #34d399; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 40px; margin: 0 auto 24px; color: #0f0f1a;
}
.install-path {
    background: #0f3460; padding: 12px 16px;
    border-radius: 8px; font-size: 13px;
    word-break: break-all; margin: 16px 0;
    color: #94a3b8;
}
.launch-check {
    display: flex; align-items: center; gap: 10px;
    justify-content: center; margin: 20px 0;
    font-size: 14px; cursor: pointer;
}
.launch-check input { width: 18px; height: 18px; accent-color: #34d399; }

/* 错误 */
.error-icon {
    width: 80px; height: 80px;
    background: #f87171; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 40px; margin: 0 auto 24px; color: white;
}
.error-msg {
    background: #1e1020; padding: 16px;
    border-radius: 8px; color: #f87171;
    font-size: 13px; line-height: 1.6;
    margin: 16px 0;
}
</style>
</head>
<body>

<div class="header">
    <div class="logo">H</div>
    <div>
        <div class="title">Hermes WebUI 安装向导</div>
    </div>
</div>

<div class="container">

<!-- ===== 欢迎页 ===== -->
<div id="page-welcome" class="page active">
    <div class="welcome-icon"><span>H</span></div>
    <h1>Hermes WebUI</h1>
    <div class="version">VERSION __VERSION__</div>
    <div class="desc">
        AI 智能助手桌面客户端<br>
        集成多模型对话、文件管理、数据分析等功能<br>
        点击下方按钮开始安装
    </div>
    <div class="btn-row">
        <button class="btn btn-primary btn-lg" onclick="showPage('options')">开始安装</button>
    </div>
    <div class="btn-row">
        <button class="btn btn-secondary" onclick="closeSetup()">退出</button>
    </div>
</div>

<!-- ===== 安装选项页 ===== -->
<div id="page-options" class="page">
    <h1 style="font-size:22px;margin-bottom:20px;">安装选项</h1>

    <div class="card">
        <h3>安装位置</h3>
        <div style="margin-bottom:10px;font-size:13px;color:#94a3b8;">推荐选择以下路径（无需管理员权限）：</div>
        <div style="display:flex;flex-direction:column;gap:6px;margin-bottom:12px;">
            <label class="checkbox-item" style="cursor:pointer;" onclick="setPath('__USERPROFILE__')">
                <input type="radio" name="preset-path" checked style="accent-color:#6366f1;">
                <span id="label-user">用户目录 (Hermes WebUI)</span>
            </label>
            <label class="checkbox-item" style="cursor:pointer;" onclick="setPath('__LOCALAPPDATA__')">
                <input type="radio" name="preset-path" style="accent-color:#6366f1;">
                <span id="label-local">AppData (Hermes WebUI)</span>
            </label>
            <label class="checkbox-item" style="cursor:pointer;" onclick="setPath('__DESKTOP__')">
                <input type="radio" name="preset-path" style="accent-color:#6366f1;">
                <span>桌面 (Hermes WebUI)</span>
            </label>
            <label class="checkbox-item" style="cursor:pointer;" onclick="setPath('__CUSTOM__')">
                <input type="radio" name="preset-path" style="accent-color:#6366f1;">
                <span>自定义路径</span>
            </label>
        </div>
        <div class="path-row">
            <input type="text" id="install-path" value="__DEFAULT_PATH__" style="flex:1;">
        </div>
        <div class="space-info" id="space-info">计算中...</div>
    </div>

    <div class="card">
        <h3>附加选项</h3>
        <div class="checkbox-group">
            <label class="checkbox-item">
                <input type="checkbox" id="opt-desktop" checked>
                <span>创建桌面快捷方式</span>
            </label>
            <label class="checkbox-item">
                <input type="checkbox" id="opt-startmenu" checked>
                <span>创建开始菜单快捷方式</span>
            </label>
            <label class="checkbox-item">
                <input type="checkbox" id="opt-autostart">
                <span>开机时自动启动</span>
            </label>
        </div>
        <div class="agree-row">
            <label class="checkbox-item">
                <input type="checkbox" id="opt-agree">
                <span>我已阅读并同意《Hermes WebUI 软件许可协议》</span>
            </label>
        </div>
    </div>

    <div class="btn-row">
        <button class="btn btn-secondary" onclick="showPage('welcome')">&lt; 返回</button>
        <button class="btn btn-primary" id="btn-install" onclick="startInstall()">立即安装 &gt;</button>
    </div>
</div>

<!-- ===== 安装进度页 ===== -->
<div id="page-progress" class="page">
    <h1 style="font-size:22px;margin-bottom:20px;">正在安装</h1>
    <div class="card">
        <div class="progress-bar">
            <div class="progress-fill" id="progress-fill"></div>
        </div>
        <div class="status-text" id="status-text">准备中...</div>
        <div class="detail-text" id="detail-text"></div>
    </div>
</div>

<!-- ===== 完成页 ===== -->
<div id="page-done" class="page">
    <div class="done-icon">&#10003;</div>
    <h1>安装完成</h1>
    <div class="version" style="margin-bottom:8px;">Hermes WebUI 已成功安装</div>
    <div style="text-align:center;color:#94a3b8;font-size:13px;">安装位置：</div>
    <div class="install-path" id="done-path"></div>
    <label class="launch-check">
        <input type="checkbox" id="opt-launch" checked>
        <span>立即启动 Hermes WebUI</span>
    </label>
    <div class="btn-row">
        <button class="btn btn-success btn-lg" onclick="finish()">完成</button>
    </div>
</div>

<!-- ===== 错误页 ===== -->
<div id="page-error" class="page">
    <div class="error-icon">!</div>
    <h1>安装失败</h1>
    <div class="error-msg" id="error-msg"></div>
    <div class="btn-row">
        <button class="btn btn-secondary" onclick="closeSetup()">关闭</button>
    </div>
</div>

</div>

<script>
function showPage(name) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.getElementById('page-' + name).classList.add('active');
    if (name === 'options') {
        document.getElementById('space-info').textContent = '正在计算...';
        fetch('/api/space?path=' + encodeURIComponent(document.getElementById('install-path').value))
            .then(r => r.json())
            .then(d => { document.getElementById('space-info').textContent = d.info; })
            .catch(() => {});
    }
}

function setPath(type) {
    const input = document.getElementById('install-path');
    if (type === '__CUSTOM__') {
        const p = prompt('请输入自定义安装路径：', input.value);
        if (p && p.trim()) { input.value = p.trim(); }
    } else {
        input.value = type;
    }
    updateSpace();
}
function updateSpace() {
    document.getElementById('space-info').textContent = '计算中...';
    fetch('/api/space?path=' + encodeURIComponent(document.getElementById('install-path').value))
        .then(r => r.json()).then(d => { document.getElementById('space-info').textContent = d.info; }).catch(() => {});
}

function startInstall() {
    const agree = document.getElementById('opt-agree').checked;
    if (!agree) {
        alert('请先同意许可协议');
        return;
    }
    const path = document.getElementById('install-path').value.trim();
    if (!path) {
        alert('请输入安装路径');
        return;
    }
    const opts = {
        install_dir: path,
        desktop: document.getElementById('opt-desktop').checked,
        startmenu: document.getElementById('opt-startmenu').checked,
        autostart: document.getElementById('opt-autostart').checked,
    };
    showPage('progress');
    fetch('/api/install', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(opts)
    }).then(r => r.json()).then(d => {
        if (d.error) {
            document.getElementById('error-msg').textContent = d.error;
            showPage('error');
        }
    }).catch(e => {
        document.getElementById('error-msg').textContent = '连接失败: ' + e.message;
        showPage('error');
    });

    // 轮询进度
    const timer = setInterval(() => {
        fetch('/api/status')
            .then(r => r.json())
            .then(d => {
                document.getElementById('progress-fill').style.width = d.progress + '%';
                document.getElementById('status-text').textContent = d.message;
                document.getElementById('detail-text').textContent = d.detail || '';
                if (d.status === 'done') {
                    clearInterval(timer);
                    document.getElementById('done-path').textContent = d.install_dir;
                    showPage('done');
                } else if (d.status === 'error') {
                    clearInterval(timer);
                    document.getElementById('error-msg').textContent = d.error;
                    showPage('error');
                }
            })
            .catch(() => {});
    }, 500);
}

function finish() {
    const launch = document.getElementById('opt-launch').checked;
    if (launch) {
        fetch('/api/launch', {method: 'POST'}).catch(() => {});
    }
    fetch('/api/close', {method: 'POST'}).catch(() => {});
    window.close();
    // 如果 window.close() 不生效（某些浏览器限制），显示提示
    setTimeout(() => {
        document.body.innerHTML = '<div style="text-align:center;padding:60px;color:#94a3b8;"><h2 style="margin-bottom:16px;">安装完成</h2><p>你可以关闭此窗口。</p></div>';
    }, 1000);
}

function closeSetup() {
    fetch('/api/close', {method: 'POST'}).catch(() => {});
    window.close();
    setTimeout(() => {
        document.body.innerHTML = '<div style="text-align:center;padding:60px;color:#94a3b8;"><h2>安装向导已退出</h2><p>你可以关闭此窗口。</p></div>';
    }, 1000);
}
</script>
</body>
</html>
"""

# ============================================================
# HTTP 服务
# ============================================================

class SetupHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # 静默日志

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            html = HTML_PAGE.replace("__VERSION__", APP_VERSION)
            html = html.replace("__DEFAULT_PATH__", DEFAULT_INSTALL_DIR)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

        elif self.path.startswith("/api/status"):
            self.send_json(200, install_state)

        elif self.path.startswith("/api/space"):
            from urllib.parse import urlparse, parse_qs
            qs = parse_qs(urlparse(self.path).query)
            path = qs.get("path", [DEFAULT_INSTALL_DIR])[0]
            info = self.get_space_info(path)
            self.send_json(200, {"info": info})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""

        if self.path == "/api/install":
            try:
                data = json.loads(body)
                threading.Thread(target=self.run_install, args=(data,), daemon=True).start()
                self.send_json(200, {"ok": True})
            except Exception as e:
                self.send_json(500, {"error": str(e)})

        elif self.path == "/api/launch":
            install_dir = install_state.get("install_dir", "")
            if install_dir:
                bat = os.path.join(install_dir, "启动 Hermes WebUI.bat")
                if os.path.isfile(bat):
                    subprocess.Popen(["cmd", "/c", "start", "", bat], shell=True, cwd=install_dir)
            self.send_json(200, {"ok": True})

        elif self.path == "/api/close":
            threading.Thread(target=self.shutdown_server, daemon=True).start()
            self.send_json(200, {"ok": True})

    def send_json(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def get_space_info(self, path):
        try:
            import ctypes
            drive = os.path.splitdrive(path)[0] + "\\"
            free = ctypes.c_ulonglong(0)
            ctypes.windll.kernel32.GetDiskFreeSpaceExW(drive, None, None, ctypes.pointer(free))
            free_gb = free.value / (1024**3)
            color = "green" if free_gb > 1 else "#f87171"
            return f"所需空间：约 250 MB | 可用空间：{free_gb:.1f} GB ({drive})"
        except:
            return ""

    def run_install(self, data):
        try:
            dest = data["install_dir"]
            install_state["install_dir"] = dest
            install_state["status"] = "installing"
            install_state["progress"] = 0

            def update(pct, msg="", detail=""):
                install_state["progress"] = pct
                install_state["message"] = msg
                install_state["detail"] = detail

            # 创建安装目录（权限检查）
            update(0, "检查安装目录...")
            # 先清理旧的安装目标（如果有）
            if os.path.exists(dest):
                try:
                    shutil.rmtree(dest, ignore_errors=True)
                    time.sleep(0.5)  # 等待文件系统释放
                except:
                    pass
            # 如果是C:\Program Files等系统目录，自动回退到用户目录
            try:
                os.makedirs(dest, exist_ok=True)
                # 测试写入权限
                test_file = os.path.join(dest, ".write_test")
                with open(test_file, "w") as tf:
                    tf.write("test")
                os.remove(test_file)
            except (PermissionError, OSError):
                fallback = os.path.expandvars(r"%USERPROFILE%\Hermes WebUI")
                install_state["install_dir"] = fallback
                dest = fallback
                data["install_dir"] = fallback
                # 清理回退目录
                if os.path.exists(dest):
                    shutil.rmtree(dest, ignore_errors=True)
                    time.sleep(0.5)
                os.makedirs(dest, exist_ok=True)

            total = len(SOURCE_DIRS) + len(SOURCE_FILES) + 7
            done = 0

            def step():
                nonlocal done
                done += 1
                update(done / total * 100)

            # 复制目录（跳过 .git 和 __pycache__）
            ignore = shutil.ignore_patterns('.git', '__pycache__', '*.pyc',
                                            'node_modules', '.DS_Store', 'Thumbs.db')
            for d in SOURCE_DIRS:
                src = os.path.join(SETUP_DIR, d)
                dst = os.path.join(dest, d)
                update(done / total * 100, f"复制 {d}/...")
                # 确保目标不存在
                if os.path.exists(dst):
                    try:
                        shutil.rmtree(dst)
                    except OSError:
                        time.sleep(1)
                        try:
                            shutil.rmtree(dst)
                        except OSError:
                            pass  # 某些文件被锁定，继续尝试
                # 如果目标仍然存在（有锁定文件），逐个复制
                if os.path.exists(dst):
                    self._copy_tree_merge(src, dst, ignore)
                else:
                    shutil.copytree(src, dst, ignore=ignore)
                step()

            # 复制文件
            for f in SOURCE_FILES:
                sf = os.path.join(SETUP_DIR, f)
                df = os.path.join(dest, f)
                if os.path.exists(df):
                    os.remove(df)
                shutil.copy2(sf, df)
                step()

            # 迁移用户数据（从用户目录 ~/.hermes 到安装目录）
            update(done / total * 100, "迁移用户数据...")
            self._migrate_user_hermes(dest)
            step()

            # 修复 venv pyvenv.cfg（重定位到目标机器的 Python）
            update(done / total * 100, "配置 Python 环境...")
            venv_dir = os.path.join(dest, "hermes-agent", ".venv")
            pyvenv_cfg = os.path.join(venv_dir, "pyvenv.cfg")
            if os.path.exists(pyvenv_cfg):
                # 找目标机器的 Python 3.10+
                import shutil as _shutil
                py_exe = _shutil.which("python") or _shutil.which("python3")
                if py_exe:
                    # 规范化为绝对路径
                    import subprocess as _sp
                    try:
                        r = _sp.run([py_exe, "-c", "import sys; print(sys.executable)"],
                                    capture_output=True, text=True, timeout=10)
                        if r.returncode == 0:
                            py_exe = r.stdout.strip()
                    except Exception:
                        pass
                    py_home = os.path.dirname(py_exe)
                    py_ver = ""
                    try:
                        r2 = _sp.run([py_exe, "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"],
                                     capture_output=True, text=True, timeout=10)
                        if r2.returncode == 0:
                            py_ver = r2.stdout.strip()
                    except Exception:
                        pass
                    cfg_content = (
                        f"home = {py_home}\n"
                        f"include-system-site-packages = false\n"
                        f"version = {py_ver}\n"
                        f"executable = {py_exe}\n"
                    )
                    with open(pyvenv_cfg, "w", encoding="utf-8") as f:
                        f.write(cfg_content)

            # 创建启动脚本
            update(done / total * 100, "创建启动脚本...")
            bat = os.path.join(dest, "启动 Hermes WebUI.bat")
            vp = os.path.join(dest, "hermes-agent", ".venv", "Scripts", "python.exe")
            with open(bat, "w", encoding="utf-8") as f:
                f.write(f'@echo off\nchcp 65001 >nul 2>&1\ntitle Hermes WebUI\ncd /d "%~dp0"\necho.\necho  正在启动 Hermes WebUI...\necho.\n"{vp}" "%~dp0hermes_desktop.py"\npause\n')
            step()

            # 最小化脚本
            mb = os.path.join(dest, "启动_最小化.bat")
            with open(mb, "w", encoding="utf-8") as f:
                f.write('@echo off\r\ncd /d "%~dp0"\r\nstart /min cmd /c "启动 Hermes WebUI.bat"\r\n')
            step()

            # 配置文件
            update(done / total * 100, "创建配置文件...")
            settings = {
                "port": 8787, "window_width": 1280, "window_height": 800,
                "window_min_width": 900, "window_min_height": 600,
                "window_x": None, "window_y": None, "cache_dir": "",
                "auto_start": data.get("autostart", False),
                "minimize_to_tray": True, "start_minimized": False,
            }
            with open(os.path.join(dest, "settings.json"), "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)
            step()

            # 快捷方式
            if data.get("desktop"):
                update(done / total * 100, "创建桌面快捷方式...")
                self.create_shortcut(bat, "Hermes WebUI", os.path.join(dest, "hermes-icon.ico"), "desktop")
            step()

            if data.get("startmenu"):
                update(done / total * 100, "创建开始菜单快捷方式...")
                sm = os.path.expandvars(r"%AppData%\Microsoft\Windows\Start Menu\Programs")
                os.makedirs(sm, exist_ok=True)
                self.create_shortcut(bat, "Hermes WebUI", os.path.join(dest, "hermes-icon.ico"), "startmenu",
                                     os.path.join(sm, "Hermes WebUI"))
            step()

            # 自启动
            if data.get("autostart"):
                update(done / total * 100, "注册开机自启动...")
                self.register_autostart(mb)
            step()

            # 卸载信息
            update(done / total * 100, "注册卸载信息...")
            self.register_uninstall(dest)
            step()

            # 卸载程序
            update(done / total * 100, "创建卸载程序...")
            self.create_uninstaller(dest)
            step()

            update(100, "安装完成！")
            install_state["status"] = "done"

        except Exception as e:
            install_state["status"] = "error"
            install_state["error"] = str(e)

    def create_shortcut(self, target, name, icon, stype, target_dir=None):
        try:
            import win32com.client
            shell = win32com.client.Dispatch("WScript.Shell")
            if target_dir is None:
                if stype == "desktop":
                    target_dir = os.path.join(os.path.expandvars(r"%USERPROFILE%"), "Desktop")
                else:
                    target_dir = os.path.expandvars(r"%AppData%\Microsoft\Windows\Start Menu\Programs")
            os.makedirs(target_dir, exist_ok=True)
            lnk = os.path.join(target_dir, f"{name}.lnk")
            sc = shell.CreateShortCut(lnk)
            sc.Targetpath = target
            sc.WorkingDirectory = os.path.dirname(target)
            sc.Description = f"{APP_NAME} - AI 智能助手"
            if icon and os.path.isfile(icon):
                sc.IconLocation = f"{icon},0"
            sc.save()
        except ImportError:
            pass

    def register_autostart(self, bat):
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows\CurrentVersion\Run",
                                0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, "HermesWebUI", 0, winreg.REG_SZ, f'"{bat}"')
        except:
            pass

    def register_uninstall(self, install_dir):
        try:
            import winreg
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as key:
                winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, APP_NAME)
                winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, APP_VERSION)
                winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, "Hermes Agent Team")
                winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ,
                                  f'"{os.path.join(install_dir, "卸载 Hermes WebUI.bat")}"')
                winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, install_dir)
                winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ,
                                  os.path.join(install_dir, "hermes-icon.ico"))
                winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
                winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)
        except:
            pass

    def create_uninstaller(self, install_dir):
        u = os.path.join(install_dir, "卸载 Hermes WebUI.bat")
        c = "@echo off\r\nchcp 65001 >nul 2>&1\r\ntitle Hermes WebUI - 卸载\r\necho.\r\necho  确定要卸载 Hermes WebUI 吗？\r\nset /p c=输入 Y 确认：\r\nif /i not \"%c%\"==\"Y\" (exit /b)\r\n"
        c += 'reg delete "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run" /v "HermesWebUI" /f >nul 2>&1\r\n'
        reg = UNINSTALL_KEY.replace(r"Software\Microsoft\Windows\CurrentVersion\Uninstall\\", "")
        c += f'reg delete "HKCU\\{reg}" /f >nul 2>&1\r\n'
        c += f'rd /s /q "{install_dir}"\r\necho 卸载完成\r\npause\r\n'
        with open(u, "w", encoding="utf-8") as f:
            f.write(c)

    def _migrate_user_hermes(self, install_dir):
        """从用户目录 ~/.hermes 迁移用户数据到安装目录"""
        user_hermes = os.path.join(os.path.expanduser("~"), ".hermes")
        target_hermes = os.path.join(install_dir, ".hermes")

        # 检查用户目录是否存在
        if not os.path.isdir(user_hermes):
            return
        # 检查是否有实质内容
        has_content = any(
            os.path.exists(os.path.join(user_hermes, i))
            for i in [".env", "config.yaml", "sessions", "memories", "kanban.db"]
        )
        if not has_content:
            return

        os.makedirs(target_hermes, exist_ok=True)
        migrated_count = 0

        # --- 1. 智能合并 .env（用户数据优先，追加安装包没有的 key） ---
        src_env = os.path.join(user_hermes, ".env")
        dst_env = os.path.join(target_hermes, ".env")
        if os.path.isfile(src_env):
            user_keys = {}
            for line in open(src_env, "r", encoding="utf-8"):
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    user_keys[k] = v
            # 读取安装包 .env 中的额外 key
            if os.path.isfile(dst_env):
                for line in open(dst_env, "r", encoding="utf-8"):
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        k, v = line.split("=", 1)
                        if k not in user_keys:
                            user_keys[k] = v
            # 写入合并结果（用户 key 在前）
            with open(dst_env, "w", encoding="utf-8") as f:
                for k, v in user_keys.items():
                    f.write(f"{k}={v}\n")
            migrated_count += 1

        # --- 2. 智能合并 config.yaml（用用户配置覆盖安装包配置）---
        src_cfg = os.path.join(user_hermes, "config.yaml")
        dst_cfg = os.path.join(target_hermes, "config.yaml")
        if os.path.isfile(src_cfg):
            shutil.copy2(src_cfg, dst_cfg)
            migrated_count += 1

        # --- 3. 直接覆盖的文件（用户数据优先） ---
        for fname in ["auth.json", "SOUL.md", "kanban.db"]:
            src = os.path.join(user_hermes, fname)
            dst = os.path.join(target_hermes, fname)
            if os.path.isfile(src):
                try:
                    shutil.copy2(src, dst)
                    migrated_count += 1
                except OSError:
                    pass

        # --- 4. 合并目录（不覆盖已有文件） ---
        for dname in ["sessions", "memories", "skills", "cron"]:
            src = os.path.join(user_hermes, dname)
            dst = os.path.join(target_hermes, dname)
            if not os.path.isdir(src):
                continue
            os.makedirs(dst, exist_ok=True)
            for item in os.listdir(src):
                s = os.path.join(src, item)
                d = os.path.join(dst, item)
                if not os.path.exists(d):
                    try:
                        if os.path.isdir(s):
                            shutil.copytree(s, d,
                                ignore=shutil.ignore_patterns('*.pyc', '__pycache__'))
                        else:
                            shutil.copy2(s, d)
                        migrated_count += 1
                    except OSError:
                        pass

        if migrated_count > 0:
            install_state["detail"] = f"已迁移 {migrated_count} 项用户数据"

    def _copy_tree_merge(self, src, dst, ignore=None):
        """递归合并复制目录（目标已存在时逐文件覆盖）"""
        names = os.listdir(src)
        if ignore:
            excluded = ignore(src, names)
            names = [n for n in names if n not in excluded]
        for name in names:
            s = os.path.join(src, name)
            d = os.path.join(dst, name)
            try:
                if os.path.isdir(s):
                    if not os.path.exists(d):
                        os.makedirs(d, exist_ok=True)
                    self._copy_tree_merge(s, d, ignore)
                else:
                    os.makedirs(os.path.dirname(d), exist_ok=True)
                    if os.path.exists(d):
                        os.remove(d)
                    shutil.copy2(s, d)
            except OSError:
                pass

    def shutdown_server(self):
        time.sleep(1)
        threading.Thread(target=os.kill, args=(os.getpid(), signal.SIGTERM), daemon=True).start()


# ============================================================
# 主入口
# ============================================================

def main():
    # 验证源文件
    missing = [d for d in SOURCE_DIRS if not os.path.isdir(os.path.join(SETUP_DIR, d))]
    missing += [f for f in SOURCE_FILES if not os.path.isfile(os.path.join(SETUP_DIR, f))]
    if missing:
        print(f"安装包不完整，缺少: {missing}")
        input("按回车退出...")
        return

    # 启动HTTP服务
    port = 18392  # 随机高端口
    server = HTTPServer(("127.0.0.1", port), SetupHandler)
    url = f"http://127.0.0.1:{port}"

    print(f"安装向导已启动: {url}")

    # 自动打开浏览器
    webbrowser.open(url)

    # 运行服务（阻塞）
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()


if __name__ == "__main__":
    main()
