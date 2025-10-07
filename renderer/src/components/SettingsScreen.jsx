import { useState } from 'react';

export default function SettingsScreen() {
  const [openSection, setOpenSection] = useState('models');

  const toggleSection = (section) => {
    setOpenSection(openSection === section ? null : section);
  };

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <h1 className="text-3xl font-bold mb-6">Settings</h1>

      {/* Models & Performance */}
      <div className="card mb-4">
        <button
          onClick={() => toggleSection('models')}
          className="w-full px-6 py-4 flex justify-between items-center hover:bg-gray-50 dark:hover:bg-gray-700/50"
        >
          <span className="font-semibold">🎤 Models & Performance</span>
          <span>{openSection === 'models' ? '▼' : '▶'}</span>
        </button>
        {openSection === 'models' && (
          <div className="px-6 pb-6 space-y-4">
            <div>
              <label className="block text-sm font-medium mb-2">Default Whisper Model</label>
              <select className="input w-full">
                <option>small</option>
                <option>tiny</option>
                <option>base</option>
                <option>medium</option>
                <option>large-v3</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Default Language</label>
              <select className="input w-full">
                <option>Auto-detect</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">GPU Acceleration</label>
              <div className="space-y-2">
                <label className="flex items-center">
                  <input type="radio" name="gpu" className="mr-2" defaultChecked />
                  <span>Auto-detect</span>
                </label>
                <label className="flex items-center">
                  <input type="radio" name="gpu" className="mr-2" />
                  <span>Force CPU</span>
                </label>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Model Management */}
      <div className="card mb-4">
        <button
          onClick={() => toggleSection('management')}
          className="w-full px-6 py-4 flex justify-between items-center hover:bg-gray-50 dark:hover:bg-gray-700/50"
        >
          <span className="font-semibold">📦 Model Management</span>
          <span>{openSection === 'management' ? '▼' : '▶'}</span>
        </button>
        {openSection === 'management' && (
          <div className="px-6 pb-6">
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
              Installed models will appear here
            </p>
          </div>
        )}
      </div>

      {/* Appearance */}
      <div className="card mb-4">
        <button
          onClick={() => toggleSection('appearance')}
          className="w-full px-6 py-4 flex justify-between items-center hover:bg-gray-50 dark:hover:bg-gray-700/50"
        >
          <span className="font-semibold">🎨 Appearance</span>
          <span>{openSection === 'appearance' ? '▼' : '▶'}</span>
        </button>
        {openSection === 'appearance' && (
          <div className="px-6 pb-6">
            <label className="block text-sm font-medium mb-2">Theme</label>
            <div className="space-y-2">
              <label className="flex items-center">
                <input type="radio" name="theme" className="mr-2" defaultChecked />
                <span>Auto (follow system)</span>
              </label>
              <label className="flex items-center">
                <input type="radio" name="theme" className="mr-2" />
                <span>Light</span>
              </label>
              <label className="flex items-center">
                <input type="radio" name="theme" className="mr-2" />
                <span>Dark</span>
              </label>
            </div>
          </div>
        )}
      </div>

      <p className="text-sm text-gray-500 dark:text-gray-400 mt-6 text-center">
        Phase 2 placeholder - Full functionality in Phase 3
      </p>
    </div>
  );
}
