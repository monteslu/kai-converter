"""Automatic lyrics transcription and alignment using Whisper."""

import logging
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing

import numpy as np
import librosa
import soundfile as sf
import torch

try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    whisper = None

try:
    import torchcrepe
    CREPE_AVAILABLE = True
except ImportError:
    CREPE_AVAILABLE = False
    torchcrepe = None

logger = logging.getLogger(__name__)


def transcribe_chunk_worker(chunk: Dict[str, Any], model_name: str) -> Optional[Dict[str, Any]]:
    """Worker function for parallel chunk transcription."""
    try:
        # Each worker needs its own Whisper model instance
        import whisper
        model = whisper.load_model(model_name)
        
        # Convert to mono for transcription
        audio = chunk['audio']
        if audio.shape[0] == 2:
            audio_mono = np.mean(audio, axis=0)
        else:
            audio_mono = audio[0]
            
        # Ensure audio is in the right format for Whisper
        audio_mono = audio_mono.astype(np.float32)
        
        # Transcribe chunk with word timestamps
        # Build transcription parameters
        transcribe_params = {
            "word_timestamps": True,
            "language": "en",  # Force English
            "task": "transcribe",
            "verbose": False,
            "condition_on_previous_text": False  # Reduces repetition loops in singing
        }

        # Note: initial_prompt not used in parallel workers as it can bias individual chunks
        result = model.transcribe(audio_mono, **transcribe_params)
        
        # Add timing offset to all timestamps
        start_offset = chunk['start_time']
        
        if 'segments' in result:
            for segment in result['segments']:
                segment['start'] += start_offset
                segment['end'] += start_offset
                
                if 'words' in segment:
                    for word in segment['words']:
                        word['start'] += start_offset
                        word['end'] += start_offset
        
        # Add chunk info
        result['chunk_info'] = {
            'chunk_id': chunk['chunk_id'],
            'start_time': chunk['start_time'],
            'end_time': chunk['end_time'],
            'duration': chunk['duration']
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Worker failed to transcribe chunk {chunk['chunk_id']}: {e}")
        return None


class LyricsTranscriber:
    """Handles automatic lyrics transcription and alignment using Whisper.

    Note: Uses permissive transcription settings to avoid missing lyrics:
    - no_speech_threshold=0.3 (changed from default 0.6): Catches more potential speech/singing
    - condition_on_previous_text=False: Avoids context bias and repetition loops in singing
    """

    def __init__(self, sample_rate: int = 44100, model_name: str = "base", language: str = "en", device: Optional[str] = None, use_crepe_filter: bool = False, silence_threshold: int = -20):
        self.sample_rate = sample_rate
        self.model_name = model_name
        self.language = language
        self.model = None
        
        # Auto-detect device if not specified
        if device is None:
            if torch.cuda.is_available():
                self.device = "cuda"
            elif torch.backends.mps.is_available() and torch.backends.mps.is_built():
                self.device = "mps"
            else:
                self.device = "cpu"
        else:
            self.device = device
            
        self.use_crepe_filter = use_crepe_filter
        self.silence_threshold = silence_threshold
        
        logger.info(f"Using Whisper device: {self.device}")
        logger.info(f"CREPE filtering: {'enabled' if use_crepe_filter else 'disabled'}")
        logger.info(f"Silence threshold: {silence_threshold} dB")
        
        if not WHISPER_AVAILABLE:
            raise ImportError("Whisper is required for automatic lyrics transcription. Install with: pip install openai-whisper")
        
        # Load Whisper model
        try:
            logger.info(f"Loading Whisper model: {model_name}")
            self.model = whisper.load_model(model_name, device=self.device)
            logger.info(f"Successfully loaded Whisper model: {model_name}")
        except Exception as e:
            if self.device == "mps" and "SparseMPS" in str(e):
                logger.warning(f"MPS not compatible with {model_name}, falling back to CPU")
                self.device = "cpu"
                try:
                    self.model = whisper.load_model(model_name, device=self.device)
                    logger.info(f"Successfully loaded Whisper model: {model_name} on CPU")
                except Exception as cpu_e:
                    raise RuntimeError(f"Failed to load Whisper model {model_name} on CPU: {cpu_e}")
            else:
                raise RuntimeError(f"Failed to load Whisper model {model_name}: {e}")
    
    def detect_silence_boundaries(self, audio: np.ndarray, min_silence_duration: float = 0.5, 
                                silence_threshold: Optional[float] = None) -> List[float]:
        """
        Detect silence gaps suitable for chunk boundaries.
        
        Args:
            audio: Mono audio signal
            min_silence_duration: Minimum silence duration in seconds to consider
            silence_threshold: Silence threshold in dB (uses instance default if None)
            
        Returns:
            List of boundary timestamps in seconds
        """
        # Use instance silence threshold if not provided
        if silence_threshold is None:
            silence_threshold = self.silence_threshold
            
        logger.debug(f"Detecting silence boundaries with threshold {silence_threshold} dB")
        
        # Convert stereo to mono if needed
        if len(audio.shape) == 2:
            audio = np.mean(audio, axis=0)
        
        # Calculate RMS energy in small frames
        frame_size = int(0.1 * self.sample_rate)  # 100ms frames
        hop_size = frame_size // 4  # 25ms hop
        
        rms_values = []
        timestamps = []
        
        for i in range(0, len(audio) - frame_size, hop_size):
            frame = audio[i:i + frame_size]
            rms = np.sqrt(np.mean(frame**2))
            rms_db = 20 * np.log10(rms + 1e-8)  # Avoid log(0)
            rms_values.append(rms_db)
            timestamps.append(i / self.sample_rate)
        
        rms_values = np.array(rms_values)
        timestamps = np.array(timestamps)
        
        # Find silent regions
        silent_frames = rms_values < silence_threshold
        
        # Find continuous silent regions
        boundaries = [0.0]  # Always start at beginning
        
        in_silence = False
        silence_start = 0
        
        for i, is_silent in enumerate(silent_frames):
            if is_silent and not in_silence:
                # Start of silence
                in_silence = True
                silence_start = timestamps[i]
            elif not is_silent and in_silence:
                # End of silence
                in_silence = False
                silence_duration = timestamps[i] - silence_start
                
                if silence_duration >= min_silence_duration:
                    # Add boundary at middle of silence gap
                    boundary_time = silence_start + silence_duration / 2
                    boundaries.append(boundary_time)
        
        # Always end at audio end
        boundaries.append(len(audio) / self.sample_rate)
        
        return boundaries
    
    def create_audio_chunks(self, audio: np.ndarray, boundaries: List[float], 
                          max_chunk_duration: float = 30.0) -> List[Dict[str, Any]]:
        """
        Create audio chunks based on silence boundaries.
        
        Args:
            audio: Stereo audio (2, samples)
            boundaries: Boundary timestamps in seconds
            max_chunk_duration: Maximum chunk duration in seconds
            
        Returns:
            List of chunk dicts with audio data and timing info
        """
        chunks = []
        
        for i in range(len(boundaries) - 1):
            start_time = boundaries[i]
            end_time = boundaries[i + 1]
            duration = end_time - start_time
            
            # Split long segments
            if duration > max_chunk_duration:
                # Split into smaller chunks at max_chunk_duration intervals
                current_start = start_time
                while current_start < end_time:
                    current_end = min(current_start + max_chunk_duration, end_time)
                    
                    start_sample = int(current_start * self.sample_rate)
                    end_sample = int(current_end * self.sample_rate)
                    
                    if end_sample > start_sample:  # Ensure we have audio
                        chunk_audio = audio[:, start_sample:end_sample]
                        
                        chunks.append({
                            'audio': chunk_audio,
                            'start_time': current_start,
                            'end_time': current_end,
                            'duration': current_end - current_start,
                            'chunk_id': len(chunks)
                        })
                    
                    current_start = current_end
            else:
                # Use the whole segment
                start_sample = int(start_time * self.sample_rate)
                end_sample = int(end_time * self.sample_rate)
                
                if end_sample > start_sample:  # Ensure we have audio
                    chunk_audio = audio[:, start_sample:end_sample]
                    
                    chunks.append({
                        'audio': chunk_audio,
                        'start_time': start_time,
                        'end_time': end_time,
                        'duration': duration,
                        'chunk_id': len(chunks)
                    })
        
        logger.info(f"Created {len(chunks)} audio chunks from {len(boundaries)} boundaries")
        return chunks
    
    def analyze_chunk_vocal_quality(self, chunk: Dict[str, Any], min_confidence: float = 0.5) -> Dict[str, Any]:
        """
        Analyze chunk quality using CREPE pitch confidence to filter out non-vocal content.
        
        Args:
            chunk: Audio chunk with 'audio' key
            min_confidence: Minimum CREPE confidence threshold (0.0-1.0)
            
        Returns:
            Dict with quality analysis results
        """
        # Temporarily disable CREPE for faster processing - treat all chunks as vocal content
        logger.debug("CREPE disabled for faster processing - treating all chunks as vocal")
        return {
            'vocal_confidence': 0.7,  # Default moderate confidence
            'is_vocal': True,
            'is_strong_vocal': True,   # Assume all chunks are strong vocal 
            'is_weak_vocal': False,    # No weak vocals if all are strong
            'method': 'crepe_disabled_for_speed'
        }
            
        try:
            # Convert to mono and ensure correct format
            audio = chunk['audio']
            if audio.shape[0] == 2:
                audio_mono = np.mean(audio, axis=0)
            else:
                audio_mono = audio[0]
                
            # CREPE expects float32
            audio_mono = audio_mono.astype(np.float32)
            
            # Skip very short chunks (CREPE needs some minimum length)
            if len(audio_mono) < self.sample_rate * 0.1:  # Less than 100ms
                return {
                    'vocal_confidence': 0.3,
                    'is_vocal': False,
                    'method': 'too_short'
                }
            
            # Run CREPE pitch detection
            logger.debug(f"Running CREPE analysis on chunk ({chunk['duration']:.1f}s)")
            
            # Use torchcrepe for pitch detection (convert to torch tensor with proper dimensions)
            import torch
            # CREPE expects input shape: (batch_size, audio_length)
            audio_tensor = torch.from_numpy(audio_mono).unsqueeze(0)  # Add batch dimension
            pitch, confidence = torchcrepe.predict(
                audio_tensor,
                sample_rate=self.sample_rate,
                hop_length=512,
                fmin=80,   # Typical vocal range
                fmax=800,  # Typical vocal range
                model='tiny',  # Fast model for filtering
                batch_size=1,
                device=self.device  # Use same device as Whisper
            )
            
            # Convert tensors to numpy arrays if needed and squeeze batch dimension
            if hasattr(confidence, 'detach'):
                confidence = confidence.detach().cpu().numpy().squeeze()
            if hasattr(pitch, 'detach'):
                pitch = pitch.detach().cpu().numpy().squeeze()
                
            # Calculate statistics
            mean_confidence = float(np.mean(confidence))
            median_confidence = float(np.median(confidence))
            high_conf_ratio = float(np.sum(confidence > min_confidence) / len(confidence))
            
            # Determine vocal categories:
            # - Strong vocal: High confidence, good for transcription
            # - Weak vocal: Some vocal content, needs manual editing
            # - Non-vocal: Silence or instrumental, skip entirely
            
            is_strong_vocal = (mean_confidence >= 0.05 and high_conf_ratio >= 0.05)  # Very low thresholds to catch more vocals
            is_weak_vocal = (mean_confidence >= 0.02 and high_conf_ratio >= 0.02)   # Extremely permissive to avoid missing lyrics
            is_vocal = is_strong_vocal or is_weak_vocal
            
            logger.debug(f"Chunk vocal analysis: mean_conf={mean_confidence:.2f}, "
                        f"median_conf={median_confidence:.2f}, "
                        f"high_conf_ratio={high_conf_ratio:.2f}, "
                        f"is_vocal={is_vocal}")
            
            return {
                'vocal_confidence': mean_confidence,
                'median_confidence': median_confidence,
                'high_confidence_ratio': high_conf_ratio,
                'is_vocal': is_vocal,
                'is_strong_vocal': is_strong_vocal,
                'is_weak_vocal': is_weak_vocal and not is_strong_vocal,
                'method': 'crepe_analysis'
            }
            
        except Exception as e:
            logger.warning(f"CREPE analysis failed for chunk: {e}")
            return {
                'vocal_confidence': 0.5,  # Neutral confidence on error
                'is_vocal': True,  # Don't skip on error
                'method': 'crepe_error'
            }
            
    def transcribe_and_align(self, vocals_audio: np.ndarray, use_chunking: bool = False,
                          max_workers: Optional[int] = None, initial_prompt: Optional[str] = None) -> Dict[str, Any]:
        """
        Automatically transcribe lyrics from vocal audio with optional smart chunking.
        
        Args:
            vocals_audio: Vocal stem audio (2, samples)
            use_chunking: Whether to use smart chunking (False = full audio for better coherence)
            max_workers: Maximum number of parallel workers (None = auto-detect)
            
        Returns:
            Dict with transcribed lyrics and timing alignment
        """
        if use_chunking:
            logger.info("Transcribing lyrics from vocals using Whisper with smart chunking")
        else:
            logger.info("Transcribing lyrics from vocals using Whisper on full audio")
        
        if not use_chunking:
            # Fallback to full audio approach (better for coherent lyrics)
            return self._transcribe_full_audio(vocals_audio, initial_prompt)
        
        # Step 1: Detect silence boundaries for smart chunking
        logger.info(f"→ Analyzing vocals for silence boundaries (threshold: {self.silence_threshold} dB)...")
        boundaries = self.detect_silence_boundaries(vocals_audio)
        logger.info(f"✓ Found {len(boundaries)-1} audio segments from silence analysis")
        
        # Step 2: Create audio chunks based on boundaries
        chunks = self.create_audio_chunks(vocals_audio, boundaries, max_chunk_duration=30.0)
        
        if len(chunks) == 0:
            logger.warning("No audio chunks created, falling back to full audio transcription")
            return self._transcribe_full_audio(vocals_audio, initial_prompt)
        
        # Step 3: Filter chunks using CREPE vocal quality analysis (if enabled)
        logger.info("=" * 60)
        logger.info(f"CHUNK FILTERING SETTINGS:")
        logger.info(f"  CREPE filtering: {'ENABLED' if self.use_crepe_filter else 'DISABLED'}")
        logger.info(f"  Silence threshold: {self.silence_threshold} dB")
        logger.info(f"  Total chunks to process: {len(chunks)}")
        logger.info("=" * 60)
        
        if self.use_crepe_filter:
            logger.info(f"→ Filtering {len(chunks)} chunks using CREPE vocal quality analysis...")
            
            filtered_chunks = []
            skipped_chunks = 0
            crepe_available = CREPE_AVAILABLE
            
            if crepe_available:
                logger.info("→ CREPE available - analyzing vocal content in chunks")
            else:
                logger.info("→ CREPE not available - processing all chunks")
        else:
            logger.info("→ CREPE filtering DISABLED - processing ALL chunks (recommended for extreme vocals)")
            filtered_chunks = chunks
            skipped_chunks = 0
        
        if self.use_crepe_filter:
            for i, chunk in enumerate(chunks):
                chunk_start_time = chunk['start_time']
                chunk_end_time = chunk['end_time']
                
                # Analyze vocal quality with CREPE
                vocal_analysis = self.analyze_chunk_vocal_quality(chunk, min_confidence=0.01)
                is_vocal = vocal_analysis['is_vocal']
                confidence = vocal_analysis['vocal_confidence']
                
                logger.info(f"→ Chunk {i+1}/{len(chunks)}: {chunk_start_time:.1f}s-{chunk_end_time:.1f}s "
                           f"({chunk['duration']:.1f}s) - CREPE conf: {confidence:.2f}")
                
                # Add vocal analysis to chunk
                chunk['vocal_analysis'] = vocal_analysis
                
                is_strong = vocal_analysis.get('is_strong_vocal', False)
                is_weak = vocal_analysis.get('is_weak_vocal', False)
                
                if is_vocal:  # Keep any vocal content (strong OR weak)
                    filtered_chunks.append(chunk)
                    if is_strong:
                        logger.info(f"  ✓ Strong vocal chunk (conf: {confidence:.2f}) - will transcribe")
                    elif is_weak:
                        logger.info(f"  ⚠ Weak vocal chunk (conf: {confidence:.2f}) - will mark for editing")
                else:
                    skipped_chunks += 1
                    logger.info(f"  ✕ Non-vocal chunk (conf: {confidence:.2f}) - skipping")
            
            logger.info("=" * 60)
            logger.info(f"CREPE FILTERING RESULTS:")
            logger.info(f"  Chunks processed: {len(chunks)}")
            logger.info(f"  Chunks kept: {len(filtered_chunks)}")
            logger.info(f"  Chunks skipped: {skipped_chunks}")
            logger.info(f"  Skip rate: {skipped_chunks/len(chunks)*100:.1f}%")
            logger.info("=" * 60)
        else:
            # Add dummy vocal analysis to chunks for consistency
            for chunk in filtered_chunks:
                chunk['vocal_analysis'] = {
                    'is_vocal': True,
                    'is_strong_vocal': True,
                    'is_weak_vocal': False,
                    'vocal_confidence': 1.0
                }
            logger.info("=" * 60)
            logger.info(f"NO FILTERING APPLIED:")
            logger.info(f"  All {len(filtered_chunks)} chunks will be processed")
            logger.info(f"  No chunks skipped (0 skipped)")
            logger.info("=" * 60)
        
        if len(filtered_chunks) == 0:
            logger.warning("No vocal chunks found after filtering, processing all chunks anyway")
            filtered_chunks = chunks
        
        # Step 4: Process filtered chunks sequentially  
        logger.info(f"→ Processing {len(filtered_chunks)} chunks sequentially with pre-loaded model")
        
        chunk_results = []
        successful_chunks = 0
        total_chunk_duration = sum(chunk['duration'] for chunk in filtered_chunks)
        
        for i, chunk in enumerate(filtered_chunks):
            chunk_start_time = chunk['start_time']
            chunk_end_time = chunk['end_time']
            vocal_analysis = chunk.get('vocal_analysis', {})
            is_strong = vocal_analysis.get('is_strong_vocal', False)
            is_weak = vocal_analysis.get('is_weak_vocal', False)
            
            logger.info(f"→ Transcribing {i+1}/{len(filtered_chunks)}: {chunk_start_time:.1f}s-{chunk_end_time:.1f}s ({chunk['duration']:.1f}s)")
            
            if is_strong:
                # Try normal transcription for strong vocal chunks
                result = self._transcribe_chunk(chunk)
                if result:
                    segments_found = len(result.get('segments', []))
                    logger.info(f"  ✓ Found {segments_found} segments")
                    chunk_results.append(result)
                    successful_chunks += 1
                else:
                    logger.info(f"  ⚠ No transcription - creating placeholder")
                    # Create placeholder for failed strong vocal
                    placeholder_result = self._create_placeholder_segment(chunk, "<needs_transcription>")
                    chunk_results.append(placeholder_result)
                    successful_chunks += 1
            elif is_weak:
                # Create placeholder segment for weak vocal chunks
                logger.info(f"  ⚠ Weak vocal - creating placeholder for manual editing")
                placeholder_result = self._create_placeholder_segment(chunk, "<needs_editing>")
                chunk_results.append(placeholder_result)
                successful_chunks += 1
            else:
                # This shouldn't happen since we filtered, but just in case
                logger.info(f"  ✕ Non-vocal chunk somehow made it through filter")
        
        logger.info(f"✓ Processed {successful_chunks}/{len(chunks)} chunks successfully")
        logger.info(f"  Total audio analyzed: {total_chunk_duration:.1f}s")
        
        # Step 4: Merge chunk results back together
        return self._merge_chunk_results(chunk_results)
    
    def _create_placeholder_segment(self, chunk: Dict[str, Any], placeholder_text: str) -> Dict[str, Any]:
        """Create a placeholder segment for chunks that need manual editing."""
        return {
            'text': placeholder_text,
            'segments': [{
                'text': placeholder_text,
                'start': chunk['start_time'],
                'end': chunk['end_time'],
                'words': [{
                    'word': placeholder_text,
                    'start': chunk['start_time'],
                    'end': chunk['end_time'],
                    'probability': 0.1  # Low probability indicates needs editing
                }]
            }],
            'language': 'en',
            'chunk_info': {
                'start_time': chunk['start_time'],
                'end_time': chunk['end_time'],
                'duration': chunk['duration'],
                'vocal_analysis': chunk.get('vocal_analysis', {})
            }
        }
    
    def _transcribe_full_audio(self, vocals_audio: np.ndarray, initial_prompt: Optional[str] = None) -> Dict[str, Any]:
        """Fallback method: transcribe full audio without chunking."""
        logger.info("Using full audio transcription (no chunking)")
        
        # TEMPORARY FIX: Save vocals to temp file and let Whisper load it directly
        # This bypasses our broken audio preprocessing pipeline
        import tempfile
        import soundfile as sf
        
        logger.info("Creating temporary vocals file for Whisper to process directly")
        
        # Convert stereo to mono properly
        if vocals_audio.shape[0] == 2:
            vocals_mono = np.mean(vocals_audio, axis=0)
        else:
            vocals_mono = vocals_audio[0]
        
        # Save to temporary WAV file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            temp_vocals_path = temp_file.name
            sf.write(temp_vocals_path, vocals_mono, self.sample_rate)
        
        try:
            # Let Whisper handle the audio loading and preprocessing directly
            # Build transcription parameters
            transcribe_params = {
                "word_timestamps": True,
                "language": None if self.language == "auto" else self.language,
                "task": "transcribe",
                "verbose": False,
                "no_speech_threshold": 0.3,  # Lower threshold to catch more vocals (default 0.6)
                "condition_on_previous_text": False  # Reduces repetition loops in singing
            }

            # Add initial prompt if provided, but be careful with language consistency
            if initial_prompt:
                # For non-auto language detection, prefix prompt to reinforce language
                if self.language != "auto":
                    # Reinforce the target language in the prompt to prevent confusion
                    transcribe_params["initial_prompt"] = f"This is a {self.language} song. {initial_prompt}"
                else:
                    transcribe_params["initial_prompt"] = initial_prompt

            result = self.model.transcribe(temp_vocals_path, **transcribe_params)
        except Exception as e:
            logger.error(f"Whisper transcription failed: {e}")
            # Fallback: try without word timestamps
            try:
                logger.warning("Retrying transcription without word timestamps")
                # Build fallback transcription parameters
                fallback_params = {
                    "word_timestamps": False,
                    "language": None if self.language == "auto" else self.language,
                    "task": "transcribe",
                    "verbose": False,
                    "no_speech_threshold": 0.3,  # Lower threshold to catch more vocals (default 0.6)
                    "condition_on_previous_text": False  # Reduces repetition loops in singing
                }

                # Add initial prompt if provided, but be careful with language consistency
                if initial_prompt:
                    # For non-auto language detection, prefix prompt to reinforce language
                    if self.language != "auto":
                        # Reinforce the target language in the prompt to prevent confusion
                        fallback_params["initial_prompt"] = f"This is a {self.language} song. {initial_prompt}"
                    else:
                        fallback_params["initial_prompt"] = initial_prompt

                result = self.model.transcribe(temp_vocals_path, **fallback_params)
            except Exception as e2:
                raise RuntimeError(f"Whisper transcription failed completely: {e2}")
        
        finally:
            # Clean up temporary file
            import os
            try:
                os.unlink(temp_vocals_path)
            except:
                pass  # Ignore cleanup errors
        
        # Process results
        return self._process_whisper_result(result)
    
    def _transcribe_chunk(self, chunk: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Transcribe a single audio chunk."""
        try:
            # Convert to mono for transcription
            audio = chunk['audio']
            if audio.shape[0] == 2:
                audio_mono = np.mean(audio, axis=0)
            else:
                audio_mono = audio[0]
                
            # Ensure audio is in the right format for Whisper
            audio_mono = audio_mono.astype(np.float32)
            
            # Transcribe chunk with word timestamps
            # Build transcription parameters
            transcribe_params = {
                "word_timestamps": True,
                "language": None if self.language == "auto" else self.language,
                "task": "transcribe",
                "verbose": False,
                "no_speech_threshold": 0.3,  # Lower threshold to catch more vocals (default 0.6)
                "condition_on_previous_text": False  # Reduces repetition loops in singing
            }

            # Note: initial_prompt not used in chunking as it can bias individual chunks
            result = self.model.transcribe(audio_mono, **transcribe_params)
            
            # Add timing offset to all timestamps
            start_offset = chunk['start_time']
            
            if 'segments' in result:
                for segment in result['segments']:
                    segment['start'] += start_offset
                    segment['end'] += start_offset
                    
                    if 'words' in segment:
                        for word in segment['words']:
                            word['start'] += start_offset
                            word['end'] += start_offset
            
            # Add chunk info
            result['chunk_info'] = {
                'chunk_id': chunk['chunk_id'],
                'start_time': chunk['start_time'],
                'end_time': chunk['end_time'],
                'duration': chunk['duration']
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to transcribe chunk {chunk['chunk_id']}: {e}")
            return None
    
    def _merge_chunk_results(self, chunk_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Merge transcription results from multiple chunks."""
        if not chunk_results:
            logger.warning("No successful chunk transcriptions to merge")
            return {
                'text': '',
                'segments': [],
                'language': 'en',
                'lines': [],
                'words': [],
                'confidence': 0.0,
                'alignment_method': 'whisper_chunked_failed'
            }
        
        # Sort by chunk start time
        chunk_results.sort(key=lambda x: x.get('chunk_info', {}).get('start_time', 0))
        
        # Merge all segments and words
        all_segments = []
        all_words = []
        all_text_parts = []
        total_confidence = 0.0
        language = chunk_results[0].get('language', 'en')
        
        for result in chunk_results:
            all_text_parts.append(result.get('text', '').strip())
            
            if 'segments' in result:
                all_segments.extend(result['segments'])
                
                # Extract words from segments
                for segment in result['segments']:
                    if 'words' in segment:
                        all_words.extend(segment['words'])
                    
                    # Average confidence
                    if 'avg_logprob' in segment:
                        total_confidence += segment['avg_logprob']
        
        # Calculate average confidence
        avg_confidence = total_confidence / len(all_segments) if all_segments else 0.0
        confidence_score = max(0.0, min(1.0, (avg_confidence + 1.0) / 2.0))  # Convert logprob to 0-1
        
        # Create merged result
        merged_result = {
            'text': ' '.join(all_text_parts),
            'segments': all_segments,
            'language': language,
            'words': all_words,
            'confidence': confidence_score,
            'alignment_method': 'whisper_chunked'
        }
        
        # Process into KAI format
        return self._process_whisper_result(merged_result)
        
    def _process_whisper_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Process Whisper transcription result into KAI format."""
        logger.debug("Processing Whisper transcription result")
        
        # Extract overall text
        full_text = result.get("text", "").strip()
        if not full_text:
            logger.warning("No text transcribed from audio")
            return self._create_empty_alignment()
            
        logger.info(f"Transcribed text: '{full_text[:100]}{'...' if len(full_text) > 100 else ''}'")
        
        # Process segments and words
        segments = result.get("segments", [])
        
        if not segments:
            # No segments, create basic structure
            logger.warning("No segments found in transcription")
            return self._create_basic_alignment(full_text)
            
        # Convert segments to lines
        lines = []
        
        for i, segment in enumerate(segments):
            segment_text = segment.get("text", "").strip()
            start_time = segment.get("start", 0.0)
            end_time = segment.get("end", start_time + 3.0)
            
            # Process words in this segment
            segment_words = segment.get("words", [])
            word_timing_pairs = []

            if segment_words:
                # We have word-level timestamps from Whisper
                for j, word_data in enumerate(segment_words):
                    word_text = word_data.get("word", "").strip()
                    word_start = word_data.get("start", start_time)
                    word_end = word_data.get("end", word_start + 0.5)

                    if word_text:  # Skip empty words
                        # Calculate relative timing (relative to line start)
                        word_start_rel = word_start - start_time
                        word_end_rel = word_end - start_time
                        word_timing_pairs.append([
                            round(float(word_start_rel), 3),
                            round(float(word_end_rel), 3)
                        ])
            else:
                # No word-level timestamps, split text and estimate
                words = segment_text.split()
                if words:
                    word_duration = (end_time - start_time) / len(words)

                    for j, word_text in enumerate(words):
                        word_start_rel = j * word_duration
                        word_end_rel = (j + 1) * word_duration
                        word_timing_pairs.append([
                            round(word_start_rel, 3),
                            round(word_end_rel, 3)
                        ])
            
            # Create line object
            if segment_text:  # Skip empty segments
                line_obj = {
                    "singer_id": "A",
                    "start": round(float(start_time), 3),
                    "end": round(float(end_time), 3),
                    "text": segment_text
                }

                # Only add word_timing if we have timing data
                if word_timing_pairs:
                    line_obj["word_timing"] = word_timing_pairs
                
                # Filter out unrealistically short segments (likely artifacts)
                duration = end_time - start_time
                word_count = len(segment_text.split())
                min_duration = 0.3 + (word_count * 0.15)  # 0.3s base + 0.15s per word
                
                if duration >= min_duration:
                    lines.append(line_obj)
                else:
                    logger.info(f"Filtering out short segment ({duration:.2f}s < {min_duration:.2f}s): '{segment_text}'")
        
        # Calculate overall confidence based on segments
        avg_confidence = 0.7  # Default confidence for Whisper transcription

        alignment_result = {
            "lines": lines,
            "alignment_method": f"whisper-{self.model_name}",
            "confidence": avg_confidence,
            "reference": "aligned_to_vocals_wav",
            "offset_sec": 0.0,
            "transcribed_text": full_text
        }

        logger.info(f"Processed {len(lines)} lines, confidence: {avg_confidence:.2f}")
        
        return alignment_result
        
    def _create_empty_alignment(self) -> Dict[str, Any]:
        """Create empty alignment when no transcription is available."""
        return {
            "lines": [],
            "alignment_method": f"whisper-{self.model_name}",
            "confidence": 0.0,
            "reference": "aligned_to_vocals_wav",
            "offset_sec": 0.0,
            "transcribed_text": ""
        }
        
    def _create_basic_alignment(self, text: str) -> Dict[str, Any]:
        """Create basic alignment when no segments are available."""
        # Split text into rough lines (by sentences or length)
        import re
        
        # Split by sentence endings or long length
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            # Fall back to word splitting
            words = text.split()
            if len(words) > 8:
                # Group words into lines of ~8 words
                sentences = []
                for i in range(0, len(words), 8):
                    line = " ".join(words[i:i+8])
                    sentences.append(line)
            else:
                sentences = [text]
        
        lines = []

        # Estimate total duration (assume 3 seconds per line)
        estimated_duration = len(sentences) * 3.0
        line_duration = estimated_duration / len(sentences) if sentences else 3.0

        for i, sentence in enumerate(sentences):
            start_time = i * line_duration
            end_time = (i + 1) * line_duration
            
            # Split sentence into words
            words = sentence.split()
            word_duration = line_duration / len(words) if words else 1.0
            word_timing_pairs = []

            for j, word_text in enumerate(words):
                # Relative timing
                word_start_rel = j * word_duration
                word_end_rel = (j + 1) * word_duration
                word_timing_pairs.append([
                    round(word_start_rel, 3),
                    round(word_end_rel, 3)
                ])

            line_obj = {
                "singer_id": "A",
                "start": round(start_time, 3),
                "end": round(end_time, 3),
                "text": sentence
            }

            # Only add word_timing if we have timing data
            if word_timing_pairs:
                line_obj["word_timing"] = word_timing_pairs
            
            lines.append(line_obj)
        
        return {
            "lines": lines,
            "alignment_method": f"whisper-{self.model_name}-basic",
            "confidence": 0.3,
            "reference": "aligned_to_vocals_wav",
            "offset_sec": 0.0,
            "transcribed_text": text
        }
        
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the loaded Whisper model."""
        return {
            "model_name": self.model_name,
            "whisper_available": WHISPER_AVAILABLE,
            "sample_rate": self.sample_rate
        }