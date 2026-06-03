@echo off
title SourceCast Worker
cd /d "%~dp0backend"
call .venv\Scripts\activate.bat
python worker.py
pause
