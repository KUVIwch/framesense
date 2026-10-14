@echo off
cd /d "%~dp0"
echo 正在启动 FrameSense Web 应用...
echo 启动后请访问 http://localhost:8501
.venv\Scripts\python.exe -m streamlit run framesense/web/app.py --server.headless true --server.port 8501 --server.address 127.0.0.1
pause
