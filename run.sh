#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

VENV_DIR="$PROJECT_ROOT/.venv"
PYTHON_BIN="$VENV_DIR/bin/python"
REQUIREMENTS="$PROJECT_ROOT/requirements.txt"
ENV_FILE="$PROJECT_ROOT/.env"
ENV_EXAMPLE="$PROJECT_ROOT/.env.example"
MODELS_DIR="$PROJECT_ROOT/models"
YOLO_WEIGHTS="$MODELS_DIR/yolo11m-pose.pt"

log() { printf "\033[1;32m[run.sh]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[run.sh]\033[0m %s\n" "$*"; }
err() { printf "\033[1;31m[run.sh]\033[0m %s\n" "$*" >&2; }

check_cmd() { command -v "$1" >/dev/null 2>&1; }

ensure_uv() {
    if check_cmd uv; then
        UV_CMD="uv"
    elif check_cmd "$HOME/.local/bin/uv"; then
        UV_CMD="$HOME/.local/bin/uv"
    elif check_cmd "$HOME/.cargo/bin/uv"; then
        UV_CMD="$HOME/.cargo/bin/uv"
    else
        log "uv not found, installing via pipx/pip..."
        if check_cmd pipx; then
            pipx install uv
            UV_CMD="uv"
        elif check_cmd pip3; then
            pip3 install --user uv
            UV_CMD="$HOME/.local/bin/uv"
        elif check_cmd pip; then
            pip install --user uv
            UV_CMD="$HOME/.local/bin/uv"
        else
            err "No pip/pipx to install uv. Install uv manually: https://github.com/astral-sh/uv"
            exit 1
        fi
    fi
    log "Using uv: $($UV_CMD --version)"
}

ensure_python() {
    if [[ -x "$PYTHON_BIN" ]]; then
        log "Venv exists at $VENV_DIR"
        return
    fi
    log "Creating venv at $VENV_DIR with Python 3.12..."
    $UV_CMD venv --python 3.12 "$VENV_DIR"
    log "Venv created"
}

install_pytorch() {
    log "Installing PyTorch with CUDA 12.8..."
    local max_retries=3
    local retry=0
    while [[ $retry -lt $max_retries ]]; do
        if $UV_CMD pip install --python "$PYTHON_BIN" torch torchvision --index-url https://download.pytorch.org/whl/cu128; then
            log "PyTorch installed"
            return 0
        fi
        retry=$((retry + 1))
        warn "PyTorch install failed (attempt $retry/$max_retries). Retrying in 10s..."
        sleep 10
    done
    err "PyTorch install failed after $max_retries attempts"
    exit 1
}

install_requirements() {
    log "Installing project requirements..."
    $UV_CMD pip install --python "$PYTHON_BIN" -r "$REQUIREMENTS"
    log "Requirements installed"
}

ensure_env_file() {
    if [[ ! -f "$ENV_FILE" ]]; then
        if [[ -f "$ENV_EXAMPLE" ]]; then
            cp "$ENV_EXAMPLE" "$ENV_FILE"
            warn "Created .env from .env.example — fill in your API keys"
        else
            warn ".env.example not found, creating empty .env"
            touch "$ENV_FILE"
        fi
    fi
}

ensure_yolo_weights() {
    if [[ -f "$YOLO_WEIGHTS" ]]; then
        log "YOLO weights found: $YOLO_WEIGHTS"
        return
    fi
    mkdir -p "$MODELS_DIR"
    warn "YOLO weights not found at $YOLO_WEIGHTS"
    warn "Download yolo11m-pose.pt from Ultralytics v8.4.0 release and place it in models/"
    warn "Or run: wget -O '$YOLO_WEIGHTS' 'https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo11m-pose.pt'"
}

check_ffmpeg() {
    if check_cmd ffmpeg; then
        log "ffmpeg found: $(ffmpeg -version | head -1)"
    else
        err "ffmpeg not on PATH. Install: sudo pacman -S ffmpeg  (Arch) / sudo apt install ffmpeg  (Debian/Ubuntu)"
        exit 1
    fi
}

run_hub() {
    local port="${1:-8000}"
    log "Starting hub on http://127.0.0.1:$port ..."
    exec "$PYTHON_BIN" -m angelseye.hub --port "$port"
}

run_engine() {
    log "Starting engine: $*"
    exec "$PYTHON_BIN" -m angelseye.engine "$@"
}

run_geo() {
    log "Generating camera registry from MEVA calibration..."
    exec "$PYTHON_BIN" -m angelseye.geo
}

run_eval() {
    shift || true
    log "Running evaluation: $*"
    exec "$PYTHON_BIN" -m angelseye.eval "$@"
}

run_bench() {
    shift || true
    log "Running benchmark: $*"
    exec "$PYTHON_BIN" -m angelseye.bench "$@"
}

main() {
    ensure_uv
    ensure_python
    install_pytorch
    install_requirements
    ensure_env_file
    ensure_yolo_weights
    check_ffmpeg

    case "${1:-demo}" in
        demo)
            log "Starting full demo: hub + engine on sample video"
            log "Open http://127.0.0.1:8000 in your browser"
            run_hub 8000 &
            HUB_PID=$!
            sleep 3
            if [[ -f "data/meva/G506.avi" ]]; then
                run_engine data/meva/G506.avi --camera G506 --hub http://127.0.0.1:8000
            else
                warn "No sample video at data/meva/G506.avi"
                warn "Run './run.sh engine <video> --camera <ID> --hub http://127.0.0.1:8000' manually"
                wait $HUB_PID
            fi
            ;;
        hub)        run_hub "${2:-8000}" ;;
        engine)     run_engine "$@" ;;
        geo)        run_geo ;;
        eval)       run_eval "$@" ;;
        bench)      run_bench "$@" ;;
        *)          err "Usage: $0 {demo|hub|engine|geo|eval|bench} [args...]"
                    echo "  demo              - Start hub + engine on sample video (default)"
                    echo "  hub [port]        - Start API + web UI only (default port 8000)"
                    echo "  engine <video> [--camera ID] [--live] [--hub URL] [--describe] [--out DIR]"
                    echo "  geo               - Build cameras.json from MEVA calibration"
                    echo "  eval [--gt FILE]  - Run evaluation"
                    echo "  bench [args...]   - Run benchmark"
                    exit 1 ;;
    esac
}

main "$@"