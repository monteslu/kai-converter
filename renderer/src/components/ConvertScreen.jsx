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
        // Store LLM settings for later use
        window._kaiLlmSettings = settings.llm;
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
          setInputFile(filePath);
          setResult(null);
          setError(null);
          // Auto-generate output file path
          const kaiPath = filePath.replace(/\.[^.]+$/, '.kai');
          setOutputFile(kaiPath);
        }
      }
    } catch (error) {
      console.error('File selection error:', error);
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

  function handleDrop(e) {
    e.preventDefault();
    setIsDragging(false);

    const files = e.dataTransfer?.files;
    if (files && files.length > 0) {
      const file = files[0];
      // In Electron, we get the file path from the File object
      const filePath = file.path;
      if (filePath) {
        setInputFile(filePath);
        setResult(null);
        setError(null);
        const kaiPath = filePath.replace(/\.[^.]+$/, '.kai');
        setOutputFile(kaiPath);
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
      // Get LLM settings from stored state
      const llmSettings = window._kaiLlmSettings || {};

      const options = {
        inputFile,
        outputFile,
        whisperModel,
        language: language === 'auto' ? 'en' : language,
        fourStems,
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
            <span>2-stem (vocals + music) - Faster</span>
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
            <span>4-stem (vocals + drums + bass + other) - Better quality</span>
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
              <span>{Math.round(getProgressPercent())}%</span>
            </div>
            <div className="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
              <div
                className="h-2 bg-blue-600 rounded-full transition-all"
                style={{ width: `${getProgressPercent()}%` }}
              />
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
            {result.processing_time && (
              <p className="text-gray-600 dark:text-gray-400">
                Processing time: {Math.round(result.processing_time)}s
              </p>
            )}
            {result.stats && (
              <div className="mt-2 text-gray-600 dark:text-gray-400">
                <p>Stems: {result.stats.stems}</p>
                {result.stats.lyrics_count > 0 && (
                  <p>Lyrics: {result.stats.lyrics_count} lines transcribed</p>
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
