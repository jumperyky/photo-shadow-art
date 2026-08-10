@echo off
setlocal
cd /d "%~dp0"

rem ============================================================
rem  Photo Shadow Art - update to the latest version on Windows
rem
rem    update.bat  : git pull, then reinstall dependencies
rem
rem  node_modules and .venv are built per machine, so refreshing
rem  them after pulling new source keeps things consistent.
rem
rem  NOTE on encoding: saved in CP932, must NOT call chcp 65001.
rem  See the comment in setup.bat for the reason.
rem ============================================================

echo.
echo ============================================
echo   Photo Shadow Art 更新
echo ============================================
echo.

where git >nul 2>&1
if errorlevel 1 goto :no_git

rem --- refuse to pull over uncommitted work -------------------
git diff --quiet
if errorlevel 1 goto :dirty
git diff --cached --quiet
if errorlevel 1 goto :dirty

set "BRANCH="
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


rem ==================== error handlers ====================
:no_git
echo [エラー] git が見つかりません。
echo         https://git-scm.com/download/win
goto :fail

:dirty
echo [中止] コミットしていない変更があります。
echo.
echo   先に変更を退避するかコミットしてください。
echo   退避する場合は  git stash  を実行します。
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
