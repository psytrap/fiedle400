@echo off
rem PO-400 console launcher.
rem
rem Makes `po400` usable as a bare command in this window WITHOUT touching PATH:
rem doskey registers an alias for this console session only. Nothing is written
rem to the registry and nothing persists after the window closes.
rem
rem %~dp0 is the directory holding this script (and po400.exe), with a trailing
rem backslash. It is quoted so a user profile containing spaces still works.

title PO-400 Oximeter
doskey po400="%~dp0po400.exe" $*

echo.
echo   PO-400 Oximeter
echo   ---------------
echo   Type  po400 --help      to see all commands.
echo   Type  po400 info        to read the connected device.
echo.
echo   Files are saved in the current folder:
echo     %CD%
echo.
