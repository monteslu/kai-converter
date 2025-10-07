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
      const args = [
        '-c',
        `
import sys
import json
sys.path.insert(0, '${join(__dirname, '..', 'src').replace(/\\/g, '\\\\')}')

from kai_pack.api import KaiAPI

def progress_callback(stage, percent, message):
    print(f"PROGRESS:{json.dumps({'stage': stage, 'percent': percent, 'message': message})}", flush=True)

api = KaiAPI(progress_callback=progress_callback)
result = api.process_audio(
    input_file='${options.inputFile.replace(/\\/g, '\\\\')}',
    output_file=${options.outputFile ? `'${options.outputFile.replace(/\\/g, '\\\\')}'` : 'None'},
    whisper_model='${options.whisperModel || 'small'}',
    language='${options.language || 'en'}',
    four_stems=${options.fourStems ? 'True' : 'False'},
    features=${options.features ? `['${options.features.join("', '")}']` : 'None'},
    llm_enabled=${options.llm?.enabled ? 'True' : 'False'},
    llm_provider=${options.llm?.provider ? `'${options.llm.provider}'` : 'None'},
    llm_model=${options.llm?.model ? `'${options.llm.model}'` : 'None'},
    llm_api_key=${options.llm?.apiKey ? `'${options.llm.apiKey.replace(/'/g, "\\'")}'` : 'None'},
    llm_base_url=${options.llm?.baseUrl ? `'${options.llm.baseUrl}'` : 'None'}
)

print(f"RESULT:{json.dumps(result)}", flush=True)
`
      ];

      const python = spawn(this.pythonPath, args, {
        cwd: join(__dirname, '..'),
        stdio: ['pipe', 'pipe', 'pipe'],
      });

      let outputBuffer = '';
      let errorBuffer = '';

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

        // Parse tqdm progress bars (format: "drums: 45%|████▌     | 45/100")
        // Extract both stem name and percentage
        const tqdmMatch = text.match(/(vocals|drums|bass|other):\s*(\d+)%/i);
        if (tqdmMatch && progressCallback) {
          const stemName = tqdmMatch[1].charAt(0).toUpperCase() + tqdmMatch[1].slice(1);
          const percent = parseInt(tqdmMatch[2]);
          // Emit as sub-progress for current step
          progressCallback({
            stage: 'demucs',
            percent: percent,
            message: `Separating ${stemName} stem...`,
            subProgress: percent / 100
          });
        }
      });

      python.on('close', (code) => {
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
    metadata = extractor.extract_metadata(Path('${filePath.replace(/\\/g, '\\\\')}'))
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
        if (code === 0 && output.trim()) {
          try {
            resolve(JSON.parse(output.trim()));
          } catch (e) {
            resolve({
              success: false,
              error: 'Failed to parse response',
              title: null,
              artist: null,
            });
          }
        } else {
          resolve({
            success: false,
            error: 'Failed to read metadata',
            title: null,
            artist: null,
          });
        }
      });

      python.on('error', () => {
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
      const args = [
        '-c',
        `
import sys
import json
sys.path.insert(0, '${join(__dirname, '..', 'src').replace(/\\/g, '\\\\')}')

from utils.lyrics_utils import fetch_lyrics_from_lrclib

try:
    lyrics = fetch_lyrics_from_lrclib('${title.replace(/'/g, "\\'")}', '${artist.replace(/'/g, "\\'")}')
    if lyrics:
        result = {'success': True, 'lyrics': lyrics}
    else:
        result = {'success': False, 'error': 'No lyrics found'}
    print(json.dumps(result))
except Exception as e:
    result = {'success': False, 'error': str(e)}
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
}

export default PythonBridge;
