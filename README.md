# Hermes WebUI

> 🤖 基于 Hermes Agent 的 Windows 桌面 AI 助手客户端

[![Version](https://img.shields.io/badge/version-v3.2.0-blue)]()
[![Python](https://img.shields.io/badge/python-3.12-green)]()
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-lightgrey)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 项目简介

Hermes WebUI 将 [Hermes Agent](https://github.com/NousResearch/hermes-agent) 打包为独立的 Windows 桌面应用。用户无需安装 Python 或配置环境，双击安装包即可获得完整的 AI 助手体验。

### 核心特性

| 特性 | 说明 |
|------|------|
| **原生桌面体验** | 基于 pywebview + WebView2，独立窗口，非浏览器标签页 |
| **系统托盘常驻** | 最小化到托盘后台运行，右键菜单快速操作 |
| **开机自启动** | 支持通过注册表实现开机启动 |
| **崩溃自动恢复** | 后端异常时自动重启（3 次/5 分钟限制） |
| **窗口状态记忆** | 自动保存窗口位置、大小，下次启动恢复 |
| **免安装 Python** | 内嵌 Python 3.12 运行时，开箱即用 |
| **WebView2 自动安装** | 安装包自动检测并安装 WebView2 运行时 |
| **安全打包** | 安装包不含任何 API Key，用户自行配置 |

---

## v3.1.0 新功能

### 🚀 性能优化
- Python 路径缓存，启动提速 30-50%
- RotatingFileHandler 日志系统（10MB × 3 自动轮转）
- 配置常量提取，减少硬编码魔法数字
- 启动流程优化，减少固定等待约 2.7 秒

### 🎨 UI/UX 升级
- 统一设计系统（CSS 变量：颜色/字体/间距/圆角/阴影）
- UI 组件库（Toast 通知、Dialog 弹窗、Loading 组件）
- 全新 Loading 过渡页（双环旋转动画 + 进度条）

### 💡 思考面板
- 右侧实时展示 AI 思考过程
- 支持折叠/展开，带打字机光标动画
- 切换会话时自动恢复历史思考内容

### ⚡ 原生 Toast 通知
- 权限请求和需要回复时，右下角弹出 Windows 原生通知
- 即使软件最小化到托盘也能看到
- 后台轮询检测权限请求，不依赖前端 JSBridge

### 📋 已有功能（hermes-agent 0.15.2 原生）
- **Kanban 多代理协作板** — 自动拆解任务、swarm 拓扑、每任务独立模型
- **检查点/回滚** — 文件修改前自动快照，一键恢复
- **定时任务（Cron）** — 自然语言安排任务，可附加技能
- **@文件引用** — 输入 `@` 自动补全工作区文件
- **持久化记忆** — 跨会话记忆用户偏好和项目上下文
- **技能系统** — 按需加载知识文档，兼容 agentskills.io
- **多平台接入** — 支持飞书/微信/企微/QQ/钉钉等 7 个平台

---

## 系统要求

| 组件 | 要求 |
|------|------|
| 操作系统 | Windows 10/11 64-bit |
| WebView2 | 安装包自动安装（Windows 11 自带） |
| 磁盘空间 | 500 MB+ |
| 内存 | 4 GB+（推荐 8 GB） |
| 网络 | 需要（AI API 调用） |

**不需要预装 Python、WSL 或其他任何软件。**

---

## 安装

### 方式一：下载安装包（推荐）

1. 从 [Releases](../../releases) 下载 `HermesWebUI_Setup_v3.1.0.exe`
2. 双击运行，按提示完成安装
3. 安装程序会自动安装 WebView2 运行时（如需要）
4. 桌面会出现快捷方式，双击即可启动

### 方式二：从源码构建

```bash
# 前置条件：安装 Inno Setup 6
# https://jrsoftware.org/isdl.php

git clone https://github.com/your-username/hermes-webui.git
cd hermes-webui

# 编译安装包
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" build_installer.iss

# 输出：dist\HermesWebUI_Setup_v3.1.0.exe
```

---

## 配置

首次启动后，需要配置 AI 模型的 API Key：

1. 打开 Hermes WebUI
2. 编辑 `.hermes/.env` 文件（安装目录下），填入你的 API Key

支持的模型提供商：

| 提供商 | 环境变量 | 说明 |
|--------|---------|------|
| 小米 MiMo | `XIAOMI_API_KEY` | 默认模型 |
| DeepSeek | `DEEPSEEK_API_KEY` | DeepSeek V4 |
| OpenAI | `OPENAI_API_KEY` | GPT 系列 |
| Anthropic | `ANTHROPIC_API_KEY` | Claude 系列 |
| 智谱 GLM | `ZHIPU_API_KEY` | GLM 系列 |
| Kimi | `KIMI_API_KEY` | Kimi 系列 |
| OpenRouter | `OPENROUTER_API_KEY` | 多模型路由 |
| 更多 | 参考 `.env.example` | 完整列表 |

---

## 项目结构

```
hermes-webui/
├── hermes_desktop.py          ← 桌面端主程序
├── hermes-webui-cn/           ← WebUI 前端 + Flask 后端
│   ├── static/                ← 前端资源（HTML/CSS/JS）
│   ├── api/                   ← REST API 路由
│   └── server.py              ← Flask 入口
├── hermes-agent/              ← Agent 核心引擎（含 .venv）
├── hermes-warden/             ← 任务守护进程
├── python-runtime/            ← 嵌入式 Python 3.12 运行时
├── build_installer.iss        ← Inno Setup 安装脚本
├── build_installer.bat        ← 构建辅助脚本
├── design-system.css          ← 设计系统变量
├── ui-components.css/js       ← UI 组件库
├── loading.html               ← Loading 过渡页
├── .env.example               ← API Key 配置模板
└── 使用说明.txt               ← 用户手册
```

---

## 技术栈

| 组件 | 技术 |
|------|------|
| 桌面窗口 | pywebview 6.2.1 (EdgeChromium / WebView2) |
| 前端 | HTML5 + JavaScript + CSS（无构建步骤） |
| 后端框架 | Flask (Python) |
| Agent 引擎 | Hermes Agent 0.16.0 |
| 安装包 | Inno Setup 6 (Pascal Script) |
| 嵌入式 Python | Python 3.12.10 |
| 系统托盘 | infi.systray + Win32 API |
| 单实例锁 | Win32 Named Mutex |
| 通知 | Windows.UI.Notifications (WinRT) |
| 压缩 | LZMA2 (Solid) |

---

## 常见问题

| 问题 | 解决方案 |
|------|---------|
| 安装后双击无反应 | 检查 `logs/hermes.log` 日志 |
| 页面空白 | 确认 WebView2 已安装（Windows 11 自带，Windows 10 需手动安装） |
| API 调用失败 | 在 `.hermes/.env` 中配置正确的 API Key |
| 端口被占用 | 应用会自动尝试其他端口 |

---

## 许可证

MIT License

`hermes-agent` 和 `hermes-webui-cn` 保留各自原始许可证。

---

## 致谢

- [Nous Research](https://nousresearch.com) — Hermes Agent 核心引擎
- [pywebview](https://pywebview.flowrl.com/) — 跨平台桌面窗口框架
- [Hermes Agent 中文社区](https://hermesagent.org.cn/) — 中文文档与社区支持

---

*版本 3.2.0 | 更新于 2026-06-05*
