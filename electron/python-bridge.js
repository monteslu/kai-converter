import { spawn } from 'child_process';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

/**
 * Python Bridge - Communicates with KAI Python backend
 *
 * Spawns Python processes to call the KaiAPI we created in Phase 1.
 * Parses progress updates and returns structured results.
 */

export class PythonBridge {
  constructor() {
    this.pythonPath = this._getPythonPath();
    this.activeProcesses = new Set();
  }

  /**
   * Get the Python executable path
   * In dev: use system Python
   * In production: use bundled Python
   */
  _getPythonPath() {
    const isDev = !process.env.NODE_ENV || process.env.NODE_ENV === 'development';

    if (isDev) {
      // Development: use system Python with venv
      return 'python3';
    } else {
      // Production: use bundled Python (will be implemented in Phase 5)
      // For now, fall back to system Python
      return 'python3';
    }
  }

  /**
   * Process an audio file to KAI format
   *
   * @param {Object} options - Processing options
   * @param {string} options.inputFile - Path to input audio file
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
        inputFile: options.inputFile,
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

      const args = [
        '-c',
        `
import sys
import json
sys.path.insert(0, '${join(__dirname, '..', 'src').replace(/\\/g, '\\\\')}')

from kai_pack.api import KaiAPI

def progress_callback(stage, percent, message):
    print(f"PROGRESS:{json.dumps({'stage': stage, 'percent': percent, 'message': message})}", flush=True)

# Parse arguments from command line
args = json.loads(sys.argv[1])

api = KaiAPI(progress_callback=progress_callback)
result = api.process_audio(
    input_file=args['inputFile'],
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
`,
        argsJson
      ];

      const python = spawn(this.pythonPath, args, {
        cwd: join(__dirname, '..'),
        stdio: ['pipe', 'pipe', 'pipe'],
        env: {
          ...process.env,
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
          }
        }
      });

      python.stderr.on('data', (data) => {
        const text = data.toString();
        errorBuffer += text;

        // Parse tqdm progress bars (Demucs)
        // Format 1: Per-stem progress like "vocals: 45%|████▌     | 45/100"
        const stemMatch = text.match(/(vocals|drums|bass|other):\s*(\d+)%/i);
        if (stemMatch && progressCallback) {
          const stemName = stemMatch[1].charAt(0).toUpperCase() + stemMatch[1].slice(1);
          const percent = parseInt(stemMatch[2]);
          progressCallback({
            stage: 'demucs',
            percent: percent,
            message: `Separating ${stemName} stem...`,
            subProgress: percent / 100
          });
        }

        // Format 2: Overall Demucs progress like "  59%|██████|  93.6/157.95 [00:17<00:11, 5.66s/s]"
        const overallMatch = text.match(/^\s*(\d+)%\|[█▏▎▍▌▋▊▉ ]+\|\s*[\d.]+\/[\d.]+/);
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
    return new Promise((resolve) => {
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
      });

      let output = '';

      python.stdout.on('data', (data) => {
        output += data.toString();
      });

      python.on('close', (code) => {
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

      python.on('error', () => {
        resolve({
          available: false,
          error: 'Python not found',
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
