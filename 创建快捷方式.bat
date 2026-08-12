@echo off
cd /d "%~dp0"
set "PY=D:\Anaconda\envs\my_pytorch\python.exe"
if exist "%PY%" ("%PY%" create_shortcut.py && exit /b)
where python >nul 2>&1 && (python create_shortcut.py && exit /b)
echo Python not found. Please install Python 3.10+.
pause
