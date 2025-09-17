#!/usr/bin/env python3
"""Regenerate lyrics in KAI file using existing vocals stem."""

import json
import logging
import os
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import re

import click
import numpy as np
import soundfile as sf
import requests

# Add kai_pack to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from kai_pack.transcription import LyricsTranscriber


def setup_logging(verbose: bool) -> None:
    """Set up logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    format_str = "%(asctime)s - %(levelname)s - %(message)s"
    logging.basicConfig(level=level, format=format_str)


# Import common lyrics utilities
from utils.lyrics_utils import prepare_whisper_context, save_lyrics_temp_info


def extract_kai_file(kai_path: Path, temp_dir: Path) -> Dict[str, Any]:
    """Extract KAI file and return existing song.json data."""
    logger = logging.getLogger(__name__)

    logger.info(f"Extracting KAI file: {kai_path}")
    with zipfile.ZipFile(kai_path, 'r') as z:
        z.extractall(temp_dir)

    # Load existing song.json for metadata
    song_json_path = temp_dir / "song.json"
    if not song_json_path.exists():
        raise ValueError("Invalid KAI file: no song.json found")

    with open(song_json_path, 'r') as f:
        existing_data = json.load(f)

    # Verify vocals.mp3 exists
    vocals_path = temp_dir / "vocals.mp3"
    if not vocals_path.exists():
        raise ValueError("Invalid KAI file: no vocals.mp3 found")

    logger.info("✓ KAI file extracted successfully")
    return existing_data


def load_vocals_audio(vocals_path: Path, sample_rate: int = 44100) -> np.ndarray:
    """Load vocals audio from MP3."""
    logger = logging.getLogger(__name__)

    logger.info(f"Loading vocals audio: {vocals_path}")
    audio, sr = sf.read(str(vocals_path))

    # Convert to expected format (channels, samples)
    if audio.ndim == 1:
        # Mono audio
        vocals_audio = np.array([audio, audio])  # Duplicate to stereo
    else:
        # Stereo audio
        vocals_audio = audio.T  # Transpose to (channels, samples)

    logger.info(f"✓ Vocals loaded: {vocals_audio.shape[1]/sr:.1f}s, {sr}Hz")
    return vocals_audio


def regenerate_lyrics(
    existing_data: Dict[str, Any],
    vocals_audio: np.ndarray,
    whisper_model: str = "small",
    language: str = "en",
    sample_rate: int = 44100
) -> tuple[Dict[str, Any], Optional[str]]:
    """Regenerate only the lyrics in song.json with fresh transcription."""
    logger = logging.getLogger(__name__)

    logger.info("Starting lyrics transcription...")

    # Generate initial prompt from song metadata and lyrics
    song_data = existing_data.get("song", {})
    title = song_data.get("title", "")
    artist = song_data.get("artist", "")

    # Use common lyrics utility to prepare Whisper context
    initial_prompt, lyrics_temp_file = prepare_whisper_context(title, artist)

    # Initialize transcriber
    transcriber = LyricsTranscriber(
        sample_rate=sample_rate,
        model_name=whisper_model,
        language=language
    )

    # Run transcription
    logger.info("→ Running Whisper transcription...")
    alignment_data = transcriber.transcribe_and_align(vocals_audio, initial_prompt=initial_prompt)
    logger.info(f"✓ Transcribed {len(alignment_data.get('lines', []))} lines")

    # Copy existing song.json and update only lyrics sections
    updated_data = existing_data.copy()

    # Update the lines with new transcription
    updated_data["lines"] = alignment_data.get("lines", [])

    # Update timing section if it exists
    if "timing" in updated_data:
        updated_data["timing"].update({
            "alignment_method": alignment_data.get("alignment_method", "whisper"),
            "confidence": alignment_data.get("confidence", 0.0),
            "reference": alignment_data.get("reference", "aligned_to_vocals_wav")
        })

    logger.info("✓ Lyrics updated in song.json")
    return updated_data, lyrics_temp_file


def repack_kai_file(temp_dir: Path, output_path: Path, new_song_json: Dict[str, Any]) -> None:
    """Repack KAI file with new song.json."""
    logger = logging.getLogger(__name__)

    # Write new song.json
    song_json_path = temp_dir / "song.json"
    with open(song_json_path, 'w') as f:
        json.dump(new_song_json, f, indent=2)

    # Create new KAI file
    logger.info(f"→ Creating updated KAI file: {output_path}")
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as z:
        for file_path in temp_dir.rglob('*'):
            if file_path.is_file():
                arcname = file_path.relative_to(temp_dir)
                z.write(file_path, arcname)

    logger.info("✓ Updated KAI file created")


@click.command()
@click.argument("input_kai", type=click.Path(exists=True, path_type=Path))
@click.option("-o", "--output", type=click.Path(path_type=Path),
              help="Output KAI file (default: overwrite input)")
@click.option("--whisper-model", default="small",
              type=click.Choice(["tiny", "base", "small", "medium", "large", "large-v2", "large-v3", "large-v3-turbo"]),
              help="Whisper model for transcription")
@click.option("--language", default="en",
              help="Language code for transcription (or 'auto' for detection)")
@click.option("--verbose", is_flag=True, help="Verbose logging")
def main(
    input_kai: Path,
    output: Optional[Path],
    whisper_model: str,
    language: str,
    verbose: bool
) -> None:
    """Regenerate lyrics in KAI file using existing vocals stem.

    This preserves all existing data but regenerates only the lyrics/transcription.
    Uses LRCLIB to fetch reference lyrics for improved Whisper context.
    Useful for trying different Whisper models or language settings.
    """
    setup_logging(verbose)
    logger = logging.getLogger(__name__)

    if output is None:
        output = input_kai

    logger.info("========================================")
    logger.info("KAI Lyrics Regenerator")
    logger.info("========================================")
    logger.info(f"Input: {input_kai}")
    logger.info(f"Output: {output}")
    logger.info(f"Whisper model: {whisper_model}")
    logger.info(f"Language: {language}")

    try:
        with tempfile.TemporaryDirectory(prefix="kai_regen_lyrics_") as temp_dir:
            temp_path = Path(temp_dir)

            # Extract KAI file
            existing_data = extract_kai_file(input_kai, temp_path)

            # Load vocals audio
            vocals_audio = load_vocals_audio(temp_path / "vocals.mp3")

            # Regenerate only lyrics
            updated_song_json, lyrics_temp_file = regenerate_lyrics(
                existing_data=existing_data,
                vocals_audio=vocals_audio,
                whisper_model=whisper_model,
                language=language
            )

            # Repack KAI file
            repack_kai_file(temp_path, output, updated_song_json)

        logger.info("========================================")
        logger.info("✓ Lyrics regeneration complete!")
        logger.info("========================================")
        logger.info(f"Updated file: {output}")

        # Store temp file path for potential fix_lyrics usage
        if lyrics_temp_file:
            logger.info(f"Reference lyrics available for fix_lyrics: {lyrics_temp_file}")
            save_lyrics_temp_info(lyrics_temp_file)

    except Exception as e:
        logger.error(f"Lyrics regeneration failed: {e}")
        if verbose:
            logger.exception("Full traceback:")
        # Clean up temp file on error
        if 'lyrics_temp_file' in locals() and lyrics_temp_file:
            try:
                import os
                os.unlink(lyrics_temp_file)
            except:
                pass
        sys.exit(1)


if __name__ == "__main__":
    main()