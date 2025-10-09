import { useState, useEffect, useRef } from 'react';

export default function LogsScreen() {
  const [logs, setLogs] = useState([]);
  const [autoScroll, setAutoScroll] = useState(true);
  const [filter, setFilter] = useState('all'); // 'all', 'info', 'warning', 'error'
  const logsEndRef = useRef(null);
  const logsContainerRef = useRef(null);

  useEffect(() => {
    console.log('[LogsScreen] Setting up log listener...');
    console.log('[LogsScreen] electronAPI available:', !!window.electronAPI);
    console.log('[LogsScreen] onLogs available:', !!window.electronAPI?.onLogs);

    // Subscribe to log events from main process
    const unsubscribe = window.electronAPI?.onLogs?.((logEntry) => {
      console.log('[LogsScreen] Received log entry:', logEntry);
      setLogs(prev => {
        const newLogs = [...prev, {
          ...logEntry,
          timestamp: logEntry.timestamp || new Date().toISOString()
        }];
        console.log('[LogsScreen] Total logs now:', newLogs.length);
        return newLogs;
      });
    });

    console.log('[LogsScreen] Listener setup complete, unsubscribe:', !!unsubscribe);

    return () => {
      if (unsubscribe) {
        console.log('[LogsScreen] Cleaning up listener');
        unsubscribe();
      }
    };
  }, []);

  useEffect(() => {
    if (autoScroll && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, autoScroll]);

  function clearLogs() {
    setLogs([]);
  }

  function downloadLogs() {
    const logsText = logs.map(log =>
      `[${new Date(log.timestamp).toLocaleString()}] [${log.level?.toUpperCase() || 'INFO'}] ${log.message}`
    ).join('\n');

    const blob = new Blob([logsText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `kai-converter-logs-${Date.now()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  }

  const filteredLogs = logs.filter(log => {
    if (filter === 'all') return true;
    return log.level === filter;
  });

  function getLogLevelColor(level) {
    switch (level) {
      case 'error': return 'text-red-600 dark:text-red-400';
      case 'warning': return 'text-yellow-600 dark:text-yellow-400';
      case 'info': return 'text-blue-600 dark:text-blue-400';
      case 'debug': return 'text-gray-500 dark:text-gray-400';
      default: return 'text-gray-700 dark:text-gray-300';
    }
  }

  return (
    <div className="p-8 max-w-6xl mx-auto h-screen flex flex-col">
      <div className="mb-6">
        <h1 className="text-3xl font-bold mb-2">📋 Logs</h1>
        <p className="text-gray-600 dark:text-gray-400">
          View real-time processing logs, Whisper prompts, and debug information
        </p>
      </div>

      {/* Controls */}
      <div className="card p-4 mb-4">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={autoScroll}
                onChange={(e) => setAutoScroll(e.target.checked)}
                className="rounded"
              />
              <span className="text-sm">Auto-scroll</span>
            </label>

            <div className="flex items-center gap-2">
              <span className="text-sm font-medium">Filter:</span>
              <select
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                className="input text-sm py-1"
              >
                <option value="all">All ({logs.length})</option>
                <option value="error">Errors ({logs.filter(l => l.level === 'error').length})</option>
                <option value="warning">Warnings ({logs.filter(l => l.level === 'warning').length})</option>
                <option value="info">Info ({logs.filter(l => l.level === 'info').length})</option>
                <option value="debug">Debug ({logs.filter(l => l.level === 'debug').length})</option>
              </select>
            </div>
          </div>

          <div className="flex gap-2">
            <button
              onClick={downloadLogs}
              disabled={logs.length === 0}
              className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg disabled:bg-gray-300 disabled:text-gray-500 disabled:cursor-not-allowed"
            >
              💾 Download Logs
            </button>
            <button
              onClick={clearLogs}
              disabled={logs.length === 0}
              className="px-4 py-2 text-sm bg-red-600 hover:bg-red-700 text-white rounded-lg disabled:bg-gray-300 disabled:text-gray-500 disabled:cursor-not-allowed"
            >
              🗑️ Clear Logs
            </button>
          </div>
        </div>
      </div>

      {/* Logs Display */}
      <div className="card flex-1 overflow-hidden flex flex-col">
        <div
          ref={logsContainerRef}
          className="flex-1 overflow-y-auto p-4 bg-gray-50 dark:bg-gray-900 font-mono text-xs"
        >
          {filteredLogs.length === 0 ? (
            <div className="text-center text-gray-500 dark:text-gray-400 mt-8">
              No logs yet. Start processing audio to see logs here.
            </div>
          ) : (
            filteredLogs.map((log, index) => (
              <div key={index} className="mb-1 flex gap-2">
                <span className="text-gray-500 dark:text-gray-400 flex-shrink-0">
                  {new Date(log.timestamp).toLocaleTimeString()}
                </span>
                <span className={`font-medium flex-shrink-0 ${getLogLevelColor(log.level)}`}>
                  [{log.level?.toUpperCase() || 'INFO'}]
                </span>
                <span className="text-gray-700 dark:text-gray-300 break-words">
                  {log.message}
                </span>
              </div>
            ))
          )}
          <div ref={logsEndRef} />
        </div>
      </div>

      <div className="mt-4 text-sm text-gray-500 dark:text-gray-400 text-center">
        Showing {filteredLogs.length} of {logs.length} log entries
      </div>
    </div>
  );
}
