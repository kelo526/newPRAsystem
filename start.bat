@echo off
rem ============================================================
rem  newPRAsystem 一键启动（重写版）
rem  修复：后端直接调用 pyenv Python 3.11.4 真实解释器，
rem        不依赖 pyenv shim / uvicorn PATH，中文路径下可用。
rem  窗口标题保留 newpra-backend / newpra-demo / newpra-web，
rem  stop.bat 可正常按标题停止服务。
rem ============================================================
setlocal

set "ROOT=%~dp0"
set "PY=C:\Users\h50013007\.pyenv\pyenv-win\versions\3.11.4\python.exe"

echo ============================================
echo   newPRAsystem 一键启动
echo ============================================
echo.

if not exist "%PY%" (
    echo [错误] 未找到 Python 解释器：
    echo        %PY%
    echo        请确认 pyenv 中已安装 Python 3.11.4，或修改本脚本中的 PY 变量。
    echo.
    pause
    exit /b 1
)

rem ---- [1/3] 后端（8000） ----
netstat -ano | findstr ":8000 " | findstr "LISTENING" >nul 2>&1
if errorlevel 1 (
    start "newpra-backend" cmd /k "cd /d "%ROOT%server" && "%PY%" -m uvicorn main:app --port 8000"
    echo [1/3] 后端已启动            http://localhost:8000
) else (
    echo [1/3] 后端已在运行，跳过   http://localhost:8000
)

rem ---- [2/3] 模拟业务系统（5173） ----
netstat -ano | findstr ":5173 " | findstr "LISTENING" >nul 2>&1
if errorlevel 1 (
    start "newpra-demo" cmd /k "cd /d "%ROOT%demo-target" && npm run dev"
    echo [2/3] 模拟业务系统已启动    http://localhost:5173 （admin / admin123）
) else (
    echo [2/3] 模拟系统已在运行，跳过 http://localhost:5173
)

rem ---- [3/3] 平台前端（5174） ----
netstat -ano | findstr ":5174 " | findstr "LISTENING" >nul 2>&1
if errorlevel 1 (
    start "newpra-web" cmd /k "cd /d "%ROOT%web" && npm run dev"
    echo [3/3] 平台前端已启动        http://localhost:5174
) else (
    echo [3/3] 前端已在运行，跳过   http://localhost:5174
)

echo.
echo ============================================
echo   全部服务就绪（首次启动请等待 10~20 秒）
echo.
echo   平台前端：      http://localhost:5174
echo   模拟业务系统：   http://localhost:5173 （admin / admin123）
echo   后端健康检查：   http://localhost:8000/api/health
echo   数据库：         SQLite（server\newpra.db，零配置）
echo ============================================
echo.
echo 提示：停止服务请运行 stop.bat
pause