/**
 * Setup Helper - Downloads and installs Python on first run
 */

import https from 'https';
import { createWriteStream, existsSync, mkdirSync, rmSync } from 'fs';
import { execSync } from 'child_process';
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

function installPackages(pythonPath, requirementsPath, progressCallback) {
  if (!existsSync(requirementsPath)) {
    console.warn('requirements.txt not found, skipping package installation');
    return;
  }

  if (progressCallback) {
    progressCallback({
      stage: 'packages',
      percent: 0,
      message: 'Installing Python packages...'
    });
  }

  try {
    // Upgrade pip first
    execSync(`"${pythonPath}" -m pip install --upgrade pip`, {
      stdio: 'inherit',
    });

    if (progressCallback) {
      progressCallback({
        stage: 'packages',
        percent: 20,
        message: 'Installing dependencies...'
      });
    }

    // Install requirements
    execSync(`"${pythonPath}" -m pip install -r "${requirementsPath}"`, {
      stdio: 'inherit',
    });

    if (progressCallback) {
      progressCallback({
        stage: 'packages',
        percent: 100,
        message: 'Package installation complete'
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
    installPackages(pythonPath, requirementsPath, progressCallback);

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
