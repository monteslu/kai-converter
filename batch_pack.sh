#!/bin/bash

# batch_pack.sh - Batch process MP3 files in a folder to KAI format
# Processes all MP3 files that don't already have matching KAI files

set -e

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS] FOLDER"
    echo ""
    echo "Batch convert MP3 files in FOLDER to KAI karaoke format"
    echo "Only processes MP3 files that don't already have matching .kai files"
    echo ""
    echo "Options (all kai_pack.sh options are supported):"
    echo "  --whisper-model MODEL  Whisper model size (default: small)"
    echo "                         Options: tiny, base, small, medium, large, large-v2, large-v3, large-v3-turbo"
    echo "  --language LANG        Language code for transcription (default: en)"
    echo "                         Use 'auto' for mixed-language songs"
    echo "                         Examples: en, es, fr, de, ja, zh, ko, pt"
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
    echo "  --crepe-filter         Enable CREPE filtering to skip non-vocal chunks"
    echo "  --silence-threshold DB Silence threshold in dB for chunk detection (default: -20)"
    echo "  --vocal-pitch-type TYPE Vocal pitch quantization (default: midi_cents)"
    echo "  --dry-run              Show what would be processed without actually doing it"
    echo "  --verbose              Enable verbose logging"
    echo "  --help                 Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 /music/albums/                              # Process all MP3s with defaults"
    echo "  $0 --language es /music/spanish/               # Spanish transcription"
    echo "  $0 --language auto /music/mixed/               # Auto-detect language"
    echo "  $0 --four-stems --whisper-model large /music/  # High quality with 4 stems"
    echo "  $0 --fix-lyrics --llm-provider openai /music/  # Auto-fix lyrics with OpenAI"
    echo "  $0 --dry-run /music/test/                      # See what would be processed"
    echo "  $0 --verbose --gpu /music/albums/              # Verbose output, force GPU"
    echo ""
    echo "Requirements:"
    echo "  - All kai_pack.sh requirements"
    echo "  - For --fix-lyrics: API key for selected provider"
    echo ""
    echo "Notes:"
    echo "  - Skips files that already have matching .kai files"
    echo "  - Preserves original MP3 files"
    echo "  - Processes files in alphabetical order"
    echo "  - Use Ctrl+C to stop processing at any time"
    exit 1
}

# Initialize variables
FOLDER=""
KAI_PACK_ARGS=""
DRY_RUN=false
VERBOSE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --help|-h)
            show_usage
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --verbose)
            VERBOSE=true
            KAI_PACK_ARGS="$KAI_PACK_ARGS --verbose"
            shift
            ;;
        --*)
            # Pass through all other options to kai_pack.sh
            KAI_PACK_ARGS="$KAI_PACK_ARGS $1"
            if [[ -n "$2" ]] && [[ ! "$2" =~ ^-- ]]; then
                KAI_PACK_ARGS="$KAI_PACK_ARGS $2"
                shift
            fi
            shift
            ;;
        *)
            if [ -z "$FOLDER" ]; then
                FOLDER="$1"
            else
                echo "Error: Too many arguments"
                echo ""
                show_usage
            fi
            shift
            ;;
    esac
done

# Check if folder was provided
if [ -z "$FOLDER" ]; then
    echo "Error: Folder is required"
    echo ""
    show_usage
fi

# Check if folder exists
if [ ! -d "$FOLDER" ]; then
    echo "Error: Folder '$FOLDER' does not exist"
    exit 1
fi

# Get absolute path
FOLDER=$(realpath "$FOLDER")

echo "=========================================="
echo "KAI Batch Processor"
echo "=========================================="
echo "Folder: $FOLDER"
echo "Options: $KAI_PACK_ARGS"
echo ""

# Find all MP3 files
mapfile -t MP3_FILES < <(find "$FOLDER" -maxdepth 1 -name "*.mp3" -type f | sort)

if [ ${#MP3_FILES[@]} -eq 0 ]; then
    echo "No MP3 files found in $FOLDER"
    exit 0
fi

echo "Found ${#MP3_FILES[@]} MP3 files:"

# Check which files need processing
TO_PROCESS=()
ALREADY_EXIST=()

for mp3_file in "${MP3_FILES[@]}"; do
    # Get base name without extension
    base_name=$(basename "$mp3_file" .mp3)
    kai_file="${mp3_file%.mp3}.kai"

    if [ -f "$kai_file" ]; then
        ALREADY_EXIST+=("$base_name")
    else
        TO_PROCESS+=("$mp3_file")
    fi
done

# Show summary
echo ""
echo "Status summary:"
echo "  Total MP3 files: ${#MP3_FILES[@]}"
echo "  Already have KAI files: ${#ALREADY_EXIST[@]}"
echo "  Need processing: ${#TO_PROCESS[@]}"

if [ ${#ALREADY_EXIST[@]} -gt 0 ]; then
    echo ""
    echo "Files with existing KAI files (skipping):"
    for file in "${ALREADY_EXIST[@]}"; do
        echo "  ✓ $file"
    done
fi

if [ ${#TO_PROCESS[@]} -eq 0 ]; then
    echo ""
    echo "All files already have KAI files. Nothing to process."
    exit 0
fi

echo ""
echo "Files to process:"
for mp3_file in "${TO_PROCESS[@]}"; do
    base_name=$(basename "$mp3_file")
    echo "  → $base_name"
done

if [ "$DRY_RUN" = true ]; then
    echo ""
    echo "DRY RUN: Would process ${#TO_PROCESS[@]} files"
    echo "Commands that would be executed:"
    for mp3_file in "${TO_PROCESS[@]}"; do
        echo "  ./kai_pack.sh$KAI_PACK_ARGS \"$mp3_file\""
    done
    exit 0
fi

echo ""
echo "=========================================="
echo "Starting batch processing..."
echo "=========================================="

# Process files
SUCCESS_COUNT=0
FAILED_COUNT=0
FAILED_FILES=()

for i in "${!TO_PROCESS[@]}"; do
    mp3_file="${TO_PROCESS[$i]}"
    base_name=$(basename "$mp3_file")

    echo ""
    echo "[$((i+1))/${#TO_PROCESS[@]}] Processing: $base_name"
    echo "----------------------------------------"

    # Build kai_pack command
    KAI_PACK_CMD="./kai_pack.sh$KAI_PACK_ARGS \"$mp3_file\""

    if [ "$VERBOSE" = true ]; then
        echo "Running: $KAI_PACK_CMD"
        echo ""
    fi

    # Execute kai_pack.sh
    start_time=$(date +%s)
    if eval $KAI_PACK_CMD; then
        end_time=$(date +%s)
        duration=$((end_time - start_time))
        echo "✓ Success! (${duration}s)"
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
    else
        echo "✗ Failed!"
        FAILED_COUNT=$((FAILED_COUNT + 1))
        FAILED_FILES+=("$base_name")

        # Log failure to lyric_errors.txt
        {
            echo ""
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] Batch Processing Failure:"
            echo "File: $mp3_file"
            echo "Command: $KAI_PACK_CMD"
            echo "Exit code: $?"
            echo "$(printf '%s' '-' | head -c 50)"
        } >> lyric_errors.txt
    fi
done

echo ""
echo "=========================================="
echo "Batch processing complete!"
echo "=========================================="
echo "Results:"
echo "  Successful: $SUCCESS_COUNT"
echo "  Failed: $FAILED_COUNT"
echo "  Total processed: ${#TO_PROCESS[@]}"

if [ $FAILED_COUNT -gt 0 ]; then
    echo ""
    echo "Failed files:"
    for file in "${FAILED_FILES[@]}"; do
        echo "  ✗ $file"
    done
    echo ""
    echo "You can retry failed files individually with:"
    echo "  ./kai_pack.sh [OPTIONS] \"path/to/file.mp3\""
fi

echo ""
echo "Next steps:"
echo "  - View lyrics: ./log_kai_lyrics.sh \"file.kai\""
echo "  - Create videos: ./make_movie.sh \"file.kai\""
echo "  - Batch create videos: find \"$FOLDER\" -name \"*.kai\" -exec ./make_movie.sh {} \\;"

if [ $FAILED_COUNT -gt 0 ]; then
    exit 1
else
    exit 0
fi