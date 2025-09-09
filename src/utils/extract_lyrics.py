#!/usr/bin/env python3
"""Extract and display lyrics from a .kai file."""

import json
import zipfile
import sys
from pathlib import Path

def extract_lyrics(kai_file: str):
    """Extract lyrics from .kai file and display them."""
    kai_path = Path(kai_file)
    
    if not kai_path.exists():
        print(f"Error: {kai_file} not found")
        return
    
    try:
        with zipfile.ZipFile(kai_path, 'r') as kai_zip:
            # Extract song.json
            song_json_data = kai_zip.read('song.json').decode('utf-8')
            song_data = json.loads(song_json_data)
            
            # Display file info
            print("=" * 60)
            print(f"KAI FILE: {kai_path.name}")
            print("=" * 60)
            print(f"Title: {song_data.get('song', {}).get('title', 'Unknown')}")
            print(f"Artist: {song_data.get('song', {}).get('artist', 'Unknown')}")
            print(f"Duration: {song_data.get('song', {}).get('duration_sec', 0):.1f}s")
            print(f"KAI Version: {song_data.get('kai_version', 'unknown')}")
            
            # Display transcription info
            lines = song_data.get('lines', [])
            meta = song_data.get('meta', {})
            processing = meta.get('processing', {})
            alignment = processing.get('alignment', {})
            
            print(f"Transcription Method: {alignment.get('method', 'unknown')}")
            print(f"Confidence: {alignment.get('confidence', 0.0):.2f}")
            print(f"Lines Found: {len(lines)}")
            
            # Display lyrics
            print("\n" + "=" * 60)
            print("DETECTED LYRICS")
            print("=" * 60)
            
            if lines:
                for i, line in enumerate(lines, 1):
                    text = line.get('text', '').strip()
                    start = line.get('start', 0)
                    end = line.get('end', 0)
                    singer = line.get('singer_id', 'A')
                    
                    if text:  # Only show non-empty lines
                        print(f"[{start:6.1f}s - {end:6.1f}s] ({singer}) {text}")
            else:
                print("No lyrics found in transcription")
            
            # Display file contents
            contents = kai_zip.namelist()
            print(f"\n" + "=" * 60)
            print(f"KAI FILE CONTENTS ({len(contents)} files)")
            print("=" * 60)
            for file in sorted(contents):
                info = kai_zip.getinfo(file)
                print(f"{file:<20} {info.file_size:>10,} bytes")
                
            print("=" * 60)
            
    except Exception as e:
        print(f"Error reading KAI file: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python extract_lyrics.py <file.kai>")
        sys.exit(1)
    
    extract_lyrics(sys.argv[1])