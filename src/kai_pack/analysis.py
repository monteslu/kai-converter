"""Musical analysis features extraction."""

import logging
import warnings
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

import numpy as np
import librosa
import scipy.signal
from scipy.ndimage import median_filter

# Suppress warnings from analysis libraries
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

try:
    import crepe
    CREPE_AVAILABLE = True
except ImportError:
    CREPE_AVAILABLE = False
    
try:
    import madmom
    MADMOM_AVAILABLE = True  
except ImportError:
    MADMOM_AVAILABLE = False

try:
    import essentia.standard as es
    ESSENTIA_AVAILABLE = True
except ImportError:
    ESSENTIA_AVAILABLE = False


logger = logging.getLogger(__name__)


class MusicalAnalyzer:
    """Handles musical analysis feature extraction."""
    
    def __init__(self, sample_rate: int = 44100, hop_length: int = 512, vocal_pitch_type: str = "midi_cents"):
        self.sample_rate = sample_rate
        self.hop_length = hop_length
        self.frame_rate = sample_rate / hop_length
        self.vocal_pitch_type = vocal_pitch_type
        
    def extract_features(
        self, 
        vocals_audio: np.ndarray,
        full_audio: np.ndarray,
        feature_list: List[str]
    ) -> Dict[str, Any]:
        """
        Extract requested musical features.
        
        Args:
            vocals_audio: Vocal stem audio (2, samples)
            full_audio: Full mix audio (2, samples) 
            feature_list: List of features to extract
            
        Returns:
            Dict mapping feature names to extracted data
        """
        logger.info(f"Extracting features: {feature_list}")
        
        features = {}
        
        # Convert to mono for analysis
        vocals_mono = np.mean(vocals_audio, axis=0) if vocals_audio.shape[0] == 2 else vocals_audio[0]
        full_mono = np.mean(full_audio, axis=0) if full_audio.shape[0] == 2 else full_audio[0]
        
        for i, feature in enumerate(feature_list, 1):
            try:
                logger.info(f"  [{i}/{len(feature_list)}] Extracting {feature}...")
                start_time = datetime.utcnow()
                
                if feature == "f0":
                    logger.info(f"    → Running CREPE pitch detection on vocals ({len(vocals_mono)/self.sample_rate:.1f}s of audio)...")
                    f0_data = self.extract_f0(vocals_mono)
                    features["vocals_f0"] = f0_data

                    # Quantize pitch data for vocal_pitch
                    logger.info(f"    → Quantizing pitch data using method: {self.vocal_pitch_type}")
                    vocal_pitch_data = self.quantize_vocal_pitch(f0_data, self.vocal_pitch_type)
                    features["vocal_pitch"] = vocal_pitch_data

                    # Also detect musical key from the pitch data
                    logger.info(f"    → Detecting musical key from pitch data...")
                    key_data = self.detect_key_from_f0(f0_data)
                    features["key_detection"] = key_data
                    logger.info(f"    ✓ F0 extraction and key detection complete - detected key: {key_data['key']}")
                elif feature == "notes":
                    logger.info(f"    → Detecting musical notes from pitch data...")
                    features["notes_ref"] = self.extract_notes(vocals_mono)
                    logger.info(f"    ✓ Note detection complete")
                elif feature == "onsets":
                    logger.info(f"    → Detecting note onsets in vocals...")
                    features["onsets_ref"] = self.extract_onsets(vocals_mono)
                    logger.info(f"    ✓ Onset detection complete")
                elif feature == "tempo":
                    logger.info(f"    → Analyzing tempo and beat tracking on full mix...")
                    features["tempo_map"] = self.extract_tempo(full_mono)
                    logger.info(f"    ✓ Tempo analysis complete")
                elif feature == "keys":
                    logger.info(f"    → Detecting musical keys from full mix...")
                    features["keys"] = self.extract_keys(full_mono)
                    logger.info(f"    ✓ Key detection complete")
                elif feature == "chords":
                    logger.info(f"    → Analyzing chord progressions from full mix...")
                    features["chords"] = self.extract_chords(full_mono)
                    logger.info(f"    ✓ Chord analysis complete")
                elif feature == "mfcc":
                    logger.info(f"    → Extracting MFCC features from vocals...")
                    features["mfcc_ref"] = self.extract_mfcc(vocals_mono)
                    logger.info(f"    ✓ MFCC extraction complete")
                else:
                    logger.warning(f"Unknown feature: {feature}")
                
                elapsed = (datetime.utcnow() - start_time).total_seconds()
                logger.info(f"    ⏱ Completed in {elapsed:.1f}s")
                    
            except Exception as e:
                logger.error(f"Failed to extract {feature}: {e}")
                
        logger.info(f"Extracted {len(features)} features successfully")
        return features
        
    def extract_f0(self, audio: np.ndarray) -> Dict[str, Any]:
        """Extract F0 contour using CREPE or librosa."""
        logger.debug("Extracting F0 contour")
        
        if CREPE_AVAILABLE:
            return self._extract_f0_crepe(audio)
        else:
            return self._extract_f0_librosa(audio)
            
    def _extract_f0_crepe(self, audio: np.ndarray) -> Dict[str, Any]:
        """Extract F0 using CREPE."""
        # CREPE step size for 25ms frames (good balance of speed vs accuracy)
        step_size = 25  # 25ms

        time, frequency, confidence, _ = crepe.predict(
            audio,
            self.sample_rate,
            step_size=step_size,  # 25ms
            viterbi=False,  # Skip smoothing for speed
            model_capacity='tiny'  # Fast model
        )

        # Convert to cents relative to A4 (440 Hz)
        cents = np.zeros_like(frequency)
        valid_mask = frequency > 0
        cents[valid_mask] = 1200 * np.log2(frequency[valid_mask] / 440.0)

        return {
            "times": time.tolist(),
            "frequencies": frequency.tolist(),
            "cents": cents.tolist(),
            "confidence": confidence.tolist(),
            "hop_ms": step_size,
            "method": "crepe-tiny"
        }
    
    def detect_key_from_f0(self, f0_data: Dict[str, Any]) -> Dict[str, Any]:
        """Detect musical key from F0/pitch data."""
        frequencies = np.array(f0_data["frequencies"])
        confidence = np.array(f0_data["confidence"])
        
        # Filter out low-confidence and zero frequencies
        valid_mask = (frequencies > 0) & (confidence > 0.7)
        if not np.any(valid_mask):
            return {"key": "unknown", "confidence": 0.0, "method": "insufficient_data"}
        
        valid_frequencies = frequencies[valid_mask]
        
        # Convert frequencies to MIDI notes (semitones)
        midi_notes = librosa.hz_to_midi(valid_frequencies)
        
        # Round to nearest semitone and get pitch classes (0-11)
        pitch_classes = np.round(midi_notes) % 12
        
        # Count occurrences of each pitch class
        pitch_histogram = np.zeros(12)
        for pc in pitch_classes:
            pitch_histogram[int(pc)] += 1
        
        # Normalize histogram
        if np.sum(pitch_histogram) > 0:
            pitch_histogram = pitch_histogram / np.sum(pitch_histogram)
        
        # Define major and minor key profiles (Krumhansl-Schmuckler)
        major_profile = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
        minor_profile = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
        
        # Normalize profiles
        major_profile = major_profile / np.sum(major_profile)
        minor_profile = minor_profile / np.sum(minor_profile)
        
        # Calculate correlation for each possible key
        best_correlation = -1
        best_key = "unknown"
        best_mode = "major"
        
        note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        
        for root in range(12):
            # Test major key
            shifted_major = np.roll(major_profile, root)
            correlation_major = np.corrcoef(pitch_histogram, shifted_major)[0, 1]
            if not np.isnan(correlation_major) and correlation_major > best_correlation:
                best_correlation = correlation_major
                best_key = note_names[root]
                best_mode = "major"
            
            # Test minor key  
            shifted_minor = np.roll(minor_profile, root)
            correlation_minor = np.corrcoef(pitch_histogram, shifted_minor)[0, 1]
            if not np.isnan(correlation_minor) and correlation_minor > best_correlation:
                best_correlation = correlation_minor
                best_key = note_names[root]
                best_mode = "minor"
        
        key_string = f"{best_key} {best_mode}" if best_key != "unknown" else "unknown"
        
        return {
            "key": key_string,
            "confidence": max(0.0, best_correlation) if best_correlation > 0 else 0.0,
            "method": "krumhansl_schmuckler",
            "pitch_histogram": pitch_histogram.tolist()
        }

    def quantize_vocal_pitch(self, f0_data: Dict[str, Any], quantization_type: str) -> Dict[str, Any]:
        """
        Quantize vocal pitch data using the specified method.

        Args:
            f0_data: Raw F0 data from extract_f0
            quantization_type: One of "midi_cents", "note_only_rle", "segments", "delta_encoded"

        Returns:
            Quantized pitch data suitable for song.json vocal_pitch field
        """
        frequencies = np.array(f0_data["frequencies"])
        times = np.array(f0_data["times"])
        confidence = np.array(f0_data["confidence"])

        if quantization_type == "midi_cents":
            return self._quantize_midi_cents(frequencies, times, confidence)
        elif quantization_type == "note_only_rle":
            return self._quantize_note_only_rle(frequencies, times, confidence)
        elif quantization_type == "segments":
            return self._quantize_segments(frequencies, times, confidence)
        elif quantization_type == "delta_encoded":
            return self._quantize_delta_encoded(frequencies, times, confidence)
        else:
            logger.warning(f"Unknown quantization type: {quantization_type}, using midi_cents")
            return self._quantize_midi_cents(frequencies, times, confidence)

    def _quantize_midi_cents(self, frequencies: np.ndarray, times: np.ndarray, confidence: np.ndarray,
                            sample_rate_hz: int = 25) -> Dict[str, Any]:
        """Quantize to MIDI note + cents at fixed sample rate."""
        # Resample to target rate
        target_times = np.arange(0, times[-1], 1.0 / sample_rate_hz)
        resampled_freqs = np.interp(target_times, times, frequencies)
        resampled_conf = np.interp(target_times, times, confidence)

        quant_data = []
        for freq, conf in zip(resampled_freqs, resampled_conf):
            if freq > 0 and conf > 0.3:  # Confidence threshold
                midi_note = librosa.hz_to_midi(freq)
                note = int(np.round(midi_note))
                cents = int(np.round((midi_note - note) * 100))
                # Clamp values
                note = int(np.clip(note, 0, 127))
                cents = int(np.clip(cents, -50, 50))
                quant_data.append([note, cents])
            else:
                quant_data.append([0, 0])  # Silence

        return {
            "quantization_type": "midi_cents",
            "sample_rate_hz": sample_rate_hz,
            "quant_data": quant_data
        }

    def _quantize_note_only_rle(self, frequencies: np.ndarray, times: np.ndarray, confidence: np.ndarray) -> Dict[str, Any]:
        """Run-length encode MIDI notes only."""
        quant_data = []
        current_note = None
        start_time = 0

        for i, (freq, conf, time) in enumerate(zip(frequencies, confidence, times)):
            if freq > 0 and conf > 0.3:
                midi_note = int(np.round(librosa.hz_to_midi(freq)))
                midi_note = int(np.clip(midi_note, 0, 127))
            else:
                midi_note = 0  # Silence

            if midi_note != current_note:
                if current_note is not None:
                    duration_ms = int((time - start_time) * 1000)
                    if duration_ms > 0:
                        quant_data.append([current_note, duration_ms])
                current_note = midi_note
                start_time = time

        # Add final segment
        if current_note is not None:
            duration_ms = int((times[-1] - start_time) * 1000)
            if duration_ms > 0:
                quant_data.append([current_note, duration_ms])

        return {
            "quantization_type": "note_only_rle",
            "quant_data": quant_data
        }

    def _quantize_segments(self, frequencies: np.ndarray, times: np.ndarray, confidence: np.ndarray) -> Dict[str, Any]:
        """Create time-based pitch segments."""
        quant_data = []
        current_note = None
        current_cents = None
        segment_start = 0

        for i, (freq, conf, time) in enumerate(zip(frequencies, confidence, times)):
            if freq > 0 and conf > 0.3:
                midi_val = librosa.hz_to_midi(freq)
                note = int(np.round(midi_val))
                cents = int(np.round((midi_val - note) * 100))
                note = int(np.clip(note, 0, 127))
                cents = int(np.clip(cents, -50, 50))
            else:
                note = 0
                cents = 0

            # Check if pitch changed significantly
            if note != current_note or (current_cents is not None and abs(cents - current_cents) > 10):
                if current_note is not None:
                    # Save previous segment
                    segment = {
                        "t": int(segment_start * 1000),  # ms
                        "d": int((time - segment_start) * 1000),  # ms
                        "n": current_note,
                        "c": current_cents
                    }
                    if segment["d"] > 0:
                        quant_data.append(segment)

                current_note = note
                current_cents = cents
                segment_start = time

        # Add final segment
        if current_note is not None:
            segment = {
                "t": int(segment_start * 1000),
                "d": int((times[-1] - segment_start) * 1000),
                "n": current_note,
                "c": current_cents
            }
            if segment["d"] > 0:
                quant_data.append(segment)

        return {
            "quantization_type": "segments",
            "quant_data": quant_data
        }

    def _quantize_delta_encoded(self, frequencies: np.ndarray, times: np.ndarray, confidence: np.ndarray,
                               sample_rate_hz: int = 25) -> Dict[str, Any]:
        """Delta encode pitch changes from initial value."""
        # Resample first
        target_times = np.arange(0, times[-1], 1.0 / sample_rate_hz)
        resampled_freqs = np.interp(target_times, times, frequencies)
        resampled_conf = np.interp(target_times, times, confidence)

        # Find first valid pitch
        initial_note = 60  # Default to middle C
        initial_cents = 0
        for freq, conf in zip(resampled_freqs, resampled_conf):
            if freq > 0 and conf > 0.3:
                midi_val = librosa.hz_to_midi(freq)
                initial_note = int(np.round(midi_val))
                initial_cents = int(np.round((midi_val - initial_note) * 100))
                initial_note = int(np.clip(initial_note, 0, 127))
                initial_cents = int(np.clip(initial_cents, -50, 50))
                break

        # Calculate deltas in semitones
        deltas = []
        prev_note = initial_note + initial_cents / 100.0

        for freq, conf in zip(resampled_freqs, resampled_conf):
            if freq > 0 and conf > 0.3:
                midi_val = librosa.hz_to_midi(freq)
            else:
                midi_val = 0

            delta = int(np.round(midi_val - prev_note))
            deltas.append(delta)

            if midi_val > 0:
                prev_note = midi_val

        return {
            "quantization_type": "delta_encoded",
            "sample_rate_hz": sample_rate_hz,
            "quant_data": {
                "initial": [initial_note, initial_cents],
                "deltas": deltas
            }
        }

    def _extract_f0_librosa(self, audio: np.ndarray) -> Dict[str, Any]:
        """Extract F0 using librosa pyin."""
        f0, voiced_flag, voiced_probs = librosa.pyin(
            audio,
            fmin=librosa.note_to_hz('C2'),
            fmax=librosa.note_to_hz('C7'),
            sr=self.sample_rate,
            hop_length=self.hop_length,
            frame_length=2048
        )
        
        # Convert to cents
        cents = np.zeros_like(f0)
        valid_mask = ~np.isnan(f0) & (f0 > 0)
        cents[valid_mask] = 1200 * np.log2(f0[valid_mask] / 440.0)
        cents[~valid_mask] = 0
        
        times = librosa.frames_to_time(
            np.arange(len(f0)), 
            sr=self.sample_rate, 
            hop_length=self.hop_length
        )
        
        return {
            "times": times.tolist(),
            "frequencies": np.nan_to_num(f0).tolist(),
            "cents": cents.tolist(),
            "confidence": voiced_probs.tolist(),
            "hop_ms": (self.hop_length / self.sample_rate) * 1000,
            "method": "librosa-pyin"
        }
        
    def extract_notes(self, audio: np.ndarray) -> Dict[str, Any]:
        """Extract note segments from F0 contour."""
        logger.debug("Extracting note segments")
        
        # First extract F0
        f0_data = self.extract_f0(audio)
        frequencies = np.array(f0_data["frequencies"])
        times = np.array(f0_data["times"])
        confidence = np.array(f0_data["confidence"])
        
        # Find voiced segments
        voiced_mask = (frequencies > 0) & (confidence > 0.5)
        
        # Segment into notes based on frequency changes and gaps
        notes = []
        if np.any(voiced_mask):
            # Find voiced segments
            voiced_diff = np.diff(np.concatenate(([False], voiced_mask, [False])).astype(int))
            segment_starts = np.where(voiced_diff == 1)[0]
            segment_ends = np.where(voiced_diff == -1)[0]
            
            for start_idx, end_idx in zip(segment_starts, segment_ends):
                if end_idx > start_idx:
                    segment_freqs = frequencies[start_idx:end_idx]
                    segment_times = times[start_idx:end_idx]
                    
                    # Use median frequency for the note
                    median_freq = np.median(segment_freqs[segment_freqs > 0])
                    if median_freq > 0:
                        midi_note = librosa.hz_to_midi(median_freq)
                        cents_offset = (librosa.hz_to_midi(median_freq) - round(midi_note)) * 100
                        
                        # Calculate vibrato (frequency variation)
                        freq_std = np.std(segment_freqs[segment_freqs > 0])
                        vibrato_cents = 1200 * np.log2((median_freq + freq_std) / median_freq) if freq_std > 0 else 0
                        
                        note = {
                            "midi": int(round(midi_note)),
                            "start": float(segment_times[0]),
                            "end": float(segment_times[-1]),
                            "cents": float(cents_offset),
                            "vibrato": {
                                "rate_hz": 0.0,  # Would need more analysis
                                "extent_cents": float(vibrato_cents)
                            }
                        }
                        notes.append(note)
                        
        return {
            "notes": notes,
            "method": "f0_segmentation"
        }
        
    def extract_onsets(self, audio: np.ndarray) -> Dict[str, Any]:
        """Extract onset times."""
        logger.debug("Extracting onsets")
        
        if MADMOM_AVAILABLE:
            return self._extract_onsets_madmom(audio)
        else:
            return self._extract_onsets_librosa(audio)
            
    def _extract_onsets_madmom(self, audio: np.ndarray) -> Dict[str, Any]:
        """Extract onsets using madmom."""
        try:
            proc = madmom.features.onsets.OnsetPeakPickingProcessor(fps=100)
            act = madmom.features.onsets.RNNOnsetProcessor()(audio.astype(np.float32))
            onsets = proc(act)
            
            return {
                "times": onsets.tolist(),
                "method": "madmom-rnn"
            }
        except Exception as e:
            logger.warning(f"Madmom onset detection failed: {e}, falling back to librosa")
            return self._extract_onsets_librosa(audio)
            
    def _extract_onsets_librosa(self, audio: np.ndarray) -> Dict[str, Any]:
        """Extract onsets using librosa."""
        onset_frames = librosa.onset.onset_detect(
            y=audio,
            sr=self.sample_rate,
            hop_length=self.hop_length,
            units='time'
        )
        
        return {
            "times": onset_frames.tolist(),
            "method": "librosa-default"
        }
        
    def extract_tempo(self, audio: np.ndarray) -> Dict[str, Any]:
        """Extract tempo and beat tracking."""
        logger.debug("Extracting tempo and beats")
        
        if MADMOM_AVAILABLE:
            return self._extract_tempo_madmom(audio)
        else:
            return self._extract_tempo_librosa(audio)
            
    def _extract_tempo_madmom(self, audio: np.ndarray) -> Dict[str, Any]:
        """Extract tempo using madmom."""
        try:
            proc = madmom.features.tempo.TempoEstimationProcessor(fps=200)
            act = madmom.features.beats.RNNBeatProcessor()(audio.astype(np.float32))
            tempo = proc(act)[0][0]  # Get the top tempo estimate
            
            # Get beat times
            beat_proc = madmom.features.beats.BeatTrackingProcessor(fps=200)
            beats = beat_proc(act)
            
            return {
                "bpm": float(tempo),
                "beats": beats.tolist(),
                "bars": [],  # Would need bar detection
                "method": "madmom-rnn"
            }
        except Exception as e:
            logger.warning(f"Madmom tempo detection failed: {e}, falling back to librosa")
            return self._extract_tempo_librosa(audio)
            
    def _extract_tempo_librosa(self, audio: np.ndarray) -> Dict[str, Any]:
        """Extract tempo using librosa."""
        tempo, beats = librosa.beat.beat_track(
            y=audio,
            sr=self.sample_rate,
            hop_length=self.hop_length
        )
        
        beat_times = librosa.frames_to_time(beats, sr=self.sample_rate, hop_length=self.hop_length)
        
        return {
            "bpm": float(tempo),
            "beats": beat_times.tolist(),
            "bars": [],  # Simple 4/4 assumption
            "method": "librosa-default"
        }
        
    def extract_keys(self, audio: np.ndarray) -> Dict[str, Any]:
        """Extract key signature timeline."""
        logger.debug("Extracting key signatures")
        
        if ESSENTIA_AVAILABLE:
            return self._extract_keys_essentia(audio)
        else:
            return self._extract_keys_librosa(audio)
            
    def _extract_keys_essentia(self, audio: np.ndarray) -> Dict[str, Any]:
        """Extract keys using Essentia."""
        try:
            # Essentia key detection
            key_extractor = es.KeyExtractor()
            key, scale, strength = key_extractor(audio.astype(np.float32))
            
            return {
                "segments": [{
                    "start": 0.0,
                    "end": len(audio) / self.sample_rate,
                    "key": key,
                    "mode": scale,
                    "confidence": float(strength)
                }],
                "method": "essentia-key-extractor"
            }
        except Exception as e:
            logger.warning(f"Essentia key detection failed: {e}, falling back to librosa")
            return self._extract_keys_librosa(audio)
            
    def _extract_keys_librosa(self, audio: np.ndarray) -> Dict[str, Any]:
        """Extract keys using librosa chroma analysis."""
        # Extract chroma features
        chroma = librosa.feature.chroma_cqt(
            y=audio,
            sr=self.sample_rate,
            hop_length=self.hop_length
        )
        
        # Simple key estimation based on chroma energy
        chroma_mean = np.mean(chroma, axis=1)
        key_idx = np.argmax(chroma_mean)
        
        keys = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        estimated_key = keys[key_idx]
        
        return {
            "segments": [{
                "start": 0.0,
                "end": len(audio) / self.sample_rate,
                "key": estimated_key,
                "mode": "major",  # Simple assumption
                "confidence": float(chroma_mean[key_idx])
            }],
            "method": "librosa-chroma"
        }
        
    def extract_chords(self, audio: np.ndarray) -> Dict[str, Any]:
        """Extract chord progression."""
        logger.debug("Extracting chord progression")
        
        # Simple chord detection based on chroma
        chroma = librosa.feature.chroma_cqt(
            y=audio,
            sr=self.sample_rate,
            hop_length=self.hop_length * 4  # Longer hops for chord analysis
        )
        
        times = librosa.frames_to_time(
            np.arange(chroma.shape[1]), 
            sr=self.sample_rate, 
            hop_length=self.hop_length * 4
        )
        
        # Very simple chord recognition (just major triads)
        chord_templates = {
            'C': [1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0],
            'F': [1, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0],
            'G': [0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 1],
            'Am': [1, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0],
            'N': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]  # No chord
        }
        
        segments = []
        for i, frame_chroma in enumerate(chroma.T):
            # Find best matching chord template
            best_chord = 'N'
            best_score = -1
            
            for chord_name, template in chord_templates.items():
                score = np.dot(frame_chroma, template)
                if score > best_score:
                    best_score = score
                    best_chord = chord_name
                    
            segments.append({
                "start": float(times[i]),
                "end": float(times[i + 1]) if i < len(times) - 1 else len(audio) / self.sample_rate,
                "chord": best_chord,
                "confidence": float(best_score)
            })
            
        return {
            "segments": segments,
            "method": "librosa-chroma-template"
        }
        
    def extract_mfcc(self, audio: np.ndarray) -> Dict[str, Any]:
        """Extract MFCC features for timbre analysis."""
        logger.debug("Extracting MFCC features")
        
        mfcc = librosa.feature.mfcc(
            y=audio,
            sr=self.sample_rate,
            hop_length=self.hop_length * 8,  # Lower rate for MFCC
            n_mfcc=13
        )
        
        times = librosa.frames_to_time(
            np.arange(mfcc.shape[1]), 
            sr=self.sample_rate, 
            hop_length=self.hop_length * 8
        )
        
        return {
            "times": times.tolist(),
            "mfcc": mfcc.T.tolist(),  # (frames, coefficients)
            "method": "librosa-mfcc"
        }
        
    def save_features(self, features: Dict[str, Any], output_dir: Path) -> Dict[str, Path]:
        """Save extracted features to JSON files."""
        import json
        
        output_dir.mkdir(parents=True, exist_ok=True)
        saved_files = {}
        
        for feature_name, feature_data in features.items():
            filename = f"{feature_name}.json"
            output_path = output_dir / filename
            
            with open(output_path, 'w') as f:
                json.dump(feature_data, f, indent=2)
                
            saved_files[feature_name] = output_path
            logger.debug(f"Saved feature '{feature_name}' to {output_path}")
            
        return saved_files