#!/usr/bin/env python3
"""Basic test of kai-pack functionality without full demucs."""

import os
import sys
from pathlib import Path
import tempfile

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_imports():
    """Test that core components can be imported."""
    try:
        print("Testing imports...")
        from kai_pack.audio import AudioProcessor
        print("✓ AudioProcessor imported")
        
        from kai_pack.metadata import MetadataExtractor
        print("✓ MetadataExtractor imported")
        
        from kai_pack.transcription import LyricsTranscriber
        print("✓ LyricsTranscriber imported")
        
        from kai_pack.song_json import SongJsonGenerator
        print("✓ SongJsonGenerator imported")
        
        from kai_pack.packaging import KaiPackager
        print("✓ KaiPackager imported")
        
        print("All core components imported successfully!")
        return True
        
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False

def test_audio_loading():
    """Test audio loading."""
    try:
        print("\nTesting audio loading...")
        from kai_pack.audio import AudioProcessor
        
        audio_file = Path("06 - Sailing.mp3")
        if not audio_file.exists():
            print(f"✗ Audio file not found: {audio_file}")
            return False
            
        processor = AudioProcessor(sample_rate=44100)
        audio_data, audio_info = processor.load_and_preprocess(audio_file)
        
        print(f"✓ Loaded audio: {audio_info['duration_seconds']:.1f}s, {audio_info['target_sample_rate']}Hz")
        print(f"  Audio shape: {audio_data.shape}")
        return True
        
    except Exception as e:
        print(f"✗ Audio loading failed: {e}")
        return False

def test_metadata_extraction():
    """Test metadata extraction."""
    try:
        print("\nTesting metadata extraction...")
        from kai_pack.metadata import MetadataExtractor
        
        audio_file = Path("06 - Sailing.mp3")
        if not audio_file.exists():
            print(f"✗ Audio file not found: {audio_file}")
            return False
            
        extractor = MetadataExtractor()
        metadata = extractor.extract_metadata(audio_file)
        
        print(f"✓ Extracted metadata:")
        print(f"  Title: {metadata['song']['title']}")
        print(f"  Artist: {metadata['song']['artist']}")
        print(f"  Duration: {metadata['song'].get('duration_sec', 'unknown')}s")
        return True
        
    except Exception as e:
        print(f"✗ Metadata extraction failed: {e}")
        return False

def test_whisper_model_loading():
    """Test that Whisper model can be loaded."""
    try:
        print("\nTesting Whisper model loading...")
        from kai_pack.transcription import LyricsTranscriber
        
        # Use tiny model for testing to avoid memory issues
        transcriber = LyricsTranscriber(model_name="tiny")
        print("✓ Whisper model loaded successfully")
        
        model_info = transcriber.get_model_info()
        print(f"  Model: {model_info['model_name']}")
        return True
        
    except Exception as e:
        print(f"✗ Whisper model loading failed: {e}")
        return False

def main():
    """Run basic tests."""
    print("=== KAI-Pack Basic Test ===")
    
    tests = [
        test_imports,
        test_audio_loading,
        test_metadata_extraction,
        test_whisper_model_loading,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"✗ Test {test.__name__} crashed: {e}")
            results.append(False)
    
    print(f"\n=== Results ===")
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All tests passed!")
        return 0
    else:
        print("❌ Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())