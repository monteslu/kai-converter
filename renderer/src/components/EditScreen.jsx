import { useState, useEffect } from 'react';

export default function EditScreen() {
  const [inputFile, setInputFile] = useState(null);
  const [kaiData, setKaiData] = useState(null);
  const [lyrics, setLyrics] = useState([]);
  const [originalLyrics, setOriginalLyrics] = useState([]);
  const [metadata, setMetadata] = useState({
    title: '',
    artist: '',
    album: '',
    year: '',
    genre: '',
    key: '',
  });
  const [hasChanges, setHasChanges] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveResult, setSaveResult] = useState(null);
  const [error, setError] = useState(null);
  const [editingLineIndex, setEditingLineIndex] = useState(null);

  // Handle file selection
  async function handleSelectFile() {
    try {
      if (window.electronAPI) {
        const filePath = await window.electronAPI.selectKaiFile();
        if (filePath) {
          await loadKaiFile(filePath);
        }
      }
    } catch (error) {
      console.error('File selection error:', error);
      setError('Failed to select file: ' + error.message);
    }
  }

  // Load KAI file
  async function loadKaiFile(filePath) {
    setInputFile(filePath);
    setSaveResult(null);
    setError(null);
    setKaiData(null);
    setLyrics([]);
    setOriginalLyrics([]);
    setHasChanges(false);
    setEditingLineIndex(null);

    try {
      const result = await window.electronAPI.readKaiMetadata(filePath);
      setKaiData(result);

      // Load metadata
      setMetadata({
        title: result.song?.title || '',
        artist: result.song?.artist || '',
        album: result.song?.album || '',
        year: result.song?.year || '',
        genre: result.song?.genre || '',
        key: result.song?.key || '',
      });

      // Load lyrics
      if (result.lines && Array.isArray(result.lines)) {
        const sortedLyrics = [...result.lines].sort((a, b) => {
          const aStart = a.start || a.startTimeSec || 0;
          const bStart = b.start || b.startTimeSec || 0;
          return aStart - bStart;
        });
        setLyrics(JSON.parse(JSON.stringify(sortedLyrics)));
        setOriginalLyrics(JSON.parse(JSON.stringify(sortedLyrics)));
      }
    } catch (err) {
      console.error('Failed to load KAI file:', err);
      setError('Failed to load KAI file: ' + err.message);
    }
  }

  // Handle metadata changes
  function handleMetadataChange(field, value) {
    setMetadata((prev) => ({ ...prev, [field]: value }));
    setHasChanges(true);
  }

  // Handle lyric line text change
  function handleLyricTextChange(index, newText) {
    setLyrics((prev) =>
      prev.map((line, i) => (i === index ? { ...line, text: newText } : line))
    );
    setHasChanges(true);
  }

  // Handle lyric time change
  function handleLyricTimeChange(index, field, value) {
    const numValue = parseFloat(value) || 0;
    setLyrics((prev) =>
      prev.map((line, i) => {
        if (i === index) {
          const updatedLine = {
            ...line,
            [field]: numValue,
          };
          // Update both formats for compatibility
          if (field === 'start') updatedLine.startTimeSec = numValue;
          if (field === 'end') updatedLine.endTimeSec = numValue;
          return updatedLine;
        }
        return line;
      })
    );
    setHasChanges(true);
  }

  // Delete a lyric line
  function handleDeleteLine(index) {
    if (confirm('Delete this lyric line?')) {
      setLyrics((prev) => prev.filter((_, i) => i !== index));
      setHasChanges(true);
      if (editingLineIndex === index) {
        setEditingLineIndex(null);
      }
    }
  }

  // Add new line after
  function handleAddLineAfter(index) {
    const currentLine = lyrics[index];
    const nextLine = lyrics[index + 1];

    const currentEndTime = currentLine.end || currentLine.endTimeSec || 0;
    const nextStartTime = nextLine
      ? nextLine.start || nextLine.startTimeSec || currentEndTime + 3
      : currentEndTime + 3;

    const newLine = {
      start: currentEndTime + 0.5,
      startTimeSec: currentEndTime + 0.5,
      end: nextStartTime - 0.5,
      endTimeSec: nextStartTime - 0.5,
      text: '',
    };

    setLyrics((prev) => [
      ...prev.slice(0, index + 1),
      newLine,
      ...prev.slice(index + 1),
    ]);
    setHasChanges(true);
    setEditingLineIndex(index + 1);
  }

  // Reset to original
  function handleReset() {
    if (confirm('Reset all changes? This cannot be undone.')) {
      setLyrics(JSON.parse(JSON.stringify(originalLyrics)));
      setMetadata({
        title: kaiData?.song?.title || '',
        artist: kaiData?.song?.artist || '',
        album: kaiData?.song?.album || '',
        year: kaiData?.song?.year || '',
        genre: kaiData?.song?.genre || '',
        key: kaiData?.song?.key || '',
      });
      setHasChanges(false);
      setSaveResult(null);
      setError(null);
    }
  }

  // Save changes
  async function handleSave() {
    if (!inputFile) {
      setError('No file loaded');
      return;
    }

    setIsSaving(true);
    setSaveResult(null);
    setError(null);

    try {
      // Sort lyrics by start time before saving
      const sortedLyrics = [...lyrics].sort((a, b) => {
        const aStart = a.start || a.startTimeSec || 0;
        const bStart = b.start || b.startTimeSec || 0;
        return aStart - bStart;
      });

      const updates = {
        inputFile,
        outputFile: inputFile, // Save back to same file
        metadata,
        lyrics: sortedLyrics,
      };

      const result = await window.electronAPI.updateKaiFile(updates);

      if (result.success) {
        setSaveResult('File saved successfully!');
        setHasChanges(false);
        // Update original lyrics after successful save
        setOriginalLyrics(JSON.parse(JSON.stringify(sortedLyrics)));
        setLyrics(sortedLyrics);
      } else {
        setError('Save failed: ' + (result.error || 'Unknown error'));
      }
    } catch (err) {
      console.error('Save error:', err);
      setError('Save failed: ' + err.message);
    } finally {
      setIsSaving(false);
    }
  }

  // Format time for display
  function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = (seconds % 60).toFixed(2);
    return `${mins}:${secs.padStart(5, '0')}`;
  }

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <h1 className="text-3xl font-bold mb-6">✏️ Edit KAI File</h1>

      {/* File Selection */}
      {!inputFile && (
        <div className="card p-6 mb-6">
          <button
            onClick={handleSelectFile}
            className="w-full py-12 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg hover:border-gray-400 dark:hover:border-gray-500 transition-colors"
          >
            <p className="text-4xl mb-4">📦</p>
            <p className="text-lg text-gray-700 dark:text-gray-300">
              Click to select a .kai file to edit
            </p>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
              You can edit lyrics and metadata
            </p>
          </button>
        </div>
      )}

      {/* File Info and Actions */}
      {inputFile && (
        <div className="card p-6 mb-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Editing:</p>
              <p className="text-lg font-medium text-gray-700 dark:text-gray-300">
                {inputFile.split('/').pop().split('\\').pop()}
              </p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleReset}
                disabled={!hasChanges || isSaving}
                className="px-4 py-2 border rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Reset
              </button>
              <button
                onClick={handleSelectFile}
                disabled={isSaving}
                className="px-4 py-2 border rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700"
              >
                Load Different File
              </button>
              <button
                onClick={handleSave}
                disabled={!hasChanges || isSaving}
                className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                  hasChanges && !isSaving
                    ? 'bg-blue-600 hover:bg-blue-700 text-white'
                    : 'bg-gray-300 dark:bg-gray-700 text-gray-500 dark:text-gray-400 cursor-not-allowed'
                }`}
              >
                {isSaving ? 'Saving...' : hasChanges ? 'Save Changes *' : 'Saved'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Success Message */}
      {saveResult && (
        <div className="card p-4 mb-6 bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800">
          <p className="text-green-800 dark:text-green-300">✓ {saveResult}</p>
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div className="card p-4 mb-6 bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800">
          <p className="text-red-800 dark:text-red-300">✗ {error}</p>
        </div>
      )}

      {/* Metadata Section */}
      {inputFile && kaiData && (
        <div className="card p-6 mb-6">
          <h2 className="text-xl font-semibold mb-4">Metadata</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-2">Title</label>
              <input
                type="text"
                className="input w-full"
                value={metadata.title}
                onChange={(e) => handleMetadataChange('title', e.target.value)}
                disabled={isSaving}
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Artist</label>
              <input
                type="text"
                className="input w-full"
                value={metadata.artist}
                onChange={(e) => handleMetadataChange('artist', e.target.value)}
                disabled={isSaving}
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Album</label>
              <input
                type="text"
                className="input w-full"
                value={metadata.album}
                onChange={(e) => handleMetadataChange('album', e.target.value)}
                disabled={isSaving}
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Year</label>
              <input
                type="text"
                className="input w-full"
                value={metadata.year}
                onChange={(e) => handleMetadataChange('year', e.target.value)}
                disabled={isSaving}
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Genre</label>
              <input
                type="text"
                className="input w-full"
                value={metadata.genre}
                onChange={(e) => handleMetadataChange('genre', e.target.value)}
                disabled={isSaving}
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Key</label>
              <input
                type="text"
                className="input w-full"
                value={metadata.key}
                onChange={(e) => handleMetadataChange('key', e.target.value)}
                disabled={isSaving}
              />
            </div>
          </div>
        </div>
      )}

      {/* Lyrics Section */}
      {inputFile && kaiData && (
        <div className="card p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold">Lyrics ({lyrics.length} lines)</h2>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Click a line to edit timing and text
            </p>
          </div>

          {lyrics.length === 0 ? (
            <div className="text-center py-12 text-gray-500 dark:text-gray-400">
              <p>No lyrics found in this file</p>
            </div>
          ) : (
            <div className="space-y-2">
              {lyrics.map((line, index) => {
                const isEditing = editingLineIndex === index;
                const start = line.start || line.startTimeSec || 0;
                const end = line.end || line.endTimeSec || 0;

                return (
                  <div
                    key={index}
                    className={`p-3 border rounded-lg transition-colors ${
                      isEditing
                        ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                        : 'border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500'
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <div className="flex-shrink-0 w-12 text-sm text-gray-500 dark:text-gray-400 pt-2">
                        #{index + 1}
                      </div>
                      <div className="flex-1 space-y-2">
                        {/* Timing Controls */}
                        <div className="flex items-center gap-2 text-sm">
                          <div className="flex items-center gap-1">
                            <span className="text-gray-600 dark:text-gray-400">Start:</span>
                            <input
                              type="number"
                              step="0.1"
                              className="input w-24 text-sm px-2 py-1"
                              value={start.toFixed(2)}
                              onChange={(e) => handleLyricTimeChange(index, 'start', e.target.value)}
                              disabled={isSaving}
                            />
                            <span className="text-gray-500 dark:text-gray-400">
                              {formatTime(start)}
                            </span>
                          </div>
                          <span className="text-gray-400">→</span>
                          <div className="flex items-center gap-1">
                            <span className="text-gray-600 dark:text-gray-400">End:</span>
                            <input
                              type="number"
                              step="0.1"
                              className="input w-24 text-sm px-2 py-1"
                              value={end.toFixed(2)}
                              onChange={(e) => handleLyricTimeChange(index, 'end', e.target.value)}
                              disabled={isSaving}
                            />
                            <span className="text-gray-500 dark:text-gray-400">
                              {formatTime(end)}
                            </span>
                          </div>
                          <span className="text-gray-500 dark:text-gray-400 ml-2">
                            ({(end - start).toFixed(2)}s)
                          </span>
                        </div>

                        {/* Text Input */}
                        <textarea
                          className="input w-full resize-none"
                          rows={2}
                          value={line.text || ''}
                          onChange={(e) => handleLyricTextChange(index, e.target.value)}
                          onFocus={() => setEditingLineIndex(index)}
                          onBlur={() => setEditingLineIndex(null)}
                          disabled={isSaving}
                          placeholder="Enter lyric text..."
                        />

                        {/* Action Buttons */}
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleAddLineAfter(index)}
                            disabled={isSaving}
                            className="text-xs px-2 py-1 border rounded hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50"
                          >
                            + Add After
                          </button>
                          <button
                            onClick={() => handleDeleteLine(index)}
                            disabled={isSaving}
                            className="text-xs px-2 py-1 border border-red-300 dark:border-red-700 text-red-600 dark:text-red-400 rounded hover:bg-red-50 dark:hover:bg-red-900/20 disabled:opacity-50"
                          >
                            Delete
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
