/**
 * Setup Helper - Downloads and installs Python on first run
 */

import https from 'https';
import { createWriteStream, existsSync, mkdirSync, rmSync } from 'fs';
import { execSync, spawn } from 'child_process';
import { join } from 'path';
import * as tar from 'tar';

const PYTHON_BUILDS = {
  darwin: {
    x64: 'https://github.com/indygreg/python-build-standalone/releases/download/20241016/cpython-3.12.7+20241016-x86_64-apple-darwin-install_only.tar.gz',
    arm64: 'https://github.com/indygreg/python-build-standalone/releases/download/20241016/cpython-3.12.7+20241016-aarch64-apple-darwin-install_only.tar.gz',
  },
  win32: {
    x64: 'https://github.com/indygreg/python-build-standalone/releases/download/20241016/cpython-3.12.7+20241016-x86_64-pc-windows-msvc-shared-install_only.tar.gz',
  },
  linux: {
    x64: 'https://github.com/indygreg/python-build-standalone/releases/download/20241016/cpython-3.12.7+20241016-x86_64-unknown-linux-gnu-install_only.tar.gz',
    arm64: 'https://github.com/indygreg/python-build-standalone/releases/download/20241016/cpython-3.12.7+20241016-aarch64-unknown-linux-gnu-install_only.tar.gz',
  },
};

function getBuildUrl() {
  const platform = process.platform;
  const arch = process.arch;

  const builds = PYTHON_BUILDS[platform];
  if (!builds) {
    throw new Error(`Unsupported platform: ${platform}`);
  }

  const url = builds[arch] || builds.x64;
  if (!url) {
    throw new Error(`Unsupported architecture: ${arch} on ${platform}`);
  }

  return url;
}

async function download(url, destPath, progressCallback) {
  return new Promise((resolve, reject) => {
    https.get(url, (response) => {
      if (response.statusCode === 302 || response.statusCode === 301) {
        return download(response.headers.location, destPath, progressCallback).then(resolve).catch(reject);
      }

      if (response.statusCode !== 200) {
        reject(new Error(`Failed to download: ${response.statusCode}`));
        return;
      }

      const totalBytes = parseInt(response.headers['content-length'] || '0', 10);
      let downloadedBytes = 0;

      response.on('data', (chunk) => {
        downloadedBytes += chunk.length;
        const percent = totalBytes > 0 ? Math.floor((downloadedBytes / totalBytes) * 100) : 0;
        if (progressCallback) {
          progressCallback({
            stage: 'download',
            percent,
            message: `Downloading Python... ${(downloadedBytes / 1024 / 1024).toFixed(1)}MB / ${(totalBytes / 1024 / 1024).toFixed(1)}MB`
          });
        }
      });

      const fileStream = createWriteStream(destPath);
      response.pipe(fileStream);

      fileStream.on('finish', () => {
        fileStream.close();
        resolve();
      });

      fileStream.on('error', (err) => {
        rmSync(destPath, { force: true });
        reject(err);
      });
    }).on('error', reject);
  });
}

async function extractTarGz(tarPath, destDir, progressCallback) {
  if (progressCallback) {
    progressCallback({
      stage: 'extract',
      percent: 50,
      message: 'Extracting Python...'
    });
  }

  await tar.extract({
    file: tarPath,
    cwd: destDir,
    strip: 1,
  });

  // Remove macOS quarantine attribute so spawned processes work
  if (process.platform === 'darwin') {
    try {
      execSync(`xattr -cr "${destDir}"`, { stdio: 'ignore' });
      console.log('Removed macOS quarantine attribute');
    } catch (e) {
      console.warn('Could not remove quarantine (non-fatal):', e.message);
    }
  }

  if (progressCallback) {
    progressCallback({
      stage: 'extract',
      percent: 100,
      message: 'Extraction complete'
    });
  }
}

function getPythonExecutable(pythonDir) {
  if (process.platform === 'win32') {
    return join(pythonDir, 'python.exe');
  } else {
    return join(pythonDir, 'bin', 'python3');
  }
}

function detectGPU() {
  const platform = process.platform;

  // macOS: Check for Apple Silicon (MPS support)
  if (platform === 'darwin') {
    try {
      const arch = process.arch;
      if (arch === 'arm64') {
        console.log('✓ Apple Silicon detected (M1/M2/M3) - will use MPS acceleration');
        return { type: 'mps', hasCuda: false };
      } else {
        console.log('✗ Intel Mac detected - will use CPU-only PyTorch');
        return { type: 'cpu', hasCuda: false };
      }
    } catch {
      return { type: 'cpu', hasCuda: false };
    }
  }

  // Windows/Linux: Check for NVIDIA GPU
  try {
    // Try nvidia-smi first (works on both Windows and Linux)
    const nvidiaSmiCmd = platform === 'win32' ? 'nvidia-smi.exe' : 'nvidia-smi';
    execSync(nvidiaSmiCmd, { stdio: 'ignore' });
    console.log('✓ NVIDIA GPU detected (nvidia-smi found) - will use CUDA');
    return { type: 'cuda', hasCuda: true };
  } catch {
    // nvidia-smi not found, try lspci on Linux as backup
    if (platform === 'linux') {
      try {
        const output = execSync('lspci', { encoding: 'utf8' });
        if (output.toLowerCase().includes('nvidia')) {
          console.log('✓ NVIDIA GPU detected (lspci found NVIDIA device) - will use CUDA');
          return { type: 'cuda', hasCuda: true };
        }
      } catch {
        // lspci failed
      }
    }
    console.log('✗ No NVIDIA GPU detected - will use CPU-only PyTorch');
    return { type: 'cpu', hasCuda: false };
  }
}

async function runPipCommand(pythonPath, args, progressCallback, messagePrefix) {
  return new Promise((resolve, reject) => {
    const proc = spawn(pythonPath, ['-m', 'pip', ...args], {
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    let lastOutput = '';

    const processOutput = (data) => {
      const text = data.toString();
      console.log(text); // Log to terminal
      lastOutput = text;

      if (progressCallback) {
        // Extract useful info from pip output
        const lines = text.split('\n');
        for (const line of lines) {
          if (line.includes('Downloading') || line.includes('Installing') || line.includes('Collecting')) {
            const cleanLine = line.trim().substring(0, 80);
            progressCallback({
              stage: 'packages',
              percent: 50,
              message: `${messagePrefix}: ${cleanLine}`
            });
          }
        }
      }
    };

    proc.stdout.on('data', processOutput);
    proc.stderr.on('data', processOutput);

    proc.on('close', (code) => {
      if (code === 0) {
        resolve();
      } else {
        reject(new Error(`pip command failed with code ${code}`));
      }
    });

    proc.on('error', reject);
  });
}

async function installPackages(pythonPath, requirementsPath, progressCallback) {
  if (!existsSync(requirementsPath)) {
    console.warn('requirements.txt not found, skipping package installation');
    return;
  }

  if (progressCallback) {
    progressCallback({
      stage: 'packages',
      percent: 0,
      message: 'Detecting GPU capabilities...'
    });
  }

  // Detect GPU
  const gpu = detectGPU();

  try {
    // Upgrade pip first
    if (progressCallback) {
      progressCallback({
        stage: 'packages',
        percent: 5,
        message: 'Upgrading pip...'
      });
    }
    await runPipCommand(pythonPath, ['install', '--upgrade', 'pip'], progressCallback, 'Upgrading pip');

    // Install PyTorch first with appropriate version
    if (progressCallback) {
      let installMsg = '';
      if (gpu.type === 'cuda') {
        installMsg = 'Installing PyTorch with CUDA support (~3.8GB)...';
      } else if (gpu.type === 'mps') {
        installMsg = 'Installing PyTorch with MPS support (~200MB)...';
      } else {
        installMsg = 'Installing PyTorch CPU-only (~200MB)...';
      }
      progressCallback({
        stage: 'packages',
        percent: 10,
        message: installMsg
      });
    }

    if (gpu.type === 'cuda') {
      // Install CUDA version (Linux/Windows with NVIDIA GPU)
      console.log('Installing PyTorch with CUDA support...');
      await runPipCommand(
        pythonPath,
        ['install', 'torch', 'torchaudio', '--index-url', 'https://download.pytorch.org/whl/cu124'],
        progressCallback,
        'Installing PyTorch (CUDA)'
      );
    } else {
      // Install CPU-only version (works for Intel CPUs and enables MPS on Apple Silicon)
      // Note: MPS is automatically detected by PyTorch at runtime on Apple Silicon
      console.log(`Installing PyTorch (${gpu.type === 'mps' ? 'with MPS support' : 'CPU-only'})...`);
      await runPipCommand(
        pythonPath,
        ['install', 'torch', 'torchaudio', '--index-url', 'https://download.pytorch.org/whl/cpu'],
        progressCallback,
        gpu.type === 'mps' ? 'Installing PyTorch (MPS)' : 'Installing PyTorch (CPU)'
      );
    }

    // Install remaining requirements
    if (progressCallback) {
      progressCallback({
        stage: 'packages',
        percent: 60,
        message: 'Installing remaining dependencies...'
      });
    }
    await runPipCommand(
      pythonPath,
      ['install', '-r', requirementsPath],
      progressCallback,
      'Installing dependencies'
    );

    if (progressCallback) {
      progressCallback({
        stage: 'packages',
        percent: 100,
        message: 'Package installation complete!'
      });
    }
  } catch (error) {
    throw new Error(`Failed to install packages: ${error.message}`);
  }
}

export async function setupPython(pythonDir, requirementsPath, progressCallback) {
  try {
    // Clean existing installation
    if (existsSync(pythonDir)) {
      if (progressCallback) {
        progressCallback({
          stage: 'cleanup',
          percent: 0,
          message: 'Removing old installation...'
        });
      }
      rmSync(pythonDir, { recursive: true, force: true });
    }

    // Create directory
    mkdirSync(pythonDir, { recursive: true });

    // Download
    const buildUrl = getBuildUrl();
    const tarPath = join(pythonDir, 'python.tar.gz');

    await download(buildUrl, tarPath, progressCallback);

    // Extract
    await extractTarGz(tarPath, pythonDir, progressCallback);

    // Clean up tarball
    rmSync(tarPath);

    // Get Python executable
    const pythonPath = getPythonExecutable(pythonDir);

    if (!existsSync(pythonPath)) {
      throw new Error(`Python executable not found at ${pythonPath}`);
    }

    // Verify Python
    const version = execSync(`"${pythonPath}" --version`).toString().trim();
    console.log(`Python installed: ${version}`);

    // Install packages
    await installPackages(pythonPath, requirementsPath, progressCallback);

    if (progressCallback) {
      progressCallback({
        stage: 'complete',
        percent: 100,
        message: 'Python setup complete!'
      });
    }

    return { success: true, pythonPath };
  } catch (error) {
    if (progressCallback) {
      progressCallback({
        stage: 'error',
        percent: 0,
        message: `Setup failed: ${error.message}`
      });
    }
    throw error;
  }
}
