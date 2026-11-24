@echo off
title Lael Personal Assistant
cd /d "%~dp0backend"
if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found. Please run setup first.
    pause
    exit /b 1
)
echo Starting Lael Personal Assistant...
".venv\Scripts\python.exe" desktop.py
