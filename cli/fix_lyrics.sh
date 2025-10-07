#!/bin/bash

# fix_lyrics.sh - Use LLM providers to correct lyrics in a KAI file
# Wrapper for the Python lyrics correction tool

# If no arguments provided, show usage
if [ $# -eq 0 ]; then
    echo "Usage: $0 INPUT.kai [OPTIONS]"
    echo ""
    echo "Use LLM providers to correct transcription errors in KAI file lyrics"
    echo ""
    echo "Arguments:"
    echo "  INPUT.kai                      Input KAI file with lyrics to correct (required)"
    echo ""
    echo "Options:"
    echo "  -l, --lyrics-source FILE/URL   Lyrics source file or URL (auto-fetch if not provided)"
    echo "  -o, --output FILE.kai          Output file (default: INPUT_fixed.kai)"
    echo "  --llm-provider PROVIDER        LLM provider: openai, lmstudio, anthropic, gemini (default: auto)"
    echo "  --llm-model MODEL              LLM model name (uses provider default if not specified)"
    echo "  --llm-base-url URL             Base URL for LM Studio or compatible APIs"
    echo "  --llm-api-key KEY              API key (overrides environment variables)"
    echo ""
    echo "Environment (auto-detected):"
    echo "  OPENAI_API_KEY      OpenAI API key"
    echo "  ANTHROPIC_API_KEY   Anthropic Claude API key"
    echo "  GEMINI_API_KEY      Google Gemini API key"
    echo ""
    echo "Examples:"
    echo "  $0 song.kai                              # Auto-fetch lyrics, auto-detect provider"
    echo "  $0 song.kai --llm-provider lmstudio     # Use local LM Studio (free)"
    echo "  $0 song.kai --llm-provider openai       # Use OpenAI GPT"
    echo "  $0 song.kai --llm-provider gemini       # Use Google Gemini"
    echo "  $0 song.kai -l lyrics.txt                # Use local lyrics file"  
    echo "  $0 song.kai -l https://genius.com/...    # Use Genius URL"
    echo "  $0 song.kai -o corrected.kai             # Custom output name"
    exit 1
fi

# Check if file exists
if [ ! -f "$1" ]; then
    echo "Error: File '$1' not found"
    exit 1
fi

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Pass all arguments to the Python script with correct PYTHONPATH
PYTHONPATH="${SCRIPT_DIR}/src:${PYTHONPATH}" python3 "${SCRIPT_DIR}/src/utils/fix_lyrics.py" "$@"