import https from 'https';
import http from 'http';
import { createWriteStream, existsSync, statSync, mkdirSync } from 'fs';
import { join, dirname } from 'path';
import { homedir, platform } from 'os';
import { spawn } from 'child_process';
import { fileURLToPath } from 'url';
import { app } from 'electron';
import { setupPython } from './setup-helper.js';

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
   * Always uses cache directory (same in dev and production)
   */
  _getPythonPath() {
    const platform = process.platform;

    // Helper to get Python executable path
    const getPythonExePath = (baseDir) => {
      if (platform === 'win32') {
        return join(baseDir, 'python.exe');
      } else {
        return join(baseDir, 'bin', 'python3');
      }
    };

    // Always use cache directory - same location in dev and production
    const pythonDir = join(this._getCacheDir(), 'python');
    const pythonPath = getPythonExePath(pythonDir);

    if (existsSync(pythonPath)) {
      console.log('[DownloadManager] Using Python:', pythonPath);
      return pythonPath;
    } else {
      console.error('[DownloadManager] ❌ Python not found in cache');
      throw new Error('Python not installed. Please run first-time setup.');
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
   * Get the Python source path (where kai_pack module is)
   */
  _getPythonSrcPath() {
    if (app.isPackaged) {
      // In production, src is bundled in resources
      return join(process.resourcesPath, 'python-src');
    } else {
      // In development, use local src
      return join(__dirname, '..', 'src');
    }
  }

  /**
   * Get environment variables for Python processes
   * Sets TORCH_HOME to consolidate model downloads to app's cache
   */
  _getPythonEnv() {
    const cacheDir = this._getCacheDir();
    const torchHome = join(cacheDir, 'models', 'torch');
    const whisperCache = join(cacheDir, 'models', 'whisper');

    return {
      ...process.env,
      TORCH_HOME: torchHome,
      HF_HOME: join(cacheDir, 'models', 'huggingface'), // For Hugging Face models if needed
      KAI_WHISPER_CACHE: whisperCache, // For Whisper models
    };
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
   * Upgrade pip
   *
   * @returns {Promise<void>}
   */
  async _upgradePip() {
    if (!this.pythonPath) {
      throw new Error('Python not initialized');
    }

    return new Promise((resolve, reject) => {
      const args = ['-m', 'pip', 'install', '--upgrade', 'pip'];

      const pip = spawn(this.pythonPath, args, {
        stdio: ['pipe', 'pipe', 'pipe'],
        env: this._getPythonEnv(),
      });

      let errorOutput = '';

      pip.stderr.on('data', (data) => {
        errorOutput += data.toString();
      });

      pip.on('close', (code) => {
        if (code === 0) {
          resolve();
        } else {
          console.error('[DownloadManager] pip upgrade failed with code', code);
          console.error('[DownloadManager] pip upgrade stderr:', errorOutput);
          reject(new Error(`pip upgrade failed with code ${code}: ${errorOutput}`));
        }
      });

      pip.on('error', (error) => {
        reject(error);
      });
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
      // Split packageSpec by spaces to handle multiple packages and flags
      const packageArgs = packageSpec.split(/\s+/);
      const args = ['-m', 'pip', 'install', ...packageArgs, '--no-cache-dir'];

      const pip = spawn(this.pythonPath, args, {
        stdio: ['pipe', 'pipe', 'pipe'],
        env: this._getPythonEnv(),
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
          console.error('[DownloadManager] pip install failed with code', code);
          console.error('[DownloadManager] pip stderr:', errorOutput);
          console.error('[DownloadManager] pip stdout:', output);
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
   * Download and install Python
   *
   * @param {Function} progressCallback - Called with progress updates
   * @returns {Promise<Object>}
   */
  async downloadPython(progressCallback) {
    try {
      const cacheDir = this._getCacheDir();
      const pythonDir = join(cacheDir, 'python');

      // Download and extract Python only (skip pip package installation)
      // We install PyTorch, Demucs, etc. separately through the UI
      await setupPython(pythonDir, null, progressCallback, true);

      return {
        success: true,
        component: 'python',
        message: 'Python installed successfully',
        path: pythonDir,
      };
    } catch (error) {
      return {
        success: false,
        component: 'python',
        error: error.message,
      };
    }
  }

  /**
   * Download and install PyTorch
   *
   * @param {string} variant - 'cpu', 'cuda', 'default', or 'auto'
   *   - 'auto': macOS gets default (MPS), Linux/Windows gets CPU-only
   *   - 'cpu': CPU-only (~200MB, no GPU)
   *   - 'cuda': CUDA 11.8 (~4GB, NVIDIA GPU)
   *   - 'default': Default PyPI wheel (MPS on macOS, CUDA on Linux/Windows)
   * @param {Function} progressCallback - Called with progress updates
   * @returns {Promise<Object>}
   */
  async downloadPyTorch(variant = 'auto', progressCallback) {
    try {
      const plat = platform();

      // Detect variant if auto
      if (variant === 'auto') {
        if (plat === 'darwin') {
          // macOS: Use default wheel which includes MPS support
          variant = 'default';
        } else {
          // Linux/Windows: Default to CPU for safety
          // Could check for NVIDIA GPU here, but safer to let user choose
          variant = 'cpu';
        }
      }

      // Upgrade pip first (in case Python was just installed)
      if (progressCallback) {
        progressCallback({ stage: 'preparing', percent: 0, message: 'Upgrading pip...' });
      }

      try {
        await this._upgradePip();
      } catch (error) {
        console.warn('Failed to upgrade pip (non-fatal):', error);
      }

      // PyTorch install command
      let packageSpec;

      if (variant === 'cuda') {
        // CUDA 11.8 version (most compatible)
        packageSpec = 'torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118';
      } else if (variant === 'default' || plat === 'darwin') {
        // macOS or explicit default: Use PyPI default (includes MPS on macOS)
        packageSpec = 'torch torchvision torchaudio';
      } else {
        // CPU-only version (much smaller, no GPU support)
        packageSpec = 'torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu';
      }

      if (progressCallback) {
        progressCallback({ stage: 'preparing', percent: 5, message: 'Preparing to download PyTorch...' });
      }

      await this._pipInstall(packageSpec, (update) => {
        if (progressCallback) {
          // Estimate progress based on stage
          let percent = 10;
          if (update.stage === 'downloading') percent = 30;
          else if (update.stage === 'installing') percent = 70;
          else if (update.stage === 'complete') percent = 90;

          progressCallback({
            stage: update.stage,
            percent: percent,
            message: update.message,
          });
        }
      });

      // Install PyTorch-dependent packages (torchcrepe for pitch detection)
      if (progressCallback) {
        progressCallback({ stage: 'installing', percent: 95, message: 'Installing torchcrepe (pitch detection)...' });
      }

      await this._pipInstall('torchcrepe>=0.0.12', (update) => {
        if (progressCallback && update.stage === 'complete') {
          progressCallback({ stage: 'complete', percent: 100, message: 'PyTorch and dependencies installed' });
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
        progressCallback({ stage: 'preparing', percent: 0, message: 'Upgrading pip...' });
      }

      // Upgrade pip first
      try {
        await this._upgradePip();
      } catch (error) {
        console.warn('Failed to upgrade pip (non-fatal):', error);
      }

      if (progressCallback) {
        progressCallback({ stage: 'preparing', percent: 5, message: 'Preparing to download Demucs...' });
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
        progressCallback({ stage: 'preparing', percent: 0, message: 'Upgrading pip...' });
      }

      // Upgrade pip first
      try {
        await this._upgradePip();
      } catch (error) {
        console.warn('Failed to upgrade pip (non-fatal):', error);
      }

      if (progressCallback) {
        progressCallback({ stage: 'preparing', percent: 5, message: 'Preparing to download Whisper...' });
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
   * Download and install core Python dependencies from requirements-core.txt
   * These are REQUIRED for the app to function (mutagen, scipy, librosa, etc.)
   * Does NOT include demucs or whisper (which depend on PyTorch and must be installed after)
   *
   * @param {Function} progressCallback - Called with progress updates
   * @returns {Promise<Object>}
   */
  async downloadCoreDeps(progressCallback) {
    try {
      if (progressCallback) {
        progressCallback({ stage: 'preparing', percent: 0, message: 'Upgrading pip...' });
      }

      // Upgrade pip first
      try {
        await this._upgradePip();
      } catch (error) {
        console.warn('Failed to upgrade pip (non-fatal):', error);
      }

      // Find requirements-core.txt (excludes PyTorch-dependent packages)
      const requirementsPath = app.isPackaged
        ? join(process.resourcesPath, 'requirements-core.txt')
        : join(__dirname, '..', 'requirements-core.txt');

      if (!existsSync(requirementsPath)) {
        throw new Error('requirements-core.txt not found');
      }

      if (progressCallback) {
        progressCallback({ stage: 'preparing', percent: 5, message: 'Installing core dependencies...' });
      }

      // Install from requirements.txt using -r flag
      await this._pipInstall(`-r ${requirementsPath}`, (update) => {
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
        component: 'core-deps',
        message: 'Core dependencies installed successfully',
      };
    } catch (error) {
      return {
        success: false,
        component: 'core-deps',
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
      const pythonSrcPath = this._getPythonSrcPath().replace(/\\/g, '\\\\');
      const testScript = `
import sys
import json
sys.path.insert(0, '${pythonSrcPath}')

# Use our helper to load Whisper with custom cache
try:
    from utils.whisper_utils import load_whisper_model
    use_helper = True
except ImportError:
    import whisper
    use_helper = False

try:
    print("Loading ${modelName} model...", file=sys.stderr)
    if use_helper:
        model = load_whisper_model("${modelName}")
    else:
        model = whisper.load_model("${modelName}")
    print(json.dumps({"success": True, "model": "${modelName}"}))
except Exception as e:
    print(json.dumps({"success": False, "error": str(e)}))
`;

      await new Promise((resolve, reject) => {
        const python = spawn(this.pythonPath, ['-c', testScript], {
          stdio: ['pipe', 'pipe', 'pipe'],
          env: this._getPythonEnv(),
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
import os

# Suppress extra output from Demucs during model loading
try:
    print("Loading ${modelName} model...", file=sys.stderr)

    # Redirect stdout to stderr temporarily to avoid contaminating JSON output
    old_stdout = sys.stdout
    sys.stdout = sys.stderr

    from demucs.pretrained import get_model
    model = get_model("${modelName}")

    # Restore stdout and print JSON result
    sys.stdout = old_stdout
    print(json.dumps({"success": True, "model": "${modelName}"}))

except Exception as e:
    # Make sure stdout is restored
    sys.stdout = old_stdout if 'old_stdout' in locals() else sys.stdout
    print(json.dumps({"success": False, "error": str(e)}))
`;

      await new Promise((resolve, reject) => {
        const python = spawn(this.pythonPath, ['-c', testScript], {
          stdio: ['pipe', 'pipe', 'pipe'],
          env: this._getPythonEnv(),
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
          } catch (parseError) {
            console.error('[DownloadManager] Failed to parse Demucs model output');
            console.error('[DownloadManager] stdout:', output);
            console.error('[DownloadManager] stderr:', errorOutput);
            reject({
              success: false,
              error: 'Failed to parse output',
              stderr: errorOutput,
              stdout: output,
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
      const finalBinaryName = plat === 'win32' ? 'ffmpeg.exe' : 'ffmpeg';
      const finalBinaryPath = join(binDir, finalBinaryName);

      // Check if already exists
      if (existsSync(finalBinaryPath)) {
        return {
          success: true,
          component: 'ffmpeg',
          message: 'ffmpeg already downloaded',
          path: finalBinaryPath,
        };
      }

      let url, archiveFilename;

      if (plat === 'darwin') {
        url = 'https://evermeet.cx/ffmpeg/getrelease/ffmpeg/zip';
        archiveFilename = 'ffmpeg.zip';
      } else if (plat === 'win32') {
        url = 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip';
        archiveFilename = 'ffmpeg.zip';
      } else {
        url = 'https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz';
        archiveFilename = 'ffmpeg.tar.xz';
      }

      const archivePath = join(binDir, archiveFilename);

      // Download archive
      await this._downloadFile(url, archivePath, (downloaded, total) => {
        if (progressCallback && total > 0) {
          const percent = (downloaded / total) * 60; // 0-60%
          progressCallback({
            stage: 'downloading',
            percent: percent,
            message: `Downloading ffmpeg: ${(downloaded / 1024 / 1024).toFixed(1)}MB / ${(total / 1024 / 1024).toFixed(1)}MB`,
          });
        }
      });

      // Extract archive
      if (progressCallback) {
        progressCallback({ stage: 'extracting', percent: 70, message: 'Extracting ffmpeg...' });
      }

      await this._extractFfmpegArchive(archivePath, finalBinaryPath, plat);

      // Clean up archive
      const { rmSync } = await import('fs');
      rmSync(archivePath, { force: true });

      // Make executable on Unix
      if (plat !== 'win32') {
        const { chmodSync } = await import('fs');
        chmodSync(finalBinaryPath, 0o755);
      }

      if (progressCallback) {
        progressCallback({ stage: 'complete', percent: 100, message: 'ffmpeg downloaded successfully' });
      }

      return {
        success: true,
        component: 'ffmpeg',
        message: 'ffmpeg installed successfully',
        path: finalBinaryPath,
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
   * Extract ffmpeg from archive
   */
  async _extractFfmpegArchive(archivePath, destPath, plat) {
    const { promisify } = await import('util');
    const { exec } = await import('child_process');
    const execAsync = promisify(exec);
    const { mkdtempSync, rmSync, copyFileSync, readdirSync, statSync } = await import('fs');
    const { tmpdir } = await import('os');

    const tempExtractDir = mkdtempSync(join(tmpdir(), 'ffmpeg-extract-'));

    try {
      if (plat === 'win32' || plat === 'darwin') {
        // Extract ZIP
        await execAsync(`unzip -q "${archivePath}" -d "${tempExtractDir}"`);
      } else {
        // Extract tar.xz
        await execAsync(`tar -xf "${archivePath}" -C "${tempExtractDir}"`);
      }

      // Find ffmpeg binary
      const findFile = (dir, filename) => {
        const files = readdirSync(dir);
        for (const file of files) {
          const fullPath = join(dir, file);
          try {
            if (statSync(fullPath).isDirectory()) {
              const found = findFile(fullPath, filename);
              if (found) return found;
            } else if (file.toLowerCase() === filename.toLowerCase()) {
              return fullPath;
            }
          } catch (e) {
            continue;
          }
        }
        return null;
      };

      const binaryName = plat === 'win32' ? 'ffmpeg.exe' : 'ffmpeg';
      const ffmpegPath = findFile(tempExtractDir, binaryName);

      if (ffmpegPath) {
        copyFileSync(ffmpegPath, destPath);
      } else {
        throw new Error(`ffmpeg binary not found in archive`);
      }

      // Clean up
      rmSync(tempExtractDir, { recursive: true, force: true });
    } catch (error) {
      rmSync(tempExtractDir, { recursive: true, force: true });
      throw error;
    }
  }


  /**
   * Download mp4box binary (GPAC)
   *
   * Downloads and extracts MP4Box from official GPAC nightly builds.
   * Note: Linux extracts binary but not all shared libraries - system libs are used.
   *
   * @param {Function} progressCallback - Called with progress updates
   * @returns {Promise<Object>}
   */
  async downloadMp4box(progressCallback) {
    const plat = platform();

    // All platforms: Download and extract from GPAC nightly builds
    try {
      if (progressCallback) {
        progressCallback({ stage: 'preparing', percent: 0, message: 'Preparing to download mp4box...' });
      }

      const cacheDir = this._getCacheDir();
      const binDir = join(cacheDir, 'bin');

      if (!existsSync(binDir)) {
        mkdirSync(binDir, { recursive: true });
      }

      const finalBinaryName = plat === 'win32' ? 'mp4box.exe' : 'mp4box';
      const finalBinaryPath = join(binDir, finalBinaryName);

      // Check if already exists
      if (existsSync(finalBinaryPath)) {
        return {
          success: true,
          component: 'mp4box',
          message: 'mp4box already downloaded',
          path: finalBinaryPath,
        };
      }

      let url, installerFilename;

      if (plat === 'darwin') {
        // macOS: Download GPAC .pkg (includes lib directory with dependencies)
        url = 'https://download.tsi.telecom-paristech.fr/gpac/new_builds/gpac_latest_head_macos.pkg';
        installerFilename = 'gpac_installer.pkg';
      } else if (plat === 'win32') {
        // Windows: Download GPAC .exe installer (includes DLLs)
        url = 'https://download.tsi.telecom-paristech.fr/gpac/new_builds/gpac_latest_head_win64.exe';
        installerFilename = 'gpac_installer.exe';
      } else {
        // Linux: Download GPAC .deb (binary only, uses system libs)
        url = 'https://download.tsi.telecom-paristech.fr/gpac/new_builds/gpac_latest_head_linux64.deb';
        installerFilename = 'gpac_installer.deb';
      }

      const installerPath = join(binDir, installerFilename);

      // Download installer
      if (progressCallback) {
        progressCallback({ stage: 'downloading', percent: 10, message: 'Downloading GPAC installer...' });
      }

      await this._downloadFile(url, installerPath, (downloaded, total) => {
        if (progressCallback && total > 0) {
          const percent = 10 + ((downloaded / total) * 50); // 10-60%
          progressCallback({
            stage: 'downloading',
            percent: percent,
            message: `Downloading GPAC: ${(downloaded / 1024 / 1024).toFixed(1)}MB / ${(total / 1024 / 1024).toFixed(1)}MB`,
          });
        }
      });

      // Extract mp4box binary from installer
      if (progressCallback) {
        progressCallback({ stage: 'extracting', percent: 65, message: 'Extracting mp4box binary...' });
      }

      const { mkdtempSync, rmSync } = await import('fs');
      const { tmpdir } = await import('os');
      const tempExtractDir = mkdtempSync(join(tmpdir(), 'gpac-extract-'));

      try {
        // Extract based on platform (Linux already handled above)
        if (plat === 'darwin') {
          // macOS: Extract .pkg package (includes lib directory)
          await this._extractPkgPackage(installerPath, tempExtractDir, finalBinaryPath);
        } else if (plat === 'win32') {
          // Windows: Extract .exe installer (includes DLLs)
          await this._extractWindowsInstaller(installerPath, tempExtractDir, finalBinaryPath);
        }

        // Make executable on macOS
        if (plat === 'darwin') {
          const { chmodSync } = await import('fs');
          chmodSync(finalBinaryPath, 0o755);
        }

        // Clean up
        rmSync(tempExtractDir, { recursive: true, force: true });
        rmSync(installerPath, { force: true });

      } catch (extractError) {
        // Clean up on error
        rmSync(tempExtractDir, { recursive: true, force: true });
        rmSync(installerPath, { force: true });
        throw extractError;
      }

      if (progressCallback) {
        progressCallback({ stage: 'complete', percent: 100, message: 'mp4box installed successfully' });
      }

      return {
        success: true,
        component: 'mp4box',
        message: 'mp4box installed successfully',
        path: finalBinaryPath,
      };
    } catch (error) {
      return {
        success: false,
        component: 'mp4box',
        error: error.message,
      };
    }
  }

  /**
   * Extract mp4box from Debian package
   * Also extracts shared libraries (libgpac.so*) needed by mp4box
   */
  async _extractDebPackage(debPath, tempDir, destPath) {
    console.log('[DownloadManager] Extracting .deb package:', debPath);
    console.log('[DownloadManager] Extraction directory:', tempDir);

    const { promisify } = await import('util');
    const { exec } = await import('child_process');
    const execAsync = promisify(exec);

    // Extract .deb using dpkg-deb or ar
    try {
      // Try dpkg-deb first
      console.log('[DownloadManager] Trying dpkg-deb extraction...');
      await execAsync(`dpkg-deb -x "${debPath}" "${tempDir}"`);
      console.log('[DownloadManager] ✓ dpkg-deb extraction succeeded');
    } catch (error) {
      // Fallback to ar (more portable)
      console.log('[DownloadManager] dpkg-deb failed, trying ar extraction...');
      await execAsync(`ar x "${debPath}" --output="${tempDir}"`);
      // Extract data.tar.*
      const { readdirSync } = await import('fs');
      const files = readdirSync(tempDir);
      const dataTar = files.find(f => f.startsWith('data.tar'));
      if (dataTar) {
        console.log(`[DownloadManager] Found data archive: ${dataTar}, extracting...`);
        await execAsync(`tar -xf "${join(tempDir, dataTar)}" -C "${tempDir}"`);
        console.log('[DownloadManager] ✓ ar extraction succeeded');
      }
    }

    // Find mp4box binary (usually in usr/bin/) - try both lowercase and capitalized
    const { copyFileSync, readdirSync, statSync } = await import('fs');

    console.log('[DownloadManager] Searching for mp4box binary...');

    // First try common paths with both naming conventions
    const possiblePaths = [
      join(tempDir, 'usr', 'bin', 'mp4box'),
      join(tempDir, 'usr', 'bin', 'MP4Box'),
      join(tempDir, 'usr', 'local', 'bin', 'mp4box'),
      join(tempDir, 'usr', 'local', 'bin', 'MP4Box'),
      join(tempDir, 'bin', 'mp4box'),
      join(tempDir, 'bin', 'MP4Box'),
    ];

    let mp4boxPath = null;
    for (const path of possiblePaths) {
      if (existsSync(path)) {
        console.log(`[DownloadManager] Found mp4box at: ${path}`);
        mp4boxPath = path;
        break;
      }
    }

    // If not found in common paths, recursively search entire extracted directory
    if (!mp4boxPath) {
      console.log('[DownloadManager] Not found in common paths, searching recursively...');
      const findFile = (dir, filenames) => {
        try {
          const files = readdirSync(dir);
          for (const file of files) {
            const fullPath = join(dir, file);
            try {
              if (statSync(fullPath).isDirectory()) {
                const found = findFile(fullPath, filenames);
                if (found) return found;
              } else if (filenames.includes(file)) {
                return fullPath;
              }
            } catch (e) {
              continue;
            }
          }
        } catch (e) {
          return null;
        }
        return null;
      };

      mp4boxPath = findFile(tempDir, ['mp4box', 'MP4Box']);
      if (mp4boxPath) {
        console.log(`[DownloadManager] Found mp4box via recursive search: ${mp4boxPath}`);
      }
    }

    if (!mp4boxPath) {
      console.error('[DownloadManager] ❌ mp4box binary not found in .deb package');
      throw new Error('mp4box binary not found in .deb package');
    }

    // Copy mp4box binary
    console.log(`[DownloadManager] Copying mp4box to: ${destPath}`);
    copyFileSync(mp4boxPath, destPath);
    console.log('[DownloadManager] ✓ mp4box binary copied');

    // Find and copy shared libraries (libgpac.so*)
    const cacheDir = this._getCacheDir();
    const libDir = join(cacheDir, 'lib');
    if (!existsSync(libDir)) {
      mkdirSync(libDir, { recursive: true });
    }

    // Search for all shared libraries in extracted package
    // MP4Box/GPAC depends on: libgpac, libjpeg, libpng, libz, libssl, libcrypto, etc.
    const libPaths = [
      join(tempDir, 'usr', 'lib', 'x86_64-linux-gnu'),
      join(tempDir, 'usr', 'lib64'),
      join(tempDir, 'usr', 'lib'),
      join(tempDir, 'usr', 'local', 'lib', 'x86_64-linux-gnu'),
      join(tempDir, 'usr', 'local', 'lib64'),
      join(tempDir, 'usr', 'local', 'lib'),
      join(tempDir, 'lib', 'x86_64-linux-gnu'),
      join(tempDir, 'lib64'),
      join(tempDir, 'lib'),
    ];

    let copiedLibs = 0;
    for (const libPath of libPaths) {
      if (existsSync(libPath)) {
        try {
          const files = readdirSync(libPath);
          for (const file of files) {
            // Copy all .so* files (shared libraries)
            // This includes libgpac, libjpeg, libpng, libz, etc.
            if (file.endsWith('.so') || file.includes('.so.')) {
              const srcPath = join(libPath, file);
              const destLibPath = join(libDir, file);
              try {
                copyFileSync(srcPath, destLibPath);
                console.log(`[DownloadManager] Copied shared library: ${file}`);
                copiedLibs++;
              } catch (copyError) {
                // Skip if we can't copy (might be a symlink or permission issue)
                continue;
              }
            }
          }
        } catch (e) {
          // Ignore errors reading directories
          continue;
        }
      }
    }

    if (copiedLibs === 0) {
      console.warn('[DownloadManager] Warning: No shared libraries found in .deb package');
    } else {
      console.log(`[DownloadManager] Copied ${copiedLibs} shared libraries from .deb package`);
    }
  }

  /**
   * Extract mp4box from macOS .pkg
   */
  async _extractPkgPackage(pkgPath, tempDir, destPath) {
    const { promisify } = await import('util');
    const { exec } = await import('child_process');
    const execAsync = promisify(exec);

    // Extract .pkg using pkgutil
    await execAsync(`pkgutil --expand-full "${pkgPath}" "${tempDir}"`);

    // Find mp4box in extracted contents (usually in Payload)
    const { copyFileSync } = await import('fs');
    const { readdirSync, statSync } = await import('fs');

    // Recursively search for mp4box
    const findFile = (dir, filename) => {
      const files = readdirSync(dir);
      for (const file of files) {
        const fullPath = join(dir, file);
        if (statSync(fullPath).isDirectory()) {
          const found = findFile(fullPath, filename);
          if (found) return found;
        } else if (file === filename) {
          return fullPath;
        }
      }
      return null;
    };

    const mp4boxPath = findFile(tempDir, 'MP4Box') || findFile(tempDir, 'mp4box');
    if (mp4boxPath) {
      copyFileSync(mp4boxPath, destPath);
      return;
    }

    throw new Error('mp4box binary not found in .pkg package');
  }

  /**
   * Extract mp4box from Windows installer
   */
  async _extractWindowsInstaller(exePath, tempDir, destPath) {
    const { promisify } = await import('util');
    const { exec } = await import('child_process');
    const execAsync = promisify(exec);

    // Try to extract with 7zip if available
    try {
      await execAsync(`7z x "${exePath}" -o"${tempDir}" -y`);
    } catch {
      // If 7zip not available, try running installer in silent mode
      // GPAC installer supports /S for silent install
      const installDir = join(tempDir, 'gpac');
      try {
        await execAsync(`"${exePath}" /S /D="${installDir}"`);
      } catch {
        throw new Error('Failed to extract Windows installer. Please install 7-Zip or run the installer manually.');
      }
    }

    // Find mp4box.exe in extracted contents
    const { copyFileSync, readdirSync, statSync } = await import('fs');

    const findFile = (dir, filename) => {
      const files = readdirSync(dir);
      for (const file of files) {
        const fullPath = join(dir, file);
        try {
          if (statSync(fullPath).isDirectory()) {
            const found = findFile(fullPath, filename);
            if (found) return found;
          } else if (file.toLowerCase() === filename.toLowerCase()) {
            return fullPath;
          }
        } catch (e) {
          // Skip files we can't access
          continue;
        }
      }
      return null;
    };

    const mp4boxPath = findFile(tempDir, 'MP4Box.exe');
    if (mp4boxPath) {
      copyFileSync(mp4boxPath, destPath);
      return;
    }

    throw new Error('mp4box.exe not found in installer');
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
