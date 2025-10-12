export default function BatchScreen() {
  return (
    <div className="p-8 max-w-6xl mx-auto">
      <h1 className="text-3xl font-bold mb-6">Batch Processing</h1>

      {/* Folder Selection */}
      <div className="card p-6 mb-6">
        <div className="flex items-center gap-4">
          <input
            type="text"
            placeholder="Select folder containing MP3 files..."
            className="input flex-1"
            readOnly
          />
          <button className="btn-secondary">Browse</button>
        </div>
      </div>

      {/* File List */}
      <div className="card p-6 mb-6">
        <h2 className="text-lg font-semibold mb-4">Files to Process (0 found)</h2>
        <div className="text-center py-12 text-gray-500 dark:text-gray-400">
          No folder selected
        </div>
      </div>

      {/* Batch Options */}
      <div className="card p-6 mb-6">
        <h2 className="text-lg font-semibold mb-4">Apply to All</h2>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium mb-2">Whisper Model</label>
            <select className="input w-full">
              <option>small</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium mb-2">Language</label>
            <select className="input w-full">
              <option>Auto-detect</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium mb-2">Stems</label>
            <select className="input w-full">
              <option>2-stem</option>
              <option>4-stem</option>
            </select>
          </div>
        </div>

        <div className="mt-4 space-y-2">
          <label className="flex items-center">
            <input type="checkbox" className="mr-2" defaultChecked />
            <span>Skip existing KAI files</span>
          </label>
          <label className="flex items-center">
            <input type="checkbox" className="mr-2" defaultChecked />
            <span>Continue on error</span>
          </label>
        </div>
      </div>

      {/* Controls */}
      <div className="flex gap-4">
        <button className="btn-primary flex-1">▶️ Start Batch</button>
        <button className="btn-secondary">⏸️ Pause</button>
        <button className="btn-secondary">⏹️ Stop</button>
      </div>

      <p className="text-sm text-gray-500 dark:text-gray-400 mt-4 text-center">
        Phase 2 placeholder - Full functionality in Phase 4
      </p>
    </div>
  );
}
