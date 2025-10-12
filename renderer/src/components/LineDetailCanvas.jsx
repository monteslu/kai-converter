/**
 * LineDetailCanvas - Zoomed waveform view for selected lyric line
 *
 * Features:
 * - Shows waveform for just the selected line's time range
 * - Stretched to fill canvas width for detailed viewing
 * - Colored border matching selection color from main canvas
 * - Playhead for current position within the line
 */

import { useEffect, useRef } from 'react';

export function LineDetailCanvas({
  selectedLine,
  vocalsWaveform,
  songDuration,
  currentPosition,
  isPlaying,
}) {
  const canvasRef = useRef(null);
  const containerRef = useRef(null);

  const CANVAS_WIDTH = 3800;
  const CANVAS_HEIGHT = 120;

  // Draw canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;

    // Clear canvas
    ctx.clearRect(0, 0, width, height);

    // Draw black background (always, like full song canvas)
    ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
    ctx.fillRect(0, 0, width, height);

    // If no line selected or no waveform, just show empty canvas
    if (!selectedLine || !vocalsWaveform) return;

    const lineStart = selectedLine.start || selectedLine.startTimeSec || 0;
    const lineEnd = selectedLine.end || selectedLine.endTimeSec || lineStart + 3;
    const lineDuration = lineEnd - lineStart;

    // Draw waveform segment for this line (stretched to full width)
    drawWaveformSegment(ctx, vocalsWaveform, lineStart, lineEnd, songDuration, width, height);

    // Draw playhead if playing and within this line's range
    if (isPlaying && currentPosition >= lineStart && currentPosition <= lineEnd) {
      const relativePosition = currentPosition - lineStart;
      const x = (relativePosition / lineDuration) * width;

      ctx.strokeStyle = 'rgba(255, 255, 255, 0.9)';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();
    }
  }, [selectedLine, vocalsWaveform, songDuration, currentPosition, isPlaying]);

  // Draw waveform segment for the selected line (stretched to full canvas width)
  const drawWaveformSegment = (ctx, waveform, startTime, endTime, totalDuration, width, height) => {
    if (!waveform || waveform.length === 0) return;

    const _lineDuration = endTime - startTime;
    const samplesPerSecond = waveform.length / totalDuration;
    const startSample = Math.floor(startTime * samplesPerSecond);
    const endSample = Math.floor(endTime * samplesPerSecond);
    const lineWaveform = waveform.slice(startSample, endSample);

    if (lineWaveform.length === 0) return;

    const centerY = height / 2;
    const scale = height / 256;

    // Draw waveform (top half)
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 1;
    ctx.beginPath();

    for (let i = 0; i < lineWaveform.length; i++) {
      const x = (i / lineWaveform.length) * width;
      const value = lineWaveform[i];
      const y = centerY - value * scale;

      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    }

    ctx.stroke();

    // Mirror for bottom half
    ctx.beginPath();
    for (let i = 0; i < lineWaveform.length; i++) {
      const x = (i / lineWaveform.length) * width;
      const value = lineWaveform[i];
      const y = centerY + value * scale;

      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    }

    ctx.stroke();

    // Draw center line
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.3)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, centerY);
    ctx.lineTo(width, centerY);
    ctx.stroke();
  };

  // Determine border color based on line type
  const getBorderColor = () => {
    if (!selectedLine) return 'transparent';

    // Match colors from main canvas selection
    if (selectedLine.backup === true) {
      return 'rgba(255, 200, 0, 0.9)'; // Yellow/orange for backup lines
    }
    return 'rgba(0, 255, 255, 0.9)'; // Cyan for regular lines
  };

  return (
    <div
      ref={containerRef}
      className="w-full"
      style={{
        border: selectedLine ? `2px solid ${getBorderColor()}` : 'none',
        borderRadius: '4px',
        transition: 'border-color 0.2s ease'
      }}
    >
      <canvas
        ref={canvasRef}
        width={CANVAS_WIDTH}
        height={CANVAS_HEIGHT}
        className="w-full h-auto block"
      />
    </div>
  );
}
