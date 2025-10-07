export default function ConvertScreen() {
  return (
    <div className="p-8 max-w-4xl mx-auto">
      <h1 className="text-3xl font-bold mb-6">Convert Audio to KAI</h1>

      {/* Drop Zone */}
      <div className="card p-12 mb-6 text-center">
        <div className="border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg p-12">
          <p className="text-4xl mb-4">🎵</p>
          <p className="text-lg mb-2 text-gray-700 dark:text-gray-300">
            Drop audio file here or click to browse
          </p>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Supported: MP3, WAV, FLAC, M4A, OGG
          </p>
        </div>
      </div>

      {/* Options */}
      <div className="card p-6 mb-6">
        <h2 className="text-lg font-semibold mb-4">Processing Options</h2>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium mb-2">Whisper Model</label>
            <select className="input w-full">
              <option>small</option>
              <option>tiny</option>
              <option>base</option>
              <option>medium</option>
              <option>large-v3</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium mb-2">Language</label>
            <select className="input w-full">
              <option>Auto-detect</option>
              <option>English</option>
              <option>Spanish</option>
              <option>French</option>
              <option>German</option>
            </select>
          </div>
        </div>

        <div className="mt-4">
          <label className="flex items-center">
            <input type="radio" name="stems" className="mr-2" defaultChecked />
            <span>2-stem (vocals + music)</span>
          </label>
          <label className="flex items-center mt-2">
            <input type="radio" name="stems" className="mr-2" />
            <span>4-stem (vocals + drums + bass + other)</span>
          </label>
        </div>
      </div>

      {/* Action Button */}
      <button className="btn-primary w-full text-lg py-3">
        Convert to KAI
      </button>

      <p className="text-sm text-gray-500 dark:text-gray-400 mt-4 text-center">
        Phase 2 placeholder - Full functionality in Phase 3
      </p>
    </div>
  );
}
