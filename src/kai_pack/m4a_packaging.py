"""M4A packaging with karaoke extensions."""

import hashlib
import json
import logging
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import numpy as np

from .webvtt_generator import WebVTTGenerator
from .mp4_atoms import MP4CustomAtoms

logger = logging.getLogger(__name__)


class StemsM4aPackager:
    """Handles packaging of multi-track M4A files with karaoke extensions."""

    def __init__(self):
        self.webvtt_generator = WebVTTGenerator()
        self.mp4_atoms = MP4CustomAtoms()

    def _calculate_aac_bitrate(self, source_bitrate: Optional[int], max_bitrate: int = 256000) -> str:
        """
        Calculate appropriate AAC bitrate based on source quality.

        Args:
            source_bitrate: Original source bitrate in bits/sec (None for lossless)
            max_bitrate: Maximum bitrate ceiling in bits/sec

        Returns:
            Bitrate string for ffmpeg (e.g., "192k")
        """
        # Default to max bitrate for lossless sources or unknown
        if source_bitrate is None:
            target_bitrate = max_bitrate
        else:
            # Use source bitrate but don't exceed max
            # AAC is ~30% more efficient than MP3, so we can use slightly lower
            # but let's be conservative and match the source
            target_bitrate = min(source_bitrate, max_bitrate)

        # Round to common bitrate values
        common_bitrates = [96000, 128000, 160000, 192000, 224000, 256000, 320000]
        target_bitrate = min(common_bitrates, key=lambda x: abs(x - target_bitrate))

        # Convert to ffmpeg format (e.g., "192k")
        return f"{target_bitrate // 1000}k"

    def _find_mp4box(self) -> Optional[str]:
        """
        Find mp4box binary in system PATH or cache directory.

        Returns:
            Path to mp4box binary, or None if not found
        """
        import shutil
        import sys
        from pathlib import Path

        # Check system PATH first (preferred)
        system_mp4box = shutil.which('mp4box') or shutil.which('MP4Box')
        if system_mp4box:
            logger.info(f"Found mp4box in system PATH: {system_mp4box}")
            return system_mp4box

        # Fall back to cache directory (legacy support)
        cache_paths = {
            'darwin': Path.home() / 'Library' / 'Caches' / 'KAI-Converter' / 'bin' / 'mp4box',
            'win32': Path.home() / 'AppData' / 'Local' / 'KAI-Converter' / 'Cache' / 'bin' / 'mp4box.exe',
            'linux': Path.home() / '.cache' / 'kai-converter' / 'bin' / 'mp4box'
        }

        platform = sys.platform
        cache_path = cache_paths.get(platform)

        if cache_path and cache_path.exists():
            logger.info(f"Found mp4box in cache: {cache_path}")
            return str(cache_path)

        logger.warning("mp4box not found in system PATH or cache")
        return None

    def package_stems_m4a(
        self,
        output_path: Path,
        stems_wav_files: Dict[str, Path],  # stem_name -> WAV file path
        mixdown_wav: Path,  # Original audio as WAV
        lyrics_data: Dict[str, Any],  # Aligned lyrics with timing
        metadata: Dict[str, Any],  # Song metadata
        analysis_features: Optional[Dict[str, Any]] = None,  # Musical analysis
        sample_rate: int = 44100,
        profile: str = "STEMS-4",  # or "STEMS-2"
        codec: str = "aac",  # or "alac"
        bitrate: Optional[str] = None,  # If None, auto-detect from source
        use_mp4box: bool = True,  # Required for Traktor compatibility
        cover_art: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Package stems and karaoke data into .stem.m4a file.

        Args:
            output_path: Output .stem.m4a file path
            stems_wav_files: Dictionary of stem name -> WAV file path
            mixdown_wav: Original mixdown audio as WAV
            lyrics_data: Lyrics data from transcription
            metadata: Song metadata (title, artist, etc.)
            analysis_features: Optional analysis features (pitch, onsets, etc.)
            sample_rate: Audio sample rate
            profile: STEMS-4 or STEMS-2
            codec: aac or alac
            bitrate: AAC bitrate (e.g., "256k"). If None, auto-detects from source quality.
                    Ignored for ALAC.
            use_mp4box: Use MP4Box for muxing (required for Traktor)
            cover_art: Optional cover art image path

        Returns:
            Dictionary with packaging results
        """
        logger.info(f"Packaging stems M4A: {output_path}")
        logger.info(f"Profile: {profile}, Codec: {codec}, MP4Box: {use_mp4box}")

        # Auto-detect bitrate from source if not provided
        if bitrate is None and codec == "aac":
            source_bitrate = metadata.get('original_bitrate')
            bitrate = self._calculate_aac_bitrate(source_bitrate)
            if source_bitrate:
                logger.info(f"Auto-detected AAC bitrate: {bitrate} (source: {source_bitrate//1000}k)")
            else:
                logger.info(f"Using default AAC bitrate: {bitrate} (lossless source)")
        elif bitrate is None:
            bitrate = "256k"  # Default fallback

        start_time = datetime.utcnow()

        # Create temporary working directory
        with tempfile.TemporaryDirectory(prefix="m4a_pack_") as temp_dir:
            temp_path = Path(temp_dir)

            # Step 1: Encode stems to AAC/ALAC
            logger.info("Step 1: Encoding stems to AAC/ALAC...")
            encoded_files, encoder_delay = self._encode_stems(
                stems_wav_files, mixdown_wav, temp_path, codec, bitrate, profile
            )

            # Step 2: Generate WebVTT
            logger.info("Step 2: Generating WebVTT lyrics...")
            webvtt_content = self.webvtt_generator.generate_webvtt(
                lyrics_data, encoder_delay, sample_rate
            )
            webvtt_path = temp_path / "lyrics.vtt"
            webvtt_path.write_text(webvtt_content, encoding='utf-8')
            logger.info(f"✓ WebVTT generated: {len(webvtt_content)} bytes")

            # Step 3: Mux with FFmpeg
            logger.info("Step 3: Muxing multi-track M4A with FFmpeg...")
            self._mux_with_ffmpeg(encoded_files, webvtt_path, output_path, metadata)

            # Step 3a: Add NI Stems metadata for Traktor compatibility
            logger.info("Step 3a: Adding NI Stems metadata...")
            stem_names = ['Drums', 'Bass', 'Other', 'Vocals']
            if profile == 'STEMS-2':
                stem_names = ['Music', 'Vocals']
            self.mp4_atoms.add_ni_stems_metadata(output_path, stem_names)

            # Step 3b: Disable all tracks except mixdown (track 0)
            logger.info("Step 3b: Setting track flags for Traktor...")
            # Disable tracks 1, 2, 3, 4 (keep only track 0 enabled for mixdown)
            tracks_to_disable = list(range(1, len(encoded_files)))
            if tracks_to_disable:
                self.mp4_atoms.disable_tracks(output_path, tracks_to_disable)

            # Step 4: Generate kaid atom data
            logger.info("Step 4: Generating karaoke data atoms...")
            kaid_data = self._generate_kaid_atom(
                lyrics_data, analysis_features, encoder_delay, sample_rate, profile
            )

            # Step 5: Write custom atoms to file
            logger.info("Step 5: Writing custom atoms...")
            self._write_custom_atoms(output_path, kaid_data, analysis_features, metadata, cover_art)

            # Step 6: Validate and return results
            logger.info("Step 6: Validating output...")
            file_size = output_path.stat().st_size
            file_hash = self._compute_file_hash(output_path)

            end_time = datetime.utcnow()
            processing_time = (end_time - start_time).total_seconds()

            results = {
                "success": True,
                "output_file": str(output_path),
                "file_size_bytes": file_size,
                "file_sha256": file_hash,
                "processing_time_seconds": processing_time,
                "profile": profile,
                "codec": codec,
                "encoder_delay_samples": encoder_delay,
                "karaoke_features": self.mp4_atoms.get_karaoke_features(output_path)
            }

            logger.info(f"✓ M4A packaging complete: {file_size:,} bytes in {processing_time:.1f}s")
            return results

    def _encode_stems(
        self,
        stems_wav_files: Dict[str, Path],
        mixdown_wav: Path,
        output_dir: Path,
        codec: str,
        bitrate: str,
        profile: str
    ) -> tuple[List[Path], int]:
        """
        Encode stems to AAC or ALAC.

        Returns:
            Tuple of (list of encoded file paths in NI Stems order, encoder delay in samples)
        """
        encoded_files = []
        encoder_delay = 1105 if codec == "aac" else 0  # AAC has ~1105 samples delay

        # NI Stems track order: mixdown, drums, bass, other, vocals
        # Map our stem names to this order
        stems_order = {
            'STEMS-4': ['mixdown', 'drums', 'bass', 'other', 'vocals'],
            'STEMS-2': ['mixdown', 'music', 'vocals']
        }

        ordered_stems = stems_order.get(profile, [])

        for stem_name in ordered_stems:
            if stem_name == 'mixdown':
                input_wav = mixdown_wav
            elif stem_name in stems_wav_files:
                input_wav = stems_wav_files[stem_name]
            else:
                raise ValueError(f"Missing stem: {stem_name}")

            output_file = output_dir / f"{stem_name}.m4a"

            if codec == "aac":
                # AAC encoding with VBR
                cmd = [
                    'ffmpeg', '-i', str(input_wav),
                    '-c:a', 'aac',
                    '-b:a', bitrate,
                    '-vbr', '4',
                    '-movflags', 'faststart',
                    '-y',
                    str(output_file)
                ]
            elif codec == "alac":
                # ALAC lossless encoding
                cmd = [
                    'ffmpeg', '-i', str(input_wav),
                    '-c:a', 'alac',
                    '-movflags', 'faststart',
                    '-y',
                    str(output_file)
                ]
            else:
                raise ValueError(f"Unsupported codec: {codec}")

            logger.info(f"→ Encoding {stem_name}.m4a ({codec})...")
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                raise RuntimeError(f"FFmpeg encoding failed: {result.stderr}")

            encoded_files.append(output_file)
            file_size = output_file.stat().st_size
            logger.info(f"  ✓ {stem_name}.m4a: {file_size:,} bytes")

        return encoded_files, encoder_delay

    def _mux_with_mp4box(
        self,
        audio_files: List[Path],
        webvtt_path: Path,
        output_path: Path,
        metadata: Dict[str, Any],
        mp4box_path: str
    ) -> None:
        """Mux audio tracks and WebVTT with MP4Box (Traktor compatible)."""
        import base64

        cmd = [mp4box_path]

        # Add audio tracks with NI Stems format
        # First track (mixdown) is enabled, others are disabled
        for i, audio_file in enumerate(audio_files):
            if i == 0:
                # Mixdown track: enabled, ID=Z
                cmd.extend(['-add', f"{audio_file}#ID=Z"])
            else:
                # Stem tracks: disabled, ID=Z
                cmd.extend(['-add', f"{audio_file}#ID=Z:disable"])

        # Add WebVTT subtitle track
        cmd.extend(['-add', f"{webvtt_path}:name=Lyrics:lang=en"])

        # NI Stems brand flags
        cmd.extend(['-brand', 'M4A:0', '-rb', 'isom', '-rb', 'iso2'])

        # Add NI Stems metadata in UDTA atom
        stems_metadata = {
            "stems": [
                {"name": "Drums", "color": "#FF0000"},
                {"name": "Bass", "color": "#00FF00"},
                {"name": "Other", "color": "#0000FF"},
                {"name": "Vocals", "color": "#FFFF00"}
            ],
            "version": "1.0.0"
        }
        metadata_json = json.dumps(stems_metadata)
        metadata_b64 = base64.b64encode(metadata_json.encode()).decode()
        cmd.extend(['-udta', f"0:type=stem:src=base64,{metadata_b64}"])

        # Output file
        cmd.append(str(output_path))

        # Set up environment with library path for downloaded mp4box
        import os
        import sys
        env = os.environ.copy()

        # Add lib directory to LD_LIBRARY_PATH (for libgpac.so on Linux)
        if sys.platform == 'linux':
            lib_paths = {
                'linux': Path.home() / '.cache' / 'kai-converter' / 'lib'
            }
            lib_dir = lib_paths.get('linux')
            if lib_dir and lib_dir.exists():
                existing_ld_path = env.get('LD_LIBRARY_PATH', '')
                if existing_ld_path:
                    env['LD_LIBRARY_PATH'] = f"{lib_dir}:{existing_ld_path}"
                else:
                    env['LD_LIBRARY_PATH'] = str(lib_dir)
                logger.debug(f"Set LD_LIBRARY_PATH={env['LD_LIBRARY_PATH']}")

        logger.info(f"Running MP4Box: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)

        if result.returncode != 0:
            raise RuntimeError(f"MP4Box muxing failed: {result.stderr}")

        logger.info("✓ MP4Box muxing complete")

    def _mux_with_ffmpeg(
        self,
        audio_files: List[Path],
        webvtt_path: Path,
        output_path: Path,
        metadata: Dict[str, Any]
    ) -> None:
        """Mux audio tracks and WebVTT with FFmpeg (Mixxx compatible)."""
        cmd = ['ffmpeg']

        # Add audio inputs
        for audio_file in audio_files:
            cmd.extend(['-i', str(audio_file)])

        # Add WebVTT input
        cmd.extend(['-i', str(webvtt_path)])

        # Map all audio tracks
        for i in range(len(audio_files)):
            cmd.extend(['-map', f'{i}:a'])

        # Map subtitle track
        cmd.extend(['-map', f'{len(audio_files)}:s'])

        # Copy audio codecs, convert subtitle to mov_text
        cmd.extend(['-c:a', 'copy', '-c:s', 'mov_text'])

        # Set track 0 as default, disable others for Mixxx/Traktor compatibility
        for i in range(len(audio_files)):
            if i == 0:
                cmd.extend([f'-disposition:a:{i}', 'default'])
            else:
                cmd.extend([f'-disposition:a:{i}', '0'])

        # Add metadata
        if 'title' in metadata.get('song', {}):
            cmd.extend(['-metadata', f"title={metadata['song']['title']}"])
        if 'artist' in metadata.get('song', {}):
            cmd.extend(['-metadata', f"artist={metadata['song']['artist']}"])
        if 'album' in metadata.get('song', {}):
            cmd.extend(['-metadata', f"album={metadata['song']['album']}"])

        # Move moov atom to beginning for faster parsing
        cmd.extend(['-movflags', 'faststart'])

        # Output file
        cmd.extend(['-y', str(output_path)])

        logger.info(f"Running FFmpeg: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg muxing failed: {result.stderr}")

        logger.info("✓ FFmpeg muxing complete")

    def _generate_kaid_atom(
        self,
        lyrics_data: Dict[str, Any],
        analysis_features: Optional[Dict[str, Any]],
        encoder_delay: int,
        sample_rate: int,
        profile: str
    ) -> Dict[str, Any]:
        """Generate kaid (Karaoke Data) atom content."""
        # Build sources list based on profile
        if profile == "STEMS-4":
            sources = [
                {"track": 0, "id": "mixdown", "role": "mixdown"},
                {"track": 1, "id": "drums", "role": "drums"},
                {"track": 2, "id": "bass", "role": "bass"},
                {"track": 3, "id": "other", "role": "other"},
                {"track": 4, "id": "vocals", "role": "vocals"}
            ]
        elif profile == "STEMS-2":
            sources = [
                {"track": 0, "id": "mixdown", "role": "mixdown"},
                {"track": 1, "id": "music", "role": "music"},
                {"track": 2, "id": "vocals", "role": "vocals"}
            ]
        else:
            sources = []

        # Build kaid data
        kaid_data = {
            "stems_karaoke_version": "1.0",
            "audio": {
                "profile": profile,
                "encoder_delay_samples": encoder_delay,
                "sources": sources,
                "presets": [
                    {"id": "karaoke", "levels": {"vocals": -120}}  # Mute vocals
                ]
            },
            "timing": {
                "reference": "aligned_to_vocals",
                "offset_sec": 0.000
            },
            "lines": lyrics_data.get('lines', []),
            "singers": lyrics_data.get('singers', [{"id": "A", "name": "Lead", "guide_track": 4 if profile == "STEMS-4" else 2}])
        }

        # Tempo/BPM removed - DJ software analyzes this itself

        return kaid_data

    def _write_custom_atoms(
        self,
        output_path: Path,
        kaid_data: Dict[str, Any],
        analysis_features: Optional[Dict[str, Any]],
        metadata: Dict[str, Any],
        cover_art: Optional[Path]
    ) -> None:
        """Write all custom atoms and metadata to MP4 file."""
        try:
            from mutagen.mp4 import MP4, MP4Cover, MP4FreeForm
        except ImportError:
            raise ImportError("mutagen library required for MP4 metadata writing")

        # Write kaid atom
        self.mp4_atoms.write_kaid_atom(output_path, kaid_data)

        # Write vocal pitch if available
        if analysis_features and 'vocal_pitch' in analysis_features:
            logger.debug(f"vocal_pitch type: {type(analysis_features['vocal_pitch'])}")
            vocal_pitch = analysis_features['vocal_pitch']

            # Handle both dict and array formats
            if isinstance(vocal_pitch, dict):
                pitch_data = vocal_pitch.get('midi_cents', np.array([]))
            elif isinstance(vocal_pitch, np.ndarray):
                pitch_data = vocal_pitch
            else:
                logger.warning(f"Unexpected vocal_pitch type: {type(vocal_pitch)}, skipping vpch atom")
                pitch_data = np.array([])

            if isinstance(pitch_data, np.ndarray) and len(pitch_data) > 0:
                self.mp4_atoms.write_vpch_atom(output_path, pitch_data)
            else:
                logger.debug(f"Skipping vpch atom - pitch_data type: {type(pitch_data)}, len: {len(pitch_data) if hasattr(pitch_data, '__len__') else 'N/A'}")

        # Write onsets if available
        if analysis_features and 'onsets' in analysis_features:
            logger.debug(f"onsets type: {type(analysis_features['onsets'])}")
            onsets = analysis_features['onsets']

            # Handle both dict and array formats
            if isinstance(onsets, dict):
                onsets_data = onsets.get('times', np.array([]))
            elif isinstance(onsets, np.ndarray):
                onsets_data = onsets
            else:
                logger.warning(f"Unexpected onsets type: {type(onsets)}, skipping kons atom")
                onsets_data = np.array([])

            if isinstance(onsets_data, np.ndarray) and len(onsets_data) > 0:
                self.mp4_atoms.write_kons_atom(output_path, onsets_data)
            else:
                logger.debug(f"Skipping kons atom - onsets_data type: {type(onsets_data)}, len: {len(onsets_data) if hasattr(onsets_data, '__len__') else 'N/A'}")

        # Write iTunes metadata and cover art
        try:
            mp4 = MP4(output_path)

            song_metadata = metadata.get('song', {})

            # Title
            if 'title' in song_metadata:
                title = song_metadata['title']
                if isinstance(title, str):
                    mp4['\xa9nam'] = [title]

            # Artist
            if 'artist' in song_metadata:
                artist = song_metadata['artist']
                if isinstance(artist, str):
                    mp4['\xa9ART'] = [artist]

            # Album
            if 'album' in song_metadata:
                album = song_metadata['album']
                if isinstance(album, str):
                    mp4['\xa9alb'] = [album]

            # Year
            if 'year' in song_metadata:
                year = song_metadata['year']
                if isinstance(year, (int, str)):
                    mp4['\xa9day'] = [str(year)]

            # Genre
            if 'genre' in song_metadata:
                genre = song_metadata['genre']
                if isinstance(genre, str):
                    mp4['\xa9gen'] = [genre]

            # Musical key (from analysis features if available)
            if analysis_features and 'key_detection' in analysis_features:
                key_info = analysis_features['key_detection']
                detected_key = key_info.get('key', '').strip()
                confidence = key_info.get('confidence', 0.0)

                # Only write key if confidence is reasonable (>0.3)
                if detected_key and detected_key != 'unknown' and confidence > 0.3:
                    # Write to freeform ----:com.apple.iTunes:initialkey (standard for DJ software)
                    mp4['----:com.apple.iTunes:initialkey'] = [MP4FreeForm(detected_key.encode('utf-8'), dataformat=1)]
                    logger.info(f"✓ Musical key added: {detected_key} (confidence: {confidence:.2f})")

            # Track number
            if 'track' in song_metadata:
                track = song_metadata['track']
                if isinstance(track, int):
                    mp4['trkn'] = [(track, 0)]
                elif isinstance(track, str) and track.isdigit():
                    mp4['trkn'] = [(int(track), 0)]
                elif isinstance(track, dict) and 'no' in track:
                    # Handle dict format like {'no': 3, 'of': 0}
                    track_no = track.get('no', 0)
                    track_of = track.get('of', 0)
                    if isinstance(track_no, int):
                        mp4['trkn'] = [(track_no, track_of)]
                else:
                    logger.warning(f"Invalid track number type: {type(track)}, value: {track}")

            # Add cover art if provided
            if cover_art and cover_art.exists():
                with open(cover_art, 'rb') as f:
                    image_data = f.read()

                # Determine image format
                if cover_art.suffix.lower() in ['.jpg', '.jpeg']:
                    image_format = MP4Cover.FORMAT_JPEG
                elif cover_art.suffix.lower() == '.png':
                    image_format = MP4Cover.FORMAT_PNG
                else:
                    image_format = MP4Cover.FORMAT_JPEG  # Default

                mp4['covr'] = [MP4Cover(image_data, imageformat=image_format)]
                logger.info(f"✓ Cover art added ({len(image_data)} bytes)")

            mp4.save()
            logger.info("✓ iTunes metadata written")
        except Exception as e:
            import traceback
            logger.error(f"Error writing iTunes metadata: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            logger.error(f"Metadata content: {metadata}")
            raise

    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA256 hash of file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
