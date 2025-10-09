const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods that allow the renderer process to use
// ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld('electronAPI', {
  // Theme management
  getTheme: () => ipcRenderer.invoke('get-theme'),
  setTheme: (theme) => ipcRenderer.invoke('set-theme', theme),
  onThemeChanged: (callback) => {
    const subscription = (event, theme) => callback(theme);
    ipcRenderer.on('theme-changed', subscription);
    // Return unsubscribe function
    return () => ipcRenderer.removeListener('theme-changed', subscription);
  },

  // System check
  checkSystem: () => ipcRenderer.invoke('check-system'),

  // Audio processing
  processAudio: (options) => ipcRenderer.invoke('process-audio', options),
  onProgress: (callback) => {
    const subscription = (event, progress) => callback(progress);
    ipcRenderer.on('processing-progress', subscription);
    return () => ipcRenderer.removeListener('processing-progress', subscription);
  },

  // Model downloads
  downloadComponent: (component) => ipcRenderer.invoke('download-component', component),
  onDownloadProgress: (callback) => {
    const subscription = (event, progress) => callback(progress);
    ipcRenderer.on('download-progress', subscription);
    return () => ipcRenderer.removeListener('download-progress', subscription);
  },

  // File dialogs
  selectAudioFile: () => ipcRenderer.invoke('select-audio-file'),
  selectOutputFolder: () => ipcRenderer.invoke('select-output-folder'),
  selectKaiFile: () => ipcRenderer.invoke('select-kai-file'),

  // Audio metadata
  readAudioMetadata: (filePath) => ipcRenderer.invoke('read-audio-metadata', filePath),
  readKaiMetadata: (filePath) => ipcRenderer.invoke('read-kai-metadata', filePath),

  // Lyrics
  fetchLyrics: (title, artist) => ipcRenderer.invoke('fetch-lyrics', title, artist),
  regenerateLyrics: (options) => ipcRenderer.invoke('regenerate-lyrics', options),
  fixLyrics: (options) => ipcRenderer.invoke('fix-lyrics', options),

  // Settings
  saveSettings: (settings) => ipcRenderer.invoke('save-settings', settings),
  loadSettings: () => ipcRenderer.invoke('load-settings'),

  // External links
  openExternal: (url) => ipcRenderer.invoke('open-external', url),

  // Paths
  getHomeDirectory: () => ipcRenderer.invoke('get-home-directory'),

  // Logs
  onLogs: (callback) => {
    const subscription = (event, logEntry) => callback(logEntry);
    ipcRenderer.on('log-entry', subscription);
    return () => ipcRenderer.removeListener('log-entry', subscription);
  },
});
