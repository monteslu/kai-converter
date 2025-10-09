# KAI Converter

A complete toolkit for creating KAI karaoke files with AI-powered source separation, transcription, and lyrics correction.

## Features

- 🎵 **Audio stem separation** - Isolate vocals and music using Demucs v4
- 🎤 **AI lyrics transcription** - OpenAI Whisper with word-level timing
- 🌍 **Multi-language support** - Auto-detection for mixed-language songs
- ✨ **Automatic lyrics correction** - Multiple LLM providers (OpenAI, Claude, Gemini, local)
- 📺 **YouTube support** - Download and convert videos directly
- 🎬 **Karaoke video generation** - Create MP4s with synchronized lyrics
- 🎹 **Musical analysis** - Key detection, tempo, chords, and more
- 📦 **KAI v1.0 format** - Complete karaoke file packages

## Two Ways to Use KAI Converter

### 🖥️ Desktop App (GUI) - For Everyone

**Download the app, no technical setup required!**

Available for macOS, Windows, and Linux. Coming soon...

- ✅ No Python installation needed
- ✅ No command-line required
- ✅ Easy-to-use graphical interface
- ✅ Everything included in one download

### 💻 Command-Line Tools (CLI) - For Power Users

For developers and advanced users who prefer terminal workflows.

See installation instructions below.

---

## Desktop App Installation (GUI)

**Coming soon!** Pre-built desktop apps with zero dependencies will be available for download.

In the meantime, developers can build the app from source:

```bash
git clone <repo>
cd kai-converter
npm install
npm run setup:all        # One-time setup (downloads Python, AI models, ffmpeg, yt-dlp)
npm run dev:all          # Run the app in development mode
```

See [BUILDING.md](BUILDING.md) for detailed developer instructions.

---

## Command-Line Installation (CLI)

### Prerequisites

**System Requirements:**
- **Python 3.8+** (Python 3.9+ recommended)
- **ffmpeg** for audio processing
- **git** to clone the repository

### 1. Clone Repository & Setup

```bash
git clone https://github.com/your-repo/kai-converter.git
cd kai-converter
```

### 2. System Dependencies

#### macOS
```bash
# Install ffmpeg via Homebrew
brew install ffmpeg

# Or via MacPorts
sudo port install ffmpeg
```

#### Linux (Ubuntu/Debian)
```bash
sudo apt-get update
sudo apt-get install ffmpeg python3-venv python3-pip
```

#### Linux (CentOS/RHEL/Fedora)
```bash
# For Fedora/newer RHEL
sudo dnf install ffmpeg python3-venv python3-pip

# For older CentOS/RHEL (may need EPEL repository)
sudo yum install epel-release
sudo yum install ffmpeg python3-venv python3-pip
```

### 3. Python Environment Setup

**Both macOS and Linux:**

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# IMPORTANT: Always activate the virtual environment before using kai-converter:
# source venv/bin/activate

# Option 1: Use the install script (recommended)
./install.sh

# Option 2: Manual installation
pip install -r requirements.txt

# Optional: Install enhanced audio analysis packages
# These may fail on some systems (especially ARM64) but are not required
pip install numpy  # Install first if using madmom
pip install -r requirements-optional.txt --no-build-isolation

# For YouTube support
pip install yt-dlp
```

**Note for ARM64 systems (Raspberry Pi, etc.):**
- Some optional packages (madmom, essentia) may have limited support
- The core functionality works without them using librosa fallbacks
- Use `./install.sh` which handles architecture detection automatically

### Jetson Nano Installation

For NVIDIA Jetson devices, additional steps are required for CUDA support:

#### Prerequisites
1. JetPack SDK with CUDA installed
2. Verify CUDA: `nvcc --version`

#### Installation
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install NVIDIA's PyTorch wheels (required for CUDA on Jetson)
# For JetPack 5.x:
wget https://developer.download.nvidia.com/compute/redist/jp/v512/pytorch/torch-2.1.0a0+41361538.nv23.06-cp310-cp310-linux_aarch64.whl
pip install torch-2.1.0a0+41361538.nv23.06-cp310-cp310-linux_aarch64.whl

# For older JetPack, see: https://forums.developer.nvidia.com/t/pytorch-for-jetson

# Install remaining dependencies
pip install torchcrepe torchaudio
pip install -r requirements.txt
```

#### Jetson Memory Management
Jetson Nano has only 4GB RAM. To avoid out-of-memory issues:

1. **Use smaller models:**
   ```bash
   python -m kai_pack input.mp3 --whisper-model tiny
   ```

2. **Increase swap space:**
   ```bash
   sudo fallocate -l 8G /swapfile
   sudo chmod 600 /swapfile
   sudo mkswap /swapfile
   sudo swapon /swapfile
   # Add to /etc/fstab: /swapfile none swap sw 0 0
   ```

3. **Force CPU if needed:**
   ```bash
   python -m kai_pack input.mp3 --cpu
   ```

#### Troubleshooting Jetson Issues
- **NumPy conflicts:** Try `pip install "numpy<2.0"`
- **CUDA not detected:** Export CUDA paths:
  ```bash
  export PATH=/usr/local/cuda/bin:$PATH
  export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH
  ```
- **Monitor resources:** Use `tegrastats` to watch GPU/memory usage

### 4. Optional: LLM Providers for Lyrics Correction

Choose and install **only the provider you plan to use:**

```bash
# OpenAI GPT models (requires OPENAI_API_KEY)
pip install openai

# Anthropic Claude (requires ANTHROPIC_API_KEY)  
pip install anthropic

# Google Gemini (requires GEMINI_API_KEY or GOOGLE_API_KEY)
pip install google-generativeai

# Local LM Studio - no additional packages needed
# Just run LM Studio locally on localhost:1234
```

### 5. Test Installation

```bash
# Activate virtual environment (if not already active)
source venv/bin/activate

# Test basic functionality
python -c "from src.kai_pack.processor import KaiProcessor; print('✓ Installation successful!')"

# Test Whisper
python -c "import whisper; print('✓ Whisper available')"

# Test ffmpeg
ffmpeg -version | head -1
```

## GPU Acceleration (Optional)

- **NVIDIA GPUs**: CUDA acceleration supported automatically
- **Apple Silicon Macs**: MPS acceleration used automatically  
- **CPU-only**: Works fine, just slower for processing

## Common Issues & Solutions

### macOS
- **"No module named 'X'"**: Make sure virtual environment is activated: `source venv/bin/activate`
- **Permission errors**: Use `pip install --user` if needed
- **Apple Silicon**: Some packages may need Rosetta 2: `arch -x86_64 pip install package`

### Linux
- **Missing Python headers**: `sudo apt-get install python3-dev`
- **Audio issues**: `sudo apt-get install libasound2-dev libportaudio2`
- **Build failures**: `sudo apt-get install build-essential`

### General
- **FFmpeg not found**: Ensure ffmpeg is in PATH, test with `ffmpeg -version`
- **Out of memory**: Use `--chunk-size` parameter or smaller Whisper model
- **Slow processing**: Enable GPU acceleration or use smaller models

## Quick Start

**⚠️ IMPORTANT:** Always activate the virtual environment before using kai-converter:

```bash
source venv/bin/activate
```

All main functionality is available through simple shell scripts in the `cli/` directory:

### 1. Convert Audio to KAI

```bash
# Basic conversion (2-stem: vocals + music, English)
./cli/kai_pack.sh song.mp3

# With options
./cli/kai_pack.sh --language es --whisper-model large --four-stems song.mp3

# Auto-fix lyrics with OpenAI
export OPENAI_API_KEY="your-key"
./cli/kai_pack.sh --fix-lyrics --language auto song.mp3
```

### 2. Convert YouTube to KAI

```bash
# Download and convert YouTube video
./cli/convert_youtube.sh --title "Song Name" --artist "Artist" 'https://youtube.com/watch?v=...'

# With language detection and auto-fixing
./cli/convert_youtube.sh \
  --title "Mixed Language Song" \
  --artist "Artist" \
  --language auto \
  --fix-lyrics \
  'https://youtu.be/...'
```

### 3. Batch Process MP3 Files

```bash
# Process all MP3 files in a folder (skips existing KAI files)
./cli/batch_pack.sh /path/to/music/folder/

# With options (passed to each file)
./cli/batch_pack.sh --language auto --fix-lyrics --llm-provider openai /music/albums/

# See what would be processed without doing it
./cli/batch_pack.sh --dry-run /music/test/

# High quality batch processing
./cli/batch_pack.sh --four-stems --whisper-model large-v3 --fix-lyrics /music/collection/
```

### 4. View and Fix Lyrics

```bash
# View lyrics from KAI file
./cli/log_kai_lyrics.sh song.kai

### 5. Regenerate Lyrics (Optional)

```bash
# Regenerate lyrics with better Whisper model
./cli/regen_lyrics.sh song.kai

# Use different Whisper model
./cli/regen_lyrics.sh --whisper-model large-v3 song.kai

# Regenerate with different language
./cli/regen_lyrics.sh --language es song.kai
```

### 6. Fix Lyrics (Optional)

```bash
# Fix lyrics manually (auto-fetch)
export OPENAI_API_KEY="your-key"
./cli/fix_lyrics.sh song.kai

# Fix lyrics with custom source
./cli/fix_lyrics.sh song.kai --lyrics-source https://genius.com/song-url

# Fix lyrics with custom output
./cli/fix_lyrics.sh song.kai --output song_corrected.kai

# Use different LLM providers
./cli/fix_lyrics.sh song.kai --llm-provider lmstudio      # Local LM Studio
./cli/fix_lyrics.sh song.kai --llm-provider anthropic     # Anthropic Claude
./cli/fix_lyrics.sh song.kai --llm-provider gemini        # Google Gemini
./cli/fix_lyrics.sh song.kai --llm-provider openai        # OpenAI (default)
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
./cli/fix_lyrics.sh song.kai --llm-provider openai --llm-model gpt-4o

export ANTHROPIC_API_KEY="your-key"
./cli/fix_lyrics.sh song.kai --llm-provider anthropic --llm-model claude-3-5-sonnet-20241022

export GEMINI_API_KEY="your-key"
./cli/fix_lyrics.sh song.kai --llm-provider gemini --llm-model gemini-1.5-pro

# Local LM Studio (free, private) - model chosen in LM Studio GUI
./cli/fix_lyrics.sh song.kai --llm-provider lmstudio
```

### 7. Create Karaoke Video

```bash
# Generate MP4 karaoke video with synchronized lyrics (instrumental only)
./cli/make_movie.sh song.kai

# Include vocals in the video
./cli/make_movie.sh --with-vocals song.kai

# Custom output name
./cli/make_movie.sh song.kai my_video.mp4

# Custom output with vocals
./cli/make_movie.sh --with-vocals song.kai full_version.mp4
```

## Script Options

### kai_pack.sh Options
- `--whisper-model MODEL` - Whisper model: tiny, base, small, medium, large, large-v2, large-v3
- `--language LANG` - Language code (en, es, fr, de, ja, etc.) or 'auto' for detection
- `--four-stems` - Use 4-stem separation instead of default 2-stem
- `--fix-lyrics` - Automatically fix lyrics with OpenAI after processing
- `--crepe-filter` - Enable CREPE filtering to skip non-vocal chunks (default: disabled)
- `--silence-threshold DB` - Silence threshold in dB for chunk detection (default: -20, lower = more sensitive)
- `--verbose` - Detailed logging

### convert_youtube.sh Options  
- `--title "TITLE"` - Song title (required)
- `--artist "ARTIST"` - Artist name (required)
- All kai_pack.sh options are supported (including --crepe-filter and --silence-threshold)
- `--keep-mp3` - Keep intermediate MP3 file

## Extreme Vocals & Metal

For extreme vocals (death metal, black metal, screaming, etc.), the default CREPE filtering may skip vocal sections. Use these settings:

```bash
# For extreme vocals - disable CREPE filtering, increase sensitivity
./kai_pack.sh --silence-threshold -10 --whisper-model large-v3 extreme_song.mp3

# For YouTube extreme vocals
./convert_youtube.sh \
  --title "Multinational Corporations" \
  --artist "Napalm Death" \
  --silence-threshold -10 \
  --whisper-model large-v3 \
  'https://youtube.com/watch?v=...'
```

**What these settings do:**
- **No `--crepe-filter`**: Processes all audio chunks instead of filtering non-vocal sections
- **`--silence-threshold -10`**: More sensitive to quiet/distorted vocals (default: -20)
- **`--whisper-model large-v3`**: Best accuracy for difficult vocals

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
├── regen_song_json.sh     # Regenerate transcription/analysis
├── fix_lyrics.sh          # Fix lyrics with LLM
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