#!/usr/bin/env python3
"""HermesWarden v1.1 · goal命令 + 钩子 + 任务隔离 + 长任务模型
Windows adapted: sys.executable for python, PowerShell for hooks, .bat for on_complete."""

import json, os, sys, time, subprocess, shutil, threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

HOME = Path(os.environ.get("WARDEN_HOME", Path.home() / "hermes-warden"))
IS_WINDOWS = sys.platform == "win32"
QUEUE = HOME / "task_queue.json"
STATUS = HOME / "status.json"
HEARTBEAT = HOME / "heartbeat.json"
LOCKFILE = HOME / ".daemon.lock"

DEFAULT_RATES = {"generate": 300, "batch": 0, "watch": 0, "scheduled": 0}

# 长任务模型推荐
LONG_TASK_MODELS = {
    "free": ["z-ai/glm-5.1", "nvidia/nemotron-3-super-120b-a12b", "mistralai/mistral-large-3-675b-instruct-2512"],
    "paid": ["mimo-v2.5-pro", "mimo-v2.5", "deepseek-v4-pro"]
}

def load_json(path):
    with open(path) as f:
        return json.load(f)

def save_json(obj, path):
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False, default=str)

def acquire_lock():
    try:
        fd = os.open(LOCKFILE, os.O_CREAT | os.O_EXCL | os.O_RDWR)
        os.close(fd); return True
    except FileExistsError:
        try:
            if time.time() - os.path.getmtime(LOCKFILE) > 300:
                LOCKFILE.unlink(missing_ok=True)
                fd = os.open(LOCKFILE, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                os.close(fd); return True
        except: pass
        return False

def release_lock():
    LOCKFILE.unlink(missing_ok=True)

def heartbeat_thread():
    while True:
        save_json({"hb": time.strftime("%Y-%m-%dT%H:%M:%S%z")}, HEARTBEAT)
        time.sleep(300)

def check_disk():
    gb = shutil.disk_usage(HOME).free / (1024**3)
    return gb, gb < load_json(QUEUE).get("disk_alert_gb", 10)

def detect_cycles(tasks):
    g = {t["id"]: t.get("depends_on", []) for t in tasks}
    col = {n: 0 for n in g}
    def dfs(n, p):
        col[n] = 1
        for m in g.get(n, []):
            if m not in col: continue
            if col[m] == 1: return p + [m]
            if col[m] == 0:
                r = dfs(m, p + [m])
                if r: return r
        col[n] = 2
    for n in g:
        if col[n] == 0:
            c = dfs(n, [n])
            if c: return c

def check_orphans(tasks):
    ids = {t["id"] for t in tasks}
    return [(t["id"], d) for t in tasks for d in t.get("depends_on", []) if d not in ids]

def _run_script(script_path, cwd=None):
    """Cross-platform script runner. Uses bash on Linux, .bat/.ps1/.py on Windows."""
    p = Path(script_path)
    if not p.exists():
        return
    cwd = cwd or HOME
    if IS_WINDOWS:
        if p.suffix == ".py":
            subprocess.run([sys.executable, str(p)], cwd=cwd, timeout=60)
        elif p.suffix == ".ps1":
            subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(p)],
                           cwd=cwd, timeout=60)
        else:
            subprocess.run([str(p)], cwd=cwd, timeout=60, shell=True)
    else:
        subprocess.run(["bash", str(p)], cwd=cwd, timeout=60)


def run_hook(task, phase):
    """生命周期钩子：before_episode / after_episode / on_error"""
    hook_script = task.get("hooks", {}).get(phase, "")
    if not hook_script:
        return
    _run_script(HOME / hook_script)

def run_episode(task):
    run_hook(task, "before_episode")
    script = task["script"]
    ttype = task.get("type", "generate")
    timeout = task.get("episode_timeout", 1800)
    check_cmd = task.get("check", "")
    gb, low = check_disk()
    if low:
        run_hook(task, "on_error")
        return {"error": f"磁盘不足{gb:.1f}GB", "exit_code": -1}
    try:
        # 注入goal变量到子进程
        env = os.environ.copy()
        env["WARDEN_GOAL"] = task.get("goal", "")
        env["WARDEN_TASK_ID"] = task["id"]
        env["WARDEN_OUTPUT_DIR"] = str(task.get("output_dir", ""))
        result = subprocess.run([sys.executable, script], capture_output=True, text=True,
                                timeout=timeout, cwd=HOME, env=env)
        exit_code = result.returncode
    except subprocess.TimeoutExpired:
        exit_code = -1
    lines = 0
    if check_cmd and ttype == "generate":
        try:
            r = subprocess.run(check_cmd, shell=True, capture_output=True, text=True, cwd=HOME)
            lines = int(r.stdout.strip())
        except: pass
    run_hook(task, "after_episode")
    if exit_code != 0:
        run_hook(task, "on_error")
    return {"exit_code": exit_code, "lines": lines}

def check_done(task, lines):
    if task["type"] == "batch": return True
    if task["type"] in ("watch", "scheduled"): return False
    return lines >= task.get("target", 0)

def task_output_dir(task):
    """按日期+goal隔离产出目录"""
    today = time.strftime("%Y-%m-%d")
    slug = task.get("id", "task")
    d = HOME / "output" / f"{today}-{slug}"
    d.mkdir(parents=True, exist_ok=True)
    return d

def update_status(config, current_id, etas, cost_info, last_error):
    tasks = config.get("tasks", [])
    queue_status = [{"id": t["id"], "status": t.get("status"), "goal": t.get("goal",""),
                     "done": t.get("current_lines",0), "target": t.get("target",0)} for t in tasks]
    gb, _ = check_disk()
    old = load_json(STATUS) if STATUS.exists() else {}
    today = time.strftime("%Y-%m-%d")
    ln = old.get("last_night", {})
    if ln.get("date") != today:
        ln = {"date": today, "total_at_sundown": ln.get("total_at_sundown", 0)}
    save_json({"warden": "v1.1", "current_task": current_id,
               "cost": cost_info, "queue": queue_status, "etas": etas,
               "last_night": ln, "last_error": last_error,
               "disk_free_gb": round(gb,1),
               "heartbeat": time.strftime("%Y-%m-%dT%H:%M:%S%z")}, STATUS)

def main():
    if not acquire_lock():
        print("Warden已在运行"); return
    threading.Thread(target=heartbeat_thread, daemon=True).start()
    fail_count = {}
    while True:
        try: config = load_json(QUEUE)
        except: time.sleep(60); continue
        tasks = config.get("tasks", [])
        cycle = detect_cycles(tasks)
        if cycle:
            print(f"❌ 依赖环: {'→'.join(cycle)}")
            time.sleep(60); continue
        orphans = check_orphans(tasks)
        for tid, dep in orphans:
            print(f"⚠️ orphan: {tid}→{dep}")
        done_ids = {t["id"] for t in tasks if t.get("status") == "done"}
        max_par = config.get("max_parallel", 2)
        cands = []
        for t in tasks:
            if t.get("status") not in ("pending", "running"): continue
            deps = t.get("depends_on", [])
            if all(d in done_ids for d in deps):
                cands.append(t)
        if not cands:
            time.sleep(3600); continue
        
        # 真正并行：每个候选任务开线程
        selected = cands[:max_par]
        for t in selected:
            t["status"] = "running"
            if not t.get("output_dir"):
                t["output_dir"] = str(task_output_dir(t))
        save_json(config, QUEUE)
        
        def run_one(t):
            lines_before = 0
            if t.get("type") == "generate" and t.get("check"):
                try:
                    r = subprocess.run(t["check"], shell=True, capture_output=True, text=True, cwd=HOME)
                    lines_before = int(r.stdout.strip())
                except: pass
            result = run_episode(t)
            return t, lines_before, result
        
        with ThreadPoolExecutor(max_workers=max_par) as pool:
            futures = {pool.submit(run_one, t): t for t in selected}
            for future in as_completed(futures):
                t, lines_before, result = future.result()
                fid = t["id"]
            if result.get("exit_code", -1) != 0:
                fail_count[fid] = fail_count.get(fid, 0) + 1
                if fail_count[fid] >= t.get("max_consecutive_fails", 3):
                    t["status"] = "blocked"
                else:
                    t["status"] = "running"
            elif check_done(t, result.get("lines", 0)):
                t["status"] = "done"
                fail_count[fid] = 0
            else:
                t["status"] = "running"
                t["current_lines"] = result.get("lines", 0)
            save_json(config, QUEUE)
        non_watch = [t for t in tasks if t.get("type") != "watch"]
        if non_watch and all(t.get("status") == "done" for t in non_watch):
            hook = HOME / ("on_complete.bat" if IS_WINDOWS else "on_complete.sh")
            if hook.exists():
                _run_script(hook)
        time.sleep(300)

if __name__ == "__main__":
    import sys
    if "--doctor" in sys.argv:
        print("🔍 Warden体检...")
        try:
            config = load_json(QUEUE)
            tasks = config.get("tasks", [])
            print("✅ task_queue.json OK")
            cycle = detect_cycles(tasks)
            print(f"{'❌ 环:'+ '→'.join(cycle) if cycle else '✅ 无环'}")
            orphans = check_orphans(tasks)
            for tid, dep in orphans: print(f"⚠️ orphan:{tid}→{dep}")
            if not orphans: print("✅ 无orphan")
            for t in tasks:
                p = HOME / t.get("script", "")
                print(f"{'✅' if p.exists() else '⚠️'} {t['script']}")
            gb, low = check_disk()
            env_file = HOME / ".env"
            print(f"{'✅' if env_file.exists() else '⚠️'} .env")
            print(f"{'⚠️' if low else '✅'} 磁盘{gb:.1f}GB")
        except Exception as e:
            print(f"❌ {e}")
        sys.exit(0)
    main()
