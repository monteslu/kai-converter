#!/bin/bash

# log_kai_lyrics.sh - Display lyrics from a KAI file
# Wrapper for the Python lyrics logger

# If no arguments provided, show usage
if [ $# -eq 0 ]; then
    echo "Usage: $0 INPUT.kai"
    echo ""
    echo "Display and analyze lyrics from a KAI file"
    echo ""
    echo "Features:"
    echo "  - Shows all lyrics with timing information"
    echo "  - Identifies disabled lines"
    echo "  - Detects gaps between lyrics"
    echo "  - Highlights lines without timing data"
    echo "  - Displays song metadata (title, artist, duration, key)"
    echo ""
    echo "Arguments:"
    echo "  INPUT.kai    KAI file to analyze (required)"
    echo ""
    echo "Examples:"
    echo "  $0 song.kai"
    echo "  $0 \"My Song.kai\"    # File with spaces"
    echo ""
    echo "Output format:"
    echo "  Line   1: [ 10.50 -  15.30] (4.80s) ✓         First line of lyrics"
    echo "  Line   2: [ 15.30 -  20.10] (4.80s) ✗ DISABLED Second line (disabled)"
    echo "  Line   3: [  NO TIMING     ] (    )  ✓         Line without timing"
    exit 1
fi

# Check if file exists
if [ ! -f "$1" ]; then
    echo "Error: File '$1' not found"
    echo "Run '$0' without arguments for usage information"
    exit 1
fi

python3 /home/monteslu/code/mine/kai-converter/src/utils/log_kai_lyrics.py "$@"