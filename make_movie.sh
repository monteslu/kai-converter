#!/bin/bash

# make_movie.sh - Create a karaoke video from a KAI file
# Usage: ./make_movie.sh input.kai [output.mp4]

set -e

if [ $# -eq 0 ]; then
    echo "Usage: $0 INPUT.kai [OUTPUT.mp4]"
    echo ""
    echo "Create a karaoke video from a KAI file"
    echo ""
    echo "Features:"
    echo "  - Displays synchronized lyrics from KAI file"
    echo "  - Skips lyrics marked with disabled=true"
    echo "  - Shows progress bars during instrumental gaps (5+ seconds)"
    echo "  - Supports both 'lines' and 'lyrics' JSON fields"
    echo "  - Uses instrumental mix (music.mp3 if available, or combines stems)"
    echo ""
    echo "Arguments:"
    echo "  INPUT.kai    Input KAI file (required)"
    echo "  OUTPUT.mp4   Output video file (optional, defaults to INPUT.mp4)"
    echo ""
    echo "Examples:"
    echo "  $0 song.kai                    # Creates song.mp4"
    echo "  $0 song.kai karaoke.mp4        # Custom output name"
    echo "  $0 \"My Song.kai\" \"My Video.mp4\"  # Files with spaces"
    echo ""
    echo "Requirements:"
    echo "  - ffmpeg (for video generation)"
    echo "  - python3 (for JSON processing)"
    echo "  - unzip (for KAI extraction)"
    exit 1
fi

KAI_FILE="$1"
OUTPUT="${2:-${KAI_FILE%.kai}.mp4}"

if [ ! -f "$KAI_FILE" ]; then
    echo "Error: KAI file '$KAI_FILE' not found"
    exit 1
fi

echo "Creating karaoke video from $KAI_FILE..."

# Create temp directory
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

# Extract KAI file
echo "Extracting KAI file..."
unzip -q "$KAI_FILE" -d "$TEMP_DIR"

# Read metadata from song.json
echo "Reading metadata..."
TITLE=$(python3 -c "import json; data=json.load(open('$TEMP_DIR/song.json')); print(data['song']['title'])")
ARTIST=$(python3 -c "import json; data=json.load(open('$TEMP_DIR/song.json')); print(data['song']['artist'])")
DURATION=$(python3 -c "import json; data=json.load(open('$TEMP_DIR/song.json')); print(data['song']['duration_sec'])")


echo "Title: $TITLE"
echo "Artist: $ARTIST"
echo "Duration: ${DURATION}s"

# Check if music.mp3 exists, otherwise create instrumental mix from stems
if [ -f "$TEMP_DIR/music.mp3" ]; then
    echo "Using existing music.mp3..."
    cp "$TEMP_DIR/music.mp3" "$TEMP_DIR/instrumental.wav"
else
    echo "Creating instrumental mix from stems..."
    ffmpeg -y -i "$TEMP_DIR/drums.mp3" -i "$TEMP_DIR/bass.mp3" -i "$TEMP_DIR/other.mp3" \
        -filter_complex "[0:a][1:a][2:a]amix=inputs=3:duration=longest:dropout_transition=2" \
        "$TEMP_DIR/instrumental.wav"
fi

# Generate drawtext filters for each lyric line
echo "Generating lyric overlays..."
python3 -c "
import json
import sys
import textwrap

data = json.load(open('$TEMP_DIR/song.json'))

# Check for both 'lines' and 'lyrics' fields
lyrics_data = data.get('lyrics', data.get('lines', []))

def wrap_text(text, max_chars=50):
    '''Wrap text to fit on screen, preserving word boundaries'''
    if len(text) <= max_chars:
        return [text]
    
    # Use textwrap to break at word boundaries
    wrapped_lines = textwrap.wrap(text, width=max_chars, break_long_words=False)
    return wrapped_lines[:2]  # Limit to 2 lines max

with open('$TEMP_DIR/lyric_filters.txt', 'w') as f:
    # First pass: collect all lines with timing (including disabled ones for gap calculation)
    all_lines = []
    active_lines = []
    
    for i, line in enumerate(lyrics_data):
        if 'start' in line and 'end' in line:
            disabled = line.get('disabled', False)
            # Explicitly check if disabled is True (boolean or string)
            is_disabled = disabled is True or disabled == 'true' or disabled == True
            text = line.get('text', '')[:50]  # First 50 chars for logging
            status = 'DISABLED' if is_disabled else 'ENABLED'
            
            
            all_lines.append(line)
            if not is_disabled:
                active_lines.append(line)
    
    # Sort both lists by start time
    all_lines.sort(key=lambda x: x['start'])
    active_lines.sort(key=lambda x: x['start'])
    
    # Check for intro gap (start to first lyric)
    if len(active_lines) > 0:
        first_lyric_start = active_lines[0]['start']
        if first_lyric_start >= 5.0:  # 5+ second intro
            gap_start = 0
            gap_end = first_lyric_start
            
            # Add progress bar background first - bigger and centered
            progress_bg = f\"drawbox=x=560:y=490:w=800:h=50:color=gray@0.8:t=fill:enable='between(t,{gap_start},{gap_end})',\"
            f.write(progress_bg + '\n')
            
            # Add progress bar fill using a simple time-based approach - draw multiple small rectangles for ultra-smooth animation
            for i in range(100):  # Draw 100 segments of 8px each for 800px width
                segment_start_time = gap_start + (gap_end - gap_start) * i / 100
                segment_x = 560 + i * 8
                segment_filter = f\"drawbox=x={segment_x}:y=490:w=8:h=50:color=green@0.9:t=fill:enable='gte(t,{segment_start_time})*between(t,{gap_start},{gap_end})',\"
                f.write(segment_filter + '\n')
    
    # Second pass: detect gaps between active lines and add progress bars
    for i, line in enumerate(active_lines):
        start_time = line['start']
        end_time = line['end']
        
        # Check for gap before this line (except first line)
        if i > 0:
            prev_end = active_lines[i-1]['end']
            gap_duration = start_time - prev_end
            
            if gap_duration >= 5.0:  # 5+ second gap
                gap_start = prev_end
                gap_end = start_time
                
                # Add progress bar background first - bigger and centered
                progress_bg = f\"drawbox=x=560:y=490:w=800:h=50:color=gray@0.8:t=fill:enable='between(t,{gap_start},{gap_end})',\"
                f.write(progress_bg + '\n')
                
                # Add progress bar fill using a simple time-based approach - draw multiple small rectangles for ultra-smooth animation
                for i in range(100):  # Draw 100 segments of 8px each for 800px width
                    segment_start_time = gap_start + (gap_end - gap_start) * i / 100
                    segment_x = 560 + i * 8
                    segment_filter = f\"drawbox=x={segment_x}:y=490:w=8:h=50:color=green@0.9:t=fill:enable='gte(t,{segment_start_time})*between(t,{gap_start},{gap_end})',\"
                    f.write(segment_filter + '\n')
        
        # Add the actual lyric text (only for active/non-disabled lines)
        text = line.get('text', '').replace(\"'\", \"\\\\''\").replace(':', '\\\\:')
        
        # Wrap long text into multiple lines
        text_lines = wrap_text(text)
        
        # Create separate drawtext filter for each line
        for j, text_line in enumerate(text_lines):
            # Calculate vertical position: center minus offset for multiple lines
            if len(text_lines) == 1:
                y_pos = '(h-text_h)/2'  # Single line - center
            else:
                # Multiple lines - offset from center
                y_offset = (j - (len(text_lines)-1)/2) * 80  # 80px spacing between lines
                y_pos = f'(h-text_h)/2+{y_offset}'
            
            filter_line = f\"drawtext=text='{text_line}':fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:fontsize=64:fontcolor=white:x=(w-text_w)/2:y={y_pos}:borderw=4:bordercolor=black:enable='between(t,{start_time},{end_time})',\"
            f.write(filter_line + '\n')
"

# Create simple background video (solid color only)
echo "Creating background..."
ffmpeg -y -f lavfi -i "color=c=0x1a1a2e:size=1920x1080:duration=$DURATION" \
    -c:v libx264 -pix_fmt yuv420p "$TEMP_DIR/background.mp4"

# Combine background, audio, and lyric overlays
echo "Creating final karaoke video..."
LYRIC_FILTERS=$(cat "$TEMP_DIR/lyric_filters.txt" | tr '\n' ' ')
ffmpeg -y -i "$TEMP_DIR/background.mp4" -i "$TEMP_DIR/instrumental.wav" \
    -c:v libx264 -c:a aac -b:a 192k \
    -vf "drawtext=text='$TITLE':fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:fontsize=48:fontcolor=white:x=(w-text_w)/2:y=h/3:enable='between(t,0,5)',
         drawtext=text='by $ARTIST':fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:fontsize=32:fontcolor=gray:x=(w-text_w)/2:y=h/3+80:enable='between(t,0,5)',
         ${LYRIC_FILTERS%,}" \
    -shortest "$OUTPUT"

echo "Karaoke video created: $OUTPUT"
echo "Video info:"
ffprobe -v quiet -show_format -show_streams "$OUTPUT" | grep -E "(duration|bit_rate|width|height)" | head -5