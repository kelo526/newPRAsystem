@echo off
rem ============================================================
rem  newPRAsystem 一键启动
rem  默认：后端(8000) + nginx 生产前端(9080) —— 主入口
rem  start.bat dev 额外启动 Vite 开发前端(5174) + 模拟业务系统(5173)
rem  修复：直接调用 pyenv Python 3.11.4 真实解释器，中文路径可用
rem  窗口标题：newpra-backend / newpra-nginx / newpra-web / newpra-demo
rem           （stop.bat 按标题停止）
rem ============================================================
setlocal

set "ROOT=%~dp0"
set "PY=C:\Users\h50013007\.pyenv\pyenv-win\versions\3.11.4\python.exe"
set "DEV=0"
if /i "%~1"=="dev" set "DEV=1"

echo ============================================
echo   newPRAsystem 一键启动
if "%DEV%"=="1" echo   （开发模式：额外启动 Vite 与模拟业务系统）
echo ============================================
echo.

if not exist "%PY%" (
    echo [错误] 未找到 Python 解释器：%PY%
    echo        请确认 pyenv 中已安装 Python 3.11.4，或修改本脚本的 PY 变量。
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

rem ---- [2/3] nginx 生产前端（9080，主入口） ----
if not exist "%ROOT%web\dist\index.html" (
    echo [2/3] 首次发布：构建前端产物（约 30 秒）...
    pushd "%ROOT%web"
    call npm run build
    popd
)
netstat -ano | findstr ":9080 " | findstr "LISTENING" >nul 2>&1
if errorlevel 1 (
    start "newpra-nginx" /MIN cmd /c "cd /d "%ROOT%nginx-1.28.0" && nginx.exe"
    echo [2/3] nginx 前端已启动      http://localhost:9080  （主入口）
) else (
    echo [2/3] nginx 前端已在运行，跳过 http://localhost:9080
)

rem ---- [3/3] 开发模式（可选）：Vite 5174 + 模拟业务系统 5173 ----
if "%DEV%"=="1" goto devmode
echo [3/3] 开发模式未启用（Vite/模拟系统不启动；体验模拟流程请运行 start.bat dev）
goto summary

:devmode
netstat -ano | findstr ":5173 " | findstr "LISTENING" >nul 2>&1
if errorlevel 1 (
    start "newpra-demo" cmd /k "cd /d "%ROOT%demo-target" && npm run dev"
    echo [3/3] 模拟业务系统已启动    http://localhost:5173 （admin / admin123）
) else (
    echo [3/3] 模拟系统已在运行，跳过 http://localhost:5173
)
netstat -ano | findstr ":5174 " | findstr "LISTENING" >nul 2>&1
if errorlevel 1 (
    start "newpra-web" cmd /k "cd /d "%ROOT%web" && npm run dev"
    echo [+]   Vite 开发前端已启动   http://localhost:5174
) else (
    echo [+]   Vite 开发前端已在运行，跳过 http://localhost:5174
)

:summary
echo.
echo ============================================
echo   全部服务就绪（首次启动请等待 10~20 秒）
echo.
echo   平台前端（主入口）： http://localhost:9080
echo   后端健康检查：       http://localhost:8000/api/health
if "%DEV%"=="1" (
echo   Vite 开发前端：      http://localhost:5174
echo   模拟业务系统：       http://localhost:5173 （admin / admin123）
)
echo   数据库：             SQLite（server\newpra.db，零配置）
echo ============================================
echo.
echo 提示：停止服务请运行 stop.bat
pause