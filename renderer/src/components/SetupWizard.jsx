import { useState } from 'react';

export default function SetupWizard({ onComplete }) {
  const [step, setStep] = useState(1);

  const steps = [
    { id: 1, title: 'System Check', description: 'Checking requirements...' },
    { id: 2, title: 'Model Selection', description: 'Choose models to download' },
    { id: 3, title: 'Downloading', description: 'Downloading models...' },
    { id: 4, title: 'Complete', description: 'Setup complete!' },
  ];

  const currentStep = steps.find((s) => s.id === step);

  return (
    <div className="h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
      <div className="card p-8 w-full max-w-2xl">
        <h1 className="text-3xl font-bold mb-2">KAI Converter Setup</h1>
        <p className="text-gray-600 dark:text-gray-400 mb-8">
          Step {step}/4: {currentStep.title}
        </p>

        {/* Progress Bar */}
        <div className="mb-8">
          <div className="flex justify-between mb-2">
            {steps.map((s) => (
              <div
                key={s.id}
                className={`text-sm ${s.id <= step ? 'text-blue-600 dark:text-blue-400' : 'text-gray-400'}`}
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
          {step === 1 && (
            <div>
              <h2 className="text-xl font-semibold mb-4">Checking System Requirements</h2>
              <div className="space-y-2">
                <div className="flex items-center">
                  <span className="text-green-600 mr-2">✓</span>
                  <span>Python runtime</span>
                </div>
                <div className="flex items-center">
                  <span className="text-green-600 mr-2">✓</span>
                  <span>FFmpeg</span>
                </div>
                <div className="flex items-center">
                  <span className="text-green-600 mr-2">✓</span>
                  <span>Core dependencies</span>
                </div>
                <div className="flex items-center">
                  <span className="text-yellow-600 mr-2">⚠</span>
                  <span>PyTorch: Not installed</span>
                </div>
                <div className="flex items-center">
                  <span className="text-yellow-600 mr-2">⚠</span>
                  <span>Demucs models: Not installed</span>
                </div>
                <div className="flex items-center">
                  <span className="text-yellow-600 mr-2">⚠</span>
                  <span>Whisper models: Not installed</span>
                </div>
              </div>
            </div>
          )}

          {step === 2 && (
            <div>
              <h2 className="text-xl font-semibold mb-4">Choose Models</h2>
              <div className="space-y-4">
                <div>
                  <p className="font-medium mb-2">GPU: Not detected</p>
                  <p className="text-sm text-gray-600 dark:text-gray-400">CPU mode will be used</p>
                </div>
                <div>
                  <p className="font-medium mb-2">Whisper Model (required):</p>
                  <div className="space-y-2">
                    <label className="flex items-center">
                      <input type="radio" name="whisper" className="mr-2" />
                      <span>tiny (75MB) - Fastest</span>
                    </label>
                    <label className="flex items-center">
                      <input type="radio" name="whisper" className="mr-2" />
                      <span>base (150MB)</span>
                    </label>
                    <label className="flex items-center">
                      <input type="radio" name="whisper" className="mr-2" defaultChecked />
                      <span>small (500MB) ⭐ Recommended</span>
                    </label>
                    <label className="flex items-center">
                      <input type="radio" name="whisper" className="mr-2" />
                      <span>medium (1.5GB)</span>
                    </label>
                  </div>
                </div>
                <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
                  <p className="text-sm">
                    <strong>Total download:</strong> ~850MB
                  </p>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    Available space: 45GB
                  </p>
                </div>
              </div>
            </div>
          )}

          {step === 3 && (
            <div>
              <h2 className="text-xl font-semibold mb-4">Downloading Models...</h2>
              <div className="space-y-4">
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span>PyTorch CPU</span>
                    <span>100%</span>
                  </div>
                  <div className="h-2 bg-gray-200 dark:bg-gray-700 rounded-full">
                    <div className="h-2 bg-green-600 rounded-full w-full" />
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span>Demucs Model</span>
                    <span>68%</span>
                  </div>
                  <div className="h-2 bg-gray-200 dark:bg-gray-700 rounded-full">
                    <div className="h-2 bg-blue-600 rounded-full w-2/3" />
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span>Whisper small</span>
                    <span>25%</span>
                  </div>
                  <div className="h-2 bg-gray-200 dark:bg-gray-700 rounded-full">
                    <div className="h-2 bg-blue-600 rounded-full w-1/4" />
                  </div>
                </div>
              </div>
              <p className="text-sm text-gray-600 dark:text-gray-400 mt-4">
                Speed: 8.5 MB/s - 32s remaining
              </p>
            </div>
          )}

          {step === 4 && (
            <div className="text-center">
              <div className="text-6xl mb-4">✓</div>
              <h2 className="text-2xl font-semibold mb-4">Setup Complete!</h2>
              <div className="space-y-2 text-left max-w-md mx-auto">
                <div className="flex items-center">
                  <span className="text-green-600 mr-2">✓</span>
                  <span>PyTorch CPU installed</span>
                </div>
                <div className="flex items-center">
                  <span className="text-green-600 mr-2">✓</span>
                  <span>Demucs model ready</span>
                </div>
                <div className="flex items-center">
                  <span className="text-green-600 mr-2">✓</span>
                  <span>Whisper small ready</span>
                </div>
              </div>
              <p className="text-gray-600 dark:text-gray-400 mt-6">
                You can now convert audio to KAI!
              </p>
            </div>
          )}
        </div>

        {/* Buttons */}
        <div className="flex gap-4">
          {step > 1 && step < 4 && (
            <button onClick={() => setStep(step - 1)} className="btn-secondary">
              Back
            </button>
          )}
          {step < 3 && (
            <button onClick={() => setStep(step + 1)} className="btn-primary flex-1">
              Continue
            </button>
          )}
          {step === 3 && (
            <button onClick={() => setStep(4)} className="btn-primary flex-1">
              Simulate Download Complete
            </button>
          )}
          {step === 4 && (
            <button onClick={onComplete} className="btn-primary flex-1">
              Start Using KAI Converter
            </button>
          )}
        </div>

        <p className="text-sm text-gray-500 dark:text-gray-400 mt-6 text-center">
          Phase 2 placeholder - Real downloads in Phase 3
        </p>
      </div>
    </div>
  );
}
