@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo == UPDATE ==
git pull
echo.
cmd
