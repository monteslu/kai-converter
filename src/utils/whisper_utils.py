"""
Whisper utilities - Helper functions for loading Whisper models with custom cache
"""

import os
import whisper


def load_whisper_model(model_name, device=None):
    """
    Load a Whisper model with custom cache directory support.

    Reads KAI_WHISPER_CACHE environment variable to determine where to store models.
    If not set, uses Whisper's default cache location.

    Args:
        model_name: Model size (tiny, base, small, medium, large, large-v3, large-v3-turbo)
        device: Device to load model on (cpu, cuda, mps, or None for auto)

    Returns:
        Whisper model instance
    """
    cache_dir = os.environ.get('KAI_WHISPER_CACHE')

    if cache_dir:
        # Use custom cache directory
        return whisper.load_model(model_name, device=device, download_root=cache_dir)
    else:
        # Use default cache
        return whisper.load_model(model_name, device=device)
