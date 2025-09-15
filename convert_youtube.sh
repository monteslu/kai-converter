#!/bin/bash

# convert_youtube.sh - Download YouTube video and convert to KAI format
# Downloads video, extracts audio, and creates KAI file with AI-generated lyrics

set -e

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS] YOUTUBE_URL [OUTPUT.kai]"
    echo ""
    echo "Download YouTube video and convert to KAI karaoke format"
    echo ""
    echo "Required:"
    echo "  --title \"TITLE\"        Song title (required for proper metadata)"
    echo "  --artist \"ARTIST\"      Artist name (required for proper metadata)"
    echo ""
    echo "Options:"
    echo "  --whisper-model MODEL  Whisper model size (default: small)"
    echo "                         Options: tiny, base, small, medium, large, large-v2, large-v3"
    echo "  --language LANG        Language code for transcription (default: en)"
    echo "                         Use 'auto' for mixed-language songs"
    echo "                         Examples: en, es, fr, de, ja, zh, ko, pt"
    echo "  --four-stems           Use 4-stem separation instead of default 2-stem"
    echo "  --fix-lyrics           Automatically fix lyrics using OpenAI after processing"
    echo "  --crepe-filter         Enable CREPE filtering to skip non-vocal chunks (default: disabled)"
    echo "  --silence-threshold DB Silence threshold in dB for chunk detection (default: -20)"
    echo "  --remove-mp3           Remove the intermediate MP3 file after conversion (default: keep)"
    echo "  --mp3-quality QUALITY  Audio quality (0=best, 9=worst, default: 0)"
    echo "  --verbose              Enable verbose logging"
    echo "  --help                 Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --title \"Bohemian Rhapsody\" --artist \"Queen\" 'https://youtube.com/watch?v=...'"
    echo "  $0 --title \"La Bamba\" --artist \"Ritchie Valens\" --language es 'URL'"
    echo "  $0 --title \"Song\" --artist \"Artist\" --language auto --whisper-model large 'URL'"
    echo "  $0 --title \"My Song\" --artist \"My Artist\" --four-stems 'URL' output.kai"
    echo "  $0 --title \"Extreme Song\" --artist \"Metal Band\" --silence-threshold -10 'URL'"
    echo ""
    echo "Requirements:"
    echo "  - yt-dlp (install with: pip install yt-dlp)"
    echo "  - ffmpeg"
    echo "  - All kai_pack.sh requirements"
    echo "  - For --fix-lyrics: OPENAI_API_KEY environment variable"
    exit 1
}

# Initialize variables
YOUTUBE_URL=""
OUTPUT_FILE=""
TITLE=""
ARTIST=""
WHISPER_MODEL=""
LANGUAGE=""
FOUR_STEMS=""
FIX_LYRICS=""
KEEP_MP3=true  # Default to keeping MP3 files
MP3_QUALITY="0"
VERBOSE=""
EXTRA_ARGS=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --help|-h)
            show_usage
            ;;
        --title)
            TITLE="$2"
            shift 2
            ;;
        --artist)
            ARTIST="$2"
            shift 2
            ;;
        --whisper-model)
            WHISPER_MODEL="--whisper-model $2"
            shift 2
            ;;
        --language)
            LANGUAGE="--language $2"
            shift 2
            ;;
        --four-stems)
            FOUR_STEMS="--four-stems"
            shift
            ;;
        --fix-lyrics)
            FIX_LYRICS="--fix-lyrics"
            shift
            ;;
        --crepe-filter)
            EXTRA_ARGS="$EXTRA_ARGS --crepe-filter"
            shift
            ;;
        --silence-threshold)
            EXTRA_ARGS="$EXTRA_ARGS --silence-threshold $2"
            shift 2
            ;;
        --remove-mp3)
            KEEP_MP3=false
            shift
            ;;
        --mp3-quality)
            MP3_QUALITY="$2"
            shift 2
            ;;
        --verbose)
            VERBOSE="--verbose"
            shift
            ;;
        --*)
            # Pass through any other options to kai_pack
            EXTRA_ARGS="$EXTRA_ARGS $1"
            if [[ -n "$2" ]] && [[ ! "$2" =~ ^-- ]]; then
                EXTRA_ARGS="$EXTRA_ARGS $2"
                shift
            fi
            shift
            ;;
        *)
            if [ -z "$YOUTUBE_URL" ]; then
                YOUTUBE_URL="$1"
            elif [ -z "$OUTPUT_FILE" ]; then
                OUTPUT_FILE="$1"
            else
                echo "Error: Too many arguments"
                echo ""
                show_usage
            fi
            shift
            ;;
    esac
done

# Check if required parameters were provided
if [ -z "$YOUTUBE_URL" ]; then
    echo "Error: YouTube URL is required"
    echo ""
    show_usage
fi

if [ -z "$TITLE" ]; then
    echo "Error: --title is required for proper metadata"
    echo ""
    show_usage
fi

if [ -z "$ARTIST" ]; then
    echo "Error: --artist is required for proper metadata"
    echo ""
    show_usage
fi

# Validate URL looks like YouTube
if ! [[ "$YOUTUBE_URL" =~ (youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/) ]]; then
    echo "Error: URL doesn't appear to be a YouTube URL"
    echo "Expected format: https://youtube.com/watch?v=... or https://youtu.be/..."
    exit 1
fi

# Check for yt-dlp
if ! command -v yt-dlp &> /dev/null; then
    echo "Error: yt-dlp is not installed"
    echo "Install with: pip install yt-dlp"
    exit 1
fi

# Check for ffmpeg
if ! command -v ffmpeg &> /dev/null; then
    echo "Error: ffmpeg is not installed"
    echo "Install ffmpeg for your system"
    exit 1
fi

echo "=========================================="
echo "YouTube to KAI Converter"
echo "=========================================="
echo "URL: $YOUTUBE_URL"

# Get video info and title
echo ""
echo "Fetching video information..."
VIDEO_TITLE=$(yt-dlp --get-title "$YOUTUBE_URL" 2>/dev/null || echo "Unknown")
VIDEO_ID=$(yt-dlp --get-id "$YOUTUBE_URL" 2>/dev/null || echo "unknown")

# Clean filename (remove problematic characters)
SAFE_TITLE=$(echo "$VIDEO_TITLE" | sed 's/[^a-zA-Z0-9 ._-]/_/g' | sed 's/__*/_/g' | sed 's/^_//;s/_$//')

echo "Title: $VIDEO_TITLE"
echo "Video ID: $VIDEO_ID"

# Set default output name if not provided
if [ -z "$OUTPUT_FILE" ]; then
    OUTPUT_FILE="${ARTIST} - ${TITLE}.kai"
fi

# Ensure output has .kai extension
if [[ ! "$OUTPUT_FILE" =~ \.kai$ ]]; then
    OUTPUT_FILE="${OUTPUT_FILE}.kai"
fi

MP3_FILE="${OUTPUT_FILE%.kai}.mp3"

echo "Output: $OUTPUT_FILE"
echo ""

# Create temp directory for download
TEMP_DIR=$(mktemp -d -t youtube_kai_XXXXXX)
trap "rm -rf $TEMP_DIR" EXIT

# Download and extract audio
echo "Downloading and extracting audio..."
echo "----------------------------------------"

# Download best audio and convert to MP3
yt-dlp \
    --extract-audio \
    --audio-format mp3 \
    --audio-quality "$MP3_QUALITY" \
    --output "$TEMP_DIR/%(title)s.%(ext)s" \
    --no-playlist \
    "$YOUTUBE_URL"

# Find the downloaded MP3 file
DOWNLOADED_MP3=$(find "$TEMP_DIR" -name "*.mp3" -type f | head -n 1)

if [ -z "$DOWNLOADED_MP3" ] || [ ! -f "$DOWNLOADED_MP3" ]; then
    echo "Error: Failed to download or convert audio"
    exit 1
fi

# Move to final MP3 location
mv "$DOWNLOADED_MP3" "$MP3_FILE"

echo "✓ Audio extracted: $MP3_FILE"

# Write ID3 tags to the MP3 file
echo "Writing ID3 tags to MP3..."
python3 -c "
import sys
try:
    from mutagen.id3 import ID3, TIT2, TPE1, TDRC, COMM
    import re
    
    mp3_file = '$MP3_FILE'
    title = '$TITLE'
    artist = '$ARTIST'
    video_title = '$VIDEO_TITLE'
    
    # Load or create ID3 tags
    try:
        tags = ID3(mp3_file)
    except:
        tags = ID3()
    
    # Add basic tags
    tags.add(TIT2(encoding=3, text=title))
    tags.add(TPE1(encoding=3, text=artist))
    
    # Try to extract year from video title or use current year
    year_match = re.search(r'(19|20)\d{2}', video_title)
    if year_match:
        tags.add(TDRC(encoding=3, text=year_match.group()))
    
    # Add comment with original YouTube title
    tags.add(COMM(encoding=3, lang='eng', desc='YouTube', text=video_title))
    
    # Save tags
    tags.save(mp3_file)
    print(f'✓ ID3 tags written: {title} by {artist}')
    
except ImportError:
    print('⚠ Warning: mutagen not available, skipping ID3 tags')
except Exception as e:
    print(f'⚠ Warning: Failed to write ID3 tags: {e}')
"

echo ""

# Convert to KAI format
echo "Converting to KAI format..."
echo "----------------------------------------"

# Build kai_pack command
KAI_PACK_CMD="./kai_pack.sh"
KAI_PACK_CMD="$KAI_PACK_CMD --title \"$TITLE\""
KAI_PACK_CMD="$KAI_PACK_CMD --artist \"$ARTIST\""
KAI_PACK_CMD="$KAI_PACK_CMD $WHISPER_MODEL"
KAI_PACK_CMD="$KAI_PACK_CMD $LANGUAGE"
KAI_PACK_CMD="$KAI_PACK_CMD $FOUR_STEMS"
KAI_PACK_CMD="$KAI_PACK_CMD $FIX_LYRICS"
KAI_PACK_CMD="$KAI_PACK_CMD $VERBOSE"
KAI_PACK_CMD="$KAI_PACK_CMD $EXTRA_ARGS"
KAI_PACK_CMD="$KAI_PACK_CMD --output \"$OUTPUT_FILE\" \"$MP3_FILE\""

echo "Running: $KAI_PACK_CMD"
echo ""

# Execute the conversion
eval $KAI_PACK_CMD

# Check if conversion was successful
if [ -f "$OUTPUT_FILE" ]; then
    echo ""
    echo "=========================================="
    echo "✓ Conversion complete!"
    echo "=========================================="
    echo "Output file: $OUTPUT_FILE"
    
    # Clean up MP3 if requested
    if [ "$KEEP_MP3" = false ]; then
        rm -f "$MP3_FILE"
        echo "MP3 file removed (use default behavior to keep)"
    else
        echo "MP3 file kept: $MP3_FILE"
    fi
    
    echo ""
    echo "Next steps:"
    echo "  - View lyrics: ./log_kai_lyrics.sh \"$OUTPUT_FILE\""
    echo "  - Create video: ./make_movie.sh \"$OUTPUT_FILE\""
else
    echo "Error: KAI conversion failed"
    exit 1
fi