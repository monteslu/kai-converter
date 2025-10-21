import { app, BrowserWindow, ipcMain, nativeTheme, shell, dialog } from 'electron';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import { existsSync } from 'fs';
import Store from 'electron-store';
import { PythonBridge } from './python-bridge.js';
import { SystemChecker } from './system-checker.js';
import { DownloadManager } from './download-manager.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Lazy-initialize store and bridges (after app is ready)
let store = null;
let pythonBridge = null;
let systemChecker = null;
let downloadManager = null;

function getStore() {
  if (!store) {
    store = new Store({
      name: 'kai-converter-settings',
      encryptionKey: 'kai-converter-secure-key', // Basic encryption for API keys
    });
  }
  return store;
}

function getBridges() {
  if (!pythonBridge) {
    pythonBridge = new PythonBridge(sendLog);
    systemChecker = new SystemChecker();
    downloadManager = new DownloadManager();
  }
  return { pythonBridge, systemChecker, downloadManager };
}

// Reinitialize bridges (e.g., after Python setup completes)
function reinitializeBridges() {
  console.log('[Main] Reinitializing bridges after setup...');
  pythonBridge = new PythonBridge(sendLog);
  systemChecker = new SystemChecker();
  downloadManager = new DownloadManager();
  return { pythonBridge, systemChecker, downloadManager };
}

const isDev = !app.isPackaged;

let mainWindow = null;

// Helper to send logs to renderer
function sendLog(level, message) {
  if (mainWindow && !mainWindow.isDestroyed()) {
    try {
      mainWindow.webContents.send('log-entry', {
        level,
        message,
        timestamp: new Date().toISOString()
      });
    } catch {
      // Ignore errors if window is being destroyed
    }
  }
}

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      preload: join(__dirname, 'preload.cjs'),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: false, // Needed for some Node.js APIs
    },
    show: false, // Don't show until ready
  });

  // Show when ready
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    // Test log to verify logging system
    setTimeout(() => {
      sendLog('info', 'KAI Converter ready - logging system initialized');
    }, 1000);
  });

  // Fallback: show window after timeout if ready-to-show doesn't fire
  const showTimeout = setTimeout(() => {
    if (mainWindow && !mainWindow.isVisible()) {
      console.warn('[Main] Window not shown after 3s, forcing show');
      mainWindow.show();
    }
  }, 3000);

  // Load the app
  try {
    if (isDev) {
      await mainWindow.loadURL('http://localhost:5174');
      mainWindow.webContents.openDevTools();
    } else {
      await mainWindow.loadFile(join(__dirname, '..', 'renderer', 'dist', 'index.html'));
    }
    clearTimeout(showTimeout);
  } catch (error) {
    console.error('[Main] Failed to load window:', error);
    clearTimeout(showTimeout);
    // Show window anyway so user can see what's wrong
    mainWindow.show();
  }

  // Handle window close
  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// App lifecycle
app.whenReady().then(async () => {
  // Initialize bridges (they gracefully handle missing Python)
  getBridges();

  // Load and apply saved theme before creating window
  const savedTheme = getStore().get('theme', 'system');
  nativeTheme.themeSource = savedTheme;

  createWindow();

  // macOS: Re-create window when dock icon is clicked
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

// Quit when all windows are closed (ALL platforms - no background running)
app.on('window-all-closed', () => {
  app.quit(); // Always quit - don't run in background
});

// Clean up Python processes when quitting
app.on('before-quit', () => {
  if (pythonBridge) {
    pythonBridge.cleanup();
  }
});

// IPC Handlers

// Theme management
ipcMain.handle('get-theme', () => {
  // Return the saved theme preference (not the computed dark/light state)
  return getStore().get('theme', 'system');
});

ipcMain.handle('set-theme', (event, theme) => {
  // theme: 'light', 'dark', or 'system'
  nativeTheme.themeSource = theme;
  // Persist theme preference to store
  getStore().set('theme', theme);
  return nativeTheme.shouldUseDarkColors ? 'dark' : 'light';
});

// Listen for theme changes and notify renderer
nativeTheme.on('updated', () => {
  if (mainWindow) {
    const theme = nativeTheme.shouldUseDarkColors ? 'dark' : 'light';
    mainWindow.webContents.send('theme-changed', theme);
  }
});

// System check
ipcMain.handle('check-system', async () => {
  try {
    const bridges = getBridges();
    const result = await bridges.systemChecker.checkSystem();
    return result;
  } catch (error) {
    console.error('System check error:', error);
    return {
      error: error.message,
      python: { available: false },
      pytorch: { available: false },
      demucs: { available: false },
      whisper: { available: false },
      gpu: { available: false, type: 'none' },
    };
  }
});

// Audio processing
ipcMain.handle('process-audio', async (event, options) => {
  try {
    const bridges = getBridges();
    const result = await bridges.pythonBridge.processAudio(options, (progress) => {
      // Send progress to renderer
      if (mainWindow) {
        mainWindow.webContents.send('processing-progress', progress);
      }
    });
    return result;
  } catch (error) {
    console.error('Processing error:', error);
    return {
      success: false,
      error: error.error || error.message,
      error_type: error.error_type || 'UnknownError',
    };
  }
});

// Reinitialize bridges (e.g., after Python is downloaded)
ipcMain.handle('reinitialize-bridges', async () => {
  try {
    reinitializeBridges();
    return { success: true };
  } catch (error) {
    console.error('Failed to reinitialize bridges:', error);
    return { success: false, error: error.message };
  }
});

// Download component
ipcMain.handle('download-component', async (event, options) => {
  try {
    const { component, variant, model } = options;

    let result;

    // Progress callback to send updates to renderer
    const progressCallback = (progress) => {
      if (mainWindow) {
        mainWindow.webContents.send('download-progress', {
          component,
          ...progress,
        });
      }
    };

    // Route to appropriate download method
    switch (component) {
      case 'python':
        result = await getBridges().downloadManager.downloadPython(progressCallback);
        // If Python was just installed, reinitialize bridges so they pick up the new Python
        if (result.success) {
          console.log('[Main] Python installed - reinitializing bridges...');
          reinitializeBridges();
        }
        break;

      case 'pytorch':
        result = await getBridges().downloadManager.downloadPyTorch(variant || 'auto', progressCallback);
        break;

      case 'demucs':
        result = await getBridges().downloadManager.downloadDemucs(progressCallback);
        break;

      case 'whisper':
        result = await getBridges().downloadManager.downloadWhisper(progressCallback);
        break;

      case 'core-deps':
        result = await getBridges().downloadManager.downloadCoreDeps(progressCallback);
        break;

      case 'whisper-model':
        result = await getBridges().downloadManager.downloadWhisperModel(model || 'small', progressCallback);
        break;

      case 'demucs-model':
        result = await getBridges().downloadManager.downloadDemucsModel(model || 'htdemucs_ft', progressCallback);
        break;

      case 'ffmpeg':
        result = await getBridges().downloadManager.downloadFfmpeg(progressCallback);
        break;

      // Note: yt-dlp is installed via pip in core-deps (requirements-core.txt)
      // Note: mp4box is no longer used - we use pymp4 library instead

      default:
        return {
          success: false,
          error: `Unknown component: ${component}`,
        };
    }

    return result;
  } catch (error) {
    console.error('Download error:', error);
    return {
      success: false,
      error: error.error || error.message,
      stderr: error.stderr,
    };
  }
});

// File dialogs (will be fully implemented in Phase 3)
ipcMain.handle('select-audio-file', async () => {
  const { dialog } = await import('electron');
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openFile'],
    filters: [
      { name: 'Audio Files', extensions: ['mp3', 'wav', 'flac', 'm4a', 'ogg'] },
      { name: 'All Files', extensions: ['*'] },
    ],
  });
  return result.filePaths[0] || null;
});

ipcMain.handle('select-output-folder', async () => {
  const { dialog } = await import('electron');
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory'],
  });
  return result.filePaths[0] || null;
});

// Read audio metadata
ipcMain.handle('read-audio-metadata', async (event, filePath) => {
  try {
    const bridges = getBridges();
    const metadata = await bridges.pythonBridge.readAudioMetadata(filePath);
    return metadata;
  } catch (error) {
    console.error('Metadata read error:', error);
    return {
      success: false,
      error: error.message,
      title: null,
      artist: null,
    };
  }
});

// Fetch lyrics from LRCLIB
ipcMain.handle('fetch-lyrics', async (event, title, artist) => {
  try {
    const bridges = getBridges();
    const result = await bridges.pythonBridge.fetchLyrics(title, artist);
    return result;
  } catch (error) {
    console.error('Lyrics fetch error:', error);
    return {
      success: false,
      error: error.message,
    };
  }
});

// Settings
ipcMain.handle('save-settings', async (event, settings) => {
  try {
    // Save all settings to encrypted store
    getStore().set('settings', settings);
    console.log('Settings saved successfully');
    return { success: true };
  } catch (error) {
    console.error('Failed to save settings:', error);
    return { success: false, error: error.message };
  }
});

ipcMain.handle('load-settings', async () => {
  try {
    // Load settings from store with defaults
    const settings = getStore().get('settings', {
      whisperModel: 'large-v3-turbo',
      language: 'auto',
      stems: 2,
      gpu: 'auto',
      llm: {
        enabled: true,
        provider: 'claude',
        claudeApiKey: '',
        claudeModel: 'claude-3-5-sonnet-20241022',
        openaiApiKey: '',
        openaiModel: 'gpt-4o',
        geminiApiKey: '',
        geminiModel: 'gemini-1.5-flash',
        localLlmHost: 'localhost',
        localLlmPort: '1234',
      },
    });
    return settings;
  } catch (error) {
    console.error('Failed to load settings:', error);
    // Return defaults on error
    return {
      whisperModel: 'large-v3-turbo',
      language: 'auto',
      stems: 2,
      gpu: 'auto',
      llm: {
        enabled: true,
        provider: 'claude',
        claudeApiKey: '',
        claudeModel: 'claude-3-5-sonnet-20241022',
        openaiApiKey: '',
        openaiModel: 'gpt-4o',
        geminiApiKey: '',
        geminiModel: 'gemini-1.5-flash',
        localLlmHost: 'localhost',
        localLlmPort: '1234',
      },
    };
  }
});

// Open external links
ipcMain.handle('open-external', async (event, url) => {
  try {
    await shell.openExternal(url);
    return { success: true };
  } catch (error) {
    console.error('Failed to open external link:', error);
    return { success: false, error: error.message };
  }
});

// Get user's home directory
ipcMain.handle('get-home-directory', async () => {
  return app.getPath('home');
});

// Select KAI file
ipcMain.handle('select-kai-file', async () => {
  const { dialog } = await import('electron');
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openFile'],
    filters: [
      { name: 'KAI Files', extensions: ['kai'] },
      { name: 'All Files', extensions: ['*'] },
    ],
  });
  return result.filePaths[0] || null;
});

// Read KAI metadata
ipcMain.handle('read-kai-metadata', async (event, filePath) => {
  try {
    const bridges = getBridges();
    const metadata = await bridges.pythonBridge.readKaiMetadata(filePath);
    return metadata;
  } catch (error) {
    console.error('KAI metadata read error:', error);
    return {
      success: false,
      error: error.message,
    };
  }
});

// Update KAI file (save edits)
ipcMain.handle('update-kai-file', async (event, updates) => {
  try {
    const bridges = getBridges();
    const result = await bridges.pythonBridge.updateKaiFile(updates);
    return result;
  } catch (error) {
    console.error('KAI file update error:', error);
    return {
      success: false,
      error: error.message,
    };
  }
});

// Extract audio files from KAI for playback
ipcMain.handle('extract-kai-audio', async (event, filePath) => {
  try {
    const bridges = getBridges();
    const result = await bridges.pythonBridge.extractKaiAudio(filePath);
    return result;
  } catch (error) {
    console.error('KAI audio extraction error:', error);
    return {
      success: false,
      error: error.message,
    };
  }
});

// Regenerate lyrics (full Whisper re-transcription)
ipcMain.handle('regenerate-lyrics', async (event, options) => {
  try {
    const bridges = getBridges();
    const result = await bridges.pythonBridge.regenerateLyrics(options, (progress) => {
      // Send progress to renderer
      if (mainWindow) {
        mainWindow.webContents.send('processing-progress', progress);
      }
    });
    return result;
  } catch (error) {
    console.error('Regenerate lyrics error:', error);
    return {
      success: false,
      error: error.error || error.message,
      error_type: error.error_type || 'UnknownError',
    };
  }
});

// Fix lyrics (LLM correction only)
ipcMain.handle('fix-lyrics', async (event, options) => {
  try {
    const bridges = getBridges();
    const result = await bridges.pythonBridge.fixLyrics(options);
    return result;
  } catch (error) {
    console.error('Fix lyrics error:', error);
    return {
      success: false,
      error: error.error || error.message,
      error_type: error.error_type || 'UnknownError',
    };
  }
});
