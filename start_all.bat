@echo off
setlocal

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

set "PYTHON=%ROOT%\.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
  echo [ERROR] Python virtualenv not found: %PYTHON%
  exit /b 1
)

echo [1/3] Starting FastAPI backend on http://127.0.0.1:8000 ...
start "AI-IDS Backend" cmd /k ""%PYTHON%" -m uvicorn server.main:app --host 127.0.0.1 --port 8000"

timeout /t 2 /nobreak >nul

echo [2/3] Starting static frontend on http://127.0.0.1:8080 ...
start "AI-IDS Frontend" cmd /k ""%PYTHON%" -m http.server 8080 --directory "%ROOT%\web""

timeout /t 2 /nobreak >nul

echo [3/3] Opening dashboard in browser ...
start "" http://127.0.0.1:8080

echo Done. Backend: http://127.0.0.1:8000  Frontend: http://127.0.0.1:8080
endlocal
