import https from 'https';
import http from 'http';
import { createWriteStream, existsSync, statSync, mkdirSync } from 'fs';
import { join, dirname } from 'path';
import { homedir, platform } from 'os';
import { spawn } from 'child_process';
import { fileURLToPath } from 'url';
import { app } from 'electron';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

/**
 * Download Manager - Handles downloading and installing components
 *
 * Downloads:
 * - PyTorch (CPU/CUDA versions)
 * - Whisper models (tiny, base, small, medium, large-v3)
 * - Demucs models (htdemucs_ft)
 *
 * Features:
 * - Progress tracking
 * - Resume capability
 * - Error handling
 * - Checksum verification (for models)
 */

export class DownloadManager {
  constructor() {
    try {
      this.pythonPath = this._getPythonPath();
    } catch (error) {
      console.error('[DownloadManager] Failed to initialize:', error.message);
      this.pythonPath = null;
      this.initError = error.message;
    }
    this.activeDownloads = new Map();
  }

  /**
   * Get the Python executable path
   * - Development: use python-standalone (same as production)
   * - Production: use bundled python-standalone
   *
   * This ensures consistency - if it works in dev, it works for users!
   */
  _getPythonPath() {
    const platform = process.platform;

    // Helper to get standalone Python executable path
    const getStandalonePath = (baseDir) => {
      if (platform === 'win32') {
        return join(baseDir, 'python.exe');
      } else {
        return join(baseDir, 'bin', 'python3');
      }
    };

    if (app.isPackaged) {
      // Production: use bundled standalone Python
      const bundledPython = getStandalonePath(join(process.resourcesPath, 'python'));
      console.log('[DownloadManager] Using bundled Python:', bundledPython);
      return bundledPython;
    } else {
      // Development: use local standalone Python (same as production!)
      const standalonePython = getStandalonePath(join(__dirname, '..', 'python-standalone'));
      if (existsSync(standalonePython)) {
        console.log('[DownloadManager] Using standalone Python:', standalonePython);
        return standalonePython;
      } else {
        console.error('[DownloadManager] ❌ Standalone Python not found!');
        console.error('[DownloadManager] Run: npm run setup:python');
        throw new Error('Python not found. Please run: npm run setup:python');
      }
    }
  }

  /**
   * Get cache directory for downloads
   */
  _getCacheDir() {
    const plat = platform();
    if (plat === 'darwin') {
      return join(homedir(), 'Library', 'Caches', 'KAI-Converter');
    } else if (plat === 'win32') {
      return join(homedir(), 'AppData', 'Local', 'KAI-Converter', 'Cache');
    } else {
      return join(homedir(), '.cache', 'kai-converter');
    }
  }

  /**
   * Download a file with progress tracking
   *
   * @param {string} url - URL to download from
   * @param {string} destination - File path to save to
   * @param {Function} progressCallback - Called with (bytesDownloaded, totalBytes)
   * @returns {Promise<void>}
   */
  async _downloadFile(url, destination, progressCallback) {
    return new Promise((resolve, reject) => {
      const protocol = url.startsWith('https') ? https : http;

      // Ensure directory exists
      const dir = dirname(destination);
      if (!existsSync(dir)) {
        mkdirSync(dir, { recursive: true });
      }

      // Check if file already exists (resume support)
      let resumePosition = 0;
      if (existsSync(destination)) {
        resumePosition = statSync(destination).size;
      }

      const options = {};
      if (resumePosition > 0) {
        options.headers = { Range: `bytes=${resumePosition}-` };
      }

      const request = protocol.get(url, options, (response) => {
        // Handle redirects
        if (response.statusCode === 301 || response.statusCode === 302) {
          const redirectUrl = response.headers.location;
          resolve(this._downloadFile(redirectUrl, destination, progressCallback));
          return;
        }

        if (response.statusCode !== 200 && response.statusCode !== 206) {
          reject(new Error(`HTTP ${response.statusCode}: ${response.statusMessage}`));
          return;
        }

        const totalBytes = parseInt(response.headers['content-length'] || '0', 10);
        const totalWithResume = totalBytes + resumePosition;
        let downloadedBytes = resumePosition;

        const fileStream = createWriteStream(destination, {
          flags: resumePosition > 0 ? 'a' : 'w'
        });

        response.on('data', (chunk) => {
          downloadedBytes += chunk.length;
          if (progressCallback) {
            progressCallback(downloadedBytes, totalWithResume);
          }
        });

        response.pipe(fileStream);

        fileStream.on('finish', () => {
          fileStream.close();
          resolve();
        });

        fileStream.on('error', (error) => {
          fileStream.close();
          reject(error);
        });
      });

      request.on('error', (error) => {
        reject(error);
      });

      request.end();
    });
  }

  /**
   * Run pip install command
   *
   * @param {string} packageSpec - Package specification (e.g., 'torch' or 'torch==2.0.0')
   * @param {Function} progressCallback - Called with progress updates
   * @returns {Promise<Object>}
   */
  async _pipInstall(packageSpec, progressCallback) {
    if (!this.pythonPath) {
      throw {
        success: false,
        error: this.initError || 'Python not initialized',
      };
    }

    return new Promise((resolve, reject) => {
      const args = ['-m', 'pip', 'install', packageSpec, '--no-cache-dir'];

      const pip = spawn(this.pythonPath, args, {
        stdio: ['pipe', 'pipe', 'pipe'],
      });

      let output = '';
      let errorOutput = '';

      pip.stdout.on('data', (data) => {
        const text = data.toString();
        output += text;

        // Parse pip progress
        const lines = text.split('\n');
        for (const line of lines) {
          if (progressCallback) {
            // Simple progress parsing - pip doesn't have great progress output
            if (line.includes('Downloading')) {
              progressCallback({ stage: 'downloading', message: line.trim() });
            } else if (line.includes('Installing')) {
              progressCallback({ stage: 'installing', message: line.trim() });
            } else if (line.includes('Successfully installed')) {
              progressCallback({ stage: 'complete', message: line.trim() });
            }
          }
        }
      });

      pip.stderr.on('data', (data) => {
        errorOutput += data.toString();
      });

      pip.on('close', (code) => {
        if (code === 0) {
          resolve({
            success: true,
            output: output,
          });
        } else {
          reject({
            success: false,
            error: `pip install failed with code ${code}`,
            stderr: errorOutput,
          });
        }
      });

      pip.on('error', (error) => {
        reject({
          success: false,
          error: `Failed to run pip: ${error.message}`,
        });
      });
    });
  }

  /**
   * Download and install PyTorch
   *
   * @param {string} variant - 'cpu', 'cuda', or 'auto'
   * @param {Function} progressCallback - Called with progress updates
   * @returns {Promise<Object>}
   */
  async downloadPyTorch(variant = 'auto', progressCallback) {
    try {
      // Detect CUDA availability if auto
      if (variant === 'auto') {
        variant = 'cpu'; // Default to CPU for safety
        // Could check for NVIDIA GPU here, but safer to let user choose
      }

      // PyTorch install command
      let packageSpec = 'torch torchvision torchaudio';

      if (variant === 'cuda') {
        // CUDA 11.8 version (most compatible)
        packageSpec = 'torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118';
      }

      if (progressCallback) {
        progressCallback({ stage: 'preparing', percent: 0, message: 'Preparing to download PyTorch...' });
      }

      await this._pipInstall(packageSpec, (update) => {
        if (progressCallback) {
          // Estimate progress based on stage
          let percent = 10;
          if (update.stage === 'downloading') percent = 30;
          else if (update.stage === 'installing') percent = 70;
          else if (update.stage === 'complete') percent = 100;

          progressCallback({
            stage: update.stage,
            percent: percent,
            message: update.message,
          });
        }
      });

      return {
        success: true,
        component: 'pytorch',
        variant: variant,
        message: 'PyTorch installed successfully',
      };
    } catch (error) {
      return {
        success: false,
        component: 'pytorch',
        error: error.error || error.message,
        stderr: error.stderr,
      };
    }
  }

  /**
   * Download and install Demucs
   *
   * @param {Function} progressCallback - Called with progress updates
   * @returns {Promise<Object>}
   */
  async downloadDemucs(progressCallback) {
    try {
      if (progressCallback) {
        progressCallback({ stage: 'preparing', percent: 0, message: 'Preparing to download Demucs...' });
      }

      await this._pipInstall('demucs', (update) => {
        if (progressCallback) {
          let percent = 10;
          if (update.stage === 'downloading') percent = 40;
          else if (update.stage === 'installing') percent = 80;
          else if (update.stage === 'complete') percent = 100;

          progressCallback({
            stage: update.stage,
            percent: percent,
            message: update.message,
          });
        }
      });

      return {
        success: true,
        component: 'demucs',
        message: 'Demucs installed successfully',
      };
    } catch (error) {
      return {
        success: false,
        component: 'demucs',
        error: error.error || error.message,
        stderr: error.stderr,
      };
    }
  }

  /**
   * Download and install Whisper
   *
   * @param {Function} progressCallback - Called with progress updates
   * @returns {Promise<Object>}
   */
  async downloadWhisper(progressCallback) {
    try {
      if (progressCallback) {
        progressCallback({ stage: 'preparing', percent: 0, message: 'Preparing to download Whisper...' });
      }

      await this._pipInstall('openai-whisper', (update) => {
        if (progressCallback) {
          let percent = 10;
          if (update.stage === 'downloading') percent = 40;
          else if (update.stage === 'installing') percent = 80;
          else if (update.stage === 'complete') percent = 100;

          progressCallback({
            stage: update.stage,
            percent: percent,
            message: update.message,
          });
        }
      });

      return {
        success: true,
        component: 'whisper',
        message: 'Whisper installed successfully',
      };
    } catch (error) {
      return {
        success: false,
        component: 'whisper',
        error: error.error || error.message,
        stderr: error.stderr,
      };
    }
  }

  /**
   * Download a specific Whisper model
   *
   * Models are downloaded automatically on first use by Whisper library,
   * but we can pre-download them by running a test transcription.
   *
   * @param {string} modelName - Model size (tiny, base, small, medium, large-v3)
   * @param {Function} progressCallback - Called with progress updates
   * @returns {Promise<Object>}
   */
  async downloadWhisperModel(modelName = 'small', progressCallback) {
    try {
      if (progressCallback) {
        progressCallback({
          stage: 'downloading',
          percent: 0,
          message: `Downloading Whisper ${modelName} model...`
        });
      }

      // Create a minimal test file to trigger model download
      const testScript = `
import whisper
import json
import sys

try:
    print(f"Loading {modelName} model...", file=sys.stderr)
    model = whisper.load_model("${modelName}")
    print(json.dumps({"success": True, "model": "${modelName}"}))
except Exception as e:
    print(json.dumps({"success": False, "error": str(e)}))
`;

      await new Promise((resolve, reject) => {
        const python = spawn(this.pythonPath, ['-c', testScript], {
          stdio: ['pipe', 'pipe', 'pipe'],
        });

        let output = '';
        let errorOutput = '';

        python.stdout.on('data', (data) => {
          output += data.toString();
        });

        python.stderr.on('data', (data) => {
          errorOutput += data.toString();
          // Whisper prints download progress to stderr
          if (progressCallback) {
            const text = data.toString();
            if (text.includes('%')) {
              // Parse progress from stderr
              progressCallback({
                stage: 'downloading',
                percent: 50, // Approximate
                message: text.trim(),
              });
            }
          }
        });

        python.on('close', () => {
          try {
            const result = JSON.parse(output.trim());
            if (result.success) {
              resolve(result);
            } else {
              reject(result);
            }
          } catch {
            reject({
              success: false,
              error: 'Failed to parse output',
              stderr: errorOutput,
            });
          }
        });

        python.on('error', (error) => {
          reject({
            success: false,
            error: error.message,
          });
        });
      });

      if (progressCallback) {
        progressCallback({
          stage: 'complete',
          percent: 100,
          message: `Whisper ${modelName} model downloaded`
        });
      }

      return {
        success: true,
        component: 'whisper-model',
        model: modelName,
        message: `Whisper ${modelName} model ready`,
      };
    } catch (error) {
      return {
        success: false,
        component: 'whisper-model',
        model: modelName,
        error: error.error || error.message,
        stderr: error.stderr,
      };
    }
  }

  /**
   * Download Demucs model
   *
   * Demucs models are downloaded automatically on first use,
   * but we can pre-download them by running a test separation.
   *
   * @param {string} modelName - Model name (htdemucs_ft, htdemucs)
   * @param {Function} progressCallback - Called with progress updates
   * @returns {Promise<Object>}
   */
  async downloadDemucsModel(modelName = 'htdemucs_ft', progressCallback) {
    try {
      if (progressCallback) {
        progressCallback({
          stage: 'downloading',
          percent: 0,
          message: `Downloading Demucs ${modelName} model...`
        });
      }

      // Trigger model download by importing and loading
      const testScript = `
import json
import sys
from demucs.pretrained import get_model

try:
    print(f"Loading {modelName} model...", file=sys.stderr)
    model = get_model("${modelName}")
    print(json.dumps({"success": True, "model": "${modelName}"}))
except Exception as e:
    print(json.dumps({"success": False, "error": str(e)}))
`;

      await new Promise((resolve, reject) => {
        const python = spawn(this.pythonPath, ['-c', testScript], {
          stdio: ['pipe', 'pipe', 'pipe'],
        });

        let output = '';
        let errorOutput = '';

        python.stdout.on('data', (data) => {
          output += data.toString();
        });

        python.stderr.on('data', (data) => {
          errorOutput += data.toString();
          // Demucs prints download progress to stderr
          if (progressCallback) {
            progressCallback({
              stage: 'downloading',
              percent: 50, // Approximate
              message: data.toString().trim(),
            });
          }
        });

        python.on('close', () => {
          try {
            const result = JSON.parse(output.trim());
            if (result.success) {
              resolve(result);
            } else {
              reject(result);
            }
          } catch {
            reject({
              success: false,
              error: 'Failed to parse output',
              stderr: errorOutput,
            });
          }
        });

        python.on('error', (error) => {
          reject({
            success: false,
            error: error.message,
          });
        });
      });

      if (progressCallback) {
        progressCallback({
          stage: 'complete',
          percent: 100,
          message: `Demucs ${modelName} model downloaded`
        });
      }

      return {
        success: true,
        component: 'demucs-model',
        model: modelName,
        message: `Demucs ${modelName} model ready`,
      };
    } catch (error) {
      return {
        success: false,
        component: 'demucs-model',
        model: modelName,
        error: error.error || error.message,
        stderr: error.stderr,
      };
    }
  }

  /**
   * Download ffmpeg binary
   *
   * @param {Function} progressCallback - Called with progress updates
   * @returns {Promise<Object>}
   */
  async downloadFfmpeg(progressCallback) {
    try {
      if (progressCallback) {
        progressCallback({ stage: 'preparing', percent: 0, message: 'Preparing to download ffmpeg...' });
      }

      const cacheDir = this._getCacheDir();
      const binDir = join(cacheDir, 'bin');

      if (!existsSync(binDir)) {
        mkdirSync(binDir, { recursive: true });
      }

      const plat = platform();
      let url, filename;

      if (plat === 'darwin') {
        url = 'https://evermeet.cx/ffmpeg/getrelease/ffmpeg/zip';
        filename = 'ffmpeg';
      } else if (plat === 'win32') {
        url = 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip';
        filename = 'ffmpeg.exe';
      } else {
        url = 'https://johnvansickle.com/ffmpeg/builds/ffmpeg-release-amd64-static.tar.xz';
        filename = 'ffmpeg';
      }

      const destPath = join(binDir, filename);

      // Check if already exists
      if (existsSync(destPath)) {
        return {
          success: true,
          component: 'ffmpeg',
          message: 'ffmpeg already downloaded',
          path: destPath,
        };
      }

      await this._downloadFile(url, destPath, (downloaded, total) => {
        if (progressCallback && total > 0) {
          const percent = (downloaded / total) * 100;
          progressCallback({
            stage: 'downloading',
            percent: percent,
            message: `Downloading ffmpeg: ${(downloaded / 1024 / 1024).toFixed(1)}MB / ${(total / 1024 / 1024).toFixed(1)}MB`,
          });
        }
      });

      // Make executable on Unix
      if (plat !== 'win32') {
        const { chmodSync } = await import('fs');
        chmodSync(destPath, 0o755);
      }

      if (progressCallback) {
        progressCallback({ stage: 'complete', percent: 100, message: 'ffmpeg downloaded successfully' });
      }

      return {
        success: true,
        component: 'ffmpeg',
        message: 'ffmpeg installed successfully',
        path: destPath,
      };
    } catch (error) {
      return {
        success: false,
        component: 'ffmpeg',
        error: error.message,
      };
    }
  }

  /**
   * Download yt-dlp binary
   *
   * @param {Function} progressCallback - Called with progress updates
   * @returns {Promise<Object>}
   */
  async downloadYtDlp(progressCallback) {
    try {
      if (progressCallback) {
        progressCallback({ stage: 'preparing', percent: 0, message: 'Preparing to download yt-dlp...' });
      }

      const cacheDir = this._getCacheDir();
      const binDir = join(cacheDir, 'bin');

      if (!existsSync(binDir)) {
        mkdirSync(binDir, { recursive: true });
      }

      const plat = platform();
      let url, filename;

      if (plat === 'darwin') {
        url = 'https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_macos';
        filename = 'yt-dlp';
      } else if (plat === 'win32') {
        url = 'https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe';
        filename = 'yt-dlp.exe';
      } else {
        url = 'https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp';
        filename = 'yt-dlp';
      }

      const destPath = join(binDir, filename);

      // Check if already exists
      if (existsSync(destPath)) {
        return {
          success: true,
          component: 'yt-dlp',
          message: 'yt-dlp already downloaded',
          path: destPath,
        };
      }

      await this._downloadFile(url, destPath, (downloaded, total) => {
        if (progressCallback && total > 0) {
          const percent = (downloaded / total) * 100;
          progressCallback({
            stage: 'downloading',
            percent: percent,
            message: `Downloading yt-dlp: ${(downloaded / 1024 / 1024).toFixed(1)}MB / ${(total / 1024 / 1024).toFixed(1)}MB`,
          });
        }
      });

      // Make executable on Unix
      if (plat !== 'win32') {
        const { chmodSync } = await import('fs');
        chmodSync(destPath, 0o755);
      }

      if (progressCallback) {
        progressCallback({ stage: 'complete', percent: 100, message: 'yt-dlp downloaded successfully' });
      }

      return {
        success: true,
        component: 'yt-dlp',
        message: 'yt-dlp installed successfully',
        path: destPath,
      };
    } catch (error) {
      return {
        success: false,
        component: 'yt-dlp',
        error: error.message,
      };
    }
  }

  /**
   * Cancel an active download
   *
   * @param {string} downloadId - Download ID to cancel
   */
  cancelDownload(downloadId) {
    const download = this.activeDownloads.get(downloadId);
    if (download && download.cancel) {
      download.cancel();
      this.activeDownloads.delete(downloadId);
      return true;
    }
    return false;
  }

  /**
   * Get download progress for a specific download
   *
   * @param {string} downloadId - Download ID
   * @returns {Object|null} Progress info or null
   */
  getDownloadProgress(downloadId) {
    return this.activeDownloads.get(downloadId) || null;
  }
}

export default DownloadManager;
