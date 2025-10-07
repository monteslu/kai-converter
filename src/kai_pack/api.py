"""API facade for GUI integration.

This module provides a clean, GUI-friendly interface to the KAI processing pipeline.
It wraps the existing KaiProcessor with structured results, progress callbacks,
and exception handling, making it easy to integrate with Electron or other GUIs.
"""

import logging
import traceback
from pathlib import Path
from typing import Dict, Any, Optional, Callable, List

from .processor import KaiProcessor


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
                output_path = input_path.with_suffix('.kai')
            else:
                output_path = Path(output_file)

            # Ensure .kai extension
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
                use_crepe_filter=use_crepe_filter,
                silence_threshold=silence_threshold,
                vocal_pitch_type=vocal_pitch_type,
                verbose=verbose,
                progress_callback=self.progress_callback
            )

            self._emit_progress("loading", 5, "Loading audio file...")

            # Process the audio
            # Note: In Task 1.3, we'll add progress callback support to KaiProcessor
            # For now, we emit manual progress updates based on typical processing stages
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

            # Apply LLM lyric correction if enabled
            if llm_enabled and llm_provider:
                self._emit_progress("llm_correction", 95, "Applying AI lyric correction...")
                logger.info("LLM correction enabled, running fix_lyrics...")

                try:
                    from ..utils.fix_lyrics import fix_lyrics_direct

                    # Map GUI provider names to fix_lyrics provider names
                    provider_map = {
                        'claude': 'anthropic',
                        'openai': 'openai',
                        'local': 'lmstudio'
                    }

                    fix_provider = provider_map.get(llm_provider, llm_provider)

                    # Call fix_lyrics_direct on the output KAI file
                    fix_result = fix_lyrics_direct(
                        kai_file=output_path,
                        lyrics_source=None,  # Auto-fetch based on metadata
                        output=output_path,  # Overwrite the original file
                        llm_provider=fix_provider,
                        llm_model=llm_model,
                        llm_api_key=llm_api_key,
                        llm_base_url=llm_base_url,
                        progress_callback=self.progress_callback
                    )

                    if fix_result.get("success"):
                        logger.info(f"LLM correction applied: {fix_result.get('corrections_applied', 0)} corrections")
                    else:
                        logger.warning(f"LLM correction failed: {fix_result.get('error', 'Unknown error')}")
                        # Don't fail the entire process if LLM correction fails

                except Exception as e:
                    logger.error(f"LLM correction error: {e}")
                    # Don't fail the entire process if LLM correction fails

            self._emit_progress("complete", 100, "Processing complete!")

            # Return structured success result
            return {
                "success": True,
                "output_file": str(output_path),
                "processing_time": result.get("processing_time_seconds", 0),
                "stats": {
                    "lines": result.get("processing_stats", {}).get("lines_aligned", 0),
                    "confidence": result.get("processing_stats", {}).get("alignment_confidence", 0.0),
                    "stems": result.get("processing_stats", {}).get("stems_separated", 0),
                    "features": result.get("processing_stats", {}).get("features_extracted", 0)
                },
                "input_info": result.get("input_info", {}),
                "validation": result.get("validation", {})
            }

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
