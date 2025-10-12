"""Lyrics-to-audio alignment using CTC and DTW.

NOTE: This module is currently unused and not imported anywhere in the codebase.
It was part of an earlier approach to lyrics alignment that was replaced by
Whisper's built-in word-level timestamps. This file uses librosa which is not
included in the core dependencies.

If you want to use this module, you'll need to:
1. Install librosa: pip install librosa>=0.10.0
2. Import and use the LyricsAligner class in your processing pipeline
"""

import logging
import re
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

import numpy as np
from scipy.spatial.distance import cdist
from dtw import dtw
from phonemizer import phonemize
from phonemizer.backend import EspeakBackend


logger = logging.getLogger(__name__)


class LyricsAligner:
    """Handles lyrics-to-audio alignment using phonemization and DTW."""
    
    def __init__(self, sample_rate: int = 44100, hop_length: int = 512):
        self.sample_rate = sample_rate
        self.hop_length = hop_length
        self.frame_rate = sample_rate / hop_length
        
        # Initialize phonemizer backend
        try:
            self.phonemizer = EspeakBackend(
                language='en-us',
                preserve_punctuation=True,
                with_stress=True
            )
            logger.info("Initialized espeak phonemizer")
        except Exception as e:
            logger.warning(f"Could not initialize phonemizer: {e}")
            self.phonemizer = None
            
    def align_lyrics(
        self, 
        lyrics_file: Path, 
        vocals_audio: np.ndarray
    ) -> Dict[str, Any]:
        """
        Align lyrics text to vocal audio.
        
        Args:
            lyrics_file: Path to lyrics text file (.txt or .lrc)
            vocals_audio: Vocal stem audio (2, samples)
            
        Returns:
            Dict with alignment results including words, lines, and timing
        """
        logger.info(f"Aligning lyrics from {lyrics_file}")
        
        # Load and parse lyrics
        lyrics_data = self._load_lyrics(lyrics_file)
        
        # Extract audio features for alignment
        audio_features = self._extract_audio_features(vocals_audio)
        
        # Perform alignment
        if lyrics_data["format"] == "lrc":
            # LRC already has timing, just validate and refine
            alignment = self._refine_lrc_timing(lyrics_data, audio_features)
        else:
            # Plain text, need full alignment
            alignment = self._align_text_to_audio(lyrics_data, audio_features)
            
        # Post-process alignment
        alignment = self._post_process_alignment(alignment)
        
        logger.info(f"Aligned {len(alignment['lines'])} lines, "
                   f"{len(alignment['words'])} words")
        
        return alignment
        
    def _load_lyrics(self, lyrics_file: Path) -> Dict[str, Any]:
        """Load lyrics from text or LRC file."""
        with open(lyrics_file, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            
        if lyrics_file.suffix.lower() == '.lrc':
            return self._parse_lrc(content)
        else:
            return self._parse_text(content)
            
    def _parse_lrc(self, content: str) -> Dict[str, Any]:
        """Parse LRC format lyrics."""
        lines = []
        metadata = {}
        
        # LRC time pattern: [mm:ss.xx]
        time_pattern = r'\[(\d{2}):(\d{2})\.(\d{2})\](.+?)(?=\[|$)'
        
        for match in re.finditer(time_pattern, content):
            minutes, seconds, centiseconds, text = match.groups()
            timestamp = int(minutes) * 60 + int(seconds) + int(centiseconds) / 100
            
            if text.strip():
                lines.append({
                    "text": text.strip(),
                    "start": timestamp,
                    "end": timestamp + 3.0  # Estimate, will be refined
                })
                
        # Sort by timestamp
        lines.sort(key=lambda x: x["start"])
        
        # Estimate end times based on next line starts
        for i in range(len(lines) - 1):
            lines[i]["end"] = lines[i + 1]["start"]
            
        return {
            "format": "lrc",
            "lines": lines,
            "metadata": metadata
        }
        
    def _parse_text(self, content: str) -> Dict[str, Any]:
        """Parse plain text lyrics."""
        # Split into lines and clean
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        
        # Remove common metadata patterns
        lyrics_lines = []
        for line in lines:
            # Skip lines that look like metadata
            if (line.startswith('[') or 
                line.lower().startswith(('artist:', 'title:', 'album:')) or
                line.startswith('#')):
                continue
            lyrics_lines.append(line)
            
        return {
            "format": "text",
            "lines": [{"text": line} for line in lyrics_lines],
            "metadata": {}
        }
        
    def _extract_audio_features(self, audio: np.ndarray) -> Dict[str, np.ndarray]:
        """Extract features from vocal audio for alignment."""
        # Convert to mono for feature extraction
        if audio.shape[0] == 2:
            audio_mono = np.mean(audio, axis=0)
        else:
            audio_mono = audio[0]
            
        # Extract MFCC features
        mfcc = librosa.feature.mfcc(
            y=audio_mono,
            sr=self.sample_rate,
            hop_length=self.hop_length,
            n_mfcc=13
        )
        
        # Extract onset strength
        onset_strength = librosa.onset.onset_strength(
            y=audio_mono,
            sr=self.sample_rate,
            hop_length=self.hop_length
        )
        
        # Extract spectral centroid (brightness)
        spectral_centroid = librosa.feature.spectral_centroid(
            y=audio_mono,
            sr=self.sample_rate,
            hop_length=self.hop_length
        )[0]
        
        # Time axis in seconds
        times = librosa.times_like(mfcc, sr=self.sample_rate, hop_length=self.hop_length)
        
        return {
            "mfcc": mfcc.T,  # (frames, features)
            "onset_strength": onset_strength,
            "spectral_centroid": spectral_centroid,
            "times": times
        }
        
    def _align_text_to_audio(
        self, 
        lyrics_data: Dict[str, Any], 
        audio_features: Dict[str, np.ndarray]
    ) -> Dict[str, Any]:
        """Align plain text lyrics to audio using DTW."""
        lines = lyrics_data["lines"]
        
        if not self.phonemizer:
            logger.warning("No phonemizer available, using heuristic alignment")
            return self._heuristic_alignment(lines, audio_features)
            
        # Phonemize all text
        all_text = " ".join([line["text"] for line in lines])
        try:
            phones = phonemize(
                all_text,
                backend='espeak',
                language='en-us',
                preserve_punctuation=True,
                with_stress=True
            )
        except Exception as e:
            logger.warning(f"Phonemization failed: {e}, using heuristic alignment")
            return self._heuristic_alignment(lines, audio_features)
            
        # Create phone-based alignment target
        phone_features = self._create_phone_features(phones, audio_features)
        
        # Align using DTW
        alignment_path = self._dtw_align(phone_features, audio_features["mfcc"])
        
        # Map alignment back to words and lines
        aligned_data = self._map_alignment_to_text(alignment_path, lines, audio_features)
        
        return aligned_data
        
    def _heuristic_alignment(
        self, 
        lines: List[Dict[str, Any]], 
        audio_features: Dict[str, np.ndarray]
    ) -> Dict[str, Any]:
        """Simple heuristic alignment based on onset detection."""
        logger.info("Using heuristic alignment based on onsets")
        
        # Find strong onsets
        onset_frames = librosa.onset.onset_detect(
            onset_envelope=audio_features["onset_strength"],
            sr=self.sample_rate,
            hop_length=self.hop_length,
            units='time'
        )
        
        # Distribute lines across detected onsets
        if len(onset_frames) < len(lines):
            # Not enough onsets, distribute evenly
            duration = audio_features["times"][-1]
            line_duration = duration / len(lines)
            onset_frames = [i * line_duration for i in range(len(lines))]
            
        # Assign lines to onset times
        aligned_lines = []
        words = []
        
        for i, line_data in enumerate(lines):
            start_time = onset_frames[min(i, len(onset_frames) - 1)]
            end_time = onset_frames[min(i + 1, len(onset_frames) - 1)] if i < len(lines) - 1 else audio_features["times"][-1]
            
            # Split line into words
            line_words = line_data["text"].split()
            word_duration = (end_time - start_time) / max(len(line_words), 1)
            
            line_word_list = []
            for j, word_text in enumerate(line_words):
                word_start = start_time + j * word_duration
                word_end = start_time + (j + 1) * word_duration
                
                word_id = f"W{len(words) + 1}"
                word = {
                    "id": word_id,
                    "t": word_text,
                    "s": round(word_start, 3),
                    "e": round(word_end, 3),
                    "conf": 0.5  # Low confidence for heuristic
                }
                
                words.append(word)
                line_word_list.append(word)
                
            line_id = f"L{i + 1}"
            aligned_lines.append({
                "id": line_id,
                "singer_id": "A",
                "start": round(start_time, 3),
                "end": round(end_time, 3),
                "text": line_data["text"],
                "words": line_word_list
            })
            
        return {
            "lines": aligned_lines,
            "words": words,
            "alignment_method": "heuristic",
            "confidence": 0.5
        }
        
    def _create_phone_features(
        self, 
        phones: str, 
        audio_features: Dict[str, np.ndarray]
    ) -> np.ndarray:
        """Create feature representation for phonemized text."""
        # This is a simplified approach - in practice you'd want
        # a proper acoustic model here
        phone_list = phones.split()
        
        # Create simple phone-to-feature mapping
        phone_features = []
        for phone in phone_list:
            # Map phones to rough acoustic features
            feature = self._phone_to_feature(phone)
            phone_features.append(feature)
            
        return np.array(phone_features)
        
    def _phone_to_feature(self, phone: str) -> List[float]:
        """Map phoneme to rough acoustic feature vector."""
        # Very simplified phone-to-acoustic mapping
        # In practice, use a trained acoustic model
        vowels = {'a', 'e', 'i', 'o', 'u', 'ə', 'ɪ', 'ʊ', 'ɛ', 'ɔ'}
        fricatives = {'f', 'v', 's', 'z', 'ʃ', 'ʒ', 'θ', 'ð', 'h'}
        stops = {'p', 'b', 't', 'd', 'k', 'g'}
        
        feature = [0.0] * 13  # Match MFCC dimension
        
        if any(v in phone.lower() for v in vowels):
            feature[0] = 1.0  # Vowel indicator
            feature[1] = 0.8  # Energy
        elif any(f in phone.lower() for f in fricatives):
            feature[2] = 1.0  # Fricative indicator
            feature[3] = 0.6  # High frequency
        elif any(s in phone.lower() for s in stops):
            feature[4] = 1.0  # Stop indicator
            feature[5] = 0.4  # Short duration
        else:
            feature[6] = 0.5  # Other/consonant
            
        return feature
        
    def _dtw_align(
        self, 
        phone_features: np.ndarray, 
        audio_features: np.ndarray
    ) -> List[Tuple[int, int]]:
        """Perform DTW alignment between phone and audio features."""
        # Compute distance matrix
        distance_matrix = cdist(phone_features, audio_features, metric='euclidean')
        
        # Perform DTW
        alignment = dtw(distance_matrix, keep_internals=True)
        
        # Extract alignment path
        path = list(zip(alignment.index1, alignment.index2))
        
        return path
        
    def _map_alignment_to_text(
        self, 
        alignment_path: List[Tuple[int, int]], 
        lines: List[Dict[str, Any]], 
        audio_features: Dict[str, np.ndarray]
    ) -> Dict[str, Any]:
        """Map DTW alignment back to words and lines."""
        # This is a simplified mapping - production version would be more sophisticated
        times = audio_features["times"]
        
        # For now, fall back to heuristic alignment
        return self._heuristic_alignment(lines, audio_features)
        
    def _refine_lrc_timing(
        self, 
        lyrics_data: Dict[str, Any], 
        audio_features: Dict[str, np.ndarray]
    ) -> Dict[str, Any]:
        """Refine existing LRC timing using audio features."""
        lines = lyrics_data["lines"]
        
        # Convert to expected format
        aligned_lines = []
        words = []
        
        for i, line_data in enumerate(lines):
            # Split line into words
            line_words = line_data["text"].split()
            word_duration = (line_data["end"] - line_data["start"]) / max(len(line_words), 1)
            
            line_word_list = []
            for j, word_text in enumerate(line_words):
                word_start = line_data["start"] + j * word_duration
                word_end = line_data["start"] + (j + 1) * word_duration
                
                word_id = f"W{len(words) + 1}"
                word = {
                    "id": word_id,
                    "t": word_text,
                    "s": round(word_start, 3),
                    "e": round(word_end, 3),
                    "conf": 0.8  # Higher confidence for LRC
                }
                
                words.append(word)
                line_word_list.append(word)
                
            line_id = f"L{i + 1}"
            aligned_lines.append({
                "id": line_id,
                "singer_id": "A",
                "start": round(line_data["start"], 3),
                "end": round(line_data["end"], 3),
                "text": line_data["text"],
                "words": line_word_list
            })
            
        return {
            "lines": aligned_lines,
            "words": words,
            "alignment_method": "lrc_refined",
            "confidence": 0.8
        }
        
    def _post_process_alignment(self, alignment: Dict[str, Any]) -> Dict[str, Any]:
        """Post-process alignment results."""
        # Ensure no overlapping segments
        lines = alignment["lines"]
        for i in range(len(lines) - 1):
            if lines[i]["end"] > lines[i + 1]["start"]:
                # Resolve overlap by splitting the gap
                gap_mid = (lines[i]["end"] + lines[i + 1]["start"]) / 2
                lines[i]["end"] = gap_mid
                lines[i + 1]["start"] = gap_mid
                
        # Update word timing within lines
        for line in lines:
            line_duration = line["end"] - line["start"]
            word_count = len(line["words"])
            if word_count > 0:
                word_duration = line_duration / word_count
                for j, word in enumerate(line["words"]):
                    word["s"] = line["start"] + j * word_duration
                    word["e"] = line["start"] + (j + 1) * word_duration
                    
        alignment["reference"] = "aligned_to_vocals_wav"
        alignment["offset_sec"] = 0.0
        
        return alignment