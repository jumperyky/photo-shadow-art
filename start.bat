@echo off
setlocal
cd /d "%~dp0"

rem ============================================================
rem  Photo Shadow Art - launcher for Windows
rem
rem    start.bat  : start the API and the UI in separate windows,
rem                 then open the browser once the UI responds
rem
rem  Run setup.bat first.
rem  To stop, close the two windows that open, or press Ctrl+C.
rem
rem  To change ports, from cmd:
rem    set PORT_API=8001 and set PORT_UI=3100 before running.
rem
rem  NOTE on encoding: saved in CP932, must NOT call chcp 65001.
rem  See the comment in setup.bat for the reason.
rem ============================================================

if not defined PORT_API set "PORT_API=8000"
if not defined PORT_UI  set "PORT_UI=3000"

set "PYEXE=%~dp0.venv\Scripts\python.exe"

rem --- check that setup.bat has been run ----------------------
if not exist "%PYEXE%" goto :no_venv
if not exist "frontend\node_modules" goto :no_node_modules

"%PYEXE%" -c "import fastapi, uvicorn, shapely, trimesh, mapbox_earcut" 2>nul
if errorlevel 1 goto :no_deps

rem --- port check. connect_ex 0 means something is listening --
"%PYEXE%" -c "import socket,sys; sys.exit(1 if socket.socket().connect_ex(('127.0.0.1',%PORT_API%))==0 else 0)"
if errorlevel 1 goto :api_port_busy

"%PYEXE%" -c "import socket,sys; sys.exit(1 if socket.socket().connect_ex(('127.0.0.1',%PORT_UI%))==0 else 0)"
if errorlevel 1 goto :ui_port_busy

rem --- launch -------------------------------------------------
echo.
echo   API を起動しています  http://127.0.0.1:%PORT_API%
start "Photo Shadow Art - API" /d "%~dp0backend" cmd /k ""%PYEXE%" -m uvicorn app.main:app --reload --port %PORT_API%"

echo   UI  を起動しています  http://localhost:%PORT_UI%
start "Photo Shadow Art - UI" /d "%~dp0frontend" cmd /k "set "API_BASE_URL=http://127.0.0.1:%PORT_API%" && set "PORT=%PORT_UI%" && npm run dev"

rem --- wait for the UI to answer, then open the browser -------
echo.
echo   起動を待っています...
set /a TRIES=0
:wait_ui
set /a TRIES+=1
if %TRIES% gtr 40 goto :ui_timeout
"%PYEXE%" -c "import socket,sys; sys.exit(0 if socket.socket().connect_ex(('127.0.0.1',%PORT_UI%))==0 else 1)"
if not errorlevel 1 goto :ui_ready
timeout /t 1 /nobreak >nul
goto :wait_ui

:ui_ready
echo.
echo ============================================
echo   起動しました
echo.
echo   http://localhost:%PORT_UI%
echo.
echo   停止するときは開いた2つのウィンドウを閉じてください
echo ============================================
start "" "http://localhost:%PORT_UI%"
timeout /t 3 /nobreak >nul
exit /b 0

:ui_timeout
echo.
echo [警告] UI が時間内に応答しませんでした。
echo        「Photo Shadow Art - UI」のウィンドウに
echo        エラーが出ていないか確認してください。
echo.
pause
exit /b 1


rem ==================== error handlers ====================
:no_venv
echo [エラー] .venv がありません。
echo         先に setup.bat をダブルクリックしてください。
goto :fail

:no_node_modules
echo [エラー] frontend\node_modules がありません。
echo         先に setup.bat をダブルクリックしてください。
goto :fail

:no_deps
echo [エラー] Python の依存が足りません。
echo         setup.bat をもう一度実行してください。
goto :fail

:api_port_busy
echo [エラー] ポート %PORT_API% は使用中です。
echo.
echo   前回の「Photo Shadow Art - API」のウィンドウが
echo   残っていませんか。閉じてからもう一度実行してください。
goto :fail

:ui_port_busy
echo [エラー] ポート %PORT_UI% は使用中です。
echo.
echo   前回の「Photo Shadow Art - UI」のウィンドウが
echo   残っていませんか。閉じてからもう一度実行してください。
goto :fail

:fail
echo.
pause
exit /b 1
