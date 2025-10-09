# Building KAI Converter from Source

This guide is for developers who want to build, modify, or contribute to KAI Converter.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Project Structure](#project-structure)
3. [Development Workflow](#development-workflow)
4. [Building for Distribution](#building-for-distribution)
5. [Cross-Platform Builds](#cross-platform-builds)
6. [Architecture](#architecture)

---

## Quick Start

### Prerequisites

- **Node.js** 18+ (for Electron and Vite)
- **npm** 9+
- **Git**

**That's it!** No Python installation needed - the setup script downloads everything.

### Setup Steps

```bash
# 1. Clone the repository
git clone <repo-url>
cd kai-converter

# 2. Install Node dependencies
npm install

# 3. Download and setup all dependencies (one-time, ~5-10 minutes)
npm run setup:all

# 4. Run the app in development mode
npm run dev:all
```

**What `npm run setup:all` does:**
- Downloads Python 3.12 standalone build for your platform (~50MB)
- Extracts to `python-standalone/`
- Installs all Python dependencies:
  - PyTorch (CPU version, ~150MB)
  - Whisper (~50MB)
  - Demucs (~50MB)
  - All other requirements from `requirements.txt`
- Downloads platform-specific binaries:
  - ffmpeg (~100MB) - for audio encoding
  - yt-dlp (~10MB) - for YouTube downloads
- Total: ~400MB download, ~600MB installed

### Verify Setup

```bash
# Check standalone Python
./python-standalone/bin/python3 --version
# Should show: Python 3.11.x

# Check packages are installed
./python-standalone/bin/pip list | grep torch
./python-standalone/bin/pip list | grep whisper
./python-standalone/bin/pip list | grep demucs

# Run the app
npm run dev:all
```

---

## Project Structure

```
kai-converter/
├── electron/                      # Electron main process (Node.js)
│   ├── main.js                   # App entry point, window management
│   ├── preload.cjs               # Security bridge (CommonJS required)
│   ├── python-bridge.js          # Spawns Python processes, parses output
│   ├── system-checker.js         # Detects Python/dependencies
│   └── download-manager.js       # Downloads models (optional)
│
├── renderer/                      # React frontend (Vite)
│   ├── index.html                # HTML entry
│   └── src/
│       ├── App.jsx               # Main app with routing
│       ├── components/           # React components
│       │   ├── ConvertScreen.jsx
│       │   ├── BatchScreen.jsx
│       │   ├── SettingsScreen.jsx
│       │   └── SetupWizard.jsx
│       └── index.css             # Tailwind imports
│
├── src/                           # Python backend
│   └── kai_pack/                 # Main Python package
│       ├── api.py                # GUI-friendly API facade
│       ├── processor.py          # Core processing orchestrator
│       ├── transcription.py      # Whisper transcription
│       ├── separation.py         # Demucs stem separation
│       ├── alignment.py          # Lyrics alignment
│       ├── analysis.py           # Musical analysis
│       └── packaging.py          # KAI file creation
│
├── scripts/                       # Build scripts
│   └── setup-python.js           # Downloads standalone Python
│
├── python-standalone/             # Self-contained Python (gitignored)
│   ├── bin/python3               # Python interpreter
│   └── lib/python3.11/
│       └── site-packages/        # All packages
│
├── cli/                           # Shell scripts for CLI users
│   ├── kai_pack.sh
│   ├── batch_pack.sh
│   └── ...
│
├── venv/                          # Optional: for CLI scripts only
│
├── package.json                   # Node dependencies, build config
├── vite.config.js                # Vite configuration
├── tailwind.config.js            # Tailwind CSS config
├── requirements.txt              # Python dependencies
├── README.md                      # User-facing documentation
├── BUILDING.md                    # This file (developer guide)
└── PYTHON_SETUP.md                # Detailed Python bundling info
```

---

## Development Workflow

### Running in Development Mode

```bash
npm run dev:all
```

This starts:
1. **Vite dev server** on http://localhost:5174 (React UI with hot reload)
2. **Electron app** that loads the Vite server

**What Python it uses:**
- `python-standalone/bin/python3` (same as production build!)
- Ensures: "If it works in dev, it works for users"

### Editing Code

**React/UI changes (hot reload):**
```bash
# 1. Edit files in renderer/src/
# 2. Vite automatically reloads
# 3. See changes instantly in Electron
```

**Python code changes (manual reload):**
```bash
# 1. Edit files in src/kai_pack/
# 2. Reload Electron (Cmd+R / Ctrl+R)
# 3. Changes take effect immediately
```

**Electron main process changes (restart required):**
```bash
# 1. Edit files in electron/
# 2. Stop npm run dev:all (Ctrl+C)
# 3. Restart: npm run dev:all
```

### Adding Python Packages

```bash
# 1. Add package to requirements.txt
echo "your-package==1.2.3" >> requirements.txt

# 2. Install into standalone Python
./python-standalone/bin/pip install -r requirements.txt

# 3. Restart dev server (if running)
npm run dev:all
```

### Adding Node Packages

```bash
# For runtime dependencies
npm install package-name

# For development tools
npm install --save-dev package-name
```

### Running Python Scripts Directly (Testing)

```bash
# Test the API facade
./python-standalone/bin/python3 -c "
from src.kai_pack.api import KaiAPI
api = KaiAPI()
print('API loaded successfully!')
"

# Test processing
./python-standalone/bin/python3 -m src.kai_pack.cli input.mp3
```

---

## Building for Distribution

### Build for Your Current Platform

```bash
# macOS
npm run package:mac
# Output: dist-electron/KAI-Converter-1.0.0.dmg

# Windows (only works on Windows)
npm run package:win
# Output: dist-electron/KAI-Converter-Setup-1.0.0.exe

# Linux (only works on Linux)
npm run package:linux
# Output: dist-electron/KAI-Converter-1.0.0.AppImage
```

### What Gets Bundled

The built app includes:

```
YourApp.app/Contents/Resources/
├── app/                           # Your Electron code
├── python/                        # Complete standalone Python
│   ├── bin/python3
│   └── lib/python3.11/
│       └── site-packages/
│           ├── torch/             # ~150MB
│           ├── whisper/
│           ├── demucs/
│           └── [all deps]
└── python-src/                    # Your Python source
    └── kai_pack/
```

**Total app size:** ~500-600MB
- Self-contained
- Zero dependencies
- Works offline

### Build Process

```bash
npm run package:mac
```

This:
1. Runs `vite build` → builds React UI to `renderer/dist/`
2. Copies `python-standalone/` → app's `Resources/python/`
3. Copies `src/` → app's `Resources/python-src/`
4. Copies `electron/` → app's main process
5. Creates installer (`.dmg`, `.exe`, etc.)

---

## Cross-Platform Builds

### The Challenge

You **cannot build for other platforms** from your current machine because:
- Each platform needs its own standalone Python build
- Native modules differ per platform
- electron-builder limitations

### Solution: GitHub Actions (Recommended)

Use CI/CD to build all platforms automatically.

**Example workflow** (`.github/workflows/build.yml`):

```yaml
name: Build Multi-Platform

on:
  push:
    branches: [main]
  release:
    types: [created]

jobs:
  build-mac:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: 18
      - run: npm install
      - run: npm run setup:python
      - run: npm run package:mac
      - uses: actions/upload-artifact@v3
        with:
          name: mac-builds
          path: dist-electron/*.dmg

  build-windows:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: 18
      - run: npm install
      - run: npm run setup:python
      - run: npm run package:win
      - uses: actions/upload-artifact@v3
        with:
          name: windows-builds
          path: dist-electron/*.exe

  build-linux:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: 18
      - run: npm install
      - run: npm run setup:python
      - run: npm run package:linux
      - uses: actions/upload-artifact@v3
        with:
          name: linux-builds
          path: dist-electron/*.AppImage
```

**Benefits:**
- ✅ Free on GitHub
- ✅ Builds all platforms in parallel
- ✅ Each platform gets correct Python + dependencies
- ✅ Automatic on every push/release

---

## Architecture

### Communication Flow

```
┌─────────────────────────────────────┐
│  React UI (renderer/src/)           │
│  - User interactions                │
│  - Display results                  │
└──────────────┬──────────────────────┘
               │
               │ IPC (contextBridge)
               ↓
┌─────────────────────────────────────┐
│  Electron Main (electron/)          │
│  - Window management                │
│  - Python process spawning          │
│  - File system access               │
└──────────────┬──────────────────────┘
               │
               │ spawn() Python subprocess
               ↓
┌─────────────────────────────────────┐
│  Python Backend (src/kai_pack/)     │
│  - Audio processing (Demucs)        │
│  - Transcription (Whisper)          │
│  - KAI file generation              │
└─────────────────────────────────────┘
```

### Python Integration

**PythonBridge (`electron/python-bridge.js`):**
- Spawns `python-standalone/bin/python3`
- Passes arguments as JSON via command-line
- Reads `PROGRESS:` and `RESULT:` from stdout
- Returns structured results to Electron

**KaiAPI (`src/kai_pack/api.py`):**
- GUI-friendly facade over KaiProcessor
- Accepts progress callbacks
- Returns structured dicts (not exit codes)
- No subprocess calls internally

**Example flow:**
```javascript
// Electron calls Python
const result = await pythonBridge.processAudio({
  inputFile: '/path/to/song.mp3',
  whisperModel: 'small',
  language: 'en'
});

// Python responds with:
{
  success: true,
  output_file: '/path/to/song.kai',
  processing_time: 45.2,
  lines_count: 32
}
```

### Why Standalone Python?

**Alternatives considered:**
1. ❌ **PyInstaller** - Complex, large bundles, compilation needed
2. ❌ **System Python** - Users must install, version conflicts
3. ❌ **Virtual env** - Not portable, needs system Python
4. ✅ **Standalone builds** - No compilation, portable, consistent

**Benefits:**
- Pre-built binaries (no compilation)
- Fully portable (copy entire folder)
- Consistent versions (dev = production)
- Zero user setup required

---

## Troubleshooting

**Problem: `python-standalone not found`**
```bash
npm run setup:python
```

**Problem: Vite port already in use**
```bash
# Kill process on port 5174
lsof -ti:5174 | xargs kill
# Or edit vite.config.js to use different port
```

**Problem: Electron won't start**
```bash
# Clear node_modules and reinstall
rm -rf node_modules package-lock.json
npm install
```

**Problem: Python packages missing**
```bash
./python-standalone/bin/pip install -r requirements.txt
```

**Problem: Build fails**
```bash
# Clean build artifacts
rm -rf dist-electron renderer/dist
# Rebuild
npm run build
npm run package:mac
```

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes
4. Test thoroughly: `npm run dev:all`
5. Build to ensure it works: `npm run package:mac`
6. Commit: `git commit -am "Add feature"`
7. Push: `git push origin feature-name`
8. Create a Pull Request

---

## Additional Resources

- [PYTHON_SETUP.md](PYTHON_SETUP.md) - Detailed Python bundling explanation
- [README.md](README.md) - User-facing documentation
- [Electron Documentation](https://www.electronjs.org/docs)
- [Vite Documentation](https://vitejs.dev/)
- [python-build-standalone](https://github.com/indygreg/python-build-standalone)
