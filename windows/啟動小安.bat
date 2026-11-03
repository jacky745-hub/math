@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
title 小安 Xiao-An 本機版
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 xiaoan_local.py
  goto end
)
where python >nul 2>nul
if %errorlevel%==0 (
  python xiaoan_local.py
  goto end
)
echo.
echo 找不到 Python。請到 https://www.python.org/downloads/ 安裝 Python 3（安裝時勾選 Add python.exe to PATH），再重新執行這個檔案。
:end
pause
