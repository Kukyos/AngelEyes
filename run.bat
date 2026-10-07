@echo off
setlocal enabledelayedexpansion

set "PROJECT_ROOT=%~dp0"
cd /d "%PROJECT_ROOT%"

set "VENV_DIR=%PROJECT_ROOT%.venv"
set "PYTHON_BIN=%VENV_DIR%\Scripts\python.exe"
set "REQUIREMENTS=%PROJECT_ROOT%requirements.txt"
set "ENV_FILE=%PROJECT_ROOT%.env"
set "ENV_EXAMPLE=%PROJECT_ROOT%.env.example"
set "MODELS_DIR=%PROJECT_ROOT%models"
set "YOLO_WEIGHTS=%MODELS_DIR%\yolo11m-pose.pt"

for %%i in ("%PROJECT_ROOT%") do set "PROJECT_ROOT=%%~fi"
for %%i in ("%VENV_DIR%") do set "VENV_DIR=%%~fi"

call :log "Project root: %PROJECT_ROOT%"

where uv >nul 2>nul
if %errorlevel% equ 0 (
    set "UV_CMD=uv"
    call :log "Found uv in PATH"
) else if exist "%USERPROFILE%\.local\bin\uv.exe" (
    set "UV_CMD=%USERPROFILE%\.local\bin\uv.exe"
    call :log "Found uv at %UV_CMD%"
) else if exist "%USERPROFILE%\.cargo\bin\uv.exe" (
    set "UV_CMD=%USERPROFILE%\.cargo\bin\uv.exe"
    call :log "Found uv at %UV_CMD%"
) else (
    call :log "uv not found, trying to install via pip..."
    where pip >nul 2>nul && (
        pip install --user uv
        set "UV_CMD=%USERPROFILE%\.local\bin\uv.exe"
    ) || (
        where pip3 >nul 2>nul && (
            pip3 install --user uv
            set "UV_CMD=%USERPROFILE%\.local\bin\uv.exe"
        ) || (
            call :err "uv not found and no pip to install it. Install uv manually: https://github.com/astral-sh/uv"
            exit /b 1
        )
    )
)

if not exist "%PYTHON_BIN%" (
    call :log "Creating venv at %VENV_DIR% with Python 3.12..."
    "%UV_CMD%" venv --python 3.12 "%VENV_DIR%"
    if not exist "%PYTHON_BIN%" (
        call :err "Failed to create venv"
        exit /b 1
    )
    call :log "Venv created"
) else (
    call :log "Venv exists at %VENV_DIR%"
)

call :log "Installing PyTorch with CUDA 12.8 (retry up to 3 times)..."
set "RETRY=0"
:TORCH_RETRY
"%UV_CMD%" pip install --python "%PYTHON_BIN%" torch torchvision --index-url https://download.pytorch.org/whl/cu128
if %errorlevel% neq 0 (
    set /a RETRY+=1
    if !RETRY! lss 3 (
        call :warn "PyTorch install failed (attempt !RETRY!/3). Retrying in 10s..."
        timeout /t 10 /nobreak >nul
        goto TORCH_RETRY
    )
    call :err "PyTorch install failed after 3 attempts"
    exit /b 1
)
call :log "PyTorch installed"

call :log "Installing project requirements..."
"%UV_CMD%" pip install --python "%PYTHON_BIN%" -r "%REQUIREMENTS%"
if %errorlevel% neq 0 (
    call :err "Requirements install failed"
    exit /b 1
)
call :log "Requirements installed"

if not exist "%ENV_FILE%" (
    if exist "%ENV_EXAMPLE%" (
        copy "%ENV_EXAMPLE%" "%ENV_FILE%" >nul
        call :warn "Created .env from .env.example - fill in your API keys"
    ) else (
        type nul > "%ENV_FILE%"
        call :warn ".env.example not found, created empty .env"
    )
)

if not exist "%YOLO_WEIGHTS%" (
    if not exist "%MODELS_DIR%" mkdir "%MODELS_DIR%"
    call :warn "YOLO weights not found at %YOLO_WEIGHTS%"
    call :warn "Download yolo11m-pose.pt from Ultralytics v8.4.0 release and place it in models\"
    call :warn "Or: curl -L -o \"%YOLO_WEIGHTS%\" \"https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo11m-pose.pt\""
)

where ffmpeg >nul 2>nul
if %errorlevel% neq 0 (
    call :err "ffmpeg not on PATH. Install from https://ffmpeg.org/download.html or via winget/chocolatey/scoop"
    exit /b 1
)
call :log "ffmpeg found"

set "CMD=%~1"
if "%CMD%"=="" set "CMD=demo"

if /i "%CMD%"=="demo" (
    call :log "Starting full demo: hub + engine on sample video"
    call :log "Open http://127.0.0.1:8000 in your browser"
    start "Angel's Eye Hub" "%PYTHON_BIN%" -m angelseye.hub --port 8000
    timeout /t 3 /nobreak >nul
    if exist "data\meva\G506.avi" (
        "%PYTHON_BIN%" -m angelseye.engine data\meva\G506.avi --camera G506 --hub http://127.0.0.1:8000
    ) else (
        call :warn "No sample video at data\meva\G506.avi"
        call :warn "Run 'run.bat engine ^<video^> --camera ^<ID^> --hub http://127.0.0.1:8000' manually"
    )
) else if /i "%CMD%"=="hub" (
    set "PORT=%~2"
    if "%PORT%"=="" set "PORT=8000"
    call :log "Starting hub on http://127.0.0.1:%PORT% ..."
    "%PYTHON_BIN%" -m angelseye.hub --port %PORT%
) else if /i "%CMD%"=="engine" (
    shift
    call :log "Starting engine: %*"
    "%PYTHON_BIN%" -m angelseye.engine %*
) else if /i "%CMD%"=="geo" (
    call :log "Generating camera registry from MEVA calibration..."
    "%PYTHON_BIN%" -m angelseye.geo
) else if /i "%CMD%"=="eval" (
    shift
    call :log "Running evaluation: %*"
    "%PYTHON_BIN%" -m angelseye.eval %*
) else if /i "%CMD%"=="bench" (
    shift
    call :log "Running benchmark: %*"
    "%PYTHON_BIN%" -m angelseye.bench %*
) else (
    call :err "Usage: %~nx0 {demo^|hub^|engine^|geo^|eval^|bench} [args...]"
    echo   demo              - Start hub + engine on sample video (default)
    echo   hub [port]        - Start API + web UI only (default port 8000)
    echo   engine ^<video^> [--camera ID] [--live] [--hub URL] [--describe] [--out DIR]
    echo   geo               - Build cameras.json from MEVA calibration
    echo   eval [--gt FILE]  - Run evaluation
    echo   bench [args...]   - Run benchmark
    exit /b 1
)
exit /b 0

:log
echo [run.bat] %*
exit /b 0

:warn
echo [run.bat] WARNING: %*
exit /b 0

:err
echo [run.bat] ERROR: %* >&2
exit /b 0