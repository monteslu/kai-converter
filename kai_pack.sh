#!/bin/bash

# kai_pack.sh - Convert MP3 to KAI format
# Wrapper for python3 -m kai_pack

# If no arguments provided, show usage
if [ $# -eq 0 ]; then
    echo "Usage: $0 [OPTIONS] INPUT_AUDIO [OUTPUT.kai]"
    echo ""
    echo "Convert audio file to KAI karaoke format with AI-generated lyrics"
    echo ""
    echo "Options:"
    echo "  --whisper-model MODEL  Whisper model size (default: small)"
    echo "                         Options: tiny, base, small, medium, large, large-v2, large-v3"
    echo "  --language LANG        Language code for transcription (default: en)"
    echo "                         Use 'auto' for mixed-language songs"
    echo "                         Examples: en, es, fr, de, ja, zh, ko, pt"
    echo "  --four-stems           Use 4-stem separation instead of default 2-stem"
    echo "  --fix-lyrics           Automatically fix lyrics using OpenAI after processing"
    echo "  --stem-bitrate RATE    MP3 bitrate for stems (default: 160k)"
    echo "  --vocals-bitrate RATE  MP3 bitrate for vocals (default: same as stem-bitrate)"
    echo "  --no-analysis          Skip musical feature extraction (faster)"
    echo "  --features LIST        Comma-separated features to extract"
    echo "                         (default: f0,notes,tempo,keys,chords,onsets,mfcc)"
    echo "  --gpu / --cpu          Force GPU or CPU for processing (auto: CUDA/MPS/CPU)"
    echo "  --verbose              Enable verbose logging"
    echo "  --help                 Show detailed help"
    echo ""
    echo "Examples:"
    echo "  $0 song.mp3                              # Default: English, 2-stem"
    echo "  $0 --language es song.mp3                # Spanish transcription"
    echo "  $0 --language auto mixed.mp3             # Auto-detect language"
    echo "  $0 --four-stems --whisper-model large song.mp3 output.kai"
    echo "  $0 --fix-lyrics song.mp3                 # Auto-fix lyrics with OpenAI"
    exit 1
fi

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Pass all arguments to the Python module with correct PYTHONPATH
PYTHONPATH="${SCRIPT_DIR}/src:${PYTHONPATH}" python3 -m kai_pack "$@"