export default function AboutScreen() {
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
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-gray-600 dark:text-gray-400">OS:</span>
            <span>Detecting...</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-600 dark:text-gray-400">Python:</span>
            <span>Bundled</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-600 dark:text-gray-400">PyTorch:</span>
            <span>Not checked yet</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-600 dark:text-gray-400">GPU:</span>
            <span>Detecting...</span>
          </div>
        </div>
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
        Phase 2 placeholder - System info will be populated in Phase 3
      </p>
    </div>
  );
}
