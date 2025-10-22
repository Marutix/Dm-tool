@echo off
title Discord DM Tool - Installer
echo ========================================
echo    Discord DM Tool - Auto Installer
echo ========================================
echo.
echo This will install Python dependencies and run the DM tool.
echo.

:: Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH!
    echo Please install Python from https://python.org
    echo.
    pause
    exit /b 1
)

:: Check if pip is available
pip --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: pip is not available!
    echo Please ensure Python is installed correctly.
    echo.
    pause
    exit /b 1
)

echo Installing required packages...
echo.

:: Install packages
pip install discord.py colorama aiohttp

if errorlevel 1 (
    echo.
    echo ERROR: Failed to install one or more packages!
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================
echo    All dependencies installed successfully!
echo ========================================
echo.
echo Creating tokens.txt file if it doesn't exist...
if not exist tokens.txt (
    echo. > tokens.txt
    echo Created tokens.txt file.
    echo Please add your bot tokens to this file, separated by commas.
) else (
    echo tokens.txt already exists.
)

echo.
echo ========================================
echo    Starting Discord DM Tool...
echo ========================================
echo.
pause

:: Run the main script
python dm_tool.py

:: If the main script doesn't exist, create it
if errorlevel 1 (
    echo.
    echo ERROR: dm_tool.py not found!
    echo Creating the main script file...

    copy /y nul dm_tool.py >nul
    echo Creating the DM tool Python file...

    :: You would need to add the actual Python code here
    echo Please make sure dm_tool.py exists in the same directory.
    echo.
    pause
)
