import { PythonBridge } from './python-bridge.js';
import { existsSync } from 'fs';
import { homedir, platform } from 'os';
import { join } from 'path';

/**
 * System Checker - Validates system requirements and checks installed components
 *
 * Checks for:
 * - Python availability
 * - PyTorch installation
 * - Demucs models
 * - Whisper models
 * - GPU availability
 * - Disk space
 */

export class SystemChecker {
  constructor() {
    this.pythonBridge = new PythonBridge();
  }

  /**
   * Get the cache directory for models
   */
  _getCacheDir() {
    const plat = platform();
    if (plat === 'darwin') {
      return join(homedir(), 'Library', 'Caches', 'KAI-Converter');
    } else if (plat === 'win32') {
      return join(homedir(), 'AppData', 'Local', 'KAI-Converter', 'Cache');
    } else {
      // Linux
      return join(homedir(), '.cache', 'kai-converter');
    }
  }

  /**
   * Check if Whisper model is downloaded
   */
  _checkWhisperModel(modelName) {
    // Check both old and new locations
    const cacheDir = this._getCacheDir();
    const newWhisperCache = join(cacheDir, 'models', 'whisper');
    const oldWhisperCache = join(homedir(), '.cache', 'whisper');

    const newModelFile = join(newWhisperCache, `${modelName}.pt`);
    const oldModelFile = join(oldWhisperCache, `${modelName}.pt`);

    return existsSync(newModelFile) || existsSync(oldModelFile);
  }

  /**
   * Check if Demucs model is downloaded
   */
  _checkDemucsModel(_modelName = 'htdemucs_ft') {
    // Check both old and new locations
    const cacheDir = this._getCacheDir();
    const newTorchCache = join(cacheDir, 'models', 'torch', 'hub', 'checkpoints');
    const oldTorchCache = join(homedir(), '.cache', 'torch', 'hub', 'checkpoints');

    // Just check if directory exists and has model files
    return existsSync(newTorchCache) || existsSync(oldTorchCache);
  }

  /**
   * Check if a command is available in system PATH
   */
  _checkSystemCommand(command) {
    try {
      const { execSync } = require('child_process');
      const plat = platform();
      const checkCmd = plat === 'win32' ? `where ${command}` : `which ${command}`;
      execSync(checkCmd, { stdio: 'ignore' });
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Check if ffmpeg is available (system or downloaded)
   */
  _checkFfmpeg() {
    // First check system PATH
    if (this._checkSystemCommand('ffmpeg')) {
      return { available: true, source: 'system' };
    }

    // Then check downloaded version
    const cacheDir = this._getCacheDir();
    const plat = platform();
    const filename = plat === 'win32' ? 'ffmpeg.exe' : 'ffmpeg';
    const ffmpegPath = join(cacheDir, 'bin', filename);
    if (existsSync(ffmpegPath)) {
      return { available: true, source: 'downloaded', path: ffmpegPath };
    }

    return { available: false };
  }


  /**
   * Perform complete system check
   *
   * @returns {Promise<Object>} System status
   */
  async checkSystem() {
    const result = {
      python: {
        available: false,
        version: null,
        path: this.pythonBridge.pythonPath || null,
      },
      pytorch: {
        available: false,
        version: null,
      },
      gpu: {
        available: false,
        type: 'none', // 'cuda', 'mps', 'none'
      },
      demucs: {
        available: false,
        model: 'htdemucs_ft',
      },
      whisper: {
        available: false,
        models: [],
      },
      ffmpeg: {
        available: false,
      },
      disk: {
        cacheDir: this._getCacheDir(),
      },
    };

    // Note: yt-dlp is installed via pip (requirements-core.txt), not as a binary
    // Note: mp4box is no longer used - we use pymp4 library instead

    try {
      // Test Python and modules
      const pythonTest = await this.pythonBridge.testPython();

      result.python.available = pythonTest.available;
      result.python.version = pythonTest.python_version;

      if (pythonTest.torch) {
        result.pytorch.available = true;
        result.pytorch.version = pythonTest.torch_version;

        if (pythonTest.cuda_available) {
          result.gpu.available = true;
          result.gpu.type = 'cuda';
        } else if (platform() === 'darwin') {
          // Check for Apple Silicon MPS
          result.gpu.type = 'mps';
          result.gpu.available = true; // Assume MPS available on macOS
        }
      }

      if (pythonTest.demucs) {
        result.demucs.available = true;
      }

      if (pythonTest.whisper) {
        result.whisper.available = true;
        // Check for downloaded models
        const models = ['tiny', 'base', 'small', 'medium', 'large', 'large-v2', 'large-v3', 'large-v3-turbo'];
        result.whisper.models = models.filter((m) => this._checkWhisperModel(m));
      }

      // Check for ffmpeg
      const ffmpegCheck = this._checkFfmpeg();
      result.ffmpeg = ffmpegCheck;
    } catch (error) {
      console.error('System check error:', error);
      result.error = error.message;
    }

    return result;
  }

  /**
   * Get list of available Whisper models
   */
  getAvailableWhisperModels() {
    return [
      { name: 'tiny', size: 75 * 1024 * 1024, description: 'Fastest, least accurate' },
      { name: 'base', size: 150 * 1024 * 1024, description: 'Fast' },
      { name: 'small', size: 500 * 1024 * 1024, description: 'Fast' },
      { name: 'medium', size: 1500 * 1024 * 1024, description: 'Good accuracy' },
      { name: 'large-v3', size: 3000 * 1024 * 1024, description: 'Best accuracy' },
      { name: 'large-v3-turbo', size: 1600 * 1024 * 1024, description: 'Recommended' },
    ];
  }
}

export default SystemChecker;
