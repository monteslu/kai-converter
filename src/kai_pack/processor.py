"""Main processor that orchestrates the KAI-Pack pipeline."""

import hashlib
import logging
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

import numpy as np

from .audio import AudioProcessor
from .separation import StemSeparator
from .transcription import LyricsTranscriber
from .metadata import MetadataExtractor
from .analysis import MusicalAnalyzer
from .song_json import SongJsonGenerator
from .packaging import KaiPackager
from utils.lyrics_utils import prepare_whisper_context, save_lyrics_temp_info


logger = logging.getLogger(__name__)


class KaiProcessor:
    """Main processor that orchestrates the complete KAI-Pack pipeline."""

    def __init__(
        self,
        sample_rate: int = 44100,
        model_name: str = "htdemucs_ft",
        chunk_size: int = 44100,
        overlap: float = 0.25,
        device: Optional[str] = None,
        whisper_model: str = "base",
        language: str = "en",
        lyrics_url: Optional[str] = None,
        use_crepe_filter: bool = False,
        silence_threshold: int = -20,
        vocal_pitch_type: str = "midi_cents",
        verbose: bool = False,
        progress_callback: Optional[Any] = None
    ):
        self.sample_rate = sample_rate
        self.model_name = model_name
        self.verbose = verbose
        self.language = language
        self.lyrics_url = lyrics_url
        self.progress_callback = progress_callback

        # Initialize components
        self.audio_processor = AudioProcessor(sample_rate=sample_rate)
        self.stem_separator = StemSeparator(
            model_name=model_name,
            device=device,
            chunk_size=chunk_size,
            overlap=overlap
        )
        self.lyrics_transcriber = LyricsTranscriber(
            sample_rate=sample_rate,
            model_name=whisper_model,
            language=language,
            device=device,
            use_crepe_filter=use_crepe_filter,
            silence_threshold=silence_threshold
        )
        self.metadata_extractor = MetadataExtractor()
        self.musical_analyzer = MusicalAnalyzer(
            sample_rate=sample_rate,
            vocal_pitch_type=vocal_pitch_type
        )
        self.song_json_generator = SongJsonGenerator()
        self.packager = KaiPackager()

    def _emit_progress(self, step: int, total: int, message: str) -> None:
        """Emit progress update if callback is registered.

        Args:
            step: Current processing step (1-9)
            total: Total number of steps (usually 9)
            message: Progress message describing current operation
        """
        if self.progress_callback:
            try:
                # Calculate percentage based on step
                # Give more weight to time-intensive steps (separation, transcription)
                step_weights = {
                    1: 5,   # Loading audio
                    2: 2,   # Extracting metadata
                    3: 35,  # Stem separation (time-intensive)
                    4: 40,  # Lyrics transcription (time-intensive)
                    5: 8,   # Musical analysis (optional)
                    6: 5,   # Encoding MP3 stems
                    7: 2,   # Generating song.json
                    8: 1,   # Saving features
                    9: 2    # Packaging KAI file
                }

                # Calculate cumulative percentage
                completed_weight = sum(step_weights.get(i, 0) for i in range(1, step))
                percent = completed_weight

                stage = f"step_{step}"
                self.progress_callback(stage, percent, message)
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")
        
    def process(
        self,
        input_audio: Path,
        output_path: Path,
        stem_bitrate: str = "160k",
        vocals_bitrate: str = "128k",
        features: Optional[List[str]] = None,
        metadata_overrides: Optional[Dict[str, str]] = None,
        cover_art: Optional[Path] = None,
        include_meta: bool = True,
        include_id3_raw: bool = True,
        create_music_stem: bool = True
    ) -> Dict[str, Any]:
        """
        Process audio into KAI format with AI-generated lyrics.
        
        Args:
            input_audio: Path to input audio file
            output_path: Output .kai file path
            stem_bitrate: MP3 bitrate for stems
            vocals_bitrate: MP3 bitrate for vocals
            features: List of features to extract
            metadata_overrides: Optional metadata overrides
            cover_art: Optional cover art file
            include_meta: Whether to include optional meta section
            include_id3_raw: Whether to include raw ID3 frames
            create_music_stem: Whether to create music.mp3 from non-vocal stems (default True for 2-stem mode)
            
        Returns:
            Dict with processing results and statistics
        """
        logger.info(f"Starting KAI processing: {input_audio} -> {output_path}")
        
        start_time = datetime.utcnow()
        features = features or []
        
        # Create temporary working directory
        with tempfile.TemporaryDirectory(prefix="kai_pack_") as temp_dir:
            temp_path = Path(temp_dir)
            
            try:
                # Step 1: Load and preprocess audio
                self._emit_progress(1, 9, "Loading and preprocessing audio...")
                logger.info("=" * 60)
                logger.info("STEP 1/9: LOADING AND PREPROCESSING AUDIO")
                logger.info("=" * 60)
                logger.info(f"Input file: {input_audio}")
                logger.info(f"Target sample rate: {self.sample_rate} Hz")

                start_step = datetime.utcnow()
                audio_data, audio_info = self.audio_processor.load_and_preprocess(input_audio)
                step_time = (datetime.utcnow() - start_step).total_seconds()

                logger.info(f"✓ Audio loaded: {audio_info['duration_seconds']:.1f}s, {audio_info['original_channels']} channels")
                logger.info(f"✓ Step 1 completed in {step_time:.1f}s")
                
                # Step 2: Extract metadata
                self._emit_progress(2, 9, "Extracting metadata...")
                logger.info("\n" + "=" * 60)
                logger.info("STEP 2/9: EXTRACTING METADATA")
                logger.info("=" * 60)

                start_step = datetime.utcnow()
                metadata = self.metadata_extractor.extract_metadata(
                    input_audio,
                    overrides=metadata_overrides
                )
                step_time = (datetime.utcnow() - start_step).total_seconds()

                logger.info(f"✓ Title: {metadata['song'].get('title', 'Unknown')}")
                logger.info(f"✓ Artist: {metadata['song'].get('artist', 'Unknown')}")
                logger.info(f"✓ Step 2 completed in {step_time:.1f}s")
                
                # Update metadata with actual audio info
                metadata["song"].update({
                    "duration_sec": audio_info["duration_seconds"],
                    "sample_rate": audio_info["target_sample_rate"],
                    "channels": 2
                })
                
                # Step 3: Stem separation
                self._emit_progress(3, 9, "Separating stems with Demucs...")
                logger.info("\n" + "=" * 60)
                logger.info("STEP 3/9: PERFORMING STEM SEPARATION (DEMUCS)")
                logger.info("=" * 60)
                logger.info(f"Model: {self.model_name}")
                logger.info(f"Device: {self.stem_separator.device}")
                logger.info("Separating into: vocals, drums, bass, other")

                start_step = datetime.utcnow()
                stems = self.stem_separator.separate_stems(audio_data, self.sample_rate)
                step_time = (datetime.utcnow() - start_step).total_seconds()
                
                logger.info(f"✓ Stems separated: {', '.join(stems.keys())}")
                for stem_name, stem_audio in stems.items():
                    logger.info(f"  - {stem_name}: {stem_audio.shape}")
                logger.info(f"✓ Step 3 completed in {step_time:.1f}s")
                
                # Save stems as WAV for processing
                stem_wav_files = {}
                for stem_name, stem_audio in stems.items():
                    wav_path = temp_path / f"{stem_name}.wav"
                    self.audio_processor.save_wav(stem_audio, wav_path)
                    stem_wav_files[stem_name] = wav_path
                
                # Create music.wav if requested (combine non-vocal stems right after separation)
                if create_music_stem:
                    logger.info("Creating music.wav from non-vocal stems...")
                    non_vocal_stems = []
                    for stem_name in ['drums', 'bass', 'other']:
                        if stem_name in stems:
                            non_vocal_stems.append(stems[stem_name])
                    
                    if non_vocal_stems:
                        music_audio = np.mean(non_vocal_stems, axis=0)
                        music_wav_path = temp_path / "music.wav"
                        self.audio_processor.save_wav(music_audio, music_wav_path)
                        stem_wav_files["music"] = music_wav_path
                        logger.info(f"  ✓ Created music.wav from {len(non_vocal_stems)} non-vocal stems")
                        
                        # Remove individual non-vocal stems in 2-stem mode
                        for stem_name in ['drums', 'bass', 'other']:
                            if stem_name in stem_wav_files:
                                del stem_wav_files[stem_name]
                        logger.info("  ✓ Using 2-stem mode: vocals + music only")
                    
                # Step 4: Automatic lyrics transcription and alignment
                self._emit_progress(4, 9, "Transcribing lyrics with Whisper...")
                logger.info("\n" + "=" * 60)
                logger.info("STEP 4/9: AI LYRICS TRANSCRIPTION (WHISPER FULL AUDIO)")
                logger.info("=" * 60)

                vocals_audio = stems.get("vocals")
                if vocals_audio is None:
                    raise ValueError("No vocals stem found for transcription")

                logger.info(f"Whisper model: {self.lyrics_transcriber.model_name}")
                logger.info(f"Vocals audio shape: {vocals_audio.shape}")

                # Prepare Whisper context with LRCLIB vocabulary hints
                title = metadata['song'].get('title', '')
                artist = metadata['song'].get('artist', '')
                initial_prompt, lyrics_temp_file = prepare_whisper_context(title, artist, self.lyrics_url)

                logger.info("Starting smart chunking and transcription...")

                start_step = datetime.utcnow()
                alignment_data = self.lyrics_transcriber.transcribe_and_align(vocals_audio, initial_prompt=initial_prompt)
                step_time = (datetime.utcnow() - start_step).total_seconds()
                
                logger.info(f"✓ Transcription completed:")
                logger.info(f"  - Lines found: {len(alignment_data.get('lines', []))}")
                logger.info(f"  - Confidence: {alignment_data.get('confidence', 0.0):.2f}")
                logger.info(f"  - Language: {alignment_data.get('language', 'unknown')}")
                logger.info(f"✓ Step 4 completed in {step_time:.1f}s")
                
                # Step 5: Musical analysis (if requested)
                analysis_features = {}
                if features:
                    self._emit_progress(5, 9, "Extracting musical features...")
                    logger.info("\n" + "=" * 60)
                    logger.info("STEP 5/9: MUSICAL ANALYSIS (OPTIONAL)")
                    logger.info("=" * 60)
                    logger.info(f"Features requested: {', '.join(features)}")

                    start_step = datetime.utcnow()
                    analysis_features = self.musical_analyzer.extract_features(
                        vocals_audio, audio_data, features
                    )
                    step_time = (datetime.utcnow() - start_step).total_seconds()

                    logger.info(f"✓ Features extracted: {len(analysis_features)}")
                    for feature_name in analysis_features:
                        logger.info(f"  - {feature_name}")
                    logger.info(f"✓ Step 5 completed in {step_time:.1f}s")
                else:
                    self._emit_progress(5, 9, "Skipping musical analysis...")
                    logger.info("\n" + "=" * 60)
                    logger.info("STEP 5/9: MUSICAL ANALYSIS (SKIPPED)")
                    logger.info("=" * 60)
                    logger.info("No features requested - skipping analysis")
                    
                # Step 6: Encode MP3 stems
                self._emit_progress(6, 9, "Encoding MP3 stems...")
                logger.info("\n" + "=" * 60)
                logger.info("STEP 6/9: ENCODING MP3 STEMS")
                logger.info("=" * 60)
                if vocals_bitrate == stem_bitrate:
                    logger.info(f"All stems bitrate: {stem_bitrate}")
                else:
                    logger.info(f"Vocals bitrate: {vocals_bitrate}")
                    logger.info(f"Other stems bitrate: {stem_bitrate}")

                start_step = datetime.utcnow()
                stem_mp3_files = {}
                encoder_delays = {}
                
                for stem_name, wav_path in stem_wav_files.items():
                    mp3_path = temp_path / f"{stem_name}.mp3"
                    bitrate = vocals_bitrate if stem_name == "vocals" else stem_bitrate
                    
                    logger.info(f"→ Encoding {stem_name}.mp3 at {bitrate}...")
                    encoding_info = self.audio_processor.encode_mp3_with_ffmpeg(
                        wav_path, mp3_path, bitrate, metadata, stem_name
                    )
                    
                    stem_mp3_files[stem_name] = mp3_path
                    encoder_delays[stem_name] = encoding_info["encoder_delay_samples"]
                    
                    # Check file size
                    file_size = mp3_path.stat().st_size
                    logger.info(f"  ✓ {stem_name}.mp3: {file_size:,} bytes, delay: {encoder_delays[stem_name]} samples")
                
                
                step_time = (datetime.utcnow() - start_step).total_seconds()
                logger.info(f"✓ Step 6 completed in {step_time:.1f}s")
                    
                # Use vocals encoder delay as canonical (they should all be the same)
                canonical_encoder_delay = encoder_delays.get("vocals", 1105)
                
                # Step 7: Generate song.json
                self._emit_progress(7, 9, "Generating song.json...")
                logger.info("\n" + "=" * 60)
                logger.info("STEP 7/9: GENERATING SONG.JSON")
                logger.info("=" * 60)
                logger.info("Creating KAI v1.0 descriptor with metadata, timing, and audio info...")

                start_step = datetime.utcnow()
                
                # Prepare processing information for meta section
                processing_info = {
                    "timestamp": start_time.isoformat() + "Z",
                    "source_filename": input_audio.name,
                    "source_sha256": self._compute_file_hash(input_audio),
                    "processing": {
                        "separation": {
                            "model": self.model_name,
                            "device": self.stem_separator.device,
                            "profile": "KAI-4"
                        },
                        "alignment": {
                            "method": alignment_data.get("alignment_method", "heuristic"),
                            "confidence": alignment_data.get("confidence", 0.5)
                        },
                        "analysis": {
                            "features": features,
                            "methods": {feat: analysis_features.get(feat, {}).get("method", "unknown") 
                                      for feat in features if feat in analysis_features}
                        }
                    }
                }
                
                song_json = self.song_json_generator.generate(
                    metadata=metadata,
                    audio_info=audio_info,
                    alignment_data=alignment_data,
                    stem_info=stem_mp3_files,  # Pass the actual encoded stems, not the original demucs stems
                    encoder_delay=canonical_encoder_delay,
                    processing_info=processing_info,
                    analysis_features=analysis_features,
                    include_meta=include_meta,
                    include_id3_raw=include_id3_raw
                )
                
                step_time = (datetime.utcnow() - start_step).total_seconds()
                
                # Validate song.json
                if not self.song_json_generator.validate_json(song_json):
                    raise ValueError("Generated song.json failed validation")
                
                logger.info(f"✓ song.json generated: {len(song_json)} top-level keys")
                logger.info(f"  - kai_version: {song_json.get('kai_version', 'unknown')}")
                logger.info(f"  - Lines: {len(song_json.get('lines', []))}")
                logger.info(f"  - Audio profile: {song_json.get('audio', {}).get('profile', 'unknown')}")
                logger.info(f"✓ Step 7 completed in {step_time:.1f}s")
                    
                # Step 8: Save features (if any)
                self._emit_progress(8, 9, "Saving features..." if analysis_features else "Skipping features...")
                logger.info("\n" + "=" * 60)
                logger.info("STEP 8/9: SAVING FEATURES (OPTIONAL)")
                logger.info("=" * 60)

                features_files = {}
                if analysis_features:
                    start_step = datetime.utcnow()
                    features_dir = temp_path / "features"
                    features_files = self.musical_analyzer.save_features(
                        analysis_features, features_dir
                    )
                    step_time = (datetime.utcnow() - start_step).total_seconds()

                    logger.info(f"✓ Features saved: {len(features_files)} files")
                    for feature_name in features_files:
                        logger.info(f"  - {feature_name}")
                    logger.info(f"✓ Step 8 completed in {step_time:.1f}s")
                else:
                    logger.info("No features to save - skipping")
                    
                # Add file hashes to processing_info
                output_hashes = {}
                for stem_name, mp3_path in stem_mp3_files.items():
                    output_hashes[f"{stem_name}.mp3"] = {
                        "sha256": self._compute_file_hash(mp3_path),
                        "bitrate_kbps": int(vocals_bitrate.replace('k', '')) if stem_name == "vocals" else int(stem_bitrate.replace('k', ''))
                    }
                
                # Add hashes to processing_info for meta section
                processing_info["outputs"] = output_hashes
                
                # Step 9: Package KAI file
                self._emit_progress(9, 9, "Packaging KAI file...")
                logger.info("\n" + "=" * 60)
                logger.info("STEP 9/9: PACKAGING KAI FILE")
                logger.info("=" * 60)
                logger.info(f"Output: {output_path}")
                logger.info(f"Packaging: song.json + {len(stem_mp3_files)} MP3 stems + optional features")

                start_step = datetime.utcnow()
                package_info = self.packager.package_kai(
                    output_path=output_path,
                    song_json=song_json,
                    stem_files=stem_mp3_files,
                    features_files=features_files if features else None
                    # No more separate manifest.json
                )
                
                # Final validation
                validation_result = self.packager.validate_kai_file(output_path)
                if not validation_result["valid"]:
                    raise ValueError(f"Generated KAI file failed validation: {validation_result['errors']}")
                
                step_time = (datetime.utcnow() - start_step).total_seconds()
                final_size = output_path.stat().st_size
                
                logger.info(f"✓ KAI file created: {final_size:,} bytes")
                logger.info(f"✓ Validation: PASSED")
                logger.info(f"✓ Contents: {len(validation_result.get('contents', []))} files")
                logger.info(f"✓ Step 9 completed in {step_time:.1f}s")
                    
                end_time = datetime.utcnow()
                processing_time = (end_time - start_time).total_seconds()
                
                # Compile final results
                results = {
                    "success": True,
                    "output_file": str(output_path),
                    "processing_time_seconds": processing_time,
                    "input_info": {
                        "file": str(input_audio),
                        "lyrics_source": "AI_transcription",
                        "duration_seconds": audio_info["duration_seconds"],
                        "sample_rate": audio_info["target_sample_rate"]
                    },
                    "output_info": package_info,
                    "processing_stats": {
                        "stems_separated": len(stems),
                        "lines_aligned": len(alignment_data.get("lines", [])),
                        "features_extracted": len(analysis_features),
                        "encoder_delay_samples": canonical_encoder_delay,
                        "alignment_confidence": alignment_data.get("confidence", 0.5)
                    },
                    "validation": validation_result
                }
                
                # Final summary
                logger.info("\n" + "=" * 60)
                logger.info("KAI PROCESSING COMPLETED SUCCESSFULLY!")
                logger.info("=" * 60)
                logger.info(f"Total time: {processing_time:.1f}s")
                logger.info(f"Input: {input_audio.name} ({audio_info['duration_seconds']:.1f}s)")
                logger.info(f"Output: {output_path.name} ({final_size:,} bytes)")
                logger.info(f"Transcription: {len(alignment_data.get('lines', []))} lines")
                logger.info(f"Confidence: {alignment_data.get('confidence', 0.0):.2f}")
                logger.info("=" * 60)

                # Save lyrics temp file info for potential fix_lyrics usage
                if lyrics_temp_file:
                    logger.info(f"Reference lyrics available for fix_lyrics: {lyrics_temp_file}")
                    save_lyrics_temp_info(lyrics_temp_file)

                return results
                
            except Exception as e:
                logger.error(f"KAI processing failed: {str(e)}")
                raise
                
    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA256 hash of file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
        
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about loaded models and components."""
        return {
            "audio_processor": {
                "sample_rate": self.audio_processor.sample_rate,
                "target_lufs": self.audio_processor.target_lufs
            },
            "stem_separator": self.stem_separator.get_model_info(),
            "lyrics_transcriber": self.lyrics_transcriber.get_model_info(),
            "musical_analyzer": {
                "sample_rate": self.musical_analyzer.sample_rate,
                "frame_rate": self.musical_analyzer.frame_rate
            }
        }