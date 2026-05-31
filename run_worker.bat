@echo off
title SourceCast Worker
cd /d C:\Users\Munna\Documents\GitSync\SourceCast\backend
call .venv\Scripts\activate.bat
python worker.py
pause
