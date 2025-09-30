# KAI Converter - GUI Development Plan

## Overview

This document outlines the plan for building an Electron-based GUI for KAI Converter while maintaining backward compatibility with all existing command-line scripts and workflows.

## Table of Contents

1. [Architecture Goals](#architecture-goals)
2. [Necessary Refactoring](#necessary-refactoring)
3. [Electron App Structure](#electron-app-structure)
4. [System Detection & Setup](#system-detection--setup)
5. [Building & Packaging](#building--packaging)
6. [Distribution with GitHub Actions](#distribution-with-github-actions)
7. [Backward Compatibility](#backward-compatibility)

---

## Architecture Goals

### Current State (✅ Good Foundation)

**Strengths:**
- Clean modular Python structure (`src/kai_pack/`)
- Thin shell script wrappers (`kai_pack.sh`, `batch_pack.sh`)
- Well-separated concerns (audio, separation, transcription, analysis)
- Core processor orchestrator pattern (`processor.py`)

**Flexibility Score: 7.5/10**
- Core logic is in importable Python classes ✅
- Each processing step is a separate method ✅
- Some subprocess calls bypass clean API ⚠️
- Progress reporting is log-based, not callback-based ⚠️

### GUI Integration Goals

1. **Create clean Python API layer** for GUI consumption
2. **Add progress callbacks** instead of just logging
3. **Remove subprocess dependencies** between Python modules
4. **Maintain all existing CLI scripts** unchanged for power users
5. **Smart system detection** to avoid unnecessary downloads
6. **Cross-platform packaging** (Windows, macOS, Linux)

---

## Necessary Refactoring

### 1. Create API Facade (`src/kai_pack/api.py`)

**Purpose:** Clean interface between Electron and Python backend, separate from CLI

```python
# src/kai_pack/api.py
"""
Clean API for GUI integration.
Provides progress callbacks, structured errors, and direct function calls.
"""

from typing import Callable, Optional, Dict, Any
from pathlib import Path
from .processor import KaiProcessor
from utils.fix_lyrics import fix_lyrics_direct  # New direct import version

class KaiAPI:
    """
    High-level API for GUI integration.
    Provides callbacks, structured responses, and better error handling.
    """

    def __init__(self, progress_callback: Optional[Callable] = None):
        self.progress_callback = progress_callback or self._default_progress
        self.processor = None

    def _default_progress(self, stage: str, percent: float, message: str):
        """Default progress handler (no-op)."""
        pass

    def process_audio(
        self,
        input_audio: Path,
        output_path: Path,
        whisper_model: str = "small",
        language: str = "en",
        fix_lyrics: bool = False,
        llm_provider: str = "auto",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Process audio with progress callbacks.

        Returns:
            {
                "success": bool,
                "output_file": str,
                "processing_time": float,
                "lines_count": int,
                "confidence": float,
                "error": str (if failed)
            }
        """
        try:
            # Create processor
            self.processor = KaiProcessor(
                whisper_model=whisper_model,
                language=language,
                **kwargs
            )

            # Hook into processor stages for progress
            self._emit_progress("loading", 0, "Loading audio...")

            # Process (main work happens here)
            result = self.processor.process(
                input_audio=input_audio,
                output_path=output_path,
                **kwargs
            )

            self._emit_progress("processing", 90, "Processing complete")

            # Fix lyrics if requested (direct call, not subprocess)
            if fix_lyrics:
                self._emit_progress("fixing_lyrics", 95, "Correcting lyrics...")
                fix_lyrics_direct(
                    kai_file=output_path,
                    llm_provider=llm_provider,
                    progress_callback=self._emit_progress
                )

            self._emit_progress("complete", 100, "Done!")

            return {
                "success": True,
                "output_file": str(output_path),
                "processing_time": result["processing_time_seconds"],
                "lines_count": len(result["processing_stats"].get("lines_aligned", [])),
                "confidence": result["processing_stats"].get("alignment_confidence", 0)
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }

    def _emit_progress(self, stage: str, percent: float, message: str):
        """Emit progress update."""
        if self.progress_callback:
            self.progress_callback(stage, percent, message)
```

**Key Improvements:**
- No `subprocess.run()` calls
- Structured return values (dicts, not exit codes)
- Progress callbacks for GUI updates
- Exceptions instead of `sys.exit()`

### 2. Refactor `fix_lyrics.py` for Direct Import

**Current Issue:** `cli.py:180-236` calls `fix_lyrics.py` via subprocess

**Solution:** Extract core logic into importable function

```python
# src/utils/fix_lyrics.py

def fix_lyrics_direct(
    kai_file: Path,
    lyrics_source: Optional[str] = None,
    llm_provider: str = "auto",
    llm_model: Optional[str] = None,
    progress_callback: Optional[Callable] = None
) -> Dict[str, Any]:
    """
    Fix lyrics directly (no subprocess).

    Returns:
        {
            "success": bool,
            "corrections_made": int,
            "confidence": float,
            "error": str (if failed)
        }
    """
    # Core logic here (extract from main())
    pass

# Keep CLI interface for backward compatibility
def main():
    """CLI interface - calls fix_lyrics_direct()"""
    # Existing argparse code
    result = fix_lyrics_direct(...)
    sys.exit(0 if result["success"] else 1)
```

### 3. Replace Temp File Communication

**Current Issue:** `cli.py:166-178` uses temp files to pass LRCLIB lyrics between processes

**Solution:** Pass data directly as function parameters

```python
# Before (fragile):
temp_info_file = os.path.join(tempfile.gettempdir(), f"lrclib_lyrics_path_{os.getpid()}.txt")
with open(temp_info_file, 'w') as f:
    f.write(lyrics_temp_file)

# After (clean):
fix_lyrics_direct(
    kai_file=output_path,
    lyrics_source=lyrics_temp_file,  # Direct parameter
    llm_provider=llm_provider
)
```

### 4. Add Progress Callbacks to Processor

**Modify `src/kai_pack/processor.py`:**

```python
class KaiProcessor:
    def __init__(self, ..., progress_callback: Optional[Callable] = None):
        self.progress_callback = progress_callback
        # ...

    def _emit_progress(self, step: int, total: int, message: str):
        """Emit progress event."""
        if self.progress_callback:
            percent = (step / total) * 100
            self.progress_callback(f"step_{step}", percent, message)
        # Still log as before for CLI users
        logger.info(message)

    def process(self, ...):
        # Before each major step:
        self._emit_progress(1, 9, "Loading audio...")
        # ... do work

        self._emit_progress(2, 9, "Extracting metadata...")
        # ... do work
```

### 5. Refactoring Summary Checklist

- [ ] Create `src/kai_pack/api.py` - clean GUI facade
- [ ] Extract `fix_lyrics_direct()` function from `fix_lyrics.py`
- [ ] Remove temp file communication, use direct parameters
- [ ] Add `progress_callback` parameter to `KaiProcessor`
- [ ] Replace `sys.exit()` with exceptions in API layer
- [ ] Add `src/utils/system_check.py` (already created ✅)
- [ ] Keep all CLI scripts unchanged (they use existing code paths)

**Estimated Refactoring Time:** 1-2 days

---

## Electron App Structure

### Project Layout

```
kai-converter/
├── src/                          # Existing Python code (unchanged)
│   ├── kai_pack/
│   │   ├── api.py               # NEW: GUI API facade
│   │   ├── processor.py         # Modified: add callbacks
│   │   ├── cli.py               # Unchanged: CLI still works
│   │   └── ...
│   └── utils/
│       ├── system_check.py      # NEW: system detection
│       ├── fix_lyrics.py        # Modified: extract direct function
│       └── ...
│
├── electron/                     # NEW: Electron app
│   ├── main.js                  # Main process (Node.js)
│   ├── preload.js               # Security bridge
│   ├── python-bridge.js         # Python subprocess manager
│   ├── system-checker.js        # Uses system_check.py
│   ├── download-manager.js      # Model/dependency downloader
│   └── menu.js                  # App menu
│
├── renderer/                     # NEW: Frontend (React/Vue/plain JS)
│   ├── index.html
│   ├── app.js
│   ├── components/
│   │   ├── SetupScreen.jsx      # System check & downloads
│   │   ├── MainScreen.jsx       # Audio processing UI
│   │   ├── SettingsScreen.jsx   # Config & model management
│   │   ├── BatchScreen.jsx      # Batch processing
│   │   └── ProgressBar.jsx      # Real-time progress
│   └── styles/
│       └── app.css
│
├── resources/                    # NEW: Bundled resources
│   ├── bin/                     # Platform-specific binaries
│   │   ├── ffmpeg-win.exe
│   │   ├── ffmpeg-mac
│   │   ├── ffmpeg-linux
│   │   └── ffprobe-*
│   └── python/                  # Python distribution (optional)
│
├── scripts/                      # NEW: Build scripts
│   ├── build-python.js          # PyInstaller packaging
│   ├── download-ffmpeg.js       # Download static FFmpeg
│   └── bundle-models.js         # Optional: pre-bundle models
│
├── *.sh                          # Existing CLI scripts (unchanged)
├── package.json                  # NEW: Electron dependencies
├── electron-builder.yml          # NEW: Build configuration
└── requirements.txt              # Existing Python deps (unchanged)
```

### Technology Stack

**Frontend:**
- **Electron** 28+ (Chromium + Node.js)
- **React** 18+ (or Vue 3, or vanilla JS)
- **Vite** for fast dev builds
- **TailwindCSS** or custom CSS

**Backend Bridge:**
- **Python subprocess** via `child_process.spawn()`
- **JSON-RPC** or **REST API** (Python HTTP server)
- **IPC** for Electron main ↔ renderer communication

**Packaging:**
- **electron-builder** for installers
- **PyInstaller** or **PyOxidizer** for Python bundle
- **GitHub Actions** for CI/CD

### Communication Architecture

```
┌─────────────────────────────────────────────────────┐
│  Electron Renderer (React UI)                       │
│  - User interactions                                │
│  - Progress displays                                │
│  - File selection                                   │
└──────────────────┬──────────────────────────────────┘
                   │ IPC (contextBridge)
                   ↓
┌─────────────────────────────────────────────────────┐
│  Electron Main Process (Node.js)                    │
│  - Window management                                │
│  - Python process spawning                          │
│  - File system access                               │
│  - Download management                              │
└──────────────────┬──────────────────────────────────┘
                   │ spawn() / HTTP
                   ↓
┌─────────────────────────────────────────────────────┐
│  Python Backend (KaiAPI)                            │
│  - Audio processing                                 │
│  - AI transcription                                 │
│  - Stem separation                                  │
│  - Lyrics correction                                │
└─────────────────────────────────────────────────────┘
```

### Key Files

#### `electron/main.js`

```javascript
const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const PythonBridge = require('./python-bridge');
const SystemChecker = require('./system-checker');

let mainWindow;
let pythonBridge;
let systemChecker;

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
    }
  });

  mainWindow.loadFile('renderer/index.html');

  // Initialize Python bridge
  const pythonPath = app.isPackaged
    ? path.join(process.resourcesPath, 'python', 'kai_converter')
    : 'python3';

  pythonBridge = new PythonBridge(pythonPath);
  systemChecker = new SystemChecker(pythonPath, process.resourcesPath);

  // Check system on startup
  const systemStatus = await systemChecker.checkSystem();
  mainWindow.webContents.send('system-status', systemStatus);
}

// IPC Handlers
ipcMain.handle('check-system', async () => {
  return await systemChecker.checkSystem();
});

ipcMain.handle('process-audio', async (event, options) => {
  return await pythonBridge.processAudio(options, (progress) => {
    mainWindow.webContents.send('progress', progress);
  });
});

ipcMain.handle('download-component', async (event, componentId) => {
  // Download manager implementation
  return await downloadManager.download(componentId);
});

app.whenReady().then(createWindow);
```

#### `electron/python-bridge.js`

```javascript
const { spawn } = require('child_process');
const path = require('path');

class PythonBridge {
  constructor(pythonPath) {
    this.pythonPath = pythonPath;
    this.apiScript = path.join(__dirname, '..', 'src', 'kai_pack', 'api.py');
  }

  async processAudio(options, progressCallback) {
    return new Promise((resolve, reject) => {
      const args = [
        this.apiScript,
        '--input', options.inputPath,
        '--output', options.outputPath,
        '--whisper-model', options.whisperModel || 'small',
        '--language', options.language || 'en',
        '--json-output'  // Return structured JSON
      ];

      if (options.fixLyrics) {
        args.push('--fix-lyrics', '--llm-provider', options.llmProvider || 'auto');
      }

      const process = spawn(this.pythonPath, args, {
        env: {
          ...process.env,
          FFMPEG_PATH: this.getFFmpegPath()
        }
      });

      let stdout = '';
      let stderr = '';

      process.stdout.on('data', (data) => {
        const lines = data.toString().split('\n');
        lines.forEach(line => {
          if (line.startsWith('PROGRESS:')) {
            // Parse progress JSON
            const progress = JSON.parse(line.substring(9));
            progressCallback(progress);
          } else if (line.trim()) {
            stdout += line + '\n';
          }
        });
      });

      process.stderr.on('data', (data) => {
        stderr += data.toString();
      });

      process.on('close', (code) => {
        if (code === 0) {
          try {
            resolve(JSON.parse(stdout));
          } catch (e) {
            reject(new Error(`Failed to parse output: ${e.message}`));
          }
        } else {
          reject(new Error(`Processing failed: ${stderr}`));
        }
      });
    });
  }

  getFFmpegPath() {
    // Return bundled FFmpeg path
    const platform = process.platform;
    const ffmpegName = platform === 'win32' ? 'ffmpeg.exe' : 'ffmpeg';
    return path.join(process.resourcesPath, 'bin', ffmpegName);
  }
}

module.exports = PythonBridge;
```

#### `electron/preload.js` (Security Bridge)

```javascript
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  // System check
  checkSystem: () => ipcRenderer.invoke('check-system'),

  // Audio processing
  processAudio: (options) => ipcRenderer.invoke('process-audio', options),

  // Progress events
  onProgress: (callback) => {
    ipcRenderer.on('progress', (event, progress) => callback(progress));
  },

  // Download components
  downloadComponent: (componentId, progressCallback) => {
    return ipcRenderer.invoke('download-component', componentId);
  },

  // File dialogs
  selectAudioFile: () => ipcRenderer.invoke('select-audio-file'),
  selectOutputFolder: () => ipcRenderer.invoke('select-output-folder'),

  // Settings
  saveSettings: (settings) => ipcRenderer.invoke('save-settings', settings),
  loadSettings: () => ipcRenderer.invoke('load-settings'),
});
```

#### `renderer/components/MainScreen.jsx` (Example)

```jsx
import React, { useState } from 'react';

function MainScreen() {
  const [inputFile, setInputFile] = useState(null);
  const [processing, setProcessing] = useState(false);
  const [progress, setProgress] = useState({ stage: '', percent: 0, message: '' });

  // Listen for progress events
  React.useEffect(() => {
    window.electronAPI.onProgress((progressData) => {
      setProgress(progressData);
    });
  }, []);

  async function handleSelectFile() {
    const file = await window.electronAPI.selectAudioFile();
    setInputFile(file);
  }

  async function handleProcess() {
    setProcessing(true);

    try {
      const result = await window.electronAPI.processAudio({
        inputPath: inputFile,
        outputPath: inputFile.replace(/\.[^.]+$/, '.kai'),
        whisperModel: 'small',
        language: 'en',
        fixLyrics: true,
        llmProvider: 'auto'
      });

      if (result.success) {
        alert(`Success! Created ${result.output_file}`);
      } else {
        alert(`Error: ${result.error}`);
      }
    } catch (error) {
      alert(`Error: ${error.message}`);
    } finally {
      setProcessing(false);
    }
  }

  return (
    <div className="main-screen">
      <h1>KAI Converter</h1>

      <div className="file-selector">
        <button onClick={handleSelectFile}>Select Audio File</button>
        {inputFile && <p>Selected: {inputFile}</p>}
      </div>

      <button
        onClick={handleProcess}
        disabled={!inputFile || processing}
      >
        {processing ? 'Processing...' : 'Create KAI File'}
      </button>

      {processing && (
        <div className="progress">
          <div className="progress-bar" style={{ width: `${progress.percent}%` }} />
          <p>{progress.message}</p>
        </div>
      )}
    </div>
  );
}

export default MainScreen;
```

---

## System Detection & Setup

See `src/utils/system_check.py` (already implemented) for comprehensive system detection.

### Setup Wizard Flow

```
1. App Launch
   ↓
2. Run System Check (system_check.py --json)
   ↓
3. Evaluate Results:
   ├─ All Required Components? → Go to Main App
   ├─ Missing FFmpeg? → Show Download Option
   ├─ Missing PyTorch? → Show Download Option (CPU/CUDA)
   ├─ Missing Whisper Models? → Show Download Options
   └─ Low Disk Space? → Warn User
   ↓
4. Download Missing Components
   ├─ Show Progress Bars
   ├─ Verify Downloads (checksums)
   └─ Re-run System Check
   ↓
5. All Ready → Main App
```

### Smart Detection Features

✅ **FFmpeg:**
- Check system PATH first
- Use bundled version if needed
- Show version and source to user

✅ **Python/PyTorch:**
- Detect CPU vs GPU support
- Recommend CUDA if NVIDIA GPU found
- Allow CPU-only for compatibility

✅ **Whisper Models:**
- List already-downloaded models
- Show disk usage per model
- Allow selective downloads

✅ **Disk Space:**
- Warn if < 10GB free
- Show total size before downloading
- Allow custom model location

✅ **LLM Providers:**
- Detect API keys from environment
- Test connectivity to LM Studio
- Optional setup (not required)

---

## Building & Packaging

### Development Setup

```bash
# Install Electron dependencies
cd kai-converter
npm init -y
npm install --save-dev electron electron-builder vite

# Install frontend dependencies (if using React)
npm install react react-dom

# Development mode
npm run dev  # Starts Vite + Electron
```

### `package.json`

```json
{
  "name": "kai-converter",
  "version": "1.0.0",
  "description": "AI-powered karaoke file creator",
  "main": "electron/main.js",
  "scripts": {
    "dev": "vite",
    "dev:electron": "electron .",
    "build": "vite build && electron-builder",
    "build:python": "node scripts/build-python.js",
    "build:all": "npm run build:python && npm run build",
    "package:win": "electron-builder --win",
    "package:mac": "electron-builder --mac",
    "package:linux": "electron-builder --linux"
  },
  "devDependencies": {
    "electron": "^28.0.0",
    "electron-builder": "^24.0.0",
    "vite": "^5.0.0",
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  },
  "build": {
    "appId": "com.kaiconverter.app",
    "productName": "KAI Converter",
    "files": [
      "electron/**/*",
      "renderer/dist/**/*",
      "resources/**/*"
    ],
    "extraResources": [
      {
        "from": "dist/python",
        "to": "python"
      },
      {
        "from": "resources/bin",
        "to": "bin"
      }
    ],
    "win": {
      "target": ["nsis", "portable"],
      "icon": "resources/icon.ico"
    },
    "mac": {
      "target": ["dmg", "zip"],
      "icon": "resources/icon.icns",
      "category": "public.app-category.music"
    },
    "linux": {
      "target": ["AppImage", "deb", "rpm"],
      "icon": "resources/icon.png",
      "category": "Audio"
    }
  }
}
```

### Building Python Backend

#### `scripts/build-python.js`

```javascript
const { execSync } = require('child_process');
const fs = require('fs-extra');
const path = require('path');

async function buildPython() {
  console.log('Building Python backend with PyInstaller...');

  // Create spec file for PyInstaller
  const specContent = `
# kai_converter.spec
import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ['src/kai_pack/__main__.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('src/kai_pack', 'kai_pack'),
        ('src/utils', 'utils'),
    ],
    hiddenimports=[
        'torch',
        'torchaudio',
        'whisper',
        'demucs',
        'torchcrepe',
        'librosa',
        'soundfile',
        'mutagen',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='kai_converter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='kai_converter',
)
`;

  fs.writeFileSync('kai_converter.spec', specContent);

  // Run PyInstaller
  execSync('pyinstaller kai_converter.spec --clean', { stdio: 'inherit' });

  // Copy to dist directory
  const distDir = path.join(__dirname, '..', 'dist', 'python');
  fs.ensureDirSync(distDir);
  fs.copySync('dist/kai_converter', distDir);

  console.log('✅ Python backend built successfully');
}

buildPython().catch(console.error);
```

### Download FFmpeg

#### `scripts/download-ffmpeg.js`

```javascript
const https = require('https');
const fs = require('fs-extra');
const path = require('path');
const { execSync } = require('child_process');

const FFMPEG_URLS = {
  win32: 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip',
  darwin: 'https://evermeet.cx/ffmpeg/getrelease/ffmpeg/zip',
  linux: 'https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz'
};

async function downloadFFmpeg() {
  const platform = process.platform;
  const url = FFMPEG_URLS[platform];

  console.log(`Downloading FFmpeg for ${platform}...`);

  const binDir = path.join(__dirname, '..', 'resources', 'bin');
  fs.ensureDirSync(binDir);

  // Download and extract logic here
  // ... (implementation)

  console.log('✅ FFmpeg downloaded successfully');
}

downloadFFmpeg().catch(console.error);
```

### Build Commands

```bash
# Development
npm run dev              # Run in dev mode with hot reload

# Build Python backend
npm run build:python     # PyInstaller → dist/python/

# Build Electron app
npm run build            # Vite build + electron-builder

# Platform-specific builds
npm run package:win      # Windows installer
npm run package:mac      # macOS DMG
npm run package:linux    # Linux AppImage/deb/rpm

# Complete build (everything)
npm run build:all        # Python + Electron + all platforms
```

### Package Sizes

| Component | Size | Included? |
|-----------|------|-----------|
| Electron framework | 200 MB | ✅ Always |
| Python runtime | 50 MB | ✅ Always |
| PyTorch (CPU) | 2-4 GB | ⚠️ On-demand |
| PyTorch (CUDA) | 6-8 GB | ⚠️ Optional |
| FFmpeg | 100 MB | ✅ Bundled |
| Whisper models | 75 MB - 1.5 GB | ⚠️ On-demand |
| Demucs models | 350 MB | ⚠️ On-demand |
| Your code | 10 MB | ✅ Always |

**Initial Download:** ~500 MB (framework + Python + FFmpeg + code)
**After Setup:** 3-10 GB (with models)

---

## Distribution with GitHub Actions

### CI/CD Workflow

#### `.github/workflows/build.yml`

```yaml
name: Build and Release

on:
  push:
    tags:
      - 'v*'
  pull_request:
    branches: [ main ]
  workflow_dispatch:

jobs:
  build-python:
    strategy:
      matrix:
        os: [ubuntu-22.04, windows-2022, macos-12]
    runs-on: ${{ matrix.os }}

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install Python dependencies
        run: |
          pip install -r requirements.txt
          pip install pyinstaller

      - name: Build Python backend
        run: |
          pyinstaller kai_converter.spec --clean

      - name: Upload Python artifact
        uses: actions/upload-artifact@v3
        with:
          name: python-backend-${{ matrix.os }}
          path: dist/kai_converter/

  build-electron:
    needs: build-python
    strategy:
      matrix:
        os: [ubuntu-22.04, windows-2022, macos-12]
    runs-on: ${{ matrix.os }}

    steps:
      - uses: actions/checkout@v3

      - name: Set up Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'

      - name: Download Python backend
        uses: actions/download-artifact@v3
        with:
          name: python-backend-${{ matrix.os }}
          path: dist/python/

      - name: Install dependencies
        run: npm ci

      - name: Download FFmpeg
        run: node scripts/download-ffmpeg.js

      - name: Build Electron app
        run: npm run build
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - name: Upload artifacts
        uses: actions/upload-artifact@v3
        with:
          name: kai-converter-${{ matrix.os }}
          path: dist/*.{exe,dmg,AppImage,deb,rpm,zip}

  release:
    needs: build-electron
    runs-on: ubuntu-latest
    if: startsWith(github.ref, 'refs/tags/')

    steps:
      - uses: actions/checkout@v3

      - name: Download all artifacts
        uses: actions/download-artifact@v3
        with:
          path: artifacts/

      - name: Create Release
        uses: softprops/action-gh-release@v1
        with:
          files: artifacts/**/*
          draft: false
          prerelease: false
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### Release Process

```bash
# 1. Tag a new version
git tag v1.0.0
git push origin v1.0.0

# 2. GitHub Actions automatically:
#    - Builds Python backend for all platforms
#    - Builds Electron app for all platforms
#    - Creates GitHub Release
#    - Uploads installers

# 3. Users download platform-specific installer:
#    - Windows: KAI-Converter-Setup-1.0.0.exe
#    - macOS: KAI-Converter-1.0.0.dmg
#    - Linux: KAI-Converter-1.0.0.AppImage
```

### Auto-Updates

Add `electron-updater` for automatic updates:

```javascript
// electron/main.js
const { autoUpdater } = require('electron-updater');

app.on('ready', () => {
  autoUpdater.checkForUpdatesAndNotify();
});

autoUpdater.on('update-downloaded', () => {
  dialog.showMessageBox({
    type: 'info',
    title: 'Update Ready',
    message: 'A new version has been downloaded. Restart to apply?',
    buttons: ['Restart', 'Later']
  }).then(result => {
    if (result.response === 0) {
      autoUpdater.quitAndInstall();
    }
  });
});
```

Configure in `electron-builder.yml`:

```yaml
publish:
  provider: github
  owner: your-username
  repo: kai-converter
  releaseType: release
```

---

## Backward Compatibility

### ✅ All Existing Scripts Continue to Work

**Key Principle:** The GUI is a **new interface** to existing functionality, not a replacement.

### CLI Scripts (Unchanged)

```bash
# All existing scripts work exactly as before:

./kai_pack.sh song.mp3                    # ✅ Works
./batch_pack.sh /music/folder/            # ✅ Works
./fix_lyrics.sh song.kai                  # ✅ Works
./make_movie.sh song.kai                  # ✅ Works
./convert_youtube.sh "URL"                # ✅ Works

# Python CLI still works:
python3 -m kai_pack song.mp3              # ✅ Works
python3 src/utils/fix_lyrics.py song.kai  # ✅ Works
```

### How Both Coexist

```
CLI Path (existing):
    kai_pack.sh → cli.py → processor.py → [processing]

GUI Path (new):
    Electron → api.py → processor.py → [processing]
               ↑
               └─ New clean interface, same core
```

### Code Organization

```python
# src/kai_pack/
├── cli.py          # CLI interface (unchanged)
│   └─ Uses: KaiProcessor, subprocess calls (legacy path)
│
├── api.py          # NEW: GUI interface
│   └─ Uses: KaiProcessor, direct function calls (clean path)
│
└── processor.py    # Core logic (used by both)
    └─ Modified: added optional progress_callback
       (ignored by CLI, used by GUI)
```

### Migration Path

**Phase 1: Add GUI alongside CLI (Recommended)**
- Refactor creates new `api.py`
- CLI code stays exactly as-is
- GUI uses new API
- Power users keep using CLI
- New users use GUI

**Phase 2: (Optional) Gradual CLI improvement**
- Slowly migrate CLI to use `api.py` internally
- Maintain same command-line interface
- Share more code between CLI and GUI
- Timeline: Future (not required)

### Testing Both Interfaces

```bash
# Test CLI (existing)
./kai_pack.sh test.mp3
# Expected: test.kai created via CLI code path

# Test GUI (new)
npm run dev
# Select test.mp3 in GUI
# Expected: test.kai created via GUI code path

# Both should produce identical output!
```

### Documentation

Keep separate docs:
- `README.md` - CLI usage (existing)
- `GUI_README.md` - GUI usage (new)
- `DEVELOPMENT.md` - Developer setup (both)

---

## Development Roadmap

### Realistic Timeline Estimates

**Human Developer:** 7+ weeks (part-time), 3-4 weeks (full-time)
**With Claude Code:** 2-4 days for MVP, 1-2 weeks for production-ready

### Phase 1: Foundation (4-8 hours with Claude)
- [ ] Refactor Python code (`api.py`, callbacks, direct imports)
- [ ] Set up Electron project structure
- [ ] Basic Python ↔ Electron bridge
- [ ] System check integration
- [ ] Test CLI still works after refactoring

**Claude can:** Generate entire files, refactor existing code, set up project structure
**You do:** Review, test, tweak, provide feedback

### Phase 2: Core GUI (6-10 hours with Claude)
- [ ] Setup wizard with system detection
- [ ] Main processing screen
- [ ] Progress bars with real-time updates
- [ ] Settings screen
- [ ] File selection dialogs

**Claude can:** Build full React components, wire up IPC, implement UI logic
**You do:** Design decisions, UX feedback, manual testing

### Phase 3: Advanced Features (4-6 hours with Claude)
- [ ] Batch processing UI
- [ ] Model download manager
- [ ] LLM provider configuration
- [ ] Error handling and logging
- [ ] Help and documentation

**Claude can:** Implement download logic, error handling, create docs
**You do:** Test edge cases, verify download URLs work

### Phase 4: Polish (2-4 hours with Claude)
- [ ] UI/UX improvements
- [ ] Icons and branding
- [ ] Keyboard shortcuts
- [ ] Drag-and-drop support
- [ ] User testing

**Claude can:** Add CSS polish, implement shortcuts, drag-drop handlers
**You do:** Provide brand assets, UI feedback, actual user testing

### Phase 5: Packaging (3-5 hours with Claude)
- [ ] PyInstaller Python builds
- [ ] electron-builder configuration
- [ ] Platform-specific testing (Win/Mac/Linux)
- [ ] GitHub Actions CI/CD
- [ ] Release process documentation

**Claude can:** Write build scripts, GitHub Actions workflow, config files
**You do:** Actually run builds on different platforms, debug platform-specific issues

### Phase 6: Distribution (Ongoing)
- [ ] GitHub Releases
- [ ] Auto-update mechanism
- [ ] User documentation
- [ ] Video tutorials
- [ ] Community feedback

**Claude can:** Write release notes, docs, help troubleshoot user issues
**You do:** Manage releases, create videos, community engagement

---

### Accelerated Development with Claude

**Day 1 (4-6 hours):**
- Morning: Python refactoring (api.py, callbacks, fix_lyrics)
- Afternoon: Electron setup, basic bridge, system check UI
- **Deliverable:** Can launch GUI, check system, see status

**Day 2 (4-6 hours):**
- Morning: Main processing screen, progress bars
- Afternoon: Settings screen, file dialogs
- **Deliverable:** Can process a single file with GUI

**Day 3 (3-4 hours):**
- Morning: Batch processing, model downloads
- Afternoon: Error handling, polish
- **Deliverable:** Feature-complete MVP

**Day 4 (2-3 hours):**
- Morning: Build scripts, testing
- Afternoon: GitHub Actions, packaging
- **Deliverable:** Installable builds for all platforms

**Days 5-7 (optional):**
- Polish, user testing, documentation
- Bug fixes from real-world testing
- **Deliverable:** Production release v1.0

---

### What Takes Time (Even with Claude)

**Fast (Claude does it):**
- ✅ Writing boilerplate code
- ✅ Setting up project structure
- ✅ Implementing well-defined features
- ✅ Creating documentation
- ✅ Writing tests

**Slower (You do it):**
- ⏱️ Deciding what you actually want
- ⏱️ Testing on real hardware
- ⏱️ Debugging platform-specific issues
- ⏱️ UI/UX iterations ("make it prettier")
- ⏱️ Dealing with weird edge cases

**The Real Timeline:**
- **Hacking together a demo:** 1 day
- **Working MVP you'd show friends:** 2-3 days
- **Production-ready for strangers:** 1-2 weeks
- **Polished, stable, documented:** 3-4 weeks

The difference is you're **designing and directing**, Claude is **building and implementing**.

---

## Resources

### Electron
- [Electron Documentation](https://www.electronjs.org/docs/latest/)
- [electron-builder](https://www.electron.build/)
- [Electron Security Best Practices](https://www.electronjs.org/docs/latest/tutorial/security)

### Python Packaging
- [PyInstaller Manual](https://pyinstaller.org/en/stable/)
- [PyOxidizer](https://pyoxidizer.readthedocs.io/)
- [Nuitka](https://nuitka.net/)

### Similar Projects
- [Whisper Desktop](https://github.com/Const-me/Whisper) - Electron + Whisper
- [Demucs GUI](https://github.com/CarlGao4/Demucs-Gui) - PyQt GUI for Demucs
- [Ultimate Vocal Remover](https://github.com/Anjok07/ultimatevocalremovergui) - Audio separation GUI

### GitHub Actions
- [Building Electron Apps](https://www.electron.build/multi-platform-build)
- [GitHub Actions for Python](https://docs.github.com/en/actions/automating-builds-and-tests/building-and-testing-python)

---

## FAQ

**Q: Will the CLI scripts still work after adding the GUI?**
A: Yes! All existing scripts remain unchanged. The GUI is a parallel interface.

**Q: Do users need to install Python?**
A: No, Python is bundled with the Electron app (via PyInstaller).

**Q: What about ffmpeg?**
A: Bundled with the app, but will use system ffmpeg if already installed.

**Q: How big is the download?**
A: ~500 MB initial installer, 3-10 GB after downloading models.

**Q: Can users skip model downloads?**
A: No, at minimum they need PyTorch + one Whisper model (~2.5 GB).

**Q: What about updates?**
A: Auto-update via electron-updater, or manual download from GitHub Releases.

**Q: Does this work offline?**
A: Yes, after initial setup. LLM features require internet (or local LM Studio).

**Q: Can power users still use the CLI?**
A: Absolutely! CLI is unchanged and fully supported.

---

## Next Steps

1. **Review this plan** - Adjust timeline, scope, priorities
2. **Start refactoring** - Create `api.py`, add callbacks (1-2 days)
3. **Prototype Electron** - Basic bridge, system check (2-3 days)
4. **Build MVP** - Single-file processing GUI (1 week)
5. **Test & iterate** - Get feedback, fix issues (ongoing)
6. **Package & release** - Build installers, publish v1.0

---

**This document is a living plan - update as development progresses!**