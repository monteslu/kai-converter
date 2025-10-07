import { useState, useEffect } from 'react';
import ConvertScreen from './components/ConvertScreen';
import BatchScreen from './components/BatchScreen';
import SettingsScreen from './components/SettingsScreen';
import AboutScreen from './components/AboutScreen';
import SetupWizard from './components/SetupWizard';

export default function App() {
  const [currentTab, setCurrentTab] = useState('convert');
  const [theme, setTheme] = useState('light');
  const [setupComplete, setSetupComplete] = useState(false);

  // Initialize theme from system
  useEffect(() => {
    if (window.electronAPI) {
      // Get initial theme
      window.electronAPI.getTheme().then((systemTheme) => {
        setTheme(systemTheme);
        // Apply to document
        if (systemTheme === 'dark') {
          document.documentElement.classList.add('dark');
        } else {
          document.documentElement.classList.remove('dark');
        }
      });

      // Listen for theme changes
      const unsubscribe = window.electronAPI.onThemeChanged((newTheme) => {
        setTheme(newTheme);
        if (newTheme === 'dark') {
          document.documentElement.classList.add('dark');
        } else {
          document.documentElement.classList.remove('dark');
        }
      });

      return unsubscribe;
    }
  }, []);

  // Check if setup is complete
  useEffect(() => {
    async function checkSetup() {
      if (window.electronAPI) {
        const systemInfo = await window.electronAPI.checkSystem();

        // Setup is complete if all required components are installed
        const isComplete =
          systemInfo.python?.available &&
          systemInfo.pytorch?.available &&
          systemInfo.demucs?.available &&
          systemInfo.whisper?.available;

        setSetupComplete(isComplete);
      }
    }
    checkSetup();
  }, []);

  // Show setup wizard if not complete
  if (!setupComplete) {
    return <SetupWizard onComplete={() => setSetupComplete(true)} />;
  }

  const tabs = [
    { id: 'convert', label: '🎵 Convert', component: ConvertScreen },
    { id: 'batch', label: '📦 Batch', component: BatchScreen },
    { id: 'settings', label: '🔧 Settings', component: SettingsScreen },
    { id: 'about', label: 'ℹ️ About', component: AboutScreen },
  ];

  const ActiveComponent = tabs.find((tab) => tab.id === currentTab)?.component;

  return (
    <div className="h-screen flex flex-col bg-gray-50 dark:bg-gray-900">
      {/* Tab Navigation */}
      <div className="flex border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setCurrentTab(tab.id)}
            className={`
              px-6 py-3 font-medium transition-colors
              ${
                currentTab === tab.id
                  ? 'text-blue-600 dark:text-blue-400 border-b-2 border-blue-600 dark:border-blue-400'
                  : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
              }
            `}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-auto">
        {ActiveComponent && <ActiveComponent />}
      </div>
    </div>
  );
}
