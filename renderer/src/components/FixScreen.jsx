import { useState, useEffect } from 'react';

export default function FixScreen() {
  const [inputFile, setInputFile] = useState(null);
  const [kaiMetadata, setKaiMetadata] = useState(null);
  const [outputFile, setOutputFile] = useState(null);
  const [whisperModel, setWhisperModel] = useState('large-v3-turbo');
  const [language, setLanguage] = useState('auto');
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
      }
    } catch (error) {
      console.error('Failed to load settings:', error);
    }
  }

  // Handle KAI file selection
  async function handleSelectFile() {
    try {
      if (window.electronAPI) {
        const filePath = await window.electronAPI.selectKaiFile();
        if (filePath) {
          await processKaiFile(filePath);
        }
      }
    } catch (error) {
      console.error('File selection error:', error);
    }
  }

  // Process KAI file - read metadata and fetch lyrics
  async function processKaiFile(filePath) {
    setInputFile(filePath);
    setResult(null);
    setError(null);
    setLyricsStatus(null);
    setReferenceLyrics(null);
    setManualLyrics('');
    setShowLyricsInput(false);
    setShowLyricsDisplay(false);
    setKaiMetadata(null);

    // Auto-generate output file path (default to overwriting)
    setOutputFile(filePath);

    try {
      // Read KAI metadata
      const metadata = await window.electronAPI.readKaiMetadata(filePath);
      setKaiMetadata(metadata);
      console.log('KAI metadata:', metadata);

      const title = metadata.song?.title;
      const artist = metadata.song?.artist;

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
    } catch (err) {
      console.error('Failed to read KAI metadata:', err);
      setError('Failed to read KAI file metadata: ' + err.message);
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
      const filePath = file.path;
      if (filePath && filePath.endsWith('.kai')) {
        await processKaiFile(filePath);
      } else {
        setError('Please drop a .kai file');
      }
    }
  }

  // Regenerate lyrics with Whisper
  async function handleRegenerateLyrics() {
    if (!inputFile) {
      setError('Please select a KAI file');
      return;
    }

    setIsProcessing(true);
    setProgress(null);
    setResult(null);
    setError(null);

    const unsubscribe = window.electronAPI?.onProgress((progressUpdate) => {
      setProgress(progressUpdate);
    });

    try {
      const settings = await window.electronAPI.loadSettings();
      const llmSettings = settings.llm || {};

      const options = {
        inputFile,
        outputFile,
        whisperModel,
        language: language === 'auto' ? 'en' : language,
        referenceLyrics: referenceLyrics || null,
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

      const processingResult = await window.electronAPI.regenerateLyrics(options);

      if (processingResult.success) {
        setResult(processingResult);
        setError(null);
      } else {
        setError(processingResult.error || 'Lyrics regeneration failed');
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

  // Fix lyrics with LLM only
  async function handleFixLyrics() {
    if (!inputFile) {
      setError('Please select a KAI file');
      return;
    }

    setIsProcessing(true);
    setProgress({ message: 'Fixing lyrics with LLM...', percent: 50 });
    setResult(null);
    setError(null);

    try {
      const settings = await window.electronAPI.loadSettings();
      const llmSettings = settings.llm || {};

      if (!llmSettings.enabled || !llmSettings.provider) {
        setError('LLM is not configured. Please configure LLM settings first.');
        setIsProcessing(false);
        setProgress(null);
        return;
      }

      const options = {
        inputFile,
        outputFile,
        referenceLyrics: referenceLyrics || null,
        llm: {
          enabled: true,
          provider: llmSettings.provider,
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

      const processingResult = await window.electronAPI.fixLyrics(options);

      if (processingResult.success) {
        setResult(processingResult);
        setError(null);
      } else {
        setError(processingResult.error || 'Lyrics correction failed');
        setResult(null);
      }
    } catch (err) {
      setError(err.message || 'An unexpected error occurred');
      setResult(null);
    } finally {
      setIsProcessing(false);
      setProgress(null);
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
      <h1 className="text-3xl font-bold mb-6">🔧 Fix KAI File</h1>

      {/* File Upload */}
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
          <p className="text-4xl mb-4">📦</p>
          {inputFile ? (
            <>
              <p className="text-lg mb-2 text-gray-700 dark:text-gray-300 font-medium">
                {inputFile.split('/').pop().split('\\').pop()}
              </p>
              {kaiMetadata && (
                <div className="mt-3 text-sm text-gray-600 dark:text-gray-400">
                  <p><strong>Title:</strong> {kaiMetadata.song?.title || 'Unknown'}</p>
                  <p><strong>Artist:</strong> {kaiMetadata.song?.artist || 'Unknown'}</p>
                  <p><strong>Stems:</strong> {kaiMetadata.audio?.profile || 'Unknown'}</p>
                  {kaiMetadata.lines && (
                    <p><strong>Current lyrics:</strong> {kaiMetadata.lines.length} lines</p>
                  )}
                </div>
              )}
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-3">Click to change file</p>
            </>
          ) : (
            <>
              <p className="text-lg mb-2 text-gray-700 dark:text-gray-300">
                Drop .kai file here or click to browse
              </p>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Select a KAI file to fix its lyrics
              </p>
            </>
          )}
        </div>
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
                  ✓ Found reference lyrics - will improve correction accuracy
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
                    Paste lyrics to improve correction accuracy (optional):
                  </label>
                  <textarea
                    className="input w-full h-32 font-mono text-sm"
                    placeholder="Paste plain text lyrics here..."
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
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
            Leave as-is to overwrite the original file, or change to save a new copy
          </p>
        </div>
      )}

      {/* Options for Regenerate Lyrics */}
      {inputFile && (
        <div className="card p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">Regenerate Options (for full re-transcription)</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-2">Whisper Model</label>
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
        </div>
      )}

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
            ✓ Processing Complete!
          </h2>
          <div className="space-y-1 text-sm">
            <p className="text-gray-700 dark:text-gray-300">
              <strong>Output file:</strong> {result.output_file}
            </p>

            {/* Fix Lyrics results */}
            {result.corrections_count !== undefined && (
              <div className="mt-2 text-gray-600 dark:text-gray-400">
                <p>
                  <strong>LLM Correction Results:</strong>
                </p>
                <ul className="list-disc list-inside ml-2 mt-1">
                  <li className={result.corrections_count > 0 ? 'text-green-600 dark:text-green-400' : ''}>
                    {result.corrections_count} correction{result.corrections_count !== 1 ? 's' : ''} applied
                  </li>
                  {result.rejections_count > 0 && (
                    <li className="text-yellow-600 dark:text-yellow-400">
                      {result.rejections_count} questionable correction{result.rejections_count !== 1 ? 's' : ''} rejected
                    </li>
                  )}
                  {result.missing_lines_count > 0 && (
                    <li className="text-blue-600 dark:text-blue-400">
                      {result.missing_lines_count} missing line{result.missing_lines_count !== 1 ? 's' : ''} suggested
                    </li>
                  )}
                </ul>
              </div>
            )}

            {/* Regenerate Lyrics results */}
            {result.lines_count !== undefined && (
              <div className="mt-2 text-gray-600 dark:text-gray-400">
                <p>
                  <strong>Re-transcription Results:</strong>
                </p>
                <p className="ml-2 mt-1">
                  {result.lines_count} lyric line{result.lines_count !== 1 ? 's' : ''} generated
                </p>
              </div>
            )}

            {/* Legacy format support */}
            {result.stats && result.stats.lines > 0 && (
              <div className="mt-2 text-gray-600 dark:text-gray-400">
                <p>
                  Lyrics: {result.stats.lines} lines
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
              </div>
            )}
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="card p-6 mb-6 bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800">
          <h2 className="text-lg font-semibold mb-2 text-red-800 dark:text-red-300">
            ✗ Processing Failed
          </h2>
          <p className="text-sm text-red-700 dark:text-red-400">{error}</p>
        </div>
      )}

      {/* Action Buttons */}
      <div className="grid grid-cols-2 gap-4">
        <button
          onClick={handleRegenerateLyrics}
          disabled={!inputFile || isProcessing}
          className={`text-lg py-3 rounded-lg font-medium transition-colors ${
            !inputFile || isProcessing
              ? 'bg-gray-300 dark:bg-gray-700 text-gray-500 dark:text-gray-400 cursor-not-allowed'
              : 'bg-purple-600 hover:bg-purple-700 text-white'
          }`}
        >
          {isProcessing ? 'Processing...' : '🎤 Regenerate Lyrics (Full Whisper)'}
        </button>
        <button
          onClick={handleFixLyrics}
          disabled={!inputFile || isProcessing || !referenceLyrics}
          className={`text-lg py-3 rounded-lg font-medium transition-colors ${
            !inputFile || isProcessing || !referenceLyrics
              ? 'bg-gray-300 dark:bg-gray-700 text-gray-500 dark:text-gray-400 cursor-not-allowed'
              : 'bg-blue-600 hover:bg-blue-700 text-white'
          }`}
          title={!referenceLyrics ? 'Reference lyrics required for LLM correction' : ''}
        >
          {isProcessing ? 'Processing...' : '✨ Fix Lyrics (LLM Only)'}
        </button>
      </div>

      {/* Help text for disabled Fix Lyrics button */}
      {inputFile && !referenceLyrics && !isProcessing && (
        <p className="text-sm text-yellow-600 dark:text-yellow-400 mt-2 text-center">
          ℹ️ Fix Lyrics requires reference lyrics. Search for them above or paste manually.
        </p>
      )}

      {inputFile && !isProcessing && (
        <button
          onClick={() => {
            setInputFile(null);
            setKaiMetadata(null);
            setOutputFile(null);
            setResult(null);
            setError(null);
            setLyricsStatus(null);
            setReferenceLyrics(null);
            setManualLyrics('');
            setShowLyricsInput(false);
            setShowLyricsDisplay(false);
          }}
          className="w-full mt-4 text-sm py-2 text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
        >
          Clear and start over
        </button>
      )}
    </div>
  );
}
