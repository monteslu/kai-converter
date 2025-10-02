"""Audio preprocessing and normalization utilities."""

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Tuple, Dict, Any, Optional

import numpy as np
import pyloudnorm as pyln
import soundfile as sf
from scipy.io import wavfile
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TPE2, TRCK, TPOS, TDRC, TCON, TSRC


logger = logging.getLogger(__name__)


class AudioProcessor:
    """Handles audio loading, preprocessing, and normalization."""
    
    def __init__(self, sample_rate: int = 44100, target_lufs: float = -14.0):
        self.sample_rate = sample_rate
        self.target_lufs = target_lufs
        
    def load_and_preprocess(self, input_path: Path) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Load audio file and preprocess to standard format.

        Args:
            input_path: Path to input audio file

        Returns:
            Tuple of (audio_data, metadata)
            audio_data: stereo float32 audio at target sample rate
            metadata: dict with original file info and processing stats
        """
        logger.info(f"Loading audio from {input_path}")

        # Use ffmpeg to load audio and convert to target format
        try:
            # Create temporary WAV file for intermediate processing
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                tmp_wav = Path(tmp_file.name)

            # First, get original sample rate using ffprobe
            cmd_probe = [
                "ffprobe", "-v", "quiet", "-show_entries",
                "stream=sample_rate,channels", "-of", "csv=p=0", str(input_path)
            ]
            result = subprocess.run(cmd_probe, capture_output=True, text=True, check=True)
            probe_output = result.stdout.strip().split(',')
            orig_sr = int(probe_output[0])
            orig_channels = int(probe_output[1])

            # Convert to WAV at target sample rate with stereo output
            cmd = [
                "ffmpeg", "-y",
                "-i", str(input_path),
                "-ar", str(self.sample_rate),
                "-ac", "2",  # Force stereo
                "-f", "wav",
                str(tmp_wav)
            ]

            subprocess.run(cmd, capture_output=True, text=True, check=True)

            # Load the converted WAV file
            audio, load_sr = sf.read(tmp_wav)

            # Clean up temp file
            tmp_wav.unlink()

            # Convert to (channels, samples) format
            audio = audio.T

        except Exception as e:
            raise RuntimeError(f"Failed to load audio file {input_path}: {e}")

        logger.info(f"Loaded audio: {audio.shape} at {orig_sr} Hz -> {self.sample_rate} Hz")

        # Normalize loudness
        audio_normalized, loudness_stats = self._normalize_loudness(audio)

        metadata = {
            "original_sample_rate": orig_sr,
            "target_sample_rate": self.sample_rate,
            "original_channels": orig_channels,
            "duration_seconds": audio_normalized.shape[1] / self.sample_rate,
            "loudness_stats": loudness_stats
        }

        return audio_normalized, metadata
        
    def _normalize_loudness(self, audio: np.ndarray) -> Tuple[np.ndarray, Dict[str, float]]:
        """
        Normalize audio to target LUFS using pyloudnorm.
        
        Args:
            audio: stereo audio array (2, samples)
            
        Returns:
            Tuple of (normalized_audio, loudness_stats)
        """
        logger.info(f"Normalizing loudness to {self.target_lufs} LUFS")
        
        # pyloudnorm expects (samples, channels)
        audio_t = audio.T
        
        # Measure current loudness
        meter = pyln.Meter(self.sample_rate)
        current_lufs = meter.integrated_loudness(audio_t)
        
        # Normalize to target LUFS
        if np.isfinite(current_lufs):
            normalized = pyln.normalize.loudness(audio_t, current_lufs, self.target_lufs)
            logger.info(f"Normalized from {current_lufs:.1f} LUFS to {self.target_lufs} LUFS")
        else:
            logger.warning("Could not measure loudness, skipping normalization")
            normalized = audio_t
            current_lufs = float('nan')
            
        # Back to (channels, samples)
        normalized = normalized.T
        
        # Ensure no clipping
        max_val = np.max(np.abs(normalized))
        if max_val > 0.99:
            headroom_db = 20 * np.log10(0.99 / max_val)
            logger.warning(f"Applying {headroom_db:.1f} dB headroom to prevent clipping")
            normalized = normalized * (0.99 / max_val)
            
        loudness_stats = {
            "original_lufs": current_lufs,
            "target_lufs": self.target_lufs,
            "peak_before": np.max(np.abs(audio)),
            "peak_after": np.max(np.abs(normalized))
        }
        
        return normalized, loudness_stats
        
    def save_wav(self, audio: np.ndarray, output_path: Path) -> None:
        """Save audio as WAV file."""
        # Convert to (samples, channels) for soundfile
        audio_t = audio.T
        sf.write(output_path, audio_t, self.sample_rate, subtype='FLOAT')
        logger.debug(f"Saved WAV: {output_path}")
        
    def encode_mp3_with_ffmpeg(
        self, 
        input_wav: Path, 
        output_mp3: Path, 
        bitrate: str = "128k",
        metadata: Optional[Dict[str, Any]] = None,
        stem_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Encode WAV to MP3 using ffmpeg and extract encoder delay.
        
        Args:
            input_wav: Input WAV file
            output_mp3: Output MP3 file
            bitrate: MP3 bitrate (e.g., "128k", "192k")
            metadata: Optional metadata dict to write as ID3 tags
            stem_name: Optional stem name for title modification
            
        Returns:
            Dict with encoding info including encoder_delay_samples
        """
        logger.info(f"Encoding MP3: {input_wav} -> {output_mp3} @ {bitrate}")
        
        # Use ffmpeg for encoding
        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_wav),
            "-codec:a", "libmp3lame",
            "-b:a", bitrate,
            "-ar", str(self.sample_rate),
            "-ac", "2",
            str(output_mp3)
        ]
        
        try:
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                check=True
            )
            logger.debug("ffmpeg encoding successful")
            
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"ffmpeg encoding failed: {e.stderr}")
            
        # Extract encoder delay from MP3 file
        encoder_delay = self._get_mp3_encoder_delay(output_mp3)
        
        # Write ID3 tags if metadata provided
        if metadata:
            self._write_id3_tags(output_mp3, metadata, stem_name)
        
        return {
            "bitrate": bitrate,
            "encoder_delay_samples": encoder_delay,
            "sample_rate": self.sample_rate
        }
        
    def _get_mp3_encoder_delay(self, mp3_path: Path) -> int:
        """
        Extract encoder delay from MP3 file using ffprobe.
        
        Returns:
            Encoder delay in samples (defaults to 1105 for LAME if unknown)
        """
        try:
            cmd = [
                "ffprobe", "-v", "quiet", "-show_entries", 
                "format=start_time", "-of", "csv=p=0", str(mp3_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # Convert start_time to samples
            start_time = float(result.stdout.strip())
            delay_samples = int(start_time * self.sample_rate)
            
            if delay_samples > 0:
                logger.debug(f"Detected encoder delay: {delay_samples} samples")
                return delay_samples
            else:
                # Fall back to LAME default
                logger.debug("Using default LAME encoder delay: 1105 samples")
                return 1105
                
        except Exception as e:
            logger.warning(f"Could not detect encoder delay: {e}, using default 1105")
            return 1105

    def _write_id3_tags(self, mp3_path: Path, metadata: Dict[str, Any], stem_name: Optional[str] = None) -> None:
        """
        Write ID3 tags to MP3 file using metadata.
        
        Args:
            mp3_path: Path to MP3 file
            metadata: Metadata dict with song information
            stem_name: Optional stem name to append to title
        """
        try:
            # Load or create ID3 tags
            try:
                tags = ID3(mp3_path)
            except:
                # No ID3 tags exist, create new
                tags = ID3()
            
            # Get normalized metadata
            song_meta = metadata.get("song", {}) if isinstance(metadata, dict) else metadata
            
            # Basic text frames
            title = song_meta.get("title", "Unknown")
            if stem_name:
                title = f"{title} ({stem_name.capitalize()})"
            tags.add(TIT2(encoding=3, text=title))
            
            if "artist" in song_meta:
                tags.add(TPE1(encoding=3, text=song_meta["artist"]))
                
            if "album" in song_meta:
                tags.add(TALB(encoding=3, text=song_meta["album"]))
                
            if "album_artist" in song_meta:
                tags.add(TPE2(encoding=3, text=song_meta["album_artist"]))
                
            # Track and disc info
            track_info = song_meta.get("track", {})
            if isinstance(track_info, dict):
                track_no = track_info.get("no")
                track_of = track_info.get("of", 0)
                if track_no:
                    track_text = f"{track_no}/{track_of}" if track_of else str(track_no)
                    tags.add(TRCK(encoding=3, text=track_text))
            
            disc_info = song_meta.get("disc", {})
            if isinstance(disc_info, dict):
                disc_no = disc_info.get("no")
                disc_of = disc_info.get("of", 1)
                if disc_no:
                    disc_text = f"{disc_no}/{disc_of}" if disc_of else str(disc_no)
                    tags.add(TPOS(encoding=3, text=disc_text))
            
            # Date/year
            if "year" in song_meta:
                tags.add(TDRC(encoding=3, text=song_meta["year"]))
                
            if "genre" in song_meta:
                tags.add(TCON(encoding=3, text=song_meta["genre"]))
                
            if "isrc" in song_meta:
                tags.add(TSRC(encoding=3, text=song_meta["isrc"]))
            
            # Save tags to file
            tags.save(mp3_path)
            logger.debug(f"Written ID3 tags to {mp3_path} (stem: {stem_name})")
            
        except Exception as e:
            logger.warning(f"Failed to write ID3 tags to {mp3_path}: {e}")