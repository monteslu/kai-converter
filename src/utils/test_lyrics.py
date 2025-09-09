#!/usr/bin/env python3
"""Test AI lyrics transcription with the Sailing.mp3 file."""

import sys
from pathlib import Path
import tempfile
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_transcription():
    """Test Whisper transcription on the sailing vocals."""
    try:
        print("=== AI Lyrics Transcription Test ===")
        
        from kai_pack.audio import AudioProcessor
        from kai_pack.transcription import LyricsTranscriber
        from kai_pack.metadata import MetadataExtractor
        
        # Load the audio file
        audio_file = Path("06 - Sailing.mp3")
        if not audio_file.exists():
            print(f"✗ Audio file not found: {audio_file}")
            return False
            
        print(f"Loading: {audio_file}")
        
        # Load and preprocess audio
        audio_processor = AudioProcessor(sample_rate=44100)
        audio_data, audio_info = audio_processor.load_and_preprocess(audio_file)
        print(f"✓ Audio loaded: {audio_info['duration_seconds']:.1f}s")
        
        # Extract metadata
        metadata_extractor = MetadataExtractor()
        metadata = metadata_extractor.extract_metadata(audio_file)
        print(f"✓ Song: '{metadata['song']['title']}' by {metadata['song']['artist']}")
        
        # Use Whisper to transcribe lyrics from the full mix
        # (In real implementation, this would be done on separated vocals)
        print("\n🤖 Running AI lyrics transcription...")
        print("Note: Using full mix instead of separated vocals for this test")
        print("(Real implementation separates vocals first with Demucs)")
        
        # Use tiny model for fast testing
        transcriber = LyricsTranscriber(model_name="tiny")
        
        # Transcribe - this will take a while!
        alignment_data = transcriber.transcribe_and_align(audio_data)
        
        print(f"\n✓ Transcription completed!")
        print(f"  Confidence: {alignment_data.get('confidence', 0.0):.2f}")
        print(f"  Lines: {len(alignment_data.get('lines', []))}")
        print(f"  Words: {len(alignment_data.get('words', []))}")
        
        # Show first few lines
        lines = alignment_data.get('lines', [])
        if lines:
            print("\n📝 First few lyrics lines:")
            for i, line in enumerate(lines[:5]):
                start_time = line.get('start_time', 0.0)
                end_time = line.get('end_time', 0.0)
                text = line.get('text', '').strip()
                print(f"  [{start_time:5.1f}-{end_time:5.1f}s] {text}")
            
            if len(lines) > 5:
                print(f"  ... and {len(lines) - 5} more lines")
        
        # Show first few words with timing
        words = alignment_data.get('words', [])
        if words:
            print("\n🔤 First few words with timing:")
            for i, word in enumerate(words[:10]):
                start_time = word.get('start_time', 0.0)
                end_time = word.get('end_time', 0.0)
                text = word.get('text', '').strip()
                print(f"  [{start_time:5.1f}-{end_time:5.1f}s] '{text}'")
            
            if len(words) > 10:
                print(f"  ... and {len(words) - 10} more words")
        
        # Save results to file for inspection
        results_file = Path("lyrics_test_results.json")
        with open(results_file, 'w') as f:
            json.dump({
                'metadata': metadata,
                'audio_info': audio_info,
                'alignment_data': alignment_data
            }, f, indent=2, default=str)
        
        print(f"\n💾 Full results saved to: {results_file}")
        print("🎉 AI lyrics transcription test completed successfully!")
        
        return True
        
    except Exception as e:
        print(f"✗ Transcription test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run the lyrics transcription test."""
    print("This test will use AI to automatically extract lyrics from the audio.")
    print("It may take several minutes depending on song length and system speed.")
    print("Using tiny Whisper model for faster processing...")
    print()
    
    success = test_transcription()
    
    if success:
        print("\n🚀 The kai-pack utility is ready for full testing!")
        print("Next step: Install demucs for stem separation and run full pipeline.")
        return 0
    else:
        print("\n❌ Test failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())