#!/bin/bash

# rename_mp3.sh - Rename MP3 files based on ID3 tags
# Usage: ./rename_mp3.sh <folder_path>

# Check if folder argument is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <folder_path>"
    echo "Example: $0 /path/to/music/folder"
    exit 1
fi

FOLDER="$1"

# Check if folder exists
if [ ! -d "$FOLDER" ]; then
    echo "Error: Folder '$FOLDER' does not exist"
    exit 1
fi

# Check if ffprobe is available
if ! command -v ffprobe &> /dev/null; then
    echo "Error: ffprobe is required but not installed"
    echo "Install it with: brew install ffmpeg (on macOS) or apt install ffmpeg (on Ubuntu)"
    exit 1
fi

# Function to clean filename (remove invalid characters)
clean_filename() {
    local filename="$1"
    # Remove/replace characters that are invalid in filenames
    echo "$filename" | sed 's/[\/\\:*?"<>|]/_/g' | sed 's/[[:space:]]*$//'
}

# Counter for processed files
processed=0
renamed=0
skipped=0

echo "Processing MP3 files in: $FOLDER"
echo "----------------------------------------"

# Find all MP3 files and process them
find "$FOLDER" -name "*.mp3" -type f | while read -r mp3_file; do
    ((processed++))
    
    echo "Processing: $(basename "$mp3_file")"
    
    # Extract artist and title using ffprobe
    artist=$(ffprobe -v quiet -show_entries format_tags=artist -of default=noprint_wrappers=1:nokey=1 "$mp3_file" 2>/dev/null)
    title=$(ffprobe -v quiet -show_entries format_tags=title -of default=noprint_wrappers=1:nokey=1 "$mp3_file" 2>/dev/null)
    
    # Check if both artist and title exist and are not empty
    if [ -n "$artist" ] && [ -n "$title" ]; then
        # Clean the artist and title for filename use
        clean_artist=$(clean_filename "$artist")
        clean_title=$(clean_filename "$title")
        
        # Create new filename
        new_filename="${clean_artist} - ${clean_title}.mp3"
        new_filepath="$(dirname "$mp3_file")/$new_filename"
        
        # Check if the file already has the correct name
        current_filename=$(basename "$mp3_file")
        if [ "$current_filename" = "$new_filename" ]; then
            echo "  ✓ Already correctly named"
            ((skipped++))
        else
            # Check if target file already exists
            if [ -e "$new_filepath" ]; then
                echo "  ⚠ Target file already exists: $new_filename"
                ((skipped++))
            else
                # Rename the file
                if mv "$mp3_file" "$new_filepath"; then
                    echo "  ✓ Renamed to: $new_filename"
                    ((renamed++))
                else
                    echo "  ✗ Failed to rename"
                fi
            fi
        fi
    else
        echo "  ⚠ Missing ID3 tags - Artist: '$artist', Title: '$title'"
        ((skipped++))
    fi
    
    echo ""
done

# Final summary
echo "----------------------------------------"
echo "Processing complete!"
echo "Files processed: $processed"
echo "Files renamed: $renamed" 
echo "Files skipped: $skipped"