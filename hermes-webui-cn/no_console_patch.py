"""
No-Console Subprocess Patch — 消除 Windows 终端窗口闪动

通过 monkey-patch subprocess 核心入口 + os.system，
在任何导入本模块的 Python 进程中自动注入 CREATE_NO_WINDOW (0x08000000)。

设计要点：
- subprocess.run / call / check_call / check_output 内部均通过 Popen 实现，
  因此只 patch Popen 即可覆盖以上所有 API。
- os.system 在 Windows 上直接调用 CreateProcess，不走 subprocess 路径，
  需单独 wrapper。
- os.popen 在 Python 3 内部使用 subprocess.Popen，已被 Popen patch 覆盖。
- 通过 HERMES_SUBPROCESS_NO_WINDOW 环境变量控制是否生效（默认关闭）。
"""

import os
import sys
import subprocess as _subprocess
import logging as _logging

_logger = _logging.getLogger(__name__)


def apply_patch() -> bool:
    """应用 no-console monkey-patch。返回 True 表示已应用。"""
    if sys.platform != "win32":
        return False

    env_flag = os.environ.get("HERMES_SUBPROCESS_NO_WINDOW", "").strip()
    if env_flag not in ("1", "true", "yes", "on"):
        return False

    # 二次调用幂等检查
    if getattr(apply_patch, "_applied", False):
        return True

    CREATE_NO_WINDOW = 0x08000000

    # ── 保存原始引用 ──
    _original_Popen = _subprocess.Popen
    _original_system = os.system

    # ── Popen patch：自动注入 creationflags ──
    def _patched_Popen(*args, **kwargs):
        cf = kwargs.get("creationflags", 0) or 0
        kwargs["creationflags"] = cf | CREATE_NO_WINDOW
        return _original_Popen(*args, **kwargs)

    # ── os.system patch：转发到 subprocess.call ──
    def _patched_system(command):
        return _subprocess.call(command, shell=True, creationflags=CREATE_NO_WINDOW)

    # 注入
    _subprocess.Popen = _patched_Popen
    os.system = _patched_system

    apply_patch._applied = True  # type: ignore[attr-defined]
    _logger.info("no_console_patch 已注入 (CREATE_NO_WINDOW -> subprocess.Popen + os.system)")
    return True