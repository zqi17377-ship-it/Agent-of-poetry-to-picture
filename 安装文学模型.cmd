@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo 请先运行 安装依赖.cmd。
  pause
  exit /b 1
)
echo 正在安装本机文学模型，首次需要下载约 2.5GB。
".venv\Scripts\python.exe" scripts\setup_local_text.py
pause
