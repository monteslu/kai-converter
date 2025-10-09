#!/usr/bin/env node

/**
 * Download and setup standalone Python for cross-platform bundling
 *
 * Uses python-build-standalone by Gregory Szorc
 * https://github.com/indygreg/python-build-standalone
 *
 * This creates a completely self-contained Python environment with all dependencies
 * No system Python needed, no compilation required!
 */

import https from 'https';
import { createWriteStream, existsSync, mkdirSync, rmSync } from 'fs';
import { pipeline } from 'stream/promises';
import { execSync, spawn } from 'child_process';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { createGunzip } from 'zlib';
import * as tar from 'tar';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const ROOT_DIR = join(__dirname, '..');
const PYTHON_DIR = join(ROOT_DIR, 'python-standalone');

// Python standalone build URLs (latest stable versions)
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

function getPlatformArch() {
  const platform = process.platform;
  const arch = process.arch;
  return { platform, arch };
}

function getBuildUrl() {
  const { platform, arch } = getPlatformArch();

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

async function download(url, destPath) {
  console.log(`📥 Downloading from ${url}...`);

  return new Promise((resolve, reject) => {
    https.get(url, (response) => {
      if (response.statusCode === 302 || response.statusCode === 301) {
        // Follow redirect
        return download(response.headers.location, destPath).then(resolve).catch(reject);
      }

      if (response.statusCode !== 200) {
        reject(new Error(`Failed to download: ${response.statusCode}`));
        return;
      }

      const totalBytes = parseInt(response.headers['content-length'] || '0', 10);
      let downloadedBytes = 0;

      response.on('data', (chunk) => {
        downloadedBytes += chunk.length;
        const percent = ((downloadedBytes / totalBytes) * 100).toFixed(1);
        process.stdout.write(`\r   Progress: ${percent}% (${(downloadedBytes / 1024 / 1024).toFixed(1)}MB / ${(totalBytes / 1024 / 1024).toFixed(1)}MB)`);
      });

      const fileStream = createWriteStream(destPath);
      response.pipe(fileStream);

      fileStream.on('finish', () => {
        fileStream.close();
        console.log('\n✅ Download complete!');
        resolve();
      });

      fileStream.on('error', (err) => {
        rmSync(destPath, { force: true });
        reject(err);
      });
    }).on('error', reject);
  });
}

async function extractTarGz(tarPath, destDir) {
  console.log(`📦 Extracting to ${destDir}...`);

  await tar.extract({
    file: tarPath,
    cwd: destDir,
    strip: 1, // Strip the top-level directory
  });

  console.log('✅ Extraction complete!');
}

function getPythonExecutable() {
  const { platform } = getPlatformArch();

  if (platform === 'win32') {
    return join(PYTHON_DIR, 'python.exe');
  } else {
    return join(PYTHON_DIR, 'bin', 'python3');
  }
}

function installPackages(pythonPath) {
  console.log('\n📦 Installing Python packages...');

  const requirementsFile = join(ROOT_DIR, 'requirements.txt');

  if (!existsSync(requirementsFile)) {
    console.warn('⚠️  requirements.txt not found, skipping package installation');
    return;
  }

  console.log('   Installing from requirements.txt...');

  try {
    execSync(`"${pythonPath}" -m pip install --upgrade pip`, {
      stdio: 'inherit',
      cwd: ROOT_DIR
    });

    execSync(`"${pythonPath}" -m pip install -r "${requirementsFile}"`, {
      stdio: 'inherit',
      cwd: ROOT_DIR
    });

    console.log('✅ Packages installed successfully!');
  } catch (error) {
    console.error('❌ Failed to install packages:', error.message);
    throw error;
  }
}

async function setup() {
  console.log('🐍 Setting up standalone Python environment...\n');

  // Clean existing installation
  if (existsSync(PYTHON_DIR)) {
    console.log('🗑️  Removing existing installation...');
    rmSync(PYTHON_DIR, { recursive: true, force: true });
  }

  // Create directory
  mkdirSync(PYTHON_DIR, { recursive: true });

  // Download
  const buildUrl = getBuildUrl();
  const tarPath = join(PYTHON_DIR, 'python.tar.gz');

  await download(buildUrl, tarPath);

  // Extract
  await extractTarGz(tarPath, PYTHON_DIR);

  // Clean up tarball
  rmSync(tarPath);

  // Get Python executable
  const pythonPath = getPythonExecutable();

  if (!existsSync(pythonPath)) {
    throw new Error(`Python executable not found at ${pythonPath}`);
  }

  console.log(`\n✅ Python installed at: ${pythonPath}`);

  // Verify Python
  const version = execSync(`"${pythonPath}" --version`).toString().trim();
  console.log(`   Version: ${version}`);

  // Install packages
  installPackages(pythonPath);

  console.log('\n🎉 Standalone Python setup complete!\n');
  console.log('Next steps:');
  console.log('  1. Run: npm run dev:all (to test in development)');
  console.log('  2. Run: npm run package (to build distributable app)');
  console.log('');
}

// Run setup
setup().catch((error) => {
  console.error('\n❌ Setup failed:', error.message);
  process.exit(1);
});
