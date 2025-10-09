import { spawn } from 'child_process';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { existsSync } from 'fs';
import { app } from 'electron';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

/**
 * Python Bridge - Communicates with KAI Python backend
 *
 * Spawns Python processes to call the KaiAPI we created in Phase 1.
 * Parses progress updates and returns structured results.
 */

export class PythonBridge {
  constructor(logCallback = null) {
    try {
      this.pythonPath = this._getPythonPath();
    } catch (error) {
      console.error('[PythonBridge] Failed to initialize:', error.message);
      this.pythonPath = null;
      this.initError = error.message;
    }
    this.activeProcesses = new Set();
    this.logCallback = logCallback;
  }

  _sendLog(level, message) {
    if (this.logCallback) {
      this.logCallback(level, message);
    }
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
      console.log('[PythonBridge] Using bundled Python:', bundledPython);
      return bundledPython;
    } else {
      // Development: use local standalone Python (same as production!)
      const standalonePython = getStandalonePath(join(__dirname, '..', 'python-standalone'));
      if (existsSync(standalonePython)) {
        console.log('[PythonBridge] Using standalone Python:', standalonePython);
        return standalonePython;
      } else {
        console.error('[PythonBridge] ❌ Standalone Python not found!');
        console.error('[PythonBridge] Run: npm run setup:python');
        throw new Error('Python not found. Please run: npm run setup:python');
      }
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
   * Get the bundled binaries path (ffmpeg, yt-dlp)
   */
  _getBinPath() {
    if (app.isPackaged) {
      // In production, binaries are bundled in resources
      return join(process.resourcesPath, 'bin');
    } else {
      // In development, use local resources/bin
      return join(__dirname, '..', 'resources', 'bin');
    }
  }

  /**
   * Get environment with bundled binaries in PATH
   */
  _getEnvWithBinPath() {
    const binPath = this._getBinPath();
    const env = { ...process.env };

    // Add bundled bin directory to PATH (at the front so it takes priority)
    if (existsSync(binPath)) {
      const pathSeparator = process.platform === 'win32' ? ';' : ':';
      env.PATH = `${binPath}${pathSeparator}${env.PATH || ''}`;
    }

    return env;
  }

  /**
   * Process an audio file to KAI format
   *
   * @param {Object} options - Processing options
   * @param {string} options.inputFile - Path to input audio file (or null if youtubeUrl is provided)
   * @param {string} options.youtubeUrl - YouTube URL (or null if inputFile is provided)
   * @param {string} options.title - Song title (required for YouTube mode)
   * @param {string} options.artist - Artist name (required for YouTube mode)
   * @param {string} options.outputFile - Path to output .kai file (optional)
   * @param {string} options.whisperModel - Whisper model size
   * @param {string} options.language - Language code
   * @param {boolean} options.fourStems - Use 4-stem separation
   * @param {Object} options.llm - LLM settings for lyric correction
   * @param {boolean} options.llm.enabled - Enable LLM lyric correction
   * @param {string} options.llm.provider - LLM provider (claude/openai/local)
   * @param {string} options.llm.model - LLM model name
   * @param {string} options.llm.apiKey - API key for LLM provider
   * @param {string} options.llm.baseUrl - Base URL for local LLM
   * @param {Function} progressCallback - Called with progress updates
   * @returns {Promise<Object>} Processing result
   */
  async processAudio(options, progressCallback) {
    return new Promise((resolve, reject) => {
      // Build args JSON to pass safely
      const argsJson = JSON.stringify({
        inputFile: options.inputFile || null,
        youtubeUrl: options.youtubeUrl || null,
        title: options.title || null,
        artist: options.artist || null,
        outputFile: options.outputFile || null,
        whisperModel: options.whisperModel || 'small',
        language: options.language || 'en',
        fourStems: options.fourStems || false,
        features: options.features || null,
        referenceLyrics: options.referenceLyrics || null,
        llmEnabled: options.llm?.enabled || false,
        llmProvider: options.llm?.provider || null,
        llmModel: options.llm?.model || null,
        llmApiKey: options.llm?.apiKey || null,
        llmBaseUrl: options.llm?.baseUrl || null
      });

      const pythonSrcPath = this._getPythonSrcPath().replace(/\\/g, '\\\\');

      const args = [
        '-c',
        `
import sys
import json
import os
import tempfile
import subprocess
import logging

# Configure logging to stderr
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stderr,
    force=True
)
logger = logging.getLogger(__name__)

sys.path.insert(0, '${pythonSrcPath}')

from kai_pack.api import KaiAPI

logger.info("Starting KAI processing...")

def progress_callback(stage, percent, message):
    print(f"PROGRESS:{json.dumps({'stage': stage, 'percent': percent, 'message': message})}", flush=True)

# Parse arguments from command line
args = json.loads(sys.argv[1])

# Handle YouTube download if youtubeUrl is provided
input_file = args['inputFile']
temp_mp3 = None

if args['youtubeUrl']:
    import shutil

    # Check for yt-dlp
    ytdlp_path = shutil.which('yt-dlp')
    if not ytdlp_path:
        result = {
            'success': False,
            'error': 'yt-dlp is not available. Please ensure it is installed.',
            'error_type': 'MissingDependency'
        }
        print(f"RESULT:{json.dumps(result)}", flush=True)
        sys.exit(1)

    # Create temp file for downloaded MP3
    temp_dir = tempfile.mkdtemp(prefix='kai_youtube_')
    temp_mp3 = os.path.join(temp_dir, f"{args['artist']} - {args['title']}.mp3")

    try:
        # Download and extract audio
        progress_callback('youtube_download', 10, 'Downloading from YouTube...')
        subprocess.run([
            ytdlp_path,
            '--extract-audio',
            '--audio-format', 'mp3',
            '--audio-quality', '0',
            '--output', temp_mp3,
            '--no-playlist',
            args['youtubeUrl']
        ], check=True, capture_output=True)

        # Write ID3 tags
        try:
            from mutagen.id3 import ID3, TIT2, TPE1
            tags = ID3()
            tags.add(TIT2(encoding=3, text=args['title']))
            tags.add(TPE1(encoding=3, text=args['artist']))
            tags.save(temp_mp3)
        except:
            pass  # Continue without tags if mutagen unavailable

        input_file = temp_mp3
        progress_callback('youtube_download', 100, 'YouTube download complete')

    except subprocess.CalledProcessError as e:
        result = {
            'success': False,
            'error': f'Failed to download from YouTube: {e.stderr.decode() if e.stderr else str(e)}',
            'error_type': 'DownloadError'
        }
        print(f"RESULT:{json.dumps(result)}", flush=True)
        sys.exit(1)
    except Exception as e:
        result = {
            'success': False,
            'error': f'YouTube download error: {str(e)}',
            'error_type': 'DownloadError'
        }
        print(f"RESULT:{json.dumps(result)}", flush=True)
        sys.exit(1)

try:
    api = KaiAPI(progress_callback=progress_callback)
    result = api.process_audio(
        input_file=input_file,
        output_file=args['outputFile'],
        whisper_model=args['whisperModel'],
        language=args['language'],
        four_stems=args['fourStems'],
        features=args['features'],
        reference_lyrics=args['referenceLyrics'],
        llm_enabled=args['llmEnabled'],
        llm_provider=args['llmProvider'],
        llm_model=args['llmModel'],
        llm_api_key=args['llmApiKey'],
        llm_base_url=args['llmBaseUrl']
    )

    print(f"RESULT:{json.dumps(result)}", flush=True)
finally:
    # Clean up temp file
    if temp_mp3 and os.path.exists(temp_mp3):
        try:
            os.unlink(temp_mp3)
            os.rmdir(os.path.dirname(temp_mp3))
        except:
            pass
`,
        argsJson
      ];

      const python = spawn(this.pythonPath, args, {
        cwd: join(__dirname, '..'),
        stdio: ['pipe', 'pipe', 'pipe'],
        env: {
          ...this._getEnvWithBinPath(),
          PYTHONUNBUFFERED: '1',  // Disable Python output buffering
          FORCE_COLOR: '1'  // May help tqdm output
        }
      });

      // Track active process
      this.activeProcesses.add(python);

      let outputBuffer = '';
      let errorBuffer = '';
      let lastDemucsPercent = 0;
      let stemCounter = 0;
      const totalStems = 4; // Demucs always separates 4 stems internally

      python.stdout.on('data', (data) => {
        const text = data.toString();
        outputBuffer += text;

        // Parse progress updates
        const lines = text.split('\n');
        for (const line of lines) {
          if (line.startsWith('PROGRESS:')) {
            try {
              const progress = JSON.parse(line.substring(9));
              if (progressCallback) {
                progressCallback(progress);
              }
            } catch (e) {
              console.error('Failed to parse progress:', e);
            }
          } else if (line.startsWith('RESULT:')) {
            try {
              const result = JSON.parse(line.substring(7));
              resolve(result);
            } catch (e) {
              console.error('Failed to parse result:', e);
            }
          } else if (line.trim()) {
            // Send other output as logs
            this._sendLog('info', line.trim());
          }
        }
      });

      python.stderr.on('data', (data) => {
        const text = data.toString();
        errorBuffer += text;

        // Process each line separately
        const lines = text.split('\n');
        for (const line of lines) {
          if (!line.trim()) continue;

          // Parse tqdm progress bars (Demucs)
          // Format 1: Per-stem progress like "vocals: 45%|████▌     | 45/100"
          const stemMatch = line.match(/(vocals|drums|bass|other):\s*(\d+)%/i);
          if (stemMatch && progressCallback) {
            const stemName = stemMatch[1].charAt(0).toUpperCase() + stemMatch[1].slice(1);
            const percent = parseInt(stemMatch[2]);
            progressCallback({
              stage: 'demucs',
              percent: percent,
              message: `Separating ${stemName} stem...`,
              subProgress: percent / 100
            });
            continue;
          }

          // Format 2: Overall Demucs progress like "  59%|██████|  93.6/157.95 [00:17<00:11, 5.66s/s]"
          const overallMatch = line.match(/^\s*(\d+)%\|[█▏▎▍▌▋▊▉ ]+\|\s*[\d.]+\/[\d.]+/);
          if (overallMatch && progressCallback) {
            const percent = parseInt(overallMatch[1]);

            // Detect if progress reset (new stem started) - need significant drop
            if (percent < lastDemucsPercent - 20 && lastDemucsPercent > 20) {
              stemCounter++;
            }
            lastDemucsPercent = percent;

            // Cap stem counter to not exceed total
            const currentStem = Math.min(stemCounter + 1, totalStems);

            // If we're seeing multiple passes, show stem counter
            const message = stemCounter > 0 && stemCounter < totalStems
              ? `Separating stems (${currentStem} of ${totalStems})...`
              : `Separating stems...`;

            progressCallback({
              stage: 'demucs',
              percent: percent,
              message: message,
              subProgress: percent / 100
            });
            continue;
          }

          // Not a progress bar - send as log
          // Determine log level based on content
          let level = 'info';
          const lowerLine = line.toLowerCase();
          if (lowerLine.includes('error') || lowerLine.includes('failed')) {
            level = 'error';
          } else if (lowerLine.includes('warning') || lowerLine.includes('warn')) {
            level = 'warning';
          } else if (lowerLine.includes('debug')) {
            level = 'debug';
          }

          this._sendLog(level, line.trim());
        }
      });

      python.on('close', (code) => {
        this.activeProcesses.delete(python);
        if (code !== 0) {
          reject({
            success: false,
            error: `Python process exited with code ${code}`,
            error_type: 'ProcessError',
            stderr: errorBuffer,
          });
        }
      });

      python.on('error', (error) => {
        this.activeProcesses.delete(python);
        reject({
          success: false,
          error: `Failed to spawn Python: ${error.message}`,
          error_type: 'SpawnError',
        });
      });
    });
  }

  /**
   * Read audio file metadata (ID3 tags)
   *
   * @param {string} filePath - Path to audio file
   * @returns {Promise<Object>} Metadata result
   */
  async readAudioMetadata(filePath) {
    return new Promise((resolve) => {
      const args = [
        '-c',
        `
import sys
import json
from pathlib import Path
sys.path.insert(0, '${join(__dirname, '..', 'src').replace(/\\/g, '\\\\')}')

from kai_pack.metadata import MetadataExtractor

try:
    extractor = MetadataExtractor()
    file_path = sys.argv[1]
    metadata = extractor.extract_metadata(Path(file_path))
    song_meta = metadata.get('song', {})
    result = {
        'success': True,
        'title': song_meta.get('title'),
        'artist': song_meta.get('artist'),
        'album': song_meta.get('album')
    }
    print(json.dumps(result))
except Exception as e:
    result = {'success': False, 'error': str(e), 'title': None, 'artist': None}
    print(json.dumps(result))
`,
        filePath
      ];

      const python = spawn(this.pythonPath, args, {
        cwd: join(__dirname, '..'),
        stdio: ['pipe', 'pipe', 'pipe'],
        env: this._getEnvWithBinPath(),
      });

      let output = '';
      let errorOutput = '';

      python.stdout.on('data', (data) => {
        output += data.toString();
      });

      python.stderr.on('data', (data) => {
        errorOutput += data.toString();
      });

      python.on('close', (code) => {
        if (errorOutput) {
          console.error('Metadata read stderr:', errorOutput);
        }

        if (code === 0 && output.trim()) {
          try {
            const result = JSON.parse(output.trim());
            if (!result.success) {
              console.error('Metadata extraction failed:', result.error);
            }
            resolve(result);
          } catch (e) {
            console.error('Failed to parse metadata output:', output);
            resolve({
              success: false,
              error: 'Failed to parse response',
              title: null,
              artist: null,
            });
          }
        } else {
          console.error(`Metadata read failed: code=${code}, output="${output}"`);
          resolve({
            success: false,
            error: 'Failed to read metadata',
            title: null,
            artist: null,
          });
        }
      });

      python.on('error', (error) => {
        console.error('Python spawn error:', error);
        resolve({
          success: false,
          error: 'Python not found',
          title: null,
          artist: null,
        });
      });
    });
  }

  /**
   * Fetch lyrics from LRCLIB
   *
   * @param {string} title - Song title
   * @param {string} artist - Artist name
   * @returns {Promise<Object>} Lyrics result
   */
  async fetchLyrics(title, artist) {
    return new Promise((resolve) => {
      const argsJson = JSON.stringify({ title, artist });

      const args = [
        '-c',
        `
import sys
import json
sys.path.insert(0, '${join(__dirname, '..', 'src').replace(/\\/g, '\\\\')}')

from utils.lyrics_utils import fetch_lyrics_from_lrclib

try:
    args = json.loads(sys.argv[1])
    lyrics = fetch_lyrics_from_lrclib(args['title'], args['artist'])
    if lyrics:
        result = {'success': True, 'lyrics': lyrics}
    else:
        result = {'success': False, 'error': 'No lyrics found'}
    print(json.dumps(result))
except Exception as e:
    result = {'success': False, 'error': str(e)}
    print(json.dumps(result))
`,
        argsJson
      ];

      const python = spawn(this.pythonPath, args, {
        cwd: join(__dirname, '..'),
        stdio: ['pipe', 'pipe', 'pipe'],
        env: this._getEnvWithBinPath(),
      });

      let output = '';

      python.stdout.on('data', (data) => {
        output += data.toString();
      });

      python.on('close', (code) => {
        if (code === 0 && output.trim()) {
          try {
            resolve(JSON.parse(output.trim()));
          } catch (e) {
            resolve({
              success: false,
              error: 'Failed to parse response',
            });
          }
        } else {
          resolve({
            success: false,
            error: 'Failed to fetch lyrics',
          });
        }
      });

      python.on('error', () => {
        resolve({
          success: false,
          error: 'Python not found',
        });
      });
    });
  }

  /**
   * Test if Python and required modules are available
   *
   * @returns {Promise<Object>} Test results
   */
  async testPython() {
    // Check if Python path was initialized
    if (!this.pythonPath) {
      return {
        available: false,
        error: this.initError || 'Python not initialized',
      };
    }

    return new Promise((resolve) => {
      // Set a timeout to prevent hanging
      const timeout = setTimeout(() => {
        resolve({
          available: false,
          error: 'Python check timed out',
        });
      }, 5000); // 5 second timeout

      const args = [
        '-c',
        `
import sys
import json

result = {
    'python_version': '.'.join(map(str, sys.version_info[:3])),
    'available': True
}

try:
    import torch
    result['torch'] = True
    result['torch_version'] = torch.__version__
    result['cuda_available'] = torch.cuda.is_available()
except:
    result['torch'] = False

try:
    import demucs
    result['demucs'] = True
except:
    result['demucs'] = False

try:
    import whisper
    result['whisper'] = True
except:
    result['whisper'] = False

print(json.dumps(result))
`
      ];

      const python = spawn(this.pythonPath, args, {
        cwd: join(__dirname, '..'),
        stdio: ['pipe', 'pipe', 'pipe'],
        env: this._getEnvWithBinPath(),
      });

      let output = '';

      python.stdout.on('data', (data) => {
        output += data.toString();
      });

      python.on('close', (code) => {
        clearTimeout(timeout);
        if (code === 0) {
          try {
            resolve(JSON.parse(output.trim()));
          } catch (e) {
            resolve({
              available: false,
              error: 'Failed to parse Python output',
            });
          }
        } else {
          resolve({
            available: false,
            error: `Python exited with code ${code}`,
          });
        }
      });

      python.on('error', (error) => {
        clearTimeout(timeout);
        resolve({
          available: false,
          error: `Python not found: ${error.message}`,
        });
      });
    });
  }

  /**
   * Read metadata from a KAI file
   *
   * @param {string} kaiFilePath - Path to .kai file
   * @returns {Promise<Object>} KAI metadata (song.json contents)
   */
  async readKaiMetadata(kaiFilePath) {
    return new Promise((resolve, reject) => {
      const pythonSrcPath = this._getPythonSrcPath().replace(/\\/g, '\\\\');
      const escapedKaiPath = kaiFilePath.replace(/\\/g, '\\\\').replace(/'/g, "\\'");

      const args = [
        '-c',
        `
import sys
import json
import zipfile
sys.path.insert(0, '${pythonSrcPath}')

try:
    with zipfile.ZipFile('${escapedKaiPath}', 'r') as kai_zip:
        if 'song.json' not in kai_zip.namelist():
            raise Exception('song.json not found in KAI file')

        song_json_str = kai_zip.read('song.json').decode('utf-8')
        metadata = json.loads(song_json_str)
        print(json.dumps(metadata))
except Exception as e:
    print(json.dumps({'error': str(e)}), file=sys.stderr)
    sys.exit(1)
`
      ];

      const python = spawn(this.pythonPath, args, {
        cwd: join(__dirname, '..'),
        stdio: ['pipe', 'pipe', 'pipe'],
        env: this._getEnvWithBinPath(),
      });

      let output = '';
      let error = '';

      python.stdout.on('data', (data) => {
        output += data.toString();
      });

      python.stderr.on('data', (data) => {
        const text = data.toString();
        error += text;

        // Send stderr as logs
        const lines = text.split('\n');
        for (const line of lines) {
          if (!line.trim()) continue;
          let level = 'info';
          const lowerLine = line.toLowerCase();
          if (lowerLine.includes('error') || lowerLine.includes('failed')) {
            level = 'error';
          } else if (lowerLine.includes('warning') || lowerLine.includes('warn')) {
            level = 'warning';
          }
          this._sendLog(level, line.trim());
        }
      });

      python.on('close', (code) => {
        if (code === 0) {
          try {
            resolve(JSON.parse(output.trim()));
          } catch (e) {
            reject(new Error(`Failed to parse metadata: ${e.message}`));
          }
        } else {
          reject(new Error(`Failed to read KAI metadata: ${error || output}`));
        }
      });
    });
  }

  /**
   * Regenerate lyrics using Whisper (full re-transcription)
   *
   * @param {Object} options - Processing options
   * @param {string} options.inputFile - Path to input .kai file
   * @param {string} options.outputFile - Path to output .kai file
   * @param {string} options.whisperModel - Whisper model size
   * @param {string} options.language - Language code
   * @param {string} options.referenceLyrics - Reference lyrics for correction
   * @param {Object} options.llm - LLM settings
   * @param {Function} progressCallback - Progress updates
   * @returns {Promise<Object>} Processing result
   */
  async regenerateLyrics(options, progressCallback) {
    return new Promise((resolve, reject) => {
      const argsJson = JSON.stringify({
        inputFile: options.inputFile,
        outputFile: options.outputFile || options.inputFile,
        whisperModel: options.whisperModel || 'large-v3-turbo',
        language: options.language || 'en',
        referenceLyrics: options.referenceLyrics || null,
        llmEnabled: options.llm?.enabled || false,
        llmProvider: options.llm?.provider || null,
        llmModel: options.llm?.model || null,
        llmApiKey: options.llm?.apiKey || null,
        llmBaseUrl: options.llm?.baseUrl || null
      });

      const pythonSrcPath = this._getPythonSrcPath().replace(/\\/g, '\\\\');

      const args = [
        '-c',
        `
import sys
import json
import logging

# Configure logging to stderr
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stderr,
    force=True
)
logger = logging.getLogger(__name__)

sys.path.insert(0, '${pythonSrcPath}')

from kai_pack.api import KaiAPI

logger.info("Starting lyrics regeneration...")

def progress_callback(stage, percent, message):
    print(f"PROGRESS:{json.dumps({'stage': stage, 'percent': percent, 'message': message})}", flush=True)

# Parse arguments
args = json.loads(sys.argv[1])

try:
    api = KaiAPI(progress_callback=progress_callback)
    result = api.regenerate_lyrics(
        input_file=args['inputFile'],
        output_file=args['outputFile'],
        whisper_model=args['whisperModel'],
        language=args['language'],
        reference_lyrics=args['referenceLyrics'],
        llm_enabled=args['llmEnabled'],
        llm_provider=args['llmProvider'],
        llm_model=args['llmModel'],
        llm_api_key=args['llmApiKey'],
        llm_base_url=args['llmBaseUrl']
    )
    print(f"RESULT:{json.dumps(result)}", flush=True)
except Exception as e:
    result = {
        'success': False,
        'error': str(e),
        'error_type': type(e).__name__
    }
    print(f"RESULT:{json.dumps(result)}", flush=True)
    sys.exit(1)
`,
        argsJson
      ];

      const python = spawn(this.pythonPath, args, {
        cwd: join(__dirname, '..'),
        stdio: ['pipe', 'pipe', 'pipe'],
        env: this._getEnvWithBinPath(),
      });

      this.activeProcesses.add(python);

      let outputBuffer = '';
      let result = null;

      python.stdout.on('data', (data) => {
        const lines = data.toString().split('\n');
        for (const line of lines) {
          if (line.startsWith('PROGRESS:')) {
            try {
              const progress = JSON.parse(line.substring(9));
              if (progressCallback) progressCallback(progress);
            } catch (e) {
              console.error('Failed to parse progress:', e);
            }
          } else if (line.startsWith('RESULT:')) {
            try {
              result = JSON.parse(line.substring(7));
            } catch (e) {
              console.error('Failed to parse result:', e);
            }
          } else {
            outputBuffer += line + '\n';
          }
        }
      });

      python.stderr.on('data', (data) => {
        const text = data.toString();
        const lines = text.split('\n');
        for (const line of lines) {
          if (!line.trim()) continue;

          // Parse progress bars if present
          if (line.match(/^\s*\d+%\|/) || line.match(/(vocals|drums|bass|other):\s*\d+%/i)) {
            continue; // Skip progress bars
          }

          // Send as log
          let level = 'info';
          const lowerLine = line.toLowerCase();
          if (lowerLine.includes('error') || lowerLine.includes('failed')) {
            level = 'error';
          } else if (lowerLine.includes('warning') || lowerLine.includes('warn')) {
            level = 'warning';
          } else if (lowerLine.includes('debug')) {
            level = 'debug';
          }

          this._sendLog(level, line.trim());
        }
      });

      python.on('close', (code) => {
        this.activeProcesses.delete(python);

        if (result) {
          resolve(result);
        } else if (code === 0) {
          resolve({ success: true });
        } else {
          reject({
            error: `Process exited with code ${code}`,
            error_type: 'ProcessError',
            stderr: outputBuffer
          });
        }
      });

      python.on('error', (error) => {
        this.activeProcesses.delete(python);
        reject({
          error: error.message,
          error_type: 'SpawnError'
        });
      });
    });
  }

  /**
   * Fix lyrics using LLM only (no Whisper re-transcription)
   *
   * @param {Object} options - Processing options
   * @param {string} options.inputFile - Path to input .kai file
   * @param {string} options.outputFile - Path to output .kai file
   * @param {string} options.referenceLyrics - Reference lyrics for correction
   * @param {Object} options.llm - LLM settings
   * @returns {Promise<Object>} Processing result
   */
  async fixLyrics(options) {
    return new Promise((resolve, reject) => {
      const argsJson = JSON.stringify({
        inputFile: options.inputFile,
        outputFile: options.outputFile || options.inputFile,
        referenceLyrics: options.referenceLyrics || null,
        llmProvider: options.llm?.provider || null,
        llmModel: options.llm?.model || null,
        llmApiKey: options.llm?.apiKey || null,
        llmBaseUrl: options.llm?.baseUrl || null
      });

      const pythonSrcPath = this._getPythonSrcPath().replace(/\\/g, '\\\\');

      const args = [
        '-c',
        `
import sys
import json
sys.path.insert(0, '${pythonSrcPath}')

from kai_pack.api import KaiAPI

# Parse arguments
args = json.loads(sys.argv[1])

try:
    api = KaiAPI()
    result = api.fix_lyrics(
        input_file=args['inputFile'],
        output_file=args['outputFile'],
        reference_lyrics=args['referenceLyrics'],
        llm_provider=args['llmProvider'],
        llm_model=args['llmModel'],
        llm_api_key=args['llmApiKey'],
        llm_base_url=args['llmBaseUrl']
    )
    print(json.dumps(result))
except Exception as e:
    result = {
        'success': False,
        'error': str(e),
        'error_type': type(e).__name__
    }
    print(json.dumps(result), file=sys.stderr)
    sys.exit(1)
`,
        argsJson
      ];

      const python = spawn(this.pythonPath, args, {
        cwd: join(__dirname, '..'),
        stdio: ['pipe', 'pipe', 'pipe'],
        env: this._getEnvWithBinPath(),
      });

      this.activeProcesses.add(python);

      let output = '';
      let error = '';

      python.stdout.on('data', (data) => {
        output += data.toString();
      });

      python.stderr.on('data', (data) => {
        const text = data.toString();
        error += text;

        // Also send stderr as logs
        const lines = text.split('\n');
        for (const line of lines) {
          if (!line.trim()) continue;

          // Determine log level
          let level = 'info';
          const lowerLine = line.toLowerCase();
          if (lowerLine.includes('error') || lowerLine.includes('failed')) {
            level = 'error';
          } else if (lowerLine.includes('warning') || lowerLine.includes('warn')) {
            level = 'warning';
          } else if (lowerLine.includes('debug')) {
            level = 'debug';
          }

          this._sendLog(level, line.trim());
        }
      });

      python.on('close', (code) => {
        this.activeProcesses.delete(python);

        if (code === 0) {
          try {
            resolve(JSON.parse(output.trim()));
          } catch (e) {
            reject({
              error: `Failed to parse result: ${e.message}`,
              error_type: 'ParseError'
            });
          }
        } else {
          try {
            const errorResult = JSON.parse(error.trim());
            reject(errorResult);
          } catch (e) {
            reject({
              error: error || output || `Process exited with code ${code}`,
              error_type: 'ProcessError'
            });
          }
        }
      });

      python.on('error', (error) => {
        this.activeProcesses.delete(python);
        reject({
          error: error.message,
          error_type: 'SpawnError'
        });
      });
    });
  }

  /**
   * Kill all active Python processes
   * Call this when the app is quitting
   */
  cleanup() {
    for (const process of this.activeProcesses) {
      try {
        process.kill('SIGKILL');
      } catch (e) {
        console.error('Failed to kill Python process:', e);
      }
    }
    this.activeProcesses.clear();
  }
}

export default PythonBridge;
