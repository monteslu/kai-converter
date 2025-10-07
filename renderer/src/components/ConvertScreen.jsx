import { useState, useEffect, useRef } from 'react';

export default function ConvertScreen() {
  const [inputFile, setInputFile] = useState(null);
  const [outputFile, setOutputFile] = useState(null);
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
  const fileInputRef = useRef(null);

  // Load settings on mount
  useEffect(() => {
    loadSettings();
  }, []);

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

    // Auto-generate output file path
    const kaiPath = filePath.replace(/\.[^.]+$/, '.kai');
    setOutputFile(kaiPath);

    // Read metadata
    const metadata = await window.electronAPI.readAudioMetadata(filePath);
    console.log('Metadata result:', metadata);
    const title = metadata.title;
    const artist = metadata.artist;

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

  // Handle output folder selection
  async function handleSelectOutputFolder() {
    try {
      if (window.electronAPI) {
        const folderPath = await window.electronAPI.selectOutputFolder();
        if (folderPath && inputFile) {
          const fileName = inputFile.split('/').pop().split('\\').pop();
          const kaiFileName = fileName.replace(/\.[^.]+$/, '.kai');
          setOutputFile(`${folderPath}/${kaiFileName}`);
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
    if (!inputFile) {
      setError('Please select an input file');
      return;
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
        inputFile,
        outputFile,
        whisperModel,
        language: language === 'auto' ? 'en' : language,
        fourStems,
        features: ['f0', 'tempo'],  // Enable musical analysis by default
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
    return progress.message || progress.stage || '';
  }

  // Check if we're in Whisper transcription (indeterminate progress)
  function isWhisperStage() {
    if (!progress) return false;
    return progress.stage === 'step_4' || progress.message?.includes('Transcribing');
  }

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <h1 className="text-3xl font-bold mb-6">🎵 Convert Audio to KAI</h1>

      {/* Drop Zone */}
      <div className="card p-6 mb-6">
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
        <input
          ref={fileInputRef}
          type="file"
          accept=".mp3,.wav,.flac,.m4a,.ogg"
          className="hidden"
        />
      </div>

      {/* Lyrics Status */}
      {inputFile && lyricsStatus && (
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
      {inputFile && (
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
            <span>2-stem (vocals + music) - Smaller KAI file</span>
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
      </div>

      {/* Progress */}
      {isProcessing && (
        <div className="card p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">Processing...</h2>
          <div className="space-y-2">
            <div className="flex justify-between text-sm mb-1">
              <span>{getProgressMessage()}</span>
              {!isWhisperStage() && <span>{Math.round(getProgressPercent())}%</span>}
            </div>
            <div className="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
              {isWhisperStage() ? (
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
                <div
                  className="h-2 bg-blue-600 rounded-full transition-all"
                  style={{ width: `${getProgressPercent()}%` }}
                />
              )}
            </div>
          </div>
        </div>
      )}

      {/* Result */}
      {result && (
        <div className="card p-6 mb-6 bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800">
          <h2 className="text-lg font-semibold mb-2 text-green-800 dark:text-green-300">
            ✓ Conversion Complete!
          </h2>
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
        disabled={!inputFile || isProcessing}
        className={`w-full text-lg py-3 rounded-lg font-medium transition-colors ${
          !inputFile || isProcessing
            ? 'bg-gray-300 dark:bg-gray-700 text-gray-500 dark:text-gray-400 cursor-not-allowed'
            : 'btn-primary'
        }`}
      >
        {isProcessing ? 'Processing...' : 'Convert to KAI'}
      </button>

      {inputFile && !isProcessing && (
        <button
          onClick={() => {
            setInputFile(null);
            setOutputFile(null);
            setResult(null);
            setError(null);
          }}
          className="w-full mt-2 text-sm py-2 text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
        >
          Clear and start over
        </button>
      )}
    </div>
  );
}
