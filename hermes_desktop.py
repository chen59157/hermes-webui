"""
Hermes WebUI - Windows/Mac 桌面客户端
====================================
版本: 3.2.0
功能:
  - 自动查找并使用正确的 Python 环境
  - 自定义缓存/数据存储位置
  - 开机自启动管理
  - 崩溃自动恢复（3次/5分钟内限制）
  - 窗口状态记忆
  - 系统托盘常驻
  - 优雅退出
"""

import os
import sys
import subprocess
import time
import json
import atexit
import threading
import shutil
import ctypes
import ctypes.wintypes
import urllib.request
import logging
from logging.handlers import RotatingFileHandler

try:
    import webview
except ImportError:
    print("[Hermes] ERROR: pywebview not installed. Run: pip install pywebview")
    sys.exit(1)

try:
    import winreg
except ImportError:
    winreg = None

try:
    from infi.systray import SysTrayIcon
    HAS_SYSTRAY = True
except ImportError:
    HAS_SYSTRAY = False
    log_warning_systray = True


# ============================================================
# Subprocess Monkey-Patch：消除 Windows 黑窗口
# ============================================================

# 使用共享模块 no_console_patch.py（与 server.py 共用同一份逻辑）
# 先确保 hermes-webui-cn 目录在 sys.path 中
_server_dir = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "hermes-webui-cn"
)
if _server_dir not in sys.path:
    sys.path.insert(0, _server_dir)

try:
    from no_console_patch import apply_patch as patch_subprocess_create_no_window
except ImportError:
    # 兜底：如果共享模块不存在，用简化版内联 patch
    def patch_subprocess_create_no_window():
        if sys.platform != "win32":
            return
        CREATE_NO_WINDOW = 0x08000000
        _orig_Popen = subprocess.Popen
        def _p(*args, **kwargs):
            kwargs["creationflags"] = (kwargs.get("creationflags", 0) or 0) | CREATE_NO_WINDOW
            return _orig_Popen(*args, **kwargs)
        subprocess.Popen = _p


# ============================================================
# 路径配置
# ============================================================

if getattr(sys, "frozen", False):
    EXE_DIR = os.path.dirname(sys.executable)
    if os.path.basename(EXE_DIR).lower().startswith("hermes"):
        APP_DIR = os.path.dirname(EXE_DIR)
    else:
        APP_DIR = EXE_DIR
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

SERVER_DIR = os.path.join(APP_DIR, "hermes-webui-cn")
HERMES_PORT = 8787
SETTINGS_FILE = os.path.join(APP_DIR, "settings.json")
LOG_FILE = os.path.join(APP_DIR, "logs", "hermes.log")
ICON_FILE = os.path.join(APP_DIR, "hermes-icon.ico")

server_process = None
_warden_process = None
window = None
health_check_running = False
restart_count = 0
restart_times = []
_window_created_at = 0  # 窗口创建时间戳，用于启动保护期
server_lock = threading.RLock()        # 保护 server_process 操作的锁（可重入，防死锁）


# ============================================================
# 配置常量
# ============================================================

# 启动和保护期
STARTUP_PROTECTION_SECONDS = 3.0
STARTUP_TIMEOUT = 30

# 崩溃恢复
CRASH_WINDOW_SECONDS = 300  # 5分钟
MAX_RESTARTS = 3

# 健康检查
HEALTH_CHECK_INTERVAL_SSE = 2
HEALTH_CHECK_INTERVAL_HTTP = 10
HEALTH_CHECK_TIMEOUT = 3
HEALTH_CHECK_RETRIES = 3

# 进程管理
PROCESS_TERMINATE_TIMEOUT = 5
SERVER_TERMINATE_TIMEOUT = 8
WMIC_TIMEOUT = 5

# 日志配置
LOG_MAX_SIZE_MB = 10
LOG_BACKUP_COUNT = 3

# 端口检测
PORT_CHECK_TIMEOUT = 1
PORT_RANGE_START = HERMES_PORT
PORT_RANGE_END = HERMES_PORT + 20


# ============================================================
# Python 路径缓存
# ============================================================

_python_path_cache = None
_python_path_cache_lock = threading.Lock()


def find_python_cached():
    """带缓存的 Python 查找，避免重复查找"""
    global _python_path_cache

    # 快速路径：如果缓存已存在，直接返回
    if _python_path_cache is not None:
        return _python_path_cache

    # 慢路径：获取锁并查找
    with _python_path_cache_lock:
        # 双重检查锁模式
        if _python_path_cache is not None:
            return _python_path_cache

        result = find_python()
        _python_path_cache = result
        return result


def _force_window_visible():
    """强制显示窗口：pywebview EdgeChromium 有时窗口创建后未实际显示"""
    import ctypes
    from ctypes import wintypes
    try:
        hwnd = ctypes.windll.user32.FindWindowW(None, "Hermes Agent")
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 5)  # SW_SHOW
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            log("_force_window_visible: ShowWindow SW_SHOW 已调用")
        else:
            log("_force_window_visible: 未找到窗口句柄，延迟重试")
            time.sleep(0.5)
            hwnd = ctypes.windll.user32.FindWindowW(None, "Hermes Agent")
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 5)
                ctypes.windll.user32.SetForegroundWindow(hwnd)
    except Exception as e:
        log(f"_force_window_visible: 异常 {e}")
_global_mutex = None                  # 单实例互斥体（模块级变量，防 GC）
_server_log_handler = None            # 服务日志 handler（替代手动 open）


# ============================================================
# 日志系统
# ============================================================

# 配置日志
_logger = logging.getLogger("Hermes")
_logger.setLevel(logging.DEBUG)

# 控制台处理器
_console_handler = logging.StreamHandler()
_console_handler.setLevel(logging.INFO)
_console_format = logging.Formatter('[%(asctime)s] [Hermes] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
_console_handler.setFormatter(_console_format)
_logger.addHandler(_console_handler)

# 文件处理器（RotatingFileHandler）
try:
    # 确保日志目录存在
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    _file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=LOG_MAX_SIZE_MB * 1024 * 1024,  # 10MB
        backupCount=LOG_BACKUP_COUNT,
        encoding='utf-8'
    )
    _file_handler.setLevel(logging.DEBUG)
    _file_format = logging.Formatter('[%(asctime)s] [Hermes] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    _file_handler.setFormatter(_file_format)
    _logger.addHandler(_file_handler)
except Exception:
    pass  # 日志目录无写入权限时静默跳过

_log_lock = threading.Lock()


def log(msg):
    """记录日志（使用 logging 模块）"""
    with _log_lock:
        try:
            _logger.info(msg)
        except Exception:
            pass  # pythonw.exe 下可能出错


def log_error(msg):
    """记录错误日志"""
    with _log_lock:
        try:
            _logger.error(msg)
        except Exception:
            pass


def log_warning(msg):
    """记录警告日志"""
    with _log_lock:
        try:
            _logger.warning(msg)
        except Exception:
            pass


# ============================================================
# 设置管理
# ============================================================

DEFAULT_SETTINGS = {
    "port": HERMES_PORT,
    "window_width": 1280,
    "window_height": 800,
    "window_min_width": 900,
    "window_min_height": 600,
    "window_x": None,
    "window_y": None,
    "cache_dir": "",
    "auto_start": False,
    "minimize_to_tray": True,
    "start_minimized": False,
}

_settings_cache = {}

def get_settings():
    global _settings_cache
    if _settings_cache:
        return _settings_cache
    settings = dict(DEFAULT_SETTINGS)
    if os.path.isfile(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                settings.update(saved)
        except Exception:
            pass
    _settings_cache = settings
    return settings


def save_settings(settings):
    global _settings_cache
    _settings_cache = settings
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log(f"保存设置失败: {e}")


def set_setting(key, value):
    s = get_settings()
    s[key] = value
    save_settings(s)
    return s


# ============================================================
# 缓存目录管理
# ============================================================

def setup_cache_dir():
    """设置自定义缓存目录，迁移现有数据"""
    settings = get_settings()
    cache_dir = settings.get("cache_dir", "").strip()

    if not cache_dir:
        # 默认使用用户目录下的 .hermes（与 Hermes Agent 共享数据）
        user_home = os.path.expanduser("~")
        cache_dir = os.path.join(user_home, ".hermes")

    # 确保目录存在
    os.makedirs(cache_dir, exist_ok=True)
    os.makedirs(os.path.join(cache_dir, "logs"), exist_ok=True)
    os.makedirs(os.path.join(cache_dir, "sessions"), exist_ok=True)

    # 检查是否需要迁移数据（仅当用户自定义了目录时）
    default_cache = os.path.join(os.path.expanduser("~"), ".hermes")
    if cache_dir != default_cache and os.path.isdir(default_cache):
        if not os.path.isfile(os.path.join(cache_dir, ".migrated")):
            log(f"迁移缓存数据: {default_cache} -> {cache_dir}")
            try:
                for item in os.listdir(default_cache):
                    src = os.path.join(default_cache, item)
                    dst = os.path.join(cache_dir, item)
                    if not os.path.exists(dst):
                        if os.path.isdir(src):
                            shutil.copytree(src, dst)
                        else:
                            shutil.copy2(src, dst)
                with open(os.path.join(cache_dir, ".migrated"), "w") as f:
                    f.write(time.strftime("%Y-%m-%d %H:%M:%S"))
                log("缓存数据迁移完成")
            except Exception as e:
                log(f"缓存迁移失败: {e}")

    return cache_dir


# ============================================================
# Python 查找
# ============================================================

def find_python():
    """按优先级查找可用的 Python 3.10+，优先 pythonw.exe（无窗口）"""
    # 1. hermes-agent 自带 venv 中的 pythonw.exe（优先，无控制台窗口）
    for venv_name in ["hermes-agent"]:
        venv_pythonw = os.path.join(APP_DIR, venv_name, ".venv", "Scripts", "pythonw.exe")
        if os.path.isfile(venv_pythonw):
            log(f"找到 Python (venv pythonw): {venv_pythonw}")
            return venv_pythonw
        venv_py = os.path.join(APP_DIR, venv_name, ".venv", "Scripts", "python.exe")
        if os.path.isfile(venv_py):
            log(f"找到 Python (venv): {venv_py}")
            return venv_py

    # 2. 打包时自带的 python
    bundled = os.path.join(APP_DIR, "_internal", "python.exe")
    if os.path.isfile(bundled):
        log(f"找到 Python (bundled): {bundled}")
        return bundled

    # 3. 系统 PATH 搜索（隐藏窗口）— 仅当 venv 不可用时才走
    _no_win = dict(creationflags=0x08000000) if sys.platform == "win32" else {}
    try:
        result = subprocess.run(
            ["where", "python"],
            capture_output=True, text=True, timeout=5, shell=True, **_no_win
        )
        if result.returncode == 0:
            for line in result.stdout.strip().splitlines():
                p = line.strip()
                if os.path.isfile(p):
                    log(f"找到 Python (PATH): {p}")
                    return p
    except Exception:
        pass

    # 4. 常见安装路径
    common_paths = [
        os.path.expandvars(r"%LocalAppData%\Programs\Python\Python312\python.exe"),
        os.path.expandvars(r"%LocalAppData%\Programs\Python\Python311\python.exe"),
        os.path.expandvars(r"%LocalAppData%\Programs\Python\Python310\python.exe"),
        r"C:\Python312\python.exe",
        r"C:\Python311\python.exe",
    ]
    for p in common_paths:
        if os.path.isfile(p):
            log(f"找到 Python (common): {p}")
            return p

    return None


# ============================================================
# 端口与网络工具
# ============================================================

def is_port_in_use(port):
    """检查端口是否被占用，返回占用进程PID或0"""
    try:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex(("127.0.0.1", port))
            if result != 0:
                return 0
        # 端口被占用，尝试获取PID
        _no_win = dict(creationflags=0x08000000) if sys.platform == "win32" else {}
        res = subprocess.run(
            f'netstat -ano | findstr ":{port} " | findstr LISTENING',
            shell=True, capture_output=True, text=True, timeout=5, **_no_win
        )
        for line in res.stdout.strip().splitlines():
            parts = line.strip().split()
            if len(parts) >= 5:
                return int(parts[-1])
    except Exception:
        pass
    return 0


def find_free_port(start=8787, max_tries=20):
    """查找可用端口"""
    for offset in range(max_tries):
        port = start + offset
        if not is_port_in_use(port):
            return port
    return start


def check_server_ready(port, timeout=STARTUP_TIMEOUT):
    """等待服务就绪（默认30秒超时）"""
    url = f"http://127.0.0.1:{port}/api/settings"
    for i in range(timeout):
        try:
            with urllib.request.urlopen(url, timeout=HEALTH_CHECK_TIMEOUT) as resp:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def _sse_health_check(port):
    """SSE 心跳检测：连接 /api/health/stream 并在 5 秒内等待 heartbeat。

    Returns:
        True  — 收到 heartbeat，后端存活
        False — 连接失败或超时，后端异常
        None  — SSE 端点不可用（404/非 SSE 响应），需降级 HTTP 轮询
    """
    url = f"http://127.0.0.1:{port}/api/health/stream"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.getcode() != 200:
                return None
            ct = resp.headers.get("Content-Type", "")
            if "text/event-stream" not in ct:
                return None
            # 只读取第一个 SSE 消息（~18字节），不阻塞等待大块数据
            chunk = resp.readline()
            while chunk and not chunk.startswith(b"data:"):
                chunk = resp.readline()
            if chunk and b"heartbeat" in chunk:
                return True
            # 继续读最多 2 条，以防第一条不是 heartbeat
            for _ in range(2):
                chunk = resp.readline()
                if chunk and b"heartbeat" in chunk:
                    return True
            return False
    except urllib.error.HTTPError as e:
        if e.code in (404, 405):
            return None
        return False
    except Exception:
        return False


# ============================================================
# 服务器进程管理
# ============================================================

def start_server(python_exe, port, wait=True):
    """启动 Hermes 后端服务。

    Args:
        python_exe: Python 解释器路径
        port: 监听端口
        wait: True 时阻塞等待后端就绪（默认向后兼容）；
              False 时启动子进程后立即返回（用于并行启动）
    """
    global server_process, restart_count, restart_times

    with server_lock:
        server_script = os.path.join(SERVER_DIR, "server.py")
        if not os.path.isfile(server_script):
            log(f"错误: 找不到服务脚本 {server_script}")
            return False

        # 检查是否已有服务在运行
        existing = is_port_in_use(port)
        if existing:
            url = f"http://127.0.0.1:{port}/api/settings"
            try:
                with urllib.request.urlopen(url, timeout=3) as resp:
                    log(f"检测到已运行的 Hermes 服务 (端口 {port})")
                    return True
            except Exception:
                log(f"端口 {port} 被占用但服务不可用，关闭旧进程...")
                try:
                    _no_win = dict(creationflags=0x08000000) if sys.platform == "win32" else {}
                    subprocess.run(
                        ["taskkill", "/F", "/PID", str(existing)],
                        capture_output=True, timeout=5, **_no_win
                    )
                except Exception:
                    pass
                time.sleep(2)

        # 设置环境变量
        settings = get_settings()
        cache_dir = setup_cache_dir()
        env = os.environ.copy()
        env["HERMES_HOME"] = cache_dir
        env["HERMES_PORT"] = str(port)
        env["HERMES_SUBPROCESS_NO_WINDOW"] = "1"  # 信号传递给 agent 子进程

        # 清除 PYTHONPATH 避免第三方软件（如 WPS）的 Python 环境污染模块导入
        env.pop("PYTHONPATH", None)

        # 确保 .hermes 目录存在
        hermes_home = os.path.join(APP_DIR, ".hermes")
        os.makedirs(hermes_home, exist_ok=True)

        # 确保 .env 存在
        env_file = os.path.join(hermes_home, ".env")
        if not os.path.isfile(env_file):
            # 尝试从源项目复制
            src_env = os.path.join(APP_DIR, ".hermes", ".env")
            if not os.path.isfile(src_env):
                src_env = os.path.join(APP_DIR, "hermes-webui-cn", ".env")
            if os.path.isfile(src_env):
                shutil.copy2(src_env, env_file)

        log(f"启动 Hermes Agent 服务 (端口 {port})...")
        log(f"Python: {python_exe}")
        log(f"工作目录: {SERVER_DIR}")

        log_path = os.path.join(cache_dir, "logs", "server.log")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)

        try:
            import logging
            from logging.handlers import RotatingFileHandler
            global _server_log_handler
            # 关闭旧的 handler（如果有）
            if _server_log_handler:
                try:
                    _server_log_handler.close()
                except Exception:
                    pass
            # 使用 RotatingFileHandler 管理日志文件句柄
            _server_log_handler = RotatingFileHandler(
                log_path, maxBytes=10*1024*1024, backupCount=3, encoding="utf-8"
            )
            server_process = subprocess.Popen(
                [python_exe, server_script],
                cwd=SERVER_DIR,
                stdout=_server_log_handler.stream,
                stderr=subprocess.STDOUT,
                env=env,
                creationflags=0x08000000,
            )
        except Exception as e:
            log(f"启动服务失败: {e}")
            return False

        log(f"后端进程 PID: {server_process.pid}")

        if wait:
            if check_server_ready(port):
                log("Hermes Agent 服务已就绪")
                # 启动健康检查线程
                start_health_check(port)
                return True
            else:
                log("等待服务超时，请查看日志获取详情")
                return False
        else:
            # 不等待，立即返回
            log("后端进程已启动（异步模式）")
            return True


def stop_server():
    """停止后端服务"""
    global server_process
    with server_lock:
        if server_process and server_process.poll() is None:
            log("正在停止后端服务...")
            try:
                server_process.terminate()
                server_process.wait(timeout=SERVER_TERMINATE_TIMEOUT)
            except subprocess.TimeoutExpired:
                log("进程未响应 SIGTERM，强制终止...")
                server_process.kill()
            except Exception:
                server_process.kill()
            log("后端服务已停止")
        server_process = None


# ============================================================
# 崩溃恢复与健康检查
# ============================================================

def can_restart():
    """检查是否允许自动重启（5分钟内最多3次）"""
    global restart_times
    now = time.time()
    # 清理超过5分钟的记录
    restart_times = [t for t in restart_times if now - t < CRASH_WINDOW_SECONDS]
    return len(restart_times) < MAX_RESTARTS


def do_restart(port):
    """执行重启"""
    global server_process, restart_count, restart_times
    with server_lock:
        restart_times.append(time.time())
        restart_count += 1
        log(f"自动重启后端服务 (第 {len(restart_times)} 次/5分钟)")
        if server_process:
            try:
                server_process.kill()
            except Exception:
                pass
            server_process = None
        time.sleep(2)
        python_exe = find_python_cached()
        if python_exe:
            return start_server(python_exe, port)
        return False


def start_warden():
    """启动 HermesWarden 任务守护进程（后台静默运行）。

    如果 hermes-warden 目录存在且未被禁用，则在独立进程中启动 warden_daemon.py。
    失败不影响主程序运行。
    """
    global _warden_process
    try:
        warden_dir = os.path.join(APP_DIR, "hermes-warden")
        warden_script = os.path.join(warden_dir, "warden_daemon.py")
        if not os.path.isfile(warden_script):
            return

        # 检查设置中是否禁用 Warden
        settings = get_settings()
        if not settings.get("warden_enabled", True):
            log("HermesWarden 已禁用（设置中 warden_enabled=false）")
            return

        # 设置 WARDEN_HOME 环境变量
        env = os.environ.copy()
        env["WARDEN_HOME"] = warden_dir

        python_exe = find_python_cached()
        if not python_exe:
            log("HermesWarden: 未找到 Python，跳过启动")
            return

        _no_win = dict(creationflags=0x08000000) if sys.platform == "win32" else {}
        _warden_process = subprocess.Popen(
            [python_exe, warden_script],
            cwd=warden_dir,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            **_no_win
        )
        log(f"HermesWarden 守护进程已启动 (PID: {_warden_process.pid})")
    except Exception as e:
        log(f"HermesWarden 启动失败（不影响主程序）: {e}")


def start_health_check(port):
    """启动健康检查线程（SSE 优先，自动降级 HTTP 轮询）。

    SSE 模式下检测延迟约 2~5 秒；若 SSE 端点不可用则自动降级为
    10 秒 HTTP 轮询，兼容旧版后端。
    """
    global health_check_running
    if health_check_running:
        return
    health_check_running = True

    # per-thread state; True = SSE, False = HTTP polling fallback
    _sse_mode = True

    def _check_loop():
        nonlocal _sse_mode
        consecutive_failures = 0
        while health_check_running:
            if _sse_mode:
                result = _sse_health_check(port)
                if result is True:
                    consecutive_failures = 0
                    continue  # heartbeat OK, immediately loop again (~2–3 s cycle)
                elif result is None:
                    # SSE endpoint not available — verify backend is actually up via HTTP
                    try:
                        urllib.request.urlopen(
                            f"http://127.0.0.1:{port}/api/settings", timeout=3
                        )
                        # HTTP works but SSE doesn't → old backend, permanent fallback
                        _sse_mode = False
                        consecutive_failures = 0
                        log("SSE 端点不可用，降级为 HTTP 轮询模式")
                        time.sleep(10)
                    except Exception:
                        # Both SSE and HTTP failed → backend is down
                        consecutive_failures += 1
                        time.sleep(2)
                else:
                    # result is False — SSE connection failed, backend likely down
                    consecutive_failures += 1
                    time.sleep(2)
            else:
                # HTTP polling fallback (original behavior: 10 s interval)
                time.sleep(10)
                try:
                    urllib.request.urlopen(
                        f"http://127.0.0.1:{port}/api/settings", timeout=3
                    )
                    consecutive_failures = 0
                except Exception:
                    consecutive_failures += 1

            if consecutive_failures >= 3 and can_restart():
                log(f"后端无响应 ({consecutive_failures} 次失败)，尝试恢复...")
                try:
                    if window:
                        window.evaluate_js(
                            "// 使用 HermesToast 组件（如果已加载）"
                            "if(window.HermesToast){"
                            "HermesToast.warning('后端服务恢复中，请稍候...', {duration: 8000});"
                            "}else{"
                            "// 降级到内联样式"
                            "var t=document.getElementById('hermes-offline-toast');"
                            "if(!t){"
                            "t=document.createElement('div');"
                            "t.id='hermes-offline-toast';"
                            "t.style.cssText='position:fixed;top:20px;left:50%;"
                            "transform:translateX(-50%);background:#f59e0b;color:#000;"
                            "padding:12px 24px;border-radius:8px;z-index:99999;"
                            "font-size:14px;box-shadow:0 4px 12px rgba(0,0,0,0.3)';"
                            "t.textContent='后端服务恢复中，请稍候...';"
                            "document.body.appendChild(t);}"
                            "t.style.display='block';"
                            "setTimeout(function(){var e=document.getElementById('hermes-offline-toast');"
                            "if(e)e.style.display='none';},8000);"
                            "}"
                        )
                except Exception:
                    pass
                do_restart(port)
                # After restart, retry SSE first
                _sse_mode = True
                consecutive_failures = 0

    t = threading.Thread(target=_check_loop, daemon=True)
    t.start()


# ============================================================
# 系统托盘（使用 infi.systray，更可靠）
# ============================================================

systray_icon = None  # type: SysTrayIcon | None


def _tray_open(systray):
    """托盘菜单 - 打开窗口"""
    _restore_window()


def _tray_restart(systray):
    """托盘菜单 - 重启后端"""
    settings = get_settings()
    port = settings.get("port", HERMES_PORT)
    python_exe = find_python_cached()
    if python_exe:
        stop_server()
        time.sleep(1)
        start_server(python_exe, port)


def _tray_quit(systray):
    """托盘菜单 - 退出"""
    shutdown_app()


def _restore_window():
    """从托盘恢复窗口"""
    global window
    try:
        if window is not None:
            try:
                window.show()
                window.restore()
                # 恢复窗口位置
                settings = get_settings()
                wx = settings.get("window_x")
                wy = settings.get("window_y")
                if wx is not None and wy is not None:
                    try:
                        window.move(wx, wy)
                    except Exception:
                        pass
                log("窗口已从托盘恢复")
                # 恢复后重新设置图标
                try:
                    _set_window_icon()
                except Exception:
                    pass
                return
            except Exception as e:
                log(f"窗口 show/restore 失败，需要重新创建: {e}")

        # 窗口对象失效，通过打开浏览器访问后端
        settings = get_settings()
        port = settings.get("port", HERMES_PORT)
        url = f"http://127.0.0.1:{port}"
        log(f"窗口对象不可用，在浏览器中打开: {url}")
        import webbrowser
        webbrowser.open(url)
    except Exception as e:
        log(f"恢复窗口失败: {e}")


def _set_window_icon():
    """设置窗口标题栏和任务栏图标。
    pywebview 6.x EdgeChromium 后端使用 WinForms Form，
    通过 Win32 API 设置图标最可靠（不依赖 pythonnet/clr）。"""
    if not os.path.isfile(ICON_FILE):
        log("图标文件不存在，跳过设置窗口图标")
        return

    # 获取窗口句柄
    hwnd = None
    if window and hasattr(window, 'native') and window.native is not None:
        try:
            hwnd = int(window.native.Handle)
        except Exception:
            pass
    if not hwnd:
        hwnd = ctypes.windll.user32.FindWindowW(None, "Hermes Agent")
    if not hwnd:
        log("未找到窗口句柄，跳过图标设置")
        return

    WM_SETICON = 0x0080
    IMAGE_ICON = 1
    LR_LOADFROMFILE = 0x00000010
    ICON_BIG = 1   # WM_SETICON wParam: ICON_BIG (任务栏图标)
    ICON_SMALL = 0  # WM_SETICON wParam: ICON_SMALL (标题栏图标)

    # 加载大图标 (32x32) 和小图标 (16x16)
    for size, icon_type in [(32, ICON_BIG), (16, ICON_SMALL)]:
        hicon = ctypes.windll.user32.LoadImageW(
            None, ICON_FILE, IMAGE_ICON,
            size, size, LR_LOADFROMFILE
        )
        if hicon:
            ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, icon_type, hicon)
            log(f"窗口图标已设置 ({size}x{size}, type={'BIG' if icon_type else 'SMALL'})")
        else:
            log(f"LoadImageW 加载 {size}x{size} 图标失败，尝试 ExtractIconExW")
            # 回退：用 ExtractIconExW 提取第一个图标
            hicon_large = ctypes.wintypes.HICON()
            hicon_small = ctypes.wintypes.HICON()
            extracted = ctypes.windll.shell32.ExtractIconExW(
                ICON_FILE, 0,
                ctypes.byref(hicon_large),
                ctypes.byref(hicon_small),
                1
            )
            if extracted > 0:
                h = hicon_large.value if icon_type == ICON_BIG else hicon_small.value
                if h:
                    ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, icon_type, h)
                    log(f"窗口图标已设置 (ExtractIconExW, type={'BIG' if icon_type else 'SMALL'})")
                break  # ExtractIconExW 一次拿两个，用一次就够
            else:
                log(f"ExtractIconExW 也失败了，跳过此尺寸")


def _on_closing():
    """窗口关闭前拦截 — 阻止关闭，改为隐藏到托盘"""
    # 启动保护期：窗口创建后 3 秒内忽略关闭事件
    # （pywebview EdgeChromium 后端在窗口初始化时会误触 closing 事件）
    if time.time() - _window_created_at < STARTUP_PROTECTION_SECONDS:
        log("启动保护期：忽略关闭事件（pywebview 初始化误触）")
        return False  # 阻止关闭

    settings_s = get_settings()
    if settings_s.get("minimize_to_tray", True) and systray_icon:
        save_window_state()  # 保存窗口位置
        log("窗口关闭 → 隐藏到系统托盘（进程保持运行）")
        try:
            window.hide()
        except Exception:
            pass
        return False  # 返回 False = 阻止窗口关闭
    else:
        save_window_state()  # 保存窗口位置
        log("窗口关闭 → 退出应用")
        return True  # 返回 True = 允许关闭


def _on_closed():
    """窗口关闭后回调（仅在允许关闭时触发）"""
    log("窗口已关闭")


def _patch_systray_icon_loader():
    """Patch infi.systray to use ExtractIconExW for PNG-based ICO support.
    infi.systray internally uses LoadImageA which does not support PNG-compressed
    ICO files. ExtractIconExW from shell32 handles these correctly."""
    try:
        from infi.systray import traybar
        import ctypes
        from ctypes import wintypes

        def _patched_load_icon(self):
            if not self._icon_shared and self._hicon != 0:
                ctypes.windll.user32.DestroyIcon(self._hicon)
                self._hicon = 0

            hicon = 0
            if self._icon is not None and os.path.isfile(self._icon):
                hicon_large = wintypes.HICON()
                hicon_small = wintypes.HICON()
                extracted = ctypes.windll.shell32.ExtractIconExW(
                    self._icon, 0,
                    ctypes.byref(hicon_large),
                    ctypes.byref(hicon_small),
                    1
                )
                if extracted > 0:
                    hicon = hicon_large.value
                    if hicon:
                        self._hicon = hicon
                        self._icon_shared = False
                        return

            # Fallback to default application icon
            if hicon == 0:
                self._hicon = ctypes.windll.user32.LoadIconW(0, 32512)
                self._icon_shared = True
                self._icon = None

        traybar.SysTrayIcon._load_icon = _patched_load_icon
        log("infi.systray 图标加载器已 patched (ExtractIconExW)")
    except Exception as e:
        log(f"Patch infi.systray 失败: {e}")


def setup_tray():
    """创建系统托盘图标"""
    global systray_icon
    if not HAS_SYSTRAY:
        log("infi.systray 未安装，跳过系统托盘功能")
        return

    # Patch infi.systray 图标加载器以支持 PNG-based ICO
    _patch_systray_icon_loader()

    try:
        # infi.systray 必须有 ico 文件
        icon_path = ICON_FILE if os.path.isfile(ICON_FILE) else None
        if not icon_path:
            log("未找到托盘图标文件，尝试使用默认图标")
            # 尝试使用 Python 自带的图标作为后备
            import sys
            possible = os.path.join(os.path.dirname(sys.executable), "DLLs", "py.ico")
            if os.path.isfile(possible):
                icon_path = possible
            else:
                # 创建一个简单的默认图标
                icon_path = _create_default_icon()

        menu_options = (
            ("打开 Hermes", None, _tray_open),
            ("重启后端", None, _tray_restart),
        )
        systray_icon = SysTrayIcon(
            icon_path,
            "Hermes Agent",
            menu_options,
            on_quit=_tray_quit,
            default_menu_index=0,
        )
        systray_icon.start()
        log("系统托盘图标已创建")
    except Exception as e:
        log(f"系统托盘创建失败: {e}")
        # 如果托盘创建失败，关闭窗口时应退出而非隐藏
        set_setting("minimize_to_tray", False)


def _create_default_icon():
    """创建一个默认的 .ico 文件（如果 hermes-icon.ico 不存在）"""
    import struct
    icon_path = os.path.join(APP_DIR, "_default_tray.ico")
    if os.path.isfile(icon_path):
        return icon_path

    try:
        # 创建最简单的 16x16 ICO 文件（纯色方块）
        # ICO 文件格式：Header + Directory + BMP Data
        header = struct.pack("<HHH", 0, 1, 1)  # Reserved, Type(1=ICO), Count
        # Directory entry: w, h, colors, reserved, planes, bpp, size, offset
        bmp_size = 16 * 16 * 4 + 16 * 4 + 40  # RGBA pixels + AND mask + BITMAPINFOHEADER
        directory = struct.pack("<BBBBHHIH",
            16, 16,   # width, height
            0, 0,     # colors, reserved
            1, 32,    # planes, bits per pixel
            bmp_size, 40  # size of image data, offset
        )
        # BITMAPINFOHEADER
        bmp_header = struct.pack("<IiiHHIIiiII",
            40, 16, 32,  # size, width, height (doubled for ICO)
            1, 32,       # planes, bpp
            0,           # compression
            16 * 16 * 4,  # image size
            0, 0,        # x/y pixels per meter
            0, 0         # colors used, important colors
        )
        # 紫色像素 (#6366f1)
        pixel = struct.pack("BBBB", 99, 102, 241, 255)  # BGRA
        pixels = pixel * (16 * 16)
        # AND mask (all opaque = all zeros)
        and_mask = b"\x00" * (16 * 4)

        with open(icon_path, "wb") as f:
            f.write(header + directory + bmp_header + pixels + and_mask)
        log(f"已创建默认托盘图标: {icon_path}")
        return icon_path
    except Exception as e:
        log(f"创建默认图标失败: {e}")
        return None


# ============================================================
# 开机自启动
# ============================================================

def set_auto_start(enable):
    """设置开机自启动"""
    if not winreg:
        log("当前平台不支持开机自启动")
        return False
    try:
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
            if enable:
                # 直接用 pythonw.exe 启动，避免弹出 cmd/terminal 窗口
                pythonw_exe = os.path.join(APP_DIR, "hermes-agent", ".venv", "Scripts", "pythonw.exe")
                script_path = os.path.join(APP_DIR, "hermes_desktop.py")
                launch_cmd = f'"{pythonw_exe}" "{script_path}"'
                winreg.SetValueEx(key, "HermesWebUI", 0, winreg.REG_SZ, launch_cmd)
                log("开机自启动已启用")
            else:
                try:
                    winreg.DeleteValue(key, "HermesWebUI")
                    log("开机自启动已禁用")
                except FileNotFoundError:
                    pass
        return True
    except Exception as e:
        log(f"设置开机自启动失败: {e}")
        return False

def is_auto_start_enabled():
    """检查开机自启动状态"""
    if not winreg:
        return False
    try:
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, "HermesWebUI")
            return True
    except (FileNotFoundError, OSError):
        return False


# ============================================================
# Windows 原生 Toast 通知（无需第三方库）
# ============================================================

def show_windows_toast(title, body, icon_path=None):
    """显示 Windows 原生 Toast 通知"""
    try:
        import ctypes
        from ctypes import wintypes, Structure, sizeof, byref
        import threading

        user32 = ctypes.windll.user32
        shell32 = ctypes.windll.shell32

        NIM_ADD = 0x00
        NIM_MODIFY = 0x01
        NIM_DELETE = 0x02
        NIF_ICON = 0x02
        NIF_TIP = 0x04
        NIF_INFO = 0x10
        NIIF_INFO = 0x01
        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x0010

        class GUID(Structure):
            _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                        ("Data3", wintypes.WORD), ("Data4", ctypes.c_byte * 8)]

        class NOTIFYICONDATA(Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND),
                ("uID", wintypes.UID), ("uFlags", wintypes.UID),
                ("uCallbackMessage", wintypes.UID), ("hIcon", wintypes.HICON),
                ("szTip", ctypes.c_wchar * 128), ("dwState", wintypes.DWORD),
                ("dwStateMask", wintypes.DWORD), ("szInfo", ctypes.c_wchar * 256),
                ("uTimeoutOrVersion", wintypes.UID), ("szInfoTitle", ctypes.c_wchar * 64),
                ("dwInfoFlags", wintypes.DWORD), ("guidItem", GUID),
                ("hBalloonIcon", wintypes.HICON),
            ]

        hInstance = user32.GetModuleHandleW(None)
        clsName = "HermesToast_" + str(os.getpid())

        class WNDCLS(Structure):
            _fields_ = [("cbSize", wintypes.UID), ("style", wintypes.UID),
                        ("lpfnWndProc", ctypes.c_void_p), ("cbClsExtra", ctypes.c_int),
                        ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE),
                        ("hIcon", wintypes.HICON), ("hCursor", wintypes.HANDLE),
                        ("hbrBackground", wintypes.HBRUSH), ("lpszMenuName", wintypes.LPCWSTR),
                        ("lpszClassName", wintypes.LPCWSTR), ("hIconSm", wintypes.HICON)]

        wc = WNDCLS()
        wc.cbSize = sizeof(WNDCLS)
        wc.lpfnWndProc = user32.DefWindowProcW
        wc.hInstance = hInstance
        wc.lpszClassName = clsName
        user32.RegisterClassExW(byref(wc))

        hwnd = user32.CreateWindowExW(0, clsName, "", 0, 0, 0, 0, 0, 0, 0, hInstance, None)

        nid = NOTIFYICONDATA()
        nid.cbSize = sizeof(NOTIFYICONDATA)
        nid.hWnd = hwnd
        nid.uID = 9527
        nid.uFlags = NIF_ICON | NIF_TIP | NIF_INFO
        wcscpy = ctypes.cdll.msvcrt.wcscpy
        wcscpy(ctypes.byref(nid.szTip), "Hermes WebUI")
        wcscpy(ctypes.byref(nid.szInfoTitle), (title or "Hermes")[:63])
        wcscpy(ctypes.byref(nid.szInfo), (body or "")[:255])
        nid.dwInfoFlags = NIIF_INFO

        if icon_path and os.path.isfile(icon_path):
            hicon = user32.LoadImageW(0, icon_path, IMAGE_ICON, 0, 0, LR_LOADFROMFILE)
            if hicon:
                nid.hIcon = hicon
                nid.dwInfoFlags = 0x03

        shell32.Shell_NotifyIconW(NIM_ADD, byref(nid))
        shell32.Shell_NotifyIconW(NIM_MODIFY, byref(nid))

        def _cleanup():
            import time
            time.sleep(10)
            try:
                shell32.Shell_NotifyIconW(NIM_DELETE, byref(nid))
                user32.DestroyWindow(hwnd)
                user32.UnregisterClassW(clsName, hInstance)
            except Exception:
                pass
        threading.Thread(target=_cleanup, daemon=True).start()
        log("Toast: " + (title or ""))
        return True
    except Exception as e:
        log("Toast failed: %s" % e)
        return False

class HermesJsApi:
    """暴露给前端的 Python API（通过 pywebview JSBridge）"""

    def __init__(self):
        self._icon_path = None

    def set_icon_path(self, path):
        self._icon_path = path

    def show_toast(self, title, body):
        """显示 Windows 原生 Toast 通知"""
        return show_windows_toast(title, body, self._icon_path)



def _register_toast_app():
    """注册 Hermes WebUI 为 Windows 通知发送者（首次运行时需要）"""
    try:
        import winreg
        app_key = r"Software\Classes\AppUserModelId\Hermes.WebUI"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, app_key, 0, winreg.KEY_READ)
            winreg.CloseKey(key)
            return  # Already registered
        except FileNotFoundError:
            pass
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, app_key)
        winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, "Hermes WebUI")
        winreg.SetValueEx(key, "IconUri", 0, winreg.REG_SZ, ICON_FILE if os.path.isfile(ICON_FILE) else "")
        winreg.CloseKey(key)
        log("已注册 Windows 通知发送者: Hermes WebUI")
    except Exception as e:
        log(f"注册通知发送者失败: {e}")



# ============================================================
# 后台轮询权限请求（弥补前端 JSBridge 不可靠的问题）
# ============================================================

_approval_poll_running = False
_last_approval_id = None

def _start_approval_polling(port):
    """后台线程：轮询后端 /api/approval/pending，有权限请求时弹 Toast"""
    global _approval_poll_running, _last_approval_id
    if _approval_poll_running:
        return
    _approval_poll_running = True

    def _poll():
        global _last_approval_id
        import urllib.request
        import json as _json
        url = f"http://127.0.0.1:{port}/api/approval/pending"
        log("权限请求轮询线程已启动")
        while _approval_poll_running:
            try:
                req = urllib.request.Request(url, headers={"Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=3) as resp:
                    data = _json.loads(resp.read().decode("utf-8"))
                    pending = data.get("pending")
                    if pending:
                        aid = pending.get("approval_id", "")
                        desc = pending.get("description", "") or pending.get("command", "")
                        if aid != _last_approval_id:
                            _last_approval_id = aid
                            show_windows_toast("⚠️ 需要授权", desc or "Agent 请求执行需要确认的操作")
                    else:
                        _last_approval_id = None
            except Exception:
                pass
            time.sleep(2)

    t = threading.Thread(target=_poll, daemon=True, name="ApprovalPoll")
    t.start()

_js_api = HermesJsApi()


# ============================================================
# 窗口管理
# ============================================================

def create_window(port, url=None):
    """创建主窗口。

    Args:
        port: 后端端口
        url: 初始加载 URL。为 None 时默认加载 http://127.0.0.1:{port}
    """
    global window
    settings = get_settings()
    if url is None:
        url = f"http://127.0.0.1:{port}"

    win_w = settings.get("window_width", 1280)
    win_h = settings.get("window_height", 800)
    min_w = settings.get("window_min_width", 900)
    min_h = settings.get("window_min_height", 600)
    win_x = settings.get("window_x")
    win_y = settings.get("window_y")

    kwargs = {
        "title": "Hermes Agent",
        "url": url,
        "width": win_w,
        "height": win_h,
        "min_size": (min_w, min_h),
        "resizable": True,
        "shadow": True,
        "text_select": False,
        "js_api": _js_api,
    }

    if win_x is not None and win_y is not None:
        kwargs["x"] = win_x
        kwargs["y"] = win_y

    log(f"创建窗口 {win_w}x{win_h}...")

    # 设置 Toast 通知图标
    _js_api.set_icon_path(ICON_FILE if os.path.isfile(ICON_FILE) else None)

    # 注意：icon 参数在 webview.start() 上，不在 create_window() 上
    window = webview.create_window(**kwargs)

    # 记录窗口创建时间，用于启动保护期（防止 closing 事件误触）
    global _window_created_at
    _window_created_at = time.time()

    # 绑定窗口关闭事件：拦截关闭，改为隐藏到托盘
    window.events.closing += _on_closing
    window.events.closed += _on_closed

    # 绑定窗口显示事件：窗口显示后立即设置图标
    def _on_shown():
        log("窗口已成功显示")
        _set_window_icon()
        # 补救：pywebview EdgeChromium 有时窗口创建后未实际显示，手动 ShowWindow
        _force_window_visible()
    window.events.shown += _on_shown

    return window


def _wait_for_backend_and_switch(port, loading_url, timeout=30):
    """后台线程：等待后端就绪后将窗口切换到实际页面。

    Args:
        port: 后端端口
        loading_url: loading 页面的 file:// URL（用于检测是否需要切换）
        timeout: 最长等待秒数（默认 30s）
    """
    log(f"并行启动：等待后端就绪（最长 {timeout}s）...")
    target_url = f"http://127.0.0.1:{port}"

    # 先短暂等待让子进程有时间初始化
    time.sleep(0.3)

    # 使用 SSE 快速检测 + HTTP 兜底
    deadline = time.time() + timeout
    while time.time() < deadline:
        # 优先 SSE 心跳（2~3s 检测）
        sse_result = _sse_health_check(port)
        if sse_result is True:
            break
        if sse_result is None:
            # SSE 不可用，走 HTTP 轮询
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/settings", timeout=3)
                break
            except Exception:
                pass
        time.sleep(0.5)

    if time.time() >= deadline:
        # 超时：在窗口显示错误信息
        log("后端启动超时，显示错误页面")
        try:
            if window:
                window.evaluate_js(
                    "if(window._hermesSetStatus){"
                    "window._hermesSetStatus('后端服务启动超时，请检查日志或点击重试', true);"
                    "}"
                )
        except Exception:
            pass
        # 仍然启动健康检查（后端可能延迟启动）
        start_health_check(port)
        return

    log(f"后端已就绪，切换窗口到 {target_url}")
    try:
        if window:
            window.load_url(target_url)
    except Exception as e:
        log(f"窗口 URL 切换失败: {e}")

    # 恢复右侧工作区面板偏好（防止 localStorage 丢失后面板默认关闭）
    try:
        time.sleep(0.5)  # 等待页面加载完成
        if window:
            window.evaluate_js(
                "(function(){"
                "var v=localStorage.getItem('hermes-webui-workspace-panel');"
                "if(v!=='open'){"
                "localStorage.setItem('hermes-webui-workspace-panel','open');"
                "localStorage.setItem('hermes-webui-workspace-panel-pref','open');"
                "console.log('[Hermes] 已恢复右侧面板偏好');"
                "}}())"
            )
    except Exception:
        pass

    # 启动健康检查
    start_health_check(port)


def save_window_state():
    """保存窗口位置和大小（使用 Win32 API，不创建 tkinter 窗口）"""
    if not window:
        return
    try:
        hwnd = None
        if hasattr(window, 'native') and window.native is not None:
            hwnd = int(window.native.Handle)
        if not hwnd:
            return
        rect = ctypes.wintypes.RECT()
        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
        settings = get_settings()
        settings["window_x"] = rect.left
        settings["window_y"] = rect.top
        settings["window_width"] = rect.right - rect.left
        settings["window_height"] = rect.bottom - rect.top
        save_settings(settings)
    except Exception:
        pass


# ============================================================
# 设置 IPC 接口
# ============================================================

class SettingsAPI:
    """通过 JSBridge 提供设置接口"""

    def get_all(self):
        return json.dumps(get_settings())

    def get(self, key):
        s = get_settings()
        return s.get(key, "")

    def set(self, key, value):
        try:
            value = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            pass
        s = set_setting(key, value)

        # 处理特殊设置
        if key == "auto_start":
            set_auto_start(bool(value))
        elif key == "cache_dir" and value:
            setup_cache_dir()

        return json.dumps({"ok": True})

    def set_cache_dir(self, path):
        """设置缓存目录"""
        path = path.strip()
        if path and not os.path.isdir(path):
            try:
                os.makedirs(path, exist_ok=True)
            except Exception as e:
                return json.dumps({"ok": False, "error": str(e)})
        return json.dumps({"ok": set_setting("cache_dir", path)})

    def toggle_auto_start(self):
        """切换开机自启动"""
        current = get_settings().get("auto_start", False)
        new_val = not current
        set_setting("auto_start", new_val)
        set_auto_start(new_val)
        return json.dumps({"auto_start": new_val})

    def restart_backend(self):
        """重启后端服务"""
        settings = get_settings()
        port = settings.get("port", HERMES_PORT)
        stop_server()
        time.sleep(2)
        python_exe = find_python_cached()
        if python_exe:
            ok = start_server(python_exe, port)
            return json.dumps({"ok": ok, "port": port})
        return json.dumps({"ok": False, "error": "Python not found"})

    def get_status(self):
        """获取服务状态"""
        settings = get_settings()
        port = settings.get("port", HERMES_PORT)
        try:
            url = f"http://127.0.0.1:{port}/health"
            urllib.request.urlopen(url, timeout=3)
            return json.dumps({"status": "running", "port": port})
        except Exception:
            return json.dumps({"status": "stopped", "port": port})

    def open_cache_dir(self):
        """打开缓存目录"""
        cache_dir = setup_cache_dir()
        os.startfile(cache_dir)
        return json.dumps({"ok": True})

    def browse_folder(self):
        """通过 JS 无法直接打开文件夹选择器，需要特殊处理"""
        return json.dumps({"ok": False, "message": "请在设置页面手动输入路径"})


# ============================================================
# 错误提示
# ============================================================

def show_error(msg):
    """显示错误弹窗（使用设计系统）"""
    try:
        # 转义HTML特殊字符
        escaped_msg = msg.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        html = f"""<!DOCTYPE html>
<html lang="zh-CN" data-theme="dark">
<head>
  <meta charset="utf-8">
  <style>
    :root {{
      --color-error: #ef4444;
      --color-error-hover: #f87171;
      --color-background: #0f172a;
      --color-surface: #1e293b;
      --color-text: #f1f5f9;
      --color-text-muted: #94a3b8;
      --font-family: 'Microsoft YaHei', 'Segoe UI', system-ui, sans-serif;
      --spacing-md: 16px;
      --spacing-lg: 24px;
      --spacing-xl: 32px;
      --radius-lg: 12px;
      --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.5);
    }}

    * {{ margin: 0; padding: 0; box-sizing: border-box; }}

    body {{
      font-family: var(--font-family);
      background: var(--color-background);
      color: var(--color-text);
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      padding: var(--spacing-xl);
    }}

    .error-container {{
      background: var(--color-surface);
      border-radius: var(--radius-lg);
      box-shadow: var(--shadow-lg);
      padding: var(--spacing-xl);
      max-width: 560px;
      width: 100%;
    }}

    .error-header {{
      display: flex;
      align-items: center;
      gap: var(--spacing-md);
      margin-bottom: var(--spacing-lg);
    }}

    .error-icon {{
      width: 48px;
      height: 48px;
      flex-shrink: 0;
    }}

    .error-title {{
      font-size: 20px;
      font-weight: 600;
      color: var(--color-error);
    }}

    .error-details {{
      background: rgba(239, 68, 68, 0.1);
      border: 1px solid rgba(239, 68, 68, 0.2);
      border-radius: 8px;
      padding: var(--spacing-md);
      margin-bottom: var(--spacing-lg);
    }}

    .error-details pre {{
      white-space: pre-wrap;
      word-break: break-word;
      font-size: 13px;
      color: var(--color-text-muted);
      font-family: 'Consolas', 'Monaco', monospace;
      line-height: 1.6;
    }}

    .error-actions {{
      display: flex;
      justify-content: flex-end;
    }}

    .btn {{
      background: var(--color-error);
      color: white;
      border: none;
      padding: 10px 24px;
      border-radius: 8px;
      font-size: 14px;
      font-weight: 500;
      cursor: pointer;
      transition: background 0.2s;
    }}

    .btn:hover {{
      background: var(--color-error-hover);
    }}
  </style>
</head>
<body>
  <div class="error-container">
    <div class="error-header">
      <svg class="error-icon" viewBox="0 0 48 48" fill="none">
        <circle cx="24" cy="24" r="20" fill="#ef4444" opacity="0.2"/>
        <path d="M24 14v12M24 30v2" stroke="#ef4444" stroke-width="3" stroke-linecap="round"/>
      </svg>
      <h1 class="error-title">Hermes WebUI</h1>
    </div>
    <div class="error-details">
      <pre>{escaped_msg}</pre>
    </div>
    <div class="error-actions">
      <button class="btn" onclick="window.close()">关闭</button>
    </div>
  </div>
</body>
</html>"""

        w = webview.create_window("Hermes Agent - Error", html=html,
                                   width=560, height=400, resizable=False)
        webview.start()
    except Exception:
        print(f"ERROR: {msg}", file=sys.stderr)


# ============================================================
# 应用关闭
# ============================================================

def shutdown_app():
    """优雅关闭应用"""
    global health_check_running, systray_icon, _server_log_handler, _warden_process
    health_check_running = False
    # 停止 Warden 守护进程
    if _warden_process and _warden_process.poll() is None:
        try:
            _warden_process.terminate()
            _warden_process.wait(timeout=PROCESS_TERMINATE_TIMEOUT)
        except Exception:
            try:
                _warden_process.kill()
            except Exception:
                pass
        _warden_process = None
    stop_server()
    # 关闭服务日志文件句柄
    if _server_log_handler:
        try:
            _server_log_handler.close()
        except Exception:
            pass
        _server_log_handler = None
    # 清理系统托盘
    if systray_icon:
        try:
            systray_icon.shutdown()
        except Exception:
            pass
        systray_icon = None
    sys.exit(0)  # 允许 atexit 执行，替代 os._exit(0)


# ============================================================
# 创建启动脚本
# ============================================================


def _needs_script_update(file_path, new_content):
    """检查文件是否需要更新（不存在或内容不同）"""
    if not os.path.isfile(file_path):
        return True
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            existing_content = f.read()
        return existing_content != new_content
    except Exception:
        return True


def create_launch_scripts():
    """创建启动相关的脚本和桌面快捷方式，全部走 pythonw.exe 避免弹窗"""
    try:
        _create_launch_scripts_inner()
    except Exception as e:
        log(f"创建启动脚本时出错（可能是权限不足）: {e}")


def _create_launch_scripts_inner():
    """内部实现：创建启动脚本"""
    # 优先使用 pythonw.exe
    pythonw = os.path.join(APP_DIR, "hermes-agent", ".venv", "Scripts", "pythonw.exe")
    launcher = pythonw if os.path.isfile(pythonw) else sys.executable
    script_path = os.path.join(APP_DIR, "hermes_desktop.py")

    # 1. start_hermes.bat（无空格文件名，可靠启动）
    bat_path = os.path.join(APP_DIR, "start_hermes.bat")
    bat_content = (
        "@echo off\r\n"
        "chcp 65001 >nul 2>&1\r\n"
        f"cd /d \"{APP_DIR}\"\r\n"
        f"start /B \"\" \"{launcher}\" \"{script_path}\"\r\n"
    )
    if _needs_script_update(bat_path, bat_content):
        with open(bat_path, "w", encoding="utf-8") as f:
            f.write(bat_content)
        log(f"启动脚本已更新: {bat_path}")

    # 2. 启动 Hermes WebUI.vbs（完全无窗口启动）
    vbs_path = os.path.join(APP_DIR, "启动 Hermes WebUI.vbs")
    vbs_content = (
        "Set WshShell = CreateObject(\"WScript.Shell\")\r\n"
        f"WshShell.CurrentDirectory = \"{APP_DIR}\"\r\n"
        f"WshShell.Run \"\"\"{launcher}\"\" \"\"{script_path}\"\"\", 0, False\r\n"
    )
    if _needs_script_update(vbs_path, vbs_content):
        with open(vbs_path, "w", encoding="utf-8") as f:
            f.write(vbs_content)
        log(f"启动脚本已更新: {vbs_path}")

    # 3. 直接用 Python 创建桌面快捷方式（不生成 .vbs 文件，避免杀软误报）
    _create_desktop_shortcut(launcher, script_path)

    log(f"启动脚本已创建: {bat_path}, {vbs_path}")


def _create_desktop_shortcut(launcher, script_path):
    """用 Python ctypes 创建桌面快捷方式（不写 .vbs，不触发杀软）"""
    try:
        import ctypes
        from ctypes import wintypes

        # 获取桌面路径
        CSIDL_DESKTOP = 0
        buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
        ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_DESKTOP, None, 0, buf)
        desktop = buf.value

        shortcut_path = os.path.join(desktop, "Hermes WebUI.lnk")

        # 如果快捷方式已存在且指向正确，跳过
        if os.path.isfile(shortcut_path):
            log("桌面快捷方式已存在，跳过创建")
            return

        # 使用 PowerShell 创建快捷方式（比 COM 更简洁，且不会误报）
        _no_win = dict(creationflags=0x08000000) if sys.platform == "win32" else {}
        ps_cmd = (
            f'$ws = New-Object -ComObject WScript.Shell;'
            f'$sc = $ws.CreateShortcut(\'{shortcut_path}\');'
            f'$sc.TargetPath = \'{launcher}\';'
            f'$sc.Arguments = \'"{script_path}"\';'
            f'$sc.WorkingDirectory = \'{APP_DIR}\';'
            f'$sc.Description = "Hermes WebUI - AI 智能助手";'
        )
        if os.path.isfile(ICON_FILE):
            ps_cmd += f'$sc.IconLocation = \'{ICON_FILE}\';'
        ps_cmd += '$sc.Save()'

        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True, text=True, timeout=10, **_no_win
        )
        if result.returncode == 0:
            log(f"桌面快捷方式已创建: {shortcut_path}")
        else:
            log(f"桌面快捷方式创建失败: {result.stderr.strip()}")
    except Exception as e:
        log(f"桌面快捷方式创建跳过: {e}")


# ============================================================
# 主入口
# ============================================================

# ============================================================
# 单实例锁
# ============================================================

def check_single_instance():
    """确保只有一个 Hermes Agent 实例运行。
    如果已有实例且后端正常，尝试激活其窗口并退出。
    如果已有实例但后端已死，清理旧进程并让当前实例继续启动。"""
    import ctypes
    from ctypes import wintypes

    mutex_name = "HermesWebUI_SingleInstance"

    # 尝试创建命名互斥体
    kernel32 = ctypes.windll.kernel32
    mutex = kernel32.CreateMutexW(None, False, mutex_name)
    last_error = kernel32.GetLastError()

    if last_error == 183:  # ERROR_ALREADY_EXISTS
        log("检测到已有 Hermes Agent 实例运行...")

        # 先检查后端是否还在运行
        port = get_settings().get("port", HERMES_PORT)
        backend_alive = False
        try:
            url = f"http://127.0.0.1:{port}/api/settings"
            urllib.request.urlopen(url, timeout=3)
            backend_alive = True
        except Exception:
            pass

        hwnd = ctypes.windll.user32.FindWindowW(None, "Hermes Agent")
        if not hwnd and backend_alive:
            # 窗口隐藏到托盘后 FindWindowW 找不到，用 EnumWindows 遍历所有窗口
            found_hwnd = ctypes.wintypes.HWND()
            def _enum_proc(h, _):
                buf = ctypes.create_unicode_buffer(256)
                ctypes.windll.user32.GetWindowTextW(h, buf, 256)
                if buf.value == "Hermes Agent":
                    nonlocal found_hwnd
                    found_hwnd = h
                    return False  # 停止枚举
                return True  # 继续枚举
            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
            ctypes.windll.user32.EnumWindows(WNDENUMPROC(_enum_proc), 0)
            hwnd = found_hwnd or 0

        if hwnd and backend_alive:
            # 后端正常，窗口存在 → 激活并退出
            # 三步法绕过 Windows SetForegroundWindow 限制:
            #   1. AttachThreadInput 获取前台线程权限
            #   2. ShowWindow(SW_RESTORE) 恢复隐藏的窗口
            #   3. SetWindowPos(TOPMOST→NOTOPMOST) 强制置顶再恢复，绕过前台锁
            our_thread = ctypes.windll.kernel32.GetCurrentThreadId()
            fg_hwnd = ctypes.windll.user32.GetForegroundWindow()
            fg_thread = 0
            if fg_hwnd:
                fg_thread = ctypes.windll.user32.GetWindowThreadProcessId(fg_hwnd, None)

            if fg_hwnd and fg_thread:
                ctypes.windll.user32.AttachThreadInput(our_thread, fg_thread, True)

            ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE

            # 置顶→取消置顶 技巧：绕过前台窗口锁定
            HWND_TOPMOST = -1
            HWND_NOTOPMOST = -2
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            ctypes.windll.user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                                              SWP_NOMOVE | SWP_NOSIZE)
            ctypes.windll.user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0,
                                              SWP_NOMOVE | SWP_NOSIZE)

            ctypes.windll.user32.SetForegroundWindow(hwnd)

            if fg_hwnd and fg_thread:
                ctypes.windll.user32.AttachThreadInput(our_thread, fg_thread, False)

            # 兜底：闪烁任务栏
            time.sleep(0.15)
            if ctypes.windll.user32.GetForegroundWindow() != hwnd:
                FLASHW_ALL = 3
                FLASHW_TIMERNOFG = 12
                class FLASHWINFO(ctypes.Structure):
                    _fields_ = [
                        ("cbSize", ctypes.wintypes.UINT),
                        ("hwnd", ctypes.wintypes.HWND),
                        ("dwFlags", ctypes.wintypes.DWORD),
                        ("uCount", ctypes.wintypes.UINT),
                        ("dwTimeout", ctypes.wintypes.DWORD),
                    ]
                fwi = FLASHWINFO()
                fwi.cbSize = ctypes.sizeof(FLASHWINFO)
                fwi.hwnd = hwnd
                fwi.dwFlags = FLASHW_ALL | FLASHW_TIMERNOFG
                fwi.uCount = 0
                fwi.dwTimeout = 0
                ctypes.windll.user32.FlashWindowEx(ctypes.byref(fwi))
                log("已激活现有窗口（任务栏闪烁兜底）")
            else:
                log("已激活现有窗口")
            sys.exit(0)
        elif backend_alive and not hwnd:
            # 后端正常但窗口找不到 → 通过 browser 打开
            log("后端正常运行，在浏览器中打开")
            import webbrowser
            webbrowser.open(f"http://127.0.0.1:{port}")
            sys.exit(0)
        else:
            # 后端已死 → 清理旧进程，让当前实例继续启动
            log("后端服务无响应，清理旧进程...")
            # 尝试 kill 占用端口的进程
            try:
                pid = is_port_in_use(port)
                if pid:
                    subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, timeout=5)
                    time.sleep(1)
            except Exception:
                pass
            # 尝试查找并 kill 旧 pythonw.exe 进程（仅限 Hermes 相关的）
            try:
                _no_win = dict(creationflags=0x08000000) if sys.platform == "win32" else {}
                res = subprocess.run(
                    ['wmic', 'process', 'where',
                     'name="pythonw.exe" and commandline like "%hermes_desktop%"',
                     'get', 'processid'],
                    capture_output=True, text=True, timeout=WMIC_TIMEOUT, **_no_win
                )
                for line in res.stdout.strip().splitlines():
                    line = line.strip()
                    if line.isdigit():
                        subprocess.run(["taskkill", "/F", "/PID", line], capture_output=True, timeout=5, creationflags=0x08000000)
                        log(f"已终止旧进程 PID {line}")
                time.sleep(1)
            except Exception:
                pass
            # 尝试释放当前获取到的 mutex handle
            try:
                kernel32.ReleaseMutex(mutex)
                kernel32.CloseHandle(mutex)
            except Exception:
                pass
            # 尝试打开已有的互斥锁并释放
            try:
                existing = kernel32.OpenMutexW(0x1F0001, False, mutex_name)  # MUTEX_ALL_ACCESS
                if existing:
                    kernel32.ReleaseMutex(existing)
                    kernel32.CloseHandle(existing)
            except Exception:
                pass
            # 返回 None 表示没有成功获取锁，让主流程继续尝试启动
            log("旧进程已清理，当前实例将继续启动")
            return None

    return mutex  # 保持引用，避免被 GC


def main():
    global window, _global_mutex

    # 全局注入 subprocess patch（必须在所有 subprocess 调用之前）
    patch_subprocess_create_no_window()
    _register_toast_app()  # 注册通知
    # 设置环境变量，让 server.py 子进程也应用 patch
    os.environ["HERMES_SUBPROCESS_NO_WINDOW"] = "1"

    # 单实例锁：如果已有实例运行则退出
    _global_mutex = check_single_instance()
    if _global_mutex is None:
        log("未能获取单实例锁，但将继续尝试启动...")
        # 旧实例已清理，尝试重新获取互斥锁
        import ctypes as _ct
        kernel32 = _ct.windll.kernel32
        _global_mutex = kernel32.CreateMutexW(None, False, "HermesWebUI_SingleInstance")
        err = kernel32.GetLastError()
        if err == 183:
            log("重新获取互斥锁仍失败，但将继续启动")
        else:
            log("重新获取互斥锁成功")

    log("=" * 50)
    log("Hermes Agent 桌面客户端启动")
    log("=" * 50)

    # 初始化缓存目录
    cache_dir = setup_cache_dir()
    log(f"缓存目录: {cache_dir}")
    log(f"应用目录: {APP_DIR}")

    # 检查服务目录
    if not os.path.isdir(SERVER_DIR):
        msg = (
            f"找不到 hermes-webui-cn 目录！\n\n"
            f"请确保以下目录存在：\n{SERVER_DIR}\n\n"
            f"本程序需要与 hermes-webui-cn 目录放在同一文件夹下才能运行。"
        )
        log(msg)
        show_error(msg)
        return

    # 创建启动脚本
    create_launch_scripts()

    # 读取设置
    settings = get_settings()
    port = settings.get("port", HERMES_PORT)

    # 同步自启动状态
    if settings.get("auto_start", False):
        if not is_auto_start_enabled():
            set_auto_start(True)

    # 查找 Python（使用缓存）
    python_exe = find_python_cached()
    if not python_exe:
        msg = (
            "未找到可用的 Python 环境！\n\n"
            "Hermes WebUI 需要 Python 3.10+ 才能运行后端服务。\n\n"
            "解决方案：\n"
            "1. 确保已安装 Python 3.10 或更高版本\n"
            "2. 确保 hermes-agent\\.venv 目录存在\n\n"
            "下载地址: https://www.python.org/downloads/"
        )
        log(msg)
        show_error(msg)
        return

    # 并行启动：后端启动不等待就绪，窗口立即显示过渡页
    if not start_server(python_exe, port, wait=False):
        msg = (
            "Hermes 后端服务启动失败！\n\n"
            f"Python: {python_exe}\n"
            f"服务目录: {SERVER_DIR}\n\n"
            f"请检查日志：\n{os.path.join(cache_dir, 'logs', 'server.log')}"
        )
        show_error(msg)
        return

    # 启动 HermesWarden 任务守护进程（后台静默，失败不影响主流程）
    _start_approval_polling(port)
    start_warden()

    # 注册退出清理
    atexit.register(shutdown_app)

    # 确保托盘功能开启（之前旧代码的 bug 可能把它关了）
    settings = get_settings()
    if not settings.get("minimize_to_tray", True):
        log("修复设置：重新启用 minimize_to_tray")
        set_setting("minimize_to_tray", True)

    # 先创建系统托盘（在窗口之前，这样关闭窗口后托盘还在）
    setup_tray()

    # 构建过渡页 URL
    loading_path = os.path.join(APP_DIR, "loading.html")
    if os.path.isfile(loading_path):
        loading_url = f"file:///{loading_path.replace(os.sep, '/')}"
    else:
        loading_url = f"http://127.0.0.1:{port}"
        log("loading.html 未找到，直接加载后端 URL")

    # 立即创建窗口（加载过渡页）
    create_window(port, url=loading_url)

    # 后台线程：等待后端就绪后切换窗口到实际页面
    threading.Thread(
        target=_wait_for_backend_and_switch,
        args=(port, loading_url),
        daemon=True,
    ).start()

    # 启动 webview 事件循环（窗口关闭由 events.closing 拦截）
    log("启动桌面窗口...")
    icon_path = ICON_FILE if os.path.isfile(ICON_FILE) else None
    webview.start(debug=False, icon=icon_path)

    # webview.start() 返回 = 窗口已关闭
    # 如果 minimize_to_tray=True，进程保持运行（托盘或静默保活）
    settings = get_settings()
    if settings.get("minimize_to_tray", True):
        if systray_icon:
            # 托盘正常 → 主线程保活等托盘操作
            log("窗口已关闭，进程在托盘保持运行...")
            try:
                keep_alive = threading.Event()
                keep_alive.wait()
            except KeyboardInterrupt:
                shutdown_app()
        else:
            # 托盘未创建 → 仍然保活（后端继续运行，可通过浏览器访问）
            log("窗口已关闭，托盘不可用，后端仍保持运行（可通过浏览器访问 http://127.0.0.1:%d）" % port)
            try:
                keep_alive = threading.Event()
                keep_alive.wait()
            except KeyboardInterrupt:
                shutdown_app()
    else:
        log("Hermes Agent 已退出")
        shutdown_app()


if __name__ == "__main__":
    main()
