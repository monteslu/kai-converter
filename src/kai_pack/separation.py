"""Audio source separation using Demucs."""

import logging
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable

import torch
import torchaudio
import numpy as np
from demucs.pretrained import get_model
from demucs.apply import apply_model
from demucs.audio import convert_audio
from tqdm import tqdm


logger = logging.getLogger(__name__)


class TqdmCallback(tqdm):
    """Custom tqdm that calls a progress callback."""

    def __init__(self, *args, callback=None, **kwargs):
        self.callback = callback
        super().__init__(*args, **kwargs)

    def update(self, n=1):
        super().update(n)
        if self.callback and self.total:
            # Calculate progress as 0.0 to 1.0
            progress = self.n / self.total
            self.callback(progress)


class StemSeparator:
    """Handles 4-stem audio separation using Demucs."""
    
    def __init__(
        self, 
        model_name: str = "htdemucs_ft", 
        device: Optional[str] = None,
        chunk_size: int = 44100,
        overlap: float = 0.25
    ):
        self.model_name = model_name
        self.chunk_size = chunk_size 
        self.overlap = overlap
        
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
            
        logger.info(f"Using device: {self.device}")
        
        # Load the Demucs model
        try:
            self.model = get_model(model_name)
            self.model.to(self.device)
            self.model.eval()
            logger.info(f"Loaded Demucs model: {model_name}")
        except Exception as e:
            raise RuntimeError(f"Failed to load Demucs model {model_name}: {e}")
            
        # Get source names from model
        self.source_names = self.model.sources
        logger.info(f"Model sources: {self.source_names}")
        
    def separate_stems(
        self,
        audio: np.ndarray,
        sample_rate: int,
        num_stems: int = 2,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> Dict[str, np.ndarray]:
        """
        Separate audio into stems using Demucs.

        Args:
            audio: stereo audio array (2, samples)
            sample_rate: audio sample rate
            num_stems: number of stems to output (2 or 4). Default is 2.
                      2 = vocals + music
                      4 = vocals + drums + bass + other
            progress_callback: Optional callback for progress updates (0.0 to 1.0)

        Returns:
            Dict mapping stem names to audio arrays
        """
        if num_stems not in [2, 4]:
            raise ValueError(f"num_stems must be 2 or 4, got {num_stems}")
            
        logger.info(f"Separating audio into {num_stems} stems (model has {len(self.source_names)} sources)")
        
        # Convert numpy to torch tensor
        audio_tensor = torch.from_numpy(audio).float()
        
        # Convert to model's expected sample rate and format
        audio_tensor = convert_audio(
            audio_tensor.unsqueeze(0),  # Add batch dimension
            sample_rate,
            self.model.samplerate,
            self.model.audio_channels
        )
        audio_tensor = audio_tensor.to(self.device)
        
        # Apply the model with progress callback
        with torch.no_grad():
            if progress_callback:
                # Monkey-patch tqdm module temporarily to capture progress
                import demucs.apply
                import types

                # Save original tqdm module
                original_tqdm_module = demucs.apply.tqdm

                # Create a wrapper function
                def tqdm_wrapper(*args, **kwargs):
                    kwargs['file'] = None  # Disable output to stdout
                    kwargs['disable'] = False
                    return TqdmCallback(*args, callback=progress_callback, **kwargs)

                # Create a fake module with tqdm attribute
                fake_module = types.SimpleNamespace(tqdm=tqdm_wrapper)

                try:
                    # Replace the tqdm module in demucs.apply
                    demucs.apply.tqdm = fake_module
                    sources = apply_model(
                        self.model,
                        audio_tensor,
                        device=self.device,
                        shifts=1,
                        split=True,
                        overlap=self.overlap,
                        progress=True
                    )
                finally:
                    demucs.apply.tqdm = original_tqdm_module
            else:
                sources = apply_model(
                    self.model,
                    audio_tensor,
                    device=self.device,
                    shifts=1,
                    split=True,
                    overlap=self.overlap,
                    progress=True
                )
            
        # Convert back to original sample rate if needed
        if self.model.samplerate != sample_rate:
            sources = convert_audio(
                sources,
                self.model.samplerate,
                sample_rate,
                sources.shape[1]  # Keep same number of channels
            )
            
        # Convert to numpy and create output dict
        stems = {}
        for i, source_name in enumerate(self.source_names):
            stem_audio = sources[0, i].cpu().numpy()  # Remove batch dim, get source i
            
            # Map Demucs source names to KAI-4 standard names
            kai_name = self._map_source_name(source_name)
            stems[kai_name] = stem_audio
            
            logger.debug(f"Extracted stem '{kai_name}' (was '{source_name}'): {stem_audio.shape}")
            
        return stems
        
    def _map_source_name(self, demucs_name: str) -> str:
        """
        Map Demucs source names to KAI-4 standard names.
        
        Demucs typically outputs: ['drums', 'bass', 'other', 'vocals']
        KAI-4 expects: ['vocals', 'drums', 'bass', 'other']
        """
        mapping = {
            "vocals": "vocals",
            "drums": "drums", 
            "bass": "bass",
            "other": "other",
            # Some models might use different names
            "accompaniment": "music",  # For 2-stem models
            "no_vocals": "music"       # Alternative name
        }
        
        return mapping.get(demucs_name.lower(), demucs_name.lower())
        
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the loaded model."""
        return {
            "name": self.model_name,
            "sources": self.source_names,
            "sample_rate": self.model.samplerate,
            "audio_channels": self.model.audio_channels,
            "device": self.device
        }
        
    def save_stems(
        self, 
        stems: Dict[str, np.ndarray], 
        output_dir: Path,
        sample_rate: int,
        file_format: str = "wav"
    ) -> Dict[str, Path]:
        """
        Save separated stems to files.
        
        Args:
            stems: Dict mapping stem names to audio arrays
            output_dir: Directory to save stems
            sample_rate: Sample rate for output files
            file_format: Output format ('wav' or 'mp3')
            
        Returns:
            Dict mapping stem names to output file paths
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        saved_files = {}
        
        for stem_name, audio in stems.items():
            filename = f"{stem_name}.{file_format}"
            output_path = output_dir / filename
            
            # Ensure audio is in correct format (channels, samples)
            if audio.ndim == 1:
                # Mono to stereo
                audio = np.stack([audio, audio])
            elif audio.shape[0] > 2:
                # Multi-channel to stereo
                audio = audio[:2]
                
            # Save using torchaudio for better format support
            audio_tensor = torch.from_numpy(audio).float()
            torchaudio.save(str(output_path), audio_tensor.T, sample_rate)
            
            saved_files[stem_name] = output_path
            logger.debug(f"Saved stem '{stem_name}' to {output_path}")
            
        return saved_files