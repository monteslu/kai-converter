# Standalone Python Setup

This document explains how KAI Converter creates **fully self-contained desktop apps** that end users can run with **zero technical setup**.

## Design Goal: Easy for Non-Developers

**End User Experience:**
```
1. Download KAI Converter.dmg (or .exe, .AppImage)
2. Install/run the app
3. Start creating karaoke files
   - No Python installation
   - No pip commands
   - No terminal required
   - Just works! ✅
```

## How We Achieve This

KAI Converter uses **standalone Python builds** (no compilation needed!) to bundle everything into a single app package.

### Standalone Python Builds
We use [python-build-standalone](https://github.com/indygreg/python-build-standalone) by Gregory Szorc:
- ✅ Pre-compiled Python distributions
- ✅ No system Python required
- ✅ No compilation/building needed
- ✅ Just download, extract, and bundle!

### One Simple Approach

**Both development AND production use the same standalone Python:**

```bash
# Development (same Python as production)
npm run dev:all
# Uses: python-standalone/bin/python3

# Production (bundles the same Python)
npm run package:mac
# Bundles: python-standalone/ into the app
```

**Consistency = Reliability!**
- Same Python version everywhere (3.11)
- Same packages everywhere
- If it works in dev, it works for users
- No surprises!

## Developer Setup Instructions

### First Time Setup (One Time Only)

1. **Clone and install Node dependencies:**
   ```bash
   git clone <repo>
   cd kai-converter
   npm install
   ```

2. **Download and setup standalone Python:**
   ```bash
   npm run setup:python
   ```

   This will:
   - Download Python 3.11 for your platform (macOS/Windows/Linux)
   - Extract to `python-standalone/`
   - Install ALL requirements from `requirements.txt`
     - PyTorch (CPU version)
     - Whisper
     - Demucs
     - All other dependencies
   - Takes ~5-10 minutes and downloads ~200-300MB
   - **Only need to do this once!**

3. **Run the app in development mode:**
   ```bash
   npm run dev:all
   ```

   The app will:
   - Use `python-standalone/bin/python3` (same as production)
   - Load your Python code from `src/` (hot-reloadable)
   - Start Electron + Vite dev server

### Daily Development Workflow

**Edit Python code:**
```bash
# 1. Edit files in src/kai_pack/*.py
# 2. Reload Electron (Cmd+R or Ctrl+R)
# 3. Changes take effect immediately
```

**Edit React/UI code:**
```bash
# 1. Edit files in renderer/src/**/*.jsx
# 2. Vite hot-reloads automatically
# 3. See changes instantly
```

**Add/update Python packages:**
```bash
# 1. Add package to requirements.txt
# 2. Install into standalone Python:
./python-standalone/bin/pip install -r requirements.txt
# 3. Restart dev server
```

**Build distributable app:**
```bash
# Build for your current platform
npm run package:mac     # macOS
npm run package:win     # Windows
npm run package:linux   # Linux
```

## What Gets Bundled in the Final App

When you build (`npm run package:mac`), the app includes:

```
YourApp.app/
└── Contents/
    └── Resources/
        ├── app/                           # Electron/React UI
        ├── python/                        # Complete Python installation
        │   ├── bin/python3               # Python interpreter
        │   ├── lib/python3.11/
        │   │   ├── [stdlib]              # All built-in modules
        │   │   └── site-packages/
        │   │       ├── torch/            # PyTorch (~150MB)
        │   │       ├── whisper/          # Whisper
        │   │       ├── demucs/           # Demucs
        │   │       └── ...               # All deps
        │   └── [everything Python needs]
        └── python-src/                    # Your Python code
            └── kai_pack/
                ├── api.py
                ├── processor.py
                └── ...
```

**Total app size: ~500-600MB**
- Electron + Chromium: ~200MB
- Standalone Python: ~80MB
- PyTorch CPU: ~150MB
- Other packages: ~50MB
- Your code: ~10MB

**User needs to install:** Nothing! Everything is included.

## File Structure (Development)

```
kai-converter/
├── python-standalone/         # Self-contained Python (dev + production)
│   ├── bin/python3           # macOS/Linux executable
│   ├── python.exe            # Windows executable
│   ├── lib/python3.11/
│   │   ├── [stdlib]          # Standard library
│   │   └── site-packages/    # All packages installed here
│   │       ├── torch/
│   │       ├── whisper/
│   │       └── demucs/
│   └── include/              # Python headers
├── src/                       # Your Python source code
│   └── kai_pack/             # Main package
│       ├── api.py
│       ├── processor.py
│       ├── transcription.py
│       └── ...
├── electron/                  # Electron main process
│   ├── main.js
│   ├── python-bridge.js      # Spawns Python processes
│   └── ...
├── renderer/                  # React UI
│   └── src/
│       ├── App.jsx
│       └── components/
└── venv/                      # OPTIONAL: For CLI scripts only
    └── (Not used by GUI)
```

## Cross-Platform Building

### Supported Platforms

| Platform | Architecture | Build Command | Output |
|----------|-------------|---------------|---------|
| **macOS** | Intel (x86_64) | `npm run package:mac` | `.dmg`, `.zip` |
| **macOS** | Apple Silicon (arm64) | `npm run package:mac` | `.dmg`, `.zip` |
| **Windows** | x64 | `npm run package:win` | NSIS installer, portable `.exe` |
| **Linux** | x86_64 | `npm run package:linux` | AppImage, `.deb`, `.rpm` |
| **Linux** | arm64 | `npm run package:linux` | AppImage, `.deb`, `.rpm` |

### Building for Other Platforms

**Option 1: Use GitHub Actions (Recommended)**

Set up CI/CD to build all platforms automatically:
- macOS runner builds for macOS
- Windows runner builds for Windows
- Linux runner builds for Linux

See `.github/workflows/build.yml` (to be added)

**Option 2: Build on Each Platform**

You can only build for the platform you're currently on:
```bash
# On macOS → builds for macOS
npm run setup:python
npm run package:mac

# On Windows → builds for Windows
npm run setup:python
npm run package:win

# On Linux → builds for Linux
npm run setup:python
npm run package:linux
```

## User Experience (What End Users See)

### macOS Users
1. Download `KAI-Converter-1.0.0.dmg`
2. Drag to Applications folder
3. Open KAI Converter
4. Start creating karaoke files
   - No setup wizard
   - No dependencies to install
   - Everything just works!

### Windows Users
1. Download `KAI-Converter-Setup-1.0.0.exe`
2. Run installer (or use portable version)
3. Open KAI Converter
4. Start creating karaoke files
   - No Python installation needed
   - No PATH configuration
   - Everything just works!

### Linux Users
1. Download `KAI-Converter-1.0.0.AppImage`
2. Make executable: `chmod +x KAI-Converter-*.AppImage`
3. Run the AppImage
4. Start creating karaoke files
   - No dependencies to install (AppImage is self-contained)
   - Works on any modern Linux distro
   - Everything just works!

## Benefits of This Approach

✅ **Zero User Setup**
- No Python installation required
- No pip commands
- No terminal/command line needed
- No "Install Python 3.11 first" instructions

✅ **Consistent Experience**
- Same Python version everywhere (3.11)
- Same package versions everywhere
- Identical behavior across all platforms
- No "works on my machine" issues

✅ **Professional Distribution**
- Native installers for each platform
- Code-signed apps (when configured)
- Auto-update support (via electron-updater)
- Looks and feels like any other desktop app

✅ **Developer Friendly**
- Simple development workflow
- What you test is what users get
- Easy to debug (same Python everywhere)
- Fast iteration (no rebuild needed for code changes)

## Troubleshooting

**Problem: `python-standalone not found`**
```bash
npm run setup:python
```

**Problem: Python packages missing after setup**
```bash
# Reinstall packages into standalone Python
./python-standalone/bin/pip install -r requirements.txt
```

**Problem: Want to update a package**
```bash
# Update specific package
./python-standalone/bin/pip install --upgrade package-name

# Update all packages from requirements.txt
./python-standalone/bin/pip install -r requirements.txt --upgrade
```

**Problem: App size too large?**
- This is expected: ~500-600MB for a self-contained AI app
- PyTorch alone is ~150MB
- Users prefer "download once, works forever" over complex setup

**Problem: Building for another platform**
- Build on that platform, or
- Use GitHub Actions for automated multi-platform builds
