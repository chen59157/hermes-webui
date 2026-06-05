# 开发环境搭建指南

> 本文档说明如何搭建 Hermes WebUI Desktop Client 的本地开发环境。

---

## 1. 前置条件

| 工具 | 版本要求 | 安装方式 |
|------|---------|---------|
| Python | 3.11+ | [python.org](https://www.python.org/downloads/) |
| Git | 2.30+ | [git-scm.com](https://git-scm.com/) |
| uv (可选) | 最新版 | `pip install uv` |

### 验证安装

```powershell
python --version    # 应输出 Python 3.11.x 或更高
git --version       # 应输出 git version 2.xx.x
```

---

## 2. 克隆仓库

```powershell
git clone https://github.com/your-org/hermes-webui-desktop.git
cd hermes-webui-desktop
```

### 子模块初始化

如果 `hermes-agent` 和 `hermes-webui-cn` 作为 Git 子模块管理：

```powershell
git submodule update --init --recursive
```

---

## 3. 虚拟环境搭建

### 方式一：使用 uv（推荐）

```powershell
# hermes-agent 虚拟环境
cd hermes-agent
uv venv
.venv\Scripts\activate
uv pip install -e .
deactivate

# hermes-webui-cn 依赖
cd ..\hermes-webui-cn
uv venv
.venv\Scripts\activate
uv pip install -r requirements.txt
deactivate
cd ..
```

### 方式二：使用标准 venv

```powershell
# hermes-agent 虚拟环境
cd hermes-agent
python -m venv .venv
.venv\Scripts\activate
pip install -e .
deactivate

# hermes-webui-cn 依赖
cd ..\hermes-webui-cn
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
deactivate
cd ..
```

### 安装桌面客户端依赖

```powershell
pip install pywebview
```

---

## 4. 配置环境变量

在项目根目录创建 `.env` 文件（或复制模板）：

```powershell
# 复制模板
copy hermes-webui-cn\.env.example .env

# 编辑 .env，至少配置一个 LLM Provider
```

常用 Provider 配置：

```env
# Nous Portal（推荐）
NOUS_API_KEY=your_api_key_here

# OpenRouter
OPENROUTER_API_KEY=your_api_key_here

# OpenAI
OPENAI_API_KEY=your_api_key_here
```

---

## 5. 运行开发模式

### 5.1 仅启动 Web UI（不启动桌面外壳）

```powershell
cd hermes-webui-cn
.venv\Scripts\python.exe server.py
```

浏览器打开 `http://127.0.0.1:8787`

### 5.2 启动完整的桌面客户端

```powershell
# 确保 hermes_desktop.py 中的 Python 路径指向正确
.venv\Scripts\python.exe hermes_desktop.py
```

### 5.3 修改启动脚本中的 Python 路径

编辑 `启动 Hermes WebUI.bat`，将 Python 路径改为：

```batch
"项目目录\hermes-agent\.venv\Scripts\python.exe" "%~dp0hermes_desktop.py"
```

---

## 6. 调试技巧

### 6.1 日志查看

| 日志文件 | 位置 | 内容 |
|---------|------|------|
| 桌面客户端日志 | `hermes.log` | 启动流程、崩溃恢复、服务管理 |
| 后端服务日志 | `.hermes/logs/server.log` | HTTP 请求、Agent 执行详情 |
| Agent 日志 | `.hermes/logs/` | 对话、技能、工具调用 |

### 6.2 查看实时日志

```powershell
# 桌面客户端日志
Get-Content hermes.log -Wait

# 后端服务日志
Get-Content .hermes\logs\server.log -Wait
```

### 6.3 单独调试后端

```powershell
# 启动后端并保持终端输出
cd hermes-webui-cn
.venv\Scripts\python.exe server.py --debug
```

### 6.4 pywebview 调试

在 `hermes_desktop.py` 中开启开发者工具：

```python
# 在 create_window() 中添加
window = webview.create_window(
    title="Hermes WebUI",
    url=f"http://127.0.0.1:{port}",
    width=width, height=height,
    min_size=(min_w, min_h),
    # 开发时启用
    easy_drag=False
)
```

---

## 7. 代码结构速查

```
hermes-webui-desktop/
│
├── hermes_desktop.py          # 【核心】桌面客户端主程序
│   ├── 行 1-14:    模块导入
│   ├── 行 20-52:   路径配置
│   ├── 行 58-75:   日志系统
│   ├── 行 82-130:  设置管理
│   ├── 行 137-173: 缓存目录管理
│   ├── 行 180-229: Python 查找
│   ├── 行 234-275: 端口与网络工具
│   ├── 行 282-381: 服务器进程管理
│   ├── 行 388-443: 崩溃恢复与健康检查
│   ├── 行 450-700: 系统托盘
│   ├── 行 708-850: 开机自启动
│   ├── 行 858-920: 窗口管理
│   └── 行 926-963: 主入口
│
├── 启动 Hermes WebUI.bat      # Windows 启动脚本
├── 启动_最小化.bat            # 最小化启动
├── 卸载 Hermes WebUI.bat      # 卸载脚本
├── settings.json              # 运行时设置
│
├── hermes-agent/              # Agent 核心（上游子模块）
│   ├── agent/                 # Agent 循环与工具
│   ├── skills/                # 技能系统
│   ├── gateway/               # 消息网关
│   └── pyproject.toml         # Python 项目配置
│
└── hermes-webui-cn/           # Web UI（上游子模块）
    ├── server.py              # HTTP 服务入口
    ├── api/                   # API 路由与业务逻辑
    ├── static/                # 前端静态资源
    └── docs/                  # WebUI 自身文档
```

---

## 8. 测试

### hermes-webui-cn 测试

```powershell
cd hermes-webui-cn
.venv\Scripts\python.exe -m pytest tests/ -v
```

当前测试覆盖: 3309 个测试用例，CI 在 Python 3.11/3.12/3.13 上运行。

### hermes-agent 测试

```powershell
cd hermes-agent
.venv\Scripts\python.exe -m pytest tests/ -v
```

---

## 9. IDE 配置建议

### VS Code

推荐的扩展：
- Python (ms-python.python)
- Pylance (ms-python.vscode-pylance)
- Even Better TOML (tamasfe.even-better-toml)

推荐设置（`.vscode/settings.json`）：

```json
{
  "python.defaultInterpreterPath": "hermes-agent/.venv/Scripts/python.exe",
  "python.analysis.extraPaths": ["hermes-agent", "hermes-webui-cn"],
  "[python]": {
    "editor.formatOnSave": true,
    "editor.defaultFormatter": "ms-python.black-formatter"
  }
}
```

---

*更新于 2026-05-24*