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

### macOS Setup

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Cython first (required for madmom)
pip install Cython

# Install all dependencies
pip install -r requirements.txt

# Install madmom separately if it fails above
pip install madmom --no-build-isolation

# For YouTube support
pip install yt-dlp

# For lyrics correction - install packages for your chosen LLM provider:
pip install openai              # For OpenAI GPT models  
pip install anthropic           # For Anthropic Claude models
pip install google-generativeai # For Google Gemini models (REQUIRED if using Gemini)
# Local LM Studio requires no additional packages

# Note: You only need to install the package for the provider you plan to use
```

### Linux Setup

```bash
# Install dependencies
pip install -r requirements.txt

# For YouTube support (or use system package: sudo apt install yt-dlp)
pip install yt-dlp

# For lyrics correction - install packages for your chosen LLM provider:
pip install openai              # For OpenAI GPT models
pip install anthropic           # For Anthropic Claude models  
pip install google-generativeai # For Google Gemini models (REQUIRED if using Gemini)
# Local LM Studio requires no additional packages
```

## Requirements

- Python 3.10+
- ffmpeg (for audio/video processing)
- yt-dlp (for YouTube downloads)
- GPU acceleration supported: CUDA (NVIDIA) or MPS (Apple Silicon)

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
*Note: Apple Silicon Macs will automatically use MPS acceleration for faster processing.*

**Windows:**
- Install ffmpeg from https://ffmpeg.org/download.html

## Quick Start

**Note for macOS users:** Remember to activate your virtual environment before running commands:
```bash
source venv/bin/activate
```

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

# Use different LLM providers
./fix_lyrics.sh song.kai --llm-provider lmstudio      # Local LM Studio
./fix_lyrics.sh song.kai --llm-provider anthropic     # Anthropic Claude  
./fix_lyrics.sh song.kai --llm-provider gemini        # Google Gemini
./fix_lyrics.sh song.kai --llm-provider openai        # OpenAI (default)
```

#### LLM Provider Options

The lyrics correction feature supports multiple AI providers:

- **OpenAI** (default): Requires `OPENAI_API_KEY` environment variable
- **LM Studio** (local): Free local inference, requires LM Studio running on localhost:1234  
- **Anthropic Claude**: Requires `ANTHROPIC_API_KEY` environment variable
- **Google Gemini**: Requires `GEMINI_API_KEY` or `GOOGLE_API_KEY` environment variable
- **OpenAI-compatible**: For Ollama, Together.ai, etc. (specify `--llm-base-url`)

```bash
# Examples with different providers
export OPENAI_API_KEY="your-key"
./fix_lyrics.sh song.kai --llm-provider openai --llm-model gpt-4o

export ANTHROPIC_API_KEY="your-key" 
./fix_lyrics.sh song.kai --llm-provider anthropic --llm-model claude-3-5-sonnet-20241022

export GEMINI_API_KEY="your-key"
./fix_lyrics.sh song.kai --llm-provider gemini --llm-model gemini-1.5-pro

# Local LM Studio (free, private) - model chosen in LM Studio GUI
./fix_lyrics.sh song.kai --llm-provider lmstudio
```

### 4. Create Karaoke Video

```bash
# Generate MP4 karaoke video with synchronized lyrics (instrumental only)
./make_movie.sh song.kai

# Include vocals in the video
./make_movie.sh --with-vocals song.kai

# Custom output name
./make_movie.sh song.kai my_video.mp4

# Custom output with vocals
./make_movie.sh --with-vocals song.kai full_version.mp4
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

# 2. Create karaoke video (instrumental)
./make_movie.sh song.kai

# Or with vocals included
./make_movie.sh --with-vocals song.kai
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

# Or include vocals for sing-along version
./make_movie.sh --with-vocals "Bohemian Rhapsody.kai"
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

# Or with vocals for reference
./make_movie.sh --with-vocals song_fixed.kai
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

## LLM Provider System

The KAI Converter features a flexible LLM (Large Language Model) abstraction system for lyrics correction, supporting multiple AI providers with automatic fallback and consistent performance.

### Supported Providers

| Provider | Type | Cost | Setup Required | Default Model |
|----------|------|------|----------------|---------------|
| **OpenAI** | Cloud API | Paid | `OPENAI_API_KEY` | gpt-4o |
| **Google Gemini** | Cloud API | Paid | `GEMINI_API_KEY` | gemini-1.5-pro |
| **Anthropic Claude** | Cloud API | Paid | `ANTHROPIC_API_KEY` | claude-3-5-sonnet |
| **LM Studio** | Local | Free | Local setup | Selected in GUI |
| **OpenAI-Compatible** | Various | Varies | Custom endpoint | Custom |

### Auto-Detection

The system automatically detects available providers in this order:
1. **OpenAI** (if `OPENAI_API_KEY` environment variable exists)
2. **Anthropic** (if `ANTHROPIC_API_KEY` exists)  
3. **Google Gemini** (if `GEMINI_API_KEY` or `GOOGLE_API_KEY` exists)
4. **LM Studio** (fallback - assumes localhost:1234)

### Provider Comparison

**OpenAI GPT-4o**
- ✅ Excellent instruction following
- ✅ Large context window  
- ✅ Reliable, well-tested
- ❌ Most expensive option
- 💡 Best for: High-quality corrections, production use

**Google Gemini 1.5 Pro**
- ✅ Competitive quality
- ✅ Large context window (2M tokens)
- ✅ Often cheaper than OpenAI
- ✅ Multiple model tiers (Pro/Flash)
- 💡 Best for: Cost-conscious users wanting cloud quality

**Anthropic Claude 3.5**
- ✅ Strong reasoning capabilities
- ✅ Conservative, thoughtful corrections
- ✅ Good instruction following
- ❌ More expensive than Gemini
- 💡 Best for: Users preferring Claude's correction style

**Local LM Studio**
- ✅ Completely free and private
- ✅ No API key required
- ✅ Works offline
- ❌ Requires local GPU/powerful CPU
- ❌ Model quality varies
- 💡 Best for: Privacy-focused users, unlimited usage

### Quick Setup Examples

**OpenAI (recommended for beginners)**
```bash
export OPENAI_API_KEY="sk-your-key-here"
./fix_lyrics.sh song.kai  # Auto-detects and uses OpenAI
```

**Google Gemini (great value)**
```bash
export GEMINI_API_KEY="your-gemini-key"
./fix_lyrics.sh song.kai --llm-provider gemini --llm-model gemini-1.5-flash  # Faster/cheaper
```

**LM Studio (free and private)**
```bash
# 1. Download and install LM Studio from https://lmstudio.ai/
# 2. Download and load a model (see recommendations below)
# 3. Start local server on port 1234
./fix_lyrics.sh song.kai --llm-provider lmstudio
```

**Recommended models for lyrics correction:**
- **Llama 3.1 8B Instruct** - Best overall quality/speed balance, works well on 16GB RAM
- **Mistral 7B Instruct v0.2** - Faster, lower memory (8GB RAM), still good quality  
- **Qwen2.5 7B Instruct** - Excellent instruction following, good for text correction
- **CodeLlama 7B Instruct** - Surprisingly good at structured text tasks
- **Phi-3 Medium 14B** - High quality but requires more memory (24GB+ RAM)

**Memory requirements:**
- 7B models: ~8GB RAM minimum, ~12GB recommended
- 8B models: ~10GB RAM minimum, ~16GB recommended  
- 14B+ models: ~20GB+ RAM required

**Performance tips:**
- Enable GPU acceleration if you have a compatible GPU (RTX 3060+)
- Use quantized models (Q4_K_M) for better speed with minimal quality loss
- Close other memory-intensive apps while running larger models

**Custom providers (advanced)**
```bash
# Ollama example
./fix_lyrics.sh song.kai --llm-provider openai-compatible --llm-base-url http://localhost:11434 --llm-model llama3
```

### Advanced Configuration

All providers support these options:
- `--llm-model`: Override default model
- `--llm-api-key`: Override environment variable  
- `--llm-base-url`: Custom endpoint (for compatible APIs)

**Model recommendations by provider:**
- **OpenAI**: `gpt-4o` (best), `gpt-4` (cheaper), `gpt-3.5-turbo` (budget)
- **Gemini**: `gemini-1.5-pro` (quality), `gemini-1.5-flash` (speed/cost)
- **Claude**: `claude-3-5-sonnet-20241022` (latest), `claude-3-haiku-20240307` (budget)
- **LM Studio**: Model selected in GUI (recommended: Llama 3.1 8B+ Instruct)

## Technical Details

- **Source Separation**: Demucs v4 with htdemucs_ft model
- **Transcription**: OpenAI Whisper with word-level timestamps  
- **Key Detection**: CREPE pitch analysis + Krumhansl-Schmuckler algorithm
- **Lyrics Correction**: Multi-provider LLM system (OpenAI, Gemini, Claude, Local) with conservative error fixing
- **Video Generation**: FFmpeg with synchronized lyrics, progress bars, and optional vocal tracks
- **Audio Quality**: MP3 encoding at configurable bitrates (default 160k stems, 128k vocals)