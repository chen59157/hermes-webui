@echo off
set PYTHONPATH=
set PATH=%~dp0..\hermes-agent\.venv\Scripts;%PATH%
start "" "%~dp0..\hermes-agent\.venv\Scripts\pythonw.exe" "%~dp0server.py"