import { useState, useEffect } from 'react';

export default function SetupWizard({ onComplete }) {
  const [step, setStep] = useState(1);
  const [systemInfo, setSystemInfo] = useState(null);
  const [checking, setChecking] = useState(true);
  const [selectedWhisperModel, setSelectedWhisperModel] = useState('large-v3-turbo');
  const [selectedPyTorchVariant, setSelectedPyTorchVariant] = useState('cpu');
  const [downloads, setDownloads] = useState([]);
  const [downloadProgress, setDownloadProgress] = useState({});
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadComplete, setDownloadComplete] = useState(false);

  const steps = [
    { id: 1, title: 'System Check', description: 'Checking requirements...' },
    { id: 2, title: 'Model Selection', description: 'Choose models to download' },
    { id: 3, title: 'Downloading', description: 'Downloading models...' },
    { id: 4, title: 'Complete', description: 'Setup complete!' },
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
      });
    }

    if (!systemInfo?.demucs?.available) {
      required.push({
        component: 'demucs',
        name: 'Demucs',
      });
    }

    if (!systemInfo?.whisper?.available) {
      required.push({
        component: 'whisper',
        name: 'Whisper Library',
      });
    }

    // Always download selected Whisper model if not present
    if (!systemInfo?.whisper?.models?.includes(selectedWhisperModel)) {
      required.push({
        component: 'whisper-model',
        name: `Whisper ${selectedWhisperModel} model`,
        model: selectedWhisperModel,
      });
    }

    // Always download Demucs model (they're downloaded on first use)
    required.push({
      component: 'demucs-model',
      name: 'Demucs htdemucs_ft model',
      model: 'htdemucs_ft',
    });

    return required;
  }

  // Step 3: Download components
  async function startDownloads() {
    const required = getRequiredDownloads();
    setDownloads(required);
    setIsDownloading(true);
    setDownloadComplete(false);

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

    try {
      // Download each component sequentially
      for (const download of required) {
        const options = {
          component: download.component,
          variant: download.variant,
          model: download.model,
        };

        const result = await window.electronAPI.downloadComponent(options);

        if (!result.success) {
          console.error(`Failed to download ${download.name}:`, result.error);
          // Continue with other downloads
        }
      }

      setDownloadComplete(true);
      setIsDownloading(false);
    } catch (error) {
      console.error('Download error:', error);
      setIsDownloading(false);
    } finally {
      if (unsubscribe) unsubscribe();
    }
  }

  // Auto-advance to step 4 when downloads complete
  useEffect(() => {
    if (downloadComplete && step === 3) {
      setTimeout(() => setStep(4), 1000);
    }
  }, [downloadComplete, step]);

  const currentStep = steps.find((s) => s.id === step);

  return (
    <div className="h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
      <div className="card p-8 w-full max-w-2xl">
        <h1 className="text-3xl font-bold mb-2">🎵 KAI Converter Setup</h1>
        <p className="text-gray-600 dark:text-gray-400 mb-8">
          Step {step}/4: {currentStep.title}
        </p>

        {/* Progress Bar */}
        <div className="mb-8">
          <div className="flex justify-between mb-2">
            {steps.map((s) => (
              <div
                key={s.id}
                className={`text-sm ${s.id <= step ? 'text-blue-600 dark:text-blue-400 font-medium' : 'text-gray-400'}`}
              >
                {s.id}. {s.title}
              </div>
            ))}
          </div>
          <div className="h-2 bg-gray-200 dark:bg-gray-700 rounded-full">
            <div
              className="h-2 bg-blue-600 dark:bg-blue-400 rounded-full transition-all"
              style={{ width: `${(step / 4) * 100}%` }}
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
                      <li key={i}>• {d.name}</li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          )}

          {/* Step 3: Downloading */}
          {step === 3 && (
            <div>
              <h2 className="text-xl font-semibold mb-4">
                {downloadComplete ? 'Downloads Complete!' : 'Downloading Components...'}
              </h2>
              <div className="space-y-4">
                {downloads.map((download, index) => {
                  const progress = downloadProgress[download.component] || { percent: 0, message: '', stage: 'preparing' };
                  const isComplete = progress.stage === 'complete' || progress.percent === 100;

                  return (
                    <div key={index}>
                      <div className="flex justify-between text-sm mb-1">
                        <span>{download.name}</span>
                        <span className={isComplete ? 'text-green-600' : ''}>
                          {isComplete ? '✓ Complete' : `${Math.round(progress.percent)}%`}
                        </span>
                      </div>
                      <div className="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                        <div
                          className={`h-2 rounded-full transition-all ${
                            isComplete ? 'bg-green-600' : 'bg-blue-600'
                          }`}
                          style={{ width: `${progress.percent}%` }}
                        />
                      </div>
                      {progress.message && (
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 truncate">
                          {progress.message}
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
              {!isDownloading && !downloadComplete && (
                <p className="text-sm text-gray-600 dark:text-gray-400 mt-4">
                  Ready to download. Click "Start Download" to begin.
                </p>
              )}
            </div>
          )}

          {/* Step 4: Complete */}
          {step === 4 && (
            <div className="text-center">
              <div className="text-6xl mb-4">✓</div>
              <h2 className="text-2xl font-semibold mb-4">Setup Complete!</h2>
              <div className="space-y-2 text-left max-w-md mx-auto">
                {downloads.map((download, index) => (
                  <div key={index} className="flex items-center">
                    <span className="text-green-600 mr-2">✓</span>
                    <span>{download.name}</span>
                  </div>
                ))}
              </div>
              <p className="text-gray-600 dark:text-gray-400 mt-6">
                You can now convert audio files to KAI format!
              </p>
            </div>
          )}
        </div>

        {/* Buttons */}
        <div className="flex gap-4">
          {step > 1 && step < 3 && (
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
            <button
              onClick={() => {
                setStep(3);
                setTimeout(startDownloads, 500);
              }}
              className="btn-primary flex-1"
            >
              Start Download
            </button>
          )}
          {step === 3 && !isDownloading && !downloadComplete && (
            <button onClick={startDownloads} className="btn-primary flex-1">
              Retry
            </button>
          )}
          {step === 4 && (
            <button onClick={onComplete} className="btn-primary flex-1">
              Start Using KAI Converter
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
