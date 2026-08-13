@echo off
rem ============================================================
rem  vibekit CLI entry (Windows)
rem  Usage: vibekit [watch|dashboard|metrics|checkpoint|...] [args]
rem  Examples:
rem    vibekit watch            realtime status window (Ctrl+C exit)
rem    vibekit watch --plain
rem    vibekit metrics
rem    vibekit checkpoint status
rem    vibekit dashboard --html dashboard.html
rem ============================================================
setlocal
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
set "VIBEKIT_SCRIPTS=%USERPROFILE%\.pi\agent\skills\vibekit\scripts"

rem no arg or watch/w -> realtime window
if "%~1"=="" goto :watch
if "%~1"=="watch" goto :watch
if "%~1"=="w" goto :watch
if "%~1"=="open-watch" goto :openwatch
if "%~1"=="ow" goto :openwatch
if "%~1"=="task" goto :taskcmd

rem other: vibekit <script> <args...>
if exist "%VIBEKIT_SCRIPTS%\%~1.py" (
    python "%VIBEKIT_SCRIPTS%\%~1.py" %2 %3 %4 %5 %6 %7 %8 %9
    goto :eof
)

echo [vibekit] unknown command: %~1
echo available: watch ^| dashboard ^| metrics ^| summary ^| checkpoint ^| vibe_state ^| security ^| adr ^| init
goto :eof

:watch
python "%VIBEKIT_SCRIPTS%\dashboard.py" --watch %2 %3 %4 %5
goto :eof

:openwatch
python "%VIBEKIT_SCRIPTS%\open_watch.py" %2 %3 %4 %5 %6 %7
goto :eof

:taskcmd
python "%VIBEKIT_SCRIPTS%	ask.py" %2 %3 %4 %5 %6 %7
goto :eof
endlocal
