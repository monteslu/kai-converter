"""Word-level timing alignment for audio segments with known lyrics."""

import os
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Union
import numpy as np
import whisper
from pydub import AudioSegment
import logging
from .whisper_utils import load_whisper_model

logger = logging.getLogger(__name__)


def align_words_to_audio(
    audio_path: Union[str, Path],
    start_time: float,
    end_time: float,
    lyrics: str,
    whisper_model: Union[str, whisper.Whisper] = "base",
    language: str = "en",
    device: Optional[str] = None
) -> Dict:
    """
    Align words to audio segment using forced alignment with Whisper.

    Args:
        audio_path: Path to MP3 or WAV file
        start_time: Start time in seconds
        end_time: End time in seconds
        lyrics: Text to align to the audio segment
        whisper_model: Whisper model name or loaded model instance
        language: Language code (e.g., 'en', 'es', 'fr')
        device: Device to use ('cuda', 'cpu', or None for auto)

    Returns:
        Dictionary with word timings:
        {
            "text": "full text",
            "words": [
                {"word": "hello", "start": 0.5, "end": 0.8},
                {"word": "world", "start": 0.9, "end": 1.2}
            ],
            "segment_start": original_start_time,
            "segment_end": original_end_time
        }
    """
    # Load audio file
    audio_path = Path(audio_path)
    if audio_path.suffix.lower() == '.mp3':
        audio = AudioSegment.from_mp3(str(audio_path))
    elif audio_path.suffix.lower() == '.wav':
        audio = AudioSegment.from_wav(str(audio_path))
    else:
        raise ValueError(f"Unsupported audio format: {audio_path.suffix}")

    # Extract segment
    start_ms = int(start_time * 1000)
    end_ms = int(end_time * 1000)
    segment = audio[start_ms:end_ms]

    # Convert to mono 16kHz for Whisper
    segment = segment.set_channels(1).set_frame_rate(16000)

    # Export to temporary WAV file
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
        temp_path = tmp_file.name
        segment.export(temp_path, format='wav')

    try:
        # Load Whisper model if needed
        if isinstance(whisper_model, str):
            logger.info(f"Loading Whisper model: {whisper_model}")
            model = load_whisper_model(whisper_model, device=device)
        else:
            model = whisper_model

        # Transcribe with forced alignment
        logger.debug(f"Aligning text: '{lyrics[:50]}...' to {end_time - start_time:.1f}s of audio")

        result = model.transcribe(
            temp_path,
            language=language,
            initial_prompt=lyrics,  # Guide transcription with known text
            word_timestamps=True,   # Get word-level timestamps
            condition_on_previous_text=False,  # Don't use context from other segments
            temperature=0.0,  # Deterministic
            no_speech_threshold=0.8,  # Be more lenient for forced alignment
            logprob_threshold=None,  # Accept all words
            compression_ratio_threshold=None  # No filtering
        )

        # Extract word timings and adjust to original audio timeline
        words = []
        for segment in result.get('segments', []):
            for word_data in segment.get('words', []):
                words.append({
                    'w': word_data['word'].strip(),  # KAI format uses 'w' for word
                    's': start_time + word_data['start'],  # 's' for start
                    'e': start_time + word_data['end'],  # 'e' for end
                    'probability': word_data.get('probability', 1.0)
                })

        return {
            'text': result.get('text', '').strip(),
            'words': words,
            'segment_start': start_time,
            'segment_end': end_time,
            'original_lyrics': lyrics,
            'language': result.get('language', language)
        }

    finally:
        # Clean up temp file
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def batch_align_segments(
    audio_path: Union[str, Path],
    segments: List[Dict],
    whisper_model: Union[str, whisper.Whisper] = "base",
    language: str = "en",
    device: Optional[str] = None
) -> List[Dict]:
    """
    Batch process multiple segments for word alignment.

    Args:
        audio_path: Path to audio file
        segments: List of segments with format:
            [{"start": 0.5, "end": 3.2, "text": "lyrics here"}, ...]
        whisper_model: Whisper model (reused across segments)
        language: Language code
        device: Device to use

    Returns:
        List of aligned segments with word timings
    """
    # Load model once for efficiency
    if isinstance(whisper_model, str):
        logger.info(f"Loading Whisper model: {whisper_model}")
        model = load_whisper_model(whisper_model, device=device)
    else:
        model = whisper_model

    aligned_segments = []
    for i, segment in enumerate(segments):
        logger.info(f"Aligning segment {i+1}/{len(segments)}")

        result = align_words_to_audio(
            audio_path=audio_path,
            start_time=segment['start'],
            end_time=segment['end'],
            lyrics=segment['text'],
            whisper_model=model,  # Pass loaded model
            language=language,
            device=device
        )
        aligned_segments.append(result)

    return aligned_segments


def realign_kai_lyrics(kai_data: Dict, audio_path: Union[str, Path],
                       whisper_model: str = "base", device: Optional[str] = None) -> Dict:
    """
    Re-align word timings in a KAI file's lyrics after correction.

    Args:
        kai_data: Parsed KAI file data (song.json contents)
        audio_path: Path to original audio file
        whisper_model: Whisper model to use
        device: Device for processing

    Returns:
        Updated KAI data with corrected word timings
    """
    if 'lyrics' not in kai_data or 'segments' not in kai_data['lyrics']:
        logger.warning("No lyrics segments found in KAI data")
        return kai_data

    language = kai_data['lyrics'].get('language', 'en')
    segments_to_align = []

    # Prepare segments for alignment
    for segment in kai_data['lyrics']['segments']:
        segments_to_align.append({
            'start': segment['start'],
            'end': segment['end'],
            'text': segment['text']
        })

    # Batch align all segments
    aligned = batch_align_segments(
        audio_path=audio_path,
        segments=segments_to_align,
        whisper_model=whisper_model,
        language=language,
        device=device
    )

    # Update KAI data with new word timings
    for i, segment in enumerate(kai_data['lyrics']['segments']):
        if i < len(aligned):
            segment['words'] = aligned[i]['words']
            # Keep original segment boundaries but update words
            segment['text'] = aligned[i]['original_lyrics']  # Preserve corrected text

    return kai_data


# Example usage
if __name__ == "__main__":
    # Example: Align a single segment
    result = align_words_to_audio(
        audio_path="/path/to/song.mp3",
        start_time=10.5,
        end_time=15.2,
        lyrics="gonna take you for a ride",
        whisper_model="base",
        language="en"
    )

    print("Aligned words:")
    for word in result['words']:
        print(f"  {word['w']}: {word['s']:.2f}s - {word['e']:.2f}s")