#!/usr/bin/env node

/**
 * Download platform-specific binaries (ffmpeg only)
 * yt-dlp is installed via pip in the Python environment
 */

import https from 'https';
import { createWriteStream, existsSync, mkdirSync, rmSync, chmodSync } from 'fs';
import { execSync } from 'child_process';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import * as tar from 'tar';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const ROOT_DIR = join(__dirname, '..');
const BIN_DIR = join(ROOT_DIR, 'resources', 'bin');

// Download URLs for binaries with fallbacks
const BINARIES = {
  darwin: {
    ffmpeg: {
      urls: [
        'https://evermeet.cx/ffmpeg/getrelease/zip',
        'https://github.com/eugeneware/ffmpeg-static/releases/latest/download/darwin-x64',
      ],
      filename: 'ffmpeg.zip',
      extract: 'ffmpeg',
    },
  },
  win32: {
    ffmpeg: {
      urls: [
        'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip',
        'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip',
      ],
      filename: 'ffmpeg.zip',
      extract: 'ffmpeg.exe',
    },
  },
  linux: {
    ffmpeg: {
      urls: [
        'https://github.com/ffbinaries/ffbinaries-prebuilt/releases/download/v4.4.1/ffmpeg-4.4.1-linux-64.zip',
      ],
      filename: 'ffmpeg.zip',
      extract: 'ffmpeg',
    },
  },
};

function getPlatform() {
  return process.platform;
}

async function download(url, destPath) {
  console.log(`📥 Downloading from ${url}...`);

  return new Promise((resolve, reject) => {
    const parsedUrl = new URL(url);
    const options = {
      headers: { 'User-Agent': 'KAI-Converter' }
    };

    const request = https.get(url, options, (response) => {
      // Follow redirects
      if (response.statusCode === 302 || response.statusCode === 301) {
        let redirectUrl = response.headers.location;

        // Handle relative URLs
        if (redirectUrl.startsWith('/')) {
          redirectUrl = `${parsedUrl.protocol}//${parsedUrl.host}${redirectUrl}`;
        } else if (!redirectUrl.startsWith('http')) {
          redirectUrl = `${parsedUrl.protocol}//${parsedUrl.host}/${redirectUrl}`;
        }

        return download(redirectUrl, destPath).then(resolve).catch(reject);
      }

      if (response.statusCode !== 200) {
        reject(new Error(`Failed to download: ${response.statusCode}`));
        return;
      }

      const totalBytes = parseInt(response.headers['content-length'] || '0', 10);
      let downloadedBytes = 0;

      response.on('data', (chunk) => {
        downloadedBytes += chunk.length;
        if (totalBytes > 0) {
          const percent = ((downloadedBytes / totalBytes) * 100).toFixed(1);
          process.stdout.write(`\r   Progress: ${percent}% (${(downloadedBytes / 1024 / 1024).toFixed(1)}MB / ${(totalBytes / 1024 / 1024).toFixed(1)}MB)`);
        }
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
    });

    request.on('error', reject);
  });
}

async function extractZip(zipPath, targetFile, destPath) {
  console.log(`📦 Extracting ${targetFile}...`);

  const platform = getPlatform();

  if (platform === 'win32') {
    // Use PowerShell on Windows
    execSync(`powershell -command "Expand-Archive -Path '${zipPath}' -DestinationPath '${dirname(zipPath)}' -Force"`, {
      stdio: 'inherit',
    });
    // Find the extracted file (might be in subdirectory)
    const extractDir = dirname(zipPath);
    const files = execSync(`powershell -command "Get-ChildItem -Path '${extractDir}' -Recurse -Filter '${targetFile}' | Select-Object -First 1 -ExpandProperty FullName"`)
      .toString()
      .trim();
    if (files) {
      execSync(`move /y "${files}" "${destPath}"`, { stdio: 'inherit' });
    }
  } else {
    // Use unzip on macOS/Linux
    execSync(`unzip -o "${zipPath}" -d "${dirname(zipPath)}"`, { stdio: 'inherit' });
    // Find the extracted file
    const files = execSync(`find "${dirname(zipPath)}" -name "${targetFile}" -type f`)
      .toString()
      .trim()
      .split('\n');
    if (files[0]) {
      execSync(`mv "${files[0]}" "${destPath}"`, { stdio: 'inherit' });
    }
  }

  // Clean up zip
  rmSync(zipPath, { force: true });
  console.log('✅ Extraction complete!');
}

async function extractTarXz(tarPath, targetFile, destPath) {
  console.log(`📦 Extracting ${targetFile}...`);

  const extractDir = dirname(tarPath);

  // Extract tar.xz
  await tar.extract({
    file: tarPath,
    cwd: extractDir,
  });

  // Find the extracted file
  const files = execSync(`find "${extractDir}" -name "${targetFile}" -type f`)
    .toString()
    .trim()
    .split('\n');

  if (files[0]) {
    execSync(`mv "${files[0]}" "${destPath}"`, { stdio: 'inherit' });
  }

  // Clean up tar
  rmSync(tarPath, { force: true });
  console.log('✅ Extraction complete!');
}

async function downloadBinary(name, config) {
  console.log(`\n🔧 Setting up ${name}...`);

  const tempPath = join(BIN_DIR, config.filename);
  const finalPath = join(BIN_DIR, config.extract || config.filename);

  // Skip if already exists
  if (existsSync(finalPath)) {
    console.log(`✓ ${name} already exists, skipping`);
    return;
  }

  // Try each URL until one works
  const urls = Array.isArray(config.urls) ? config.urls : [config.url];
  let lastError = null;

  for (let i = 0; i < urls.length; i++) {
    const url = urls[i];
    try {
      console.log(`  Trying source ${i + 1}/${urls.length}...`);
      await download(url, tempPath);
      lastError = null;
      break; // Success!
    } catch (error) {
      lastError = error;
      console.log(`  ✗ Failed: ${error.message}`);
      if (i < urls.length - 1) {
        console.log(`  Trying fallback...`);
      }
    }
  }

  if (lastError) {
    throw new Error(`All download sources failed for ${name}: ${lastError.message}`);
  }

  // Extract if needed
  if (config.extract) {
    if (tempPath.endsWith('.zip')) {
      await extractZip(tempPath, config.extract, finalPath);
    } else if (tempPath.endsWith('.tar.xz')) {
      await extractTarXz(tempPath, config.extract, finalPath);
    }
  } else {
    // Direct binary, just rename if needed
    if (tempPath !== finalPath) {
      execSync(`mv "${tempPath}" "${finalPath}"`, { stdio: 'inherit' });
    }
  }

  // Make executable on Unix-like systems
  if (process.platform !== 'win32') {
    chmodSync(finalPath, 0o755);
  }

  console.log(`✅ ${name} ready at ${finalPath}`);
}

async function setup() {
  console.log('🔧 Setting up platform binaries...\n');

  const platform = getPlatform();
  const binaries = BINARIES[platform];

  if (!binaries) {
    console.error(`❌ Unsupported platform: ${platform}`);
    process.exit(1);
  }

  // Create bin directory
  if (!existsSync(BIN_DIR)) {
    mkdirSync(BIN_DIR, { recursive: true });
  }

  // Download each binary
  for (const [name, config] of Object.entries(binaries)) {
    try {
      await downloadBinary(name, config);
    } catch (error) {
      console.error(`\n❌ Failed to setup ${name}:`, error.message);
      process.exit(1);
    }
  }

  console.log('\n🎉 All binaries setup complete!\n');
}

// Run setup
setup().catch((error) => {
  console.error('\n❌ Setup failed:', error.message);
  process.exit(1);
});
