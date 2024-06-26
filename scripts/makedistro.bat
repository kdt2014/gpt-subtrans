call envsubtrans/scripts/activate
python.exe -m pip install --upgrade pip
pip install pywin32-ctypes
pip install --upgrade pyinstaller
pip install --upgrade -r requirements.txt
pip install --upgrade openai
pip install --upgrade google.generativeai
pip install --upgrade anthropic

python.exe tests/unit_tests.py
if %errorlevel% neq 0 (
    echo Unit tests failed. Exiting...
    exit /b %errorlevel%
)

pyinstaller --noconfirm --additional-hooks-dir="PySubtitleHooks" --add-data "theme/*;theme/" --add-data "assets/*;assets/" --add-data "instructions*;instructions/" --add-data "LICENSE;." "scripts/gui-subtrans.py"
