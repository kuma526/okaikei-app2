@echo off
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
echo ========================================================
echo  個人事業主 出納帳 Webアプリケーション
echo ========================================================
echo.
echo アプリケーションを起動しています...
echo.

cd /d "%~dp0"
"%~dp0.venv\Scripts\python.exe" main.py

pause

