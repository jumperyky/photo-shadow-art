@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

rem ============================================================
rem  Photo Shadow Art - 起動 (Windows)
rem
rem    start.bat  … API(:8000) と UI(:3000) を別ウィンドウで起動し、
rem                 準備ができたらブラウザを開く
rem
rem  初回は先に setup.bat を実行すること。
rem  停止するときは開いた2つのウィンドウを閉じる(または Ctrl+C)。
rem
rem  ポートを変えたい場合:
rem    set PORT_API=8001 ^&^& set PORT_UI=3100 ^&^& start.bat
rem ============================================================

if not defined PORT_API set "PORT_API=8000"
if not defined PORT_UI  set "PORT_UI=3000"

set "PYEXE=%~dp0.venv\Scripts\python.exe"

rem --- セットアップ済みかの確認 -------------------------------
if not exist "%PYEXE%" goto :no_venv
if not exist "frontend\node_modules" goto :no_node_modules

"%PYEXE%" -c "import fastapi, uvicorn, shapely, trimesh, mapbox_earcut" 2>nul
if errorlevel 1 goto :no_deps

rem --- ポートの空き確認 ---------------------------------------
rem connect_ex が 0 = 誰かが待ち受けている = 使用中
"%PYEXE%" -c "import socket,sys; sys.exit(1 if socket.socket().connect_ex(('127.0.0.1',%PORT_API%))==0 else 0)"
if errorlevel 1 goto :api_port_busy

"%PYEXE%" -c "import socket,sys; sys.exit(1 if socket.socket().connect_ex(('127.0.0.1',%PORT_UI%))==0 else 0)"
if errorlevel 1 goto :ui_port_busy

rem --- 起動 ---------------------------------------------------
echo.
echo   API を起動しています  http://127.0.0.1:%PORT_API%
start "Photo Shadow Art - API" /d "%~dp0backend" cmd /k ""%PYEXE%" -m uvicorn app.main:app --reload --port %PORT_API%"

echo   UI  を起動しています  http://localhost:%PORT_UI%
start "Photo Shadow Art - UI" /d "%~dp0frontend" cmd /k "set "API_BASE_URL=http://127.0.0.1:%PORT_API%" && set "PORT=%PORT_UI%" && npm run dev"

rem --- UI が応答するまで待ってからブラウザを開く ---------------
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
echo        「Photo Shadow Art - UI」のウィンドウにエラーが出ていないか
echo        確認してください。
echo.
pause
exit /b 1


rem ==================== エラー処理 ====================
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
echo   前回の「Photo Shadow Art - API」のウィンドウが残っていませんか。
echo   残っていれば閉じてから、もう一度 start.bat を実行してください。
goto :fail

:ui_port_busy
echo [エラー] ポート %PORT_UI% は使用中です。
echo.
echo   前回の「Photo Shadow Art - UI」のウィンドウが残っていませんか。
echo   残っていれば閉じてから、もう一度 start.bat を実行してください。
goto :fail

:fail
echo.
pause
exit /b 1
