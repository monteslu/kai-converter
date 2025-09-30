#!/bin/bash

# batch_pack_parallel.sh - Parallel batch process MP3 files to KAI format
# Processes multiple files simultaneously with optimal memory management

set -e

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS] FOLDER"
    echo ""
    echo "Parallel batch convert MP3 files in FOLDER to KAI karaoke format"
    echo "Only processes MP3 files that don't already have matching .kai files"
    echo ""
    echo "Parallel Processing Options:"
    echo "  --workers N            Number of parallel workers (default: 3, max: 8)"
    echo "  --threads-per-worker N Set threads per worker (default: auto-detect)"
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
    echo "  $0 /music/albums/                              # Process with 3 workers"
    echo "  $0 --workers 2 /music/albums/                  # Use 2 parallel workers"
    echo "  $0 --workers 4 --threads-per-worker 6 /music/  # 4 workers, 6 threads each"
    echo "  $0 --language auto --fix-lyrics /music/mixed/  # Auto-detect language"
    echo "  $0 --dry-run /music/test/                      # See what would be processed"
    echo ""
    echo "Performance Notes:"
    echo "  - Each worker loads models once and processes multiple files"
    echo "  - Memory usage: ~3-4GB per worker (Whisper + Demucs models)"
    echo "  - Recommended workers: 2-4 for systems with 16GB+ RAM"
    echo "  - Monitor memory usage with: watch -n 1 free -h"
    echo ""
    echo "Requirements:"
    echo "  - GNU parallel (install: sudo apt install parallel)"
    echo "  - All kai_pack.sh requirements"
    echo "  - For --fix-lyrics: API key for selected provider"
    exit 1
}

# Initialize variables
FOLDER=""
KAI_PACK_ARGS=""
DRY_RUN=false
VERBOSE=false
WORKERS=3
THREADS_PER_WORKER=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --help|-h)
            show_usage
            ;;
        --workers)
            WORKERS="$2"
            if ! [[ "$WORKERS" =~ ^[1-8]$ ]]; then
                echo "Error: --workers must be between 1 and 8"
                exit 1
            fi
            shift 2
            ;;
        --threads-per-worker)
            THREADS_PER_WORKER="$2"
            if ! [[ "$THREADS_PER_WORKER" =~ ^[1-9][0-9]*$ ]]; then
                echo "Error: --threads-per-worker must be a positive integer"
                exit 1
            fi
            shift 2
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
        --fix-lyrics|--four-stems|--no-analysis|--gpu|--cpu|--crepe-filter)
            # Boolean flags that don't take arguments
            KAI_PACK_ARGS="$KAI_PACK_ARGS $1"
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

# Expand tilde in folder path
FOLDER=$(eval echo "$FOLDER")

# Check if folder exists
if [ ! -d "$FOLDER" ]; then
    echo "Error: Folder '$FOLDER' does not exist"
    exit 1
fi

# Check if GNU parallel is available
if ! command -v parallel &> /dev/null; then
    echo "Error: GNU parallel is required but not installed"
    echo "Install with: sudo apt install parallel"
    echo "Or use the original batch_pack.sh for sequential processing"
    exit 1
fi

# Get absolute path
FOLDER=$(realpath "$FOLDER")

echo "=========================================="
echo "KAI Parallel Batch Processor"
echo "=========================================="
echo "Folder: $FOLDER"
echo "Workers: $WORKERS"
echo "Options: $KAI_PACK_ARGS"
echo ""

# Auto-detect optimal threading if not specified
if [ -z "$THREADS_PER_WORKER" ]; then
    TOTAL_CORES=$(nproc)
    THREADS_PER_WORKER=$((TOTAL_CORES / WORKERS))
    if [ $THREADS_PER_WORKER -lt 2 ]; then
        THREADS_PER_WORKER=2
    fi
    echo "Auto-detected threads per worker: $THREADS_PER_WORKER (total cores: $TOTAL_CORES)"
else
    echo "Using threads per worker: $THREADS_PER_WORKER"
fi

# Memory optimization setup
echo "Setting up parallel processing environment..."
# Set per-worker thread limits
export OMP_NUM_THREADS=$THREADS_PER_WORKER
export MKL_NUM_THREADS=$THREADS_PER_WORKER
export TORCH_NUM_THREADS=$THREADS_PER_WORKER

# Only set CUDA-specific vars if CUDA is available
if python3 -c "import torch; exit(0 if torch.cuda.is_available() else 1)" 2>/dev/null; then
    echo "  CUDA detected - enabling GPU memory optimizations"
    export PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:64
    export CUDA_LAUNCH_BLOCKING=0
    export PYTORCH_NO_CUDA_MEMORY_CACHING=0
else
    echo "  CPU mode - optimizing for parallel CPU processing"
fi

echo "  Threads per worker: $THREADS_PER_WORKER"
echo "  Total parallel threads: $((WORKERS * THREADS_PER_WORKER))"

# Find all MP3 files (portable method for older bash/zsh compatibility)
MP3_FILES=()
while IFS= read -r -d '' file; do
    MP3_FILES+=("$file")
done < <(find "$FOLDER" -maxdepth 1 -name "*.mp3" -type f -print0 | sort -z)

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
    echo "DRY RUN: Would process ${#TO_PROCESS[@]} files with $WORKERS parallel workers"
    echo "Commands that would be executed in parallel:"
    for mp3_file in "${TO_PROCESS[@]}"; do
        echo "  ./kai_pack.sh $KAI_PACK_ARGS \"$mp3_file\""
    done
    echo ""
    echo "Estimated memory usage: $((WORKERS * 4))GB (${WORKERS} workers × ~4GB per worker)"
    echo "Estimated speedup: ${WORKERS}x faster than sequential processing"
    exit 0
fi

echo ""
echo "=========================================="
echo "Starting parallel batch processing..."
echo "Workers: $WORKERS | Threads per worker: $THREADS_PER_WORKER"
echo "=========================================="

# Create a temporary file list for parallel processing
TEMP_LIST=$(mktemp)
printf '%s\n' "${TO_PROCESS[@]}" > "$TEMP_LIST"

# Create wrapper script for parallel execution that reads args from environment
WRAPPER_SCRIPT=$(mktemp)
cat > "$WRAPPER_SCRIPT" << EOF
#!/bin/bash
mp3_file="\$1"
base_name=\$(basename "\$mp3_file")

# Show progress
echo "[\$\$ - \$(date '+%H:%M:%S')] Processing: \$base_name"

# Clear GPU memory before processing (if CUDA available)
python3 -c "import torch; import gc; gc.collect(); torch.cuda.empty_cache() if torch.cuda.is_available() else None" 2>/dev/null || true

# Execute kai_pack.sh with the args from the main script
start_time=\$(date +%s)

if ./kai_pack.sh $KAI_PACK_ARGS "\$mp3_file"; then
    end_time=\$(date +%s)
    duration=\$((end_time - start_time))
    echo "[\$\$ - \$(date '+%H:%M:%S')] ✓ \$base_name completed (\${duration}s)"
    exit 0
else
    echo "[\$\$ - \$(date '+%H:%M:%S')] ✗ \$base_name failed"

    # Log failure to lyric_errors.txt (with file locking)
    (
        flock -x 200
        {
            echo ""
            echo "[\$(date '+%Y-%m-%d %H:%M:%S')] Parallel Batch Processing Failure:"
            echo "File: \$mp3_file"
            echo "Command: ./kai_pack.sh $KAI_PACK_ARGS \"\$mp3_file\""
            echo "Worker PID: \$\$"
            echo "\$(printf '%s' '-' | head -c 50)"
        } >> lyric_errors.txt
    ) 200>>lyric_errors.txt

    exit 1
fi
EOF

chmod +x "$WRAPPER_SCRIPT"

# Run parallel processing with progress bar
echo "Processing ${#TO_PROCESS[@]} files with $WORKERS parallel workers..."
echo ""

# Use GNU parallel to process files
if [ "$VERBOSE" = true ]; then
    parallel_args="--jobs $WORKERS --ungroup"
else
    parallel_args="--jobs $WORKERS --ungroup"
fi

start_time_total=$(date +%s)

if parallel $parallel_args "$WRAPPER_SCRIPT" :::: "$TEMP_LIST"; then
    PARALLEL_EXIT_CODE=0
else
    PARALLEL_EXIT_CODE=$?
fi

end_time_total=$(date +%s)
total_duration=$((end_time_total - start_time_total))

# Count results
SUCCESS_COUNT=0
FAILED_COUNT=0
FAILED_FILES=()

for mp3_file in "${TO_PROCESS[@]}"; do
    base_name=$(basename "$mp3_file" .mp3)
    kai_file="${mp3_file%.mp3}.kai"

    if [ -f "$kai_file" ]; then
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
    else
        FAILED_COUNT=$((FAILED_COUNT + 1))
        FAILED_FILES+=("$base_name")
    fi
done

# Cleanup temporary files
rm -f "$TEMP_LIST" "$WRAPPER_SCRIPT"

echo ""
echo "=========================================="
echo "Parallel batch processing complete!"
echo "=========================================="
echo "Results:"
echo "  Successful: $SUCCESS_COUNT"
echo "  Failed: $FAILED_COUNT"
echo "  Total processed: ${#TO_PROCESS[@]}"
echo "  Total time: ${total_duration}s"
echo "  Workers used: $WORKERS"

if [ $SUCCESS_COUNT -gt 0 ]; then
    avg_time_per_file=$((total_duration / SUCCESS_COUNT))
    echo "  Average time per file: ${avg_time_per_file}s"
    estimated_sequential_time=$((avg_time_per_file * SUCCESS_COUNT))
    speedup=$(echo "scale=1; $estimated_sequential_time / $total_duration" | bc -l 2>/dev/null || echo "~${WORKERS}")
    echo "  Estimated speedup: ${speedup}x"
fi

if [ $FAILED_COUNT -gt 0 ]; then
    echo ""
    echo "Failed files:"
    for file in "${FAILED_FILES[@]}"; do
        echo "  ✗ $file"
    done
    echo ""
    echo "You can retry failed files individually with:"
    echo "  ./kai_pack.sh [OPTIONS] \"path/to/file.mp3\""
    echo ""
    echo "Or retry with fewer workers:"
    echo "  $0 --workers $((WORKERS - 1)) \"$FOLDER\""
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