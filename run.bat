@echo off
cd /d "%~dp0"
REM .pyw + pythonw = 검은 콘솔 창 없음
start "" pythonw "%~dp0main.pyw"
