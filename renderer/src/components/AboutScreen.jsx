import { useState, useEffect } from 'react';

export default function AboutScreen() {
  const [systemInfo, setSystemInfo] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function checkSystem() {
      if (window.electronAPI) {
        const info = await window.electronAPI.checkSystem();
        setSystemInfo(info);
        setLoading(false);
      }
    }
    checkSystem();
  }, []);

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="text-center mb-8">
        <h1 className="text-4xl font-bold mb-2">🎵 KAI Converter</h1>
        <p className="text-xl text-gray-600 dark:text-gray-400">v1.0.0</p>
        <p className="text-gray-600 dark:text-gray-400 mt-2">
          AI-powered karaoke file creator with source separation and lyrics transcription
        </p>
      </div>

      <div className="card p-6 mb-6">
        <h2 className="text-lg font-semibold mb-4">Quick Links</h2>
        <div className="space-y-3">
          <a href="#" className="block text-blue-600 dark:text-blue-400 hover:underline">
            📖 User Guide → Open Documentation
          </a>
          <a href="#" className="block text-blue-600 dark:text-blue-400 hover:underline">
            🐛 Report Bug → GitHub Issues
          </a>
          <a href="#" className="block text-blue-600 dark:text-blue-400 hover:underline">
            ⭐ Star on GitHub → github.com/user/repo
          </a>
          <a href="#" className="block text-blue-600 dark:text-blue-400 hover:underline">
            💬 Discussions → GitHub Discussions
          </a>
        </div>
      </div>

      <div className="card p-6 mb-6">
        <h2 className="text-lg font-semibold mb-4">System Information</h2>
        {loading ? (
          <p className="text-gray-500 dark:text-gray-400">Checking system...</p>
        ) : (
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-600 dark:text-gray-400">Python:</span>
              <span className={systemInfo?.python?.available ? 'text-green-600' : 'text-red-600'}>
                {systemInfo?.python?.available
                  ? `✓ ${systemInfo.python.version}`
                  : '✗ Not found'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600 dark:text-gray-400">PyTorch:</span>
              <span className={systemInfo?.pytorch?.available ? 'text-green-600' : 'text-red-600'}>
                {systemInfo?.pytorch?.available
                  ? `✓ ${systemInfo.pytorch.version}`
                  : '✗ Not installed'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600 dark:text-gray-400">GPU:</span>
              <span className={systemInfo?.gpu?.available ? 'text-green-600' : 'text-gray-500'}>
                {systemInfo?.gpu?.available
                  ? `✓ ${systemInfo.gpu.type.toUpperCase()} available`
                  : `CPU only (${systemInfo?.gpu?.type || 'none'})`}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600 dark:text-gray-400">Demucs:</span>
              <span className={systemInfo?.demucs?.available ? 'text-green-600' : 'text-red-600'}>
                {systemInfo?.demucs?.available ? '✓ Installed' : '✗ Not installed'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600 dark:text-gray-400">Whisper:</span>
              <span className={systemInfo?.whisper?.available ? 'text-green-600' : 'text-red-600'}>
                {systemInfo?.whisper?.available
                  ? `✓ Installed (${systemInfo.whisper.models.length} models)`
                  : '✗ Not installed'}
              </span>
            </div>
          </div>
        )}
      </div>

      <div className="card p-6">
        <h2 className="text-lg font-semibold mb-4">Quick Tips</h2>
        <ul className="space-y-2 text-sm text-gray-700 dark:text-gray-300">
          <li>• Drag & drop audio files to the Convert tab</li>
          <li>• Use "small" Whisper model for best speed/quality balance</li>
          <li>• Enable GPU for 3-5x faster processing</li>
          <li>• Batch mode skips existing KAI files automatically</li>
        </ul>
      </div>

      <p className="text-sm text-gray-500 dark:text-gray-400 mt-6 text-center">
        Phase 3 - System check now working! ✓
      </p>
    </div>
  );
}
