@echo off
rem Fleet node launcher — double-click to join the mesh. No install, no admin.
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
    echo [node] Python not found. Install Python 3.8+ from python.org
    echo [node] and check "Add python.exe to PATH" during setup.
    pause
    exit /b 1
)
python run_node.py --config node_config.json
echo.
echo [node] stopped.
pause
