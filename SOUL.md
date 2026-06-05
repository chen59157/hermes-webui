# Hermes-WebUI SOUL

## Warden 触发词

进度查询：用户说"进度"或"咋样了"或"后台任务"时 →
  读 $WARDEN_HOME/status.json → 格式化为面板回复

Warden 体检：用户说"warden状态"或"守护进程"时 →
  运行 python warden_daemon.py --doctor → 展示体检结果

## 配置

- gateway_timeout: 从 cli-config.yaml 的 gateway.timeout_seconds 读取