@echo off
setlocal enabledelayedexpansion

if not exist scripts (
    echo This script must be run from the root directory of the project.
    exit /b 1
)

echo Checking if Python 3 is installed...
python --version >nul 2>&1
if errorlevel 1 (
    echo Python 3 not found. Please install Python 3 and try again.
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version') do set PYTHON_VERSION=%%i
set MIN_VERSION=3.10.0

python -c "import sys; sys.exit(not (tuple(map(int, '%PYTHON_VERSION%'.split('.'))) >= tuple(map(int, '%MIN_VERSION%'.split('.')))))"
if errorlevel 1 (
    echo Detected Python version is less than 3.10.0. Please upgrade your Python version.
    exit /b 1
)

echo Python version is compatible.

echo Checking if "envsubtrans" folder exists...
if exist envsubtrans (
    echo "envsubtrans" folder already exists.
    set /p user_choice=Do you want to perform a clean install? This will delete the existing environment. [Y/N]:
    if /i "!user_choice!"=="Y" (
        echo Performing a clean install...
        rmdir /s /q envsubtrans
        del *.cmd
        if exist .env del .env
        python -m venv envsubtrans
        call envsubtrans\Scripts\activate.bat
        echo Installing requirements from "requirements.txt"...
        pip install -r requirements.txt
    ) else if /i "!user_choice!"=="N" (
        call envsubtrans\Scripts\activate.bat
        echo Updating requirements in the existing environment...
        pip install -U -r requirements.txt
    ) else (
        echo Invalid choice. Exiting installation.
        exit /b 1
    )
) else (
    echo Creating and activating virtual environment "envsubtrans"...
    python -m venv envsubtrans
    call envsubtrans\Scripts\activate.bat
    echo Installing requirements from "requirements.txt"...
    pip install -r requirements.txt
)

echo Generating command scripts...
call scripts\generate-cmd.bat gui-subtrans
call scripts\generate-cmd.bat llm-subtrans

exit /b 0
