@echo off
setlocal
cd /d "%~dp0"

rem ============================================================
rem  Photo Shadow Art - first time setup for Windows
rem
rem    setup.bat  : create .venv, install Python and npm deps
rem
rem  Run start.bat afterwards.
rem  Run this again after a git pull to refresh dependencies.
rem
rem  NOTE on encoding: this file is saved in CP932 and must NOT
rem  call "chcp 65001". Switching cmd.exe to UTF-8 makes it lose
rem  track of its byte offset inside a batch file that contains
rem  multi byte characters, and it starts executing the middle of
rem  comment lines. Keep comments ASCII, messages CP932.
rem
rem  NOTE on the parser: cmd eats round brackets and redirect signs
rem  inside for /f and if blocks, so the Python one liners stay
rem  outside them and every branch is written with goto.
rem ============================================================

echo.
echo ============================================
echo   Photo Shadow Art セットアップ
echo ============================================
echo.

rem --- locate Python: try "python" then "py -3" ---------------
set "PY="
python --version >nul 2>&1 && set "PY=python"
if defined PY goto :py_found
py -3 --version >nul 2>&1 && set "PY=py -3"
if defined PY goto :py_found
goto :no_python
:py_found

rem --- require 3.10 or newer ----------------------------------
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)"
if errorlevel 1 goto :old_python

set "PYVER=?"
for /f "tokens=2" %%v in ('%PY% --version 2^>^&1') do set "PYVER=%%v"
echo [1/5] Python %PYVER% を使います

rem --- virtual environment ------------------------------------
if exist ".venv\Scripts\python.exe" goto :venv_ready
echo [2/5] 仮想環境 .venv を作成しています...
%PY% -m venv .venv
if errorlevel 1 goto :venv_failed
goto :venv_done
:venv_ready
echo [2/5] 既存の .venv を使います
:venv_done

set "PYEXE=%~dp0.venv\Scripts\python.exe"

rem --- Python dependencies ------------------------------------
echo [3/5] Python の依存をインストールしています。数分かかります...
"%PYEXE%" -m pip install --upgrade pip --quiet
"%PYEXE%" -m pip install -r backend\requirements.txt --quiet
if errorlevel 1 goto :pip_failed

rem --- Node ---------------------------------------------------
where npm >nul 2>&1
if errorlevel 1 goto :no_npm

rem --- frontend dependencies ----------------------------------
echo [4/5] フロントエンドの依存をインストールしています...
pushd frontend
call npm install --no-audit --no-fund --loglevel=error
if errorlevel 1 goto :npm_failed_pop
popd

rem --- smoke test ---------------------------------------------
echo [5/5] 動作確認をしています...
"%PYEXE%" -c "import fastapi, uvicorn, shapely, trimesh, mapbox_earcut, manifold3d"
if errorlevel 1 goto :verify_failed

echo.
echo ============================================
echo   セットアップ完了
echo.
echo   start.bat をダブルクリックすると起動します
echo ============================================
echo.
pause
exit /b 0


rem ==================== error handlers ====================
:no_python
echo [エラー] Python が見つかりません。
echo.
echo   Python 3.10 以上をインストールし、インストーラの
echo   「Add python.exe to PATH」にチェックを入れてください。
echo   https://www.python.org/downloads/windows/
goto :fail

:old_python
echo [エラー] Python 3.10 以上が必要です。今の Python は:
%PY% --version
goto :fail

:venv_failed
echo [エラー] 仮想環境 .venv の作成に失敗しました。
goto :fail

:pip_failed
echo [エラー] Python の依存のインストールに失敗しました。
echo         上に出ているメッセージを確認してください。
goto :fail

:no_npm
echo [エラー] npm が見つかりません。
echo.
echo   Node.js 20 以上をインストールしてください。
echo   https://nodejs.org/
goto :fail

:npm_failed_pop
popd
echo [エラー] npm install に失敗しました。
goto :fail

:verify_failed
echo [エラー] 依存は入りましたが読み込みに失敗しました。
echo         上に出ているメッセージを確認してください。
goto :fail

:fail
echo.
pause
exit /b 1
