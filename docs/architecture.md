# 架构设计文档

> Hermes WebUI Desktop Client 的完整架构说明

---

## 1. 整体架构概览

Hermes WebUI Desktop Client 采用三层架构，将 Agent 核心、Web UI 服务和桌面外壳解耦：

```
┌──────────────────────────────────────────────────┐
│          Hermes Desktop Client (桌面外壳)          │
│  ┌────────────────────────────────────────────┐  │
│  │           pywebview 原生窗口                │  │
│  │  ┌──────────────────────────────────────┐  │  │
│  │  │    Hermes Web UI (Browser Content)    │  │  │
│  │  │    http://127.0.0.1:8787             │  │  │
│  │  └──────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────┘  │
│                                                 │
│  ┌──────────────┐  ┌──────────────┐            │
│  │  系统托盘     │  │  开机自启动    │            │
│  └──────────────┘  └──────────────┘            │
└───────────────────────┬──────────────────────────┘
                        │ HTTP
┌───────────────────────┴──────────────────────────┐
│          hermes-webui-cn (Web 服务层)              │
│  ┌─────────┐  ┌─────────┐  ┌─────────────────┐  │
│  │ server.py│  │ api/    │  │ static/         │  │
│  │ (路由)   │  │ (业务)   │  │ (前端 JS/CSS)   │  │
│  └─────────┘  └─────────┘  └─────────────────┘  │
└───────────────────────┬──────────────────────────┘
                        │ 子进程调用
┌───────────────────────┴──────────────────────────┐
│          hermes-agent (Agent 核心引擎)             │
│  ┌─────────┐  ┌─────────┐  ┌─────────────────┐  │
│  │ Agent   │  │ Skills  │  │ Memory/Sessions │  │
│  │ Loop    │  │ Hub     │  │                 │  │
│  └─────────┘  └─────────┘  └─────────────────┘  │
└──────────────────────────────────────────────────┘
```

### 各层职责

| 层 | 组件 | 职责 | 技术栈 |
|---|------|------|--------|
| 桌面外壳 | `hermes_desktop.py` | 窗口管理、系统托盘、进程管理、设置持久化 | Python + pywebview + Win32 API |
| Web 服务 | `hermes-webui-cn/` | HTTP API、会话管理、前端界面渲染 | Python HTTP Server + Vanilla JS |
| Agent 核心 | `hermes-agent/` | AI 对话、技能执行、记忆管理、工具调用 | Python 异步 + CLI |

---

## 2. 桌面客户端详解 (`hermes_desktop.py`)

### 2.1 模块划分

```
hermes_desktop.py (963 行)
├── 路径配置 (APP_DIR, SERVER_DIR, SETTINGS_FILE 等)
├── 日志系统 (log 函数 + 线程安全锁)
├── 设置管理 (get_settings / save_settings / set_setting)
├── 缓存目录管理 (setup_cache_dir + 数据迁移)
├── Python 查找 (find_python 多级回退)
├── 端口与网络工具 (is_port_in_use / find_free_port / check_server_ready)
├── 服务器进程管理 (start_server / stop_server)
├── 崩溃恢复与健康检查 (can_restart / do_restart / start_health_check)
├── 系统托盘 (setup_tray_icon + 消息循环)
├── 开机自启动 (auto_start / auto_start_disabled)
├── 窗口管理 (create_window + 事件处理)
└── 主入口 (main 函数)
```

### 2.2 Python 环境查找策略

`find_python()` 按以下优先级查找 Python 3.10+：

1. `hermes-agent/.venv/Scripts/python.exe`（项目自带虚拟环境）
2. `_internal/python.exe`（打包时内嵌的 Python）
3. 系统 PATH 中的 `python` / `python3`
4. 常见安装路径（`%LocalAppData%\Programs\Python\Python3xx\`）

### 2.3 进程管理

```
main()
  ├── find_python()         # 查找 Python
  ├── setup_cache_dir()     # 设置缓存目录
  ├── find_free_port()      # 查找可用端口
  ├── start_server()        # 启动后端子进程
  │   ├── subprocess.Popen  # DETACHED_PROCESS + CREATE_NEW_PROCESS_GROUP
  │   ├── check_server_ready()  # 轮询 /api/settings 直到就绪
  │   └── start_health_check()  # 启动健康检查线程
  ├── create_window()       # 创建 pywebview 窗口
  ├── setup_tray_icon()     # 创建系统托盘
  └── window.start()        # 进入事件循环
```

### 2.4 崩溃恢复机制

```
健康检查线程（每 10 秒）
  ├── 请求 /api/settings
  ├── 失败累计 >= 3 次
  │   └── can_restart()
  │       ├── 5 分钟内 < 3 次 → 执行重启
  │       └── 5 分钟内 >= 3 次 → 跳过
  ├── 失败累计 >= 6 次
  │   └── 重置计数器
  └── 在 WebView 中注入离线提示 Toast
```

### 2.5 系统托盘实现

使用 Windows 原生 Win32 API（`ctypes` 调用 `shell32.dll` / `user32.dll`）：

- **类名**: `HermesTrayHost`
- **消息循环**: 独立线程处理 `WM_TRAYICON_MSG`
- **左键**: 显示/隐藏主窗口
- **右键菜单**: 重启服务、设置、退出

### 2.6 设置持久化

- 格式: JSON（`settings.json`）
- 内存缓存: `_settings_cache` 字典
- 自动记忆: 窗口位置（`window_x`, `window_y`）、上次端口

---

## 3. Web UI 层详解 (`hermes-webui-cn/`)

### 3.1 文件结构

参考 `hermes-webui-cn/ARCHITECTURE.md` 第 2 节 "File Inventory"。

### 3.2 架构特点

- **无构建步骤**：不使用 Webpack/Vite 等打包工具
- **原生 JavaScript**：7 个 ES Module，零框架依赖
- **服务端路由**: `server.py`（81 行）作为薄路由层，委托给 `api/routes.py`
- **SSE 流式传输**: 对话流通过 Server-Sent Events 推送

### 3.3 关键 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/settings` | GET | 获取设置（健康检查端点） |
| `/api/conversations` | GET/POST | 会话列表 / 创建 |
| `/api/conversations/{id}` | GET/DELETE | 会话详情 / 删除 |
| `/api/chat` | POST | 发送消息（SSE 流式响应） |
| `/health` | GET | 健康状态 |

---

## 4. Agent 核心层详解 (`hermes-agent/`)

### 4.1 核心组件

| 组件 | 目录 | 职责 |
|------|------|------|
| Agent Loop | `agent/` | 对话循环、工具调用编排 |
| Skills Hub | `skills/` | 技能注册、创建、自我改进 |
| Memory | `hermes_cli/memory.py` | 会话记忆、FTS5 搜索 |
| Gateway | `gateway/` | 多平台消息网关（Telegram/Discord 等） |
| TUI | `ui-tui/` | 终端界面（prompt_toolkit） |
| Providers | `providers/` | 多 LLM 提供商适配 |

### 4.2 数据流

```
用户输入 → Web UI → API → Agent Loop → LLM Provider → 工具调用 → 技能执行
                                        ↓
                                    Memory 存储 ← 技能学习循环
```

---

## 5. 数据目录结构

```
.hermes/                     # 运行时数据目录
├── .env                     # 环境变量 / API Key
├── .migrated                # 数据迁移标记
├── cron/                    # 定时任务配置
├── logs/
│   └── server.log           # 后端服务日志
├── memories/                # Agent 记忆持久化
├── sessions/                # 会话数据
└── skills/                  # Agent 技能存储
```

---

## 6. 通信协议

```
[pywebview 窗口] ←──── HTTP ────→ [hermes-webui-cn server.py:8787]
                                      │
                                      │ 子进程 stdin/stdout + 文件系统
                                      ↓
                                 [hermes-agent CLI]
```

所有前后端通信通过 HTTP REST API + SSE 完成，桌面外壳仅代理浏览器窗口，不介入业务数据流。

---

## 7. 安全考量

| 层面 | 措施 |
|------|------|
| 网络 | 仅绑定 `127.0.0.1`，不暴露到局域网 |
| 设置 | `settings.json` 已加入 `.gitignore`，不提交含路径的本地配置 |
| 环境变量 | API Key 存储在 `.env`（不追踪），通过 `python-dotenv` 加载 |
| 进程隔离 | 后端在独立子进程中运行，崩溃不影响桌面外壳 |

---

*更新于 2026-05-24*