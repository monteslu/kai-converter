# KAI Converter

A complete toolkit for creating KAI karaoke files with AI-powered source separation, transcription, and lyrics correction. Convert audio files, YouTube videos, and generate karaoke videos with synchronized lyrics.

## Features

- **2-stem/4-stem separation** using Demucs v4 (default: vocals + music, optional: vocals/drums/bass/other)
- **AI lyrics transcription** using OpenAI Whisper with word-level timing
- **Multi-language support** including auto-detection for mixed-language songs
- **Automatic lyrics correction** using OpenAI GPT models
- **YouTube video downloading** and conversion
- **Karaoke video generation** with progress bars and synchronized lyrics
- **Musical analysis** with key detection (F0, notes, tempo, keys, chords, onsets, MFCC)
- **KAI v1.0 format** compliant output

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# For YouTube support (or use system package: sudo apt install yt-dlp)
pip install yt-dlp

# For lyrics correction
pip install openai
```

## Requirements

- Python 3.10+
- ffmpeg (for audio/video processing)
- yt-dlp (for YouTube downloads)

### System Dependencies

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install ffmpeg yt-dlp
```

**macOS:**
```bash
brew install ffmpeg
```

**Windows:**
- Install ffmpeg from https://ffmpeg.org/download.html

## Quick Start

All main functionality is available through simple shell scripts:

### 1. Convert Audio to KAI

```bash
# Basic conversion (2-stem: vocals + music, English)
./kai_pack.sh song.mp3

# With options
./kai_pack.sh --language es --whisper-model large --four-stems song.mp3

# Auto-fix lyrics with OpenAI
export OPENAI_API_KEY="your-key"
./kai_pack.sh --fix-lyrics --language auto song.mp3
```

### 2. Convert YouTube to KAI

```bash
# Download and convert YouTube video
./convert_youtube.sh --title "Song Name" --artist "Artist" 'https://youtube.com/watch?v=...'

# With language detection and auto-fixing
./convert_youtube.sh \
  --title "Mixed Language Song" \
  --artist "Artist" \
  --language auto \
  --fix-lyrics \
  'https://youtu.be/...'
```

### 3. View and Fix Lyrics

```bash
# View lyrics from KAI file
./log_kai_lyrics.sh song.kai

# Fix lyrics manually (auto-fetch)
export OPENAI_API_KEY="your-key"
./fix_lyrics.sh song.kai

# Fix lyrics with custom source
./fix_lyrics.sh song.kai --lyrics-source https://genius.com/song-url

# Fix lyrics with custom output
./fix_lyrics.sh song.kai --output song_corrected.kai
```

### 4. Create Karaoke Video

```bash
# Generate MP4 karaoke video with synchronized lyrics
./make_movie.sh song.kai

# Custom output name
./make_movie.sh song.kai my_video.mp4
```

## Script Options

### kai_pack.sh Options
- `--whisper-model MODEL` - Whisper model: tiny, base, small, medium, large, large-v2, large-v3
- `--language LANG` - Language code (en, es, fr, de, ja, etc.) or 'auto' for detection
- `--four-stems` - Use 4-stem separation instead of default 2-stem
- `--fix-lyrics` - Automatically fix lyrics with OpenAI after processing
- `--verbose` - Detailed logging

### convert_youtube.sh Options  
- `--title "TITLE"` - Song title (required)
- `--artist "ARTIST"` - Artist name (required)
- All kai_pack.sh options are supported
- `--keep-mp3` - Keep intermediate MP3 file

## Example Workflows

### From Local Audio File
```bash
# 1. Convert with auto-fixing
export OPENAI_API_KEY="your-key"
./kai_pack.sh --fix-lyrics --whisper-model large song.mp3

# 2. Create karaoke video
./make_movie.sh song.kai
```

### From YouTube Video
```bash
# 1. Download, convert, and auto-fix in one step
export OPENAI_API_KEY="your-key"
./convert_youtube.sh \
  --title "Bohemian Rhapsody" \
  --artist "Queen" \
  --language auto \
  --fix-lyrics \
  'https://youtube.com/watch?v=fJ9rUzIMcZQ'

# 2. Create karaoke video
./make_movie.sh "Bohemian Rhapsody.kai"
```

### Manual Lyrics Correction
```bash
# 1. Basic conversion
./kai_pack.sh --language ja song.mp3

# 2. Check lyrics
./log_kai_lyrics.sh song.kai

# 3. Fix manually if needed
export OPENAI_API_KEY="your-key"
./fix_lyrics.sh song.kai

# 4. Create video
./make_movie.sh song_fixed.kai
```

## KAI File Format

KAI files are ZIP archives containing:
- `song.json` - Metadata, lyrics with timing, and audio configuration
- **2-stem mode** (default): `vocals.mp3`, `music.mp3`  
- **4-stem mode**: `vocals.mp3`, `drums.mp3`, `bass.mp3`, `other.mp3`
- `features/` - Optional musical analysis data

## Project Structure

```
kai-converter/
├── kai_pack.sh           # Convert audio to KAI
├── convert_youtube.sh     # Download YouTube and convert
├── fix_lyrics.sh          # Fix lyrics with OpenAI  
├── log_kai_lyrics.sh      # View KAI file lyrics
├── make_movie.sh          # Create karaoke videos
├── src/                   # Python source code
│   └── kai_pack/          # Main processing package
├── docs/                  # Documentation
└── README.md
```

## Technical Details

- **Source Separation**: Demucs v4 with htdemucs_ft model
- **Transcription**: OpenAI Whisper with word-level timestamps  
- **Key Detection**: CREPE pitch analysis + Krumhansl-Schmuckler algorithm
- **Lyrics Correction**: OpenAI GPT models with conservative error fixing
- **Video Generation**: FFmpeg with synchronized lyrics and progress bars
- **Audio Quality**: MP3 encoding at configurable bitrates (default 160k stems, 128k vocals)