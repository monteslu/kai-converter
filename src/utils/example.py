#!/usr/bin/env python3
"""
Example usage of kai-pack library.
"""

from pathlib import Path
from kai_pack.processor import KaiProcessor

def main():
    """Example of using KaiProcessor directly."""
    
    # Example input files (you'll need to provide these)
    input_audio = Path("example_song.mp3")  # Your audio file
    output_kai = Path("example_output.kai")   # Output KAI file
    
    if not input_audio.exists():
        print(f"Please provide an audio file at: {input_audio}")
        print("Lyrics will be automatically extracted using AI!")
        return
    
    # Create processor
    processor = KaiProcessor(
        sample_rate=44100,
        model_name="htdemucs_ft",  # Use htdemucs for faster processing
        whisper_model="large-v3",  # Best Whisper model for lyrics extraction
        device="cpu",              # Use "cuda" if you have GPU
        verbose=True
    )
    
    # Print model info
    print("Model Information:")
    model_info = processor.get_model_info()
    for component, info in model_info.items():
        print(f"  {component}: {info}")
    print()
    
    try:
        # Process the audio with AI lyrics extraction
        print(f"Processing: {input_audio} -> {output_kai}")
        results = processor.process(
            input_audio=input_audio,
            output_path=output_kai,
            stem_bitrate="160k",
            vocals_bitrate="128k",
            features=["f0", "notes", "tempo"],  # Extract some features
            metadata_overrides={
                "artist": "Example Artist",
                "title": "Example Song"
            }
        )
        
        if results["success"]:
            print("\n✓ Processing completed successfully!")
            print(f"Output file: {results['output_file']}")
            print(f"Processing time: {results['processing_time_seconds']:.1f}s")
            print(f"File size: {results['output_info']['size_bytes']:,} bytes")
            
            stats = results["processing_stats"]
            print(f"\nProcessing Statistics:")
            print(f"  Lines aligned: {stats['lines_aligned']}")
            print(f"  Words aligned: {stats['words_aligned']}")
            print(f"  Features extracted: {stats['features_extracted']}")
            print(f"  Alignment confidence: {stats['alignment_confidence']:.2f}")
            
        else:
            print("✗ Processing failed!")
            
    except Exception as e:
        print(f"✗ Error: {e}")


if __name__ == "__main__":
    main()