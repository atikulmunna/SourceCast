@echo off
title SourceCast Backend
cd /d C:\Users\Munna\Documents\GitSync\SourceCast\backend
call .venv\Scripts\activate.bat
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
pause
