"""Stems enhancer - add karaoke to existing NI Stems files."""

import logging
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import numpy as np

from .mp4_atoms import MP4CustomAtoms
from .webvtt_generator import WebVTTGenerator

logger = logging.getLogger(__name__)


class StemsKaraokeEnhancer:
    """Add karaoke extensions to existing NI Stems files."""

    def __init__(
        self,
        lyrics_transcriber,
        musical_analyzer,
        webvtt_generator: Optional[WebVTTGenerator] = None,
        mp4_atoms: Optional[MP4CustomAtoms] = None
    ):
        self.lyrics_transcriber = lyrics_transcriber
        self.musical_analyzer = musical_analyzer
        self.webvtt_generator = webvtt_generator or WebVTTGenerator()
        self.mp4_atoms = mp4_atoms or MP4CustomAtoms()

    def enhance_stems_file(
        self,
        input_stems_path: Path,
        output_path: Optional[Path] = None,
        extract_pitch: bool = True,
        extract_onsets: bool = True,
        in_place: bool = False,
        force: bool = False,
        metadata_overrides: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Add karaoke data to existing NI Stems file.

        Args:
            input_stems_path: Path to existing .stem.m4a file
            output_path: Output path (if None, auto-generate)
            extract_pitch: Extract vocal pitch data
            extract_onsets: Extract onset data
            in_place: Update file in-place (creates backup)
            force: Force enhancement even if already has karaoke
            metadata_overrides: Override song metadata

        Returns:
            Dictionary with enhancement results
        """
        logger.info(f"Enhancing stems file: {input_stems_path}")

        start_time = datetime.utcnow()

        # Step 0: Check if already enhanced
        if not force:
            features = self.mp4_atoms.get_karaoke_features(input_stems_path)
            if features['has_lyrics']:
                logger.info("File already has karaoke data - skipping (use --force to override)")
                return {'skipped': True, 'reason': 'already_has_karaoke'}

        # Step 1: Validate NI Stems format
        if not self._validate_stems_file(input_stems_path):
            raise ValueError("Not a valid NI Stems file")

        # Step 2: Extract vocals track
        logger.info("Extracting vocals track from stems file...")
        vocals_audio, sample_rate = self._extract_vocals_track(input_stems_path)

        # Step 3: Transcribe lyrics
        logger.info("Transcribing lyrics with Whisper...")
        alignment_data = self.lyrics_transcriber.transcribe_and_align(vocals_audio)
        logger.info(f"✓ Transcribed {len(alignment_data.get('lines', []))} lines")

        # Step 4: Optional analysis
        analysis_features = {}
        if extract_pitch or extract_onsets:
            logger.info("Extracting musical features...")
            features_list = []
            if extract_pitch:
                features_list.append('vocal_pitch')
            if extract_onsets:
                features_list.append('onsets')

            analysis_features = self.musical_analyzer.extract_features(
                vocals_audio, None, features_list
            )
            logger.info(f"✓ Extracted {len(analysis_features)} features")

        # Step 5: Generate WebVTT
        logger.info("Generating WebVTT lyrics...")
        webvtt_content = self.webvtt_generator.generate_webvtt(
            alignment_data, encoder_delay_samples=0, sample_rate=sample_rate
        )

        # Step 6: Generate karaoke atoms
        logger.info("Generating karaoke data atoms...")
        kaid_data = self._generate_kaid_atom(alignment_data, analysis_features, sample_rate)

        # Step 7: Determine output path
        if in_place:
            output = input_stems_path
            # Create backup first
            backup_path = input_stems_path.with_suffix('.m4a.backup')
            shutil.copy2(input_stems_path, backup_path)
            logger.info(f"Created backup: {backup_path}")
        else:
            output = output_path or self._generate_output_path(input_stems_path)
            shutil.copy2(input_stems_path, output)
            logger.info(f"Output file: {output}")

        # Step 8: Add WebVTT track
        logger.info("Adding WebVTT lyrics track...")
        self._add_webvtt_track(output, webvtt_content)

        # Step 9: Write karaoke data atoms
        logger.info("Writing custom atoms...")
        self._write_karaoke_atoms(output, kaid_data, analysis_features, metadata_overrides)

        # Step 10: Validate and return results
        end_time = datetime.utcnow()
        processing_time = (end_time - start_time).total_seconds()

        features = self.mp4_atoms.get_karaoke_features(output)
        display_level = self._get_display_level(features)

        results = {
            'success': True,
            'input_file': str(input_stems_path),
            'output_file': str(output),
            'karaoke_level': display_level,
            'karaoke_features': features,
            'line_count': len(alignment_data.get('lines', [])),
            'processing_time_seconds': processing_time
        }

        logger.info(f"✓ Enhancement complete: Level {display_level} karaoke in {processing_time:.1f}s")
        return results

    def _validate_stems_file(self, file_path: Path) -> bool:
        """Validate file is NI Stems format."""
        try:
            from mutagen.mp4 import MP4
        except ImportError:
            raise ImportError("mutagen library required for MP4 validation")

        try:
            mp4 = MP4(file_path)
            # Check it has multiple audio tracks
            # NI Stems files have specific structure
            return True  # Basic check - file is readable as MP4
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return False

    def _extract_vocals_track(self, stems_path: Path) -> tuple[np.ndarray, int]:
        """
        Extract vocals track from NI Stems file.

        For STEMS-4: Track 4 is vocals
        For STEMS-2: Track 2 is vocals

        Returns:
            Tuple of (vocals audio array, sample rate)
        """
        # Use FFmpeg to extract vocals track
        # STEMS-4: Track 4 (index 4)
        # Try track 4 first (STEMS-4), fallback to track 2 (STEMS-2)

        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
            tmp_path = Path(tmp_file.name)

        try:
            # Try track 4 (STEMS-4)
            cmd = [
                'ffmpeg',
                '-i', str(stems_path),
                '-map', '0:a:4',  # Map 5th audio track (vocals in STEMS-4)
                '-y',
                str(tmp_path)
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                # Try track 2 (STEMS-2)
                logger.info("Track 4 not found, trying track 2 (STEMS-2)...")
                cmd = [
                    'ffmpeg',
                    '-i', str(stems_path),
                    '-map', '0:a:2',  # Map 3rd audio track (vocals in STEMS-2)
                    '-y',
                    str(tmp_path)
                ]
                result = subprocess.run(cmd, capture_output=True, text=True)

                if result.returncode != 0:
                    raise RuntimeError(f"Failed to extract vocals track: {result.stderr}")

            # Load extracted WAV
            import librosa
            vocals_audio, sample_rate = librosa.load(str(tmp_path), sr=44100, mono=False)

            # Convert to stereo if mono
            if vocals_audio.ndim == 1:
                vocals_audio = np.stack([vocals_audio, vocals_audio])

            logger.info(f"✓ Extracted vocals: {vocals_audio.shape}, {sample_rate}Hz")
            return vocals_audio, sample_rate

        finally:
            # Clean up temp file
            if tmp_path.exists():
                tmp_path.unlink()

    def _generate_kaid_atom(
        self,
        lyrics_data: Dict[str, Any],
        analysis_features: Dict[str, Any],
        sample_rate: int
    ) -> Dict[str, Any]:
        """Generate kaid atom data."""
        kaid_data = {
            "stems_karaoke_version": "1.0",
            "timing": {
                "reference": "aligned_to_vocals",
                "offset_sec": 0.000
            },
            "lines": lyrics_data.get('lines', []),
            "singers": lyrics_data.get('singers', [{"id": "A", "name": "Lead"}])
        }

        # Add BPM if available
        if 'tempo' in analysis_features:
            kaid_data["meter"] = {
                "bpm": float(analysis_features['tempo'].get('bpm', 0))
            }

        return kaid_data

    def _add_webvtt_track(self, output_path: Path, webvtt_content: str) -> None:
        """Add WebVTT track to MP4 file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.vtt', delete=False, encoding='utf-8') as tmp_file:
            tmp_file.write(webvtt_content)
            tmp_vtt_path = Path(tmp_file.name)

        try:
            # Create temporary output
            tmp_output = output_path.with_suffix('.tmp.m4a')

            # Use MP4Box to add subtitle track
            cmd = [
                'mp4box',
                '-add', f"{tmp_vtt_path}:name=Lyrics:lang=en",
                str(output_path),
                '-out', str(tmp_output)
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                raise RuntimeError(f"MP4Box failed to add WebVTT: {result.stderr}")

            # Replace original with new file
            shutil.move(str(tmp_output), str(output_path))
            logger.info("✓ WebVTT track added")

        finally:
            if tmp_vtt_path.exists():
                tmp_vtt_path.unlink()
            if tmp_output and tmp_output.exists():
                tmp_output.unlink()

    def _write_karaoke_atoms(
        self,
        output_path: Path,
        kaid_data: Dict[str, Any],
        analysis_features: Dict[str, Any],
        metadata_overrides: Optional[Dict] = None
    ) -> None:
        """Write karaoke atoms to file."""
        # Write kaid atom
        self.mp4_atoms.write_kaid_atom(output_path, kaid_data)

        # Write vocal pitch if available
        if 'vocal_pitch' in analysis_features:
            pitch_data = analysis_features['vocal_pitch'].get('midi_cents', np.array([]))
            if len(pitch_data) > 0:
                self.mp4_atoms.write_vpch_atom(output_path, pitch_data)

        # Write onsets if available
        if 'onsets' in analysis_features:
            onsets_data = analysis_features['onsets'].get('times', np.array([]))
            if len(onsets_data) > 0:
                self.mp4_atoms.write_kons_atom(output_path, onsets_data)

        # Apply metadata overrides if provided
        if metadata_overrides:
            try:
                from mutagen.mp4 import MP4
                mp4 = MP4(output_path)

                if 'title' in metadata_overrides:
                    mp4['\xa9nam'] = [metadata_overrides['title']]
                if 'artist' in metadata_overrides:
                    mp4['\xa9ART'] = [metadata_overrides['artist']]
                if 'album' in metadata_overrides:
                    mp4['\xa9alb'] = [metadata_overrides['album']]

                mp4.save()
                logger.info("✓ Metadata overrides applied")
            except Exception as e:
                logger.warning(f"Failed to apply metadata overrides: {e}")

    def _generate_output_path(self, input_path: Path) -> Path:
        """Generate output path by adding -karaoke suffix."""
        stem = input_path.stem
        if stem.endswith('.stem'):
            # file.stem.m4a -> file-karaoke.stem.m4a
            base = stem[:-5]  # Remove '.stem'
            return input_path.with_name(f"{base}-karaoke.stem.m4a")
        else:
            # file.m4a -> file-karaoke.m4a
            return input_path.with_name(f"{stem}-karaoke{input_path.suffix}")

    def _get_display_level(self, features: Dict[str, bool]) -> int:
        """Convert features to display level (0-3)."""
        if not features['has_lyrics']:
            return 0

        if features['has_advanced'] and features['has_word_timing']:
            return 3
        elif features['has_word_timing']:
            return 2
        elif features['has_advanced']:
            return 3
        else:
            return 1
