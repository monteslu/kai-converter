import { app, BrowserWindow, ipcMain, nativeTheme } from 'electron';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import { PythonBridge } from './python-bridge.js';
import { SystemChecker } from './system-checker.js';
import { DownloadManager } from './download-manager.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Initialize bridges
const pythonBridge = new PythonBridge();
const systemChecker = new SystemChecker();
const downloadManager = new DownloadManager();

const isDev = !app.isPackaged;

let mainWindow = null;

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

  // Load the app
  if (isDev) {
    await mainWindow.loadURL('http://localhost:5174');
    mainWindow.webContents.openDevTools();
  } else {
    await mainWindow.loadFile(join(__dirname, '..', 'renderer', 'dist', 'index.html'));
  }

  // Show when ready
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  // Handle window close
  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// App lifecycle
app.whenReady().then(() => {
  createWindow();

  // macOS: Re-create window when dock icon is clicked
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

// Quit when all windows are closed (except macOS)
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// IPC Handlers

// Theme management
ipcMain.handle('get-theme', () => {
  return nativeTheme.shouldUseDarkColors ? 'dark' : 'light';
});

ipcMain.handle('set-theme', (event, theme) => {
  // theme: 'light', 'dark', or 'system'
  nativeTheme.themeSource = theme;
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
    const result = await systemChecker.checkSystem();
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
    const result = await pythonBridge.processAudio(options, (progress) => {
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
      case 'pytorch':
        result = await downloadManager.downloadPyTorch(variant || 'auto', progressCallback);
        break;

      case 'demucs':
        result = await downloadManager.downloadDemucs(progressCallback);
        break;

      case 'whisper':
        result = await downloadManager.downloadWhisper(progressCallback);
        break;

      case 'whisper-model':
        result = await downloadManager.downloadWhisperModel(model || 'small', progressCallback);
        break;

      case 'demucs-model':
        result = await downloadManager.downloadDemucsModel(model || 'htdemucs_ft', progressCallback);
        break;

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

// Settings (will be fully implemented in Phase 3)
ipcMain.handle('save-settings', async (event, settings) => {
  // TODO: Save to config file
  console.log('Save settings:', settings);
  return { success: true };
});

ipcMain.handle('load-settings', async () => {
  // TODO: Load from config file
  return {
    whisperModel: 'large-v3-turbo',
    language: 'auto',
    stems: 2,
    gpu: 'auto',
  };
});
