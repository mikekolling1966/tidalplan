@echo off
cd /d "%~dp0"
if not exist .env copy .env.example .env && echo Created .env - add your UKHO_API_KEY
pip install -q -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
