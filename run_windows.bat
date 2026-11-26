@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo             AICompanyOS Launcher
echo ==========================================
echo.

where python >nul 2>nul
if %errorlevel%==0 (
    echo Starting AICompanyOS with Python...
    python -m streamlit run app.py
    if not errorlevel 1 goto :end
)

where py >nul 2>nul
if %errorlevel%==0 (
    echo Trying Python launcher...
    py -3 -m streamlit run app.py
    if not errorlevel 1 goto :end
)

echo.
echo Could not start Streamlit.
echo Install dependencies with:
echo   python -m pip install -r requirements.txt
echo Then run this file again.
echo.
pause

:end
endlocal
