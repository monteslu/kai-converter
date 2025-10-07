import { useState, useEffect } from 'react';

export default function SettingsScreen() {
  const [openSection, setOpenSection] = useState('models');
  const [whisperModel, setWhisperModel] = useState('large-v3-turbo');
  const [language, setLanguage] = useState('auto');
  const [stems, setStems] = useState(2);
  const [gpu, setGpu] = useState('auto');
  const [theme, setTheme] = useState('system');
  const [systemInfo, setSystemInfo] = useState(null);
  const [checking, setChecking] = useState(false);
  const [saving, setSaving] = useState(false);

  // LLM settings
  const [llmEnabled, setLlmEnabled] = useState(false);
  const [llmProvider, setLlmProvider] = useState('claude');
  const [claudeApiKey, setClaudeApiKey] = useState('');
  const [claudeModel, setClaudeModel] = useState('claude-3-5-sonnet-20241022');
  const [openaiApiKey, setOpenaiApiKey] = useState('');
  const [openaiModel, setOpenaiModel] = useState('gpt-4o');
  const [localLlmHost, setLocalLlmHost] = useState('localhost');
  const [localLlmPort, setLocalLlmPort] = useState('1234');

  // Load settings on mount
  useEffect(() => {
    loadSettings();
    checkSystem();
  }, []);

  async function loadSettings() {
    try {
      if (window.electronAPI) {
        const settings = await window.electronAPI.loadSettings();
        setWhisperModel(settings.whisperModel || 'large-v3-turbo');
        setLanguage(settings.language || 'auto');
        setStems(settings.stems || 2);
        setGpu(settings.gpu || 'auto');

        // Load LLM settings
        if (settings.llm) {
          setLlmEnabled(settings.llm.enabled || false);
          setLlmProvider(settings.llm.provider || 'claude');
          setClaudeApiKey(settings.llm.claudeApiKey || '');
          setClaudeModel(settings.llm.claudeModel || 'claude-3-5-sonnet-20241022');
          setOpenaiApiKey(settings.llm.openaiApiKey || '');
          setOpenaiModel(settings.llm.openaiModel || 'gpt-4o');
          setLocalLlmHost(settings.llm.localLlmHost || 'localhost');
          setLocalLlmPort(settings.llm.localLlmPort || '1234');
        }

        const currentTheme = await window.electronAPI.getTheme();
        setTheme(currentTheme);
      }
    } catch (error) {
      console.error('Failed to load settings:', error);
    }
  }

  async function checkSystem() {
    setChecking(true);
    try {
      if (window.electronAPI) {
        const info = await window.electronAPI.checkSystem();
        setSystemInfo(info);
      }
    } catch (error) {
      console.error('System check error:', error);
    } finally {
      setChecking(false);
    }
  }

  async function saveSettings() {
    setSaving(true);
    try {
      if (window.electronAPI) {
        await window.electronAPI.saveSettings({
          whisperModel,
          language,
          stems,
          gpu,
          llm: {
            enabled: llmEnabled,
            provider: llmProvider,
            claudeApiKey,
            claudeModel,
            openaiApiKey,
            openaiModel,
            localLlmHost,
            localLlmPort,
          },
        });
      }
    } catch (error) {
      console.error('Failed to save settings:', error);
    } finally {
      setSaving(false);
    }
  }

  async function handleThemeChange(newTheme) {
    setTheme(newTheme);
    if (window.electronAPI) {
      await window.electronAPI.setTheme(newTheme);
    }
  }

  const toggleSection = (section) => {
    setOpenSection(openSection === section ? null : section);
  };

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <h1 className="text-3xl font-bold mb-6">⚙️ Settings</h1>

      {/* Models & Performance */}
      <div className="card mb-4">
        <button
          onClick={() => toggleSection('models')}
          className="w-full px-6 py-4 flex justify-between items-center hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
        >
          <span className="font-semibold">🎤 Models & Performance</span>
          <span className="text-gray-500">{openSection === 'models' ? '▼' : '▶'}</span>
        </button>
        {openSection === 'models' && (
          <div className="px-6 pb-6 space-y-4 border-t border-gray-200 dark:border-gray-700 pt-4">
            <div>
              <label className="block text-sm font-medium mb-2">Default Whisper Model</label>
              <select
                className="input w-full"
                value={whisperModel}
                onChange={(e) => setWhisperModel(e.target.value)}
              >
                <option value="tiny">tiny (fastest, least accurate)</option>
                <option value="base">base</option>
                <option value="small">small (fast)</option>
                <option value="medium">medium</option>
                <option value="large-v3">large-v3 (best quality)</option>
                <option value="large-v3-turbo">large-v3-turbo (recommended)</option>
              </select>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                This model will be used by default for new conversions
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">Default Language</label>
              <select
                className="input w-full"
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
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

            <div>
              <label className="block text-sm font-medium mb-2">Default Stem Separation</label>
              <div className="space-y-2">
                <label className="flex items-center">
                  <input
                    type="radio"
                    name="stems"
                    value="2"
                    checked={stems === 2}
                    onChange={(e) => setStems(2)}
                    className="mr-2"
                  />
                  <span>2-stem (vocals + music) - Faster</span>
                </label>
                <label className="flex items-center">
                  <input
                    type="radio"
                    name="stems"
                    value="4"
                    checked={stems === 4}
                    onChange={(e) => setStems(4)}
                    className="mr-2"
                  />
                  <span>4-stem (vocals + drums + bass + other) - Better quality</span>
                </label>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">GPU Acceleration</label>
              <div className="space-y-2">
                <label className="flex items-center">
                  <input
                    type="radio"
                    name="gpu"
                    value="auto"
                    checked={gpu === 'auto'}
                    onChange={(e) => setGpu('auto')}
                    className="mr-2"
                  />
                  <span>Auto-detect</span>
                </label>
                <label className="flex items-center">
                  <input
                    type="radio"
                    name="gpu"
                    value="cpu"
                    checked={gpu === 'cpu'}
                    onChange={(e) => setGpu('cpu')}
                    className="mr-2"
                  />
                  <span>Force CPU</span>
                </label>
              </div>
              {systemInfo?.gpu?.available && (
                <p className="text-xs text-green-600 dark:text-green-400 mt-2">
                  ✓ {systemInfo.gpu.type.toUpperCase()} GPU detected
                </p>
              )}
            </div>

            <button
              onClick={saveSettings}
              disabled={saving}
              className="btn-primary w-full"
            >
              {saving ? 'Saving...' : 'Save Settings'}
            </button>
          </div>
        )}
      </div>

      {/* Model Management */}
      <div className="card mb-4">
        <button
          onClick={() => toggleSection('management')}
          className="w-full px-6 py-4 flex justify-between items-center hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
        >
          <span className="font-semibold">📦 Model Management</span>
          <span className="text-gray-500">{openSection === 'management' ? '▼' : '▶'}</span>
        </button>
        {openSection === 'management' && (
          <div className="px-6 pb-6 border-t border-gray-200 dark:border-gray-700 pt-4">
            {checking ? (
              <div className="text-center py-4">
                <div className="inline-block animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600" />
                <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">Checking installed models...</p>
              </div>
            ) : systemInfo ? (
              <div className="space-y-4">
                {/* PyTorch */}
                <div className="flex items-center justify-between py-2 border-b border-gray-200 dark:border-gray-700">
                  <div>
                    <p className="font-medium">PyTorch</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      {systemInfo.pytorch?.available
                        ? `Version ${systemInfo.pytorch.version}`
                        : 'Not installed'}
                    </p>
                  </div>
                  <span
                    className={systemInfo.pytorch?.available ? 'text-green-600' : 'text-red-600'}
                  >
                    {systemInfo.pytorch?.available ? '✓ Installed' : '✗ Missing'}
                  </span>
                </div>

                {/* Demucs */}
                <div className="flex items-center justify-between py-2 border-b border-gray-200 dark:border-gray-700">
                  <div>
                    <p className="font-medium">Demucs</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      Audio source separation
                    </p>
                  </div>
                  <span
                    className={systemInfo.demucs?.available ? 'text-green-600' : 'text-red-600'}
                  >
                    {systemInfo.demucs?.available ? '✓ Installed' : '✗ Missing'}
                  </span>
                </div>

                {/* Whisper */}
                <div className="flex items-center justify-between py-2 border-b border-gray-200 dark:border-gray-700">
                  <div>
                    <p className="font-medium">Whisper</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      Speech-to-text for lyrics
                    </p>
                  </div>
                  <span
                    className={systemInfo.whisper?.available ? 'text-green-600' : 'text-red-600'}
                  >
                    {systemInfo.whisper?.available ? '✓ Installed' : '✗ Missing'}
                  </span>
                </div>

                {/* Whisper Models */}
                {systemInfo.whisper?.available && systemInfo.whisper?.models?.length > 0 && (
                  <div>
                    <p className="font-medium mb-2">Downloaded Whisper Models:</p>
                    <div className="space-y-1">
                      {systemInfo.whisper.models.map((model) => (
                        <div
                          key={model}
                          className="flex items-center justify-between py-1 px-3 bg-gray-50 dark:bg-gray-800 rounded"
                        >
                          <span className="text-sm">{model}</span>
                          <span className="text-xs text-green-600">✓</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="flex gap-2">
                  <button
                    onClick={checkSystem}
                    className="flex-1 px-4 py-2 border rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700"
                  >
                    Refresh System Check
                  </button>
                  <button
                    onClick={() => {
                      localStorage.setItem('forceSetup', 'true');
                      window.location.reload();
                    }}
                    className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                  >
                    Re-run Setup Wizard
                  </button>
                </div>
              </div>
            ) : (
              <div className="text-center py-4">
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                  No system information available
                </p>
                <button
                  onClick={checkSystem}
                  className="btn-primary"
                >
                  Check System
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Lyric Correction (LLM) */}
      <div className="card mb-4">
        <button
          onClick={() => toggleSection('llm')}
          className="w-full px-6 py-4 flex justify-between items-center hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
        >
          <span className="font-semibold">🤖 Lyric Correction (LLM)</span>
          <span className="text-gray-500">{openSection === 'llm' ? '▼' : '▶'}</span>
        </button>
        {openSection === 'llm' && (
          <div className="px-6 pb-6 space-y-4 border-t border-gray-200 dark:border-gray-700 pt-4">
            {/* Enable/Disable Toggle */}
            <div>
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={llmEnabled}
                  onChange={(e) => setLlmEnabled(e.target.checked)}
                  className="mr-2"
                />
                <span className="font-medium">Enable AI-powered lyric correction</span>
              </label>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                Use large language models to improve transcription accuracy after Whisper
              </p>
            </div>

            {llmEnabled && (
              <>
                {/* Provider Selection */}
                <div>
                  <label className="block text-sm font-medium mb-2">LLM Provider</label>
                  <select
                    className="input w-full"
                    value={llmProvider}
                    onChange={(e) => setLlmProvider(e.target.value)}
                  >
                    <option value="claude">Anthropic Claude</option>
                    <option value="openai">OpenAI</option>
                    <option value="local">Local LLM (LM Studio)</option>
                  </select>
                </div>

                {/* Claude Settings */}
                {llmProvider === 'claude' && (
                  <>
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
                    <div>
                      <label className="block text-sm font-medium mb-2">Claude Model</label>
                      <select
                        className="input w-full"
                        value={claudeModel}
                        onChange={(e) => setClaudeModel(e.target.value)}
                      >
                        <option value="claude-3-5-sonnet-20241022">Claude 3.5 Sonnet (recommended)</option>
                        <option value="claude-3-5-haiku-20241022">Claude 3.5 Haiku (faster)</option>
                        <option value="claude-3-opus-20240229">Claude 3 Opus (most capable)</option>
                      </select>
                    </div>
                  </>
                )}

                {/* OpenAI Settings */}
                {llmProvider === 'openai' && (
                  <>
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
                    <div>
                      <label className="block text-sm font-medium mb-2">OpenAI Model</label>
                      <select
                        className="input w-full"
                        value={openaiModel}
                        onChange={(e) => setOpenaiModel(e.target.value)}
                      >
                        <option value="gpt-4o">GPT-4o (recommended)</option>
                        <option value="gpt-4o-mini">GPT-4o mini (faster, cheaper)</option>
                        <option value="gpt-4-turbo">GPT-4 Turbo</option>
                      </select>
                    </div>
                  </>
                )}

                {/* Local LLM Settings */}
                {llmProvider === 'local' && (
                  <>
                    <div>
                      <label className="block text-sm font-medium mb-2">Local LLM Host</label>
                      <input
                        type="text"
                        className="input w-full"
                        value={localLlmHost}
                        onChange={(e) => setLocalLlmHost(e.target.value)}
                        placeholder="localhost"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium mb-2">Local LLM Port</label>
                      <input
                        type="text"
                        className="input w-full"
                        value={localLlmPort}
                        onChange={(e) => setLocalLlmPort(e.target.value)}
                        placeholder="1234"
                      />
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                        Default port for LM Studio is 1234. Make sure your local LLM server is running.
                      </p>
                    </div>
                  </>
                )}

                <button
                  onClick={saveSettings}
                  disabled={saving}
                  className="btn-primary w-full"
                >
                  {saving ? 'Saving...' : 'Save LLM Settings'}
                </button>
              </>
            )}
          </div>
        )}
      </div>

      {/* Appearance */}
      <div className="card mb-4">
        <button
          onClick={() => toggleSection('appearance')}
          className="w-full px-6 py-4 flex justify-between items-center hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
        >
          <span className="font-semibold">🎨 Appearance</span>
          <span className="text-gray-500">{openSection === 'appearance' ? '▼' : '▶'}</span>
        </button>
        {openSection === 'appearance' && (
          <div className="px-6 pb-6 border-t border-gray-200 dark:border-gray-700 pt-4">
            <label className="block text-sm font-medium mb-2">Theme</label>
            <div className="space-y-2">
              <label className="flex items-center">
                <input
                  type="radio"
                  name="theme"
                  value="system"
                  checked={theme === 'system'}
                  onChange={(e) => handleThemeChange('system')}
                  className="mr-2"
                />
                <span>Auto (follow system)</span>
              </label>
              <label className="flex items-center">
                <input
                  type="radio"
                  name="theme"
                  value="light"
                  checked={theme === 'light'}
                  onChange={(e) => handleThemeChange('light')}
                  className="mr-2"
                />
                <span>Light</span>
              </label>
              <label className="flex items-center">
                <input
                  type="radio"
                  name="theme"
                  value="dark"
                  checked={theme === 'dark'}
                  onChange={(e) => handleThemeChange('dark')}
                  className="mr-2"
                />
                <span>Dark</span>
              </label>
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-3">
              Current theme: {theme === 'system' ? 'System default' : theme.charAt(0).toUpperCase() + theme.slice(1)}
            </p>
          </div>
        )}
      </div>

      {/* About */}
      <div className="card mb-4">
        <button
          onClick={() => toggleSection('about')}
          className="w-full px-6 py-4 flex justify-between items-center hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
        >
          <span className="font-semibold">ℹ️ About</span>
          <span className="text-gray-500">{openSection === 'about' ? '▼' : '▶'}</span>
        </button>
        {openSection === 'about' && (
          <div className="px-6 pb-6 border-t border-gray-200 dark:border-gray-700 pt-4">
            <div className="space-y-2 text-sm">
              <p><strong>KAI Converter</strong> v1.0.0</p>
              <p className="text-gray-600 dark:text-gray-400">
                AI-powered karaoke file creator with source separation and lyrics transcription
              </p>
              <div className="pt-3 border-t border-gray-200 dark:border-gray-700 mt-3">
                <p className="text-gray-600 dark:text-gray-400">
                  OS: {systemInfo ? process.platform : 'Unknown'}
                </p>
                <p className="text-gray-600 dark:text-gray-400">
                  Python: {systemInfo?.python?.available ? systemInfo.python.version : 'Not detected'}
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
