#!/bin/bash

# kai_pack.sh - Convert MP3 to KAI format
# Wrapper for python3 -m kai_pack

# Load common functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# Find bundled Python and setup PATH for bundled binaries
PYTHON_PATH="$(find_python)"
PROJECT_ROOT="$(get_project_root)"
setup_bin_path

# If no arguments provided, show usage
if [ $# -eq 0 ]; then
    echo "Usage: $0 [OPTIONS] INPUT_AUDIO [OUTPUT.kai]"
    echo ""
    echo "Convert audio file to KAI karaoke format with AI-generated lyrics"
    echo ""
    echo "Options:"
    echo "  --whisper-model MODEL  Whisper model size (default: small)"
    echo "                         Options: tiny, base, small, medium, large, large-v2, large-v3, large-v3-turbo"
    echo "  --language LANG        Language code for transcription (default: en)"
    echo "                         Use 'auto' for mixed-language songs"
    echo "                         Examples: en, es, fr, de, ja, zh, ko, pt"
    echo "  --lyrics-url URL       LRCLIB URL for reference lyrics (e.g., https://lrclib.net/api/get/123456)"
    echo "  --four-stems           Use 4-stem separation instead of default 2-stem"
    echo "  --fix-lyrics           Automatically fix lyrics using LLM after processing"
    echo "  --llm-provider PROV    LLM provider: openai, lmstudio, anthropic, gemini (default: auto)"
    echo "  --llm-model MODEL      LLM model name (uses provider default if not specified)"
    echo "  --llm-base-url URL     Base URL for LM Studio or compatible APIs"
    echo "  --llm-api-key KEY      API key (overrides environment variables)"
    echo "  --stem-bitrate RATE    MP3 bitrate for stems (default: 160k)"
    echo "  --vocals-bitrate RATE  MP3 bitrate for vocals (default: same as stem-bitrate)"
    echo "  --no-analysis          Skip musical feature extraction (faster)"
    echo "  --features LIST        Comma-separated features to extract"
    echo "                         (default: f0,tempo for auto-tune + BPM)"
    echo "  --gpu / --cpu          Force GPU or CPU for processing (auto: CUDA/MPS/CPU)"
    echo "  --verbose              Enable verbose logging"
    echo "  --help                 Show detailed help"
    echo ""
    echo "Examples:"
    echo "  $0 song.mp3                              # Default: English, 2-stem"
    echo "  $0 --language es song.mp3                # Spanish transcription"
    echo "  $0 --language auto mixed.mp3             # Auto-detect language"
    echo "  $0 --four-stems --whisper-model large song.mp3 output.kai"
    echo "  $0 --fix-lyrics song.mp3                 # Auto-fix lyrics (auto-detect provider)"
    echo "  $0 --fix-lyrics --llm-provider openai song.mp3     # Use OpenAI GPT"
    echo "  $0 --fix-lyrics --llm-provider lmstudio song.mp3   # Use local LM Studio"
    echo "  $0 --fix-lyrics --llm-provider gemini song.mp3     # Use Google Gemini"
    exit 1
fi

# Pass all arguments to the Python module with correct PYTHONPATH
PYTHONPATH="${PROJECT_ROOT}/src:${PYTHONPATH}" "$PYTHON_PATH" -m kai_pack "$@"