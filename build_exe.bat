@echo off
rem Builds "dist\Snakes and Ladders.exe" (requires: pip install pyinstaller pillow)
cd /d "%~dp0"
python make_icon.py snake.ico || exit /b 1
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name "Snakes and Ladders" ^
    --icon snake.ico ^
    --add-data "snake.ico;." ^
    main.py || exit /b 1
echo.
echo Done: dist\Snakes and Ladders.exe
