#!/bin/bash

# common.sh - Shared functions for KAI CLI scripts
# Source this file in other scripts: source "$(dirname "$0")/common.sh"

# Find the bundled Python executable
find_python() {
    local SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[1]}")" && pwd)"
    local PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
    local PYTHON_STANDALONE="$PROJECT_ROOT/python-standalone"

    # Check OS type
    if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
        # Windows
        PYTHON_PATH="$PYTHON_STANDALONE/python.exe"
    else
        # macOS/Linux
        PYTHON_PATH="$PYTHON_STANDALONE/bin/python3"
    fi

    # Check if bundled Python exists
    if [ ! -f "$PYTHON_PATH" ]; then
        echo "❌ Error: Bundled Python not found at: $PYTHON_PATH" >&2
        echo "" >&2
        echo "Please run the setup script first:" >&2
        echo "  npm run setup:all" >&2
        echo "" >&2
        echo "Or if you're using the CLI only (without npm):" >&2
        echo "  ./install.sh" >&2
        exit 1
    fi

    echo "$PYTHON_PATH"
}

# Get project root directory
get_project_root() {
    local SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[1]}")" && pwd)"
    echo "$(cd "$SCRIPT_DIR/.." && pwd)"
}

# Setup PATH to include bundled binaries (ffmpeg, yt-dlp)
setup_bin_path() {
    local PROJECT_ROOT="$(get_project_root)"
    local BIN_DIR="$PROJECT_ROOT/resources/bin"

    if [ -d "$BIN_DIR" ]; then
        export PATH="$BIN_DIR:$PATH"
        # echo "[CLI] Added bundled binaries to PATH: $BIN_DIR" >&2
    fi
}
