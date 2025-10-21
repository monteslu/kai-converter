"""WebVTT generator for karaoke lyrics."""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class WebVTTGenerator:
    """Generate WebVTT files from KAI lyrics data."""

    def generate_webvtt(
        self,
        lyrics_data: Dict[str, Any],
        encoder_delay_samples: int = 0,
        sample_rate: int = 44100
    ) -> str:
        """
        Convert KAI lyrics format to WebVTT with voice tags and word timing.

        Args:
            lyrics_data: KAI lyrics data with lines and singers
            encoder_delay_samples: Encoder delay to compensate (e.g., 1105 for AAC/MP3)
            sample_rate: Audio sample rate

        Returns:
            WebVTT formatted string
        """
        lines = lyrics_data.get('lines', [])
        singers = {s['id']: s for s in lyrics_data.get('singers', [])}

        # Calculate time offset from encoder delay
        delay_offset = encoder_delay_samples / sample_rate

        # Start WebVTT file
        vtt_lines = ["WEBVTT", ""]

        for line_data in lines:
            # Skip disabled lines (they won't be shown during playback)
            if line_data.get('disabled', False):
                continue

            # Get line timing (adjust for encoder delay)
            start_time = line_data['start'] + delay_offset
            end_time = line_data['end'] + delay_offset

            # Format timestamps
            start_ts = self._format_timestamp(start_time)
            end_ts = self._format_timestamp(end_time)

            # Build cue text with voice tags and word timing
            cue_text = self._build_cue_text(line_data, singers)

            # Add cue
            vtt_lines.append(f"{start_ts} --> {end_ts}")
            vtt_lines.append(cue_text)
            vtt_lines.append("")  # Blank line between cues

        return "\n".join(vtt_lines)

    def _format_timestamp(self, seconds: float) -> str:
        """
        Format timestamp for WebVTT (HH:MM:SS.mmm).

        Args:
            seconds: Time in seconds

        Returns:
            Formatted timestamp string
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60

        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"

    def _build_cue_text(
        self,
        line_data: Dict[str, Any],
        singers: Dict[str, Dict[str, Any]]
    ) -> str:
        """
        Build cue text with voice tags and word-level timing.

        Args:
            line_data: Line data from KAI format
            singers: Dictionary of singer info

        Returns:
            Formatted cue text
        """
        text = line_data['text']
        singer_id = line_data.get('singer', 'A')
        backup = line_data.get('backup', False)
        word_timing = line_data.get('word_timing', [])

        # Start with voice tag if singer specified
        cue_parts = []
        if singer_id and singer_id in singers:
            cue_parts.append(f"<v {singer_id}>")

        # Add class tag for backup vocals
        if backup:
            cue_parts.append("<c.backup>")

        # Add word-level timing if available
        if word_timing and len(word_timing) > 0:
            # Split text into words
            words = text.split()

            if len(words) == len(word_timing):
                # Build text with karaoke timestamps
                word_parts = []
                line_start = line_data['start']

                for i, word in enumerate(words):
                    word_start_rel, word_end_rel = word_timing[i]
                    # Convert relative time to absolute
                    word_start_abs = line_start + word_start_rel

                    # Add timestamp before word (karaoke-style)
                    timestamp = self._format_timestamp(word_start_abs)
                    word_parts.append(f"<{timestamp}>{word}")

                text_with_timing = " ".join(word_parts)
                cue_parts.append(text_with_timing)
            else:
                # Mismatch between words and timing - just use plain text
                logger.warning(
                    f"Word count mismatch: {len(words)} words, {len(word_timing)} timings"
                )
                cue_parts.append(text)
        else:
            # No word timing - just plain text
            cue_parts.append(text)

        # Close backup class tag
        if backup:
            cue_parts.append("</c>")

        return "".join(cue_parts)

    def validate_webvtt(self, vtt_content: str) -> bool:
        """
        Validate WebVTT content.

        Args:
            vtt_content: WebVTT string to validate

        Returns:
            True if valid
        """
        lines = vtt_content.split('\n')

        # Must start with WEBVTT
        if not lines or lines[0].strip() != 'WEBVTT':
            logger.error("WebVTT must start with 'WEBVTT'")
            return False

        # Check for at least one cue
        has_cue = any('-->' in line for line in lines)
        if not has_cue:
            logger.warning("WebVTT has no cues")
            return False

        return True
