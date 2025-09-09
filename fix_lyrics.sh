#!/bin/bash

# fix_lyrics.sh - Use OpenAI to correct lyrics in a KAI file
# Wrapper for the Python lyrics correction tool

# If no arguments provided, show usage
if [ $# -eq 0 ]; then
    echo "Usage: $0 INPUT.kai [OPTIONS]"
    echo ""
    echo "Use OpenAI to correct transcription errors in KAI file lyrics"
    echo ""
    echo "Arguments:"
    echo "  INPUT.kai                      Input KAI file with lyrics to correct (required)"
    echo ""
    echo "Options:"
    echo "  -l, --lyrics-source FILE/URL   Lyrics source file or URL (auto-fetch if not provided)"
    echo "  -o, --output FILE.kai          Output file (default: INPUT_fixed.kai)"
    echo ""
    echo "Environment:"
    echo "  OPENAI_API_KEY   OpenAI API key (required)"
    echo ""
    echo "Examples:"
    echo "  $0 song.kai                              # Auto-fetch lyrics, creates song_fixed.kai"
    echo "  $0 song.kai -l lyrics.txt                # Use local lyrics file"  
    echo "  $0 song.kai -l https://genius.com/...    # Use Genius URL"
    echo "  $0 song.kai -o corrected.kai             # Custom output name"
    echo ""
    echo "Requirements:"
    echo "  - OpenAI API key: export OPENAI_API_KEY='your-key'"
    echo "  - pip install openai requests beautifulsoup4"
    exit 1
fi

# Check if file exists
if [ ! -f "$1" ]; then
    echo "Error: File '$1' not found"
    exit 1
fi

python3 /home/monteslu/code/mine/kai-converter/src/utils/fix_lyrics.py "$@"