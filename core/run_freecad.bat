@echo off
setlocal

REM Define possible locations for FreeCADCmd.exe
set "FREECAD_CMD_0=C:\Program Files\FreeCAD 1.0\bin\FreeCADCmd.exe"
set "FREECAD_CMD_0=C:\Program Files\FreeCAD 1.0\bin\FreeCADCmd.exe"
set "FREECAD_CMD_1=C:\Program Files\FreeCAD 0.21\bin\FreeCADCmd.exe"
set "FREECAD_CMD_2=C:\Program Files\FreeCAD 0.20\bin\FreeCADCmd.exe"
set "FREECAD_CMD_3=C:\Program Files\FreeCAD 0.19\bin\FreeCADCmd.exe"
set "FREECAD_CMD_4=C:\Program Files\FreeCAD\bin\FreeCADCmd.exe"

REM Check which one exists
if exist "%FREECAD_CMD_0%" (
    set "FREECAD_EXE=%FREECAD_CMD_0%"
) else if exist "%FREECAD_CMD_1%" (
    set "FREECAD_EXE=%FREECAD_CMD_1%"
) else if exist "%FREECAD_CMD_2%" (
    set "FREECAD_EXE=%FREECAD_CMD_2%"
) else if exist "%FREECAD_CMD_3%" (
    set "FREECAD_EXE=%FREECAD_CMD_3%"
) else if exist "%FREECAD_CMD_4%" (
    set "FREECAD_EXE=%FREECAD_CMD_4%"
) else (
    echo Error: FreeCADCmd.exe not found in standard locations.
    echo Please install FreeCAD or edit this script to point to your installation.
    exit /b 1
)

REM Execute the script passed as the first argument
"%FREECAD_EXE%" -P "%~dp0" "%~1"

endlocal
