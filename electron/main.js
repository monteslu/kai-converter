import { app, BrowserWindow, ipcMain, nativeTheme } from 'electron';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

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
    await mainWindow.loadURL('http://localhost:5173');
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

// Placeholder IPC handlers (will be implemented in Phase 3)
ipcMain.handle('check-system', async () => {
  // TODO: Implement system checker
  return {
    python: { available: false },
    pytorch: { available: false },
    demucs: { available: false },
    whisper: { available: false },
    gpu: { available: false, type: 'none' },
  };
});

ipcMain.handle('process-audio', async (event, options) => {
  // TODO: Implement Python bridge
  return {
    success: false,
    error: 'Not implemented yet',
  };
});

ipcMain.handle('download-component', async (event, component) => {
  // TODO: Implement download manager
  return {
    success: false,
    error: 'Not implemented yet',
  };
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
    whisperModel: 'small',
    language: 'auto',
    stems: 2,
    gpu: 'auto',
  };
});
