#!/usr/bin/env python3
"""Test script for vocals transcription - takes vocals.mp3 and outputs vocals.json with timings."""

import json
import sys
import logging
import time
from pathlib import Path
from typing import Dict, Any, List

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.kai_pack.transcription import LyricsTranscriber
from src.kai_pack.audio import AudioProcessor

# Set up detailed logging to show progress
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


def test_vocals_transcription(vocals_file: str, output_file: str = None, 
                            whisper_model: str = "tiny", use_chunking: bool = False) -> Dict[str, Any]:
    """
    Test vocals transcription and save results to JSON.
    
    Args:
        vocals_file: Path to vocals.mp3 file
        output_file: Output JSON file (defaults to vocals.json)
        whisper_model: Whisper model to use (tiny, base, small, medium, large-v3)
        use_chunking: Whether to use chunking or full audio transcription
        
    Returns:
        Dict with transcription results
    """
    vocals_path = Path(vocals_file)
    if not vocals_path.exists():
        raise FileNotFoundError(f"Vocals file not found: {vocals_file}")
    
    if output_file is None:
        output_file = vocals_path.with_suffix('.txt')
    
    print("="*80)
    print(f"VOCALS TRANSCRIPTION TEST")
    print("="*80)
    print(f"Input file: {vocals_file}")
    print(f"Whisper model: {whisper_model}")
    print(f"Use chunking: {use_chunking}")
    print(f"Output file: {output_file}")
    print("="*80)
    
    total_start = time.time()
    
    # Initialize components
    logger.info("Initializing audio processor...")
    init_start = time.time()
    audio_processor = AudioProcessor(sample_rate=44100)
    logger.info(f"✓ Audio processor initialized ({time.time() - init_start:.1f}s)")
    
    logger.info(f"Loading Whisper model: {whisper_model}")
    model_start = time.time()
    transcriber = LyricsTranscriber(sample_rate=44100, model_name=whisper_model)
    model_time = time.time() - model_start
    logger.info(f"✓ Whisper model '{whisper_model}' loaded ({model_time:.1f}s)")
    
    if model_time > 30:
        logger.warning(f"⚠ Model loading took {model_time:.1f}s - this is quite slow!")
    elif model_time > 10:
        logger.info(f"ℹ Model loading took {model_time:.1f}s - normal for larger models")
    
    try:
        # Load vocals audio
        logger.info("Loading vocals audio...")
        audio_start = time.time()
        vocals_audio, audio_info = audio_processor.load_and_preprocess(vocals_path)
        audio_time = time.time() - audio_start
        logger.info(f"✓ Vocals loaded: {vocals_audio.shape} at {audio_info['target_sample_rate']} Hz ({audio_time:.1f}s)")
        logger.info(f"ℹ Duration: {audio_info['duration_seconds']:.1f}s")
        
        # Transcribe with specified settings
        logger.info(f"Starting transcription (chunking={use_chunking})...")
        logger.info("⏳ This may take a while depending on audio length and model size...")
        transcription_start = time.time()
        
        # Enable verbose logging for transcription to show progress
        transcription_logger = logging.getLogger('src.kai_pack.transcription')
        transcription_logger.setLevel(logging.INFO)
        
        alignment_data = transcriber.transcribe_and_align(vocals_audio, use_chunking=use_chunking)
        transcription_time = time.time() - transcription_start
        
        logger.info(f"✓ Transcription completed ({transcription_time:.1f}s)")
        
        # Extract results
        lines = alignment_data.get('lines', [])
        words = alignment_data.get('words', [])
        confidence = alignment_data.get('confidence', 0.0)
        language = alignment_data.get('language', 'unknown')
        method = alignment_data.get('alignment_method', 'unknown')
        
        # Performance analysis
        total_time = time.time() - total_start
        
        logger.info("="*60)
        logger.info("TRANSCRIPTION RESULTS:")
        logger.info(f"  - Lines: {len(lines)}")
        logger.info(f"  - Words: {len(words)}")
        logger.info(f"  - Confidence: {confidence:.3f}")
        logger.info(f"  - Language: {language}")
        logger.info(f"  - Method: {method}")
        logger.info("="*60)
        logger.info("PERFORMANCE BREAKDOWN:")
        logger.info(f"  - Model loading: {model_time:.1f}s ({model_time/total_time*100:.1f}%)")
        logger.info(f"  - Audio loading: {audio_time:.1f}s ({audio_time/total_time*100:.1f}%)")
        logger.info(f"  - Transcription: {transcription_time:.1f}s ({transcription_time/total_time*100:.1f}%)")
        logger.info(f"  - Total time: {total_time:.1f}s")
        logger.info(f"  - Processing rate: {audio_info['duration_seconds']/transcription_time:.1f}x realtime")
        logger.info("="*60)
        
        # Create results structure
        results = {
            "input_file": str(vocals_path),
            "whisper_model": whisper_model,
            "use_chunking": use_chunking,
            "audio_info": {
                "duration_seconds": audio_info['duration_seconds'],
                "sample_rate": audio_info['target_sample_rate'],
                "channels": audio_info.get('channels', 2),
                "shape": list(vocals_audio.shape)
            },
            "transcription": {
                "language": language,
                "confidence": confidence,
                "method": method,
                "total_lines": len(lines),
                "total_words": len(words)
            },
            "performance": {
                "model_loading_time": round(model_time, 1),
                "audio_loading_time": round(audio_time, 1), 
                "transcription_time": round(transcription_time, 1),
                "total_time": round(total_time, 1),
                "processing_rate_x_realtime": round(audio_info['duration_seconds']/transcription_time, 1),
                "model_loading_percent": round(model_time/total_time*100, 1),
                "transcription_percent": round(transcription_time/total_time*100, 1)
            },
            "lines": []
        }
        
        # Add line data with timings, duration, and text
        for i, line in enumerate(lines, 1):
            text = line.get('text', '').strip()
            start = line.get('start', 0.0)
            end = line.get('end', 0.0)
            duration = end - start
            singer_id = line.get('singer_id', 'A')
            
            if text:  # Only include non-empty lines
                line_data = {
                    "line_number": i,
                    "text": text,
                    "start": round(start, 2),
                    "end": round(end, 2),
                    "duration": round(duration, 2),
                    "singer_id": singer_id
                }
                results["lines"].append(line_data)
        
        # Calculate coverage stats
        if results["lines"]:
            first_start = min(line["start"] for line in results["lines"])
            last_end = max(line["end"] for line in results["lines"])
            coverage_duration = last_end - first_start
            coverage_percent = (coverage_duration / audio_info['duration_seconds']) * 100
            
            results["coverage"] = {
                "first_vocal": first_start,
                "last_vocal": last_end,
                "vocal_duration": round(coverage_duration, 1),
                "coverage_percent": round(coverage_percent, 1)
            }
        
        # Generate text output in same format as log_kai_lyrics.py
        output_text = []
        output_text.append("="*80)
        output_text.append(f"VOCALS TRANSCRIPTION TEST RESULTS: {vocals_path.name}")
        output_text.append("="*80)
        output_text.append(f"Input: {vocals_file}")
        output_text.append(f"Whisper Model: {whisper_model}")
        output_text.append(f"Chunking: {'Enabled' if use_chunking else 'Disabled'}")
        output_text.append(f"Duration: {audio_info['duration_seconds']:.1f}s")
        output_text.append(f"Transcription Method: whisper-{whisper_model}")
        output_text.append(f"Overall Confidence: {confidence:.3f}")
        output_text.append(f"Lines Found: {len(results['lines'])}")
        output_text.append("="*80)
        output_text.append("PERFORMANCE BREAKDOWN:")
        output_text.append(f"Model Loading: {model_time:.1f}s ({model_time/total_time*100:.1f}%)")
        output_text.append(f"Audio Loading: {audio_time:.1f}s ({audio_time/total_time*100:.1f}%)")
        output_text.append(f"Transcription: {transcription_time:.1f}s ({transcription_time/total_time*100:.1f}%)")
        output_text.append(f"Total Time: {total_time:.1f}s")
        output_text.append(f"Processing Rate: {audio_info['duration_seconds']/transcription_time:.1f}x realtime")
        output_text.append("="*80)
        
        if not results["lines"]:
            output_text.append("No lyrics found in transcription")
        else:
            output_text.append("LYRICS WITH TIMING & DURATION")
            output_text.append("="*80)
            
            for i, line in enumerate(results["lines"], 1):
                output_text.append(f"{i:2d}. [{line['start']:7.2f}s - {line['end']:7.2f}s] ({line['duration']:5.2f}s) ({line['singer_id']}) \"{line['text']}\"")
        
        output_text.append("="*80)
        output_text.append(f"Total segments: {len(results['lines'])}")
        
        if results.get("coverage"):
            cov = results["coverage"]
            output_text.append(f"Vocal coverage: {cov['first_vocal']:.1f}s to {cov['last_vocal']:.1f}s ({cov['coverage_percent']:.1f}% of song)")
        
        output_text.append("="*80)
        
        # Save to text file
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(output_text))
        
        logger.info(f"Results saved to: {output_file}")
        
        # Print to console as well
        print("\n" + '\n'.join(output_text))
        
        return results
        
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_vocals_transcription.py <vocals.mp3> [output.txt] [--model MODEL] [--chunking]")
        print("       python test_vocals_transcription.py vocals.mp3")
        print("       python test_vocals_transcription.py vocals.mp3 --model base --chunking")
        print("       python test_vocals_transcription.py vocals.mp3 results.txt --model large-v3")
        sys.exit(1)
    
    vocals_file = sys.argv[1]
    output_file = None
    whisper_model = "tiny"
    use_chunking = False
    
    # Parse arguments
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == "--model" and i + 1 < len(sys.argv):
            whisper_model = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--chunking":
            use_chunking = True
            i += 1
        elif not output_file and not sys.argv[i].startswith("--"):
            output_file = sys.argv[i]
            i += 1
        else:
            print(f"Unknown argument: {sys.argv[i]}")
            sys.exit(1)
    
    try:
        results = test_vocals_transcription(vocals_file, output_file, whisper_model, use_chunking)
        print(f"\n✅ Test completed successfully!")
        print(f"📄 Results saved to: {output_file or Path(vocals_file).with_suffix('.txt')}")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()