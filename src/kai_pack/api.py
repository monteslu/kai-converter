"""API facade for GUI integration.

This module provides a clean, GUI-friendly interface to the KAI processing pipeline.
It wraps the existing KaiProcessor with structured results, progress callbacks,
and exception handling, making it easy to integrate with Electron or other GUIs.
"""

import json
import logging
import traceback
import sys
from pathlib import Path
from typing import Dict, Any, Optional, Callable, List

from .processor import KaiProcessor


# Configure logging to go to stderr (not stdout)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)


# Progress callback signature: (stage: str, percent: float, message: str) -> None
ProgressCallback = Callable[[str, float, str], None]


class KaiAPI:
    """
    High-level API for KAI file processing.

    This class provides a simplified interface suitable for GUI applications.
    Results are returned as structured dictionaries instead of using exit codes,
    and progress updates are delivered via callbacks.

    Example:
        def on_progress(stage: str, percent: float, message: str):
            print(f"[{stage}] {percent:.0f}% - {message}")

        api = KaiAPI(progress_callback=on_progress)
        result = api.process_audio(
            input_file="/path/to/song.mp3",
            output_file="/path/to/song.kai",
            whisper_model="small",
            language="en"
        )

        if result["success"]:
            print(f"Created: {result['output_file']}")
        else:
            print(f"Error: {result['error']}")
    """

    def __init__(self, progress_callback: Optional[ProgressCallback] = None):
        """
        Initialize the API.

        Args:
            progress_callback: Optional callback function for progress updates.
                               Signature: (stage: str, percent: float, message: str) -> None
        """
        self.progress_callback = progress_callback
        self._processor = None

    def _emit_progress(self, stage: str, percent: float, message: str) -> None:
        """Emit a progress update if callback is registered."""
        if self.progress_callback:
            try:
                self.progress_callback(stage, percent, message)
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")

    def process_audio(
        self,
        input_file: str,
        output_file: Optional[str] = None,
        output_format: str = "kai",  # 'kai' or 'm4a'
        whisper_model: str = "small",
        language: str = "en",
        device: Optional[str] = None,
        four_stems: bool = False,
        stem_bitrate: str = "160k",
        vocals_bitrate: Optional[str] = None,
        features: Optional[List[str]] = None,
        title: Optional[str] = None,
        artist: Optional[str] = None,
        cover_art: Optional[str] = None,
        lyrics_url: Optional[str] = None,
        reference_lyrics: Optional[str] = None,
        use_crepe_filter: bool = False,
        silence_threshold: int = -20,
        vocal_pitch_type: str = "midi_cents",
        sample_rate: int = 44100,
        demucs_model: str = "htdemucs_ft",
        chunk_size: int = 44100,
        overlap: float = 0.25,
        include_id3_raw: bool = True,
        verbose: bool = False,
        # LLM lyric correction parameters
        llm_enabled: bool = False,
        llm_provider: Optional[str] = None,
        llm_model: Optional[str] = None,
        llm_api_key: Optional[str] = None,
        llm_base_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process an audio file into KAI karaoke format.

        This is the main entry point for converting audio to KAI format.

        Args:
            input_file: Path to input audio file (MP3, WAV, FLAC, etc.)
            output_file: Path to output .kai file (default: <input>.kai)
            whisper_model: Whisper model size (tiny, base, small, medium, large, large-v3)
            language: Language code (en, es, fr, etc.) or 'auto' for auto-detection
            device: Processing device ('cuda', 'cpu', 'mps', or None for auto)
            four_stems: Use 4-stem separation (vocals/drums/bass/other) vs 2-stem (vocals/music)
            stem_bitrate: MP3 bitrate for instrumental stems (default: 160k)
            vocals_bitrate: MP3 bitrate for vocals (default: same as stem_bitrate)
            features: List of features to extract (e.g., ['f0', 'tempo'])
            title: Override song title from ID3 metadata
            artist: Override artist name from ID3 metadata
            cover_art: Path to cover art image file
            lyrics_url: LRCLIB URL for reference lyrics
            use_crepe_filter: Enable CREPE filtering for extreme vocals
            silence_threshold: Silence threshold in dB (default: -20)
            vocal_pitch_type: Pitch quantization type (midi_cents, note_only_rle, etc.)
            sample_rate: Target sample rate for processing (default: 44100)
            demucs_model: Demucs model name (default: htdemucs_ft)
            chunk_size: Demucs chunk size in samples (default: 44100)
            overlap: Demucs overlap fraction 0-1 (default: 0.25)
            include_id3_raw: Include raw ID3 frames in metadata (default: True)
            verbose: Enable verbose logging

        Returns:
            Dictionary with processing results:
            {
                "success": bool,              # True if processing succeeded
                "output_file": str,           # Path to created .kai file (if success)
                "processing_time": float,     # Processing time in seconds (if success)
                "stats": {                    # Processing statistics (if success)
                    "lines": int,             # Number of lyric lines
                    "confidence": float,      # Transcription confidence (0-1)
                    "stems": int,             # Number of audio stems
                    "features": int           # Number of features extracted
                },
                "error": str,                 # Error message (if not success)
                "error_type": str,            # Error type/category (if not success)
                "traceback": str              # Full error traceback (if not success and verbose)
            }
        """
        try:
            # Convert paths
            input_path = Path(input_file)
            if not input_path.exists():
                return {
                    "success": False,
                    "error": f"Input file not found: {input_file}",
                    "error_type": "FileNotFoundError"
                }

            # Auto-generate output path if not provided
            if output_file is None:
                if output_format == 'm4a':
                    # For M4A format, use .stem.m4a extension
                    output_path = input_path.with_suffix('.stem.m4a')
                else:
                    output_path = input_path.with_suffix('.kai')
            else:
                output_path = Path(output_file)

            # Ensure correct extension based on format
            if output_format == 'm4a':
                if not str(output_path).endswith('.stem.m4a'):
                    # Replace extension with .stem.m4a
                    output_path = Path(str(output_path).rsplit('.', 1)[0] + '.stem.m4a')
            else:
                if output_path.suffix != '.kai':
                    output_path = output_path.with_suffix('.kai')

            # Parse features list
            features_list = features or []

            # Default vocals bitrate to stem bitrate if not specified
            if vocals_bitrate is None:
                vocals_bitrate = stem_bitrate

            # Create metadata overrides
            metadata_overrides = {}
            if title:
                metadata_overrides["title"] = title
            if artist:
                metadata_overrides["artist"] = artist

            # Convert cover art path
            cover_path = Path(cover_art) if cover_art else None

            # Progress tracking
            self._emit_progress("initializing", 0, "Initializing processor...")

            # Create processor with progress callback
            self._processor = KaiProcessor(
                sample_rate=sample_rate,
                model_name=demucs_model,
                chunk_size=chunk_size,
                overlap=overlap,
                device=device,
                whisper_model=whisper_model,
                language=language,
                lyrics_url=lyrics_url,
                reference_lyrics=reference_lyrics,
                use_crepe_filter=use_crepe_filter,
                silence_threshold=silence_threshold,
                vocal_pitch_type=vocal_pitch_type,
                verbose=verbose,
                progress_callback=self.progress_callback,
                llm_enabled=llm_enabled,
                llm_provider=llm_provider,
                llm_model=llm_model,
                llm_api_key=llm_api_key,
                llm_base_url=llm_base_url
            )

            self._emit_progress("loading", 5, "Loading audio file...")

            # Route to appropriate processing method based on output format
            if output_format == 'm4a':
                # Process to M4A Stems format
                result = self._processor.process_to_m4a(
                    input_audio=input_path,
                    output_path=output_path,
                    features=features_list,
                    metadata_overrides=metadata_overrides,
                    cover_art=cover_path,
                    stems_profile="STEMS-4" if four_stems else "STEMS-2",
                    codec="aac",  # Could be made configurable later
                    bitrate="256k"  # Could be made configurable later
                )
            else:
                # Process to KAI format (default)
                result = self._processor.process(
                    input_audio=input_path,
                    output_path=output_path,
                    stem_bitrate=stem_bitrate,
                    vocals_bitrate=vocals_bitrate,
                    features=features_list,
                    metadata_overrides=metadata_overrides,
                    cover_art=cover_path,
                    include_id3_raw=include_id3_raw,
                    create_music_stem=not four_stems
                )

            # Apply LLM lyric correction if enabled (KAI format only - M4A correction is done before packaging)
            llm_stats = None
            if llm_enabled and llm_provider and output_format == 'kai':
                self._emit_progress("llm_correction", 95, "Applying AI lyric correction...")
                logger.info("LLM correction enabled, running fix_lyrics...")

                try:
                    import tempfile
                    import os
                    from utils.fix_lyrics import fix_lyrics_direct

                    # Map GUI provider names to fix_lyrics provider names
                    provider_map = {
                        'claude': 'anthropic',
                        'openai': 'openai',
                        'gemini': 'gemini',
                        'local': 'lmstudio'
                    }

                    fix_provider = provider_map.get(llm_provider, llm_provider)

                    # Save reference lyrics to temp file if available (avoids third LRCLIB lookup)
                    lyrics_source_file = None
                    if reference_lyrics:
                        lyrics_temp_fd, lyrics_source_file = tempfile.mkstemp(suffix='.txt', prefix='reference_lyrics_')
                        with open(lyrics_source_file, 'w', encoding='utf-8') as f:
                            f.write(reference_lyrics)
                        os.close(lyrics_temp_fd)
                        logger.info(f"Using pre-fetched lyrics for LLM correction: {lyrics_source_file}")

                    # Call fix_lyrics_direct on the output KAI file
                    fix_result = fix_lyrics_direct(
                        kai_file=output_path,
                        lyrics_source=lyrics_source_file,  # Use pre-fetched lyrics
                        output=output_path,  # Overwrite the original file
                        llm_provider=fix_provider,
                        llm_model=llm_model,
                        llm_api_key=llm_api_key,
                        llm_base_url=llm_base_url,
                        progress_callback=self.progress_callback
                    )

                    # Clean up temp file
                    if lyrics_source_file:
                        try:
                            os.unlink(lyrics_source_file)
                        except Exception as e:
                            logger.warning(f"Failed to clean up temp lyrics file: {e}")

                    if fix_result.get("success"):
                        logger.info(f"LLM correction applied: {fix_result.get('corrections_applied', 0)} corrections")
                        llm_stats = {
                            "corrections_applied": fix_result.get("corrections_applied", 0),
                            "suggestions_made": fix_result.get("suggestions_made", 0),
                            "corrections_rejected": fix_result.get("corrections_rejected", 0),
                            "failed": False
                        }
                    else:
                        logger.warning(f"LLM correction failed: {fix_result.get('error', 'Unknown error')}")
                        llm_stats = {
                            "corrections_applied": 0,
                            "suggestions_made": 0,
                            "corrections_rejected": 0,
                            "failed": True,
                            "error": fix_result.get("error", "Unknown error")
                        }

                except Exception as e:
                    logger.error(f"LLM correction error: {e}")
                    llm_stats = {
                        "corrections_applied": 0,
                        "suggestions_made": 0,
                        "corrections_rejected": 0,
                        "failed": True,
                        "error": str(e)
                    }

            self._emit_progress("complete", 100, "Processing complete!")

            # Return structured success result
            response = {
                "success": True,
                "output_file": str(output_path),
                "processing_time": result.get("processing_time_seconds", 0),
                "stats": {
                    "lines": result.get("processing_stats", {}).get("lines_aligned", 0) or result.get("stats", {}).get("lines", 0),
                    "confidence": result.get("processing_stats", {}).get("alignment_confidence", 0.0) or result.get("stats", {}).get("confidence", 0.0),
                    "stems": result.get("processing_stats", {}).get("stems_separated", 0) or result.get("stats", {}).get("stems", 0),
                    "features": result.get("processing_stats", {}).get("features_extracted", 0) or result.get("stats", {}).get("features", 0)
                },
                "input_info": result.get("input_info", {}),
                "validation": result.get("validation", {})
            }

            # Add LLM stats from either KAI correction (local llm_stats) or M4A correction (result['llm_stats'])
            if llm_stats:
                response["llm_stats"] = llm_stats
            elif result.get("llm_stats"):
                response["llm_stats"] = result["llm_stats"]

            return response

        except FileNotFoundError as e:
            error_msg = f"File not found: {str(e)}"
            logger.error(error_msg)
            self._emit_progress("error", 0, error_msg)
            return {
                "success": False,
                "error": error_msg,
                "error_type": "FileNotFoundError"
            }

        except PermissionError as e:
            error_msg = f"Permission denied: {str(e)}"
            logger.error(error_msg)
            self._emit_progress("error", 0, error_msg)
            return {
                "success": False,
                "error": error_msg,
                "error_type": "PermissionError"
            }

        except ValueError as e:
            error_msg = f"Invalid parameter: {str(e)}"
            logger.error(error_msg)
            self._emit_progress("error", 0, error_msg)
            return {
                "success": False,
                "error": error_msg,
                "error_type": "ValueError"
            }

        except Exception as e:
            error_msg = f"Processing failed: {str(e)}"
            logger.error(error_msg)
            if verbose:
                logger.exception("Full traceback:")
            self._emit_progress("error", 0, error_msg)

            result = {
                "success": False,
                "error": error_msg,
                "error_type": type(e).__name__
            }

            if verbose:
                result["traceback"] = traceback.format_exc()

            return result

    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about loaded models and components.

        Returns:
            Dictionary with model information, or error if processor not initialized.
        """
        if self._processor is None:
            return {
                "error": "Processor not initialized. Call process_audio() first."
            }

        try:
            return self._processor.get_model_info()
        except Exception as e:
            logger.error(f"Failed to get model info: {e}")
            return {
                "error": str(e)
            }

    def regenerate_lyrics(
        self,
        input_file: str,
        output_file: Optional[str] = None,
        whisper_model: str = "large-v3-turbo",
        language: str = "en",
        reference_lyrics: Optional[str] = None,
        llm_enabled: bool = False,
        llm_provider: Optional[str] = None,
        llm_model: Optional[str] = None,
        llm_api_key: Optional[str] = None,
        llm_base_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Regenerate lyrics in a KAI file using Whisper re-transcription.

        Args:
            input_file: Path to input .kai file
            output_file: Path to output .kai file (default: overwrite input)
            whisper_model: Whisper model size
            language: Language code
            reference_lyrics: Reference lyrics for LLM correction
            llm_enabled: Enable LLM lyric correction
            llm_provider: LLM provider (claude/openai/gemini/local)
            llm_model: LLM model name
            llm_api_key: API key for LLM provider
            llm_base_url: Base URL for local LLM

        Returns:
            Dictionary with success status and result info
        """
        try:
            import sys
            import tempfile
            import zipfile
            import shutil
            from pathlib import Path
            import soundfile as sf
            import numpy as np

            # Import transcription utilities
            from kai_pack.transcription import LyricsTranscriber
            from utils.lyrics_utils import prepare_whisper_context

            input_path = Path(input_file)
            if not input_path.exists():
                return {
                    "success": False,
                    "error": f"Input file not found: {input_file}",
                    "error_type": "FileNotFoundError"
                }

            output_path = Path(output_file) if output_file else input_path

            # Create temp directory for extraction
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Extract KAI file
                self._emit_progress("extract", 10, "Extracting KAI file...")
                with zipfile.ZipFile(input_path, 'r') as z:
                    z.extractall(temp_path)

                # Load existing song.json
                song_json_path = temp_path / "song.json"
                if not song_json_path.exists():
                    return {
                        "success": False,
                        "error": "Invalid KAI file: no song.json found",
                        "error_type": "InvalidKAIFile"
                    }

                with open(song_json_path, 'r') as f:
                    existing_data = json.load(f)

                # Load vocals audio
                vocals_path = temp_path / "vocals.mp3"
                if not vocals_path.exists():
                    return {
                        "success": False,
                        "error": "Invalid KAI file: no vocals.mp3 found",
                        "error_type": "InvalidKAIFile"
                    }

                self._emit_progress("load_vocals", 20, "Loading vocals audio...")
                audio, sr = sf.read(str(vocals_path))

                # Convert to expected format
                if audio.ndim == 1:
                    vocals_audio = np.array([audio, audio])
                else:
                    vocals_audio = audio.T

                # Prepare Whisper context from reference lyrics using proper function
                whisper_context = None
                lyrics_temp_file = None
                if reference_lyrics:
                    # Extract title and artist from existing KAI file metadata
                    title = existing_data.get('title', '')
                    artist = existing_data.get('artist', '')

                    # Use prepare_whisper_context to get proper token-scored vocabulary hints
                    whisper_context, lyrics_temp_file = prepare_whisper_context(
                        title=title,
                        artist=artist,
                        reference_lyrics=reference_lyrics
                    )

                # Transcribe vocals
                self._emit_progress("transcribe", 30, "Transcribing vocals with Whisper...")
                logger.info(f"Starting Whisper transcription with model: {whisper_model}, language: {language}")
                if whisper_context:
                    logger.info(f"Using Whisper prompt with vocabulary hints")
                    logger.info(f"Whisper prompt: {whisper_context}")

                transcriber = LyricsTranscriber(
                    sample_rate=sr,
                    model_name=whisper_model,
                    language=language,
                    device=None  # Auto-detect
                )

                transcription_result = transcriber.transcribe_and_align(
                    vocals_audio=vocals_audio,
                    use_chunking=False,  # Use full audio for better coherence
                    initial_prompt=whisper_context
                )

                # Extract lines from transcription result
                new_lyrics = transcription_result.get('lines', [])

                # Apply LLM correction if enabled
                if llm_enabled and reference_lyrics:
                    self._emit_progress("llm_correction", 80, "Applying LLM lyric correction...")
                    from utils.fix_lyrics import fix_lyrics_with_llm
                    import sys
                    import io

                    llm_config = {
                        'provider': llm_provider,
                        'model': llm_model,
                        'api_key': llm_api_key,
                        'base_url': llm_base_url
                    }

                    # Suppress stdout from fix_lyrics_with_llm to avoid polluting JSON output
                    old_stdout = sys.stdout
                    sys.stdout = io.StringIO()

                    try:
                        llm_result = fix_lyrics_with_llm(
                            new_lyrics,
                            reference_lyrics,
                            llm_config=llm_config,
                            song_data=existing_data
                        )

                        # fix_lyrics_with_llm returns a tuple: (corrected_lines, rejections, missing_lines, corrections_applied)
                        if llm_result and len(llm_result) == 4 and llm_result[0] is not None:
                            corrected_lines, rejections, missing_lines, corrections_applied = llm_result
                            new_lyrics = corrected_lines
                    finally:
                        # Restore stdout
                        sys.stdout = old_stdout

                # Update song.json with new lyrics
                existing_data['lyrics'] = new_lyrics

                # Save updated song.json
                self._emit_progress("save", 90, "Saving updated KAI file...")
                with open(song_json_path, 'w') as f:
                    json.dump(existing_data, f, indent=2)

                # Repack KAI file
                with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as z:
                    for file_path in temp_path.iterdir():
                        if file_path.is_file():
                            z.write(file_path, file_path.name)

                self._emit_progress("complete", 100, "Lyrics regeneration complete")

                return {
                    "success": True,
                    "output_file": str(output_path),
                    "lines_count": len(new_lyrics)
                }

        except Exception as e:
            logger.error(f"Lyrics regeneration failed: {e}")
            import traceback
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc()
            }

    def fix_lyrics(
        self,
        input_file: str,
        output_file: Optional[str] = None,
        reference_lyrics: Optional[str] = None,
        llm_provider: Optional[str] = None,
        llm_model: Optional[str] = None,
        llm_api_key: Optional[str] = None,
        llm_base_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fix lyrics in a KAI file using LLM correction (no Whisper re-transcription).

        Args:
            input_file: Path to input .kai file
            output_file: Path to output .kai file (default: overwrite input)
            reference_lyrics: Reference lyrics for correction
            llm_provider: LLM provider (claude/openai/gemini/local)
            llm_model: LLM model name
            llm_api_key: API key for LLM provider
            llm_base_url: Base URL for local LLM

        Returns:
            Dictionary with success status and correction info
        """
        try:
            import tempfile
            import zipfile
            from pathlib import Path
            from utils.fix_lyrics import fix_lyrics_with_llm

            input_path = Path(input_file)
            if not input_path.exists():
                return {
                    "success": False,
                    "error": f"Input file not found: {input_file}",
                    "error_type": "FileNotFoundError"
                }

            output_path = Path(output_file) if output_file else input_path

            # Reference lyrics are required for LLM correction to work
            if not reference_lyrics:
                return {
                    "success": False,
                    "error": "Reference lyrics are required for fix_lyrics. Use regenerate_lyrics if you want to re-transcribe without correction.",
                    "error_type": "MissingParameter"
                }

            # Create temp directory for extraction
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Extract KAI file
                with zipfile.ZipFile(input_path, 'r') as z:
                    z.extractall(temp_path)

                # Load existing song.json
                song_json_path = temp_path / "song.json"
                if not song_json_path.exists():
                    return {
                        "success": False,
                        "error": "Invalid KAI file: no song.json found",
                        "error_type": "InvalidKAIFile"
                    }

                with open(song_json_path, 'r') as f:
                    song_data = json.load(f)

                existing_lyrics = song_data.get('lyrics', [])

                # Apply LLM correction
                llm_config = {
                    'provider': llm_provider,
                    'model': llm_model,
                    'api_key': llm_api_key,
                    'base_url': llm_base_url
                }

                # Suppress stdout from fix_lyrics_with_llm to avoid polluting JSON output
                import sys
                import io
                old_stdout = sys.stdout
                sys.stdout = io.StringIO()

                try:
                    llm_result = fix_lyrics_with_llm(
                        existing_lyrics,
                        reference_lyrics,
                        llm_config=llm_config,
                        song_data=song_data,
                        kai_file_path=str(input_path)
                    )
                finally:
                    # Restore stdout
                    sys.stdout = old_stdout

                # fix_lyrics_with_llm returns a tuple: (corrected_lines, rejections, missing_lines, corrections_applied)
                if not llm_result or len(llm_result) != 4:
                    return {
                        "success": False,
                        "error": "LLM correction returned invalid result",
                        "error_type": "LLMError"
                    }

                corrected_lines, rejections, missing_lines, corrections_applied = llm_result

                if corrected_lines is None:
                    return {
                        "success": False,
                        "error": "LLM correction failed to return corrected lyrics",
                        "error_type": "LLMError"
                    }

                # Update song.json with corrected lyrics
                song_data['lyrics'] = corrected_lines

                # Store corrections count for result
                corrections_count = corrections_applied if isinstance(corrections_applied, int) else 0

                # Save updated song.json
                with open(song_json_path, 'w') as f:
                    json.dump(song_data, f, indent=2)

                # Repack KAI file
                with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as z:
                    for file_path in temp_path.iterdir():
                        if file_path.is_file():
                            z.write(file_path, file_path.name)

                return {
                    "success": True,
                    "output_file": str(output_path),
                    "corrections_count": corrections_count,
                    "rejections_count": len(rejections) if rejections else 0,
                    "missing_lines_count": len(missing_lines) if missing_lines else 0
                }

        except Exception as e:
            logger.error(f"Lyrics fix failed: {e}")
            import traceback
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc()
            }
