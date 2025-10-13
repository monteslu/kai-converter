/**
 * Load audio files from a .kai file for playback in the editor
 *
 * Since we're in Electron, we can ask the backend to extract audio
 * and return them as buffers/blobs
 */

export async function loadKaiAudioFiles(kaiFilePath) {
  if (!window.electronAPI) {
    throw new Error('Electron API not available');
  }

  // Ask backend to extract audio files from .kai
  const result = await window.electronAPI.extractKaiAudio(kaiFilePath);

  if (!result.success) {
    throw new Error(result.error || 'Failed to extract audio from KAI file');
  }

  // result.audioFiles is an array of { name, data: Buffer }
  // Convert to blob URLs for Audio elements
  const audioFiles = result.audioFiles.map(file => {
    const blob = new Blob([file.data], { type: 'audio/mp3' });
    const url = URL.createObjectURL(blob);
    return {
      name: file.name,
      downloadUrl: url,
      audioData: file.data // Keep raw data for waveform analysis
    };
  });

  return audioFiles;
}
