#!/usr/bin/env python3
"""Simple test script to extract lyrics from audio using our transcription system."""

import logging
import tempfile
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from kai_pack.audio import AudioProcessor
from kai_pack.separation import StemSeparator
from kai_pack.transcription import LyricsTranscriber

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_transcription(audio_file: str, model: str = "tiny"):
    """Test transcription with minimal processing."""
    try:
        logger.info(f"Testing transcription on {audio_file} with {model} model")
        
        # Initialize components
        audio_processor = AudioProcessor(sample_rate=44100)
        stem_separator = StemSeparator(model_name="htdemucs_ft", device="cpu")
        transcriber = LyricsTranscriber(sample_rate=44100, model_name=model)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Load audio
            logger.info("Loading audio...")
            audio_data, audio_info = audio_processor.load_and_preprocess(Path(audio_file))
            
            # Separate stems (just get vocals)
            logger.info("Separating vocals...")
            stems = stem_separator.separate_stems(audio_data, 44100)
            vocals = stems.get("vocals")
            
            if vocals is None:
                raise ValueError("No vocals found")
            
            # Transcribe vocals
            logger.info("Transcribing vocals...")
            result = transcriber.transcribe_and_align(vocals)
            
            # Print results
            print("\n" + "="*50)
            print("TRANSCRIPTION RESULTS")
            print("="*50)
            print(f"Language detected: {result.get('language', 'unknown')}")
            print(f"Confidence: {result.get('confidence', 0.0):.2f}")
            print(f"Lines found: {len(result.get('lines', []))}")
            print(f"Words found: {len(result.get('words', []))}")
            
            # Print transcribed text
            print("\nTRANSCRIBED LYRICS:")
            print("-" * 30)
            
            lines = result.get('lines', [])
            if lines:
                for i, line in enumerate(lines, 1):
                    text = line.get('text', '').strip()
                    start = line.get('start', 0)
                    end = line.get('end', 0)
                    print(f"[{start:.1f}s-{end:.1f}s] {text}")
            else:
                # Fallback to raw segments if no lines
                segments = result.get('segments', [])
                for segment in segments:
                    text = segment.get('text', '').strip()
                    start = segment.get('start', 0)
                    end = segment.get('end', 0)
                    if text:
                        print(f"[{start:.1f}s-{end:.1f}s] {text}")
            
            # Print raw text if available
            raw_text = result.get('text', '')
            if raw_text:
                print("\nRAW TEXT:")
                print("-" * 30)
                print(raw_text.strip())
            
            print("="*50)
            
    except Exception as e:
        logger.error(f"Transcription test failed: {e}")
        raise

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_transcription.py <audio_file> [model]")
        print("Available models: tiny, base, small, medium, large-v3")
        sys.exit(1)
    
    audio_file = sys.argv[1]
    model = sys.argv[2] if len(sys.argv) > 2 else "tiny"
    
    test_transcription(audio_file, model)