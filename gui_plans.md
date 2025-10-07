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
├── electron/                     # NEW: Electron app (ES modules)
│   ├── main.js                  # Main process (ESM)
│   ├── preload.cjs              # Security bridge (CommonJS - required)
│   ├── python-bridge.js         # Python subprocess manager (ESM)
│   ├── system-checker.js        # Uses system_check.py (ESM)
│   ├── download-manager.js      # Model/dependency downloader (ESM)
│   ├── model-urls.js            # Download URLs and checksums (ESM)
│   └── menu.js                  # App menu (ESM)
│
├── renderer/                     # NEW: Frontend (React + Vite)
│   ├── index.html               # Vite entry point
│   ├── src/
│   │   ├── main.jsx             # React entry point
│   │   ├── App.jsx              # Root component with routing
│   │   ├── index.css            # Tailwind imports
│   │   ├── components/
│   │   │   ├── SetupScreen.jsx      # System check & downloads
│   │   │   ├── MainScreen.jsx       # Audio processing UI
│   │   │   ├── SettingsScreen.jsx   # Config & model management
│   │   │   ├── BatchScreen.jsx      # Batch processing
│   │   │   ├── ProgressBar.jsx      # Real-time progress
│   │   │   └── common/
│   │   │       ├── Button.jsx       # Reusable button
│   │   │       ├── Card.jsx         # Reusable card
│   │   │       └── FileInput.jsx    # File picker component
│   │   ├── hooks/
│   │   │   ├── useElectron.js       # Electron API hook
│   │   │   ├── useProgress.js       # Progress tracking hook
│   │   │   └── useSystemCheck.js    # System status hook
│   │   └── utils/
│   │       ├── formatting.js        # Time/size formatting
│   │       └── validation.js        # Input validation
│   └── dist/                    # Build output (gitignored)
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
- **React** 18+ with hooks and functional components
- **Vite** 5+ for fast dev builds and HMR
- **TailwindCSS** for styling
- **ES Modules** (not CommonJS, not TypeScript)
- **No globals** - all communication via contextBridge API

**Backend Bridge:**
- **Python subprocess** via `child_process.spawn()`
- **JSON-RPC** or **REST API** (Python HTTP server)
- **IPC** for Electron main ↔ renderer communication
- **Modular architecture** - proper imports/exports throughout

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
import { app, BrowserWindow, ipcMain } from 'electron';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import PythonBridge from './python-bridge.js';
import SystemChecker from './system-checker.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

let mainWindow;
let pythonBridge;
let systemChecker;

const isDev = !app.isPackaged;

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      preload: join(__dirname, 'preload.cjs'), // Preload must be CommonJS
      nodeIntegration: false,
      contextIsolation: true,
    }
  });

  // In development, load from Vite dev server
  // In production, load from built files
  if (isDev) {
    await mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools();
  } else {
    await mainWindow.loadFile(join(__dirname, '..', 'renderer', 'dist', 'index.html'));
  }

  // Initialize Python bridge
  const pythonPath = app.isPackaged
    ? join(process.resourcesPath, 'python', 'kai_converter')
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

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});
```

#### `electron/python-bridge.js`

```javascript
import { spawn } from 'child_process';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

export default class PythonBridge {
  constructor(pythonPath) {
    this.pythonPath = pythonPath;
    this.apiScript = join(__dirname, '..', 'src', 'kai_pack', 'api.py');
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

      const childProcess = spawn(this.pythonPath, args, {
        env: {
          ...process.env,
          FFMPEG_PATH: this.getFFmpegPath()
        }
      });

      let stdout = '';
      let stderr = '';

      childProcess.stdout.on('data', (data) => {
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

      childProcess.stderr.on('data', (data) => {
        stderr += data.toString();
      });

      childProcess.on('close', (code) => {
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
    return join(process.resourcesPath, 'bin', ffmpegName);
  }
}
```

#### `electron/preload.cjs` (Security Bridge - Must be CommonJS)

**Note:** Electron's preload scripts must use CommonJS syntax, not ES modules.

```javascript
const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods that renderer can access
contextBridge.exposeInMainWorld('electronAPI', {
  // System check
  checkSystem: () => ipcRenderer.invoke('check-system'),

  // Audio processing
  processAudio: (options) => ipcRenderer.invoke('process-audio', options),

  // Progress events
  onProgress: (callback) => {
    const listener = (event, progress) => callback(progress);
    ipcRenderer.on('progress', listener);
    // Return cleanup function
    return () => ipcRenderer.removeListener('progress', listener);
  },

  // Download components
  downloadComponent: (componentId) => {
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

#### `renderer/src/main.jsx` (Entry Point)

```jsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

#### `renderer/index.html`

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>KAI Converter</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

#### `renderer/src/App.jsx` (Root Component)

```jsx
import { useState } from 'react';
import MainScreen from './components/MainScreen';
import SetupScreen from './components/SetupScreen';
import SettingsScreen from './components/SettingsScreen';

export default function App() {
  const [currentScreen, setCurrentScreen] = useState('main');

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100">
      <nav className="bg-gray-800 border-b border-gray-700 px-4 py-3">
        <div className="flex gap-4">
          <button
            onClick={() => setCurrentScreen('main')}
            className={currentScreen === 'main' ? 'text-primary' : 'text-gray-400'}
          >
            Convert
          </button>
          <button
            onClick={() => setCurrentScreen('settings')}
            className={currentScreen === 'settings' ? 'text-primary' : 'text-gray-400'}
          >
            Settings
          </button>
        </div>
      </nav>

      <main className="container mx-auto p-6">
        {currentScreen === 'main' && <MainScreen />}
        {currentScreen === 'settings' && <SettingsScreen />}
      </main>
    </div>
  );
}
```

#### `renderer/src/components/MainScreen.jsx`

```jsx
import { useState, useEffect } from 'react';
import { useProgress } from '../hooks/useProgress';
import ProgressBar from './ProgressBar';

export default function MainScreen() {
  const [inputFile, setInputFile] = useState(null);
  const [processing, setProcessing] = useState(false);
  const { progress, startListening, stopListening } = useProgress();

  useEffect(() => {
    startListening();
    return () => stopListening();
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
    <div className="max-w-2xl mx-auto space-y-6">
      <h1 className="text-3xl font-bold">KAI Converter</h1>

      <div className="bg-gray-800 rounded-lg p-6 space-y-4">
        <button
          onClick={handleSelectFile}
          className="btn-primary w-full"
        >
          Select Audio File
        </button>

        {inputFile && (
          <p className="text-sm text-gray-400">Selected: {inputFile}</p>
        )}

        <button
          onClick={handleProcess}
          disabled={!inputFile || processing}
          className="btn-primary w-full disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {processing ? 'Processing...' : 'Create KAI File'}
        </button>

        {processing && <ProgressBar progress={progress} />}
      </div>
    </div>
  );
}
```

#### `renderer/src/hooks/useProgress.js`

```javascript
import { useState } from 'react';

export function useProgress() {
  const [progress, setProgress] = useState({
    stage: '',
    percent: 0,
    message: ''
  });

  const startListening = () => {
    const cleanup = window.electronAPI.onProgress((progressData) => {
      setProgress(progressData);
    });
    return cleanup;
  };

  const stopListening = startListening();

  return { progress, startListening, stopListening };
}
```

---

## System Detection & Setup

See `src/utils/system_check.py` (already implemented) for comprehensive system detection.

### Setup Wizard Flow

```
1. App Launch (First Time)
   ↓
2. Run System Check (system_check.py --json)
   ↓
3. Detect What's Missing:
   ├─ FFmpeg: ✅ Bundled (skip)
   ├─ Python: ✅ Bundled (skip)
   ├─ PyTorch: ❌ Missing → Download CPU version
   ├─ Demucs Models: ❌ Missing → Download htdemucs_ft
   └─ Whisper Models: ❌ Missing → Show selection dialog
   ↓
4. GPU Detection:
   ├─ NVIDIA GPU detected? → Offer CUDA PyTorch (optional)
   ├─ Apple Silicon? → Use MPS (included with CPU version)
   └─ No GPU? → Use CPU version
   ↓
5. Model Selection Dialog:
   ┌─────────────────────────────────────────────┐
   │ Select Whisper Model (Required):           │
   │ ○ tiny (75 MB) - Fastest, lower accuracy   │
   │ ○ base (150 MB) - Fast, decent accuracy    │
   │ ● small (500 MB) - Recommended ⭐          │
   │ ○ medium (1.5 GB) - Slower, high accuracy  │
   │ ○ large-v3 (3 GB) - Slowest, best accuracy │
   │                                             │
   │ [ ] Also download CUDA PyTorch (+2 GB)     │
   │     Enables GPU acceleration               │
   │                                             │
   │ Total download: 850 MB                     │
   │ Available space: 45 GB                     │
   │                                             │
   │    [Cancel]  [Download & Continue]         │
   └─────────────────────────────────────────────┘
   ↓
6. Download Components:
   ┌─────────────────────────────────────────────┐
   │ Downloading required components...          │
   │                                             │
   │ PyTorch CPU ████████████░░░ 75% (150 MB)  │
   │ Demucs Model ███████████████ 100% (350 MB)│
   │ Whisper small ████░░░░░░░░░ 30% (500 MB)  │
   │                                             │
   │ Overall: 56% (500 MB / 1 GB)               │
   │ Speed: 5.2 MB/s - 2 min remaining          │
   └─────────────────────────────────────────────┘
   ↓
7. Verify & Install:
   ├─ Verify checksums (ensure integrity)
   ├─ Extract/install models to cache
   └─ Re-run system check
   ↓
8. ✅ Setup Complete → Main App

On Subsequent Launches:
   → System check passes → Main App directly
   → If models deleted → Re-show setup wizard
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
npm install --save-dev electron electron-builder vite @vitejs/plugin-react

# Install frontend dependencies
npm install react react-dom

# Install TailwindCSS
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p

# Development mode
npm run dev  # Starts Vite dev server with HMR
npm run dev:electron  # Starts Electron pointing to Vite dev server
```

### Vite Configuration

#### `vite.config.js`

```javascript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  base: './',
  build: {
    outDir: 'renderer/dist',
    emptyOutDir: true,
  },
  server: {
    port: 5173,
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './renderer/src'),
      '@components': path.resolve(__dirname, './renderer/src/components'),
      '@hooks': path.resolve(__dirname, './renderer/src/hooks'),
      '@utils': path.resolve(__dirname, './renderer/src/utils'),
    },
  },
});
```

### TailwindCSS Configuration

#### `tailwind.config.js`

```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./renderer/index.html",
    "./renderer/src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: '#6366f1',
        secondary: '#8b5cf6',
      },
    },
  },
  plugins: [],
}
```

#### `renderer/src/index.css`

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  body {
    @apply bg-gray-900 text-gray-100;
  }
}

@layer components {
  .btn-primary {
    @apply bg-primary hover:bg-primary/90 text-white px-4 py-2 rounded-lg transition-colors;
  }

  .btn-secondary {
    @apply bg-gray-700 hover:bg-gray-600 text-white px-4 py-2 rounded-lg transition-colors;
  }
}
```

### `package.json`

```json
{
  "name": "kai-converter",
  "version": "1.0.0",
  "description": "AI-powered karaoke file creator",
  "type": "module",
  "main": "electron/main.js",
  "scripts": {
    "dev": "vite",
    "dev:electron": "wait-on http://localhost:5173 && electron .",
    "dev:all": "concurrently \"npm run dev\" \"npm run dev:electron\"",
    "build": "vite build && electron-builder",
    "build:python": "node scripts/build-python.js",
    "build:all": "npm run build:python && npm run build",
    "package:win": "electron-builder --win",
    "package:mac": "electron-builder --mac",
    "package:linux": "electron-builder --linux",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.2.0",
    "autoprefixer": "^10.4.16",
    "concurrently": "^8.2.2",
    "electron": "^28.0.0",
    "electron-builder": "^24.0.0",
    "postcss": "^8.4.32",
    "tailwindcss": "^3.3.6",
    "vite": "^5.0.0",
    "wait-on": "^7.2.0"
  },
  "build": {
    "appId": "com.kaiconverter.app",
    "productName": "KAI Converter",
    "files": [
      "electron/**/*",
      "renderer/dist/**/*",
      "resources/**/*",
      "!resources/models/**/*"
    ],
    "extraResources": [
      {
        "from": "dist/python",
        "to": "python",
        "filter": ["**/*", "!**/*.pyc", "!**/__pycache__"]
      },
      {
        "from": "resources/bin",
        "to": "bin"
      }
    ],
    "win": {
      "target": [
        {
          "target": "nsis",
          "arch": ["x64"]
        },
        {
          "target": "portable",
          "arch": ["x64"]
        }
      ],
      "icon": "resources/icon.ico",
      "artifactName": "KAI-Converter-${version}-Windows-${arch}.${ext}"
    },
    "mac": {
      "target": [
        {
          "target": "dmg",
          "arch": ["x64", "arm64"]
        },
        {
          "target": "zip",
          "arch": ["x64", "arm64"]
        }
      ],
      "icon": "resources/icon.icns",
      "category": "public.app-category.music",
      "hardenedRuntime": true,
      "gatekeeperAssess": false,
      "entitlements": "build/entitlements.mac.plist",
      "entitlementsInherit": "build/entitlements.mac.plist",
      "artifactName": "KAI-Converter-${version}-macOS-${arch}.${ext}"
    },
    "linux": {
      "target": [
        {
          "target": "AppImage",
          "arch": ["x64"]
        },
        {
          "target": "deb",
          "arch": ["x64"]
        },
        {
          "target": "rpm",
          "arch": ["x64"]
        }
      ],
      "icon": "resources/icon.png",
      "category": "Audio",
      "artifactName": "KAI-Converter-${version}-Linux-${arch}.${ext}"
    },
    "compression": "maximum",
    "publish": {
      "provider": "github",
      "owner": "your-username",
      "repo": "kai-converter"
    }
  }
}
```

### Building Python Backend

#### `scripts/build-python.js`

```javascript
import { execSync } from 'child_process';
import fs from 'fs-extra';
import path from 'path';
import { fileURLToPath } from 'url';
import { dirname } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

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
  await fs.ensureDir(distDir);
  await fs.copy('dist/kai_converter', distDir);

  console.log('✅ Python backend built successfully');
}

buildPython().catch(console.error);
```

### Download FFmpeg

#### `scripts/download-ffmpeg.js`

```javascript
import https from 'https';
import fs from 'fs-extra';
import path from 'path';
import { execSync } from 'child_process';
import { fileURLToPath } from 'url';
import { dirname } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

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
  await fs.ensureDir(binDir);

  // Download and extract logic here
  // ... (implementation)

  console.log('✅ FFmpeg downloaded successfully');
}

downloadFFmpeg().catch(console.error);
```

### Dynamic Model Downloader

#### `electron/model-urls.js`

```javascript
// Model download URLs and checksums
export const MODEL_URLS = {
  pytorch: {
    cpu: {
      url: 'https://download.pytorch.org/whl/cpu/torch-2.1.0%2Bcpu-cp311-cp311-{platform}.whl',
      size: 150 * 1024 * 1024, // 150 MB
      checksum: {
        win32: 'sha256-hash-here',
        darwin: 'sha256-hash-here',
        linux: 'sha256-hash-here'
      }
    },
    cuda: {
      url: 'https://download.pytorch.org/whl/cu121/torch-2.1.0%2Bcu121-cp311-cp311-{platform}.whl',
      size: 2.5 * 1024 * 1024 * 1024, // 2.5 GB
      checksum: {
        win32: 'sha256-hash-here',
        linux: 'sha256-hash-here'
      }
    }
  },
  whisper: {
    tiny: {
      url: 'https://openaipublic.azureedge.net/main/whisper/models/65147644a518d12f04e32d6f3b26facc3f8dd46e5390956a9424a650c0ce22b9/tiny.pt',
      size: 75 * 1024 * 1024,
      checksum: '65147644a518d12f04e32d6f3b26facc3f8dd46e5390956a9424a650c0ce22b9'
    },
    base: {
      url: 'https://openaipublic.azureedge.net/main/whisper/models/ed3a0b6b1c0edf879ad9b11b1af5a0e6ab5db9205f891f668f8b0e6c6326e34e/base.pt',
      size: 142 * 1024 * 1024,
      checksum: 'ed3a0b6b1c0edf879ad9b11b1af5a0e6ab5db9205f891f668f8b0e6c6326e34e'
    },
    small: {
      url: 'https://openaipublic.azureedge.net/main/whisper/models/9ecf779972d90ba49c06d968637d720dd632c55bbf19d441fb42bf17a411e794/small.pt',
      size: 488 * 1024 * 1024,
      checksum: '9ecf779972d90ba49c06d968637d720dd632c55bbf19d441fb42bf17a411e794'
    },
    medium: {
      url: 'https://openaipublic.azureedge.net/main/whisper/models/345ae4da62f9b3d59415adc60127b97c714f32e89e936602e85993674d08dcb1/medium.pt',
      size: 1.5 * 1024 * 1024 * 1024,
      checksum: '345ae4da62f9b3d59415adc60127b97c714f32e89e936602e85993674d08dcb1'
    },
    'large-v3': {
      url: 'https://openaipublic.azureedge.net/main/whisper/models/e5b1a55b89c1367dacf97e3e19bfd829a01529dbfdeefa8caeb59b3f1b81dadb/large-v3.pt',
      size: 2.9 * 1024 * 1024 * 1024,
      checksum: 'e5b1a55b89c1367dacf97e3e19bfd829a01529dbfdeefa8caeb59b3f1b81dadb'
    }
  },
  demucs: {
    htdemucs_ft: {
      url: 'https://dl.fbaipublicfiles.com/demucs/hybrid_transformer/04573f0d-f3cf25b2.th',
      size: 350 * 1024 * 1024,
      checksum: '04573f0d-f3cf25b2'
    }
  }
};

// Get model cache directory
export function getModelCacheDir() {
  const { app } = require('electron');
  const path = require('path');
  const os = require('os');

  // Use platform-specific cache directories
  const cacheDir = process.platform === 'darwin'
    ? path.join(os.homedir(), 'Library', 'Caches', 'KAI-Converter')
    : process.platform === 'win32'
    ? path.join(os.homedir(), 'AppData', 'Local', 'KAI-Converter', 'Cache')
    : path.join(os.homedir(), '.cache', 'kai-converter');

  return cacheDir;
}
```

#### `electron/download-manager.js`

```javascript
import https from 'https';
import fs from 'fs-extra';
import { join } from 'path';
import { createHash } from 'crypto';
import { MODEL_URLS, getModelCacheDir } from './model-urls.js';

export default class DownloadManager {
  constructor() {
    this.activeDownloads = new Map();
    this.cacheDir = getModelCacheDir();
  }

  async downloadModel(modelType, modelName, progressCallback) {
    const modelInfo = MODEL_URLS[modelType]?.[modelName];
    if (!modelInfo) {
      throw new Error(`Unknown model: ${modelType}/${modelName}`);
    }

    // Ensure cache directory exists
    await fs.ensureDir(this.cacheDir);

    const outputPath = join(this.cacheDir, `${modelType}-${modelName}`);

    // Check if already downloaded and valid
    if (await this.verifyFile(outputPath, modelInfo.checksum)) {
      progressCallback({ percent: 100, status: 'cached' });
      return outputPath;
    }

    return this.downloadFile(modelInfo.url, outputPath, modelInfo.checksum, progressCallback);
  }

  async downloadFile(url, outputPath, expectedChecksum, progressCallback) {
    return new Promise((resolve, reject) => {
      const tempPath = `${outputPath}.part`;
      const file = fs.createWriteStream(tempPath);

      https.get(url, (response) => {
        const totalSize = parseInt(response.headers['content-length'], 10);
        let downloadedSize = 0;
        let lastProgressUpdate = Date.now();

        response.on('data', (chunk) => {
          downloadedSize += chunk.length;
          file.write(chunk);

          // Throttle progress updates to every 100ms
          const now = Date.now();
          if (now - lastProgressUpdate > 100) {
            const percent = (downloadedSize / totalSize) * 100;
            progressCallback({
              percent,
              downloaded: downloadedSize,
              total: totalSize,
              status: 'downloading'
            });
            lastProgressUpdate = now;
          }
        });

        response.on('end', async () => {
          file.end();

          // Verify checksum
          if (await this.verifyFile(tempPath, expectedChecksum)) {
            await fs.move(tempPath, outputPath, { overwrite: true });
            progressCallback({ percent: 100, status: 'complete' });
            resolve(outputPath);
          } else {
            await fs.remove(tempPath);
            reject(new Error('Checksum verification failed'));
          }
        });
      }).on('error', (err) => {
        file.end();
        fs.remove(tempPath).catch(() => {});
        reject(err);
      });
    });
  }

  async verifyFile(filePath, expectedChecksum) {
    try {
      const hash = createHash('sha256');
      const stream = fs.createReadStream(filePath);

      return new Promise((resolve) => {
        stream.on('data', (data) => hash.update(data));
        stream.on('end', () => {
          const fileHash = hash.digest('hex');
          resolve(fileHash === expectedChecksum);
        });
        stream.on('error', () => resolve(false));
      });
    } catch (error) {
      return false;
    }
  }

  async downloadMultiple(downloads, overallProgressCallback) {
    const results = [];
    let completed = 0;
    const total = downloads.length;

    for (const download of downloads) {
      try {
        const result = await this.downloadModel(
          download.type,
          download.name,
          (progress) => {
            overallProgressCallback({
              current: download.name,
              currentProgress: progress.percent,
              overall: ((completed + (progress.percent / 100)) / total) * 100
            });
          }
        );
        results.push({ success: true, path: result, ...download });
        completed++;
      } catch (error) {
        results.push({ success: false, error: error.message, ...download });
      }
    }

    return results;
  }

  getCacheSize() {
    // Calculate total size of cached models
    return fs.readdirSync(this.cacheDir)
      .reduce((total, file) => {
        const stats = fs.statSync(join(this.cacheDir, file));
        return total + stats.size;
      }, 0);
  }

  async clearCache() {
    await fs.emptyDir(this.cacheDir);
  }
}
```

### Build Commands

```bash
# Development
npm run dev              # Vite dev server only
npm run dev:electron     # Electron only (waits for Vite)
npm run dev:all          # Both Vite + Electron concurrently

# Build Python backend (one-time, cross-platform)
npm run build:python     # PyInstaller → dist/python/

# Build Electron app
npm run build            # Vite build + electron-builder for current platform

# Platform-specific builds
npm run package:win      # Windows x64 NSIS + portable
npm run package:mac      # macOS Intel + ARM64 DMG + zip
npm run package:linux    # Linux x64 AppImage + deb + rpm

# Build all platforms (requires appropriate OS or CI)
npm run package:all      # All platforms (Windows/Mac/Linux)

# Complete build workflow
npm run build:all        # 1. Build Python backend
                         # 2. Build Vite frontend
                         # 3. Package for all platforms
```

### Multi-Platform Build Matrix

**On macOS (recommended for all platforms):**
```bash
# Install dependencies for cross-platform builds
brew install wine mono

# Build for all platforms
npm run package:all
```

**Output artifacts:**
```
dist/
├── KAI-Converter-1.0.0-Windows-x64.exe          # Windows installer
├── KAI-Converter-1.0.0-Windows-x64-portable.exe # Windows portable
├── KAI-Converter-1.0.0-macOS-x64.dmg            # macOS Intel
├── KAI-Converter-1.0.0-macOS-arm64.dmg          # macOS Apple Silicon
├── KAI-Converter-1.0.0-macOS-x64.zip            # macOS Intel (zip)
├── KAI-Converter-1.0.0-macOS-arm64.zip          # macOS ARM (zip)
├── KAI-Converter-1.0.0-Linux-x64.AppImage       # Linux AppImage
├── KAI-Converter-1.0.0-Linux-x64.deb            # Debian/Ubuntu
└── KAI-Converter-1.0.0-Linux-x64.rpm            # RedHat/Fedora
```

### Package Sizes & Bundling Strategy

**✅ BUNDLED (Included in installer):**

| Component | Size | Windows | macOS | Linux | Notes |
|-----------|------|---------|-------|-------|-------|
| Electron framework | 200 MB | ✅ | ✅ | ✅ | Chromium + Node |
| Python runtime | 50 MB | ✅ | ✅ | ✅ | Bundled via PyInstaller |
| Core Python deps | 50 MB | ✅ | ✅ | ✅ | scipy, mutagen, soundfile, etc. |
| FFmpeg binaries | 100 MB | ✅ | ✅ | ✅ | Static builds included |
| Your code | 10 MB | ✅ | ✅ | ✅ | KAI Converter scripts |

**🔽 DOWNLOADED ON FIRST RUN (Dynamic downloads):**

| Component | Size | Required? | When? |
|-----------|------|-----------|-------|
| PyTorch (CPU) | 150-200 MB | ✅ Yes | First run or setup wizard |
| PyTorch (CUDA) | 2-4 GB | ⚠️ Optional | User chooses GPU acceleration |
| Whisper tiny | 75 MB | ⚠️ Optional | User selects model |
| Whisper base | 150 MB | ⚠️ Optional | User selects model |
| Whisper small | 500 MB | ✅ Recommended | Default model |
| Whisper medium | 1.5 GB | ⚠️ Optional | User selects model |
| Whisper large-v3 | 3 GB | ⚠️ Optional | User selects model |
| Demucs htdemucs_ft | 350 MB | ✅ Yes | First run or setup wizard |

**Package Sizes by Platform:**

| Platform | Installer Size | After Setup (Minimal) | After Setup (Full) |
|----------|----------------|----------------------|-------------------|
| Windows | ~320 MB | ~1.1 GB | ~5.8 GB |
| macOS Intel | ~360 MB | ~1.2 GB | ~6.2 GB |
| macOS ARM64 | ~320 MB | ~1.0 GB | ~5.3 GB |
| Linux | ~290 MB | ~1.0 GB | ~5.8 GB |

**Download Strategy:**
- **Initial Download:** 290-360 MB installer (no ML models, no librosa)
- **Minimal Setup:** +750 MB (PyTorch CPU + Whisper small + Demucs) = ~1.1 GB total
- **Full Setup:** +5 GB (all models + CUDA) = ~5.8 GB total
- **User Choice:** Users select which models to download based on needs

**Note:** madmom and essentia are optional and not bundled. They enable enhanced onset/beat detection and key detection features respectively, but are not required for core functionality.

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
    name: Build Python Backend
    runs-on: ubuntu-22.04

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
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
        uses: actions/upload-artifact@v4
        with:
          name: python-backend
          path: dist/kai_converter/
          retention-days: 1

  build-electron:
    name: Build Electron - ${{ matrix.os }}
    needs: build-python
    strategy:
      fail-fast: false
      matrix:
        include:
          - os: windows-2022
            platform: win
          - os: macos-12
            platform: mac
          - os: ubuntu-22.04
            platform: linux
    runs-on: ${{ matrix.os }}

    steps:
      - uses: actions/checkout@v4

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'

      - name: Download Python backend
        uses: actions/download-artifact@v4
        with:
          name: python-backend
          path: dist/python/

      - name: Install dependencies
        run: npm ci

      - name: Download FFmpeg
        run: node scripts/download-ffmpeg.js

      - name: Build Vite frontend
        run: npm run build

      - name: Package Electron app
        run: npm run package:${{ matrix.platform }}
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - name: Upload build artifacts
        uses: actions/upload-artifact@v4
        with:
          name: kai-converter-${{ matrix.platform }}
          path: |
            dist/*.exe
            dist/*.dmg
            dist/*.zip
            dist/*.AppImage
            dist/*.deb
            dist/*.rpm
          retention-days: 7

  release:
    name: Create GitHub Release
    needs: build-electron
    runs-on: ubuntu-latest
    if: startsWith(github.ref, 'refs/tags/')

    steps:
      - uses: actions/checkout@v4

      - name: Download all artifacts
        uses: actions/download-artifact@v4
        with:
          path: artifacts/

      - name: Display structure
        run: ls -R artifacts/

      - name: Create Release
        uses: softprops/action-gh-release@v2
        with:
          files: |
            artifacts/kai-converter-win/*.exe
            artifacts/kai-converter-mac/*.dmg
            artifacts/kai-converter-mac/*.zip
            artifacts/kai-converter-linux/*.AppImage
            artifacts/kai-converter-linux/*.deb
            artifacts/kai-converter-linux/*.rpm
          draft: false
          prerelease: false
          generate_release_notes: true
          body: |
            ## KAI Converter Release

            ### Installation

            **Windows:**
            - Download `KAI-Converter-*-Windows-x64.exe` for installer
            - Or download `KAI-Converter-*-Windows-x64-portable.exe` for portable version

            **macOS:**
            - Intel Macs: Download `KAI-Converter-*-macOS-x64.dmg`
            - Apple Silicon: Download `KAI-Converter-*-macOS-arm64.dmg`

            **Linux:**
            - AppImage (universal): `KAI-Converter-*-Linux-x64.AppImage`
            - Debian/Ubuntu: `KAI-Converter-*-Linux-x64.deb`
            - RedHat/Fedora: `KAI-Converter-*-Linux-x64.rpm`

            ### First Run

            On first launch, the app will download required AI models (~1.2 GB).
            You can choose which Whisper model to use based on your needs.

            ### Package Sizes

            - Installer: ~350-420 MB (no models)
            - After setup: ~1.2 GB (minimal) to ~6 GB (all models)
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

## Development Plan

### Overview

This plan breaks down the GUI development into clear, actionable tasks organized by phase. Each task includes acceptance criteria so you know when it's done.

**Estimated Timeline:**
- **MVP (working GUI):** 2-4 days with Claude Code
- **Production-ready:** 1-2 weeks with testing
- **Polished release:** 3-4 weeks with documentation

---

## Phase 0: Repository Cleanup

**Goal:** Reorganize repository structure for GUI/CLI separation

### Task 0.1: Reorganize CLI Scripts
**What to do:**
- [ ] Create `cli/` directory
- [ ] Move CLI scripts to `cli/`:
  - `kai_pack.sh` → `cli/kai_pack.sh`
  - `fix_lyrics.sh` → `cli/fix_lyrics.sh`
  - `batch_pack.sh` → `cli/batch_pack.sh`
  - `convert_youtube.sh` → `cli/convert_youtube.sh`
  - `make_movie.sh` → `cli/make_movie.sh`
- [ ] Keep `install.sh` in root (developer setup script)
- [ ] Update any internal path references in moved scripts
- [ ] Update `.gitignore` if needed (add `cli/*.kai`, etc.)
- [ ] Update README.md to reflect new paths:
  - GUI: Download from Releases (primary)
  - CLI: `./install.sh` then `./cli/kai_pack.sh` (secondary)
- [ ] Test all CLI scripts still work from new location

**Acceptance criteria:**
- All shell scripts work from `cli/` directory
- `install.sh` remains in root
- README updated with new paths
- No broken references in code
- Repository root is cleaner

**Files to move:**
- `*.sh` (except install.sh) → `cli/*.sh`

**Files to modify:**
- `README.md`
- Potentially scripts if they reference each other
- `.gitignore`

---

## Phase 1: Python Backend Refactoring

**Goal:** Make Python code GUI-friendly without breaking CLI

### Task 1.1: Create API Facade Layer
**File:** `src/kai_pack/api.py`

**What to do:**
- [ ] Create `KaiAPI` class with clean interface
- [ ] Add `process_audio()` method that returns structured dicts (not exit codes)
- [ ] Add progress callback support: `progress_callback(stage, percent, message)`
- [ ] Return structured results: `{"success": bool, "output_file": str, "error": str}`
- [ ] Use exceptions instead of `sys.exit()`

**Acceptance criteria:**
- Can import and call `KaiAPI.process_audio()` from Python script
- Progress callback fires with updates during processing
- Returns dict with success/failure info
- Doesn't break when called without callback

**Files to create/modify:**
- Create: `src/kai_pack/api.py`

---

### Task 1.2: Refactor fix_lyrics for Direct Import
**File:** `src/utils/fix_lyrics.py`

**What to do:**
- [ ] Extract `fix_lyrics_direct()` function from `main()`
- [ ] Accept parameters directly (no argparse in function)
- [ ] Add progress callback support
- [ ] Return structured dict with results
- [ ] Keep existing `main()` CLI interface that calls `fix_lyrics_direct()`

**Acceptance criteria:**
- Can call `fix_lyrics_direct(kai_file, llm_provider)` from Python
- Returns dict with correction count, confidence, errors
- CLI script (`./fix_lyrics.sh`) still works unchanged
- Progress callback fires during processing

**Files to modify:**
- `src/utils/fix_lyrics.py`

---

### Task 1.3: Add Progress Callbacks to KaiProcessor
**File:** `src/kai_pack/processor.py`

**What to do:**
- [ ] Add `progress_callback` parameter to `__init__()`
- [ ] Add `_emit_progress(step, total, message)` method
- [ ] Call `_emit_progress()` at major processing steps:
  - Loading audio
  - Extracting metadata
  - Separating stems (with Demucs progress)
  - Transcribing lyrics (with Whisper progress)
  - Analyzing audio features
  - Packaging KAI file
- [ ] Still log to logger (for CLI users)
- [ ] Gracefully handle missing callback (no-op)

**Acceptance criteria:**
- GUI can subscribe to progress updates
- CLI users see logs as before (no change)
- Progress goes from 0% to 100%
- Each major step updates progress

**Files to modify:**
- `src/kai_pack/processor.py`

---

### Task 1.4: Remove Temp File Communication
**File:** `src/kai_pack/cli.py`

**What to do:**
- [ ] Replace temp file LRCLIB lyrics passing with direct parameters
- [ ] Pass lyrics data directly to `fix_lyrics_direct()`
- [ ] Clean up temp file creation code

**Acceptance criteria:**
- No temp files used for inter-process communication
- Lyrics data passed directly as strings/dicts
- Tests pass

**Files to modify:**
- `src/kai_pack/cli.py`

---

### Task 1.5: Verify CLI Still Works
**What to do:**
- [ ] Test `./kai_pack.sh song.mp3` works
- [ ] Test `./fix_lyrics.sh song.kai` works
- [ ] Test `./batch_pack.sh /folder/` works
- [ ] Test `python -m kai_pack song.mp3` works

**Acceptance criteria:**
- All existing CLI scripts produce same output as before
- No regressions in functionality
- Error messages still make sense

---

## Phase 2: Electron Project Setup

**Goal:** Get basic Electron + Vite + React running

### Task 2.1: Initialize Electron Project
**What to do:**
- [ ] Run `npm init -y` if no package.json
- [ ] Install dependencies:
  ```bash
  npm install --save-dev electron electron-builder vite @vitejs/plugin-react
  npm install --save-dev concurrently wait-on
  npm install --save-dev tailwindcss postcss autoprefixer
  npm install react react-dom
  ```
- [ ] Add npm scripts to `package.json`:
  - `dev`: Vite dev server
  - `dev:electron`: Electron (waits for Vite)
  - `dev:all`: Both concurrently
  - `build`: Vite build + electron-builder
  - `package:win/mac/linux`: Platform-specific builds
- [ ] Add `"type": "module"` to package.json

**Acceptance criteria:**
- `npm install` completes successfully
- All dependencies installed

**Files to create/modify:**
- Modify: `package.json`

---

### Task 2.2: Configure Vite + TailwindCSS
**What to do:**
- [ ] Create `vite.config.js` with React plugin
- [ ] Configure build output to `renderer/dist`
- [ ] Set up path aliases (`@components`, `@hooks`, etc.)
- [ ] Run `npx tailwindcss init -p`
- [ ] Configure `tailwind.config.js` content paths
- [ ] Create `renderer/src/index.css` with Tailwind imports

**Acceptance criteria:**
- `npm run dev` starts Vite dev server on port 5173
- Hot reload works when editing React files
- TailwindCSS classes work

**Files to create:**
- `vite.config.js`
- `tailwind.config.js`
- `postcss.config.js`
- `renderer/src/index.css`

---

### Task 2.3: Create Electron Main Process
**What to do:**
- [ ] Create `electron/main.js` with ES modules
- [ ] Set up BrowserWindow with proper security (contextIsolation, nodeIntegration: false)
- [ ] Load Vite dev server in dev mode, built files in production
- [ ] Add window lifecycle handlers (quit on close, reopen on activate)

**Acceptance criteria:**
- `npm run dev:all` opens Electron window
- Window loads React app from Vite
- DevTools open automatically in dev mode
- Window closes properly

**Files to create:**
- `electron/main.js`

---

### Task 2.4: Create Preload Bridge
**What to do:**
- [ ] Create `electron/preload.cjs` (CommonJS required)
- [ ] Use `contextBridge.exposeInMainWorld('electronAPI', {...})`
- [ ] Expose placeholder methods:
  - `checkSystem()`
  - `processAudio(options)`
  - `onProgress(callback)`
  - `selectAudioFile()`
  - `selectOutputFolder()`

**Acceptance criteria:**
- React app can access `window.electronAPI`
- No console errors about undefined API

**Files to create:**
- `electron/preload.cjs`

---

### Task 2.5: Create React App Structure
**What to do:**
- [ ] Create `renderer/index.html` with root div
- [ ] Create `renderer/src/main.jsx` as entry point
- [ ] Create `renderer/src/App.jsx` with basic navigation
- [ ] Create placeholder components:
  - `renderer/src/components/MainScreen.jsx`
  - `renderer/src/components/SetupScreen.jsx`
  - `renderer/src/components/SettingsScreen.jsx`
- [ ] Create hooks:
  - `renderer/src/hooks/useProgress.js`
  - `renderer/src/hooks/useSystemCheck.js`

**Acceptance criteria:**
- App renders in Electron window
- Can navigate between screens
- TailwindCSS styles apply
- No console errors

**Files to create:**
- `renderer/index.html`
- `renderer/src/main.jsx`
- `renderer/src/App.jsx`
- `renderer/src/components/*.jsx`
- `renderer/src/hooks/*.js`

---

## Phase 3: Core Functionality

**Goal:** Wire up Python backend to Electron

### Task 3.1: Create Python Bridge
**What to do:**
- [ ] Create `electron/python-bridge.js` (ES module)
- [ ] Implement `processAudio(options, progressCallback)`
- [ ] Use `spawn()` to call Python API
- [ ] Parse JSON output from Python
- [ ] Parse progress lines (`PROGRESS: {...}`)
- [ ] Get FFmpeg path from bundled resources

**Acceptance criteria:**
- Can spawn Python process from Electron
- Progress updates stream back to Electron
- Results return as structured JSON
- Errors handled gracefully

**Files to create:**
- `electron/python-bridge.js`

---

### Task 3.2: Create System Checker
**What to do:**
- [ ] Create `electron/system-checker.js` (ES module)
- [ ] Call `src/utils/system_check.py --json`
- [ ] Parse system status response
- [ ] Detect missing components (PyTorch, Demucs, Whisper models)
- [ ] Return structured status object

**Acceptance criteria:**
- Returns JSON with all system requirements
- Correctly detects GPU (NVIDIA/Apple Silicon/none)
- Lists available Whisper models
- Shows disk space available

**Files to create:**
- `electron/system-checker.js`

---

### Task 3.3: Create Download Manager
**What to do:**
- [ ] Create `electron/model-urls.js` with all download URLs
- [ ] Create `electron/download-manager.js` (ES module)
- [ ] Implement `downloadModel(type, name, progressCallback)`
- [ ] Implement checksum verification (SHA256)
- [ ] Cache downloads in platform-specific directories
- [ ] Implement `downloadMultiple()` for parallel downloads
- [ ] Add `getCacheSize()` and `clearCache()` methods

**Acceptance criteria:**
- Can download PyTorch wheel
- Can download Whisper models
- Can download Demucs models
- Verifies checksums before completing
- Progress callbacks work
- Resume/retry on failure
- Uses correct cache directory per platform

**Files to create:**
- `electron/model-urls.js`
- `electron/download-manager.js`

---

### Task 3.4: Wire IPC Handlers in Main Process
**What to do:**
- [ ] Add IPC handlers in `electron/main.js`:
  - `check-system`: Call SystemChecker
  - `process-audio`: Call PythonBridge
  - `download-component`: Call DownloadManager
  - `select-audio-file`: Open file dialog
  - `select-output-folder`: Open folder dialog
  - `save-settings`: Write to config file
  - `load-settings`: Read from config file
- [ ] Send progress events to renderer via `webContents.send()`

**Acceptance criteria:**
- All IPC handlers registered
- Renderer can invoke handlers
- Progress events flow to renderer
- File dialogs work

**Files to modify:**
- `electron/main.js`

---

### Task 3.5: Implement Setup Wizard
**What to do:**
- [ ] Build `SetupScreen.jsx` component:
  - [ ] Show system check results
  - [ ] Display missing components
  - [ ] GPU detection with CUDA offer
  - [ ] Whisper model selection (tiny/base/small/medium/large)
  - [ ] Download progress bars (individual + overall)
  - [ ] Checksum verification status
  - [ ] Error handling with retry
- [ ] Add state management for setup flow
- [ ] Save setup completion flag to config

**Acceptance criteria:**
- First launch shows setup wizard
- User can select Whisper model size
- CUDA option shown only if NVIDIA GPU detected
- Progress bars update in real-time
- Can retry failed downloads
- Subsequent launches skip wizard if setup complete

**Files to modify:**
- `renderer/src/components/SetupScreen.jsx`

---

### Task 3.6: Implement Main Processing Screen
**What to do:**
- [ ] Build `MainScreen.jsx` component:
  - [ ] File selection button
  - [ ] Show selected file path
  - [ ] Processing options (language, model, stems, fix-lyrics)
  - [ ] Start processing button
  - [ ] Real-time progress bar
  - [ ] Progress message display
  - [ ] Success/error alerts
  - [ ] Link to output file
- [ ] Wire up to `window.electronAPI.processAudio()`
- [ ] Subscribe to progress events

**Acceptance criteria:**
- Can select audio file via dialog
- Options panel works
- Processing starts when button clicked
- Progress bar updates smoothly
- Shows success message with output path
- Shows error messages on failure
- Can click to open output file

**Files to modify:**
- `renderer/src/components/MainScreen.jsx`

---

### Task 3.7: Implement Settings Screen
**What to do:**
- [ ] Build `SettingsScreen.jsx` component:
  - [ ] Default Whisper model selector
  - [ ] Default language selector
  - [ ] Default stems (2 vs 4)
  - [ ] LLM provider configuration (API keys)
  - [ ] Model cache location
  - [ ] Show cache size
  - [ ] Clear cache button
  - [ ] Theme selector (dark/light)
- [ ] Load/save settings from config file

**Acceptance criteria:**
- Settings persist between app launches
- Cache location can be changed
- Cache size displays correctly
- Clear cache works
- Theme changes apply immediately

**Files to modify:**
- `renderer/src/components/SettingsScreen.jsx`

---

## Phase 4: Advanced Features

**Goal:** Add power-user features

### Task 4.1: Batch Processing UI
**What to do:**
- [ ] Create `BatchScreen.jsx` component:
  - [ ] Folder selection
  - [ ] File list with status (pending/processing/complete/failed)
  - [ ] Apply settings to all files
  - [ ] Skip existing KAI files option
  - [ ] Overall progress (3/10 files)
  - [ ] Individual file progress
  - [ ] Pause/resume batch
  - [ ] Cancel batch
- [ ] Process files sequentially
- [ ] Show results summary

**Acceptance criteria:**
- Can select folder of audio files
- Shows all found audio files
- Processes files one by one
- Updates status for each file
- Can pause and resume
- Can cancel gracefully
- Shows summary when complete

**Files to create:**
- `renderer/src/components/BatchScreen.jsx`

---

### Task 4.2: Model Management UI
**What to do:**
- [ ] Create `ModelsScreen.jsx` component:
  - [ ] List installed models (Whisper, Demucs, PyTorch)
  - [ ] Show model sizes
  - [ ] Download additional models
  - [ ] Delete unused models
  - [ ] Re-download corrupted models
  - [ ] Switch between CPU and CUDA PyTorch

**Acceptance criteria:**
- Shows all installed models
- Can download missing models
- Can delete individual models
- Confirms before deleting
- Updates list after changes

**Files to create:**
- `renderer/src/components/ModelsScreen.jsx`

---

### Task 4.3: Drag & Drop Support
**What to do:**
- [ ] Add drag-drop zone to `MainScreen`
- [ ] Accept audio files (.mp3, .wav, .flac, .m4a, .ogg)
- [ ] Visual feedback on drag over
- [ ] Auto-start processing on drop (with confirmation)
- [ ] Support dropping multiple files (opens batch mode)

**Acceptance criteria:**
- Can drag audio file onto window
- Drop zone highlights on drag over
- File processes after drop
- Multiple files trigger batch mode

**Files to modify:**
- `renderer/src/components/MainScreen.jsx`

---

### Task 4.4: Keyboard Shortcuts
**What to do:**
- [ ] Add keyboard shortcuts:
  - `Cmd/Ctrl+O`: Open file
  - `Cmd/Ctrl+,`: Open settings
  - `Cmd/Ctrl+B`: Batch mode
  - `Escape`: Cancel current operation
  - `Cmd/Ctrl+Q`: Quit app
- [ ] Show shortcuts in menu tooltips

**Acceptance criteria:**
- All shortcuts work
- Shortcuts shown in UI
- No conflicts with browser shortcuts

**Files to modify:**
- `electron/main.js`
- All screen components

---

### Task 4.5: Error Handling & Logging
**What to do:**
- [ ] Create error boundary components
- [ ] Add global error handler in main process
- [ ] Log errors to file (platform-specific logs directory)
- [ ] Show user-friendly error messages
- [ ] Add "Copy error details" button
- [ ] Add "Report issue" button (opens GitHub)

**Acceptance criteria:**
- Errors don't crash the app
- Users see friendly error messages
- Error details available for debugging
- Logs saved to file
- Can copy/paste error info

**Files to create:**
- `renderer/src/components/ErrorBoundary.jsx`
- `electron/logger.js`

---

## Phase 5: Build & Distribution

**Goal:** Package for all platforms

### Task 5.1: Python Backend Packaging
**What to do:**
- [ ] Create `kai_converter.spec` for PyInstaller
- [ ] Include all required Python modules
- [ ] Include hidden imports (torch, demucs, whisper, etc.)
- [ ] Include data files (configs, etc.)
- [ ] Create `scripts/build-python.js` to automate
- [ ] Test on all platforms

**Acceptance criteria:**
- `npm run build:python` creates standalone Python bundle
- Bundle includes all dependencies
- Can run bundled Python without system Python
- Works on Windows, macOS, Linux

**Files to create:**
- `kai_converter.spec`
- `scripts/build-python.js`

---

### Task 5.2: FFmpeg Bundling
**What to do:**
- [ ] Create `scripts/download-ffmpeg.js`
- [ ] Download static FFmpeg builds for each platform:
  - Windows: BtbN builds
  - macOS: evermeet.cx builds
  - Linux: John Van Sickle builds
- [ ] Extract and place in `resources/bin/`
- [ ] Verify executables work

**Acceptance criteria:**
- FFmpeg binaries downloaded for all platforms
- Binaries placed in correct locations
- Bundled FFmpeg works on each platform

**Files to create:**
- `scripts/download-ffmpeg.js`

---

### Task 5.3: Electron Builder Configuration
**What to do:**
- [ ] Configure `electron-builder` in `package.json`:
  - [ ] Set app ID, name, description
  - [ ] Configure file patterns (include/exclude)
  - [ ] Set up extraResources (Python, FFmpeg)
  - [ ] Configure Windows: NSIS + portable
  - [ ] Configure macOS: DMG + zip, Intel + ARM64
  - [ ] Configure Linux: AppImage + deb + rpm
  - [ ] Set compression to maximum
  - [ ] Configure artifact names with version

**Acceptance criteria:**
- `npm run package:win` builds Windows installers
- `npm run package:mac` builds macOS DMGs (both archs)
- `npm run package:linux` builds Linux packages
- All artifacts named consistently

**Files to modify:**
- `package.json`

---

### Task 5.4: GitHub Actions CI/CD
**What to do:**
- [ ] Create `.github/workflows/build.yml`:
  - [ ] Job 1: Build Python backend (Ubuntu)
  - [ ] Job 2: Build Electron (matrix: Windows/Mac/Linux)
  - [ ] Job 3: Create release (on tags only)
- [ ] Test workflow on pull request
- [ ] Test release on tag push

**Acceptance criteria:**
- PR builds succeed on all platforms
- Tag push creates GitHub Release
- All 9 artifacts uploaded to release
- Release notes auto-generated

**Files to create:**
- `.github/workflows/build.yml`

---

### Task 5.5: Auto-Update Configuration
**What to do:**
- [ ] Install `electron-updater`
- [ ] Add auto-update logic to `electron/main.js`
- [ ] Show update notification dialog
- [ ] Download and install updates
- [ ] Configure in `electron-builder.yml`

**Acceptance criteria:**
- App checks for updates on launch
- Users notified of updates
- Can download and install updates
- Restart applies update

**Files to modify:**
- `electron/main.js`
- Create: `electron-builder.yml`

---

## Phase 6: Testing & Polish

**Goal:** Production-ready release

### Task 6.1: Manual Testing Checklist
**What to do:**
- [ ] Test on Windows 10/11
- [ ] Test on macOS Intel
- [ ] Test on macOS Apple Silicon
- [ ] Test on Ubuntu 22.04
- [ ] Test on Fedora
- [ ] Test with NVIDIA GPU
- [ ] Test CPU-only
- [ ] Test with all Whisper models
- [ ] Test batch processing with 10+ files
- [ ] Test network failures during download
- [ ] Test disk space issues
- [ ] Test permissions errors
- [ ] Test with non-ASCII filenames
- [ ] Test with spaces in paths
- [ ] Test drag & drop
- [ ] Test keyboard shortcuts

**Acceptance criteria:**
- All tests pass on all platforms
- No crashes
- Errors handled gracefully

---

### Task 6.2: Documentation
**What to do:**
- [ ] Update `README.md` with GUI instructions
- [ ] Create `docs/GUI_USER_GUIDE.md`:
  - [ ] Installation instructions per platform
  - [ ] First-run setup walkthrough
  - [ ] Feature guide with screenshots
  - [ ] Troubleshooting section
  - [ ] FAQ
- [ ] Create `docs/DEVELOPMENT.md`:
  - [ ] Dev environment setup
  - [ ] Building locally
  - [ ] Running tests
  - [ ] Contributing guidelines
- [ ] Add screenshots to `docs/screenshots/`

**Acceptance criteria:**
- Users can install and use app from README
- All features documented
- Screenshots up-to-date

**Files to create/modify:**
- `README.md`
- `docs/GUI_USER_GUIDE.md`
- `docs/DEVELOPMENT.md`

---

### Task 6.3: UI Polish
**What to do:**
- [ ] Design/add app icons (16x16 to 512x512)
- [ ] Add loading spinners
- [ ] Add empty states ("No files selected")
- [ ] Add success animations
- [ ] Polish button states (hover, active, disabled)
- [ ] Add tooltips to complex options
- [ ] Improve color scheme
- [ ] Add dark mode support
- [ ] Test accessibility (keyboard navigation, screen readers)

**Acceptance criteria:**
- App looks professional
- All interactions have visual feedback
- Icons look good at all sizes
- Dark mode works
- Keyboard navigation works

---

### Task 6.4: Performance Optimization
**What to do:**
- [ ] Optimize React renders (useMemo, useCallback)
- [ ] Lazy load heavy components
- [ ] Debounce progress updates (100ms)
- [ ] Optimize file list rendering (virtual scrolling for 100+ files)
- [ ] Profile and fix memory leaks
- [ ] Test with large files (>100 MB audio)

**Acceptance criteria:**
- UI stays responsive during processing
- No memory leaks over 1 hour
- Batch of 50 files completes without issues

---

### Task 6.5: Release v1.0
**What to do:**
- [ ] Tag release: `git tag v1.0.0`
- [ ] Push tag: `git push origin v1.0.0`
- [ ] Wait for GitHub Actions to build
- [ ] Download and test all artifacts
- [ ] Write release notes with:
  - [ ] What's new
  - [ ] Installation instructions
  - [ ] Known issues
  - [ ] System requirements
- [ ] Publish release
- [ ] Share on social media/forums

**Acceptance criteria:**
- GitHub Release created
- All 9 artifacts available
- Release notes complete
- Artifacts tested

---

## Task Priority Summary

**Must-Have (MVP):**
1. Phase 0: Task 0.1 (Repository cleanup)
2. Phase 1: All tasks (Python refactoring)
3. Phase 2: All tasks (Electron setup)
4. Phase 3: Tasks 3.1-3.6 (Core functionality)
5. Phase 5: Tasks 5.1-5.3 (Building)

**Should-Have (v1.0):**
6. Phase 3: Task 3.7 (Settings)
7. Phase 4: Tasks 4.1-4.2 (Batch, Models)
8. Phase 5: Tasks 5.4-5.5 (CI/CD, Updates)
9. Phase 6: Tasks 6.1-6.2 (Testing, Docs)

**Nice-to-Have (v1.1+):**
10. Phase 4: Tasks 4.3-4.5 (Polish features)
11. Phase 6: Tasks 6.3-6.5 (Polish, Performance)

---

## Development Timeline

### Week 1: Core MVP
- **Day 1 Morning:** Phase 0 (Repository cleanup - 1-2 hours)
- **Day 1-2:** Phase 1 (Python refactoring)
- **Day 3:** Phase 2 (Electron setup)
- **Day 4-5:** Phase 3 (Core GUI functionality)

### Week 2: Complete v1.0
- **Day 1:** Phase 4 (Advanced features)
- **Day 2:** Phase 5 (Building & CI/CD)
- **Day 3-5:** Phase 6 (Testing & polish)

### Week 3+: Production Release
- Bug fixes from testing
- Documentation polish
- Community feedback
- v1.0.0 release

---

## Next Steps

**Start here:**
1. ✅ Run `git checkout -b feature/electron-gui`
2. ⬜ Begin Phase 0, Task 0.1 (Repository cleanup)
3. ⬜ Test CLI scripts after moving them
4. ⬜ Continue to Phase 1, Task 1.1 (Create API facade)
5. ⬜ Commit frequently with clear messages
6. ⬜ Ask Claude Code for help with each task!

**Remember:**
- Test the CLI after each Phase 0 and Phase 1 task
- Commit after completing each task
- Run the app frequently to catch issues early
- Don't optimize prematurely - make it work first!

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