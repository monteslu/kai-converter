import { useState, useEffect, useRef } from 'react';

export default function ConvertScreen() {
  const [inputMode, setInputMode] = useState('file'); // 'file' or 'youtube'
  const [inputFile, setInputFile] = useState(null);
  const [youtubeUrl, setYoutubeUrl] = useState('');
  const [youtubeTitle, setYoutubeTitle] = useState('');
  const [youtubeArtist, setYoutubeArtist] = useState('');
  const [outputFile, setOutputFile] = useState(null);
  const [outputFormat, setOutputFormat] = useState('kai'); // 'kai' or 'm4a'
  const [whisperModel, setWhisperModel] = useState('large-v3-turbo');
  const [language, setLanguage] = useState('auto');
  const [fourStems, setFourStems] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [progress, setProgress] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [lyricsStatus, setLyricsStatus] = useState(null); // 'loading', 'found', 'not-found'
  const [referenceLyrics, setReferenceLyrics] = useState(null);
  const [manualLyrics, setManualLyrics] = useState('');
  const [showLyricsInput, setShowLyricsInput] = useState(false);
  const [showLyricsDisplay, setShowLyricsDisplay] = useState(false);
  const [liveLyric, setLiveLyric] = useState(null); // Live transcription from Whisper
  const [songDuration, setSongDuration] = useState(null); // Song duration in seconds
  const [whisperProgress, setWhisperProgress] = useState(null); // { currentTime, confidence }
  const fileInputRef = useRef(null);

  // Load settings on mount
  useEffect(() => {
    loadSettings();
  }, []);

  // Listen for live lyrics during Whisper transcription
  useEffect(() => {
    if (!window.electronAPI?.onLogs) return;

    const unsubscribe = window.electronAPI.onLogs((logEntry) => {
      // Only show live lyrics during Whisper stage
      if (!isWhisperStage()) {
        if (liveLyric) setLiveLyric(null); // Clear when not in Whisper stage
        if (whisperProgress) setWhisperProgress(null); // Clear progress too
        return;
      }

      // Check if this is a Whisper transcription line (format: [00:22.020 --> 00:25.000]  Text)
      const timestampMatch = logEntry.message?.match(/^\[(\d{2}):(\d{2})\.(\d{3}) --> (\d{2}):(\d{2})\.(\d{3})\]/);
      if (logEntry.level === 'info' && timestampMatch) {
        // Extract the end timestamp (how far through the song we've transcribed)
        const minutes = parseInt(timestampMatch[4]);
        const seconds = parseInt(timestampMatch[5]);
        const milliseconds = parseInt(timestampMatch[6]);
        const currentTime = minutes * 60 + seconds + milliseconds / 1000;

        // Extract lyric text
        const lyricText = logEntry.message.replace(/^\[\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}\.\d{3}\]\s*/, '');
        setLiveLyric(lyricText.trim());

        // Update progress time
        setWhisperProgress(prev => ({ ...prev, currentTime }));
      }

      // Parse confidence values (format: "confidence: 0.70")
      const confidenceMatch = logEntry.message?.match(/confidence:\s*(0?\.\d+)/);
      if (confidenceMatch) {
        const confidence = parseFloat(confidenceMatch[1]);
        setWhisperProgress(prev => ({ ...prev, confidence }));
      }
    });

    return unsubscribe;
  }, [isProcessing, progress]);

  // Update output file extension when format changes
  useEffect(() => {
    if (outputFile) {
      const extension = outputFormat === 'm4a' ? '.stem.m4a' : '.kai';
      // Replace the extension at the end
      const newPath = outputFile.replace(/\.(kai|stem\.m4a)$/, extension);
      if (newPath !== outputFile) {
        setOutputFile(newPath);
      }
    }
  }, [outputFormat]);

  async function loadSettings() {
    try {
      if (window.electronAPI) {
        const settings = await window.electronAPI.loadSettings();
        setWhisperModel(settings.whisperModel || 'large-v3-turbo');
        setLanguage(settings.language || 'auto');
        setFourStems(settings.stems === 4);
      }
    } catch (error) {
      console.error('Failed to load settings:', error);
    }
  }

  // Handle file selection via dialog
  async function handleSelectFile() {
    try {
      if (window.electronAPI) {
        const filePath = await window.electronAPI.selectAudioFile();
        if (filePath) {
          await processFileSelection(filePath);
        }
      }
    } catch (error) {
      console.error('File selection error:', error);
    }
  }

  // Process file selection - read metadata and fetch lyrics
  async function processFileSelection(filePath) {
    setInputFile(filePath);
    setResult(null);
    setError(null);
    setLyricsStatus(null);
    setReferenceLyrics(null);
    setManualLyrics('');
    setShowLyricsInput(false);
    setShowLyricsDisplay(false);

    // Auto-generate output file path based on format
    const extension = outputFormat === 'm4a' ? '.stem.m4a' : '.kai';
    const outputPath = filePath.replace(/\.[^.]+$/, extension);
    setOutputFile(outputPath);

    // Read metadata
    const metadata = await window.electronAPI.readAudioMetadata(filePath);
    console.log('Metadata result:', metadata);
    const title = metadata.title;
    const artist = metadata.artist;

    // Extract song duration for progress calculation
    if (metadata.duration || metadata.duration_seconds) {
      setSongDuration(metadata.duration || metadata.duration_seconds);
    }

    // Fetch lyrics if we have title and artist
    if (title && artist) {
      setLyricsStatus('loading');
      const lyricsResult = await window.electronAPI.fetchLyrics(title, artist);

      if (lyricsResult.success) {
        setLyricsStatus('found');
        setReferenceLyrics(lyricsResult.lyrics);
      } else {
        setLyricsStatus('not-found');
      }
    } else {
      setLyricsStatus('no-metadata');
    }
  }

  // Process YouTube URL - fetch lyrics based on title/artist
  async function processYoutubeUrl() {
    setResult(null);
    setError(null);
    setLyricsStatus(null);
    setReferenceLyrics(null);
    setManualLyrics('');
    setShowLyricsInput(false);
    setShowLyricsDisplay(false);

    // Auto-generate output file path in user's home directory
    if (youtubeTitle && youtubeArtist) {
      const extension = outputFormat === 'm4a' ? '.stem.m4a' : '.kai';
      const outputFileName = `${youtubeArtist} - ${youtubeTitle}${extension}`;

      // Get user's home directory and create full path
      if (window.electronAPI?.getHomeDirectory) {
        const homeDir = await window.electronAPI.getHomeDirectory();
        setOutputFile(`${homeDir}/${outputFileName}`);
      } else {
        // Fallback if API not available
        setOutputFile(outputFileName);
      }

      // Fetch lyrics if we have title and artist
      setLyricsStatus('loading');
      const lyricsResult = await window.electronAPI.fetchLyrics(youtubeTitle, youtubeArtist);

      if (lyricsResult.success) {
        setLyricsStatus('found');
        setReferenceLyrics(lyricsResult.lyrics);
      } else {
        setLyricsStatus('not-found');
      }
    }
  }

  // Handle output folder selection
  async function handleSelectOutputFolder() {
    try {
      if (window.electronAPI) {
        const folderPath = await window.electronAPI.selectOutputFolder();
        if (folderPath && inputFile) {
          const fileName = inputFile.split('/').pop().split('\\').pop();
          const extension = outputFormat === 'm4a' ? '.stem.m4a' : '.kai';
          const outputFileName = fileName.replace(/\.[^.]+$/, extension);
          setOutputFile(`${folderPath}/${outputFileName}`);
        }
      }
    } catch (error) {
      console.error('Folder selection error:', error);
    }
  }

  // Handle drag and drop
  function handleDragOver(e) {
    e.preventDefault();
    setIsDragging(true);
  }

  function handleDragLeave(e) {
    e.preventDefault();
    setIsDragging(false);
  }

  async function handleDrop(e) {
    e.preventDefault();
    setIsDragging(false);

    const files = e.dataTransfer?.files;
    if (files && files.length > 0) {
      const file = files[0];
      // In Electron, we get the file path from the File object
      const filePath = file.path;
      if (filePath) {
        await processFileSelection(filePath);
      }
    }
  }

  // Process audio
  async function handleConvert() {
    if (inputMode === 'file' && !inputFile) {
      setError('Please select an input file');
      return;
    }

    if (inputMode === 'youtube') {
      if (!youtubeUrl) {
        setError('Please enter a YouTube URL');
        return;
      }
      if (!youtubeTitle) {
        setError('Please enter the song title');
        return;
      }
      if (!youtubeArtist) {
        setError('Please enter the artist name');
        return;
      }
    }

    setIsProcessing(true);
    setProgress(null);
    setResult(null);
    setError(null);

    // Subscribe to progress updates
    const unsubscribe = window.electronAPI?.onProgress((progressUpdate) => {
      setProgress(progressUpdate);
    });

    try {
      // Reload LLM settings to pick up any changes made in Settings screen
      const settings = await window.electronAPI.loadSettings();
      const llmSettings = settings.llm || {};

      const options = {
        inputFile: inputMode === 'file' ? inputFile : null,
        youtubeUrl: inputMode === 'youtube' ? youtubeUrl : null,
        title: inputMode === 'youtube' ? youtubeTitle : null,
        artist: inputMode === 'youtube' ? youtubeArtist : null,
        outputFile,
        outputFormat,  // Pass format: 'kai' or 'm4a'
        whisperModel,
        language: language === 'auto' ? 'en' : language,
        fourStems,
        features: ['f0'],  // Enable pitch detection for karaoke
        referenceLyrics: referenceLyrics || null,  // Pass pre-fetched lyrics to avoid second lookup
        llm: {
          enabled: llmSettings.enabled !== undefined ? llmSettings.enabled : true,
          provider: llmSettings.provider || null,
          model: llmSettings.provider === 'claude' ? llmSettings.claudeModel :
                 llmSettings.provider === 'openai' ? llmSettings.openaiModel :
                 llmSettings.provider === 'gemini' ? llmSettings.geminiModel : null,
          apiKey: llmSettings.provider === 'claude' ? llmSettings.claudeApiKey :
                  llmSettings.provider === 'openai' ? llmSettings.openaiApiKey :
                  llmSettings.provider === 'gemini' ? llmSettings.geminiApiKey : null,
          baseUrl: llmSettings.provider === 'local' ?
                   `http://${llmSettings.localLlmHost || 'localhost'}:${llmSettings.localLlmPort || '1234'}` : null,
        },
      };

      const processingResult = await window.electronAPI.processAudio(options);

      if (processingResult.success) {
        setResult(processingResult);
        setError(null);
      } else {
        setError(processingResult.error || 'Processing failed');
        setResult(null);
      }
    } catch (err) {
      setError(err.message || 'An unexpected error occurred');
      setResult(null);
    } finally {
      setIsProcessing(false);
      setProgress(null);
      setLiveLyric(null); // Clear live lyric when processing completes
      setWhisperProgress(null); // Clear Whisper progress when processing completes
      if (unsubscribe) unsubscribe();
    }
  }

  // Get progress percentage
  function getProgressPercent() {
    if (!progress) return 0;
    return progress.percent || 0;
  }

  // Get progress message
  function getProgressMessage() {
    if (!progress) return '';
    // Show stem-specific messages from Demucs tqdm parsing (e.g., "Separating Vocals stem...")
    // These come through as stage='demucs' with per-stem messages
    return progress.message || progress.stage || '';
  }

  // Check if we're in Whisper transcription (indeterminate progress)
  function isWhisperStage() {
    if (!progress) return false;
    return progress.stage === 'step_4' || progress.message?.includes('Transcribing');
  }

  // Format seconds as MM:SS
  function formatTime(seconds) {
    if (!seconds) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  }

  // Get Whisper progress percentage
  function getWhisperProgressPercent() {
    if (!whisperProgress?.currentTime || !songDuration) return 0;
    return Math.min(100, (whisperProgress.currentTime / songDuration) * 100);
  }

  // Get confidence color for progress bar
  function getConfidenceColor() {
    const confidence = whisperProgress?.confidence;
    if (!confidence) return 'bg-blue-600'; // Default blue
    if (confidence >= 0.7) return 'bg-blue-600'; // High confidence: blue
    if (confidence >= 0.5) return 'bg-cyan-500'; // Medium confidence: cyan
    return 'bg-gray-500'; // Low confidence: gray
  }

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <h1 className="text-3xl font-bold mb-6">🎵 Convert Audio to Karaoke</h1>

      {/* Input Mode Toggle */}
      <div className="card p-6 mb-6">
        <div className="flex gap-2 mb-4">
          <button
            onClick={() => setInputMode('file')}
            className={`flex-1 py-2 px-4 rounded-lg font-medium transition-colors ${
              inputMode === 'file'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600'
            }`}
          >
            📁 Audio File
          </button>
          <button
            onClick={() => setInputMode('youtube')}
            className={`flex-1 py-2 px-4 rounded-lg font-medium transition-colors ${
              inputMode === 'youtube'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600'
            }`}
          >
            📺 YouTube URL
          </button>
        </div>

        {/* File Upload Mode */}
        {inputMode === 'file' && (
          <div
            className={`border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition-colors ${
              isDragging
                ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                : 'border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500'
            }`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={handleSelectFile}
          >
            <p className="text-4xl mb-4">🎵</p>
            {inputFile ? (
              <>
                <p className="text-lg mb-2 text-gray-700 dark:text-gray-300 font-medium">
                  {inputFile.split('/').pop().split('\\').pop()}
                </p>
                <p className="text-sm text-gray-500 dark:text-gray-400">Click to change file</p>
              </>
            ) : (
              <>
                <p className="text-lg mb-2 text-gray-700 dark:text-gray-300">
                  Drop audio file here or click to browse
                </p>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  Supported: MP3, WAV, FLAC, M4A, OGG
                </p>
              </>
            )}
          </div>
        )}

        {/* YouTube URL Mode */}
        {inputMode === 'youtube' && (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-2">YouTube URL *</label>
              <input
                type="text"
                value={youtubeUrl}
                onChange={(e) => setYoutubeUrl(e.target.value)}
                className="input w-full"
                placeholder="https://youtube.com/watch?v=... or https://youtu.be/..."
                disabled={isProcessing}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-2">Artist Name *</label>
                <input
                  type="text"
                  value={youtubeArtist}
                  onChange={(e) => setYoutubeArtist(e.target.value)}
                  className="input w-full"
                  placeholder="e.g., Queen"
                  disabled={isProcessing}
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">Song Title *</label>
                <input
                  type="text"
                  value={youtubeTitle}
                  onChange={(e) => setYoutubeTitle(e.target.value)}
                  className="input w-full"
                  placeholder="e.g., Bohemian Rhapsody"
                  disabled={isProcessing}
                />
              </div>
            </div>

            {/* Search for Lyrics Button */}
            {!lyricsStatus && (
              <button
                onClick={processYoutubeUrl}
                disabled={!youtubeTitle || !youtubeArtist || isProcessing}
                className={`w-full py-2 px-4 rounded-lg font-medium transition-colors ${
                  !youtubeTitle || !youtubeArtist || isProcessing
                    ? 'bg-gray-300 dark:bg-gray-700 text-gray-500 dark:text-gray-400 cursor-not-allowed'
                    : 'btn-primary'
                }`}
              >
                🔍 Search for Lyrics
              </button>
            )}

            {/* Lyrics Status for YouTube Mode */}
            {lyricsStatus && (
              <div className="border-t pt-4">
                {lyricsStatus === 'loading' && (
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    🔍 Looking up reference lyrics on LRCLIB...
                  </p>
                )}

                {lyricsStatus === 'found' && (
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <p className="text-sm text-green-600 dark:text-green-400 font-medium">
                        ✓ Found reference lyrics - will improve transcription accuracy
                      </p>
                      <button
                        onClick={() => setShowLyricsDisplay(!showLyricsDisplay)}
                        className="text-sm px-3 py-1 text-blue-600 dark:text-blue-400 hover:underline"
                      >
                        {showLyricsDisplay ? 'Hide' : 'Show'}
                      </button>
                    </div>
                    {showLyricsDisplay && referenceLyrics && (
                      <div className="border border-gray-300 dark:border-gray-600 rounded-lg p-3 bg-gray-50 dark:bg-gray-800/50">
                        <pre className="text-xs font-mono text-gray-700 dark:text-gray-300 whitespace-pre-wrap max-h-48 overflow-y-auto">
                          {referenceLyrics}
                        </pre>
                      </div>
                    )}
                  </div>
                )}

                {lyricsStatus === 'not-found' && (
                  <div>
                    <p className="text-sm text-yellow-600 dark:text-yellow-400 font-medium mb-2">
                      ⚠ No reference lyrics found on LRCLIB
                    </p>
                    <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
                      You can paste lyrics manually below to improve transcription accuracy (optional):
                    </p>
                    <textarea
                      className="input w-full h-32 font-mono text-sm"
                      placeholder="Paste plain text lyrics here...&#10;&#10;Example:&#10;Hello darkness my old friend&#10;I've come to talk with you again..."
                      value={manualLyrics}
                      onChange={(e) => {
                        setManualLyrics(e.target.value);
                        if (e.target.value.trim()) {
                          setReferenceLyrics(e.target.value);
                        } else {
                          setReferenceLyrics(null);
                        }
                      }}
                    />
                    {manualLyrics.trim() && (
                      <p className="text-sm text-green-600 dark:text-green-400 mt-2">
                        ✓ Lyrics added - will improve accuracy
                      </p>
                    )}
                  </div>
                )}
              </div>
            )}

            <p className="text-xs text-gray-500 dark:text-gray-400">
              * Required fields. Title and artist are used for metadata and lyrics lookup.
            </p>
          </div>
        )}

        <input
          ref={fileInputRef}
          type="file"
          accept=".mp3,.wav,.flac,.m4a,.ogg"
          className="hidden"
        />
      </div>

      {/* Lyrics Status */}
      {((inputMode === 'file' && inputFile) || (inputMode === 'youtube' && youtubeTitle && youtubeArtist)) && lyricsStatus && (
        <div className="card p-4 mb-6">
          {lyricsStatus === 'loading' && (
            <p className="text-sm text-gray-600 dark:text-gray-400">
              🔍 Looking up reference lyrics on LRCLIB...
            </p>
          )}
          {lyricsStatus === 'found' && (
            <div>
              <div className="flex items-center justify-between">
                <p className="text-sm text-green-600 dark:text-green-400">
                  ✓ Found reference lyrics - will improve transcription accuracy
                </p>
                <button
                  onClick={() => setShowLyricsDisplay(!showLyricsDisplay)}
                  className="text-sm px-3 py-1 text-blue-600 dark:text-blue-400 hover:underline"
                >
                  {showLyricsDisplay ? 'Hide lyrics' : 'Show lyrics'}
                </button>
              </div>
              {showLyricsDisplay && referenceLyrics && (
                <div className="mt-3 border border-gray-300 dark:border-gray-600 rounded-lg p-3 bg-gray-50 dark:bg-gray-800/50">
                  <pre className="text-xs font-mono text-gray-700 dark:text-gray-300 whitespace-pre-wrap max-h-48 overflow-y-auto">
                    {referenceLyrics}
                  </pre>
                </div>
              )}
            </div>
          )}
          {lyricsStatus === 'not-found' && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm text-yellow-600 dark:text-yellow-400">
                  ⚠ No reference lyrics found on LRCLIB
                </p>
                {!showLyricsInput && (
                  <button
                    onClick={() => setShowLyricsInput(true)}
                    className="text-sm px-3 py-1 text-blue-600 dark:text-blue-400 hover:underline"
                  >
                    Paste lyrics manually
                  </button>
                )}
              </div>
              {showLyricsInput && (
                <div className="mt-3">
                  <label className="block text-sm font-medium mb-2">
                    Paste lyrics to improve transcription accuracy (optional):
                  </label>
                  <textarea
                    className="input w-full h-32 font-mono text-sm"
                    placeholder="Paste plain text lyrics here...&#10;&#10;Example:&#10;Hello darkness my old friend&#10;I've come to talk with you again..."
                    value={manualLyrics}
                    onChange={(e) => {
                      setManualLyrics(e.target.value);
                      if (e.target.value.trim()) {
                        setReferenceLyrics(e.target.value);
                      } else {
                        setReferenceLyrics(null);
                      }
                    }}
                  />
                  <div className="flex gap-2 mt-2">
                    <button
                      onClick={() => {
                        setManualLyrics('');
                        setReferenceLyrics(null);
                        setShowLyricsInput(false);
                      }}
                      className="text-sm px-3 py-1 text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
                    >
                      Clear
                    </button>
                    {manualLyrics.trim() && (
                      <p className="text-sm text-green-600 dark:text-green-400 self-center">
                        ✓ Lyrics added - will improve accuracy
                      </p>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
          {lyricsStatus === 'no-metadata' && (
            <p className="text-sm text-gray-600 dark:text-gray-400">
              ℹ Missing title/artist metadata - cannot look up reference lyrics
            </p>
          )}
        </div>
      )}

      {/* Output Path */}
      {((inputMode === 'file' && inputFile) || (inputMode === 'youtube' && youtubeUrl && youtubeTitle && youtubeArtist)) && (
        <div className="card p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">Output File</h2>
          <div className="flex gap-2">
            <input
              type="text"
              value={outputFile || ''}
              onChange={(e) => setOutputFile(e.target.value)}
              className="input flex-1"
              placeholder="Output file path"
            />
            <button
              onClick={handleSelectOutputFolder}
              className="px-4 py-2 border rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700"
            >
              Browse
            </button>
          </div>
        </div>
      )}

      {/* Options */}
      <div className="card p-6 mb-6">
        <h2 className="text-lg font-semibold mb-4">Processing Options</h2>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium mb-2">Whisper (lyric detection) Model</label>
            <select
              className="input w-full"
              value={whisperModel}
              onChange={(e) => setWhisperModel(e.target.value)}
              disabled={isProcessing}
            >
              <option value="tiny">tiny (fastest, least accurate)</option>
              <option value="base">base</option>
              <option value="small">small (fast)</option>
              <option value="medium">medium</option>
              <option value="large-v3">large-v3 (best quality)</option>
              <option value="large-v3-turbo">large-v3-turbo (recommended)</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium mb-2">Language</label>
            <select
              className="input w-full"
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              disabled={isProcessing}
            >
              <option value="auto">Auto-detect</option>
              <option value="en">English</option>
              <option value="es">Spanish</option>
              <option value="fr">French</option>
              <option value="de">German</option>
              <option value="it">Italian</option>
              <option value="pt">Portuguese</option>
              <option value="ja">Japanese</option>
              <option value="ko">Korean</option>
              <option value="zh">Chinese</option>
            </select>
          </div>
        </div>

        <div className="mt-4">
          <p className="text-sm font-medium mb-2">Stem Separation</p>
          <label className="flex items-center">
            <input
              type="radio"
              name="stems"
              checked={!fourStems}
              onChange={() => setFourStems(false)}
              disabled={isProcessing}
              className="mr-2"
            />
            <span>2-stem (vocals + music) - Smaller file</span>
          </label>
          <label className="flex items-center mt-2">
            <input
              type="radio"
              name="stems"
              checked={fourStems}
              onChange={() => setFourStems(true)}
              disabled={isProcessing}
              className="mr-2"
            />
            <span>4-stem (vocals + drums + bass + other)</span>
          </label>
        </div>

        <div className="mt-4">
          <p className="text-sm font-medium mb-2">Output Format</p>
          <label className="flex items-center">
            <input
              type="radio"
              name="format"
              checked={outputFormat === 'kai'}
              onChange={() => setOutputFormat('kai')}
              disabled={isProcessing}
              className="mr-2"
            />
            <span>KAI (ZIP) - Smaller file (~16 MB), kai-player only</span>
          </label>
          <label className="flex items-center mt-2">
            <input
              type="radio"
              name="format"
              checked={outputFormat === 'm4a'}
              onChange={() => setOutputFormat('m4a')}
              disabled={isProcessing}
              className="mr-2"
            />
            <span>M4A Stems - Universal format (~34 MB), works in DJ software</span>
          </label>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
            M4A format: Compatible with Mixxx, Traktor, and kai-player. Uses NI Stems + karaoke extensions.
          </p>
        </div>
      </div>

      {/* Progress */}
      {isProcessing && (
        <div className="card p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">Processing...</h2>
          <div className="space-y-2">
            <div className="flex justify-between text-sm mb-1">
              <span>{getProgressMessage()}</span>
              {/* Show time-based progress during Whisper if we have duration */}
              {isWhisperStage() && whisperProgress?.currentTime && songDuration ? (
                <span>
                  {formatTime(whisperProgress.currentTime)} / {formatTime(songDuration)} ({Math.round(getWhisperProgressPercent())}%)
                </span>
              ) : !isWhisperStage() ? (
                <span>{Math.round(getProgressPercent())}%</span>
              ) : null}
            </div>
            <div className="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
              {isWhisperStage() && whisperProgress?.currentTime && songDuration ? (
                // Time-based progress with confidence coloring
                <div
                  className={`h-2 rounded-full transition-all ${getConfidenceColor()}`}
                  style={{ width: `${getWhisperProgressPercent()}%` }}
                />
              ) : isWhisperStage() ? (
                // Indeterminate shimmer when we don't have duration yet
                <div className="h-2 bg-gradient-to-r from-blue-400 via-blue-600 to-blue-400 rounded-full animate-pulse bg-[length:200%_100%]"
                     style={{ animation: 'pulse 1.5s ease-in-out infinite, shimmer 2s linear infinite', width: '100%' }}>
                  <style>{`
                    @keyframes shimmer {
                      0% { background-position: -200% 0; }
                      100% { background-position: 200% 0; }
                    }
                  `}</style>
                </div>
              ) : (
                // Regular determinate progress for other stages
                <div
                  className="h-2 bg-blue-600 rounded-full transition-all"
                  style={{ width: `${getProgressPercent()}%` }}
                />
              )}
            </div>
            {/* Live lyrics and confidence during Whisper transcription */}
            {isWhisperStage() && (liveLyric || whisperProgress?.confidence !== undefined) && (
              <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-700 space-y-1">
                {liveLyric && (
                  <p className="text-xs text-gray-500 dark:text-gray-400 italic truncate">
                    🎤 {liveLyric.length > 100 ? liveLyric.substring(0, 100) + '...' : liveLyric}
                  </p>
                )}
                {whisperProgress?.confidence !== undefined && (
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    Confidence: {Math.round(whisperProgress.confidence * 100)}%
                    <span className={`ml-2 ${whisperProgress.confidence >= 0.7 ? 'text-blue-600 dark:text-blue-400' : whisperProgress.confidence >= 0.5 ? 'text-cyan-600 dark:text-cyan-400' : 'text-gray-600 dark:text-gray-400'}`}>
                      {whisperProgress.confidence >= 0.7 ? '(High)' : whisperProgress.confidence >= 0.5 ? '(Medium)' : '(Low)'}
                    </span>
                  </p>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Result */}
      {result && (
        <div className="card p-6 mb-6 bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800">
          <h2 className="text-lg font-semibold mb-2 text-green-800 dark:text-green-300">
            ✓ Conversion Complete!
          </h2>

          {/* AI Correction Warning */}
          {result.llm_stats && result.llm_stats.failed && (
            <div className="mb-3 p-3 bg-yellow-100 dark:bg-yellow-900/30 border border-yellow-300 dark:border-yellow-700 rounded-lg">
              <p className="text-sm text-yellow-800 dark:text-yellow-200">
                <strong>⚠ AI lyric correction failed:</strong> {result.llm_stats.error || 'Unknown error'}
              </p>
              <p className="text-xs text-yellow-700 dark:text-yellow-300 mt-1">
                Lyrics were transcribed but not corrected by AI. Check your API key in Settings if you want AI correction.
              </p>
            </div>
          )}

          <div className="space-y-1 text-sm">
            <p className="text-gray-700 dark:text-gray-300">
              <strong>Output file:</strong> {result.output_file}
            </p>
            {result.processing_time && result.input_info && (
              <p className="text-gray-600 dark:text-gray-400">
                Song duration: {Math.round(result.input_info.duration_seconds)}s |
                Processing time: {Math.round(result.processing_time)}s |
                Speed: {Math.round((result.input_info.duration_seconds / result.processing_time) * 100)}%
              </p>
            )}
            {result.stats && (
              <div className="mt-2 text-gray-600 dark:text-gray-400">
                <p>Stems: {fourStems ? '4 (vocals, drums, bass, other)' : '2 (vocals, music)'}</p>
                {result.stats.lines > 0 && (
                  <p>
                    Lyrics: {result.stats.lines} lines transcribed
                    {result.llm_stats && result.llm_stats.failed && (
                      <span className="ml-2 text-red-600 dark:text-red-400">
                        (AI correction failed: {result.llm_stats.error || 'Unknown error'})
                      </span>
                    )}
                    {result.llm_stats && !result.llm_stats.failed && (
                      <span className={`ml-2 ${result.llm_stats.corrections_applied > 0 ? 'text-green-600 dark:text-green-400' : 'text-gray-600 dark:text-gray-400'}`}>
                        (AI: {result.llm_stats.corrections_applied} corrected, {result.llm_stats.suggestions_made} suggestions, {result.llm_stats.corrections_rejected} rejected)
                      </span>
                    )}
                  </p>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="card p-6 mb-6 bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800">
          <h2 className="text-lg font-semibold mb-2 text-red-800 dark:text-red-300">
            ✗ Conversion Failed
          </h2>
          <p className="text-sm text-red-700 dark:text-red-400">{error}</p>
        </div>
      )}

      {/* Action Button */}
      <button
        onClick={handleConvert}
        disabled={(inputMode === 'file' && !inputFile) || (inputMode === 'youtube' && (!youtubeUrl || !youtubeTitle || !youtubeArtist)) || isProcessing}
        className={`w-full text-lg py-3 rounded-lg font-medium transition-colors ${
          ((inputMode === 'file' && !inputFile) || (inputMode === 'youtube' && (!youtubeUrl || !youtubeTitle || !youtubeArtist)) || isProcessing)
            ? 'bg-gray-300 dark:bg-gray-700 text-gray-500 dark:text-gray-400 cursor-not-allowed'
            : 'btn-primary'
        }`}
      >
        {isProcessing ? 'Processing...' : outputFormat === 'm4a' ? 'Convert to M4A Stems' : 'Convert to KAI'}
      </button>

      {((inputMode === 'file' && inputFile) || (inputMode === 'youtube' && youtubeUrl)) && !isProcessing && (
        <button
          onClick={() => {
            setInputFile(null);
            setYoutubeUrl('');
            setYoutubeTitle('');
            setYoutubeArtist('');
            setOutputFile(null);
            setResult(null);
            setError(null);
            setLyricsStatus(null);
            setReferenceLyrics(null);
            setManualLyrics('');
            setShowLyricsInput(false);
            setShowLyricsDisplay(false);
          }}
          className="w-full mt-2 text-sm py-2 text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
        >
          Clear and start over
        </button>
      )}
    </div>
  );
}
