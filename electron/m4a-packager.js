/**
 * M4A Stems Packager - JavaScript bridge to m4a-stems module
 * Replaces Python M4A packaging with JavaScript implementation
 */

import { M4AStemsWriter } from 'm4a-stems';
import fs from 'fs/promises';
import path from 'path';

/**
 * Package M4A Stems file from WAV stems + JSON metadata
 *
 * This replaces the Python m4a_packaging.package_stems_m4a() function
 *
 * @param {Object} options - Packaging options
 * @returns {Promise<Object>} Packaging results
 */
export async function packageStemsM4A(options) {
  const {
    outputPath,
    stemsWavFiles,     // { drums: '/path/to/drums.wav', bass: '...', other: '...', vocals: '...' }
    mixdownWav,        // '/path/to/mixdown.wav'
    lyricsData,        // { lines: [...], singers: [...] }
    metadata,          // { song: { title, artist, album, ... }, original_bitrate }
    analysisFeatures = {},
    sampleRate = 44100,
    profile = 'STEMS-4',  // or 'STEMS-2'
    codec = 'aac',        // or 'alac'
    bitrate = null,
    coverArt = null
  } = options;

  console.log(`[M4A Packager] Packaging ${outputPath}`);
  console.log(`[M4A Packager] Profile: ${profile}, Codec: ${codec}`);

  try {
    // Call m4a-stems Writer
    const result = await M4AStemsWriter.write({
      outputPath,
      stemsWavFiles,
      mixdownWav,
      metadata,
      lyricsData,
      analysisFeatures,
      profile,
      codec,
      bitrate,
      sampleRate,
      coverArt
    });

    console.log(`[M4A Packager] ✓ Packaging complete: ${result.fileSizeBytes} bytes`);

    // Return result in format expected by Python bridge
    return {
      success: true,
      output_file: result.outputFile,
      file_size_bytes: result.fileSizeBytes,
      file_sha256: result.fileSha256,
      processing_time_seconds: result.processingTimeSeconds,
      profile: result.profile,
      codec: result.codec,
      encoder_delay_samples: result.encoderDelaySamples
    };

  } catch (error) {
    console.error(`[M4A Packager] Error: ${error.message}`);
    throw error;
  }
}

/**
 * Validate that all required WAV files exist
 * @param {Object} stemsWavFiles - Dictionary of stem WAV paths
 * @param {string} mixdownWav - Path to mixdown WAV
 * @returns {Promise<boolean>} True if all files exist
 */
export async function validateWavFiles(stemsWavFiles, mixdownWav) {
  const allFiles = Object.values(stemsWavFiles).concat([mixdownWav]);

  for (const filePath of allFiles) {
    try {
      await fs.access(filePath);
    } catch (error) {
      console.error(`[M4A Packager] Missing WAV file: ${filePath}`);
      return false;
    }
  }

  return true;
}

export default {
  packageStemsM4A,
  validateWavFiles
};
