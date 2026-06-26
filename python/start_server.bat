@echo off
cd /d c:\Users\Lenovo\Desktop\灵境制造（上线版）\python
python -m uvicorn app.main:app --host 127.0.0.1 --port 8765 --log-level info
