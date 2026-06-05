# Changelog

All notable changes to the Hermes WebUI Desktop Client will be documented in this file.

## [2.0] - 2026-05-16

### Added
- Initial release of Hermes WebUI Desktop Client for Windows
- pywebview-based native desktop wrapper with system tray integration
- Automatic Python environment detection and virtual environment setup
- Crash auto-recovery with rate limiting (3 restarts per 5 minutes)
- Window position/size memory across sessions
- System tray with context menu (Restart Service, Settings, Exit)
- Minimize-to-tray support with configurable behavior
- Custom cache directory management with data migration
- Auto-start with Windows (registry-based)
- Graceful shutdown with server process cleanup
- Settings persistence via settings.json
- Chinese language documentation and UI

### Dependencies
- hermes-agent v0.13.0 (Agent core engine)
- hermes-webui-cn v0.50.245 (Web UI backend + frontend)