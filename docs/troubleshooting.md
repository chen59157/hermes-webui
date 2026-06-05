# 故障排除手册

> 常见问题与解决方案，按影响程度排序。

---

## 1. 启动故障

### 1.1 双击 bat 文件闪退

**症状**：双击 `启动 Hermes WebUI.bat` 后命令行窗口一闪而过，程序未启动。

**原因**：系统未安装 Python 或 Python 未加入 PATH。

**解决方案**：

1. 下载并安装 [Python 3.10+](https://www.python.org/downloads/)
2. 安装时务必勾选 **"Add Python to PATH"**
3. 重新打开命令行验证：`python --version`

---

### 1.2 虚拟环境创建失败

**症状**：启动时报 `venv` 或 `pip` 相关错误。

**解决方案**：

```powershell
# 手动创建虚拟环境
cd "C:\Users\<用户名>\Hermes WebUI\hermes-agent"
python -m venv .venv --clear
.venv\Scripts\activate
pip install -e .
deactivate
```

---

### 1.3 找不到 Python 解释器

**症状**：日志显示 `ERROR: pywebview not installed` 或 `找不到 Python xxx`

**解决方案**：

修改 `启动 Hermes WebUI.bat` 中的 Python 路径为系统实际路径：

```batch
"C:\Users\<用户名>\AppData\Local\Programs\Python\Python312\python.exe" "%~dp0hermes_desktop.py"
```

---

## 2. 运行时故障

### 2.1 页面显示 "You are offline"

**症状**：窗口打开后显示离线状态，无法正常使用。

**排查步骤**：

1. 检查后端进程是否运行：
```powershell
netstat -ano | findstr :8787
```

2. 查看后端日志：
```powershell
Get-Content "C:\Users\<用户名>\Hermes WebUI\.hermes\logs\server.log" -Tail 50
```

3. 手动启动后端测试：
```powershell
cd "C:\Users\<用户名>\Hermes WebUI\hermes-webui-cn"
.venv\Scripts\python.exe server.py
```

**常见子问题**：

| 子问题 | 症状 | 解决方案 |
|--------|------|---------|
| Agent 启动失败 | `ImportError` / `ModuleNotFoundError` | 重新安装 `hermes-agent` 依赖 |
| API Key 缺失 | 调用 LLM 时报认证错误 | 在设置页面配置 API Key |
| 端口冲突 | `Address already in use` | 修改 `settings.json` 中 `port` 值 |

### 2.2 端口被占用

**症状**：日志显示 `端口 8787 被占用`。

**解决方案**：

```powershell
# 查找占用端口的进程
netstat -ano | findstr :8787

# 终止占用进程（替换 PID）
taskkill /F /PID <PID>

# 或手动修改端口
# 编辑 settings.json: "port": 8788
```

### 2.3 频繁崩溃重启

**症状**：程序反复崩溃并自动重启。

**原因**：后端服务持续异常退出，触发了崩溃恢复机制。

**限制**：系统限制 5 分钟内最多重启 3 次，超出后不再自动重启。

**排查**：

1. 查看 `hermes.log` 确认崩溃模式
2. 查看 `.hermes/logs/server.log` 定位后端错误
3. 检查系统资源（内存/磁盘）

---

## 3. 设置相关问题

### 3.1 开机自启动不生效

**排查步骤**：

1. 确认已在设置中开启「开机自启动」
2. 检查注册表项：
```powershell
Get-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name "HermesWebUI"
```

3. 手动添加：
```powershell
# 方式一：放置快捷方式到启动文件夹
# 按 Win+R → shell:startup → 放入快捷方式

# 方式二：注册表
$path = "C:\Users\<用户名>\Hermes WebUI\启动 Hermes WebUI.bat"
Set-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name "HermesWebUI" -Value $path
```

### 3.2 缓存目录迁移失败

**症状**：修改缓存目录后数据未迁移。

**手动迁移**：

```powershell
# 停止程序后执行
$source = "C:\Users\<用户名>\Hermes WebUI\.hermes"
$dest = "D:\HermesCache"

# 复制数据
robocopy $source $dest /E /COPYALL

# 更新 settings.json
# "cache_dir": "D:\\HermesCache"
```

---

## 4. API 相关故障

### 4.1 API Key 无效

**症状**：对话时报认证错误。

**解决方案**：

1. 确认 API Key 正确（无多余空格）
2. 在 WebUI 设置页面重新配置
3. 检查 Provider 服务状态
4. 确认账户余额/配额充足

### 4.2 请求超时

**症状**：长时间等待无响应。

**排查**：

1. 检查网络连接稳定性
2. 尝试切换其他 LLM Provider
3. 检查防火墙/代理设置是否拦截

---

## 5. 完全重置

当以上所有方法均无效时，执行完全重置：

```powershell
# 1. 停止所有 Hermes 进程
taskkill /F /IM python.exe /FI "WINDOWTITLE eq Hermes*"

# 2. 备份数据（可选）
Copy-Item "C:\Users\<用户名>\Hermes WebUI\.hermes" "C:\Users\<用户名>\Desktop\hermes_backup" -Recurse

# 3. 删除缓存和设置
Remove-Item "C:\Users\<用户名>\Hermes WebUI\.hermes" -Recurse -Force
Remove-Item "C:\Users\<用户名>\Hermes WebUI\settings.json" -Force

# 4. 重建虚拟环境
cd "C:\Users\<用户名>\Hermes WebUI\hermes-agent"
Remove-Item .venv -Recurse -Force
python -m venv .venv
.venv\Scripts\activate
pip install -e .
deactivate

cd ..\hermes-webui-cn
Remove-Item .venv -Recurse -Force
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
deactivate

# 5. 重新启动程序
cd ..
.\启动 Hermes WebUI.bat
```

---

## 6. 日志位置速查

| 日志 | 路径 | 用途 |
|------|------|------|
| 桌面客户端 | `hermes.log` | 启动流程、端口检测、进程管理 |
| 后端服务 | `.hermes/logs/server.log` | HTTP 请求、Agent 执行 |
| Python 错误 | `server_err.txt` (工作空间) | 未捕获的 Python 异常 |

---

## 7. 获取帮助

1. 查看 [GitHub Issues](https://github.com/your-org/hermes-webui-desktop/issues)
2. 提交新 Issue 时附上：
   - 操作系统版本：`winver`
   - Python 版本：`python --version`
   - 日志文件（脱敏后）：`hermes.log` 和 `.hermes/logs/server.log`
   - 复现步骤

---

*更新于 2026-05-24*