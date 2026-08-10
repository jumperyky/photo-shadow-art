@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

rem ============================================================
rem  Photo Shadow Art - 初回セットアップ (Windows)
rem
rem    setup.bat  … .venv を作って Python / npm の依存を入れる
rem
rem  完了後は start.bat で起動できる。
rem  git pull で更新したあとにもう一度実行すると依存を入れ直せる。
rem
rem  注意: for /f の in(...) の中や if(...) ブロックの中では
rem  丸カッコと > が cmd のパーサーに食われるため、
rem  Python のワンライナーはそれらの外に置いている。
rem ============================================================

echo.
echo ============================================
echo   Photo Shadow Art セットアップ
echo ============================================
echo.

rem --- Python を探す (python → py -3 の順) --------------------
set "PY="
python --version >nul 2>&1 && set "PY=python"
if defined PY goto :py_found
py -3 --version >nul 2>&1 && set "PY=py -3"
if defined PY goto :py_found
goto :no_python
:py_found

rem --- バージョン確認 (3.10 以上) -----------------------------
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)"
if errorlevel 1 goto :old_python

set "PYVER=?"
for /f "tokens=2" %%v in ('%PY% --version 2^>^&1') do set "PYVER=%%v"
echo [1/5] Python %PYVER% を使います

rem --- 仮想環境 -----------------------------------------------
if exist ".venv\Scripts\python.exe" goto :venv_ready
echo [2/5] 仮想環境 .venv を作成しています...
%PY% -m venv .venv
if errorlevel 1 goto :venv_failed
goto :venv_done
:venv_ready
echo [2/5] 既存の .venv を使います
:venv_done

set "PYEXE=%~dp0.venv\Scripts\python.exe"

rem --- Python の依存 ------------------------------------------
echo [3/5] Python の依存をインストールしています（数分かかります）...
"%PYEXE%" -m pip install --upgrade pip --quiet
"%PYEXE%" -m pip install -r backend\requirements.txt --quiet
if errorlevel 1 goto :pip_failed

rem --- Node の確認 --------------------------------------------
where npm >nul 2>&1
if errorlevel 1 goto :no_npm

rem --- フロントエンドの依存 -----------------------------------
echo [4/5] フロントエンドの依存をインストールしています...
pushd frontend
call npm install --no-audit --no-fund --loglevel=error
if errorlevel 1 goto :npm_failed_pop
popd

rem --- 動作確認 -----------------------------------------------
echo [5/5] 動作確認をしています...
"%PYEXE%" -c "import fastapi, uvicorn, shapely, trimesh, mapbox_earcut"
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


rem ==================== エラー処理 ====================
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
