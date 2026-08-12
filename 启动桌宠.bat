@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM Try hardcoded Python path first, then fallback to PATH
set "PYTHON=D:\Anaconda\envs\my_pytorch\pythonw.exe"
if not exist "%PYTHON%" set "PYTHON=D:\Anaconda\envs\my_pytorch\python.exe"
if exist "%PYTHON%" (
    start "" "%PYTHON%" main.py
    exit /b
)

REM Fallback: try pythonw / python from PATH
where pythonw >nul 2>&1 && (start "" pythonw main.py && exit /b)
where python >nul 2>&1 && (start "" python main.py && exit /b)

echo Python not found. Please edit this bat file to set the correct Python path.
pause
