#!/bin/bash

# regen_lyrics.sh - Regenerate lyrics in KAI file with new transcription
# Keeps existing stems but re-runs Whisper transcription only

set -e

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS] INPUT.kai [OUTPUT.kai]"
    echo ""
    echo "Regenerate lyrics in KAI file with fresh transcription"
    echo "Preserves existing audio stems and analysis but re-runs Whisper only"
    echo ""
    echo "Options:"
    echo "  --whisper-model MODEL  Whisper model size (default: small)"
    echo "                         Options: tiny, base, small, medium, large, large-v2, large-v3, large-v3-turbo"
    echo "  --language LANG        Language code for transcription (default: en)"
    echo "                         Use 'auto' for mixed-language songs"
    echo "                         Examples: en, es, fr, de, ja, zh, ko, pt"
    echo "  --fix-lyrics           Automatically fix lyrics using LLM after regeneration"
    echo "  --llm-provider PROV    LLM provider for lyrics fixing: openai, gemini, anthropic (default: auto)"
    echo "  --llm-model MODEL      LLM model name (uses provider default if not specified)"
    echo "  --verbose              Enable verbose logging"
    echo "  --help                 Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 song.kai                                      # Basic regeneration"
    echo "  $0 --whisper-model large-v3-turbo song.kai      # Use latest/fastest Whisper model"
    echo "  $0 --language es song.kai                       # Spanish transcription"
    echo "  $0 --fix-lyrics --llm-provider openai song.kai  # Regenerate + fix lyrics"
    echo "  $0 song.kai song_v2.kai                         # Save to new file"
    echo ""
    echo "This is useful when you want to:"
    echo "  - Try a different Whisper model on existing stems"
    echo "  - Re-transcribe with different language settings"
    echo "  - Apply LLM lyrics correction to existing transcription"
    exit 1
}

# Initialize variables
INPUT_KAI=""
OUTPUT_KAI=""
WHISPER_MODEL=""
LANGUAGE=""
FIX_LYRICS=""
LLM_PROVIDER=""
LLM_MODEL=""
VERBOSE=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --help|-h)
            show_usage
            ;;
        --whisper-model)
            WHISPER_MODEL="--whisper-model $2"
            shift 2
            ;;
        --language)
            LANGUAGE="--language $2"
            shift 2
            ;;
        --fix-lyrics)
            FIX_LYRICS="--fix-lyrics"
            shift
            ;;
        --llm-provider)
            LLM_PROVIDER="--llm-provider $2"
            shift 2
            ;;
        --llm-model)
            LLM_MODEL="--llm-model $2"
            shift 2
            ;;
        --verbose)
            VERBOSE="--verbose"
            shift
            ;;
        --*)
            echo "Error: Unknown option $1"
            echo ""
            show_usage
            ;;
        *)
            if [ -z "$INPUT_KAI" ]; then
                INPUT_KAI="$1"
            elif [ -z "$OUTPUT_KAI" ]; then
                OUTPUT_KAI="$1"
            else
                echo "Error: Too many arguments"
                echo ""
                show_usage
            fi
            shift
            ;;
    esac
done

# Check if input file was provided
if [ -z "$INPUT_KAI" ]; then
    echo "Error: Input KAI file is required"
    echo ""
    show_usage
fi

# Check if input file exists
if [ ! -f "$INPUT_KAI" ]; then
    echo "Error: Input file '$INPUT_KAI' not found"
    exit 1
fi

# Set default output to same as input if not specified
if [ -z "$OUTPUT_KAI" ]; then
    OUTPUT_KAI="$INPUT_KAI"
fi

echo "=========================================="
echo "KAI Lyrics Regenerator"
echo "=========================================="
echo "Input: $INPUT_KAI"
echo "Output: $OUTPUT_KAI"

# Get the directory where this script is located (before changing directories)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Convert to absolute path before doing anything
INPUT_KAI_FULL="$(cd "$(dirname "$INPUT_KAI")" && pwd)/$(basename "$INPUT_KAI")"
OUTPUT_KAI_FULL="$(cd "$(dirname "$OUTPUT_KAI")" && pwd)/$(basename "$OUTPUT_KAI")"

# Run Python regeneration script directly on the KAI file
echo ""
echo "Regenerating lyrics transcription..."
echo "----------------------------------------"

# Build Python command
PYTHON_CMD="PYTHONPATH=\"$SCRIPT_DIR/src:\$PYTHONPATH\" python3 \"$SCRIPT_DIR/src/utils/regen_lyrics.py\""
PYTHON_CMD="$PYTHON_CMD \"$INPUT_KAI_FULL\""
PYTHON_CMD="$PYTHON_CMD --output \"$OUTPUT_KAI_FULL\""

# Add Whisper model if specified
if [ -n "$WHISPER_MODEL" ]; then
    PYTHON_CMD="$PYTHON_CMD $WHISPER_MODEL"
fi

# Add language if specified
if [ -n "$LANGUAGE" ]; then
    PYTHON_CMD="$PYTHON_CMD $LANGUAGE"
fi


# Add verbose if specified
if [ -n "$VERBOSE" ]; then
    PYTHON_CMD="$PYTHON_CMD $VERBOSE"
fi

echo "Running: $PYTHON_CMD"
echo ""

# Execute the regeneration with live progress display
LRCLIB_INFO_FILE=""

# Capture stderr for info file path while showing stdout progress
exec 3>&1 4>&2  # Save original stdout/stderr
STDERR_CAPTURE=$(eval $PYTHON_CMD 3>&1 1>&4 2>&3 | tee /dev/stderr | grep "LRCLIB_INFO_FILE=" | head -1)
REGEN_EXIT_CODE=$?
exec 3>&- 4>&-  # Close extra file descriptors

if [ $REGEN_EXIT_CODE -ne 0 ]; then
    echo "Error: Regeneration failed with exit code $REGEN_EXIT_CODE"
    exit $REGEN_EXIT_CODE
fi

echo "✓ Updated KAI file created: $OUTPUT_KAI"

# Extract info file path and read lyrics temp file location
if [ -n "$STDERR_CAPTURE" ]; then
    LRCLIB_INFO_FILE=$(echo "$STDERR_CAPTURE" | sed 's/LRCLIB_INFO_FILE=//')
    if [ -f "$LRCLIB_INFO_FILE" ]; then
        LYRICS_TEMP_FILE=$(cat "$LRCLIB_INFO_FILE")
        rm -f "$LRCLIB_INFO_FILE"  # Clean up info file
    fi
fi

# Run lyrics fixing if requested
if [ -n "$FIX_LYRICS" ]; then
    echo ""
    echo "Running lyrics correction..."
    echo "----------------------------------------"

    # Build fix_lyrics command
    FIX_CMD="\"$SCRIPT_DIR/fix_lyrics.sh\" \"$OUTPUT_KAI_FULL\""

    # Use LRCLIB lyrics temp file if available
    if [ -n "$LYRICS_TEMP_FILE" ] && [ -f "$LYRICS_TEMP_FILE" ]; then
        echo "Using LRCLIB reference lyrics from temp file"
        FIX_CMD="$FIX_CMD --lyrics-source \"$LYRICS_TEMP_FILE\""
    else
        echo "No LRCLIB lyrics found, will auto-fetch from web"
    fi

    if [ -n "$LLM_PROVIDER" ]; then
        FIX_CMD="$FIX_CMD $LLM_PROVIDER"
    fi
    if [ -n "$LLM_MODEL" ]; then
        FIX_CMD="$FIX_CMD $LLM_MODEL"
    fi

    echo "Running: $FIX_CMD"
    eval $FIX_CMD

    # Clean up temp file after use
    if [ -n "$LYRICS_TEMP_FILE" ] && [ -f "$LYRICS_TEMP_FILE" ]; then
        rm -f "$LYRICS_TEMP_FILE"
        echo "Cleaned up temp lyrics file"
    fi
fi

echo ""
echo "=========================================="
echo "✓ Regeneration complete!"
echo "=========================================="
echo "Updated file: $OUTPUT_KAI"
echo ""
echo "Changes made:"
echo "  - Fresh Whisper transcription"
echo "  - Preserved original audio stems and analysis"
if [ -n "$FIX_LYRICS" ]; then
    echo "  - Applied LLM lyrics correction"
fi
echo ""
echo "Next steps:"
echo "  - Review lyrics: ./log_kai_lyrics.sh \"$OUTPUT_KAI\""
echo "  - Create video: ./make_movie.sh \"$OUTPUT_KAI\""