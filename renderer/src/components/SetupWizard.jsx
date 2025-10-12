import { useState, useEffect } from 'react';

export default function SetupWizard({ onComplete }) {
  const [step, setStep] = useState(1);
  const [systemInfo, setSystemInfo] = useState(null);
  const [checking, setChecking] = useState(true);
  const [selectedWhisperModel, setSelectedWhisperModel] = useState('large-v3-turbo');
  const [selectedPyTorchVariant, setSelectedPyTorchVariant] = useState('cpu');
  const [downloads, setDownloads] = useState([]);
  const [downloadProgress, setDownloadProgress] = useState({});
  const [downloadResults, setDownloadResults] = useState({});
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadComplete, setDownloadComplete] = useState(false);

  // LLM settings
  const [llmEnabled, setLlmEnabled] = useState(true);
  const [llmProvider, setLlmProvider] = useState('claude');
  const [claudeApiKey, setClaudeApiKey] = useState('');
  const [openaiApiKey, setOpenaiApiKey] = useState('');
  const [geminiApiKey, setGeminiApiKey] = useState('');

  const steps = [
    { id: 1, title: 'System Check', description: 'Checking requirements...' },
    { id: 2, title: 'Model Selection', description: 'Choose models to download' },
    { id: 3, title: 'LLM Setup', description: 'Configure lyric correction (optional)' },
    { id: 4, title: 'Downloading', description: 'Downloading models...' },
    { id: 5, title: 'Complete', description: 'Setup complete!' },
  ];

  // Whisper model options
  const whisperModels = [
    { name: 'tiny', size: '75MB', description: 'Fastest, least accurate' },
    { name: 'base', size: '150MB', description: 'Fast' },
    { name: 'small', size: '500MB', description: 'Fast' },
    { name: 'medium', size: '1.5GB', description: 'Good accuracy' },
    { name: 'large-v3', size: '3GB', description: 'Best accuracy' },
    { name: 'large-v3-turbo', size: '1.6GB', description: '⭐ Recommended' },
  ];

  // Step 1: Check system on mount
  useEffect(() => {
    if (step === 1) {
      checkSystem();
    }
  }, [step]);

  async function checkSystem() {
    setChecking(true);
    try {
      if (window.electronAPI) {
        const info = await window.electronAPI.checkSystem();
        setSystemInfo(info);

        // Auto-select PyTorch variant based on GPU
        if (info.gpu?.available && info.gpu.type === 'cuda') {
          setSelectedPyTorchVariant('cuda');
        } else {
          setSelectedPyTorchVariant('cpu');
        }
      }
    } catch (error) {
      console.error('System check error:', error);
    } finally {
      setChecking(false);
    }
  }

  // Determine what needs to be downloaded
  function getRequiredDownloads() {
    const required = [];

    if (!systemInfo?.pytorch?.available) {
      required.push({
        component: 'pytorch',
        name: `PyTorch (${selectedPyTorchVariant.toUpperCase()})`,
        variant: selectedPyTorchVariant,
        required: true,
      });
    }

    if (!systemInfo?.demucs?.available) {
      required.push({
        component: 'demucs',
        name: 'Demucs',
        required: true,
      });
    }

    if (!systemInfo?.whisper?.available) {
      required.push({
        component: 'whisper',
        name: 'Whisper Library',
        required: true,
      });
    }

    // Always download selected Whisper model if not present
    if (!systemInfo?.whisper?.models?.includes(selectedWhisperModel)) {
      required.push({
        component: 'whisper-model',
        name: `Whisper ${selectedWhisperModel} model`,
        model: selectedWhisperModel,
        required: true,
      });
    }

    // Always download Demucs model (they're downloaded on first use)
    required.push({
      component: 'demucs-model',
      name: 'Demucs htdemucs_ft model',
      model: 'htdemucs_ft',
      required: true,
    });

    // Check for ffmpeg - REQUIRED (essential for all processing)
    if (!systemInfo?.ffmpeg?.available) {
      required.push({
        component: 'ffmpeg',
        name: 'FFmpeg',
        required: true,
      });
    }

    // Check for yt-dlp - OPTIONAL (only needed for YouTube tab)
    if (!systemInfo?.ytdlp?.available) {
      required.push({
        component: 'yt-dlp',
        name: 'yt-dlp (YouTube support)',
        required: false,
      });
    }

    return required;
  }

  // Step 3: Download components
  async function startDownloads() {
    const required = getRequiredDownloads();
    setDownloads(required);
    setIsDownloading(true);
    setDownloadComplete(false);
    setDownloadResults({});

    // Set up progress listener
    const unsubscribe = window.electronAPI?.onDownloadProgress((progress) => {
      setDownloadProgress((prev) => ({
        ...prev,
        [progress.component]: {
          percent: progress.percent || 0,
          message: progress.message || '',
          stage: progress.stage || 'preparing',
        },
      }));
    });

    const results = {};
    let hasRequiredFailures = false;

    try {
      // Download each component sequentially
      for (const download of required) {
        const options = {
          component: download.component,
          variant: download.variant,
          model: download.model,
        };

        const result = await window.electronAPI.downloadComponent(options);

        // Track result
        results[download.component] = {
          success: result.success,
          error: result.error,
          required: download.required,
        };

        if (!result.success) {
          console.error(`Failed to download ${download.name}:`, result.error);

          // Check if this was a required component
          if (download.required) {
            hasRequiredFailures = true;
          }
          // Continue with other downloads even on failure
        }
      }

      setDownloadResults(results);

      // Only mark as complete if no required components failed
      if (!hasRequiredFailures) {
        setDownloadComplete(true);
      }

      setIsDownloading(false);
    } catch (error) {
      console.error('Download error:', error);
      setIsDownloading(false);
    } finally {
      if (unsubscribe) unsubscribe();
    }
  }

  // Auto-advance to step 5 when downloads complete
  useEffect(() => {
    if (downloadComplete && step === 4) {
      setTimeout(() => setStep(5), 1000);
    }
  }, [downloadComplete, step]);

  const currentStep = steps.find((s) => s.id === step);

  return (
    <div className="h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
      <div className="card p-8 w-full max-w-2xl">
        <h1 className="text-3xl font-bold mb-2">🎵 KAI Converter Setup</h1>
        <p className="text-gray-600 dark:text-gray-400 mb-8">
          Step {step}/5: {currentStep.title}
        </p>

        {/* Progress Bar */}
        <div className="mb-8">
          <div className="flex justify-between mb-2 text-xs">
            {steps.map((s) => (
              <div
                key={s.id}
                className={`${s.id <= step ? 'text-blue-600 dark:text-blue-400 font-medium' : 'text-gray-400'}`}
              >
                {s.id}. {s.title}
              </div>
            ))}
          </div>
          <div className="h-2 bg-gray-200 dark:bg-gray-700 rounded-full">
            <div
              className="h-2 bg-blue-600 dark:bg-blue-400 rounded-full transition-all"
              style={{ width: `${(step / 5) * 100}%` }}
            />
          </div>
        </div>

        {/* Step Content */}
        <div className="mb-8">
          {/* Step 1: System Check */}
          {step === 1 && (
            <div>
              <h2 className="text-xl font-semibold mb-4">Checking System Requirements</h2>
              {checking ? (
                <div className="text-center py-8">
                  <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
                  <p className="mt-4 text-gray-600 dark:text-gray-400">Checking system...</p>
                </div>
              ) : systemInfo ? (
                <div className="space-y-2">
                  <div className="flex items-center">
                    <span className={systemInfo.python?.available ? 'text-green-600 mr-2' : 'text-red-600 mr-2'}>
                      {systemInfo.python?.available ? '✓' : '✗'}
                    </span>
                    <span>
                      Python {systemInfo.python?.available ? systemInfo.python.version : 'Not found'}
                    </span>
                  </div>
                  <div className="flex items-center">
                    <span className={systemInfo.pytorch?.available ? 'text-green-600 mr-2' : 'text-yellow-600 mr-2'}>
                      {systemInfo.pytorch?.available ? '✓' : '⚠'}
                    </span>
                    <span>
                      PyTorch {systemInfo.pytorch?.available ? systemInfo.pytorch.version : 'Not installed'}
                    </span>
                  </div>
                  <div className="flex items-center">
                    <span className={systemInfo.gpu?.available ? 'text-green-600 mr-2' : 'text-gray-400 mr-2'}>
                      {systemInfo.gpu?.available ? '✓' : 'ℹ'}
                    </span>
                    <span>
                      GPU: {systemInfo.gpu?.available ? systemInfo.gpu.type.toUpperCase() : 'CPU only'}
                    </span>
                  </div>
                  <div className="flex items-center">
                    <span className={systemInfo.demucs?.available ? 'text-green-600 mr-2' : 'text-yellow-600 mr-2'}>
                      {systemInfo.demucs?.available ? '✓' : '⚠'}
                    </span>
                    <span>Demucs {systemInfo.demucs?.available ? 'installed' : 'Not installed'}</span>
                  </div>
                  <div className="flex items-center">
                    <span className={systemInfo.whisper?.available ? 'text-green-600 mr-2' : 'text-yellow-600 mr-2'}>
                      {systemInfo.whisper?.available ? '✓' : '⚠'}
                    </span>
                    <span>
                      Whisper {systemInfo.whisper?.available
                        ? `installed (${systemInfo.whisper.models.length} models)`
                        : 'Not installed'}
                    </span>
                  </div>
                </div>
              ) : (
                <div className="text-red-600">Failed to check system</div>
              )}
            </div>
          )}

          {/* Step 2: Model Selection */}
          {step === 2 && (
            <div>
              <h2 className="text-xl font-semibold mb-4">Choose Components to Download</h2>
              <div className="space-y-6">
                {/* GPU/PyTorch Selection */}
                <div>
                  <p className="font-medium mb-2">
                    GPU: {systemInfo?.gpu?.available
                      ? `${systemInfo.gpu.type.toUpperCase()} detected`
                      : 'Not detected'}
                  </p>
                  {systemInfo?.gpu?.available && systemInfo?.gpu?.type === 'cuda' && (
                    <div className="space-y-2">
                      <label className="flex items-center">
                        <input
                          type="radio"
                          name="pytorch"
                          value="cuda"
                          checked={selectedPyTorchVariant === 'cuda'}
                          onChange={(e) => setSelectedPyTorchVariant(e.target.value)}
                          className="mr-2"
                        />
                        <span>PyTorch with CUDA (recommended for GPU)</span>
                      </label>
                      <label className="flex items-center">
                        <input
                          type="radio"
                          name="pytorch"
                          value="cpu"
                          checked={selectedPyTorchVariant === 'cpu'}
                          onChange={(e) => setSelectedPyTorchVariant(e.target.value)}
                          className="mr-2"
                        />
                        <span>PyTorch CPU only</span>
                      </label>
                    </div>
                  )}
                  {(!systemInfo?.gpu?.available || systemInfo?.gpu?.type !== 'cuda') && (
                    <p className="text-sm text-gray-600 dark:text-gray-400">CPU mode will be used</p>
                  )}
                </div>

                {/* Whisper Model Selection */}
                <div>
                  <p className="font-medium mb-2">Whisper Model (required):</p>
                  <div className="space-y-2">
                    {whisperModels.map((model) => (
                      <label key={model.name} className="flex items-center">
                        <input
                          type="radio"
                          name="whisper"
                          value={model.name}
                          checked={selectedWhisperModel === model.name}
                          onChange={(e) => setSelectedWhisperModel(e.target.value)}
                          className="mr-2"
                        />
                        <span>
                          {model.name} ({model.size}) - {model.description}
                        </span>
                      </label>
                    ))}
                  </div>
                </div>

                {/* Download Summary */}
                <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
                  <p className="text-sm font-medium mb-2">Components to download:</p>
                  <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
                    {getRequiredDownloads().map((d, i) => (
                      <li key={i}>
                        • {d.name}
                        {!d.required && <span className="text-xs italic"> (optional)</span>}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          )}

          {/* Step 3: LLM Setup */}
          {step === 3 && (
            <div>
              <h2 className="text-xl font-semibold mb-4">AI-Powered Lyric Correction (Optional)</h2>
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                KAI Converter can use large language models to improve transcription accuracy.
                This step is optional - you can skip it and configure it later in Settings.
              </p>

              <div className="space-y-4">
                <label className="flex items-center">
                  <input
                    type="checkbox"
                    checked={llmEnabled}
                    onChange={(e) => setLlmEnabled(e.target.checked)}
                    className="mr-2"
                  />
                  <span className="font-medium">Enable AI lyric correction</span>
                </label>

                {llmEnabled && (
                  <>
                    <div>
                      <label className="block text-sm font-medium mb-2">Choose Provider</label>
                      <div className="space-y-2">
                        <label className="flex items-center">
                          <input
                            type="radio"
                            name="llmProvider"
                            value="claude"
                            checked={llmProvider === 'claude'}
                            onChange={(e) => setLlmProvider(e.target.value)}
                            className="mr-2"
                          />
                          <span>Anthropic Claude (recommended)</span>
                        </label>
                        <label className="flex items-center">
                          <input
                            type="radio"
                            name="llmProvider"
                            value="openai"
                            checked={llmProvider === 'openai'}
                            onChange={(e) => setLlmProvider(e.target.value)}
                            className="mr-2"
                          />
                          <span>OpenAI (GPT-4o)</span>
                        </label>
                        <label className="flex items-center">
                          <input
                            type="radio"
                            name="llmProvider"
                            value="gemini"
                            checked={llmProvider === 'gemini'}
                            onChange={(e) => setLlmProvider(e.target.value)}
                            className="mr-2"
                          />
                          <span>Google Gemini</span>
                        </label>
                        <label className="flex items-center">
                          <input
                            type="radio"
                            name="llmProvider"
                            value="local"
                            checked={llmProvider === 'local'}
                            onChange={(e) => setLlmProvider(e.target.value)}
                            className="mr-2"
                          />
                          <span>Local LLM (LM Studio) - No API key needed</span>
                        </label>
                      </div>
                    </div>

                    {llmProvider === 'claude' && (
                      <div>
                        <label className="block text-sm font-medium mb-2">Claude API Key</label>
                        <input
                          type="password"
                          className="input w-full"
                          value={claudeApiKey}
                          onChange={(e) => setClaudeApiKey(e.target.value)}
                          placeholder="sk-ant-..."
                        />
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                          Get your API key from{' '}
                          <a
                            href="https://console.anthropic.com/"
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-600 hover:underline"
                          >
                            console.anthropic.com
                          </a>
                        </p>
                      </div>
                    )}

                    {llmProvider === 'openai' && (
                      <div>
                        <label className="block text-sm font-medium mb-2">OpenAI API Key</label>
                        <input
                          type="password"
                          className="input w-full"
                          value={openaiApiKey}
                          onChange={(e) => setOpenaiApiKey(e.target.value)}
                          placeholder="sk-..."
                        />
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                          Get your API key from{' '}
                          <a
                            href="https://platform.openai.com/api-keys"
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-600 hover:underline"
                          >
                            platform.openai.com
                          </a>
                        </p>
                      </div>
                    )}

                    {llmProvider === 'gemini' && (
                      <div>
                        <label className="block text-sm font-medium mb-2">Gemini API Key</label>
                        <input
                          type="password"
                          className="input w-full"
                          value={geminiApiKey}
                          onChange={(e) => setGeminiApiKey(e.target.value)}
                          placeholder="AIza..."
                        />
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                          Get your API key from{' '}
                          <a
                            href="https://aistudio.google.com/app/apikey"
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-600 hover:underline"
                          >
                            Google AI Studio
                          </a>
                        </p>
                      </div>
                    )}

                    {llmProvider === 'local' && (
                      <div className="text-sm text-gray-600 dark:text-gray-400">
                        <p>Make sure LM Studio (or compatible server) is running on localhost:1234</p>
                        <p className="mt-2">You can configure host and port in Settings later.</p>
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          )}

          {/* Step 4: Downloading */}
          {step === 4 && (
            <div>
              <h2 className="text-xl font-semibold mb-4">
                {downloadComplete ? 'Downloads Complete!' : !isDownloading ? 'Ready to Download' : 'Downloading Components...'}
              </h2>
              <div className="space-y-4">
                {downloads.map((download, index) => {
                  const progress = downloadProgress[download.component] || { percent: 0, message: '', stage: 'preparing' };
                  const result = downloadResults[download.component];
                  const isComplete = progress.stage === 'complete' || progress.percent === 100 || result?.success === true;
                  const hasFailed = result && !result.success;

                  return (
                    <div key={index}>
                      <div className="flex justify-between text-sm mb-1">
                        <span>
                          {download.name}
                          {!download.required && <span className="text-xs italic text-gray-500"> (optional)</span>}
                        </span>
                        <span className={
                          hasFailed
                            ? download.required ? 'text-red-600' : 'text-yellow-600'
                            : isComplete ? 'text-green-600' : ''
                        }>
                          {hasFailed
                            ? download.required ? '✗ Failed (required)' : '⚠ Skipped (optional)'
                            : isComplete ? '✓ Complete' : `${Math.round(progress.percent)}%`
                          }
                        </span>
                      </div>
                      <div className="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                        <div
                          className={`h-2 rounded-full transition-all ${
                            hasFailed
                              ? download.required ? 'bg-red-600' : 'bg-yellow-600'
                              : isComplete ? 'bg-green-600' : 'bg-blue-600'
                          }`}
                          style={{ width: hasFailed || isComplete ? '100%' : `${progress.percent}%` }}
                        />
                      </div>
                      {progress.message && !hasFailed && (
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 truncate">
                          {progress.message}
                        </p>
                      )}
                      {hasFailed && result.error && (
                        <p className="text-xs text-red-500 dark:text-red-400 mt-1 truncate">
                          Error: {result.error}
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
              {!isDownloading && !downloadComplete && Object.keys(downloadResults).length === 0 && (
                <p className="text-sm text-gray-600 dark:text-gray-400 mt-4">
                  Ready to download. Click "Start Download" to begin.
                </p>
              )}
              {!isDownloading && Object.keys(downloadResults).length > 0 && (
                <div className="mt-4 p-3 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg">
                  <p className="text-sm text-yellow-800 dark:text-yellow-200">
                    {Object.values(downloadResults).some(r => r.required && !r.success)
                      ? '⚠ Some required components failed to download. Please retry or check your internet connection.'
                      : Object.values(downloadResults).some(r => !r.success)
                        ? 'ℹ Some optional features are unavailable. You can continue without them.'
                        : null
                    }
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Step 5: Complete */}
          {step === 5 && (
            <div className="text-center">
              <div className="text-6xl mb-4">✓</div>
              <h2 className="text-2xl font-semibold mb-4">Setup Complete!</h2>
              <div className="space-y-2 text-left max-w-md mx-auto">
                {downloads.map((download, index) => {
                  const result = downloadResults[download.component];
                  const success = result?.success !== false;

                  return (
                    <div key={index} className="flex items-center">
                      <span className={`mr-2 ${success ? 'text-green-600' : 'text-yellow-600'}`}>
                        {success ? '✓' : '⚠'}
                      </span>
                      <span className={success ? '' : 'text-gray-500'}>
                        {download.name}
                        {!success && ' (unavailable)'}
                      </span>
                    </div>
                  );
                })}
              </div>

              {/* Show warning if yt-dlp failed */}
              {downloadResults['yt-dlp'] && !downloadResults['yt-dlp'].success && (
                <div className="mt-6 p-3 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg max-w-md mx-auto">
                  <p className="text-sm text-yellow-800 dark:text-yellow-200 text-left">
                    <strong>Note:</strong> YouTube support (yt-dlp) is unavailable. The YouTube tab will be disabled.
                    You can still convert local audio files.
                  </p>
                </div>
              )}

              <p className="text-gray-600 dark:text-gray-400 mt-6">
                {Object.values(downloadResults).every(r => r.success !== false)
                  ? 'You can now convert audio files to KAI format!'
                  : 'Core features are ready! You can convert audio files to KAI format.'
                }
              </p>
            </div>
          )}
        </div>

        {/* Buttons */}
        <div className="flex gap-4">
          {step > 1 && step < 4 && (
            <button onClick={() => setStep(step - 1)} className="px-4 py-2 border rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700">
              Back
            </button>
          )}
          {step === 1 && !checking && systemInfo && (
            <button onClick={() => setStep(2)} className="btn-primary flex-1">
              Continue
            </button>
          )}
          {step === 2 && (
            <button onClick={() => setStep(3)} className="btn-primary flex-1">
              Continue
            </button>
          )}
          {step === 3 && (
            <button
              onClick={async () => {
                // Save LLM settings
                if (window.electronAPI && llmEnabled) {
                  await window.electronAPI.saveSettings({
                    llm: {
                      enabled: llmEnabled,
                      provider: llmProvider,
                      claudeApiKey,
                      claudeModel: 'claude-3-5-sonnet-20241022',
                      openaiApiKey,
                      openaiModel: 'gpt-4o',
                      geminiApiKey,
                      geminiModel: 'gemini-1.5-flash',
                      localLlmHost: 'localhost',
                      localLlmPort: '1234',
                    },
                  });
                }
                setStep(4);
                setTimeout(startDownloads, 500);
              }}
              className="btn-primary flex-1"
            >
              Start Download
            </button>
          )}
          {step === 4 && !isDownloading && Object.keys(downloadResults).length > 0 && (
            <>
              {/* Show Retry button if there were failures */}
              {Object.values(downloadResults).some(r => !r.success) && (
                <button onClick={startDownloads} className="px-4 py-2 border rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700">
                  Retry Failed Downloads
                </button>
              )}

              {/* Allow continuing if only optional components failed OR all succeeded */}
              {!Object.values(downloadResults).some(r => r.required && !r.success) && (
                <button onClick={() => setStep(5)} className="btn-primary flex-1">
                  {Object.values(downloadResults).some(r => !r.success) ? 'Continue Anyway' : 'Continue'}
                </button>
              )}
            </>
          )}
          {step === 5 && (
            <button onClick={onComplete} className="btn-primary flex-1">
              Start Using KAI Converter
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
