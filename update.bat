@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

rem ============================================================
rem  Photo Shadow Art - 最新版に更新 (Windows)
rem
rem    update.bat  … git pull してから依存を入れ直す
rem
rem  依存(node_modules / .venv)は端末ごとに作るものなので、
rem  ソースを更新したらこれを実行しておくと確実。
rem ============================================================

echo.
echo ============================================
echo   Photo Shadow Art 更新
echo ============================================
echo.

where git >nul 2>&1
if errorlevel 1 goto :no_git

rem --- 未コミットの変更があれば止める -------------------------
git diff --quiet
if errorlevel 1 goto :dirty
git diff --cached --quiet
if errorlevel 1 goto :dirty

for /f "delims=" %%b in ('git rev-parse --abbrev-ref HEAD') do set "BRANCH=%%b"
echo 現在のブランチ: %BRANCH%
echo.

echo --- git pull ---
git pull origin %BRANCH%
if errorlevel 1 goto :pull_failed

echo.
echo --- 依存を更新します ---
call "%~dp0setup.bat"
exit /b %errorlevel%


rem ==================== エラー処理 ====================
:no_git
echo [エラー] git が見つかりません。
echo         https://git-scm.com/download/win
goto :fail

:dirty
echo [中止] コミットしていない変更があります。
echo.
echo   先に変更を退避するかコミットしてください。
echo   退避する場合:  git stash
echo.
git status --short
goto :fail

:pull_failed
echo [エラー] git pull に失敗しました。
echo         上に出ているメッセージを確認してください。
goto :fail

:fail
echo.
pause
exit /b 1
