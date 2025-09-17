#!/usr/bin/env python3
"""Extract and log lyrics with timing from a .kai file."""

import json
import zipfile
import sys
from pathlib import Path

def log_kai_lyrics(kai_file: str):
    """Extract lyrics from .kai file and log them with timing."""
    kai_path = Path(kai_file)
    
    if not kai_path.exists():
        print(f"Error: {kai_file} not found")
        return False
    
    try:
        with zipfile.ZipFile(kai_path, 'r') as kai_zip:
            # Extract song.json
            song_json_data = kai_zip.read('song.json').decode('utf-8')
            song_data = json.loads(song_json_data)
            
            # Get basic info
            title = song_data.get('song', {}).get('title', 'Unknown')
            artist = song_data.get('song', {}).get('artist', 'Unknown')
            duration = song_data.get('song', {}).get('duration_sec', 0)
            
            # Get transcription info
            lines = song_data.get('lines', [])
            meta = song_data.get('meta', {})
            processing = meta.get('processing', {})
            alignment = processing.get('alignment', {})
            
            method = alignment.get('method', 'unknown')
            confidence = alignment.get('confidence', 0.0)
            
            print("=" * 80)
            print(f"KAI LYRICS LOG: {kai_path.name}")
            print("=" * 80)
            print(f"Title: {title}")
            print(f"Artist: {artist}")
            print(f"Duration: {duration:.1f}s")
            print(f"Transcription Method: {method}")
            print(f"Overall Confidence: {confidence:.3f}")
            print(f"Lines Found: {len(lines)}")
            print("=" * 80)
            
            if not lines:
                print("No lyrics found in transcription")
                return True
            
            print("LYRICS WITH TIMING & DURATION")
            print("=" * 80)
            
            for i, line in enumerate(lines, 1):
                text = line.get('text', '').strip()
                start = line.get('start', 0)
                end = line.get('end', 0)
                duration_line = end - start
                singer = line.get('singer_id', 'A')
                
                if text:  # Only show non-empty lines
                    print(f"{i:2d}. [{start:7.2f}s - {end:7.2f}s] ({duration_line:5.2f}s) ({singer}) \"{text}\"")
            
            print("=" * 80)
            print(f"Total segments: {len([l for l in lines if l.get('text', '').strip()])}")

            # Calculate timing coverage
            if lines:
                first_line = min(l.get('start', float('inf')) for l in lines if l.get('text', '').strip())
                last_line = max(l.get('end', 0) for l in lines if l.get('text', '').strip())
                coverage = (last_line - first_line) / duration * 100 if duration > 0 else 0
                print(f"Vocal coverage: {first_line:.1f}s to {last_line:.1f}s ({coverage:.1f}% of song)")

            # Check for rejected lyric corrections
            corrections = meta.get('corrections', {})
            rejected_corrections = corrections.get('rejected', [])

            if rejected_corrections:
                print("=" * 80)
                print("REJECTED LYRIC CORRECTIONS")
                print("=" * 80)
                for i, rejection in enumerate(rejected_corrections, 1):
                    line_num = rejection.get('line', 'Unknown')
                    start = rejection.get('start', 0)
                    end = rejection.get('end', 0)
                    reason = rejection.get('reason', 'No reason given')
                    old_text = rejection.get('old', 'N/A')
                    new_text = rejection.get('new', 'N/A')
                    retention = rejection.get('word_retention', 0.0)

                    print(f"Rejection {i}: Line {line_num} [{start:.1f}s - {end:.1f}s]")
                    print(f"  Reason: {reason}")
                    print(f"  Word retention: {retention:.1%}")
                    print(f"  OLD: {old_text}")
                    print(f"  NEW: {new_text}")
                    print()

            # Check for missing lines suggestions
            missing_lines = corrections.get('missing_lines_suggested', [])

            if missing_lines:
                print("=" * 80)
                print("SUGGESTED MISSING LINES")
                print("=" * 80)
                for i, suggestion in enumerate(missing_lines, 1):
                    start = suggestion.get('start', 0)
                    end = suggestion.get('end', 0)
                    text = suggestion.get('suggested_text', 'N/A')
                    confidence = suggestion.get('confidence', 'unknown')
                    reason = suggestion.get('reason', 'No reason given')
                    pitch = suggestion.get('pitch_activity', 'N/A')

                    print(f"Suggestion {i}: [{start:.1f}s - {end:.1f}s] ({end-start:.1f}s)")
                    print(f"  Text: \"{text}\"")
                    print(f"  Confidence: {confidence}")
                    print(f"  Reason: {reason}")
                    print(f"  Pitch activity: {pitch}")
                    print()

            print("=" * 80)
            return True
            
    except Exception as e:
        print(f"Error reading KAI file: {e}")
        return False

def main():
    if len(sys.argv) != 2:
        print("Usage: python log_kai_lyrics.py <file.kai>")
        print("       ./log_kai_lyrics.py <file.kai>")
        sys.exit(1)
    
    kai_file = sys.argv[1]
    success = log_kai_lyrics(kai_file)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()