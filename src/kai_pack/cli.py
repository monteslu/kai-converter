"""Command-line interface for kai-pack."""

import json
import logging
import sys
from pathlib import Path
from typing import Optional, List

import click

from .processor import KaiProcessor


def setup_logging(verbose: bool) -> None:
    """Set up logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    format_str = "%(asctime)s - %(levelname)s - %(message)s"
    
    if verbose:
        # JSON structured logging for verbose mode
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(format_str))
        logging.basicConfig(level=level, handlers=[handler])
    else:
        logging.basicConfig(level=level, format=format_str)


@click.command()
@click.argument("input_audio", type=click.Path(exists=True, path_type=Path))
@click.option("-o", "--output", type=click.Path(path_type=Path), 
              help="Output .kai file path (default: <input_name>.kai)")
@click.option("--gpu/--cpu", default=None, help="Device selection (default: auto)")
@click.option("--sr", default=44100, help="Target sample rate for processing")
@click.option("--model", default="htdemucs_ft", 
              type=click.Choice(["htdemucs_ft", "htdemucs", "mdx_extra", "mdx"]),
              help="Demucs model (htdemucs_ft = best 4-stem quality)")
@click.option("--chunk", default=44100, help="Demucs chunk size (samples)")
@click.option("--overlap", default=0.25, help="Demucs overlap fraction [0..1]")
@click.option("--stem-bitrate", default="160k", help="MP3 bitrate for all stems (vocals/drums/bass/other)")
@click.option("--vocals-bitrate", default=None, help="MP3 bitrate for vocals (defaults to same as --stem-bitrate)")
@click.option("--four-stems", is_flag=True, help="Use 4-stem separation instead of default 2-stem (vocals + music)")
@click.option("--no-analysis", "--skip-features", is_flag=True, help="Skip features/ (faster)")
@click.option("--features", default="f0,notes,tempo,keys,chords,onsets,mfcc",
              help="Comma-separated list of features to extract")
@click.option("--id3-raw/--no-id3-raw", default=True,
              help="Include raw ID3 frames in meta section (default: true)")
@click.option("--title", help="Override title from ID3")
@click.option("--artist", help="Override artist from ID3")
@click.option("--cover", type=click.Path(exists=True, path_type=Path),
              help="Optional cover art")
@click.option("--whisper-model", default="small", 
              type=click.Choice(["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"]),
              help="Whisper model for lyrics transcription (default: small for good speed/accuracy balance)")
@click.option("--language", default="en", help="Language code for transcription (e.g., 'en', 'es', 'fr', 'de', 'ja') or 'auto' for auto-detection")
@click.option("--fix-lyrics", is_flag=True, help="Automatically fix lyrics using OpenAI after processing")
@click.option("--verbose", is_flag=True, help="Verbose logging")
def main(
    input_audio: Path,
    output: Optional[Path],
    gpu: Optional[bool],
    sr: int,
    model: str,
    chunk: int,
    overlap: float,
    stem_bitrate: str,
    vocals_bitrate: str,
    four_stems: bool,
    no_analysis: bool,
    features: str,
    id3_raw: bool,
    title: Optional[str],
    artist: Optional[str],
    cover: Optional[Path],
    whisper_model: str,
    language: str,
    fix_lyrics: bool,
    verbose: bool,
) -> None:
    """Convert INPUT_AUDIO to a .kai karaoke file with AI-generated lyrics."""
    setup_logging(verbose)
    logger = logging.getLogger(__name__)
    
    try:
        # Generate output filename if not provided
        if output is None:
            output = input_audio.with_suffix('.kai')
            logger.info(f"Auto-generating output filename: {output}")
    
        # Parse features list
        features_list = [] if no_analysis else features.split(",")
        
        # Default vocals bitrate to same as stem bitrate if not specified
        if vocals_bitrate is None:
            vocals_bitrate = stem_bitrate
            logger.info(f"Using same bitrate for all stems: {stem_bitrate}")
        
        # Determine device
        device = None
        if gpu is True:
            device = "cuda"
        elif gpu is False:
            device = "cpu"
        
        # Create processor
        processor = KaiProcessor(
            sample_rate=sr,
            model_name=model,
            chunk_size=chunk,
            overlap=overlap,
            device=device,
            whisper_model=whisper_model,
            language=language,
            verbose=verbose
        )
        
        # Override metadata if provided
        overrides = {}
        if title:
            overrides["title"] = title
        if artist:
            overrides["artist"] = artist
            
        # Process the audio
        logger.info(f"Processing {input_audio} -> {output}")
        processor.process(
            input_audio=input_audio,
            output_path=output,
            stem_bitrate=stem_bitrate,
            vocals_bitrate=vocals_bitrate,
            features=features_list,
            metadata_overrides=overrides,
            cover_art=cover,
            include_id3_raw=id3_raw,
            create_music_stem=not four_stems
        )
        
        logger.info(f"Successfully created {output}")
        
        # Auto-fix lyrics if requested
        if fix_lyrics:
            logger.info("Auto-fixing lyrics using OpenAI...")
            try:
                import subprocess
                import os
                
                # Check for OpenAI API key
                if not os.getenv("OPENAI_API_KEY"):
                    logger.error("OPENAI_API_KEY environment variable not set - skipping lyrics fixing")
                else:
                    # Call the fix_lyrics.py script in auto-fetch mode 
                    fix_script = Path(__file__).parent.parent / "utils" / "fix_lyrics.py"
                    
                    result = subprocess.run([
                        "python3", str(fix_script),
                        str(output),  # Input KAI file
                        "--output", str(output)  # Output to same file (replace original)
                    ])  # No capture_output - let it show through
                    
                    if result.returncode == 0:
                        logger.info("✓ Lyrics automatically fixed using OpenAI")
                    else:
                        logger.error("Lyrics fixing failed - see errors above")
                            
            except Exception as fix_error:
                logger.error(f"Failed to auto-fix lyrics: {fix_error}")
        
    except Exception as e:
        logger.error(f"Processing failed: {str(e)}")
        if verbose:
            logger.exception("Full traceback:")
        sys.exit(1)


if __name__ == "__main__":
    main()