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
    four_stems=${options.fourStems ? 'True' : 'False'}
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
        errorBuffer += data.toString();
        console.error('Python stderr:', data.toString());
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
